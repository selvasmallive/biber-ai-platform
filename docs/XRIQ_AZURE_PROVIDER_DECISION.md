# XRIQ Cloud Provider Decision: Azure

Status: provider decision recorded. No cloud resources created.

This document records the Phase 2 cloud-provider decision required by
`docs/XRIQ_PRODUCTION_ROADMAP.md` before any provider-specific infrastructure.
Recording this decision does **not** create, modify, or destroy any Azure
resource, does not authenticate to Azure, and does not introduce secrets. It
selects Azure as the target provider and captures the planning inputs so that a
human can later review and apply infrastructure-as-code deliberately.

This document is not legal, financial, tax, or compliance advice. Public
network, token, exchange, custody, and privacy work stays blocked behind
`docs/XRIQ_LEGAL_RISK_REDUCTION.md` and the roadmap acceptance gates.

## Decision

- **Selected provider:** Microsoft Azure.
- **Why Azure:** chosen by the human maintainer. The repository stays
  provider-aware; provider-specific code lives only under `infra/azure/`.
- **Scope of this decision:** documentation and reviewable Terraform module
  boundaries only. No `terraform apply`, no resource creation, no `az login`
  performed by automation.

## Account And Ownership

- **Account owner:** `selva@kani.network` (human maintainer).
- **Subscription:** to be supplied by the owner at apply time as an identifier
  (subscription ID and tenant ID are identifiers, not secrets). They are not
  stored in this repository.
- **Operational ownership:** the human maintainer owns billing, access, and
  apply/rollback decisions.

## Regions And Data Residency

- **Primary region:** `eastus` (Azure East US).
- **Data residency assumption:** staging-devnet data is non-production test data
  with no monetary value and no real user PII. Region may be revisited before
  any public-testnet or production-candidate environment.

## Budget And Cost Controls

- **Monthly budget ceiling (staging-devnet):** USD 150.
- **Alert thresholds:** notify at 80% (USD 120) and at 100% (USD 150) of the
  monthly budget.
- **Cost posture:** prefer smallest viable managed tiers; allow stopping or
  scaling idle resources. A budget with alerts is a required guardrail before
  any always-on resource is provisioned.

## Environment Isolation

Phase 2 targets only `staging-devnet`. Later environments are out of scope for
this decision and must each get separate subscriptions or resource groups,
service accounts, databases, storage, network boundaries, monitoring alerts, and
deployment approvals, per the roadmap Environment Model:

- `local` (developer machine, current baseline),
- `staging-devnet` (this decision; private/staging topology, no public claims),
- `public-testnet`, `production-candidate`, `mainnet` (future, separate human
  decisions; must not share credentials, keys, or databases with lower
  environments).

## Required Decision Inputs (Azure Service Mapping)

These are planning choices, not yet implemented. They map to the roadmap
Reference Production Architecture using Azure managed services:

| Capability | Azure service (planned) | Notes |
|---|---|---|
| Container orchestration / compute | AKS or a small VM scale set | Start with the cheapest viable option for staging-devnet |
| Managed PostgreSQL read model | Azure Database for PostgreSQL Flexible Server | Smallest burstable tier for staging |
| Object storage (snapshots, backups, artifacts) | Azure Blob Storage | Lifecycle + soft-delete enabled |
| Secrets | Azure Key Vault | No secrets in git; CI/apply reads from Key Vault |
| KMS/HSM | Key Vault keys (Managed HSM later if required) | Key protection for future signing/custody review only |
| Container registry | Azure Container Registry | Image provenance/signing where available |
| Logs / metrics / traces | Azure Monitor + Log Analytics | Structured logs with chain/network ids |
| Edge / WAF / rate limit | Azure Front Door + WAF | For future public APIs only |
| DNS / TLS | Azure DNS + managed certificates | TLS at public edges only |
| Networking | Private VNet + subnets | Databases and internal node services stay private |

## Secrets And Key Management

- No secrets in git, fixtures, logs, screenshots, or this document.
- At apply time the human maintainer authenticates locally (`az login`) or via a
  least-privilege service principal whose secret lives in Azure Key Vault or a
  secure environment, never in the repository or chat.
- Credential rotation stays deliberate and documented; no automatic frequent
  rotation without a separate approved runbook.
- User wallet private keys remain out of scope for server custody by default.

## Infrastructure-As-Code Plan

- Terraform is the IaC tool. Provider-specific code lives under `infra/azure/`.
- State backend: planned Azure Blob remote state (separate per environment); not
  configured here so static validation needs no cloud access.
- Safe validation only (no apply):

```bash
cd infra/azure
terraform fmt -recursive -check
terraform init -backend=false
terraform validate
```

- `terraform plan` and `terraform apply` against a real Azure subscription are
  performed only by the human maintainer after explicit approval of the exact
  subscription, region, environment, and action.

## Explicit Boundaries (unchanged)

- No resource creation, modification, or destruction from automation.
- No `az login`, `terraform apply`, or cloud deletion commands from automation.
- No secrets or credentials committed or transmitted through chat.
- No public mainnet/testnet, DEX, bridge, custody, privacy, exchange, or
  tokenomics behavior.
- No tag creation, movement, or deletion.

## Implementation Status

The `infra/azure/` modules now declare real Terraform resources (resource group,
network, Key Vault + workload identity + container registry, private PostgreSQL
Flexible Server + object storage, a Linux node VM, and Log Analytics +
Application Insights + a consumption budget). They are validated with
`terraform validate` only; **no resources are created from automation or CI**.
Applying them is a human-gated step documented in
`docs/XRIQ_AZURE_APPLY_RUNBOOK.md`.

## Next Steps After This Decision

1. Review and edit this decision (subscription details, any region/budget
   changes) — owner action.
2. Follow `docs/XRIQ_AZURE_APPLY_RUNBOOK.md`: the owner runs `az login`,
   configures the remote state backend, runs `terraform plan` against the chosen
   subscription, reviews it, and only then applies.
3. Add incident-response and disaster-recovery runbook detail as the staging
   environment is exercised.

## Cheap Verification

```bash
python scripts/xriq_azure_provider_decision_check.py
```

This guard validates the decision markers and the `infra/azure/` boundary
layout, and asserts no apply/secret material is present. It creates no
resources and touches no cloud account.
