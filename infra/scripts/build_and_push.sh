#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Fight Fire With AI - Build & Push Container Images to Artifact Registry
# ==============================================================================

PROJECT_ID="${1:-${GCP_PROJECT_ID:-}}"
REGION="${2:-us-central1}"
REPO_NAME="ffwai-docker-repo"
TAG="${3:-latest}"

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: GCP Project ID is required."
    echo "Usage: ./infra/scripts/build_and_push.sh <PROJECT_ID> [REGION] [TAG]"
    exit 1
fi

REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

echo "==> Ensuring Artifact Registry repository '${REPO_NAME}' exists..."
gcloud artifacts repositories describe "${REPO_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" &> /dev/null || \
gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Fight Fire With AI Container Images" \
    --project="${PROJECT_ID}"

echo "==> Building and pushing container images using Google Cloud Build..."

# 1. Django REST API & Celery Worker Image
echo "==> Building django-backend image..."
gcloud builds submit backend \
    --tag "${REGISTRY}/django-backend:${TAG}" \
    --project="${PROJECT_ID}"

# 2. FastAPI ML Adapter Image
echo "==> Building ml-adapter image..."
gcloud builds submit ml_adapter \
    --tag "${REGISTRY}/ml-adapter:${TAG}" \
    --project="${PROJECT_ID}"

# 3. U-Net Inference Microservice Image
echo "==> Building unet-service image..."
gcloud builds submit ml_services/unet_service \
    --tag "${REGISTRY}/unet-service:${TAG}" \
    --project="${PROJECT_ID}"

# 4. PIML Simulation Microservice Image
echo "==> Building piml-service image..."
gcloud builds submit ml_services/ml_pinn_service \
    --tag "${REGISTRY}/piml-service:${TAG}" \
    --project="${PROJECT_ID}"

echo "==> All images built and pushed successfully to ${REGISTRY}!"

