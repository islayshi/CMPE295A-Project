"""
Harvester Tasks — Fight Fire With AI

Celery tasks for the daily data harvest and ML inference pipeline.
This is the core orchestration module — it ties together all external
data sources and the FastAPI ML Adapter.

Design Doc §1.1 Module 1: The Harvester (pluggable template)
Implementation Plan v4: Week 2 tasks

Pipeline flow (triggered daily by Celery Beat):
  trigger_daily_inference()
    ├── fetch_goes18_imagery()     → GEE → GCS
    ├── fetch_viirs_hotspots()     → GEE → GCS
    ├── fetch_vegetation_indices() → GEE → PostGIS VegetationIndex table
    ├── fetch_nws_alerts()         → NWS API → Redis
    ├── fetch_wind_data()          → NOAA/OpenWeather → Redis
    └── POST /predict/progression  → FastAPI ML Adapter
          └── store_geojson_result() → PostGIS + Redis cache

NFR-R05: Exponential backoff retry logic on all external API calls.
NFR-O01: Structured JSON logging for all task events.
"""

import json
import logging
import time
from datetime import datetime, timezone

import requests
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

logger = logging.getLogger(__name__)

# Redis cache keys (must match telemetry/views.py constants)
WIND_CACHE_KEY = "ffwai:wind_current"
ALERTS_CACHE_KEY = "ffwai:nws_alerts"
CURRENT_RISK_CACHE_KEY = "ffwai:current_risk_map"


# ===========================================================================
# MAIN ORCHESTRATOR TASK
# Scheduled daily by Celery Beat (settings.CELERY_BEAT_SCHEDULE)
# ===========================================================================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes between retries — NFR-R05
    name="harvester.tasks.trigger_daily_inference",
)
def trigger_daily_inference(self):
    """
    Daily orchestration task. Runs at 06:00 UTC (configured in settings.py).

    Orchestrates the full data harvest and ML inference pipeline:
    1. Harvest satellite + weather + alert data
    2. POST feature payload to FastAPI ML Adapter
    3. Write GeoJSON result to PostGIS + Redis cache

    NFR-R04: On ML adapter failure, system falls back to last cached GeoJSON.
    NFR-R05: Exponential backoff retry on network failures.
    NFR-O01: All events logged as structured JSON.
    """
    run_start = time.monotonic()
    logger.info(
        '{"event": "harvest_start", "task_id": "%s", "timestamp": "%s"}',
        self.request.id,
        datetime.now(timezone.utc).isoformat(),
    )

    try:
        # Step 1: Harvest environmental data (run in parallel in future)
        fetch_nws_alerts.delay()
        fetch_wind_data.delay()
        fetch_vegetation_indices.delay()
        fetch_goes18_imagery.delay()
        fetch_viirs_hotspots.delay()

        # Step 2: Build feature payload for ML Adapter
        # PLACEHOLDER: In Month 2, this will assemble the actual feature
        # tensor from PostGIS + GCS data and send it to FastAPI.
        # For now, the ML Adapter responds with mock GeoJSON when
        # MOCK_INFERENCE=True (settings.py).
        feature_payload = _build_feature_payload()

        # Step 3: POST to FastAPI ML Adapter
        geojson_result = _call_ml_adapter(feature_payload)

        if geojson_result is None:
            logger.warning(
                '{"event": "harvest_ml_failure", "action": "falling_back_to_cache"}'
            )
            # AP architecture: system remains available with stale data (NFR-R04)
            return {"status": "partial", "reason": "ML adapter unreachable — using cached data"}

        # Step 4: Store result to PostGIS + Redis
        predictions_written = store_geojson_result(geojson_result)

        duration = time.monotonic() - run_start
        logger.info(
            '{"event": "harvest_complete", "predictions_written": %d, "duration_seconds": %.2f}',
            predictions_written,
            duration,
        )
        return {"status": "success", "predictions_written": predictions_written}

    except Exception as exc:
        logger.error('{"event": "harvest_error", "error": "%s"}', str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries * 60)


