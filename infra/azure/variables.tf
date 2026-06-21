# Input variables for the XRIQ Azure staging-devnet boundaries.
# All values are non-secret planning inputs. Subscription/tenant identifiers and
# any credentials are supplied by the human maintainer's environment at apply
# time, never stored here.

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
    error_message = "Phase 2 boundaries only support environment = staging-devnet."
  }
}

variable "location" {
  description = "Azure region for the staging-devnet."
  type        = string
  default     = "eastus"
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

variable "tags" {
  description = "Common tags applied to all resources once implemented."
  type        = map(string)
  default = {
    project     = "xriq"
    environment = "staging-devnet"
    managed_by  = "terraform"
    scope       = "private-staging-no-public-financial-claims"
  }
}
