"""Routing URL routes — Design Doc §8."""
from django.urls import path
from .views import evacuate

urlpatterns = [
    path("evacuate/", evacuate, name="routing-evacuate"),
]
