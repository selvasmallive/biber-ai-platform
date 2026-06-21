# XRIQ Azure Infrastructure (staging-devnet)

Status: Terraform for the XRIQ `staging-devnet`. Validated, not applied from
automation.

This directory holds the Terraform that provisions the XRIQ `staging-devnet` on
Azure, per `../../docs/XRIQ_AZURE_PROVIDER_DECISION.md` and the policy in
`../../docs/XRIQ_PRODUCTION_ROADMAP.md`.

The modules declare real resources, but **nothing is applied by this repo or
CI** — only `terraform fmt` and `terraform validate` run here. Provisioning is a
human-gated step; follow `../../docs/XRIQ_AZURE_APPLY_RUNBOOK.md`.

## Safety boundaries

- No `az login`, `terraform apply`, or cloud deletion is run by automation.
- No secrets, subscription IDs, or tenant IDs are stored here. Authentication is
  resolved at apply time from the maintainer's `az login` session or ARM_* env
  vars. The PostgreSQL admin password is supplied at apply time via
  `TF_VAR_postgres_admin_password` and is never committed.
- State backend is intentionally unconfigured so static validation needs no
  Azure access; the config defaults to local state. See the apply runbook for
  remote-state options.

## Layout

- `versions.tf` — Terraform and azurerm provider version constraints.
- `variables.tf` — non-secret planning inputs (project, environment, region,
  `name_suffix`, budget, SKUs, SSH public key, ...).
- `main.tf` — root composition: resource group + module wiring.
- `outputs.tf` — key resource identifiers.
- `terraform.tfvars.example` — copy to `terraform.tfvars` (gitignored) and edit.
- `modules/network` — VNet, app subnet, delegated database subnet, NSG.
- `modules/security` — Key Vault (RBAC), workload identity, container registry.
- `modules/data` — object storage and a private PostgreSQL Flexible Server.
- `modules/compute` — a single small Linux node VM (SSH-key auth, private).
- `modules/observability` — Log Analytics, Application Insights, consumption budget.

## Safe validation (no cloud access)

```bash
cd infra/azure
terraform fmt -recursive -check
terraform init -backend=false
terraform validate
```

## Apply (human maintainer only)

See `../../docs/XRIQ_AZURE_APPLY_RUNBOOK.md`. `terraform plan`/`apply` run only
by the human maintainer after `az login` and explicit review, against an approved
subscription. Expect to iterate on `plan` for any region/quota-specific SKU
adjustments.
