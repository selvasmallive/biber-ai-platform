# Root composition for the XRIQ Azure staging-devnet.
#
# This wires the staging-devnet resources. It creates real resources when a
# human runs `terraform apply` against an approved subscription. Nothing is
# applied from automation: CI and this repo only run `terraform fmt` /
# `validate`. The azurerm provider carries no credentials; authentication is
# resolved at apply time from the maintainer's `az login` session or ARM_* env
# vars.

provider "azurerm" {
  features {}

  # subscription_id is supplied by the environment (ARM_SUBSCRIPTION_ID or the
  # active az login) at plan/apply time; it is intentionally not set here.
}

data "azurerm_client_config" "current" {}

locals {
  name_prefix          = "${var.project}-${var.environment}"
  resource_group_name  = "${var.project}-${var.environment}-rg"
  storage_account_name = substr(lower(replace("${var.project}${var.environment}${var.name_suffix}", "-", "")), 0, 24)
  key_vault_name       = substr("${var.project}-kv-${var.name_suffix}", 0, 24)
  acr_name             = substr(lower(replace("${var.project}acr${var.name_suffix}", "-", "")), 0, 50)
  postgres_name        = "${var.project}-pg-${var.environment}-${var.name_suffix}"
  common_tags          = var.tags
}

resource "azurerm_resource_group" "main" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.common_tags
}

module "network" {
  source = "./modules/network"

  name_prefix           = local.name_prefix
  resource_group_name   = azurerm_resource_group.main.name
  location              = var.location
  operator_allowed_cidr = var.operator_allowed_cidr
  tags                  = local.common_tags
}

module "security" {
  source = "./modules/security"

  name_prefix         = local.name_prefix
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  key_vault_name      = local.key_vault_name
  acr_name            = local.acr_name
  tenant_id           = data.azurerm_client_config.current.tenant_id
  tags                = local.common_tags
}

module "data" {
  source = "./modules/data"

  name_prefix            = local.name_prefix
  resource_group_name    = azurerm_resource_group.main.name
  location               = var.location
  storage_account_name   = local.storage_account_name
  postgres_name          = local.postgres_name
  postgres_sku_name      = var.postgres_sku_name
  postgres_storage_mb    = var.postgres_storage_mb
  administrator_login    = var.postgres_admin_login
  administrator_password = var.postgres_admin_password
  vnet_id                = module.network.vnet_id
  delegated_subnet_id    = module.network.database_subnet_id
  tags                   = local.common_tags
}

module "compute" {
  source = "./modules/compute"

  name_prefix         = local.name_prefix
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  subnet_id           = module.network.app_subnet_id
  vm_size             = var.vm_size
  admin_username      = var.admin_username
  ssh_public_key      = var.ssh_public_key
  tags                = local.common_tags
}

module "observability" {
  source = "./modules/observability"

  name_prefix                     = local.name_prefix
  resource_group_name             = azurerm_resource_group.main.name
  resource_group_id               = azurerm_resource_group.main.id
  location                        = var.location
  monthly_budget_amount           = var.monthly_budget_amount
  budget_alert_threshold_percents = var.budget_alert_threshold_percents
  budget_contact_emails           = var.budget_contact_emails
  budget_start_date               = var.budget_start_date
  tags                            = local.common_tags
}
