# Project Report

## 1. Project Title

**Educational EMA Crossover Strategy Backtester**

## 2. Abstract

The Educational EMA Crossover Strategy Backtester is a Django web application that evaluates a long-only EMA crossover strategy against historical market data. The system helps students understand the relationship between trading signals, execution costs, drawdowns, and final portfolio value before any real-money use. Users select a symbol, timeframe, date range, EMA parameters, trading costs, and starting capital. The application downloads historical candles from yfinance, validates them, simulates the strategy using next-open execution, and presents charts, trades, metrics, buy-and-hold comparison, and CSV export.

The system is an educational analysis tool only. It does not place trades, predict prices, or provide financial advice.

## 3. Problem Statement

Testing a trading idea manually is time-consuming and error-prone. Common mistakes include using a price that was not available at the time of a decision, ignoring transaction charges, investing more cash than is available, or reporting returns without considering drawdown. Students need a small and understandable system that demonstrates correct backtesting on historical data.

This project solves that problem by providing a web interface that runs a defined EMA crossover strategy using validated market candles and explicit execution rules.

## 4. Objectives

1. Download historical OHLCV data for BTC-USD, RELIANCE.NS, and ^NSEI.
2. Validate downloaded data before it is used in a backtest.
3. Implement a long-only EMA crossover strategy without look-ahead bias.
4. Include fee, slippage, starting capital, fractional crypto quantity, and whole-share equity quantity rules.
5. Display final equity, return, CAGR, drawdown, win rate, profit factor, trade history, and buy-and-hold comparison.
6. Provide a user-friendly Django interface and CSV export of closed trades.
7. Verify the application through automated tests.

## 5. Scope

### Included

- Symbols: BTC-USD, RELIANCE.NS, and ^NSEI.
- Timeframes: 1-hour and 1-day.
- One long-only EMA crossover strategy.
- Historical data download through yfinance.
- Charts, metrics, trade table, and CSV export.

### Excluded

- Live trading and broker APIs.
- Short selling, leverage, pyramiding, and parameter optimisation.
- Tax calculation and exchange-grade market-data guarantees.
- Machine-learning prediction, payments, and multi-user features.

## 6. Technologies and Tools Used

| Technology | Purpose |
| --- | --- |
| Python 3.11+ | Application programming language |
| Django 5 | Web framework, routing, forms, templates, and SQLite configuration |
| SQLite | Local development database used by Django |
| pandas and numpy | Time-series data handling and calculations |
| yfinance | Historical market-data source |
| Plotly | Candlestick and equity-curve charts |
| Bootstrap 5 | Responsive user-interface styling |
| pytest and pytest-django | Automated testing |
| Git and GitHub | Version control and source-code hosting |

## 7. System Design

### 7.1 Architecture

```text
Browser
  ↓
Django form and dashboard view
  ↓
Market-data module → yfinance → validated OHLCV candles
  ↓
Backtest module → EMA strategy → next-open execution → metrics
  ↓
Plotly charts / trade table / CSV response / Django template
```

The implementation separates business logic from Django presentation code:

- `apps/market/` contains pure data-download, validation, and gap-report functions.
- `apps/backtest/` contains pure strategy, execution, buy-and-hold, and metric calculations. It has no Django imports.
- `apps/dashboard/` contains the form, view, templates, chart builders, URL routes, and CSV export.

### 7.2 Backtesting Workflow

1. The user submits a form with a supported symbol, timeframe, dates, EMA periods, costs, and capital.
2. The application downloads candles from yfinance and validates timestamps and OHLCV values.
3. The EMA strategy creates a 0/1 target position from historical closing prices.
4. A signal at candle *t* executes at the open of candle *t + 1*.
5. The engine applies slippage and fees, tracks cash and quantity, and marks equity at every candle close.
6. Open positions are closed at the final close and marked as forced closes.
7. Metrics, comparison chart, table, and CSV output are produced.

## 8. Django Concepts Demonstrated

| Django concept | Implementation |
| --- | --- |
| Views | `backtest_dashboard` renders the form and results; `export_trades_csv` returns a CSV response. |
| Templates | Bootstrap-based `base.html` and `backtest.html` render inputs, metrics, charts, and trades. |
| Forms | `BacktestForm` validates allowed symbols, dates, EMA order, and positive inputs. |
| URLs | Dashboard and CSV-export routes are registered through Django URL configuration. |
| Database integration | Django is configured with SQLite and standard migrations were successfully applied. |
| Models | No custom application model has been created in the current version. |
| User management | Django's built-in authentication tables are migrated, but login, registration, and per-user saved-backtest screens are not implemented. |

