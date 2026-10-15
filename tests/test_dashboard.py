"""Tests for dashboard input validation and thin result rendering."""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from django.test import Client

from apps.dashboard.charts import build_candlestick_chart, build_equity_chart
from apps.dashboard.forms import BacktestForm
from apps.market.data import GapReport


def dashboard_candles() -> pd.DataFrame:
    """Return synthetic daily OHLCV data sufficient for a dashboard test run."""
    index = pd.date_range("2025-01-01T00:00:00Z", periods=40, freq="D")
    close = [100.0 + (position % 8) for position in range(len(index))]
    return pd.DataFrame(
        {"open": [100.0] * len(index), "high": [max(value, 100.0) + 1 for value in close],
         "low": [min(value, 100.0) - 1 for value in close], "close": close, "volume": [1.0] * len(index)},
        index=index,
    )


def test_form_rejects_invalid_date_and_ema_pairs() -> None:
    """The form independently validates both user-controlled strategy constraints."""
    form = BacktestForm(data={
        "symbol": "BTC-USD", "timeframe": "1d", "start_date": "2025-02-01", "end_date": "2025-01-01",
        "fast_period": 21, "slow_period": 9, "fee_percent": 0.1, "slippage_percent": 0.05, "start_capital": 1000,
    })
    assert not form.is_valid()
    assert "end_date" in form.errors and "fast_period" in form.errors


@pytest.mark.django_db
def test_dashboard_get_has_required_disclaimer() -> None:
    """Every rendered dashboard page includes the mandatory educational disclaimer."""
    response = Client().get("/")
    assert response.status_code == 200
    assert b"Educational tool, not financial advice" in response.content


@pytest.mark.django_db
def test_dashboard_post_renders_data_summary_and_charts(monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful POST delegates to pure functions and renders its result page."""
    candles = dashboard_candles()
    monkeypatch.setattr("apps.dashboard.views.download_market_data", lambda *args: candles)
    monkeypatch.setattr(
        "apps.dashboard.views.build_gap_report",
        lambda *args: GapReport(expected_interval=pd.Timedelta(days=1), gaps=()),
    )
    response = Client().post("/", {
        "symbol": "BTC-USD", "timeframe": "1d", "start_date": "2025-01-01", "end_date": "2025-02-15",
        "fast_period": 2, "slow_period": 3, "fee_percent": 0.1, "slippage_percent": 0.05, "start_capital": 1000,
    })
    assert response.status_code == 200
    assert b"Data summary" in response.content
    assert b"Candle count: 40" in response.content
    assert b"Equity curve comparison" in response.content


@pytest.mark.django_db
def test_csv_export_has_trade_headers_and_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """CSV export reruns validated inputs and serializes closed trades in UTC."""
    candles = dashboard_candles()
    monkeypatch.setattr("apps.dashboard.views.download_market_data", lambda *args: candles)
    monkeypatch.setattr(
        "apps.dashboard.views.build_gap_report",
        lambda *args: GapReport(expected_interval=pd.Timedelta(days=1), gaps=()),
    )
    response = Client().post("/export-trades/", {
        "symbol": "BTC-USD", "timeframe": "1d", "start_date": "2025-01-01", "end_date": "2025-02-15",
        "fast_period": 2, "slow_period": 3, "fee_percent": 0.1, "slippage_percent": 0.05, "start_capital": 1000,
    })
    csv_text = response.content.decode("utf-8")
    assert response.status_code == 200
    assert response["Content-Disposition"] == 'attachment; filename="trades.csv"'
    assert csv_text.startswith("entry_timestamp_utc,exit_timestamp_utc,quantity")
    assert len(csv_text.splitlines()) > 1


@pytest.mark.django_db
def test_csv_export_rejects_invalid_form() -> None:
    """Export does not accept incomplete or invalid inputs outside the normal form flow."""
    response = Client().post("/export-trades/", {"symbol": "BTC-USD"})
    assert response.status_code == 400


def test_chart_builders_return_plotly_html() -> None:
    """Both chart builders return embeddable HTML with the requested chart titles."""
    candles = dashboard_candles().iloc[:4]
    candle_html = build_candlestick_chart(candles, (), "UTC")
    equity_html = build_equity_chart(pd.Series([100.0] * 4, index=candles.index), None)
    assert "Price and executed fills" in candle_html
    assert "Equity curve comparison" in equity_html
