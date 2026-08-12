# XRIQ — Production Deployment Steps

Status: **PLANNING DOCUMENT ONLY.** Nothing here is an authorization to deploy, and nothing
in it has been executed. As of this writing XRIQ is **test-only and valueless**: it runs as a
private devnet with a functional-fee-only unit and test signatures. This document describes
*what would be required* to reach production and *which guardrails presently block that*, so
the work — and its real-world prerequisites — is visible and estimable.

Scope: **XRIQ only.** AGNA is a separate, independent project in its own private repository and
has its own `PRODUCTION_DEPLOYMENT_STEPS.md` there; it is not covered or coupled here.

No cloud resources were provisioned to produce this document. No `gcloud`/`terraform`/`psql`
was run, and no Google Cloud account (including `xriq@kani.network`) was connected. The GCP
section is an architecture plan, not an execution log.

---

## 0. Read this first — engineering-readiness is not legal/regulatory-readiness

Two independent kinds of "ready" must both be true before any real-value production step:

1. **Engineering readiness** — the code, infra, security controls, and operations are
   production-grade. This document can fully specify these steps, and they are largely under
   your control.
2. **Legal / regulatory / compliance readiness** — a value-bearing blockchain or a DEX that
   moves anything of real value implicates money-transmission / VASP, securities, AML/KYC,
   sanctions, tax, and consumer-protection law. These requirements are **external to the code**
   and cannot be satisfied by editing a policy document, by governance sign-off, or by flipping
   a flag. Governance authorization does not waive any applicable law.

There is a **known inconsistency in the current XRIQ docs** that must be reconciled *with
qualified counsel* before any real-value step, not unilaterally:

- `docs/XRIQ_LEGAL_RISK_REDUCTION.md` (v2, "controlling ... deployment-policy document")
  reframes legal review as a recommended risk-reduction measure under a phased,
  NGA-administered model — "neither ... is made an absolute engineering prerequisite by this
  document." It also states it "is not legal, tax, accounting, compliance, or regulatory
  advice."
- `docs/XRIQ_EXCHANGE_READINESS_CHECKLIST.md` and `docs/XRIQ_PRODUCTION_READINESS_ROADMAP.md`
  still describe **Hard Blocks** and hold that legally-gated items (public mainnet with value,
  token sale, DEX, bridge, custody, staking rewards) remain **blocked regardless of
  engineering progress**.

**Safe reading adopted by this plan:** for anything that touches **real value**, treat
qualified legal/regulatory clearance and an independent security audit as **hard
prerequisites**. Reconciling the two policy positions is itself a required step (see §2,
Guardrail L1). This document does not declare any legal gate satisfied or optional.

---

## 1. XRIQ production path (Layer-1 chain + explorer/indexer + wallet)

Reference roadmaps already in-repo: `docs/XRIQ_PRODUCTION_READINESS_ROADMAP.md` (engineering),
`docs/XRIQ_PRODUCTION_ROADMAP.md` (phase/gate model), `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`
(test → production signatures), `docs/XRIQ_GCP_RESOURCE_PLAN.md` (infra). The steps below
sequence and summarize them.

### A1. Engineering hardening (no real value yet)
1. **Consensus:** replace prototype consensus with a production BFT implementation — finality,
   fork handling, replay protection, deterministic state roots.
2. **Cryptography:** complete `XRIQ_PRODUCTION_CRYPTO_MIGRATION.md` — replace test-only
   signatures with a production signature scheme; keys never leave a KMS/HSM boundary.
3. **State & storage:** durable, corruption-detecting storage; deterministic replay from
   genesis; snapshot/restore; backup and point-in-time recovery.
4. **Node/network:** peer networking, mempool DoS protection, rate limiting, chain/address/
   signature/proof version metadata.
5. **APIs & indexer:** stable, versioned REST/JSON schema (`docs/XRIQ_NODE_JSON_SCHEMA.md`);
   PostgreSQL-backed indexer with replay-verified writes; explorer visibility.
6. **Wallet:** non-custodial; local signing; explicit mutation-control gate
   (`docs/XRIQ_PHASE1_2_UI_MUTATION_CONTROL_GATE.md`); no managed private keys.
