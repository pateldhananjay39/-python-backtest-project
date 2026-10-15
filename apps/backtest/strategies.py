"""Long-only trading strategies that use only current and past candles."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


class StrategyError(ValueError):
    """Raised when strategy inputs or parameters are invalid."""


@dataclass(frozen=True)
class EmaCrossoverParameters:
    """Parameters for the long-only EMA crossover strategy."""

    fast_period: int
    slow_period: int

    def __post_init__(self) -> None:
        """Require positive periods with the fast EMA shorter than the slow EMA."""
        if not isinstance(self.fast_period, int) or not isinstance(self.slow_period, int):
            raise StrategyError("EMA periods must be integers.")
        if self.fast_period <= 0 or self.slow_period <= 0:
            raise StrategyError("EMA periods must be positive.")
        if self.fast_period >= self.slow_period:
            raise StrategyError("The fast EMA period must be less than the slow EMA period.")


def ema_crossover_position(candles: pd.DataFrame, parameters: EmaCrossoverParameters) -> pd.Series:
    """Return a 0/1 long target based on the current and prior closing prices.

    EMA values use pandas' recursive ``ewm(span=n, adjust=False)`` definition.
    The target remains zero during the slow-EMA warm-up; it never uses a future
    candle and is intended to be executed by the engine at the next candle open.
    """
    if not isinstance(candles, pd.DataFrame) or "close" not in candles.columns:
        raise StrategyError("Candles must be a DataFrame containing a close column.")
    if candles["close"].isna().any():
        raise StrategyError("Close prices must not contain NaN values.")

    close = candles["close"].astype(float)
    fast_ema = close.ewm(span=parameters.fast_period, adjust=False).mean()
    slow_ema = close.ewm(span=parameters.slow_period, adjust=False).mean()
    position = (fast_ema > slow_ema).astype("int64")
    position.iloc[: parameters.slow_period - 1] = 0
    return position.rename("target_position")
