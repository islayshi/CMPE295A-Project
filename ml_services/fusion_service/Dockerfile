# ==============================================================================
# Physics-informed fusion UNet service (model_type "fusion"), port 8083
# ==============================================================================
# Runs the U-Net service's code and weights and the PIML service's package in-process to build the fusion
# model's 33 input layers, then the 3 frozen fusion copies (NumPy). Build context = ml_services/:
#   gcloud builds submit ml_services --config ml_services/fusion_service/cloudbuild.yaml
#   docker build -f fusion_service/Dockerfile -t fusion-service ml_services      (local)
#   docker run --rm -p 8083:8083 -e FIRMS_MAP_KEY=<your key> fusion-service
# Pass the FIRMS key at run time (Secret Manager on GCP); never bake it into the image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AIP_HTTP_PORT=8083 \
    UNET_DIR=/app/unet \
    PINN_ROOT=/app \
    WILDFIRE_MODEL_DIR=/app/unet/models \
    WILDFIRE_STATIC_CACHE=/app/unet/static_ca_1km.npz \
    STATIC_LAYERS=/app/pinn_service/static/bay_area_static.npz

WORKDIR /app
COPY unet_service/requirements.txt /app/unet_requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/unet_requirements.txt "pydantic>=2.6"

COPY unet_service/settings.py unet_service/postprocessing.py unet_service/native_ingestion.py unet_service/inference.py /app/unet/
COPY unet_service/models /app/unet/models
COPY unet_service/static_ca_1km.npz /app/unet/static_ca_1km.npz
COPY ml_pinn_service/pinn_service /app/pinn_service
COPY fusion_service/serve.py /app/serve.py
COPY fusion_service/fusion /app/fusion
RUN rm -rf /app/pinn_service/tests /app/pinn_service/test_features && \
    find /app -name "firms_key*.txt" -delete

RUN useradd --create-home --uid 10001 app && \
    mkdir -p /tmp/goes_cache && \
    chown -R app:app /app /tmp/goes_cache

USER app
EXPOSE 8083
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"AIP_HTTP_PORT\",\"8083\")}/health')"
CMD ["sh", "-c", "exec uvicorn serve:app --host 0.0.0.0 --port ${AIP_HTTP_PORT:-8083}"]
