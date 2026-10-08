"""Telemetry URL routes — Design Doc §8."""
from django.urls import path
from .views import (
    wind_telemetry,
    nws_alerts,
    emergency_shelters,
    aqi_data,
    get_gee_ndvi_tile,
)

urlpatterns = [
    path("wind/", wind_telemetry, name="telemetry-wind"),
    path("alerts/", nws_alerts, name="telemetry-alerts"),
    path("shelters/", emergency_shelters, name="telemetry-shelters"),
    path("aqi/", aqi_data, name="telemetry-aqi"),
    path("gee/ndvi-tile/", get_gee_ndvi_tile, name="telemetry-gee-ndvi-tile"),
]