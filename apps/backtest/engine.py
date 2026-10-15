"""Pure, long-only next-open execution engine."""

from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd


class BacktestError(ValueError):
    """Raised when execution inputs or settings are invalid."""


@dataclass(frozen=True)
class ExecutionSettings:
    """Per-side cost settings and quantity constraint for a backtest."""

    fee_rate: float
    slippage_rate: float
    fractional_quantity: bool

    def __post_init__(self) -> None:
        """Validate non-negative, finite fractional cost settings."""
        for label, value in (("fee rate", self.fee_rate), ("slippage rate", self.slippage_rate)):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise BacktestError(f"{label.capitalize()} must be a finite value greater than or equal to zero.")


@dataclass(frozen=True)
class Trade:
    """A fully closed long trade, with all amounts net of the stated costs."""

    entry_timestamp: pd.Timestamp
    exit_timestamp: pd.Timestamp
    quantity: float
    entry_fill: float
    exit_fill: float
    entry_fee: float
    exit_fee: float
    entry_cost: float
    exit_proceeds: float
    pnl: float
    forced_close: bool


@dataclass(frozen=True)
class BacktestResult:
    """Execution output containing a close-marked equity curve and closed trades."""

    equity: pd.Series
    trades: tuple[Trade, ...]


@dataclass
class _OpenPosition:
    """Internal state retained until a long position is closed."""

    timestamp: pd.Timestamp
    quantity: float
    fill: float
    fee: float
    cost: float


def _validate_inputs(candles: pd.DataFrame, target_position: pd.Series, start_capital: float) -> None:
    """Validate the minimum market and signal invariants required by the engine."""
    if not isinstance(candles, pd.DataFrame) or not {"open", "close"}.issubset(candles.columns):
        raise BacktestError("Candles must be a DataFrame containing open and close columns.")
    if candles.empty:
        raise BacktestError("At least one candle is required.")
    if not isinstance(candles.index, pd.DatetimeIndex) or candles.index.tz is None:
        raise BacktestError("Candles must have a timezone-aware DatetimeIndex.")
    if not candles.index.is_monotonic_increasing or candles.index.has_duplicates:
        raise BacktestError("Candle timestamps must be ascending and unique.")
    if candles[["open", "close"]].isna().any().any() or (candles[["open", "close"]] <= 0).any().any():
        raise BacktestError("Open and close prices must be positive and must not contain NaN values.")
    if not isinstance(target_position, pd.Series) or not target_position.index.equals(candles.index):
        raise BacktestError("Target position must be a Series indexed exactly like the candles.")
    if target_position.isna().any() or not target_position.isin((0, 1)).all():
        raise BacktestError("Target position must contain only 0 or 1 values.")
    if not isinstance(start_capital, (int, float)) or not math.isfinite(start_capital) or start_capital <= 0:
        raise BacktestError("Start capital must be a finite value greater than zero.")


def _buy_quantity(cash: float, fill: float, settings: ExecutionSettings) -> float:
    """Calculate the maximum affordable quantity including the entry fee."""
    quantity = cash / (fill * (1.0 + settings.fee_rate))
    return quantity if settings.fractional_quantity else float(math.floor(quantity))


def _close_trade(position: _OpenPosition, timestamp: pd.Timestamp, fill: float, settings: ExecutionSettings, forced_close: bool) -> Trade:
    """Create one closed-trade record from an open position and an exit fill."""
    gross_proceeds = position.quantity * fill
    exit_fee = gross_proceeds * settings.fee_rate
    exit_proceeds = gross_proceeds - exit_fee
    return Trade(
        entry_timestamp=position.timestamp,
        exit_timestamp=timestamp,
        quantity=position.quantity,
        entry_fill=position.fill,
        exit_fill=fill,
        entry_fee=position.fee,
        exit_fee=exit_fee,
        entry_cost=position.cost,
        exit_proceeds=exit_proceeds,
        pnl=exit_proceeds - position.cost,
        forced_close=forced_close,
    )


