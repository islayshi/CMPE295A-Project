#!/usr/bin/env bash
# ==============================================================================
# Fight Fire With AI (ffwai-prod) - Team IAM Access Provisioning Script
# ==============================================================================
# Usage:
#   ./infra/scripts/grant_team_access.sh <email-or-group> [collaborative|least-privilege] [project-id]
#
# Examples:
#   ./infra/scripts/grant_team_access.sh teammate@sjsu.edu
#   ./infra/scripts/grant_team_access.sh teammate@sjsu.edu collaborative ffwai-prod
#   ./infra/scripts/grant_team_access.sh ffwai-engineers@googlegroups.com least-privilege
# ==============================================================================

set -euo pipefail

TARGET="${1:-}"
MODEL="${2:-collaborative}"
PROJECT_ID="${3:-ffwai-prod}"
DRY_RUN="${DRY_RUN:-false}"

if [[ -z "$TARGET" || "$TARGET" == "-h" || "$TARGET" == "--help" ]]; then
    echo "Usage: $0 <email-or-group> [collaborative|least-privilege] [project-id]"
    echo ""
    echo "Arguments:"
    echo "  <email-or-group> : Google Account email (e.g. user@sjsu.edu) or Google Group"
    echo "  [model]          : 'collaborative' (Model A, recommended for capstone dev)"
    echo "                     or 'least-privilege' (Model B, granular production roles)"
    echo "  [project-id]     : GCP Project ID (defaults to 'ffwai-prod')"
    exit 1
fi

# Detect whether principal is a user or a Google group
if [[ "$TARGET" =~ ^group: ]] || [[ "$TARGET" =~ @googlegroups\.com$ ]]; then
    PRINCIPAL="${TARGET#group:}"
    MEMBER_SPEC="group:$PRINCIPAL"
else
    PRINCIPAL="${TARGET#user:}"
    MEMBER_SPEC="user:$PRINCIPAL"
fi

echo "=============================================================================="
echo "Fight Fire With AI - IAM Provisioning"
echo "Project   : $PROJECT_ID"
echo "Principal : $MEMBER_SPEC"
echo "Model     : $MODEL"
echo "=============================================================================="

# Define roles based on selected access model
ROLES=()
if [[ "$MODEL" == "collaborative" || "$MODEL" == "editor" ]]; then
    echo "Applying Model A: Collaborative Team Standard (Editor + ServiceAccountUser + FirebaseAdmin)..."
    ROLES=(
        "roles/editor"
        "roles/iam.serviceAccountUser"
        "roles/firebasehosting.admin"
    )
elif [[ "$MODEL" == "least-privilege" || "$MODEL" == "granular" ]]; then
    echo "Applying Model B: Granular Least Privilege Bundle..."
    ROLES=(
        "roles/run.admin"
        "roles/iam.serviceAccountUser"
        "roles/artifactregistry.writer"
        "roles/cloudbuild.builds.editor"
        "roles/cloudsql.client"
        "roles/secretmanager.secretAccessor"
        "roles/cloudscheduler.admin"
        "roles/firebasehosting.admin"
        "roles/logging.viewer"
    )
else
    echo "Error: Unknown model '$MODEL'. Expected 'collaborative' or 'least-privilege'."
    exit 1
fi

# Apply roles to project
for role in "${ROLES[@]}"; do
    if [[ "$DRY_RUN" == "true" || "$DRY_RUN" == "1" ]]; then
        echo "[DRY RUN] Would execute: gcloud projects add-iam-policy-binding $PROJECT_ID --member=\"$MEMBER_SPEC\" --role=\"$role\""
    else
        echo "Granting $role to $MEMBER_SPEC on $PROJECT_ID..."
        gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="$MEMBER_SPEC" \
            --role="$role" \
            --condition=None \
            --quiet > /dev/null
    fi
done

echo ""
echo "=============================================================================="
echo "IAM Roles Successfully Granted!"
echo "Target Member : $MEMBER_SPEC"
echo "Roles Assigned:"
for role in "${ROLES[@]}"; do
    echo "  - $role"
done
echo "------------------------------------------------------------------------------"
echo "NOTE: To grant access to the Firebase Web Console, also invite $PRINCIPAL at:"
echo "https://console.firebase.google.com/project/$PROJECT_ID/settings/usersandpermissions"
echo "=============================================================================="
