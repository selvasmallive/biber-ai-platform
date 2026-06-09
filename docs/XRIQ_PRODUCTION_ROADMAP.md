# XRIQ Production Roadmap

Status: planning guide for GitHub Copilot agents and future production work.
The current Codex focus remains the XRIQ private-devnet prototype. This roadmap
defines the later path from that prototype to a production public ecosystem.
The private-devnet prototype wrap-up is recorded in
`docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md`.

This document is not legal, financial, tax, securities, banking, or compliance
advice. Before public launch, exchange integrations, token issuance, privacy
features, custody, fiat payment claims, or user-facing financial products,
human maintainers must obtain appropriate professional review.

## Strategy

The intended cost-saving path is:

1. Complete the XRIQ private-devnet prototype with Codex in this repo.
2. Push the complete prototype, tests, fixtures, and docs to GitHub.
3. Use GitHub Copilot agents and Copilot Chat for most Phase 2-6 production
   implementation work in the same repo.
4. Use Codex/OpenAI sparingly for architecture review, difficult debugging, or
   high-risk design review only.

Validate this roadmap and the Copilot cloud handoff with:

```bash
python scripts/xriq_production_roadmap_check.py
```

## Current Baseline

Phase 1 is the local/private prototype. It includes the Rust private-devnet
chain, local wallet/API/explorer/admin surfaces, smoke tests, docs, RC
checkpoints, and Phase 1.4 signed-transfer work.

Phase 1 is not production. It must not be described as mainnet-ready,
exchange-ready, legally approved, custody-ready, privacy-ready, or public
financial infrastructure.

## Non-Negotiable Guardrails

- No secrets in git.
- No browser-held private keys, seed phrases, mnemonics, raw signatures, or
  custody material.
- No production public-network behavior without the matching roadmap phase and
  explicit human issue approval.
- No DEX, bridge, asset issuance, smart-contract, privacy, CEX-listing, or
  compliance claims without roadmap acceptance gates.
- No tag creation or release publication without exact human approval.
- All accepted mutation paths must be explicit, local/private or environment
  gated, auditable, and covered by tests.
- Follow `docs/XRIQ_LEGAL_RISK_REDUCTION.md` for public-token, exchange,
  privacy, AML, CEX, custody, market-facing, and compliance-sensitive work.
- Do not create, modify, or destroy cloud resources without explicit human
  approval for the provider, account/project/subscription, region, environment,
  and exact action.

## Cloud Provider Strategy

XRIQ production may use Azure, AWS, or Google Cloud Platform. The repository
must stay provider-aware but not provider-locked until a human selects the
target provider for a phase.

Before creating provider-specific infrastructure, open a provider decision issue
that records:

- selected cloud provider,
- account/project/subscription ownership,
- regions and data residency assumptions,
- estimated monthly budget and alert thresholds,
- managed Kubernetes or VM strategy,
- managed PostgreSQL/read-model strategy,
- object storage and backup strategy,
- secrets/KMS/HSM strategy,
- container registry strategy,
- logging, metrics, tracing, and alerting strategy,
- WAF/DDoS/rate-limit strategy,
- DNS/TLS strategy,
- support plan and operational ownership,
- exit/migration risks.

Use provider-neutral names in application configuration where possible. Keep
cloud-specific code in clearly named infrastructure directories, for example
`infra/azure/`, `infra/aws/`, or `infra/gcp/`, only after the matching issue is
approved.

## Reference Production Architecture

The production architecture should evolve from the private-devnet prototype into
separate deployable surfaces:

- XRIQ validator/full node services,
- public/API gateway and rate-limited RPC/API services,
- wallet backend services that do not custody user keys by default,
- explorer/indexer workers,
- PostgreSQL read model for explorer, analytics, and audit views,
- object storage for snapshots, backups, release artifacts, and audit exports,
- React/TypeScript wallet, explorer, exchange-facing, and admin UIs,
- admin and operator tools on private networks only,
- observability stack for logs, metrics, traces, dashboards, and alerts,
- CI/CD pipeline with signed artifacts and environment promotion gates,
- backup, restore, disaster-recovery, and incident-response runbooks.

Recommended cloud service categories by provider:

