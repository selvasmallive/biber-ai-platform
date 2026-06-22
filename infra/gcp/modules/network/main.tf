# Network module for the XRIQ GCP staging-devnet.
#
# Custom-mode VPC with a regional subnet, an internal-allow firewall, an optional
# operator SSH rule, and private services access so Cloud SQL gets a private IP.

variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "operator_allowed_cidr" {
  type    = string
  default = null
}

resource "google_compute_network" "main" {
  project                 = var.project_id
  name                    = "${var.name_prefix}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "main" {
  project                  = var.project_id
  name                     = "${var.name_prefix}-subnet"
  region                   = var.region
  network                  = google_compute_network.main.id
  ip_cidr_range            = "10.42.1.0/24"
  private_ip_google_access = true
}

resource "google_compute_firewall" "internal" {
  project   = var.project_id
  name      = "${var.name_prefix}-allow-internal"
  network   = google_compute_network.main.id
  direction = "INGRESS"

  allow {
    protocol = "tcp"
  }
  allow {
    protocol = "udp"
  }
  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.42.0.0/16"]
}

# Optional inbound SSH, only when an operator CIDR is provided.
resource "google_compute_firewall" "ssh" {
  count     = var.operator_allowed_cidr == null ? 0 : 1
  project   = var.project_id
  name      = "${var.name_prefix}-allow-operator-ssh"
  network   = google_compute_network.main.id
  direction = "INGRESS"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = [var.operator_allowed_cidr]
  target_tags   = ["xriq-node"]
}

# Private services access: reserve a range and peer with servicenetworking so
# Cloud SQL can use a private IP on this VPC.
resource "google_compute_global_address" "private_services" {
  project       = var.project_id
  name          = "${var.name_prefix}-psa-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_services" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_services.name]
}

output "network_id" {
  value = google_compute_network.main.id
}

output "subnet_id" {
  value = google_compute_subnetwork.main.id
}

output "private_vpc_connection" {
  value = google_service_networking_connection.private_services.id
}
