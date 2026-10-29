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

    Query params:
      model   (optional): "ensemble" (default), "unet", "pinn", "rl"
      horizon (optional): integer horizon hours (0, 1, 3, 6)
    """
    raw_model = request.query_params.get("model")
    horizon_param = request.query_params.get("horizon")

    if raw_model:
        model_param = raw_model.lower().strip()
        if model_param == "piml":
            model_param = "pinn"
        cache_key = f"ffwai:predictions:current:{model_param}"
    else:
        model_param = "pinn"
        cache_key = CURRENT_RISK_CACHE_KEY

    feature_collection = None
    cached_data = cache.get(cache_key)
    if (not cached_data or (isinstance(cached_data, str) and '"features": []' in cached_data)) and cache_key == "ffwai:predictions:current:ensemble":
        cached_data = cache.get(CURRENT_RISK_CACHE_KEY)

    if cached_data:
        if isinstance(cached_data, dict):
            feature_collection = cached_data
        else:
            try:
                feature_collection = json.loads(cached_data)
            except (TypeError, ValueError):
                feature_collection = None

    if not feature_collection or not feature_collection.get("features"):
        import datetime as dt
        from predictions.models import FireIncident

        # 1. Multi-incident aggregation: if active fire incidents exist with recent predictions
        active_incidents = list(FireIncident.objects.filter(is_active=True).values_list("id", flat=True))
        if active_incidents:
            six_hours_ago = datetime.now(timezone.utc) - dt.timedelta(hours=6)
            active_polygons = PredictionPolygon.objects.filter(
                fire_incident_id__in=active_incidents,
                timestamp__gte=six_hours_ago,
            ).select_related("grid")

            if raw_model and model_param in ("unet", "pinn", "rl"):
                active_polygons = active_polygons.filter(source_model=model_param)
            elif raw_model and model_param == "ensemble":
                ensemble_polygons = active_polygons.filter(source_model="ensemble")
                if ensemble_polygons.exists():
                    active_polygons = ensemble_polygons

            if active_polygons.exists():
                serializer = PredictionPolygonGeoJSONSerializer(active_polygons, many=True)
                feature_collection = {
                    "type": "FeatureCollection",
                    "metadata": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "total_cells": active_polygons.count(),
                        "active_incidents": len(active_incidents),
                        "source_model": model_param if raw_model else "ensemble",
                    },
                    "features": serializer.data,
                }
                cache.set(cache_key, json.dumps(feature_collection), timeout=21600)
                if cache_key == "ffwai:predictions:current:ensemble":
                    cache.set(CURRENT_RISK_CACHE_KEY, json.dumps(feature_collection), timeout=21600)
                elif cache_key == CURRENT_RISK_CACHE_KEY:
                    cache.set("ffwai:predictions:current:ensemble", json.dumps(feature_collection), timeout=21600)

        # 2. Recent predictions fallback (unlinked incidents or recent active runs)
        if not feature_collection or not feature_collection.get("features"):
            from django.db.models import Q
            six_hours_ago = datetime.now(timezone.utc) - dt.timedelta(hours=6)
            qs = PredictionPolygon.objects.filter(
                timestamp__gte=six_hours_ago,
                timestamp__lte=datetime.now(timezone.utc),
            ).filter(
                Q(fire_incident__isnull=True) | Q(fire_incident__is_active=True)
            )
            if raw_model and model_param in ("unet", "pinn", "rl"):
                qs = qs.filter(source_model=model_param)
            elif raw_model and model_param == "ensemble":
                ensemble_qs = qs.filter(source_model="ensemble")
                if ensemble_qs.exists():
                    qs = ensemble_qs

            latest_prediction = qs.order_by("-timestamp").first()
            if latest_prediction:
                valid_polygons = qs.filter(timestamp=latest_prediction.timestamp).select_related("grid")
                serializer = PredictionPolygonGeoJSONSerializer(valid_polygons, many=True)
                feature_collection = {
                    "type": "FeatureCollection",
                    "metadata": {
                        "timestamp": latest_prediction.timestamp.isoformat(),
                        "total_cells": valid_polygons.count(),
                        "source_model": model_param,
                    },
                    "features": serializer.data,
                }
                cache.set(cache_key, json.dumps(feature_collection), timeout=21600)
                if cache_key == "ffwai:predictions:current:ensemble":
                    cache.set(CURRENT_RISK_CACHE_KEY, json.dumps(feature_collection), timeout=21600)
                elif cache_key == CURRENT_RISK_CACHE_KEY:
                    cache.set("ffwai:predictions:current:ensemble", json.dumps(feature_collection), timeout=21600)

        if not feature_collection or not feature_collection.get("features"):
            feature_collection = {
                "type": "FeatureCollection",
                "status": "no_active_fire",
                "metadata": {
                    "source_model": model_param,
                    "total_cells": 0,
                    "status": "no_active_fire",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                "features": []
            }

    # Optional horizon filtering - strictly scoped to [0, 1, 3, 6]
    ALLOWED_HORIZONS = (0, 1, 3, 6)
    if horizon_param is not None:
        try:
            val = float(horizon_param)
            if not val.is_integer():
                raise ValueError(f"Non-integer horizon '{horizon_param}'")
            target_h = int(val)
            if target_h not in ALLOWED_HORIZONS:
                return Response(
                    {"error": f"Invalid horizon '{horizon_param}'. Allowed horizons: {list(ALLOWED_HORIZONS)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            def _matches_horizon(feat, target):
                props = feat.get("properties", {})
                h = props.get("horizon_hours")
                if h is None:
                    h = props.get("lead_time_hours")
                if h is None:
                    return target == 0
                try:
                    return int(float(h)) == target
                except (ValueError, TypeError):
                    return False

            filtered_features = [
                f for f in feature_collection.get("features", [])
                if _matches_horizon(f, target_h)
            ]
            return Response({
                **feature_collection,
                "features": filtered_features,
                "metadata": {
                    **feature_collection.get("metadata", {}),
                    "total_cells": len(filtered_features),
                    "filtered_horizon": target_h,
                }
            })
        except (ValueError, TypeError):
            return Response(
                {"error": f"Invalid horizon '{horizon_param}'. Allowed horizons: {list(ALLOWED_HORIZONS)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


    return Response(feature_collection)


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
