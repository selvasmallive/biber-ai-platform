# Observability and cost-control module for the XRIQ GCP staging-devnet.
#
# A billing budget with alert thresholds as a hard cost guardrail, plus an
# optional email notification channel. Cloud Logging and Monitoring are enabled
# at the project level via the root google_project_service resources.

variable "project_id" {
  type = string
}

variable "name_prefix" {
  type = string
}

variable "enable_budget" {
  type = bool
}

variable "billing_account" {
  type = string
}

variable "monthly_budget_amount" {
  type = number
}

variable "budget_alert_threshold_percents" {
  type = list(number)
}

variable "budget_notification_email" {
  type = string
}

data "google_project" "current" {
  project_id = var.project_id
}

resource "google_monitoring_notification_channel" "budget" {
  count        = var.enable_budget && var.budget_notification_email != "" ? 1 : 0
  project      = var.project_id
  display_name = "${var.name_prefix}-budget-email"
  type         = "email"

  labels = {
    email_address = var.budget_notification_email
  }
}

resource "google_billing_budget" "main" {
  count           = var.enable_budget ? 1 : 0
  billing_account = var.billing_account
  display_name    = "${var.name_prefix}-budget"

  budget_filter {
    projects = ["projects/${data.google_project.current.number}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = tostring(var.monthly_budget_amount)
    }
  }

  dynamic "threshold_rules" {
    for_each = var.budget_alert_threshold_percents
    content {
      threshold_percent = threshold_rules.value / 100
      spend_basis       = "CURRENT_SPEND"
    }
  }

  dynamic "all_updates_rule" {
    for_each = var.budget_notification_email == "" ? [] : [1]
    content {
      monitoring_notification_channels = [google_monitoring_notification_channel.budget[0].id]
      disable_default_iam_recipients   = false
    }
  }
}

output "budget_id" {
  value = length(google_billing_budget.main) > 0 ? google_billing_budget.main[0].id : null
}

output "notification_channel_id" {
  value = length(google_monitoring_notification_channel.budget) > 0 ? google_monitoring_notification_channel.budget[0].id : null
}
