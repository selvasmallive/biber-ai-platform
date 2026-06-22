# Provider and version constraints for the XRIQ GCP infrastructure.
# This declares constraints only; it provisions nothing. State backend is left
# unconfigured so static validation (terraform init -backend=false; validate)
# needs no GCP access. A remote GCS backend is configured per environment by the
# human maintainer before any apply.

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}
