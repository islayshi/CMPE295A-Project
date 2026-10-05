"""
Predictions Views — Fight Fire With AI

Serves the core fire risk prediction data to the React frontend.
The frontend polls these endpoints every 5 minutes (REST polling MVP).

Design Doc §8: Django REST API — Predictions endpoints
  GET /api/predictions/current/  → Latest predictions from Redis cache
  GET /api/predictions/history/  → Historical predictions with date filter

NFR-R04: current/ reads from Redis cache (< 100ms).
         Falls back to DB query if cache is cold (AP architecture).
NFR-P01: Inference is async (Celery). These views only READ — they are fast.
"""

import json
import logging
from datetime import datetime, timezone

from django.conf import settings
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import PredictionPolygon
from .serializers import PredictionPolygonGeoJSONSerializer

logger = logging.getLogger(__name__)

CURRENT_RISK_CACHE_KEY = "ffwai:predictions:current"


@api_view(["GET"])
def current_predictions(request):
    """
    GET /api/predictions/current/

    Returns the most recent complete fire risk prediction as a
    GeoJSON FeatureCollection. Fetches from Redis cache O(1).
    """
    cached_data = cache.get("ffwai:predictions:current")
    if cached_data:
        try:
            return Response(json.loads(cached_data))
        except (TypeError, ValueError):
            pass
            
    latest_prediction = PredictionPolygon.objects.filter(
        timestamp__lte=datetime.now(timezone.utc)
    ).order_by("-timestamp").first()
    if latest_prediction:
        valid_polygons = PredictionPolygon.objects.filter(timestamp=latest_prediction.timestamp).select_related("grid")
        serializer = PredictionPolygonGeoJSONSerializer(valid_polygons, many=True)
        feature_collection = {
            "type": "FeatureCollection",
            "metadata": {
                "timestamp": latest_prediction.timestamp.isoformat(),
                "total_cells": valid_polygons.count()
            },
            "features": serializer.data,
        }
        cache.set("ffwai:predictions:current", json.dumps(feature_collection), timeout=3600)
        return Response(feature_collection)

    return Response({
        "type": "FeatureCollection",
        "features": []
    })


@api_view(["GET"])
def prediction_history(request):
    """
    GET /api/predictions/history/?start=YYYY-MM-DD&end=YYYY-MM-DD&model=unet

    Returns a paginated list of historical prediction timestamps and
    summary statistics. Supports optional date range and model filtering.

    Query params:
      start  (optional): ISO date string, filter predictions after this date
      end    (optional): ISO date string, filter predictions before this date
      model  (optional): source_model filter (unet | pinn | rl | ensemble | mock)

    FR-E01: Historical prediction review.
    """
    queryset = PredictionPolygon.objects.all()

    # Optional date range filter
    start = request.query_params.get("start")
    end = request.query_params.get("end")
    model_filter = request.query_params.get("model")

    if start:
        try:
            queryset = queryset.filter(timestamp__date__gte=datetime.fromisoformat(start).date())
        except ValueError:
            return Response({"error": "Invalid `start` date. Use YYYY-MM-DD."}, status=400)

    if end:
        try:
            queryset = queryset.filter(timestamp__date__lte=datetime.fromisoformat(end).date())
        except ValueError:
            return Response({"error": "Invalid `end` date. Use YYYY-MM-DD."}, status=400)

    if model_filter:
        queryset = queryset.filter(source_model=model_filter)

    # Return distinct inference timestamps (not every cell — that's thousands of rows)
    timestamps = (
        queryset.order_by("-timestamp")
        .values_list("timestamp", flat=True)
        .distinct()[:50]  # Limit to 50 most recent runs
    )

    return Response({
        "count": len(timestamps),
        "inference_runs": [ts.isoformat() for ts in timestamps],
    })
