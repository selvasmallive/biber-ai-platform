# Network boundary for the XRIQ Azure staging-devnet.
#
# Responsibility (not yet implemented): private virtual network and subnets so
# databases and internal node services stay private, with public ingress only
# through a controlled edge. No resources are created here yet; this declares the
# module interface so the topology can be reviewed before any apply.
#
# Planned resources: azurerm_resource_group, azurerm_virtual_network,
# azurerm_subnet (app/data/private-endpoints), azurerm_network_security_group.

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
    responsibility = "private VNet and subnets; internal services stay private"
    planned_resources = [
      "azurerm_resource_group",
      "azurerm_virtual_network",
      "azurerm_subnet",
      "azurerm_network_security_group",
    ]
    implemented = false
  }
}