**Important:** The final two rows accurately describe the present source code. If the college rubric requires custom models and visible user-management features, the project should be extended with a `BacktestRun` model plus registration/login and saved-run pages before submission.

## 9. Database Schema

The configured database is SQLite (`db.sqlite3`). After running migrations, it contains Django's standard framework tables, including authentication, permissions, sessions, admin logs, and content types.

```text
auth_user
  ├── username
  ├── password
  ├── email
  ├── first_name / last_name
  ├── is_active / is_staff / is_superuser
  └── date_joined / last_login

django_session
  ├── session_key
  ├── session_data
  └── expire_date
```

No custom database table is used to persist backtests in the current implementation. Backtest results are calculated from the submitted form and returned immediately in the response.

## 10. Implementation Details

### 10.1 Data Validation

The application rejects empty results, naive timestamps, unsorted or duplicate indices, NaN values, invalid high/low relationships, non-positive prices, and negative volume. Data is stored in UTC. Indian symbols use `auto_adjust=True`, and NSE values are displayed in Asia/Kolkata time.

### 10.2 Strategy and Execution

The fast and slow EMAs use `ewm(span=n, adjust=False)`. No target is generated before the slow EMA warm-up completes. The next-open rule prevents use of an unknown future fill price. Entry fill is `next_open × (1 + slippage)` and exit fill is `next_open × (1 - slippage)`. Fees are charged on both sides.

### 10.3 Metrics

The system calculates total return, CAGR for periods of at least 30 days, maximum drawdown, win rate, profit factor, final equity, and a buy-and-hold comparison. Undefined values render as `N/A`.

### 10.4 User Interface

The Bootstrap dashboard contains fields for all backtest inputs, a loading message, source-data warning, charts, metrics cards, trade table, and a Download Trades CSV button. Every rendered dashboard page includes the required educational disclaimer.

## 11. Screenshots

Add your own screenshots before submitting the report. Suggested screenshot captions are:

1. **Figure 1: Dashboard input form** — market, timeframe, dates, EMA periods, costs, and starting capital.
2. **Figure 2: Backtest results** — first/last candle, data warning, and metrics cards.
3. **Figure 3: Candlestick chart** — price candles with buy and sell execution markers.
4. **Figure 4: Equity curve and trade table** — strategy equity versus buy-and-hold, followed by closed trades.
5. **Figure 5: CSV export** — downloaded trade file opened in spreadsheet software.

> Insert only screenshots you personally captured from your own running project. Do not use another student's screenshots.

## 12. Testing and Results

The project uses synthetic test data for deterministic tests; live market prices are not fabricated in tests. The test suite covers:

- Invalid data: duplicates, NaN, bad high/low, unsorted index, and naive timestamps.
- Known-answer execution with hand-calculated fees and final equity.
- No-look-ahead behavior and final-candle signal handling.
- Correct next-open/slippage fills, cost impact, flat strategy, and equity reconciliation.
- EMA recurrence calculation and metric edge cases.
- Django form validation, result-page rendering, chart output, and CSV export.

Latest verification result:

```text
26 passed
System check identified no issues (0 silenced).
```

## 13. Achieved Outcome

The project successfully delivers an educational web backtester for the required supported symbols and timeframes. A user can run a historical EMA crossover simulation, see how starting capital changed to final equity, inspect transaction costs and trades, compare against buy-and-hold, and download the results. The project is available on GitHub:

https://github.com/pateldhananjay39/-python-backtest-project

## 14. Conclusion

The project demonstrates practical Django development with views, templates, forms, URL routing, validation, external data integration, testing, and SQLite configuration. It also demonstrates correct backtesting principles such as next-open execution and transaction-cost accounting. It is suitable as an educational trading-analysis project, subject to the stated data and financial limitations.

Before final college submission, custom models and visible user-management screens should be added if they are compulsory assessment requirements.

## 15. Limitations

- yfinance is not exchange-grade; important data should be spot-checked against TradingView or an exchange.
- Indian equity costs are editable approximations; taxes are not modelled.
- Only the EMA crossover strategy is available.
- The system does not predict future market behavior.
- This is an educational tool, not financial advice. Past performance does not guarantee future results.
