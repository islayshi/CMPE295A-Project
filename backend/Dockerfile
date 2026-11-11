# ==============================================================================
# Fight Fire With AI - Django REST API & Celery Worker Base Container
# ==============================================================================
# Python: 3.12 (Debian Bookworm Slim)
# Includes GDAL, GEOS, and Proj libraries required by GeoDjango.
# Used for:
# 1. Cloud Run Service: django-backend (Gunicorn entrypoint)
# 2. Cloud Run Worker Pool: celery-worker (Celery worker command override)
# 3. Cloud Run Jobs: migrate-job, grid-job, shelter-job
# ==============================================================================

FROM python:3.12-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000

WORKDIR /app

# Install native GIS and database client libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    libgdal-dev \
    libgeos-dev \
    libpq-dev \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application source code
COPY . /app/

# Create unprivileged application user
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m django && \
    chown -R django:appgroup /app

USER django

EXPOSE 8000

# Health check probing Django health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health/ || exit 1

# Default entrypoint for Cloud Run HTTP service
CMD exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:${PORT} \
    --workers 3 \
    --threads 2 \
    --timeout 60 \
    --access-logfile - \
    --error-logfile -

