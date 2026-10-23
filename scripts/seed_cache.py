#!/usr/bin/env python3
"""
scripts/seed_cache.py — Fight Fire With AI
===========================================
Warms up Redis cache and PostGIS database with live telemetry and fire predictions.
Runs immediately upon starting the local development stack so that the frontend
map immediately has:
1. Live Open-Meteo wind field vector grid (40x40 IDW interpolation)
2. Live AirNow AQI telemetry stations
3. NASA FIRMS VIIRS active fire detections (Active Fire Scout)
4. Calibrated fire progression predictions (U-Net, PINN, and Ensemble) across
   0h, 1h, 3h, 6h, and 24h horizons.
"""

import os
import sys
from pathlib import Path

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "ml_adapter"))
sys.path.insert(0, str(PROJECT_ROOT / "ml_services/unet_service"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.utils import timezone
from harvester.tasks import fetch_wind_data, fetch_aqi_data, trigger_active_inference, run_async_inference
from predictions.models import FireIncident, PredictionPolygon

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"


def main():
    print(f"{CYAN}=== Fight Fire With AI: Seeding Telemetry & ML Predictions ==={RESET}\n")

    # 1. Wind Telemetry
    print(f"1. Fetching live wind data (Open-Meteo)...")
    try:
        wind_res = fetch_wind_data()
        print(f"   {GREEN}✔ Wind data populated in Redis (ffwai:wind_current){RESET}")
    except Exception as exc:
        print(f"   {YELLOW}⚠ Wind fetch warning: {exc}{RESET}")

    # 2. AQI Telemetry
    print(f"\n2. Fetching live AQI data (AirNow)...")
    try:
        aqi_res = fetch_aqi_data()
        print(f"   {GREEN}✔ AQI data populated in Redis (ffwai:aqi_data){RESET}")
    except Exception as exc:
        print(f"   {YELLOW}⚠ AQI fetch warning: {exc}{RESET}")

    # 3. Active Fire Scout (NASA FIRMS)
    print(f"\n3. Running Active Fire Scout (NASA FIRMS VIIRS 375m)...")
    fires_found = 0
    try:
        scout_res = trigger_active_inference()
        fires_found = scout_res.get("fires_detected", 0) if isinstance(scout_res, dict) else 0
        print(f"   {GREEN}✔ Active fire scout executed: {fires_found} active wildfire cluster(s) detected{RESET}")
    except Exception as exc:
        print(f"   {YELLOW}⚠ Scout warning: {exc}{RESET}")

    # 4. If no natural active wildfire currently burning in Bay Area, seed simulated incident
    recent_polygons = PredictionPolygon.objects.filter(
        timestamp__gte=timezone.now() - timezone.timedelta(hours=6)
    ).count()

    if recent_polygons == 0:
        print(f"\n4. No natural wildfires burning today in the Bay Area. Seeding active test fire...")
        now = timezone.now()
        inc, _ = FireIncident.objects.get_or_create(
            name="Santa Cruz Mountains Wildfire",
            defaults={"start_time": now, "is_active": True}
        )
        inc.is_active = True
        inc.save()

        # Santa Cruz Mountains / Loma Prieta fire zone
        bbox = [-122.25, 37.05, -121.85, 37.35]
        for model in ["unet", "pinn", "ensemble"]:
            print(f"   - Generating {model.upper()} predictions via ML Adapter...")
            run_async_inference(bbox=bbox, model_type=model, incident_id=inc.id, time_horizon=6)

        print(f"   {GREEN}✔ Pre-seeded 0h, 1h, 3h, 6h, 24h predictions for U-Net, PINN, and Ensemble{RESET}")
    else:
        print(f"\n4. {GREEN}✔ Found {recent_polygons} active prediction polygons ready in PostGIS and Redis.{RESET}")

    print(f"\n{GREEN}=== Cache and Database Warmup Complete! ==={RESET}")
    print(f"You can now refresh the browser at http://localhost:5173 to see live wind, AQI, and fire polygons.\n")


if __name__ == "__main__":
    main()
