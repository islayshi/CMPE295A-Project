"""
Django Settings — Fight Fire With AI (fightfirewai)

Design Document Reference: docs/design-doc.md
Architecture: GCP-native modular monolith
  - Cloud SQL (PostGIS) → local: docker-compose `db` service
  - Memorystore (Redis) → local: docker-compose `redis` service
  - Cloud Run             → local: python manage.py runserver

NFR References:
  NFR-S01: 100 concurrent REST users (gunicorn workers in prod)
  NFR-R04: Staleness < 48h — Redis cache TTL enforced here
  NFR-U01: OpenAPI 3.0 docs via drf-spectacular at /api/docs/
  NFR-O01: Structured JSON logging via Django logging config
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv() # Load variables from .env into os.environment

# ---------------------------------------------------------------------------
# Base Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security — loaded from environment, never hardcoded
# See: .env.example for setup instructions
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-fallback-key-replace-before-production"
)
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# ---------------------------------------------------------------------------
# Application Definition
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Django built-ins
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # GeoDjango — REQUIRED for PostGIS spatial fields and A* routing
    # Design Doc §1.1 Module 3: PostGIS spatial queries
    "django.contrib.gis",
    # Third-party
    "rest_framework",       # Django REST Framework — all API endpoints
    "corsheaders",          # CORS for React frontend polling
    "drf_spectacular",      # OpenAPI 3.0 auto-docs — NFR-U01
    # Project apps (each owns a distinct domain — see design-doc.md §1.1)
    "api",          # Legacy connection test — will be removed after full migration
    "grid",         # BayAreaGrid, TerrainFeature, VegetationIndex models
    "predictions",  # FireRiskPrediction, ModelPerformanceMetric models
    "harvester",    # Celery tasks: data harvest + ML inference trigger
    "routing",      # A* evacuation routing engine
    "telemetry",    # Wind, NWS alerts, emergency shelters (FEMA/CalOES)
    "metrics",      # Model performance dashboard — FR-E10
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",        # Must be FIRST
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

WSGI_APPLICATION = "core.wsgi.application"

# ---------------------------------------------------------------------------
# CORS — Allow React frontend to poll the REST API
# In production, restrict to the actual Cloud CDN / Cloud Run frontend URL
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all in dev; restrict in prod
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",    # Vite local dev server (React)
    "http://localhost:3000",    # Alternative React dev port
]

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database — PostgreSQL + PostGIS
# Design Doc §2: Cloud SQL (PostGIS) in production, docker-compose in dev
# GeoDjango requires the PostGIS-enabled engine
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": os.environ.get("DB_NAME", "ffwai_db"),
        "USER": os.environ.get("DB_USER", "ffwai_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "ffwai_password"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# ---------------------------------------------------------------------------
# Redis Cache — GeoJSON cache + Celery broker
# Design Doc §2: Memorystore (Redis) in production
# NFR-R04: Cache TTL of 48h prevents serving stale predictions
# ---------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "TIMEOUT": 60 * 60 * 48,  # 48 hours — NFR-R04 staleness limit
        "KEY_PREFIX": "ffwai",
    }
}

# ---------------------------------------------------------------------------
# Celery — Task queue for data harvesting and ML inference
# Design Doc §1.1 Module 1: Celery Beat daily cron
# Architecture Guide: Celery is the async task coordinator
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# Celery Beat schedule — daily inference cron (ADR-003)
# Runs at 06:00 UTC daily; configurable via env in production
CELERY_BEAT_SCHEDULE = {
    "trigger-daily-inference": {
        "task": "harvester.tasks.trigger_daily_inference",
        "schedule": 86400,  # 24 hours in seconds
    },
}

# ---------------------------------------------------------------------------
# Django REST Framework — All API endpoints
# Design Doc §8: API Endpoint Registry
# NFR-U01: OpenAPI docs enabled via drf-spectacular
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],  # No auth for MVP (public read)
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# drf-spectacular OpenAPI settings — NFR-U01
SPECTACULAR_SETTINGS = {
    "TITLE": "Fight Fire With AI API",
    "DESCRIPTION": (
        "Backend REST API for the Fight Fire With AI wildfire prediction and "
        "dynamic evacuation routing platform. Extends research from Malik et al. "
        "(Atmosphere 2021), Adhikari et al. (IEEE CCWC 2024), and Malik et al. "
        "(IEEE CCWC 2022)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ---------------------------------------------------------------------------
# ML Inference Configuration
# Design Doc §14: ML Integration Contract
# MOCK_INFERENCE=True during Month 1 — returns bay_area_fixture.json
# MOCK_INFERENCE=False during Month 2 — invokes Vertex AI endpoints
# ---------------------------------------------------------------------------
MOCK_INFERENCE = os.environ.get("MOCK_INFERENCE", "True") == "True"
ML_ADAPTER_URL = os.environ.get("ML_ADAPTER_URL", "http://localhost:8001")

# GCP Vertex AI — populated by ML team after model deployment (Month 2)
VERTEX_AI_PROJECT_ID = os.environ.get("VERTEX_AI_PROJECT_ID", "")
VERTEX_AI_LOCATION = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
VERTEX_UNET_ENDPOINT_ID = os.environ.get("VERTEX_UNET_ENDPOINT_ID", "")
VERTEX_PINN_ENDPOINT_ID = os.environ.get("VERTEX_PINN_ENDPOINT_ID", "")
VERTEX_RL_ENDPOINT_ID = os.environ.get("VERTEX_RL_ENDPOINT_ID", "")

# ---------------------------------------------------------------------------
# External API Keys
# ---------------------------------------------------------------------------
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "")
NWS_API_USER_AGENT = os.environ.get(
    "NWS_API_USER_AGENT",
    "FightFireWithAI/1.0 (contact@example.com)"
)
GCS_BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", "fightfirewai-features")
GEE_PROJECT_ID = os.environ.get("GEE_PROJECT_ID", "")

# ---------------------------------------------------------------------------
# Logging — Structured JSON logging for NFR-O01 observability
# In production: Cloud Logging picks up stdout JSON automatically
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{"time":"%(asctime)s","level":"%(levelname)s",'
                '"logger":"%(name)s","message":"%(message)s"}'
            ),
        },
        "verbose": {
            "format": "[%(levelname)s] %(asctime)s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose" if DEBUG else "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "harvester": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "predictions": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static Files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# Default Primary Key
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
