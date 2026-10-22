from django.urls import path
from .views import (
    get_gee_ndvi_tile,
    get_gee_available_dates,
    get_firms_hotspots,
    get_firms_active_dates,
    get_weather_telemetry,
    get_goes_fire_telemetry,
    aqi_data,
    wind_telemetry,
    nws_alerts,
    emergency_shelters,
    get_mtbs_historical_perimeters,
)

urlpatterns = [
    path("gee/ndvi-tile/", get_gee_ndvi_tile, name="telemetry-gee-ndvi-tile"),
    path("gee/available-dates/", get_gee_available_dates, name="telemetry-gee-available-dates"),
    path("firms/", get_firms_hotspots, name="telemetry-firms-hotspots"),
    path("firms/active-dates/", get_firms_active_dates, name="telemetry-firms-active-dates"),
    path("weather/", get_weather_telemetry, name="telemetry-weather"),
    path("goes/", get_goes_fire_telemetry, name="telemetry-goes"),
    path("aqi/", aqi_data, name="telemetry-aqi"),
    path("wind/", wind_telemetry, name="telemetry-wind"),
    path("alerts/", nws_alerts, name="telemetry-alerts"),
    path("shelters/", emergency_shelters, name="telemetry-shelters"),
    path("mtbs/", get_mtbs_historical_perimeters, name="mtbs_perimeters"),
]