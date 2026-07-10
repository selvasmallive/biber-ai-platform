# Data module for the XRIQ GCP staging-devnet.
#
# A private-IP Cloud SQL for PostgreSQL read model and a Cloud Storage bucket for
# snapshots/backups/artifacts. The database has no public IP; it is reachable
# only over the VPC private services connection.

variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "network_id" {
  type = string
}

variable "private_vpc_connection" {
  description = "Id of the service networking connection; used to order creation after private services access is ready."
  type        = string
}

variable "bucket_name" {
  type = string
}

variable "postgres_tier" {
  type = string
}

variable "postgres_admin_user" {
  type = string
}

variable "postgres_admin_password" {
  type      = string
  sensitive = true
}

variable "db_deletion_protection" {
  type = bool
}

variable "labels" {
  type = map(string)
}

resource "google_storage_bucket" "artifacts" {
  project                     = var.project_id
  name                        = var.bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  labels                      = var.labels

  versioning {
    enabled = true
  }
}

resource "google_sql_database_instance" "main" {
  project             = var.project_id
  name                = "${var.name_prefix}-postgres"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.db_deletion_protection

  depends_on = [var.private_vpc_connection]

  settings {
    tier              = var.postgres_tier
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"
    disk_size         = 10
    disk_autoresize   = true
    user_labels       = var.labels

    ip_configuration {
      ipv4_enabled    = false
      private_network = var.network_id
    }

    backup_configuration {
      enabled = true
    }
  }
}

resource "google_sql_database" "main" {
  project  = var.project_id
  name     = "xriq"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "admin" {
  project  = var.project_id
  name     = var.postgres_admin_user
  instance = google_sql_database_instance.main.name
  password = var.postgres_admin_password
}

output "instance_connection_name" {
  value = google_sql_database_instance.main.connection_name
}

output "private_ip_address" {
  value = google_sql_database_instance.main.private_ip_address
}

output "bucket_name" {
  value = google_storage_bucket.artifacts.name
}
