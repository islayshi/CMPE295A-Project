# ==============================================================================
# Cloud SQL for PostgreSQL 16 (Spatial PostGIS Database)
# ==============================================================================

resource "google_project_service" "sqladmin" {
  project            = var.project_id
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

# Generate secure random DB password if not explicitly supplied
resource "random_password" "generated_db_password" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

locals {
  effective_db_password = var.db_password != "" ? var.db_password : random_password.generated_db_password.result
}

# Cloud SQL PostgreSQL 16 Instance
resource "google_sql_database_instance" "postgres" {
  name             = "${var.db_instance_name}-${random_id.db_suffix.hex}"
  database_version = "POSTGRES_16"
  region           = var.region

  depends_on = [
    google_project_service.sqladmin,
    google_service_networking_connection.private_vpc_connection
  ]

  settings {
    tier              = var.db_instance_tier
    availability_type = "ZONAL" # Sized for cost efficiency; switch to REGIONAL for multi-zone HA
    disk_size         = 20
    disk_type         = "PD_SSD"
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled                                  = false # Zero public IP exposure
      private_network                               = google_compute_network.ffwai_vpc.id
      enable_private_path_for_google_cloud_services = true
    }

    # PostgreSQL configuration flags
    database_flags {
      name  = "max_connections"
      value = "100"
    }

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "04:00"
    }

    insights_config {
      query_insights_enabled  = true
      record_application_tags = true
    }
  }

  deletion_protection = false # Set to true in multi-tenant enterprise environments
}

# Default Database
resource "google_sql_database" "ffwai_db" {
  name     = var.db_name
  instance = google_sql_database_instance.postgres.name
}

# Default Database User
resource "google_sql_user" "ffwai_user" {
  name     = var.db_user
  instance = google_sql_database_instance.postgres.name
  password = local.effective_db_password
}

