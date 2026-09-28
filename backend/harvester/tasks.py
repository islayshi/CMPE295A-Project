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

def _get_gee_bounding_box():
    """
    Initializes Google Earth Engine via ADC and returns the ee.Geometry.Rectangle
    bounding box for the current BayAreaGrid in PostGIS.
    
    Returns None if GEE_PROJECT_ID is missing, the grid is empty, or init fails.
    """
    import ee
    from django.contrib.gis.db.models import Extent
    from grid.models import BayAreaGrid

    if not settings.GEE_PROJECT_ID:
        logger.warning('{"event": "gee_init_skip", "reason": "GEE_PROJECT_ID not set"}')
        return None

    try:
        # Initialize GEE using Application Default Credentials (ADC)
        ee.Initialize(project=settings.GEE_PROJECT_ID)

        # Dynamically calculate the bounding box from the PostGIS grid
        extent = BayAreaGrid.objects.aggregate(ext=Extent('geometry'))['ext']
        if not extent:
            logger.error('{"event": "gee_init_error", "error": "BayAreaGrid is empty"}')
            return None
        
        # extent format: (xmin, ymin, xmax, ymax)
        return ee.Geometry.Rectangle([extent[0], extent[1], extent[2], extent[3]])
    except Exception as exc:
        logger.error('{"event": "gee_init_error", "error": "%s"}', str(exc))
        return None


@shared_task(name="harvester.tasks.fetch_goes18_imagery", bind=True, max_retries=3, default_retry_delay=60)
def fetch_goes18_imagery(self):
    """
    Fetches the daily GOES-18 fire detection composite from GEE.
    """
    import ee
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info('{"event": "fetch_goes18_start", "date": "%s"}', run_date)

    roi = _get_gee_bounding_box()
    if not roi:
        return

    try:
        start_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime.now(timezone.utc)

        fdcc = ee.ImageCollection('NOAA/GOES/18/FDCC') \
            .filterBounds(roi) \
            .filterDate(start_time.isoformat(), end_time.isoformat())
        
        if fdcc.size().getInfo() == 0:
            logger.warning('{"event": "fetch_goes18_empty", "reason": "No imagery found"}')
            return

        daily_composite = fdcc.select(['Area', 'Temp']).max().clip(roi)

        export_path = f"daily/{run_date}/goes18_fire"
        task = ee.batch.Export.image.toCloudStorage(
            image=daily_composite,
            description=f'GOES18_Export_{run_date}',
            bucket=settings.GCS_BUCKET_NAME,
            fileNamePrefix=export_path,
            scale=2000,
            region=roi,
            fileFormat='GeoTIFF'
        )

        if settings.MOCK_INFERENCE:
            logger.info('{"event": "fetch_goes18_mock_bypass", "action": "skipped export.start()"}')
        else:
            task.start()
            logger.info('{"event": "fetch_goes18_export_started", "path": "%s"}', export_path)
            
    except Exception as exc:
        logger.error('{"event": "fetch_goes18_error", "error": "%s"}', str(exc))
        raise self.retry(exc=exc)


@shared_task(name="harvester.tasks.fetch_viirs_hotspots", bind=True, max_retries=3, default_retry_delay=60)
def fetch_viirs_hotspots(self):
    """
    Fetches VIIRS active fire hotspots from GEE.
      GEE Collection: NOAA/VIIRS/001/VNP14A1 (Thermal Anomalies/Fire)
      
    Crops the imagery to the exact BayAreaGrid extent and exports to GCS.
    MOCK MODE: bypasses task.start() when MOCK_INFERENCE=True.
    """
    import ee
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info('{"event": "fetch_viirs_start", "date": "%s"}', run_date)

    roi = _get_gee_bounding_box()
    if not roi:
        return

    try:
        # VNP14A1 is daily, we fetch the most recent available day
        start_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime.now(timezone.utc)

        viirs = ee.ImageCollection('NOAA/VIIRS/001/VNP14A1') \
            .filterBounds(roi) \
            .filterDate(start_time.isoformat(), end_time.isoformat())
            
        if viirs.size().getInfo() == 0:
            logger.warning('{"event": "fetch_viirs_empty", "reason": "No imagery found"}')
            return

        # MaxFRP = Fire Radiative Power (standard measure for fire intensity)
        daily_composite = viirs.select(['MaxFRP']).max().clip(roi)

        export_path = f"daily/{run_date}/viirs_fire"
        task = ee.batch.Export.image.toCloudStorage(
            image=daily_composite,
            description=f'VIIRS_Export_{run_date}',
            bucket=settings.GCS_BUCKET_NAME,
            fileNamePrefix=export_path,
            scale=1000, # VIIRS thermal native resolution is 1km
            region=roi,
            fileFormat='GeoTIFF'
        )

        if settings.MOCK_INFERENCE:
            logger.info('{"event": "fetch_viirs_mock_bypass", "action": "skipped export.start()"}')
        else:
            task.start()
            logger.info('{"event": "fetch_viirs_export_started", "path": "%s"}', export_path)
            
    except Exception as exc:
        logger.error('{"event": "fetch_viirs_error", "error": "%s"}', str(exc))
        raise self.retry(exc=exc)