# ===========================================================================
# ML ADAPTER COMMUNICATION
# ===========================================================================

def _build_feature_payload() -> dict:
    """
    Assembles the feature payload to send to the FastAPI ML Adapter.

    PLACEHOLDER (Month 1): Returns empty dict — ML Adapter uses mock fixture.
    IMPLEMENTATION (Month 2): Load .npz file from GCS, convert to dict payload.

    ML Interface Contract §1.2: The ML team must specify the exact tensor
    shape and feature order before this function can be fully implemented.
    """
    logger.info('{"event": "feature_payload_build", "mock": %s}', settings.MOCK_INFERENCE)
    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "mock": settings.MOCK_INFERENCE,
        # TODO Month 2: Add actual feature arrays here
        # "features": load_features_from_gcs(date=today, bucket=settings.GCS_BUCKET_NAME)
    }


def _call_ml_adapter(payload: dict, retries: int = 3) -> dict | None:
    """
    POSTs the feature payload to the FastAPI ML Adapter and returns GeoJSON.

    NFR-R05: Implements exponential backoff retry (up to `retries` attempts).
    Design Doc §1.1: FastAPI ML Adapter endpoint POST /predict/progression.

    Returns the GeoJSON FeatureCollection dict, or None on failure.
    """
    url = f"{settings.ML_ADAPTER_URL}/predict/progression"
    for attempt in range(1, retries + 1):
        try:
            logger.info(
                '{"event": "ml_adapter_request", "attempt": %d, "url": "%s"}',
                attempt, url,
            )
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            wait = 2 ** attempt * 10  # Exponential backoff: 20s, 40s, 80s
            logger.warning(
                '{"event": "ml_adapter_retry", "attempt": %d, "wait_seconds": %d, "error": "%s"}',
                attempt, wait, str(exc),
            )
            if attempt < retries:
                time.sleep(wait)
    return None


# ===========================================================================
# RESULT STORAGE
# ===========================================================================

def store_geojson_result(geojson: dict) -> int:
    """
    Parses the GeoJSON FeatureCollection from the ML Adapter and writes:
      1. Individual FireRiskPrediction rows to PostGIS (Cloud SQL)
      2. Full GeoJSON to Redis cache (for fast REST polling — NFR-P01)

    ML Interface Contract §3.1: Expected GeoJSON structure.
    Returns the number of prediction rows written to the DB.
    """
    from predictions.models import FireRiskPrediction
    from grid.models import BayAreaGrid

    features = geojson.get("features", [])
    metadata = geojson.get("metadata", {})
    timestamp_str = metadata.get("timestamp", datetime.now(timezone.utc).isoformat())
    source_model = metadata.get("source_model", "mock")

    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except ValueError:
        timestamp = datetime.now(timezone.utc)

    predictions_to_create = []
    for feature in features:
        props = feature.get("properties", {})
        grid_id = props.get("grid_id")
        fire_prob = props.get("fire_probability")
        risk_label = props.get("risk_label", "LOW_RISK")

        if grid_id is None or fire_prob is None:
            logger.warning('{"event": "store_skip", "reason": "missing grid_id or fire_probability"}')
            continue

        predictions_to_create.append(FireRiskPrediction(
            grid_id=grid_id,
            timestamp=timestamp,
            source_model=source_model,
            fire_probability=fire_prob,
            risk_label=risk_label,
        ))

    # Atomic bulk insert — ffwai-django-celery skill: wrap PostGIS writes in
    # transaction.atomic() so partial data is never exposed to the A* routing
    # engine if the insert crashes mid-way. Redis write is intentionally outside
    # the transaction since Redis does not participate in PostgreSQL transactions.
    with transaction.atomic():
        FireRiskPrediction.objects.bulk_create(predictions_to_create, ignore_conflicts=True)

    # Update Redis cache with the full GeoJSON (REST polling reads this — NFR-P01)
    cache.set(CURRENT_RISK_CACHE_KEY, json.dumps(geojson), timeout=60 * 60 * 48)  # 48h — NFR-R04
    logger.info('{"event": "store_complete", "predictions_written": %d}', len(predictions_to_create))

    return len(predictions_to_create)


