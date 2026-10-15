"""Thin Django views that orchestrate pure market and backtest functions."""

from __future__ import annotations

import csv

import pandas as pd
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import render

from apps.backtest.engine import BacktestResult, ExecutionSettings, run_backtest, run_buy_and_hold
from apps.backtest.metrics import compute_buy_and_hold_metrics, compute_performance_metrics
from apps.backtest.strategies import EmaCrossoverParameters, ema_crossover_position
from apps.dashboard.charts import build_candlestick_chart, build_equity_chart
from apps.dashboard.forms import BacktestForm
from apps.market.data import GapReport, INDIA_SYMBOLS, MarketDataError, build_gap_report, download_market_data


DISCLAIMER = "Educational tool, not financial advice. Past performance does not guarantee future results."
SOURCE_WARNING = "yfinance is not exchange-grade; spot-check 5 candles against TradingView or the exchange."


def _format_metric(value: float | None, percent: bool = False) -> str:
    """Format a defined metric for display, or return the required N/A label."""
    if value is None:
        return "N/A"
    return f"{value:.2%}" if percent else f"{value:,.2f}"


def _trade_rows(result_trades: tuple[object, ...], timezone: str) -> list[dict[str, object]]:
    """Convert engine trade records to explicitly formatted template rows."""
    rows: list[dict[str, object]] = []
    for trade in result_trades:
        rows.append(
            {
                "entry_timestamp": trade.entry_timestamp.tz_convert(timezone).strftime("%Y-%m-%d %H:%M %Z"),
                "exit_timestamp": trade.exit_timestamp.tz_convert(timezone).strftime("%Y-%m-%d %H:%M %Z"),
                "quantity": f"{trade.quantity:.8f}",
                "entry_fill": f"{trade.entry_fill:.4f}",
                "exit_fill": f"{trade.exit_fill:.4f}",
                "pnl": f"{trade.pnl:,.2f}",
                "forced_close": trade.forced_close,
            }
        )
    return rows


def _execute_backtest(cleaned_data: dict[str, object]) -> tuple[pd.DataFrame, GapReport, BacktestResult, ExecutionSettings]:
    """Download validated candles and run the pure strategy/execution pipeline once."""
    symbol = str(cleaned_data["symbol"])
    candles = download_market_data(
        symbol,
        str(cleaned_data["timeframe"]),
        cleaned_data["start_date"],
        cleaned_data["end_date"],
    )
    gap_report = build_gap_report(candles, symbol, str(cleaned_data["timeframe"]))
    target = ema_crossover_position(
        candles,
        EmaCrossoverParameters(int(cleaned_data["fast_period"]), int(cleaned_data["slow_period"])),
    )
    settings = ExecutionSettings(
        fee_rate=float(cleaned_data["fee_percent"]) / 100,
        slippage_rate=float(cleaned_data["slippage_percent"]) / 100,
        fractional_quantity=symbol == "BTC-USD",
    )
    result = run_backtest(candles, target, float(cleaned_data["start_capital"]), settings)
    return candles, gap_report, result, settings


def backtest_dashboard(request: object) -> object:
    """Render the input form and, for a valid POST, one complete backtest result."""
    form = BacktestForm(request.POST or None)
    context: dict[str, object] = {"form": form, "disclaimer": DISCLAIMER}
    if request.method != "POST" or not form.is_valid():
        return render(request, "dashboard/backtest.html", context)

    cleaned = form.cleaned_data
    symbol = str(cleaned["symbol"])
    timezone = "Asia/Kolkata" if symbol in INDIA_SYMBOLS else "UTC"
    try:
        candles, gap_report, result, settings = _execute_backtest(cleaned)
        metrics = compute_performance_metrics(result.equity, float(cleaned["start_capital"]), result.trades)
        buy_and_hold_equity = None
        buy_and_hold_metrics = None
        if result.trades:
            buy_and_hold = run_buy_and_hold(candles, float(cleaned["start_capital"]), settings, result.trades[0].entry_timestamp)
            buy_and_hold_equity = buy_and_hold.equity
            buy_and_hold_metrics = compute_buy_and_hold_metrics(buy_and_hold.equity, float(cleaned["start_capital"]))
    except (MarketDataError, ValueError) as exc:
        form.add_error(None, str(exc))
        return render(request, "dashboard/backtest.html", context)

    context.update(
        {
            "has_results": True,
            "source_warning": SOURCE_WARNING,
            "india_adjustment_note": symbol in INDIA_SYMBOLS,
            "timezone": timezone,
            "data_summary": {
                "first_timestamp": candles.index[0].tz_convert(timezone).strftime("%Y-%m-%d %H:%M %Z"),
                "last_timestamp": candles.index[-1].tz_convert(timezone).strftime("%Y-%m-%d %H:%M %Z"),
                "candle_count": len(candles),
                "unexpected_gaps": len(gap_report.gaps),
            },
            "metrics": {
                "final_equity": _format_metric(metrics.final_equity),
                "total_return": _format_metric(metrics.total_return, percent=True),
                "cagr": _format_metric(metrics.cagr, percent=True),
                "max_drawdown": _format_metric(metrics.max_drawdown, percent=True),
                "win_rate": _format_metric(metrics.win_rate, percent=True),
                "profit_factor": _format_metric(metrics.profit_factor),
                "closed_trades": metrics.closed_trades,
            },
            "buy_and_hold_metrics": None
            if buy_and_hold_metrics is None
            else {
                "total_return": _format_metric(buy_and_hold_metrics.total_return, percent=True),
                "max_drawdown": _format_metric(buy_and_hold_metrics.max_drawdown, percent=True),
            },
            "trade_rows": _trade_rows(result.trades, timezone),
            "candlestick_chart": build_candlestick_chart(candles, result.trades, timezone),
            "equity_chart": build_equity_chart(result.equity, buy_and_hold_equity),
        }
    )
    return render(request, "dashboard/backtest.html", context)


def export_trades_csv(request: object) -> HttpResponse:
    """Return the closed trades for a valid submitted configuration as a CSV download."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    form = BacktestForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("CSV export requires valid backtest inputs.")
    try:
        _, _, result, _ = _execute_backtest(form.cleaned_data)
    except (MarketDataError, ValueError) as exc:
        return HttpResponseBadRequest(str(exc))

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="trades.csv"'
    writer = csv.writer(response)
    writer.writerow(
        [
            "entry_timestamp_utc",
            "exit_timestamp_utc",
            "quantity",
            "entry_fill",
            "exit_fill",
            "entry_fee",
            "exit_fee",
            "entry_cost",
            "exit_proceeds",
            "pnl",
            "forced_close",
        ]
    )
    for trade in result.trades:
        writer.writerow(
            [
                trade.entry_timestamp.isoformat(),
                trade.exit_timestamp.isoformat(),
                trade.quantity,
                trade.entry_fill,
                trade.exit_fill,
                trade.entry_fee,
                trade.exit_fee,
                trade.entry_cost,
                trade.exit_proceeds,
                trade.pnl,
                trade.forced_close,
            ]
        )
    return response
