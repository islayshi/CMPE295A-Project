# ==============================================================================
# Variables Definition
# ==============================================================================

variable "project_id" {
  description = "The Google Cloud Platform project ID."
  type        = string
}

variable "region" {
  description = "The GCP region for all provisioned infrastructure."
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment identifier (e.g. production, staging, development)."
  type        = string
  default     = "production"
}

# ------------------------------------------------------------------------------
# Networking
# ------------------------------------------------------------------------------

variable "network_name" {
  description = "Name of the dedicated Virtual Private Cloud (VPC) network."
  type        = string
  default     = "ffwai-vpc"
}

variable "subnet_cidr" {
  description = "Primary CIDR range for the private subnetwork."
  type        = string
  default     = "10.0.0.0/20"
}

# ------------------------------------------------------------------------------
# Cloud SQL (PostGIS)
# ------------------------------------------------------------------------------

variable "db_instance_name" {
  description = "Base name for the Cloud SQL PostgreSQL instance."
  type        = string
  default     = "ffwai-postgres"
}

variable "db_instance_tier" {
  description = "Machine type for the Cloud SQL instance. Recommended: db-custom-2-7680 (production) or db-f1-micro (dev)."
  type        = string
  default     = "db-custom-2-7680"
}

variable "db_name" {
  description = "Default database name for Fight Fire With AI."
  type        = string
  default     = "ffwai_db"
}

variable "db_user" {
  description = "Primary database user name."
  type        = string
  default     = "ffwai_user"
}

variable "db_password" {
  description = "Password for the database user. If left empty, a secure random password is generated."
  type        = string
  sensitive   = true
  default     = ""
}

# ------------------------------------------------------------------------------
# Memorystore for Redis
# ------------------------------------------------------------------------------

variable "redis_instance_name" {
  description = "Name of the Memorystore Redis instance."
  type        = string
  default     = "ffwai-redis"
}

variable "redis_memory_size_gb" {
  description = "Redis memory capacity in GiB. 1 GiB provides ample headroom for GeoJSON caching and Celery queues."
  type        = number
  default     = 1
}

# ------------------------------------------------------------------------------
# Secrets & Integrations
# ------------------------------------------------------------------------------

variable "django_secret_key" {
  description = "Secret key for Django cryptographic signing. If empty, a secure random string is generated."
  type        = string
  sensitive   = true
  default     = ""
}

variable "firms_map_key" {
  description = "NASA FIRMS API key for active wildfire hotspot data."
  type        = string
  sensitive   = true
  default     = ""
}

# ------------------------------------------------------------------------------
# Triggering Endpoints
# ------------------------------------------------------------------------------

variable "django_backend_url" {
  description = "The deployed URL of the Django backend service for Cloud Scheduler cron triggers (can be updated post-deployment)."
  type        = string
  default     = "https://placeholder-django-backend-url.run.app"
}

