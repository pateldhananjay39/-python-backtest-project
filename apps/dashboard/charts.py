"""Plotly figure builders for the dashboard presentation layer."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from apps.backtest.engine import Trade


def build_candlestick_chart(candles: pd.DataFrame, trades: tuple[Trade, ...], timezone: str) -> str:
    """Return an HTML candlestick chart with markers for executed trade fills."""
    figure = go.Figure(
        data=[
            go.Candlestick(
                x=candles.index,
                open=candles["open"],
                high=candles["high"],
                low=candles["low"],
                close=candles["close"],
                name="Price",
            )
        ]
    )
    if trades:
        figure.add_trace(
            go.Scatter(
                x=[trade.entry_timestamp for trade in trades],
                y=[trade.entry_fill for trade in trades],
                mode="markers",
                marker={"color": "#198754", "symbol": "triangle-up", "size": 10},
                name="Buy fill",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[trade.exit_timestamp for trade in trades],
                y=[trade.exit_fill for trade in trades],
                mode="markers",
                marker={"color": "#dc3545", "symbol": "triangle-down", "size": 10},
                name="Sell fill",
            )
        )
    figure.update_layout(
        title="Price and executed fills",
        xaxis_title=f"Timestamp ({timezone})",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        height=500,
        margin={"l": 50, "r": 25, "t": 55, "b": 45},
    )
    return figure.to_html(full_html=False, include_plotlyjs="cdn", config={"responsive": True})


def build_equity_chart(strategy_equity: pd.Series, buy_and_hold_equity: pd.Series | None) -> str:
    """Return an HTML equity chart, adding buy-and-hold only when it is defined."""
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=strategy_equity.index, y=strategy_equity, mode="lines", name="EMA crossover"))
    if buy_and_hold_equity is not None:
        figure.add_trace(go.Scatter(x=buy_and_hold_equity.index, y=buy_and_hold_equity, mode="lines", name="Buy and hold"))
    figure.update_layout(
        title="Equity curve comparison",
        xaxis_title="Timestamp",
        yaxis_title="Equity",
        template="plotly_white",
        height=400,
        margin={"l": 50, "r": 25, "t": 55, "b": 45},
    )
    return figure.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True})
