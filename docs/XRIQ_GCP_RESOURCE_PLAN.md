# XRIQ GCP Resource Plan

Status: Phase 1.1 planning guide. Do not provision paid resources from this
document unless the user explicitly approves the spend.

## Short Answer

No Google Cloud resources are required for the immediate next XRIQ Phase 1.1
step.

Continue Milestone A locally:

- API contracts
- PostgreSQL schema contracts
- indexer contract fixtures
- ISO 20022 mapping contracts
- local validation scripts

The current Milestone A contract baseline is
`docs/XRIQ_PHASE1_1_CONTRACTS.md`.
The local PostgreSQL schema and fixtures are `xriq/db/schema.sql` and
`xriq/fixtures/phase1_1/`; validate them with
`python scripts/xriq_phase1_1_contract_check.py`.

Provision GCP only after the local contracts and first indexer prototype are
stable enough to deploy. The first Rust-only indexer scaffold is
`xriq/crates/xriq-indexer`; it still does not require GCP.

## Recommended GCP Shape

When the project is ready for cloud deployment, use a small managed footprint:

```text
Google Cloud project
 |-- Cloud Run services/jobs        Rust API, indexer job, admin service
 |-- Cloud SQL for PostgreSQL       XRIQ explorer/indexer database
 |-- Artifact Registry             Container images
 |-- Secret Manager                Database/API secrets
 |-- Cloud Storage                 Snapshots, exports, backups, artifacts
 `-- Cloud Build or GitHub Actions Container build and deploy path
```

Avoid GKE/Kubernetes at first. XRIQ Phase 1.1 does not need a cluster until the
system has multiple long-running services, heavier networking needs, or
production-grade orchestration requirements.

## When To Provision

### Now

Do not create paid GCP runtime resources yet. It is enough to have:

- a Google Cloud account
- a project name reserved or chosen
- billing budget alerts planned
- preferred region chosen
- local Docker/PostgreSQL available for development

### After Milestone A

Provision only if the API/database contracts are stable:

- Artifact Registry repository for container images
- Cloud Storage bucket for non-sensitive snapshots/export artifacts
- Secret Manager entries for future app secrets

### After Milestone B

Provision a small Cloud SQL for PostgreSQL instance only after the local
PostgreSQL schema and indexer replay tests pass and a local persistence adapter
exists. The current `xriq-indexer` crate is intentionally in-memory, so it does
not justify Cloud SQL yet.

### After Milestone C/D

Deploy early private services:

- Cloud Run service for the Rust API
- Cloud Run job for indexer replay/backfill
- Cloud Run service for the private explorer/admin UI, or static hosting if the
  UI is static-only

## Suggested Resource Names

Use names that make the private/non-production scope obvious:

```text
Project:        xriq-private-dev
Region:         choose once, then keep services together
Artifact repo:  xriq-containers
Cloud SQL:      xriq-private-dev-postgres
Storage bucket: xriq-private-dev-artifacts-<unique-suffix>
Secrets:        xriq-private-dev-db-url, xriq-private-dev-api-key
```

The user should choose the final project ID and region. For low latency from
Toronto, consider a nearby North America region, but keep cost, service
availability, and future compliance constraints in mind.

## Cost-Control Rules

- Prefer local development until a feature needs cloud integration.
- Set billing budgets/alerts before creating paid resources.
- Start with the smallest Cloud SQL shape that can run the private prototype.
- Do not create GKE, BigQuery, load balancers, public static IPs, NAT gateways,
  or multi-region databases for Phase 1.1 unless there is a clear need.
- Do not store private keys, seed phrases, or secrets in Cloud Storage or Git.
  Use Secret Manager for application secrets.
- Keep snapshots/exports test-only unless security and legal review approve
  production use.

## Phase 1.1 Deployment Order

1. Finish local API/database contracts.
2. Build local PostgreSQL schema and indexer replay tests.
3. Containerize the Rust API and indexer.
4. Push containers to Artifact Registry.
5. Provision Cloud SQL for PostgreSQL.
6. Store app secrets in Secret Manager.
7. Deploy Rust API and indexer to Cloud Run.
8. Deploy explorer/admin UI.
9. Add backups/export storage in Cloud Storage.
10. Add CI/CD only after manual deployment works.

## Not Yet Needed

- GKE/Kubernetes
- BigQuery analytics
- Pub/Sub streaming
- Dataflow
- Vertex AI
- public load balancer
- Cloud Armor
- multi-region production database
- production HSM/KMS custody architecture

These can be revisited after the local/private end-to-end prototype works.
