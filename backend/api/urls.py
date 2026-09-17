"""Health check and legacy test URL routes."""
from django.urls import path
from .views import health_check, connection_test

urlpatterns = [
    path("", health_check, name="health-check"),
    path("test/", connection_test, name="connection-test"),
]
