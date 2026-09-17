"""
Metrics Models — Fight Fire With AI

Performance metrics are stored in predictions.ModelPerformanceMetric.
This app provides the REST endpoint only; it does not define its
own models to keep a clear domain separation.

See: predictions/models.py → ModelPerformanceMetric
"""
from django.db import models  # noqa: F401 — required by Django app registry
