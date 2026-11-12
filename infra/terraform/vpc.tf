# ==============================================================================
# VPC Networking & Private Services Access
# ==============================================================================

# Enable required Google APIs
resource "google_project_service" "compute" {
  project            = var.project_id
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "servicenetworking" {
  project            = var.project_id
  service            = "servicenetworking.googleapis.com"
  disable_on_destroy = false
}

# Dedicated Virtual Private Cloud Network
resource "google_compute_network" "ffwai_vpc" {
  name                    = var.network_name
  auto_create_subnetworks = false
  description             = "Dedicated VPC for Fight Fire With AI serverless compute and private data stores"

  depends_on = [google_project_service.compute]
}

# Regional Subnetwork supporting Direct VPC Egress
resource "google_compute_subnetwork" "ffwai_subnet" {
  name                     = "${var.network_name}-subnet-${var.region}"
  ip_cidr_range            = var.subnet_cidr
  region                   = var.region
  network                  = google_compute_network.ffwai_vpc.id
  private_ip_google_access = true
  description              = "Subnetwork for Cloud Run Direct VPC Egress and private internal workloads"
}

# Global Internal IP allocation for Private Services Access (Cloud SQL & Redis)
resource "google_compute_global_address" "private_service_access_ip" {
  name          = "ffwai-private-services-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.ffwai_vpc.id
  description   = "Internal IP reservation for Google managed database and cache peering"

  depends_on = [google_project_service.servicenetworking]
}

# Private VPC Peering Connection for Google Managed Services
resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.ffwai_vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_service_access_ip.name]
}

# Internal Firewall Rule: Allow internal communication across private subnet
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.network_name}-allow-internal"
  network = google_compute_network.ffwai_vpc.name

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = [var.subnet_cidr]
}

