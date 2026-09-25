"""
Telemetry Views — Fight Fire With AI
"""

import json
import logging

from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import EmergencyShelter

logger = logging.getLogger(__name__)

WIND_CACHE_KEY = "ffwai:wind_current"
ALERTS_CACHE_KEY = "ffwai:nws_alerts"


@api_view(["GET"])
def wind_telemetry(request):
    """
    GET /api/telemetry/wind/

    Returns the live wind vector field for Deck.gl rendering.
    Data is sourced from Redis, populated continuously by the Celery harvester.
    """
    cached = cache.get(WIND_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    logger.warning("wind_telemetry: Redis cache miss — harvester has not populated live wind data.")
    return Response([])


@api_view(["GET"])
def nws_alerts(request):
    """
    GET /api/telemetry/alerts/

    Returns active NWS Red Flag Warnings as a GeoJSON FeatureCollection.
    """
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
    """
    GET /api/telemetry/shelters/
    """
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
