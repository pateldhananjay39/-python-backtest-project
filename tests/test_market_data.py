"""Tests for pure market-data validation and download boundaries."""

from datetime import date, timedelta

import pandas as pd
import pytest

from apps.market.data import MarketDataError, build_gap_report, download_market_data, validate_ohlcv


def valid_candles(periods: int = 3, frequency: str = "h") -> pd.DataFrame:
    """Create clearly labeled synthetic, valid OHLCV candles for unit tests."""
    index = pd.date_range("2025-01-01T00:00:00Z", periods=periods, freq=frequency)
    return pd.DataFrame(
        {"open": [100.0] * periods, "high": [102.0] * periods, "low": [99.0] * periods,
         "close": [101.0] * periods, "volume": [10.0] * periods},
        index=index,
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda frame: pd.concat([frame, frame.iloc[[0]]]).sort_index(), "duplicates"),
        (lambda frame: frame.assign(close=float("nan")), "NaN"),
        (lambda frame: frame.assign(high=98.0), "high"),
        (lambda frame: frame.iloc[::-1], "sorted"),
        (lambda frame: frame.set_axis(frame.index.tz_localize(None), axis="index"), "timezone-aware"),
    ],
)
def test_validate_ohlcv_rejects_invalid_data(mutation: object, message: str) -> None:
    """Reject each mandated invalid-data shape rather than changing it silently."""
    with pytest.raises(MarketDataError, match=message):
        validate_ohlcv(mutation(valid_candles()))  # type: ignore[operator]


def test_validate_ohlcv_normalizes_to_utc() -> None:
    """Convert valid timezone-aware source timestamps to UTC internally."""
    source = valid_candles()
    source.index = source.index.tz_convert("Asia/Kolkata")
    result = validate_ohlcv(source)
    assert str(result.index.tz) == "UTC"
    pd.testing.assert_frame_equal(result, valid_candles())


def test_download_uses_indian_auto_adjust_and_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use yfinance's documented download arguments and validate the response."""
    received: dict[str, object] = {}

    def fake_download(*args: object, **kwargs: object) -> pd.DataFrame:
        received.update(kwargs)
        return valid_candles()

    monkeypatch.setattr("apps.market.data.yf.download", fake_download)
    result = download_market_data("RELIANCE.NS", "1d", date(2025, 1, 1), date(2025, 1, 10))
    assert received["auto_adjust"] is True
    assert received["ignore_tz"] is False
    assert result.index.tz is not None


def test_download_rejects_overlong_hourly_range() -> None:
    """Reject hourly requests instead of returning yfinance's partial data."""
    with pytest.raises(MarketDataError, match="730"):
        download_market_data("BTC-USD", "1h", date(2023, 1, 1), date(2025, 1, 1))


def test_btc_gap_report_flags_missing_candle() -> None:
    """BTC trades continuously, so a two-hour interval means one missing 1h candle."""
    frame = valid_candles()
    frame.index = pd.DatetimeIndex([frame.index[0], frame.index[1] + timedelta(hours=1), frame.index[2] + timedelta(hours=1)])
    report = build_gap_report(frame, "BTC-USD", "1h")
    assert len(report.gaps) == 1
    assert report.gaps[0].missing_candles == 1


def test_nse_gap_report_ignores_overnight_but_flags_intraday() -> None:
    """NSE overnight gaps are expected; a gap during one local trading day is not."""
    overnight = valid_candles(2)
    overnight.index = pd.DatetimeIndex([pd.Timestamp("2025-01-01 15:15", tz="Asia/Kolkata"), pd.Timestamp("2025-01-02 09:15", tz="Asia/Kolkata")])
    assert not build_gap_report(overnight, "RELIANCE.NS", "1h").gaps

    intraday = valid_candles(2)
    intraday.index = pd.DatetimeIndex([pd.Timestamp("2025-01-01 09:15", tz="Asia/Kolkata"), pd.Timestamp("2025-01-01 11:15", tz="Asia/Kolkata")])
    assert len(build_gap_report(intraday, "RELIANCE.NS", "1h").gaps) == 1
