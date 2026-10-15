# Educational EMA Crossover Backtester

A small Django application for testing a long-only EMA crossover strategy on BTC-USD, RELIANCE.NS, or ^NSEI. It is designed for correctness and inspectability, not speed or live trading.

**Educational tool, not financial advice. Past performance does not guarantee future results.**

## Features

- Daily or hourly yfinance data with strict OHLCV validation and gap reporting.
- Long-only EMA crossover: signals use each candle's close and execute at the next candle's open.
- Fees, slippage, fractional BTC quantities, and whole-share Indian equity quantities.
- Equity curve, buy-and-hold comparison, executed-trades table, and CSV export.
- Synthetic known-answer tests for execution, costs, look-ahead safety, indicators, metrics, and data validation.

## Setup

Requires Python 3.11 or newer.

```powershell
git clone <repository-url>
Set-Location <repository-directory>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000/.

## Test

```powershell
python -m pytest -q
python manage.py check
```

## How the backtest works

- EMA values use `ewm(span=n, adjust=False)` and require the slow-period warm-up.
- A target position from candle *t* executes at candle *t + 1*'s open. The final candle's signal cannot trade.
- Entries use `next_open * (1 + slippage)` and exits use `next_open * (1 - slippage)`; each side pays the configured fee.
- Open positions are closed at the final close and marked as forced closes.
- Buy-and-hold begins at the strategy's first executed entry open, uses the same costs, and holds to the final candle.

## Data and display

- Data comes from yfinance. Indian symbols are requested with `auto_adjust=True`.
- Data is stored internally in UTC; NSE results display in Asia/Kolkata.
- yfinance hourly history is limited to roughly 730 days. Longer requests are rejected rather than returned partially.
- The results page shows first/last candle timestamps, candle count, and unexpected gaps.

## Limitations

- yfinance is not exchange-grade data; spot-check five candles against TradingView or the exchange before relying on a result.
- Costs are editable approximations. Indian equity costs approximate brokerage, STT, exchange charges, GST, and stamp duty.
- Tax is not modelled.
- This application has no live trading, broker integration, shorting, leverage, parameter optimisation, machine-learning prediction, or multi-user accounts.
- A backtest does not predict future performance. Educational tool, not financial advice. Past performance does not guarantee future results.
