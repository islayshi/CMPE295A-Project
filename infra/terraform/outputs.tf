# ==============================================================================
# Terraform Outputs
# ==============================================================================

# ------------------------------------------------------------------------------
# Networking
# ------------------------------------------------------------------------------
output "vpc_network_id" {
  description = "The ID of the dedicated VPC network."
  value       = google_compute_network.ffwai_vpc.id
}

output "vpc_network_name" {
  description = "The name of the dedicated VPC network."
  value       = google_compute_network.ffwai_vpc.name
}

output "subnet_id" {
  description = "The ID of the private subnetwork used for Direct VPC Egress."
  value       = google_compute_subnetwork.ffwai_subnet.id
}

output "subnet_name" {
  description = "The name of the private subnetwork used for Direct VPC Egress."
  value       = google_compute_subnetwork.ffwai_subnet.name
}

# ------------------------------------------------------------------------------
# Cloud SQL (PostGIS)
# ------------------------------------------------------------------------------
output "cloud_sql_instance_name" {
  description = "Cloud SQL instance name."
  value       = google_sql_database_instance.postgres.name
}

output "cloud_sql_connection_name" {
  description = "Connection name for Cloud Run Unix socket integration (PROJECT:REGION:INSTANCE)."
  value       = google_sql_database_instance.postgres.connection_name
}

output "cloud_sql_private_ip" {
  description = "Private IP address of the PostgreSQL PostGIS instance."
  value       = google_sql_database_instance.postgres.private_ip_address
}

output "database_name" {
  description = "The application database name."
  value       = google_sql_database.ffwai_db.name
}

output "database_user" {
  description = "The primary database username."
  value       = google_sql_user.ffwai_user.name
}

# ------------------------------------------------------------------------------
# Memorystore for Redis
# ------------------------------------------------------------------------------
output "redis_host" {
  description = "Private IP address of the Memorystore Redis cache."
  value       = google_redis_instance.redis.host
}

output "redis_port" {
  description = "Port number of the Memorystore Redis instance."
  value       = google_redis_instance.redis.port
}

# ------------------------------------------------------------------------------
# Storage
# ------------------------------------------------------------------------------
output "features_bucket_name" {
  description = "Google Cloud Storage bucket for satellite imagery and cached features."
  value       = google_storage_bucket.features_bucket.name
}

# ------------------------------------------------------------------------------
# Identity & Service Accounts
# ------------------------------------------------------------------------------
output "django_backend_sa_email" {
  description = "Email of the Django REST API Cloud Run service account."
  value       = google_service_account.sa_django_backend.email
}

output "celery_worker_sa_email" {
  description = "Email of the Celery Worker Cloud Run service account."
  value       = google_service_account.sa_celery_worker.email
}

output "ml_services_sa_email" {
  description = "Email of the ML Adapter & microservices service account."
  value       = google_service_account.sa_ml_services.email
}

output "cloud_scheduler_sa_email" {
  description = "Email of the Cloud Scheduler invocation service account."
  value       = google_service_account.sa_cloud_scheduler.email
}

