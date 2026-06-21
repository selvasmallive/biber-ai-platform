# Observability and cost-control module for the XRIQ Azure staging-devnet.
#
# Log Analytics + Application Insights for logs/metrics/traces, and a monthly
# consumption budget with alert thresholds as a hard cost guardrail.

variable "name_prefix" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "resource_group_id" {
  type = string
}

variable "location" {
  type = string
}

variable "monthly_budget_amount" {
  type = number
}

variable "budget_alert_threshold_percents" {
  type = list(number)
}

variable "budget_contact_emails" {
  type = list(string)
}

variable "budget_start_date" {
  type = string
}

variable "tags" {
  type = map(string)
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "${var.name_prefix}-logs"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "main" {
  name                = "${var.name_prefix}-appi"
  resource_group_name = var.resource_group_name
  location            = var.location
  application_type    = "other"
  workspace_id        = azurerm_log_analytics_workspace.main.id
  tags                = var.tags
}

resource "azurerm_consumption_budget_resource_group" "main" {
  name              = "${var.name_prefix}-budget"
  resource_group_id = var.resource_group_id
  amount            = var.monthly_budget_amount
  time_grain        = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  dynamic "notification" {
    for_each = var.budget_alert_threshold_percents
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = "Actual"
      contact_emails = var.budget_contact_emails
    }
  }
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.main.id
}

output "application_insights_id" {
  value = azurerm_application_insights.main.id
}

output "budget_id" {
  value = azurerm_consumption_budget_resource_group.main.id
}
