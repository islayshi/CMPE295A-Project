"""
API App Views — Fight Fire With AI

Health check endpoint + legacy connection test.
Design Doc §8: GET /api/health/
NFR-O01: Health endpoint exposes DB, Redis, and inference staleness.
NFR-O02: System health monitoring.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
import ee
from django.http import JsonResponse
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health_check(request):
    """
    GET /api/health/

    Returns the operational status of all system components.
    Used for uptime monitoring (NFR-O02) and debugging staleness (NFR-R04).

    Response schema:
      {
        "status": "healthy" | "degraded",
        "db": "ok" | "error",
        "redis": "ok" | "error",
        "mock_inference": true | false,
        "last_inference_timestamp": "ISO8601" | null,
        "staleness_hours": float | null,
        "is_stale": bool
      }
    """
    health = {
        "status": "healthy",
        "db": "ok",
        "redis": "ok",
        "mock_inference": settings.MOCK_INFERENCE,
        "last_inference_timestamp": None,
        "staleness_hours": None,
        "is_stale": False,
    }

    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:
        logger.error("Health check: DB connection failed — %s", exc)
        health["db"] = "error"
        health["status"] = "degraded"

    # Check Redis connectivity
    try:
        cache.set("ffwai:health_ping", "pong", timeout=10)
        result = cache.get("ffwai:health_ping")
        if result != "pong":
            raise ValueError("Redis ping-pong mismatch")
    except Exception as exc:
        logger.error("Health check: Redis connection failed — %s", exc)
        health["redis"] = "error"
        health["status"] = "degraded"

    # Check prediction staleness (NFR-R04: alert if > 48h old)
    try:
        from predictions.models import PredictionPolygon
        latest = PredictionPolygon.objects.order_by("-timestamp").first()
        if latest:
            health["last_inference_timestamp"] = latest.timestamp.isoformat()
            staleness = timezone.now() - latest.timestamp
            health["staleness_hours"] = round(staleness.total_seconds() / 3600, 1)
            health["is_stale"] = staleness > timedelta(hours=48)
            if health["is_stale"]:
                health["status"] = "degraded"
    except Exception as exc:
        logger.warning("Health check: could not determine staleness — %s", exc)

    return Response(health)


@api_view(["GET"])
def connection_test(request):
    """Legacy connection test endpoint. Will be removed post-migration."""
    return Response({"message": "Backend is online!", "version": "1.0.0"})

SERVICE_ACCOUNT_FILE = settings.BASE_DIR / 'gee_service_account.json'

# Initialize GEE when module loads
try:
    credentials = ee.ServiceAccountCredentials(key_file=SERVICE_ACCOUNT_FILE)
    ee.Initialize(credentials)
except Exception as e:
    print(f"GEE Initialization warning: {e}")

@api_view(['GET'])
def get_gee_ndvi_tile(request):
    """
    Returns GEE tile URL template for Sentinel-2 NDVI (Vegetation Index).
    """
    try:
        # Define region: SF Bay Area / NorCal wildfire risk zone
        roi = ee.Geometry.BBox(-122.6, 37.0, -121.5, 38.2)
        
        # Get latest low-cloud Sentinel-2 image
        s2_collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(roi)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            .sort('system:time_start', False)
        )
        
        image = s2_collection.first()

        # Calculate NDVI: (NIR - Red) / (NIR + Red) -> (B8 - B4) / (B8 + B4)
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

        # Dry vegetation = Red/Yellow, Dense green = Dark Green
        vis_params = {
            'min': 0.0,
            'max': 0.8,
            'palette': ['d73027', 'f46d43', 'fdae61', 'fee08b', 'd9ef8b', 'a6d96a', '66bd63', '1a9850']
        }

        # Generate GEE tile URL template
        map_id = ee.data.getTileUrlTemplate(
            ndvi.getMapId(vis_params)
        )

        return JsonResponse({
            'status': 'success',
            'tile_url': map_id, # Format: https://earthengine.googleapis.com/.../tiles/{z}/{x}/{y}
            'description': 'Sentinel-2 NDVI Vegetation Layer'
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