| Capability | Azure example | AWS example | GCP example |
|---|---|---|---|
| Container orchestration | AKS | EKS | GKE |
| Managed PostgreSQL | Azure Database for PostgreSQL | RDS/Aurora PostgreSQL | Cloud SQL for PostgreSQL |
| Object storage | Blob Storage | S3 | Cloud Storage |
| Secrets | Key Vault | Secrets Manager | Secret Manager |
| KMS/HSM | Key Vault Managed HSM | KMS/CloudHSM | Cloud KMS/Cloud HSM |
| Container registry | Azure Container Registry | ECR | Artifact Registry |
| Logs/metrics | Azure Monitor | CloudWatch | Cloud Logging/Monitoring |
| Edge/WAF | Front Door/WAF | CloudFront/WAF | Cloud Armor/Load Balancing |

These are examples, not automatic choices. Copilot agents must not add
provider-specific infrastructure until a human issue chooses the provider and
environment.

## Environment Model

Use separate environments with hard isolation:

- `local`: developer machine only, no cloud resources required.
- `dev`: disposable cloud or local integration environment.
- `staging`: private/staging devnet with production-like topology but no public
  financial claims.
- `public-testnet`: public test-only network with no monetary-value language.
- `production-candidate`: constrained launch candidate with rollback drills.
- `mainnet`: public production network after explicit human launch approval.

Each cloud environment must have separate secrets, service accounts, databases,
object storage buckets/containers, network boundaries, monitoring alerts, and
deployment approvals. Do not share mainnet credentials, keys, or databases with
lower environments.

## Infrastructure-As-Code Policy

Terraform is the default infrastructure-as-code tool unless a human issue
chooses another tool. Infrastructure PRs should include:

- module layout,
- variable descriptions,
- state backend plan,
- provider version constraints,
- least-privilege IAM design,
- network topology,
- backup and restore design,
- cost controls and budget alarms,
- safe validation output.

Safe default validation:

```bash
terraform fmt -check
terraform validate
terraform plan
```

Do not run `terraform apply` or destructive cloud commands from Copilot unless
the issue explicitly approves the exact target and action.

## Secrets And Key Management

Production must use managed secrets and KMS/HSM-backed protection where
available. Never store secrets in git, local checked-in config, screenshots,
fixtures, or logs.

Credential rotation should be deliberate and documented. Do not implement
frequent automatic credential rotation unless a human issue explicitly approves
the rotation cadence, runbook, rollback procedure, and monitoring plan.

User wallet private keys are out of scope for server custody by default. Any
future custody or managed signing feature requires a separate architecture,
security review, legal review, and human approval.

## Observability And Operations

Production phases must add:

- structured logs with request ids and chain/network ids,
- metrics for node health, block height, peer count, mempool size, API latency,
  error rate, database health, queue depth, and wallet/explorer operations,
- traces for API and indexer flows,
- dashboards for operators,
- alert thresholds and on-call runbook,
- audit event retention policy,
- backup verification and restore drills,
- incident response severity definitions.

Do not expose admin/operator endpoints on public networks.

## Phase 1: Private-Devnet Prototype

Goal: complete an end-to-end local/private development prototype.

Primary capabilities:

- deterministic local chain state,
- wallet send/receive behavior,
- signed-transfer artifact and verifier path,
- pending state and block production,
- explorer/API/admin/audit views,
- local UI behavior,
- smoke tests and demo runbook,
- handoff docs for future agents.

Exit criteria:

- signed artifact can move through accepted local/private signed-submit to
  pending state behind explicit approval,
- block production confirms the pending transfer,
- wallet balances, account history, mempool, explorer, admin, audit, and
  ISO-style preview surfaces agree,
- final local demo runbook works from a clean clone,
- CI or documented local checks cover the flow.

## Phase 2: Hardened Private/Staging Devnet

Goal: make the prototype reliable enough for staging-like development.

Work items:

- replace ad hoc local paths with robust configuration,
- harden signed-submit parsing, verification, duplicate detection, nonce
  handling, expiry, and persistence,
- add recovery tests for corrupt pending files, replay, restart, and partial
  failure,
- strengthen API error contracts,
- improve wallet UI safety states,
- add structured audit records for accepted and refused mutations,
- improve CI coverage for Rust, TypeScript, smoke scripts, and docs,
- define staging deployment topology without public financial claims,
- draft provider-neutral Terraform module boundaries,
- add cloud provider decision issue template content,
- define secrets/KMS, database, object storage, and observability plans without
  creating production resources.

Exit criteria:

- clean clone can run local/staging smoke tests,
- restart/replay recovery tests pass,
- no unsafe key material enters browser or server custody paths,
- private/staging configuration is clearly separated from production,
- cloud provider decision is documented before provider-specific deployment.

