# Root outputs for the XRIQ Azure staging-devnet.

output "resource_group_name" {
  description = "Resource group holding the staging-devnet."
  value       = azurerm_resource_group.main.name
}

output "location" {
  description = "Target Azure region."
  value       = var.location
}

output "vnet_id" {
  description = "Virtual network id."
  value       = module.network.vnet_id
}

output "key_vault_id" {
  description = "Key Vault id for managed secrets."
  value       = module.security.key_vault_id
}

output "container_registry_login_server" {
  description = "Container registry login server."
  value       = module.security.container_registry_login_server
}

output "postgres_server_fqdn" {
  description = "PostgreSQL Flexible Server fully-qualified domain name."
  value       = module.data.postgres_fqdn
}

output "storage_account_name" {
  description = "Object storage account for snapshots, backups, and artifacts."
  value       = module.data.storage_account_name
}

output "node_vm_private_ip" {
  description = "Private IP of the staging node VM."
  value       = module.compute.private_ip_address
}

output "log_analytics_workspace_id" {
  description = "Log Analytics workspace id."
  value       = module.observability.log_analytics_workspace_id
}
