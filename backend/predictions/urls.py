"""Predictions URL routes — Design Doc §8."""
from django.urls import path
from .views import current_predictions, prediction_history

urlpatterns = [
    path("current/", current_predictions, name="predictions-current"),
    path("history/", prediction_history, name="predictions-history"),
]
