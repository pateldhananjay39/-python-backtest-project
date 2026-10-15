# One-Page Project Summary

## Project Title

**Educational EMA Crossover Strategy Backtester**

## Problem Statement

Retail investors and students often find it difficult to evaluate a trading strategy objectively before using real money. Manual calculation is slow and can introduce errors such as using future prices, ignoring brokerage costs, or overlooking drawdowns. This project provides a simple web-based backtesting tool that applies a defined EMA crossover strategy to historical market data and presents the outcome clearly.

## Objectives

- Download and validate historical BTC-USD and Indian-market OHLCV data.
- Simulate a long-only EMA crossover strategy without look-ahead bias.
- Let users configure dates, EMA periods, starting capital, fee, and slippage.
- Show final equity, returns, risk metrics, executed trades, charts, and a CSV export.

## Implementation Summary

The application is built with Django, SQLite, pandas, numpy, yfinance, Plotly, Bootstrap 5, pytest, and pytest-django. Django forms validate the user's input. Django views coordinate the request, templates render the results, and Plotly generates candlestick and equity charts. Core market-data validation, strategy logic, execution, and metrics are kept as pure Python functions outside the views.

The strategy uses a fast and slow exponential moving average. A target generated at a candle close executes at the following candle open; therefore, it does not use future prices. Both entry and exit include editable slippage and fees. BTC allows fractional quantities, while Indian equity trades use whole-share quantities. Final equity reports how the starting capital changed by the selected end date.

## Achieved Outcome

The completed application supports BTC-USD, RELIANCE.NS, and ^NSEI on 1-hour and 1-day data. It displays a data summary, performance metrics, buy-and-hold comparison, trade table, and CSV export. The codebase has 26 automated tests covering data validation, execution, no-look-ahead behavior, costs, metrics, dashboard rendering, and export. All 26 tests pass.

## GitHub Repository

https://github.com/pateldhananjay39/-python-backtest-project

## Note for Submission

The current application uses SQLite and Django's migrated built-in authentication tables, but it does not yet include a custom persistent backtest model or login/register screens. If user management and custom database models are mandatory assessment criteria, they should be added before final submission.
