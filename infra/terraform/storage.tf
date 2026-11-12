# ==============================================================================
# Google Cloud Storage (Satellite Rasters & Feature Cache)
# ==============================================================================

resource "google_storage_bucket" "features_bucket" {
  name                        = "fightfirewai-features-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age        = 30 # Retain satellite GeoTIFF and intermediate rasters for 30 days
      with_state = "ANY"
    }
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

