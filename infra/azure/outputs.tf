# Root outputs for the XRIQ Azure staging-devnet boundaries.
# These echo planning metadata only; no resource attributes exist until the
# module boundaries are implemented and applied.

output "name_prefix" {
  description = "Resource name prefix derived from project and environment."
  value       = local.name_prefix
}

output "location" {
  description = "Target Azure region."
  value       = var.location
}

output "planned_module_boundaries" {
  description = "Module boundaries defined for the staging-devnet."
  value = {
    network       = module.network.boundary
    security      = module.security.boundary
    data          = module.data.boundary
    compute       = module.compute.boundary
    observability = module.observability.boundary
  }
}
