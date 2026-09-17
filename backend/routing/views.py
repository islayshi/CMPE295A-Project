"""
Routing Views — Fight Fire With AI

A* evacuation routing engine. Accepts a user origin GPS point,
queries PostGIS for danger zones (FireRiskPrediction polygons marked
HIGH_RISK), and computes the shortest safe path to the nearest shelter.

Design Doc §8: POST /api/routing/evacuate/
Design Doc §1.1 Module 3: A* routing via GeoDjango + PostGIS
NFR-P02: Sub-2.0 second response time for Bay Area distances.

FR-E02: Dynamic A* routing avoiding danger_zone polygons.
"""

import logging
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)


@api_view(["POST"])
def evacuate(request):
    """
    POST /api/routing/evacuate/

    Calculates the optimal A* evacuation route from the user's
    current location to the nearest safe emergency shelter,
    routing around active HIGH_RISK fire prediction zones.

    Request body:
      {
        "origin": {
          "lat": 37.1234,
          "lon": -122.4567
        }
      }

    Response:
      {
        "type": "Feature",
        "geometry": {
          "type": "LineString",
          "coordinates": [[lon, lat], ...]
        },
        "properties": {
          "distance_km": 12.4,
          "estimated_duration_minutes": 18,
          "destination_shelter": "Chabot College Emergency Shelter",
          "danger_zones_avoided": 3
        }
      }

    NFR-P02: Must respond in < 2.0 seconds for Bay Area distances.
    FR-E02: Route must actively avoid PostGIS HIGH_RISK prediction polygons.
    """
    origin = request.data.get("origin")

    if not origin or "lat" not in origin or "lon" not in origin:
        return Response(
            {"error": "Request body must include `origin` with `lat` and `lon` fields."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lat = origin["lat"]
    lon = origin["lon"]

    # --- A* Routing Implementation (STUB — Week 3 implementation) ---
    # TODO: Implement GeoDjango spatial query for A* routing:
    #
    # Step 1: Get all HIGH_RISK polygons from the latest inference run
    #   latest_ts = FireRiskPrediction.objects.order_by('-timestamp').values('timestamp').first()
    #   danger_zones = FireRiskPrediction.objects.filter(
    #       timestamp=latest_ts['timestamp'], risk_label='HIGH_RISK'
    #   ).values_list('grid__geometry', flat=True)
    #
    # Step 2: Get all shelter locations
    #   shelters = EmergencyShelter.objects.all()
    #
    # Step 3: Run A* on Bay Area road graph (PostGIS pgrouting or custom impl)
    #   route = compute_astar_route(
    #       origin_point=Point(lon, lat, srid=4326),
    #       destinations=shelters,
    #       obstacles=danger_zones
    #   )
    #
    # Step 4: Return GeoJSON LineString

    logger.info("evacuate: stub called for origin lat=%s lon=%s", lat, lon)

    # MOCK RESPONSE — replaced in Week 3 with real A* implementation
    return Response({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [lon, lat],
                [lon + 0.02, lat + 0.01],
                [lon + 0.05, lat + 0.03],
            ],
        },
        "properties": {
            "distance_km": None,
            "estimated_duration_minutes": None,
            "destination_shelter": "STUB — A* routing not yet implemented",
            "danger_zones_avoided": 0,
            "note": "This is a stub response. Real A* routing implemented in Week 3.",
        },
    })
