# Input variables for the XRIQ GCP staging-devnet.
# All values are non-secret planning inputs except postgres_admin_password, which
# is supplied at apply time (TF_VAR_postgres_admin_password) and never committed.
# The GCP project id and billing account are identifiers, not secrets, supplied
# by the maintainer.

variable "project_id" {
  description = "Target Google Cloud project id (e.g. xriq-private-dev)."
  type        = string
}

variable "project" {
  description = "Short project slug used in resource naming."
  type        = string
  default     = "xriq"
}

variable "environment" {
  description = "Environment name. Phase 2 targets staging-devnet only."
  type        = string
  default     = "staging-devnet"

  validation {
    condition     = contains(["staging-devnet"], var.environment)
    error_message = "Phase 2 infra only supports environment = staging-devnet."
  }
}

variable "region" {
  description = "GCP region for the staging-devnet."
  type        = string
  default     = "northamerica-northeast2"
}

variable "zone" {
  description = "GCP zone for zonal resources (node VM)."
  type        = string
  default     = "northamerica-northeast2-a"
}

variable "name_suffix" {
  description = "Short lowercase suffix (3-8 chars) used to make globally-unique names (Cloud Storage bucket) unique."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,8}$", var.name_suffix))
    error_message = "name_suffix must be 3-8 lowercase alphanumeric characters."
  }
}

variable "billing_account" {
  description = "Cloud Billing account id (XXXXXX-XXXXXX-XXXXXX) for the budget. An identifier, not a secret. May be empty when enable_budget is false."
  type        = string
  default     = ""
}

variable "enable_budget" {
  description = "Whether to create the Cloud Billing budget. Creating a budget needs billing-account-level IAM (roles/billing.costsManager); set false to skip it if that permission is not available."
  type        = bool
  default     = true
}

variable "enable_alerts" {
  description = "Whether to create the monitoring alert policies and dashboard."
  type        = bool
  default     = true
}

variable "cloudsql_cpu_threshold" {
  description = "Cloud SQL CPU utilization alert threshold (0-1)."
  type        = number
  default     = 0.8
}

variable "cloudsql_disk_threshold" {
  description = "Cloud SQL disk utilization alert threshold (0-1)."
  type        = number
  default     = 0.85
}

variable "vm_cpu_threshold" {
  description = "Node VM CPU utilization alert threshold (0-1)."
  type        = number
  default     = 0.9
}

variable "monthly_budget_amount" {
  description = "Monthly cost ceiling in USD for budget alerts."
  type        = number
  default     = 150
}

variable "budget_alert_threshold_percents" {
  description = "Budget alert thresholds as fractions of the monthly ceiling are derived from these percentages."
  type        = list(number)
  default     = [80, 100]
}

variable "budget_notification_email" {
  description = "Email notified by the budget alert. Empty disables the email notification channel."
  type        = string
  default     = ""
}

variable "postgres_tier" {
  description = "Cloud SQL machine tier (smallest shared-core by default for staging)."
  type        = string
  default     = "db-f1-micro"
}

variable "postgres_admin_user" {
  description = "Cloud SQL administrator user name."
  type        = string
  default     = "xriqpgadmin"
}

variable "postgres_admin_password" {
  description = "Cloud SQL administrator password. Supplied at apply time (TF_VAR_postgres_admin_password); never committed. No default so it cannot be hard-coded."
  type        = string
  sensitive   = true
}

variable "db_deletion_protection" {
  description = "Whether the Cloud SQL instance has deletion protection."
  type        = bool
  default     = true
}

variable "vm_machine_type" {
  description = "Compute Engine machine type for the node VM (cheapest viable for staging)."
  type        = string
  default     = "e2-small"
}

variable "ssh_user" {
  description = "Linux admin username for the staging node VM."
  type        = string
  default     = "xriqop"
}

variable "ssh_public_key" {
  description = "SSH public key (OpenSSH format) for the node VM. A public key is not a secret; the matching private key stays on the operator's machine."
  type        = string
}

variable "operator_allowed_cidr" {
  description = "Optional CIDR allowed inbound SSH to the node VM (for example the operator's IP/32). Null leaves SSH closed at the firewall."
  type        = string
  default     = null
}

variable "enable_iap_ssh" {
  description = "Allow SSH from Google's IAP range so operators can reach the no-external-IP VM via gcloud compute ssh --tunnel-through-iap."
  type        = bool
  default     = true
}

variable "enable_public_edge" {
  description = "Create a public HTTPS load balancer (managed TLS + Cloud Armor) in front of the API. Default false: this makes the API PUBLICLY REACHABLE and must be opted into explicitly with a domain. The Cloud Armor policy allows only read (GET) methods and blocks admin endpoints."
  type        = bool
  default     = false
}

variable "enable_testnet" {
  description = "Provision the multi-node XRIQ testnet (a seed producer+faucet VM and follower peer-sync VMs). Default false; opt in explicitly. TEST-ONLY: nodes are VPC-internal (no public ingress) and run the test-only signature scheme with no monetary value."
  type        = bool
  default     = false
}

variable "testnet_machine_type" {
  description = "Compute Engine machine type for each testnet node VM."
  type        = string
  default     = "e2-small"
}

variable "testnet_follower_count" {
  description = "Number of follower nodes that peer-sync from the seed."
  type        = number
  default     = 1
}

variable "api_domain" {
  description = "Fully-qualified domain for the public API edge (required when enable_public_edge is true). Its DNS A record must point at the edge IP output before the managed certificate provisions."
  type        = string
  default     = ""
}

variable "edge_rate_limit_per_minute" {
  description = "Per-client-IP request rate limit at the public edge."
  type        = number
  default     = 600
}

variable "labels" {
  description = "Common labels applied to resources."
  type        = map(string)
  default = {
    project     = "xriq"
    environment = "staging-devnet"
    managed_by  = "terraform"
    scope       = "private-staging-no-public-financial-claims"
  }
}
