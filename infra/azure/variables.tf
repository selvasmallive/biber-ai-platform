# Input variables for the XRIQ Azure staging-devnet.
# All values are non-secret planning inputs. Subscription/tenant identifiers and
# any credentials come from the maintainer's environment (az login /
# ARM_* env vars) at plan/apply time, never from this repository. Globally
# unique names are derived from var.name_suffix, which the maintainer sets.

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

variable "location" {
  description = "Azure region for the staging-devnet."
  type        = string
  default     = "eastus"
}

variable "name_suffix" {
  description = "Short lowercase suffix (3-8 chars) used to make globally-unique resource names unique (storage account, Key Vault, container registry, PostgreSQL server)."
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9]{3,8}$", var.name_suffix))
    error_message = "name_suffix must be 3-8 lowercase alphanumeric characters."
  }
}

variable "monthly_budget_amount" {
  description = "Monthly cost ceiling in USD for budget alerts."
  type        = number
  default     = 150
}

variable "budget_alert_threshold_percents" {
  description = "Budget alert thresholds as percentages of the monthly ceiling."
  type        = list(number)
  default     = [80, 100]
}

variable "budget_contact_emails" {
  description = "Email addresses notified by the budget alerts. Empty disables email alerts."
  type        = list(string)
  default     = []
}

variable "postgres_sku_name" {
  description = "PostgreSQL Flexible Server SKU (smallest burstable by default for staging)."
  type        = string
  default     = "B_Standard_B1ms"
}

variable "postgres_storage_mb" {
  description = "PostgreSQL Flexible Server storage in MB."
  type        = number
  default     = 32768
}

variable "postgres_admin_login" {
  description = "PostgreSQL administrator login name."
  type        = string
  default     = "xriqpgadmin"
}

variable "postgres_admin_password" {
  description = "PostgreSQL administrator password. Supplied at apply time (e.g. TF_VAR_postgres_admin_password from Key Vault); never committed. No default so it cannot be hard-coded."
  type        = string
  sensitive   = true
}

variable "budget_start_date" {
  description = "First-of-month start date for the consumption budget, RFC3339 (e.g. 2026-06-01T00:00:00Z). Set to the current month at apply time."
  type        = string
  default     = "2026-06-01T00:00:00Z"
}

variable "vm_size" {
  description = "Compute VM size (cheapest viable burstable by default for staging)."
  type        = string
  default     = "Standard_B2s"
}

variable "admin_username" {
  description = "Linux admin username for the staging node VM."
  type        = string
  default     = "xriqop"
}

variable "ssh_public_key" {
  description = "SSH public key (OpenSSH format) for the staging node VM admin user. A public key is not a secret; the matching private key stays on the operator's machine."
  type        = string
}

variable "operator_allowed_cidr" {
  description = "Optional CIDR allowed inbound SSH to the node VM (for example the operator's IP/32). Null leaves SSH closed at the network security group."
  type        = string
  default     = null
}

variable "tags" {
  description = "Common tags applied to all resources."
  type        = map(string)
  default = {
    project     = "xriq"
    environment = "staging-devnet"
    managed_by  = "terraform"
    scope       = "private-staging-no-public-financial-claims"
  }
}
