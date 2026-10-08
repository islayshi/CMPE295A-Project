"""
Telemetry Views — Fight Fire With AI
"""

import json
import logging
import ee
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import EmergencyShelter

logger = logging.getLogger(__name__)

WIND_CACHE_KEY = "ffwai:wind_current"
ALERTS_CACHE_KEY = "ffwai:nws_alerts"
AQI_CACHE_KEY = "ffwai:aqi_data"

# --- Earth Engine Initialization ---
SERVICE_ACCOUNT_FILE = settings.BASE_DIR / 'gee_service_account.json'

try:
    credentials = ee.ServiceAccountCredentials(key_file=str(SERVICE_ACCOUNT_FILE))
    ee.Initialize(credentials)
    logger.info("Google Earth Engine initialized successfully in telemetry app.")
except Exception as e:
    logger.warning(f"GEE Initialization Warning: {e}")


@api_view(["GET"])
def get_gee_ndvi_tile(request):
    """
    GET /api/telemetry/gee/ndvi-tile/
    """
    try:
        roi = ee.Geometry.BBox(-122.6, 37.0, -121.5, 38.2)

        s2_collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(roi)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            .sort('system:time_start', False)
        )

        image = s2_collection.first()
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

        vis_params = {
            'min': 0.0,
            'max': 0.8,
            'palette': ['d73027', 'f46d43', 'fdae61', 'fee08b', 'd9ef8b', 'a6d96a', '66bd63', '1a9850']
        }

        map_id_dict = ndvi.getMapId(vis_params)
        map_id = map_id_dict['tile_fetcher'].url_format

        return JsonResponse({
            'status': 'success',
            'tile_url': map_id,
            'description': 'Sentinel-2 NDVI Vegetation Dryness Layer'
        })

    except Exception as e:
        logger.error(f"GEE tile generation failed: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@api_view(["GET"])
def aqi_data(request):
    cached = cache.get(AQI_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    logger.warning("aqi_data: Redis cache miss — harvester has not populated AQI data yet.")
    return Response({"aqi": None, "status": "Unavailable", "pm25": None})


@api_view(["GET"])
def wind_telemetry(request):
    cached = cache.get(WIND_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    logger.warning("wind_telemetry: Redis cache miss — harvester has not populated live wind data.")
    return Response([])


@api_view(["GET"])
def nws_alerts(request):
    cached = cache.get(ALERTS_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    logger.warning("nws_alerts: Redis cache miss — returning mock red flag warning")
    return Response({
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [-122.10, 37.69],
                        [-122.03, 37.69],
                        [-122.03, 37.64],
                        [-122.10, 37.64],
                        [-122.10, 37.69]
                    ]]
                }
            }
        ]
    })


@api_view(["GET"])
def emergency_shelters(request):
    queryset = EmergencyShelter.objects.all()

    county = request.query_params.get("county")
    if county:
        queryset = queryset.filter(county__icontains=county)

    features = []
    for shelter in queryset:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [shelter.location.x, shelter.location.y],
            },
            "properties": {
                "id": shelter.id,
                "name": shelter.name,
                "address": shelter.address,
                "county": shelter.county,
                "capacity": shelter.capacity,
                "source": shelter.source,
            },
        })

    return Response({
        "type": "FeatureCollection",
        "total": len(features),
        "features": features,
    })