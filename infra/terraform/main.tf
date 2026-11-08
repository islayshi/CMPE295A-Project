# ==============================================================================
# Fight Fire With AI - Modular Terraform Foundation
# ==============================================================================
# Provisions:
# 1. Custom VPC network and subnet with Direct VPC Egress support
# 2. Private Services Access for Google Managed Services
# 3. Cloud SQL for PostgreSQL 16 (PostGIS enabled via extensions)
# 4. Memorystore for Redis 7.0 (Cache & Broker)
# 5. Cloud Storage (Satellite Imagery Rasters)
# 6. Secret Manager (DB password, Django secret key, FIRMS key)
# 7. Least-Privilege IAM Service Accounts
# 8. Cloud Scheduler Jobs (Cron triggers for Harvester & Scout)
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # ----------------------------------------------------------------------------
  # Remote GCS State Backend
  # ----------------------------------------------------------------------------
  # Uncomment after bootstrapping the bucket via infra/scripts/bootstrap_gcs_state.sh
  # backend "gcs" {
  #   bucket = "ffwai-tf-state-<PROJECT_ID>"
  #   prefix = "terraform/foundation"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Provider for generating random passwords and resource suffixes
provider "random" {}

resource "random_id" "db_suffix" {
  byte_length = 4
}

