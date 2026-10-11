from django.urls import path
from .views import (
    get_gee_ndvi_tile,
    get_gee_available_dates,
    aqi_data,
    wind_telemetry,
    nws_alerts,
    emergency_shelters,
)

urlpatterns = [
    path("gee/ndvi-tile/", get_gee_ndvi_tile, name="telemetry-gee-ndvi-tile"),
    path("gee/available-dates/", get_gee_available_dates, name="telemetry-gee-available-dates"),
    path("aqi/", aqi_data, name="telemetry-aqi"),
    path("wind/", wind_telemetry, name="telemetry-wind"),
    path("alerts/", nws_alerts, name="telemetry-alerts"),
    path("shelters/", emergency_shelters, name="telemetry-shelters"),
]