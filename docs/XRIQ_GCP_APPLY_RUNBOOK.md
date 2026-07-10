# XRIQ GCP Apply Runbook (Agent-Executable)

Status: runbook for an autonomous coding agent (e.g. Codex) to provision the XRIQ
`staging-devnet` on Google Cloud from the repository.

This runbook is written to be executed end to end by an agent that has a shell
with `gcloud` and `terraform`, and permission to authenticate and apply. Run the
steps in order and follow the decision points. The Terraform is hardened for a
non-interactive apply (API-enablement is pre-run and gated by a wait; the billing
budget is optional).

Inputs the agent needs (ask the user if not provided):

- `PROJECT_ID` — target Google Cloud project id (new or existing).
- `BILLING_ACCOUNT` — Cloud Billing account id `XXXXXX-XXXXXX-XXXXXX` (only if
  creating the budget).
- `NAME_SUFFIX` — 3-8 lowercase alphanumeric chars (globally-unique bucket name).
- `NOTIFY_EMAIL` — email for budget alerts (default `xriq@kani.network`).
- Region is `northamerica-northeast2` (default in the Terraform).

Non-negotiable safety rules for the agent:

- Never commit `terraform.tfvars`, `*.tfstate`, `tfplan`, the database password,
  or any secret. They are gitignored; keep them so.
- Never print the generated database password to logs.
- This is a private staging environment. Do not add public-network, DEX, custody,
  or exchange behavior.

## 0. Preconditions

```bash
gcloud --version && terraform version
cd infra/gcp
```

## 1. Authenticate and select the project

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project "$PROJECT_ID"
```

If the project does not exist yet, create and link billing:

```bash
gcloud projects create "$PROJECT_ID" --name="XRIQ private dev" || true
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"
```

Verify billing is enabled (required, or apply will fail):

```bash
gcloud beta billing projects describe "$PROJECT_ID" --format='value(billingEnabled)'
# Expect: True
```

## 2. Pre-enable the APIs (avoids first-apply propagation errors)

Terraform also enables these, but pre-enabling makes the first apply
deterministic:

```bash
gcloud services enable \
  compute.googleapis.com sqladmin.googleapis.com servicenetworking.googleapis.com \
  secretmanager.googleapis.com artifactregistry.googleapis.com storage.googleapis.com \
  monitoring.googleapis.com logging.googleapis.com billingbudgets.googleapis.com \
  cloudresourcemanager.googleapis.com serviceusage.googleapis.com \
  --project "$PROJECT_ID"
```

## 3. Budget IAM decision

The budget needs billing-account IAM. Try to grant it; if that fails, disable the
budget so the apply still succeeds.

```bash
ACTIVE_ACCOUNT="$(gcloud config get-value account)"
gcloud billing accounts add-iam-policy-binding "$BILLING_ACCOUNT" \
  --member="user:${ACTIVE_ACCOUNT}" --role="roles/billing.costsManager" \
  && export ENABLE_BUDGET=true \
  || export ENABLE_BUDGET=false
```

If you do not have a billing account or do not want the budget, set
`ENABLE_BUDGET=false`.

## 4. SSH key for the node VM

Use an existing public key or generate one (private key stays on this machine):

```bash
[ -f ~/.ssh/xriq_node.pub ] || ssh-keygen -t ed25519 -N "" -f ~/.ssh/xriq_node
SSH_PUBLIC_KEY="$(cat ~/.ssh/xriq_node.pub)"
```

## 5. Write terraform.tfvars (no secrets in it)

```bash
cat > terraform.tfvars <<EOF
project_id  = "$PROJECT_ID"
region      = "northamerica-northeast2"
zone        = "northamerica-northeast2-a"
name_suffix = "$NAME_SUFFIX"

enable_budget             = $ENABLE_BUDGET
billing_account           = "$BILLING_ACCOUNT"
budget_notification_email = "$NOTIFY_EMAIL"

ssh_public_key = "$SSH_PUBLIC_KEY"
EOF
```

## 6. Database password (out of band, never in a file or log)

```bash
export TF_VAR_postgres_admin_password="$(openssl rand -base64 24)"
```

Terraform stores it in Secret Manager during apply.

## 7. Init, plan, apply (with one automatic retry)

```bash
terraform init
terraform plan -out tfplan
terraform apply -auto-approve tfplan || { sleep 60; terraform apply -auto-approve; }
```

The retry covers the rare case where a just-enabled API needs extra propagation
time. If it still fails, go to Troubleshooting.

## 8. Post-apply verification

```bash
terraform output
# Confirm the Cloud SQL instance has a PRIVATE ip and no public ip:
gcloud sql instances describe xriq-staging-devnet-postgres \
  --project "$PROJECT_ID" --format='value(ipAddresses)'
```

Report the outputs (node VM internal IP, Artifact Registry repo, Cloud SQL
connection name, bucket, budget id) back to the user.

## Troubleshooting (apply the fix, then re-run `terraform apply -auto-approve`)

| Error contains | Fix |
|---|---|
| `Billing must be enabled` / `billingEnabled: False` | Link billing: `gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"` |
| `Permission denied on resource project` / `403` on project | Wrong project or ADC; re-run step 1 and confirm `gcloud config get-value project` matches `PROJECT_ID` |
| `API [...] not enabled` / `Service Networking` errors | Re-run step 2, wait 60s, re-apply (the `time_sleep` gate usually covers this) |
| `400`/`invalid argument` on the **budget** (`google_billing_budget`), or `403` on `billing.budgets` | Set `enable_budget = false` in `terraform.tfvars` and re-apply; create the budget manually in Cloud Billing if desired |
| Cloud Storage bucket name `already exists` / unavailable | Bucket names are global; change `name_suffix` in `terraform.tfvars` (e.g. add a letter: `dev01` -> `dev01a`) and re-apply |
| Cloud SQL `tier ... not supported` / quota | Set `postgres_tier = "db-g1-small"` (the module pins `edition = "ENTERPRISE"` so shared-core tiers work) or a `db-custom-1-3840`, re-apply |
| VM `machine type ... not found` / quota | Set `vm_machine_type = "e2-medium"` in `terraform.tfvars`, re-apply |
| Cloud SQL delete blocked on destroy | Set `db_deletion_protection = false`, `terraform apply`, then destroy |

## Teardown (only if asked)

```bash
# ensure db_deletion_protection = false in terraform.tfvars first, then:
terraform destroy -auto-approve
```

Remove `terraform.tfvars` and unset `TF_VAR_postgres_admin_password` afterward.
Do not commit any of the generated files.
