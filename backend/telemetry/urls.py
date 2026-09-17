"""Telemetry URL routes — Design Doc §8."""
from django.urls import path
from .views import wind_telemetry, nws_alerts, emergency_shelters

urlpatterns = [
    path("wind/", wind_telemetry, name="telemetry-wind"),
    path("alerts/", nws_alerts, name="telemetry-alerts"),
    path("shelters/", emergency_shelters, name="telemetry-shelters"),
]