7. **Quality bar:** reproducible tests, deterministic smoke scripts, fuzzing, and a documented
   coverage/security baseline (`docs/SECURITY_REVIEW.md`).

### A2. Staging (private → partner devnet, still valueless)
1. Stand up the staging devnet per `docs/XRIQ_PHASE2_STAGING_DEVNET_PLAN.md` and
   `docs/XRIQ_PHASE2_NODE_OPERATOR_RUNBOOK.md`.
2. Config separation (`docs/XRIQ_PHASE2_CONFIG_SEPARATION.md`): genesis, fees, and network
   identity are environment-scoped; test genesis can never be loaded by a production binary.
3. Independent node operators; observability (`docs/XRIQ_GCP_OBSERVABILITY.md`); public edge
   hardening design (`docs/XRIQ_GCP_PUBLIC_EDGE.md`).

### A3. Public testnet candidate (still no real value)
1. Satisfy the compatibility gates in `docs/XRIQ_EXCHANGE_READINESS_CHECKLIST.md` (Gate 2+) and
   `docs/XRIQ_PHASE3_PUBLIC_TESTNET_PLAN.md`.
2. External security review of the full stack; published disclosure policy; incident runbooks.

### A4. Production / mainnet with value — **GATED** (do not start until §2 gates clear)
1. Complete **all** legal/regulatory and security-audit guardrails in §2 and obtain the written
   artifacts.
2. NGA change-control record authorizing the specific production phase per the controlling
   policy — **in addition to**, not instead of, the legal/audit artifacts.
3. Only then: production genesis, key ceremony inside HSM/KMS, monitored rollout with a
   documented rollback and pause capability.

---

## 2. Guardrail inventory and how each is satisfied

"Satisfy" means: complete the underlying work, obtain the real external artifact where one is
required, and record its status in the doc named. For legal/compliance/audit gates, "satisfy"
is **not** editing the guardrail text — it is completing the process the text points to.

### XRIQ guardrail files

| # | File | What it blocks | How to satisfy |
|---|------|----------------|----------------|
| L1 | `docs/XRIQ_LEGAL_RISK_REDUCTION.md` | Controlling deployment-phase policy; defines NGA, approved wallets, phase behavior. | Reconcile its v2 "not-an-absolute-prerequisite" framing with the Hard-Block docs **with qualified counsel**; record the resolved position and an auditable NGA change-control entry for the target phase. Necessary but **not sufficient** on its own for real value. |
| L2 | `docs/XRIQ_LEGAL_COUNSEL_QUESTIONS.md` | Open legal questions for counsel. | Engage qualified counsel; obtain written answers; attach the opinion/artifacts. |
| L3 | `docs/XRIQ_EXCHANGE_READINESS_CHECKLIST.md` | "Hard Blocks": public mainnet/value, token sale/airdrop, DEX, custody, fiat on/off-ramp, bridge, listing prep. | Complete each named review gate (security, legal, compliance, tokenomics, ops, custody) and record explicit review status; do not contact any venue/market-maker before then. |
| L4 | `docs/XRIQ_PRODUCTION_READINESS_ROADMAP.md` | Legally-gated items "blocked regardless of engineering progress". | Same legal/audit artifacts as L1–L3; engineering completion alone does **not** lift this. |
| S1 | `docs/SECURITY_REVIEW.md` | Security baseline / review status. | Independent third-party security audit + remediation; record findings closed. |
| G1 | `docs/XRIQ_PHASE1_2_UI_MUTATION_CONTROL_GATE.md` | Wallet state-changing actions behind an explicit control gate. | Implement and test the gate; keep it enforced in production builds. |
| G2 | `docs/XRIQ_GCP_RESOURCE_PLAN.md` | "Do not provision paid resources ... unless the user explicitly approves the spend." | Get explicit spend approval; provision least-privilege, per §3. |
| G3 | `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md` | Test-only signatures in use. | Complete the migration to production crypto; keys in HSM/KMS only. |
| P1 | `docs/XRIQ_PHASE2_CONFIG_SEPARATION.md` | Test vs production config bleed. | Environment-scoped genesis/fees/identity; production binary rejects test genesis. |

