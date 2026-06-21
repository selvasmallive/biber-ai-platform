# Observability and cost-control boundary for the XRIQ Azure staging-devnet.
#
# Responsibility (not yet implemented): structured logs, metrics, traces, and
# dashboards via Azure Monitor + Log Analytics, plus a monthly budget with alert
# thresholds as a hard cost guardrail before any always-on resource. No
# resources are created here yet.
#
# Planned resources: azurerm_log_analytics_workspace,
# azurerm_application_insights, azurerm_monitor_action_group,
# azurerm_consumption_budget_resource_group.

variable "name_prefix" {
  description = "Resource name prefix."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "monthly_budget_amount" {
  description = "Monthly cost ceiling in USD for budget alerts."
  type        = number
}

variable "budget_alert_threshold_percents" {
  description = "Budget alert thresholds as percentages of the monthly ceiling."
  type        = list(number)
}

variable "tags" {
  description = "Common tags."
  type        = map(string)
}

output "boundary" {
  description = "Declared responsibilities and planned resources for this module."
  value = {
    name_prefix                     = var.name_prefix
    location                        = var.location
    monthly_budget_amount           = var.monthly_budget_amount
    budget_alert_threshold_percents = var.budget_alert_threshold_percents
    tags                            = var.tags
    responsibility                  = "logs/metrics/traces/dashboards and a monthly budget with alerts"
    planned_resources = [
      "azurerm_log_analytics_workspace",
      "azurerm_application_insights",
      "azurerm_monitor_action_group",
      "azurerm_consumption_budget_resource_group",
    ]
    implemented = false
  }
}
