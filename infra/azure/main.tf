# Root composition for the XRIQ Azure staging-devnet.
#
# IMPORTANT: This file wires module BOUNDARIES only. The modules declare their
# interfaces (inputs/outputs) and responsibilities but intentionally create no
# resources yet. Provisioning happens only after the human maintainer reviews a
# real `terraform plan` against an approved subscription and runs apply.
#
# The azurerm provider block carries no credentials. Authentication is resolved
# at apply time from the maintainer's `az login` session or a least-privilege
# service principal supplied via environment, never from this repository.

provider "azurerm" {
  features {}

  # subscription_id is intentionally omitted; it is supplied by the environment
  # (ARM_SUBSCRIPTION_ID or the active az login) at plan/apply time.
}

locals {
  name_prefix = "${var.project}-${var.environment}"
  common_tags = var.tags
}

module "network" {
  source = "./modules/network"

  name_prefix = local.name_prefix
  location    = var.location
  tags        = local.common_tags
}

module "security" {
  source = "./modules/security"

  name_prefix = local.name_prefix
  location    = var.location
  tags        = local.common_tags
}

module "data" {
  source = "./modules/data"

  name_prefix = local.name_prefix
  location    = var.location
  tags        = local.common_tags
}

module "compute" {
  source = "./modules/compute"

  name_prefix = local.name_prefix
  location    = var.location
  tags        = local.common_tags
}

module "observability" {
  source = "./modules/observability"

  name_prefix                     = local.name_prefix
  location                        = var.location
  monthly_budget_amount           = var.monthly_budget_amount
  budget_alert_threshold_percents = var.budget_alert_threshold_percents
  tags                            = local.common_tags
}
