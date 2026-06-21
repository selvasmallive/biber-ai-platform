# Compute boundary for the XRIQ Azure staging-devnet.
#
# Responsibility (not yet implemented): run the XRIQ node/API/indexer services.
# Start with the cheapest viable option for staging (small AKS node pool or a
# single VM scale set), scalable or stoppable when idle for cost control. Admin
# and operator surfaces stay on the private network only. No resources are
# created here yet.
#
# Planned resources: azurerm_kubernetes_cluster (or azurerm_linux_virtual_machine_scale_set),
# with images pulled from the security module's container registry.

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
    responsibility = "node/API/indexer compute; cheapest viable staging tier; admin stays private"
    planned_resources = [
      "azurerm_kubernetes_cluster_or_vm_scale_set",
    ]
    implemented = false
  }
}
