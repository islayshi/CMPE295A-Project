"""
Telemetry Views — Fight Fire With AI
"""

import json
import logging
import ee
from pathlib import Path
from datetime import datetime, timedelta
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
        # 1. Parse date parameter or default to today
        end_date_str = request.GET.get('end_date', datetime.utcnow().strftime('%Y-%m-%d'))
        end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        
        # Look back 30 days to collect enough overlapping passes for full coverage
        start_date_str = (end_dt - timedelta(days=30)).strftime('%Y-%m-%d')

        # 2. Bounding box covering the entire SF Bay Area
        bay_area_roi = ee.Geometry.BBox(-123.1, 36.8, -121.5, 38.8)

        # 3. Filter image collection across space and time
        s2_collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(bay_area_roi)
            .filterDate(start_date_str, end_date_str)
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
        )

        # Check if imagery exists in this range
        count = s2_collection.size().getInfo()
        if count == 0:
            return JsonResponse({
                'status': 'error',
                'message': f'No imagery found between {start_date_str} and {end_date_str}.'
            }, status=404)

        # 4. Create a median composite across all images and clip to Bay Area ROI
        composite = s2_collection.median().clip(bay_area_roi)

        # 5. Compute NDVI on the seamless composite
        ndvi = composite.normalizedDifference(['B8', 'B4']).rename('NDVI')

        # 6. Color palette (Red = low vegetation/dry, Green = healthy vegetation)
        vis_params = {
            'min': 0.0,
            'max': 0.8,
            'palette': ['d73027', 'f46d43', 'fdae61', 'fee08b', 'd9ef8b', 'a6d96a', '66bd63', '1a9850']
        }

        # 7. Generate Leaflet-compatible tile URL
        map_id_dict = ndvi.getMapId(vis_params)
        tile_url = map_id_dict['tile_fetcher'].url_format

        return JsonResponse({
            'status': 'success',
            'tile_url': tile_url,
            'date_range': f"{start_date_str} to {end_date_str}",
            'description': 'SF Bay Area Sentinel-2 30-Day NDVI Composite'
        })

    except Exception as e:
        logger.error(f"GEE tile generation failed: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@api_view(["GET"])
def get_gee_available_dates(request):
    """
    GET /api/telemetry/gee/available-dates/
    """
    try:
        bay_area_roi = ee.Geometry.BBox(-123.1, 36.8, -121.5, 38.8)

        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=365)

        s2_collection = (
            ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(bay_area_roi)
            .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
        )

        timestamps = s2_collection.aggregate_array('system:time_start').getInfo()

        available_dates = sorted(list(set([
            datetime.utcfromtimestamp(ts / 1000.0).strftime('%Y-%m-%d')
            for ts in timestamps
        ])))

        return JsonResponse({
            'status': 'success',
            'dates': available_dates
        })

    except Exception as e:
        logger.error(f"GEE available dates query failed: {e}")
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