@shared_task(name="harvester.tasks.fetch_vegetation_indices", bind=True, max_retries=3, default_retry_delay=60)
def fetch_vegetation_indices(self):
    """
    Fetches NDVI from Landsat 9 via GEE:
      GEE Collection: LANDSAT/LC09/C02/T1_L2
      
    Calculates zonal statistics (mean NDVI) for the BayAreaGrid and
    writes the results to the grid.VegetationIndex PostGIS table.
    
    MOCK MODE: bypasses execution when MOCK_INFERENCE=True.
    """
    import ee
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    logger.info('{"event": "fetch_veg_start", "date": "%s"}', run_date)

    roi = _get_gee_bounding_box()
    if not roi:
        return

    try:
        # Landsat 9 Surface Reflectance (daily overpass, if available)
        start_time = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime.now(timezone.utc)

        l9 = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2") \
            .filterBounds(roi) \
            .filterDate(start_time.isoformat(), end_time.isoformat())
            
        if l9.size().getInfo() == 0:
            logger.warning('{"event": "fetch_veg_empty", "reason": "No imagery found"}')
            return
            
        # Calculate NDVI: (NIR - Red) / (NIR + Red)
        # Landsat 9: SR_B5 is NIR (Near-Infrared), SR_B4 is Red
        def calculate_ndvi(image):
            ndvi = image.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI')
            return image.addBands(ndvi)
            
        ndvi_composite = l9.map(calculate_ndvi).select('NDVI').max().clip(roi)

        if settings.MOCK_INFERENCE:
            logger.info('{"event": "fetch_veg_mock_bypass", "action": "skipped GEE extraction and PostGIS write"}')
        else:
            # Month 2 Implementation:
            # 1. Convert PostGIS BayAreaGrid to ee.FeatureCollection
            # 2. Run ndvi_composite.reduceRegions(reducer=ee.Reducer.mean(), collection=grid_fc, scale=30)
            # 3. Export to GCS as CSV, then bulk_create into grid.VegetationIndex
            logger.info('{"event": "fetch_veg_execution", "action": "extracting zonal stats"}')
            pass
            
    except Exception as exc:
        logger.error('{"event": "fetch_veg_error", "error": "%s"}', str(exc))
        raise self.retry(exc=exc)


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


import math

@shared_task(name="harvester.tasks.fetch_wind_data", bind=True, max_retries=3, default_retry_delay=300)
def fetch_wind_data(self):
    """
    FR-E04: Wind data for animated particle vectors.
    Queries 9 coordinates across the Bay Area from Open-Meteo and uses
    Inverse Distance Weighting (IDW) interpolation to generate a true
    continuous atmospheric vector field.
    
    Formats the output strictly to the GFS JSON standard required by
    WebGL turn-key wind libraries.
    """
    try:
        import time
        # 3x3 Grid covering BayAreaGrid (38.3 to 36.9 lat, -122.9 to -121.5 lon)
        lats = [38.3, 37.95, 37.6, 37.25, 36.9]
        lons = [-122.9, -122.55, -122.2, -121.85, -121.5]
        
        samples = []
        for lat in lats:
            import time
            for lon in lons:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=wind_speed_10m,wind_direction_10m&wind_speed_unit=mph"
                try:
                    res = requests.get(url, timeout=20)
                except Exception:
                    time.sleep(1)
                    res = requests.get(url, timeout=20)
                time.sleep(0.2) # Avoid Open-Meteo throttling
                if res.status_code == 200:
                    data = res.json()
                    speed_mph = data.get("current", {}).get("wind_speed_10m", 0)
                    dir_deg = data.get("current", {}).get("wind_direction_10m", 0)
                    
                    rad = dir_deg * (math.pi / 180.0)
                    samples.append({
                        "lat": lat, "lon": lon,
                        "u": -speed_mph * math.sin(rad),
                        "v": -speed_mph * math.cos(rad)
                    })
                time.sleep(0.1) # Rate limit protection
                
        if not samples:
            raise Exception("Open-Meteo returned no data for all 25 points")

        # 40x40 IDW Interpolation
        nx, ny = 40, 40
        la1, lo1 = 38.3, -122.9
        la2, lo2 = 36.9, -121.5
        dx, dy = (lo2 - lo1) / (nx - 1), (la2 - la1) / (ny - 1)
        
        u_data, v_data = [], []
        
        for j in range(ny):
            lat = la1 + j * dy
            for i in range(nx):
                lon = lo1 + i * dx
                
                num_u, num_v, den = 0, 0, 0
                for s in samples:
                    dist_sq = (s['lon'] - lon)**2 + (s['lat'] - lat)**2
                    weight = 1e6 if dist_sq < 1e-6 else 1.0 / dist_sq
                    num_u += s['u'] * weight
                    num_v += s['v'] * weight
                    den += weight
                    
                u_data.append(round(num_u / den, 3))
                v_data.append(round(num_v / den, 3))
                
        # Export as GFS Wind JSON standard format
        gfs_payload = [
            {
                "header": { "parameterCategory": 2, "parameterNumber": 2, "nx": nx, "ny": ny, "lo1": lo1, "la1": la1, "dx": dx, "dy": dy },
                "data": u_data
            },
            {
                "header": { "parameterCategory": 2, "parameterNumber": 3, "nx": nx, "ny": ny, "lo1": lo1, "la1": la1, "dx": dx, "dy": dy },
                "data": v_data
            }
        ]
        
        cache.set(WIND_CACHE_KEY, json.dumps(gfs_payload), timeout=60 * 60 * 24)
        logger.info('{"event": "fetch_wind_success", "grid_points": %d}', nx * ny)
        return {"status": "success", "grid_points": nx * ny}

    except Exception as exc:
        logger.error('{"event": "fetch_wind_error", "error": "%s"}', str(exc))
        raise self.retry(exc=exc)
