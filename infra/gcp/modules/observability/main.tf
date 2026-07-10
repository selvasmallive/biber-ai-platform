# Observability and cost-control module for the XRIQ GCP staging-devnet.
#
# An email notification channel (shared by the budget and the alert policies),
# a Cloud Billing budget, native-metric alert policies for Cloud SQL and the node
# VM, and a monitoring dashboard. Cloud Logging and Monitoring are enabled at the
# project level via the root google_project_service resources. All metrics used
# here are native (no agent required); richer VM memory/disk metrics come from the
# Ops Agent installed by vm-bootstrap.sh.

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

variable "enable_alerts" {
  type = bool
}

variable "cloudsql_cpu_threshold" {
  type = number
}

variable "cloudsql_disk_threshold" {
  type = number
}

variable "vm_cpu_threshold" {
  type = number
}

data "google_project" "current" {
  project_id = var.project_id
}

locals {
  postgres_database_id  = "${var.project_id}:${var.name_prefix}-postgres"
  notification_channels = google_monitoring_notification_channel.email[*].id
}

# Email channel, created whenever an address is set (used by budget and alerts),
# independent of whether the budget itself is enabled.
resource "google_monitoring_notification_channel" "email" {
  count        = var.budget_notification_email == "" ? 0 : 1
  project      = var.project_id
  display_name = "${var.name_prefix}-email"
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
    for_each = length(local.notification_channels) > 0 ? [1] : []
    content {
      monitoring_notification_channels = local.notification_channels
      disable_default_iam_recipients   = false
    }
  }
}

resource "google_monitoring_alert_policy" "cloudsql_cpu" {
  count        = var.enable_alerts ? 1 : 0
  project      = var.project_id
  display_name = "${var.name_prefix} Cloud SQL CPU high"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL CPU utilization high"
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${local.postgres_database_id}\" AND metric.type = \"cloudsql.googleapis.com/database/cpu/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.cloudsql_cpu_threshold
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = local.notification_channels
}

resource "google_monitoring_alert_policy" "cloudsql_disk" {
  count        = var.enable_alerts ? 1 : 0
  project      = var.project_id
  display_name = "${var.name_prefix} Cloud SQL disk high"
  combiner     = "OR"

  conditions {
    display_name = "Cloud SQL disk utilization high"
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${local.postgres_database_id}\" AND metric.type = \"cloudsql.googleapis.com/database/disk/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.cloudsql_disk_threshold
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = local.notification_channels
}

resource "google_monitoring_alert_policy" "vm_cpu" {
  count        = var.enable_alerts ? 1 : 0
  project      = var.project_id
  display_name = "${var.name_prefix} node VM CPU high"
  combiner     = "OR"

  conditions {
    display_name = "Node VM CPU utilization high"
    condition_threshold {
      filter          = "resource.type = \"gce_instance\" AND metric.type = \"compute.googleapis.com/instance/cpu/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = var.vm_cpu_threshold
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = local.notification_channels
}

resource "google_monitoring_dashboard" "main" {
  count   = var.enable_alerts ? 1 : 0
  project = var.project_id

  dashboard_json = jsonencode({
    displayName = "${var.name_prefix} staging-devnet"
    gridLayout = {
      columns = 2
      widgets = [
        {
          title = "Cloud SQL CPU utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter      = "resource.type=\"cloudsql_database\" AND metric.type=\"cloudsql.googleapis.com/database/cpu/utilization\""
                  aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_MEAN" }
                }
              }
            }]
          }
        },
        {
          title = "Cloud SQL disk utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter      = "resource.type=\"cloudsql_database\" AND metric.type=\"cloudsql.googleapis.com/database/disk/utilization\""
                  aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_MEAN" }
                }
              }
            }]
          }
        },
        {
          title = "Node VM CPU utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter      = "resource.type=\"gce_instance\" AND metric.type=\"compute.googleapis.com/instance/cpu/utilization\""
                  aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_MEAN" }
                }
              }
            }]
          }
        },
        {
          title = "Cloud SQL active connections"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter      = "resource.type=\"cloudsql_database\" AND metric.type=\"cloudsql.googleapis.com/database/postgresql/num_backends\""
                  aggregation = { alignmentPeriod = "300s", perSeriesAligner = "ALIGN_MEAN" }
                }
              }
            }]
          }
        },
      ]
    }
  })
}

output "budget_id" {
  value = length(google_billing_budget.main) > 0 ? google_billing_budget.main[0].id : null
}

output "notification_channel_id" {
  value = length(google_monitoring_notification_channel.email) > 0 ? google_monitoring_notification_channel.email[0].id : null
}

output "dashboard_id" {
  value = length(google_monitoring_dashboard.main) > 0 ? google_monitoring_dashboard.main[0].id : null
}
