# Compute module for the XRIQ GCP staging-devnet.
#
# A single small Compute Engine VM to run the XRIQ node/API/indexer for staging.
# It has no external IP (private only); operator access is via the network's
# optional SSH firewall rule plus IAP/bastion added later. Admin auth is
# SSH-public-key only via instance metadata. No secrets are stored here.

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

resource "google_compute_instance" "node" {
  project      = var.project_id
  name         = "${var.name_prefix}-node"
  zone         = var.zone
  machine_type = var.machine_type
  tags         = ["xriq-node"]
  labels       = var.labels

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnet_id
    # No access_config block => no external IP (private only).
  }

  metadata = {
    ssh-keys = "${var.ssh_user}:${var.ssh_public_key}"
  }

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }
}

output "instance_id" {
  value = google_compute_instance.node.id
}

output "internal_ip" {
  value = google_compute_instance.node.network_interface[0].network_ip
}
