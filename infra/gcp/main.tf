# Root composition for the XRIQ GCP staging-devnet.
#
# This wires the staging-devnet resources. It creates real resources only when a
# human runs `terraform apply` against an approved project. Nothing is applied
# from automation: CI and this repo only run `terraform fmt` / `validate`. The
# google provider carries no credentials; authentication is resolved at apply
# time from the maintainer's `gcloud auth application-default login` or a
# service-account key supplied via environment, never from this repository.

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  name_prefix = "${var.project}-${var.environment}"
  bucket_name = "${var.project}-${var.environment}-artifacts-${var.name_suffix}"
  labels      = var.labels
}

# Enable the APIs the staging-devnet uses. disable_on_destroy = false keeps the
# APIs enabled if the configuration is later removed.
resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "storage.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com",
    "billingbudgets.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Give newly-enabled APIs time to propagate before dependent resources are
# created, so a first apply does not fail with transient "API not enabled" or
# service-networking errors.
resource "time_sleep" "wait_for_apis" {
  depends_on      = [google_project_service.apis]
  create_duration = "60s"
}

module "network" {
  source = "./modules/network"

  project_id            = var.project_id
  name_prefix           = local.name_prefix
  region                = var.region
  operator_allowed_cidr = var.operator_allowed_cidr
  enable_iap_ssh        = var.enable_iap_ssh

  depends_on = [time_sleep.wait_for_apis]
}

module "security" {
  source = "./modules/security"

  project_id              = var.project_id
  name_prefix             = local.name_prefix
  region                  = var.region
  postgres_admin_password = var.postgres_admin_password
  labels                  = local.labels

  depends_on = [time_sleep.wait_for_apis]
}

module "data" {
  source = "./modules/data"

  project_id              = var.project_id
  name_prefix             = local.name_prefix
  region                  = var.region
  network_id              = module.network.network_id
  private_vpc_connection  = module.network.private_vpc_connection
  bucket_name             = local.bucket_name
  postgres_tier           = var.postgres_tier
  postgres_admin_user     = var.postgres_admin_user
  postgres_admin_password = var.postgres_admin_password
  db_deletion_protection  = var.db_deletion_protection
  labels                  = local.labels

  depends_on = [time_sleep.wait_for_apis]
}

module "compute" {
  source = "./modules/compute"

  project_id            = var.project_id
  name_prefix           = local.name_prefix
  zone                  = var.zone
  network_id            = module.network.network_id
  subnet_id             = module.network.subnet_id
  machine_type          = var.vm_machine_type
  ssh_user              = var.ssh_user
  ssh_public_key        = var.ssh_public_key
  service_account_email = module.security.workload_service_account_email
  labels                = local.labels

  depends_on = [time_sleep.wait_for_apis]
}

module "testnet" {
  source = "./modules/testnet"
  count  = var.enable_testnet ? 1 : 0

  project_id            = var.project_id
  name_prefix           = local.name_prefix
  zone                  = var.zone
  network_id            = module.network.network_id
  subnet_id             = module.network.subnet_id
  machine_type          = var.testnet_machine_type
  ssh_user              = var.ssh_user
  ssh_public_key        = var.ssh_public_key
  service_account_email = module.security.workload_service_account_email
  labels                = local.labels
  follower_count        = var.testnet_follower_count

  depends_on = [time_sleep.wait_for_apis]
}

module "edge" {
  source = "./modules/edge"
  count  = var.enable_public_edge ? 1 : 0

  project_id            = var.project_id
  name_prefix           = local.name_prefix
  zone                  = var.zone
  network_id            = module.network.network_id
  vm_self_link          = module.compute.instance_self_link
  api_domain            = var.api_domain
  rate_limit_per_minute = var.edge_rate_limit_per_minute

  depends_on = [time_sleep.wait_for_apis]
}

module "observability" {
  source = "./modules/observability"

  project_id                      = var.project_id
  name_prefix                     = local.name_prefix
  enable_budget                   = var.enable_budget
  billing_account                 = var.billing_account
  monthly_budget_amount           = var.monthly_budget_amount
  budget_alert_threshold_percents = var.budget_alert_threshold_percents
  budget_notification_email       = var.budget_notification_email
  enable_alerts                   = var.enable_alerts
  cloudsql_cpu_threshold          = var.cloudsql_cpu_threshold
  cloudsql_disk_threshold         = var.cloudsql_disk_threshold
  vm_cpu_threshold                = var.vm_cpu_threshold

  depends_on = [time_sleep.wait_for_apis]
}
