# XRIQ GCP Apply Runbook (Human-Operated)

Status: operator runbook for provisioning the XRIQ `staging-devnet` on Google
Cloud.

These steps are run **by the human maintainer**, not by automation or by the
assistant. The assistant never runs `gcloud auth`, `terraform apply`, or handles
secrets. The repository and CI only run `terraform fmt`/`validate`.

Prerequisites:

- Google Cloud SDK (`gcloud`) and Terraform `>= 1.6` installed locally.
- A Google Cloud account owned by `xriq@kani.network`, a project (new or
  existing), and a Cloud Billing account linked to it.
- The SSH **public** key you will use for the node VM (the private key stays on
  your machine).

The provisioned footprint (region `northamerica-northeast2`, budget USD 150/mo
with 80%/100% alerts) is: enabled APIs; VPC + subnet + firewall + private
services access; workload service account, Artifact Registry, Secret Manager db
secret; private Cloud SQL for PostgreSQL + Cloud Storage bucket; a small Compute
Engine node VM; and a Cloud Billing budget. Estimated cost at the default tiers
is roughly USD 40-70/month; review with `terraform plan` and the GCP pricing
calculator before applying.

## 1. Authenticate and select the project

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project <your-project-id>
gcloud projects describe <your-project-id> --format="value(projectId, projectNumber)"
```

If you need a new project:

```bash
gcloud projects create <your-project-id> --name="XRIQ private dev"
gcloud billing projects link <your-project-id> --billing-account=<XXXXXX-XXXXXX-XXXXXX>
```

## 2. Configure variables

```bash
cd infra/gcp
cp terraform.tfvars.example terraform.tfvars   # terraform.tfvars is gitignored
```

Edit `terraform.tfvars`:

- `project_id` — your GCP project id.
- `billing_account` — your Cloud Billing account id (`XXXXXX-XXXXXX-XXXXXX`).
- `name_suffix` — a short unique suffix (3-8 lowercase alphanumeric).
- `ssh_public_key` — your SSH public key (e.g. contents of `~/.ssh/id_ed25519.pub`).
- `budget_notification_email` — an address for budget alerts.
- `operator_allowed_cidr` — optional; your IP as `x.x.x.x/32` to open inbound SSH.

## 3. Provide the database password out of band (not in git)

```bash
export TF_VAR_postgres_admin_password="$(openssl rand -base64 24)"
```

Terraform stores this in Secret Manager during apply; keep it out of any file.

## 4. Plan and review

State backend: this repo ships with **local state** (no backend block, so the
config validates without cloud access). For a first staging apply, local state is
fine — keep `infra/gcp/terraform.tfstate` secure and backed up. To use a remote
GCS backend instead, create a state bucket and add a local (gitignored)
`backend "gcs"` configuration before `init`; do not commit that backend block
(the repo guard intentionally forbids it in tracked files).

```bash
terraform init
terraform plan -out tfplan
```

Read the plan carefully. The first plan/apply may need to enable APIs before
dependent resources resolve; if a resource fails because an API was just enabled,
re-run `plan`/`apply`. Region/quota constraints may require a different Cloud SQL
tier or VM machine type — adjust `terraform.tfvars` and re-plan until clean.

## 5. Apply

```bash
terraform apply tfplan
```

## 6. Post-apply

- Confirm the Cloud SQL instance has **no public IP** (private IP only).
- Confirm the budget and alerts exist in Cloud Billing.
- The database password is in Secret Manager as `<name_prefix>-db-password`;
  grant only the workload service account access (already configured).
- Note the outputs (`terraform output`) for the node VM internal IP, Artifact
  Registry repo, Cloud SQL connection name, and bucket.

## Teardown

```bash
terraform destroy
```

Cloud SQL `deletion_protection` defaults to on; set `db_deletion_protection =
false` and re-apply before destroying, or remove protection in the console.
Remove `terraform.tfvars` and the exported password from your shell history when
finished.

## Safety reminders

- Never commit `terraform.tfvars`, `*.tfstate`, the database password, service
  account keys, or any secret. They are gitignored; keep them that way.
- Keep `staging-devnet` separate from any future `production-candidate`/`mainnet`
  project; do not share credentials, keys, or databases across environments.
- This is a private staging environment with no public financial claims.
