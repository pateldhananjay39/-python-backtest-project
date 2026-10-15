"""Pure performance metrics for completed long-only backtests."""

from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from apps.backtest.engine import Trade


class MetricsError(ValueError):
    """Raised when an equity curve cannot be used for metric calculation."""


@dataclass(frozen=True)
class PerformanceMetrics:
    """Defined performance values; undefined values are represented by ``None``."""

    final_equity: float
    total_return: float
    cagr: float | None
    max_drawdown: float
    win_rate: float | None
    profit_factor: float | None
    closed_trades: int


@dataclass(frozen=True)
class BuyAndHoldMetrics:
    """The required return and drawdown comparison values for buy-and-hold."""

    final_equity: float
    total_return: float
    max_drawdown: float


def _validate_equity(equity: pd.Series, start_capital: float) -> None:
    """Reject empty, invalid, or non-finite curves instead of emitting NaN metrics."""
    if not isinstance(equity, pd.Series) or equity.empty:
        raise MetricsError("Equity must be a non-empty pandas Series.")
    if not isinstance(equity.index, pd.DatetimeIndex) or equity.index.tz is None:
        raise MetricsError("Equity must have a timezone-aware DatetimeIndex.")
    if equity.isna().any() or not pd.Series(equity).map(math.isfinite).all() or (equity <= 0).any():
        raise MetricsError("Equity values must be positive and finite.")
    if not isinstance(start_capital, (int, float)) or not math.isfinite(start_capital) or start_capital <= 0:
        raise MetricsError("Start capital must be positive and finite.")


def _max_drawdown(equity: pd.Series) -> float:
    """Return the minimum equity-to-running-peak drawdown as a decimal."""
    return float((equity / equity.cummax() - 1.0).min())


def compute_performance_metrics(
    equity: pd.Series,
    start_capital: float,
    trades: tuple[Trade, ...],
) -> PerformanceMetrics:
    """Compute the specified return, CAGR, drawdown, win-rate, and profit-factor metrics."""
    _validate_equity(equity, start_capital)
    final_equity = float(equity.iloc[-1])
    total_return = final_equity / float(start_capital) - 1.0
    calendar_days = (equity.index[-1] - equity.index[0]).total_seconds() / 86_400
    cagr = None if calendar_days < 30 else (final_equity / float(start_capital)) ** (365.25 / calendar_days) - 1.0
    pnls = [trade.pnl for trade in trades]
    closed_trades = len(pnls)
    win_rate = None if closed_trades == 0 else sum(pnl > 0 for pnl in pnls) / closed_trades
    gross_profit = sum(pnl for pnl in pnls if pnl > 0)
    gross_loss = -sum(pnl for pnl in pnls if pnl < 0)
    profit_factor = None if closed_trades == 0 or gross_loss == 0 else gross_profit / gross_loss
    return PerformanceMetrics(
        final_equity=final_equity,
        total_return=total_return,
        cagr=cagr,
        max_drawdown=_max_drawdown(equity),
        win_rate=win_rate,
        profit_factor=profit_factor,
        closed_trades=closed_trades,
    )


def compute_buy_and_hold_metrics(equity: pd.Series, start_capital: float) -> BuyAndHoldMetrics:
    """Compute the required return and maximum-drawdown buy-and-hold comparison."""
    _validate_equity(equity, start_capital)
    final_equity = float(equity.iloc[-1])
    return BuyAndHoldMetrics(
        final_equity=final_equity,
        total_return=final_equity / float(start_capital) - 1.0,
        max_drawdown=_max_drawdown(equity),
    )
