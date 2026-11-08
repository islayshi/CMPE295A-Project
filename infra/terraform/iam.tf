# ==============================================================================
# IAM & Least-Privilege Service Accounts
# ==============================================================================

resource "google_project_service" "iam" {
  project            = var.project_id
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

# ------------------------------------------------------------------------------
# 1. Django REST API Service Account
# ------------------------------------------------------------------------------
resource "google_service_account" "sa_django_backend" {
  account_id   = "sa-django-backend"
  display_name = "Fight Fire With AI Django Backend Service Account"
  description  = "Dedicated identity for Django REST API Cloud Run service"

  depends_on = [google_project_service.iam]
}

resource "google_project_iam_member" "django_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.sa_django_backend.email}"
}

resource "google_project_iam_member" "django_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.sa_django_backend.email}"
}

resource "google_storage_bucket_iam_member" "django_storage_viewer" {
  bucket = google_storage_bucket.features_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.sa_django_backend.email}"
}

# ------------------------------------------------------------------------------
# 2. Celery Harvester & Worker Service Account
# ------------------------------------------------------------------------------
resource "google_service_account" "sa_celery_worker" {
  account_id   = "sa-celery-worker"
  display_name = "Fight Fire With AI Celery Worker Service Account"
  description  = "Dedicated identity for Celery asynchronous background worker pool"

  depends_on = [google_project_service.iam]
}

resource "google_project_iam_member" "celery_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.sa_celery_worker.email}"
}

resource "google_project_iam_member" "celery_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.sa_celery_worker.email}"
}

resource "google_storage_bucket_iam_member" "celery_storage_admin" {
  bucket = google_storage_bucket.features_bucket.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.sa_celery_worker.email}"
}

# Google Earth Engine access via Application Default Credentials (ADC)
resource "google_project_iam_member" "celery_earthengine_viewer" {
  project = var.project_id
  role    = "roles/earthengine.viewer"
  member  = "serviceAccount:${google_service_account.sa_celery_worker.email}"
}

# Permission to invoke internal ML Adapter Cloud Run service
resource "google_project_iam_member" "celery_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.sa_celery_worker.email}"
}

# ------------------------------------------------------------------------------
# 3. Machine Learning Microservices Identity
# ------------------------------------------------------------------------------
resource "google_service_account" "sa_ml_services" {
  account_id   = "sa-ml-services"
  display_name = "Fight Fire With AI ML Services Service Account"
  description  = "Identity for FastAPI ML Adapter to invoke U-Net and PIML microservices"

  depends_on = [google_project_service.iam]
}

resource "google_project_iam_member" "ml_services_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.sa_ml_services.email}"
}

# ------------------------------------------------------------------------------
# 4. Cloud Scheduler Identity (Cron Triggers)
# ------------------------------------------------------------------------------
resource "google_service_account" "sa_cloud_scheduler" {
  account_id   = "sa-cloud-scheduler"
  display_name = "Fight Fire With AI Cloud Scheduler Identity"
  description  = "Invokes authenticated HTTP cron endpoints on the Django backend"

  depends_on = [google_project_service.iam]
}

resource "google_project_iam_member" "scheduler_run_invoker" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.sa_cloud_scheduler.email}"
}

