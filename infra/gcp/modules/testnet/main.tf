# Testnet topology module for the XRIQ GCP public testnet (TEST-ONLY).
#
# Provisions a small multi-node XRIQ testnet: one seed node (block producer +
# faucet) and `follower_count` follower nodes that stay in sync via peer-sync.
# All VMs are PRIVATE (no external IP); operator access is via IAP SSH. Peer +
# read HTTP (:8899) is reachable only between testnet nodes (network tags), never
# from the public internet. This runs the test-only signature scheme and carries
# NO monetary value. Created only when a human runs `terraform apply` with
# enable_testnet = true; nothing is applied from automation.

variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "zone" {
  type = string
}

variable "network_id" {
  type = string
}

variable "subnet_id" {
  type = string
}

variable "machine_type" {
  type = string
}

variable "ssh_user" {
  type = string
}

variable "ssh_public_key" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "labels" {
  type = map(string)
}

variable "follower_count" {
  type        = number
  default     = 1
  description = "Number of follower nodes that peer-sync from the seed."
}

locals {
  # Shared boot/network/identity settings for every testnet VM.
  boot_image   = "debian-cloud/debian-12"
  ssh_metadata = { ssh-keys = "${var.ssh_user}:${var.ssh_public_key}" }
}

# Seed node: authoritative producer + faucet. Serves read routes and the peer
# endpoints (/v1/peer/identity,/blocks,/peers) on :8899.
resource "google_compute_instance" "seed" {
  project      = var.project_id
  name         = "${var.name_prefix}-testnet-seed"
  zone         = var.zone
  machine_type = var.machine_type
  tags         = ["xriq-node", "xriq-testnet", "xriq-testnet-seed"]
  labels       = var.labels

  boot_disk {
    initialize_params {
      image = local.boot_image
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet_id
    # No access_config block => no external IP (private only).
  }

  metadata = local.ssh_metadata

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }
}

# Follower nodes: each runs a genesis-parametrized testnet node plus a peer-sync
# timer that pulls validated blocks from the seed. Followers do not produce.
resource "google_compute_instance" "follower" {
  count        = var.follower_count
  project      = var.project_id
  name         = "${var.name_prefix}-testnet-follower-${count.index}"
  zone         = var.zone
  machine_type = var.machine_type
  tags         = ["xriq-node", "xriq-testnet", "xriq-testnet-follower"]
  labels       = var.labels

  boot_disk {
    initialize_params {
      image = local.boot_image
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet_id
  }

  metadata = local.ssh_metadata

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }
}

# Allow peer + read HTTP (:8899) ONLY between testnet nodes (by network tag).
# No public ingress; peers reach each other on the private VPC.
resource "google_compute_firewall" "testnet_peer" {
  project     = var.project_id
  name        = "${var.name_prefix}-testnet-peer"
  network     = var.network_id
  description = "XRIQ testnet peer/read HTTP between testnet nodes only (TEST-ONLY)."

  direction = "INGRESS"

  allow {
    protocol = "tcp"
    ports    = ["8899"]
  }

  source_tags = ["xriq-testnet"]
  target_tags = ["xriq-testnet"]
}

output "seed_internal_ip" {
  value = google_compute_instance.seed.network_interface[0].network_ip
}

output "seed_name" {
  value = google_compute_instance.seed.name
}

output "follower_internal_ips" {
  value = [for vm in google_compute_instance.follower : vm.network_interface[0].network_ip]
}
