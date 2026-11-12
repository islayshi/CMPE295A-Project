#!/usr/bin/env bash
# ==============================================================================
# Fight Fire With AI (ffwai-prod) - Workload Identity Federation Setup
# ==============================================================================
# Configures keyless OpenID Connect (OIDC) authentication between GitHub Actions
# and Google Cloud Platform, allowing automated/manual deployments without
# storing static JSON private key files in GitHub Secrets.
#
# Usage:
#   ./infra/scripts/setup_workload_identity.sh [PROJECT_ID] [REPO]
#
# Examples:
#   ./infra/scripts/setup_workload_identity.sh ffwai-prod islayshi/CMPE295A-Project
#   DRY_RUN=1 ./infra/scripts/setup_workload_identity.sh
# ==============================================================================

set -euo pipefail

PROJECT_ID="${1:-ffwai-prod}"
REPO="${2:-islayshi/CMPE295A-Project}"
POOL_ID="github-actions-pool"
PROVIDER_ID="github-actions-provider"
SA_NAME="sa-github-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
DRY_RUN="${DRY_RUN:-false}"

echo "=============================================================================="
echo "Configuring GCP Workload Identity Federation for GitHub Actions"
echo "Project ID        : $PROJECT_ID"
echo "GitHub Repository : $REPO"
echo "Service Account   : $SA_EMAIL"
echo "Pool ID           : $POOL_ID"
echo "Provider ID       : $PROVIDER_ID"
echo "Dry Run           : $DRY_RUN"
echo "=============================================================================="

# Helper function to execute or preview commands
run_cmd() {
    if [[ "$DRY_RUN" == "true" || "$DRY_RUN" == "1" ]]; then
        echo "[DRY RUN] $*"
    else
        "$@"
    fi
}

# 1. Enable required Google Cloud APIs
echo "Step 1: Enabling required Google Cloud APIs..."
run_cmd gcloud services enable \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    sts.googleapis.com \
    cloudresourcemanager.googleapis.com \
    --project="$PROJECT_ID"

# 2. Get Project Number
if [[ "$DRY_RUN" == "true" || "$DRY_RUN" == "1" ]]; then
    PROJECT_NUMBER="492249904968"
else
    PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
fi
echo "Project Number: $PROJECT_NUMBER"

# 3. Create or verify Workload Identity Pool
echo "Step 2: Configuring Workload Identity Pool..."
if [[ "$DRY_RUN" == "true" || "$DRY_RUN" == "1" ]]; then
    run_cmd gcloud iam workload-identity-pools create "$POOL_ID" \
        --project="$PROJECT_ID" \
        --location="global" \
        --display-name="GitHub Actions Deployment Pool"
else
    if ! gcloud iam workload-identity-pools describe "$POOL_ID" --project="$PROJECT_ID" --location="global" &>/dev/null; then
        gcloud iam workload-identity-pools create "$POOL_ID" \
            --project="$PROJECT_ID" \
            --location="global" \
            --display-name="GitHub Actions Deployment Pool"
    else
        echo "Workload Identity Pool '$POOL_ID' already exists."
    fi
fi

# 4. Create or verify Workload Identity Provider
echo "Step 3: Configuring Workload Identity Provider with GitHub OIDC..."
if [[ "$DRY_RUN" == "true" || "$DRY_RUN" == "1" ]]; then
    run_cmd gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
        --project="$PROJECT_ID" \
        --location="global" \
        --workload-identity-pool="$POOL_ID" \
        --display-name="GitHub Actions OIDC Provider" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
        --attribute-condition="assertion.repository == '${REPO}'"
else
    if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
        --project="$PROJECT_ID" \
        --location="global" \
        --workload-identity-pool="$POOL_ID" &>/dev/null; then
        gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
            --project="$PROJECT_ID" \
            --location="global" \
            --workload-identity-pool="$POOL_ID" \
            --display-name="GitHub Actions OIDC Provider" \
            --issuer-uri="https://token.actions.githubusercontent.com" \
            --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
            --attribute-condition="assertion.repository == '${REPO}'"
    else
        echo "Workload Identity Provider '$PROVIDER_ID' already exists."
    fi
fi

# 5. Create or verify dedicated GitHub Actions Deployer Service Account
echo "Step 4: Configuring Service Account '$SA_NAME'..."
if [[ "$DRY_RUN" == "true" || "$DRY_RUN" == "1" ]]; then
    run_cmd gcloud iam service-accounts create "$SA_NAME" \
        --project="$PROJECT_ID" \
        --display-name="GitHub Actions Deployer"
else
    if ! gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
        gcloud iam service-accounts create "$SA_NAME" \
            --project="$PROJECT_ID" \
            --display-name="GitHub Actions Deployer"
    else
        echo "Service Account '$SA_NAME' already exists."
    fi
fi

# 6. Allow GitHub repository to impersonate the service account via Workload Identity
echo "Step 5: Binding Workload Identity User role to GitHub repository..."
run_cmd gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --project="$PROJECT_ID" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${REPO}" \
    --condition=None \
    --quiet

# 7. Grant required deployment roles to the deployer service account
echo "Step 6: Granting required deployment permissions to $SA_EMAIL..."
DEPLOYMENT_ROLES=(
    "roles/run.admin"
    "roles/iam.serviceAccountUser"
    "roles/artifactregistry.writer"
    "roles/cloudbuild.builds.editor"
    "roles/firebasehosting.admin"
    "roles/cloudsql.client"
    "roles/storage.admin"
    "roles/serviceusage.serviceUsageConsumer"
)

for role in "${DEPLOYMENT_ROLES[@]}"; do
    echo "  Granting $role..."
    run_cmd gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$role" \
        --condition=None \
        --quiet
done

# 8. Output configuration summary for GitHub Secrets
WIF_PROVIDER_URI="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"

echo ""
echo "=============================================================================="
echo "Workload Identity Federation Setup Complete!"
echo "=============================================================================="
echo "Add the following two secrets to your GitHub repository:"
echo "GitHub Repo: https://github.com/${REPO}/settings/secrets/actions"
echo ""
echo "Secret Name  : WIF_PROVIDER"
echo "Secret Value : $WIF_PROVIDER_URI"
echo ""
echo "Secret Name  : WIF_SERVICE_ACCOUNT"
echo "Secret Value : $SA_EMAIL"
echo "=============================================================================="
