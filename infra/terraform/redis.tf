# ==============================================================================
# Google Cloud Memorystore for Redis 7.0 (Cache & Task Broker)
# ==============================================================================

resource "google_project_service" "redis" {
  project            = var.project_id
  service            = "redis.googleapis.com"
  disable_on_destroy = false
}

# Memorystore Redis Instance
resource "google_redis_instance" "redis" {
  name           = var.redis_instance_name
  tier           = "BASIC" # Basic standalone instance (scales to Standard HA if required)
  memory_size_gb = var.redis_memory_size_gb
  region         = var.region

  authorized_network = google_compute_network.ffwai_vpc.id
  connect_mode       = "PRIVATE_SERVICE_ACCESS"
  redis_version      = "REDIS_7_0"
  display_name       = "Fight Fire With AI Redis Cache and Celery Broker"

  redis_configs = {
    maxmemory-policy = "volatile-lru"
  }

  depends_on = [
    google_project_service.redis,
    google_service_networking_connection.private_vpc_connection
  ]
}

