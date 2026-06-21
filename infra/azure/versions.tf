# Provider and version constraints for the XRIQ Azure infrastructure.
# This declares constraints only; it provisions nothing. State backend is left
# unconfigured so static validation (terraform init -backend=false; validate)
# needs no Azure access. A remote Azure Blob backend is configured per
# environment by the human maintainer before any apply.

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}
