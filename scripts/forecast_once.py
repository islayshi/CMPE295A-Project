#!/usr/bin/env python3
"""
scripts/forecast_once.py — Fight Fire With AI
=============================================
Runs ONE model for ONE bbox through the real local pipeline (ML adapter -> model service -> Django storage ->
Redis cache) so its polygons show on the local dashboard. Useful for checking a model end to end when the
FIRMS scout finds no fire cluster.

    python scripts/forecast_once.py --model fusion --bbox -122.15 37.37 -122.00 37.48
    python scripts/forecast_once.py --model fusion --bbox -122.15 37.37 -122.00 37.48 --date 2026-11-13T23:00:00Z

Needs the local stack running (Docker services, ML adapter on 8001). Then open the dashboard, pick the model
and move the time slider (0, 1, 3, 6 h). The FIRMS hotspots layer shows where fires are right now; use a
bbox of ~10-20 km around one of them (inside the Bay Area: lon -123.2..-121.2, lat 36.4..38.8).
"""

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "ml_adapter"))
sys.path.insert(0, str(PROJECT_ROOT / "ml_services/unet_service"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django  # noqa: E402

django.setup()

from django.core.cache import cache  # noqa: E402
from django.utils import timezone  # noqa: E402

from harvester.tasks import run_async_inference  # noqa: E402
from predictions.models import FireIncident, PredictionPolygon  # noqa: E402
from predictions.serializers import PredictionPolygonGeoJSONSerializer  # noqa: E402

ap = argparse.ArgumentParser(description="Run one model for one bbox and show it on the local dashboard")
ap.add_argument("--model", default="fusion", choices=["unet", "pinn", "ensemble", "fusion"])
ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
ap.add_argument("--date", default=None, help="ISO time (UTC); default = now")
args = ap.parse_args()

incident = FireIncident.objects.create(name=f"Manual {args.model} check", start_time=timezone.now(), is_active=True)
centre = [(args.bbox[0] + args.bbox[2]) / 2, (args.bbox[1] + args.bbox[3]) / 2]
print(f"Running {args.model} for bbox {args.bbox} (incident {incident.id}) via the ML adapter...")
res = run_async_inference.apply(
    args=(args.bbox,),
    kwargs={"model_type": args.model, "incident_id": incident.id, "time_horizon": 6,
            "seed_points": [centre], "date": args.date},
).get()

feats = res.get("features", []) if isinstance(res, dict) else []
meta = res.get("metadata", {}) if isinstance(res, dict) else {}
print(f"Status: {meta.get('status', res.get('status') if isinstance(res, dict) else '?')}, {len(feats)} cells returned")
for (h, label), n in sorted(Counter((f["properties"].get("horizon_hours"), f["properties"].get("risk_label"))
                                    for f in feats).items(), key=lambda x: (x[0][0] or 0, str(x[0][1]))):
    print(f"  +{h} h  {label or '-':<14} {n}")

# Make the dashboard's per-model view show this run (the API serves ffwai:predictions:current:<model>).
polys = PredictionPolygon.objects.filter(fire_incident_id=incident.id, source_model=args.model).select_related("grid")
fc = {"type": "FeatureCollection",
      "metadata": {"timestamp": timezone.now().isoformat(), "total_cells": polys.count(), "source_model": args.model},
      "features": PredictionPolygonGeoJSONSerializer(polys, many=True).data}
cache.set(f"ffwai:predictions:current:{args.model}", json.dumps(fc), timeout=21600)
print(f"Stored {polys.count()} polygons in PostGIS and Redis key ffwai:predictions:current:{args.model}.")
print("Open the dashboard, select the model, and move the time slider.")
