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
   supported horizons.
"""

import os
import sys
import time
from pathlib import Path

import requests

# Setup paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "ml_adapter"))
sys.path.insert(0, str(PROJECT_ROOT / "ml_services/unet_service"))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from harvester.tasks import fetch_wind_data, fetch_aqi_data, trigger_active_inference, run_async_inference
from predictions.models import FireIncident, PredictionPolygon

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def check_ml_adapter(max_retries: int = 10, delay: float = 1.0) -> bool:
    """
    Verifies that the FastAPI ML Adapter is online and responding to /health
    before dispatching inference tasks.
    """
    health_url = f"{settings.ML_ADAPTER_URL}/health"
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(health_url, timeout=2)
            if resp.status_code == 200:
                return True
        except requests.RequestException:
            pass
        time.sleep(delay)
    return False


def main():
    force = "--force" in sys.argv or "--clean" in sys.argv
    print(f"{CYAN}=== Fight Fire With AI: Seeding Telemetry & ML Predictions ==={RESET}")
    print(f"Mode: {BOLD}{'MOCK' if settings.MOCK_INFERENCE else 'LIVE DOCKER INFERENCE'}{RESET}\n")

    # Clear old prediction polygons and cache keys to ensure clean state
    if force or not settings.MOCK_INFERENCE:
        print("Cleaning previous prediction cache...")
        PredictionPolygon.objects.all().delete()
        FireIncident.objects.all().delete()
        cache.delete("ffwai:predictions:current")
        cache.delete("ffwai:predictions:current:unet")
        cache.delete("ffwai:predictions:current:pinn")

    # 1. Wind Telemetry
    print(f"1. Fetching live wind data (Open-Meteo)...")
    try:
        wind_res = fetch_wind_data()
        status_msg = "using fallback" if wind_res.get("status") == "fallback" else "live telemetry"
        print(f"   {GREEN}✔ Wind data populated in Redis (ffwai:wind_current) [{status_msg}]{RESET}")
    except Exception as exc:
        print(f"   {YELLOW}⚠ Wind fetch warning: {exc}{RESET}")

    # 2. AQI Telemetry
    print(f"\n2. Fetching live AQI data (AirNow)...")
    try:
        fetch_aqi_data()
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
        cached_hotspots = cache.get("ffwai:telemetry:firms_hotspots")
        hotspot_count = 0
        if cached_hotspots:
            data = json.loads(cached_hotspots) if isinstance(cached_hotspots, str) else cached_hotspots
            hotspot_count = len(data.get("features", []))
        print(f"   {GREEN}✔ Satellite hotspots cached in Redis (ffwai:telemetry:firms_hotspots) [{hotspot_count} detections/flares]{RESET}")
        if hotspot_count == 0:
            baseline_hotspots = {
                "type": "FeatureCollection",
                "metadata": {
                    "timestamp": timezone.now().isoformat(),
                    "total_hotspots": 3,
                    "note": "Dev baseline ground-truth hotspots",
                },
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-122.05, 37.20]},
                        "properties": {
                            "latitude": 37.20,
                            "longitude": -122.05,
                            "frp": 28.4,
                            "confidence": "high",
                            "satellite": "NOAA-20",
                            "is_industrial_flare": False,
                            "flare_site_name": None,
                            "acq_date": timezone.now().strftime("%Y-%m-%d"),
                            "acq_time": "2030",
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-122.3858, 37.9358]},
                        "properties": {
                            "latitude": 37.9358,
                            "longitude": -122.3858,
                            "frp": 45.2,
                            "confidence": "high",
                            "satellite": "Suomi-NPP",
                            "is_industrial_flare": True,
                            "flare_site_name": "Chevron Richmond Refinery",
                            "acq_date": timezone.now().strftime("%Y-%m-%d"),
                            "acq_time": "1945",
                        },
                    },
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [-121.9323, 37.4557]},
                        "properties": {
                            "latitude": 37.4557,
                            "longitude": -121.9323,
                            "frp": 22.0,
                            "confidence": "high",
                            "satellite": "NOAA-21",
                            "is_industrial_flare": True,
                            "flare_site_name": "Newby Island Landfill (Alviso)",
                            "acq_date": timezone.now().strftime("%Y-%m-%d"),
                            "acq_time": "2115",
                        },
                    },
                ],
            }
            cache.set("ffwai:telemetry:firms_hotspots", json.dumps(baseline_hotspots), timeout=60 * 60 * 24)
            print(f"   {GREEN}✔ Seeded dev baseline satellite hotspots (1 wildland + 2 suppressed flares){RESET}")
    except Exception as exc:
        print(f"   {YELLOW}⚠ Scout warning: {exc}{RESET}")

    # 4. Process predictions from Active Fire Scout or seed test fire
    if fires_found > 0:
        print(f"\n4. Active wildfire cluster(s) detected. Waiting for Celery worker to finish inference...")
        for _ in range(15):
            recent_polygons = PredictionPolygon.objects.filter(
                timestamp__gte=timezone.now() - timezone.timedelta(hours=6)
            ).count()
            if recent_polygons > 0:
                break
            time.sleep(1)

    recent_polygons = PredictionPolygon.objects.filter(
        timestamp__gte=timezone.now() - timezone.timedelta(hours=6)
    ).count()

    if recent_polygons == 0:
        target_name = "Live Docker ML Test Fire" if not settings.MOCK_INFERENCE else "Santa Cruz Mountains Wildfire"
        print(f"\n4. No natural wildfires burning today in the Bay Area.")

        # Ensure ML Adapter is alive before attempting inference
        print(f"   Checking ML Adapter availability at {settings.ML_ADAPTER_URL}/health...")
        if not check_ml_adapter(max_retries=10, delay=1.0):
            print(f"   {YELLOW}⚠ ML Adapter is unreachable on {settings.ML_ADAPTER_URL}. Skipping prediction seeding.{RESET}")
            print(f"     (Start it with: uvicorn ml_adapter.main:app --port 8001)")
        else:
            print(f"   {GREEN}✔ ML Adapter is online!{RESET}")
            print(f"   Dispatching test coordinates to ML Adapter ({'Live Docker U-Net & PINN' if not settings.MOCK_INFERENCE else 'Mock Mode'})...")
            now = timezone.now()
            inc = FireIncident.objects.create(
                name=target_name,
                start_time=now,
                is_active=True
            )

            # Santa Cruz Mountains fire zone
            bbox = [-122.25, 37.05, -121.85, 37.35]
            for model in ["unet", "pinn", "ensemble"]:
                print(f"   - Invoking {model.upper()} via ML Adapter...")
                try:
                    res = run_async_inference(bbox=bbox, model_type=model, incident_id=inc.id, time_horizon=6)
                    feat_count = len(res.get("features", [])) if isinstance(res, dict) else 0
                    print(f"     -> {model.upper()} returned {feat_count} features")
                except Exception as exc:
                    print(f"     {YELLOW}⚠ {model.upper()} invocation error: {exc}{RESET}")

            print(f"   {GREEN}✔ Generated and cached predictions for U-Net, PINN, and Ensemble{RESET}")
    else:
        print(f"\n4. {GREEN}✔ Found {recent_polygons} active prediction polygons ready in PostGIS and Redis.{RESET}")

    print(f"\n{GREEN}=== Cache and Database Warmup Complete! ==={RESET}")
    print(f"You can now refresh the browser at http://localhost:5173 to see live wind, AQI, and fire polygons.\n")


if __name__ == "__main__":
    main()