def run_backtest(
    candles: pd.DataFrame,
    target_position: pd.Series,
    start_capital: float,
    settings: ExecutionSettings,
) -> BacktestResult:
    """Execute a 0/1 target at the following candle's open and mark equity at close.

    A target computed at the final candle is deliberately never executed. Any
    remaining position is closed at that last candle's close with the normal exit
    fee and is marked as a forced close; no exit slippage is applied because its
    stated fill is the final close.
    """
    _validate_inputs(candles, target_position, start_capital)

    cash = float(start_capital)
    position: _OpenPosition | None = None
    trades: list[Trade] = []
    equity_values: list[float] = []
    for row_number, (timestamp, row) in enumerate(candles.iterrows()):
        if row_number > 0:
            desired_position = int(target_position.iloc[row_number - 1])
            if desired_position == 1 and position is None:
                entry_fill = float(row["open"]) * (1.0 + settings.slippage_rate)
                quantity = _buy_quantity(cash, entry_fill, settings)
                if quantity > 0:
                    entry_notional = quantity * entry_fill
                    entry_fee = entry_notional * settings.fee_rate
                    entry_cost = entry_notional + entry_fee
                    cash = 0.0 if settings.fractional_quantity else cash - entry_cost
                    position = _OpenPosition(timestamp, quantity, entry_fill, entry_fee, entry_cost)
            elif desired_position == 0 and position is not None:
                exit_fill = float(row["open"]) * (1.0 - settings.slippage_rate)
                trade = _close_trade(position, timestamp, exit_fill, settings, forced_close=False)
                cash += trade.exit_proceeds
                trades.append(trade)
                position = None

        close = float(row["close"])
        equity_values.append(cash + (position.quantity * close if position is not None else 0.0))

    if position is not None:
        final_timestamp = candles.index[-1]
        forced_trade = _close_trade(position, final_timestamp, float(candles["close"].iloc[-1]), settings, forced_close=True)
        cash += forced_trade.exit_proceeds
        trades.append(forced_trade)
        equity_values[-1] = cash

    equity = pd.Series(equity_values, index=candles.index, name="equity", dtype="float64")
    return BacktestResult(equity=equity, trades=tuple(trades))


def run_buy_and_hold(
    candles: pd.DataFrame,
    start_capital: float,
    settings: ExecutionSettings,
    entry_timestamp: pd.Timestamp,
) -> BacktestResult:
    """Buy at the strategy's first entry open and close at the final candle close.

    The entry timestamp comes from the strategy result, so this comparison uses
    the same observable entry open, capital, and cost settings. The close at the
    final candle is recorded as a forced close with the normal exit fee.
    """
    empty_target = pd.Series(0, index=candles.index, dtype="int64")
    _validate_inputs(candles, empty_target, start_capital)
    if entry_timestamp not in candles.index:
        raise BacktestError("Buy-and-hold entry timestamp must be a candle timestamp.")

    entry_location = candles.index.get_loc(entry_timestamp)
    if not isinstance(entry_location, int):
        raise BacktestError("Buy-and-hold entry timestamp must identify exactly one candle.")
    cash = float(start_capital)
    entry_fill = float(candles["open"].iloc[entry_location]) * (1.0 + settings.slippage_rate)
    quantity = _buy_quantity(cash, entry_fill, settings)
    if quantity == 0:
        equity = pd.Series(cash, index=candles.index, name="equity", dtype="float64")
        return BacktestResult(equity=equity, trades=())

    entry_notional = quantity * entry_fill
    entry_fee = entry_notional * settings.fee_rate
    entry_cost = entry_notional + entry_fee
    cash = 0.0 if settings.fractional_quantity else cash - entry_cost
    position = _OpenPosition(entry_timestamp, quantity, entry_fill, entry_fee, entry_cost)
    equity_values: list[float] = []
    for row_number, (_, row) in enumerate(candles.iterrows()):
        equity_values.append(
            float(start_capital) if row_number < entry_location else cash + quantity * float(row["close"])
        )

    final_timestamp = candles.index[-1]
    exit_trade = _close_trade(position, final_timestamp, float(candles["close"].iloc[-1]), settings, forced_close=True)
    cash += exit_trade.exit_proceeds
    equity_values[-1] = cash
    equity = pd.Series(equity_values, index=candles.index, name="equity", dtype="float64")
    return BacktestResult(equity=equity, trades=(exit_trade,))