# ===========================================================================
# INDIVIDUAL HARVESTER TASKS (Stubs — fully implemented in Week 2)
# ===========================================================================

@shared_task(name="harvester.tasks.fetch_goes18_imagery")
def fetch_goes18_imagery():
    """
    PLACEHOLDER — Week 2 Implementation.

    Fetches the daily GOES-18 fire detection composite from GEE:
      GEE Collection: NOAA/GOES/18/FDCC
      GEE Collection: NOAA/GOES/18/MCMIPC

    Exports processed composite to GCS:
      gs://{GCS_BUCKET_NAME}/daily/{date}/goes18_fire.tif

    ML Interface Contract §1.1: This data is provided to the ML team
    via GCS for model training and daily inference.
    """
    logger.info('{"event": "fetch_goes18", "status": "STUB — not yet implemented"}')
    # TODO Week 2:
    # import ee
    # ee.Initialize(credentials=...)
    # collection = ee.ImageCollection('NOAA/GOES/18/FDCC') ...


@shared_task(name="harvester.tasks.fetch_viirs_hotspots")
def fetch_viirs_hotspots():
    """
    PLACEHOLDER — Week 2 Implementation.

    Fetches VIIRS active fire hotspots from GEE:
      GEE Collection: NASA/VIIRS/002/VNP09GA

    Exports to GCS for ML team access.
    Paired with GOES-18 for super-resolution training (advisor suggestion).
    """
    logger.info('{"event": "fetch_viirs", "status": "STUB — not yet implemented"}')


@shared_task(name="harvester.tasks.fetch_vegetation_indices")
def fetch_vegetation_indices():
    """
    PLACEHOLDER — Week 2 Implementation.

    Fetches NDVI/EVI/NDWI from Landsat 8/9 via GEE:
      GEE Collection: LANDSAT/LC09/C02/T1_L2

    Writes results to: grid.VegetationIndex table in PostGIS.

    Research Reference: Used in all three advisor papers as a
    critical fire risk feature (vegetation fuel load indicator).
    """
    logger.info('{"event": "fetch_vegetation", "status": "STUB — not yet implemented"}')


@shared_task(name="harvester.tasks.fetch_nws_alerts")
def fetch_nws_alerts():
    """
    Fetches active NWS Red Flag Warnings for the Bay Area.
    Writes GeoJSON FeatureCollection to Redis cache.

    API: https://api.weather.gov/alerts/active?area=CA
    Served by: GET /api/telemetry/alerts/
    FR-E04: Red Flag Warning polygon overlay requirement.
    """
    try:
        headers = {"User-Agent": settings.NWS_API_USER_AGENT}
        response = requests.get(
            "https://api.weather.gov/alerts/active?area=CA&event=Red+Flag+Warning",
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        geojson = response.json()

        cache.set(ALERTS_CACHE_KEY, json.dumps(geojson), timeout=60 * 60 * 6)  # 6h TTL
        logger.info(
            '{"event": "fetch_nws_alerts", "features_count": %d}',
            len(geojson.get("features", [])),
        )
    except Exception as exc:
        logger.error('{"event": "fetch_nws_alerts_error", "error": "%s"}', str(exc))


@shared_task(name="harvester.tasks.fetch_wind_data")
def fetch_wind_data():
    """
    PLACEHOLDER — Week 2 Implementation.

    Fetches current wind speed and direction from NOAA/OpenWeather.
    Writes structured JSON to Redis cache.

    Served by: GET /api/telemetry/wind/
    FR-E04: Wind data for Deck.gl animated particle vectors.
    """
    logger.info('{"event": "fetch_wind", "status": "STUB — not yet implemented"}')
    # TODO Week 2:
    # api_key = settings.OPENWEATHER_API_KEY
    # response = requests.get(
    #     f"https://api.openweathermap.org/data/2.5/weather?..."
    # )
