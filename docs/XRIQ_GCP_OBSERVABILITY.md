# XRIQ GCP Staging-Devnet Observability

Status: monitoring for the deployed GCP `staging-devnet`. IaC + agent config only;
apply is human/agent-operated.

## What is monitored

Native Cloud Monitoring metrics (no agent required):

- **Cloud SQL** CPU utilization, disk utilization, and active connections.
- **Node VM** CPU utilization.

Via the Cloud Ops Agent (installed on the VM by `deploy/gcp/vm-bootstrap.sh`):

- VM memory, disk, and process metrics, plus syslog to Cloud Logging.

## Alerts (Terraform, tunable)

`infra/gcp/modules/observability` creates alert policies wired to an email
notification channel (`budget_notification_email`, created whenever an address is
set — independent of the budget):

| Alert | Default threshold | Duration |
|---|---|---|
| Cloud SQL CPU high | `cloudsql_cpu_threshold` = 0.80 | 5 min |
| Cloud SQL disk high | `cloudsql_disk_threshold` = 0.85 | 5 min |
| Node VM CPU high | `vm_cpu_threshold` = 0.90 | 5 min |

Tune the thresholds in `terraform.tfvars`; set `enable_alerts = false` to skip the
policies and dashboard.

## Dashboard

A `google_monitoring_dashboard` (`<name_prefix> staging-devnet`) charts Cloud SQL
CPU/disk/connections and node VM CPU. View it in Cloud Monitoring > Dashboards
after apply.

## Applying

1. Re-apply Terraform (creates the notification channel, alert policies, and
   dashboard, and grants the workload service account `roles/monitoring.metricWriter`
   and `roles/logging.logWriter`):

   ```bash
   cd infra/gcp
   terraform workspace select xriq-project-dev
   export TF_VAR_postgres_admin_password="$(gcloud secrets versions access latest \
     --secret=xriq-staging-devnet-db-password --project=xriq-project-dev)"
   terraform apply
   ```

2. Re-run `deploy/gcp/vm-bootstrap.sh` on the VM (installs the Cloud Ops Agent for
   VM memory/disk metrics and logs).

## Follow-up

Application-level error alerting (xriq-api container error logs -> Cloud Logging ->
log-based metric -> alert) is a follow-up: it needs the Ops Agent configured to
tail the docker json logs (keeping `docker logs` working) or the docker `gcplogs`
driver. The native-metric alerts above cover node/DB health without it.
