# Data boundary for the XRIQ Azure staging-devnet.
#
# Responsibility (not yet implemented): managed PostgreSQL read model for
# explorer/analytics/audit views, plus object storage for snapshots, backups,
# and release artifacts. Databases stay on the private network with encrypted
# storage and backups. No resources are created here yet.
#
# Planned resources: azurerm_postgresql_flexible_server (smallest staging tier),
# azurerm_storage_account, azurerm_storage_container, private endpoints.

variable "name_prefix" {
  description = "Resource name prefix."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
}

output "boundary" {
  description = "Declared responsibilities and planned resources for this module."
  value = {
    name_prefix    = var.name_prefix
    location       = var.location
    tags           = var.tags
    responsibility = "managed PostgreSQL read model and object storage; private, encrypted, backed up"
    planned_resources = [
      "azurerm_postgresql_flexible_server",
      "azurerm_storage_account",
      "azurerm_storage_container",
      "azurerm_private_endpoint",
    ]
    implemented = false
  }
}