(AGNA's guardrails are tracked separately in AGNA's own repository and its
`PRODUCTION_DEPLOYMENT_STEPS.md`; they are not part of XRIQ.)

---

## 3. Google Cloud Platform resources

This is an architecture plan drawn from `docs/XRIQ_GCP_RESOURCE_PLAN.md`,
`docs/XRIQ_GCP_TESTNET_TOPOLOGY.md`, `docs/XRIQ_GCP_PUBLIC_EDGE.md`, and
`docs/XRIQ_GCP_OBSERVABILITY.md`. **Nothing here has been provisioned.** Per the resource plan,
"No Google Cloud resources are required for the immediate next XRIQ step," and paid resources
must not be provisioned without explicit spend approval.

### 3.1 Managed footprint (early private/staging services)
```
Google Cloud project (dedicated, non-personal; budget alerts on)
 ├─ Artifact Registry     container images
 ├─ Cloud Run (svc/jobs)  Rust API, indexer job, admin service
 ├─ Cloud SQL (Postgres)  explorer/indexer database
 ├─ Secret Manager        DB/API secrets (no secrets in code or env files)
 ├─ Cloud Storage         snapshots, exports, backups, artifacts
 └─ Cloud Build / GH Actions   build + deploy pipeline
```
Avoid GKE/Kubernetes at first (per the resource plan) — a cluster is unjustified until there
are multiple long-running services or production orchestration needs.

### 3.2 Additional resources for a public network with value (only after §2 gates clear)
- **GKE (or managed VMs)** for validator / full-node fleet with autoscaling and node pools.
- **Cloud KMS + Cloud HSM** (or external HSM) for the production signing/key ceremony —
  keys never exported; ties to Guardrail G3.
- **Cloud Load Balancing + Cloud Armor** (WAF/DDoS) for the public edge; **Cloud CDN** for
  static explorer assets; **Cloud DNS** for the domain.
- **VPC + Cloud NAT + private service connect**; nodes on private subnets, minimal public
  surface.
- **Cloud Monitoring, Logging, Trace, Error Reporting**; alerting + on-call; uptime checks.
- **Cloud SQL** with HA, read replicas, PITR; **backups** to Cloud Storage with lifecycle rules.
- **IAM:** a dedicated least-privilege deployment service account per environment; Workload
  Identity Federation for CI (no long-lived keys); org policies + billing budgets/quota.

### 3.3 GCP security/operational preconditions
- Use a **dedicated deployment identity**, not a personal login. (Note: an earlier concern in
  this project was avoiding GCP connection under `xriq@kani.network`; provisioning should use a
  purpose-made, least-privilege service account, and any human owner/billing account is a
  deliberate, separate decision by you.)
- No credentials committed to either repo; all secrets in Secret Manager/KMS.
- Separate projects (or at least separate service accounts + VPCs) for testnet vs production.
- Budget alerts and hard quotas before any paid resource is created.

---

## 4. What this document does NOT do

- It does **not** deploy anything, provision any GCP resource, run `gcloud`/`terraform`/`psql`,
  or connect to any Google Cloud account.
- It does **not** give XRIQ, AGNA, or any token real value, and does **not** lift any guardrail.
- It does **not** constitute legal, tax, accounting, compliance, or regulatory advice, and does
  **not** declare any legal or audit gate satisfied. Those require qualified counsel and
  independent auditors, whose written artifacts are the actual evidence of satisfaction.

## 5. Suggested order of execution
1. Finish XRIQ engineering hardening (A1–A3) — all still valueless.
2. Reconcile the legal-policy inconsistency and engage counsel (L1, L2, L4); commission the
   independent security audit (S1).
3. Obtain written legal/regulatory clearance and audit sign-off; record artifacts against L3.
4. Get explicit GCP spend approval (G2); provision the §3.1 footprint for staging.
5. NGA change-control authorization for the specific production phase (L1).
6. Only with 2–5 complete: production crypto (G3), §3.2 resources, monitored rollout with
   rollback/pause.
