# XRIQ GCP Infrastructure (staging-devnet)

Status: Terraform for the XRIQ `staging-devnet` on Google Cloud. Validated, not
applied from automation.

This directory holds the Terraform that provisions the XRIQ `staging-devnet` on
GCP, per `../../docs/XRIQ_GCP_PROVIDER_DECISION.md`, the shape in
`../../docs/XRIQ_GCP_RESOURCE_PLAN.md`, and the policy in
`../../docs/XRIQ_PRODUCTION_ROADMAP.md`.

The modules declare real resources, but **nothing is applied by this repo or
CI** — only `terraform fmt` and `terraform validate` run here. Provisioning is a
human-gated step; follow `../../docs/XRIQ_GCP_APPLY_RUNBOOK.md`.

## Safety boundaries

- No `gcloud auth`, `terraform apply`, or cloud deletion is run by automation.
- No secrets are stored here. Authentication is resolved at apply time from the
  maintainer's `gcloud auth application-default login`. The Cloud SQL admin
  password is supplied at apply via `TF_VAR_postgres_admin_password` and stored
  in Secret Manager; it is never committed.
- State backend is intentionally unconfigured so static validation needs no GCP
  access; the config defaults to local state. See the apply runbook for remote
  GCS state.

## Layout

- `versions.tf` — Terraform and google provider version constraints.
- `variables.tf` — non-secret planning inputs (project_id, region, name_suffix,
  billing account, budget, SKUs, SSH public key, ...).
- `main.tf` — root composition: enabled APIs + module wiring.
- `outputs.tf` — key resource identifiers.
- `terraform.tfvars.example` — copy to `terraform.tfvars` (gitignored) and edit.
- `modules/network` — custom VPC, subnet, firewall, private services access.
- `modules/security` — workload service account, Artifact Registry, Secret
  Manager db secret, IAM bindings.
- `modules/data` — Cloud Storage bucket and a private-IP Cloud SQL for
  PostgreSQL.
- `modules/compute` — a single small Compute Engine node VM (SSH-key, private).
- `modules/observability` — billing budget with alerts + optional email channel.

## Safe validation (no cloud access)

```bash
cd infra/gcp
terraform fmt -recursive -check
terraform init -backend=false
terraform validate
```

## Apply (human maintainer only)

See `../../docs/XRIQ_GCP_APPLY_RUNBOOK.md`. `terraform plan`/`apply` run only by
the human maintainer after `gcloud auth` and explicit review, against an approved
project. Expect to iterate on `plan` for any region/quota-specific adjustments.
