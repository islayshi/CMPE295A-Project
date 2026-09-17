"""
Root URL Configuration — Fight Fire With AI

Design Doc §8: API Endpoint Registry
All endpoints are prefixed with /api/ and routed to their
respective Django app url modules.

Endpoint summary:
  /api/predictions/current/     GET  Latest risk map (Redis cache)
  /api/predictions/history/     GET  Historical predictions
  /api/routing/evacuate/        POST A* evacuation route
  /api/telemetry/wind/          GET  Wind speed/direction
  /api/telemetry/shelters/      GET  FEMA/CalOES shelter POIs
  /api/telemetry/alerts/        GET  Active NWS Red Flag Warnings
  /api/metrics/                 GET  Model performance metrics
  /api/health/                  GET  System health check
  /api/docs/                    GET  OpenAPI 3.0 Swagger UI (NFR-U01)
  /api/schema/                  GET  Raw OpenAPI schema (JSON/YAML)
"""

from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    # Django Admin
    path("admin/", admin.site.urls),

    # -------------------------------------------------------
    # Core API Routes — see design-doc.md §8 API Endpoint Registry
    # -------------------------------------------------------
    path("api/predictions/", include("predictions.urls")),
    path("api/routing/", include("routing.urls")),
    path("api/telemetry/", include("telemetry.urls")),
    path("api/metrics/", include("metrics.urls")),

    # -------------------------------------------------------
    # System Endpoints
    # -------------------------------------------------------
    path("api/health/", include("api.urls")),    # Health check + legacy test

    # -------------------------------------------------------
    # OpenAPI 3.0 Documentation — NFR-U01
    # /api/schema/  → raw schema (JSON download)
    # /api/docs/    → Swagger UI
    # -------------------------------------------------------
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
