"""
Routing Views — Fight Fire With AI

A* evacuation routing engine endpoint.
"""

import logging
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Distance
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from predictions.models import FireRiskPrediction
from telemetry.models import EmergencyShelter
from routing.engine import compute_astar_route, _haversine

logger = logging.getLogger(__name__)

@api_view(["POST"])
def evacuate(request):
    """
    POST /api/routing/evacuate/

    Calculates the optimal A* evacuation route from the user's
    current location to the nearest safe emergency shelter,
    routing around active HIGH_RISK fire prediction zones.
    """
    origin = request.data.get("origin")

    if not origin or "lat" not in origin or "lon" not in origin:
        return Response(
            {"error": "Request body must include `origin` with `lat` and `lon` fields."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    lat = origin["lat"]
    lon = origin["lon"]
    user_point = Point(lon, lat, srid=4326)

    # 1. Get blocked cells from the latest prediction run
    latest_ts = FireRiskPrediction.objects.order_by('-timestamp').values('timestamp').first()
    if latest_ts:
        blocked_cell_ids = set(FireRiskPrediction.objects.filter(
            timestamp=latest_ts['timestamp'], 
            risk_label='HIGH_RISK'
        ).values_list('grid_id', flat=True))
    else:
        blocked_cell_ids = set()

    # 2. Get the 3 nearest shelters
    nearest_shelters = EmergencyShelter.objects.annotate(
        distance=Distance('location', user_point)
    ).order_by('distance')[:3]

    if not nearest_shelters:
        return Response(
            {"error": "No emergency shelters found in the database. Please run the seed_shelters command."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # 3. Try routing to each shelter in order of proximity
    best_route = None
    best_shelter = None
    best_distance = float('inf')

    for shelter in nearest_shelters:
        logger.info("Attempting A* route to shelter: %s", shelter.name)
        route_points = compute_astar_route(user_point, shelter.location, blocked_cell_ids)
        
        if route_points:
            # Calculate distance of this specific route (not straight-line)
            route_dist = 0.0
            for i in range(len(route_points) - 1):
                route_dist += _haversine(
                    route_points[i].x, route_points[i].y, 
                    route_points[i+1].x, route_points[i+1].y
                )
            
            # If it's a valid route, let's just take the first one since we sorted by proximity
            # Alternatively, if we ran all 3, we could pick the one with the shortest route_dist.
            # To be thorough and match the design, we return the shortest successful route.
            if route_dist < best_distance:
                best_distance = route_dist
                best_route = route_points
                best_shelter = shelter

    if not best_route:
        return Response(
            {"error": "No safe evacuation route could be found to any nearby shelter."},
            status=status.HTTP_404_NOT_FOUND
        )

    # 4. Format as GeoJSON Feature
    # Estimate speed: 30 km/h in evacuation traffic -> 0.5 km/min
    duration_mins = int(best_distance / 0.5)

    return Response({
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[p.x, p.y] for p in best_route],
        },
        "properties": {
            "distance_km": round(best_distance, 2),
            "estimated_duration_minutes": duration_mins,
            "destination_shelter": best_shelter.name,
            "danger_zones_avoided": len(blocked_cell_ids),
        },
    })
