#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Fight Fire With AI - Database Lifecycle Execution via Cloud Run Jobs
# ==============================================================================
# Executes schema migrations and spatial precomputations in run-to-completion
# jobs connected via Direct VPC Egress, eliminating instance boot race conditions.
# ==============================================================================

PROJECT_ID="${1:-${GCP_PROJECT_ID:-}}"
REGION="${2:-us-central1}"
NETWORK="${3:-ffwai-vpc}"
SUBNET="${4:-ffwai-vpc-subnet-${REGION}}"
REPO_NAME="ffwai-docker-repo"
TAG="${5:-latest}"

if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: GCP Project ID is required."
    echo "Usage: ./infra/scripts/run_migrations.sh <PROJECT_ID> [REGION] [NETWORK] [SUBNET] [TAG]"
    exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/django-backend:${TAG}"

# Query Cloud SQL private IP and instance name
DB_INSTANCE=$(gcloud sql instances list --project="${PROJECT_ID}" --format='value(name)' 2>/dev/null | grep ffwai-postgres | head -n1 || echo "ffwai-postgres-7764938b")
DB_HOST=$(gcloud sql instances describe "${DB_INSTANCE}" --project="${PROJECT_ID}" --format='value(ipAddresses[0].ipAddress)' 2>/dev/null || echo "10.178.0.5")

echo "==> Using Database Host: ${DB_HOST} (${DB_INSTANCE})"
echo "==> Configuring database migration and initialization Cloud Run Jobs..."

# 1. Database Schema Migrations Job
echo "==> Running schema migrations (python manage.py migrate)..."
gcloud run jobs deploy ffwai-migrate-job \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --network="${NETWORK}" \
    --subnet="${SUBNET}" \
    --vpc-egress=private-ranges-only \
    --service-account="sa-django-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-secrets="DB_PASSWORD=ffwai-db-password:latest,SECRET_KEY=django-secret-key:latest" \
    --set-env-vars="DB_HOST=${DB_HOST},DB_PORT=5432,DB_NAME=ffwai_db,DB_USER=ffwai_user,DEBUG=False" \
    --command="python" \
    --args="manage.py,migrate"

gcloud run jobs execute ffwai-migrate-job --region="${REGION}" --project="${PROJECT_ID}" --wait

# 2. Hexagonal Spatial Grid Generation Job (19,344 cells)
echo "==> Generating 19,344-cell hexagonal PostGIS grid..."
gcloud run jobs deploy ffwai-grid-job \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --network="${NETWORK}" \
    --subnet="${SUBNET}" \
    --vpc-egress=private-ranges-only \
    --service-account="sa-django-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-secrets="DB_PASSWORD=ffwai-db-password:latest,SECRET_KEY=django-secret-key:latest" \
    --set-env-vars="DB_HOST=${DB_HOST},DB_PORT=5432,DB_NAME=ffwai_db,DB_USER=ffwai_user,DEBUG=False" \
    --command="python" \
    --args="manage.py,generate_grid"

gcloud run jobs execute ffwai-grid-job --region="${REGION}" --project="${PROJECT_ID}" --wait

# 3. Emergency Shelter POI Seeding Job
echo "==> Seeding emergency shelter POIs..."
gcloud run jobs deploy ffwai-shelter-job \
    --image="${IMAGE}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --network="${NETWORK}" \
    --subnet="${SUBNET}" \
    --vpc-egress=private-ranges-only \
    --service-account="sa-django-backend@${PROJECT_ID}.iam.gserviceaccount.com" \
    --set-secrets="DB_PASSWORD=ffwai-db-password:latest,SECRET_KEY=django-secret-key:latest" \
    --set-env-vars="DB_HOST=${DB_HOST},DB_PORT=5432,DB_NAME=ffwai_db,DB_USER=ffwai_user,DEBUG=False" \
    --command="python" \
    --args="manage.py,seed_shelters"

gcloud run jobs execute ffwai-shelter-job --region="${REGION}" --project="${PROJECT_ID}" --wait

echo "==> Database migrations, spatial grid, and emergency shelters seeded successfully!"

