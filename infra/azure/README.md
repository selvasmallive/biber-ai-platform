# XRIQ Azure Infrastructure (staging-devnet boundaries)

Status: provider-specific module **boundaries** only. Nothing is provisioned.

This directory holds the Terraform module boundaries for the XRIQ
`staging-devnet` on Azure, per the decision in
`../../docs/XRIQ_AZURE_PROVIDER_DECISION.md` and the policy in
`../../docs/XRIQ_PRODUCTION_ROADMAP.md`.

The modules declare their interfaces and responsibilities but **create no
resources yet**. They exist so the topology, naming, tags, budget, and module
seams can be reviewed before any real plan or apply.

## Safety boundaries

- No resources are created, modified, or destroyed by anything in this repo.
- No `az login`, `terraform apply`, or cloud deletion is run by automation.
- No secrets, subscription IDs, or tenant IDs are stored here. Authentication is
  resolved at apply time from the maintainer's `az login` session or a
  least-privilege service principal supplied via environment variables.
- State backend is intentionally unconfigured so static validation needs no
  Azure access. A remote Azure Blob backend is added per environment by the
  human maintainer before any apply.

## Layout

- `versions.tf` — Terraform and azurerm provider version constraints.
- `variables.tf` — non-secret planning inputs (project, environment, region,
  budget, tags).
- `main.tf` — root composition wiring the module boundaries.
- `outputs.tf` — planning metadata only.
- `terraform.tfvars.example` — copy to `terraform.tfvars` (gitignored) and edit.
- `modules/network` — private VNet and subnets.
- `modules/security` — Key Vault secrets, identities, container registry.
- `modules/data` — managed PostgreSQL read model and object storage.
- `modules/compute` — node/API/indexer compute (cheapest viable staging tier).
- `modules/observability` — logs/metrics/traces and a monthly budget with alerts.

## Safe validation (no cloud access)

```bash
cd infra/azure
terraform fmt -recursive -check
terraform init -backend=false
terraform validate
```

## Apply (human maintainer only, after explicit approval)

`terraform plan` / `terraform apply` against a real subscription are run only by
the human maintainer after approving the exact subscription, region,
environment, and action. Implement the module resources first; do not apply
empty boundary modules.
