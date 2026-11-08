#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Fight Fire With AI - Production Cloud Run Services Rollout
# ==============================================================================
# Deploys:
# 1. Private U-Net Inference Microservice (port 8081)
# 2. Private PIML Physics Simulation Microservice (port 8082)
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

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: GCP Project ID is required."
    echo "Usage: ./infra/scripts/deploy_services.sh <PROJECT_ID> [REGION] [NETWORK] [SUBNET] [TAG]"
    exit 1
fi

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

echo "==> 1. Deploying private U-Net Inference Service..."
gcloud run deploy unet-service \
    --image="${REGISTRY}/unet-service:${TAG}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --ingress=internal \
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
    --ingress=internal \
    --service-account="sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-secrets="FIRMS_MAP_KEY=firms-map-key:latest" \
    --min-instances=0 \
    --max-instances=2 \
    --port=8082 \
    --memory=2Gi \
    --cpu=1

PIML_URL=$(gcloud run services describe piml-service --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')

echo "==> 3. Deploying private FastAPI ML Adapter..."
gcloud run deploy ml-adapter \
    --image="${REGISTRY}/ml-adapter:${TAG}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --ingress=internal \
    --service-account="sa-ml-services@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-env-vars="UNET_SERVICE_URL=${UNET_URL},PINN_SERVICE_URL=${PIML_URL}" \
    --min-instances=0 \
    --max-instances=3 \
    --port=8001 \
    --memory=1Gi \
    --cpu=1

ADAPTER_URL=$(gcloud run services describe ml-adapter --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')

# Query Redis host from Terraform outputs or Cloud Memorystore
REDIS_HOST=$(gcloud redis instances describe ffwai-redis --region="${REGION}" --project="${PROJECT_ID}" --format='value(host)' 2>/dev/null || echo "10.0.1.3")

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
    --set-env-vars="DEBUG=False,ALLOWED_HOSTS=*,DB_NAME=ffwai_db,DB_USER=ffwai_user,REDIS_URL=redis://${REDIS_HOST}:6379/0,ML_ADAPTER_URL=${ADAPTER_URL}" \
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
    --no-cpu-throttling \
    --network="${NETWORK}" \
    --subnet="${SUBNET}" \
    --vpc-egress=private-ranges-only \
    --service-account="sa-celery-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-secrets="DB_PASSWORD=ffwai-db-password:latest,SECRET_KEY=django-secret-key:latest,FIRMS_MAP_KEY=firms-map-key:latest" \
    --set-env-vars="DEBUG=False,DB_NAME=ffwai_db,DB_USER=ffwai_user,REDIS_URL=redis://${REDIS_HOST}:6379/0,CELERY_BROKER_URL=redis://${REDIS_HOST}:6379/0,ML_ADAPTER_URL=${ADAPTER_URL}" \
    --command="celery" \
    --args="-A,core,worker,-l,info,--concurrency=2" \
    --min-instances=1 \
    --max-instances=3 \
    --memory=2Gi \
    --cpu=1

echo "=============================================================================="
echo "Deployment Complete!"
echo "Django Backend Serving URL: ${DJANGO_URL}"
echo "ML Adapter URL (Internal):  ${ADAPTER_URL}"
echo "=============================================================================="

