# ==============================================================================
# Google Cloud Scheduler (Cron Triggers Replacing Celery Beat)
# ==============================================================================

resource "google_project_service" "cloudscheduler" {
  project            = var.project_id
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

# ------------------------------------------------------------------------------
# 1. Daily Wildfire Prediction Harvest Trigger (06:00 UTC)
# ------------------------------------------------------------------------------
resource "google_cloud_scheduler_job" "daily_inference_trigger" {
  name        = "ffwai-daily-inference-trigger"
  description = "Triggers daily GOES-18 / Earth Engine data ingestion and ML inference"
  schedule    = "0 6 * * *"
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${var.django_backend_url}/api/telemetry/harvest/trigger/"

    oidc_token {
      service_account_email = google_service_account.sa_cloud_scheduler.email
      audience              = var.django_backend_url
    }

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode("{\"source\": \"cloud-scheduler\", \"action\": \"daily_harvest\"}")
  }

  depends_on = [google_project_service.cloudscheduler]
}

# ------------------------------------------------------------------------------
# 2. Active Wildfire Hotspot Scout Trigger (Every 30 Minutes)
# ------------------------------------------------------------------------------
resource "google_cloud_scheduler_job" "active_fire_scout_trigger" {
  name        = "ffwai-active-fire-scout-trigger"
  description = "Polls NASA FIRMS satellite feeds every 30 minutes to detect active wildfire clusters"
  schedule    = "*/30 * * * *"
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "${var.django_backend_url}/api/telemetry/scout/trigger/"

    oidc_token {
      service_account_email = google_service_account.sa_cloud_scheduler.email
      audience              = var.django_backend_url
    }

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode("{\"source\": \"cloud-scheduler\", \"action\": \"firms_scout\"}")
  }

  depends_on = [google_project_service.cloudscheduler]
}

