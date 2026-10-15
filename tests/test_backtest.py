"""Synthetic, known-answer tests for the pure strategy, engine, and metrics."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from apps.backtest.engine import ExecutionSettings, Trade, run_backtest, run_buy_and_hold
from apps.backtest.metrics import compute_buy_and_hold_metrics, compute_performance_metrics
from apps.backtest.strategies import EmaCrossoverParameters, ema_crossover_position


def synthetic_candles(periods: int = 12) -> pd.DataFrame:
    """Return explicitly synthetic, valid candles with constant opens for simple arithmetic."""
    index = pd.date_range("2025-01-01T00:00:00Z", periods=periods, freq="h")
    closes = [100, 100, 101, 102, 100, 99, 98, 100, 101, 102, 100, 99][:periods]
    opens = [100.0] * periods
    return pd.DataFrame(
        {"open": opens, "high": [max(value, 100.0) + 1 for value in closes],
         "low": [min(value, 100.0) - 1 for value in closes], "close": closes},
        index=index,
        dtype="float64",
    )


def target_for_two_trades(index: pd.DatetimeIndex) -> pd.Series:
    """Return a hand-specified target that enters at candles 3 and 8, then exits."""
    return pd.Series([0, 0, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0][:len(index)], index=index, dtype="int64")


def test_known_answer_trade_list_fees_and_final_equity() -> None:
    """Check the hand-calculated two-trade result, including both entry and exit fees.

    With $1,000, $100 opens, and 1% fees, each round trip multiplies cash by
    0.99 / 1.01.  Therefore final equity is 1000 * (0.99 / 1.01) ** 2.
    The target at candle 2 enters at candle 3's open; the target at candle 4
    exits at candle 5's open, and the second trade uses candles 8 and 11.
    """
    candles = synthetic_candles()
    result = run_backtest(candles, target_for_two_trades(candles.index), 1000.0, ExecutionSettings(0.01, 0.0, True))

    assert [(trade.entry_timestamp, trade.exit_timestamp) for trade in result.trades] == [
        (candles.index[3], candles.index[5]),
        (candles.index[8], candles.index[11]),
    ]
    assert all(trade.entry_fee > 0 and trade.exit_fee > 0 for trade in result.trades)
    assert result.equity.iloc[-1] == pytest.approx(1000.0 * (0.99 / 1.01) ** 2)


def test_ema_uses_recursive_adjust_false_values_and_warmup() -> None:
    """Match EMA values independently by recurrence: e_t = alpha*x_t + (1-alpha)*e_(t-1)."""
    candles = synthetic_candles(6)
    parameters = EmaCrossoverParameters(fast_period=2, slow_period=3)
    result = ema_crossover_position(candles, parameters)
    close = list(candles["close"])
    fast = [close[0]]
    slow = [close[0]]
    for value in close[1:]:
        fast.append((2 / 3) * value + (1 / 3) * fast[-1])
        slow.append(0.5 * value + 0.5 * slow[-1])
    expected = [0 if position < 2 else int(fast[position] > slow[position]) for position in range(len(close))]
    assert result.tolist() == expected


def test_execution_uses_the_following_open_with_slippage() -> None:
    """Every entry/exit fill is the following candle open adjusted by stated slippage."""
    candles = synthetic_candles()
    settings = ExecutionSettings(0.0, 0.005, True)
    result = run_backtest(candles, target_for_two_trades(candles.index), 1000.0, settings)
    for trade in result.trades:
        assert trade.entry_fill == pytest.approx(candles.loc[trade.entry_timestamp, "open"] * 1.005)
        assert trade.exit_fill == pytest.approx(candles.loc[trade.exit_timestamp, "open"] * 0.995)


def test_last_candle_signal_creates_no_trade() -> None:
    """An entry target only on the final close cannot execute because no next open exists."""
    candles = synthetic_candles(5)
    target = pd.Series([0, 0, 0, 0, 1], index=candles.index)
    assert not run_backtest(candles, target, 1000.0, ExecutionSettings(0.0, 0.0, True)).trades


def test_no_lookahead_when_data_is_truncated_after_a_closed_trade() -> None:
    """Full and truncated runs agree exactly through a timestamp with no open position."""
    candles = synthetic_candles()
    target = target_for_two_trades(candles.index)
    full = run_backtest(candles, target, 1000.0, ExecutionSettings(0.01, 0.0, True))
    truncated = run_backtest(candles.iloc[:6], target.iloc[:6], 1000.0, ExecutionSettings(0.01, 0.0, True))
    pd.testing.assert_series_equal(full.equity.iloc[:6], truncated.equity)
    assert tuple(trade for trade in full.trades if trade.exit_timestamp <= candles.index[5]) == truncated.trades


def test_costs_reduce_final_equity() -> None:
    """The same trades produce less final equity when fees and slippage are enabled."""
    candles = synthetic_candles()
    target = target_for_two_trades(candles.index)
    without_costs = run_backtest(candles, target, 1000.0, ExecutionSettings(0.0, 0.0, True))
    with_costs = run_backtest(candles, target, 1000.0, ExecutionSettings(0.01, 0.005, True))
    assert with_costs.equity.iloc[-1] < without_costs.equity.iloc[-1]


def test_flat_strategy_preserves_starting_capital_exactly() -> None:
    """A zero target cannot create trades or change equity."""
    candles = synthetic_candles()
    result = run_backtest(candles, pd.Series(0, index=candles.index), 1234.56, ExecutionSettings(0.01, 0.005, True))
    assert not result.trades
    assert (result.equity == 1234.56).all()


def test_equity_reconciles_to_sum_of_closed_trade_pnl() -> None:
    """Forced closing ensures final equity equals initial cash plus every trade P&L."""
    candles = synthetic_candles(10)
    target = pd.Series([0, 0, 1, 1, 1, 1, 1, 1, 1, 1], index=candles.index)
    result = run_backtest(candles, target, 1000.0, ExecutionSettings(0.01, 0.005, True))
    assert result.trades[-1].forced_close is True
    assert result.equity.iloc[-1] == pytest.approx(1000.0 + sum(trade.pnl for trade in result.trades), abs=1e-6)


def test_buy_and_hold_uses_the_strategy_first_entry_open_and_costs() -> None:
    """The comparison enters at the first strategy fill and exits at the final close."""
    candles = synthetic_candles()
    settings = ExecutionSettings(0.01, 0.005, True)
    strategy = run_backtest(candles, target_for_two_trades(candles.index), 1000.0, settings)
    result = run_buy_and_hold(candles, 1000.0, settings, strategy.trades[0].entry_timestamp)
    trade = result.trades[0]
    assert trade.entry_timestamp == strategy.trades[0].entry_timestamp
    assert trade.entry_fill == pytest.approx(candles.loc[trade.entry_timestamp, "open"] * 1.005)
    assert trade.exit_fill == candles["close"].iloc[-1]
    assert result.equity.iloc[-1] == pytest.approx(1000.0 + trade.pnl)


def make_trade(pnl: float) -> Trade:
    """Create a synthetic closed trade for metrics-only edge-case tests."""
    timestamp = pd.Timestamp("2025-01-01T00:00:00Z")
    return Trade(timestamp, timestamp, 1.0, 100.0, 100.0, 0.0, 0.0, 100.0, 100.0 + pnl, pnl, False)


def test_metrics_edge_cases_have_no_nan_or_division_errors() -> None:
    """Exercise zero, one, and all-losing trade cases using a finite synthetic curve."""
    index = pd.date_range("2025-01-01T00:00:00Z", periods=31, freq="D")
    equity = pd.Series([100.0] * 30 + [90.0], index=index)
    zero = compute_performance_metrics(equity, 100.0, ())
    one = compute_performance_metrics(equity, 100.0, (make_trade(5.0),))
    losses = compute_performance_metrics(equity, 100.0, (make_trade(-5.0), make_trade(-2.0)))
    assert zero.win_rate is None and zero.profit_factor is None
    assert one.win_rate == 1.0 and one.profit_factor is None
    assert losses.win_rate == 0.0 and losses.profit_factor == 0.0
    assert all(math.isfinite(value) for value in (zero.total_return, zero.cagr, zero.max_drawdown, losses.profit_factor))
    buy_and_hold = compute_buy_and_hold_metrics(equity, 100.0)
    assert buy_and_hold.total_return == pytest.approx(-0.1)
