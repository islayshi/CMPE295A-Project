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

import json
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
from harvester.tasks import (
    fetch_wind_data,
    fetch_aqi_data,
    trigger_active_inference,
    run_async_inference,
    store_geojson_result,
)
from predictions.models import FireIncident, PredictionPolygon

GREEN = "\033[92m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

BENCHMARK_TIMESTAMP = "2025-01-10T21:00:00Z"


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
        cache.delete("ffwai:predictions:current:ensemble")
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
                    "total_hotspots": 4,
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
                        "geometry": {"type": "Point", "coordinates": [-121.72, 37.17]},
                        "properties": {
                            "latitude": 37.17,
                            "longitude": -121.72,
                            "frp": 32.5,
                            "confidence": "high",
                            "satellite": "VIIRS_NOAA20_NRT",
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
            print(f"   {GREEN}✔ Seeded dev baseline satellite hotspots (2 wildland [Los Gatos, Coyote] + 2 suppressed flares){RESET}")
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

    cached_ensemble = cache.get("ffwai:predictions:current:ensemble") or cache.get("ffwai:predictions:current")
    cached_unet = cache.get("ffwai:predictions:current:unet")
    cached_pinn = cache.get("ffwai:predictions:current:pinn")

    needs_seeding = (
        recent_polygons == 0
        or not (cached_ensemble and cached_unet and cached_pinn)
    )

    if needs_seeding:
        print(f"\n4. Seeding fire predictions colocated with active NASA FIRMS hotspot centroids...")

        # Ensure ML Adapter is alive before attempting inference
        print(f"   Checking ML Adapter availability at {settings.ML_ADAPTER_URL}/health...")
        if not check_ml_adapter(max_retries=10, delay=1.0):
            print(f"   {YELLOW}⚠ ML Adapter is unreachable on {settings.ML_ADAPTER_URL}. Skipping prediction seeding.{RESET}")
            print(f"     (Start it with: uvicorn ml_adapter.main:app --port 8001)")
        else:
            print(f"   {GREEN}✔ ML Adapter is online!{RESET}")
            print(f"   Dispatching colocated test coordinates to ML Adapter ({'Live Docker U-Net & PINN' if not settings.MOCK_INFERENCE else 'Mock Mode'})...")
            now = timezone.now()

            # Active fire hotspot targets to colocate predictions with:
            # Los Gatos centroid [-122.05, 37.20] and Coyote centroid [-121.72, 37.17]
            cluster_targets = [
                {
                    "name": "Los Gatos Wildfire Incident",
                    "centroid": [-122.05, 37.20],
                    "bbox": [-122.15, 37.10, -121.95, 37.30],
                },
                {
                    "name": "Coyote / Calero Wildfire Incident",
                    "centroid": [-121.72, 37.17],
                    "bbox": [-121.82, 37.07, -121.62, 37.27],
                },
            ]

            for target in cluster_targets:
                inc = FireIncident.objects.create(
                    name=target["name"],
                    start_time=now,
                    is_active=True
                )
                bbox = target["bbox"]
                seed_pt = target["centroid"]
                print(f"   * Cluster: {target['name']} at centroid {seed_pt}...")

                for model in ["unet", "pinn", "ensemble"]:
                    print(f"     - Invoking {model.upper()} via ML Adapter...")
                    feat_count = 0
                    try:
                        res = run_async_inference(
                            bbox=bbox,
                            model_type=model,
                            incident_id=inc.id,
                            time_horizon=24,
                            seed_points=[seed_pt],
                        )
                        feat_count = len(res.get("features", [])) if isinstance(res, dict) else 0
                        print(f"       -> {model.upper()} returned {feat_count} features (date=now)")
                    except Exception as exc:
                        print(f"       {YELLOW}⚠ {model.upper()} invocation error: {exc}{RESET}")

                    # If live Docker inference returned 0 features (no active wildfire burning today),
                    # automatically fall back to querying the ML adapter with benchmark wildfire timestamp
                    if feat_count == 0:
                        print(f"       -> Querying benchmark replay / calibrated fixture with target_bbox={bbox}...")
                        try:
                            url = f"{settings.ML_ADAPTER_URL}/predict/progression"
                            payload = {
                                "bbox": bbox,
                                "time_horizon": 24,
                                "model_type": model,
                                "date": BENCHMARK_TIMESTAMP,
                                "mock": settings.MOCK_INFERENCE,
                                "seed_points": [seed_pt],
                            }
                            resp = requests.post(url, json=payload, timeout=120)
                            resp.raise_for_status()
                            benchmark_fc = resp.json()
                            b_features = benchmark_fc.get("features", [])
                            feat_count = len(b_features)

                            # If live container sees 0 features in this specific bbox on benchmark date,
                            # fall back to calibrated Bay Area benchmark fixture colocated via target_bbox
                            if feat_count == 0 and not settings.MOCK_INFERENCE:
                                print(f"       -> Live {model.upper()} saw 0 features on benchmark date. Using calibrated benchmark fixture...")
                                payload["mock"] = True
                                resp = requests.post(url, json=payload, timeout=120)
                                resp.raise_for_status()
                                benchmark_fc = resp.json()
                                b_features = benchmark_fc.get("features", [])
                                feat_count = len(b_features)

                            print(f"       -> Colocated {model.upper()} returned {feat_count} features across horizons [0, 1, 3, 6, 24]")

                            if feat_count > 0:
                                now_iso = timezone.now().isoformat()
                                benchmark_fc.setdefault("metadata", {})
                                benchmark_fc["metadata"]["timestamp"] = now_iso
                                benchmark_fc["metadata"]["source_model"] = model
                                benchmark_fc["metadata"]["benchmark_replay"] = True
                                benchmark_fc["metadata"]["benchmark_date"] = BENCHMARK_TIMESTAMP

                                store_geojson_result(benchmark_fc, incident_id=inc.id)
                        except Exception as exc:
                            print(f"       {YELLOW}⚠ {model.upper()} benchmark replay error: {exc}{RESET}")

            # Multi-incident aggregation across all active incidents into current risk keys with 6h TTL
            active_incidents = list(FireIncident.objects.filter(is_active=True).values_list("id", flat=True))
            if active_incidents:
                from predictions.serializers import PredictionPolygonGeoJSONSerializer
                for model_key in ["ensemble", "unet", "pinn"]:
                    model_polys = PredictionPolygon.objects.filter(
                        fire_incident_id__in=active_incidents,
                        source_model=model_key,
                        timestamp__gte=timezone.now() - timezone.timedelta(hours=6)
                    ).select_related("grid")
                    if model_polys.exists():
                        serializer = PredictionPolygonGeoJSONSerializer(model_polys, many=True)
                        model_fc = {
                            "type": "FeatureCollection",
                            "metadata": {
                                "timestamp": timezone.now().isoformat(),
                                "total_cells": model_polys.count(),
                                "active_incidents": len(active_incidents),
                                "source_model": model_key,
                            },
                            "features": serializer.data,
                        }
                        if model_key == "ensemble":
                            cache.set("ffwai:predictions:current", json.dumps(model_fc), timeout=21600)
                            cache.set("ffwai:predictions:current:ensemble", json.dumps(model_fc), timeout=21600)
                        else:
                            cache.set(f"ffwai:predictions:current:{model_key}", json.dumps(model_fc), timeout=21600)

            # Ensure bidirectional sync between ffwai:predictions:current and ffwai:predictions:current:ensemble
            curr = cache.get("ffwai:predictions:current")
            curr_ens = cache.get("ffwai:predictions:current:ensemble")
            if not curr and curr_ens:
                cache.set("ffwai:predictions:current", curr_ens, timeout=21600)
            elif not curr_ens and curr:
                cache.set("ffwai:predictions:current:ensemble", curr, timeout=21600)

            # Verify and report Redis cache keys
            for key_suffix in ["", ":ensemble", ":unet", ":pinn"]:
                cache_key = f"ffwai:predictions:current{key_suffix}"
                cached = cache.get(cache_key)
                if cached:
                    try:
                        data = json.loads(cached) if isinstance(cached, str) else cached
                        c_count = len(data.get("features", []))
                        print(f"   {GREEN}✔ Redis key '{cache_key}' cached ({c_count} features){RESET}")
                    except Exception:
                        pass
                else:
                    print(f"   {YELLOW}⚠ Redis key '{cache_key}' not populated{RESET}")

            print(f"   {GREEN}✔ Generated and cached predictions for U-Net, PINN, and Ensemble{RESET}")
    else:
        print(f"\n4. {GREEN}✔ Found {recent_polygons} active prediction polygons ready in PostGIS and Redis.{RESET}")

    print(f"\n{GREEN}=== Cache and Database Warmup Complete! ==={RESET}")
    print(f"You can now refresh the browser at http://localhost:5173 to see live wind, AQI, and fire polygons.\n")


if __name__ == "__main__":
    main()
