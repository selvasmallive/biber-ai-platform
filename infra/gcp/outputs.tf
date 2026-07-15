# Root outputs for the XRIQ GCP staging-devnet.

output "network_id" {
  description = "VPC network id."
  value       = module.network.network_id
}

output "artifact_registry_repository" {
  description = "Artifact Registry repository id for container images."
  value       = module.security.artifact_registry_repository
}

output "db_secret_id" {
  description = "Secret Manager secret id holding the database password."
  value       = module.security.db_secret_id
}

output "postgres_instance_connection_name" {
  description = "Cloud SQL instance connection name."
  value       = module.data.instance_connection_name
}

output "postgres_private_ip" {
  description = "Cloud SQL private IP address."
  value       = module.data.private_ip_address
}

output "storage_bucket" {
  description = "Cloud Storage bucket for snapshots, backups, and artifacts."
  value       = module.data.bucket_name
}

output "node_vm_internal_ip" {
  description = "Internal IP of the staging node VM."
  value       = module.compute.internal_ip
}

output "edge_ip" {
  description = "Public edge load balancer IP (point the api_domain DNS A record here). Null when the public edge is disabled."
  value       = var.enable_public_edge ? module.edge[0].edge_ip : null
}

output "edge_api_url" {
  description = "Public API URL when the edge is enabled."
  value       = var.enable_public_edge ? module.edge[0].api_url : null
}

output "testnet_seed_internal_ip" {
  description = "Internal IP of the testnet seed node (point followers' peer-sync --peer http://<ip>:8899 here). Null when the testnet is disabled."
  value       = var.enable_testnet ? module.testnet[0].seed_internal_ip : null
}

output "testnet_follower_internal_ips" {
  description = "Internal IPs of the testnet follower nodes. Empty when the testnet is disabled."
  value       = var.enable_testnet ? module.testnet[0].follower_internal_ips : []
}
