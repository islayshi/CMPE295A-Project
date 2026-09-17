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
        from predictions.models import FireRiskPrediction
        latest = FireRiskPrediction.objects.order_by("-timestamp").first()
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
