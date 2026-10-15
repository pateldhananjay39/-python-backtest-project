# Project Report — Educational EMA Crossover Backtester

## Summary

This project is a Django web application for educational, long-only backtesting of an EMA crossover strategy on BTC-USD, RELIANCE.NS, and ^NSEI. A user selects a market, 1-day or 1-hour timeframe, date range, EMA periods, trading costs, and starting capital. The application then downloads historical OHLCV data from yfinance, validates it rigorously, simulates the strategy, and presents the resulting equity curve, executed trades, performance statistics, buy-and-hold comparison, and a downloadable trade CSV.

The dashboard's **Final equity** is the direct answer to “if I started with a given capital, how much would it be at the end of the selected backtest?” For example, entering `10000` as starting capital makes Final equity show the simulated ending amount after all configured costs.

## Design and correctness controls

- Market data is restricted to an explicit symbol and timeframe allow-list, normalized to UTC, and rejected if unsorted, duplicated, timezone-naive, invalid, or missing OHLCV values.
- Indian instruments are requested with `auto_adjust=True`. Hourly requests beyond yfinance's roughly 730-day window are rejected rather than silently returned partially.
- The EMA strategy uses `ewm(span=n, adjust=False)`. It is long-only, uses a slow-EMA warm-up, and produces a target position from only current and earlier candles.
- A signal at candle close executes only at the next candle open. No final-candle signal can create a trade. Entries and exits apply configurable slippage and per-side fees.
- BTC permits fractional quantity; India equity orders use whole shares and retain unused cash. Any open strategy position is closed at the final close and identified as a forced close.
- Metrics implement total return, CAGR, maximum drawdown, win rate, and profit factor, returning `N/A` in the UI when a value is undefined.

## Application structure

- `apps/market`: pure yfinance download, validation, and gap reporting.
- `apps/backtest`: pure strategy, execution, buy-and-hold, and metrics logic; it has no Django imports.
- `apps/dashboard`: Django forms, thin views, Bootstrap templates, Plotly chart builders, and CSV export.
- `tests`: synthetic known-answer and web-flow tests. Synthetic data is used only for tests; the dashboard downloads its selected market data at run time.

## Verification

The automated suite currently contains 26 tests covering data validation, known-answer execution, no-look-ahead behavior, costs, equity reconciliation, indicator values, metric edge cases, dashboard validation/rendering, and CSV export. The latest verification completed successfully:

```text
26 passed
System check identified no issues (0 silenced).
```

## Limitations and responsible use

yfinance is not exchange-grade data; results should be spot-checked against an exchange or TradingView. Cost settings are editable approximations, especially for Indian equities, and taxes are not modelled. The application intentionally excludes live trading, broker APIs, shorting, leverage, optimisation, machine learning, and multi-user features. It is an educational tool, not financial advice; past performance does not guarantee future results.
