# ==============================================================================
# U-Net Wildfire Spread Inference Service Container (Port 8081)
# ==============================================================================
# Predicts fire progression at [1, 3, 6] hour horizons using GOES-18 satellite
# imagery and static physiographic raster features.
# Compatible with standalone Cloud Run and Vertex AI custom container serving.
# ==============================================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AIP_HTTP_PORT=8081

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/

# Create application user and setup writable cache directory
RUN useradd --create-home --uid 10001 app && \
    mkdir -p /tmp/goes_cache && \
    chown -R app:app /app /tmp/goes_cache

USER app

EXPOSE 8081

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"AIP_HTTP_PORT\",\"8081\")}/health')"

CMD ["sh", "-c", "exec uvicorn serve:app --host 0.0.0.0 --port ${AIP_HTTP_PORT:-8081}"]
