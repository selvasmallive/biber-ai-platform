# Security module for the XRIQ GCP staging-devnet.
#
# Workload service account, Artifact Registry for container images, and a Secret
# Manager secret holding the database password. No secret is committed; the
# password is supplied at apply time and stored in Secret Manager.

variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "region" {
  type = string
}

variable "postgres_admin_password" {
  type      = string
  sensitive = true
}

variable "labels" {
  type = map(string)
}

resource "google_service_account" "workload" {
  project      = var.project_id
  account_id   = "${var.name_prefix}-workload"
  display_name = "XRIQ ${var.name_prefix} workload"
}

resource "google_artifact_registry_repository" "main" {
  project       = var.project_id
  location      = var.region
  repository_id = "${var.name_prefix}-containers"
  format        = "DOCKER"
  description   = "XRIQ staging-devnet container images"
  labels        = var.labels
}

resource "google_artifact_registry_repository_iam_member" "workload_reader" {
  project    = var.project_id
  location   = google_artifact_registry_repository.main.location
  repository = google_artifact_registry_repository.main.name
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.workload.email}"
}

resource "google_secret_manager_secret" "db_password" {
  project   = var.project_id
  secret_id = "${var.name_prefix}-db-password"
  labels    = var.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "db_password" {
  secret      = google_secret_manager_secret.db_password.id
  secret_data = var.postgres_admin_password
}

resource "google_secret_manager_secret_iam_member" "workload_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.db_password.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.workload.email}"
}

output "workload_service_account_email" {
  value = google_service_account.workload.email
}

output "artifact_registry_repository" {
  value = google_artifact_registry_repository.main.id
}

output "db_secret_id" {
  value = google_secret_manager_secret.db_password.secret_id
}
