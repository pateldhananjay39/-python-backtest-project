"""Django configuration for market data."""

from django.apps import AppConfig


class MarketConfig(AppConfig):
    """Configure the market-data app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.market"
