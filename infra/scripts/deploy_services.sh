#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Fight Fire With AI - Production Cloud Run Services Rollout
# ==============================================================================
# Deploys:
# 1. Private U-Net Inference Microservice (port 8081)
# 2. Private PIML Physics Simulation Microservice (port 8082)
# 2b. Private Physics-informed Fusion UNet Microservice (port 8083)
# 3. Private FastAPI ML Adapter (port 8001)
# 4. Public Django REST API Backend (port 8000, Direct VPC Egress)
# 5. Background Celery Worker Pool (Direct VPC Egress)
# ==============================================================================

PROJECT_ID="${1:-${GCP_PROJECT_ID:-}}"
REGION="${2:-us-central1}"
NETWORK="${3:-ffwai-vpc}"
SUBNET="${4:-ffwai-vpc-subnet-${REGION}}"
REPO_NAME="ffwai-docker-repo"
TAG="${5:-latest}"
COMPONENT="${COMPONENT:-all}"

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: GCP Project ID is required."
    echo "Usage: ./infra/scripts/deploy_services.sh <PROJECT_ID> [REGION] [NETWORK] [SUBNET] [TAG]"
    exit 1
fi

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "ml" ]]; then
    echo "==> 1. Deploying private U-Net Inference Service..."
    gcloud run deploy unet-service \
        --image="${REGISTRY}/unet-service:${TAG}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --ingress=all \
        --no-allow-unauthenticated \
        --service-account="sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
        --min-instances=0 \
        --max-instances=2 \
        --port=8081 \
        --memory=4Gi \
        --cpu=2

    UNET_URL=$(gcloud run services describe unet-service --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')

    echo "==> 2. Deploying private PIML Simulation Service..."
    gcloud run deploy piml-service \
        --image="${REGISTRY}/piml-service:${TAG}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --ingress=all \
        --no-allow-unauthenticated \
        --service-account="sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
        --set-secrets="FIRMS_MAP_KEY=firms-map-key:latest" \
        --min-instances=0 \
        --max-instances=2 \
        --port=8082 \
        --memory=2Gi \
        --cpu=1

    PIML_URL=$(gcloud run services describe piml-service --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')

    echo "==> 2b. Deploying private Fusion UNet Service..."
    gcloud run deploy fusion-service \
        --image="${REGISTRY}/fusion-service:${TAG}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --ingress=all \
        --no-allow-unauthenticated \
        --service-account="sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
        --set-secrets="FIRMS_MAP_KEY=firms-map-key:latest" \
        --min-instances=0 \
        --max-instances=2 \
        --concurrency=1 \
        --timeout=300 \
        --port=8083 \
        --memory=4Gi \
        --cpu=2

    FUSION_URL=$(gcloud run services describe fusion-service --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')

    echo "==> 3. Deploying private FastAPI ML Adapter..."
    gcloud run deploy ml-adapter \
        --image="${REGISTRY}/ml-adapter:${TAG}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --ingress=all \
        --no-allow-unauthenticated \
        --network="${NETWORK}" \
        --subnet="${SUBNET}" \
        --vpc-egress=private-ranges-only \
        --service-account="sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
        --set-env-vars="MOCK_INFERENCE=false,UNET_SERVICE_URL=${UNET_URL},PINN_SERVICE_URL=${PIML_URL},FUSION_SERVICE_URL=${FUSION_URL}" \
        --timeout=300 \
        --min-instances=0 \
        --max-instances=3 \
        --port=8001 \
        --memory=1Gi \
        --cpu=1
fi

ADAPTER_URL=$(gcloud run services describe ml-adapter --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)' 2>/dev/null || echo "")

if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "backend" ]]; then
    # Query Redis host from Terraform outputs or Cloud Memorystore
    REDIS_HOST=$(gcloud redis instances describe ffwai-redis --region="${REGION}" --project="${PROJECT_ID}" --format='value(host)' 2>/dev/null || echo "10.178.96.131")

    # Query Cloud SQL private IP and instance name
    DB_INSTANCE=$(gcloud sql instances list --project="${PROJECT_ID}" --format='value(name)' 2>/dev/null | grep ffwai-postgres | head -n1 || echo "ffwai-postgres-7764938b")
    DB_HOST=$(gcloud sql instances describe "${DB_INSTANCE}" --project="${PROJECT_ID}" --format='value(ipAddresses[0].ipAddress)' 2>/dev/null || echo "10.178.0.5")

    echo "==> Using Database Host: ${DB_HOST} (${DB_INSTANCE}) and Redis: ${REDIS_HOST}"

    echo "==> 4. Deploying Django REST API Backend..."
    gcloud run deploy django-backend \
        --image="${REGISTRY}/django-backend:${TAG}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --ingress=all \
        --allow-unauthenticated \
        --network="${NETWORK}" \
        --subnet="${SUBNET}" \
        --vpc-egress=private-ranges-only \
        --service-account="sa-django-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
        --set-secrets="DB_PASSWORD=ffwai-db-password:latest,SECRET_KEY=django-secret-key:latest,FIRMS_MAP_KEY=firms-map-key:latest" \
        --set-env-vars="DEBUG=False,ALLOWED_HOSTS=*,MOCK_INFERENCE=false,DB_HOST=${DB_HOST},DB_PORT=5432,DB_NAME=ffwai_db,DB_USER=ffwai_user,REDIS_URL=redis://${REDIS_HOST}:6379/0,CELERY_BROKER_URL=redis://${REDIS_HOST}:6379/0,CELERY_RESULT_BACKEND=redis://${REDIS_HOST}:6379/1,ML_ADAPTER_URL=${ADAPTER_URL}" \
        --min-instances=0 \
        --max-instances=5 \
        --port=8000 \
        --memory=2Gi \
        --cpu=1

    DJANGO_URL=$(gcloud run services describe django-backend --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')

    echo "==> 5. Deploying Celery Worker Consumer Pool..."
    gcloud run deploy celery-worker \
        --image="${REGISTRY}/django-backend:${TAG}" \
        --region="${REGION}" \
        --project="${PROJECT_ID}" \
        --ingress=internal \
        --no-allow-unauthenticated \
        --no-cpu-throttling \
        --network="${NETWORK}" \
        --subnet="${SUBNET}" \
        --vpc-egress=private-ranges-only \
        --service-account="sa-celery-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
        --set-secrets="DB_PASSWORD=ffwai-db-password:latest,SECRET_KEY=django-secret-key:latest,FIRMS_MAP_KEY=firms-map-key:latest" \
        --set-env-vars="DEBUG=False,MOCK_INFERENCE=false,DB_HOST=${DB_HOST},DB_PORT=5432,DB_NAME=ffwai_db,DB_USER=ffwai_user,REDIS_URL=redis://${REDIS_HOST}:6379/0,CELERY_BROKER_URL=redis://${REDIS_HOST}:6379/0,CELERY_RESULT_BACKEND=redis://${REDIS_HOST}:6379/1,ML_ADAPTER_URL=${ADAPTER_URL}" \
        --command="python" \
        --args="run_celery_worker.py" \
        --port=8080 \
        --min-instances=1 \
        --max-instances=3 \
        --memory=2Gi \
        --cpu=1
fi

echo "==> 6. Setting inter-service Cloud Run IAM bindings..."
gcloud run services add-iam-policy-binding ml-adapter \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:sa-celery-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" --quiet || true

gcloud run services add-iam-policy-binding ml-adapter \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:sa-django-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" --quiet || true

gcloud run services add-iam-policy-binding unet-service \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" --quiet || true

gcloud run services add-iam-policy-binding piml-service \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" --quiet || true

gcloud run services add-iam-policy-binding fusion-service \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" --quiet || true

if [ -n "${DJANGO_URL:-}" ]; then
    echo "==> 7. Updating Cloud Scheduler jobs with Django Backend URL..."
    gcloud scheduler jobs update http ffwai-daily-inference-trigger \
        --project="${PROJECT_ID}" \
        --location="${REGION}" \
        --uri="${DJANGO_URL}/api/telemetry/harvest/trigger/" \
        --oidc-service-account-email="sa-cloud-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --oidc-token-audience="${DJANGO_URL}" \
        --quiet || true

    gcloud scheduler jobs update http ffwai-active-fire-scout-trigger \
        --project="${PROJECT_ID}" \
        --location="${REGION}" \
        --uri="${DJANGO_URL}/api/telemetry/scout/trigger/" \
        --oidc-service-account-email="sa-cloud-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --oidc-token-audience="${DJANGO_URL}" \
        --quiet || true

    gcloud scheduler jobs create http ffwai-aqi-trigger \
        --project="${PROJECT_ID}" \
        --location="${REGION}" \
        --schedule="*/30 * * * *" \
        --uri="${DJANGO_URL}/api/telemetry/aqi/trigger/" \
        --http-method=POST \
        --oidc-service-account-email="sa-cloud-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --oidc-token-audience="${DJANGO_URL}" \
        --quiet 2>/dev/null || \
    gcloud scheduler jobs update http ffwai-aqi-trigger \
        --project="${PROJECT_ID}" \
        --location="${REGION}" \
        --schedule="*/30 * * * *" \
        --uri="${DJANGO_URL}/api/telemetry/aqi/trigger/" \
        --http-method=POST \
        --oidc-service-account-email="sa-cloud-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
        --oidc-token-audience="${DJANGO_URL}" \
        --quiet || true
fi

echo "=============================================================================="
echo "Deployment Complete!"
echo "Django Backend Serving URL: ${DJANGO_URL}"
echo "ML Adapter URL (Internal):  ${ADAPTER_URL}"
echo "=============================================================================="

