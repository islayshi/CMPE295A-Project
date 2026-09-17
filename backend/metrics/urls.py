"""Metrics URL routes — Design Doc §8."""
from django.urls import path
from .views import model_metrics

urlpatterns = [
    path("", model_metrics, name="model-metrics"),
]
