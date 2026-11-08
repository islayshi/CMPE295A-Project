#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Fight Fire With AI - Terraform Remote State Bucket Bootstrapper
# ==============================================================================
# This script provisions an encrypted, versioned Google Cloud Storage (GCS)
# bucket to hold the remote Terraform state for the infrastructure foundation.
# ==============================================================================

PROJECT_ID="${1:-${GCP_PROJECT_ID:-}}"
REGION="${2:-us-central1}"

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: GCP Project ID is required."
    echo "Usage: ./bootstrap_gcs_state.sh <PROJECT_ID> [REGION]"
    echo "   Or: export GCP_PROJECT_ID=<PROJECT_ID> && ./bootstrap_gcs_state.sh"
    exit 1
fi

BUCKET_NAME="ffwai-tf-state-${PROJECT_ID}"

echo "==> Configuring Terraform state bucket: gs://${BUCKET_NAME} in ${REGION}"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI is not installed or not in PATH."
    echo "Please run this in Google Cloud Shell or install Google Cloud SDK."
    exit 1
fi

# Ensure project is selected
gcloud config set project "${PROJECT_ID}" --quiet

# Check if bucket already exists
if gcloud storage buckets describe "gs://${BUCKET_NAME}" &> /dev/null; then
    echo "==> Bucket gs://${BUCKET_NAME} already exists."
else
    echo "==> Creating GCS bucket: gs://${BUCKET_NAME}..."
    gcloud storage buckets create "gs://${BUCKET_NAME}" \
        --project="${PROJECT_ID}" \
        --location="${REGION}" \
        --uniform-bucket-level-access
fi

# Enable Object Versioning for state safety
echo "==> Enabling object versioning on gs://${BUCKET_NAME}..."
gcloud storage buckets update "gs://${BUCKET_NAME}" --versioning

echo "==> Success! Configure your infra/terraform/main.tf with:"
cat <<EOF

terraform {
  backend "gcs" {
    bucket = "${BUCKET_NAME}"
    prefix = "terraform/foundation"
  }
}

EOF

