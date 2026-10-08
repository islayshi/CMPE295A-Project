"""Health check and legacy test URL routes."""
from django.urls import path
from .views import health_check, connection_test
from .views import get_gee_ndvi_tile

urlpatterns = [
    path("", health_check, name="health-check"),
    path("test/", connection_test, name="connection-test"),
    path('gee/ndvi-tile/', get_gee_ndvi_tile, name='gee-ndvi-tile'),
]