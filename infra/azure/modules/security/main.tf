# Security/secrets boundary for the XRIQ Azure staging-devnet.
#
# Responsibility (not yet implemented): managed secrets and key protection via
# Azure Key Vault, least-privilege identities, and (later, only after security
# and legal review) Managed HSM for any signing/custody work. No secrets are
# ever stored in this repository. No resources are created here yet.
#
# Planned resources: azurerm_key_vault, azurerm_user_assigned_identity,
# azurerm_role_assignment (least privilege), azurerm_container_registry.

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
    responsibility = "Key Vault secrets, least-privilege identities, registry; no secrets in git"
    planned_resources = [
      "azurerm_key_vault",
      "azurerm_user_assigned_identity",
      "azurerm_role_assignment",
      "azurerm_container_registry",
    ]
    implemented = false
  }
}
