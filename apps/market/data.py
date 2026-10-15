"""Pure market-data download, validation, and gap-report functions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import pandas as pd
import yfinance as yf


Symbol = Literal["BTC-USD", "RELIANCE.NS", "^NSEI"]
Timeframe = Literal["1d", "1h"]

ALLOWED_SYMBOLS: frozenset[str] = frozenset({"BTC-USD", "RELIANCE.NS", "^NSEI"})
ALLOWED_TIMEFRAMES: frozenset[str] = frozenset({"1d", "1h"})
INDIA_SYMBOLS: frozenset[str] = frozenset({"RELIANCE.NS", "^NSEI"})
REQUIRED_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")
MAX_HOURLY_DAYS = 730


class MarketDataError(ValueError):
    """Raised when downloaded market data is unsupported, incomplete, or invalid."""


@dataclass(frozen=True)
class CandleGap:
    """A missing-candle interval detected in a market-data series."""

    previous_timestamp: pd.Timestamp
    next_timestamp: pd.Timestamp
    missing_candles: int


@dataclass(frozen=True)
class GapReport:
    """Summary of missing candles, limited to gaps unexpected for the market."""

    expected_interval: pd.Timedelta
    gaps: tuple[CandleGap, ...]


def _as_timestamp(value: date | datetime | pd.Timestamp) -> pd.Timestamp:
    """Convert a date-like input to a pandas timestamp without changing its timezone."""
    return pd.Timestamp(value)


def _hourly_range_exceeds_limit(start: date | datetime | pd.Timestamp, end: date | datetime | pd.Timestamp) -> bool:
    """Return whether an hourly request exceeds yfinance's supported lookback window."""
    return _as_timestamp(end) - _as_timestamp(start) > pd.Timedelta(days=MAX_HOURLY_DAYS)


def _flatten_download_columns(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Return a single-symbol yfinance result with lower-case OHLCV column names."""
    result = frame.copy()
    if isinstance(result.columns, pd.MultiIndex):
        matching_levels = [level for level in range(result.columns.nlevels) if symbol in result.columns.get_level_values(level)]
        if len(matching_levels) != 1:
            raise MarketDataError("yfinance returned an unexpected multi-symbol column layout.")
        result = result.xs(symbol, axis=1, level=matching_levels[0], drop_level=True)

    normalized_columns = {str(column).strip().lower(): column for column in result.columns}
    missing = set(REQUIRED_COLUMNS).difference(normalized_columns)
    if missing:
        raise MarketDataError(f"yfinance response is missing required columns: {', '.join(sorted(missing))}.")
    return result.loc[:, [normalized_columns[column] for column in REQUIRED_COLUMNS]].rename(
        columns={normalized_columns[column]: column for column in REQUIRED_COLUMNS}
    )


def validate_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate OHLCV candles and return a UTC-indexed copy.

    The input index must already be timezone-aware; naive source timestamps are
    rejected rather than guessed or silently localized.
    """
    if not isinstance(frame, pd.DataFrame):
        raise MarketDataError("Market data must be a pandas DataFrame.")
    if frame.empty:
        raise MarketDataError("No candles were returned for the selected range.")
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise MarketDataError("Market data must use a DatetimeIndex.")
    if frame.index.tz is None:
        raise MarketDataError("Market-data timestamps must be timezone-aware.")
    if not frame.index.is_monotonic_increasing:
        raise MarketDataError("Market-data timestamps must be sorted ascending.")
    if frame.index.has_duplicates:
        raise MarketDataError("Market-data timestamps must not contain duplicates.")

    result = frame.copy()
    result.columns = [str(column).strip().lower() for column in result.columns]
    missing = set(REQUIRED_COLUMNS).difference(result.columns)
    if missing:
        raise MarketDataError(f"Market data is missing required columns: {', '.join(sorted(missing))}.")
    result = result.loc[:, REQUIRED_COLUMNS]
    if result.isna().any().any():
        raise MarketDataError("Market data contains NaN values in OHLCV columns.")

    prices = result.loc[:, ["open", "high", "low", "close"]]
    if (prices <= 0).any().any():
        raise MarketDataError("Open, high, low, and close prices must all be greater than zero.")
    if (result["volume"] < 0).any():
        raise MarketDataError("Volume must be greater than or equal to zero.")
    if (result["high"] < result[["open", "close"]].max(axis=1)).any():
        raise MarketDataError("Every high must be at least the open and close price.")
    if (result["low"] > result[["open", "close"]].min(axis=1)).any():
        raise MarketDataError("Every low must be at most the open and close price.")
    result.index = result.index.tz_convert("UTC")
    return result


def download_market_data(
    symbol: Symbol,
    timeframe: Timeframe,
    start: date | datetime | pd.Timestamp,
    end: date | datetime | pd.Timestamp,
) -> pd.DataFrame:
    """Download one allowed symbol from yfinance and return validated UTC candles."""
    if symbol not in ALLOWED_SYMBOLS:
        raise MarketDataError("Unsupported symbol. Choose BTC-USD, RELIANCE.NS, or ^NSEI.")
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise MarketDataError("Unsupported timeframe. Choose 1d or 1h.")
    if _as_timestamp(end) <= _as_timestamp(start):
        raise MarketDataError("The end date must be after the start date.")
    if timeframe == "1h" and _hourly_range_exceeds_limit(start, end):
        raise MarketDataError("yfinance limits 1h data to about 730 days; select a shorter range.")

    raw = yf.download(
        symbol,
        start=start,
        end=end,
        interval=timeframe,
        auto_adjust=symbol in INDIA_SYMBOLS,
        actions=False,
        progress=False,
        threads=False,
        ignore_tz=False,
    )
    return validate_ohlcv(_flatten_download_columns(raw, symbol))


def build_gap_report(frame: pd.DataFrame, symbol: Symbol, timeframe: Timeframe) -> GapReport:
    """Report unexpected missing candles without treating NSE overnight gaps as errors."""
    validated = validate_ohlcv(frame)
    if symbol not in ALLOWED_SYMBOLS:
        raise MarketDataError("Unsupported symbol. Choose BTC-USD, RELIANCE.NS, or ^NSEI.")
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise MarketDataError("Unsupported timeframe. Choose 1d or 1h.")

    expected_interval = pd.Timedelta(days=1) if timeframe == "1d" else pd.Timedelta(hours=1)
    gaps: list[CandleGap] = []
    for previous, following in zip(validated.index[:-1], validated.index[1:], strict=True):
        delta = following - previous
        if delta <= expected_interval:
            continue
        if symbol in INDIA_SYMBOLS:
            if timeframe != "1h" or previous.tz_convert("Asia/Kolkata").date() != following.tz_convert("Asia/Kolkata").date():
                continue
        missing_candles = max(1, int(delta // expected_interval) - 1)
        gaps.append(CandleGap(previous, following, missing_candles))
    return GapReport(expected_interval=expected_interval, gaps=tuple(gaps))
