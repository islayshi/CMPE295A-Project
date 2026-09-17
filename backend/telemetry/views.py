"""
Telemetry Views — Fight Fire With AI

Serves live environmental telemetry and static emergency POI data.
Wind and NWS alert data comes from Redis (populated by Celery harvesters).
Shelter data comes from PostGIS (loaded once via management command).

Design Doc §8:
  GET /api/telemetry/wind/      → Wind for Deck.gl particles (FR-E04)
  GET /api/telemetry/alerts/    → NWS Red Flag Warnings (FR-E04)
  GET /api/telemetry/shelters/  → FEMA/CalOES POIs (FR-E05)
"""

import json
import logging

from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import EmergencyShelter

logger = logging.getLogger(__name__)

# Redis cache keys (written by harvester Celery tasks)
WIND_CACHE_KEY = "ffwai:wind_current"
ALERTS_CACHE_KEY = "ffwai:nws_alerts"


@api_view(["GET"])
def wind_telemetry(request):
    """
    GET /api/telemetry/wind/

    Returns current wind speed and direction for the Bay Area.
    Data is fetched daily by the Celery harvester from NOAA/OpenWeather
    and cached in Redis.

    Response:
      {
        "speed_mph": 12.5,
        "direction_degrees": 225,
        "direction_label": "SW",
        "timestamp": "2026-09-16T18:00:00Z",
        "source": "NOAA/OpenWeather"
      }

    FR-E04: Wind data drives Deck.gl animated wind particle vectors.
    """
    cached = cache.get(WIND_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    # Cache miss — return placeholder until harvester populates Redis
    logger.warning("wind_telemetry: Redis cache miss — harvester not yet run")
    return Response({
        "speed_mph": None,
        "direction_degrees": None,
        "direction_label": None,
        "timestamp": None,
        "source": "NOAA/OpenWeather",
        "note": "Wind data not yet available. Celery harvester populates this cache daily.",
    })


@api_view(["GET"])
def nws_alerts(request):
    """
    GET /api/telemetry/alerts/

    Returns active NWS Red Flag Warnings as a GeoJSON FeatureCollection.
    Warnings are fetched by the Celery harvester from the NWS Alerts API
    and cached in Redis.

    Response: GeoJSON FeatureCollection (Polygons)

    FR-E04: Red Flag Warning polygon overlay on the Mapbox map.
    """
    cached = cache.get(ALERTS_CACHE_KEY)
    if cached:
        return Response(json.loads(cached))

    logger.warning("nws_alerts: Redis cache miss — harvester not yet run")
    return Response({
        "type": "FeatureCollection",
        "features": [],
        "note": "NWS alerts not yet available. Celery harvester populates this cache daily.",
    })


@api_view(["GET"])
def emergency_shelters(request):
    """
    GET /api/telemetry/shelters/

    Returns FEMA/CalOES emergency shelter locations as a GeoJSON
    FeatureCollection (Point features). Data is static and loaded
    once into PostGIS via `python manage.py load_shelters`.

    Query params:
      county (optional): Filter shelters by Bay Area county name.

    Response: GeoJSON FeatureCollection (Points)

    FR-E05: Emergency POI markers on the Mapbox map.
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
