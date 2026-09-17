"""
Routing Models — Fight Fire With AI

The A* routing engine operates purely on the existing PostGIS tables
(BayAreaGrid, FireRiskPrediction) via spatial queries. No additional
models are required for the MVP.

Future: a RouteHistory model could archive evacuation routes
for analytics if needed.
"""
from django.db import models  # noqa: F401 — required by Django app registry