## Phase 3: Public Testnet

Goal: expose a test-only public network with no economic value.

Work items:

- multi-node networking,
- peer discovery and node identity model,
- validator/test-node configuration,
- faucet/test coins with no monetary-value language,
- public testnet explorer,
- testnet wallet flow,
- monitoring, logs, alerting, and abuse controls,
- public testnet documentation and disclaimers,
- testnet deployment through the selected cloud provider,
- testnet faucet abuse limits and reset procedure,
- public API WAF/rate-limit/DDoS controls.

Exit criteria:

- at least two independent nodes can sync and continue producing valid blocks,
- testnet reset/recovery procedure is documented,
- testnet coins are clearly non-production and non-investment,
- public testnet API is rate-limited and monitored,
- backup/restore and rollback drills pass in the selected cloud.

## Phase 4: Security, Legal, And Economic Readiness

Goal: decide whether a production public ecosystem is responsible to launch.

Work items:

- consensus threat model,
- cryptography and crypto-agility review,
- wallet/key-management review,
- node/network abuse review,
- smart-contract or asset-issuance design review if those features exist,
- privacy design review with selective-disclosure direction,
- legal-risk reduction review,
- tokenomics and governance review,
- incident-response and disclosure process,
- external audit planning.

Exit criteria:

- high-risk findings are fixed or explicitly deferred by humans,
- production launch risks are documented,
- legal/compliance posture is reviewed by qualified humans,
- no production claims exceed what the system can prove.

## Phase 5: Production Candidate

Goal: run a constrained production-candidate network before public mainnet.

Work items:

- production-grade configuration and deployment scripts,
- backup and restore,
- monitoring and incident response,
- validator/operator runbooks,
- wallet release-candidate flow,
- explorer/API production-candidate flow,
- final testnet-to-mainnet migration or genesis procedure,
- limited-user pilot plan,
- production-candidate IaC with approval-gated apply,
- cost alarms and quota safeguards,
- cloud support/escalation path.

Exit criteria:

- production-candidate network can run continuously with monitoring,
- rollback/recovery drills are completed,
- user-facing docs and risk disclosures are reviewed,
- launch/no-launch decision is made by humans,
- no unresolved critical security, operational, or legal-risk blockers remain.

## Phase 6: Public Mainnet And Ecosystem

Goal: operate the public XRIQ ecosystem with responsible guardrails.

Work items:

- public mainnet genesis and validator/operator process,
- public wallet and explorer release,
- public API and documentation,
- governance and upgrade process,
- asset issuance or smart-contract modules only if prior phases approved them,
- DEX/bridge/exchange direction only after legal/security/economic review,
- ongoing monitoring, incident response, release management, and audits.

Exit criteria:

- public mainnet launch is explicitly approved by humans,
- operational support exists,
- security and legal risks are reviewed,
- public claims are conservative and evidence-based.

## Copilot Agent Workflow

Use GitHub issues for production work. Each issue should state:

- target phase,
- exact scope,
- files or modules likely involved,
- acceptance tests,
- commands to run,
- prohibited scope,
- expected PR summary.

Recommended issue labels:

- `phase-2-staging`
- `phase-3-testnet`
- `phase-4-security-legal`
- `phase-5-production-candidate`
- `phase-6-mainnet`
- `rust`
- `react-typescript`
- `api`
- `wallet`
- `explorer`
- `audit`
- `devops`
- `security`
- `legal-risk`

Copilot PRs should stay narrow. If an issue uncovers broader design work, open
a follow-up issue instead of expanding the PR.

## Recommended Production Issue Sequence

After Phase 1 private-devnet completion, start Phase 2 with:

1. Harden signed-submit accepted path persistence and replay.
2. Add restart/recovery smoke for pending and chain files.
3. Add CI workflow for Rust, frontend, and key Python smoke checks.
4. Add staging configuration separation.
5. Add wallet UI safety review for signed-transfer submission.
6. Add node/operator local runbook.
7. Open a cloud provider decision issue for Azure vs AWS vs GCP.
8. Draft provider-neutral Terraform module boundaries.
9. Add observability, backup, and incident-response runbook skeletons.

Do not start public testnet work until Phase 2 exit criteria are met.

## Completion Principle

Production is not a single feature. XRIQ reaches production only when the code,
tests, operational runbooks, security review, legal-risk review, user-facing
docs, monitoring, and human approval all line up for the relevant phase.
