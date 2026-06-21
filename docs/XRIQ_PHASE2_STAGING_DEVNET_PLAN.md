# XRIQ Phase 2 Hardened Private/Staging Devnet Plan

Status: active Phase 2 planning checkpoint, no production resources created.

This document opens Phase 2 of `docs/XRIQ_PRODUCTION_ROADMAP.md`
(Hardened Private/Staging Devnet). It is a planning and acceptance-criteria
checkpoint only. It does not create cloud resources, choose a cloud provider,
publish a public network, create or move tags, or change runtime behavior. It
builds on the completed private-devnet baseline recorded in
`docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md` and anchored at the Phase 1.4 RC tag
`phase1-4-xriq-local-signed-submit-rc1` at commit `45be474`.

This document is not legal, financial, securities, tax, banking, or compliance
advice. All public-network, token, DEX, bridge, custody, privacy, exchange, and
compliance work stays blocked behind `docs/XRIQ_LEGAL_RISK_REDUCTION.md` and the
roadmap acceptance gates until qualified humans approve a different path in
writing.

## Goal

Make the private-devnet prototype reliable enough for staging-like development
without adding any public financial claims. Phase 2 hardens the existing
local/private surfaces (signed-submit, pending state, block production, wallet,
explorer, admin, audit) and prepares provider-neutral operational design so a
later human can choose Azure, AWS, or GCP. Phase 2 does not deploy anything.

## Phase 2 Acceptance Criteria

Phase 2 is complete only when all of the following hold, mirroring the roadmap
Phase 2 exit criteria:

- A clean clone can run the local/staging smoke tests deterministically.
- Restart and replay recovery tests pass for pending and chain files.
- Signed-submit parsing, verification, duplicate detection, nonce handling,
  expiry, and persistence are hardened and covered by tests.
- Recovery tests exist for corrupt pending files, replay, restart, and partial
  failure.
- API error contracts are explicit, typed, and tested.
- Wallet UI safety states are reviewed; no unsafe key material enters the
  browser or any server custody path.
- Structured audit records exist for both accepted and refused mutations.
- CI coverage exists for Rust, TypeScript, smoke scripts, and docs guards.
- Private/staging configuration is clearly separated from production
  configuration and cannot be confused with production mode.
- A cloud provider decision is documented (issue template content drafted)
  before any provider-specific deployment, but no provider is chosen here.

## Production-Hardening Gaps From The Private-Devnet Prototype

These are the known gaps carried out of Phase 1.4 into Phase 2 work items. They
are tracked here for narrow, issue-scoped follow-up PRs:

- Configuration: ad hoc local paths and flags should move to robust, validated
  configuration with clear local vs staging separation.
- Signed-submit durability: persistence, duplicate detection, nonce handling,
  and expiry need hardening and explicit failure modes.
- Recovery: corrupt pending file, replay, restart, and partial-failure paths
  need deterministic recovery tests.
- API contracts: error responses need stable, typed, documented contracts.
- Wallet UI safety: submission and refusal states need a safety review with no
  key material in the browser.
- Audit: accepted and refused mutations need structured, queryable audit
  records.
- CI: Rust, TypeScript, Python smoke, and docs guards need automated coverage.
- Operational design: provider-neutral observability, backup, rollback, and
  incident-response skeletons need drafting without creating resources.

## Environment Boundaries

Phase 2 keeps hard isolation between environments. The boundaries below match
the roadmap Environment Model. Phase 2 work touches only `local` and the design
of `staging-devnet`; it must not provision or expose the later environments.

- `local`: developer machine only, no cloud resources required. This is the
  current Phase 1.4 baseline scope.
- `staging-devnet`: private/staging devnet with production-like topology but no
  public financial claims. Phase 2 designs this; it does not deploy it.
- `public-testnet`: public test-only network with no monetary-value language.
  Out of scope for Phase 2.
- `production-candidate`: constrained launch candidate with rollback drills.
  Out of scope for Phase 2.
- `mainnet`: public production network after explicit human launch approval.
  Out of scope for Phase 2.

Each cloud environment must have separate secrets, service accounts, databases,
object storage, network boundaries, monitoring alerts, and deployment
approvals. Lower environments must never share mainnet credentials, keys, or
databases.

## Required Operational Design Decisions

Phase 2 records the required decision areas without making provider-specific or
production choices. Each item is provider-neutral until a human selects a
provider in a separate cloud provider decision issue.

- Config: environment-scoped, validated configuration with explicit local vs
  staging separation and no secrets in git.
- Secrets/KMS: managed secrets storage and KMS/HSM-backed protection where
  available; never store secrets in git, fixtures, logs, or screenshots.
- IAM: least-privilege service accounts per environment.
- Deployment: infrastructure-as-code with reviewable plans; Terraform is the
  default IaC choice unless a human issue chooses another tool.
- Observability: structured logs, metrics, traces, dashboards, and alert
  thresholds with an on-call runbook.
- Backup: encrypted backups with verified restore drills.
- Rollback: documented rollback and disaster-recovery procedures.
- Cloud provider: no provider chosen here. A cloud provider decision issue must
  record provider, account/project/subscription, regions, budget/alerts,
  compute strategy, managed PostgreSQL strategy, object storage, secrets/KMS,
  container registry, observability, WAF/DDoS/rate-limit, DNS/TLS, support
  plan, and exit/migration risks before any provider-specific IaC.

## Hard Scope Boundaries

Phase 2 must not, without the matching roadmap phase and explicit human issue
approval:

- implement public mainnet or public testnet behavior;
- implement DEX trading, bridge, wrapped/synthetic asset, CEX listing, custody,
  privacy protocol, smart-contract VM, asset issuance, or tokenomics;
- generate, store, or manage browser-held private keys, seed phrases,
  mnemonics, raw signatures, or hosted wallet custody material;
- create, modify, or destroy Azure, AWS, GCP, DNS, registrar, payment,
  exchange, or production cloud resources;
- run `terraform apply`, deployment, or cloud deletion commands;
- commit secrets or rotate credentials;
- claim legal, compliance, exchange, or production readiness;
- create, move, delete, recreate, or push any tag from a generic continue.

Accepted mutation paths must stay explicit, local/private or environment gated,
auditable, and covered by tests, consistent with
`.github/copilot-instructions.md` and `docs/XRIQ_LEGAL_RISK_REDUCTION.md`.

## Recommended Phase 2 PR Sequence

Follow the roadmap Phase 2 issue sequence in narrow, separately reviewable PRs:

1. Harden signed-submit accepted path persistence and replay.
2. Add restart/recovery smoke for pending and chain files.
3. Add CI workflow for Rust, frontend, and key Python smoke checks.
4. Add staging configuration separation.
5. Add wallet UI safety review for signed-transfer submission.
6. Add node/operator local runbook.
7. Open a cloud provider decision issue for Azure vs AWS vs GCP.
8. Draft provider-neutral Terraform module boundaries.
9. Add observability, backup, and incident-response runbook skeletons.

Do not start public testnet work until these Phase 2 exit criteria are met.

## Cheap Verification

Validate this plan's guardrails from the repository root:

```bash
python scripts/xriq_phase2_plan_check.py
```

This guard validates plan markers, scope boundaries, the Phase 1.4 baseline tag
presence, and cross-document references. It does not run Rust tests, create
tags, touch cloud resources, or change runtime state. Also keep the prior
guards green:

```bash
python scripts/xriq_production_roadmap_check.py
python scripts/xriq_private_devnet_wrapup_check.py
```
