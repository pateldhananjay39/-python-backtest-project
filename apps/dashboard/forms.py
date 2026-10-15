"""Validated inputs for one educational backtest request."""

from __future__ import annotations

from datetime import date

from django import forms

from apps.market.data import ALLOWED_SYMBOLS, ALLOWED_TIMEFRAMES


class BacktestForm(forms.Form):
    """Validate the limited, long-only EMA crossover configuration."""

    symbol = forms.ChoiceField(choices=sorted((symbol, symbol) for symbol in ALLOWED_SYMBOLS), initial="BTC-USD")
    timeframe = forms.ChoiceField(choices=sorted((timeframe, timeframe) for timeframe in ALLOWED_TIMEFRAMES), initial="1d")
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    fast_period = forms.IntegerField(min_value=1, initial=9, label="Fast EMA period")
    slow_period = forms.IntegerField(min_value=2, initial=21, label="Slow EMA period")
    fee_percent = forms.FloatField(min_value=0, initial=0.10, label="Fee per side (%)")
    slippage_percent = forms.FloatField(min_value=0, initial=0.05, label="Slippage per side (%)")
    start_capital = forms.FloatField(min_value=0.000001, initial=100_000, label="Starting capital")

    def clean(self) -> dict[str, object]:
        """Require a forward date range and a valid EMA pair."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        fast_period = cleaned_data.get("fast_period")
        slow_period = cleaned_data.get("slow_period")
        if isinstance(start_date, date) and isinstance(end_date, date) and end_date <= start_date:
            self.add_error("end_date", "End date must be after the start date.")
        if isinstance(fast_period, int) and isinstance(slow_period, int) and fast_period >= slow_period:
            self.add_error("fast_period", "Fast EMA period must be less than the slow EMA period.")
        return cleaned_data
