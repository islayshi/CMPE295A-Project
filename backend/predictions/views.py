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
from datetime import datetime

from django.conf import settings
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import FireRiskPrediction
from .serializers import FireRiskPredictionGeoJSONSerializer

logger = logging.getLogger(__name__)

CURRENT_RISK_CACHE_KEY = "ffwai:current_risk_map"


@api_view(["GET"])
def current_predictions(request):
    """
    GET /api/predictions/current/

    Returns the most recent complete fire risk prediction as a
    GeoJSON FeatureCollection. Reads from Redis cache first
    (written by harvester.tasks.store_geojson_result).

    Response: GeoJSON FeatureCollection with metadata envelope.

    FR-E01: Prediction Visualization — feeds Deck.gl grid heatmap.
    NFR-R04: If cache is cold, falls back to DB query (staleness check included).
    """
    # Attempt Redis cache read first — O(1) in-memory lookup
    cached = cache.get(CURRENT_RISK_CACHE_KEY)
    if cached:
        logger.info("current_predictions: serving from Redis cache")
        return Response(json.loads(cached))

    # Cache miss — fallback to database query (AP architecture: availability first)
    logger.warning(
        "current_predictions: Redis cache miss — falling back to DB query. "
        "This may indicate the Celery harvester has not run yet."
    )
    latest_timestamp = (
        FireRiskPrediction.objects
        .order_by("-timestamp")
        .values_list("timestamp", flat=True)
        .first()
    )

    if latest_timestamp is None:
        # No predictions exist yet — return mock hint if in mock mode
        if settings.MOCK_INFERENCE:
            return Response(
                {
                    "type": "FeatureCollection",
                    "metadata": {
                        "source_model": "mock",
                        "message": "No predictions yet. Trigger the harvester to generate data.",
                    },
                    "features": [],
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": "No predictions available. Harvester has not run yet."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    queryset = FireRiskPrediction.objects.filter(timestamp=latest_timestamp).select_related("grid")
    serializer = FireRiskPredictionGeoJSONSerializer(queryset, many=True)
    response_data = {
        "type": "FeatureCollection",
        "metadata": {"timestamp": latest_timestamp.isoformat(), "total_cells": queryset.count()},
        "features": serializer.data,
    }
    return Response(response_data)


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
    queryset = FireRiskPrediction.objects.all()

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
