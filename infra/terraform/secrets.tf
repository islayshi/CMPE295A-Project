# ==============================================================================
# Google Cloud Secret Manager (Secrets & Credentials)
# ==============================================================================

resource "google_project_service" "secretmanager" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

# Generate Django Secret Key if not provided
resource "random_password" "generated_django_secret_key" {
  length  = 50
  special = false
}

locals {
  effective_django_secret_key = var.django_secret_key != "" ? var.django_secret_key : random_password.generated_django_secret_key.result
}

# ------------------------------------------------------------------------------
# Secret: Django Cryptographic Secret Key
# ------------------------------------------------------------------------------
resource "google_secret_manager_secret" "django_secret_key" {
  secret_id = "django-secret-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "django_secret_key_version" {
  secret      = google_secret_manager_secret.django_secret_key.id
  secret_data = local.effective_django_secret_key
}

# ------------------------------------------------------------------------------
# Secret: Cloud SQL Database Password
# ------------------------------------------------------------------------------
resource "google_secret_manager_secret" "db_password" {
  secret_id = "ffwai-db-password"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "db_password_version" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = local.effective_db_password
}

# ------------------------------------------------------------------------------
# Secret: NASA FIRMS Map Key
# ------------------------------------------------------------------------------
resource "google_secret_manager_secret" "firms_map_key" {
  secret_id = "firms-map-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "firms_map_key_version" {
  count       = var.firms_map_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.firms_map_key.id
  secret_data = var.firms_map_key
}

