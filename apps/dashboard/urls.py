"""URL routes for the dashboard."""

from django.urls import path

from apps.dashboard import views


app_name = "dashboard"

urlpatterns = [
    path("", views.backtest_dashboard, name="backtest"),
    path("export-trades/", views.export_trades_csv, name="export_trades"),
]
