# XRIQ Cloud Provider Decision: Google Cloud Platform

Status: provider decision recorded. No cloud resources created.

This document records the Phase 2 cloud-provider decision required by
`docs/XRIQ_PRODUCTION_ROADMAP.md` before any provider-specific infrastructure.
Recording this decision does **not** create, modify, or destroy any GCP
resource, does not authenticate to GCP, and does not introduce secrets. It
selects Google Cloud Platform as the target provider and captures the planning
inputs so that a human can later review and apply infrastructure-as-code
deliberately. It supersedes the earlier Azure decision; the Azure
implementation has been removed.

This document is not legal, financial, tax, or compliance advice. Public
network, token, exchange, custody, and privacy work stays blocked behind
`docs/XRIQ_LEGAL_RISK_REDUCTION.md` and the roadmap acceptance gates.

## Decision

- **Selected provider:** Google Cloud Platform.
- **Why GCP:** chosen by the human maintainer. The repository stays
  provider-aware; provider-specific code lives only under `infra/gcp/`.
- **Scope of this decision:** documentation and reviewable Terraform resources
  only. No `terraform apply`, no resource creation, no `gcloud auth` performed
  by automation.

## Account And Ownership

- **Account owner:** `xriq@kani.network` (human maintainer).
- **Project:** supplied by the owner at apply time as the `project_id` variable
  (a project id is an identifier, not a secret). It is not stored in this
  repository.
- **Billing account:** supplied at apply time as the `billing_account` variable
  (an identifier, not a secret).
- **Operational ownership:** the human maintainer owns billing, access, and
  apply/rollback decisions.

## Regions And Data Residency

- **Primary region:** `northamerica-northeast2` (Toronto).
- **Data residency assumption:** staging-devnet data is non-production test data
  with no monetary value and no real user PII. Region may be revisited before
  any public-testnet or production-candidate environment.

## Budget And Cost Controls

- **Monthly budget ceiling (staging-devnet):** USD 150.
- **Alert thresholds:** notify at 80% (USD 120) and at 100% (USD 150) of the
  monthly budget via a Cloud Billing budget.
- **Cost posture:** prefer smallest viable managed tiers (e.g. db-f1-micro,
  e2-small); avoid GKE, load balancers, and multi-region databases until needed.

## Environment Isolation

Phase 2 targets only `staging-devnet`. Later environments are out of scope for
this decision and must each get separate projects, service accounts, databases,
buckets, network boundaries, monitoring alerts, and deployment approvals, per the
roadmap Environment Model:

- `local`, `staging-devnet` (this decision), `public-testnet`,
  `production-candidate`, `mainnet` (future, separate human decisions; must not
  share credentials, keys, or databases with lower environments).

## GCP Service Mapping

| Capability | GCP service (planned) | Notes |
|---|---|---|
| Compute (node) | Compute Engine VM | Single small e2-small for the stateful node; Cloud Run is the future path for stateless API/indexer |
| Managed PostgreSQL read model | Cloud SQL for PostgreSQL | Private IP only, smallest shared-core tier for staging |
| Object storage | Cloud Storage | Uniform access, public access prevention enforced |
| Secrets | Secret Manager | No secrets in git; the db password is stored here at apply |
| Container registry | Artifact Registry | Image provenance/signing where available |
| Logs / metrics / traces | Cloud Logging + Monitoring | Enabled at the project level |
| Cost control | Cloud Billing budget | 80%/100% alert thresholds |
| Networking | Custom VPC + private services access | Database has no public IP |

## Secrets And Key Management

- No secrets in git, fixtures, logs, screenshots, or this document.
- At apply time the human maintainer authenticates locally
  (`gcloud auth application-default login`) or via a least-privilege service
  account whose key stays out of the repository.
- The Cloud SQL admin password is supplied at apply via
  `TF_VAR_postgres_admin_password` and stored in Secret Manager; it is never
  committed.
- User wallet private keys remain out of scope for server custody by default.

## Infrastructure-As-Code Plan

- Terraform is the IaC tool. Provider-specific code lives under `infra/gcp/`.
- State backend: planned GCS remote state (separate per environment); not
  configured here so static validation needs no cloud access.
- Safe validation only (no apply):

```bash
cd infra/gcp
terraform fmt -recursive -check
terraform init -backend=false
terraform validate
```

- `terraform plan` and `terraform apply` against a real GCP project are
  performed only by the human maintainer after explicit approval of the exact
  project, region, and action.

## Implementation Status

The `infra/gcp/` modules declare real Terraform resources (enabled APIs; custom
VPC + subnet + firewall + private services access; workload service account,
Artifact Registry, Secret Manager db secret; private Cloud SQL for PostgreSQL +
Cloud Storage bucket; a Compute Engine node VM; and a Cloud Billing budget with
alerts). They are validated with `terraform validate` only; **no resources are
created from automation or CI**. Applying them is a human-gated step documented
in `docs/XRIQ_GCP_APPLY_RUNBOOK.md`.

## Explicit Boundaries (unchanged)

- No resource creation, modification, or destruction from automation.
- No `gcloud auth`, `terraform apply`, or cloud deletion commands from
  automation.
- No secrets or credentials committed or transmitted through chat.
- No public mainnet/testnet, DEX, bridge, custody, privacy, exchange, or
  tokenomics behavior.
- No tag creation, movement, or deletion.

## Cheap Verification

```bash
python scripts/xriq_gcp_provider_decision_check.py
```

This guard validates the decision markers and the `infra/gcp/` layout, asserts
each module declares a google resource, and asserts no secret/backend material
is present. It creates no resources and touches no cloud account.
