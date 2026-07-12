# Codex Handoff

Last updated: 2026-07-12

## Current Goal

Active scope as of 2026-07-12: resume **BIBER MVP only**. Do not continue XRIQ
work in this repo unless the user explicitly asks for it; XRIQ continuation is
now treated as a separate XRIS-Coin project. Keep model providers swappable,
keep OpenAI mentor optional and disabled by default, and use GPU/training only
when a concrete BIBER eval/training need exists and current runtime access is
available. The first BIBER resume checkpoint is on branch
`biber/mvp-resume-20260712`: repo-context stack profiles now cover Rust,
PostgreSQL, React/TypeScript/JavaScript, Python/FastAPI, Docker/Compose, GitHub
Actions, Bash, and TensorFlow/Keras; the test runner now exposes matching
allowlisted commands for Python pytest, Cargo, npm check/test/build, and Docker
Compose config. Verification used local compile checks plus direct no-pytest
metadata validations; full pytest was not run because the local bundled Python
runtime does not have `pytest` installed.
Second BIBER resume checkpoint on the same branch:
`scripts/biber_agent_client.py mvp-loop` now supports `--local-target-root`,
which runs context planning, safe workspace edit plan/apply, allowlisted test
execution, and diagnosis directly against a local repo without resolving a
BIBER API key. GitHub save/PR remains server-backed and still requires the API.
Verified with `compileall` and a temporary-repo no-server smoke that changed a
Python file through the local edit-plan/apply path and wrote a local MVP-loop
artifact.
Dedicated BIBER-only sparse checkout created at
`C:\Users\vselv\OneDrive\Biber\biber-mvp-only` from branch
`biber/mvp-resume-20260712`. It intentionally excludes `xriq/`, `infra/`,
`deploy/`, XRIQ docs, and XRIQ scripts. Future BIBER sessions should prefer
that folder and start with `docs/BIBER_ONLY_WORKSPACE.md`.

Phase 1 goal is complete: XRIQ private-devnet RC1 is tagged and pushed. Phase
1.1 goal is complete for the local/private end-to-end RC1 baseline: Rust
API/backend, React + TypeScript UI, PostgreSQL indexer, ISO 20022 compatibility
adapter, and readiness guardrails are tagged as
`phase1-1-xriq-local-e2e-rc1`. Phase 1.2 local/private post-RC hardening is
complete and tagged as `phase1-2-xriq-local-private-hardening-rc1` at commit
`b3a2fe4`. Phase 1.3 local/private behavioral wallet testing is complete and
tagged as `phase1-3-xriq-local-private-behavior-rc1` at commit `345d353`.
Current next scope is post-private-devnet decision work only. The consolidated
private-devnet wrap-up is `docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md`, with cheap
verification in `scripts/xriq_private_devnet_wrapup_check.py`. Phase 1.4
local/private signed-transfer RC1 is complete and tagged as
`phase1-4-xriq-local-signed-submit-rc1` at commit `45be474`.
Phase 2 (Hardened Private/Staging Devnet) has now been opened with a narrow
planning checkpoint only: `docs/XRIQ_PHASE2_STAGING_DEVNET_PLAN.md` records the
Phase 2 acceptance criteria, the production-hardening gaps carried out of the
private-devnet prototype, the `local`/`staging-devnet`/`public-testnet`/
`production-candidate`/`mainnet` environment boundaries, and provider-neutral
operational design decisions (config, secrets/KMS, IAM, deployment,
observability, backup, rollback) without choosing Azure/AWS/GCP or creating any
cloud resource. The cheap guard is `scripts/xriq_phase2_plan_check.py`. This
checkpoint creates no tags, touches no secrets or cloud resources, and changes
no runtime behavior.
The first Phase 2 hardening code item has now begun on branch
`xriq/phase2-staging-devnet-plan`: pending-file replay is now idempotent for
duplicate entries. Previously, a pending file containing the same accepted
transaction twice (for example from a crash mid-append or a double-write) would
brick node startup, because the replay loop in
`private_devnet_node_with_pending_file` (xriq/crates/xriq-node/src/lib.rs)
propagated `MempoolError::DuplicateTransaction`. The loop now treats a duplicate
as a benign skip (the transaction is already in the mempool), so a single
corrupt/duplicated pending line no longer prevents recovery. This is covered by
the new test `node_runner_replays_duplicate_pending_line_idempotently` and does
not change the default-refused signed-submit contract, enable any UI mutation,
or touch secrets/cloud/tags. Verified with `cargo test -p xriq-node -j 1`
(53 passed), `cargo test -p xriq-api -j 1` (75 passed), and
`python scripts/xriq_phase1_4_signed_submit_lifecycle_smoke.py` (ok).
Two further Phase 2 hardening items then landed on the same branch. First,
corrupt-pending-line recovery: `read_pending_transaction_records` is now
fail-open and `quarantine_corrupt_pending_lines` moves unparseable lines to a
`<pending-file>.quarantine` sidecar (with a `xriq-pending-quarantine-v1` marker)
and self-heals them out of the live pending file exactly once, so a single
corrupt/truncated/tampered line no longer bricks startup and nothing is silently
lost. Second, a restart/recovery smoke
`scripts/xriq_phase2_restart_recovery_smoke.py` drives xriq-node and xriq-api
across real process restarts to prove accepted signed-submit persists, survives
a clean restart, replays a duplicate line idempotently, quarantines a corrupt
line, and confirms through block production across a final restart. Verified:
`cargo test -p xriq-node -j 1` (54 passed), `cargo test -p xriq-api -j 1`
(75 passed), the restart/recovery smoke (ok), and the Phase 1.4 lifecycle smoke
(ok). On Windows/OneDrive, run cargo with `CARGO_TARGET_DIR` pointed outside the
OneDrive tree to avoid transient `LNK1104` link locks. The remaining Phase 2
items are a CI workflow (Rust + frontend + Python smokes), staging config
separation, a wallet UI safety review, a node/operator runbook, and the cloud
provider decision issue. No secrets, cloud resources, or tags were touched.
The CI workflow then landed at `.github/workflows/ci.yml` (Rust fmt/build/test
plus the lifecycle and restart/recovery smokes, the doc/roadmap guards, and the
explorer-ui check/build); its first hosted run on `main` passed all three jobs.
The user then selected Azure as the cloud provider (account owner
`selva@kani.network`, region `eastus`, staging-devnet monthly budget ceiling
USD 150 with alerts at 80%/100%). This is recorded as a decision and Terraform
module boundaries only, with no resources created and no credentials handled:
`docs/XRIQ_AZURE_PROVIDER_DECISION.md` plus `infra/azure/` (root module wiring
boundary-only network/security/data/compute/observability modules that create no
resources yet). Static validation passes locally (`terraform fmt -recursive
-check`, `terraform init -backend=false`, `terraform validate`) and the cheap
guard `scripts/xriq_azure_provider_decision_check.py` passes. The state backend
is intentionally unconfigured so validation needs no Azure access; `az login`,
`terraform plan`, and `terraform apply` against a real subscription remain
human-only actions after explicit approval. The remaining Phase 2 items are
staging config separation, a wallet UI safety review, a node/operator runbook,
and then implementing the `infra/azure/` module resources for a human-run plan.
No secrets, cloud resources, or tags were touched.
Staging config separation has now begun: an explicit, fail-closed deployment
environment profile lives in `xriq-core`
(`xriq/crates/xriq-core/src/environment.rs`: `Environment::{Local,
StagingDevnet}`, with `production`/`mainnet`/`public-testnet`/unknown rejected).
The `xriq-api` binary takes an optional `--environment local|staging-devnet`
flag on `request` and `serve-readonly`, defaulting to `local` so all existing
commands, tests, fixtures, and smokes are unchanged; production-class values
make the binary exit non-zero with a clear error. See
`docs/XRIQ_PHASE2_CONFIG_SEPARATION.md`. The API response `environment` field
(`private-devnet`) and genesis `chain_id` (`xriq-devnet`) are intentionally
unchanged to preserve response contracts. Verified: `cargo test -p xriq-core -j
1` (23 passed, incl. fail-closed parse tests), `cargo test -p xriq-api -j 1`
(76 passed, incl. `environment_flag_is_fail_closed_for_request_and_serve`), the
lifecycle and restart/recovery smokes (ok under the default local profile), and
a manual binary check that `--environment production` is rejected. The node CLI
and explorer-ui environment gating remain follow-ups. No secrets, cloud
resources, or tags were touched.
The wallet UI safety review is now complete. The explorer-ui was reviewed and
holds no key material: it transmits only transfer fields (addresses, amount,
fee, nonce, expiry), performs no client-side signing, and uses no browser
storage of key-like material. This is enforced by a new CI-run guard
`xriq/apps/explorer-ui/scripts/check-wallet-key-safety.mjs` (wired into
`npm run check`), which fails the build on any forbidden pattern (private/secret
key, seed phrase, mnemonic, key pair, keystore, crypto.subtle, generateKey,
localStorage, sessionStorage, indexedDB, document.cookie, raw signature, sign
transaction) and asserts the affirmative no-signing markers. Findings are
recorded in `docs/XRIQ_PHASE2_WALLET_UI_SAFETY_REVIEW.md`. Verified: the guard
passes (10 files scanned), a negative probe confirmed it catches a violation,
and `npm run check` is green. No secrets, cloud resources, or tags were touched.
Config separation was then extended to the `xriq-node` CLI: a fail-closed
`--environment local|staging-devnet` flag is parsed centrally in
`run_node_command` (and validated in the serve config parser), stripped before
per-command parsing, defaulting to local and rejecting production-class values
with the `unsupported_environment` error (`NodeRunnerError::UnsupportedEnvironment`).
The Phase 2 "clean clone can run local/staging smoke tests" exit criterion is
now met: `scripts/xriq_phase2_restart_recovery_smoke.py` accepts
`--environment`, and `scripts/xriq_phase2_staging_smokes.py` builds once and runs
the lifecycle smoke (local) plus the restart/recovery smoke under
`staging-devnet`. CI runs the staging-smokes runner on every push from a clean
checkout (replacing the two separate smoke steps). Verified: `cargo test -p
xriq-node -j 1` (55 passed, incl. `node_environment_flag_is_fail_closed`), the
staging-devnet restart/recovery smoke (ok), and the staging-smokes runner (ok).
The node/operator local runbook is now complete:
`docs/XRIQ_PHASE2_NODE_OPERATOR_RUNBOOK.md` documents build, environment
profiles, running the node/API, accepted-mutation flags, pending-file
duplicate/corrupt recovery, snapshots, the smokes/guards, and an incident quick
reference, all local/staging only. A local node/operator runbook needs no Azure
resources, so no cloud changes were made for it; standing up Azure remains a
later human-gated `terraform plan`/`apply` step. The explorer-ui environment
banner and implementing the `infra/azure/` module resources remain follow-ups.
With this, all five Phase 2 roadmap exit criteria are satisfied (clean-clone
staging smokes in CI, restart/replay recovery, no browser/server key material,
private/staging config separated from production across both binaries, and a
documented cloud-provider decision before any provider-specific IaC). No secrets,
cloud resources, or tags were touched.
The explorer-ui now shows an environment banner (`VITE_XRIQ_ENVIRONMENT`,
local/staging-devnet/unsupported), and the `infra/azure/` Terraform modules now
declare real resources: resource group; network (VNet, app subnet, delegated
database subnet, NSG); security (Key Vault with RBAC, workload user-assigned
identity, container registry, AcrPull role); data (object storage + a
VNet-integrated private PostgreSQL Flexible Server, password auth via the
sensitive apply-time `TF_VAR_postgres_admin_password`); compute (a single small
SSH-key-only Linux node VM, private); and observability (Log Analytics,
Application Insights, a consumption budget with 80%/100% alerts). `terraform
validate` passes with no warnings, and the CI Terraform job validates it on every
push. Nothing is applied from automation: provisioning is a human-gated step in
`docs/XRIQ_AZURE_APPLY_RUNBOOK.md` (the operator runs `az login`, sets
non-secret tfvars plus the password env var, then `terraform plan`/`apply`). The
provider-decision guard now asserts each module declares an azurerm resource and
that no secret/backend material is committed. No secrets, cloud resources, or
tags were touched by automation. Note: a real `terraform plan` may need minor
region/quota-specific SKU adjustments since only `validate` (not `plan`) runs in
CI.
Provider switch (supersedes the Azure paragraphs above): the user then chose
**Google Cloud Platform** instead of Azure (owner `xriq@kani.network`, region
`northamerica-northeast2`, same USD 150 budget). The Azure implementation was
removed (`infra/azure/`, the Azure decision doc, Azure apply runbook, and Azure
guard are deleted) and replaced by GCP under `infra/gcp/`:
`docs/XRIQ_GCP_PROVIDER_DECISION.md` records the decision;
`scripts/xriq_gcp_provider_decision_check.py` is the guard (asserts each module
declares a `google_` resource and no secret/backend material); and
`docs/XRIQ_GCP_APPLY_RUNBOOK.md` is the human-operated apply runbook. The GCP
modules declare real resources (enabled project APIs; custom VPC + subnet +
firewall + private services access; workload service account, Artifact Registry,
Secret Manager db secret; private-IP Cloud SQL for PostgreSQL + Cloud Storage
bucket; a Compute Engine node VM; and a Cloud Billing budget with 80%/100%
alerts). `terraform fmt -recursive -check` and `terraform validate` pass with the
`hashicorp/google ~> 6.0` provider, and CI's Terraform job now validates
`infra/gcp` and the doc-guards run the GCP guard. Nothing is applied from
automation; `gcloud auth`, `terraform plan`/`apply`, and the Cloud SQL password
(`TF_VAR_postgres_admin_password`, stored in Secret Manager at apply) remain
human-only. A real `terraform plan` may still need minor region/quota tier
adjustments since only `validate` runs in CI.
The GCP apply path was then hardened for autonomous execution by a Codex agent:
`docs/XRIQ_GCP_APPLY_RUNBOOK.md` is now an agent-executable runbook (pre-enable
APIs via `gcloud`, generate SSH key + DB password, write `terraform.tfvars`,
`init`/`plan`/`apply -auto-approve` with one retry, plus a troubleshooting
table). The Terraform adds a `hashicorp/time` `time_sleep.wait_for_apis` gate so
newly-enabled APIs propagate before dependent resources, and an `enable_budget`
flag (default true) so the Cloud Billing budget can be skipped when
billing-account IAM (`roles/billing.costsManager`) is unavailable. The GCP guard
now checks git-tracked files (via `git ls-files`) instead of the filesystem, so a
local operator `terraform.tfvars`/`tfstate`/`tfplan` no longer false-fails it,
and `.gitignore` also ignores bare `tfplan`. `terraform validate` still passes
with the `time` provider added.
Milestone: the staging-devnet was then provisioned on GCP by a Codex agent
(project `xriq-project-dev`, Terraform workspace `xriq-project-dev`). Non-secret
outputs (from `terraform output`): node VM internal IP `10.42.1.2`; Cloud SQL
private IP `10.103.0.3` (no public IP), connection name
`xriq-project-dev:northamerica-northeast2:xriq-staging-devnet-postgres`, db
`xriq`, admin user `xriqpgadmin`; Artifact Registry
`xriq-staging-devnet-containers`; bucket
`xriq-staging-devnet-artifacts-dev01a`; VPC `xriq-staging-devnet-vpc`. The DB
password lives only in Secret Manager (`xriq-staging-devnet-db-password`) and
local gitignored files — never in the repo or chat. Apply-time deviations:
Cloud SQL `settings.edition = "ENTERPRISE"` was pinned (committed as `5e66aee`)
so `db-g1-small` works instead of defaulting to Enterprise Plus; the local
`terraform.tfvars` uses `name_suffix = "dev01a"` because the `dev01` bucket name
was globally taken; and `enable_budget = false` locally because
`google_billing_budget` returned a 400 (the budget is optional and can be created
manually in Cloud Billing). `terraform.tfvars` and `terraform.tfstate.d/` stay
local and gitignored; the guard checks git-tracked files so they do not
false-fail it. A VM deploy package was then prepared for a Codex agent to run:
`xriq/Dockerfile` (+ `.dockerignore`) builds `xriq-node`/`xriq-api`/`xriq-indexer`
into a slim image with `psql`; `deploy/gcp/` holds the run wrappers, systemd
units (`xriq-api.service` file-backed API with staging mutation flags, plus an
`xriq-indexer` service+timer that populates Cloud SQL), `xriq.env.example`, and
`vm-bootstrap.sh`; `docs/XRIQ_GCP_DEPLOY_RUNBOOK.md` is the agent-executable
runbook. Grounding facts from a code map: the node/API run file-backed on the VM
today; `xriq-indexer apply-postgres --database-url ...` supports a real
connection string so it can populate the private Cloud SQL from the VM; but
`xriq-api`'s own Postgres read-model path is docker-only
(`--postgres-docker-container`), so serving the read model *from* Cloud SQL is a
documented follow-up needing a native PG client in `xriq-api`. The Terraform
gained an `enable_iap_ssh` firewall rule (default true) so the no-external-IP VM
is reachable via `gcloud compute ssh --tunnel-through-iap`; `terraform validate`
and all guards still pass. Verified locally: `cargo build --release -p xriq-node
-p xriq-api -p xriq-indexer` succeeds and the deploy shell scripts pass
`bash -n`. Applying the IAP rule, building/pushing the image, and running the
bootstrap on the VM remain human/agent cloud steps, not repo automation.
Milestone: the deployment was then completed on GCP `xriq-project-dev` by a Codex
agent. The `xriq-api` service is active and healthy on the VM
(`xriq-staging-devnet-node`, `0.0.0.0:8090`, health `ok`, network `xriq-devnet`),
and the indexer populated the private Cloud SQL read model (a successful run with
`schema_applied=true`, `write_plan_applied=true`; `verify-postgres` showed the
genesis state: `accounts=2`, `account_balances=2`, `indexer_runs=1`, `blocks=0`,
`latest_height=none`). Three deploy fixes found during the real run are now in the
repo: the network module adds a Cloud Router + Cloud NAT
(`xriq-staging-devnet-router`/`-nat`) so the no-external-IP VM has outbound access
for package installs; `xriq/Dockerfile` copies `db/schema.sql` into the image at
`/opt/xriq/db`; and `deploy/gcp/bin/xriq-indexer-run.sh` passes
`--schema-file /opt/xriq/db/schema.sql`; plus `xriq/.gcloudignore` keeps build
dirs out of Cloud Build uploads. All secret material (DB password, VM
`/etc/xriq/xriq.env`, local credentials JSON) stays out of the repo. Both earlier
follow-ups are now addressed. First, `xriq-api` can serve the Postgres read model
directly from a host such as Cloud SQL: a new `--postgres-database-url-env <ENV>`
option (default target `XRIQ_POSTGRES_URL`) resolves the connection URL from the
environment at query time and runs `psql` with `PG*` env vars, so the password
never enters the config, argv, or logs; the docker-container path stays for local
use, and the two are mutually exclusive (`build_postgres_read_model_config`, plus
`parse_postgres_url`/`psql_url_query`, covered by unit tests;
`cargo test -p xriq-api` = 78). The API run wrapper auto-enables this when
`XRIQ_POSTGRES_URL` is set. Second, a live-chain smoke
`deploy/gcp/bin/xriq-live-smoke.sh` plus `docs/XRIQ_GCP_LIVE_CHAIN_SMOKE.md`
redeploys the updated image/config and advances the chain (staging mutation flags
now include `--enable-local-wallet-send`, so a block can be produced without a
client artifact): send -> produce block -> re-run the indexer -> verify the Cloud
SQL counts (`blocks`/`latest_height`) and the API's
`/api/v1/admin/postgres/read-model-status` reflect it. Running the redeploy and
smoke on the VM remains a human/agent cloud step.
An observability layer was then added (human-approved next step):
`infra/gcp/modules/observability` now creates native-metric alert policies
(Cloud SQL CPU/disk, node VM CPU; tunable thresholds via
`cloudsql_cpu_threshold`/`cloudsql_disk_threshold`/`vm_cpu_threshold`, default
0.80/0.85/0.90) and a `google_monitoring_dashboard` (Cloud SQL CPU/disk/
connections + VM CPU), all wired to an email notification channel that is now
decoupled from the budget (created whenever `budget_notification_email` is set).
The security module grants the workload service account
`roles/monitoring.metricWriter` and `roles/logging.logWriter`, and
`vm-bootstrap.sh` installs the Cloud Ops Agent for VM memory/disk metrics and
logs. See `docs/XRIQ_GCP_OBSERVABILITY.md`. `terraform validate` passes; applying
(re-apply + re-bootstrap) is human/agent-operated. App-level error-log alerting
is a documented follow-up. Recommended sequence for the remaining approved work:
observability (done) -> TLS/ingress -> Phase 3 public testnet, with the
public-facing steps gated behind the roadmap security/legal review.
TLS/ingress (approved next step) is now built as an optional public edge:
`infra/gcp/modules/edge` adds a global external HTTPS load balancer with a
Google-managed TLS certificate, a Cloud Armor policy (per-IP rate limit,
GET/HEAD/OPTIONS only so all POST mutations are blocked, and `/api/v1/admin`
blocked), a health check on `/api/v1/health`, an instance group over the node VM,
and a firewall for the Google Front End/health-check ranges. It is gated by
`enable_public_edge` (default **false**) plus a required `api_domain`, so nothing
is exposed unless a human opts in and points a DNS A record at the `edge_ip`
output (the managed cert provisions after DNS resolves). This makes the API
publicly reachable — a deliberate posture change documented, with the read-only
locking and the Phase 3/legal caveats, in `docs/XRIQ_GCP_PUBLIC_EDGE.md`.
`terraform validate` passes; applying is human/agent-operated. Remaining approved
work: Phase 3 public testnet, still behind the roadmap security/legal gate.
Phase 3 (public testnet) has now been opened with a planning checkpoint only:
`docs/XRIQ_PHASE3_PUBLIC_TESTNET_PLAN.md` records the goal (a test-only public
network with no monetary value), the roadmap Phase 3 acceptance criteria, narrow
milestones (networked multi-node sync as the crux, then peer identity/discovery,
explicit testnet chain/genesis, a valueless faucet with abuse limits, public
explorer/wallet, monitoring/abuse controls, GCP multi-node topology, and testnet
reset/recovery drills), the hard scope boundaries, and the Phase 4 security/legal
gate. It builds on `docs/XRIQ_PHASE3_DECISIONS.md` (deterministic authority
consensus, allowlist peer admission) and stays subject to
`docs/XRIQ_LEGAL_RISK_REDUCTION.md`. The cheap guard is
`scripts/xriq_phase3_plan_check.py`. Important correction recorded: a DEX does
**not** lower legal requirements (the user asked); per the legal-risk doc and the
Treasury DeFi guidance, "decentralized" does not remove AML/CFT/sanctions
obligations, and a project-operated DEX is a separate high-risk regulated-product
review item explicitly out of Phase 3 scope. The recommended first Phase 3 code
milestone is networked multi-node sync. No tags, secrets, cloud resources, or
runtime behavior changed by this checkpoint.
Phase 3 milestone 1 (networked multi-node sync) has begun with increment 1 (the
validated sync core, no transport yet): `xriq-storage` gained a public peer-block
wire codec (`encode_peer_blocks`/`decode_peer_blocks`, tag `XPB1`) reusing the
canonical field encoding — the block hash is not sent, so a receiver recomputes
and fully validates it. `xriq-node` gained `XriqNode::export_peer_blocks(from_height,
limit)` (read-only) and `XriqNode::import_peer_blocks(bytes) -> PeerSyncOutcome`,
which decodes and imports each block through the existing full validation
(canonical roots, ledger execution, producer authority, test-only signatures),
skipping already-synced heights so a resend is idempotent. Proven by the test
`follower_syncs_multiple_blocks_from_peer_export` (a leader produces two blocks,
the follower imports the exported range and reaches the same tip/ledger, and a
re-import applies zero). Increment 2 then added the peer HTTP endpoint: a
`peer-blocks-export` node command (parses `--from-height`/`--limit`, exports the
validated block range as hex in JSON) served over the existing node HTTP server
at `GET /v1/peer/blocks?from_height=N&limit=M` (read-only), covered by the test
`node_runner_peer_blocks_export_serves_validated_blocks` (default limit 128, max
1024). Increment 3 then closed the loop with the follower pull client: a
`peer-sync` node command (`xriq-node peer-sync --chain-file <path> --peer
<http://host:port> [--limit N] [--max-rounds R] [--alice-balance B]`) built on a
minimal blocking HTTP GET (`peer_http_get`, http-only, connection-close) plus a
tolerant response parser (`parse_peer_blocks_response`). It loops: read the local
tip, `GET /v1/peer/blocks?from_height=tip+1&limit=N`, hex-decode, and
`import_peer_blocks` (each block re-validated before commit) into the file-backed
chain until a round applies zero (caught up) or `--max-rounds` is hit; it emits a
JSON summary (`applied`, `rounds`, `current_height`, `peer_current_height`). Two
tests cover it: `peer_sync_response_parser_reads_export_json` (parses the real
export JSON and rejects malformed bodies as `PeerSyncError`, not panics) and
`peer_sync_follower_pulls_blocks_from_leader_over_tcp` (a follower pulls a leader's
block over a real loopback socket into its own chain file, then a second pull
against the re-opened file applies zero — proving on-disk persistence and
idempotent convergence; a bad peer URL is a clean `PeerSyncError`). This makes two
real node processes stay in sync over TCP. Milestone 1 is functionally complete
(pull is the default and needs no push admission control).
Phase 3 milestone 2 (peer identity + discovery) has begun with increment 1: a
compatibility handshake and multi-peer follower resilience. Each node exposes a
read-only `peer-identity` command / `GET /v1/peer/identity` returning its network
(`xriq-devnet`), wire protocol (`xriq-peer-blocks-v1`), and current tip. `peer-sync`
now handshakes each peer before pulling and refuses a mismatched network/protocol
(`peer_compatibility_error`), and it accepts either `--peer <url>` (single, strict:
any failure is fatal) or `--peers-file <path>` (many: one `http://host:port` per
line, `#` comments allowed; unreachable/incompatible peers are skipped and reported
rather than failing the sync). The summary JSON now carries `peers_total`,
`peers_reachable`, aggregate `applied`, `current_height`, and a per-peer `peers[]`
array (`status: ok|skipped`, `applied`, `rounds`, or a skip `reason`); it errors
only if no peer was reachable. Covered by `peer_identity_endpoint_reports_network_and_protocol`
(endpoint shape + handshake accept + wrong-network/protocol reject),
`parse_peers_file_reads_urls_and_skips_comments` (parse + empty-file error), and
`peer_sync_from_peers_file_skips_unreachable_peer` (a follower with a dead peer
listed first still converges via the one reachable peer and records the skip). The
increment-3 loopback test was updated for the extra handshake connection.
Milestone 2 increment 2 then added peer discovery (peers learning peers). Each
node can advertise a configured peer set at a read-only `peer-peers` command /
`GET /v1/peer/peers` (fed by an optional `--peers-file` on `serve-readonly`/
`serve-private`, plumbed through `PrivateDevnetHttpServerConfig.peers_file`); the
response is a JSON `peers[]` array. `peer-sync` gained `--discover <max-peers>`:
one-hop discovery that queries each configured seed's advertised peers and merges
new `http://` entries (deduped, order-preserving, capped) into the working set
before syncing, and reports `peers_discovered` in the summary. Discovery makes the
run tolerant (advertised peers may be unreachable). Covered by
`parse_advertised_peers_extracts_urls`, `peer_peers_endpoint_advertises_configured_peers`
(advertises a file, and empty without one), and
`peer_sync_discovers_and_syncs_from_learned_peer` (a follower given only an empty
seed node A that advertises block-holder B learns B via discovery and syncs the
block from it: `peers_discovered=1`, `peers_reachable=2`, tip reached).
Milestone 2 increment 3 added stable per-node ids, completing the identity story.
A node derives a deterministic `node_id` (`xriqnode1` + 16 bytes of a
domain-separated SHA-256 of its `--node-seed`, via a new public
`xriq_crypto::digest`); it is reported (or `null`) in the `peer-identity` handshake
and plumbed through `PrivateDevnetHttpServerConfig.node_seed` +
`serve-readonly`/`serve-private --node-seed`. `peer-sync` gained `--node-seed`
(its own id) and, having refactored the per-peer step into a single handshake
(`handshake_peer`) followed by a pull (`pull_from_peer`), now **skips any peer that
reports the follower's own id as self** (never fatal, even in strict mode) — so
discovery looping back to a node's own address is harmless. The summary carries the
follower's own `node_id`, `peers_skipped_self`, and each synced peer's `node_id`.
Note this id is test-only: the seed is not a keypair and the id is self-reported,
not cryptographically proven (production identity needs real keys, a later phase).
Covered by `derive_node_id_is_stable_and_seed_specific`, the extended
`peer_identity_endpoint_reports_network_and_protocol` (null vs derived id), and
`peer_sync_skips_self_by_node_id` (a follower with a self-peer listed first skips it
and still syncs the block from the real leader: `peers_skipped_self=1`,
`peers_reachable=1`, tip reached). Milestone 2 (peer identity + discovery) is now
functionally complete.
Phase 3 milestone 3 (public testnet) has begun with increment 1: the canonical
testnet chain/genesis spec. `xriq_core::GenesisConfig::public_testnet()` defines a
fixed, reproducible genesis — `chain_id` `xriq-testnet` (distinct from the
`xriq-devnet` devnet), testnet policy limits (mempool 4096 / block 512), dedicated
authority/fee-sink addresses, and exactly one genesis allocation: a valueless
faucet account (`xriqdev1testnetfaucet00000000`, 1,000,000,000,000 base units) that
will seed the forthcoming faucet service. A new `xriq-node testnet-genesis` command
prints the spec as JSON with a reproducible `genesis_spec_hash` (SHA-256, via the
`xriq_crypto::digest` added in m2, over a domain-separated `xriq-genesis-spec:v1`
length-prefixed encoding of every parameter + each account). The golden hash is
`af01fa096c41538735cae46a6f9a7cb052bb198b1dd33316f905e46ec7ad1580`, pinned by a
node test (drift = a hard fork) and documented in `docs/XRIQ_TESTNET_CHAINSPEC.md`.
This defines the genesis only; it does not start a network. Everything stays
test-only with no monetary value (the chain spec and doc both carry the TEST-ONLY /
valueless framing).
Milestone 3 increment 2 added the valueless faucet. `xriq-node faucet-dispense
--chain-file <testnet-path> --to <address> [--amount N] [--max-balance N]` sends a
fixed drip (default 1000 base units) of valueless test units from the genesis
faucet account to a recipient as a normal signed transaction, confirmed in a
freshly produced block on the public_testnet genesis (its own chain file). Abuse
control is a chain-derived **balance cap** (default 10000): it refuses a recipient
already at/above the cap and refuses when the faucet cannot cover amount+fee — a
deterministic rate limit needing no side state (new `FaucetRefused` error → HTTP
429). It is deliberately NOT wired into the devnet-genesis HTTP server (that would
be semantically wrong); a genesis-parametrized testnet node — a later increment —
will expose the faucet + peer sync over HTTP with additional per-IP rate limiting.
Faucet policy constants live in xriq-core (`PUBLIC_TESTNET_FAUCET_DRIP_BASE_UNITS`,
`PUBLIC_TESTNET_FAUCET_MAX_BALANCE_BASE_UNITS`). Covered by two node tests
(multi-dispense with nonce increment + on-disk persistence across re-opens across
three blocks; and refusal both over the cap and when the requested amount exceeds
the faucet balance). `docs/XRIQ_TESTNET_CHAINSPEC.md` documents the faucet.
Milestone 3 increment 3 made the peer layer genesis-parametrized so real testnet
nodes can form a testnet and stay isolated from devnet. A `RunnerGenesis` selector
(Devnet(alice_balance) | Testnet) + `runner_genesis`/`runner_node`/`open_peer_node`
open a node on either genesis; peer commands (`peer-identity`, `peer-blocks-export`,
`peer-peers`, `peer-sync`) gained `--network devnet|testnet` (default devnet,
behavior unchanged). Each node now reports its **actual chain id** as its peer
`network` (devnet→`xriq-devnet`, testnet→`xriq-testnet`) instead of a hardcoded
constant, and `peer-sync` derives its own network from its genesis and rejects any
peer on a different network (`peer_compatibility_error` now takes the follower's own
network; protocol stays a constant). `PrivateDevnetHttpServerConfig` gained a
`testnet` flag (`--network testnet` on serve-readonly/serve-private) and the peer
routes pass `--network testnet` through, so a testnet-configured server serves its
peer endpoints on the testnet genesis (new `InvalidNetwork` error → 400). Covered by
two new tests: two testnet nodes syncing a faucet-produced block over real loopback
TCP (`network: xriq-testnet`, applied 1), and a devnet follower rejecting a testnet
peer; the identity test also asserts cross-network rejection. IMPORTANT SCOPE NOTE:
this increment parametrizes the PEER + faucet paths only; the ~44
`private_devnet_file_*` explorer/read helpers (status/blocks/accounts/snapshots)
remain devnet-genesis and get parametrized in a later increment, at which point a
full testnet node also exposes explorer routes + an HTTP faucet with per-IP limits.
Remaining for milestone 3: that read-route parametrization + HTTP faucet, and the
public explorer/wallet. Everything stays test-only with no monetary value.
The user provided a master engineering roadmap, recorded as
`docs/XRIQ_PRODUCTION_READINESS_ROADMAP.md` (v1.0): 19 engineering phases (core
blockchain/consensus/crypto, networking, storage, non-custodial wallet, RPC,
explorer, SDKs, AI-assisted security review + independent audit note, testing,
CI/CD, docs, DX, open-source, performance, reliability, monitoring, public
testnet with valueless test units, governance, exchange-readiness checklist),
plus a "things to avoid until much later" list (ICO/token sale/DEX/bridge/
custody/staking/etc.) and Principal-Engineer AI development rules. It is
explicitly conservative on legal posture and defers all legally-gated items
behind counsel review; it complements (does not override)
`docs/XRIQ_PRODUCTION_ROADMAP.md` and `docs/XRIQ_LEGAL_RISK_REDUCTION.md`.
A legal-counsel briefing was also prepared: `docs/XRIQ_LEGAL_COUNSEL_QUESTIONS.md`
gathers the project facts and the specific questions (entity/jurisdiction,
securities, commodities, money transmission, AML/CFT/sanctions, tax, DEX, custody,
tokenomics, privacy, public-testnet framing, consumer protection, data privacy,
open-source) to take to qualified counsel before any public/economic step. It is
not legal advice; it complements `docs/XRIQ_LEGAL_RISK_REDUCTION.md` and records
that the DEX-lowers-legal-risk belief needs counsel confirmation (the docs
suggest the opposite).
Gemini Code Assist Enterprise handoff prompts have been added for the next
cost-saving development phase:
`docs/GEMINI_CODE_ASSIST_XRIQ_PROMPT.md` for XRIQ production hardening and
`docs/GEMINI_CODE_ASSIST_BIBER_PROMPT.md` for BIBER MVP. The intended GitHub
backup branches for the pre-Gemini handoff state are
`backup/xriq-pre-gemini-20260614` and `backup/biber-pre-gemini-20260614`.
The BIBER team-share branch `share/biber-team-20260615` was created from
GitHub `main` at commit `f8a3e3e` so it can be shared with other team members
without disturbing the active `main` branch.
Use `docs/XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md` as the scope boundary for any
post-RC maintenance.
The Phase 1.4 RC candidate report is now
`docs/XRIQ_PHASE1_4_RC_CANDIDATE_REPORT.md`, and the cheap readiness/status
guard is `scripts/xriq_phase1_4_rc_readiness.py`. Do not move, delete,
recreate, or repush the Phase 1.4 RC tag unless the user explicitly asks for
that exact tag maintenance operation.
Phase 1.1 local/private end-to-end RC1 is also now tagged and pushed as
`phase1-1-xriq-local-e2e-rc1` at commit `6a38a51a`.
Do not include BIBER MVP, model training, repo-adaptation, runtime-profile, or
local-model platform work in Phase 1.1 percentage/status reporting unless the
user explicitly resumes BIBER work. The
Vast GPU was terminated after the important BIBER runtime artifacts were backed
up locally, so future sessions must not assume `/workspace`, vLLM, FastAPI, or
live Vast SSH access exists unless the user provides a fresh instance.

- Current focus:
  - Active focus as of 2026-06-09: XRIQ private-devnet prototype wrap-up is
    complete for the Codex/local non-production scope. Continue only a
    selected next scope: production hardening through GitHub Copilot, a narrow
    local/private Phase 1.5 gap, BIBER MVP/model work, or manual demo support.
  - Active handoff as of 2026-06-14: the user plans to use Gemini Code Assist
    Enterprise for XRIQ production and BIBER MVP work to save development cost,
    with Codex used only as an occasional monitor/reviewer between milestones.
    Use `docs/GEMINI_CODE_ASSIST_XRIQ_PROMPT.md` and
    `docs/GEMINI_CODE_ASSIST_BIBER_PROMPT.md` as the Gemini starting prompts.
  - Phase 2, after Phase 1: BIBER MVP/local model API, model registry, repo
    context, file-edit/test workflows, GitHub save/PR path, optional OpenAI
    mentor review, repo-adaptation eval/training loop, and Replit-replacement
    workflow improvements.
  - XRIQ private devnet: Rust-only private-devnet chain, replay startup, local
    runner/RPC tooling, wallet flow, explorer flow, and integration tests.
  - XRIQ Phase 1.1: add local/private PostgreSQL indexing, Rust API service
    contracts, React + TypeScript wallet/explorer/admin UI, and ISO 20022
    adapter mapping without public launch or compliance claims. Use
    `docs/XRIQ_GCP_RESOURCE_PLAN.md` before provisioning Google Cloud resources.
  - XRIQ Phase 1.2: local/private post-RC hardening only: mutation preflight
    contracts, explicit disabled-by-default gates, refusal-path tests, audit
    event expectations, and private-devnet-only action loops after their
    contracts are stable. The local block-production API path exists behind
    `--enable-local-block-production true`; wallet-send and block-production UI
    controls now exist only behind explicit Vite feature switches and matching
    local API flags. Default UI mutation controls remain disabled.
  - XRIQ Phase 1.3: local/private behavioral wallet testing only: define the
    canonical local behavior fixture, prove wallet send to pending, produce one
    local block, refresh wallet/explorer/mempool/Admin/audit views, and cover
    disabled/default and invalid-input negative paths without enabling wallet
    submit UI, custody, DEX, smart contracts, public network behavior, or
    production infrastructure.
  - XRIQ Phase 1.4: complete local/private signed-transfer work:
    fixtures, CLI-only test signed artifacts, default-disabled API
    signed-submit refusal/audit behavior, Rust-side verifier preview, and the
    approved accepted pending-file mutation behind
    `--enable-local-wallet-submit-signed true`, plus the Phase 1.4 RC
    candidate report, readiness/status guard, and approved/pushed RC tag
    `phase1-4-xriq-local-signed-submit-rc1`. Do not add wallet submit UI
    mutation, custody, browser-held key material, public network, DEX, bridge,
    smart-contract, production infrastructure, or tag maintenance without
    explicit approval.
- Delayed scope:
  - Public XRIQ remains part of the later project plan, but do not implement
    public token economics, DEX/liquidity, validator rewards, public governance,
    bridges, custody, listings, or launch-facing claims during this near-term
    phase.
  - Future XRIQ privacy should follow a Zcash-like selective-disclosure
    roadmap: optional shielded transfers, viewing keys, payment/audit
    disclosure, and crypto agility after review. Do not make Monero-style
    mandatory privacy or default opaque transfers part of the MVP or default
    public design while DEX usability and AML-friendly posture remain goals.
  - Keep `docs/XRIQ_LEGAL_RISK_REDUCTION.md` as a hard guardrail for any future
    public XRIQ work.

## Cost-Control Execution Policy

Future Codex sessions must default to a low-OpenAI-cost operating mode.

- Primary near-term budget target: try to finish Phase 1 XRIQ private-devnet
  with the smallest practical Codex usage by using local Rust/Cargo tests and
  narrow checkpoints. Do not spend Phase 1 budget on BIBER MVP expansion.
- Do not use Codex as the default bulk implementation engine. Use Codex for
  planning, risky architecture, small scoped patches, security-sensitive Rust
  review, failure diagnosis, integration glue, verification interpretation, and
  handoff updates.
- Use local scripts, ordinary deterministic tests, and, when a fresh GPU is
  available again, the user's Vast.ai GPU and local BIBER model for repetitive
  generation, long-running evals, QLoRA, dataset work, smoke loops, and batch
  validation.
- Actual model training/fine-tuning should run on the Vast GPU with local
  datasets, local scripts, local checkpoints, and local evals. Do not put
  OpenAI/Codex calls inside the training loop. OpenAI/Codex cost should come
  only from bounded engineering sessions and optional mentor/reviewer calls.
- Do not start broad exploratory rewrites, large refactors, public XRIQ work,
  BIBER MVP expansion, or extra model-training loops unless they directly
  unblock Phase 1 or the user explicitly approves the cost.
- Keep OpenAI mentor/reviewer calls optional and disabled by default. Use them
  only when the user requests mentor review or when quality/risk justifies it,
  such as cryptography boundaries, security design, eval design, legal-risk
  docs, or complex architecture decisions.
- Prefer the smallest valuable checkpoint: one narrow feature, one focused test
  addition, one doc checkpoint, or one deployment verification at a time.
- For docs-only updates, do not rerun expensive Rust/Vast verification; commit,
  push, and fast-forward Vast. For Rust/code changes, run focused local checks
  first, then Vast verification only after the local result is clean.
- If a future step looks likely to consume more than about `$50` of OpenAI/Codex
  usage or to require a long open-ended agent session, pause and give the user a
  cost/risk estimate before proceeding.

## Vast Shutdown / Resume Note

The Vast GPU can be shut down to save cost when the current task is XRIQ
private-devnet prototype work. XRIQ private-devnet is CPU/Rust software and does
not require GPU inference or training to continue.

- As of the latest 2026-05-25 local checkpoint, the Vast GPU should be treated
  as unavailable/terminated. Continue XRIQ private-devnet work locally from
  GitHub `main` and do not run Vast sync, vLLM, API, or training commands until
  the user provisions a new Vast instance or volume and provides connection
  details.
- Current source code is pushed to GitHub `main`; before the fresh-volume
  resume guide was added, local and Vast checkouts were clean at commit
  `3f254942 Document Vast shutdown resume path` on 2026-05-25. Future sessions
  should use the latest GitHub `main`, not a stale local `/workspace` copy.
- Future Codex resume prompt should start with: `Read docs/CODEX_HANDOFF.md and
  continue from the current GitHub main branch. Vast may be stopped; do not
  assume /workspace exists.`
- Primary resume file for Codex is this file: `docs/CODEX_HANDOFF.md`.
- Fresh GPU/volume resume file is `readme-resume-biber.md`.
- Fresh GPU/volume reinstantiate file for local artifact backups is
  `readme-reinstantiate.md`.
- Repo overview file is `README.md`.
- XRIQ private-devnet runbook is `xriq/README.md`.
- If the 500 GB Vast volume is kept, future sessions can reuse `/workspace`
  artifacts and adapters. If the instance/volume is destroyed, code is still
  safe in GitHub, but non-git runtime artifacts must be rebuilt, redownloaded,
  retrained, or restored from another artifact store, especially
  `/workspace/adapters`, `/workspace/outputs`, `/workspace/biber-logs`, and
  `/workspace/.hf_home`.
- Do not rotate credentials as part of shutdown/resume. Use existing GitHub/Vast
  auth paths unless the user explicitly asks to replace them.

## Project Status Metrics Baseline

Use this 2026-05-26 Phase 1 baseline for future percentage/status comparisons
unless the user changes the project scope again.

- Phase 1 goal: XRIQ private-devnet prototype only.
- Phase 1 estimated completion: `100%` for the approved private-devnet RC1
  scope.
- Rust workspace/crate structure: about `86%`.
- Core ledger/block/mempool/consensus/storage primitives: about `70%`.
- Wallet transfer draft/submit flow: about `87%`.
- File-backed node runner and deterministic replay: about `76%`.
- Snapshot export/import and restore workflow: about `80%`.
- Read-only/private RPC and explorer/dashboard support: about `76%`.
- Local smoke/regression coverage: about `100%` for the RC1 gate.
- Phase 1 release/readiness documentation: about `100%` for RC1.
- Production/public XRIQ, exchange readiness, audits, privacy protocol,
  validator economics, custody, liquidity, bridges, and mainnet launch are not
  part of Phase 1 and must not be counted in this percentage.
- Phase 2 goal, not counted in Phase 1: BIBER MVP and related model/platform
  work, including local-model runtime, repo-agent workflows, repo adaptation,
  model training, and OpenAI mentor orchestration.
- Phase 1.1 goal, starting after RC1: local/private XRIQ end-to-end prototype
  with Rust API/backend, PostgreSQL indexer, React + TypeScript wallet/explorer
  and admin UI, and ISO 20022 compatibility adapter.
- Phase 1.1 estimated completion: `100%` for the approved local/private RC1
  baseline tagged as `phase1-1-xriq-local-e2e-rc1`. Current Rust
  private-devnet foundation is real and tagged, but PostgreSQL indexing, React
  UI, exchange UI, and smart contracts are not
  fully implemented yet. Milestone A now has contract docs, a PostgreSQL
  read-model schema, JSON fixtures, and a local validation script. Milestone B
  now has the first deterministic Rust read-model indexer scaffold and local
  replay command plus idempotent SQL write-plan export and a dry-run local
  PostgreSQL apply path, optional local Postgres service, dry-run/live
  verification command, and an opt-in Docker-backed smoke path that can apply
  the generated SQL inside the local Compose Postgres container without host
  `psql`. The local Phase 1.1 smoke now exercises indexer replay,
  SQL write-plan generation, apply-postgres dry-run, and verify-postgres
  dry-run before API route checks by default. The first Rust product API service, route/render
  boundary, CLI smoke path, and local read-only socket wrapper now exist in
  `xriq/crates/xriq-api`, and `xriq-api request-postgres` plus explicitly
  configured `xriq-api serve-readonly` can read the local Docker Postgres read
  model for `/api/v1/admin/postgres/read-model-status` and
  `/api/v1/admin/node/status` and `/api/v1/admin/indexer/status`, and, when explicitly configured,
  Postgres-backed product data routes for
  `/api/v1/explorer/overview`, `/api/v1/blocks?limit=...`,
  `/api/v1/blocks/{height-or-hash}`,
  `/api/v1/transactions?limit=...`,
  `/api/v1/mempool?limit=...`, and
  `/api/v1/wallet/status`,
  `/api/v1/wallet/transfers/draft-preview?...`, and
  `/api/v1/iso20022/transactions/{tx_hash}/status`, and
  `/api/v1/iso20022/payment-initiation/preview?tx_hash=...`, and
  `/api/v1/iso20022/accounts/{address}/statement?from=...&to=...`, and
  `/api/v1/mempool?limit=...`, and
  `/api/v1/transactions/{tx_hash}`,
  `/api/v1/wallet/transactions/{tx_hash}/status` including confirmed and
  pending hashes,
  `/api/v1/accounts?limit=...`, and
  `/api/v1/accounts/{address}`, and
  `/api/v1/accounts/{address}/transactions?limit=...`, and
  `/api/v1/wallet/accounts?limit=...`, and
  `/api/v1/wallet/accounts/{address}/balance`, and
  `/api/v1/wallet/accounts/{address}/history?limit=...`, and
  `/api/v1/admin/audit-events?limit=...`, and
  `/api/v1/snapshots?limit=...`, and
  `/api/v1/snapshots/{snapshot_name}` without changing the default
  file-backed API path. The first ISO
  20022 compatibility adapter exists in `xriq/crates/xriq-iso20022`, but it is
  a private-devnet preview mapping layer only, not certification or payment
  network connectivity. `xriq-api` now exposes that adapter through GET-only
  payment-initiation, transaction-status, and account-statement preview routes.
  `xriq-api` now includes private-devnet wallet status,
  account list, balance, history, transaction status, and non-mutating
  draft-preview routes, including pending-file-aware wallet transaction status
  for durable pending hashes. The first React + TypeScript explorer UI shell exists
  in `xriq/apps/explorer-ui` and renders local product API health, totals,
  network metadata, blocks, confirmed transactions, pending transactions,
  snapshot catalog, audit events, accounts, and basic drill-down detail panels.
  The same app now includes a preview-only wallet transfer draft panel
  wired to the product wallet draft-preview API. It does not sign, submit,
  persist, or manage private keys. The same wallet shell now includes a
  read-only Wallet Activity panel that combines confirmed transaction rows from
  the product read model with pending rows from the durable mempool snapshot,
  and shows selected status, direction, counterparty, amount, fee, nonce,
  pending-block, and transaction-index detail without enabling submit/send.
  Selected wallet activity now also fetches the product wallet transaction-status
  API and shows API status, block height/hash, transaction index, and preview
  warning in the same read-only wallet panel. The same wallet shell now calls
  the product wallet account-history API and renders a read-only Wallet API
  History table for the selected local account.
  The same app now includes a read-only ISO
  20022 Preview panel backed by product API payment-initiation,
  transaction-status, and account-statement preview routes. The same app now
  includes a read-only Admin
  Status panel backed by product API network, indexer, wallet-status,
  node-status, pending-file mempool-status, pending wallet transaction-status,
  optional Postgres read-model status, snapshot-catalog, and audit-event
  routes. A local CPU-only Phase 1.1
  end-to-end smoke script now creates a confirmed transfer plus one durable
  pending transfer, checks contract/UI guardrails, verifies indexer replay and
  PostgreSQL dry-run artifacts, and verifies the product API routes that feed
  the explorer, wallet, mempool, snapshot, audit, admin, and ISO preview
  panels, including wallet account history and wallet draft-preview failure
  cases. Its explicit Docker live mode now also verifies the Admin UI Postgres
  status row mapping and the first Postgres-backed product
  node-status/indexer-status/overview/block-list/block-detail/transaction-list/mempool/wallet-status/wallet-draft-preview/transaction-detail/wallet-transaction-status/iso20022-transaction-status/iso20022-payment-initiation/iso20022-account-statement/account-list/wallet-account-list/account-detail/wallet-balance/account-history/wallet-account-history
  and audit-events/snapshot-list/snapshot-detail routes against the live local
  read model. The Phase 1.1 RC readiness checklist and route-parity matrix now
  live at `docs/XRIQ_PHASE1_1_RC_READINESS.md`, with a cheap static/latest-smoke
  guardrail at `scripts/xriq_phase1_1_rc_readiness.py --latest-summary`.
  The Phase 1.1 RC candidate report now lives at
  `docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md`; proposed tag
  `phase1-1-xriq-local-e2e-rc1` must not be created without explicit user
  approval naming that tag.
- Phase 1.2 estimated completion: `100%` for the approved local/private RC1
  baseline tagged as `phase1-2-xriq-local-private-hardening-rc1` at commit
  `b3a2fe4`, after the initial
  local/private scope plan, disabled wallet submit/send preflight fixtures,
  refusal-smoke guardrail, and API-level disabled/refused responses for wallet
  submit/send, React/client disabled-action guard coverage, and audit-event
  expectation fixtures plus API-local refusal audit records, admin audit
  visibility for future submit/send attempts, and disabled block-production
  preflight/audit fixtures plus the API-level disabled/refused response and
  audit visibility for block-production attempts, plus Admin UI/client disabled
  guard coverage for block production, plus the first pending-to-confirmed loop
  contract and Rust/API-side local block-production path behind explicit
  local/private-devnet enablement, plus the guarded local Rust/API
  wallet-submit-to-pending implementation behind
  `--enable-local-wallet-submit true` with local E2E smoke coverage, plus the
  matching TypeScript client accepted-response validator and Vite SSR client
  smoke for the accepted artifact, plus the guarded local Rust/API
  wallet-send-to-pending implementation behind `--enable-local-wallet-send true`
  with local E2E smoke coverage, plus the matching TypeScript client
  accepted-response validator and Vite SSR client smoke for the accepted
  artifact, plus the first standalone wallet-send lifecycle smoke proving the
  same guarded send transaction can be produced into a local block and read
  back as confirmed in both one-shot request mode and temporary
  `serve-readonly` HTTP mode, plus the first readiness-summary gate requiring
  refusal, accepted wallet-send, and lifecycle evidence before any UI
  mutation-control milestone is considered, plus a review-only UI
  mutation-control gate document and checker, plus the approved local
  wallet-send UI implementation behind
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`, using the shared API client and
  keeping wallet submit deferred, plus the first server-backed wallet-send UI
  live smoke against a temporary local/private `serve-readonly` API with only
  `--enable-local-wallet-send true` enabled, plus the first read-only wallet
  refresh smoke proving an accepted pending send appears through the existing
  snapshot/mempool/wallet-activity path, plus the approved local
  block-production UI implementation behind
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`, using the shared API
  client, keeping wallet submit deferred, keeping wallet send separate, and
  proving one pending transaction can be produced into exactly one local block
  through a temporary `serve-readonly` live smoke, plus a post-production Admin
  refresh smoke proving the same Admin Status row helper moves from height `1`
  with one pending transaction to height `2` with zero pending transactions,
  plus a no-pending negative block-production smoke proving HTTP `400`
  `no_pending_transactions` leaves Admin rows, network height, mempool count,
  and the pending file unchanged when there are no transactions to include,
  plus an updated readiness summary and UI mutation-control gate requiring the
  latest block-production UI live, Admin refresh, and no-pending negative
  evidence before any Phase 1.2 RC decision, plus a docs-only Phase 1.2 RC
  candidate report/checklist proposing a tag name but not creating it, plus a
  non-mutating Phase 1.2 RC readiness guardrail that verifies the candidate
  report, latest evidence summaries, referenced artifacts, doc references,
  optional clean-git/origin-main/tag-absent conditions before the explicitly
  approved RC tag action, and the approved Phase 1.2 RC1 tag itself.
  It is not a public launch phase. The approved Phase 1.2 RC1 scope is the
  local/private hardening baseline for local-only action contracts before broader
  UI mutation controls, snapshot-mutation, DEX, custody, public network
  behavior, or production infrastructure are implemented.
- Phase 1.3 estimated completion: `100%` after the initial local/private
  behavior plan, canonical behavior fixture/contract check, CPU-only
  request-mode wallet behavior smoke, and UI-backed shared TypeScript client
  behavior smoke, plus the cheap readiness/negative-matrix consolidation guard
  in `scripts/xriq_phase1_3_readiness_summary.py`, plus the local/private
  browser demo runbook and launcher, plus the docs-only
  `docs/XRIQ_PHASE1_3_RC_CANDIDATE_REPORT.md`, and the approved/pushed
  `phase1-3-xriq-local-private-behavior-rc1` tag at commit `345d353`.
  The next narrow step is post-RC/next-phase work only. Do not move, delete,
  recreate, or repush the Phase 1.3 tag unless the user explicitly requests
  that exact tag maintenance operation.
- Phase 1.4 estimated completion: `100%` for the local/private
  signed-transfer prototype RC1 after the signed-submit lifecycle smoke,
  RC-candidate report, readiness/status guard, and approved/pushed
  `phase1-4-xriq-local-signed-submit-rc1` tag. This percentage is for XRIQ
  private-devnet non-production Phase 1.4 only, not BIBER MVP or
  public/production XRIQ.
  Completed Phase 1.4 surfaces now include the signing plan, fixture inventory,
  CLI-only `xriq-wallet signed-transfer ...` test artifact, default-disabled
  signed-submit refusal/audit route, Rust-side verifier preview, non-mutating
  signed-submit request/parser adapter, and accepted local/private pending-file
  mutation behind `--enable-local-wallet-submit-signed true`, plus a CPU-only
  signed-submit lifecycle smoke proving signed artifact -> accepted submit ->
  pending status -> local block production -> confirmed wallet/explorer/
  mempool/Admin read-back.
  Remaining work is post-RC/next-phase selection only. Keep custody, public
  networks, DEX/bridge, smart contracts, asset issuance, production
  infrastructure, and tag maintenance out of scope until explicitly approved.
- XRIQ private-devnet wrap-up completion: `100%` for the Codex/local
  non-production private-devnet baseline through Phase 1.4. The consolidated
  wrap-up is `docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md`; the cheap guard is
  `scripts/xriq_private_devnet_wrapup_check.py`.
- Phase 1.1 Google Cloud resource stance: no GCP runtime resources are required
  for the current local contracts/indexer scaffold work. Prepare a
  project/region/budget plan, but delay paid Cloud SQL/Cloud Run/Artifact
  Registry resources until local contracts and indexer replay tests are stable.
- Remaining OpenAI/Codex key cost estimate for Phase 1 only, excluding Vast GPU,
  servers, production infrastructure, audits, public launch, and any BIBER MVP
  expansion:
  - Disciplined/minimal: about `$150-$350`.
  - Realistic working range: about `$350-$800`.
  - Deep Rust/debugging case: about `$800-$1,500`.

## Immediate Resume State

As of the latest 2026-06-07 checkpoint, the active work mode is local
workstation development for XRIQ Phase 1.3 local/private behavioral wallet
testing after the completed private-devnet RC1, Phase 1.1 local/e2e RC1, and
Phase 1.2 local/private hardening RC1 tags. The previous Vast deployment is not
an active target because the GPU was terminated to save cost.

- Latest native XRIQ Phase 1.2 local block-production API checkpoint:
  `xriq-api request` and `xriq-api serve-readonly` now parse
  `--enable-local-block-production true`, while the default path still returns
  the stable HTTP `403` `block_production_disabled` response. With the explicit
  local flag, `POST /api/v1/blocks/produce` accepts only a private-devnet
  request with `local_request_id`, `producer=xriqdev1author00000000000`,
  `max_transactions=4`, `timestamp_ms`, an optional `consensus_round`, and a
  local pending file. The accepted path appends exactly one local block from
  pending transactions, clears only confirmed pending hashes, and returns HTTP
  `201 Created` with `code: "block_production_accepted_local_only"`,
  `mutation: "chain_and_pending_state_local_only"`, block metadata,
  confirmed transaction rows, pending/chain state transition details, and an
  API-local accepted audit event. The contract fixture is now
  `implementation_status:
  "request-and-serve-readonly-explicit-local-flag"`. UI mutation controls remain
  disabled, wallet submit/send success remains disabled, and this still does
  not add custody, signing, DEX/smart contracts, snapshot mutation, public
  network behavior, or production infrastructure. Verification passed
  `cargo fmt`, `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo test -p xriq-api --lib -j 1`, bundled-Python `py_compile`,
  `scripts/xriq_phase1_1_contract_check.py`,
  `scripts/xriq_phase1_2_refusal_smoke.py`, and
  `scripts/xriq_phase1_1_local_e2e_smoke.py --skip-ui-check --artifact-dir xriq/target/xriq-phase1-2-local-block-production-smoke-20260601T0620Z`.
  The smoke writes
  `xriq/target/xriq-phase1-2-local-block-production-smoke-20260601T0620Z/api/block-production-accepted-local.json`
  and
  `xriq/target/xriq-phase1-2-local-block-production-smoke-20260601T0620Z/api/block-production-accepted-local-server.json`,
  then verifies both copied pending files are cleared while the original smoke
  pending file stays unchanged. It also verifies the enabled local server
  refreshes to height `2` and mempool count `0` after the POST. Superseded by
  the client accepted-response type checkpoint below.
- Latest native XRIQ Phase 1.2 client accepted-response type checkpoint:
  the React/TypeScript API layer now defines
  `LocalBlockProductionAcceptedResponse`,
  `LocalBlockProductionConfirmedTransaction`, accepted-code/audit-scope/mutation
  constants, and `validateLocalBlockProductionAcceptedContract()` in
  `xriq/apps/explorer-ui/src/api.ts`. This gives future UI or smoke tooling a
  typed contract for the already-implemented local block-production `201`
  response, including confirmed transactions, pending-state transition,
  chain-state transition, and API-local accepted audit metadata. The static UI
  guard in `xriq/apps/explorer-ui/scripts/check-static.mjs` now requires those
  accepted-response markers. This checkpoint intentionally does not add a UI
  POST function, does not add an enabled `Produce Block` control, and does not
  change the Admin UI default disabled guard behavior. Verification passed
  `npm.cmd run check` and escalated `npm.cmd run build` after the sandboxed
  build hit a Windows Vite/esbuild config access denial. Superseded by the
  wallet-submit accepted contract checkpoint below.
- Latest native XRIQ Phase 1.2 wallet-submit accepted contract checkpoint:
  added
  `xriq/fixtures/phase1_2/wallet-transfer-submit-to-pending-contract.json` as
  the guarded local shape for `POST /api/v1/wallet/transfers/submit` moving a
  validated local draft into the pending file. The fixture is now explicitly
  `status: "guarded-local-api-implemented"` and `implementation_status:
  "request-and-serve-explicit-local-flag"`, keeps the default path refused
  through
  `wallet-transfer-submit-disabled.json`, requires
  `--enable-local-wallet-submit`, local/private-devnet mode, audit events, and
  test identity scope, and forbids private keys, seed phrases, mnemonics,
  signatures, and signed transactions. The accepted response is documented as
  `code: "wallet_submit_accepted_local_only"`, `status: "pending"`, and
  `mutation: "pending_state_only"`, with a pending transaction row,
  pending-state transition, unchanged chain-state summary, and API-local
  accepted audit metadata. `scripts/xriq_phase1_1_contract_check.py` now
  validates this fixture and reports
  `phase1_2_wallet_submit_contract_fixtures: 1`. This checkpoint does not add
  signing/custody and does not enable UI submit/send controls. Verification
  passed bundled-Python `py_compile` and
  `scripts/xriq_phase1_1_contract_check.py`. Superseded by the wallet-submit
  client accepted-response type checkpoint below and the wallet-submit
  Rust/API checkpoint below.
- Latest native XRIQ Phase 1.2 wallet-submit client accepted-response type
  checkpoint: the React/TypeScript API layer now defines
  `LocalWalletSubmitAcceptedResponse`,
  `LocalWalletSubmitPendingTransaction`,
  `LocalWalletSubmitAcceptedExpectations`, `WALLET_SUBMIT_REFUSAL_ENDPOINT`,
  `LOCAL_WALLET_SUBMIT_ACCEPTED_CODE`,
  `LOCAL_WALLET_SUBMIT_ACCEPTED_MUTATION`, and
  `validateLocalWalletSubmitAcceptedContract()` in
  `xriq/apps/explorer-ui/src/api.ts`. This mirrors the guarded local
  `wallet-transfer-submit-to-pending-contract.json` shape for a local
  pending-state-only accepted submit response, including pending transaction,
  pending-state transition, unchanged chain-state summary, and accepted audit
  metadata. The static guard in
  `xriq/apps/explorer-ui/scripts/check-static.mjs` now requires those wallet
  submit accepted-response markers. This client-only checkpoint did not add a
  UI POST helper or enable wallet submit/send controls. Verification passed
  `npm.cmd run check` and escalated `npm.cmd run build` after the sandboxed
  build hit the known Windows Vite/esbuild config access denial. Superseded by
  the wallet-send accepted contract checkpoint below and the wallet-submit
  Rust/API checkpoint below.
- Latest native XRIQ Phase 1.2 wallet-send accepted contract checkpoint:
  added
  `xriq/fixtures/phase1_2/wallet-transfer-send-to-pending-contract.json` as
  the guarded local shape for `POST /api/v1/wallet/transfers/send` moving a
  validated local send request directly into the pending file. The fixture is
  now explicitly `status: "guarded-local-api-implemented"` and
  `implementation_status: "request-and-serve-explicit-local-flag"`, keeps the
  default path refused through `wallet-transfer-send-disabled.json`, requires
  `--enable-local-wallet-send`, local/private-devnet mode, audit events, and
  test identity scope, and forbids private keys, seed phrases, mnemonics,
  signatures, and signed transactions. Unlike the submit contract, `draft_id`
  is optional for send and the audit resource is the `local_request_id`. The
  accepted response is documented as
  `code: "wallet_send_accepted_local_only"`, `status: "pending"`, and
  `mutation: "pending_state_only"`, with a pending transaction row,
  pending-state transition, unchanged chain-state summary, and API-local
  accepted audit metadata. `scripts/xriq_phase1_1_contract_check.py` now
  validates both wallet pending contracts and reports
  `phase1_2_wallet_pending_contract_fixtures: 2` while preserving
  `phase1_2_wallet_submit_contract_fixtures: 1`. This checkpoint does not add
  signing/custody and does not enable UI submit/send controls. Verification
  passed bundled-Python `py_compile` and
  `scripts/xriq_phase1_1_contract_check.py`. Superseded by the wallet-send
  client accepted-response type checkpoint below and the wallet-send Rust/API
  checkpoint below.
- Latest native XRIQ Phase 1.2 wallet-send client accepted-response type
  checkpoint: the React/TypeScript API layer now defines
  `LocalWalletSendAcceptedResponse`, `LocalWalletSendPendingTransaction`,
  `LocalWalletSendAcceptedExpectations`, `WALLET_SEND_REFUSAL_ENDPOINT`,
  `LOCAL_WALLET_SEND_ACCEPTED_CODE`,
  `LOCAL_WALLET_SEND_ACCEPTED_MUTATION`, and
  `validateLocalWalletSendAcceptedContract()` in
  `xriq/apps/explorer-ui/src/api.ts`. This mirrors the guarded local
  `wallet-transfer-send-to-pending-contract.json` shape for a local
  pending-state-only accepted send response, including pending transaction,
  pending-state transition, unchanged chain-state summary, and accepted audit
  metadata keyed by `local_request_id` rather than `draft_id`. The static guard
  in `xriq/apps/explorer-ui/scripts/check-static.mjs` now requires those wallet
  send accepted-response markers. This client-only checkpoint did not add a UI
  POST helper or enable wallet submit/send controls. Verification passed
  `npm.cmd run check` and escalated `npm.cmd run build` after the sandboxed
  build hit the known Windows Vite/esbuild config access denial. Superseded by
  the wallet-submit Rust/API checkpoint below and the wallet-send Rust/API
  checkpoint below.
- Latest native XRIQ Phase 1.2 wallet-submit Rust/API checkpoint:
  `xriq-api request` and `xriq-api serve-readonly` now parse
  `--enable-local-wallet-submit true`, while the default
  `POST /api/v1/wallet/transfers/submit` path still returns the stable HTTP
  `403` `wallet_submit_disabled` response. With the explicit local flag, the
  accepted path requires local/private-devnet query fields including
  `local_request_id`, `draft_id`, `from_address`, `to_address`,
  `amount_base_units`, `fee_base_units`, `nonce`, and `expires_at_height`; it
  is limited to the configured private-devnet Alice test sender, rejects
  signing/custody material by never accepting those fields, appends exactly one
  transaction to the specified pending file, leaves the chain file unchanged,
  and returns HTTP `201 Created` with
  `code: "wallet_submit_accepted_local_only"`,
  `mutation: "pending_state_only"`, pending/chain state summaries, and
  accepted audit metadata. UI submit/send controls remain disabled. Verification
  passed `cargo fmt`,
  `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo test -p xriq-api --lib -j 1`, bundled-Python `py_compile`,
  `scripts/xriq_phase1_1_contract_check.py`,
  `scripts/xriq_phase1_2_refusal_smoke.py`, and
  `scripts/xriq_phase1_1_local_e2e_smoke.py --skip-ui-check --artifact-dir xriq/target/xriq-phase1-2-wallet-submit-smoke-20260606Tphase12c`.
  The smoke writes
  `xriq/target/xriq-phase1-2-wallet-submit-smoke-20260606Tphase12c/api/wallet-submit-accepted-local.json`.
  Superseded by the wallet-submit client smoke checkpoint below.
- Latest native XRIQ Phase 1.2 wallet-submit client smoke checkpoint:
  added
  `xriq/apps/explorer-ui/scripts/check-wallet-submit-accepted-contract.mjs`,
  which uses Vite SSR to import the real
  `validateLocalWalletSubmitAcceptedContract()` function from
  `xriq/apps/explorer-ui/src/api.ts`. The smoke validates the guarded
  `wallet-transfer-submit-to-pending-contract.json` example response and, when
  present, the latest local E2E artifact
  `api/wallet-submit-accepted-local.json`. `npm.cmd run check` now runs this
  smoke after `scripts/check-static.mjs`; it validated
  `xriq/target/xriq-phase1-2-wallet-submit-smoke-20260606Tphase12c/api/wallet-submit-accepted-local.json`.
  This checkpoint does not add a UI POST helper, does not enable wallet
  submit/send controls. Verification passed `npm.cmd run check`. Superseded by
  the wallet-send Rust/API checkpoint below.
- Latest native XRIQ Phase 1.2 wallet-send Rust/API checkpoint:
  `xriq-api request` and `xriq-api serve-readonly` now parse
  `--enable-local-wallet-send true`, while the default
  `POST /api/v1/wallet/transfers/send` path still returns the stable HTTP
  `403` `wallet_send_disabled` response. With the explicit local flag, the
  accepted path requires local/private-devnet query fields including
  `local_request_id`, `from_address`, `to_address`, `amount_base_units`,
  `fee_base_units`, `nonce`, and `expires_at_height`; it is limited to the
  configured private-devnet Alice test sender, appends exactly one transaction
  to the specified pending file, leaves the chain file unchanged, and returns
  HTTP `201 Created` with `code: "wallet_send_accepted_local_only"`,
  `mutation: "pending_state_only"`, pending/chain state summaries, and
  accepted audit metadata keyed by `local_request_id`. UI submit/send controls
  remain disabled. Verification passed `cargo fmt`,
  `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo test -p xriq-api --lib -j 1`, bundled-Python `py_compile`,
  `scripts/xriq_phase1_1_contract_check.py`,
  `scripts/xriq_phase1_2_refusal_smoke.py`, and
  `scripts/xriq_phase1_1_local_e2e_smoke.py --skip-ui-check --artifact-dir xriq/target/xriq-phase1-2-wallet-send-smoke-20260606Tphase12a`.
  The smoke writes
  `xriq/target/xriq-phase1-2-wallet-send-smoke-20260606Tphase12a/api/wallet-send-accepted-local.json`.
  Superseded by the wallet-send client smoke checkpoint below.
- Latest native XRIQ Phase 1.2 wallet-send client smoke checkpoint:
  added
  `xriq/apps/explorer-ui/scripts/check-wallet-send-accepted-contract.mjs`,
  which uses Vite SSR to import the real
  `validateLocalWalletSendAcceptedContract()` function from
  `xriq/apps/explorer-ui/src/api.ts`. The smoke validates the guarded
  `wallet-transfer-send-to-pending-contract.json` example response and, when
  present, the latest local E2E artifact
  `api/wallet-send-accepted-local.json`. `npm.cmd run check` now runs this
  smoke after the static and wallet-submit checks; it validated
  `xriq/target/xriq-phase1-2-wallet-send-smoke-20260606Tphase12a/api/wallet-send-accepted-local.json`.
  The client validator now explicitly enforces the wallet-send audit
  `resource_id` policy: `resource_id` remains the `local_request_id` marker,
  while `event_id` and metadata carry the concrete local request id. This
  checkpoint does not add a UI POST helper and does not enable wallet
  submit/send controls. Verification passed `npm.cmd run check`; escalated
  `npm.cmd run build` passed after the sandboxed build hit the known Windows
  Vite/esbuild config access denial.
- Latest native XRIQ Phase 1.2 wallet-send lifecycle smoke checkpoint:
  added `scripts/xriq_phase1_2_wallet_send_lifecycle_smoke.py`, a CPU-only
  local/private smoke that builds `xriq-node` and `xriq-api`, creates a fresh
  chain with one confirmed Alice-to-Bob transfer, calls guarded
  `POST /api/v1/wallet/transfers/send` with `--enable-local-wallet-send true`
  to append exactly one Alice-to-Carol pending transaction, calls guarded
  `POST /api/v1/blocks/produce` with `--enable-local-block-production true` to
  confirm that exact transaction in block height `2`, verifies
  `/api/v1/wallet/transactions/{tx_hash}/status` returns the same hash as
  confirmed, and verifies `/api/v1/mempool?limit=5` has `pending_count: 0`.
  The same smoke now also starts a temporary `xriq-api serve-readonly` process
  with explicit `--enable-local-wallet-send true` and
  `--enable-local-block-production true`, repeats wallet-send ->
  block-production -> confirmed-status over HTTP, verifies server network
  height `2`, verifies the server pending file is cleared, and stops the
  temporary process.
  The smoke does not enable UI submit/send controls, does not accept signing or
  custody material, and does not touch Docker, GCP, Vast, public network, DEX,
  smart-contract, bridge, custody, exchange-listing, or production
  infrastructure scope. `scripts/xriq_phase1_1_local_e2e_smoke.py`
  `start_api_readonly_server()` now has default-off
  `enable_local_wallet_submit` and `enable_local_wallet_send` parameters so
  server-mode lifecycle smokes can opt in without changing existing callers.
  Verification passed bundled-Python `py_compile`, bundled-Python
  `scripts/xriq_phase1_2_wallet_send_lifecycle_smoke.py --skip-build`, and
  bundled-Python `scripts/xriq_phase1_2_wallet_send_lifecycle_smoke.py`.
  Latest artifact:
  `xriq/target/xriq-phase1-2-wallet-send-lifecycle-smoke-20260606T213131Z/summary.json`.
- Latest native XRIQ Phase 1.2 readiness-summary checkpoint:
  `scripts/xriq_phase1_2_readiness_summary.py` is now a CPU-only local
  evidence gate that checks the latest Phase 1.2 refusal summary, accepted
  local wallet-send artifact, wallet-send lifecycle summary, block-production
  UI live summary, block-production Admin refresh summary, and
  block-production no-pending negative summary before any UI mutation-control
  milestone or Phase 1.2 RC decision is considered. It verifies the disabled
  fixture/audit guard set, the accepted wallet-send response and audit fields,
  absence of signing/custody field names, request-mode pending-to-confirmed
  evidence, temporary `serve-readonly` pending-to-confirmed evidence, required
  artifact file paths, empty mempool after block production, network height
  `2` after the local block is produced, Admin row refresh from height `1` to
  `2`, and the HTTP `400` `no_pending_transactions` path that leaves chain and
  pending state unchanged. The summary reports
  `ready_for_ui_mutation_design_review: true`,
  `block_production_evidence_required_for_rc: true`, and
  `block_production_evidence_current: true` while keeping
  `ui_mutation_controls_enabled: false`,
  `safe_to_enable_ui_mutation_controls: false`,
  `approval_required_before_ui_mutation_controls: true`,
  `ready_for_phase1_2_rc_decision: false`, and
  `phase1_2_rc_approval_required: true`.
  Verification passed bundled-Python `py_compile` and bundled-Python
  `scripts/xriq_phase1_2_readiness_summary.py`.
  Latest artifact:
  `xriq/target/xriq-phase1-2-readiness-summary-20260607T115109Z/summary.json`.
- Latest native XRIQ Phase 1.2 UI mutation-control gate checkpoint:
  `docs/XRIQ_PHASE1_2_UI_MUTATION_CONTROL_GATE.md` now records the user's
  explicit 2026-06-06 approval for local/private-devnet wallet-send UI behind
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true` and the user's explicit
  2026-06-07 approval for local/private-devnet block-production UI behind
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`, while keeping wallet
  submit deferred and all broader mutation scope out of this checkpoint.
  `scripts/xriq_phase1_2_ui_mutation_gate_check.py`, a CPU-only local checker
  validates the gate document, latest readiness summary, wallet UI source,
  Admin UI source, static UI guardrails, and shared accepted-response
  validators. The checker now requires the readiness summary to include
  current block-production UI live, Admin refresh, and no-pending negative
  evidence, `block_production_evidence_required_for_rc: true`, and
  `ready_for_phase1_2_rc_decision: false`. It verifies default UI mutation
  remains disabled, wallet-send and block-production require their feature
  switches, wallet submit remains deferred, UI mutation sources have no direct
  mutation endpoint strings or direct `fetch(`, and UI mutation sources have no
  browser persistence or sensitive signing/custody field names.
  Verification passed bundled-Python `py_compile` and bundled-Python
  `scripts/xriq_phase1_2_ui_mutation_gate_check.py`.
  Latest artifact:
  `xriq/target/xriq-phase1-2-ui-mutation-gate-check-20260607T115109Z/summary.json`.
- Latest native XRIQ Phase 1.2 wallet-send UI implementation checkpoint:
  `docs/XRIQ_PHASE1_2_WALLET_SEND_UI_IMPLEMENTATION_PLAN.md` now records the
  approved implementation. `xriq/apps/explorer-ui/src/api.ts` exposes
  `sendLocalWalletTransfer`, which posts through the shared API client to the
  local wallet-send path, expects HTTP `201`, and validates
  `wallet_send_accepted_local_only` with
  `validateLocalWalletSendAcceptedContract`. `xriq/apps/explorer-ui/src/wallet.tsx`
  renders `Local Wallet Send` behind
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`; the button is disabled by
  default, disabled on validation failures, and disabled while a send is in
  flight. The UI renders the local request id, audit event id, pending
  transaction hash, pending file marker, chain file marker, mutation, status,
  and chain unchanged state after an accepted send. Wallet submit remains
  disabled/deferred, and block production remains separate/explicit.
  `xriq/apps/explorer-ui/scripts/check-wallet-send-ui-control.mjs` is included
  in `npm run check` and verifies the feature switch, shared API client usage,
  wallet-submit deferral, no direct wallet UI `fetch(`, no direct submit/send
  endpoint strings in wallet UI source, no browser persistence markers, and no
  sensitive signing/custody field names.
  `scripts/xriq_phase1_2_wallet_send_ui_plan_check.py` validates the docs,
  source markers, latest gate summary, and implementation constraints.
  Verification passed bundled-Python `py_compile` and bundled-Python
  `scripts/xriq_phase1_2_wallet_send_ui_plan_check.py`, `npm.cmd run check`,
  and escalated `npm.cmd run build` after the sandboxed build hit the known
  Windows Vite/esbuild config access denial.
  Latest artifact:
  `xriq/target/xriq-phase1-2-wallet-send-ui-plan-check-20260607T105541Z/summary.json`.
- Latest native XRIQ Phase 1.2 wallet-send UI live smoke checkpoint:
  added `xriq/apps/explorer-ui/scripts/check-wallet-send-ui-live.mjs`, which
  uses Vite SSR to import the real `sendLocalWalletTransfer` helper from
  `xriq/apps/explorer-ui/src/api.ts`, requires
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`, and calls a live
  local/private `xriq-api serve-readonly` endpoint. Added
  `scripts/xriq_phase1_2_wallet_send_ui_live_smoke.py`, a CPU-only local
  orchestrator that builds `xriq-node`/`xriq-api`, creates a fresh temporary
  private-devnet chain, starts `serve-readonly` with
  `--enable-local-wallet-send true` only, runs
  `npm.cmd run check:wallet-send-ui-live`, verifies exactly one accepted
  pending wallet-send response through the shared UI client, verifies the
  pending file contains the accepted transaction, verifies chain height remains
  `1`, verifies wallet submit still returns the disabled/refused response
  without `--enable-local-wallet-submit`, and verifies block production still
  returns the disabled/refused response without
  `--enable-local-block-production`. The smoke does not enable wallet submit,
  does not produce a block, does not accept signing/custody material, and does
  not touch Docker, GCP, Vast, public network, DEX, smart-contract, custody,
  bridge, exchange-listing, or production infrastructure scope.
  Verification passed bundled-Python `py_compile`, `npm.cmd run check`,
  bundled-Python
  `scripts/xriq_phase1_2_wallet_send_ui_live_smoke.py --skip-build`, and
  bundled-Python `scripts/xriq_phase1_2_wallet_send_ui_live_smoke.py`.
  Latest artifact:
  `xriq/target/xriq-phase1-2-wallet-send-ui-live-smoke-20260606T232950Z/summary.json`.
- Latest native XRIQ Phase 1.2 wallet-send read-only refresh smoke checkpoint:
  `xriq/apps/explorer-ui/src/wallet.tsx` now exports the existing pure
  `walletActivityRows` helper so smoke tooling can validate the same read-only
  wallet activity shaping used by the UI. Added
  `xriq/apps/explorer-ui/scripts/check-wallet-send-refresh-live.mjs`, which
  uses Vite SSR to call the real `sendLocalWalletTransfer`, reloads
  `loadExplorerSnapshot`, checks the accepted transaction in the snapshot
  mempool, checks `loadWalletTransactionStatus` still reports it as pending,
  and checks `walletActivityRows` renders the pending row for both the sender
  and recipient. Added `scripts/xriq_phase1_2_wallet_send_refresh_smoke.py`,
  a CPU-only local orchestrator that creates a fresh temporary private-devnet
  chain, starts `serve-readonly` with `--enable-local-wallet-send true` only,
  runs `npm.cmd run check:wallet-send-refresh-live`, verifies wallet submit
  still refuses without `--enable-local-wallet-submit`, and verifies block
  production still refuses without `--enable-local-block-production`. This is
  read-only refresh evidence after one accepted wallet-send; it does not add
  wallet submit, does not produce a block, does not accept signing/custody
  material, and does not touch Docker, GCP, Vast, public network, DEX,
  smart-contract, custody, bridge, exchange-listing, or production
  infrastructure scope.
  Verification passed bundled-Python `py_compile`, `node --check`,
  `npm.cmd run check`, bundled-Python
  `scripts/xriq_phase1_2_wallet_send_refresh_smoke.py --skip-build`, and
  bundled-Python `scripts/xriq_phase1_2_wallet_send_refresh_smoke.py`.
  Latest artifact:
  `xriq/target/xriq-phase1-2-wallet-send-refresh-smoke-20260607T005924Z/summary.json`.
- Latest native XRIQ Phase 1.2 block-production UI design checkpoint:
  `docs/XRIQ_PHASE1_2_BLOCK_PRODUCTION_UI_DESIGN.md` now records the approved
  implementation of a local/private-devnet block-production UI mutation
  control behind `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`. The API
  client exposes `produceLocalBlock`, which posts through the shared API layer,
  expects HTTP `201`, and validates `block_production_accepted_local_only`
  with `validateLocalBlockProductionAcceptedContract`. The Admin UI renders
  `Local Block Production`; the button is disabled by default, disabled unless
  the feature switch is on, disabled when no pending transaction exists, and
  disabled while production is in flight. It renders local request/audit
  metadata plus produced block height/hash, confirmed transaction count and
  hashes, pending before/after counts, and chain previous/current height. The
  disabled `Produce Block` refusal guard remains available separately. Wallet
  send remains separate and explicit; wallet submit remains deferred. The
  checker now verifies the implementation markers, docs, latest wallet-send
  refresh evidence, latest block-production UI live evidence, latest Admin
  refresh evidence, latest no-pending negative evidence, no direct Admin
  `fetch(`, no hard-coded block-production endpoint path in Admin UI source, no
  browser persistence markers, and no sensitive signing/custody field names.
  Latest design-check artifact:
  `xriq/target/xriq-phase1-2-block-production-ui-design-check-20260607T115109Z/summary.json`.
- Latest native XRIQ Phase 1.2 block-production UI live smoke checkpoint:
  added `xriq/apps/explorer-ui/scripts/check-block-production-ui-control.mjs`,
  `xriq/apps/explorer-ui/scripts/check-block-production-ui-live.mjs`, and
  `scripts/xriq_phase1_2_block_production_ui_live_smoke.py`. The static control
  check is now part of `npm run check`. The live smoke creates a fresh
  temporary private-devnet chain, starts `xriq-api serve-readonly` with
  `--enable-local-wallet-send true` and `--enable-local-block-production true`
  while leaving wallet submit disabled, sets
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`, creates one pending
  wallet-send transaction through the shared client, produces exactly one local
  block through `produceLocalBlock`, verifies the pending file is cleared,
  verifies network height advances from `1` to `2`, verifies the wallet
  transaction becomes confirmed, and verifies wallet submit still returns the
  disabled/refused response without `--enable-local-wallet-submit`. Verification
  passed bundled-Python `py_compile`, `node --check`,
  `npm.cmd run check`, bundled-Python
  `scripts/xriq_phase1_2_block_production_ui_live_smoke.py --skip-build`, and
  bundled-Python `scripts/xriq_phase1_2_block_production_ui_live_smoke.py`.
  Latest artifact:
  `xriq/target/xriq-phase1-2-block-production-ui-live-smoke-20260607T105329Z/summary.json`.
- Latest native XRIQ Phase 1.2 block-production Admin refresh smoke checkpoint:
  `xriq/apps/explorer-ui/src/admin.tsx` now exports `adminSnapshotRows` and uses
  that same helper to render the Admin Status `Node`, `Network`, `Wallet`, and
  `Mempool` row groups. Added
  `xriq/apps/explorer-ui/scripts/check-block-production-admin-refresh-live.mjs`
  and `scripts/xriq_phase1_2_block_production_admin_refresh_smoke.py`. The
  smoke starts a temporary local/private `serve-readonly` API with
  `--enable-local-wallet-send true` and `--enable-local-block-production true`
  while leaving wallet submit disabled, sets
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`, creates one pending
  wallet-send transaction, verifies Admin rows show height `1` and one pending
  transaction, produces exactly one local block, verifies Admin rows show height
  `2` and zero pending transactions, verifies the confirmed wallet transaction
  status, and verifies wallet submit still returns the disabled/refused response
  without `--enable-local-wallet-submit`. The Admin read-only status labels for
  wallet send and block production remain disabled labels; the explicit local
  action is controlled by the feature switch and API flag. Verification passed
  bundled-Python `py_compile`, `node --check`, `npm.cmd run check`,
  bundled-Python
  `scripts/xriq_phase1_2_block_production_admin_refresh_smoke.py --skip-build`,
  and bundled-Python
  `scripts/xriq_phase1_2_block_production_admin_refresh_smoke.py`.
  Latest artifact:
  `xriq/target/xriq-phase1-2-block-production-admin-refresh-smoke-20260607T110810Z/summary.json`.
- Latest native XRIQ Phase 1.2 block-production no-pending negative smoke checkpoint:
  `xriq/apps/explorer-ui/src/api.ts` now exposes
  `produceLocalBlockNoPendingRefusal` and
  `validateLocalBlockProductionNoPendingContract` for the stable HTTP `400`
  `no_pending_transactions` response. Added
  `xriq/apps/explorer-ui/scripts/check-block-production-no-pending-live.mjs`
  and `scripts/xriq_phase1_2_block_production_no_pending_smoke.py`. The smoke
  starts a temporary local/private `serve-readonly` API with
  `--enable-local-block-production true`, an empty pending file, wallet send
  disabled, and wallet submit disabled, sets
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`, verifies Admin rows stay
  at height `1` with zero pending transactions before and after the shared
  client refusal helper, verifies the direct API refusal returns
  `no_pending_transactions`, and verifies network height, mempool count, and
  pending-file contents remain unchanged. Verification passed `node --check`,
  bundled-Python `py_compile`, `npm.cmd run check`, bundled-Python
  `scripts/xriq_phase1_2_block_production_no_pending_smoke.py --skip-build`,
  and bundled-Python
  `scripts/xriq_phase1_2_block_production_no_pending_smoke.py`. The sandboxed
  `npm.cmd run build` hit the known Vite/esbuild access-denied path; rerunning
  the same command with approved escalation passed.
  Latest artifact:
  `xriq/target/xriq-phase1-2-block-production-no-pending-smoke-20260607T112046Z/summary.json`.
- Latest native XRIQ Phase 1.2 RC candidate report checkpoint:
  added `docs/XRIQ_PHASE1_2_RC_CANDIDATE_REPORT.md` as the docs-only candidate
  report/checklist for the local/private hardening scope. The report proposes
  `phase1-2-xriq-local-private-hardening-rc1`, references the latest readiness
  summary, UI mutation gate, block-production UI design check, wallet-send
  lifecycle/UI/refresh evidence, block-production UI live evidence, Admin
  refresh evidence, and no-pending negative evidence, and keeps public mainnet,
  DEX/liquidity, bridges, custody, smart contracts, wallet-submit UI mutation,
  snapshot mutation, production infrastructure, ISO certification, and market
  claims out of scope. No tag was created, moved, or pushed by that report
  checkpoint; the tag was created later only after exact explicit user
  approval.
- Latest native XRIQ Phase 1.2 RC1 tag checkpoint: after exact explicit user
  approval on 2026-06-07, ran
  `python scripts/xriq_phase1_2_rc_readiness.py --require-clean-git --require-origin-main --require-tag-absent --write-summary`,
  which passed with clean Git, `HEAD == origin/main`, selected evidence matching
  the candidate report, and local/remote tag absence. Then created and pushed
  `phase1-2-xriq-local-private-hardening-rc1` at commit `b3a2fe4`. Do not
  move, delete, recreate, or repush this tag unless the user explicitly asks
  for that exact tag maintenance operation.
- Latest native XRIQ Phase 1.3 planning checkpoint: added
  `docs/XRIQ_PHASE1_3_LOCAL_PRIVATE_BEHAVIOR_PLAN.md` as the post-Phase 1.2 RC1
  local/private behavior plan. The plan keeps Phase 1.3 scoped to behavioral
  wallet testing only: local wallet send, one local block production, read-model
  refresh checks, Admin/audit visibility, disabled/default negative paths, and
  invalid-input refusal checks. It reuses only the accepted Phase 1.2 local
  switches (`--enable-local-wallet-send true`,
  `--enable-local-block-production true`,
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`, and
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`) and keeps wallet submit UI,
  snapshot import/export mutation, DEX/liquidity, smart contracts, custody,
  public network behavior, production infrastructure, and exchange/listing
  claims out of scope.
- Latest native XRIQ Phase 1.3 behavior fixture checkpoint: added
  `xriq/fixtures/phase1_3/local-wallet-behavior-v1.json` and
  `scripts/xriq_phase1_3_behavior_contract_check.py`. The fixture defines the
  canonical local/private behavior loop: prepare a base private-devnet chain
  with Alice sending `25` plus fee `2` to Bob, then run guarded wallet send from
  Alice to Carol for `5` plus fee `2`, then produce exactly one local block and
  verify pending cleanup, height `2`, wallet status, explorer/admin/audit
  expectations, and disabled/default negative cases. The checker validates the
  approved local switches, Phase 1.2 RC1 tag reference, no-go scope markers,
  identities, balances/nonces (`Alice=66/nonce=2`, `Bob=25`, `Carol=5`,
  fee sink `4`), expected audit actions, negative matrix, artifact policy, and
  absence of sensitive key field names. This checkpoint is fixture/checker only:
  it does not mutate chain state, start a server, run Docker, provision GCP/Vast,
  create tags, or enable wallet submit UI, DEX, smart contracts, custody, public
  network behavior, or production infrastructure. Verification passed bundled
  Python `py_compile`, bundled Python
  `scripts/xriq_phase1_3_behavior_contract_check.py`, and `git diff --check`.
  Latest artifact:
  `xriq/target/xriq-phase1-3-behavior-contract-check-20260607T130905Z/summary.json`.
- Latest native XRIQ Phase 1.3 CPU-only wallet behavior smoke checkpoint: added
  `scripts/xriq_phase1_3_wallet_behavior_smoke.py`. The smoke validates the
  Phase 1.3 fixture, uses existing local `xriq-node` and `xriq-api` debug
  binaries in request mode, creates a temporary base chain, runs guarded wallet
  send with `--enable-local-wallet-send true`, verifies pending wallet status,
  runs guarded block production with `--enable-local-block-production true`,
  verifies confirmed wallet status, empty mempool, network height, explorer
  overview, wallet balances/history for Alice/Bob/Carol/fee sink, Admin indexed
  and refusal audit visibility, and the negative matrix for default wallet send,
  default block production, deferred wallet submit, no-pending block production,
  and invalid wallet send. It starts no browser or server, uses no Docker,
  GCP, Vast, GPU, public/DEX behavior, custody, smart contracts, production
  infrastructure, or tag operation. Verification passed bundled Python
  `py_compile`, bundled Python
  `scripts/xriq_phase1_3_behavior_contract_check.py`, bundled Python
  `scripts/xriq_phase1_3_wallet_behavior_smoke.py --skip-build`, and
  `git diff --check`. Latest artifact:
  `xriq/target/xriq-phase1-3-wallet-behavior-smoke-20260607T131636Z/summary.json`.
- Latest native XRIQ Phase 1.3 UI-backed wallet behavior smoke checkpoint:
  added `xriq/apps/explorer-ui/scripts/check-phase1-3-wallet-behavior-live.mjs`,
  the npm script `check:phase1-3-wallet-behavior-live`, and
  `scripts/xriq_phase1_3_wallet_behavior_ui_smoke.py`. The wrapper validates
  the Phase 1.3 fixture, creates a temporary base chain, starts a local
  `serve-readonly` API with only `--enable-local-wallet-send true` and
  `--enable-local-block-production true`, sets only
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true` and
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`, then runs the shared
  TypeScript client flow through Vite SSR. The smoke verifies wallet-submit
  refusal, wallet send to pending, wallet/Admin pending rows before block
  production, one local block production, confirmed wallet status, wallet/Admin
  rows after block production, final balances/history for Alice/Bob/Carol/fee
  sink, and no-pending block-production refusal with state unchanged. It scans
  wallet/Admin UI sources for direct mutation `fetch(` calls, browser
  persistence, and sensitive signing/custody markers. It starts no browser,
  Docker, GCP, Vast, GPU, public/DEX behavior, custody, smart contracts,
  production infrastructure, or tag operation. Verification passed bundled
  Python `py_compile`, Node `--check`, bundled Python
  `scripts/xriq_phase1_3_behavior_contract_check.py --artifact-dir xriq/target/xriq-phase1-3-behavior-contract-check-ui-smoke-final2`,
  `npm.cmd run check` in `xriq/apps/explorer-ui`, bundled Python
  `scripts/xriq_phase1_3_wallet_behavior_ui_smoke.py --skip-build`, and
  `git diff --check`. The UI smoke wrote latest artifact:
  `xriq/target/xriq-phase1-3-wallet-behavior-ui-smoke-20260607T132901Z/summary.json`.
- Latest native XRIQ Phase 1.3 readiness/negative-matrix checkpoint: added
  `scripts/xriq_phase1_3_readiness_summary.py` as a CPU-only, non-mutating
  consolidation guard. It validates the Phase 1.3 fixture contract summary,
  CPU request-mode wallet behavior smoke, UI-backed shared-client behavior
  smoke, wallet/Admin refresh evidence, final balances/history, all five
  negative matrix cases (`default_wallet_send_disabled`,
  `default_block_production_disabled`, `wallet_submit_ui_deferred`,
  `no_pending_block_production`, and `invalid_wallet_send_request`), docs
  references, and no sensitive signing/custody field names. It reports
  `behavioral_readiness_ok: true`,
  `ready_for_phase1_3_candidate_report: true`, and
  `ready_to_create_tag_now: false`; a future tag would need exact explicit
  approval for `phase1-3-xriq-local-private-behavior-rc1`, and generic continue
  is not approval. Verification passed bundled Python `py_compile` and bundled
  Python
  `scripts/xriq_phase1_3_readiness_summary.py --cpu-smoke-summary xriq/target/xriq-phase1-3-wallet-behavior-smoke-20260607T131636Z/summary.json`.
  Latest artifact:
  `xriq/target/xriq-phase1-3-readiness-summary-20260607T134243Z/summary.json`.
- Latest native XRIQ Phase 1.3 browser demo checkpoint: added
  `docs/XRIQ_PHASE1_3_DEMO_RUNBOOK.md` and
  `scripts/xriq_phase1_3_demo_launcher.py`. The launcher has a safe default
  prepare-only mode that creates deterministic demo chain/pending files plus
  `demo-context.json`, `summary.json`, `demo-commands.ps1`, and
  `demo-commands.sh`; `--smoke-only` starts the local API/UI, verifies both
  respond, then stops; `--launch` keeps both local servers open until Ctrl+C.
  The demo uses the Phase 1.3 fixture, starts `xriq-api serve-readonly` with
  only `--enable-local-wallet-send true` and
  `--enable-local-block-production true`, starts Vite with only
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true` and
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`, and walks the user through
  Alice-to-Carol local send, pending state, one local block production, refresh,
  and confirmed wallet/Admin/mempool state. It remains local/private only and
  excludes private keys, seed phrases, signing, custody, public mainnet, DEX,
  smart contracts, GCP, Vast, Docker, production infrastructure, and tags.
  Verification passed bundled Python `py_compile`, prepare-only launcher run,
  and escalated bundled Python
  `scripts/xriq_phase1_3_demo_launcher.py --skip-build --smoke-only --auto-port`
  because the managed Codex sandbox blocked Vite config reads without
  escalation. Latest smoke artifact:
  `xriq/target/xriq-phase1-3-demo-20260607T135028Z/summary.json`.
- Latest native XRIQ Phase 1.3 RC candidate report checkpoint: added
  `docs/XRIQ_PHASE1_3_RC_CANDIDATE_REPORT.md` as a docs-only candidate report
  for `phase1-3-xriq-local-private-behavior-rc1`. The report references the
  latest readiness summary,
  `xriq/target/xriq-phase1-3-readiness-summary-20260608T135807Z/summary.json`,
  required contract/CPU/UI/demo evidence, the manual demo command, explicit
  non-production boundaries, and the exact approval phrase:
  `I explicitly approve creating and pushing the Phase 1.3 RC tag phase1-3-xriq-local-private-behavior-rc1.`
  At that candidate-report checkpoint, no tag was created. The tag was created
  later only after exact explicit user approval.
- Latest native XRIQ Phase 1.3 RC tag checkpoint: after exact explicit user
  approval on 2026-06-08, reran
  `scripts/xriq_phase1_3_readiness_summary.py --cpu-smoke-summary xriq/target/xriq-phase1-3-wallet-behavior-smoke-20260607T131636Z/summary.json --require-clean-git --require-origin-main`;
  it passed with `clean_git: true` and `head_matches_origin_main: true`.
  Verified the local and remote tag were absent, then created and pushed
  `phase1-3-xriq-local-private-behavior-rc1` at commit `345d353`. Do not move,
  delete, recreate, or repush this tag without an exact tag-maintenance request.
- Latest native XRIQ Phase 1.4 planning checkpoint: added
  `docs/XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md` and
  `scripts/xriq_phase1_4_plan_check.py`. The plan starts after
  `phase1-3-xriq-local-private-behavior-rc1` and defines a local/private
  signed-transfer path: signed intent/envelope fixtures, CLI-only test signing,
  API signed-submit verifier, local signed-send smoke, and UI design review
  before any UI mutation. It explicitly prohibits production key management,
  browser-held private keys, seed phrases, mnemonics, raw signatures, custody,
  public networking, DEX, bridges, smart contracts, asset issuance, production
  infrastructure, and tag actions without explicit approval.
- Latest native XRIQ Phase 1.4 signed-transfer contract inventory checkpoint:
  added `xriq/fixtures/phase1_4/local-signing-intent.json`,
  `test-only-signed-transfer-envelope.json`, `signed-submit-disabled.json`,
  `signed-submit-invalid-signature.json`, and
  `signed-submit-accepted-contract.json`, plus
  `scripts/xriq_phase1_4_contract_check.py`. The fixtures define the next
  local/private signed-transfer shape before implementation: signing intent,
  test-only envelope, disabled default refusal, invalid-signature refusal, and
  accepted signed-submit response contract behind
  `--enable-local-wallet-submit-signed`. At that fixture checkpoint, this was
  contract inventory only: the API refusal route did not exist yet, and there
  was no wallet submit UI mutation, browser key generation/storage,
  custody/hosted signing, public network, DEX, bridge, smart contracts, asset
  issuance, production infrastructure, or tag operation.
- Latest native XRIQ Phase 1.4 CLI-only signed artifact checkpoint: added
  `xriq-wallet signed-transfer --chain-id ... --from ... --to ... --amount ...
  --fee ... --nonce ... --signer-label <lowercase-label> [--format text|json]`
  plus `scripts/xriq_phase1_4_signed_artifact_check.py`. The signer label must
  resolve to the sender test identity. The artifact renders
  `xriq-local-signed-transfer-envelope-v1`, transaction signing hash,
  transaction hash, test-only signature algorithm metadata, and signed-submit
  preview metadata. It deliberately does not expose private keys, seed phrases,
  mnemonics, raw test signature bytes, custody accounts, browser storage,
  public network endpoints, DEX routing, production infrastructure, or tags.
  At that CLI-only checkpoint, no API/UI signed-submit implementation was
  added.
- Latest native XRIQ Phase 1.4 API signed-submit refusal checkpoint: added the
  default-disabled product/API route
  `POST /api/v1/wallet/transfers/submit-signed`. It returns
  `403 signed_submit_disabled`, advertises future explicit local enablement via
  `--enable-local-wallet-submit-signed`, records/exposes
  `wallet-transfer-signed-submit:local_request_id` in the local refusal audit
  catalog, and leaves pending state and chain state unchanged. The refusal
  response lists signed-envelope verifier metadata fields but does not accept
  key material, raw signatures, custody material, browser storage, public
  network behavior, DEX/bridge/smart-contract scope, production infrastructure,
  or tags. The route has no accepted verifier implementation yet.
- Latest native XRIQ Phase 1.4 signed-submit refusal smoke checkpoint: aligned
  `xriq/fixtures/phase1_4/signed-submit-disabled.json` with the live
  refusal/audit response and added
  `scripts/xriq_phase1_4_signed_submit_refusal_smoke.py`. The smoke builds
  `xriq-node` and `xriq-api`, creates a temporary local/private base chain,
  calls `POST /api/v1/wallet/transfers/submit-signed` in default mode with the
  Phase 1.4 fixture hashes, verifies HTTP `403 signed_submit_disabled`,
  verifies the signed-submit local refusal audit event, writes timestamped
  artifacts under `xriq/target/`, and confirms no pending file is created. It
  does not add accepted signed-submit mutation, UI mutation, custody,
  browser-held key material, public network, DEX/bridge/smart-contract scope,
  production infrastructure, or tags. Latest verified artifact:
  `xriq/target/xriq-phase1-4-signed-submit-refusal-smoke-20260608T185808Z/summary.json`
  with `pending_file_created: false`.
- Latest native XRIQ Phase 1.4 signed-submit negative-contract checkpoint:
  added `xriq/fixtures/phase1_4/signed-submit-negative-cases.json` and wired
  it into `scripts/xriq_phase1_4_contract_check.py`. This is a
  parse/verify-only contract matrix for the future verifier, not an accepted
  mutation implementation. Required cases include malformed envelope missing
  `format_version`, malformed envelope missing hashes, unsupported signature
  algorithm, wrong chain id, signing-hash mismatch, transaction-hash mismatch,
  invalid test signature, stale nonce, expired transaction, and duplicate
  pending transaction. Every case requires `mutation: none`, unchanged chain
  state, unchanged pending state, and local API audit visibility. No accepted
  signed-submit mutation, UI mutation, custody, browser-held key material,
  public network, DEX/bridge/smart-contract scope, production infrastructure,
  or tags were added. Verification passed
  `xriq/target/xriq-phase1-4-contract-check-20260608T185809Z/summary.json`.
- Latest native XRIQ Phase 1.4 signed-submit negative-smoke checkpoint: added
  `scripts/xriq_phase1_4_signed_submit_negative_smoke.py`. The smoke reads
  `signed-submit-negative-cases.json` plus the test-only envelope fixture,
  generates tampered scenario artifacts and expected refusal artifacts for all
  parse, verify, and state negative cases, and enforces `mutation: none`,
  `pending_write_allowed: false`, unchanged chain state, unchanged pending
  state, and local API audit visibility. It is parse/verify-only and does not
  call an accepted API mutation path or write pending state. Latest verified
  artifact:
  `xriq/target/xriq-phase1-4-signed-submit-negative-smoke-20260608T193237Z/summary.json`
  with `cases_checked: 10`.
- Latest native XRIQ Phase 1.4 Rust-side signed-submit verifier-preview
  checkpoint: added typed `xriq-api` inputs for the Phase 1.4 signed-transfer
  envelope, transaction, hashes, signature envelope, and local state context,
  plus `verify_signed_submit_envelope_preview`. The helper verifies the
  `xriq-local-signed-transfer-envelope-v1` fixture against canonical
  transaction signing hash, transaction hash, `test-only` signature algorithm,
  test-only signature encoding, chain id, nonce, expiry, and duplicate pending
  state. A valid preview returns `status: "verified"` and `mutation: "none"`.
  Negative cases return the same refusal codes/audit event ids as
  `signed-submit-negative-cases.json`, with `pending_write_allowed: false`,
  unchanged pending state, and unchanged chain state. This helper is not wired
  into an accepted API route yet; live
  `POST /api/v1/wallet/transfers/submit-signed` remains default-refused with
  `403 signed_submit_disabled`. Verification passed `cargo fmt`,
  `cargo test --target-dir target-codex-phase14-verify -p xriq-api -j 1`,
  bundled-Python `scripts/xriq_phase1_4_contract_check.py`
  (`xriq/target/xriq-phase1-4-contract-check-20260608T212447Z/summary.json`),
  `scripts/xriq_phase1_4_signed_submit_negative_smoke.py`
  (`xriq/target/xriq-phase1-4-signed-submit-negative-smoke-20260608T212447Z/summary.json`),
  `scripts/xriq_phase1_4_plan_check.py`
  (`xriq/target/xriq-phase1-4-plan-check-20260608T212917Z/summary.json`),
  `scripts/xriq_phase1_4_signed_artifact_check.py`
  (`xriq/target/xriq-phase1-4-signed-artifact-check-20260608T212450Z/summary.json`),
  and rebuilt `scripts/xriq_phase1_4_signed_submit_refusal_smoke.py`
  (`xriq/target/xriq-phase1-4-signed-submit-refusal-smoke-20260608T212512Z/summary.json`).
  The first refusal-smoke attempt with `--skip-build` reused an old
  `xriq/target/debug/xriq-api.exe`; run without `--skip-build` unless that
  debug binary has just been rebuilt. Next recommended narrow step: wire this
  verifier preview into the future accepted local/private signed-submit path
  only after explicit approval, or first add a non-mutating request/parser
  adapter that still returns refusals and writes no pending state.
- Latest native XRIQ Phase 1.4 non-mutating signed-submit request/parser
  adapter checkpoint: added `LocalWalletSignedSubmitPreviewRequest` in
  `xriq/crates/xriq-api/src/main.rs`. It parses signed-submit query fields into
  the typed verifier-preview envelope, derives sender nonce and duplicate
  pending-hash state from the current `XriqApiService`, and calls
  `verify_signed_submit_envelope_preview`. Tests cover valid preview
  verification against real height-1 private-devnet state plus malformed format,
  wrong chain id, and duplicate pending refusal behavior. This is still not a
  live accepted signed-submit route and it writes no pending state; product
  `POST /api/v1/wallet/transfers/submit-signed` remains default-refused with
  `403 signed_submit_disabled`. Verification passed `cargo fmt` and
  `cargo test --target-dir target-codex-phase14-adapter -p xriq-api -j 1`
  with 18 lib tests and 72 binary tests passing, plus bundled-Python
  `scripts/xriq_phase1_4_plan_check.py`
  (`xriq/target/xriq-phase1-4-plan-check-20260608T223258Z/summary.json`).
  The Phase 1.4 plan now also includes the accepted signed-submit mutation
  approval gate. Do not implement pending-file append from a generic continue.
  The exact required approval phrase is:
  `I explicitly approve implementing the Phase 1.4 local/private signed-submit accepted mutation behind --enable-local-wallet-submit-signed.`
  Verification passed bundled-Python
  `scripts/xriq_phase1_4_plan_check.py`
  (`xriq/target/xriq-phase1-4-plan-check-20260608T225342Z/summary.json`).
  Next recommended narrow implementation step after that exact approval is to
  add the accepted local/private signed-submit mutation behind
  `--enable-local-wallet-submit-signed`, then cover it with disabled/default,
  invalid-input, pending append, and block confirmation smoke.
- Latest native XRIQ Phase 1.4 accepted signed-submit mutation checkpoint:
  after the user explicitly approved the exact required phrase, `xriq-api`
  now supports `--enable-local-wallet-submit-signed true` in both one-shot
  `request` and `serve-readonly` modes for
  `POST /api/v1/wallet/transfers/submit-signed`. The default route still
  returns `403 signed_submit_disabled` without that flag. With the flag, the
  API parses the signed-submit envelope, rejects forbidden key/custody/public/
  DEX fields, verifies the test-only signed envelope before mutation, appends
  exactly one verified transaction to the local pending file through the
  existing node validation helper, compares the written transaction hash with
  the verified envelope hash, returns `201 signed_submit_accepted_local_only`,
  records accepted audit metadata, leaves chain state unchanged, and refreshes
  server-mode mempool state after success. Invalid or forbidden accepted-route
  inputs remain non-mutating. This checkpoint does not add wallet submit UI
  mutation, custody, browser-held key material, raw signatures in logs, public
  network, DEX, bridge, smart-contract, production infrastructure, or tags.
  Verification passed `cargo fmt --check` and
  `cargo test -p xriq-api -j 1 --target-dir target-codex-phase14-signed-accepted`
  with 18 library tests and 75 binary tests passing, plus bundled-Python
  `scripts/xriq_phase1_4_contract_check.py`
  (`xriq/target/xriq-phase1-4-contract-check-20260608T231501Z/summary.json`)
  and `scripts/xriq_phase1_4_plan_check.py`
  (`xriq/target/xriq-phase1-4-plan-check-20260608T231646Z/summary.json`),
  plus `scripts/xriq_phase1_4_signed_submit_negative_smoke.py`
  (`xriq/target/xriq-phase1-4-signed-submit-negative-smoke-20260608T231551Z/summary.json`)
  and `scripts/xriq_phase1_4_signed_submit_refusal_smoke.py`
  (`xriq/target/xriq-phase1-4-signed-submit-refusal-smoke-20260608T231601Z/summary.json`).
  At that accepted-mutation checkpoint, Phase 1.4/XRIQ private-devnet
  non-production status was about `85%`.
- Latest native XRIQ Phase 1.4 signed-submit lifecycle smoke checkpoint:
  added `scripts/xriq_phase1_4_signed_submit_lifecycle_smoke.py`. It is a
  CPU-only request-mode smoke that uses an isolated Cargo target directory by
  default, creates a height-1 base chain, generates a CLI-only
  `xriq-wallet signed-transfer` artifact, verifies default signed-submit
  refusal without mutation, verifies invalid signed-submit refusal without
  mutation, submits the valid signed artifact through
  `--enable-local-wallet-submit-signed true`, verifies pending status, produces
  one local block through `--enable-local-block-production true`, and verifies
  confirmed wallet status, empty mempool, network/explorer state, wallet
  balances, wallet histories, and Admin audit catalog visibility. This
  checkpoint does not add wallet submit UI mutation, custody, browser-held key
  material, public network, DEX, bridge, smart-contract, production
  infrastructure, or tags. Verification passed bundled-Python
  `scripts/xriq_phase1_4_signed_submit_lifecycle_smoke.py`; latest summary is
  `xriq/target/xriq-phase1-4-signed-submit-lifecycle-smoke-20260609T024220Z/summary.json`.
  Follow-up validation also passed bundled-Python `py_compile`,
  `scripts/xriq_phase1_4_plan_check.py`
  (`xriq/target/xriq-phase1-4-plan-check-20260609T024547Z/summary.json`),
  and `scripts/xriq_phase1_4_signed_artifact_check.py`
  (`xriq/target/xriq-phase1-4-signed-artifact-check-20260609T024602Z/summary.json`).
  Phase 1.4/XRIQ private-devnet non-production status is now about `90%`.
- Latest native XRIQ Phase 1.4 RC candidate report checkpoint: added
  `docs/XRIQ_PHASE1_4_RC_CANDIDATE_REPORT.md` as the docs-only candidate
  report for proposed tag `phase1-4-xriq-local-signed-submit-rc1`, and added
  `scripts/xriq_phase1_4_rc_readiness.py` as the cheap pre-tag readiness guard
  for the candidate report, lifecycle smoke, plan check, signed-artifact check,
  contract check, negative smoke, refusal smoke, docs references, local tag
  absence, and the no-generic-approval rule. The exact approval phrase required
  before creating/pushing the proposed Phase 1.4 tag is:
  `I explicitly approve creating and pushing the Phase 1.4 RC tag phase1-4-xriq-local-signed-submit-rc1.`
  A generic "continue" or "do the next steps" request is not approval to tag.
  The recommended next narrow step is to run the readiness guard, commit/push
  this checkpoint, and then ask the user for the exact Phase 1.4 RC tag
  decision. Phase 1.4/XRIQ private-devnet non-production status is now about
  `95%`.
- Latest native XRIQ Phase 1.4 RC tag checkpoint: after exact explicit user
  approval on 2026-06-09, created and pushed
  `phase1-4-xriq-local-signed-submit-rc1` at commit `45be474`. Updated
  `docs/XRIQ_PHASE1_4_RC_CANDIDATE_REPORT.md`,
  `docs/XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md`, README references, and
  `scripts/xriq_phase1_4_rc_readiness.py` to record the completed tag action
  and support post-tag status checks with
  `python scripts/xriq_phase1_4_rc_readiness.py --require-clean-git --require-origin-main --require-tag-present`.
  Do not move, delete, recreate, or repush the tag without an exact
  tag-maintenance request. Phase 1.4/XRIQ private-devnet non-production status
  is now `100%` for this local/private signed-transfer RC1 scope.
- Latest native XRIQ private-devnet wrap-up checkpoint: added
  `docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md` and
  `scripts/xriq_private_devnet_wrapup_check.py` to consolidate Phase 1 through
  Phase 1.4 into a completed 100% non-production private-devnet handoff. The
  guard validates the five Phase 1 tags, docs references, source-control
  status, and scope boundaries without running heavy Rust tests, touching cloud
  resources, or creating tags. This checkpoint also links the wrap-up from
  `README.md`, `xriq/README.md`, `.github/copilot-instructions.md`, and
  `docs/XRIQ_PRODUCTION_ROADMAP.md`. Next scope should be a human decision:
  GitHub Copilot production hardening, a narrow local/private Phase 1.5 gap,
  BIBER MVP/model work, or manual demo support.
- Latest Gemini Code Assist Enterprise handoff checkpoint: added
  `docs/GEMINI_CODE_ASSIST_XRIQ_PROMPT.md` and
  `docs/GEMINI_CODE_ASSIST_BIBER_PROMPT.md`. These prompts direct Gemini to
  work from GitHub repo `https://github.com/selvasmallive/biber-ai-platform`,
  use `main` as the base branch, preserve backup branches
  `backup/xriq-pre-gemini-20260614` and
  `backup/biber-pre-gemini-20260614`, keep PRs narrow, avoid cloud/secrets/tag
  changes, and ask Codex to monitor/review direction between meaningful Gemini
  milestones.
- Latest XRIQ production handoff checkpoint for later GitHub Copilot work:
  added `.github/copilot-instructions.md` and
  `docs/XRIQ_PRODUCTION_ROADMAP.md`. These files make the post-private-devnet
  strategy explicit: complete the XRIQ private-devnet prototype with Codex,
  then use GitHub Copilot agents/PRs in the same repo for Phase 2-6 production
  hardening while keeping Codex/OpenAI usage minimal. The roadmap separates
  Phase 2 hardened private/staging devnet, Phase 3 public testnet, Phase 4
  security/legal/economic readiness, Phase 5 production candidate, and Phase 6
  public mainnet/ecosystem. This checkpoint does not start production work and
  does not broaden the current active Codex scope beyond XRIQ private-devnet.
- Latest XRIQ production cloud/Copilot handoff hardening checkpoint: expanded
  `.github/copilot-instructions.md` and `docs/XRIQ_PRODUCTION_ROADMAP.md` with
  Azure/AWS/GCP-neutral production guidance. The docs now require a human cloud
  provider decision before provider-specific IaC, prohibit creating/modifying/
  destroying cloud resources without explicit approval, prefer Terraform for
  reviewable infrastructure plans, and define environment isolation,
  reference production architecture, secrets/KMS/HSM policy, observability,
  WAF/DDoS/rate-limit, backups, rollback, cost alarms, and provider examples
  for managed Kubernetes, PostgreSQL, object storage, secrets, KMS/HSM,
  container registry, monitoring, and edge/WAF. Added
  `scripts/xriq_production_roadmap_check.py` to validate the production roadmap
  and Copilot cloud handoff markers; verification passed
  `xriq/target/xriq-production-roadmap-check-20260608T225342Z/summary.json`.
  This still does not start production cloud work and does not create
  Azure/AWS/GCP resources.
- Latest native XRIQ Phase 1.2 RC readiness guardrail checkpoint:
  added `scripts/xriq_phase1_2_rc_readiness.py` as a non-mutating guard that
  checks the RC candidate report, the latest readiness summary, the latest UI
  mutation-control gate, the latest block-production UI design check, required
  smoke artifact paths, handoff/plan/gate doc references, and optional
  clean-git/origin-main/tag-absent conditions. The guard now also fails if the
  candidate report does not reference the selected/latest readiness,
  UI mutation-control, and block-production design summaries, preventing stale
  RC evidence from being tagged. The guard output now includes
  `release_decision.generic_continue_is_approval: false`, the exact approval
  phrase, allowed no-approval actions, allowed post-approval commands, and
  prohibited tag/scope actions, plus `release_decision_check` so the guard
  fails if those decision boundaries drift. The guard now also reports
  `release_decision.recommended_next_step: "ask the user for the Phase 1.2 RC decision"`
  and says generic continue should not produce more RC guardrail churn unless
  new evidence or a concrete risk appears. It can also write a timestamped
  ignored evidence artifact under `xriq/target/` with `--write-summary`. Use
  `python scripts/xriq_phase1_2_rc_readiness.py` for a cheap local check, and
  after an exact explicit tag approval, run
  `python scripts/xriq_phase1_2_rc_readiness.py --require-clean-git --require-origin-main --require-tag-absent --write-summary`
  before creating or pushing the proposed tag. The script creates no tag.
- Latest native XRIQ Phase 1.2 Admin UI block-production guard checkpoint:
  the React Admin Status panel now includes `Admin Action Guards` with a
  disabled `Produce Block` control and an explicit `Check Guard` action. The
  client calls `POST /api/v1/blocks/produce` through the shared API layer,
  accepts only the HTTP `403` disabled/refused response, validates
  `block_production_disabled`, `--enable-local-block-production`,
  `mutation: "none"`, local/private-devnet scope, request-field names, and
  refusal guards, then renders the disabled guard state. The Audit Events
  section also shows the local block-production refusal record from
  `local_refusal_audit_events`. This checkpoint still does not produce blocks,
  confirm pending transactions, change chain state, change pending state, sign,
  custody, enable wallet submit/send success, DEX/smart contracts, or public
  network behavior. Verification passed `npm.cmd run check`,
  escalated `npm.cmd run build`, browser smoke at `http://127.0.0.1:5173/`
  against `xriq-api serve-readonly` on `127.0.0.1:8090`, and the local smoke
  artifact
  `xriq/target/xriq-phase1-2-admin-guard-smoke-20260601T052800Z/summary.json`.
  Superseded by the newer local block-production API checkpoint above. Keep
  this UI guard disabled until a later explicit UI mutation-control milestone.
- Latest native XRIQ Phase 1.2 block-production API refusal checkpoint:
  `xriq-api` now returns stable HTTP `403 Forbidden` disabled responses for
  `POST /api/v1/blocks/produce`. The response declares `enabled: false`,
  `mutation: "none"`, `status: "disabled"`, `code:
  "block_production_disabled"`, `--enable-local-block-production`,
  `audit_scope: "api-local-refusal"`, `audit_event_recorded: true`,
  `block_production_attempt`, `block_production`, request field names, refusal
  guards, and test-identity-only/local-private-devnet boundaries. Admin audit
  visibility now exposes three API-local refusal records: wallet submit, wallet
  send, and block production. The block-production record is
  `block-production:local_request_id` and is visible from file-backed API
  routes plus the Postgres read-model rendering path. The local smoke writes
  `xriq/target/xriq-phase1-2-block-refusal-smoke-20260601T051300Z/api/block-production-disabled.json`
  and verifies `POST /api/v1/blocks/produce` under `failure_routes_checked`.
  This checkpoint still does not produce blocks, confirm pending transactions,
  change chain state, change pending state, sign, custody, enable wallet
  submit/send success, DEX/smart contracts, or public network behavior.
  Verification passed `cargo fmt`, `cargo test -p xriq-api --lib -j 1`,
  `cargo test --target-dir target/codex-phase1-2-block-refusal -p xriq-api --bin xriq-api -j 1`,
  bundled-Python `py_compile`, `scripts/xriq_phase1_1_contract_check.py`,
  `scripts/xriq_phase1_2_refusal_smoke.py`,
  `scripts/xriq_phase1_1_rc_readiness.py --latest-summary`, and
  `scripts/xriq_phase1_1_local_e2e_smoke.py --artifact-dir xriq/target/xriq-phase1-2-block-refusal-smoke-20260601T051300Z`.
  Superseded by the newer Admin UI guard and local block-production API
  checkpoints above.
- Latest native XRIQ Phase 1.2 block-production preflight checkpoint:
  `xriq/fixtures/phase1_2/block-production-disabled.json` and
  `xriq/fixtures/phase1_2/block-production-audit-expectation.json` now define
  the default-off contract for `POST /api/v1/blocks/produce`. The contract uses
  `block_production_attempt`, `block_production`, `--enable-local-block-production`,
  local request id policy, request-fields-only audit metadata, test-identity-only
  scope, and explicit guards that pending state and chain state are not changed
  by the default path. `scripts/xriq_phase1_1_contract_check.py` and
  `scripts/xriq_phase1_2_refusal_smoke.py` validate the block-production
  fixtures alongside the existing wallet submit/send fixtures. This checkpoint
  still does not add the API POST route, produce blocks, confirm pending
  transactions, change chain state, change pending state, sign, custody, enable
  DEX/smart contracts, or expose public network behavior. Verification passed
  bundled-Python `py_compile`, `scripts/xriq_phase1_1_contract_check.py`,
  `scripts/xriq_phase1_2_refusal_smoke.py`,
  `scripts/xriq_phase1_1_rc_readiness.py --latest-summary`, and
  `git diff --check`. This preflight-only step was followed by the API-level
  block-production refusal checkpoint above.
- Latest native XRIQ Phase 1.2 admin audit visibility checkpoint:
  `/api/v1/admin/audit-events?limit=...` now keeps indexed read-model audit
  rows in `audit_events` and adds `local_refusal_audit_count` plus
  `local_refusal_audit_events[]` for the deterministic refused wallet
  submit/send audit records. The local refusal records include
  `audit_scope: "api-local-refusal"`, `recording: "api-local-response"`,
  refused/disabled/non-mutating status, endpoint, refusal code, explicit local
  flag, local request id placeholder, and request-fields-only metadata policy.
  The file-backed API, `request-postgres`, and explicitly Postgres-enabled
  `serve-readonly` render the same section without storing these records as
  persistent chain/indexer rows. This remains visibility-only and still does
  not enable successful wallet submit/send, pending-state mutation, chain
  mutation, signing, custody, transaction hashes, DEX, smart contracts, public
  mainnet, bridges, exchange listings, or production infrastructure.
  Checkpoint artifacts:
  `xriq/target/xriq-phase1-2-audit-visibility-smoke-20260601T044700Z/summary.json`
  and
  `xriq/target/xriq-phase1-2-audit-visibility-docker-smoke-20260601T045200Z/summary.json`.
  Verification passed `cargo test --target-dir target/codex-phase1-2-audit-visibility -p xriq-api --lib -j 1`,
  `cargo test -p xriq-api --bin xriq-api -j 1`, bundled-Python `py_compile`,
  `scripts/xriq_phase1_1_contract_check.py`,
  `scripts/xriq_phase1_2_refusal_smoke.py`,
  `scripts/xriq_phase1_1_local_e2e_smoke.py --artifact-dir xriq/target/xriq-phase1-2-audit-visibility-smoke-20260601T044700Z`,
  and escalated Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live --artifact-dir xriq/target/xriq-phase1-2-audit-visibility-docker-smoke-20260601T045200Z`.
- Latest native XRIQ Phase 1.2 API-local refusal audit checkpoint: disabled
  `POST /api/v1/wallet/transfers/submit` and
  `POST /api/v1/wallet/transfers/send` responses now include
  `audit_scope: "api-local-refusal"`, `audit_event_recorded: true`, and a
  deterministic `audit_event` object. The audit record uses
  `local-private-devnet-operator`, the wallet transfer attempt action,
  `wallet_transfer` resource type, refused outcome metadata, explicit local
  flag, local request id placeholder, and request-fields-only metadata policy.
  The disabled fixtures, contract checker, refusal smoke, Rust API tests, and
  local API smoke all validate these fields while still forbidding accepted
  wallet mutation, pending-state mutation, chain mutation, signing, custody,
  transaction hashes, DEX, smart contracts, public mainnet, bridges, exchange
  listings, and production infrastructure. Checkpoint artifacts:
  `xriq/target/xriq-phase1-2-refusal-smoke-20260601T043851Z/summary.json` and
  `xriq/target/xriq-phase1-2-api-audit-refusal-smoke-20260601T043700Z/summary.json`.
  Verification passed `cargo test -p xriq-api --lib -j 1`, bundled-Python
  `py_compile`, `scripts/xriq_phase1_1_contract_check.py`,
  `scripts/xriq_phase1_2_refusal_smoke.py`, and
  `scripts/xriq_phase1_1_local_e2e_smoke.py --artifact-dir xriq/target/xriq-phase1-2-api-audit-refusal-smoke-20260601T043700Z`,
  plus `scripts/xriq_phase1_1_rc_readiness.py --latest-summary` and
  `git diff --check`.
- Latest native XRIQ Phase 1.2 API refusal checkpoint: `xriq-api` now returns
  stable HTTP `403 Forbidden` disabled responses for
  `POST /api/v1/wallet/transfers/submit` and
  `POST /api/v1/wallet/transfers/send`. Those responses declare
  `enabled: false`, `mutation: "none"`, `status: "disabled"`,
  `warning: "local-private-devnet-preflight-only"`, explicit local enablement
  flags (`--enable-local-wallet-submit` and `--enable-local-wallet-send`),
  audit-event requirements, test-identity-only boundaries, request field names,
  and refusal guards. They intentionally omit `tx_hash`, private-key material,
  seed material, custody fields, and any chain/pending-state mutation.
  `scripts/xriq_phase1_1_local_e2e_smoke.py` now checks both POST refusal
  routes and writes `api/wallet-submit-disabled.json` and
  `api/wallet-send-disabled.json` under the smoke artifact directory.
  Checkpoint artifact:
  `xriq/target/xriq-phase1-2-api-refusal-smoke-20260601T031500Z/summary.json`
  with `wallet mutation refusal smoke` completed and both POST routes listed
  under `failure_routes_checked`. Verification passed `cargo fmt --check`,
  `cargo test --target-dir target/codex-phase1-2-refusal-api -p xriq-api --lib -j 1`,
  bundled-Python `py_compile`, `python scripts/xriq_phase1_2_refusal_smoke.py`,
  `python scripts/xriq_phase1_1_contract_check.py`,
  `python scripts/xriq_phase1_1_rc_readiness.py --latest-summary`, the local
  Phase 1.2 API-refusal smoke command above, and `git diff --check`. This
  checkpoint still does not enable successful transaction submission, sending,
  pending-state mutation, block production, successful UI mutation actions,
  signing, custody, DEX, smart contracts, public mainnet, bridges, exchange
  listings, or production infrastructure.
- Latest native XRIQ Phase 1.2 UI/client action-guard checkpoint: the React
  wallet shell now includes a `Wallet Action Guards` section with disabled
  `Submit Draft` and `Send Transfer` controls plus an explicit `Check Guards`
  action. The client API layer now has `WalletMutationRefusalResponse` and
  `loadWalletMutationRefusal`, which posts to the disabled submit/send
  endpoints and accepts only HTTP `403` responses. The wallet UI validates the
  returned refusal contract (`private-devnet`, `xriq-devnet`, `enabled: false`,
  `mutation: "none"`, `status: "disabled"`, expected refusal codes, explicit
  local flags, audit-event requirement, test-identity-only boundary, and
  request field names) before showing the guards as ready. The static UI check
  now requires those markers and still rejects wallet code that directly
  contains submit/send endpoint strings, raw `fetch(` calls, or sensitive
  key/seed fields. Verification passed `npm.cmd run check` in
  `xriq/apps/explorer-ui` and `npm.cmd run build` outside the sandbox after the
  sandboxed Vite build hit the known Windows access-denied config-resolution
  issue. Browser smoke at `http://127.0.0.1:5173/` found `Wallet Action
  Guards`, `Submit Draft`, `Send Transfer`, and `Check Guards`; `Submit Draft`
  and `Send Transfer` were disabled while `Check Guards` remained enabled.
  This checkpoint still does not enable successful transaction
  submission, sending, pending-state mutation, block production, signing,
  custody, DEX, smart contracts, public mainnet, bridges, exchange listings, or
  production infrastructure.
- Latest native XRIQ Phase 1.2 planning checkpoint: added
  `docs/XRIQ_PHASE1_2_LOCAL_PRIVATE_PLAN.md` to define the post-RC local/private
  implementation ladder. The next recommended code checkpoint is a small
  mutation preflight contract update with disabled wallet submit/send fixtures
  and contract-check coverage only; do not enable transaction submission,
  block production, snapshot mutation, DEX, smart contracts, public mainnet,
  custody, bridges, exchange listings, or production infrastructure from a
  generic continuation request.
- Latest native XRIQ Phase 1.2 mutation preflight contract checkpoint: added
  disabled wallet submit/send preflight fixtures under `xriq/fixtures/phase1_2/`
  and extended `scripts/xriq_phase1_1_contract_check.py` to validate that the
  fixtures declare `enabled: false`, `mutation: "none"`, `status: "disabled"`,
  explicit local/private enablement flags, audit-event requirements, and
  test-identity-only boundaries. This checkpoint does not enable actual
  transaction submission, sending, pending-state mutation, UI actions, block
  production, or custody behavior.
- Latest native XRIQ Phase 1.2 refusal-smoke checkpoint: added
  `scripts/xriq_phase1_2_refusal_smoke.py` to independently validate the
  disabled submit/send fixtures and write a summary under
  `xriq/target/xriq-phase1-2-refusal-smoke-*`. Checkpoint artifact:
  `xriq/target/xriq-phase1-2-refusal-smoke-20260601T032806Z/summary.json` with
  `ok: xriq-phase1-2-refusal-smoke`, `fixtures_checked: 4`,
  `disabled_fixtures_checked: 2`, and `audit_expectations_checked: 2`. The
  smoke checks disabled-by-default behavior, `mutation: "none"`, explicit
  local/private enablement flags, audit-event requirements,
  test-identity-only boundaries, absence of signing/custody/transaction-hash
  response fields, and audit metadata expectations that forbid sensitive
  material. Its `next` pointer now targets API-local audit event recording for
  refused attempts before any successful local mutation path. Verification
  passed bundled-Python `py_compile`,
  `python scripts/xriq_phase1_2_refusal_smoke.py`,
  `python scripts/xriq_phase1_1_contract_check.py`,
  `python scripts/xriq_phase1_1_rc_readiness.py --latest-summary`, and
  `git diff --check`. API-level POST refusal behavior was added in the later
  Phase 1.2 API refusal checkpoint above. Successful UI mutation actions and
  custody remain disabled; the newer guarded local wallet-submit,
  wallet-send, and block-production API checkpoints above are the only accepted
  local mutation paths.
- Latest native XRIQ Phase 1.2 audit expectation checkpoint: added
  `xriq/fixtures/phase1_2/wallet-transfer-submit-audit-expectation.json` and
  `xriq/fixtures/phase1_2/wallet-transfer-send-audit-expectation.json`. These
  define the required local actor (`local-private-devnet-operator`), actions
  (`wallet_transfer_submit_attempt` and `wallet_transfer_send_attempt`),
  resource type (`wallet_transfer`), refused-by-default behavior, accepted-only
  local flag requirements, audit-event-required boundaries for both refused and
  accepted attempts, test-identity-only scope, required audit metadata, and
  forbidden metadata such as private keys, seed phrases, mnemonic material,
  signatures, signed transactions, and transaction hashes before accepted
  mutation. `scripts/xriq_phase1_1_contract_check.py` and
  `scripts/xriq_phase1_2_refusal_smoke.py` now validate those fixtures. This
  checkpoint is contract-only and does not write audit events or enable
  submit/send mutation.
- Latest native XRIQ Phase 1.1 RC1 tag checkpoint: after explicit user approval,
  created and pushed `phase1-1-xriq-local-e2e-rc1` at commit `6a38a51a`.
  Pre-tag validation passed
  `scripts/xriq_phase1_1_rc_readiness.py --latest-summary --require-clean-git --require-origin-main`,
  confirming a clean worktree, `HEAD == origin/main`, 26 readiness routes, 14
  required latest-smoke artifact paths, and the latest Docker live smoke summary
  at
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T223438Z/summary.json`
  with 60 completed steps and no skipped checks. Do not move, delete, or
  recreate this tag unless the user explicitly asks for that exact tag
  maintenance operation.
- Latest native XRIQ Phase 1.1 RC candidate report checkpoint: added
  `docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md` as the candidate summary for the
  current local/private end-to-end scope, latest Docker live smoke artifact,
  readiness guardrail evidence, non-production exclusions, and the exact
  approval phrase required before any Phase 1.1 RC tag. The proposed tag is
  `phase1-1-xriq-local-e2e-rc1`. No tag was created, moved, or pushed by that
  report checkpoint; the tag was created later only after explicit user
  approval. Phase 1.1 status was about `95%` overall before the tag.
- Latest native XRIQ Phase 1.1 RC readiness checkpoint: added
  `docs/XRIQ_PHASE1_1_RC_READINESS.md` with the local/private RC go/no-go
  checklist, route-parity matrix, deferred no-go surfaces, validation commands,
  and explicit rule that no Phase 1.1 RC tag may be created, moved, or pushed
  without user approval naming the tag. Added
  `scripts/xriq_phase1_1_rc_readiness.py` as a cheap guardrail that checks the
  readiness document, required docs references, and optionally the latest
  Docker live smoke summary via `--latest-summary`. Verification passed
  bundled-Python `py_compile`, `python scripts/xriq_phase1_1_rc_readiness.py`,
  `python scripts/xriq_phase1_1_rc_readiness.py --latest-summary`, and
  `git diff --check`. Phase 1.1 status was about `94%` overall.
- Recommended next narrow step: run
  `python scripts/xriq_phase1_4_plan_check.py` and
  `python scripts/xriq_phase1_4_contract_check.py` after any Phase 1.4
  planning or fixture edit, and
  `python scripts/xriq_phase1_4_signed_artifact_check.py` after any wallet CLI
  signed-artifact edit, and
  `python scripts/xriq_phase1_4_signed_submit_refusal_smoke.py` after any API
  signed-submit refusal edit, and
  `python scripts/xriq_phase1_4_signed_submit_negative_smoke.py` after any
  negative-case matrix edit. After the signed-submit lifecycle smoke, the next
  narrow checkpoint should be Phase 1.4 readiness/RC-candidate documentation
  and a cheap readiness guard, without creating or pushing any tag unless the
  user explicitly approves the exact tag name. Do not add wallet submit UI
  mutation, custody, browser key material, public network, DEX, bridge,
  smart-contract, asset issuance, production infrastructure, or tags without
  explicit approval.
  The user can still run the Phase 1.3 manual browser demo with
  `python scripts/xriq_phase1_3_demo_launcher.py --skip-build --launch --auto-port`
  and follow `docs/XRIQ_PHASE1_3_DEMO_RUNBOOK.md`. Do not move, delete,
  recreate, or repush
  `phase1-3-xriq-local-private-behavior-rc1`, or
  `phase1-2-xriq-local-private-hardening-rc1` unless the user explicitly asks
  for that exact tag maintenance operation. Keep wallet submit UI, snapshot
  import/export mutation, DEX, smart contracts, public mainnet, custody,
  bridges, exchange listings, and production infrastructure out of scope until
  explicitly approved.
- Latest native XRIQ Phase 1.1 Postgres-backed ISO 20022 account-statement
  checkpoint: extended `xriq-api request-postgres` and explicitly
  Postgres-enabled `xriq-api serve-readonly` to return
  `/api/v1/iso20022/accounts/{address}/statement?from=...&to=...` from
  confirmed account-history and balance rows in the local Docker Postgres read
  model. The response preserves the product ISO 20022 account-statement
  preview shape (`environment`, `not_certified`, `mapping_version`,
  `message_type`, `message_id`, `account_address`, `from`, `to`,
  `opening_balance_base_units`, `closing_balance_base_units`, `entries`, and
  `unsupported_fields`) and adds local-only `source: postgres-read-model`,
  `read_model_warning`, and `read_only: true`. The route remains
  GET-only/read-only, preview-only, and not certified; it does not claim bank,
  SWIFT, ISO certification, settlement, or payment-network connectivity.
  Without explicit Postgres flags,
  `/api/v1/iso20022/accounts/{address}/statement?from=...&to=...` still uses
  the default file-backed route. Invalid addresses or invalid timestamp query
  values return `400 bad_request` before Docker is invoked, and an unknown
  account returns `404 not_found`. The live Docker smoke now writes
  `indexer/postgres-api-iso-account-statement.json` and
  `indexer/postgres-server-iso-account-statement.json`. Verification passed
  `cargo test --target-dir target-codex-iso-statement -p xriq-api --bin xriq-api -j 1`,
  `cargo test --target-dir target-codex-iso-statement -p xriq-api --lib -j 1`,
  bundled-Python `py_compile`,
  `cargo clippy --target-dir target-codex-iso-statement -p xriq-api -- -D warnings`,
  and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T223438Z`. Phase 1.1
  status was about `93%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed ISO 20022 payment-initiation
  checkpoint: extended `xriq-api request-postgres` and explicitly
  Postgres-enabled `xriq-api serve-readonly` to return
  `/api/v1/iso20022/payment-initiation/preview?tx_hash=...` from confirmed
  rows in the local Docker Postgres read model. The response preserves the
  product ISO 20022 payment-initiation preview shape (`environment`,
  `not_certified`, `mapping_version`, `message_type`, `message_id`,
  `source_tx_hash`, `xriq`, `iso20022_aligned`, and `unsupported_fields`) and
  adds local-only `source: postgres-read-model`, `read_model_warning`, and
  `read_only: true`. The route remains GET-only/read-only, preview-only, and
  not certified; it does not claim bank, SWIFT, ISO certification, settlement,
  or payment-network connectivity. Without explicit Postgres flags,
  `/api/v1/iso20022/payment-initiation/preview?tx_hash=...` still uses the
  default file-backed route. Missing or invalid `tx_hash` returns
  `400 bad_request` before Docker is invoked, and a valid-but-unknown confirmed
  hash returns `404 not_found`. The live Docker smoke now writes
  `indexer/postgres-api-iso-payment-initiation.json` and
  `indexer/postgres-server-iso-payment-initiation.json`. Verification passed
  `cargo test --target-dir target-codex-iso-initiation -p xriq-api --bin xriq-api -j 1`,
  `cargo test --target-dir target-codex-iso-initiation -p xriq-api --lib -j 1`,
  bundled-Python `py_compile`,
  `cargo clippy --target-dir target-codex-iso-initiation -p xriq-api -- -D warnings`,
  and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T220720Z`. Phase 1.1
  status was about `92%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed ISO 20022 transaction-status
  checkpoint: extended `xriq-api request-postgres` and explicitly
  Postgres-enabled `xriq-api serve-readonly` to return
  `/api/v1/iso20022/transactions/{tx_hash}/status` from the local Docker
  Postgres read model using confirmed `xriq_transactions` and pending
  `xriq_mempool_entries`. The response preserves the product ISO 20022 payment
  status preview shape (`environment`, `not_certified`, `mapping_version`,
  `message_type`, `message_id`, `source_tx_hash`, `xriq_status`,
  `iso20022_aligned`, and `unsupported_fields`) and adds local-only
  `source: postgres-read-model`, `read_model_warning`, and `read_only: true`.
  The route remains GET-only/read-only, preview-only, and not certified; it
  does not claim bank, SWIFT, ISO certification, settlement, or payment-network
  connectivity. Without explicit Postgres flags,
  `/api/v1/iso20022/transactions/{tx_hash}/status` still uses the default
  file-backed route. Invalid hashes return `400 bad_request` before Docker is
  invoked, and missing hashes return `404 not_found`. The live Docker smoke now
  writes `indexer/postgres-api-iso-transaction-status.json` and
  `indexer/postgres-server-iso-transaction-status.json`. Verification passed
  `cargo fmt --check`, bundled-Python `py_compile`,
  `cargo test --target-dir target-codex-iso-status -p xriq-api --bin xriq-api -j 1`,
  `cargo test --target-dir target-codex-iso-status -p xriq-api --lib -j 1`,
  `cargo clippy --target-dir target-codex-iso-status -p xriq-api -- -D warnings`,
  and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T215557Z`. Phase 1.1
  status was about `91%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed wallet draft-preview
  checkpoint: extended `xriq-api request-postgres` and explicitly
  Postgres-enabled `xriq-api serve-readonly` to return
  `/api/v1/wallet/transfers/draft-preview?...` from the local Docker Postgres
  read model using `xriq_blocks` for current height and
  `xriq_account_balances` for sender balance/nonce. The response preserves the
  product wallet draft-preview fields (`warning`, `mutation`, `validation`,
  `draft`, and `balance`) and adds local-only
  `source: postgres-read-model`, `read_model_warning`, and `read_only: true`.
  The route remains GET-only/read-only with no signing, no submit, no send, and
  no mutation. Without explicit Postgres flags,
  `/api/v1/wallet/transfers/draft-preview?...` still uses the default
  file-backed chain plus pending TSV path; malformed query input returns
  `400 bad_request` before Docker is invoked. The live Docker smoke now writes
  `indexer/postgres-api-wallet-draft-preview.json` and
  `indexer/postgres-server-wallet-draft-preview.json`. Verification passed
  `cargo fmt --check`, bundled-Python `py_compile`,
  `cargo test --target-dir target-codex-draft-preview -p xriq-api --bin xriq-api -j 1`,
  `cargo test --target-dir target-codex-draft-preview -p xriq-api --lib -j 1`,
  `cargo clippy --target-dir target-codex-draft-preview -p xriq-api -- -D warnings`,
  and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T205708Z`. Phase 1.1
  status was about `90%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed wallet status checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/wallet/status` from the local
  Docker Postgres read model using `xriq_blocks`, `xriq_account_balances`, and
  `xriq_mempool_entries`. The response preserves the product wallet status
  fields (`warning`, `current_height`, `latest_block_hash`, `state_root`,
  `account_count`, `pending_transactions`, and `capabilities`) and adds
  local-only `source: postgres-read-model`, `read_model_warning`, and
  `read_only: true`. Without explicit Postgres flags,
  `/api/v1/wallet/status` still uses the default file-backed chain plus
  pending TSV path. The live Docker smoke now writes
  `indexer/postgres-api-wallet-status.json` and
  `indexer/postgres-server-wallet-status.json`. Verification passed
  `cargo fmt --check`, bundled-Python `py_compile`,
  `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo test -p xriq-api --lib -j 1`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T204308Z`. Phase 1.1
  status was about `89%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed block detail checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/blocks/{height-or-hash}` from
  the local Docker Postgres read model using `xriq_blocks` plus confirmed
  `xriq_transactions`. The response preserves the product block detail fields
  (`height`, block hashes/roots, `transaction_count`, `timestamp_utc`, and
  `transactions[]`) and adds local-only `source: postgres-read-model`,
  `warning`, and `read_only: true`. Without explicit Postgres flags,
  `/api/v1/blocks/{height-or-hash}` still uses the default file-backed chain
  path. Invalid block identifiers return `400 bad_request` before Docker is
  invoked; valid missing blocks return `404 not_found`. The live Docker smoke
  now writes `indexer/postgres-api-block-detail.json` and
  `indexer/postgres-server-block-detail.json`. Verification passed
  `cargo fmt --check`, bundled-Python `py_compile`,
  `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo test -p xriq-api --lib -j 1`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T200313Z`. Phase 1.1
  status is now about `88%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed pending wallet
  transaction-status checkpoint: split the Postgres wallet transaction-status
  query from confirmed transaction detail so
  `/api/v1/wallet/transactions/{tx_hash}/status` checks confirmed
  `xriq_transactions` first, then falls back to `xriq_mempool_entries` for
  pending hashes. Confirmed responses remain unchanged; pending Postgres
  responses now match the default file-backed product shape with
  `status: "pending"`, `block_height: null`, `block_hash: null`, and
  `transaction_index: null`, without exposing from/to/amount/fee/nonce fields
  and without enabling submit or block production. Valid missing hashes still
  return `404 not_found`; malformed hashes still return `400 bad_request`
  before Docker is invoked. The live Docker smoke now writes
  `indexer/postgres-api-wallet-pending-transaction-status.json` and
  `indexer/postgres-server-wallet-pending-transaction-status.json`.
  Verification passed `cargo fmt --check`, bundled-Python `py_compile`,
  `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo test -p xriq-api --lib -j 1`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T192954Z`. Phase 1.1
  status is now about `87%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed mempool checkpoint: extended
  `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/mempool?limit=...` from the
  local Docker Postgres read model. The route is still opt-in and local-only:
  default `xriq-api request` / `serve-readonly` behavior keeps using the
  file-backed pending TSV when explicit Postgres flags are absent. The live
  Docker smoke imports the generated durable `pending.tsv` row into
  `xriq_mempool_entries` after applying the schema and indexer write-plan, so
  the Postgres read-model status now includes `mempool_entries: 1`, and
  Postgres node status / explorer overview now report
  `pending_transactions: 1`. The mempool response preserves product mempool
  fields (`current_height`, `pending_count`, `limit`, `next_cursor`,
  `inspect_status`, disabled `submit_status`, disabled
  `produce_block_status`, and `entries[]`) and adds local-only `source:
  postgres-read-model`, `read_model_warning`, and `read_only: true` while
  keeping the product mempool no-mutation warning. Invalid `limit` values are
  rejected with `400 bad_request` before Docker is invoked. Verification passed
  `cargo fmt --check`, bundled-Python `py_compile`,
  `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo test -p xriq-api --lib -j 1`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T131859Z` with
  `indexer/postgres-api-mempool.json`,
  `indexer/postgres-server-mempool.json`, and
  `indexer/postgres-docker-live.json` showing `mempool_entries: 1`. Phase 1.1
  status was about `86%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed snapshot detail checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return
  `/api/v1/snapshots/current-indexed-chain` from the local Docker Postgres read
  model using the `xriq_snapshots` row populated by the indexer write-plan. The
  response keeps the product snapshot detail fields (`snapshot_name`,
  `snapshot_dir`, `current_height`, `latest_block_hash`, `state_root`,
  `block_count`, `transaction_count`, `audit_event_count`, and disabled
  export/import status) and adds local-only `environment`, `network`,
  `source: postgres-read-model`, `warning`, `read_model_warning`, and
  `read_only: true`. Without explicit Postgres flags,
  `/api/v1/snapshots/current-indexed-chain` still uses the default file-backed
  indexed snapshot path. Invalid snapshot names are rejected with
  `400 bad_request` before Docker is invoked, and missing snapshot rows return
  `404 not_found`. The live smoke now writes
  `indexer/postgres-api-snapshot-detail.json` and
  `indexer/postgres-server-snapshot-detail.json` in addition to the existing
  snapshot-list artifacts. Expected smoke detail has `snapshot_name:
  current-indexed-chain`, `snapshot_dir: read-model://current-indexed-chain`,
  height `1`, valid tip hash/state root, block count `1`, transaction count
  `1`, audit-event count `1`, and disabled export/import status. Verification
  passed `cargo fmt`, bundled-Python `py_compile`,
  `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo test -p xriq-api --lib -j 1`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T122858Z` with
  `indexer/postgres-api-snapshot-detail.json` and
  `indexer/postgres-server-snapshot-detail.json` showing `source:
  postgres-read-model`, `read_only: true`, the snapshot-catalog warning, and
  the expected read-only snapshot detail row. Phase 1.1 status was about
  `85%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed snapshot-list checkpoint:
  extended the indexer Postgres write-plan to populate `xriq_snapshots` with
  the current `current-indexed-chain` row, then extended
  `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/snapshots?limit=...` from the
  local Docker Postgres read model. The response keeps the product snapshot
  catalog fields (`environment`, `network`, `warning`, and `snapshots[]` with
  `snapshot_name`, `snapshot_dir`, `current_height`, `latest_block_hash`,
  `state_root`, counts, and disabled export/import status) and adds local-only
  `source: postgres-read-model`, `read_model_warning`, `read_only: true`,
  `limit`, and `next_cursor`. Without explicit Postgres flags,
  `/api/v1/snapshots` still uses the default file-backed indexed snapshot path,
  and `/api/v1/snapshots/current-indexed-chain` remains file-backed for now.
  Invalid `limit` values are rejected with `400 bad_request` before Docker is
  invoked. The live smoke now writes `indexer/postgres-api-snapshots.json` and
  `indexer/postgres-server-snapshots.json` in addition to the existing
  read-model/node/indexer/audit artifacts. Expected smoke snapshot catalog has
  one `current-indexed-chain` row with `snapshot_dir:
  read-model://current-indexed-chain`, height `1`, valid tip hash/state root,
  block count `1`, transaction count `1`, audit-event count `1`, and disabled
  export/import status. Verification passed `cargo fmt`, bundled-Python
  `py_compile`, `cargo test -p xriq-indexer --lib -j 1`,
  `cargo test -p xriq-indexer --bin xriq-indexer -j 1`,
  `cargo test -p xriq-api --lib -j 1`,
  `cargo test -p xriq-api --bin xriq-api -j 1`,
  `cargo clippy -p xriq-indexer -- -D warnings`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T120109Z` with
  `indexer/postgres-api-snapshots.json` and
  `indexer/postgres-server-snapshots.json` showing `source:
  postgres-read-model`, `read_only: true`, the snapshot-catalog warning, and
  the expected read-only snapshot row. Note: the first plain
  `cargo test -p xriq-indexer` attempt hit a Windows `LNK1104` generated
  test-exe file-lock; rerunning with narrower package targets passed. Phase
  1.1 status is now about `84%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed node status checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/admin/node/status` from the
  local Docker Postgres read model. The response preserves the product node
  status shape (`environment`, `service`, `status`, `mode`, `source`,
  `network`, `current_height`, `latest_block_hash`, `state_root`,
  `stored_blocks`, `pending_transactions`, `wallet_submit_status`, and
  `block_production_status`) and uses `source: postgres-read-model` in the
  existing source slot, plus local-only `read_only: true` and the existing
  no-mutation warning. Without explicit Postgres flags,
  `/api/v1/admin/node/status` still uses the default file-backed indexed
  snapshot plus pending-file path. In the current Docker live smoke, the
  Postgres node status reports `pending_transactions: 0` because the indexer
  write-plan does not yet populate `xriq_mempool_entries`; the default
  file-backed smoke route still reports the durable pending file count of `1`.
  The live smoke now writes `indexer/postgres-api-node-status.json` and
  `indexer/postgres-server-node-status.json` in addition to the existing
  read-model/indexer/audit artifacts. Expected smoke node status is
  `healthy`, mode `serve-readonly`, network `xriq-devnet`, latest height `1`,
  valid tip hash/state root, stored blocks `1`, wallet submit disabled, and
  block production disabled. Verification passed `cargo fmt`, bundled-Python
  `py_compile`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T112356Z` with
  `indexer/postgres-api-node-status.json` and
  `indexer/postgres-server-node-status.json` showing `source:
  postgres-read-model`, `read_only: true`, and the expected read-only node
  status. Phase 1.1 status is now about `83%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed indexer status checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/admin/indexer/status` from the
  local Docker Postgres read model. The response preserves the product indexer
  status shape (`environment`, `service`, `status`, `latest_indexed_height`,
  `latest_indexed_block_hash`, `lag_blocks`, and `last_run`) and adds
  local-only `source: postgres-read-model`, `read_only: true`, and the existing
  no-mutation warning. Without explicit Postgres flags,
  `/api/v1/admin/indexer/status` still uses the default file-backed indexed
  snapshot path. The live smoke now writes
  `indexer/postgres-api-indexer-status.json` and
  `indexer/postgres-server-indexer-status.json` in addition to the existing
  read-model/audit artifacts. Expected smoke indexer status is `current` with
  service `xriq-indexer`, latest indexed height `1`, latest block hash set,
  lag `0`, and a completed `private-devnet-replay-*` last run with one block
  and one transaction indexed. During verification, the first Docker smoke
  attempt exposed a real SQL CTE scoping bug; it was fixed by rendering the
  status SQL as one ordered key/value query. Verification then passed
  `cargo fmt`, bundled-Python `py_compile`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T111827Z` with
  `indexer/postgres-api-indexer-status.json` and
  `indexer/postgres-server-indexer-status.json` showing `source:
  postgres-read-model`, `read_only: true`, and the expected current/completed
  indexer status. Phase 1.1 status is now about `82%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed audit events checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/admin/audit-events?limit=...`
  from the local Docker Postgres read model. The response preserves the product
  audit-events list shape (`environment`, `network`, `limit`, `next_cursor`,
  `audit_events[]` with `event_id`, `actor`, `action`, `resource_type`,
  `resource_id`, and `environment`) and adds local-only `source:
  postgres-read-model`, `read_only: true`, and the existing no-mutation
  warning. Without explicit Postgres flags, `/api/v1/admin/audit-events` still
  uses the default file-backed indexed snapshot path. Invalid `limit` values
  are rejected with `400 bad_request` before Docker is invoked. The live smoke
  now writes `indexer/postgres-api-audit-events.json` and
  `indexer/postgres-server-audit-events.json` in addition to the existing
  wallet/history artifacts. Expected smoke audit event is the indexed block row
  with actor `xriq-indexer`, action `index_block`, resource type `block`,
  environment `private-devnet`, and the block hash as `resource_id`.
  Verification passed `cargo fmt`, bundled-Python `py_compile`,
  `cargo test -p xriq-api`, `cargo clippy -p xriq-api -- -D warnings`, and
  Docker live `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T110758Z` with
  `indexer/postgres-api-audit-events.json` and
  `indexer/postgres-server-audit-events.json` showing `source:
  postgres-read-model`, `read_only: true`, and the expected indexed block audit
  event. Phase 1.1 status is now about `81%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed wallet transaction-status checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return confirmed
  `/api/v1/wallet/transactions/{hash}/status` from the local Docker Postgres
  read model. The response preserves the compact wallet transaction-status
  product shape (`environment`, `network`, `tx_hash`, `status`,
  `block_height`, `block_hash`, `transaction_index`) and adds local-only
  `source: postgres-read-model`, `read_only: true`, and the existing
  no-mutation warning. Without explicit Postgres flags,
  `/api/v1/wallet/transactions/{hash}/status` still uses the default
  file-backed indexed snapshot plus pending-file path, so durable pending
  hashes continue to return null block fields through the default product API.
  Invalid hashes are rejected with `400 bad_request` before Docker is invoked;
  valid missing confirmed hashes return `404 not_found` from the Postgres read
  model. The live smoke now writes
  `indexer/postgres-api-wallet-transaction-status.json` and
  `indexer/postgres-server-wallet-transaction-status.json` in addition to the
  existing wallet account artifacts. Expected smoke wallet transaction status
  is the confirmed transfer hash with `status: "confirmed"`, block height `1`,
  transaction index `0`, and a valid block hash; it intentionally does not
  expose from/to/amount/fee/nonce fields. Verification passed `cargo fmt`,
  bundled-Python `py_compile`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T105956Z` with
  `indexer/postgres-api-wallet-transaction-status.json` and
  `indexer/postgres-server-wallet-transaction-status.json` showing `source:
  postgres-read-model`, `read_only: true`, and the expected confirmed status.
  Phase 1.1 status is now about `80%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed wallet balance checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return
  `/api/v1/wallet/accounts/{address}/balance` from the local Docker Postgres
  read model. The response preserves the wallet balance product shape
  (`environment`, `network`, `address`, `balance_base_units`, `nonce`,
  `height`, `state_root`) and adds local-only `source: postgres-read-model`,
  `read_only: true`, and the existing no-mutation warning. Without explicit
  Postgres flags, `/api/v1/wallet/accounts/{address}/balance` still uses the
  default file-backed indexed snapshot path. Invalid XRIQ addresses are
  rejected with `400 bad_request` before Docker is invoked; valid missing
  addresses return `404 not_found`. The live smoke now writes
  `indexer/postgres-api-wallet-balance.json` and
  `indexer/postgres-server-wallet-balance.json` in addition to the existing
  wallet account-list and wallet account-history artifacts. Expected smoke
  wallet balance is Alice with balance `"73"`, nonce `1`, latest height `1`,
  and a valid state root. Verification passed `cargo fmt`, bundled-Python
  `py_compile`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T104255Z` with
  `indexer/postgres-api-wallet-balance.json` and
  `indexer/postgres-server-wallet-balance.json` showing `source:
  postgres-read-model`, `read_only: true`, and the expected Alice balance.
  Phase 1.1 status is now about `79%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed wallet account list checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/wallet/accounts?limit=...`
  from the local Docker Postgres read model. The response preserves the
  account-list data shape used by the wallet list (`environment`, `network`,
  `limit`, `next_cursor`, `accounts`) and adds local-only `source:
  postgres-read-model`, `read_only: true`, and the existing no-mutation
  warning. Without explicit Postgres flags,
  `/api/v1/wallet/accounts?limit=...` still uses the default file-backed
  indexed snapshot path. Bad `limit` values are rejected with
  `400 bad_request` before Docker is invoked. The live smoke now writes
  `indexer/postgres-api-wallet-accounts.json` and
  `indexer/postgres-server-wallet-accounts.json` in addition to the existing
  wallet account-history artifacts. Expected smoke wallet account list has
  three accounts: Alice balance `"73"`, Bob balance `"25"`, and fee account
  balance `"2"`, all at latest height `1`. Verification passed `cargo fmt`,
  bundled-Python `py_compile`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T103032Z` with
  `indexer/postgres-api-wallet-accounts.json` and
  `indexer/postgres-server-wallet-accounts.json` showing `source:
  postgres-read-model`, `read_only: true`, and the expected account balances.
  Phase 1.1 status is now about `78%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed wallet account history checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return
  `/api/v1/wallet/accounts/{address}/history?limit=...` from the local Docker
  Postgres read model. The response preserves the wallet account-history
  product shape (`environment`, `network`, `address`, `limit`, `next_cursor`,
  `transactions`) and adds local-only `source: postgres-read-model`,
  `read_only: true`, and the existing no-mutation warning. Without explicit
  Postgres flags, `/api/v1/wallet/accounts/{address}/history?limit=...` still
  uses the default file-backed indexed snapshot path. Invalid XRIQ addresses
  and bad `limit` values are rejected with `400 bad_request` before Docker is
  invoked. The live smoke now writes
  `indexer/postgres-api-wallet-account-history.json` and
  `indexer/postgres-server-wallet-account-history.json` in addition to the
  status, overview, block, transaction-list, transaction-detail, account-list,
  account-detail, and account-history artifacts. Expected smoke wallet account
  history is Alice with one `sent` transaction, the confirmed transaction hash,
  block height `1`, transaction index `0`, `amount_base_units: "25"`, and
  `fee_base_units: "2"`. Verification passed `cargo fmt`, bundled-Python
  `py_compile`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T102048Z` with
  `indexer/postgres-api-wallet-account-history.json` and
  `indexer/postgres-server-wallet-account-history.json` showing `source:
  postgres-read-model`, `read_only: true`, and the Alice sent transaction.
  Phase 1.1 status is now about `77%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed account history checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return
  `/api/v1/accounts/{address}/transactions?limit=...` from the local Docker
  Postgres read model. The response preserves the normal product account
  history shape (`environment`, `network`, `address`, `limit`, `next_cursor`,
  `transactions`) and adds local-only `source: postgres-read-model`,
  `read_only: true`, and the existing no-mutation warning. Without explicit
  Postgres flags, `/api/v1/accounts/{address}/transactions?limit=...` still
  uses the default file-backed indexed snapshot path. Invalid XRIQ addresses
  and bad `limit` values are rejected with `400 bad_request` before Docker is
  invoked. The live smoke now writes `indexer/postgres-api-account-history.json`
  and `indexer/postgres-server-account-history.json` in addition to the status,
  overview, block, transaction-list, transaction-detail, account-list, and
  account-detail artifacts. Expected smoke account history is Alice with one
  `sent` transaction, the confirmed transaction hash, block height `1`,
  transaction index `0`, `amount_base_units: "25"`, and `fee_base_units: "2"`.
  Verification passed `cargo fmt`, bundled-Python `py_compile`,
  `cargo test -p xriq-api`, `cargo clippy -p xriq-api -- -D warnings`, and
  Docker live `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T101345Z` with
  `indexer/postgres-api-account-history.json` and
  `indexer/postgres-server-account-history.json` showing `source:
  postgres-read-model`, `read_only: true`, and the Alice sent transaction.
  Phase 1.1 status is now about `76%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed account detail checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/accounts/{address}` from the
  local Docker Postgres read model. The response preserves the normal product
  account-detail shape (`environment`, `network`, `address`,
  `balance_base_units`, `nonce`, `height`, `state_root`, `first_seen_height`,
  `last_seen_height`) and adds local-only `source: postgres-read-model`,
  `read_only: true`, and the existing no-mutation warning. Without explicit
  Postgres flags, `/api/v1/accounts/{address}` still uses the default
  file-backed indexed snapshot path. Invalid XRIQ addresses are rejected with
  `400 bad_request` before Docker is invoked; valid missing addresses return
  `404 not_found` from the Postgres read path. The live smoke now writes
  `indexer/postgres-api-account-detail.json` and
  `indexer/postgres-server-account-detail.json` in addition to the status,
  overview, block, transaction-list, transaction-detail, and account-list
  artifacts. Expected smoke account detail is Alice with
  `balance_base_units: "73"`, `nonce: 1`, latest indexed height `1`, valid
  state root, and integer first/last seen heights. Verification passed
  `cargo fmt`, bundled-Python `py_compile`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T095050Z` with
  `indexer/postgres-api-account-detail.json` and
  `indexer/postgres-server-account-detail.json` showing `source:
  postgres-read-model`, `read_only: true`, and the Alice account detail. Phase
  1.1 status is now about `75%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed accounts checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/accounts?limit=...` from the
  local Docker Postgres read model. The response preserves the normal product
  account-list shape (`environment`, `network`, `limit`, `next_cursor`,
  `accounts`) and adds local-only `source: postgres-read-model`, `read_only:
  true`, and the existing no-mutation warning. Without explicit Postgres
  flags, `/api/v1/accounts?limit=...` still uses the default file-backed
  indexed snapshot path. Bad `limit` values are rejected with `400
  bad_request` before Docker is invoked. The live smoke now writes
  `indexer/postgres-api-accounts.json` and
  `indexer/postgres-server-accounts.json` in addition to the status, overview,
  block, transaction-list, and transaction-detail artifacts. Expected smoke
  account state is Alice balance `"73"`, Bob balance `"25"`, fee account
  balance `"2"`, latest indexed height `1`, valid state roots, `limit: 5`, and
  `next_cursor: null`. Verification passed `cargo fmt`,
  bundled-Python `py_compile`, `cargo fmt --check`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, default
  `scripts/xriq_phase1_1_local_e2e_smoke.py`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T093810Z` with
  `indexer/postgres-api-accounts.json` and
  `indexer/postgres-server-accounts.json` showing `source:
  postgres-read-model`, `read_only: true`, the three indexed account balances,
  and `next_cursor: null`. Phase 1.1 status is now about `74%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed transaction detail checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/transactions/{tx_hash}` from
  the local Docker Postgres read model. The response preserves the normal
  product transaction-detail shape (`environment`, `network`, `tx_hash`,
  `block_height`, `block_hash`, `transaction_index`, `status`,
  `from_address`, `to_address`, `amount_base_units`, `fee_base_units`,
  `nonce`) and adds local-only `source: postgres-read-model`, `read_only:
  true`, and the existing no-mutation warning. Without explicit Postgres
  flags, `/api/v1/transactions/{tx_hash}` still uses the default file-backed
  indexed snapshot path. Invalid transaction hashes are rejected with `400
  bad_request` before Docker is invoked; valid missing hashes return `404
  not_found` from the Postgres read path. The live smoke now writes
  `indexer/postgres-api-transaction-detail.json` and
  `indexer/postgres-server-transaction-detail.json` in addition to the status,
  overview, block, and transaction-list artifacts. Expected smoke state is the
  same confirmed transfer used by the list route: block `1`, transaction index
  `0`, from `xriqdev1alice00000000000` to
  `xriqdev1bobbb00000000000`, `amount_base_units: "25"`,
  `fee_base_units: "2"`, and `nonce: 0`. Verification passed
  `cargo fmt --check`, bundled-Python `py_compile`,
  `cargo test -p xriq-api`, `cargo clippy -p xriq-api -- -D warnings`,
  default `scripts/xriq_phase1_1_local_e2e_smoke.py`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T030134Z` with
  `indexer/postgres-api-transaction-detail.json` and
  `indexer/postgres-server-transaction-detail.json` showing
  `source: postgres-read-model`, `read_only: true`, and the confirmed
  transaction detail. Phase 1.1 status is now about `73%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed transactions checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/transactions?limit=...` from
  the local Docker Postgres read model. The response preserves the normal
  product transaction-list shape (`environment`, `network`, `limit`,
  `next_cursor`, `transactions`) and adds local-only `source:
  postgres-read-model`, `read_only: true`, and the existing no-mutation
  warning. Without explicit Postgres flags, `/api/v1/transactions` still uses
  the default file-backed indexed snapshot path. Bad `limit` values are
  rejected with `400 bad_request` before Docker is invoked. The live smoke now
  writes `indexer/postgres-api-transactions.json` and
  `indexer/postgres-server-transactions.json` in addition to the existing
  status, overview, and blocks artifacts. Expected smoke state is one
  confirmed transaction in block `1`, from
  `xriqdev1alice00000000000` to `xriqdev1bobbb00000000000`,
  `amount_base_units: "25"`, `fee_base_units: "2"`, `nonce: 0`,
  `transaction_index: 0`, `next_cursor: null`, and `limit: 5`. Verification
  passed `cargo fmt --check`, bundled-Python `py_compile`,
  `cargo test -p xriq-api`, `cargo clippy -p xriq-api -- -D warnings`, default
  `scripts/xriq_phase1_1_local_e2e_smoke.py`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`,
  producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T025310Z` with
  `indexer/postgres-api-transactions.json` and
  `indexer/postgres-server-transactions.json` showing
  `source: postgres-read-model`, `read_only: true`, `limit: 5`,
  `next_cursor: null`, and one confirmed transfer. Phase 1.1 status is now
  about `72%` overall.
- Previous native XRIQ Phase 1.1 Postgres-backed blocks checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/blocks?limit=...` from the
  local Docker Postgres read model. The response preserves the normal product
  block-list shape (`environment`, `network`, `limit`, `next_cursor`,
  `blocks`) and adds local-only `source: postgres-read-model`, `read_only:
  true`, and the existing no-mutation warning. Without explicit Postgres
  flags, `/api/v1/blocks` still uses the default file-backed indexed snapshot
  path. Bad `limit` values are rejected with `400 bad_request` before Docker is
  invoked. The live smoke now writes `indexer/postgres-api-blocks.json` and
  `indexer/postgres-server-blocks.json` in addition to the existing status and
  overview artifacts. Expected smoke state is one block at height `1`, one
  confirmed transaction in that block, valid block/state/transactions hashes,
  `next_cursor: null`, and `limit: 5`. Verification passed `cargo fmt --check`,
  bundled-Python `py_compile`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, default
  `scripts/xriq_phase1_1_local_e2e_smoke.py`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T024730Z` with
  `indexer/postgres-api-blocks.json` and `indexer/postgres-server-blocks.json`
  showing `source: postgres-read-model`, `read_only: true`, `limit: 5`,
  `next_cursor: null`, and one block at height `1`. Phase 1.1 status is now
  about `71%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed explorer overview checkpoint:
  extended `xriq-api request-postgres` and explicitly Postgres-enabled
  `xriq-api serve-readonly` to return `/api/v1/explorer/overview` from the
  local Docker Postgres read model. The response preserves the normal product
  overview shape (`environment`, `network`, `chain`, `indexer`, `totals`) and
  adds local-only `source: postgres-read-model`, `read_only: true`, and the
  existing no-mutation warning. Without explicit Postgres flags,
  `/api/v1/explorer/overview` still uses the default file-backed indexed
  snapshot path. The live smoke now writes
  `indexer/postgres-api-explorer-overview.json` and
  `indexer/postgres-server-explorer-overview.json`, both showing height `1`, 1
  stored block, 1 confirmed transaction, 3 indexed accounts, 0 Postgres
  mempool entries, and indexer status `completed`. Verification passed
  `cargo fmt`, bundled-Python `py_compile`,
  `cargo test -p xriq-api`, default
  `scripts/xriq_phase1_1_local_e2e_smoke.py`, and Docker live
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T023647Z` with no skipped
  checks. A stale local `xriq-api.exe` process was stopped because it held the
  Windows test binary during linking. Phase 1.1 status is now about `70%`
  overall.
- Latest native XRIQ Phase 1.1 Postgres-enabled Admin UI smoke checkpoint:
  added `npm.cmd run check:postgres-ui`, a local UI logic smoke that uses Vite
  SSR to import the same `postgresReadModelRows` mapping used by the Admin
  Status panel. The script calls `/api/v1/admin/postgres/read-model-status`,
  supports expected `disabled` and `available` states, validates row values,
  and can write a JSON artifact without adding Playwright/jsdom/vitest
  dependencies. `scripts/xriq_phase1_1_local_e2e_smoke.py
  --postgres-docker-live` now runs this UI smoke while a temporary
  Postgres-enabled `serve-readonly` API is up, expecting database
  `xriq_phase1_1_smoke`, 1 block, 1 transaction, 3 accounts, 2 account-history
  rows, and 1 audit event. Verification passed `npm.cmd run check`,
  `npx.cmd tsc -b`, `npm.cmd run build` outside the sandbox after the known
  Windows Vite access-denied sandbox issue, bundled-Python `py_compile`, standalone disabled
  `npm.cmd run check:postgres-ui -- --base-url http://127.0.0.1:8090 --expect disabled`,
  and Docker live `scripts/xriq_phase1_1_local_e2e_smoke.py
  --postgres-docker-live`, producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T022858Z` with
  `indexer/postgres-admin-ui-read-model-status.json` showing `Status:
  available`, `Source: postgres-read-model`, `Database:
  xriq_phase1_1_smoke`, `Height: 1`, `Blocks: 1`, `Transactions: 1`,
  `Accounts: 3`, `Account History: 2`, and `Audit Events: 1`. Phase 1.1
  status is now about `69%` overall.
- Latest native XRIQ Phase 1.1 Admin UI Postgres status checkpoint:
  extended the React + TypeScript Admin Status panel with a read-only
  `Postgres Read Model` block. The UI calls
  `/api/v1/admin/postgres/read-model-status` separately from the main snapshot
  load so normal explorer/admin loading is not blocked when Postgres is not
  configured. A `404 not_found` response is treated as `disabled`; a configured
  server response shows source, route, database, indexer status, latest height,
  counts, read-only flag, and any error state without signing, submission,
  schema mutation, or credential display. Verification passed `npm.cmd run
  check`, `npx.cmd tsc -b`, `npm.cmd run build` outside the sandbox after the
  sandboxed Vite build hit a Windows access-denied issue, and a Browser DOM
  smoke against the normal file-backed API confirming `Admin Status`,
  `Postgres Read Model`, and `disabled` were visible. Screenshot capture timed
  out in the in-app browser, so the visual check used DOM state. The default
  local Phase 1.1 smoke also passed, producing artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T021412Z` with only the
  optional Postgres Docker live smoke skipped. Phase 1.1 status is now about
  `68%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed read-only server checkpoint:
  extended `xriq-api serve-readonly` with explicit
  `--postgres-docker-container <container> --postgres-database <database>`
  flags. When both flags are present, the local read-only HTTP server exposes
  `/api/v1/admin/postgres/read-model-status` from the Docker Postgres read
  model and returns the same contract-style JSON as `request-postgres`. When
  the flags are absent, the endpoint remains disabled with `404 not_found` and
  all normal file-backed `serve-readonly` routes continue unchanged. The
  Phase 1.1 live smoke now starts a temporary local `serve-readonly` server
  with those flags, calls the Postgres status endpoint over HTTP, validates the
  same table counts and latest height, and writes
  `indexer/postgres-server-read-model-status.json`. Verification passed
  `cargo fmt --check`, `cargo test -p xriq-api`, `cargo clippy -p xriq-api -- -D warnings`,
  bundled-Python `py_compile`, and
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T020202Z` with no skipped
  checks. Phase 1.1 status is now about `67%` overall.
- Latest native XRIQ Phase 1.1 Postgres-backed API read path checkpoint:
  added `xriq-api request-postgres`, an explicit local-only Docker Postgres
  read-model request command for
  `/api/v1/admin/postgres/read-model-status`. It queries the dedicated local
  Postgres read model through `docker exec ... psql`, returns contract-style
  JSON with `environment: private-devnet`, `source: postgres-read-model`,
  `read_only: true`, latest height/hash, indexer status, and table counts, and
  leaves the default file-backed `xriq-api request` and `serve-readonly` paths
  unchanged. The Phase 1.1 live smoke now validates this command after applying
  the generated SQL to `xriq_phase1_1_smoke` and writes
  `indexer/postgres-api-read-model-status.json`. Verification passed
  `cargo test -p xriq-api`, bundled-Python `py_compile`, and
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T015522Z` with no skipped
  checks. Phase 1.1 status is now about `66%` overall.
- Latest native XRIQ Phase 1.1 optional Postgres live-smoke checkpoint:
  extended `scripts/xriq_phase1_1_local_e2e_smoke.py` with an explicit
  `--postgres-docker-live` mode. The default smoke remains CPU-only,
  socketless, cloudless, and dry-run-only. When explicitly enabled, the smoke
  starts/uses the local root Compose `postgres` service, waits for the
  `xriq-postgres` health check, creates or reuses a dedicated
  `xriq_phase1_1_smoke` database, resets only that database's `public` schema,
  applies `xriq/db/schema.sql`, applies the generated indexer SQL write plan
  through container-local `psql`, verifies table counts for blocks,
  transactions, accounts, balances, account transaction history, audit events,
  indexer runs, and latest height, and writes
  `indexer/postgres-docker-live.json` under the smoke artifact directory. The
  smoke summary now also records all indexer artifact paths. This does not
  require host `psql`, GCP, Vast/GPU resources, credentials, public/DEX
  behavior, or production data. After Docker Desktop was started, live
  verification passed with
  `scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live`, producing
  artifact directory
  `xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T015003Z`, confirming
  `xriq-postgres` healthy and indexed counts of 1 block, 1 transaction, 3
  accounts, 3 balances, 2 account-history rows, 1 audit event, 1 indexer run,
  and latest height 1. Phase 1.1 status is now about `65%` overall.
- Latest native XRIQ Phase 1.1 indexer dry-run smoke checkpoint: extended
  `scripts/xriq_phase1_1_local_e2e_smoke.py` so the one-command local Phase
  1.1 smoke now builds `xriq-indexer`, replays the generated chain through the
  indexer, writes `indexer/replay.json`, writes the idempotent
  `indexer/write-plan.sql`, validates `apply-postgres --dry-run true`, and
  validates `verify-postgres --dry-run true` before running the existing
  product API route checks. This is CPU-only and does not require Docker,
  `psql`, a live PostgreSQL service, GCP, Vast/GPU resources, or credentials.
  Verification passed the bundled-Python
  `scripts/xriq_phase1_1_local_e2e_smoke.py`, including 26 product API routes,
  3 wallet draft-preview failure routes, and the new indexer replay/PostgreSQL
  dry-run artifact checks. Phase 1.1 status is now about `63%` overall.
- Latest native XRIQ Phase 1.1 wallet API-history UI checkpoint: extended the
  preview-only wallet shell with a read-only Wallet API History panel backed by
  `/api/v1/wallet/accounts/{address}/history?limit=5` for the selected local
  account. The panel shows confirmed wallet history rows from the product
  wallet API alongside the existing activity/status panels, and the local
  end-to-end smoke now explicitly verifies the wallet history product route.
  This remains inspection-only: no submit/send/signing/private-key/persistence
  behavior, no public/DEX behavior, no GCP/Vast/GPU resources, and no
  credential changes were added. Verification passed `npm.cmd run check`,
  `npm.cmd run build` after rerunning outside the sandbox because Vite could
  not read a parent directory inside the sandbox, the CPU-only
  `scripts/xriq_phase1_1_local_e2e_smoke.py` with 26 product routes checked,
  and a browser smoke at `http://127.0.0.1:5173` showing API-backed wallet
  history, confirmed plus pending activity/status, disabled submit/send
  controls, and no console errors. Temporary local servers were stopped and
  logs were removed. Phase 1.1 status is now about `62%` overall.
- Latest native XRIQ Phase 1.1 wallet API-status UI checkpoint: extended the
  read-only Wallet Activity panel in `xriq/apps/explorer-ui/src/wallet.tsx` so
  the selected confirmed or pending activity row calls the existing
  `/api/v1/wallet/transactions/{hash}/status` product route and displays
  API-backed status, block height, block hash, transaction index, and preview
  warning. This remains an inspection-only wallet UX refinement: no
  submit/send/signing/private-key/persistence behavior, no public/DEX behavior,
  no GCP/Vast/GPU resources, and no credential changes were added.
  Verification passed `npm.cmd run check`, `npm.cmd run build` after rerunning
  outside the sandbox because Vite could not read a parent directory inside the
  sandbox, the CPU-only `scripts/xriq_phase1_1_local_e2e_smoke.py`, and a
  browser smoke at `http://127.0.0.1:5173` showing the API-backed pending
  status, confirmed plus pending activity, disabled submit/send controls, and
  no console errors. Temporary local servers were stopped and logs were removed.
  Phase 1.1 status is now about `61%` overall.
- Latest native XRIQ Phase 1.1 wallet activity UI checkpoint: extended
  `xriq/apps/explorer-ui/src/wallet.tsx` so the existing preview-only
  `WalletShell` also renders a read-only Wallet Activity panel for the selected
  local account. The panel merges confirmed transaction rows from the product
  transaction read model with durable pending rows from the mempool snapshot,
  marks each row as confirmed or pending, and shows selected status, direction,
  counterparty, amount, fee, nonce, pending-block, and transaction-index detail.
  It remains inspection-only: no submit/send/signing/private-key/persistence
  behavior, no public/DEX behavior, no GCP/Vast/GPU resources, and no
  credential changes were added. Verification passed `npm.cmd run check`,
  `npm.cmd run build` after rerunning outside the sandbox because Vite could
  not read a parent directory inside the sandbox, the CPU-only
  `scripts/xriq_phase1_1_local_e2e_smoke.py`, and a browser smoke at
  `http://127.0.0.1:5173` showing confirmed plus pending activity, selected
  pending detail, disabled submit/send controls, and no console errors. Phase
  1.1 status is now about `60%` overall.
- Latest native XRIQ Phase 1.1 local end-to-end smoke checkpoint: added
  `scripts/xriq_phase1_1_local_e2e_smoke.py`, a CPU-only one-command local
  smoke for the current Phase 1.1 product surface. It runs the Phase 1.1
  contract/schema/fixture checker, runs the React explorer UI static guardrail,
  builds `xriq-node`, `xriq-wallet`, and `xriq-api`, creates a deterministic
  confirmed private-devnet transfer plus one durable pending wallet transfer,
  and verifies 26 product API routes covering health, network, explorer,
  blocks, transactions, accounts, mempool, wallet status/balance/transaction
  status/history/draft preview, admin node/indexer/audit events, snapshot
  catalog/detail, and ISO 20022 preview responses. Latest extension added three wallet
  draft-preview failure checks: combined domain-validation errors, over-balance
  debit validation, and malformed amount bad-request handling. The React UI
  static guardrail now also requires visible local wallet validation messages
  for same-recipient, amount, fee, nonce, expiry, and over-balance failures
  before any real submit/send control is added. It opens no socket, starts no
  browser, uses no GCP/Vast/GPU resources, does not mutate public/DEX behavior,
  and changes no credentials. Run it locally with the bundled or system Python:
  `python scripts/xriq_phase1_1_local_e2e_smoke.py`. Phase 1.1 status is now
  about `59%` overall.
- Latest native XRIQ Phase 1.1 audit events UI checkpoint: added
  `xriq/apps/explorer-ui/src/audit.tsx` and wired it into the local React
  explorer. The new read-only Audit Events panel renders indexed audit rows
  already loaded from `/api/v1/admin/audit-events?limit=5`, lets the operator
  select an event, and shows actor/action/resource/environment detail. It does
  not add audit mutation, admin mutation, signing, submission, or block
  production behavior. Static UI guardrails now require the audit panel file
  and markers. Phase 1.1 status is now about `57%` overall. No GCP resources
  were provisioned, no Vast/GPU work was used, no public/DEX behavior was
  added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 snapshot catalog UI checkpoint: added
  `xriq/apps/explorer-ui/src/snapshots.tsx` and wired it into the local React
  explorer. The new read-only Snapshot Catalog panel lists
  `/api/v1/snapshots` entries, fetches `/api/v1/snapshots/{name}` for selected
  snapshot detail, and displays snapshot source, height, tip hash, state root,
  and export/import statuses. Export/import controls remain explicitly
  disabled and no mutating snapshot/admin behavior was added. Static UI
  guardrails now require the snapshot panel file and markers. Phase 1.1 status
  is now about `56%` overall. No GCP resources were provisioned, no Vast/GPU
  work was used, no public/DEX behavior was added, and no credentials were
  changed.
- Latest native XRIQ Phase 1.1 pending transactions explorer checkpoint:
  added `xriq/apps/explorer-ui/src/mempool.tsx` and wired it into the local
  React explorer. The new read-only Pending Transactions panel renders durable
  pending-file entries from `/api/v1/mempool`, lets the operator select a
  pending hash, and fetches `/api/v1/wallet/transactions/{hash}/status` to show
  pending wallet status plus null block/index fields. It does not sign, submit,
  produce blocks, persist secrets, or add mutating controls. Static UI
  guardrails now require the mempool panel file and markers. Phase 1.1 status
  is now about `55%` overall. No GCP resources were provisioned, no Vast/GPU
  work was used, no public/DEX behavior was added, and no credentials were
  changed.
- Latest native XRIQ Phase 1.1 pending wallet-status UI checkpoint: extended
  `xriq/apps/explorer-ui` so the read-only Admin Status panel fetches
  `/api/v1/wallet/transactions/{hash}/status` for the first pending mempool
  hash when the product API is started with `--pending-file`. The panel now
  shows the product wallet status plus null block/index fields for a durable
  pending hash, without signing, submitting, block production, private keys, or
  mutating admin controls. Static UI guardrails now require the wallet
  transaction-status route and markers. Phase 1.1 status is now about `54%`
  overall. No GCP resources were provisioned, no Vast/GPU work was used, no
  public/DEX behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 contract-artifact checkpoint: added
  `xriq/db/schema.sql`, `xriq/fixtures/phase1_1/`, and
  `scripts/xriq_phase1_1_contract_check.py`. The schema defines the first
  PostgreSQL read-model tables for blocks, transactions, accounts, balances,
  account transaction history, mempool entries, snapshots, indexer runs, audit
  events, and ISO 20022 mapped messages. The fixture set adds 14 stable
  product-facing JSON examples for explorer, wallet, admin, and ISO 20022
  mapping surfaces. The local checker validates the required schema tables,
  parses fixtures, requires `environment: "private-devnet"`, verifies selected
  hash and integer base-unit string shapes, requires ISO mappings to declare
  `not_certified: true`, and rejects sensitive-looking key/seed fields. Local
  verification passed bundled Python syntax compilation and
  `python scripts/xriq_phase1_1_contract_check.py`, reporting 10 tables and 14
  fixtures. Phase 1.1 status is now about `17%` overall. No GCP resources were
  provisioned, no Rust behavior changed, and no credentials were changed.
- Latest native XRIQ Phase 1.1 indexer scaffold checkpoint: added
  `xriq/crates/xriq-indexer` and registered it in the Rust workspace. The crate
  builds a PostgreSQL-facing in-memory read model from the existing
  file-backed chain/ledger state for blocks, confirmed transactions, accounts,
  final balances, account transaction history, and deterministic audit events.
  It includes idempotent replay behavior and conflict detection for a different
  block at an already-indexed height. Focused verification passed with
  `cargo test -p xriq-indexer` (`4` tests). Phase 1.1 status is now about
  `20%` overall. No GCP resources were provisioned, no database was required,
  no public/DEX behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 indexer replay-command checkpoint: extended
  `xriq/crates/xriq-indexer` with canonical private-devnet chain replay
  validation and a local CLI command:
  `cargo run -p xriq-indexer -- replay --chain-file <path> --alice-balance 100 --format json`.
  The command opens a file-backed chain, replays and validates canonical block
  hashes, parent headers, producer, transaction signatures, transaction root,
  state root, and block signature, then emits stable JSON/text read-model
  counts for blocks, confirmed transactions, accounts, balances, account
  transaction history, and audit events. Focused verification passed with
  `cargo test -p xriq-indexer` (`5` tests). CLI smoke passed by producing a
  fresh transfer block with `xriq-node` and replaying it with `xriq-indexer`,
  reporting 1 block, 1 transaction, 3 accounts, 3 account balances, 2 account
  transaction records, and 1 audit event. Phase 1.1 status is now about `21%`
  overall. No GCP resources were provisioned, no database was required, no
  public/DEX behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 PostgreSQL write-plan checkpoint: added
  `xriq/crates/xriq-indexer/src/postgres.rs` and extended the replay CLI with
  `--format sql`. The write plan renders a local, reviewable PostgreSQL
  transaction with `INSERT ... ON CONFLICT` statements for `xriq_indexer_runs`,
  `xriq_accounts`, `xriq_blocks`, `xriq_transactions`,
  `xriq_account_balances`, `xriq_account_transactions`, and
  `xriq_audit_events`, ordered so foreign-key dependencies are respected. The
  plan validates money-like values as integer numeric strings and escapes SQL
  text literals. Verification passed with `cargo test -p xriq-indexer` (`8`
  tests), `cargo clippy -p xriq-indexer -- -D warnings`, and a CLI smoke:
  `cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format sql`.
  Phase 1.1 status is now about `22%` overall. No GCP resources were
  provisioned, no live database was required, no public/DEX behavior was added,
  and no credentials were changed.
- Latest native XRIQ Phase 1.1 PostgreSQL apply-path checkpoint: extended
  `xriq-indexer` with `apply-postgres`. The command defaults to `--dry-run
  true`, reads `db/schema.sql`, replays the chain, builds the SQL write plan,
  and reports whether schema/write-plan application would occur without
  invoking `psql` or requiring a database URL. Actual application requires an
  explicit `--dry-run false` and a database URL from `XRIQ_POSTGRES_URL`,
  `--database-url-env`, or `--database-url`; it invokes local `psql` for schema
  SQL and then the generated write plan. Dry-run smoke passed with:
  `cargo run -p xriq-indexer -- apply-postgres --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --schema-file db/schema.sql --dry-run true`,
  reporting current_height=1, blocks_indexed=1, transactions_indexed=1,
  write_plan_statements=12, schema_applied=false, write_plan_applied=false.
  Phase 1.1 status is now about `23%` overall. No GCP resources were
  provisioned, no live database was required, no public/DEX behavior was added,
  and no credentials were changed.
- Latest native XRIQ Phase 1.1 local PostgreSQL verification checkpoint: added
  an optional root Compose `postgres` service for the local-only XRIQ read
  model and extended `xriq-indexer` with `verify-postgres`. The verification
  command defaults to `--dry-run true`, reports the database URL source without
  printing secrets, and only invokes local `psql` when `--dry-run false` is
  explicit. The live query reports counts for blocks, transactions, accounts,
  account balances, account transaction history, audit events, indexer runs,
  and latest indexed height. Recommended local flow:
  `docker compose up -d postgres`, set
  `XRIQ_POSTGRES_URL=postgresql://xriq:xriq-local-dev-password@localhost:5433/xriq_private_dev`,
  run `apply-postgres --dry-run false`, then run
  `verify-postgres --database-url-env XRIQ_POSTGRES_URL --dry-run false`.
  Local verification for this checkpoint passed `docker compose config`,
  `cargo test -p xriq-indexer`, `cargo clippy -p xriq-indexer -- -D warnings`,
  `cargo run -p xriq-indexer -- apply-postgres ... --dry-run true`, and
  `cargo run -p xriq-indexer -- verify-postgres --dry-run true`. Live local DB
  apply/verify was not run because Docker Desktop was not running and host
  `psql` was not installed on the workstation. Phase 1.1 status is now about
  `24%` overall. No GCP resources were provisioned, no public/DEX behavior was
  added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 Rust API service-boundary checkpoint: added
  `xriq/crates/xriq-api` and registered it in the Rust workspace. This crate is
  dependency-light and does not start an HTTP server yet; it defines
  product-facing private-devnet response models and read-only service methods
  over `IndexedChainSnapshot` for health, version, network metadata, explorer
  overview, block list/detail, transaction list/detail, account list/detail,
  account history, and admin indexer status. Focused verification passed with
  `cargo test -p xriq-api` and `cargo clippy -p xriq-api -- -D warnings`.
  Phase 1.1 status is now about `26%` overall. No GCP resources were
  provisioned, no public/DEX behavior was added, no live HTTP API was started,
  and no credentials were changed.
- Latest native XRIQ Phase 1.1 ISO 20022 adapter checkpoint: added
  `xriq/crates/xriq-iso20022` and registered it in the Rust workspace. This
  crate maps private-devnet `xriq-api` transaction/account-history response
  models into payment initiation preview, payment status preview, and account
  statement preview structs. It always carries `not_certified: true`,
  `private-devnet`, `xriq-iso20022-preview-v1`, and explicit unsupported-field
  lists for bank/SWIFT/fiat/legal-entity data XRIQ does not have. Focused
  verification passed with `cargo test -p xriq-iso20022` and
  `cargo clippy -p xriq-iso20022 -- -D warnings`. Phase 1.1 status is now
  about `28%` overall. No GCP resources were provisioned, no public/DEX
  behavior was added, no certification/payment-network claim was added, and no
  credentials were changed.
- Latest native XRIQ Phase 1.1 product API route/render checkpoint: extended
  `xriq/crates/xriq-api` with dependency-light GET route/render behavior for
  `/api/v1/health`, `/api/v1/version`, `/api/v1/network`,
  `/api/v1/explorer/overview`, block list/detail, transaction list/detail,
  account list/detail, account transaction history, and admin indexer status.
  This renders contract-shaped JSON and HTTP response strings from the
  existing `IndexedChainSnapshot` read model, but it does not bind a live
  socket yet. Focused verification passed with `cargo test -p xriq-api` and
  `cargo clippy -p xriq-api -- -D warnings`; the first parallel test attempt
  hit a transient Windows linker lock while clippy was running, and the serial
  rerun passed. Phase 1.1 status is now about `30%` overall. No GCP resources
  were provisioned, no public/DEX behavior was added, no live server was
  started, and no credentials were changed.
- Latest native XRIQ Phase 1.1 product API read-only server checkpoint:
  extended `xriq/crates/xriq-api` with a binary CLI. `xriq-api request`
  replays an existing file-backed private-devnet chain into the indexed read
  model and renders one product API route without opening a socket.
  `xriq-api serve-readonly` exposes the same GET-only `/api/v1/...` route
  layer over a local socket, defaulting to `127.0.0.1:8090`; it requires an
  existing chain file and remains private-devnet/read-only. Smoke commands:
  `cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/health`,
  `cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/blocks/1`,
  plus a controlled localhost `serve-readonly` smoke on `127.0.0.1:18090`
  returning `200` for `/api/v1/health`. Verification passed with
  `cargo fmt --check`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, `cargo test --workspace -j 1`,
  `cargo clippy --workspace -- -D warnings`, and `git diff --check`.
  Phase 1.1 status is now about `32%` overall. No GCP resources were
  provisioned, no public/DEX behavior was added, no credentials were changed,
  and the server was stopped after smoke testing.
- Latest native XRIQ Phase 1.1 explorer UI shell checkpoint: added
  `xriq/apps/explorer-ui`, a Vite React + TypeScript local private-devnet
  explorer shell. It includes a typed `src/api.ts` client for
  `/api/v1/health`, `/api/v1/network`, `/api/v1/explorer/overview`,
  `/api/v1/blocks`, `/api/v1/transactions`, `/api/v1/accounts`, and
  `/api/v1/admin/indexer/status`; the default dev flow uses Vite's same-origin
  `/api` proxy to `http://127.0.0.1:8090` instead of widening the Rust API CORS
  surface. The UI renders health, height/totals, network metadata, latest
  blocks, latest transactions, accounts, and a small topology visual. Added
  `npm.cmd run check` static guard, `npm.cmd run build` production build path,
  `.gitignore` entries for `node_modules`, `dist`, and `*.tsbuildinfo`, plus
  README/runbook instructions. Verification passed with
  `npm.cmd run check`, `npm.cmd run build`, live local `xriq-api
  serve-readonly` on `127.0.0.1:8090`, live Vite dev server on
  `127.0.0.1:5173`, and browser verification showing private-devnet data:
  height=1, blocks=1, transactions=1, accounts=3. Phase 1.1 status is now
  about `34%` overall. No GCP resources were provisioned, no public/DEX
  behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 explorer detail-panel checkpoint: extended
  `xriq/apps/explorer-ui` with typed detail fetches for
  `/api/v1/blocks/{height-or-hash}`, `/api/v1/transactions/{hash}`,
  `/api/v1/accounts/{address}`, and
  `/api/v1/accounts/{address}/transactions?limit=5`. The UI now has selectable
  block, transaction, and account rows plus read-only detail panels for block
  hashes/roots/embedded transactions, transaction status/from/to/amount/fee,
  account balance/nonce/state root, and account transaction history. The
  static checker now requires those detail routes and UI markers. Verification
  passed with `npm.cmd run check`, `npm.cmd run build`, browser verification
  against live local `xriq-api` and Vite dev servers, no browser console
  errors, `cargo test -p xriq-api`, and `git diff --check`. Phase 1.1 status
  is now about `36%` overall. No GCP resources were provisioned, no public/DEX
  behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 wallet preview UI checkpoint: extended
  `xriq/apps/explorer-ui` with a `WalletShell` component that reuses the
  indexed account list from the product API. The panel selects a local
  private-devnet sender, shows balance/debit/remaining math, validates amount,
  fee, nonce, expiry, and recipient fields, and renders a deterministic
  `xriq-wallet-transfer-preview-v1` JSON draft with
  `private-devnet-preview-only-no-signing-no-submit` and `mutation: "none"`.
  Static guardrails require the wallet preview markers and reject client-side
  submit/send routes plus private-key/seed fields. Verification passed with
  `npm.cmd run check`, `npm.cmd run build`, `cargo test -p xriq-api`, and
  browser verification against live local `xriq-api` plus Vite servers showing
  the wallet preview/version/warning/mutation markers with no console errors.
  Phase 1.1 status is now about `38%` overall. No GCP resources were
  provisioned, no public/DEX behavior was added, no signing/submission/custody
  behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 wallet product API checkpoint: extended
  `xriq/crates/xriq-api` with private-devnet wallet read/preview routes over
  the indexed read model: `GET /api/v1/wallet/status`,
  `GET /api/v1/wallet/accounts`, `GET /api/v1/wallet/accounts/{address}/balance`,
  `GET /api/v1/wallet/accounts/{address}/history`,
  `GET /api/v1/wallet/transactions/{hash}/status`, and
  `GET /api/v1/wallet/transfers/draft-preview?...`. The draft-preview route
  validates sender, recipient, amount, fee, nonce, expiry, and balance/debit
  math, returns `private-devnet-preview-only-no-signing-no-submit`, and always
  reports `mutation: "none"`. It does not sign, submit, persist pending state,
  or manage private keys; POST draft/submit/send remain deferred. Verification
  passed with `cargo fmt`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, and CLI request smokes for
  `/api/v1/wallet/status` and `/api/v1/wallet/transfers/draft-preview?...`.
  Phase 1.1 status is now about `40%` overall. No GCP resources were
  provisioned, no public/DEX behavior was added, no signing/submission/custody
  behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 API-backed wallet UI checkpoint: extended
  `xriq/apps/explorer-ui` so the wallet preview shell calls the product wallet
  APIs through the existing same-origin `/api` proxy. `src/api.ts` now includes
  typed clients for `/api/v1/wallet/status`,
  `/api/v1/wallet/accounts/{address}/balance`, and
  `/api/v1/wallet/transfers/draft-preview`. `WalletShell` keeps the local
  preview as a draft display but adds an explicit `Check Preview` action that
  renders server-side validation and balance/debit/remaining results from
  `xriq-api`, including `mutation: "none"`. Static UI checks now require the
  wallet API routes and reject direct wallet submit/send/private-key behavior.
  Verification passed with `npm.cmd run check`, `npm.cmd run build`,
  `cargo fmt --check`, `cargo test -p xriq-api`, and browser verification
  against live local `xriq-api` plus Vite servers showing API validation,
  `available_base_units`, `mutation: "none"`, `no-submit`, and `no-send` with
  no console errors. Phase 1.1 status is now about `42%` overall. No GCP
  resources were provisioned, no public/DEX behavior was added, no
  signing/submission/custody behavior was added, and no credentials were
  changed.
- Latest native XRIQ Phase 1.1 read-only admin status UI checkpoint: extended
  `xriq/apps/explorer-ui` with an `AdminStatusPanel` that reads the existing
  product API snapshot and displays network environment/height/tip/state root,
  indexer `current` plus last-run `completed` status/counts, and wallet
  warning/account/pending/capability state. `src/api.ts` now includes
  `/api/v1/wallet/status` in the main explorer snapshot so the admin panel can
  show draft/submit/send flags from the server contract. Static guardrails now
  require admin status markers and still reject public-market wording in UI
  source. Verification passed with `npm.cmd run check`, `npm.cmd run build`,
  and browser verification against live local `xriq-api` plus Vite servers
  showing `Admin Status`, `current`, `completed`, wallet warning, draft enabled,
  and submit/send disabled with no console errors. Phase 1.1 status is now
  about `44%` overall. No GCP resources were provisioned, no public/DEX behavior
  was added, no mutating admin controls were added, no signing/submission
  behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 read-only admin snapshot/audit checkpoint:
  extended `xriq-api` with GET-only `/api/v1/admin/audit-events`,
  `/api/v1/snapshots`, and `/api/v1/snapshots/current-indexed-chain` routes.
  These expose deterministic indexed audit events and a read-only in-memory
  snapshot catalog with export/import status explicitly `disabled`; they do not
  perform snapshot export/import and do not add POST admin behavior. Extended
  `xriq/apps/explorer-ui` so `AdminStatusPanel` renders Snapshot Catalog and
  Audit Events sections from the same-origin product API proxy. Static
  guardrails now require the new admin routes/markers and continue rejecting
  public-market wording in UI source. Verification passed with `cargo fmt`,
  `cargo test -p xriq-api`, `cargo clippy -p xriq-api -- -D warnings`,
  `npm.cmd run check`, `npm.cmd run build`, CLI request smokes for
  `/api/v1/admin/audit-events` and `/api/v1/snapshots`, and browser
  verification against live local `xriq-api` plus Vite servers showing
  `Snapshot Catalog`, `Audit Events`, `current-indexed-chain`, `index_block`,
  and export/import disabled. Phase 1.1 status is now about `46%` overall. No
  GCP resources were provisioned, no public/DEX behavior was added, no mutating
  admin controls were added, no signing/submission behavior was added, and no
  credentials were changed.
- Latest native XRIQ Phase 1.1 read-only mempool status checkpoint: extended
  `xriq-api` with GET-only `/api/v1/mempool?limit=<n>`. The current route is
  an indexed-snapshot status/list scaffold: it reports `pending_count: 0`,
  `inspect_status: "enabled"`, `submit_status: "disabled"`, and
  `produce_block_status: "disabled"` with an empty entry list because
  `xriq-api serve-readonly` does not yet attach to a pending-file source.
  Extended `xriq/apps/explorer-ui` so `AdminStatusPanel` renders a Mempool
  section from the same-origin product API proxy. Static guardrails now require
  the mempool route/markers and continue rejecting public-market wording in UI
  source. Verification passed with `cargo fmt`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, `npm.cmd run check`,
  `npm.cmd run build`, CLI smoke for `/api/v1/mempool`, and browser
  verification against live local `xriq-api` plus Vite servers showing the
  Mempool panel, read-only warning, pending zero, inspect enabled, and
  submit/produce-block disabled. Phase 1.1 status is now about `48%` overall.
  No GCP resources were provisioned, no public/DEX behavior was added, no
  mutating admin controls were added, no wallet submission/block-production
  behavior was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 read-only admin node-status checkpoint:
  extended `xriq-api` with GET-only `/api/v1/admin/node/status`. The route
  reports health/status from the indexed-chain snapshot with mode
  `serve-readonly`, source `indexed-chain-snapshot`, current height, tip/state
  roots, stored block count, `pending_transactions: 0`,
  `wallet_submit_status: "disabled"`, and
  `block_production_status: "disabled"`. Extended
  `xriq/apps/explorer-ui` so `AdminStatusPanel` renders a Node section from
  the same-origin product API proxy. Static guardrails now require the node
  route/markers and continue rejecting public-market wording in UI source.
  Verification passed with `cargo fmt`, `cargo test -p xriq-api`,
  `cargo clippy -p xriq-api -- -D warnings`, `npm.cmd run check`,
  `npm.cmd run build`, CLI smoke for `/api/v1/admin/node/status`, direct local
  API smoke on `127.0.0.1:8090`, and browser verification against live local
  `xriq-api` plus Vite servers showing Node, healthy, `serve-readonly`,
  `indexed-chain-snapshot`, wallet submit disabled, block production disabled,
  and no console errors. Phase 1.1 status is now about `49%` overall. No GCP
  resources were provisioned, no public/DEX behavior was added, no mutating
  admin controls were added, no wallet submission/block-production behavior was
  added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 read-only pending-file mempool bridge
  checkpoint: extended `xriq-api request` and `xriq-api serve-readonly` with
  optional `--pending-file <path>`. When present, `xriq-api` reads and
  validates the existing durable private-devnet pending TSV format
  (`xriq-pending-transaction-v1`), rejects wrong chain IDs or mismatched
  transaction hashes, and exposes those pending entries through GET-only
  `/api/v1/mempool?limit=<n>`. `explorer_overview.chain.pending_transactions`
  and `/api/v1/admin/node/status.pending_transactions` now reflect the
  read-only pending-file count. Submit and block production remain explicitly
  disabled in `xriq-api`; this is inspection only, not a mutating wallet or
  block-production API. Extended `xriq/apps/explorer-ui` so the Admin Status
  Mempool block shows the first pending transaction hash, amount, and pending
  status when the API was started with `--pending-file`. Static guardrails now
  require those pending-entry UI markers and continue rejecting public-market
  wording and wallet submit/send behavior in UI source. Verification passed
  with `cargo fmt --check`, `cargo test -p xriq-api` (`15` lib tests plus `5`
  binary tests), `cargo clippy -p xriq-api -- -D warnings`,
  `npm.cmd run check`, CLI smoke using `xriq-wallet send` to create
  `target/xriq-api-pending-read-smoke.tsv`, CLI smokes for
  `/api/v1/mempool?limit=5` and `/api/v1/admin/node/status` with
  `--pending-file`, and browser verification against live local `xriq-api`
  plus Vite servers showing pending count `1`, the pending hash, first amount
  `10`, pending status, submit disabled, produce-block disabled, and no console
  errors. Phase 1.1 status is now about `50%` overall. No GCP resources were
  provisioned, no public/DEX behavior was added, no mutating admin controls
  were added, no product API wallet submission/block-production behavior was
  added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 ISO product API preview checkpoint: reversed
  the adapter dependency direction so `xriq-iso20022` is a standalone mapping
  crate and `xriq-api` can call it from the product API boundary. Added
  GET-only/read-only private-devnet routes for
  `/api/v1/iso20022/payment-initiation/preview?tx_hash=<hash>`,
  `/api/v1/iso20022/transactions/{hash}/status`, and
  `/api/v1/iso20022/accounts/{address}/statement?from=<ts>&to=<ts>`. These
  routes map confirmed indexed XRIQ data into ISO 20022-aligned preview JSON
  with `not_certified: true`, `xriq-iso20022-preview-v1`, explicit unsupported
  fields, and no bank/SWIFT/legal-compliance/payment-network claims. The
  current implementation remains GET-only and does not add wallet submission,
  custody, public DEX behavior, or production payment processing. Focused
  verification passed `cargo fmt --check`, `cargo test -p xriq-iso20022`,
  `cargo test -p xriq-api` (`16` lib tests plus `5` binary tests),
  `cargo clippy -p xriq-iso20022 -- -D warnings`,
  `cargo clippy -p xriq-api -- -D warnings`, bundled-Python
  `scripts/xriq_phase1_1_contract_check.py`, CLI request smokes for all three
  new ISO routes, `cargo test --workspace -j 1`, and `git diff --check`. Phase
  1.1 status is now about `51%` overall. No GCP resources were provisioned, no
  public/DEX behavior was added, no mutating admin controls were added, and no
  credentials were changed.
- Latest native XRIQ Phase 1.1 read-only ISO preview UI checkpoint: extended
  `xriq/apps/explorer-ui` with `src/iso.tsx`, a read-only `IsoPreviewPanel`
  that calls the product ISO preview routes for the selected transaction and
  account. The panel renders payment initiation, payment status, account
  statement, `xriq-iso20022-preview-v1`, `not_certified`, `XRIQ-DEV`, ISO
  status such as `ACSC`, opening/closing balances, and unsupported-field
  counts. Static guardrails now require the ISO panel, ISO API client routes,
  and read-only marker while continuing to reject public-market wording in UI
  source. Verification passed `npm.cmd run check`, escalated
  `npm.cmd run build` after the known Windows/Vite sandbox config-read issue,
  and browser smoke against live local `xriq-api` plus Vite servers showing
  the ISO panel, mapping version, currency, `ACSC`, opening `100`, closing
  `73`, `not_certified`, unsupported-field markers, read-only marker, and no
  console errors. Phase 1.1 status is now about `52%` overall. No GCP
  resources were provisioned, no public/DEX behavior was added, no mutating
  admin controls were added, no wallet submission/block-production behavior
  was added, and no credentials were changed.
- Latest native XRIQ Phase 1.1 pending wallet transaction-status checkpoint:
  extended `xriq-api` so `GET /api/v1/wallet/transactions/{hash}/status`
  checks confirmed indexed transactions first and then the optional
  `--pending-file` mempool entries. Pending wallet status responses return
  `status: "pending"` with `block_height`, `block_hash`, and
  `transaction_index` set to `null` until the transaction is confirmed.
  `wallet_status.pending_transactions` now reflects the read-only pending-file
  count. Confirmed wallet transaction-status JSON remains unchanged for
  confirmed rows. Verification passed `cargo fmt`, isolated-target
  `cargo test -p xriq-api -j 1` (`16` lib tests plus `5` binary tests),
  isolated-target `cargo clippy -p xriq-api -- -D warnings`, and a CLI smoke
  that created a durable pending transaction with `xriq-wallet send`, then
  queried `/api/v1/wallet/transactions/<pending-hash>/status` through
  `xriq-api request --pending-file` and received `200 OK`, `status:
  "pending"`, and null block fields. The first default-target test attempt hit
  the known Windows linker/executable lock and was rerun with
  `CARGO_TARGET_DIR=target-codex-pending-wallet-status`. Phase 1.1 status is
  now about `53%` overall. No GCP resources were provisioned, no public/DEX
  behavior was added, no mutating admin controls were added, no wallet
  submission/block-production behavior was added, and no credentials were
  changed.
- Latest native XRIQ Phase 1.1 contract checkpoint: added
  `docs/XRIQ_PHASE1_1_CONTRACTS.md` as the Milestone A contract baseline. It
  defines private/local product API groups for health, explorer, wallet, admin,
  ISO 20022 mapping, and future deferred DEX contracts; defines PostgreSQL
  read-model table contracts for blocks, transactions, accounts, balances,
  account transactions, mempool entries, snapshots, indexer runs, audit events,
  and ISO 20022 mapped messages; and sets fixture requirements for the next
  implementation checkpoint. It records that Exchange UI should be treated as
  future decentralized exchange UI, but real swaps, liquidity, custody, bridges,
  and market-facing claims remain deferred until token, smart-contract/native
  module, legal-risk, and security review gates exist. Updated
  `README.md`, `docs/XRIQ_PHASE1_1_END_TO_END_PLAN.md`,
  `docs/XRIQ_GCP_RESOURCE_PLAN.md`, and this handoff. Phase 1.1 status is now
  about `16%` overall. No GCP resources were provisioned, no Rust behavior
  changed, and no credentials were changed.
- Latest native XRIQ Phase 1.1 planning checkpoint: added
  `docs/XRIQ_PHASE1_1_END_TO_END_PLAN.md` as the post-RC1 local/private
  end-to-end plan. It makes ISO 20022 compatibility part of Phase 1.1 as an
  adapter/mapping layer, not as bank approval, legal compliance, payment-network
  connectivity, or ISO certification. It maps the user's target architecture:
  Rust node/consensus are RC1-baseline complete, wallet backend and APIs are
  partial, smart contracts are deferred, React + TypeScript UI is not started,
  and XRIQ PostgreSQL indexing/analytics/audit tables are not started. It sets
  Phase 1.1 overall completion at about `15%` because the Rust private-devnet
  foundation is complete for RC1 while the product/indexer/UI/ISO surfaces are
  mostly unbuilt. It also sets the recommended build order: contracts,
  PostgreSQL indexer, Rust API service, ISO 20022 adapter, explorer UI, wallet
  UI, admin portal, then later exchange UI and smart contracts only after
  review/stability. Updated `README.md`,
  `xriq/README.md`, `docs/XRIQ_TECHNICAL_SPEC.md`, and this handoff. No Rust
  behavior change, Vast sync, API/vLLM restart, training, OpenAI mentor call,
  tag operation, or credential change was used.
- Latest native XRIQ Phase 1.1 GCP planning checkpoint: added
  `docs/XRIQ_GCP_RESOURCE_PLAN.md`. It states that no Google Cloud resources
  are required for the immediate Milestone A contracts step, recommends local
  development first, and lays out a future small managed GCP footprint: Cloud
  Run services/jobs, Cloud SQL for PostgreSQL, Artifact Registry, Secret
  Manager, Cloud Storage, and Cloud Build or GitHub Actions. It explicitly
  defers GKE/Kubernetes, BigQuery, Pub/Sub, Dataflow, Vertex AI, public load
  balancers, and multi-region production infrastructure until the local/private
  end-to-end prototype justifies them. Updated `README.md`,
  `docs/XRIQ_PHASE1_1_END_TO_END_PLAN.md`, and this handoff. No GCP resources
  were provisioned, no Rust behavior changed, and no credentials were changed.
- Latest native XRIQ Phase 1 RC1 tag checkpoint: the user explicitly approved
  marking XRIQ private-devnet Phase 1 as RC1 and creating/pushing the
  `phase1-xriq-private-devnet-rc1` tag. Before tagging, the strict readiness
  gate passed with
  `python scripts/xriq_phase1_rc_readiness.py --require-clean-git
  --require-origin-main --require-rc-tag-available`, reporting
  `ready_for_rc_tag: true`, `origin_main_matches_head: true`, and
  `rc_tag_available: true`. The annotated Git tag
  `phase1-xriq-private-devnet-rc1` was created and pushed to GitHub. It points
  to commit `688bf913a0ba8e86ddf3a6a8c0951ee57a128731` (`688bf913`), whose
  latest full local validation artifact is
  `xriq/target/xriq-phase1-local-check-20260526T164037/summary.json`.
  Phase 1 private-devnet RC1 is now complete from the source-control/readiness
  perspective. A later handoff-only commit may leave `main` ahead of this tag;
  that is expected and does not move the RC1 release point. Do not recreate or
  move this tag unless the user explicitly asks for a corrective tag operation
  and understands the release-history risk. No Vast sync, API/vLLM restart,
  training, OpenAI mentor call, or credential change was used.
- Latest native XRIQ Phase 1 RC tag-availability checkpoint: tightened
  `scripts/xriq_phase1_rc_readiness.py` with
  `--require-rc-tag-available`, which verifies
  `phase1-xriq-private-devnet-rc1` is absent locally and on `origin` before
  returning tag-ready. The report now includes `rc_tag`,
  `local_rc_tag_exists`, `origin_rc_tag_exists`, `rc_tag_available`,
  `head_commit`, and `origin_main_commit`. `README.md`, `xriq/README.md`,
  `docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md`, `docs/XRIQ_PHASE1_RC_REPORT.md`,
  and this handoff now use the strict final command:
  `python scripts/xriq_phase1_rc_readiness.py --require-clean-git
  --require-origin-main --require-rc-tag-available`. Local verification passed
  bundled Python syntax compilation, `git diff --check`, and a pre-commit
  readiness run with `--require-origin-main --require-rc-tag-available`; the
  latter confirmed the RC tag name was available on `origin` and only reported
  `ready_for_rc_tag: false` because this checkpoint was still uncommitted. No
  Vast sync, API/vLLM restart, training, OpenAI mentor call, tag creation, or
  credential change was used.
- Latest native XRIQ Phase 1 RC-report checkpoint: added
  `docs/XRIQ_PHASE1_RC_REPORT.md` as the human-readable decision packet for
  deciding whether to mark the local/private XRIQ prototype as
  `phase1-xriq-private-devnet-rc1`. The report records candidate scope, the
  latest full local validation summary
  `xriq/target/xriq-phase1-local-check-20260526T164037/summary.json`, the 8
  completed gate steps, 15 checked smoke artifacts, explicit non-production
  boundaries, and the rule that the RC tag must not be created from a generic
  "continue" request. `README.md`, `xriq/README.md`, and
  `docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md` now link the report. The readiness
  checker now requires the report and the handoff reference before returning
  tag-ready. After this commit/push, rerun
  `python scripts/xriq_phase1_rc_readiness.py --require-clean-git
  --require-origin-main --require-rc-tag-available`; if it reports
  `ready_for_rc_tag: true`, `origin_main_matches_head: true`, and
  `rc_tag_available: true`, the only remaining Phase 1 action is to ask the
  user for explicit approval to create and push
  `phase1-xriq-private-devnet-rc1`. No Vast sync, API/vLLM restart, training,
  OpenAI mentor call, or credential change was used.
- Latest native XRIQ Phase 1 RC-readiness checkpoint: added
  `scripts/xriq_phase1_rc_readiness.py`, a cheap CPU-only checker for the latest
  `xriq_phase1_local_check.py` `summary.json`. It validates the `ok` marker,
  empty `skipped`, all required completed gate steps, at least 15 existing
  smoke artifact checks, and the README/RC-checklist/handoff references needed
  before an explicit user-approved RC tag decision. It supports
  `--require-clean-git` for the final after-commit check and does not create the
  `phase1-xriq-private-devnet-rc1` tag. Later tightened follow-up added
  `--require-origin-main` so final readiness also proves the local HEAD matches
  `origin/main` before tagging; latest follow-up adds
  `--require-rc-tag-available` so the final readiness check also proves the
  `phase1-xriq-private-devnet-rc1` tag does not already exist locally or on
  `origin`. The local gate's Python syntax step now
  compiles this readiness checker. `README.md`, `xriq/README.md`, and
  `docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md` document the checker. Local
  verification passed with bundled Python syntax compilation for
  `scripts/xriq_phase1_local_check.py` and
  `scripts/xriq_phase1_rc_readiness.py`, then
  `python scripts/xriq_phase1_rc_readiness.py` against
  `xriq/target/xriq-phase1-local-check-20260526T164037/summary.json`. The
  readiness script reported 15 artifact checks and four docs checked; it
  reported `ready_for_rc_tag: false` only because the checkpoint files were
  still uncommitted during the pre-commit run. After this commit/push, rerun
  `python scripts/xriq_phase1_rc_readiness.py --require-clean-git
  --require-origin-main --require-rc-tag-available`; if it reports
  `ready_for_rc_tag: true`, `origin_main_matches_head: true`, and
  `rc_tag_available: true`, the only remaining action before tagging is
  explicit user approval. No Vast sync, API/vLLM restart, training, OpenAI
  mentor call, or credential change was used.
- Latest native XRIQ Phase 1 local-check artifact-validation checkpoint:
  tightened `scripts/xriq_phase1_local_check.py` so the CPU-only gate now
  verifies critical generated transfer and HTTP smoke JSON artifacts after the
  smokes run. The gate checks snapshot export, latest snapshot discovery,
  latest snapshot replay check, explicit snapshot replay check, snapshot import,
  restored-chain verification, and the transfer wallet-flow post-block check.
  Its `summary.json` now records `artifact_checks` plus the completed
  `transfer smoke artifact check` and `http smoke artifact check` steps.
  `README.md`, `xriq/README.md`, and
  `docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md` now document this stronger local
  gate. Local verification passed with
  `python scripts/xriq_phase1_local_check.py`; the generated summary was
  `xriq/target/xriq-phase1-local-check-20260526T164037/summary.json`, with no
  skipped steps and 15 verified smoke artifact files. No Vast sync, API/vLLM
  restart, training, OpenAI mentor call, or credential change was used.
- Latest native XRIQ Phase 1 RC checklist checkpoint: added
  `docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md` as the go/no-go checklist for calling
  Phase 1 private-devnet complete. It records Phase 1 scope, required local
  validation through `python scripts/xriq_phase1_local_check.py`, functional
  coverage, release-candidate conditions, non-production limitations, and the
  rule that a `phase1-xriq-private-devnet-rc1` tag must not be created without
  explicit user agreement. `README.md`, `xriq/README.md`, and
  `docs/XRIQ_TECHNICAL_SPEC.md` now link/mention this checklist. This was a
  docs/readiness checkpoint after the local validation gate was already proven;
  verification was limited to `git diff --check`. No Rust smoke rerun, Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ Phase 1 local-check checkpoint: added
  `scripts/xriq_phase1_local_check.py`, a CPU-only validation wrapper for the
  current XRIQ private-devnet Phase 1 scope. It runs XRIQ Cargo format checks,
  Python smoke syntax checks, full XRIQ workspace tests, full XRIQ workspace
  clippy, the isolated transfer/replay/snapshot smoke, and the local
  submit-capable HTTP smoke with fresh artifact directories under
  `xriq/target/`. It does not use Vast, vLLM, BIBER API, model training, or
  restored runtime state. `README.md` and `xriq/README.md` now document the new
  one-command local validation path. Local verification passed by running
  `python scripts/xriq_phase1_local_check.py`; the generated summary was
  `xriq/target/xriq-phase1-local-check-20260526T163059/summary.json` and
  reported completed steps: `cargo fmt check`, `python smoke syntax check`,
  `cargo test workspace`, `cargo clippy workspace`, `transfer smoke`, and
  `http smoke`. No Vast sync, API/vLLM restart, training, OpenAI mentor call,
  or credential change was used.
- Latest native XRIQ snapshot-latest-check checkpoint: added `xriq-node
  snapshot-latest-check --snapshot-root <path> [--alice-balance <base-units>]
  [--format text|json]` and local HTTP `GET /v1/snapshots/latest/check` so
  restore/operator flows can replay-verify the latest discovered snapshot
  without first copying its name from `snapshot-list`. The command and route use
  the same deterministic ordering as `snapshot-latest` and return the same
  check shape as `snapshot-check`, with `command: snapshot-latest-check`. The
  transfer/replay smoke now writes `snapshot-latest-check.json`, and the HTTP
  smoke writes `http-snapshot-latest-check.json`. Docs updated:
  `docs/XRIQ_NODE_JSON_SCHEMA.md`, `docs/XRIQ_SNAPSHOT_EXPORT_IMPORT.md`,
  `docs/XRIQ_TECHNICAL_SPEC.md`, and `xriq/README.md`. Local verification
  passed `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled
  Python syntax compilation for the transfer and HTTP smokes,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `52 passed` using `CARGO_TARGET_DIR=target-codex-snapshot-latest-check-test`,
  `cargo clippy -p xriq-node --manifest-path xriq/Cargo.toml -- -D warnings`
  using `CARGO_TARGET_DIR=target-codex-snapshot-latest-check-clippy`, the
  isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-snapshot-latest-check-smoke` with artifact
  directory
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T-snapshot-latest-check`,
  and the isolated HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-snapshot-latest-check-http-smoke` with
  artifact directory
  `xriq/target/xriq-private-devnet-http-smoke-20260526T-snapshot-latest-check`.
  No Vast sync, API/vLLM restart, training, OpenAI mentor call, or credential
  change was used.
- Latest native XRIQ snapshot-latest checkpoint: added `xriq-node
  snapshot-latest --snapshot-root <path> [--format text|json]` and local HTTP
  `GET /v1/snapshots/latest` for operator restore flows. Both use the existing
  deterministic snapshot discovery ordering from `snapshot-list` and return the
  same snapshot detail shape, with `command: snapshot-latest`; empty snapshot
  roots now return stable `snapshot_not_found` errors. The transfer/replay
  smoke now writes `snapshot-latest.json`, and the HTTP smoke writes
  `http-snapshot-latest.json`. Docs updated:
  `docs/XRIQ_NODE_JSON_SCHEMA.md`, `docs/XRIQ_SNAPSHOT_EXPORT_IMPORT.md`,
  `docs/XRIQ_TECHNICAL_SPEC.md`, and `xriq/README.md`. Local verification
  passed `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled
  Python syntax compilation for the transfer and HTTP smokes,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `52 passed` using `CARGO_TARGET_DIR=target-codex-snapshot-latest-test`,
  `cargo clippy -p xriq-node --manifest-path xriq/Cargo.toml -- -D warnings`
  using `CARGO_TARGET_DIR=target-codex-snapshot-latest-clippy`, the isolated
  transfer smoke using `CARGO_TARGET_DIR=target-codex-snapshot-latest-smoke`
  with artifact directory
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T-snapshot-latest-2`,
  and the isolated HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-snapshot-latest-http-smoke` with artifact
  directory
  `xriq/target/xriq-private-devnet-http-smoke-20260526T-snapshot-latest`. No
  Vast sync, API/vLLM restart, training, OpenAI mentor call, or credential
  change was used.
- Latest native XRIQ wallet send-fixture checkpoint: added
  `xriq/fixtures/private-devnet/wallet-send-pending.json` as a checked golden
  example for `xriq-wallet send --format json`. `xriq-wallet` now has an
  exact-match fixture regression test for the direct wallet pending-send output
  alongside the existing wallet transfer-submit and wallet chain-check
  fixtures. `docs/XRIQ_NODE_JSON_SCHEMA.md`, `xriq/README.md`, and
  `docs/XRIQ_TECHNICAL_SPEC.md` document the new fixture coverage. Local
  verification passed the XRIQ Cargo format check,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `37 passed`, and `cargo clippy -p xriq-wallet --manifest-path
  xriq/Cargo.toml -- -D warnings`. This was a local fixture/regression
  checkpoint only; no isolated smoke rerun, Vast sync, API/vLLM restart,
  training, OpenAI mentor call, or credential change was used.
- Latest native XRIQ wallet direct-send checkpoint: added `xriq-wallet send`,
  a one-command private-devnet helper that builds a test transfer and submits
  it directly to a durable pending file without requiring an intermediate
  transfer JSON file. It reuses the existing wallet transfer builder and the
  existing node pending-file submission/validation path, emits stable
  `xriq-wallet-json-v1` output with `command: send-pending`, and remains
  private-devnet/test-identity tooling only. The isolated
  transfer/replay/snapshot smoke now uses `xriq-wallet send` for the separate
  wallet pending-to-block lifecycle and writes `wallet-flow-send-pending.json`
  before producing the pending block and confirming the transaction. Local
  verification passed the XRIQ Cargo format check, bundled Python syntax
  compilation for `scripts/xriq_private_devnet_transfer_smoke.py`, `cargo test
  -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with `36 passed`,
  `cargo clippy -p xriq-wallet --manifest-path xriq/Cargo.toml -- -D
  warnings`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-send-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T192113Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ wallet fixture checkpoint: added
  `xriq/fixtures/private-devnet/wallet-chain-check-empty.json` as a checked
  golden example for `xriq-wallet check --format json` on an empty replayed
  private-devnet chain. `xriq-wallet` now has an exact-match fixture regression
  test for the wallet chain-check output alongside the existing wallet transfer
  submit fixture. `docs/XRIQ_NODE_JSON_SCHEMA.md`, `xriq/README.md`, and
  `docs/XRIQ_TECHNICAL_SPEC.md` document the fixture coverage. Local
  verification passed the XRIQ Cargo format check,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `34 passed`, and `cargo clippy -p xriq-wallet --manifest-path
  xriq/Cargo.toml -- -D warnings`. This was a local fixture/regression
  checkpoint only; no isolated smoke rerun, Vast sync, API/vLLM restart,
  training, OpenAI mentor call, or credential change was used.
- Latest native XRIQ wallet chain-check checkpoint: `xriq-wallet check` now
  wraps the existing file-backed private-devnet replay verification path and
  returns wallet-facing text or `xriq-wallet-json-v1` output with
  `command: check`, `verified: true`, chain id, height, latest block hash,
  state root, pending transaction count, and stored block count. It supports
  optional `--pending-file`, so wallet/operator flows can verify durable
  pending state before and after block production without mutating chain or
  pending files. The isolated transfer/replay/snapshot smoke now writes
  `wallet-check-initial.json`, `wallet-flow-check-before-block.json`, and
  `wallet-flow-check-after-block.json`, proving the wallet check path reports
  pending count `1` before `produce-pending-block` and `0` after pending-file
  compaction. Local verification passed `cargo fmt --all --manifest-path
  xriq/Cargo.toml -- --check`, bundled Python syntax compilation for
  `scripts/xriq_private_devnet_transfer_smoke.py`, `cargo test -p xriq-wallet
  --manifest-path xriq/Cargo.toml -j 1` with `33 passed`, `cargo clippy -p
  xriq-wallet --manifest-path xriq/Cargo.toml -- -D warnings`, `cargo test -p
  xriq-node --manifest-path xriq/Cargo.toml -j 1` with `51 passed`, and the
  isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-chain-check-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T183959Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ wallet status checkpoint: `xriq-wallet status` now replays
  the local file-backed private-devnet chain and returns wallet-facing chain
  status in text or `xriq-wallet-json-v1` format. It supports optional
  `--pending-file` so wallet/operator flows can see durable pending transaction
  count alongside chain id, current height, latest block hash, state root, and
  stored block count. The isolated transfer/replay/snapshot smoke now writes
  `wallet-status-initial.json`, `wallet-flow-status-before-block.json`, and
  `wallet-flow-status-after-block.json`, proving the status path reports
  pending count `1` before `produce-pending-block` and `0` after pending-file
  compaction. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo clippy -p xriq-wallet --manifest-path xriq/Cargo.toml -- -D warnings`,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `31 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-status-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T182225Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ wallet lifecycle smoke checkpoint: the Windows-friendly
  isolated transfer/replay/snapshot smoke now includes a separate wallet
  pending-to-block lifecycle on its own fresh chain file. The new regression
  path runs `xriq-wallet transfer --nonce auto`, writes
  `wallet-flow-transfer.json`, submits that JSON with `xriq-wallet submit`,
  verifies `xriq-wallet pending` before block production, produces a block from
  the durable pending file with `xriq-node produce-pending-block`, verifies the
  pending file is compacted and `xriq-wallet pending` is empty, then verifies
  `xriq-wallet tx status` returns the transaction as confirmed. New smoke
  artifacts include `wallet-flow-chain.bin`, `wallet-flow-pending.tsv`,
  `wallet-flow-submit-pending.json`, `wallet-flow-pending-before-block.json`,
  `wallet-flow-produced-pending-block.json`,
  `wallet-flow-pending-after-block.json`, and
  `wallet-flow-tx-status-confirmed.json`. Local verification passed bundled
  Python syntax compilation for `scripts/xriq_private_devnet_transfer_smoke.py`
  and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-lifecycle-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T180847Z`. No Rust
  source files changed, and no Vast sync, API/vLLM restart, training, OpenAI
  mentor call, or credential change was used.
- Latest native XRIQ wallet pending-list checkpoint: `xriq-wallet pending` now
  replays the local file-backed private-devnet chain, loads
  `--pending-file`, and returns a read-only pending transaction list in text or
  `xriq-wallet-json-v1` format. The JSON output uses `command: pending`,
  `pending_count`, and an ordered `transactions` array with transaction hash,
  received order, transparent from/to addresses, base-unit amount/fee, nonce,
  and optional expiration height. This is a local private-devnet inspection
  helper only; it does not produce blocks, mutate the chain or pending file, or
  print private keys, seed phrases, or production custody material. The
  isolated transfer/replay/snapshot smoke now writes `wallet-pending.json`
  after `xriq-wallet submit` and pending `xriq-wallet tx status`, using the
  separate wallet pending file from the main snapshot path. Local verification
  passed `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`,
  bundled Python syntax compilation for
  `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo clippy -p xriq-wallet --manifest-path xriq/Cargo.toml -- -D warnings`,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `29 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-pending-list-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T175305Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ wallet pending-submit checkpoint: `xriq-wallet submit`
  now reads a wallet transfer draft or `xriq-node-transfer-submit-v1` JSON
  transfer body from `--transfer-file`, validates it against the replayed
  file-backed private-devnet chain, appends it to `--pending-file`, and returns
  stable text or `xriq-wallet-json-v1` output with `command:
  submit-pending`, `status: pending`, the transaction hash, received order, and
  transparent transfer fields. It does not produce a block, mutate the chain
  file, or print private keys, seed phrases, or production custody material.
  The isolated transfer/replay/snapshot smoke now writes
  `wallet-submit-pending.json`, `wallet-submit-pending-status.json`, and
  `wallet-submit-pending.tsv` using a separate pending file from the main
  snapshot path. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo clippy -p xriq-wallet --manifest-path xriq/Cargo.toml -- -D warnings`,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `27 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-submit-pending-smoke`. The smoke
  artifact directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T174824Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ wallet auto-nonce checkpoint: `xriq-wallet transfer` now
  accepts `--nonce auto` when paired with `--chain-file <path>` for local
  private-devnet use. The wallet replays the file-backed chain, reads the
  sender account nonce, and then constructs the same text or
  `xriq-node-transfer-submit-v1` JSON transfer draft without mutating the chain
  or pending file. Manual numeric nonces remain supported. The isolated
  transfer, replay, and snapshot smoke now writes
  `wallet-transfer-auto-nonce.json` after block production and verifies the
  second draft uses Alice's replayed nonce `1`. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo clippy -p xriq-wallet --manifest-path xriq/Cargo.toml -- -D warnings`,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `25 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-auto-nonce-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T173758Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ wallet account-list checkpoint: `xriq-wallet accounts`
  now replays the local file-backed private-devnet chain and returns a
  deterministic transparent account list for wallet/operator inspection. It
  supports text and `--format json`, emits `xriq-wallet-json-v1` with
  `command: accounts`, account count, addresses, `balance_base_units`, and
  nonces. It is private-devnet-only and does not print private keys, seed
  phrases, or production custody material. The isolated transfer, replay, and
  snapshot smoke now writes `wallet-accounts.json` after block production and
  verifies Alice, Bob, and the deterministic fee sink balances. Local
  verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo clippy -p xriq-wallet --manifest-path xriq/Cargo.toml -- -D warnings`,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `23 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-accounts-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T173327Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ wallet history checkpoint: `xriq-wallet history` now
  replays the local file-backed private-devnet chain and returns transparent
  account transaction history for a wallet address. It supports text and
  `--format json`, emits `xriq-wallet-json-v1` with `command: history`,
  address, transaction count, confirmed block fields, direction, transaction
  hash, and transparent transfer fields. It is a local private-devnet helper
  only and does not print private keys, seed phrases, or production custody
  material. The isolated transfer, replay, and snapshot smoke now writes
  `wallet-history-alice.json` after block production and verifies Alice sees
  the confirmed sent transaction. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo clippy -p xriq-wallet --manifest-path xriq/Cargo.toml -- -D warnings`,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `21 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-history-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T172708Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ pending wallet transaction-status checkpoint:
  `xriq-wallet tx status` now has explicit pending-path coverage from both a
  wallet draft file and the durable private-devnet pending file. The wallet
  test covers draft inspection before block production; the real local HTTP
  smoke writes `wallet-pending-tx-status.json` after HTTP submission and before
  block production, then verifies `status: pending`, the submitted transaction
  hash, and amount from `target/xriq-devnet-pending.tsv`. Confirmed lookup
  remains supported from a replayed local file-backed chain through the same
  command. It supports text and `--format json`, emits `xriq-wallet-json-v1`
  with `command: tx-status`, status, transaction hash, confirmed block fields
  or pending order, and transparent transfer fields. It rejects malformed
  transaction hashes before replay and does not print private keys, seed
  phrases, or production custody material. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_http_smoke.py`,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `19 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the real local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-pending-tx-status-smoke`. The smoke
  artifact directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T171010Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ wallet balance checkpoint: `xriq-wallet balance` now reads
  replayed local private-devnet account state from a file-backed chain through
  the existing node replay/account-detail path. It supports text and
  `--format json`, emits `xriq-wallet-json-v1` with `command: balance`,
  address, `balance_base_units`, and nonce, and does not print private keys,
  seed phrases, or production custody material. The isolated transfer, replay,
  and snapshot smoke now writes `wallet-balance-alice.json` after block
  production and verifies it matches the node account-detail output. Local
  verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for
  `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1` with
  `15 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-balance-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T163231Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ HTTP restored-chain-check checkpoint: after HTTP
  `POST /v1/snapshots/import`, the local HTTP smoke now calls
  `GET /v1/chain/check` against the restored `serve-private` process. It writes
  `imported-chain-check.json` and requires `verified: true`, matching restored
  height, state root, and pending transaction count against the exported
  snapshot status before transaction lookup. The Rust HTTP regression checks
  the same post-import `/v1/chain/check` contract. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_http_smoke.py`,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed`, and the real local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-http-restored-chain-check-smoke`. The smoke
  artifact directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T161020Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ HTTP snapshot-check checkpoint: `xriq-node
  serve-readonly` and `xriq-node serve-private` now expose
  `GET /v1/snapshots/{snapshot-name}/check` when `--snapshot-root <path>` is
  configured. The route keeps snapshot names constrained to one safe path
  segment, reuses the native `snapshot-check` replay/manifest comparison, and
  returns the same JSON shape as the CLI command before restore. The local HTTP
  smoke now writes `http-snapshot-check.json` and requires `verified: true`
  with no mismatches. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_http_smoke.py`,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed`, and the real local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-http-snapshot-check-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T160554Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ restored snapshot chain-check checkpoint: the isolated
  transfer/replay/snapshot smoke now runs `xriq-node chain-check` against the
  freshly imported snapshot chain and pending files after `snapshot-import`.
  It writes `imported-chain-check.json` and requires `verified: true`, matching
  height, state root, and pending transaction count against the exported
  snapshot status before it proceeds to imported transaction lookup. The
  `xriq-node` snapshot export/import Rust regression now checks the same
  post-import replay contract. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-restore-check-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T160107Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ account-list checkpoint: `xriq-rpc` and `xriq-explorer`
  now expose deterministic account listing from replayed private-devnet ledger
  state. `xriq-node account-list` renders account balances/nonces in text or
  JSON, and the local HTTP wrapper exposes `GET /v1/accounts?limit=<n>` for the
  same private explorer/operator view. The local HTTP smoke now writes
  `accounts.json` and verifies Alice/Bob appear after block production. Local
  verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_http_smoke.py`,
  `cargo test -p xriq-rpc --manifest-path xriq/Cargo.toml -j 1` with
  `10 passed`, `cargo test -p xriq-explorer --manifest-path xriq/Cargo.toml -j 1`
  with `10 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, and the local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-account-list-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T123611Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ block-list checkpoint: `xriq-explorer` now exposes a
  compact latest-block renderer, and `xriq-node block-list` renders replayed
  private-devnet block summaries in text or JSON. The local HTTP wrapper
  exposes `GET /v1/blocks?limit=<n>` for explorer/operator block browsing while
  `GET /v1/blocks/{height-or-hash-or-latest}` remains the detail lookup. The
  HTTP smoke now writes `block-list.json` and verifies the produced block height
  and block hash after block production. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_http_smoke.py`,
  `cargo test -p xriq-explorer --manifest-path xriq/Cargo.toml -j 1` with
  `10 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, `git diff --check`, and the local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-block-list-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T124501Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ snapshot-discovery checkpoint: `xriq-node snapshot-list`
  now scans an operator-provided local snapshot root for immediate child
  directories containing XRIQ snapshot manifests, and `xriq-node
  snapshot-detail` reads one snapshot manifest before restore. Both commands
  support text and `--format json`, resolve `chain.bin`/`pending.tsv` paths
  inside the snapshot directory, and report deterministic height, latest block
  hash, state root, pending count, and stored-block count. The isolated
  transfer/replay/snapshot smoke now writes `snapshot-list.json` and
  `snapshot-detail.json` after export and before import. Local verification
  passed `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`,
  bundled Python syntax compilation for
  `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-snapshot-discovery-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T125640Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ HTTP snapshot-discovery checkpoint: `xriq-node
  serve-readonly` and `xriq-node serve-private` now accept optional
  `--snapshot-root <path>`. When configured, the local HTTP wrapper exposes
  `GET /v1/snapshots?limit=<n>` for snapshot listing and
  `GET /v1/snapshots/{snapshot-name}` for one-manifest detail lookup. Snapshot
  names are constrained to a single safe path segment; requests without
  `--snapshot-root` return the existing private-devnet JSON `not_implemented`
  shape. The local HTTP smoke now writes `http-snapshot-list.json` and
  `http-snapshot-detail.json` after snapshot export and before snapshot import.
  Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_http_smoke.py`,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed`, and the real local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-http-snapshot-discovery-smoke`. The smoke
  artifact directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T132739Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ snapshot-check checkpoint: `xriq-node snapshot-check`
  now reads one local snapshot manifest, replays its `chain.bin` plus optional
  `pending.tsv`, and compares replayed chain id, height, latest block hash,
  state root, pending count, and stored-block count against the manifest before
  restore. It supports text and `--format json`; JSON returns `verified`,
  `mismatches`, the manifest-backed `snapshot` summary, and `replayed_status`.
  The isolated transfer/replay/snapshot smoke now writes `snapshot-check.json`
  between snapshot detail and snapshot import, requiring `verified: true` with
  no mismatches. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_transfer_smoke.py`,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed`, and the isolated transfer smoke using
  `CARGO_TARGET_DIR=target-codex-snapshot-check-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-transfer-smoke-20260526T154518Z`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ chain-check checkpoint: `xriq-node chain-check` now
  explicitly replays and validates the configured private-devnet chain file,
  optionally loads and validates durable pending-file records, and returns
  `verified: true` with deterministic tip/status fields. The local HTTP wrapper
  exposes the same operator check at `GET /v1/chain/check`; when
  `serve-private --pending-file <path>` is used, the endpoint validates pending
  records before returning. The HTTP smoke now writes `initial-chain-check.json`
  and `chain-check.json`, verifying `verified: true`, height, and state root
  after block production. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`,
  bundled Python syntax compilation for
  `scripts/xriq_private_devnet_http_smoke.py`,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed`, and the local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-chain-check-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T122121Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ overview state-root checkpoint: `xriq-rpc` chain status
  now carries the canonical replayed `state_root`, and `xriq-explorer`
  overview renders the same state-root marker in text and JSON. The
  `xriq-node explorer-overview --format json` output and
  `GET /v1/explorer/overview?limit=<n>` response now include `state_root`, so
  dashboard clients can compare overview output against `/v1/chain/status`,
  restart checks, and snapshot restore checks. The local HTTP smoke now verifies
  the overview `state_root` matches the produced block status. Local
  verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`,
  `cargo test -p xriq-rpc --manifest-path xriq/Cargo.toml -j 1` with
  `9 passed`, `cargo test -p xriq-explorer --manifest-path xriq/Cargo.toml -j 1`
  with `9 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, bundled Python syntax compilation for
  `scripts/xriq_private_devnet_http_smoke.py`, and the local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-overview-state-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T121627Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest native XRIQ transaction-list checkpoint: `xriq-explorer` now exposes a
  confirmed latest-transaction view model, and `xriq-node transaction-list`
  renders recent confirmed transactions from a replayed chain file in text or
  JSON. The local HTTP wrapper exposes `GET /v1/transactions?limit=<n>` for the
  same confirmed transaction list, while `GET /v1/transactions/{hash}` remains
  the detail lookup. The local HTTP smoke now writes `latest-transactions.json`
  and verifies the returned transaction hash and block height after producing a
  block. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`,
  `cargo test -p xriq-explorer --manifest-path xriq/Cargo.toml -j 1` with
  `9 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, bundled Python syntax compilation for
  `scripts/xriq_private_devnet_http_smoke.py`, and the local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-transaction-list-smoke`. The smoke artifact
  directory was
  `xriq/target/xriq-private-devnet-http-smoke-20260526T121032Z`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was
  used.
- Latest GPU-off XRIQ isolated transfer/replay/snapshot checkpoint: added
  `scripts/xriq_private_devnet_transfer_smoke.py`, a Windows-friendly stdlib
  Python smoke that runs through `cargo run` only and does not require GPU,
  vLLM, FastAPI, BIBER API, or Vast. It creates a fresh artifact directory
  under `xriq/target/xriq-private-devnet-transfer-smoke-<timestamp>`, submits a
  wallet transfer, preflights/commits it into an isolated file-backed chain,
  checks transaction, block, account, and mempool detail, exports/imports a
  snapshot, then verifies the imported transaction. The local run passed with
  Alice balance `73`, Bob balance `25`, block height `1`, state root
  `915a4319e23daea9370a2ea1dfe9b57ac0099be910f64d04a5f4b9dfb0c5d067`, and
  transaction hash
  `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`.
  `README.md`, `xriq/README.md`, and `readme-resume-biber.md` now document the
  local smoke command: `python scripts/xriq_private_devnet_transfer_smoke.py`.
  Local syntax compilation also passed. No Vast sync, API/vLLM restart,
  training, OpenAI mentor call, or credential change was used.
- Latest GPU-off XRIQ HTTP/RPC smoke checkpoint: added
  `scripts/xriq_private_devnet_http_smoke.py`, a Windows-friendly stdlib
  Python smoke that builds the local Rust binaries, starts a real
  `xriq-node serve-private` process on a temporary localhost port, submits a
  wallet transfer through `POST /v1/mempool`, restarts the server to prove
  durable pending state survives, produces a block with `POST /v1/blocks`, and
  verifies transaction, block, account, mempool, and explorer overview
  endpoints. The local run passed with Alice balance `73`, Bob balance `25`,
  block height `1`, and transaction hash
  `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`.
  `README.md`, `xriq/README.md`, and `readme-resume-biber.md` now document the
  local command: `python scripts/xriq_private_devnet_http_smoke.py`. No Vast
  sync, API/vLLM restart, training, OpenAI mentor call, or credential change
  was used.
- Latest native XRIQ HTTP snapshot checkpoint: `xriq-node serve-private` now
  exposes local `POST /v1/snapshots/export?snapshot_dir=<path>` and
  `POST /v1/snapshots/import?snapshot_dir=<path>` endpoints. Export writes a
  snapshot of the configured chain file and optional pending file. Import
  restores a snapshot into the server's configured chain/pending targets while
  preserving the existing no-overwrite guard. Query `snapshot_dir` values are
  percent-decoded so Windows paths work through the real local HTTP smoke. The
  HTTP smoke now exports a snapshot after producing a block, starts a fresh
  local server on new chain/pending files, imports the snapshot, and verifies
  the imported confirmed transaction. Local verification passed
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed` and `python scripts/xriq_private_devnet_http_smoke.py`. The first
  parallel `cargo test -p xriq-node --manifest-path xriq/Cargo.toml` attempt
  hit transient Windows linker error `LNK1104` on the test executable; no XRIQ
  process was running, and the serial retry passed. No Vast sync, API/vLLM
  restart, training, OpenAI mentor call, or credential change was used.
- Latest native XRIQ block hash lookup checkpoint: `xriq-node block-detail`
  now accepts `--block-hash <64-hex>` as an alternative to `--height`, with a
  guard that rejects ambiguous requests containing both selectors. The local
  HTTP wrapper now treats `GET /v1/blocks/{height-or-hash}` as a height lookup
  for decimal values and a hash lookup for 64-character lowercase hex values.
  The local HTTP smoke now verifies block-detail lookup by block hash after
  producing a pending block. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`,
  `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1` with
  `51 passed`, `cargo test -p xriq-wallet --manifest-path xriq/Cargo.toml -j 1`
  with `13 passed`, `python scripts/xriq_private_devnet_http_smoke.py`, and
  `python scripts/xriq_private_devnet_transfer_smoke.py`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was used.
- Latest native XRIQ latest-block lookup checkpoint: `xriq-node block-detail`
  now accepts `--height latest`, and the local HTTP wrapper exposes
  `GET /v1/blocks/latest` with the same block-detail JSON shape used by height
  and hash lookups. The local HTTP smoke now writes
  `block-detail-latest.json` and verifies the latest block height and hash after
  producing a pending block. Local verification passed
  `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`,
  `cargo test -p xriq-explorer --manifest-path xriq/Cargo.toml -j 1` with
  `7 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, bundled Python syntax compilation for
  `scripts/xriq_private_devnet_http_smoke.py`, and the local HTTP smoke using
  the bundled Python runtime. No Vast sync, API/vLLM restart, training, OpenAI
  mentor call, or credential change was used.
- Latest native XRIQ wallet transaction-hash checkpoint: `xriq-wallet transfer`
  now emits deterministic `transaction_hash` metadata in both text draft and
  `xriq-node-transfer-submit-v1` JSON output. `xriq-node` accepts this field as
  wallet metadata while still recomputing the canonical transaction hash during
  submit/pending validation. The local HTTP smoke now parses the wallet JSON and
  verifies the wallet-emitted `transaction_hash` matches the node returned
  pending `tx_hash`. The HTTP smoke binary lookup now honors
  `CARGO_TARGET_DIR`, and `.gitignore` ignores local `target-codex*/`
  directories so isolated Windows Cargo runs do not pollute git status. Local
  verification passed `cargo fmt ... -- --check`,
  wallet tests with `13 passed`, node tests with `51 passed`, bundled Python
  syntax compilation for `scripts/xriq_private_devnet_http_smoke.py`, and the
  local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-wallet-hash-smoke2`. The first alternate
  target-dir smoke attempt before the script fix mixed a new wallet binary with
  the stale default node binary and returned `unknown_json_field:
  transaction_hash`; rerunning after the script fix passed. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was used.
- Latest native XRIQ account transaction history checkpoint: `xriq-explorer`
  now exposes confirmed account transaction history view models with
  `sent`/`received`/`self` direction. `xriq-node account-transactions` renders
  the same history from a replayed chain file, and the local HTTP wrapper now
  exposes `GET /v1/accounts/{address}/transactions?limit=<n>`. The HTTP smoke
  now writes `account-alice-transactions.json` and verifies the account-history
  transaction hash and direction after producing a block. Local verification
  passed `cargo fmt --all --manifest-path xriq/Cargo.toml -- --check`,
  `cargo test -p xriq-explorer --manifest-path xriq/Cargo.toml -j 1` with
  `8 passed`, `cargo test -p xriq-node --manifest-path xriq/Cargo.toml -j 1`
  with `51 passed`, bundled Python syntax compilation for
  `scripts/xriq_private_devnet_http_smoke.py`, and the local HTTP smoke using
  `CARGO_TARGET_DIR=target-codex-account-history-smoke`. No Vast sync,
  API/vLLM restart, training, OpenAI mentor call, or credential change was used.
- Latest XRIQ-only focus checkpoint: the user narrowed the active project goal
  to completing the XRIQ private-devnet prototype first. A narrow usability
  step extended `scripts/biber_xriq_private_devnet_client.py` beyond read-only
  dashboard/snapshot access so it can now call BIBER API status, account,
  mempool, transaction, and `preflight-transfer` flows. `xriq/README.md`
  documents the repo-root client loop. Local verification used the bundled
  Python runtime for syntax compilation of the client and client tests plus CLI
  help rendering for the root command and `preflight-transfer`. Rust
  verification passed `cargo test -p xriq-wallet --manifest-path
  xriq/Cargo.toml` with `13 passed`, and `cargo test -p xriq-node
  --manifest-path xriq/Cargo.toml` with `51 passed`. Local Python pytest was
  not available on the workstation. After commit `e0c61983 Add XRIQ private
  devnet client commands` was pushed, Vast was fast-forwarded and focused
  pytest passed with `29 passed in 0.27s`:
  `/workspace/biber-venv/bin/python -m pytest tests/test_xriq_private_devnet_client.py tests/test_xriq_preflight_api.py -q`.
  No training run, OpenAI mentor call, credential change, API restart, or vLLM
  restart was used. Next XRIQ-only step: improve the private-devnet runbook/
  client loop or add the next missing wallet/RPC workflow, keeping public XRIQ
  scope delayed.
- Latest XRIQ private-devnet runbook-client checkpoint: the BIBER XRIQ stdlib
  client was extended with `block`, `snapshot-export`, and `snapshot-import`
  commands, so the repo-root client loop can now cover status, account,
  mempool, preflight transfer, transaction lookup, block lookup, snapshot
  export, snapshot listing/detail, and staging import. The Vast XRIQ API smoke
  script now also calls the non-balance-consuming client paths for status,
  account, mempool, snapshot export/import, snapshots, and snapshot detail.
  Local verification used the bundled Python runtime for syntax compilation and
  CLI help rendering; `git diff --check` passed. Commit `6458e67c Extend XRIQ
  private devnet client runbook` was pushed, Vast was fast-forwarded, and
  focused pytest passed with `32 passed in 0.27s`:
  `/workspace/biber-venv/bin/python -m pytest tests/test_xriq_private_devnet_client.py tests/test_xriq_preflight_api.py -q`.
  `bash scripts/vast_xriq_api_smoke.sh` also passed and wrote artifacts under
  `/workspace/outputs/xriq-api-smoke-20260525T151447Z-117752`; summary included
  `block_height=2`, `transaction_status=confirmed`, `snapshot_height=2`,
  `mempool_pending=0`, and client output files for overview/status/account/
  mempool/snapshot export/snapshot import/snapshots/snapshot detail. No
  training run, OpenAI mentor call, credential change, API restart, or vLLM
  restart was used for this client-only checkpoint.
- Latest BIBER MVP test-diagnosis workflow checkpoint pushed as
  `8b2047d4 Improve BIBER diagnosis repair loops`: stack detection is now
  command-first, so `python -m pytest` failures containing embedded Rust/Cargo
  fixture text stay classified as Python pytest failures instead of being
  misrouted to Rust. A focused allowlisted test command,
  `pytest-test-diagnosis`, now runs only `tests/test_test_diagnosis.py -q` for
  repair loops that should not pay the noise cost of full `pytest-core`.
  Vast verification passed
  `tests/test_test_diagnosis.py tests/test_test_runner.py tests/test_agent_capabilities.py -q`
  with `20 passed`, and the broader MVP pytest set including
  `tests/test_test_runner.py` passed with `241 passed`. No training run or
  OpenAI mentor call was used. Vast was fast-forwarded to `8b2047d4`, then
  the FastAPI process only was restarted to pid `109792` while vLLM/model
  serving stayed up. Live `vast_test_direct.sh` passed, and
  `run-test --test-id pytest-test-diagnosis --diagnose-on-failure` passed via
  `/v1/tests/run`. During the fast-forward, duplicate test-synced Vast working
  tree copies were stashed as `codex-duplicate-diagnosis-loop-sync`; do not pop
  that stash unless deliberately inspecting the duplicate pre-fast-forward
  copies.
- Latest BIBER MVP repair-extraction guard checkpoint: `extract-repair-edits`
  now enables a source-only guard when the repair request explicitly says not
  to change tests. Structured JSON edit candidates under `tests/`, `test/`,
  `__tests__/`, or common `.test`/`.spec` paths are rejected with
  `test_file_edit_blocked_by_source_only_instruction`; freeform unified diffs
  that touch test paths are flagged with
  `freeform_test_file_edit_blocked_by_source_only_instruction`. The repair
  prompt now also tells the local model to propose only implementation edits
  when tests are off-limits. Vast verification passed focused agent-client
  extraction tests with `8 passed, 137 deselected`, full
  `tests/test_biber_agent_client.py -q` with `145 passed`, and the broader
  cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_diagnosis.py tests/test_test_runner.py tests/test_agent_capabilities.py -q`
  with `165 passed`. No training run or OpenAI mentor call was used.
- Latest BIBER MVP machine-readable repair extraction checkpoint pushed as
  `69c81412 Extract source unified diffs for repairs`: repair prompts now ask
  for a strict JSON `edits` object before explanation, and
  `extract-repair-edits` can convert simple source-file unified diff hunks into
  bounded `old_text`/`new_text` edit candidates with
  `expected_replacements=1`. The source-only test-edit guard remains active for
  both JSON edits and unified diffs. Vast verification passed focused
  extraction tests with `10 passed, 137 deselected`, full
  `tests/test_biber_agent_client.py -q` with `147 passed`, and the broader
  cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_diagnosis.py tests/test_test_runner.py tests/test_agent_capabilities.py -q`
  with `167 passed`. No training run or OpenAI mentor call was used.
- Latest fresh unified-diff/strict-JSON repair probe artifact:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411`.
  The local model returned one strict JSON source edit for
  `src/biber_api/test_diagnosis.py`; extraction reported
  `ok=true`, `extraction_status=ready_for_plan_edit`, `json_values_found=1`,
  `unified_diff_candidates_found=0`, `source_only_guard.enabled=true`,
  `blocked_test_edits=0`, and `rejected=[]`. `plan-repair-edits` and guarded
  `apply-repair-edits --approve` succeeded in the temporary clone, but
  `verify-repair-edits --test-id pytest-test-diagnosis` failed. The proposed
  edit changed `primary_category = _primary_category(signals)` to
  `primary_category = _primary_category(signals) if signals else 'test_failure'`,
  which did not address the injected Rust panic rule regression. Treat this as
  useful failed-repair evidence only; it is not a trainable success row.
- Latest BIBER MVP failed-repair retry checkpoint pushed as
  `8f34c66e Add failed repair retry review helper`:
  `scripts/biber_agent_client.py` now has an offline
  `prepare-failed-repair-retry` command. It reads a failed
  `verify-repair-edits` artifact, loads the linked apply/plan/extraction/
  attempt/MVP-loop artifacts when available, records the original failure,
  attempted edit, verification failure, and writes a second bounded
  `biber_mvp_loop_repair_request` artifact for the local model. It rejects
  passed verification artifacts and keeps `safe_to_train=false`,
  `training_allowed=false`, `eligible_for_training=false`, `auto_applied=false`,
  and `auto_saved=false`. Vast verification passed focused retry/verification
  tests with `5 passed, 144 deselected`, full
  `tests/test_biber_agent_client.py -q` with `149 passed`, and the broader cheap
  MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `167 passed`. No training run or OpenAI mentor call was used. The latest
  generated failed-repair review is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-review.json`,
  and the standalone retry request for the next local-model attempt is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-request.json`.
  It captured the wrong attempted source edit in `src/biber_api/test_diagnosis.py`
  and linked the full artifact chain without artifact load errors. Vast was
  fast-forwarded to `8f34c66e`. The duplicate test-synced Vast working-tree
  copies were stashed as `codex-duplicate-failed-repair-retry-sync`; do not pop
  that stash unless deliberately inspecting the pre-fast-forward duplicate
  copies.
- Latest BIBER MVP repeated-failed-edit guard checkpoint: the generated retry
  request above was sent to the local `biber-dev-core-v1` model with
  `--max-tokens 700` after an initial `--max-tokens 1200` call exceeded the
  local 8192-token context window by one token. The local model repeated the
  exact previously failed edit for `src/biber_api/test_diagnosis.py`, so no
  `plan-repair-edits` or `apply-repair-edits` step was run. Extraction now
  rejects exact repeat edits on retry artifacts marked
  `retry_of_failed_verification=true` with reason
  `repeated_failed_repair_edit` and reports
  `repeat_failed_edit_guard.enabled=true`. Vast verification passed focused
  extraction tests with `12 passed, 139 deselected`, full
  `tests/test_biber_agent_client.py -q` with `151 passed`, and the broader
  cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `169 passed`. No training run, OpenAI mentor call, or API restart was
  used. The repeated-edit guarded extraction artifact is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-extraction-repeat-guard.json`;
  it reports `ok=false`, `extraction_status=no_valid_edits`, `edits=[]`,
  `rejected[0].reason=repeated_failed_repair_edit`, and
  `blocked_repeated_edits=1`.
- Latest BIBER MVP retry-context hardening checkpoint: `prepare-failed-repair-retry`
  now adds machine-readable `forbidden_edits` and compact
  `source_context_snippets` to the retry request and prompt. Snippets are read
  only from safe repository-relative paths under `--source-root`; CLI controls
  are `--source-root`, `--max-source-snippets`, and
  `--source-snippet-context-lines`. Vast focused retry/extraction tests passed
  with `14 passed, 137 deselected`; full `tests/test_biber_agent_client.py -q`
  passed with `151 passed`; and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  passed with `169 passed`. No training run, OpenAI mentor call, or API restart
  was used. Regenerated artifacts:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-review-context-v2.json`
  and
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-request-context-v2.json`.
  The v2 request included the forbidden exact edit, the previous bad
  `primary_category = _primary_category(signals)` target, the Python rule
  snippet, the Rust `panicked at` rule snippet, and the focused test assertion
  snippet. The local model still repeated the forbidden edit even after the v2
  context; extraction wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-extraction-context-v2.json`
  with `ok=false`, `extraction_status=no_valid_edits`,
  `rejected[0].reason=repeated_failed_repair_edit`, and
  `blocked_repeated_edits=1`. Do not plan/apply this artifact; treat it as a
  local-model gap and failure evidence.
- Latest BIBER MVP rule-prioritized retry checkpoint: retry source-context
  snippets are now grouped explicitly as `rule`, `context`, or
  `previous_failed_edit_target`, and `rule` snippets sort ahead of the previous
  failed target line. Retry prompts now label snippet kind in the compact
  source section and include the direct instruction
  `If every candidate equals a forbidden edit, return {"edits":[]}`. Vast
  focused retry/extraction tests passed with `15 passed, 137 deselected`; full
  `tests/test_biber_agent_client.py -q` passed with `152 passed`; and the
  broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  passed with `170 passed`. No training run, OpenAI mentor call, credential
  change, or API restart was used. The first v3 request was correctly
  rule-prioritized but still too large for vLLM at `--max-tokens 500` and
  `--max-tokens 400`. A narrower v4 request succeeded:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-request-context-v4.json`.
  It included only the top Python and Rust `_Rule` snippets plus the forbidden
  exact edit. The local model still emitted the forbidden edit in its strict
  JSON while explaining a different rule-order idea in prose. Extraction wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-extraction-context-v4.json`
  with `ok=false`, `extraction_status=no_valid_edits`,
  `rejected[0].reason=repeated_failed_repair_edit`, and
  `blocked_repeated_edits=1`. Do not plan/apply this artifact.
- Latest BIBER MVP repeated-forbidden retry model-gap checkpoint:
  `scripts/biber_agent_client.py` now has an offline
  `export-repeated-forbidden-retry-gap` command. It accepts only a saved
  `extract-repair-edits` artifact with `ok=false`,
  `extraction_status=no_valid_edits`, `repeat_failed_edit_guard.enabled=true`,
  and at least one `rejected[].reason=repeated_failed_repair_edit`. It loads
  the linked retry attempt, captures the repair prompt, forbidden exact edit,
  model JSON candidate, model explanation/prose, source snippets, and guard
  rejection into a JSONL model-gap review row. The row is explicitly
  `review_status=needs_human_review`, `training_allowed=false`,
  `eligible_for_training=false`, `safe_to_train=false`,
  `auto_promoted=false`, and `auto_saved=false`; it is evidence only, not a
  trainable dataset row. Vast verification passed focused
  `repeated_forbidden_retry_gap` tests with `2 passed, 152 deselected`, full
  `tests/test_biber_agent_client.py -q` with `154 passed`, and the broader
  cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `172 passed`. No training run, OpenAI mentor call, credential change,
  API restart, or vLLM restart was used. The v4 repeated-forbidden retry gap
  export is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-repeated-forbidden-retry-gap-context-v4.jsonl`;
  it contains one row for `biber-dev-core-v1` with one repeated forbidden
  candidate and one guard rejection. Next narrow gate: review this model-gap
  row as evidence for prompt/eval/training design, but do not train from it
  unless a future reviewed dataset validator explicitly promotes it.
- Latest BIBER MVP repeated-forbidden retry gap review checkpoint:
  `scripts/biber_agent_client.py` now has an offline
  `review-repeated-forbidden-retry-gaps` command. It reads one or more
  repeated-forbidden model-gap JSONL queues, rejects unsupported sources,
  groups accepted rows by model, next test id, path, and failure mode, and
  emits deterministic review hints while keeping `training_allowed=false`,
  `eligible_for_training=false`, `safe_to_train=false`,
  `auto_promoted=false`, and `auto_saved=false`. Vast verification passed
  focused `repeated_forbidden_retry_gap` tests with
  `4 passed, 152 deselected`, full `tests/test_biber_agent_client.py -q`
  with `156 passed`, and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `174 passed`. No training run, OpenAI mentor call, credential change,
  API restart, or vLLM restart was used. The review artifact is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-repeated-forbidden-retry-gap-review-context-v4.json`.
  It has `records=1`, `groups=1`, `rejected_records=0`, and review hints
  `prompt_forbidden_edit_instruction_ignored`,
  `empty_edits_escape_instruction_ignored`,
  `json_candidate_conflicts_with_model_explanation`, and
  `rule_context_seen_but_repeated_target_edit`. Next narrow gate: use this
  review summary to make a deterministic prompt/response-shape improvement or
  eval case; do not train from this row automatically.
- Latest BIBER MVP retry prompt-contract checkpoint: the failed-repair retry
  prompt now explicitly states that the first JSON object is authoritative,
  a different fix must not appear only in prose, a better explanation must be
  reflected in the JSON edit, exact forbidden matches must be removed before
  final JSON, and no non-forbidden bounded edit must return exactly
  `{"edits":[]}`. Vast verification passed focused
  `prepare_failed_repair_retry` tests with `2 passed, 154 deselected`, full
  `tests/test_biber_agent_client.py -q` with `156 passed`, and the broader
  cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `174 passed`. No training run, OpenAI mentor call, credential change,
  API restart, or vLLM restart was used. Regenerated v5 artifacts are
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-review-context-v5.json`
  and
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-request-context-v5.json`.
  One local-model GPU retry attempt with `--max-tokens 300 --temperature 0.1`
  wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-attempt-context-v5.json`.
  The model now returned `{"edits":[]}` as the first JSON object instead of
  repeating the forbidden edit; extraction wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-extraction-context-v5.json`
  with `ok=false`, `extraction_status=no_valid_edits`, `edits=[]`,
  `rejected=[]`, `repeat_failed_edit_guard.enabled=true`, and
  `blocked_repeated_edits=0`. This is a useful response-shape improvement, but
  still not a successful repair. Do not plan/apply it; next narrow gate is to
  capture empty-edit-with-confused-prose as review-only evidence or improve
  context selection toward the actual rule-order edit.
- Latest BIBER MVP empty-retry response-gap checkpoint:
  `scripts/biber_agent_client.py` now has an offline `export-empty-retry-gap`
  command. It accepts only a retry repair attempt whose extraction ended
  `ok=false`, `extraction_status=no_valid_edits`, and whose first model JSON
  object contains `{"edits":[]}`. It writes a JSONL row with the repair prompt,
  forbidden edit, model prose, empty JSON evidence, extraction guard state,
  original/verification failures, and review hints while keeping
  `training_allowed=false`, `eligible_for_training=false`,
  `safe_to_train=false`, `auto_promoted=false`, `auto_saved=false`, and
  `apply_allowed=false`. Vast verification passed focused `empty_retry_gap`
  tests with `2 passed, 156 deselected`, full
  `tests/test_biber_agent_client.py -q` with `158 passed`, and the broader
  cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `176 passed`. No training run, OpenAI mentor call, credential change,
  API restart, or vLLM restart was used. The v5 empty-retry evidence row is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-empty-retry-response-gap-context-v5.jsonl`;
  it has `gap_type=empty_retry_response_with_unresolved_prose` and review hints
  `empty_edits_json_returned` and
  `prose_describes_fix_after_empty_edits`. This remains review-only evidence;
  do not train from it automatically.
- Latest BIBER MVP empty-retry gap review checkpoint:
  `scripts/biber_agent_client.py` now has an offline
  `review-empty-retry-gaps` command. It reads one or more
  `biber_mvp_loop_empty_retry_response_gap` JSONL queues, rejects unsupported
  sources, groups accepted rows by model, next test id, path, and failure
  mode, and preserves deterministic review hints while keeping
  `training_allowed=false`, `eligible_for_training=false`,
  `safe_to_train=false`, `auto_promoted=false`, and `auto_saved=false`. Vast
  verification passed focused `empty_retry_gap` tests with
  `4 passed, 156 deselected`, full `tests/test_biber_agent_client.py -q`
  with `160 passed`, and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `178 passed`. No training run, OpenAI mentor call, credential change,
  API restart, or vLLM restart was used. The review artifact is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-empty-retry-response-gap-review-context-v5.json`;
  it has `records=1`, `groups=1`, `rejected_records=0`, path
  `src/biber_api/test_diagnosis.py`, and review hints
  `empty_edits_json_returned` and
  `prose_describes_fix_after_empty_edits`. Next narrow gate: use the repeated
  forbidden and empty-retry review summaries to improve deterministic
  context selection toward the actual rule-order edit, not to start training.
- Latest BIBER MVP failure-line retry-context checkpoint:
  `build_retry_source_context_snippets` now mines compact terms from referenced
  failing test lines and can emit `test_expectation` snippets with
  `failure_line_refs`. Referenced failing test expectations sort before source
  `rule` snippets, and rule snippets still sort before previous failed edit
  targets. Vast verification passed focused retry-context tests with
  `2 passed, 159 deselected`, full `tests/test_biber_agent_client.py -q`
  with `161 passed`, and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `179 passed`. Regenerated v8 artifacts are
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-review-context-v8.json`
  and
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-request-context-v8.json`.
  The v8 compact retry request now contains the exact failing expectation
  `tests/test_test_diagnosis.py:71-75` with `failure_line_refs=[74]` and the
  matching Rust panic source rule
  `src/biber_api/test_diagnosis.py:43-47` with `_Rule(r"panicked at", ...)`.
  A bounded local-model retry probe wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-attempt-context-v8.json`,
  and extraction wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-extraction-context-v8.json`
  with `ok=true`, `extraction_status=ready_for_plan_edit`, and one
  non-repeated source edit candidate. Do not plan/apply that v8 candidate yet:
  it changes the fallback to `'assertion_failure'`, which is likely still the
  wrong repair for the injected Rust rule-order regression. Treat it as
  review-only failure evidence until a deterministic reviewer or human approves
  the next apply step. No training run, OpenAI mentor call, credential change,
  API restart, or vLLM restart was used.
- Latest BIBER MVP retry-edit review-gate checkpoint:
  `scripts/biber_agent_client.py` now has an offline
  `review-retry-repair-edits` command. It reviews a ready
  `extract-repair-edits` retry artifact plus the linked retry attempt before
  any `plan-repair-edits` step. For retry attempts, it blocks candidates that
  mutate the previous failed target line again when the retry context includes
  a more specific referenced failing test expectation and source `rule`
  snippet. Vast verification passed focused review-gate tests with
  `2 passed, 161 deselected`, full `tests/test_biber_agent_client.py -q`
  with `163 passed`, and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `181 passed`. Running the gate against the real v8 extraction wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-review-context-v8.json`.
  It reports `review_status=retry_edit_blocked_needs_human_review`,
  `ok=false`, `plan_allowed=false`, `reviewed_plan_edit_payload.edits=[]`,
  and hard blocker
  `retry_edit_changes_previous_failed_target_outside_rule_context`. Do not run
  `plan-repair-edits` against the v8 extraction unless a future human review
  explicitly accepts that blocker. No training run, OpenAI mentor call,
  credential change, API restart, or vLLM restart was used.
- Latest BIBER MVP retry-plan guard checkpoint:
  `plan-repair-edits` now enforces the retry review gate. Retry repair edit
  extractions require `--retry-review-artifact` pointing to an accepted
  `review-retry-repair-edits` artifact with `ok=true`, `plan_allowed=true`,
  and no hard blockers; otherwise planning stops before resolving API auth or
  calling the server-side plan endpoint. Normal first-attempt repair extraction
  planning remains unchanged. Vast verification passed focused retry-review
  tests with `2 passed, 164 deselected`, focused plan-repair tests with
  `5 passed, 161 deselected`, full `tests/test_biber_agent_client.py -q`
  with `166 passed`, and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `184 passed`. Real v8 checks confirmed
  `plan-repair-edits ...failed-repair-retry-edit-extraction-context-v8.json`
  fails without `--retry-review-artifact`, and also fails with the blocked
  v8 review artifact because `review_status=retry_edit_blocked_needs_human_review`.
  No planning, applying, training, OpenAI mentor call, credential change, API
  restart, or vLLM restart was used.
- Latest BIBER MVP blocked retry-edit gap export checkpoint:
  `scripts/biber_agent_client.py` now has an offline
  `export-blocked-retry-edit-gap` command. It accepts only a blocked
  `review-retry-repair-edits` artifact with hard blockers, loads the linked
  extraction and retry attempt, and writes a JSONL model-gap row while keeping
  `training_allowed=false`, `eligible_for_training=false`,
  `safe_to_train=false`, `auto_promoted=false`, `auto_saved=false`,
  `auto_applied=false`, `apply_allowed=false`, and `plan_allowed=false`.
  Vast verification passed focused blocked retry-edit gap tests with
  `2 passed, 166 deselected`, full `tests/test_biber_agent_client.py -q`
  with `168 passed`, and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `186 passed`. The real v8 blocked retry review exported to
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-blocked-retry-edit-gap-context-v8.jsonl`
  with one record, `gap_type=blocked_retry_repair_edit_candidate`, and hard
  blocker `retry_edit_changes_previous_failed_target_outside_rule_context`.
  This is review-only evidence; do not train from it automatically.
- Latest BIBER MVP blocked retry-edit gap review checkpoint:
  `scripts/biber_agent_client.py` now has an offline
  `review-blocked-retry-edit-gaps` command. It reads one or more blocked
  retry-edit JSONL queues, rejects unsupported sources, groups accepted rows
  by model, next test id, path, failure mode, and hard blocker, and keeps
  `training_allowed=false`, `eligible_for_training=false`,
  `safe_to_train=false`, `auto_promoted=false`, and `auto_saved=false`.
  Vast verification passed focused blocked retry-edit gap tests with
  `4 passed, 166 deselected`, full `tests/test_biber_agent_client.py -q`
  with `170 passed`, and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `188 passed`. The real v8 blocked retry gap review is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-blocked-retry-edit-gap-review-context-v8.json`;
  it has `records=1`, `groups=1`, `rejected_records=0`, path
  `src/biber_api/test_diagnosis.py`, hard blocker
  `retry_edit_changes_previous_failed_target_outside_rule_context`, and hints
  `previous_failed_target_retry_blocked_by_rule_context` and
  `rule_and_failure_line_context_available`. This remains review-only evidence;
  do not train from it automatically.
- Latest BIBER MVP retry prompt anti-fallback checkpoint:
  the failed-repair retry prompt now explicitly says that when a referenced
  `test_expectation` and related `rule` snippet are present, the rule snippet
  is the primary repair target, and the model must not add an
  `if ... else '<expected>'` fallback on the previous failed target line when
  that old text is not shown inside a `rule` snippet. Vast verification passed
  focused `prepare_failed_repair_retry` tests with
  `2 passed, 168 deselected`, full `tests/test_biber_agent_client.py -q`
  with `170 passed`, and the broader cheap MVP set
  `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py -q`
  with `188 passed`. Regenerated v9 artifacts are
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-review-context-v9.json`
  and
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-request-context-v9.json`.
  One bounded local-model retry probe wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-attempt-context-v9.json`;
  extraction wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-extraction-context-v9.json`
  with `ok=false`, `extraction_status=no_valid_edits`, `edits=[]`,
  `blocked_repeated_edits=0`, and no source/test edits. This is safer than v8
  because no fallback edit was proposed, but it is still not a successful
  repair. The v9 empty response evidence and review are
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-empty-retry-response-gap-context-v9.jsonl`
  and
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-empty-retry-response-gap-review-context-v9.json`.
  They remain review-only evidence; do not train from them automatically.
- Latest BIBER MVP retry source-root/proposed-rule checkpoint:
  pushed as `8d1db148 Use failed workspace for retry source context`.
  `prepare-failed-repair-retry` now prefers the failed verification
  `test_run.cwd` as the effective source root for compact retry snippets when
  that directory exists, while preserving the CLI `--source-root` as
  `requested_source_root` fallback metadata. This fixed the real v9 mismatch
  where snippets were collected from clean `/workspace/biber-ai-platform`
  instead of the failed temp clone at
  `/workspace/biber-real-repo-candidates/diagnosis-unified-diff-20260524T231913Z-110411/repo`.
  Regenerated v10 artifacts show
  `source_root_origin=verification_test_cwd` and include the actual bad rule
  line `_Rule(r"panicked at", "test_failure", ...)` from the failed workspace.
  The retry prompt now also derives assertion-diff hints and exact
  `suggested_rule_category_edits` from rule snippets, so future sessions can
  see the bounded rule edit candidate:
  change `_Rule(r"panicked at", "test_failure", "Rust test panic", "rust"),`
  to `_Rule(r"panicked at", "assertion_failure", "Rust test panic", "rust"),`.
  Vast verification passed focused retry-context tests with
  `5 passed, 166 deselected`, full `tests/test_biber_agent_client.py` with
  `171 passed`, and the full cheap pytest suite under `tests` with
  `332 passed`. No training run, OpenAI mentor call, credential change, API
  restart, or vLLM restart was used. Real local-model probes after this change
  are review-only artifacts: v11/v12/v14 fit the context window but still put
  the fallback-line edit in the first JSON object while describing the correct
  rule edit in prose; deterministic `review-retry-repair-edits` blocked them
  with `retry_edit_changes_previous_failed_target_outside_rule_context`.
  v13 exceeded the 8192-token vLLM context window at `--max-tokens 700`.
  Latest blocked review:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-review-context-v14.json`.
  Do not plan/apply/train from v11-v14. Next narrow gate: either add a
  deterministic review/export path for the JSON/prose mismatch plus suggested
  rule edit, or ask for explicit human approval before turning the
  `suggested_rule_category_edits` candidate into a plan/apply artifact.
  Vast was fast-forwarded to `8d1db14` and is clean; the temporary test-synced
  pre-pull copies of `scripts/biber_agent_client.py` and
  `tests/test_biber_agent_client.py` were stashed as
  `codex-retry-context-sync` and should not be popped unless deliberately
  inspecting that duplicate sync state.
- Latest BIBER MVP retry local-target planning checkpoint:
  `plan-repair-edits` now detects retry repair requests that carry
  `repair_request.source_context.source_root` and validates the reviewed edit
  against that failed workspace locally (`plan_mode=local_target_root`) instead
  of incorrectly planning against the clean live repo. Normal repair planning
  still uses the API workspace root, and `--target-root` can override the local
  root explicitly. `apply-repair-edits` can also use the `target_root` recorded
  by a successful plan artifact, but it still requires explicit `--approve`.
  `prepare-failed-repair-retry` now source-scans selected implementation files
  plus failing test-line context to derive exact rule-category suggestions even
  when compact snippets are aggressively trimmed. Regenerated v15 request:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-request-context-v15.json`.
  It includes a plan-safe suggested edit changing
  `_Rule(r"panicked at", "test_failure", "Rust test panic", "rust"),` to
  `_Rule(r"panicked at", "assertion_failure", "Rust test panic", "rust"),`.
  The local model copied the correct edit in v15; deterministic retry review
  passed with `review_status=retry_edit_ready_for_plan_review`,
  `ok=true`, `plan_allowed=true`, and no hard blockers:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-review-context-v15.json`.
  Local-target plan validation succeeded without applying edits:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-plan-context-v15-local-target.json`,
  `plan_hash=a51c2bbaff1f2494b5b557f7999a06745efa9bad266ef2912a92fe2a681469fb`,
  `planned=1`, `rejected=0`, target root
  `/workspace/biber-real-repo-candidates/diagnosis-unified-diff-20260524T231913Z-110411/repo`.
  No apply, training, OpenAI mentor call, credential change, API restart, or
  vLLM restart was used. Vast verification passed focused retry/plan tests
  with `16 passed, 157 deselected`, full `tests/test_biber_agent_client.py`
  with `173 passed`, and full cheap `tests` suite with `334 passed`.
  That explicit approval was later provided; see the following apply and
  verification checkpoint before taking any next action.
- Latest BIBER MVP retry local-target apply/verification checkpoint:
  the user explicitly approved applying the v15 local-target repair plan with
  `plan_hash=a51c2bbaff1f2494b5b557f7999a06745efa9bad266ef2912a92fe2a681469fb`.
  The approved Vast apply wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-edit-apply-context-v15-local-target.json`
  with `apply_status=applied`, `ok=true`, `planned=1`, `applied=1`, and
  `src/biber_api/test_diagnosis.py changed=True` in the failed temporary repo
  at
  `/workspace/biber-real-repo-candidates/diagnosis-unified-diff-20260524T231913Z-110411/repo`.
  Direct focused verification in that temp repo passed
  `tests/test_test_diagnosis.py -q` with `10 passed`. The client now carries
  the apply artifact `target_root` into `verify-repair-edits`, runs the
  allowlisted test locally against that temp repo, and records
  `test_mode=local_target_root`, `target_root`, and `target_root_source` in the
  saved verification artifact. Official verification wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-test-verification-context-v15-local-target.json`
  with `verification_status=passed`, `ok=true`, `test_id=pytest-test-diagnosis`,
  `test_mode=local_target_root`, `target_root_source=retry_source_context`, and
  stdout ending in `10 passed in 0.24s`. Vast verification passed focused
  `verify_repair_edits` client tests with `4 passed, 170 deselected`, full
  `tests/test_biber_agent_client.py -q` with `174 passed`, and full
  `tests -q` with `335 passed`. No training run, OpenAI mentor call,
  credential change, API restart, or vLLM restart was used. Vast was
  fast-forwarded to the pushed checkpoint and is clean; the temporary pre-pull
  file sync was stashed as `codex-retry-local-verify-sync` and should not be
  popped unless deliberately inspecting that duplicate sync state.
- Latest BIBER MVP v15 verified-repair review checkpoint: the passed v15
  local-target verification was exported and reviewed without promotion.
  `export-verified-repair` wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-verified-repairs-context-v15-local-target.jsonl`
  with `records=1`, `review_status=needs_human_review`,
  `training_allowed=false`, and `eligible_for_training=false`.
  `review-verified-repairs` wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-verified-repairs-review-context-v15-local-target.json`
  with `records=1`, `ready_for_human_review=1`, `rejected_records=0`,
  `training_allowed=false`, and `eligible_for_training=false`. A complete
  `show-repair-chain` summary was then saved at
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-chain-complete-context-v15-local-target.json`
  with `chain_complete=true`, `chain_status=ready_for_human_review`,
  `ok=true`, `plan_hash_consistent=true`, `verification_passed=true`,
  `repo_provenance_ready=true`, `training_allowed=false`,
  `safe_to_train=false`, and `github_save_ready=false`. The ready-chain list,
  export, and review were also run with a pattern limited to that complete v15
  chain. They wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-list-context-v15-local-target.json`,
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chains-context-v15-local-target.jsonl`,
  and
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-review-context-v15-local-target.json`.
  The ready-chain review reports `records=1`, `ready_for_human_review=1`,
  `repo_provenance_ready=1`, `repo_provenance_missing=0`,
  `review_status=needs_human_review`, `training_allowed=false`,
  `safe_to_train=false`, and `github_save_ready=false`. No training run,
  OpenAI mentor call, credential change, API restart, or vLLM restart was
  used. The user later explicitly approved `approve_for_eval` for this v15
  ready repair-chain; see the following checkpoint before taking any next
  action.
- Latest BIBER MVP v15 eval-candidate review checkpoint: the user explicitly
  approved `approve_for_eval` for the v15 ready repair-chain decision. The
  decision was recorded with reviewer `user`, evidence source type
  `real_repo_candidate`, and notes that it is eval-only with no training or
  GitHub-save approval. Decision export wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-decisions-context-v15-local-target.jsonl`
  with `records=1`, `decision=approve_for_eval`,
  `repo_provenance_ready=1`, `training_allowed=false`,
  `safe_to_train=false`, `approved_for_training=false`, and
  `github_save_ready=false`. Decision review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-decision-review-context-v15-local-target.json`
  with `approved_for_eval_records=1`,
  `decision_counts={'approve_for_eval': 1}`, `training_allowed=false`, and
  `safe_to_train=false`. Eval-candidate export wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-eval-candidates-context-v15-local-target.jsonl`
  with `records=1`, `eval_candidates=1`, `repo_provenance_ready=1`,
  `requires_dataset_review=true`, `eval_dataset_ready=false`, and
  `training_allowed=false`. Eval-candidate review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-eval-candidate-review-context-v15-local-target.json`
  with `records=1`, `ready_for_dataset_review=1`,
  `review_status=eval_candidates_need_dataset_review`,
  `requires_dataset_review=true`, `eval_dataset_ready_records=0`,
  `eval_dataset_ready=false`, `training_allowed=false`, and
  `safe_to_train=false`. No training run, OpenAI mentor call, credential
  change, API restart, or vLLM restart was used. The user later explicitly
  approved `approve_for_eval_dataset`; see the following checkpoint before
  taking any next action.
- Latest BIBER MVP v15 held-out eval checkpoint: the user explicitly approved
  `approve_for_eval_dataset` for the v15 eval candidate. The eval-dataset
  decision was recorded with reviewer `user` and notes that it is eval-dataset
  only with no training, GitHub-save, or OpenAI mentor approval. Decision export
  wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-eval-dataset-decisions-context-v15-local-target.jsonl`
  with `records=1`, `decision=approve_for_eval_dataset`,
  `approved_for_eval_dataset_records=1`, `eval_dataset_ready=true`,
  `training_allowed=false`, and `safe_to_train=false`. Decision review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-eval-dataset-decision-review-context-v15-local-target.json`
  with `approved_for_eval_dataset_records=1`,
  `decision_counts={'approve_for_eval_dataset': 1}`,
  `eval_dataset_ready_records=1`, `training_allowed=false`, and
  `safe_to_train=false`. Eval-dataset export wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-eval-dataset-context-v15-local-target.jsonl`
  with `records=1`, `eval_dataset_records=1`, `eval_dataset_ready=true`, and
  `training_allowed=false`. Validation wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-eval-dataset-validation-context-v15-local-target.json`
  with `ok=true`, `validation_status=valid_eval_only`, `valid_records=1`,
  `invalid_records=0`, `errors=[]`, and `training_allowed=false`. Prompt export
  wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-eval-prompts-context-v15-local-target.jsonl`
  with `records=1`, `eval_prompts=1`, `eval_only=true`, and
  `training_allowed=false`. A first generic
  `scripts/vast_eval_repair_chain_prompts_direct.sh` run accidentally selected
  the older standard prompt file under
  `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/`;
  treat `/workspace/outputs/evals/biber-repair-chain-heldout-20260525T094651Z.*`
  as unrelated to this v15 approval. The v15-specific run was rerun with
  `BIBER_REPAIR_CHAIN_EVAL_PROMPTS` pointing to the v15 prompt JSONL and wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-context-v15-local-target.jsonl`
  plus
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-context-v15-local-target.summary.json`;
  it reported `1/1 responses` and `1/1 expectation checks passed`. Held-out
  eval review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-review-context-v15-local-target.json`
  with `ok=true`, `review_status=heldout_eval_passed`, `records=1`,
  `passed_records=1`, `failed_records=0`, `expectation_failed_records=0`,
  `model_counts={'biber-dev-core-v1': 1}`, `eval_only=true`,
  `training_allowed=false`, and `safe_to_train=false`. No training run, OpenAI
  mentor call, credential change, API restart, or vLLM restart was used. The
  user later explicitly approved `accept_for_baseline`; see the following
  checkpoint before taking any next action.
- Latest BIBER MVP v15 baseline-candidate checkpoint: the user explicitly
  approved `accept_for_baseline` for the v15 held-out eval review. The decision
  was recorded with reviewer `user` and notes that it is baseline-candidate
  only with no training, model promotion, GitHub-save, or OpenAI mentor
  approval. Decision export wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-decisions-context-v15-local-target.jsonl`
  with `records=1`, `decision=accept_for_baseline`,
  `accepted_for_baseline_records=1`, `baseline_candidate_ready=true`,
  `training_allowed=false`, and `safe_to_train=false`. Decision review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-decision-review-context-v15-local-target.json`
  with `accepted_for_baseline_records=1`,
  `decision_counts={'accept_for_baseline': 1}`,
  `baseline_candidate_ready_records=1`, `training_allowed=false`, and
  `safe_to_train=false`. Baseline-candidate export wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-baseline-candidates-context-v15-local-target.jsonl`
  with `records=1`, `baseline_candidates=1`, `baseline_candidate_ready=true`,
  `baseline_ready=false`, `requires_baseline_review=true`, and
  `training_allowed=false`. Baseline-candidate review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-baseline-candidate-review-context-v15-local-target.json`
  with `records=1`, `baseline_candidates=1`,
  `baseline_candidate_ready_records=1`, `baseline_ready_records=0`,
  `requires_baseline_review_records=1`, `review_status=heldout_baseline_candidate_summary_only`,
  `training_allowed=false`, and `safe_to_train=false`. No training run, OpenAI
  mentor call, credential change, API restart, or vLLM restart was used. The
  user later explicitly approved `approve_as_baseline`; see the following
  checkpoint before taking any next action.
- Latest BIBER MVP v15 training-readiness checkpoint: the user explicitly
  approved `approve_as_baseline` for the v15 held-out baseline candidate. The
  decision was recorded with reviewer `user` and notes that it is a baseline
  decision only with no training, model promotion, GitHub-save, or OpenAI mentor
  approval. Baseline decision export wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-baseline-decisions-context-v15-local-target.jsonl`
  with `records=1`, `decision=approve_as_baseline`,
  `approved_as_baseline_records=1`, `baseline_ready=true`,
  `training_allowed=false`, and `safe_to_train=false`. Baseline decision review
  wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-baseline-decision-review-context-v15-local-target.json`
  with `approved_as_baseline_records=1`,
  `decision_counts={'approve_as_baseline': 1}`, `baseline_ready_records=1`,
  `requires_baseline_review_records=0`, `training_allowed=false`, and
  `safe_to_train=false`. Training-readiness review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-training-readiness-context-v15-local-target.json`
  with `review_status=baseline_ready_manual_training_review_required`,
  `training_gate_status=manual_review_required`, `baseline_ready_records=1`,
  `ready_for_manual_training_dataset_review=true`, `training_allowed=false`,
  and required manual actions `human_training_dataset_review`,
  `explicit_user_approval_before_any_training_job`, and
  `separate_vast_gpu_training_run_outside_codex_loop`. Training-candidate export
  wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-training-candidates-context-v15-local-target.jsonl`
  with `records=1`, `training_candidate_records=1`,
  `training_dataset_ready=false`, `review_queue_only=true`, and
  `training_allowed=false`. Training-candidate review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-training-candidate-review-context-v15-local-target.json`
  with `review_status=training_candidates_need_review`, `records=1`,
  `pending_review_records=1`, `empty_output_records=1`,
  `unreviewed_quality_records=1`, `ready_for_dataset_validation=false`, and
  hard blockers `candidate_outputs_missing`, `candidate_quality_not_reviewed`,
  and `below_min_ready_records`. A first `review-repair-chain-training-pipeline`
  run against the v15 source directory expected standard artifact names and
  produced
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-training-pipeline-context-v15-local-target.json`
  with missing standard-name artifacts; treat that file as a naming-mismatch
  probe, not the valid v15 pipeline status. Corrected standard-name review
  copies were created under
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/v15-training-pipeline-standard-artifacts/`,
  and the valid pipeline status is
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/v15-training-pipeline-standard-artifacts/agent-client-mvp-loop-repair-chain-training-pipeline.json`.
  It reports `training_pipeline_status=blocked`,
  `training_gate_status=manual_review_required`, `baseline_ready_records=1`,
  `training_candidate_records=1`, `ready_for_manual_training_dataset_review=true`,
  `ready_for_dataset_validation=false`, `training_allowed=false`, and hard
  blockers `candidate_outputs_missing`, `candidate_quality_not_reviewed`,
  `below_min_ready_records`, and `dataset_validation_not_ready`. No training
  run, OpenAI mentor call, credential change, API restart, or vLLM restart was
  used. Next manual gate: inspect/fill the training-candidate output only if it
  is genuinely valuable, mark quality only after human review, then validate a
  training dataset; do not infer this from a generic "continue", and do not
  start QLoRA or any training job without a separate explicit training approval.
- Latest BIBER MVP v15 training-candidate evidence checkpoint: the v15
  training candidate was inspected and left unfilled. The original candidate
  input contained only the baseline-ready group summary, and the held-out model
  answer was generic (`Ensure the test pytest-test-diagnosis is rerun with the
  updated code`) instead of the exact source repair. The linked repair attempt
  remains useful evidence because it did produce the verified strict JSON edit
  changing `src/biber_api/test_diagnosis.py` from
  `_Rule(r"panicked at", "test_failure", "Rust test panic", "rust"),` to
  `_Rule(r"panicked at", "assertion_failure", "Rust test panic", "rust"),`, but
  do not fill the training output from the thin original candidate row. The
  exporter now enriches future `export-repair-chain-training-candidates` rows
  with a compact `evidence` object plus an `Evidence summary for human review`
  input section. The evidence includes the baseline decision review path,
  held-out eval review paths, held-out eval result paths, content previews, and
  the same safety flags, while keeping `training_allowed=false` and
  `safe_to_train=false`. Regenerated v15 enriched artifacts:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-training-candidates-enriched-context-v15-local-target.jsonl`
  and
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-training-candidate-review-enriched-context-v15-local-target.json`.
  The enriched candidate review still reports `review_status=training_candidates_need_review`,
  `pending_review_records=1`, `empty_output_records=1`,
  `unreviewed_quality_records=1`, `ready_for_dataset_validation=false`, and hard
  blockers `candidate_outputs_missing`, `candidate_quality_not_reviewed`, and
  `below_min_ready_records`. Vast verification passed focused
  `training_candidates` tests with `4 passed, 170 deselected`, full
  `tests/test_biber_agent_client.py -q` with `174 passed`, and full
  `tests -q` with `335 passed`. No training run, OpenAI mentor call,
  credential change, API restart, or vLLM restart was used. Next safe path is
  either to collect a richer real-repo repair chain whose training candidate
  carries enough concrete task/failure/patch evidence, or to ask the user for
  explicit approval before manually filling this v15 candidate. Do not start
  QLoRA or any training job without a separate explicit training approval.
- Latest BIBER MVP eval-prompt evidence checkpoint: the v15 held-out eval prompt
  was enriched so future `export-ready-repair-chain-eval-prompts` rows load
  compact linked repair evidence directly from repair/attempt/extraction/plan/
  apply/verification artifacts. The prompt now includes exact suggested and
  extracted edits, plan/apply summaries, verification status/stdout preview,
  and the model response preview when available, while preserving
  `training_allowed=false` and `safe_to_train=false`. Regenerated v15 enriched
  prompt:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-ready-chain-eval-prompts-enriched-context-v15-local-target.jsonl`.
  It includes the exact edit in `src/biber_api/test_diagnosis.py`, changing the
  Rust panic rule category from `test_failure` to `assertion_failure`, plus the
  passing `pytest-test-diagnosis` verification output. The enriched local Vast
  held-out eval wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-enriched-context-v15-local-target.jsonl`
  and
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-enriched-context-v15-local-target.summary.json`,
  with `1/1 responses` and `1/1 expectation checks passed`. Review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-review-enriched-context-v15-local-target.json`
  with `ok=true`, `review_status=heldout_eval_passed`, `passed_records=1`, and
  `training_allowed=false`. Unlike the earlier generic eval answer, the
  enriched model response names file `src/biber_api/test_diagnosis.py`, the
  exact `test_failure` to `assertion_failure` rule-category edit, and the test
  `pytest-test-diagnosis`. Vast verification passed focused eval/training
  candidate tests with `8 passed, 166 deselected`, full
  `tests/test_biber_agent_client.py -q` with `174 passed`, and full
  `tests -q` with `335 passed`. No training run, OpenAI mentor call,
  credential change, API restart, or vLLM restart was used. Next safe path:
  if this enriched eval answer should replace the earlier generic baseline path,
  run the same manual decision ladder on the enriched held-out eval review
  (`accept_for_baseline`, then `approve_as_baseline`) before considering any
  training-candidate fill; do not skip the review gates or start QLoRA without
  separate explicit training approval.
- Latest enriched v15 held-out eval baseline-candidate checkpoint: the user
  explicitly approved `accept_for_baseline` for the enriched v15 held-out eval
  review on 2026-05-25. The decision was recorded at
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-decisions-enriched-context-v15-local-target.jsonl`
  with `accepted_for_baseline_records=1`, `baseline_candidate_ready=true`,
  `training_allowed=false`, and `safe_to_train=false`. The decision review
  wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-eval-decision-review-enriched-context-v15-local-target.json`
  with `accepted_for_baseline_records=1`,
  `baseline_candidate_ready_records=1`,
  `decision_counts={'accept_for_baseline': 1}`, `training_allowed=false`, and
  `safe_to_train=false`. Exported enriched baseline candidates at
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-baseline-candidates-enriched-context-v15-local-target.jsonl`
  with `baseline_candidates=1`, `baseline_candidate_ready=true`,
  `baseline_ready=false`, `requires_baseline_review=true`, and
  `training_allowed=false`. Baseline candidate review wrote
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-unified-diff-20260524T231913Z-110411/agent-client-mvp-loop-failed-repair-retry-heldout-baseline-candidate-review-enriched-context-v15-local-target.json`
  with `baseline_candidate_ready_records=1`, `baseline_ready_records=0`,
  `requires_baseline_review_records=1`, `training_allowed=false`, and
  `safe_to_train=false`. No training run, OpenAI mentor call, credential change,
  API restart, or vLLM restart was used. Next manual gate: the user must
  explicitly approve `approve_as_baseline` for this enriched v15 baseline
  candidate if they want to promote it to baseline-ready; do not infer that
  approval from a generic "continue" request, and do not start QLoRA without
  separate explicit training approval.
- Latest source-only repair probe artifact:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-source-guard-20260524T210618Z-110014`.
  The local model again proposed a test-file diff for
  `tests/test_test_diagnosis.py` instead of the source file. Reprocessing the
  saved repair attempt offline with the new guard wrote
  `agent-client-mvp-loop-repair-edit-extraction-source-guard.json`, reporting
  `ok=false`, `extraction_status=no_valid_edits`, `source_only_guard.enabled=true`,
  `blocked_test_edits=1`, and rejected reason
  `freeform_test_file_edit_blocked_by_source_only_instruction`. This is useful
  repair-loop failure evidence only; do not mark it trainable or fill any
  training-candidate output from it.
- Latest richer temporary real-repo repair-chain probe on Vast:
  `/workspace/outputs/biber-real-repo-candidate-diagnosis-context-20260524T034514Z-109079`.
  The temp clone injected a source regression in
  `src/biber_api/test_diagnosis.py` by changing the Rust panic rule from
  `assertion_failure` to `test_failure`. With the diagnosis fix and the focused
  `pytest-test-diagnosis` command, `mvp-loop` reported
  `Detected assertion_failure in python output from 2 signal(s)` and avoided
  the unrelated `pytest-core` XRIQ preflight noise. The local model still tried
  to edit tests or emitted no valid bounded source edit; extraction ended
  `no_valid_edits`. Treat this as useful failure evidence, not a trainable row.
  Temporary APIs were stopped; the live Vast API on port `8000` remained
  running. Next narrow gate: improve source-only repair prompting/extraction or
  add stronger test-edit rejection before trying to collect another repair
  candidate. Do not fill training-candidate outputs or start QLoRA from this
  probe.
- Latest BIBER API/XRIQ wrapper commits pushed and Vast-verified:
  `ddc5dc8 Add BIBER XRIQ preflight API wrapper` and
  `67ce353 Add XRIQ wrapper Rust environment config`.
- Latest BIBER API/XRIQ read-wrapper commit pushed and Vast-verified:
  `4d8c251 Add BIBER XRIQ read wrappers`.
- Latest BIBER API/XRIQ durable mempool wrapper commit pushed and
  Vast-verified:
  `81824b3 Add XRIQ durable mempool wrapper`.
- Latest BIBER API/XRIQ explorer/block wrapper commit pushed and Vast-verified:
  `32909e8 Add BIBER XRIQ explorer wrappers`.
- Latest BIBER API/XRIQ consolidated smoke script commit pushed and
  Vast-verified:
  `16e506b Add BIBER XRIQ API smoke script`.
- Latest BIBER API/XRIQ snapshot wrapper commit pushed and Vast-verified:
  `4dbe7a0 Add BIBER XRIQ snapshot API wrapper`.
- Latest BIBER API/XRIQ snapshot discovery commit pushed and Vast-verified:
  `fc03d6d Add XRIQ snapshot discovery API`.
- Latest BIBER API/XRIQ private-devnet overview commit pushed and
  Vast-verified:
  `716e9c1 Add XRIQ private devnet overview API`.
- Latest BIBER API/XRIQ private-devnet client commit pushed and
  Vast-verified:
  `2bb7ca0 Add BIBER XRIQ private devnet client`.
- Latest BIBER API/XRIQ private-devnet dashboard commit pushed and
  Vast-verified:
  `afa080b Add XRIQ private devnet dashboard`.
- Latest BIBER API/XRIQ dashboard preflight-action commit pushed and
  Vast-verified:
  `f5f55a4 Add XRIQ dashboard preflight action`.
- Latest BIBER API/XRIQ dashboard transaction-lookup commit pushed and
  Vast-verified:
  `0e7975c Add XRIQ dashboard transaction lookup`.
- Latest BIBER API/XRIQ dashboard account-lookup commit pushed and
  Vast-verified:
  `4af1ee5 Add XRIQ dashboard account lookup`.
- Latest XRIQ explorer transaction-hash navigation commit pushed and
  Vast-verified:
  `6205b66 Expose XRIQ block transaction hashes`.
- Last XRIQ implementation commit pushed and Vast-verified:
  `919b348 Expose XRIQ replay state root`.
- Latest XRIQ checked-fixture-only commit pushed and Vast-verified:
  `66098c1 Add XRIQ block detail JSON fixture`.
- Latest XRIQ smoke-harness commit pushed and Vast-verified:
  `919b348 Expose XRIQ replay state root`.
- Latest XRIQ snapshot export/import commit pushed and Vast-verified:
  `fba4a1d Add XRIQ snapshot export import`.
- Latest BIBER MVP core-agent test-runner commit pushed and Vast-verified:
  `d4df8c0 Add allowlisted BIBER test runner API`.
- Latest BIBER MVP bounded workspace-edit commit pushed and Vast-verified:
  `992890b Add bounded BIBER workspace edit API`.
- Latest BIBER MVP GitHub branch/PR workflow commits pushed and Vast-verified:
  `552220b Add BIBER GitHub PR workflow support` and
  `179f58b Clarify GitHub workflow test label`.
- Latest BIBER MVP end-to-end agent-smoke script commit pushed and
  Vast-verified:
  `28ebe62 Add BIBER agent smoke script`.
- Latest BIBER MVP synthetic-safe agent-smoke guard commit pushed and
  Vast-verified:
  `2afa40e Keep agent smoke eval guard synthetic-safe`.
- Latest BIBER MVP real-repo approval guard commit pushed and Vast-verified:
  `d9448ec Reject smoke repair chains at approval`.
- Latest BIBER MVP repo-provenance repair-chain approval commits pushed and
  Vast-verified:
  `23d5977 Require repo provenance for repair eval approval` and
  `4508e67 Preserve repo provenance in repair decisions`.
- Latest BIBER MVP repair-chain git-provenance helper commit pushed and
  Vast-verified:
  `71119b7 Auto derive repair chain repo provenance`.
- Latest BIBER MVP ready repair-chain provenance-review counter commit pushed
  and Vast-verified:
  `56687b7 Show repo provenance readiness in repair reviews`.
- Latest BIBER MVP repair-chain decision provenance counter commit pushed and
  Vast-verified:
  `dc255bb Show provenance readiness in repair decisions`.
- Latest BIBER MVP eval-candidate provenance counter commit pushed and
  Vast-verified:
  `b138544 Show provenance readiness in eval candidates`.
- Latest BIBER MVP repair-chain list provenance counter commit pushed and
  Vast-verified:
  `80cee7b Show provenance readiness in repair chain list`.
- Latest BIBER MVP repair-edit extraction alias commit pushed and Vast-verified:
  `87f0f24 Accept file alias in repair edit extraction`.
- Latest real repo repair-chain eval-candidate checkpoint created on Vast:
  `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-candidate-review.json`.
- Latest real repo repair-chain eval-dataset/prompt checkpoint created on Vast:
  `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-prompts.jsonl`.
- Latest real repo repair-chain held-out eval review checkpoint created on
  Vast:
  `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-eval-review.json`.
- Latest real repo repair-chain held-out baseline-candidate review checkpoint
  created on Vast:
  `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-baseline-candidate-review.json`.
- Latest real repo repair-chain baseline decision and training-readiness
  checkpoint created on Vast:
  `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-training-readiness.json`.
- Latest real repo repair-chain training-candidate and pipeline review
  checkpoint created on Vast:
  `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-training-pipeline.json`.
- Latest real repo repair-chain training-candidate quality inspection:
  candidate intentionally left unfilled because the underlying repair is a
  toy one-line syntax fixture, not a high-value repo-specific training example.
- Latest BIBER MVP agent-session API/persistence commits pushed and
  Vast-verified:
  `b280d49 Add BIBER agent session API` and
  `786ec51 Persist BIBER agent sessions`.
- Latest BIBER MVP agent-session XRIQ-context commit pushed and Vast-verified:
  `e4df1d0 Add XRIQ context to agent sessions`.
- Latest BIBER MVP agent-capabilities commit pushed and Vast-verified:
  `8a539de Add BIBER agent capabilities endpoint`.
- Latest BIBER MVP agent-client helper commit pushed and Vast-verified:
  `51ad833 Add BIBER agent client helper`.
- Latest BIBER MVP agent-client create-session smoke commit pushed and
  Vast-verified:
  `6317641 Add agent client create-session smoke`.
- Latest BIBER MVP agent-client session-history commands commit pushed and
  Vast-verified:
  `b8abdfb Add agent client session history commands`.
- Latest BIBER MVP agent-client repo-context planning commit pushed and
  Vast-verified:
  `775b278 Add agent client repo context planning`.
- Latest BIBER MVP agent-client workspace-edit commands commit pushed and
  Vast-verified:
  `12450e2 Add agent client workspace edit commands`.
- Latest BIBER MVP agent-client test/diagnosis commands commit pushed and
  Vast-verified:
  `b0d1df6 Add agent client test diagnosis commands`.
- Latest BIBER MVP agent-client GitHub workflow commands commit pushed and
  Vast-verified:
  `a3ba952 Add agent client GitHub workflow commands`.
- Latest BIBER MVP agent-client MVP-loop command commit pushed and
  Vast-verified:
  `1ce9f60 Add agent client MVP loop command`.
- Latest BIBER MVP agent-client MVP-loop artifact commit pushed and
  Vast-verified:
  `38e3701 Add MVP loop output artifact option`.
- Latest BIBER MVP agent-client MVP-loop artifact viewer commit pushed and
  Vast-verified:
  `8c077d2 Add MVP loop artifact viewer`.
- Latest BIBER MVP agent-client MVP-loop artifact listing commit pushed and
  Vast-verified:
  `841dc8f Add MVP loop artifact listing`.
- Latest BIBER MVP agent-client failed MVP-loop artifact filter commit pushed
  and Vast-verified:
  `be89b78 Filter failed MVP loop artifacts`.
- Latest BIBER MVP agent-client MVP-loop failure export commit pushed and
  Vast-verified:
  `ef0cd5e Export MVP loop failure review records`.
- Latest BIBER MVP agent-client repair-request helper commit pushed and
  Vast-verified:
  `2e7a405 Add MVP loop repair request helper`.
- Latest BIBER MVP agent-client local-model repair-attempt commits pushed and
  Vast-verified:
  `fe2bb50 Add MVP repair attempt client flow` and
  `8b2d200 Fix repair attempt smoke context paths`.
- Latest BIBER MVP agent-client repair-edit extraction commits pushed and
  Vast-verified:
  `da92ebf Add repair edit extraction helper` and
  `c9ec3d7 Fix repair edit JSON extraction duplicates`.
- Latest BIBER MVP agent-client repair-edit planning commit pushed and
  Vast-verified:
  `4c7aea5 Add repair edit planning helper`.
- Latest BIBER MVP agent-client guarded repair-edit apply commit pushed and
  Vast-verified:
  `cfed893 Add guarded repair edit apply helper`.
- Latest BIBER MVP agent-client repair-test verification commit pushed and
  Vast-verified:
  `2ae4a02 Add repair test verification helper`.
- Latest BIBER MVP verified repair review export commit pushed and
  Vast-verified:
  `9b22ef5 Add verified repair review export`.
- Latest BIBER MVP verified repair review summary commit pushed and
  Vast-verified:
  `caabb32 Add verified repair review summary`.
- Latest BIBER MVP repair-chain summary commit pushed and Vast-verified:
  `6af885c Add repair chain summary helper`.
- Latest BIBER MVP repair-chain artifact listing commit pushed and
  Vast-verified:
  `a4799fe Add repair chain artifact listing`.
- Latest BIBER MVP ready repair-chain review export commit pushed and
  Vast-verified:
  `559c30d Export ready repair chains for review`.
- Latest BIBER MVP ready repair-chain review summary commit pushed and
  Vast-verified:
  `6c90400 Review ready repair chain queues`.
- Latest BIBER MVP ready repair-chain decision recording commit pushed and
  Vast-verified:
  `dc76ae6 Record ready repair chain decisions`.
- Latest BIBER MVP ready repair-chain decision review commit pushed and
  Vast-verified:
  `6566caf Review ready repair chain decisions`.
- Latest BIBER MVP repair-chain eval-candidate export commit pushed and
  Vast-verified:
  `415af7a Export repair chain eval candidates`.
- Latest BIBER MVP repair-chain eval-candidate review commit pushed and
  Vast-verified:
  `4d4ddca Review repair chain eval candidates`.
- Latest BIBER MVP repair-chain eval-dataset decision commit pushed and
  Vast-verified:
  `bb6fdc0 Record repair chain eval dataset decisions`.
- Latest BIBER MVP repair-chain eval-dataset decision review commit pushed and
  Vast-verified:
  `f600ab0 Review repair chain eval dataset decisions`.
- Latest BIBER MVP repair-chain eval-dataset export commit pushed and
  Vast-verified:
  `22566dc Export repair chain eval dataset records`.
- Latest BIBER MVP repair-chain eval-dataset validation commit pushed and
  Vast-verified:
  `78608bb Validate repair chain eval dataset records`.
- Latest BIBER MVP repair-chain held-out eval prompt export commit pushed and
  Vast-verified:
  `16523ac Export repair chain eval prompts`.
- Latest BIBER MVP repair-chain held-out eval runner commit pushed and
  Vast-verified:
  `95051e5 Add repair chain heldout eval runner`.
- Latest BIBER MVP repair-chain held-out eval result review commit pushed and
  Vast-verified:
  `28353e8 Review repair chain heldout eval results`.
- Latest BIBER MVP repair-chain held-out eval decision commit pushed and
  Vast-verified:
  `c254677 Record heldout eval decisions`.
- Latest BIBER MVP repair-chain held-out eval decision review commit pushed and
  Vast-verified:
  `bf01ce2 Review heldout eval decisions`.
- Latest BIBER MVP repair-chain held-out baseline candidate export commit
  pushed and Vast-verified:
  `e7f3fe5 Export heldout baseline candidates`.
- Latest BIBER MVP repair-chain held-out baseline candidate review commit
  pushed and Vast-verified:
  `c1fdba8 Review heldout baseline candidates`.
- Latest BIBER MVP repair-chain held-out baseline decision commit pushed and
  Vast-verified:
  `55713f4 Record heldout baseline decisions`.
- Latest BIBER MVP repair-chain held-out baseline decision review commit pushed
  and Vast-verified:
  `a045c63 Review heldout baseline decisions`.
- Latest BIBER MVP repair-chain training readiness review commit pushed and
  Vast-verified:
  `c356d70 Add repair chain training readiness review`.
- Latest BIBER MVP repair-chain training candidate export commit pushed and
  Vast-verified:
  `966ba05 Add repair chain training candidate export`.
- Latest BIBER MVP repair-chain training candidate review commit pushed and
  Vast-verified:
  `693a1ca Add repair chain training candidate review`.
- Latest Rust/XRIQ eval codegen-profile commits pushed and Vast-verified:
  `176b3e4 Add Rust XRIQ eval codegen profile`,
  `706448e Limit Rust XRIQ eval profile to ledger prompt`,
  `5788422 Refine Rust XRIQ ledger eval profile`,
  `bab1c38 Guide Rust XRIQ ledger borrow-safe output`,
  `b694eaa Prevent cloned ledger map output in XRIQ eval`, and
  `7e7b8d Clarify XRIQ ledger fee semantics in eval profile`.
- Latest BIBER MVP repo-adaptation commits pushed and Vast-verified:
  `9126fdd Add BIBER repo adaptation plan` and
  `2efa65b Fix repo adaptation relative role detection`.
- Latest BIBER MVP repo-context planner commit pushed and Vast-verified:
  `1cc790a Add BIBER repo context planner`.
- Latest BIBER MVP multi-file edit planner commit pushed and Vast-verified:
  `70e6320 Add BIBER multi-file edit planner`.
- Latest BIBER MVP test-failure diagnosis commit pushed and Vast-verified:
  `1fd510f Add BIBER test failure diagnosis`.
- Latest BIBER MVP frontend test-failure diagnosis commit pushed and
  Vast-verified:
  `bec42c8 Improve frontend test diagnosis`.
- Latest BIBER MVP agent-session test-diagnosis commit pushed and
  Vast-verified:
  `3069a50 Add agent-session test diagnosis`.
- Latest BIBER MVP `.NET`/Java test-command commit pushed and Vast-verified:
  `c5f7235 Add dotnet and java test commands`.
- Latest BIBER MVP repo-context stack-profile commit pushed and Vast-verified:
  `6050bd0 Add repo context stack profiles`.
- Latest BIBER MVP hash-gated multi-file edit-apply commits pushed and
  Vast-verified:
  `0f9a450 Add hash-gated workspace edit apply` and
  `79aad96 Fix stale workspace edit apply hash check`.
- Latest BIBER MVP repo-adaptation live-eval wrapper commits pushed and
  Vast-verified:
  `8fca321 Add repo adaptation live eval wrapper` and
  `81b9dd5 Fix repo adaptation eval direct execution`.
- Latest BIBER MVP repo-adaptation failure-review commit pushed and
  Vast-verified:
  `68479ad Add repo adaptation failure review`.
- Latest BIBER capability-roadmap TensorFlow docs commit pushed and
  Vast-fast-forwarded:
  `07eb63f Add TensorFlow capability track`.
- Latest BIBER repair-chain training pipeline status commits pushed and
  Vast-verified:
  `244ac7c Add repair chain training pipeline status` and
  `76c4401 Surface training pipeline status in smoke summary`.
- Latest BIBER repair-chain training pipeline listing commit pushed and
  Vast-verified:
  `c4abe43 List repair chain training pipeline statuses`.
- Latest BIBER repo-adaptation candidate review commit pushed and
  Vast-verified:
  `a1b9f5a Add repo adaptation candidate review`.
- Latest BIBER repo-adaptation candidate decisions commit pushed and
  Vast-verified:
  `a53be7a Add repo adaptation candidate decisions`.
- Latest BIBER repo-adaptation dataset-merge commit pushed and Vast-verified:
  `436f955 Add repo adaptation dataset merge`.
- Latest BIBER repo-adaptation dataset-readiness commit pushed and
  Vast-verified:
  `299af9b Add repo adaptation dataset readiness review`.
- Latest BIBER repo-adaptation expanded-prompt commit pushed and
  Vast-verified:
  `356872d Add expanded repo adaptation prompts`.
- Latest BIBER repo-adaptation balanced expanded-prompt commit pushed and
  Vast-verified:
  `71e9f92 Balance repo adaptation expanded prompts`.
- Latest BIBER repo-adaptation manual training-review gate commit pushed and
  Vast-verified:
  `3ef6834 Add repo adaptation training review gate`.
- Latest Vast training approval guard commit pushed and Vast-verified:
  `b0d5f49 Require explicit approval for Vast training`.
- Latest adapter promotion-review gate commit pushed and Vast-verified:
  `1834035 Add adapter promotion review gate`.
- Latest Vast candidate adapter review wrapper commit pushed and Vast-verified:
  `426fcd3 Add Vast candidate adapter review wrapper`.
- Latest candidate adapter review newest-artifact selection fix pushed and
  Vast-verified:
  `4f3bb4c Use newest artifacts in candidate adapter review`.
- Latest adapter promotion same-as-stable blocker pushed and Vast-verified:
  `25cc41e Block promotion of current stable adapter`.
- Latest repo held-out promotion margin gate pushed and Vast-verified:
  `600bff1 Require repo eval improvement margin`.
- Latest candidate-review same-as-stable fast-fail guard pushed and
  Vast-verified:
  `c38c0a7 Fail fast on stable candidate review`.
- Latest candidate-review adapter-reload fix pushed and Vast-verified:
  `608252b Restart services when reviewing candidate adapter`.
- Latest repo-adaptation anti-regression review helper commit pushed and
  Vast-verified:
  `08fdd59 Add repo adaptation regression review`.
- Latest repo-adaptation training-outcome review helper commit pushed and
  Vast-verified:
  `77837d2 Add repo adaptation training outcome review`.
- Latest profiled regression eval path commits pushed and Vast-verified:
  `e428d7b Add profiled regression eval path` and
  `426f602 Refine Rust profile for next height`.
- Latest BIBER runtime-profile contract commits pushed and Vast-verified:
  `cf4b621 Add BIBER runtime profile contract` and
  `6fd6f1a Mirror runtime profiles in live app`.
- Latest Vast API-only restart helper and capability-smoke commits pushed and
  Vast-verified:
  `2a4b713 Add Vast API-only restart helper` and
  `2c40099 Check agent capabilities in Vast smoke`.
- Latest BIBER agent-client runtime-profile ID support commit pushed and
  Vast-verified:
  `66a44f6 Add runtime profile IDs to BIBER client`.
- Latest Vast runtime-profile enabled smoke commit pushed and Vast-verified:
  `3e1a097 Add Vast runtime profile smoke`.
- Latest Vast stable profile-baseline script commit pushed and Vast-verified:
  `3e44edc Add Vast profile baseline script`.
- Latest BIBER MVP-loop runtime-profile carry-through commit pushed and
  Vast-verified:
  `abc836e Carry runtime profiles through MVP repairs`.
- Latest BIBER prepared repair-attempt commit pushed and Vast-verified:
  `1a1b9aa Allow prepared repair attempts`.
- Latest BIBER repair-attempt artifact inspection commits pushed and
  Vast-verified:
  `3a689d8 Add repair attempt artifact inspection` and
  `593d035 Preserve runtime profile in repair smoke fixture`.
- Latest BIBER repair-edit extraction artifact inspection commit pushed and
  Vast-verified:
  `ebe5c25 Add repair edit extraction inspection`.
- Latest BIBER repair-edit plan artifact inspection commit pushed and
  Vast-verified:
  `e311321 Add repair edit plan inspection`.
- Latest BIBER repair-edit apply artifact inspection commit pushed and
  Vast-verified:
  `15d1544 Add repair edit apply inspection`.
- Latest BIBER repair-test verification artifact inspection commit pushed and
  Vast-verified:
  `ad901453 Add repair test verification inspection`.
- Latest BIBER verified repair review artifact inspection commit pushed and
  Vast-verified:
  `4c79b104 Add verified repair review inspection`.
- Latest BIBER ready repair-chain review artifact inspection commit pushed and
  Vast-verified:
  `02573955 Add ready repair chain review inspection`.
- Latest BIBER ready repair-chain decision review artifact inspection commit
  pushed and Vast-verified:
  `86e84477 Add ready repair chain decision review inspection`.
- Latest BIBER ready repair-chain eval-candidate review artifact inspection
  commit pushed and Vast-verified:
  `3ac6544d Add ready repair chain eval candidate review inspection`.
- Latest BIBER ready repair-chain eval-dataset decision review artifact
  inspection commit pushed and Vast-verified:
  `05f57486 Add eval dataset decision review inspection`.
- Latest BIBER ready repair-chain eval-dataset validation artifact inspection
  commit pushed and Vast-verified:
  `572daec2 Add eval dataset validation inspection`.
- Latest BIBER ready repair-chain eval prompt inspection commit pushed and
  Vast-verified:
  `083108b Add eval prompt inspection`.
- Latest BIBER repair-chain held-out eval review artifact inspection commit
  pushed and Vast-verified:
  `647437f Add heldout eval review inspection`.
- Latest BIBER repair-chain held-out eval decision review artifact inspection
  commit pushed and Vast-verified:
  `570739f Add heldout eval decision review inspection`.
- Latest BIBER repair-chain held-out baseline candidate review artifact
  inspection commit pushed and Vast-verified:
  `57d4e4b Add heldout baseline candidate review inspection`.
- Latest BIBER repair-chain held-out baseline decision review artifact
  inspection commit pushed and Vast-verified:
  `33ed241 Add heldout baseline decision review inspection`.
- Latest BIBER repair-chain training readiness artifact inspection commit
  pushed and Vast-verified:
  `adf8b7d Add training readiness inspection`.
- Latest BIBER repair-chain training candidate review artifact inspection
  commit pushed and Vast-verified:
  `ae8c93b Add training candidate review inspection`.
- Latest BIBER repair-chain training pipeline artifact inspection commit
  pushed and Vast-verified:
  `83162d7 Add training pipeline show inspection`.
- Latest controlled BIBER repair-chain baseline-candidate evidence directory
  on Vast:
  `/workspace/outputs/biber-baseline-candidate-20260521T190501Z-94473`.
  This is baseline-ready evidence only, not a training approval. The single
  exported training-candidate row was inspected and should stay unfilled
  because it is smoke metadata, not a useful coding example.
- This handoff now makes reliable repo-context selection, safer multi-file
  editing, and structured test-failure diagnosis explicit BIBER MVP goals.
- Vast code verification is current through `d9448ec`. Full Rust/private-devnet
  verification is current through `fba4a1d`; focused BIBER API wrapper/client
  and dashboard verification is current through `4af1ee5`; consolidated BIBER
  XRIQ API smoke verification is current through `4af1ee5`; focused fixture
  verification is current through `919b348`; BIBER test-runner API verification
  is current through `d4df8c0`; BIBER workspace-edit API verification is
  current through `992890b`; BIBER GitHub branch/PR workflow verification is
  current through `179f58b`; BIBER agent-smoke verification is current through
  `51ad833`;
  BIBER agent-session API/persistence verification is current through
  `51ad833`; BIBER repo-adaptation verification is current through `2efa65b`;
  BIBER repo-context planner verification is current through `1cc790a`;
  BIBER multi-file edit planner verification is current through `70e6320`;
  BIBER test-failure diagnosis verification is current through `1fd510f`;
  BIBER frontend test-failure diagnosis verification is current through
  `bec42c8`;
  BIBER agent-session embedded test-diagnosis verification is current through
  `3069a50`; BIBER `.NET`/Java allowlisted test-command verification is
  current through `c5f7235`; BIBER repo-context stack-profile verification is
  current through `6050bd0`; BIBER hash-gated workspace edit-apply
  verification is current through `79aad96`; BIBER repo-adaptation live-eval
  wrapper verification is current through `81b9dd5`; BIBER repo-adaptation
  failure-review verification is current through `68479ad`; BIBER
  repo-adaptation candidate review verification is current through `a1b9f5a`;
  BIBER repo-adaptation candidate decision verification is current through
  `a53be7a`; BIBER repo-adaptation dataset-merge verification is current
  through `436f955`; BIBER repo-adaptation dataset-readiness verification is
  current through `299af9b`; BIBER repo-adaptation expanded/balanced prompt
  verification is current through `71e9f92`; BIBER repo-adaptation manual
  training-review gate verification is current through `3ef6834`; Vast
  training approval guard verification is current through `b0d5f49`; adapter
  promotion-review gate verification is current through `1834035`; Vast
  candidate adapter review wrapper verification is current through `426fcd3`;
  candidate adapter review newest-artifact selection verification is current
  through `4f3bb4c`; adapter promotion same-as-stable blocker verification is
  current through `25cc41e`; repo held-out promotion margin gate verification
  is current through `600bff1`; candidate-review same-as-stable fast-fail
  guard verification is current through `c38c0a7`; candidate-review
  adapter-reload verification is current through `608252b`; repo-adaptation
  anti-regression review helper verification is current through `08fdd59`;
  repo-adaptation training-outcome review helper verification is current
  through `77837d2`; profiled regression eval path verification is current
  through `426f602`; BIBER runtime-profile contract verification is current
  through `6fd6f1a`; Vast API-only restart and enhanced smoke verification is
  current through `2c40099`; BIBER agent-client runtime-profile ID verification
  is current through `66a44f6`; Vast runtime-profile enabled smoke verification
  is current through `3e1a097`; Vast stable profile-baseline script
  verification is current through `3e44edc`; BIBER agent-client MVP-loop
  runtime-profile repair carry-through verification is current through
  `abc836e`; BIBER prepared repair-attempt verification is current through
  `1a1b9aa`; BIBER repair-attempt artifact inspection verification is current
  through `593d035`; BIBER repair-edit extraction artifact inspection
  verification is current through `ebe5c25`; BIBER repair-edit plan artifact
  inspection verification is current through `e311321`; BIBER repair-edit
  apply artifact inspection verification is current through `15d1544`; BIBER
  repair-test verification artifact inspection verification is current through
  `ad901453`; BIBER verified repair review artifact inspection verification is
  current through `4c79b104`; BIBER ready repair-chain review artifact
  inspection verification is current through `02573955`; BIBER ready
  repair-chain decision review artifact inspection verification is current
  through `86e84477`; BIBER ready repair-chain eval-candidate review artifact
  inspection verification is current through `3ac6544d`; BIBER ready
  repair-chain eval-dataset decision review artifact inspection verification
  is current through `05f57486`; BIBER ready repair-chain eval-dataset
  validation artifact inspection verification is current through `572daec2`;
  BIBER ready repair-chain eval prompt inspection verification is current
  through `083108b`; BIBER repair-chain held-out eval review artifact
  inspection verification is current through `647437f`; BIBER repair-chain
  held-out eval decision review artifact inspection verification is current
  through `570739f`; BIBER repair-chain held-out baseline candidate review
  artifact inspection verification is current through `57d4e4b`; BIBER
  repair-chain held-out baseline decision review artifact inspection
  verification is current through `33ed241`; BIBER repair-chain training
  readiness artifact inspection verification is current through `adf8b7d`;
  BIBER repair-chain training candidate review artifact inspection
  verification is current through `ae8c93b`; BIBER repair-chain training
  pipeline artifact inspection verification is current through `83162d7`;
  BIBER agent-client
  create-session smoke verification is current through `6317641`; BIBER
  agent-client session-history command verification is current through
  `b8abdfb`; BIBER agent-client repo-context planning verification is current
  through `775b278`; BIBER agent-client workspace-edit command verification is
  current through `12450e2`; BIBER agent-client test/diagnosis command
  verification is current through `b0d1df6`; BIBER agent-client GitHub workflow
  command verification is current through `a3ba952`; BIBER agent-client
  MVP-loop command verification is current through `1ce9f60`; BIBER
  agent-client MVP-loop artifact verification is current through `38e3701`;
  BIBER agent-client MVP-loop artifact viewer verification is current through
  `8c077d2`; BIBER agent-client MVP-loop artifact listing verification is
  current through `841dc8f`; BIBER agent-client failed MVP-loop artifact filter
  verification is current through `be89b78`; BIBER agent-client MVP-loop
  failure-export verification is current through `ef0cd5e`; BIBER
  agent-client repair-request helper verification is current through
  `2e7a405`; BIBER agent-client local-model repair-attempt verification is
  current through `8b2d200`; BIBER agent-client repair-attempt artifact
  inspection verification is current through `593d035`; BIBER agent-client
  repair-edit extraction verification is current through `c9ec3d7`; BIBER
  agent-client repair-edit extraction artifact inspection verification is
  current through `ebe5c25`; BIBER agent-client repair-edit planning
  verification is current through `4c7aea5`; BIBER agent-client repair-edit
  plan artifact inspection verification is current through `e311321`; BIBER
  agent-client guarded repair-edit apply verification is current through
  `cfed893`; BIBER agent-client repair-edit apply artifact inspection
  verification is current through `15d1544`; BIBER agent-client repair-test
  verification artifact inspection verification is current through `ad901453`;
  BIBER agent-client repair-test verification is current through `2ae4a02`;
  BIBER verified repair review export verification is current through
  `9b22ef5`; BIBER verified repair review summary verification is current
  through `caabb32`; BIBER agent-client verified repair review artifact
  inspection verification is current through `4c79b104`; BIBER repair-chain
  summary verification is current
  through `6af885c`; BIBER repair-chain artifact listing verification is
  current through `a4799fe`; BIBER ready repair-chain review export
  verification is current through `559c30d`; BIBER ready repair-chain review
  summary verification is current through `6c90400`; BIBER agent-client ready
  repair-chain review artifact inspection verification is current through
  `02573955`; BIBER ready repair-chain decision recording verification is
  current through `dc76ae6`; BIBER ready
  repair-chain decision review verification is current through `6566caf`;
  BIBER agent-client ready repair-chain decision review artifact inspection
  verification is current through `86e84477`;
  BIBER repair-chain eval-candidate export verification is current through
  `415af7a`; BIBER repair-chain eval-candidate review verification is current
  through `4d4ddca`; BIBER agent-client ready repair-chain eval-candidate
  review artifact inspection verification is current through `3ac6544d`;
  BIBER repair-chain eval-dataset decision verification is
  current through `bb6fdc0`; BIBER repair-chain eval-dataset decision review
  verification is current through `f600ab0`; BIBER agent-client ready
  repair-chain eval-dataset decision review artifact inspection verification
  is current through `05f57486`; BIBER repair-chain eval-dataset
  export verification is current through `22566dc`; BIBER repair-chain
  eval-dataset validation verification is current through `78608bb`; BIBER
  agent-client ready repair-chain eval-dataset validation artifact inspection
  verification is current through `572daec2`; BIBER agent-client ready
  repair-chain eval prompt inspection verification is current through
  `083108b`; BIBER agent-client repair-chain held-out eval review artifact
  inspection verification is current through `647437f`; BIBER agent-client
  repair-chain held-out eval decision review artifact inspection verification
  is current through `570739f`; BIBER agent-client repair-chain held-out
  baseline candidate review artifact inspection verification is current
  through `57d4e4b`; BIBER agent-client repair-chain held-out baseline
  decision review artifact inspection verification is current through
  `33ed241`; BIBER agent-client repair-chain training readiness artifact
  inspection verification is current through `adf8b7d`; BIBER agent-client
  repair-chain training candidate review artifact inspection verification is
  current through `ae8c93b`; BIBER agent-client repair-chain training pipeline
  artifact inspection verification is current through `83162d7`; BIBER
  repair-chain held-out eval prompt export verification is current through
  `16523ac`; BIBER repair-chain held-out eval runner verification is current
  through `95051e5`; BIBER repair-chain held-out eval result review
  verification is current through `28353e8`; BIBER repair-chain held-out eval
  decision recording verification is current through `c254677`; BIBER
  repair-chain held-out eval decision review verification is current through
  `bf01ce2`; BIBER repair-chain held-out baseline candidate export
  verification is current through `e7f3fe5`; BIBER repair-chain held-out
  baseline candidate review verification is current through `c1fdba8`;
  BIBER repair-chain held-out baseline decision verification is current through
  `55713f4`; BIBER repair-chain held-out baseline decision review verification
  is current through `a045c63`; BIBER repair-chain training readiness review
  verification is current through `c356d70`; BIBER repair-chain training
  candidate export verification is current through `966ba05`; BIBER
  repair-chain training candidate review verification is current through
  `693a1ca`; BIBER repair-chain training pipeline status verification is
  current through `76c4401`; BIBER repair-chain training pipeline listing
  verification is current through `c4abe43`; Rust/XRIQ live codegen-profile
  eval verification is current through `7e7b8d`; BIBER synthetic-safe
  agent-smoke verification is current through `2afa40e`; BIBER real-repo
  repair-chain approval guard verification is current through `d9448ec`.
- Current served adapter:
  `/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z`.
- Current agent-session artifact directory:
  `/workspace/outputs/agent-sessions`.
- Current serving state:
  - vLLM pid: `104769`
  - FastAPI pid: `105366`
  - API bind: `127.0.0.1:8000`
  - vLLM bind: `127.0.0.1:8001`
  - `BIBER_RUNTIME_PROFILES_ENABLED=true`
  - Vast code/runtime verification is current through `d9448ec`. If later docs-only
    handoff commits exist, run `git pull --ff-only origin main` on Vast before
    resuming.
  - The user explicitly approved the separate Vast GPU repo-adaptation QLoRA
    training run on 2026-05-20. Serving was stopped first to free GPU memory:
    FastAPI pid `53902` and vLLM pid `5802` were stopped. The guarded command
    used `BIBER_TRAIN_APPROVED=1` and started tmux session
    `biber-repo-adapt-20260520T183028Z` with dataset
    `/workspace/data/repo_adaptation/reviewed_candidates.jsonl`, output
    adapter `/workspace/adapters/biber-dev-core-repo-adapt-20260520T183028Z`,
    log `/workspace/outputs/qlora-20260520T194109Z.log`, and run script
    `/workspace/outputs/qlora-20260520T194109Z.sh`. Training completed
    successfully in the tmux job, saved the LoRA adapter, and the tmux session
    exited. Training summary: `50` records, `7` steps, `train_loss=2.697`,
    train runtime about `32s`.
  - A first post-training candidate review run was attempted at
    `/workspace/outputs/evals/repo-adapt-candidate-20260520T194218Z/`, but it
    exposed a wrapper bug: vLLM was already running, so switching
    `BIBER_LORA_ADAPTER_DIR` did not reload the candidate adapter. Treat
    `/workspace/outputs/evals/repo-adapt-candidate-20260520T194218Z/candidate-promotion-review.json`
    as superseded/inconclusive. It must not be used for promotion decisions.
  - The `608252b` candidate-review adapter-reload fix required stopping and
    restarting services when switching between stable and candidate adapters.
    Vast verification passed `bash -n scripts/vast_review_candidate_adapter_direct.sh`,
    then reran the post-training candidate review with forced reload:
    `BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-repo-adapt-20260520T183028Z BIBER_CANDIDATE_EVAL_SESSION=repo-adapt-candidate-reloaded-20260520T195421Z bash scripts/vast_review_candidate_adapter_direct.sh`.
    The wrapper verified stable serving first, then restarted vLLM/FastAPI with
    the candidate adapter; `/v1/models` showed
    `root=/workspace/adapters/biber-dev-core-repo-adapt-20260520T183028Z` for
    the candidate eval. Artifacts are under
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/`.
    Results: stable repo held-out `128/128` responses and `77/128` expectation
    checks; candidate broad eval `18/18` responses but only `15/18`
    expectation checks; candidate Rust/XRIQ eval `7/7` responses and `7/7`
    expectation checks but only `4/7` cargo validators; candidate repo held-out
    `128/128` responses and `106/128` expectation checks. Promotion review:
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/candidate-promotion-review.json`
    with `review_status=promotion_blocked`,
    `hard_blockers=["broad_expectations_below_threshold","rust_validators_below_threshold"]`,
    `repo_baseline_improvement` passing with `delta=29`,
    `promotion_allowed=false`, `safe_to_promote=false`, and
    `serving_changed=false`. The candidate adapter is useful evidence for repo
    adaptation, but must not be promoted because it regressed broad and
    Rust/XRIQ gates.
  - After the corrected candidate review, the wrapper restored stable serving.
    `bash scripts/vast_test_direct.sh` confirmed `/health`, `/v1/runtime`,
    `/v1/models`, and chat smoke are OK. Current vLLM pid is `77494`, FastAPI
    pid is `77817`, and `/v1/models` shows served LoRA root
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `08fdd59` adds `training/repo_adaptation_regression_review.py`, which
    converts blocked candidate broad/Rust eval regressions into a
    human-review-only anti-regression queue. Vast verification passed
    `/workspace/biber-venv/bin/python -m pytest tests/test_repo_adaptation_regression_review.py tests/test_repo_adaptation_candidate_review.py -q`
    with `8 passed`. The helper was run against the corrected candidate eval
    artifacts and wrote
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/candidate-regression-review.json`
    plus
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-candidates.jsonl`.
    It found `6` regressions and `6` anti-regression candidates. Initial
    follow-up candidate review wrote
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-candidate-review.json`
    with `0/6` ready and `6` pending, so these rows are not training-ready.
    Stable service was rechecked after the review-only step with
    `bash scripts/vast_test_direct.sh`; `/v1/models` still shows the stable
    `biber-dev-core-lora-rust-xriq-400` adapter.
  - The anti-regression candidates were manually reviewed through the existing
    decision gate after explicit user approval to copy
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-decisions.json`
    to Vast. Decision application wrote
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-reviewed-candidates.jsonl`
    and
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-decisions.review.json`
    with `6/6` approved. Candidate review then wrote
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-reviewed-candidate-review.json`
    with `6/6` ready and `0` pending. These reviewed rows are ready for
    dataset validation/merge only; they are still not training approval.
  - The reviewed anti-regression rows were merged into the cumulative curated
    queue with `training/repo_adaptation_dataset_merge.py`. Merge review:
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-dataset-merge.review.json`
    with `6` added, `0` duplicates, and `56` total records in
    `/workspace/data/repo_adaptation/reviewed_candidates.jsonl`. Dataset
    readiness was rerun at
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-curated-queue-readiness.json`
    and reports `manual_training_review_required` with `56/50` ready records.
    Manual pre-training review was then written to
    `/workspace/outputs/evals/repo-adapt-candidate-reloaded-20260520T195421Z/anti-regression-manual-training-review.json`
    with `review_status=ready_for_user_training_approval`,
    `ready_for_user_training_approval=true`, `hard_blockers=[]`, categories
    `bash=5`, `markdown=8`, `python=22`, `sql=3`, `rust=8`, `json=4`, and
    `toml=6`. It still has `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`.
  - After explicit user approval, the guarded separate Vast GPU QLoRA run was
    started with `BIBER_TRAIN_APPROVED=1` from the manual training review
    artifact. Serving was stopped first to free GPU memory. Training session:
    `biber-repo-adapt-antireg-review-20260520`; dataset:
    `/workspace/data/repo_adaptation/reviewed_candidates.jsonl`; output
    adapter:
    `/workspace/adapters/biber-dev-core-repo-adapt-antireg-review-20260520`;
    log: `/workspace/outputs/qlora-20260520T220355Z.log`; run script:
    `/workspace/outputs/qlora-20260520T220355Z.sh`. Training completed
    successfully with `56` records, `7` steps, `train_loss=2.468`, and saved
    `adapter_model.safetensors`.
  - Post-training candidate review was run immediately with
    `BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-repo-adapt-antireg-review-20260520`
    and session
    `repo-adapt-antireg-candidate-20260520T2205Z`. Artifacts are under
    `/workspace/outputs/evals/repo-adapt-antireg-candidate-20260520T2205Z/`.
    Results: stable repo held-out `128/128` responses and `77/128`
    expectation checks; candidate broad eval `18/18` responses but only
    `15/18` expectation checks; candidate Rust/XRIQ eval `7/7` responses and
    `7/7` expectation checks but only `4/7` cargo validators; candidate repo
    held-out `128/128` responses and `105/128` expectation checks. Promotion
    review:
    `/workspace/outputs/evals/repo-adapt-antireg-candidate-20260520T2205Z/candidate-promotion-review.json`
    with `review_status=promotion_blocked`,
    `hard_blockers=["broad_expectations_below_threshold","rust_validators_below_threshold"]`,
    `promotion_allowed=false`, and no serving promotion. The wrapper restored
    the stable adapter afterward, and
    `bash scripts/vast_test_direct.sh` confirmed healthy serving on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400` with current vLLM
    pid `80777` and API pid `81099`.
  - `77837d2` adds `training/repo_adaptation_training_outcome_review.py`, which
    checks whether a training run actually fixed the reviewed anti-regression
    rows it was trained on. Vast verification passed
    `/workspace/biber-venv/bin/python -m pytest tests/test_repo_adaptation_training_outcome_review.py -q`
    with `3 passed`. The helper was run against the anti-regression candidate
    artifacts and wrote
    `/workspace/outputs/evals/repo-adapt-antireg-candidate-20260520T2205Z/training-outcome-review.json`.
    The review reports `review_status=training_strategy_blocked`,
    `current_failed_rows=6`, `persistent_trained_failures=6`,
    `learned_reviewed_candidate_ids=[]`, and
    `next_review_action=change_prompt_or_dataset_strategy_before_more_training`.
    The persistent IDs are `api_error_shape`,
    `api_missing_key_error_shape`, `api_rate_limit_error_shape`,
    `rust_xriq_fee_calculation`, `rust_xriq_next_height`, and
    `rust_xriq_validate_transaction`. Do not start another QLoRA run from this
    artifact pattern.
  - `e428d7b` adds optional prompt-prefix support to
    `scripts/vast_eval_lora_direct.sh` plus
    `training/api_error_response_profile.txt`, and `426f602` refines
    `training/rust_xriq_codegen_profile.txt` for the `next_height` rustfmt
    shape. Vast syntax verification passed `bash -n scripts/vast_eval_lora_direct.sh`.
    A profile experiment was run against the blocked candidate adapter
    `/workspace/adapters/biber-dev-core-repo-adapt-antireg-review-20260520`
    without promotion. Profiled broad eval artifact:
    `/workspace/outputs/evals/profiled-antireg-candidate-20260521T0300Z/candidate-profiled-broad.summary.json`
    with `18/18` expectation checks. Initial profiled Rust eval reached
    `6/7` validators; after `426f602`, rerun artifact
    `/workspace/outputs/evals/profiled-antireg-candidate-20260521T0315Z/candidate-profiled-rust-xriq.summary.json`
    reached `7/7` expectation checks and `7/7` cargo validators. The wrapper
    restored stable serving afterward, and `bash scripts/vast_test_direct.sh`
    confirmed `/workspace/adapters/biber-dev-core-lora-rust-xriq-400` is still
    served.
  - A profile-aware offline promotion review was written at
    `/workspace/outputs/evals/profiled-antireg-candidate-20260521T0315Z/profiled-candidate-promotion-review.json`
    using the profiled broad/Rust summaries and the existing candidate/stable
    repo-held-out summaries. It reports
    `review_status=ready_for_user_promotion_approval` and `hard_blockers=[]`.
    This does not promote or change serving. Treat it as eligible only if the
    API error-response profile and expanded Rust/XRIQ profile are accepted as
    part of the BIBER runtime/eval contract.
  - `cf4b621` and `6fd6f1a` codify that profile contract as an opt-in runtime
    feature in both `src/biber_api` and the live `app` server path. Requests can
    include `runtime_profile_ids` with `api-error-response` and/or
    `rust-xriq-codegen`, but the server injects them only when
    `BIBER_RUNTIME_PROFILES_ENABLED=true`. This initially shipped disabled by
    default; the current live Vast API now has it explicitly enabled after user
    approval, as recorded below.
  - `2a4b713` adds `scripts/vast_restart_api_direct.sh`, which restarts only
    FastAPI and leaves the vLLM/GPU model process running. `2c40099` extends
    `scripts/vast_test_direct.sh` to smoke-test `/v1/agent/capabilities`.
    Vast verification passed `bash -n scripts/vast_restart_api_direct.sh`,
    `bash -n scripts/vast_test_direct.sh`, focused pytest
    `tests/test_runtime_profiles.py tests/test_agent_capabilities.py tests/test_repo_context.py tests/test_openai_mentor_trigger.py -q`
    with `20 passed`, and live `bash scripts/vast_test_direct.sh`. The live
    capability smoke reported runtime profiles available, `enabled=false`, and
    the XRIQ preset requesting `["rust-xriq-codegen"]`.
  - `66a44f6` adds `--runtime-profile-id` support to
    `scripts/biber_agent_client.py` for direct `chat`, tracked
    `create-session`, and repair-attempt chat payloads. The client validates
    requested profile IDs against `/v1/agent/capabilities` before sending them,
    dedupes repeated IDs, and keeps mentor use opt-in. `docs/API_EXAMPLES.md`
    now shows direct chat and session examples with `rust-xriq-codegen`.
    `scripts/vast_biber_agent_smoke.sh` now includes runtime-profile client
    coverage for direct chat and create-session. Vast verification passed
    `/workspace/biber-venv/bin/python -m compileall scripts tests`, focused
    pytest
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `88 passed`, `bash -n scripts/vast_biber_agent_smoke.sh`, and live
    agent smoke with artifact directory
    `/workspace/outputs/biber-agent-smoke-20260521T040322Z-85400`.
  - The user explicitly approved enabling live runtime profiles on
    2026-05-21. `BIBER_RUNTIME_PROFILES_ENABLED=true` was written to the Vast
    `.env`, then only FastAPI was restarted with
    `bash scripts/vast_restart_api_direct.sh`; vLLM stayed running on pid
    `84653`, and the new FastAPI pid is `85630`. `3e1a097` adds
    `scripts/vast_runtime_profile_smoke.sh`. Vast verification passed
    `bash -n scripts/vast_runtime_profile_smoke.sh`, then live smoke with
    `BIBER_RUNTIME_PROFILE_SMOKE_CHAT_MAX_TOKENS=120` and
    `BIBER_RUNTIME_PROFILE_SMOKE_SESSION_MAX_TOKENS=60`. Smoke artifacts are in
    `/workspace/outputs/runtime-profile-smoke-20260521T043017Z-85678`; the
    capability check reported `runtime_profiles_enabled=true`, profile IDs
    `api-error-response` and `rust-xriq-codegen`, Rust direct chat content
    starting with `BIBER_RUNTIME_PROFILE_RUST_OK`, tracked session content
    starting with `BIBER_RUNTIME_PROFILE_SESSION_OK`, API error content with
    `status` and `detail`, and `mentor_used=false` for all profile smoke calls.
    No training was started and no adapter was promoted; stable serving remains
    on `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - Stable-adapter, profile-enabled baseline was run on Vast on 2026-05-21
    without extra approval because it only used the already-served stable
    adapter. Explicit approval is still required before any new training run,
    candidate adapter reload, or candidate promotion. Verification command ran
    `bash scripts/vast_status_direct.sh`, live
    `bash scripts/vast_runtime_profile_smoke.sh`, broad eval with
    `BIBER_EVAL_PROMPT_PREFIX=training/api_error_response_profile.txt` and
    `BIBER_EVAL_PROMPT_PREFIX_IDS=api_error_shape,api_missing_key_error_shape,api_rate_limit_error_shape`,
    and Rust/XRIQ eval with `BIBER_EVAL_FAIL_ON_VALIDATORS=1`. Results:
    runtime smoke passed with artifact directory
    `/workspace/outputs/runtime-profile-smoke-20260521T043719Z-85867`; broad
    API-profile eval passed `18/18` responses and `18/18` expectation checks
    with summary
    `/workspace/outputs/evals/biber-dev-core-lora-20260521T043720Z.summary.json`;
    Rust/XRIQ eval passed `7/7` responses, `7/7` expectation checks, and `7/7`
    cargo validators with summary
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260521T043745Z.summary.json`.
    Current service remains stable: vLLM pid `84653`, FastAPI pid `85630`,
    served LoRA root `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`,
    and `BIBER_RUNTIME_PROFILES_ENABLED=true`.
  - `3e44edc` adds `scripts/vast_profile_baseline_direct.sh` and documents it
    in `docs/API_EXAMPLES.md`. This wraps the stable runtime-profile smoke,
    broad API-profile eval, and Rust/XRIQ cargo-validator eval into one
    repeatable Vast command. Vast verification passed
    `bash -n scripts/vast_profile_baseline_direct.sh` and live
    `bash scripts/vast_profile_baseline_direct.sh`. Artifact directory:
    `/workspace/outputs/profile-baseline-20260521T135337Z-86922`. Combined
    summary:
    `/workspace/outputs/profile-baseline-20260521T135337Z-86922/profile-baseline.summary.json`
    with `broad_ok=true`, `broad_expectation_ok=18`,
    `rust_xriq_ok=true`, `rust_xriq_validation_ok=7`,
    `training_started=false`, `candidate_reloaded=false`, and
    `adapter_promoted=false`. Current service remains stable on vLLM pid
    `84653`, FastAPI pid `85630`, and
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `abc836e` adds profile carry-through to the stdlib BIBER MVP loop. The
    `mvp-loop` command now accepts `--runtime-profile-id`, validates requested
    profile IDs against `/v1/agent/capabilities`, records them in the saved
    loop artifact, includes them in failed-loop export records and
    `prepare-repair` artifacts, and lets `attempt-repair` inherit them unless
    the user passes replacement `--runtime-profile-id` values. `docs/API_EXAMPLES.md`
    now shows the mvp-loop profile argument and notes the inheritance behavior.
    `scripts/vast_biber_agent_smoke.sh` now verifies the saved loop artifact
    and `show-mvp-loop` report preserve `rust-xriq-codegen`. Local verification
    passed bundled-Python syntax compilation; local pytest was not available on
    this workstation. Vast verification passed
    `/workspace/biber-venv/bin/python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    focused pytest
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `90 passed`, `bash -n scripts/vast_biber_agent_smoke.sh`, and live
    `BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T140446Z-87997`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted.
  - `1a1b9aa` lets `attempt-repair` accept either the original failed
    `mvp-loop` artifact or the prepared `prepare-repair` artifact. This keeps
    the low-cost repair path cleaner: build and review the bounded repair
    request once, then send that prepared artifact to the local BIBER model.
    `docs/API_EXAMPLES.md` now shows `attempt-repair` consuming
    `/workspace/outputs/biber-mvp-loop-repair.json`, and
    `scripts/vast_biber_agent_smoke.sh` verifies this prepared-artifact path.
    Local verification passed bundled-Python syntax compilation; local pytest
    was not available on this workstation. Vast verification passed
    `/workspace/biber-venv/bin/python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    focused pytest
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `91 passed`, `bash -n scripts/vast_biber_agent_smoke.sh`, and live
    `BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T141417Z-88172`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted.
  - `3a689d8` adds offline repair-attempt artifact inspection to the stdlib
    client: `show-repair-attempt` summarizes saved `attempt-repair` JSON
    without resolving API auth, and `list-repair-attempts` scans an output
    directory for saved attempt artifacts with an optional `--ready-only`
    filter. `docs/API_EXAMPLES.md` now places both commands between
    `attempt-repair` and `extract-repair-edits`. `593d035` tightens the Vast
    smoke fixture so the synthetic failed loop preserves `rust-xriq-codegen`
    through `prepare-repair`, `attempt-repair`, `show-repair-attempt`, and
    `list-repair-attempts`. Local verification passed bundled-Python syntax
    compilation and an offline command smoke; local pytest was not available on
    this workstation, and local `bash` could not run because WSL has no
    installed distro. Vast verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    focused pytest with absolute paths and `PYTHONPATH=/workspace/biber-ai-platform`
    for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `94 passed`, `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T143304Z-88594`. The final
    Vast checkout was `593d035`. No training was started, no candidate adapter
    was reloaded, and no adapter was promoted. After the handoff-only commit
    was pushed and Vast was fast-forwarded to `b84fae7`, final status check
    showed vLLM pid `84653`, FastAPI pid `85630`, API bind
    `127.0.0.1:8000`, vLLM bind `127.0.0.1:8001`, and served LoRA root
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `ebe5c25` adds offline repair-edit extraction artifact inspection:
    `show-repair-edit-extraction` summarizes saved `extract-repair-edits`
    artifacts without resolving API auth, and `list-repair-edit-extractions`
    scans output directories with an optional `--ready-only` filter for
    `ready_for_plan_edit` artifacts. `docs/API_EXAMPLES.md` now places those
    commands between `extract-repair-edits` and `plan-repair-edits`, and
    `scripts/vast_biber_agent_smoke.sh` verifies the new no-auth inspection
    path against the live smoke artifact. Local verification passed bundled
    Python syntax compilation and an offline command smoke; local pytest was
    not available on this workstation. Vast verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `97 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T145429Z-88927`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted.
  - `e311321` adds offline repair-edit plan artifact inspection:
    `show-repair-edit-plan` summarizes saved `plan-repair-edits` artifacts
    without resolving API auth, and `list-repair-edit-plans` scans output
    directories with an optional `--planned-only` filter. `docs/API_EXAMPLES.md`
    now places those commands between `plan-repair-edits` and
    `apply-repair-edits`, and `scripts/vast_biber_agent_smoke.sh` verifies the
    no-auth plan inspection path against the live smoke artifact before any
    approved apply. Local verification passed bundled Python syntax
    compilation and an offline command smoke; local pytest was not available on
    this workstation. Vast verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `100 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T150349Z-89219`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted.
  - `15d1544` adds offline repair-edit apply artifact inspection:
    `show-repair-edit-apply` summarizes saved `apply-repair-edits` artifacts
    without resolving API auth, and `list-repair-edit-applies` scans output
    directories with an optional `--applied-only` filter. `docs/API_EXAMPLES.md`
    now places those commands between `apply-repair-edits` and
    `verify-repair-edits`, and `scripts/vast_biber_agent_smoke.sh` verifies the
    no-auth apply inspection path against the live smoke artifact before test
    verification. Local verification passed bundled Python syntax compilation
    and an offline command smoke; local pytest was not available on this
    workstation. Vast verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `103 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T151723Z-89516`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted.
  - `ad901453` adds offline repair-test verification artifact inspection:
    `show-repair-test-verification` summarizes saved `verify-repair-edits`
    artifacts without resolving API auth, and
    `list-repair-test-verifications` scans output directories with an optional
    `--passed-only` filter. `docs/API_EXAMPLES.md` now places those commands
    between `verify-repair-edits` and `export-verified-repair`, and
    `scripts/vast_biber_agent_smoke.sh` verifies the no-auth verification
    inspection path against the live smoke artifact before review export. Local
    verification passed `git diff --check`, bundled Python syntax compilation,
    and an offline command smoke; local pytest was not available on this
    workstation. Vast was fast-forwarded to `ad901453`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `106 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T153607Z-89865`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `4c79b104` adds offline verified repair review artifact inspection:
    `show-verified-repair-review` summarizes saved `review-verified-repairs`
    JSON artifacts without resolving API auth, and
    `list-verified-repair-reviews` scans output directories with an optional
    `--ready-only` filter. `docs/API_EXAMPLES.md` now places those commands
    after `review-verified-repairs`, and `scripts/vast_biber_agent_smoke.sh`
    verifies the no-auth review-summary inspection path before the repair-chain
    summary. Local verification passed `git diff --check`, bundled Python
    syntax compilation, and an offline command smoke; local pytest was not
    available on this workstation. Vast was fast-forwarded to `4c79b104`;
    verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `109 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T154545Z-90163`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `02573955` adds offline ready repair-chain review artifact inspection:
    `show-ready-repair-chain-review` summarizes saved
    `review-ready-repair-chains` JSON artifacts without resolving API auth, and
    `list-ready-repair-chain-reviews` scans output directories with an optional
    `--ready-only` filter. `docs/API_EXAMPLES.md` now includes the
    repair-chain review/export commands after verified-repair review, and
    `scripts/vast_biber_agent_smoke.sh` verifies the no-auth ready
    repair-chain review inspection path before manual decision recording. Local
    verification passed `git diff --check`, bundled Python syntax compilation,
    and an offline command smoke; local pytest was not available on this
    workstation. Vast was fast-forwarded to `02573955`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `112 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T155234Z-90463`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `86e84477` adds offline ready repair-chain decision review artifact
    inspection: `show-ready-repair-chain-decision-review` summarizes saved
    `review-ready-repair-chain-decisions` JSON artifacts without resolving API
    auth, and `list-ready-repair-chain-decision-reviews` scans output
    directories with an optional `--decision defer|reject|approve_for_eval`
    filter. `docs/API_EXAMPLES.md` now includes the decision recording/review
    commands after ready repair-chain review, and
    `scripts/vast_biber_agent_smoke.sh` verifies the no-auth decision-review
    inspection path before eval-candidate export. Local verification passed
    `git diff --check`, bundled Python syntax compilation, and an offline
    command smoke; local pytest was not available on this workstation. Vast was
    fast-forwarded to `86e84477`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `115 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T161615Z-90765`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `3ac6544d` adds offline ready repair-chain eval-candidate review artifact
    inspection: `show-ready-repair-chain-eval-candidate-review` summarizes
    saved `review-ready-repair-chain-eval-candidates` JSON artifacts without
    resolving API auth, and `list-ready-repair-chain-eval-candidate-reviews`
    scans output directories with an optional `--ready-only` filter. The
    command preserves the training guards:
    `eval_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, `github_save_ready=false`, and
    `approved_for_training=false`. `docs/API_EXAMPLES.md` now includes the
    eval-candidate export/review/show/list sequence, and
    `scripts/vast_biber_agent_smoke.sh` verifies the no-auth eval-candidate
    review inspection path before dataset-review decision recording. Local
    verification passed `git diff --check`, bundled Python syntax compilation,
    and an offline command smoke; local pytest was not available on this
    workstation. Vast was fast-forwarded to `3ac6544d`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `118 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T162408Z-91083`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `05f57486` adds offline ready repair-chain eval-dataset decision review
    artifact inspection:
    `show-ready-repair-chain-eval-dataset-decision-review` summarizes saved
    `review-ready-repair-chain-eval-dataset-decisions` JSON artifacts without
    resolving API auth, and
    `list-ready-repair-chain-eval-dataset-decision-reviews` scans output
    directories with optional `--decision defer|reject|approve_for_eval_dataset`
    and `--ready-only` filters. The command preserves the training guards:
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`.
    `docs/API_EXAMPLES.md` now includes the dataset-review
    record/review/show/list sequence, and `scripts/vast_biber_agent_smoke.sh`
    verifies the no-auth eval-dataset decision review inspection path before
    final eval-dataset export. Local verification passed `git diff --check`,
    bundled Python syntax compilation, and an offline command smoke; local
    pytest was not available on this workstation. Vast was fast-forwarded to
    `05f57486`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `121 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T163400Z-91400`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `572daec2` adds offline ready repair-chain eval-dataset validation
    artifact inspection:
    `show-ready-repair-chain-eval-dataset-validation` summarizes saved
    `validate-ready-repair-chain-eval-dataset` JSON artifacts without resolving
    API auth, and `list-ready-repair-chain-eval-dataset-validations` scans
    output directories with an optional `--ok-only` filter. The command
    preserves the training guards: `training_allowed=false`,
    `safe_to_train=false`, `github_save_ready=false`, and
    `approved_for_training=false`. `docs/API_EXAMPLES.md` now includes the
    eval-dataset export/validate/show/list/prompt-export sequence, and
    `scripts/vast_biber_agent_smoke.sh` verifies the no-auth validation
    inspection path before held-out eval prompt export. Local verification
    passed `git diff --check`, bundled Python syntax compilation, and an
    offline command smoke; local pytest was not available on this workstation.
    Vast was fast-forwarded to `572daec2`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `124 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T164203Z-91719`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `083108b` adds offline ready repair-chain held-out eval prompt inspection:
    `show-ready-repair-chain-eval-prompts` validates one or more exported
    prompt JSONL queues without resolving API auth, and
    `list-ready-repair-chain-eval-prompts` scans output directories with
    `--ready-only` and `--limit` support. The commands preserve the safety
    guards: `eval_only=true`, `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`.
    `docs/API_EXAMPLES.md` now includes the prompt show/list sequence, and
    `scripts/vast_biber_agent_smoke.sh` verifies prompt inspection before the
    synthetic held-out eval review flow. Local verification passed
    `git diff --check`, bundled Python syntax compilation, and an offline
    command smoke; local pytest was not available on this workstation. Vast was
    fast-forwarded to `083108b`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `127 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T165217Z-92040`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `647437f` adds offline repair-chain held-out eval review artifact
    inspection:
    `show-repair-chain-heldout-eval-review` summarizes saved
    `review-repair-chain-heldout-eval-results` JSON artifacts without
    resolving API auth, and `list-repair-chain-heldout-eval-reviews` scans
    output directories with `--ok-only` and `--limit` support. The commands
    preserve the safety guards: `eval_only=true`, `training_allowed=false`,
    `safe_to_train=false`, `github_save_ready=false`, and
    `approved_for_training=false`. `docs/API_EXAMPLES.md` now includes the
    held-out review/show/list sequence, and
    `scripts/vast_biber_agent_smoke.sh` verifies held-out review inspection
    before recording a synthetic held-out eval decision. Local verification
    passed `git diff --check`, bundled Python syntax compilation, and an
    offline command smoke; local pytest was not available on this workstation.
    Vast was fast-forwarded to `647437f`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `129 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T165957Z-92343`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `570739f` adds offline repair-chain held-out eval decision review artifact
    inspection:
    `show-repair-chain-heldout-eval-decision-review` summarizes saved
    `review-repair-chain-heldout-eval-decisions` JSON artifacts without
    resolving API auth, and
    `list-repair-chain-heldout-eval-decision-reviews` scans output directories
    with optional `--decision defer|reject|accept_for_baseline`,
    `--baseline-ready-only`, and `--limit` support. The commands preserve the
    safety guards: `eval_only=true`, `training_allowed=false`,
    `safe_to_train=false`, `github_save_ready=false`, and
    `approved_for_training=false`. `docs/API_EXAMPLES.md` now includes the
    held-out decision review/show/list sequence, and
    `scripts/vast_biber_agent_smoke.sh` verifies held-out decision review
    inspection before any baseline-candidate export. Local verification passed
    `git diff --check`, bundled Python syntax compilation, and an offline
    command smoke; local pytest was not available on this workstation. Vast was
    fast-forwarded to `570739f`; verification passed
    `/workspace/biber-venv/bin/python -m py_compile /workspace/biber-ai-platform/scripts/biber_agent_client.py /workspace/biber-ai-platform/tests/test_biber_agent_client.py`,
    `bash -n /workspace/biber-ai-platform/scripts/vast_biber_agent_smoke.sh`,
    focused pytest with `PYTHONPATH=/workspace/biber-ai-platform` for
    `tests/test_biber_agent_client.py tests/test_runtime_profiles.py tests/test_agent_capabilities.py -q`
    with `131 passed`, and live
    `cd /workspace/biber-ai-platform; BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=64 bash scripts/vast_biber_agent_smoke.sh`.
    Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T170909Z-92648`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `57d4e4b` adds offline repair-chain held-out baseline candidate review
    artifact inspection:
    `show-repair-chain-heldout-baseline-candidate-review` summarizes saved
    `review-repair-chain-heldout-baseline-candidates` JSON artifacts without
    resolving API auth, and
    `list-repair-chain-heldout-baseline-candidate-reviews` scans output
    directories with optional `--candidate-ready-only` and `--limit` support.
    The commands preserve the safety guards: `eval_only=true`,
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`.
    `docs/API_EXAMPLES.md` now includes the held-out baseline-candidate
    export/review/show/list sequence, and
    `scripts/vast_biber_agent_smoke.sh` verifies baseline-candidate review
    inspection before any manual baseline-candidate decision. Local
    verification passed `git diff --check`, bundled Python syntax compilation,
    and an offline command smoke; local pytest was not available on this
    workstation, and local `bash -n` was blocked because WSL has no installed
    distro. Vast was fast-forwarded to `57d4e4b`; verification passed
    `. /venv/main/bin/activate`, `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `128 passed`, and live
    `bash scripts/vast_biber_agent_smoke.sh`. Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T171749Z-92929`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `33ed241` adds offline repair-chain held-out baseline decision review
    artifact inspection:
    `show-repair-chain-heldout-baseline-decision-review` summarizes saved
    `review-repair-chain-heldout-baseline-decisions` JSON artifacts without
    resolving API auth, and
    `list-repair-chain-heldout-baseline-decision-reviews` scans output
    directories with optional `--decision defer|reject|approve_as_baseline`,
    `--baseline-ready-only`, and `--limit` support. The commands preserve the
    safety guards: `eval_only=true`, `training_allowed=false`,
    `safe_to_train=false`, `github_save_ready=false`, and
    `approved_for_training=false`. `docs/API_EXAMPLES.md` now includes the
    held-out baseline-decision record/review/show/list sequence, and
    `scripts/vast_biber_agent_smoke.sh` verifies baseline-decision review
    inspection before any training-readiness review. Local verification passed
    `git diff --check`, bundled Python syntax compilation, and an offline
    command smoke; local pytest was not available on this workstation, and
    local `bash -n` remains blocked because WSL has no installed distro. Vast
    was fast-forwarded to `33ed241`; verification passed
    `. /venv/main/bin/activate`, `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `130 passed`, and live
    `bash scripts/vast_biber_agent_smoke.sh`. Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T175022Z-93260`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `adf8b7d` adds offline repair-chain training readiness artifact
    inspection:
    `show-repair-chain-training-readiness` summarizes saved
    `review-repair-chain-training-readiness` JSON artifacts without resolving
    API auth, and `list-repair-chain-training-readiness` scans output
    directories with optional `--ready-only` and `--limit` support. The
    commands preserve the safety guards: `eval_only=true`,
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`.
    `docs/API_EXAMPLES.md` now includes the training-readiness review/show/list
    sequence, and `scripts/vast_biber_agent_smoke.sh` verifies the readiness
    inspection path before any training-candidate export. Local verification
    passed `git diff --check`, bundled Python syntax compilation, and an
    offline command smoke; local pytest was not available on this workstation,
    and local `bash -n` remains blocked because WSL has no installed distro.
    Vast was fast-forwarded to `adf8b7d`; verification passed
    `. /venv/main/bin/activate`, `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `132 passed`, and live
    `bash scripts/vast_biber_agent_smoke.sh`. Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T180528Z-93594`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `ae8c93b` adds offline repair-chain training candidate review artifact
    inspection:
    `show-repair-chain-training-candidate-review` summarizes saved
    `review-repair-chain-training-candidates` JSON artifacts without resolving
    API auth, and `list-repair-chain-training-candidate-reviews` scans output
    directories with optional `--ready-only` and `--limit` support. The
    commands preserve the safety guards: `training_dataset_ready=false`,
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`.
    `docs/API_EXAMPLES.md` now includes the training-candidate export/review,
    candidate-review show/list, and training-pipeline review/list sequence.
    `scripts/vast_biber_agent_smoke.sh` verifies candidate-review inspection
    before training-pipeline status. Local verification passed
    `git diff --check`, bundled Python syntax compilation, and an offline
    command smoke; local pytest was not available on this workstation, and
    local `bash -n` remains blocked because WSL has no installed distro. Vast
    was fast-forwarded to `ae8c93b`; verification passed
    `. /venv/main/bin/activate`, `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `134 passed`, and live
    `bash scripts/vast_biber_agent_smoke.sh`. Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T181452Z-93895`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - `83162d7` adds offline repair-chain training pipeline status artifact
    inspection:
    `show-repair-chain-training-pipeline` summarizes saved
    `review-repair-chain-training-pipeline` JSON artifacts without resolving
    API auth or recomputing the pipeline status. The existing
    `list-repair-chain-training-pipelines` command continues to scan output
    directories with optional `--ready-only` and `--limit` support. The show
    command preserves the safety guards: `eval_only=true`,
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`.
    `docs/API_EXAMPLES.md` now includes the training-pipeline review/show/list
    sequence, and `scripts/vast_biber_agent_smoke.sh` verifies pipeline show
    inspection before directory listing. Local verification passed
    `git diff --check`, bundled Python syntax compilation, CLI help, and an
    offline command smoke; local pytest was not available on this workstation,
    and local `bash -n` remains blocked because WSL has no installed distro.
    Vast was fast-forwarded to `83162d7`; verification passed
    `. /venv/main/bin/activate`, `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `135 passed`, and live
    `bash scripts/vast_biber_agent_smoke.sh`. Smoke artifact directory:
    `/workspace/outputs/biber-agent-smoke-20260521T185344Z-94191`. No training
    was started, no candidate adapter was reloaded, and no adapter was
    promoted; stable serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - The `c38c0a7` candidate-review same-as-stable fast-fail guard checkpoint
    required no service restart because it changed only
    `scripts/vast_review_candidate_adapter_direct.sh` and docs. Vast
    verification passed `bash -n scripts/vast_review_candidate_adapter_direct.sh`.
    A default same-as-stable dry-run command now exits before any eval plan:
    `BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-lora-rust-xriq-400 BIBER_CANDIDATE_EVAL_DRY_RUN=1 BIBER_CANDIDATE_EVAL_SESSION=should-fail-same-candidate bash scripts/vast_review_candidate_adapter_direct.sh`
    and prints `Candidate adapter matches the stable adapter`. The explicit
    smoke-test override still works:
    `BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-lora-rust-xriq-400 BIBER_ALLOW_STABLE_AS_CANDIDATE=1 BIBER_CANDIDATE_EVAL_DRY_RUN=1 BIBER_CANDIDATE_EVAL_SESSION=allow-same-candidate-smoke bash scripts/vast_review_candidate_adapter_direct.sh`
    prints `Allow same path: 1` and only emits the planned commands because
    dry-run is enabled. No training was started, no evals ran, no adapter was
    promoted, and serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - The `600bff1` repo held-out promotion margin gate checkpoint required no
    service restart because it changed only the offline adapter promotion
    review helper, focused tests, and docs. Vast verification passed pytest
    `tests/test_adapter_promotion_review.py tests/test_repo_adaptation_training_review.py tests/test_training_dataset.py -q`
    reporting `12 passed`. It then reran only the promotion-review command
    against the existing stable-as-candidate eval summaries with a different
    placeholder candidate path and `--skip-adapter-exists-check`, writing
    `/workspace/outputs/evals/stable-as-candidate-20260520T185016Z/candidate-promotion-review.margin-blocked.json`.
    Result: `review_status=promotion_blocked`,
    `hard_blockers=["repo_eval_improvement_below_margin"]`,
    `candidate_expectation_ok=76`, `baseline_expectation_ok=73`, `delta=3`,
    `min_repo_improvement_delta=5`, `required_candidate_expectation_ok=78`,
    `promotion_allowed=false`, `safe_to_promote=false`, and
    `serving_changed=false`. This is now the default guard against accepting
    small repo held-out score drift as a real adapter improvement.
  - The `25cc41e` adapter promotion same-as-stable blocker checkpoint required
    no service restart for the code change. A real Vast wrapper validation was
    run first with the current stable adapter as both stable and candidate:
    `BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-lora-rust-xriq-400 BIBER_CANDIDATE_EVAL_SESSION=stable-as-candidate-20260520T185016Z bash scripts/vast_review_candidate_adapter_direct.sh`.
    The wrapper used the newest repo prompts
    `/workspace/outputs/repo-adapt-balanced-xwide-20260520T165801Z.prompts.jsonl`,
    training review
    `/workspace/outputs/evals/repo-adapt-training-review-20260520T183028Z.json`,
    and wrote artifacts under
    `/workspace/outputs/evals/stable-as-candidate-20260520T185016Z/`. Results:
    stable repo held-out `128/128` responses and `73/128` expectation checks;
    candidate broad eval `18/18` responses and `18/18` expectation checks;
    candidate Rust/XRIQ eval `7/7` responses, `7/7` expectation checks, and
    `7/7` cargo validators; candidate repo held-out `128/128` responses and
    `76/128` expectation checks. This exposed nondeterministic repo-score drift:
    the pre-fix artifact
    `/workspace/outputs/evals/stable-as-candidate-20260520T185016Z/candidate-promotion-review.json`
    is superseded and must not be used for promotion decisions.
  - `25cc41e` adds an explicit `candidate_adapter_matches_stable` blocker.
    Vast verification after fast-forward passed pytest
    `tests/test_adapter_promotion_review.py tests/test_repo_adaptation_training_review.py tests/test_training_dataset.py -q`
    reporting `11 passed`, then reran only the promotion-review command against
    the existing stable-as-candidate eval summaries. The corrected artifact is
    `/workspace/outputs/evals/stable-as-candidate-20260520T185016Z/candidate-promotion-review.same-adapter-blocked.json`
    with `review_status=promotion_blocked`, `hard_blockers=["candidate_adapter_matches_stable"]`,
    `promotion_allowed=false`, `safe_to_promote=false`, and
    `serving_changed=false`. No training was started, no adapter was promoted,
    and serving remains on
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400` with vLLM pid
    `5802` and FastAPI pid `53902`.
  - The `4f3bb4c` candidate adapter review newest-artifact selection fix
    required no service restart because it changed only
    `scripts/vast_review_candidate_adapter_direct.sh`. vLLM stayed on pid
    `5802`; FastAPI stayed on pid `53902`. Vast verification passed `bash -n
    scripts/vast_review_candidate_adapter_direct.sh` plus dry-run wrapper
    execution:
    `BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-lora-rust-xriq-400 BIBER_CANDIDATE_EVAL_DRY_RUN=1 BIBER_CANDIDATE_EVAL_SESSION=dry-run-candidate-review-mtime bash scripts/vast_review_candidate_adapter_direct.sh`.
    The dry-run selected the newest repo prompt artifact by modification time:
    `/workspace/outputs/repo-adapt-balanced-xwide-20260520T165801Z.prompts.jsonl`.
    It still selected training review
    `/workspace/outputs/evals/repo-adapt-training-review-20260520T183028Z.json`,
    printed the planned stable/candidate eval and promotion-review commands,
    and did not train, serve, promote, run evals, or restart anything.
  - The `426fcd3` Vast candidate adapter review wrapper checkpoint required no
    service restart because it added only `scripts/vast_review_candidate_adapter_direct.sh`
    and docs. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`. Vast
    verification passed `bash -n scripts/vast_review_candidate_adapter_direct.sh`
    plus a dry-run wrapper execution:
    `BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-lora-rust-xriq-400 BIBER_CANDIDATE_EVAL_DRY_RUN=1 BIBER_CANDIDATE_EVAL_SESSION=dry-run-candidate-review bash scripts/vast_review_candidate_adapter_direct.sh`.
    The dry-run selected training review
    `/workspace/outputs/evals/repo-adapt-training-review-20260520T183028Z.json`
    and repo prompts
    `/workspace/outputs/repo-adapt-expanded-20260520T155919Z.prompts.jsonl`,
    printed the stable baseline repo eval, candidate broad eval, candidate
    Rust/XRIQ eval, candidate repo eval, and adapter promotion-review commands,
    and did not train, serve, promote, or restart anything. After a future
    candidate adapter exists, this wrapper is the default post-training
    evaluation path before any explicit promotion approval.
  - The `1834035` adapter promotion-review gate checkpoint required no service
    restart because it added only an offline promotion-review helper, focused
    tests, and docs. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
    Focused Vast verification passed pytest
    `tests/test_adapter_promotion_review.py tests/test_repo_adaptation_training_review.py tests/test_repo_adaptation_dataset_readiness.py tests/test_training_dataset.py -q`
    reporting `14 passed`. No adapter was trained, served, or promoted. The new
    helper is `training/adapter_promotion_review.py`; after a future candidate
    adapter is trained and evaluated, use it to require broad eval, Rust/XRIQ
    validator eval, repo held-out improvement over baseline, and training
    provenance before asking for explicit user promotion approval.
  - The `b0d5f49` Vast training approval guard checkpoint required no service
    restart because it changed only the training launcher, repo-adaptation
    review helper/test, and docs. vLLM stayed on pid `5802`; FastAPI stayed on
    pid `53902`. Focused Vast verification passed `bash -n
    scripts/vast_train_qlora_tmux.sh` plus pytest
    `tests/test_repo_adaptation_training_review.py tests/test_repo_adaptation_dataset_readiness.py tests/test_repo_adaptation_dataset_merge.py tests/test_training_dataset.py -q`
    reporting `15 passed`. A negative Vast guard check without
    `BIBER_TRAIN_APPROVED=1` exited before starting tmux and printed the
    explicit approval requirement. Training was not started.
  - The `3ef6834` repo-adaptation manual training-review gate checkpoint
    required no service restart because it changed only Python helper/test/doc
    files. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`. Focused
    Vast verification passed with pytest
    `tests/test_repo_adaptation_training_review.py tests/test_repo_adaptation_dataset_readiness.py tests/test_repo_adaptation_dataset_merge.py tests/test_repo_adaptation_candidate_review.py tests/test_training_dataset.py -q`
    reporting `19 passed`.
  - Latest manual pre-training review for the cumulative repo-adaptation queue
    has been regenerated on Vast after the approval-guard change at
    `/workspace/outputs/evals/repo-adapt-training-review-20260520T183028Z.json`.
    Result: `review_status=ready_for_user_training_approval`,
    `ready_records=50`, `records=50`, `record_gap=0`, categories `bash=5`,
    `json=4`, `markdown=8`, `python=19`, `rust=5`, `sql=3`, `toml=6`,
    qualities `reviewed=50`, and `hard_blockers=[]`.
    `ready_for_user_training_approval=true`, but
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. Training was not
    started. The recommended command captured in the artifact is:
    `BIBER_TRAIN_APPROVED=1 BIBER_TRAIN_DATASET=/workspace/data/repo_adaptation/reviewed_candidates.jsonl BIBER_TRAIN_OUTPUT_DIR=/workspace/adapters/biber-dev-core-repo-adapt-20260520T183028Z BIBER_TRAIN_SESSION=biber-repo-adapt-20260520T183028Z BIBER_TRAIN_MIN_RECORDS=50 bash scripts/vast_train_qlora_tmux.sh /workspace/data/repo_adaptation/reviewed_candidates.jsonl`.
    Do not run it until the user explicitly approves a separate Vast GPU
    training run. The training launcher requires `BIBER_TRAIN_APPROVED=1` in
    the same command after explicit approval.
  - The `71e9f92` repo-adaptation balanced expanded-prompt checkpoint required
    no service restart because it changed only Python helper/test/doc files.
    vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`. Focused Vast
    verification passed with pytest
    `tests/test_repo_adaptation_plan.py tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_failure_review.py tests/test_repo_adaptation_dataset_readiness.py tests/test_training_dataset.py -q`
    reporting `21 passed`.
  - Balanced repo-adaptation local-model eval artifacts now exist on the Vast
    volume. Plan:
    `/workspace/outputs/repo-adapt-balanced-20260520T162646Z.plan.json`.
    Prompts:
    `/workspace/outputs/repo-adapt-balanced-20260520T162646Z.prompts.jsonl`.
    The 32-prompt batch covered Python `6`, SQL `2`, Markdown `6`, Bash `2`,
    TOML `7`, JSON `3`, and Rust `6` prompts. First eval summary:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.summary.json`
    with `32/32` responses, `0` runtime/API failures, and `18/32`
    expectation checks passed. Repeat eval summary:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.repeat.summary.json`
    with `32/32` responses, `0` runtime/API failures, and `18/32`
    expectation checks passed. Repeat failure review:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.repeat-review.json`
    with `failures_seen=28`, `groups=14`, and `training_candidates=14`.
    Candidate queue:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.repeat-training-candidates.jsonl`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.repeat-candidate-review.json`
    with `records=14`, `ready_records=0`, `pending_review_records=14`, and
    `hard_blockers=["candidate_outputs_missing","candidate_quality_not_reviewed","candidate_validation_errors","below_min_ready_records"]`.
    Training was not started; the next repo-adaptation step is to review these
    14 candidates in small batches and merge only verified rows into
    `/workspace/data/repo_adaptation/reviewed_candidates.jsonl`.
  - Batch 1 of the balanced repo-adaptation candidates has been manually
    reviewed and merged. Selected candidates:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-selected-candidates.jsonl`.
    Decisions:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-candidate-decisions.json`.
    Reviewed rows:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-reviewed-candidates.jsonl`.
    Decision review:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-candidate-decisions.review.json`
    with `approved_records=6`, `records=6`, and `hard_blockers=[]`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-reviewed-candidate-review.json`
    with `ready_records=6`, `records=6`, and `hard_blockers=[]`.
    Reviewed-dataset validation:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-reviewed-dataset-validation.json`
    with `ok=true`, `records=6`, categories `bash=1`, `json=1`,
    `markdown=1`, `rust=1`, `sql=1`, `toml=1`, and `errors=[]`.
    Merge review:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-dataset-merge.review.json`
    with `added_records=6`, `duplicate_records=0`, `total_records=23`,
    and `hard_blockers=[]`. Queue validation:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-curated-queue-validation.json`
    with `ok=true`, `records=23`, `errors=[]`, categories `bash=2`,
    `json=1`, `markdown=2`, `python=14`, `rust=1`, `sql=2`, `toml=1`,
    and qualities `reviewed=23`. Readiness:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch1-curated-queue-readiness.json`
    with `review_status=training_blocked`, `ready_records=23`,
    `min_records=50`, `record_gap=27`, `category_count=7`,
    `hard_blockers=["below_min_ready_records"]`,
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. Training was not
    started.
  - Batch 2, the remaining balanced repo-adaptation candidates, has also been
    manually reviewed and merged. Selected candidates:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-selected-candidates.jsonl`.
    Decisions:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-candidate-decisions.json`.
    Reviewed rows:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-reviewed-candidates.jsonl`.
    Decision review:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-candidate-decisions.review.json`
    with `approved_records=8`, `records=8`, and `hard_blockers=[]`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-reviewed-candidate-review.json`
    with `ready_records=8`, `records=8`, and `hard_blockers=[]`.
    Reviewed-dataset validation:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-reviewed-dataset-validation.json`
    with `ok=true`, `records=8`, categories `bash=1`, `markdown=3`,
    `python=2`, `rust=1`, `toml=1`, and `errors=[]`. Merge review:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-dataset-merge.review.json`
    with `added_records=7`, `duplicate_records=1`, `total_records=30`,
    and `hard_blockers=[]`. Queue validation:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-curated-queue-validation.json`
    with `ok=true`, `records=30`, `errors=[]`, categories `bash=3`,
    `json=1`, `markdown=5`, `python=15`, `rust=2`, `sql=2`, `toml=2`,
    and qualities `reviewed=30`. Readiness:
    `/workspace/outputs/evals/repo-adapt-balanced-20260520T162646Z.batch2-curated-queue-readiness.json`
    with `review_status=training_blocked`, `ready_records=30`,
    `min_records=50`, `record_gap=20`, `category_count=7`,
    `hard_blockers=["below_min_ready_records"]`,
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. Training was not
    started. The balanced 14-candidate queue is now fully reviewed; next,
    collect at least 20 more reviewed examples before requesting any Vast
    training run.
  - A wider balanced repo-adaptation local-model eval was run on Vast to gather
    additional regression-test signal without OpenAI mentor calls or training.
    Plan:
    `/workspace/outputs/repo-adapt-balanced-wide-20260520T164735Z.plan.json`.
    Prompts:
    `/workspace/outputs/repo-adapt-balanced-wide-20260520T164735Z.prompts.jsonl`.
    The 64-prompt batch covered Python `9`, SQL `3`, Markdown `9`, Bash `3`,
    TOML `17`, JSON `7`, and Rust `16` prompts, with variants
    `implementation_step=23`, `context_selection=23`, and
    `regression_test=18`. First eval summary:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.summary.json`
    with `64/64` responses, `0` runtime/API failures, and `42/64`
    expectation checks passed. Repeat eval summary:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.repeat.summary.json`
    with `64/64` responses, `0` runtime/API failures, and `40/64`
    expectation checks passed. Repeat failure review:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.repeat-review.json`
    with `failures_seen=46`, `groups=26`, and `training_candidates=20`.
    Candidate queue:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.repeat-training-candidates.jsonl`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.repeat-candidate-review.json`
    with `records=20`, `ready_records=0`, and
    `hard_blockers=["candidate_outputs_missing","candidate_quality_not_reviewed","candidate_validation_errors","below_min_ready_records"]`.
    Training was not started.
  - Batch 1 of the wide balanced repo-adaptation candidates has been manually
    reviewed and merged. This batch selected the seven new regression-test
    candidates from the 20-candidate queue; the remaining wide candidates are
    repeat duplicates of earlier reviewed failure keys. Selected candidates:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-selected-candidates.jsonl`.
    Decisions:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-candidate-decisions.json`.
    Reviewed rows:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-reviewed-candidates.jsonl`.
    Decision review:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-candidate-decisions.review.json`
    with `approved_records=7`, `records=7`, and `hard_blockers=[]`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-reviewed-candidate-review.json`
    with `ready_records=7`, `records=7`, and `hard_blockers=[]`.
    Reviewed-dataset validation:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-reviewed-dataset-validation.json`
    with `ok=true`, `records=7`, categories `python=2`, `sql=1`,
    `toml=4`, and `errors=[]`. Merge review:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-dataset-merge.review.json`
    with `added_records=7`, `duplicate_records=0`, `total_records=37`,
    and `hard_blockers=[]`. Queue validation:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-curated-queue-validation.json`
    with `ok=true`, `records=37`, `errors=[]`, categories `bash=3`,
    `json=1`, `markdown=5`, `python=17`, `rust=2`, `sql=3`, `toml=6`,
    and qualities `reviewed=37`. Readiness:
    `/workspace/outputs/evals/repo-adapt-balanced-wide-20260520T164735Z.batch1-curated-queue-readiness.json`
    with `review_status=training_blocked`, `ready_records=37`,
    `min_records=50`, `record_gap=13`, `category_count=7`,
    `hard_blockers=["below_min_ready_records"]`,
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. Training was not
    started. The next narrow step is to collect at least 13 more non-duplicate
    reviewed repo-adaptation examples before requesting any Vast training run.
  - A larger balanced repo-adaptation local-model eval was then run on Vast to
    close the reviewed-example gap without OpenAI mentor calls or training.
    Plan:
    `/workspace/outputs/repo-adapt-balanced-xwide-20260520T165801Z.plan.json`.
    Prompts:
    `/workspace/outputs/repo-adapt-balanced-xwide-20260520T165801Z.prompts.jsonl`.
    The 128-prompt batch covered Python `20`, SQL `8`, Markdown `20`,
    Bash `8`, TOML `27`, JSON `15`, and Rust `30` prompts, with variants
    `implementation_step=33`, `context_selection=33`, `regression_test=33`,
    and `risk_and_verification=29`. First eval summary:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.summary.json`
    with `128/128` responses, `0` runtime/API failures, and `75/128`
    expectation checks passed. Repeat eval summary:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.repeat.summary.json`
    with `128/128` responses, `0` runtime/API failures, and `77/128`
    expectation checks passed. Repeat failure review:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.repeat-review.json`
    with `failures_seen=104`, `groups=55`, and `training_candidates=49`.
    Candidate queue:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.repeat-training-candidates.jsonl`.
    Non-duplicate candidate queue:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.repeat-training-candidates.nonduplicate.jsonl`
    with `27` rows across `bash=2`, `json=3`, `markdown=5`,
    `python=2`, `rust=6`, `sql=2`, and `toml=7`. Candidate review:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.repeat-candidate-review.json`
    with `records=49`, `ready_records=0`, and
    `hard_blockers=["candidate_outputs_missing","candidate_quality_not_reviewed","candidate_validation_errors","below_min_ready_records"]`.
    Training was not started.
  - Batch 1 of the xwide balanced repo-adaptation candidates has been manually
    reviewed and merged. This batch intentionally selected `13` verified
    non-duplicate rows, just enough to reach the `50` reviewed-record readiness
    threshold. Selected candidates:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-selected-candidates.jsonl`.
    Decisions:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-candidate-decisions.json`.
    Reviewed rows:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-reviewed-candidates.jsonl`.
    Decision review:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-candidate-decisions.review.json`
    with `approved_records=13`, `records=13`, and `hard_blockers=[]`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-reviewed-candidate-review.json`
    with `ready_records=13`, `records=13`, and `hard_blockers=[]`.
    Reviewed-dataset validation:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-reviewed-dataset-validation.json`
    with `ok=true`, `records=13`, categories `bash=2`, `json=3`,
    `markdown=3`, `python=2`, `rust=3`, and `errors=[]`. Merge review:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-dataset-merge.review.json`
    with `added_records=13`, `duplicate_records=0`, `total_records=50`,
    and `hard_blockers=[]`. Queue validation:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-curated-queue-validation.json`
    with `ok=true`, `records=50`, `errors=[]`, categories `bash=5`,
    `json=4`, `markdown=8`, `python=19`, `rust=5`, `sql=3`, `toml=6`,
    and qualities `reviewed=50`. Readiness:
    `/workspace/outputs/evals/repo-adapt-balanced-xwide-20260520T165801Z.batch1-curated-queue-readiness.json`
    with `review_status=manual_training_review_required`,
    `ready_records=50`, `min_records=50`, `record_gap=0`,
    `category_count=7`, `hard_blockers=[]`,
    `ready_for_manual_training_review=true`,
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. Training was not
    started. The next step is a manual training-dataset review and explicit
    user approval before launching any separate Vast GPU training run.
  - The `356872d` repo-adaptation expanded-prompt checkpoint required no
    service restart because it changed only Python helper/test/doc files. vLLM
    stayed on pid `5802`; FastAPI stayed on pid `53902`. Focused Vast
    verification passed with
    `/workspace/biber-venv/bin/python -m compileall training tests` and pytest
    `tests/test_repo_adaptation_plan.py tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_failure_review.py tests/test_repo_adaptation_dataset_readiness.py tests/test_training_dataset.py -q`
    reporting `20 passed`.
  - Expanded repo-adaptation local-model eval artifacts now exist on the Vast
    volume. Plan:
    `/workspace/outputs/repo-adapt-expanded-20260520T155919Z.plan.json`.
    Prompts:
    `/workspace/outputs/repo-adapt-expanded-20260520T155919Z.prompts.jsonl`.
    First eval summary:
    `/workspace/outputs/evals/repo-adapt-expanded-20260520T155919Z.summary.json`
    with `24/24` responses and `9/24` expectation checks passed. Repeat eval
    summary:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.summary.json`
    with `24/24` responses and `11/24` expectation checks passed.
    Repeat failure review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.repeat-review.json`
    with `failures_seen=28`, `groups=15`, and `training_candidates=13`.
    Candidate queue:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.repeat-training-candidates.jsonl`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.repeat-candidate-review.json`
    with `records=13`, `ready_records=0`, `pending_review_records=13`,
    `quality_counts={"needs_review":13}`, and
    `hard_blockers=["candidate_outputs_missing","candidate_quality_not_reviewed","candidate_validation_errors","below_min_ready_records"]`.
    Training was not started; these are review-only candidates.
  - Batch 1 of the expanded repo-adaptation candidates has been manually
    reviewed and merged. Selected candidates:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-selected-candidates.jsonl`.
    Decisions:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-candidate-decisions.json`.
    Reviewed rows:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-reviewed-candidates.jsonl`.
    Decision review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-candidate-decisions.review.json`
    with `approved_records=4`, `records=4`, and `hard_blockers=[]`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-reviewed-candidate-review.json`
    with `ready_records=4`, `records=4`, and `hard_blockers=[]`.
    Reviewed-dataset validation:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-reviewed-dataset-validation.json`
    with `ok=true`, `records=4`, and `errors=[]`. Merge review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-dataset-merge.review.json`
    with `added_records=4`, `duplicate_records=0`, `total_records=8`, and
    `hard_blockers=[]`. Queue validation:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-curated-queue-validation.json`
    with `ok=true`, `records=8`, `errors=[]`, categories `bash=1`,
    `markdown=1`, `python=5`, `sql=1`, and qualities `reviewed=8`.
    Readiness:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch1-curated-queue-readiness.json`
    with `review_status=training_blocked`, `ready_records=8`,
    `min_records=50`, `record_gap=42`,
    `hard_blockers=["below_min_ready_records"]`,
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. The first
    unfiltered batch attempt intentionally failed because the decision helper
    requires a decision for every input candidate; the passing run used the
    4-row selected candidate file above.
  - Batch 2 of the expanded repo-adaptation candidates has also been manually
    reviewed and merged. Selected candidates:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-selected-candidates.jsonl`.
    Decisions:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-candidate-decisions.json`.
    Reviewed rows:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-reviewed-candidates.jsonl`.
    Decision review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-candidate-decisions.review.json`
    with `approved_records=4`, `records=4`, and `hard_blockers=[]`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-reviewed-candidate-review.json`
    with `ready_records=4`, `records=4`, and `hard_blockers=[]`.
    Reviewed-dataset validation:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-reviewed-dataset-validation.json`
    with `ok=true`, `records=4`, and `errors=[]`. Merge review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-dataset-merge.review.json`
    with `added_records=4`, `duplicate_records=0`, `total_records=12`, and
    `hard_blockers=[]`. Queue validation:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-curated-queue-validation.json`
    with `ok=true`, `records=12`, `errors=[]`, categories `bash=1`,
    `markdown=1`, `python=9`, `sql=1`, and qualities `reviewed=12`.
    Readiness:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch2-curated-queue-readiness.json`
    with `review_status=training_blocked`, `ready_records=12`,
    `min_records=50`, `record_gap=38`,
    `hard_blockers=["below_min_ready_records"]`,
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. Training was not
    started.
  - Batch 3, the final remaining expanded repo-adaptation candidate batch, has
    also been manually reviewed and merged. Selected candidates:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-selected-candidates.jsonl`.
    Decisions:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-candidate-decisions.json`.
    Reviewed rows:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-reviewed-candidates.jsonl`.
    Decision review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-candidate-decisions.review.json`
    with `approved_records=5`, `records=5`, and `hard_blockers=[]`.
    Candidate review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-reviewed-candidate-review.json`
    with `ready_records=5`, `records=5`, and `hard_blockers=[]`.
    Reviewed-dataset validation:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-reviewed-dataset-validation.json`
    with `ok=true`, `records=5`, and `errors=[]`. Merge review:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-dataset-merge.review.json`
    with `added_records=5`, `duplicate_records=0`, `total_records=17`, and
    `hard_blockers=[]`. Queue validation:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-curated-queue-validation.json`
    with `ok=true`, `records=17`, `errors=[]`, categories `bash=1`,
    `markdown=1`, `python=14`, `sql=1`, and qualities `reviewed=17`.
    Readiness:
    `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-curated-queue-readiness.json`
    with `review_status=training_blocked`, `ready_records=17`,
    `min_records=50`, `record_gap=33`,
    `hard_blockers=["below_min_ready_records"]`,
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. Training was not
    started. The 13-candidate expanded eval queue is now fully reviewed/merged;
    next, collect more diversified repo-adaptation eval signal rather than
    training from only 17 rows.
  - The `299af9b` repo-adaptation dataset-readiness checkpoint required no
    service restart because it changed only Python helper/test/doc files. vLLM
    stayed on pid `5802`; FastAPI stayed on pid `53902`. Focused Vast
    verification passed with
    `/workspace/biber-venv/bin/python -m compileall training tests` and pytest
    `tests/test_repo_adaptation_dataset_readiness.py tests/test_repo_adaptation_dataset_merge.py tests/test_repo_adaptation_candidate_decisions.py tests/test_repo_adaptation_candidate_review.py tests/test_training_dataset.py -q`
    reporting `20 passed`.
  - Repo-adaptation curated queue readiness was generated at
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.curated-queue-readiness.json`
    for dataset `/workspace/data/repo_adaptation/reviewed_candidates.jsonl`.
    Result: `review_status=training_blocked`, `training_gate_status=blocked`,
    `ready_records=4`, `min_records=50`, `record_gap=46`,
    `category_count=4`, `category_gap=0`, `missing_required_categories=[]`,
    `hard_blockers=["below_min_ready_records"]`, `training_dataset_ready=false`,
    `training_allowed=false`, `safe_to_train=false`, and
    `approved_for_training=false`. Next, collect at least 46 more reviewed
    repo-adaptation rows before manual training review.
  - The `436f955` repo-adaptation dataset-merge checkpoint required no service
    restart because it changed only Python helper/test/doc files. vLLM stayed
    on pid `5802`; FastAPI stayed on pid `53902`. Focused Vast verification
    passed with
    `/workspace/biber-venv/bin/python -m compileall training tests` and pytest
    `tests/test_repo_adaptation_dataset_merge.py tests/test_repo_adaptation_candidate_decisions.py tests/test_repo_adaptation_candidate_review.py tests/test_training_dataset.py -q`
    reporting `16 passed`.
  - The reviewed repo-adaptation rows were merged into the cumulative curated
    queue at `/workspace/data/repo_adaptation/reviewed_candidates.jsonl`.
    Merge review:
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.dataset-merge.review.json`.
    Validation report:
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.curated-queue-validation.json`.
    Result: `added_records=4`, `duplicate_records=0`, `total_records=4`,
    `hard_blockers=[]`, validation `ok=true`, `errors=[]`, `warnings=[]`,
    categories `bash=1`, `markdown=1`, `python=1`, `sql=1`, and qualities
    `reviewed=4`. Training was not started; the merge review still keeps
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. Next, collect
    more repo-adaptation examples before any training run.
  - The `a53be7a` repo-adaptation candidate decision checkpoint required no
    service restart because it changed only Python helper/test/doc files. vLLM
    stayed on pid `5802`; FastAPI stayed on pid `53902`. Focused Vast
    verification passed with
    `/workspace/biber-venv/bin/python -m compileall training tests` and pytest
    `tests/test_repo_adaptation_candidate_decisions.py tests/test_repo_adaptation_candidate_review.py tests/test_repo_adaptation_failure_review.py tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_plan.py tests/test_training_dataset.py -q`
    reporting `23 passed`.
  - Reviewed repo-adaptation candidate artifacts now exist on the Vast volume:
    decisions
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.repeat-candidate-decisions.json`,
    reviewed rows
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.reviewed-candidates.jsonl`,
    decision review
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.candidate-decisions.review.json`,
    candidate review
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.reviewed-candidate-review.json`,
    and validation report
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.reviewed-dataset-validation.json`.
    Result: `approved_records=4`, `ready_records=4`,
    `ready_for_dataset_validation=true`, dataset validation `ok=true`,
    `records=4`, `errors=[]`, `warnings=[]`, and qualities `reviewed=4`.
    Training was not started; the review artifacts still keep
    `training_dataset_ready=false`, `training_allowed=false`,
    `safe_to_train=false`, and `approved_for_training=false`. The next
    cost-conscious step is a separate explicit promotion/merge decision for
    these four reviewed rows, not automatic training.
  - The `a1b9f5a` repo-adaptation candidate review checkpoint required no
    service restart because it changed only Python helper/test/doc files. vLLM
    stayed on pid `5802`; FastAPI stayed on pid `53902`. Training was not
    started because the repeated repo-adaptation candidate queue still has
    `ready_records=0` and `ready_for_dataset_validation=false`.
  - Latest focused Vast verification for the BIBER repo-adaptation candidate
    review slice:
    `/workspace/biber-venv/bin/python -m compileall training tests` and focused
    pytest
    `tests/test_repo_adaptation_candidate_review.py tests/test_repo_adaptation_failure_review.py tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_plan.py tests/test_training_dataset.py -q`
    with `19 passed`. The new helper was then run against
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.repeat-training-candidates.jsonl`
    and wrote
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.repeat-candidate-review.json`.
    Result: `records=4`, `ready_records=0`, `pending_review_records=4`,
    `ready_for_dataset_validation=false`,
    `hard_blockers=["candidate_outputs_missing","candidate_quality_not_reviewed","candidate_validation_errors","below_min_ready_records"]`,
    `training_dataset_ready=false`, `training_allowed=false`, and
    `safe_to_train=false`. Do not train from these rows until verified outputs
    are written and the candidate review passes.
  - The `c4abe43` repair-chain training pipeline listing checkpoint required
    no service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`. Training was not started because the latest pipeline list found
    `matched=1`, `blocked=1`, and `ready_for_dataset_validation=0`.
  - Latest focused Vast verification for the BIBER repair-chain training
    pipeline listing slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `145 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The latest smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T141710Z-70132` and verified
    `list-repair-chain-training-pipelines` against the current smoke output
    directory. The list artifact was
    `/workspace/outputs/biber-agent-smoke-20260520T141710Z-70132/agent-client-mvp-loop-repair-chain-training-pipeline-list.json`
    with `matched=1`, `blocked=1`, `ready_for_dataset_validation=0`,
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`. Use
    `scripts/biber_agent_client.py --json list-repair-chain-training-pipelines /workspace/outputs --limit 10`
    on Vast to scan recent output directories before considering training.
  - Repo-adaptation repeatability evidence was collected on Vast without
    OpenAI and without starting training. First, the scanner confirmed all
    existing repair-chain training pipeline artifacts remain blocked:
    `matched=3`, `blocked=3`, `ready_for_dataset_validation=0`. Then
    `training/repo_adaptation_plan.py` was run against
    `/workspace/biber-ai-platform` with `--max-prompts 6`, writing
    `/workspace/outputs/repo-adapt-20260520T142159Z-70342.plan.json` and
    `/workspace/outputs/repo-adapt-20260520T142159Z-70342.prompts.jsonl`.
    The same six prompts were evaluated twice through the local served BIBER
    model:
    `/workspace/outputs/evals/repo-adapt-20260520T142159Z-70342.summary.json`
    and
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.summary.json`
    both reported `ok=6`, `failed=0`, `expectation_ok=2`, and
    `expectation_failed=4`. The combined repeated-failure review was written
    to
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.repeat-review.json`
    with `failures_seen=8`, `groups=4`, `min_repeats=2`, and
    `training_candidates=4`; the review-only candidate JSONL was written to
    `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.repeat-training-candidates.jsonl`.
    These candidates still have empty `output` fields and `quality=needs_review`;
    they are evidence for human review only, not a trainable dataset.
  - The `76c4401` repair-chain training pipeline status checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`. Training was not started because the consolidated training
    pipeline status remains `blocked` with
    `missing_or_blocked_step=baseline_ready_records`.
  - Latest focused Vast verification for the BIBER repair-chain training
    pipeline status slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `144 passed` at `244ac7c`, followed by `76c4401` Vast
    fast-forward, `bash -n scripts/vast_biber_agent_smoke.sh`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`.
    The latest smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T140446Z-69910` and verified
    `review-repair-chain-training-pipeline` against the current smoke
    repair-chain artifacts. The pipeline artifact was
    `/workspace/outputs/biber-agent-smoke-20260520T140446Z-69910/agent-client-mvp-loop-repair-chain-training-pipeline.json`
    with `training_pipeline_status=blocked`,
    `missing_or_blocked_step=baseline_ready_records`,
    `baseline_ready_records=0`, `training_candidate_records=0`,
    `ready_for_dataset_validation=false`,
    `hard_blockers=["baseline_ready_records","no_baseline_ready_records","training_candidate_records","no_training_candidate_records","below_min_ready_records","dataset_validation_not_ready"]`,
    `safe_to_train=false`, `training_allowed=false`, `github_save_ready=false`,
    and `approved_for_training=false`. This is a no-model-call status report
    only; it does not create a trainable dataset, start a Vast training job,
    approve model promotion, save to GitHub, rotate credentials, or approve
    public XRIQ work.
  - The `693a1ca` repair-chain training candidate review checkpoint required
    no service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`. Training was not started because the training candidate review
    still has `records=0` and `ready_for_dataset_validation=false`.
  - Latest focused Vast verification for the BIBER repair-chain training
    candidate review slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `142 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T132554Z-69501` and verified
    `review-repair-chain-training-candidates` against the empty training
    candidate queue. The review artifact was
    `/workspace/outputs/biber-agent-smoke-20260520T132554Z-69501/agent-client-mvp-loop-repair-chain-training-candidate-review.json`
    with `records=0`, `review_status=training_candidates_need_review`,
    `ready_for_dataset_validation=false`, `training_dataset_ready=false`,
    `hard_blockers=["no_training_candidate_records","below_min_ready_records"]`,
    `safe_to_train=false`, `training_allowed=false`, `github_save_ready=false`,
    and `approved_for_training=false`. This is a candidate-review gate only; it
    does not create a trainable dataset, start a Vast training job, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - The `966ba05` repair-chain training candidate export checkpoint required
    no service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`. Training was not started because the training candidate export
    remained blocked by `no_baseline_ready_records`.
  - Latest focused Vast verification for the BIBER repair-chain training
    candidate export slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `140 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T131717Z-69256` and verified
    `export-repair-chain-training-candidates` against the blocked readiness
    artifact. The candidate JSONL was
    `/workspace/outputs/biber-agent-smoke-20260520T131717Z-69256/agent-client-mvp-loop-repair-chain-training-candidates.jsonl`
    with `records=0`, `export_status=training_candidates_blocked`,
    `training_dataset_ready=false`, `requires_human_training_dataset_review=false`,
    `review_queue_only=true`, `hard_blockers=["no_baseline_ready_records"]`,
    `safe_to_train=false`, `training_allowed=false`, `github_save_ready=false`,
    and `approved_for_training=false`. This is a candidate-export gate only;
    it does not create a trainable dataset, start a Vast training job, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - The `c356d70` repair-chain training readiness checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`. Training was not started because the readiness gate still has
    `baseline_ready_records=0`.
  - Latest focused Vast verification for the BIBER repair-chain training
    readiness slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `138 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T130509Z-69009` and verified
    `review-repair-chain-training-readiness` against the empty held-out
    baseline decision review. The readiness artifact was
    `/workspace/outputs/biber-agent-smoke-20260520T130509Z-69009/agent-client-mvp-loop-repair-chain-training-readiness.json`
    with `review_status=training_blocked`, `training_gate_status=blocked`,
    `baseline_ready_records=0`, `ready_for_manual_training_dataset_review=false`,
    `hard_blockers=["no_baseline_ready_records"]`, `eval_only=true`,
    `safe_to_train=false`, `training_allowed=false`, `github_save_ready=false`,
    and `approved_for_training=false`. This is a training-readiness gate only;
    it does not create training data, start a Vast training job, approve model
    promotion, save to GitHub, rotate credentials, or approve public XRIQ work.
  - The `57d4e4b` repair-chain held-out baseline candidate review artifact
    inspection checkpoint required no service restart because it changed only
    the stdlib agent client, smoke script, tests, and API examples. vLLM stayed
    on pid `84653`; FastAPI stayed on pid `85630`. Training was not started
    because the smoke baseline-candidate review artifact still has `records=0`,
    `baseline_candidates=0`, and `baseline_ready_records=0`.
  - Latest focused Vast verification for the BIBER repair-chain held-out
    baseline candidate review artifact inspection slice:
    local `py_compile` for `scripts/biber_agent_client.py` and
    `tests/test_biber_agent_client.py`, local `git diff --check`, and a local
    offline show/list smoke passed. Local pytest is still unavailable on the
    Windows workstation (`No module named pytest`), and local `bash -n` is
    blocked because WSL has no installed distro. Vast verification passed
    `. /venv/main/bin/activate`,
    `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `128 passed`, live
    `bash scripts/vast_biber_agent_smoke.sh`, and
    `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260521T171749Z-92929` and verified
    `show-repair-chain-heldout-baseline-candidate-review` plus
    `list-repair-chain-heldout-baseline-candidate-reviews` against
    `/workspace/outputs/biber-agent-smoke-20260521T171749Z-92929/agent-client-mvp-loop-repair-chain-heldout-baseline-candidate-review.json`.
    The review artifact stayed at `records=0`, `baseline_candidates=0`,
    `baseline_candidate_ready_records=0`, `baseline_ready_records=0`,
    `requires_baseline_review_records=0`, `eval_only=true`,
    `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    offline inspection evidence only; it does not create training data, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - The `33ed241` repair-chain held-out baseline decision review artifact
    inspection checkpoint required no service restart because it changed only
    the stdlib agent client, smoke script, tests, and API examples. vLLM stayed
    on pid `84653`; FastAPI stayed on pid `85630`. Training was not started
    because the smoke baseline-decision review artifact still has `records=0`
    and `baseline_ready_records=0`.
  - Latest focused Vast verification for the BIBER repair-chain held-out
    baseline decision review artifact inspection slice:
    local `py_compile` for `scripts/biber_agent_client.py` and
    `tests/test_biber_agent_client.py`, local `git diff --check`, and a local
    offline show/list smoke passed. Local pytest is still unavailable on the
    Windows workstation (`No module named pytest`), and local `bash -n` is
    blocked because WSL has no installed distro. Vast verification passed
    `. /venv/main/bin/activate`,
    `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `130 passed`, live
    `bash scripts/vast_biber_agent_smoke.sh`, and
    `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260521T175022Z-93260` and verified
    `show-repair-chain-heldout-baseline-decision-review` plus
    `list-repair-chain-heldout-baseline-decision-reviews` against
    `/workspace/outputs/biber-agent-smoke-20260521T175022Z-93260/agent-client-mvp-loop-repair-chain-heldout-baseline-decision-review.json`.
    The review artifact stayed at `records=0`,
    `approved_as_baseline_records=0`, `baseline_candidate_ready_records=0`,
    `baseline_ready_records=0`, `requires_baseline_review_records=0`,
    `eval_only=true`, `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    offline inspection evidence only; it does not create training data, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - The `adf8b7d` repair-chain training readiness artifact inspection
    checkpoint required no service restart because it changed only the stdlib
    agent client, smoke script, tests, and API examples. vLLM stayed on pid
    `84653`; FastAPI stayed on pid `85630`. Training was not started because
    the smoke training-readiness artifact still has
    `training_gate_status=blocked`,
    `ready_for_manual_training_dataset_review=false`, and
    `hard_blockers=["no_baseline_ready_records"]`.
  - Latest focused Vast verification for the BIBER repair-chain training
    readiness artifact inspection slice:
    local `py_compile` for `scripts/biber_agent_client.py` and
    `tests/test_biber_agent_client.py`, local `git diff --check`, and a local
    offline show/list smoke passed. Local pytest is still unavailable on the
    Windows workstation (`No module named pytest`), and local `bash -n` is
    blocked because WSL has no installed distro. Vast verification passed
    `. /venv/main/bin/activate`,
    `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `132 passed`, and live
    `bash scripts/vast_biber_agent_smoke.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260521T180528Z-93594` and verified
    `show-repair-chain-training-readiness` plus
    `list-repair-chain-training-readiness` against
    `/workspace/outputs/biber-agent-smoke-20260521T180528Z-93594/agent-client-mvp-loop-repair-chain-training-readiness.json`.
    The readiness artifact stayed at `review_status=training_blocked`,
    `training_gate_status=blocked`, `baseline_ready_records=0`,
    `ready_for_manual_training_dataset_review=false`,
    `hard_blockers=["no_baseline_ready_records"]`, `eval_only=true`,
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    offline inspection evidence only; it does not create training data, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - The `ae8c93b` repair-chain training candidate review artifact inspection
    checkpoint required no service restart because it changed only the stdlib
    agent client, smoke script, tests, and API examples. vLLM stayed on pid
    `84653`; FastAPI stayed on pid `85630`. Training was not started because
    the smoke training-candidate review artifact still has
    `review_status=training_candidates_need_review`,
    `ready_for_dataset_validation=false`, and
    `hard_blockers=["no_training_candidate_records","below_min_ready_records"]`.
  - Latest focused Vast verification for the BIBER repair-chain training
    candidate review artifact inspection slice:
    local `py_compile` for `scripts/biber_agent_client.py` and
    `tests/test_biber_agent_client.py`, local `git diff --check`, and a local
    offline show/list smoke passed. Local pytest is still unavailable on the
    Windows workstation (`No module named pytest`), and local `bash -n` is
    blocked because WSL has no installed distro. Vast verification passed
    `. /venv/main/bin/activate`,
    `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `134 passed`, and live
    `bash scripts/vast_biber_agent_smoke.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260521T181452Z-93895` and verified
    `show-repair-chain-training-candidate-review` plus
    `list-repair-chain-training-candidate-reviews` against
    `/workspace/outputs/biber-agent-smoke-20260521T181452Z-93895/agent-client-mvp-loop-repair-chain-training-candidate-review.json`.
    The candidate-review artifact stayed at
    `review_status=training_candidates_need_review`, `records=0`,
    `reviewed_records=0`, `ready_for_dataset_validation=false`,
    `training_dataset_ready=false`,
    `hard_blockers=["no_training_candidate_records","below_min_ready_records"]`,
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    offline inspection evidence only; it does not create training data, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - The `83162d7` repair-chain training pipeline status artifact inspection
    checkpoint required no service restart because it changed only the stdlib
    agent client, smoke script, tests, and API examples. vLLM stayed on pid
    `84653`; FastAPI stayed on pid `85630`. Training was not started because
    the smoke training-pipeline artifact still has
    `training_pipeline_status=blocked`,
    `missing_or_blocked_step=baseline_ready_records`, and
    `hard_blockers=["baseline_ready_records","no_baseline_ready_records","training_candidate_records","no_training_candidate_records","below_min_ready_records","dataset_validation_not_ready"]`.
  - Latest focused Vast verification for the BIBER repair-chain training
    pipeline status artifact inspection slice:
    local `py_compile` for `scripts/biber_agent_client.py` and
    `tests/test_biber_agent_client.py`, local `git diff --check`, local CLI
    help, and a local offline show/list smoke passed. Local pytest is still
    unavailable on the Windows workstation (`No module named pytest`), and
    local `bash -n` is blocked because WSL has no installed distro. Vast
    verification passed `. /venv/main/bin/activate`,
    `python -m py_compile scripts/biber_agent_client.py tests/test_biber_agent_client.py`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py -q` with `135 passed`, and live
    `bash scripts/vast_biber_agent_smoke.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260521T185344Z-94191` and verified
    `show-repair-chain-training-pipeline` against
    `/workspace/outputs/biber-agent-smoke-20260521T185344Z-94191/agent-client-mvp-loop-repair-chain-training-pipeline.json`.
    The pipeline artifact stayed at `training_pipeline_status=blocked`,
    `missing_or_blocked_step=baseline_ready_records`,
    `baseline_ready_records=0`, `training_candidate_records=0`,
    `training_candidate_review_records=0`,
    `ready_for_dataset_validation=false`, `eval_only=true`,
    `training_allowed=false`, `safe_to_train=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    offline inspection evidence only; it does not create training data, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - Controlled baseline-candidate evidence was created on Vast at
    `/workspace/outputs/biber-baseline-candidate-20260521T190501Z-94473` from
    the passing smoke held-out eval review
    `/workspace/outputs/biber-agent-smoke-20260521T185344Z-94191/agent-client-mvp-loop-repair-chain-heldout-eval-review.json`.
    The held-out eval review had `records=1`, `passed_records=1`,
    `expectation_failed_records=0`, `error_records=0`, `ok=true`, and all
    training/promotion/GitHub flags false. A controlled Codex review recorded
    `accept_for_baseline`, exported one held-out baseline candidate, then
    recorded `approve_as_baseline` as baseline evidence only. Resulting
    baseline decision review:
    `/workspace/outputs/biber-baseline-candidate-20260521T190501Z-94473/agent-client-mvp-loop-repair-chain-heldout-baseline-decision-review.json`
    with `records=1`, `approved_as_baseline_records=1`,
    `baseline_candidate_ready_records=1`, `baseline_ready_records=1`, and
    `training_allowed=false`.
  - The controlled training-readiness artifact is
    `/workspace/outputs/biber-baseline-candidate-20260521T190501Z-94473/agent-client-mvp-loop-repair-chain-training-readiness.json`.
    It reports `review_status=baseline_ready_manual_training_review_required`,
    `training_gate_status=manual_review_required`,
    `baseline_ready_records=1`, `ready_for_manual_training_dataset_review=true`,
    `hard_blockers=[]`, `training_allowed=false`, `safe_to_train=false`, and
    `approved_for_training=false`. This moved the controlled evidence path
    past the previous `no_baseline_ready_records` blocker, but still does not
    authorize training.
  - The controlled training-candidate queue is
    `/workspace/outputs/biber-baseline-candidate-20260521T190501Z-94473/agent-client-mvp-loop-repair-chain-training-candidates.jsonl`.
    It contains one human-review-only candidate row with empty `output`,
    `quality=needs_review`, and `review_required=true`. The candidate review
    artifact
    `/workspace/outputs/biber-baseline-candidate-20260521T190501Z-94473/agent-client-mvp-loop-repair-chain-training-candidate-review.json`
    reports `records=1`, `pending_review_records=1`, `reviewed_records=0`,
    `empty_output_records=1`, `unreviewed_quality_records=1`,
    `ready_for_dataset_validation=false`, and
    `hard_blockers=["candidate_outputs_missing","candidate_quality_not_reviewed","below_min_ready_records"]`.
    This candidate row was manually inspected after creation. It should not be
    filled or marked `reviewed` because its input is only controlled smoke
    baseline metadata:
    `repair_chain_python_compileall_api_254615cf9287`, with no concrete user
    repo task, patch, diagnosis, or verified coding answer. Treat it as gate
    validation evidence only, not model-improvement data.
  - The controlled training-pipeline artifact is
    `/workspace/outputs/biber-baseline-candidate-20260521T190501Z-94473/agent-client-mvp-loop-repair-chain-training-pipeline.json`.
    It reports `training_pipeline_status=blocked`,
    `missing_or_blocked_step=candidate_outputs_missing`,
    `baseline_ready_records=1`, `training_gate_status=manual_review_required`,
    `training_candidate_records=1`, `training_candidate_review_records=1`,
    `ready_for_manual_training_dataset_review=true`,
    `ready_for_dataset_validation=false`,
    `hard_blockers=["candidate_outputs_missing","candidate_quality_not_reviewed","below_min_ready_records","dataset_validation_not_ready"]`,
    and all training/promotion/GitHub flags false. Next narrow step is manual
    training-candidate review from real repo evidence: collect a candidate
    with a concrete task, failure, diagnosis, patch, and verified answer before
    filling `output` or setting `quality=reviewed|verified`. Still require
    explicit user approval before any Vast training job.
  - The `a045c63` repair-chain held-out baseline decision review checkpoint
    required no service restart because it changed only the stdlib agent
    client, smoke script, and tests. vLLM stayed on pid `5802`; FastAPI stayed
    on pid `53902`. Training was not started because the current held-out
    baseline decision review has `records=0` and `baseline_ready_records=0`.
  - Latest focused Vast verification for the BIBER repair-chain held-out
    baseline decision review slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `136 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T111537Z-68759` and verified
    `review-repair-chain-heldout-baseline-decisions` against the empty
    baseline-decision queue produced from the synthetic `defer` decision. The
    review artifact was
    `/workspace/outputs/biber-agent-smoke-20260520T111537Z-68759/agent-client-mvp-loop-repair-chain-heldout-baseline-decision-review.json`
    with `records=0`, `approved_as_baseline_records=0`,
    `baseline_ready_records=0`, `requires_baseline_review_records=0`,
    `eval_only=true`, `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    baseline-decision review evidence only; it does not create training data,
    approve model promotion, save to GitHub, rotate credentials, or approve
    public XRIQ work.
  - The `55713f4` repair-chain held-out baseline decision checkpoint required
    no service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`. Training was not started because the current held-out baseline
    decision queue has `records=0` and `baseline_ready=false`.
  - Latest focused Vast verification for the BIBER repair-chain held-out
    baseline decision slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `135 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T015932Z-68459` and verified
    `record-repair-chain-heldout-baseline-candidate-decision` against the empty
    baseline-candidate queue produced from the synthetic `defer` decision. The
    decision JSONL path was
    `/workspace/outputs/biber-agent-smoke-20260520T015932Z-68459/agent-client-mvp-loop-repair-chain-heldout-baseline-decisions.jsonl`
    with `records=0`, `rejected_records=0`,
    `approved_as_baseline_records=0`, `baseline_ready=false`,
    `eval_only=true`, `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    baseline-decision evidence only; it does not create training data, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - The `c1fdba8` repair-chain held-out baseline candidate review checkpoint
    required no service restart because it changed only the stdlib agent
    client, smoke script, and tests. vLLM stayed on pid `5802`; FastAPI stayed
    on pid `53902`. Training was not started because the current held-out
    baseline candidate queue has `records=0` and `baseline_ready_records=0`.
  - Latest focused Vast verification for the BIBER repair-chain held-out
    baseline candidate review slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `134 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T014240Z-68223` and verified
    `review-repair-chain-heldout-baseline-candidates` against the empty
    baseline-candidate queue produced from the synthetic `defer` decision. The
    review artifact was
    `/workspace/outputs/biber-agent-smoke-20260520T014240Z-68223/agent-client-mvp-loop-repair-chain-heldout-baseline-candidate-review.json`
    with `records=0`, `baseline_candidates=0`,
    `baseline_candidate_ready_records=0`, `baseline_ready_records=0`,
    `requires_baseline_review_records=0`, `eval_only=true`,
    `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    review evidence only; it does not create training data, approve model
    promotion, save to GitHub, rotate credentials, or approve public XRIQ work.
  - The `e7f3fe5` repair-chain held-out baseline candidate export checkpoint
    required no service restart because it changed only the stdlib agent
    client, smoke script, and tests. vLLM stayed on pid `5802`; FastAPI stayed
    on pid `53902`.
  - Latest focused Vast verification for the BIBER repair-chain held-out
    baseline candidate export slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `133 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260520T012019Z-67988` and verified
    `export-repair-chain-heldout-baseline-candidates` against the synthetic
    held-out decision queue. Because the smoke decision is `defer`, the export
    correctly wrote zero candidate rows with `records=0`, `skipped_records=1`,
    `rejected_records=0`, `baseline_candidates=0`,
    `baseline_candidate_ready=false`, `requires_baseline_review=false`,
    `eval_only=true`, `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. The candidate
    JSONL path was
    `/workspace/outputs/biber-agent-smoke-20260520T012019Z-67988/agent-client-mvp-loop-repair-chain-heldout-baseline-candidates.jsonl`.
    This export is baseline-review-only; it does not create training data,
    approve model promotion, save to GitHub, rotate credentials, or approve
    public XRIQ work.
  - The `bf01ce2` repair-chain held-out eval decision review checkpoint
    required no service restart because it changed only the stdlib agent
    client, smoke script, and tests. vLLM stayed on pid `5802`; FastAPI stayed
    on pid `53902`.
  - Latest focused Vast verification for the BIBER repair-chain held-out eval
    decision review slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `132 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    `bash scripts/vast_eval_repair_chain_prompts_direct.sh`,
    `review-repair-chain-heldout-eval-results`,
    `record-repair-chain-heldout-eval-decision`,
    `review-repair-chain-heldout-eval-decisions`, and
    `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T222522Z-67700` and verified
    `review-repair-chain-heldout-eval-decisions` with `records=1`,
    `decision_counts={"defer": 1}`, `defer_records=1`,
    `accepted_for_baseline_records=0`,
    `baseline_candidate_ready_records=0`, `follow_up_records=1`,
    `eval_only=true`, `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`.
    The live held-out eval runner then wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T222528Z.jsonl`
    and
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T222528Z.summary.json`;
    the review command wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T222528Z.review.json`,
    the decision command wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T222528Z.decisions.jsonl`,
    and the decision-review command wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T222528Z.decision-review.json`
    with `review_status=heldout_eval_decision_summary_only`, `records=1`,
    `rejected_records=0`, `decision_counts={"defer": 1}`,
    `defer_records=1`, `reject_records=0`,
    `accepted_for_baseline_records=0`,
    `baseline_candidate_ready_records=0`, `follow_up_records=1`,
    `eval_only=true`, `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This is
    decision-review evidence only; it does not create training data, approve
    model promotion, save to GitHub, rotate credentials, or approve public XRIQ
    work.
  - The `c254677` repair-chain held-out eval decision checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain held-out eval
    decision slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `131 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    `bash scripts/vast_eval_repair_chain_prompts_direct.sh`, and
    `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T215951Z-67419` and verified
    `record-repair-chain-heldout-eval-decision` with `decision=defer`,
    `records=1`, `accepted_for_baseline_records=0`,
    `baseline_candidate_ready=false`, `eval_only=true`,
    `safe_to_train=false`, `training_allowed=false`, `github_save_ready=false`,
    and `approved_for_training=false`.
    The live held-out eval runner then wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T215957Z.jsonl`
    and
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T215957Z.summary.json`;
    the review command wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T215957Z.review.json`,
    and the decision command wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T215957Z.decisions.jsonl`
    with `decision=defer`, `reviewer=biber-vast-smoke`,
    `accepted_for_baseline=false`, `baseline_candidate_ready=false`,
    `requires_follow_up=true`, `eval_only=true`, `safe_to_train=false`,
    `training_allowed=false`, `github_save_ready=false`, and
    `approved_for_training=false`. This is decision evidence only; it does not
    create training data, approve model promotion, save to GitHub, or approve
    public XRIQ work.
  - The `28353e8` repair-chain held-out eval result review checkpoint required
    no service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain held-out eval
    result review slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`,
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `130 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    `bash scripts/vast_eval_repair_chain_prompts_direct.sh`, and
    `bash scripts/vast_status_direct.sh`.
    The smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T205344Z-67143` and verified
    the offline `review-repair-chain-heldout-eval-results` command with
    `ok=true`, `records=1`, `passed_records=1`, `failed_records=0`,
    `eval_only=true`, `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`.
    The live held-out eval runner then wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T205350Z.jsonl`
    and
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T205350Z.summary.json`;
    the new review command wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T205350Z.review.json`
    with `review_status=heldout_eval_passed`, `ok=true`, `records=1`,
    `passed_records=1`, `failed_records=0`, `expectation_failed_records=0`,
    `rejected_records=0`, and `model_counts={"biber-dev-core-v1": 1}`. This is
    live-eval review evidence only; it does not create training data, approve
    training, save to GitHub, or approve public XRIQ work.
  - The `95051e5` repair-chain held-out eval runner checkpoint required no
    service restart because it added only the Vast helper script
    `scripts/vast_eval_repair_chain_prompts_direct.sh`. vLLM stayed on pid
    `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER repair-chain held-out eval
    runner slice:
    `bash -n scripts/vast_eval_repair_chain_prompts_direct.sh`,
    `bash scripts/vast_eval_repair_chain_prompts_direct.sh`,
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    focused pytest
    `tests/test_live_model_eval.py tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `129 passed`, and `bash scripts/vast_status_direct.sh`.
    The runner automatically found
    `/workspace/outputs/biber-agent-smoke-20260519T203639Z-66726/agent-client-mvp-loop-ready-repair-chain-eval-prompts.jsonl`,
    scored it through the current local BIBER API at `127.0.0.1:8000`, and
    wrote
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T204610Z.jsonl`
    plus
    `/workspace/outputs/evals/biber-repair-chain-heldout-20260519T204610Z.summary.json`.
    The summary had `prompts=1`, `ok=1`, `failed=0`, `expectation_ok=1`, and
    `expectation_failed=0`; the result matched `Repair`, `Test`, and `Risk`
    using model `biber-dev-core-v1`. This is live-eval evidence only; it does
    not create training data, does not approve training, does not save to
    GitHub, and does not approve public XRIQ work.
  - The `16523ac` repair-chain held-out eval prompt export checkpoint required
    no service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain held-out eval
    prompt export slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `118 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T203639Z-66726`, verified
    `export-ready-repair-chain-eval-prompts` against the validated
    eval-dataset JSONL queue, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T203639Z-66726/agent-client-mvp-loop-ready-repair-chain-eval-prompts.jsonl`
    with `records=1`, `eval_prompts=1`, `eval_only=true`,
    `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This creates
    held-out live-eval prompts only; it is not a training dataset, does not
    save to GitHub, and does not approve public XRIQ work. GitHub remained
    skipped because `github_configured=false`.
  - The `78608bb` repair-chain eval-dataset validation checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain eval-dataset
    validation slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `117 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T201849Z-66297`, verified
    `validate-ready-repair-chain-eval-dataset` against the exported
    eval-dataset JSONL queue, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T201849Z-66297/agent-client-mvp-loop-ready-repair-chain-eval-dataset-validation.json`
    with `ok=true`, `records=1`, `valid_records=1`, `invalid_records=0`,
    `rejected_records=0`, `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This validates
    the queue only for future held-out eval conversion; it is not a training
    dataset, does not save to GitHub, and does not approve public XRIQ work.
    GitHub remained skipped because `github_configured=false`.
  - The `22566dc` repair-chain eval-dataset export checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain eval-dataset
    export slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `116 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T201304Z-66068`, verified
    `export-ready-repair-chain-eval-dataset` against the eval-dataset decision
    JSONL queue, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T201304Z-66068/agent-client-mvp-loop-ready-repair-chain-eval-dataset.jsonl`
    with `records=1`, `eval_dataset_records=1`, `eval_dataset_ready=true`,
    `requires_eval_dataset_validation=true`, `safe_to_train=false`,
    `training_allowed=false`, `github_save_ready=false`, and
    `approved_for_training=false`. This is a validation-only eval-dataset
    queue; it is not a training dataset, does not save to GitHub, and does not
    approve public XRIQ work. GitHub remained skipped because
    `github_configured=false`.
  - The `f600ab0` repair-chain eval-dataset decision review checkpoint required
    no service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain eval-dataset
    decision review slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `115 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T195912Z-65843`, verified
    `review-ready-repair-chain-eval-dataset-decisions` against the
    eval-dataset decision JSONL queue, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T195912Z-65843/agent-client-mvp-loop-ready-repair-chain-eval-dataset-decision-review.json`
    with `records=1`, `decision_counts={"approve_for_eval_dataset": 1}`,
    `approved_for_eval_dataset_records=1`, `eval_dataset_ready_records=1`,
    `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This remains
    a final pre-export review artifact; it does not make the record
    training-ready, save to GitHub, or approve public XRIQ work. GitHub
    remained skipped because `github_configured=false`.
  - The `bb6fdc0` repair-chain eval-dataset decision checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain eval-dataset
    decision slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `114 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T171410Z-65610`, verified
    `record-ready-repair-chain-eval-candidate-decision` against the
    eval-candidate JSONL queue, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T171410Z-65610/agent-client-mvp-loop-ready-repair-chain-eval-dataset-decisions.jsonl`
    with `records=1`, `decision=approve_for_eval_dataset`,
    `approved_for_eval_dataset_records=1`, `eval_dataset_ready=true`,
    `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This marks
    only eval-dataset readiness; it does not make the record training-ready,
    save to GitHub, or approve public XRIQ work. GitHub remained skipped
    because `github_configured=false`.
  - The `4d4ddca` repair-chain eval-candidate review checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain eval-candidate
    review slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `113 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T170912Z-65387`, verified
    `review-ready-repair-chain-eval-candidates` against the eval-candidate
    JSONL queue, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T170912Z-65387/agent-client-mvp-loop-ready-repair-chain-eval-candidate-review.json`
    with `records=1`, `ready_for_dataset_review=1`,
    `eval_dataset_ready=false`, `requires_dataset_review=true`,
    `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This remains
    an eval-candidate review artifact only; it does not create training data,
    save to GitHub, or approve public XRIQ work. GitHub remained skipped
    because `github_configured=false`.
  - The `415af7a` repair-chain eval-candidate export checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER repair-chain eval-candidate
    export slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `112 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T170513Z-65165`, verified
    `export-ready-repair-chain-eval-candidates` against a synthetic
    `approve_for_eval` decision JSONL, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T170513Z-65165/agent-client-mvp-loop-ready-repair-chain-eval-candidates.jsonl`
    with `records=1`, `eval_candidates=1`, `eval_dataset_ready=false`,
    `requires_dataset_review=true`, `safe_to_train=false`,
    `training_allowed=false`, `github_save_ready=false`, and
    `approved_for_training=false`. This remains an eval-candidate artifact
    only; it does not create training data, save to GitHub, or approve public
    XRIQ work. GitHub remained skipped because `github_configured=false`.
  - The `6566caf` ready repair-chain decision review checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER ready repair-chain decision
    review slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `111 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T165150Z-64945`, verified
    `review-ready-repair-chain-decisions` against the deferred decision JSONL,
    and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T165150Z-64945/agent-client-mvp-loop-ready-repair-chain-decision-review.json`
    with `records=1`, `decision_counts={"defer": 1}`,
    `approved_for_eval_records=0`, `safe_to_train=false`,
    `training_allowed=false`, `github_save_ready=false`, and
    `approved_for_training=false`. This remains a decision-summary artifact
    only; it does not create training data, save to GitHub, or approve public
    XRIQ work. GitHub remained skipped because `github_configured=false`.
  - The `dc76ae6` ready repair-chain decision recording checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER ready repair-chain decision
    recording slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `110 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T164604Z-64726`, verified
    `record-ready-repair-chain-decision` against the ready repair-chain JSONL
    queue, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T164604Z-64726/agent-client-mvp-loop-ready-repair-chain-decisions.jsonl`
    with `records=1`, `decision=defer`, `reviewer=biber-smoke`,
    `safe_to_train=false`, `training_allowed=false`,
    `github_save_ready=false`, and `approved_for_training=false`. This smoke
    decision is synthetic and not a human approval; it only proves that future
    sessions can record manual review decisions without automatic training or
    GitHub save promotion. GitHub remained skipped because
    `github_configured=false`.
  - The `6c90400` ready repair-chain review summary checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER ready repair-chain review
    summary slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `109 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T161711Z-64509`, verified
    `review-ready-repair-chains` against the ready repair-chain JSONL queue,
    and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T161711Z-64509/agent-client-mvp-loop-ready-repair-chain-review.json`
    with `records=1`, `ready_for_human_review=1`,
    `safe_to_train=false`, `training_allowed=false`, and
    `github_save_ready=false`. This remains a human-review summary only; it
    does not automatically create training data or save to GitHub. GitHub
    remained skipped because `github_configured=false`.
  - The `559c30d` ready repair-chain review export checkpoint required no
    service restart because it changed only the stdlib agent client, smoke
    script, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER ready repair-chain review
    export slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `108 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T161330Z-64290`, verified
    `export-ready-repair-chains` against the saved repair-chain summary, and
    wrote
    `/workspace/outputs/biber-agent-smoke-20260519T161330Z-64290/agent-client-mvp-loop-ready-repair-chains.jsonl`
    with `records=1`, `review_status=needs_human_review`,
    `safe_to_train=false`, `training_allowed=false`, and
    `github_save_ready=false`. This remains a human-review queue only; it does
    not automatically create training data or save to GitHub. GitHub remained
    skipped because `github_configured=false`.
  - The `a4799fe` repair-chain artifact listing checkpoint required no service
    restart because it changed only the stdlib agent client, smoke script, and
    tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER repair-chain artifact
    listing slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `107 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T154519Z-64075`, verified
    `show-repair-chain` and then `list-repair-chains --ready-only` against the
    saved smoke artifact directory, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T154519Z-64075/agent-client-mvp-loop-repair-chain-list.json`
    with `matched=1`, `ready_for_human_review=1`,
    `safe_to_train=false`, and `training_allowed=false`. GitHub remained
    skipped because `github_configured=false`.
  - The `6af885c` repair-chain summary checkpoint required no service restart
    because it changed only the stdlib agent client, smoke script, and tests.
    vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER repair-chain summary slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `106 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T153550Z-63861`, verified
    `show-repair-chain` across the saved `mvp-loop`, repair request, repair
    attempt, extraction, plan, approved apply, verification, verified-repair
    JSONL, and verified-repair review summary artifacts, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T153550Z-63861/agent-client-mvp-loop-repair-chain.json`
    with `chain_status=ready_for_human_review`,
    `ready_for_human_review=true`, `safe_to_train=false`,
    `training_allowed=false`, and `github_save_ready=false`. GitHub remained
    skipped because `github_configured=false`.
  - The `caabb32` verified repair review summary checkpoint required no service
    restart because it changed only the stdlib agent client, smoke script, docs,
    and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER verified repair review
    summary slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `105 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T152710Z-63638`, verified
    `review-verified-repairs` against the verified repair JSONL queue, and
    wrote
    `/workspace/outputs/biber-agent-smoke-20260519T152710Z-63638/agent-client-mvp-loop-verified-repair-review.json`
    with `records=1`, `ready_for_human_review=1`, and no training eligibility.
    GitHub remained skipped because `github_configured=false`.
  - The `9b22ef5` verified repair review export checkpoint required no service
    restart because it changed only the stdlib agent client, smoke script, docs,
    and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER verified repair review export
    slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `104 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T150125Z-63413`, verified
    `export-verified-repair` against a passed repair verification artifact, and
    wrote
    `/workspace/outputs/biber-agent-smoke-20260519T150125Z-63413/agent-client-mvp-loop-verified-repairs.jsonl`
    with `records=1`, `review_status=needs_human_review`,
    `eligible_for_training=false`, and `training_allowed=false`. This remains a
    human-review queue only; it does not automatically create training data.
    GitHub remained skipped because `github_configured=false`.
  - The `2ae4a02` repair-test verification checkpoint required no service
    restart because it changed only the stdlib agent client, smoke script, docs,
    and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER agent-client repair-test
    verification slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `102 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T145414Z-63192`, verified
    `verify-repair-edits` against a successful approved repair-apply artifact,
    and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T145414Z-63192/agent-client-mvp-loop-repair-test-verification.json`
    with `verification_status=passed`, `test_id=python-compileall-api`,
    `auto_saved=false`, `auto_applied=false`, `training_allowed=false`, and
    plan hash `8d220a3cf404617be8969816ee880bca8d56437b0482d812195a0180ae66a83d`.
    GitHub remained skipped because `github_configured=false`.
  - The `cfed893` guarded repair-edit apply checkpoint required no service
    restart because it changed only the stdlib agent client, smoke script, docs,
    and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER agent-client guarded
    repair-edit apply slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `99 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T141424Z-62970`, verified
    `apply-repair-edits` against a successful repair-edit plan artifact, and
    wrote
    `/workspace/outputs/biber-agent-smoke-20260519T141424Z-62970/agent-client-mvp-loop-repair-edit-apply.json`
    with `apply_status=applied`, `approval_received=true`,
    `auto_applied=false`, `training_allowed=false`, and plan hash
    `e638fa0067bdc412c4040475ea016ad4ee1cb164708ac43534a7877da3333983`.
    The command still refuses to apply without `--approve`, and the smoke
    applied only to its temporary `.biber-runtime` file. GitHub remained
    skipped because `github_configured=false`.
  - The `4c7aea5` repair-edit planning checkpoint required no service restart
    because it changed only the stdlib agent client, smoke script, docs, and
    tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER agent-client repair-edit
    planning slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `96 passed`, live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`,
    and `bash scripts/vast_status_direct.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T135934Z-62752`, verified
    `plan-repair-edits` against the extracted repair payload, and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T135934Z-62752/agent-client-mvp-loop-repair-edit-plan.json`
    with `plan_status=planned`, `apply_allowed=false`,
    `auto_applied=false`, `training_allowed=false`, and plan hash
    `591500a09ec4d9972d2f10f019252086ba93e37ecc67b80c906d3293fff3f0a3`.
    The smoke also verified the planning step did not mutate the target file.
    GitHub remained skipped because `github_configured=false`.
  - The `da92ebf` and `c9ec3d7` repair-edit extraction checkpoints required no
    service restart because they changed only the stdlib agent client, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client repair-edit
    extraction slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `94 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T135041Z-62571`, verified
    `extract-repair-edits` against a deterministic repair-attempt artifact,
    wrote
    `/workspace/outputs/biber-agent-smoke-20260519T135041Z-62571/agent-client-mvp-loop-repair-edit-extraction.json`
    with `extraction_status=ready_for_plan_edit`, `ok=true`,
    `apply_allowed=false`, `training_allowed=false`, and `edits=1`, and wrote
    the plan-edit payload to
    `/workspace/outputs/biber-agent-smoke-20260519T135041Z-62571/agent-client-mvp-loop-repair-edits.json`.
    GitHub remained skipped because `github_configured=false`.
  - The `fe2bb50` and `8b2d200` repair-attempt checkpoints required no service
    restart because they changed only the stdlib agent client, smoke script,
    docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client local-model
    repair-attempt slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `91 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS=96 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T134305Z-62329`, verified
    `prepare-repair`, then verified the new `attempt-repair` command called
    the local model through `/v1/chat` with mentor disabled and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T134305Z-62329/agent-client-mvp-loop-repair-attempt.json`
    with `repair_status=model_repair_proposed`, `training_allowed=false`,
    `auto_applied=false`, `mentor_used=false`, and `model=biber-dev-core-v1`.
    The model response produced an inspectable edit-style repair proposal, but
    no file edits were automatically applied. GitHub remained skipped because
    `github_configured=false`.
  - The `2e7a405` repair-request helper checkpoint required no service restart
    because it changed only the stdlib agent client, smoke script, docs, and
    tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER agent-client repair-request
    helper slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `89 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T131740Z-62026`, verified the
    new `prepare-repair` command against a synthetic failed MVP-loop artifact,
    and wrote
    `/workspace/outputs/biber-agent-smoke-20260519T131740Z-62026/agent-client-mvp-loop-repair-output.json`
    with `repair_status=ready_for_local_model`, `training_allowed=false`,
    `test_id=dotnet-test`, and `selected_context_paths=2`. GitHub remained
    skipped because `github_configured=false`.
  - The Rust/XRIQ codegen-profile checkpoints through `7e7b8d` required no
    service restart because they changed only eval prompt/profile files,
    tests, docs, and wrappers. vLLM stayed on pid `5802`; FastAPI stayed on
    pid `53902`.
  - Latest focused Vast verification for the Rust/XRIQ codegen-profile slice:
    `/workspace/biber-venv/bin/python -m compileall training tests scripts`,
    `bash -n scripts/vast_eval_rust_xriq_direct.sh`, focused pytest
    `tests/test_live_model_eval.py tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_plan.py -q`
    with `18 passed`, and live
    `BIBER_EVAL_FAIL_ON_VALIDATORS=0 bash scripts/vast_eval_rust_xriq_direct.sh`.
    The final focused Rust/XRIQ eval wrote
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260519T125323Z.summary.json`
    and reached `7/7` responses, `7/7` expectation checks, and `7/7` cargo
    validators. The broad LoRA regression eval wrote
    `/workspace/outputs/evals/biber-dev-core-lora-20260519T125356Z.summary.json`
    and remained `18/18`. No OpenAI mentor call, credential rotation, service
    restart, or additional GPU training was used for this checkpoint.
  - After pushing the handoff checkpoint `ff558f6`, Vast was fast-forwarded and
    `bash scripts/vast_status_direct.sh` confirmed API health, vLLM pid `5802`,
    FastAPI pid `53902`, loopback binds, and served LoRA module
    `biber-dev-core=/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - The `ef0cd5e` MVP-loop failure export checkpoint required no service
    restart because it changed only the stdlib client helper, smoke script,
    docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER agent-client MVP-loop
    failure export slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `87 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T122946Z-55946`, created a
    stdlib-client session `07a46b36-06d7-4cfd-95dd-cf3fb8ba9569`, created an
    XRIQ-context session `dd5460af-165b-47c4-8d88-71cdcf06c863`, verified
    `mvp-loop --output` wrote
    `/workspace/outputs/biber-agent-smoke-20260519T122946Z-55946/agent-client-mvp-loop-output.json`,
    and verified `export-mvp-failures` wrote
    `/workspace/outputs/biber-agent-smoke-20260519T122946Z-55946/agent-client-mvp-loop-failures.jsonl`
    with `records=0` and `training_allowed=false` for the successful smoke
    run. GitHub remained skipped because `github_configured=false`.
  - The `be89b78` failed MVP-loop artifact filter checkpoint required no
    service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client failed
    MVP-loop artifact filter slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `86 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T121958Z-55732`, created a
    stdlib-client session `51a6bf1c-9061-4bb2-a43a-c33c2a272340`, created an
    XRIQ-context session `aed7a24a-06f6-4ab4-b7c7-8d34c78bf68b`, verified
    `mvp-loop --output` wrote
    `/workspace/outputs/biber-agent-smoke-20260519T121958Z-55732/agent-client-mvp-loop-output.json`,
    verified `list-mvp-loops` found one saved artifact, and verified
    `list-mvp-loops --failed-only` returned zero artifacts for the successful
    smoke run. GitHub remained skipped because `github_configured=false`.
  - The `841dc8f` agent-client MVP-loop artifact listing checkpoint required
    no service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client MVP-loop
    artifact listing slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `85 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T121101Z-55516`, created a
    stdlib-client session `e7460d64-1792-483f-9bca-50173004bab5`, created an
    XRIQ-context session `dc496301-ebc8-4ce8-92af-11a95f76cc01`, verified
    `mvp-loop --output` wrote
    `/workspace/outputs/biber-agent-smoke-20260519T121101Z-55516/agent-client-mvp-loop-output.json`,
    verified `show-mvp-loop` rendered a local report for that saved artifact,
    and verified `list-mvp-loops` found the saved artifact with
    `agent_client_mvp_loop_list_count=1`. GitHub remained skipped because
    `github_configured=false`.
  - The `8c077d2` agent-client MVP-loop artifact viewer checkpoint required no
    service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client MVP-loop
    artifact viewer slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `83 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T115726Z-55304`, created a
    stdlib-client session `e9304e94-800c-4ed1-9459-718a855c2dc1`, created an
    XRIQ-context session `5638d378-4ae0-426b-9fd2-082e2394d3ba`, verified
    `mvp-loop --output` wrote
    `/workspace/outputs/biber-agent-smoke-20260519T115726Z-55304/agent-client-mvp-loop-output.json`,
    and verified `show-mvp-loop` rendered a local report for that saved
    artifact. GitHub remained skipped because `github_configured=false`.
  - The `38e3701` agent-client MVP-loop artifact checkpoint required no
    service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client MVP-loop
    artifact slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `81 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T115229Z-55093`, created a
    stdlib-client session `bb20bd63-1cc7-45c2-a706-b92ec4fc883d`, created an
    XRIQ-context session `10474bbb-bf9b-4a5c-b0be-7a86c7816c54`, verified
    `mvp-loop --output` wrote
    `/workspace/outputs/biber-agent-smoke-20260519T115229Z-55093/agent-client-mvp-loop-output.json`,
    and confirmed that JSON matched stdout while preserving context planning,
    hash-gated temporary edit apply, and `python-compileall-api` execution.
    GitHub remained skipped because `github_configured=false`.
  - The `1ce9f60` agent-client MVP-loop command checkpoint required no service
    restart because it changed only the stdlib client helper, smoke script,
    docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER agent-client MVP-loop
    command slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `81 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T113714Z-54934`, created a
    stdlib-client session `f145e3cb-bbf4-42f6-8deb-5a38090aeb08`, created an
    XRIQ-context session `69b38c1c-2b79-46c0-856c-df8cfa9ffa2f`, verified
    `mvp-loop` through context planning, hash-gated temporary edit apply, and
    `python-compileall-api` test execution, then removed the temporary loop
    smoke file. GitHub remained skipped because `github_configured=false`.
  - The `a3ba952` agent-client GitHub workflow command checkpoint required no
    service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client GitHub workflow
    command slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `79 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T111822Z-54777`, created a
    stdlib-client session `a341fcf1-1402-41d6-a90b-f89203150590`, created an
    XRIQ-context session `bb4844af-6db9-4d43-a21b-f577c8847b54`, kept GitHub
    save/PR skipped because `github_configured=false`, and kept the BIBER API
    private/local.
  - The `b0d1df6` agent-client test/diagnosis command checkpoint required no
    service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client test/diagnosis
    command slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `67 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T111231Z-54617`, created a
    stdlib-client session `0f1873b5-631c-4353-8dab-dfd6a89134aa`, created an
    XRIQ-context session `d93e5d5a-5482-47ce-b628-c99cf3e7b88f`, confirmed the
    stdlib client can list tests, run `python-compileall-api` with `ok=true`,
    and classify synthetic `.NET` output as `compile_error` on stack `dotnet`.
  - The `12450e2` agent-client workspace-edit command checkpoint required no
    service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client workspace-edit
    command slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_workspace_edit.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_repo_context.py -q`
    with `49 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T110521Z-54464`, created a
    stdlib-client session `ea849ac2-627c-4bb4-9547-185bf7b554b2`, created an
    XRIQ-context session `f03f2123-2fa0-4cb7-b16a-e8e5d3c21d2a`, confirmed
    `plan-context` selected `README.md`, `docs/API_EXAMPLES.md`,
    `pyproject.toml`, `xriq/Cargo.lock`, and `xriq/Cargo.toml`, and verified
    `plan-edit`/`apply-edit` through a temporary smoke path
    `.biber-runtime/agent-client-edit-smoke-20260519T110521Z-54464.txt` with
    plan hash
    `f3204a5f2d64818d3cc416b4b2c61884b4244199aa656a8f0d0f7ddc777161ec`.
  - The `775b278` agent-client repo-context planning checkpoint required no
    service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client repo-context
    planning slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_repo_context.py -q`
    with `30 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T105117Z-54319`, created a
    stdlib-client session `a8f0e071-16ed-4536-83cd-1d249e51491d`, listed and
    loaded it through the stdlib client, and confirmed `plan-context` selected
    `README.md`, `docs/API_EXAMPLES.md`, `pyproject.toml`,
    `xriq/Cargo.lock`, and `xriq/Cargo.toml`.
  - The `b8abdfb` agent-client session-history command checkpoint required no
    service restart because it changed only the stdlib client helper, smoke
    script, docs, and tests. vLLM stayed on pid `5802`; FastAPI stayed on pid
    `53902`.
  - Latest focused Vast verification for the BIBER agent-client
    session-history command slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_agent_session.py tests/test_agent_capabilities.py -q`
    with `16 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T101616Z-54180`, created a
    stdlib-client session `3c113f71-e5ab-4ea4-8506-766dfc43a638`, listed it
    through `list-sessions`, loaded it through `get-session`, and created an
    XRIQ-context session `c107be8f-5d8d-495c-ac3b-8fe4d056266a` with
    `xriq_context` then `chat`.
  - The `6317641` agent-client create-session smoke checkpoint required no
    service restart because it changed only the smoke script, docs, and tests.
    vLLM stayed on pid `5802`; FastAPI stayed on pid `53902`.
  - Latest focused Vast verification for the BIBER agent-client
    create-session smoke slice:
    `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_agent_session.py tests/test_agent_capabilities.py -q`
    with `13 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
    The live smoke wrote artifacts under
    `/workspace/outputs/biber-agent-smoke-20260519T100959Z-54048`, created a
    stdlib-client session `9b57e6a5-07da-458c-803a-702db6577d32` with `chat`
    step only, and created an XRIQ-context session
    `562987a8-6003-4f21-b839-42ebefe28d2d` with `xriq_context` then `chat`.
  - The `68479ad` repo-adaptation failure-review checkpoint required a
    FastAPI-only restart because the `pytest-core` allowlist changed. vLLM
    stayed on pid `5802`; FastAPI moved from pid `53552` to pid `53902`.
  - Latest focused Vast verification for the BIBER repo-adaptation
    failure-review slice:
    `/workspace/biber-venv/bin/python -m compileall training tests app src`,
    focused pytest
    `tests/test_repo_adaptation_failure_review.py tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_plan.py tests/test_agent_capabilities.py -q`
    with `13 passed`, and a live review smoke against
    `/workspace/outputs/evals/repo-adaptation-smoke.failures.jsonl`.
    The smoke wrote
    `/workspace/outputs/evals/repo-adaptation-smoke.review.json` and
    `/workspace/outputs/evals/repo-adaptation-smoke.training-candidates.jsonl`
    with `quality=needs_review` and empty `output`, so it remains a review
    item rather than trainable data.
  - The `81b9dd5` repo-adaptation live-eval wrapper checkpoint required a
    FastAPI-only restart because the `pytest-core` allowlist changed. vLLM
    stayed on pid `5802`; FastAPI moved from pid `53128` to pid `53552`.
  - Latest focused Vast verification for the BIBER repo-adaptation live-eval
    wrapper slice:
    `/workspace/biber-venv/bin/python -m compileall training tests app src`,
    focused pytest
    `tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_plan.py tests/test_live_model_eval.py tests/test_agent_capabilities.py -q`
    with `17 passed`, `bash -n scripts/vast_eval_repo_adaptation_direct.sh`,
    and a live one-prompt smoke through `scripts/vast_eval_repo_adaptation_direct.sh`.
    The smoke produced a model response and wrote
    `/workspace/outputs/evals/repo-adaptation-smoke.jsonl`,
    `/workspace/outputs/evals/repo-adaptation-smoke.summary.json`, and
    `/workspace/outputs/evals/repo-adaptation-smoke.failures.jsonl`.
    The one generated smoke prompt had `expectation_ok=0/1`, which is useful
    repo-adaptation signal rather than a wrapper failure.
  - The `79aad96` hash-gated workspace edit-apply checkpoint required a
    FastAPI-only restart because it added `POST /v1/files/edit/apply`, added
    `plan_hash` to edit plans, and expanded agent-capability metadata. vLLM
    stayed on pid `5802`; FastAPI moved from pid `52785` to pid `53128`.
  - Latest focused Vast verification for the BIBER hash-gated workspace
    edit-apply slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_workspace_edit.py tests/test_agent_capabilities.py -q`
    with `16 passed`, and a live authenticated plan/apply smoke that wrote and
    then cleaned up `.biber-runtime/workspace-edit-apply-smoke.txt`.
  - The `6050bd0` repo-context stack-profile checkpoint required a
    FastAPI-only restart because `POST /v1/repo/context/plan` and
    `GET /v1/agent/capabilities` now return stack-profile metadata. vLLM
    stayed on pid `5802`; FastAPI moved from pid `52412` to pid `52785`.
  - Latest focused Vast verification for the BIBER repo-context stack-profile
    slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_repo_context.py tests/test_agent_capabilities.py -q`
    with `13 passed`, a live authenticated `GET /v1/agent/capabilities` smoke
    listing `dotnet,java` repo-context profiles, and a live authenticated
    `POST /v1/repo/context/plan` smoke confirming `stack_profiles` is present.
  - The `c5f7235` `.NET`/Java test-command checkpoint required a FastAPI-only
    restart because the `/v1/tests` allowlist and agent-capability metadata
    changed. vLLM stayed on pid `5802`; FastAPI moved from pid `51901` to
    pid `52412`.
  - Latest focused Vast verification for the BIBER `.NET`/Java stack
    test-command slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_test_runner.py tests/test_agent_capabilities.py -q`
    with `9 passed`, and a live authenticated `GET /v1/tests` smoke listing
    `dotnet-test`, `maven-test`, `gradle-test`, and `gradle-wrapper-test`.
  - The `3069a50` agent-session test-diagnosis checkpoint required a
    FastAPI-only restart because tracked agent sessions now attach diagnosis
    output to failed or timed-out test steps. vLLM stayed on pid `5802`;
    FastAPI moved from pid `51639` to pid `51901`.
  - Latest focused Vast verification for the BIBER agent-session
    test-diagnosis slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_agent_session.py tests/test_test_diagnosis.py -q` with
    `11 passed`, and final Vast status confirmed API health on pid `51901`.
  - The `1fd510f` test-failure diagnosis checkpoint required a FastAPI-only
    restart because it added `POST /v1/tests/diagnose`, expanded
    `GET /v1/agent/capabilities`, and updated the `pytest-core` allowlist.
    vLLM stayed on pid `5802`; FastAPI moved from pid `51376` to pid `51639`.
  - Latest focused Vast verification for the BIBER test-failure diagnosis
    slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_test_diagnosis.py tests/test_agent_capabilities.py -q`
    with `8 passed`, and a live authenticated `POST /v1/tests/diagnose` smoke
    classifying a `.NET` `CS1002` compiler error as `compile_error`.
  - The `70e6320` multi-file edit planner checkpoint required a FastAPI-only
    restart because it added `POST /v1/files/edit/plan` and expanded
    `GET /v1/agent/capabilities`. vLLM stayed on pid `5802`; FastAPI moved
    from pid `51098` to pid `51376`.
  - Latest focused Vast verification for the BIBER multi-file edit planner
    slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_workspace_edit.py tests/test_agent_capabilities.py -q`
    with `12 passed`, a live authenticated `POST /v1/files/edit/plan` smoke,
    and a follow-up check confirming the planned create file was not written.
  - The `1cc790a` repo-context planner checkpoint required a FastAPI-only
    restart because it added `POST /v1/repo/context/plan` and expanded
    `GET /v1/agent/capabilities`. vLLM stayed on pid `5802`; FastAPI moved
    from pid `50843` to pid `51098`.
  - Latest focused Vast verification for the BIBER repo-context planner slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_repo_context.py tests/test_agent_capabilities.py -q`
    with `12 passed`, and a live authenticated
    `POST /v1/repo/context/plan` smoke selecting
    `docs/API_EXAMPLES.md`, `src/biber_api/repo_context.py`,
    `tests/test_repo_context.py`, `pyproject.toml`, `xriq/Cargo.lock`, and
    `xriq/Cargo.toml`.
  - The `2efa65b` repo-adaptation checkpoint required a FastAPI-only restart
    because it also updated the `pytest-core` allowlist served by the API.
    vLLM stayed on pid `5802`; FastAPI moved from pid `50453` to pid `50843`.
  - Latest focused Vast verification for the BIBER repo-adaptation slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts training`,
    focused pytest
    `tests/test_repo_adaptation_plan.py tests/test_training_dataset.py -q`
    with `7 passed`, and a real plan smoke writing
    `/workspace/outputs/repo-adaptation-plan-smoke.json` plus
    `/workspace/outputs/repo-adaptation-eval-smoke.jsonl`.
  - The `51ad833` agent-client helper checkpoint required a FastAPI-only
    restart because it also updated the `pytest-core` allowlist served by the
    API. vLLM stayed on pid `5802`; FastAPI moved from pid `50105` to
    pid `50453`.
  - Latest focused Vast verification for the BIBER agent-client helper slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, and focused pytest covering
    `test_biber_agent_client.py`, `test_agent_capabilities.py`, and
    `test_agent_session.py` with `11 passed`.
  - The `8a539de` agent-capabilities checkpoint required a FastAPI-only
    restart. vLLM stayed on pid `5802`; FastAPI moved from pid `49733` to
    pid `50105`.
  - Latest focused Vast verification for the BIBER agent-capabilities slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, and focused pytest covering
    `test_agent_capabilities.py`, `test_agent_session.py`, and
    `test_xriq_preflight_api.py` with `25 passed`.
  - The `e4df1d0` agent-session XRIQ-context checkpoint required a FastAPI-only
    restart. vLLM stayed on pid `5802`; FastAPI moved from pid `48095` to
    pid `49733`.
  - Latest focused Vast verification for the BIBER agent-session XRIQ-context
    slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, and focused pytest covering
    `test_agent_session.py` and `test_xriq_preflight_api.py` with `23 passed`.
  - The `4af1ee5` dashboard account-lookup checkpoint required no service
    restart. vLLM stayed on pid `5802`; FastAPI stayed on pid `48095`.
  - Latest focused Vast verification for the BIBER/XRIQ dashboard account
    lookup:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest covering
    `test_xriq_preflight_api.py`, `test_xriq_private_devnet_client.py`, and
    `test_xriq_dashboard.py` with `26 passed`.
  - The `0e7975c` dashboard transaction-lookup checkpoint required no service
    restart. vLLM stayed on pid `5802`; FastAPI stayed on pid `48095`.
  - Latest focused Vast verification for the BIBER/XRIQ dashboard transaction
    lookup:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest covering
    `test_xriq_preflight_api.py`, `test_xriq_private_devnet_client.py`, and
    `test_xriq_dashboard.py` with `26 passed`.
  - The `f5f55a4` dashboard preflight-action checkpoint required no service
    restart. vLLM stayed on pid `5802`; FastAPI stayed on pid `48095`.
  - Latest focused Vast verification for the BIBER/XRIQ dashboard preflight
    action:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest covering
    `test_xriq_preflight_api.py`, `test_xriq_private_devnet_client.py`, and
    `test_xriq_dashboard.py` with `26 passed`.
  - The `afa080b` dashboard checkpoint required a FastAPI-only restart.
    vLLM stayed on pid `5802`; FastAPI moved from pid `47248` to pid `48095`.
  - Latest focused Vast verification for the BIBER/XRIQ dashboard slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest covering
    `test_xriq_preflight_api.py`, `test_xriq_private_devnet_client.py`, and
    `test_xriq_dashboard.py` with `26 passed`.
  - Browser dashboard route is live at:
    `http://127.0.0.1:8000/xriq/private-devnet/dashboard` when connected
    through the SSH tunnel. It is same-origin with the API and stores the typed
    API key only in browser `sessionStorage`.
  - The `2bb7ca0` client/docs/test checkpoint required no service restart;
    vLLM stayed on pid `5802` and FastAPI stayed on pid `47248`.
  - Latest focused Vast verification for the BIBER/XRIQ API client slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and
    `pytest tests/test_xriq_preflight_api.py tests/test_xriq_private_devnet_client.py -q`
    with `24 passed`.
  - Latest BIBER test-runner smoke:
    authenticated `GET /v1/tests` now returns the stack-oriented
    `dotnet-test`, `maven-test`, `gradle-test`, and `gradle-wrapper-test`
    commands. Earlier `POST /v1/tests/run` with
    `test_id=python-compileall-api` returned `200 OK`, `executed=true`, and
    `ok=true`.
  - Latest BIBER workspace-edit smoke:
    `POST /v1/files/edit` with `create_if_missing=true` and `dry_run=true`
    returned `200 OK`, `created=true`, `changed=true`, and did not write a
    file.
  - Latest BIBER GitHub PR workflow smoke:
    `POST /v1/github/pull-request` returned the expected `503` with
    `GitHub saving is not configured` because live GitHub credentials are still
    intentionally not configured on Vast.
  - Latest BIBER end-to-end agent smoke:
    `bash scripts/vast_biber_agent_smoke.sh` passed with repo-context chat,
    agent-capabilities discovery, workspace-edit dry-run,
    `python-compileall-api`, opt-in XRIQ private-devnet context in a tracked
    agent session, and GitHub skipped because it is not configured. Latest
    artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T000619Z-50478`.
    Latest capability presets were `default_coding_session` and
    `xriq_private_devnet_review`. The smoke also validated the new
    `scripts/biber_agent_client.py capabilities --json` path and wrote
    `agent-client-capabilities.json`.
    Latest XRIQ-context session id:
    `36c0098f-d4a6-4674-9e58-88925bfb3d31`; step order was
    `xriq_context`, then `chat`; context height was `2`; mentor was not used.
  - Latest BIBER agent-session smoke:
    `POST /v1/agent/sessions` returned `200 OK` with steps `chat`,
    `workspace_edit`, and `test_run`; `model=biber-dev-core-v1`,
    `mentor_used=false`, workspace edit was dry-run only, and
    `python-compileall-api` returned `ok=true`. The persisted artifact was
    `/workspace/outputs/agent-sessions/af658dd2-44b6-4800-bd87-561b7424c17c.json`.
    `GET /v1/agent/sessions?limit=5` included the new session, and
    `GET /v1/agent/sessions/af658dd2-44b6-4800-bd87-561b7424c17c` returned
    the same persisted session.
  - Latest endpoint smoke:
    `POST /v1/xriq/private-devnet/preflight-transfer`,
    `GET /v1/xriq/private-devnet/status`,
    `GET /v1/xriq/private-devnet/accounts/xriqdev1alice00000000000`, and
    `GET /v1/xriq/private-devnet/transactions/{hash}` returned `200 OK`.
    Latest live mempool smoke also confirmed
    `GET /v1/xriq/private-devnet/mempool` returns `200 OK` with
    `command=mempool-detail` and current `pending_count=0`.
    Latest live explorer/block smoke confirmed
    `GET /v1/xriq/private-devnet/explorer?limit=5` returns
    `command=explorer-overview` with `current_height=2`, and
    `GET /v1/xriq/private-devnet/blocks/1` returns `command=block-detail`
    with `height=1`.
    Latest consolidated API smoke with `bash scripts/vast_xriq_api_smoke.sh`
    passed with status/explorer height `2`, block height `2`, Alice account
    detail, mempool pending count `0`, `POST
    /v1/xriq/private-devnet/snapshots/export`, `POST
    /v1/xriq/private-devnet/snapshots/import` to the safe staging target,
    `GET /v1/xriq/private-devnet/snapshots?limit=10`, `GET
    /v1/xriq/private-devnet/snapshots/{snapshot_name}`, snapshot height `2`,
    `GET /v1/xriq/private-devnet/overview?explorer_limit=5&snapshot_limit=10`,
    snapshot list count `8`, overview snapshot count `8`, state root
    `578bdd2affeece78c7949d34da08391c797b363b045c3cff6c999868e0baa2d6`,
    transaction hash
    `e1dadff3325ac720c71bfa8c900ed15e2637dbb041848f0fdfe35dbfbbb94e1d`
    sourced from the latest block, transaction detail status `confirmed`, and
    the minimal stdlib client commands for overview, snapshot list, and
    snapshot detail. The smoke also fetched
    `GET /xriq/private-devnet/dashboard` and verified the dashboard marker,
    preflight-transfer endpoint marker, and `transferForm` marker without
    submitting a transaction. It also verified the dashboard transaction-detail
    endpoint marker, `transactionLookupForm` marker, dashboard account-detail
    endpoint marker, and `accountLookupForm` marker.
    Latest smoke artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T233249Z-49206`. Client
    artifacts inside that directory:
    `client-overview.txt`, `client-snapshots.txt`, and
    `client-snapshot-detail.txt`. Dashboard artifact:
    `dashboard.html`.
    The earlier read smoke confirmed `transaction_status=confirmed` and status
    `current_height=2` for the test chain used in that smoke.
  - Latest XRIQ private-devnet CLI smoke:
    `bash scripts/xriq_private_devnet_smoke.sh` passed after adding
    snapshot export/import coverage. Artifact:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260518T203806Z-44845`.
    It includes `snapshot/`, `snapshot-export.json`,
    `snapshot-import-chain.bin`, and `snapshot-import.json`.
  - Last full chat smoke remains `bash scripts/vast_test_direct.sh` with chat
    content `ok` before the FastAPI-only restart; vLLM remained running.
- Latest current Rust/XRIQ eval:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260519T125323Z.summary.json`
  - result: `7/7` responses, `7/7` substring expectations,
    `7/7` cargo validators.
  - profile: `training/rust_xriq_codegen_profile.txt` is applied only to
    `rust_xriq_apply_ledger_transaction` by default through
    `scripts/vast_eval_rust_xriq_direct.sh`.
  - improvement path: the profile moved the ledger prompt through rustfmt,
    no-external-crate, borrow-checker, no-cloned-map, and fee-semantics
    failures until the final live eval passed all cargo validators. Keep this
    as an inference/eval profile first; do not start another QLoRA run unless a
    future repeatable gap remains after profile plus deterministic repair-loop
    options are exhausted.
- Latest current broad eval:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260519T125356Z.summary.json`
  - result: `18/18` responses and `18/18` simple expectation checks.
- Current canonical training dataset:
  - path: `/workspace/data/biber_train.jsonl`
  - candidate source:
    `/workspace/data/biber_train_rust_xriq_fee_codeinstruct_1000.jsonl`
  - records: `1000`
  - mix: `2` smoke, `27` Python/API targeted, `21` Rust/XRIQ targeted,
    `3` Rust/XRIQ validation-regression, `2` Rust/XRIQ ledger-regression,
    `2` Rust/XRIQ fee-regression, and `943` CodeInstruct records.
  - provenance:
    `/workspace/outputs/dataset-provenance-rust-xriq-fee-codeinstruct-1000.json`
  - validation:
    `/workspace/outputs/internet-dataset-validation-rust-xriq-fee-codeinstruct-1000.json`
    and `/workspace/outputs/dataset-validation-rust-xriq-fee-current.json`
- QLoRA attempts made after adding the ledger eval:
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-ledger-validation-560`
    failed early and left an empty adapter directory. Log:
    `/workspace/outputs/qlora-rust-xriq-ledger-validation-560/qlora-20260517T013913Z.log`.
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-ledger-validation-280`
    completed, train loss about `0.7749`, reached `6/7` Rust/XRIQ validators,
    but broad eval regressed to `17/18`; not promoted.
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-fee-validation-280`
    completed, train loss about `0.7728`, but reached only `5/7` Rust/XRIQ
    validators; not promoted.
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-focused-120e4`
    completed, train loss about `0.6196`, reached `6/7` Rust/XRIQ validators,
    but still failed the ledger prompt; not promoted.
- Conclusion: keep serving `biber-dev-core-lora-rust-xriq-400` for now because
  the targeted Rust/XRIQ codegen profile now reaches `7/7` cargo validators and
  the served adapter still preserves the broad `18/18` baseline. Do not chase
  more blind QLoRA runs for the ledger prompt without first improving eval
  design, deterministic repair loops, or reviewed training-data strategy.
- XRIQ prototype progress made after the last model eval:
  - `docs/XRIQ_TECHNICAL_SPEC.md` now makes the intended XRIQ advantages
    explicit: no mining, predictable fees, Rust-first implementation, clean
    token issuance, DEX/BTC-swap friendliness, Zcash-like selective privacy as
    a future roadmap track, crypto agility, cautious compliance posture, and
    BIBER-assisted vertical tooling.
  - Added `xriq/crates/xriq-mempool` to the Rust workspace for deterministic
    private-devnet pending-transaction rules.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `27` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-mempool`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test` with `27`
    passing tests, and `cargo clippy -- -D warnings`.
- XRIQ prototype progress after the mempool checkpoint:
  - Added `xriq/crates/xriq-consensus` for deterministic single-authority
    private-devnet block production.
  - The producer creates child blocks from a parent header view, uses explicit
    state-root and transactions-root inputs, enforces block signatures, caps
    transaction count, and selects mempool transactions by deterministic
    fee/order/hash ordering.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `34` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-consensus`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test` with `34`
    passing tests, and `cargo clippy -- -D warnings`.
- Added the dedicated XRIQ legal-risk guardrail document:
  `docs/XRIQ_LEGAL_RISK_REDUCTION.md`.
  - Future Codex/BIBER sessions must follow it before XRIQ public-token, DEX,
    custody, bridge, stablecoin, payment, airdrop, validator-reward, liquidity,
    listing, or investment-facing messaging work.
  - Treat it as conservative engineering guidance, not legal advice. Public
    launch steps still require qualified legal, tax, AML, sanctions, securities,
    commodities, consumer-protection, and security review.
- Local XRIQ prototype progress after the legal-risk guardrail checkpoint:
  - Added `xriq/crates/xriq-rpc` for dependency-free local private-devnet RPC
    endpoint behavior.
  - The local RPC service currently covers health, chain status, account lookup,
    mempool listing, pending transaction lookup, and transaction submission with
    ledger-backed validation before mempool insertion.
  - Added `Mempool::entry` so RPC can expose pending transaction status without
    duplicating mempool internals.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `40` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-rpc`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test` with `40`
    passing tests, and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the RPC checkpoint:
  - Added `xriq/crates/xriq-storage` for in-memory block indexing and
    append-only local file storage that can reload persisted blocks.
  - Added `xriq/crates/xriq-node` for a minimal local private-devnet node loop.
  - The node loop can submit validated transactions, produce a block from
    pending transactions, apply ledger transitions, persist the block before
    committing node state, clear included mempool transactions, and expose
    RPC-visible state.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `50` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-storage` and `xriq-node`;
    Vast Rust verification also passed with `cargo fmt --check`, `cargo test`
    with `50` passing tests, and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the storage/node checkpoint:
  - Added `xriq/crates/xriq-wallet` with a real binary crate named
    `xriq-wallet`.
  - Current commands:
    - `xriq-wallet key generate --label <lowercase-label>`
    - `xriq-wallet transfer --chain-id <id> --from <address> --to <address> --amount <base-units> --fee <base-units> --nonce <number> [--expires-at-height <height>]`
  - This wallet is private-devnet-only. It creates deterministic test
    identities and fake nonempty test signatures; it does not manage real
    private keys, seed phrases, encrypted key stores, or production custody.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `56` passing tests, and
    `cargo clippy -- -D warnings`.
  - Local CLI smoke passed:
    `cargo run -p xriq-wallet -- key generate --label alice`.
  - Local transfer CLI smoke passed:
    `cargo run -p xriq-wallet -- transfer --chain-id xriq-devnet --from xriqdev1alice00000000000 --to xriqdev1bobbb00000000000 --amount 25 --fee 2 --nonce 7 --expires-at-height 100`.
  - Vast checkout was fast-forwarded to include `xriq-wallet`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test` with `56`
    passing tests, `cargo clippy -- -D warnings`, and both wallet CLI smokes.
- Local XRIQ prototype progress after the wallet checkpoint:
  - Added `xriq/crates/xriq-explorer` for private-devnet explorer view models
    and dependency-free text rendering.
  - Added `ChainStore::blocks_by_height_desc` so explorer views can list recent
    blocks without depending on a public web explorer or external database.
  - Current explorer scope is read-only and private-devnet-only: chain overview,
    latest blocks, block detail, account detail, mempool detail, and pending
    transaction detail.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `64` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-explorer`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test -j 1` with
    `64` passing tests, and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the explorer checkpoint:
  - Added `XriqNode::import_block` for in-process private-devnet block
    propagation tests between local nodes.
  - Imported peer blocks now validate the parent height/hash, chain id,
    nonempty block signature, authorized producer, and maximum transactions per
    block before any ledger or storage commit.
  - Follower nodes apply imported block transactions through the same ledger
    transition path, persist the block before committing node state, update the
    local tip, and remove matching included transactions from the local mempool.
  - Added local multi-node tests for follower import, consecutive empty block
    import, wrong-parent rejection, unauthorized-producer rejection, and
    over-limit block rejection.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `69` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include the local multi-node checkpoint;
    Vast Rust verification also passed with `cargo fmt --check`,
    `cargo test -j 1` with `69` passing tests, and
    `cargo clippy -- -D warnings`.
- XRIQ Phase 3 decision checkpoint after local multi-node verification:
  - Added `docs/XRIQ_PHASE3_DECISIONS.md`.
  - Consensus decision: keep deterministic authority consensus for the private
    devnet; defer public PoS/BFT economics, validator rewards, slashing, and
    public validator admission.
  - Supply decision: keep XRIQ supply test-only through deterministic private
    allocations; public supply, emissions, burns, treasury allocation, sale,
    airdrop, and reward schedule remain unset and blocked.
  - Governance decision: use private engineering governance through docs,
    commits, and verification; do not add token governance, treasury rights,
    revenue rights, or public upgrade promises.
  - Public-readiness decision: public launch remains blocked until crypto,
    hashing, genesis/config, networking, security, open-source, and legal-risk
    gates are satisfied.
  - Next implementation target is `xriq-crypto` plus canonical transaction and
    block hashing, with fake wallet signatures kept test-only until the crypto
    boundary is reviewed.
- Local XRIQ prototype progress after the Phase 3 decision checkpoint:
  - Added `xriq/crates/xriq-crypto`.
  - Added SHA-256 canonical transaction signing hashes, transaction hashes,
    block-header signing hashes, block/header hashes, and transaction-list
    roots using the RustCrypto `sha2` crate.
  - Added explicit signature algorithm identifiers for crypto agility and a
    `TestOnlySignatureVerifier` that accepts only hash-bound private-devnet
    test signatures.
  - Updated `xriq-wallet` so private-devnet transfer drafts produce
    hash-bound test-only signatures instead of arbitrary nonempty fake bytes.
  - This is still not production key custody or production signature
    verification.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `78` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-crypto`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test -j 1` with
    `78` passing tests, and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the crypto/hash checkpoint:
  - Wired canonical transaction hashes into higher-level RPC and node
    transaction-submission helper APIs.
  - Added a storage helper that appends blocks using the canonical
    block/header hash while keeping explicit hash append available for fixtures.
  - Added node helper APIs for canonical block production and peer-block import.
    Canonical production now derives the transaction-list root from selected
    transactions and derives the stored block hash from the produced block.
  - Explicit manual hash APIs remain available where tests need fixture control
    and negative-case construction.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `84` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `b77da59`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `84` passing tests,
    and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the canonical-hash API checkpoint:
  - Added shared private-devnet `GenesisConfig` in `xriq-core` with explicit
    chain id, genesis block hash, minimum fee, fee sink, authority,
    mempool/block limits, and deterministic test allocations.
  - Added genesis-derived constructors for ledger, mempool, consensus, and
    node setup so future tests and tooling do not need scattered fixture
    policy values.
  - Added deterministic account-state entries and SHA-256 account-state root
    calculation in `xriq-crypto`.
  - Added node canonical-root block production that derives transaction root,
    account-state root, and block hash from selected transactions and resulting
    ledger state.
  - This remains private-devnet-only. Public supply, emissions, validator
    rewards, token sale, airdrop, treasury, and public economics remain unset
    and blocked.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `96` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `a5a8c08`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `96` passing tests,
    and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the genesis/config checkpoint:
  - Imported peer blocks now reject mismatched canonical transaction roots.
  - Imported peer blocks now reject mismatched deterministic account-state roots
    after follower-side ledger execution.
  - Imported peer blocks now verify hash-bound private-devnet block-header
    signatures through `TestOnlySignatureVerifier`.
  - Wrong transaction roots, wrong state roots, and bad test-only block
    signatures leave follower ledger, tip, storage, and mempool state
    unchanged.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `99` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `543057c`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `99` passing tests,
    and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the import validation checkpoint:
  - RPC transaction submission now rejects invalid hash-bound private-devnet
    test signatures before mempool insertion.
  - Node transaction submission now rejects invalid hash-bound private-devnet
    test signatures before mempool insertion.
  - Imported peer blocks now reject transactions with invalid hash-bound
    private-devnet test signatures before follower ledger execution, storage
    commit, tip update, or mempool cleanup.
  - Explorer RPC-error mapping was updated for the new transaction-signature
    rejection case.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `102` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `3aca387`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `102` passing tests,
    and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the signature-bound import checkpoint:
  - Added deterministic private-devnet replay startup through
    `XriqNode::from_genesis_replaying_store`.
  - Replay starts from genesis, walks persisted store heights contiguously,
    rejects missing heights, rejects noncanonical stored block hashes, and uses
    the same parent/proposer/signature/transaction-root/state-root validation
    path as peer-block import before restoring ledger height, account state, and
    latest tip.
  - Added tests for file-store replay into node state, noncanonical stored hash
    rejection, and height-gap rejection.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `105` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `3e3e69c`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `105` passing
    tests, and `cargo clippy -- -D warnings`.
  - Vast noninteractive shells need the workspace Rust toolchain on PATH:
    `export CARGO_HOME=/workspace/.cargo RUSTUP_HOME=/workspace/.rustup PATH=/workspace/.cargo/bin:$PATH`.
- Local XRIQ prototype progress after the replay-startup checkpoint:
  - Added `xriq-node` as a real binary runner for private-devnet status checks.
  - New command:
    `cargo run -p xriq-node -- status --chain-file target/xriq-node-smoke-chain.bin`.
  - The status command opens the append-only file store, replays persisted
    canonical blocks through `XriqNode::from_genesis_replaying_store`, and
    prints private-devnet-only chain status including chain id, height, latest
    block hash, pending transaction count, and stored block count.
  - Added an optional `--alice-balance <base-units>` flag for local
    private-devnet test fixtures; this is not public-token economics.
  - Reaffirmed the narrowed project goal: finish BIBER MVP plus XRIQ
    private-devnet now, keep public XRIQ as a later guarded plan only.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `107` passing tests,
    `cargo clippy -- -D warnings`, and the new `xriq-node status` smoke.
  - Vast checkout was fast-forwarded to `066933f`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `107` passing
    tests, `cargo clippy -- -D warnings`, and the new `xriq-node status` smoke.
- Local XRIQ prototype progress after the status-runner checkpoint:
  - Added `xriq-node produce-transfer-block` as the first local runner command
    that moves a transfer through node state without a full HTTP server.
  - The command opens the append-only chain file, replays persisted canonical
    blocks, builds a hash-bound private-devnet test transaction, submits it
    through the node validation path, produces a canonical-root block with a
    hash-bound test block signature, persists the block, and reports replayable
    chain status.
  - Added runner tests for successful transfer/block persistence and failed
    transfer rejection without block persistence.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `109` passing tests,
    `cargo clippy -- -D warnings`, the new transfer/block smoke, and a replay
    status smoke against the same chain file.
  - Vast checkout was fast-forwarded to `4f0cb38`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `109` passing
    tests, `cargo clippy -- -D warnings`, the transfer/block smoke, and a
    replay status smoke against the same chain file.
- Local XRIQ prototype progress after the transfer-runner checkpoint:
  - Added `xriq-node explorer-overview` as the first file-backed local explorer
    runner over persisted private-devnet chain files.
  - The command opens the append-only chain file, replays persisted canonical
    blocks through `XriqNode::from_genesis_replaying_store`, and renders chain
    id, height, latest block hash, stored block count, pending count, and recent
    block summaries using `xriq-explorer`.
  - Added runner coverage for producing two persisted blocks and then rendering
    the replayed explorer overview from the same chain file.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `110` passing tests,
    `cargo clippy -- -D warnings`, two transfer/block smokes, and the new
    explorer overview smoke.
  - Vast checkout was fast-forwarded to `9b098f2`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `110` passing
    tests, `cargo clippy -- -D warnings`, two transfer/block smokes, and the
    explorer overview smoke.
- Local XRIQ prototype progress after the explorer-runner checkpoint:
  - Added `xriq-node produce-draft-block` so wallet `key=value` transfer draft
    files can be consumed by the node runner without starting HTTP/RPC serving.
  - The parser accepts the current `xriq-wallet transfer` output format,
    tolerates UTF-8 BOMs from Windows PowerShell-created files, rejects unknown,
    duplicate, missing, malformed, unsupported-version, and wrong-chain draft
    input, then uses the same private-devnet validation and block-production
    path as direct transfer production.
  - Added runner coverage for producing a block from a wallet draft file and
    rejecting a wrong-chain wallet draft without persisting a block.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `112` passing tests,
    `cargo clippy -- -D warnings`, wallet draft generation, draft-block
    production, and explorer overview replay. The local Windows test run used
    `CARGO_TARGET_DIR=target-codex-draft` because the default test binary was
    temporarily locked.
  - Vast checkout was fast-forwarded to `00f363f`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `112` passing
    tests, `cargo clippy -- -D warnings`, wallet draft generation,
    draft-block production, and explorer overview replay.
- Local XRIQ prototype progress after the wallet-draft runner checkpoint:
  - Added `xriq-node block-detail` for focused block inspection by height over
    persisted private-devnet chain files.
  - Added `xriq-node account-detail` for focused account inspection by address
    over persisted private-devnet chain files.
  - Added dependency-free account detail text rendering in `xriq-explorer`.
  - Added runner coverage for replaying a chain file before rendering block and
    account detail output.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `114` passing tests,
    `cargo clippy -- -D warnings`, wallet draft generation, draft-block
    production, explorer overview replay, block detail, and account detail.
    The local Windows test run used `CARGO_TARGET_DIR=target-codex-detail` to
    avoid default target binary locks.
  - Vast checkout was fast-forwarded to `f00e881`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `114` passing
    tests, `cargo clippy -- -D warnings`, wallet draft generation,
    draft-block production, explorer overview replay, block detail, and account
    detail.
- Local XRIQ prototype progress after the file-detail runner checkpoint:
  - Added `scripts/xriq_private_devnet_smoke.sh` as the compact one-command
    private-devnet smoke path.
  - The script chains wallet draft generation, draft-block production, explorer
    overview, block detail, and account detail against one persisted chain file
    under `xriq/target/`.
  - Added `.gitattributes` so Bash scripts keep LF line endings across Windows
    and Vast checkouts.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `114` passing tests, and
    `cargo clippy -- -D warnings`, using `CARGO_TARGET_DIR=target-codex-smoke`
    to avoid default target binary locks.
  - Local Windows Bash execution is unavailable because `bash.exe` maps to WSL
    and no WSL distribution is installed, so Bash script verification happened
    on Vast.
  - Vast checkout was fast-forwarded to `0789724`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `114` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T142125Z-19189`.
- Local XRIQ prototype progress after the mempool-detail runner checkpoint:
  - Added `xriq-node mempool-detail` for read-only pending transaction
    inspection over persisted private-devnet chain files.
  - The command replays the chain file and can preview a wallet transfer draft
    in the local mempool without producing a block or mutating storage.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the compact smoke path now
    verifies wallet draft generation, mempool preview, draft-block production,
    explorer overview, block detail, and account detail against one persisted
    chain file under `xriq/target/`.
  - Added directionally compatible exchange-readiness guardrails across the
    XRIQ docs: keep the MVP transparent and auditable, preserve future
    exchange-review surfaces, and do not claim listing readiness until public
    network, security, tokenomics, legal, AML/CFT, sanctions, custody,
    integration, and market-quality reviews are complete.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `115` passing tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-mempool` to avoid default target binary
    locks.
  - Local PowerShell smoke verified wallet draft generation, `mempool-detail`
    preview, unchanged status before block production, draft-block production,
    and explorer overview replay.
  - Vast checkout was fast-forwarded to `7e9d99f`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `115` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T144421Z-19849`.
- XRIQ exchange-compatibility documentation checkpoint:
  - Added `docs/XRIQ_EXCHANGE_READINESS_CHECKLIST.md`.
  - The checklist keeps XRIQ directionally compatible with future centralized
    exchange review while explicitly stating that XRIQ is not listing-ready.
  - It defines private-devnet, public-testnet, public-mainnet, and
    centralized-exchange review gates; hard-blocks listing outreach, market
    making, custody, bridges, public distribution, and investment-facing claims;
    and keeps privacy future-facing and selective-disclosure oriented.
  - Linked the checklist from `docs/XRIQ_TECHNICAL_SPEC.md`,
    `docs/XRIQ_PHASE3_DECISIONS.md`, `docs/XRIQ_LEGAL_RISK_REDUCTION.md`, and
    `docs/XRIQ_RUST_TRACK.md`.
- Local XRIQ prototype progress after the JSON runner checkpoint:
  - Added `--format text|json` to the file-backed `xriq-node` runner commands:
    `status`, `produce-transfer-block`, `produce-draft-block`,
    `explorer-overview`, `block-detail`, `account-detail`, and
    `mempool-detail`.
  - Text output remains the default. JSON output uses
    `format_version: xriq-node-json-v1`, keeps private-devnet warnings in the
    payload, emits hashes and addresses as strings, and emits XRIQ amounts as
    decimal `*_base_units` strings so future JS/TS clients do not lose `u128`
    precision.
  - Added Rust coverage for JSON output across status, block production,
    overview, block detail, account detail, and mempool detail.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the one-command Vast
    smoke path verifies selected JSON outputs for mempool detail, explorer
    overview, and account detail.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `116` passing tests, and
    `cargo clippy -- -D warnings`, using `CARGO_TARGET_DIR=target-codex-json2`
    to avoid default target binary locks. A first rerun under
    `target-codex-json` hit a Windows linker lock on an old test executable.
  - Vast checkout was fast-forwarded to `266daf3`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `116` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T150315Z-20580`.
- XRIQ JSON schema documentation checkpoint:
  - Added `docs/XRIQ_NODE_JSON_SCHEMA.md` for the private-devnet
    `xriq-node --format json` contract.
  - Documented the stable `xriq-node-json-v1` success shapes for status,
    produced block, explorer overview, block detail, account detail, and
    mempool detail.
  - Documented compatibility rules: text remains default, hashes and addresses
    are strings, XRIQ amounts are decimal `*_base_units` strings, optional
    heights are number-or-null, unknown fields should be ignored by consumers,
    and JSON error responses are available when `--format json` is requested.
  - Linked the schema doc from `xriq/README.md` and
    `docs/XRIQ_TECHNICAL_SPEC.md`.
- Local XRIQ prototype progress after the JSON error-response checkpoint:
  - Added structured JSON error responses for the `xriq-node` CLI when
    `--format json` is present and the command fails.
  - JSON error responses are written to stderr, exit nonzero, include
    `format_version: xriq-node-json-v1`, private-devnet warning, `ok: false`,
    optional `command`, and stable `error.code` plus `error.message`.
  - Text errors and help output remain the default when `--format json` is not
    requested.
  - Added stable `NodeRunnerError::code()` mappings and Rust coverage for the
    JSON error shape.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the one-command Vast
    smoke path verifies a missing `--chain-file` failure returns JSON with
    `ok: false`, `command: "status"`, `code: "missing_flag"`, and the expected
    message.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `117` passing tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-json-errors` to avoid default target binary
    locks.
  - Vast checkout was fast-forwarded to `8969b08`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T153320Z-21369`.
- Local XRIQ prototype progress after the JSON success-command checkpoint:
  - Added `command` to every successful `xriq-node --format json` response.
  - Success and error JSON responses now both identify the command, making the
    file-backed runner easier for future BIBER agents and HTTP/RPC wrappers to
    consume.
  - Updated `docs/XRIQ_NODE_JSON_SCHEMA.md` and
    `scripts/xriq_private_devnet_smoke.sh` to require command names in selected
    success JSON responses.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `117` passing tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-json-command` to avoid default target binary
    locks.
  - Vast checkout was fast-forwarded to `1a7218f`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T154848Z-22177`.
- Local XRIQ prototype progress after the smoke JSON artifact checkpoint:
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the one-command smoke
    path persists representative JSON response artifacts beside the draft and
    chain file.
  - Generated files are `mempool-detail.json`, `explorer-overview.json`,
    `account-detail.json`, and `status-error.json`.
  - Updated `docs/XRIQ_NODE_JSON_SCHEMA.md` and `docs/XRIQ_TECHNICAL_SPEC.md`
    so future BIBER/Codex sessions know to use those generated files as
    private-devnet examples, not public API fixtures.
  - Vast checkout was fast-forwarded to `f222b01`; focused verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `bash scripts/xriq_private_devnet_smoke.sh`, and `test -s` checks on all
    four generated JSON artifact files.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T155325Z-22475`.
  - Full Rust tests were intentionally not rerun for this script/docs-only
    checkpoint; previous full Rust and Vast verification remains through
    `1a7218f`.
- Local XRIQ prototype progress after the read-only HTTP wrapper checkpoint:
  - Added `xriq-node serve-readonly` as a dependency-free, loopback-first,
    private-devnet HTTP wrapper over the existing file-backed JSON runner
    outputs.
  - Implemented read-only endpoints for `/health`, `/v1/chain/status`,
    `/v1/explorer/overview?limit=5`, `/v1/blocks/{height}`,
    `/v1/accounts/{address}`, and `/v1/mempool`.
  - `POST /v1/transactions` and `GET /v1/transactions/{hash}` intentionally
    return `501` until a real persisted transaction index/submission path is
    added. Do not treat this wrapper as public API readiness.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the private-devnet HTTP surface and
    next-step boundaries.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    focused `cargo test -p xriq-node private_devnet_http_routes_wrap_file_backed_json_outputs -j 1`,
    `cargo test -p xriq-node -j 1` with `35` passing node tests,
    `cargo test -j 1` with `117` passing workspace tests using
    `CARGO_TARGET_DIR=target-codex-http` after the default target directory hit
    the known Windows linker lock, and `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `9618a11`; Vast verification passed
    with `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, a live loopback HTTP smoke against
    `127.0.0.1:18787`, and `bash scripts/xriq_private_devnet_smoke.sh`.
  - Live Vast HTTP smoke used chain:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-smoke-chain-20260517T160404Z-23361.bin`.
    It verified `/health`, `/v1/chain/status` with `current_height: 1`,
    `/v1/accounts/xriqdev1alice00000000000` with balance `73`, and `POST
    /v1/transactions` returning `501`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T160417Z-23404`.
- Local XRIQ prototype progress after the confirmed transaction HTTP lookup
  checkpoint:
  - Added `GET /v1/transactions/{hash}` behavior to `xriq-node
    serve-readonly` for confirmed transactions already stored in persisted
    private-devnet blocks.
  - The endpoint scans canonical transaction hashes in the replayed chain file
    and returns `command: "transaction-detail"`, `status: "confirmed"`,
    block height/hash, transaction index, sender/recipient, amount, fee, nonce,
    and expiry height.
  - Missing confirmed transactions return `404 transaction_not_found`; invalid
    non-lowercase/non-64-hex hashes return `400 invalid_hash`.
  - Durable pending transaction status and `POST /v1/transactions` remain
    intentionally deferred; do not pretend the file-backed HTTP wrapper has a
    persistent mempool yet.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the confirmed-transaction lookup
    boundary and the next implementation target.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -p xriq-node -j 1` with `35` passing node tests,
    `cargo test -j 1` with `117` passing workspace tests using
    `CARGO_TARGET_DIR=target-codex-tx-status`, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `b2080a2`; Vast verification passed
    with `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, a live loopback HTTP transaction lookup
    smoke against `127.0.0.1:18789`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Live Vast HTTP transaction lookup smoke used chain:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-tx-smoke-chain-20260517T161320Z-24229.bin`.
    It verified transaction hash
    `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`
    returned `transaction-detail`, `confirmed`, and `amount_base_units: "25"`;
    it also verified missing hash returns `404` and malformed hash returns
    `400`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T161332Z-24264`.
- Local XRIQ prototype progress after the wallet-draft HTTP submission
  checkpoint:
  - Added `xriq-node serve-private` as the submit-capable private-devnet HTTP
    mode while preserving `xriq-node serve-readonly` as read-only.
  - `POST /v1/transactions` in `serve-private` accepts the existing wallet
    transfer draft text body emitted by `xriq-wallet transfer`, validates it
    against the replayed chain state, immediately produces one block, and
    persists that block to the configured chain file.
  - `serve-readonly` still returns `501 not_implemented` for
    `POST /v1/transactions`.
  - This is an MVP submit-and-block helper, not a production mempool API.
    Durable pending transaction status and JSON transaction submission remain
    future work.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the `serve-private` command and wallet
    draft POST contract.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -p xriq-node -j 1` with `35` passing node tests,
    `cargo test -j 1` with `117` passing workspace tests using
    `CARGO_TARGET_DIR=target-codex-submit`, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `f9f4c6b`; Vast verification passed
    with `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, a live `serve-private` wallet-draft POST
    smoke against `127.0.0.1:18795`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Live Vast HTTP submit smoke used:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-submit-smoke-chain-20260517T162821Z-25111.bin`
    and draft:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-submit-smoke-draft-20260517T162821Z-25111.txt`.
    It verified `POST /v1/transactions` returned `submit-transaction` and
    `current_height: 1`, the returned transaction hash
    `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`
    was retrievable through `GET /v1/transactions/{hash}` as `confirmed`, and
    Alice's account balance became `73`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T162821Z-25143`.
- Local XRIQ prototype progress after the JSON transaction submission
  checkpoint:
  - Added dependency-free flat JSON parsing for `POST /v1/transactions` under
    `xriq-node serve-private`, while preserving the existing wallet transfer
    draft text body and preserving `serve-readonly` as read-only with `501` for
    POST.
  - Accepted JSON body shape is `xriq-node-transfer-submit-v1` with
    `version`, `chain_id`, `from`, `to`, `amount_base_units`,
    `fee_base_units`, `nonce`, and optional `expires_at_height`,
    `timestamp_ms`, and `consensus_round`. This remains a private-devnet
    submit-and-block helper, not a production mempool or signed-transaction
    format.
  - Added stable JSON error codes for malformed or unsupported JSON bodies:
    `invalid_json`, `unknown_json_field`, `duplicate_json_field`, and
    `missing_json_field`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` so future clients and BIBER agents can use
    the JSON submit body without treating it as a public API.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -p xriq-node -j 1` with `35` passing node tests,
    `cargo test -j 1` with `117` passing workspace tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `120654b`; Vast verification passed
    with the workspace-volume Rust toolchain:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`. Use that environment in future
    non-interactive SSH sessions because plain `cargo` is not on the default
    SSH `PATH`.
  - Vast Rust verification passed with `cargo fmt --check`,
    `cargo test -j 1` with `117` passing tests, and
    `cargo clippy -- -D warnings`.
  - Live Vast HTTP JSON submit smoke against `127.0.0.1:18796` passed. It
    verified JSON `POST /v1/transactions` returned `submit-transaction` and
    `current_height: 1`, the returned transaction hash
    `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`
    was retrievable through `GET /v1/transactions/{hash}` as `confirmed`, and
    Alice's account balance became `73`.
  - Live Vast JSON submit artifacts:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-json-submit-smoke-chain-20260517T193409Z-26165.bin`,
    `/workspace/biber-ai-platform/xriq/target/xriq-http-json-submit-smoke-body-20260517T193409Z-26165.json`,
    and
    `/workspace/biber-ai-platform/xriq/target/xriq-http-json-submit-smoke-response-20260517T193409Z-26165.json`.
  - Latest standard smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T193410Z-26244`.
- Local XRIQ prototype progress after the wallet JSON submit-output
  checkpoint:
  - Added `xriq-wallet transfer --format json`, which emits a
    `xriq-node-transfer-submit-v1` private-devnet JSON body accepted directly
    by `xriq-node serve-private` `POST /v1/transactions`.
  - The default `xriq-wallet transfer` text draft remains unchanged for older
    file-backed flows. The JSON output includes the private-devnet warning and
    `signature_bytes` metadata, but still does not expose private keys, seeds,
    or the test-only signature envelope.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the one-command smoke now
    generates the wallet JSON body, starts `serve-private`, posts the JSON body
    over HTTP, verifies confirmed transaction lookup, and verifies Alice's
    updated balance.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the wallet-generated JSON submit body
    and the new smoke artifacts.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -p xriq-wallet -j 1` with `12` passing wallet tests,
    `cargo test -j 1` with `120` passing workspace tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-wallet-json` to avoid default target binary
    locks. The generated local target directory was removed afterward.
  - Vast checkout was fast-forwarded to `3c0f0c1`; Vast verification passed
    with the workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `120` passing tests, `cargo clippy -- -D warnings`,
    `bash -n scripts/xriq_private_devnet_smoke.sh`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T194801Z-26995`.
    Important generated files include
    `wallet-transfer-submit.json`, `http-json-submit.json`,
    `http-json-transaction.json`, and `http-json-account.json` in that
    directory.
- Local XRIQ prototype progress after the checked JSON fixture checkpoint:
  - Added checked private-devnet golden fixtures under
    `xriq/fixtures/private-devnet/`:
    `wallet-transfer-submit.json` and `node-produce-transfer-block.json`.
  - Added exact-match Rust tests so `xriq-wallet transfer --format json` and
    `xriq-node produce-transfer-block --format json` must continue matching
    those private-devnet schema examples.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` to describe these fixtures as private-devnet
    schema drift checks, not public-mainnet API guarantees.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    focused wallet fixture tests with `13` passing wallet tests, focused node
    fixture test, `cargo test -j 1` with `122` passing workspace tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-fixtures` to avoid default target binary
    locks. Generated local target directories were removed afterward.
  - Vast checkout was fast-forwarded to `dafc5f0`; Vast verification passed
    with the workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `122` passing tests, `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T195504Z-28133`.
- Local XRIQ prototype progress after the read-only JSON fixture checkpoint:
  - Added additional checked private-devnet golden fixtures under
    `xriq/fixtures/private-devnet/`:
    `node-status-empty.json`, `node-mempool-empty.json`, and
    `node-account-alice-initial.json`.
  - Added exact-match Rust tests so fresh `xriq-node status --format json`,
    empty `xriq-node mempool-detail --format json`, and initial Alice
    `xriq-node account-detail --format json` continue matching those
    private-devnet schema examples.
  - Updated `xriq/README.md` and `docs/XRIQ_NODE_JSON_SCHEMA.md` to list the
    expanded checked fixture set for future BIBER/client-agent work.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-next-fixtures`: `cargo fmt --check`,
    focused `cargo test -p xriq-node checked_fixture -j 1` with `4` passing
    node fixture tests, `cargo test -j 1` with `125` passing workspace tests,
    and `cargo clippy -- -D warnings`. Generated local target/test files were
    removed afterward.
  - Pushed implementation commit:
    `3c50394 Add XRIQ read-only JSON fixtures`.
  - Vast checkout was fast-forwarded to `3c50394`; Vast verification passed
    with the workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `125` passing tests, and `cargo clippy -- -D warnings`. Full
    `scripts/xriq_private_devnet_smoke.sh` was intentionally not rerun for
    this fixture-only Rust checkpoint to keep cost/time low.
- Local XRIQ prototype progress after the transaction-detail runner checkpoint:
  - Added `xriq-node transaction-detail --chain-file <path> --tx-hash <64-hex>`
    with text and JSON output.
  - The command scans confirmed transactions in persisted blocks first. When
    `--draft-file <path>` is also supplied, it previews that wallet draft as an
    in-memory pending transaction and returns `status: "pending"` when the hash
    matches, without mutating the chain file or creating durable mempool state.
  - Added explicit `invalid_hash` JSON error support for malformed
    `--tx-hash` values.
  - Expanded `scripts/xriq_private_devnet_smoke.sh` so it now writes and checks
    `pending-transaction-detail.json` before block production and
    `confirmed-transaction-detail.json` after block production.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the transaction-detail runner contract
    and the new smoke artifacts.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-tx-detail`: `cargo fmt --check`, focused
    `cargo test -p xriq-node transaction_detail -j 1` with `2` passing tests,
    `cargo test -j 1` with `127` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward. Local `bash -n scripts/xriq_private_devnet_smoke.sh` could not
    run because Windows routed `bash` to WSL and no WSL distribution is
    installed, so Bash verification was done on Vast.
  - Pushed implementation commit:
    `824816e Add XRIQ transaction detail runner`.
  - Vast checkout was fast-forwarded to `824816e`; Vast verification passed
    with the workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `127` passing tests, `cargo clippy -- -D warnings`,
    `bash -n scripts/xriq_private_devnet_smoke.sh`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T202943Z-29119`.
- Local XRIQ prototype progress after the durable pending HTTP checkpoint:
  - Added optional durable private-devnet pending HTTP state to
    `xriq-node serve-private --pending-file <path>`.
  - Added `POST /v1/mempool` for private-devnet pending transaction submission.
    It accepts the same wallet draft or wallet JSON transfer body as
    `POST /v1/transactions`, validates against replayed chain state plus the
    current pending file, appends a pending record, and returns `202 Accepted`
    with the existing transaction-detail JSON shape and `status: "pending"`.
  - `GET /v1/mempool`, `GET /v1/chain/status`, and
    `GET /v1/transactions/{hash}` now include durable pending-file state when
    `--pending-file` is configured. Confirmed chain transactions are still
    resolved before pending records.
  - Existing `POST /v1/transactions` intentionally remains the simple
    submit-and-produce private-devnet flow; it persists a block immediately and
    does not become a public mempool API.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the full smoke covers
    durable pending submit/list/lookup artifacts:
    `http-pending-submit.json`, `http-pending-mempool.json`,
    `http-pending-transaction.json`, and `http-pending-mempool.tsv`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the pending HTTP endpoint contract and
    internal private-devnet pending-file behavior.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-pending-http2`: `cargo fmt --check`,
    focused
    `cargo test -p xriq-node private_devnet_http_routes_persist_pending_transactions -j 1`,
    `cargo test -j 1` with `128` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward. Local Bash verification is still unavailable because Windows has
    no WSL distribution installed, so Bash syntax and smoke verification were
    done on Vast.
  - Pushed implementation commit:
    `4e437cc Add XRIQ durable pending HTTP state`.
  - Pushed smoke-harness robustness commits:
    `174cdb1 Harden XRIQ smoke HTTP port selection` and
    `3306130 Run XRIQ smoke server directly`, followed by
    `2bd99cc Ensure XRIQ smoke server cleanup`. These fixed Vast smoke harness
    issues caused by fixed-port collisions, `cargo run` leaving the server
    child alive after the harness stopped Cargo, and the subshell needing to
    `exec` the node binary so cleanup kills the actual server process.
  - Vast Rust verification passed through `4e437cc` with
    `cargo fmt --check`, `cargo test -j 1` with `128` passing workspace tests,
    and `cargo clippy -- -D warnings`.
  - Vast checkout was then fast-forwarded to `2bd99cc`; verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh` and
    `bash scripts/xriq_private_devnet_smoke.sh`. After the final smoke,
    `pgrep -af xriq-node` showed no lingering XRIQ smoke server process.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T205029Z-32291`.
- Local XRIQ prototype progress after the durable pending block-production
  checkpoint:
  - Added `xriq-node produce-pending-block --chain-file <path> --pending-file
    <path>` with text and JSON output.
  - Added private-devnet HTTP `POST /v1/blocks` for
    `serve-private --pending-file <path>`. It loads durable pending
    transactions, produces one block, persists it to the configured chain file,
    and compacts the pending file so included transactions are removed.
  - Added `ProducedPendingBlockStatus` JSON with `block_hash`,
    `included_transaction_hashes`, `applied_transactions`, and the standard
    private-devnet node status fields.
  - Pending-file record loading now rejects records whose stored hash does not
    match the canonical transaction hash.
  - Expanded `scripts/xriq_private_devnet_smoke.sh` so the HTTP pending path
    now verifies `POST /v1/blocks`, pending-file compaction,
    `GET /v1/mempool` after production, and confirmed transaction lookup after
    production. New smoke artifacts include `http-pending-produce.json`,
    `http-pending-mempool-after-produce.json`, and
    `http-pending-confirmed-transaction.json`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the pending-block runner/API contract.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-pending-produce`: `cargo fmt --check`,
    focused `cargo test -p xriq-node pending -j 1` with `3` passing tests,
    `cargo test -j 1` with `129` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward. Bash verification is still done on Vast because this Windows
    workstation has no WSL distribution installed.
  - Pushed implementation commit:
    `ea9918d Add XRIQ pending block production`.
  - Vast checkout was fast-forwarded to `ea9918d`; verification passed with the
    workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `129` passing workspace tests, `cargo clippy -- -D warnings`,
    `bash -n scripts/xriq_private_devnet_smoke.sh`, and
    `bash scripts/xriq_private_devnet_smoke.sh`. After the smoke,
    `pgrep -af xriq-node` showed no lingering XRIQ smoke server process.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T210028Z-33204`.
- XRIQ checked pending-block fixture checkpoint:
  - Added checked fixture:
    `xriq/fixtures/private-devnet/node-produce-pending-block.json`.
  - Added Rust coverage so `xriq-node produce-pending-block --format json`
    must continue matching that fixture exactly after a deterministic durable
    pending transaction is submitted.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` so the checked fixture set includes
    pending-block production.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-pending-fixture`: `cargo fmt --check`,
    focused `cargo test -p xriq-node checked_fixture -j 1` with `5` passing
    fixture tests, `cargo test -j 1` with `130` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward.
  - Pushed fixture/docs commit:
    `77cf376 Add XRIQ pending block JSON fixture`.
  - Vast checkout was fast-forwarded to `77cf376`; focused verification passed
    with `cargo fmt --check`,
    `cargo test -p xriq-node checked_fixture -j 1` with `5` passing fixture
    tests, and `cargo clippy -p xriq-node -- -D warnings`.
  - Full Vast runtime smoke was not rerun for this fixture-only checkpoint; the
    pending-block implementation itself remains smoke-verified through
    `ea9918d` with artifacts at
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T210028Z-33204`.
- Local XRIQ prototype progress after the preflight transfer checkpoint:
  - Added `xriq-node preflight-transfer`, a deterministic private-devnet helper
    that infers the sender nonce from a replayed file-backed chain, validates a
    test-only transfer, submits it to the durable pending file, produces one
    block from pending transactions, compacts the pending file, and verifies the
    transaction through confirmed transaction lookup.
  - Added stable JSON/text output for the preflight transfer result including
    preflight balance/nonce, transaction hash, block hash, confirmed block
    height/index, final balance/nonce, and node status fields.
  - Expanded `scripts/xriq_private_devnet_smoke.sh` with preflight artifacts:
    `preflight-chain.bin`, `preflight-pending.tsv`,
    `preflight-transfer.json`, and `preflight-transaction.json`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the preflight transfer workflow and
    artifact contract.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-preflight`: focused
    `cargo test -p xriq-node preflight -j 1`, `cargo test -j 1` with `131`
    passing workspace tests, and `cargo clippy -- -D warnings`. Generated
    local target files were removed afterward.
  - Pushed implementation commit:
    `7c4030d Add XRIQ preflight transfer flow`.
  - Vast checkout was fast-forwarded to `7c4030d`; verification passed with the
    workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `131` passing workspace tests, `cargo clippy -- -D warnings`,
    `bash -n scripts/xriq_private_devnet_smoke.sh`, and
    `bash scripts/xriq_private_devnet_smoke.sh`. After the smoke,
    `pgrep -af xriq-node` showed only the invoking shell command, not a live
    XRIQ smoke server process.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T215459Z-35326`.
- XRIQ checked preflight-transfer fixture checkpoint:
  - Added checked fixture:
    `xriq/fixtures/private-devnet/node-preflight-transfer.json`.
  - Added Rust coverage so `xriq-node preflight-transfer --format json` must
    continue matching that fixture exactly after the deterministic file-backed
    preflight flow submits, produces, confirms, and compacts pending state.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` so the checked fixture set includes
    preflight transfer.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-preflight-fixture`: `cargo fmt --check`,
    focused `cargo test -p xriq-node checked_fixture -j 1` with `6` passing
    fixture tests, `cargo test -j 1` with `132` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward.
  - Pushed fixture/docs commit:
    `2a2b9d8 Add XRIQ preflight JSON fixture`.
  - Vast checkout was fast-forwarded to `2a2b9d8`; focused verification passed
    with `cargo fmt --check`,
    `cargo test -p xriq-node checked_fixture -j 1` with `6` passing fixture
    tests, and `cargo clippy -p xriq-node -- -D warnings`.
  - Full Vast runtime smoke was not rerun for this fixture-only checkpoint; the
    preflight implementation itself remains smoke-verified through `7c4030d`
    with artifacts at
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T215459Z-35326`.
- XRIQ checked block-detail transaction fixture checkpoint:
  - Added checked fixture:
    `xriq/fixtures/private-devnet/node-block-detail-transfer.json`.
  - Added Rust coverage so `xriq-node block-detail --format json` must continue
    matching the fixture exactly after a deterministic produced transfer block,
    including the block transaction hash used by the BIBER API smoke to follow
    latest-block transactions into transaction detail.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` so the checked fixture set includes block
    detail transaction hashes.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-block-detail-fixture`: `cargo fmt`, Python
    `compileall scripts`, focused
    `cargo test -p xriq-node block_detail_json_matches_checked_fixture -j 1`,
    `cargo fmt --check`, `git diff --check`, full `cargo test -j 1` with `135`
    passing Rust workspace tests, and `cargo clippy -- -D warnings`. Generated
    local target files were removed afterward.
  - Pushed fixture/docs commit:
    `66098c1 Add XRIQ block detail JSON fixture`.
  - Vast checkout was fast-forwarded to `66098c1`; focused verification passed
    with `cargo fmt --check` and
    `cargo test -p xriq-node block_detail_json_matches_checked_fixture -j 1`.
  - Full Vast runtime smoke was not rerun for this fixture-only checkpoint; the
    live BIBER API/vLLM services were not restarted and remain on the existing
    healthy direct deployment.
- XRIQ replay/startup consistency guard checkpoint:
  - Added a post-replay consistency guard inside
    `XriqNode::from_genesis_replaying_store`.
  - Replay still validates contiguous heights, canonical stored block hashes,
    parent links, authorized producer, transaction roots, state roots, and
    signatures while replaying each block. The new guard adds a final stored
    block count and replayed tip check so a corrupted/local store cannot hide
    extra records outside the replayed height range.
  - Added regression coverage with
    `replay_rejects_extra_stored_blocks_outside_replayed_height_range`, which
    creates a valid height-1 block plus an extra genesis-height record and now
    expects `UnexpectedStoredBlockCount`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` for the tightened replay/startup contract and
    current checked fixture set.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-replay-guard`: `cargo fmt`, focused replay
    guard test, `cargo fmt --check`, `git diff --check`, full
    `cargo test -j 1` with `136` passing Rust workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward.
  - Pushed implementation/docs commit:
    `66bf4bf Add XRIQ replay consistency guard`.
  - Vast checkout was fast-forwarded to `66bf4bf`; verification passed with
    `cargo fmt --check`, focused replay guard test,
    `cargo clippy -p xriq-node -- -D warnings`, full `cargo test -j 1` with
    `136` passing Rust workspace tests, and full
    `cargo clippy -- -D warnings`.
  - Live BIBER API smoke passed with
    `bash scripts/vast_xriq_api_smoke.sh`; artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T174425Z-41324`.
  - No vLLM/FastAPI restart, model training, or OpenAI mentor call was needed.
- XRIQ replay state-root/status marker checkpoint:
  - Added `state_root` to `NodeStatus`, text output, and the stable
    `xriq-node-json-v1` status/produced/preflight JSON surfaces.
  - Updated checked fixtures for empty status, produced transfer block,
    produced pending block, and preflight transfer so schema drift is explicit.
  - Updated `scripts/xriq_private_devnet_smoke.sh` to write
    `replay-status.json` and compare the replayed `status --format json`
    state root against the state root emitted immediately after block
    production. This gives future snapshot/copy/restart checks a compact marker
    without adding a premature snapshot export format.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` to document the state-root marker.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-status-root`: `cargo fmt`, focused
    `cargo test -p xriq-node checked_fixture -j 1` with `7` passing fixture
    tests, `cargo fmt --check`, `git diff --check`, full `cargo test -j 1`
    with `136` passing Rust workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward.
  - Pushed implementation/docs/smoke commit:
    `919b348 Expose XRIQ replay state root`.
  - Vast checkout was fast-forwarded to `919b348`; verification passed with
    `cargo fmt --check`, `bash -n scripts/xriq_private_devnet_smoke.sh`,
    focused checked-fixture tests, full `cargo test -j 1` with `136` passing
    Rust workspace tests, full `cargo clippy -- -D warnings`, and the full
    private-devnet smoke.
  - Latest private-devnet smoke artifact:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260518T180351Z-42108`.
    It includes `replay-status.json`.
  - Live BIBER API smoke passed with
    `bash scripts/vast_xriq_api_smoke.sh`; artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T180400Z-42662`.
  - No vLLM/FastAPI restart, model training, or OpenAI mentor call was needed.
- BIBER API XRIQ preflight wrapper checkpoint:
  - Added a thin private-devnet BIBER wrapper around the existing Rust
    `xriq-node preflight-transfer --format json` flow.
  - New API endpoint:
    `POST /v1/xriq/private-devnet/preflight-transfer`.
  - The request accepts transfer values only: `from`, `to`,
    `amount_base_units`, `fee_base_units`, optional `expires_at_height`,
    optional `timestamp_ms`, optional `consensus_round`, and optional
    `alice_balance_base_units`. It does not accept arbitrary chain or pending
    file paths.
  - Server-side XRIQ settings now include:
    `BIBER_XRIQ_WORKSPACE_DIR`, `BIBER_XRIQ_NODE_COMMAND`,
    `BIBER_XRIQ_CHAIN_FILE`, `BIBER_XRIQ_PENDING_FILE`,
    `BIBER_XRIQ_DEFAULT_ALICE_BALANCE_BASE_UNITS`,
    `BIBER_XRIQ_COMMAND_TIMEOUT_SECONDS`, `BIBER_XRIQ_RUSTUP_HOME`,
    `BIBER_XRIQ_CARGO_HOME`, and `BIBER_XRIQ_PATH_PREFIX`.
  - Vast `.env` was updated with:
    `BIBER_XRIQ_WORKSPACE_DIR=/workspace/biber-ai-platform/xriq`,
    `BIBER_XRIQ_NODE_COMMAND=/workspace/.cargo/bin/cargo run -q -p xriq-node --`,
    `BIBER_XRIQ_CHAIN_FILE=target/biber-api-private-devnet-chain.bin`,
    `BIBER_XRIQ_PENDING_FILE=target/biber-api-private-devnet-pending.tsv`,
    `BIBER_XRIQ_RUSTUP_HOME=/workspace/.rustup`,
    `BIBER_XRIQ_CARGO_HOME=/workspace/.cargo`, and
    `BIBER_XRIQ_PATH_PREFIX=/workspace/.cargo/bin`.
  - Implemented in both API paths because the packaged Docker/test path uses
    `src/biber_api`, while the current Vast direct launcher still serves
    `app.main:app`.
  - Local Windows verification: bundled Python `compileall app src` passed.
    Local pytest was not available on this workstation runtime, so pytest was
    run on Vast.
  - Vast verification passed with `/workspace/biber-venv/bin/python -m
    compileall app src`, `/workspace/biber-venv/bin/python -m pytest
    tests/test_xriq_preflight_api.py tests/test_model_registry.py
    tests/test_openai_mentor_trigger.py tests/test_repo_context.py -q`
    (`18 passed`), direct Python wrapper smoke through `src/biber_api`,
    `cargo fmt --check`, and
    `cargo test -p xriq-node checked_fixture -j 1` with `6` passing fixture
    tests.
  - FastAPI only was restarted on Vast; vLLM was not restarted. Live endpoint
    smoke passed through the current API process with a valid private-devnet
    fee of `2`. Earlier smoke with fee `1` correctly failed with
    `Transaction(FeeTooLow)`.
  - Pushed commits:
    `ddc5dc8 Add BIBER XRIQ preflight API wrapper` and
    `67ce353 Add XRIQ wrapper Rust environment config`.
- BIBER API XRIQ read-wrapper checkpoint:
  - Added thin private-devnet BIBER read wrappers around existing
    `xriq-node --format json` read commands.
  - New API endpoints:
    `GET /v1/xriq/private-devnet/status`,
    `GET /v1/xriq/private-devnet/accounts/{address}`, and
    `GET /v1/xriq/private-devnet/transactions/{tx_hash}`.
  - Implemented in both API paths because the packaged Docker/test path uses
    `src/biber_api`, while the current Vast direct launcher serves
    `app.main:app`.
  - Mempool read wrapper is intentionally delayed. The current CLI
    `xriq-node mempool-detail` command does not read the durable pending file,
    so exposing it through BIBER now would risk misleading clients about
    pending state.
  - Local Windows verification: bundled Python `compileall app src tests`
    passed. Local pytest remains unavailable on this workstation runtime, so
    pytest was run on Vast.
  - Vast verification passed with `/workspace/biber-venv/bin/python -m
    compileall app src`, `/workspace/biber-venv/bin/python -m pytest
    tests/test_xriq_preflight_api.py tests/test_model_registry.py
    tests/test_openai_mentor_trigger.py tests/test_repo_context.py -q`
    (`22 passed`), `cargo fmt --check`, and
    `cargo test -p xriq-node checked_fixture -j 1` with `6` passing fixture
    tests.
  - FastAPI only was restarted on Vast; vLLM was not restarted. Live endpoint
    smoke passed by first creating a valid private-devnet transfer through the
    preflight endpoint, then reading status, Alice account detail, and the
    confirmed transaction through the new BIBER read endpoints.
  - Pushed commit:
    `4d8c251 Add BIBER XRIQ read wrappers`.
- BIBER API/XRIQ durable mempool wrapper checkpoint:
  - Added durable pending-file support to `xriq-node mempool-detail` with
    `--pending-file`, while preserving the existing `--draft-file` preview path.
  - Added the BIBER API mempool read wrapper in both API paths:
    `GET /v1/xriq/private-devnet/mempool`.
  - Updated the private-devnet smoke script to create and verify
    `cli-pending-mempool.json` from the durable pending TSV file.
  - Local Windows verification passed: `git diff --check`, bundled Python
    `compileall app src tests`, `cargo fmt --check`, full `cargo test -j 1`
    with `134` passing Rust tests, and `cargo clippy -- -D warnings`.
    Local pytest is still unavailable in the bundled workstation runtime.
  - Vast verification passed: `/workspace/biber-venv/bin/python -m compileall
    app src tests`, focused pytest with `23 passed`, `cargo fmt --check`, full
    `cargo test -j 1` with `134` passing Rust tests, `cargo clippy -- -D
    warnings`, and `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest Vast smoke artifact:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260518T162531Z-37876/cli-pending-mempool.json`.
  - FastAPI only was restarted on Vast; vLLM was not restarted. Live endpoint
    smoke confirmed `/v1/xriq/private-devnet/mempool` returns `200 OK` with
    `command=mempool-detail` and current `pending_count=0`.
  - Pushed commit:
    `81824b3 Add XRIQ durable mempool wrapper`.
- BIBER API/XRIQ explorer/block wrapper checkpoint:
  - Added thin BIBER read wrappers around existing `xriq-node --format json`
    explorer commands.
  - New API endpoints in both API paths:
    `GET /v1/xriq/private-devnet/explorer?limit={count}` and
    `GET /v1/xriq/private-devnet/blocks/{height}`.
  - The explorer `limit` query is optional and bounded to `1..100`; block
    height is constrained to `>= 0`.
  - Local Windows verification passed: `git diff --check` and bundled Python
    `compileall app src tests`. Local pytest remains unavailable in the
    bundled workstation runtime.
  - Vast verification passed: `/workspace/biber-venv/bin/python -m compileall
    app src tests`, focused pytest with `25 passed`, and live endpoint smoke
    for `/v1/xriq/private-devnet/explorer?limit=5` plus
    `/v1/xriq/private-devnet/blocks/1`.
  - FastAPI only was restarted on Vast; vLLM was not restarted. Live smoke
    confirmed explorer `current_height=2` and block detail `height=1`.
  - Pushed commit:
    `32909e8 Add BIBER XRIQ explorer wrappers`.
- BIBER API/XRIQ consolidated smoke checkpoint:
  - Added `scripts/vast_xriq_api_smoke.sh`, a read-only live BIBER API smoke
    for the XRIQ private-devnet wrapper endpoints.
  - The script checks health, status, explorer overview, latest block detail,
    Alice account detail, and mempool detail. It stores JSON artifacts under
    `/workspace/outputs/xriq-api-smoke-*` by default.
  - Transaction detail is intentionally optional and skipped unless
    `BIBER_XRIQ_API_SMOKE_TX_HASH` is supplied; this avoids mutating the live
    chain just to create a confirmed hash.
  - Local Windows verification passed: bundled Python `compileall scripts` and
    `git diff --check`. Local `bash -n` could not run because this workstation
    has WSL but no installed Linux distro.
  - Vast verification passed: `bash -n scripts/vast_xriq_api_smoke.sh` and
    `bash scripts/vast_xriq_api_smoke.sh`.
  - Latest consolidated smoke artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T165750Z-39065/summary.json`.
  - Pushed commit:
    `16e506b Add BIBER XRIQ API smoke script`.
- XRIQ block transaction-hash navigation checkpoint:
  - Added canonical `tx_hash` to private-devnet block-detail transaction
    summaries, in both text rendering and `xriq-node block-detail --format
    json`.
  - Added `xriq-crypto` as a local `xriq-explorer` dependency so explorer view
    models derive canonical transaction hashes directly from block transactions.
  - Updated `scripts/vast_xriq_api_smoke.sh` so it automatically follows the
    first latest-block transaction hash into
    `/v1/xriq/private-devnet/transactions/{hash}` when present.
  - Local Windows verification passed: bundled Python `compileall scripts`,
    `git diff --check`, `cargo fmt --check`, full `cargo test -j 1` with `134`
    passing Rust tests, and `cargo clippy -- -D warnings`.
  - Vast verification passed: `cargo fmt --check`, full `cargo test -j 1` with
    `134` passing Rust tests, `cargo clippy -- -D warnings`, `bash -n
    scripts/vast_xriq_api_smoke.sh`, and `bash scripts/vast_xriq_api_smoke.sh`.
  - Latest consolidated smoke artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T170733Z-39972/summary.json`.
  - The live smoke confirmed `transaction_source=latest-block` and
    `transaction_status=confirmed` without mutating the chain. FastAPI and vLLM
    were not restarted.
  - Pushed commit:
    `6205b66 Expose XRIQ block transaction hashes`.
- BIBER MVP allowlisted test-runner checkpoint:
  - Added a protected, fixed-ID test-runner API in both the packaged API and
    the current Vast direct launcher path.
  - New endpoints:
    `GET /v1/tests` and `POST /v1/tests/run`.
  - Current allowlisted `test_id` values:
    `python-compileall-api`, `pytest-core`, `xriq-node-fixtures`, and
    `xriq-private-devnet-smoke`.
  - Clients choose only `test_id` and optional `dry_run`; they cannot submit
    arbitrary commands, working directories, shell fragments, or file paths.
  - Local workstation verification passed with bundled Python
    `compileall app src`, a direct runner dry-run smoke, and `git diff --check`.
    Local pytest is still unavailable in the bundled workstation runtime.
  - Vast checkout was fast-forwarded to `d4df8c0`.
  - Vast verification passed with the command
    `/workspace/biber-venv/bin/python -m compileall app src` and focused pytest:
    `tests/test_test_runner.py`, `tests/test_model_registry.py`,
    `tests/test_repo_context.py`, `tests/test_openai_mentor_trigger.py`, and
    `tests/test_xriq_preflight_api.py` with `31 passed`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `42987`.
  - Live smoke passed: `GET /v1/tests` returned the allowlist, and
    `POST /v1/tests/run` for `python-compileall-api` returned `ok=true`.
  - Pushed commit:
    `d4df8c0 Add allowlisted BIBER test runner API`.
- BIBER MVP bounded workspace-edit checkpoint:
  - Added a protected exact-text workspace edit API in both the packaged API
    and the current Vast direct launcher path.
  - New endpoint: `POST /v1/files/edit`.
  - The request accepts a workspace-relative `path`, `old_text`, `new_text`,
    `expected_replacements`, optional `create_if_missing`, and optional
    `dry_run`.
  - The edit path rejects absolute paths, path escapes, secret-looking paths,
    cache directories, common binary file types, oversized files, and
    replacement-count mismatches.
  - Creation is allowed only when `create_if_missing=true`; existing files
    require non-empty `old_text` and an exact replacement count.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --cached --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Vast checkout was fast-forwarded to `992890b`.
  - Vast verification passed with the command
    `/workspace/biber-venv/bin/python -m compileall app src tests` and focused pytest:
    `tests/test_workspace_edit.py`, `tests/test_test_runner.py`,
    `tests/test_model_registry.py`, `tests/test_repo_context.py`,
    `tests/test_openai_mentor_trigger.py`, and `tests/test_xriq_preflight_api.py`
    with `38 passed`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `43390`.
  - Live smoke passed: `GET /v1/tests` returned the updated allowlist, and
    `POST /v1/files/edit` in dry-run create mode returned `200 OK` with
    `created=true` and `changed=true`.
  - Pushed commit:
    `992890b Add bounded BIBER workspace edit API`.
- BIBER MVP GitHub branch/PR workflow checkpoint:
  - Added optional branch creation to GitHub file save. `GitHubSaveTarget` now
    supports `base_branch` and `create_branch_if_missing` so BIBER can save a
    generated file to a review branch created from a configured base branch.
  - Added the protected endpoint `POST /v1/github/pull-request` for opening a
    draft or ready pull request from an existing head branch to a base branch.
  - The GitHub client validates path/branch inputs, rejects unsafe branch
    names, wraps GitHub API failures, and keeps the token server-side.
  - Updated `docs/API_EXAMPLES.md` with the branch-save plus draft-PR flow.
  - Updated the focused `pytest-core` allowlist to include
    `tests/test_github_client.py`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --cached --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Vast checkout was fast-forwarded to `552220b`; verification passed with
    the command `/workspace/biber-venv/bin/python -m compileall app src tests`
    and focused pytest:
    `tests/test_workspace_edit.py`, `tests/test_github_client.py`,
    `tests/test_test_runner.py`, `tests/test_model_registry.py`,
    `tests/test_repo_context.py`, `tests/test_openai_mentor_trigger.py`, and
    `tests/test_xriq_preflight_api.py` with `47 passed`.
  - A follow-up label-only commit `179f58b` clarified the live `/v1/tests`
    description for GitHub workflows; Vast was fast-forwarded and compile-check
    passed after that commit.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `43893`.
  - Live smoke passed: `POST /v1/github/pull-request` returned expected
    disabled-state HTTP `503` because live GitHub credentials are intentionally
    not configured. `GET /v1/tests` shows `tests/test_github_client.py` in the
    focused pytest command.
  - Pushed commits:
    `552220b Add BIBER GitHub PR workflow support` and
    `179f58b Clarify GitHub workflow test label`.
- BIBER MVP end-to-end agent-smoke checkpoint:
  - Added `scripts/vast_biber_agent_smoke.sh`.
  - The script validates the live BIBER agent workflow with:
    repo-context `/v1/chat`, bounded `/v1/files/edit` dry-run, allowlisted
    `/v1/tests/run` with `python-compileall-api`, and optional GitHub
    save/draft-PR creation only when `BIBER_AGENT_SMOKE_GITHUB=1` is explicitly
    set.
  - Default GitHub behavior is `skip`, so the smoke does not create branches,
    commits, or pull requests unless deliberately enabled.
  - Artifacts are written outside the repo under
    `/workspace/outputs/biber-agent-smoke-*`.
  - Updated `docs/API_EXAMPLES.md` with the smoke command.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --cached --check`. Local
    `bash -n` remains unavailable because WSL has no installed distro.
  - Vast checkout was fast-forwarded to `28ebe62`; Vast verification passed
    with `bash -n scripts/vast_biber_agent_smoke.sh`,
    `/workspace/biber-venv/bin/python -m compileall app src tests`, and the
    live smoke script.
  - Latest live smoke summary: chat returned `model=biber-dev-core-v1`,
    mentor was not used, file edit was dry-run only, `python-compileall-api`
    returned `ok=true`, and GitHub was skipped because it is not configured.
  - Latest smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260518T195259Z-44005`.
  - No FastAPI/vLLM restart, model training, credential change, or OpenAI
    mentor call was needed.
  - Pushed commit:
    `28ebe62 Add BIBER agent smoke script`.
- BIBER MVP agent-session API checkpoint:
  - Added `POST /v1/agent/sessions` in both the packaged API and current Vast
    direct launcher path.
  - The endpoint wraps the existing MVP primitives into one response with a
    session id and ordered step records:
    repo-context chat, optional bounded workspace edit, optional allowlisted
    test run, optional GitHub save, and optional GitHub pull request.
  - Defaults remain conservative: `use_mentor=false`, `test_id` defaults to
    `python-compileall-api`, GitHub actions run only when explicitly included,
    and workspace edits obey the same bounded edit guardrails.
  - Added `tests/test_agent_session.py` and included it in the focused
    `pytest-core` allowlist.
  - Updated `docs/API_EXAMPLES.md` with a tracked agent-session example.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --cached --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Vast checkout was fast-forwarded to `b280d49`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests` and
    focused pytest:
    `tests/test_agent_session.py`, `tests/test_workspace_edit.py`,
    `tests/test_github_client.py`, `tests/test_test_runner.py`,
    `tests/test_model_registry.py`, `tests/test_repo_context.py`,
    `tests/test_openai_mentor_trigger.py`, and `tests/test_xriq_preflight_api.py`
    with `49 passed`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `44329`.
  - Live smoke passed: `POST /v1/agent/sessions` returned `200 OK` with chat,
    dry-run workspace edit, and successful `python-compileall-api` test step.
  - Pushed commit:
    `b280d49 Add BIBER agent session API`.
- BIBER MVP agent-session persistence checkpoint:
  - Added a file-backed agent-session artifact store in both the packaged API
    and the current Vast direct launcher path.
  - `POST /v1/agent/sessions` now persists each completed session as JSON and
    returns `artifact_path`.
  - Added read endpoints:
    `GET /v1/agent/sessions?limit=<n>` and
    `GET /v1/agent/sessions/{session_id}`.
  - New setting: `BIBER_AGENT_SESSION_DIR`. If omitted, Vast defaults to
    `/workspace/outputs/agent-sessions`; non-Vast local runs default to
    `.biber-runtime/agent-sessions` under the configured repo context root.
  - Updated `docs/API_EXAMPLES.md` with list/read examples and added
    persistence coverage to `tests/test_agent_session.py`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`. Local pytest and ruff
    are still unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `786ec51 Persist BIBER agent sessions`.
  - Vast checkout was fast-forwarded to `786ec51`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests` and
    focused pytest:
    `tests/test_agent_session.py`, `tests/test_workspace_edit.py`,
    `tests/test_github_client.py`, `tests/test_model_registry.py`,
    `tests/test_openai_mentor_trigger.py`, `tests/test_repo_context.py`, and
    `tests/test_xriq_preflight_api.py` with `44 passed`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `44642`.
  - Live persisted-session smoke passed: create/list/read all returned
    `200 OK`; session id `af658dd2-44b6-4800-bd87-561b7424c17c`; artifact:
    `/workspace/outputs/agent-sessions/af658dd2-44b6-4800-bd87-561b7424c17c.json`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP agent-session XRIQ-context checkpoint:
  - Added opt-in `include_xriq_context` to `POST /v1/agent/sessions` in both
    the packaged API and the current Vast direct launcher path.
  - When enabled, the session reads the configured XRIQ private-devnet overview
    before chat, prepends a concise chain summary to the model context, and
    persists the raw overview under an `xriq_context` step.
  - Added bounded controls `xriq_explorer_limit` and `xriq_snapshot_limit`.
    Defaults are `5`; each is capped at `25`.
  - Updated `scripts/vast_biber_agent_smoke.sh` so the live smoke now verifies
    the `xriq_context` step before `chat`, confirms mentor remains disabled,
    and records the XRIQ context height in `summary.json`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests scripts` and `git diff --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `e4df1d0 Add XRIQ context to agent sessions`.
  - Vast checkout was fast-forwarded to `e4df1d0`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_agent_session.py tests/test_xriq_preflight_api.py -q` with
    `23 passed`, and the live BIBER agent smoke.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `49733`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260518T234409Z-49758`.
    It returned session id `303e354e-79f3-4435-a936-01669802a1a4`, step order
    `xriq_context`, then `chat`, `xriq_context_height=2`, and
    `mentor_used=false`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP agent-capabilities checkpoint:
  - Added authenticated `GET /v1/agent/capabilities` in both the packaged API
    and the current Vast direct launcher path.
  - The endpoint gives future desktop/web/CLI agent clients a safe discovery
    surface for the current MVP: session endpoints, bounded workspace edits,
    allowlisted tests, GitHub save/PR availability, optional OpenAI mentor
    trigger, XRIQ private-devnet context support, and request templates.
  - Current presets:
    `default_coding_session` and `xriq_private_devnet_review`.
  - The XRIQ preset is still conservative: `language=Rust`,
    `task_type=xriq_private_devnet_review`, `use_mentor=false`,
    `include_xriq_context=true`, and `test_id=python-compileall-api`.
  - Added `tests/test_agent_capabilities.py`, updated
    `docs/API_EXAMPLES.md`, and extended `scripts/vast_biber_agent_smoke.sh`
    to validate the capabilities endpoint and preset list.
  - Local workstation verification passed with bundled Python
    `compileall app src tests scripts` and `git diff --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `8a539de Add BIBER agent capabilities endpoint`.
  - Vast checkout was fast-forwarded to `8a539de`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_agent_capabilities.py tests/test_agent_session.py tests/test_xriq_preflight_api.py -q`
    with `25 passed`, and the live BIBER agent smoke.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `50105`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260518T235843Z-50130`.
    It confirmed capability presets `default_coding_session` and
    `xriq_private_devnet_review`, returned session id
    `c1b8a1f1-fd96-4012-9607-90b687325e73`, step order `xriq_context`, then
    `chat`, and `xriq_context_height=2`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP agent-client helper checkpoint:
  - Added `scripts/biber_agent_client.py`, a dependency-free stdlib helper for
    future desktop/web/CLI client work.
  - The helper can:
    - call `GET /v1/agent/capabilities`,
    - print a concise capability/preset summary,
    - create `POST /v1/agent/sessions` requests from advertised presets, and
    - override model/language/task type/repo context/test id/XRIQ context flags
      from the command line.
  - The helper sends both `Authorization: Bearer <key>` and `X-API-Key` so it
    works against the current direct Vast API and the packaged API auth path.
  - Added `tests/test_biber_agent_client.py`, documented the helper in
    `docs/API_EXAMPLES.md`, and added the test to the `pytest-core` allowlist
    in both `app/test_runner.py` and `src/biber_api/test_runner.py`.
  - Extended `scripts/vast_biber_agent_smoke.sh` to run
    `scripts/biber_agent_client.py --json capabilities` against the live API
    and store `agent-client-capabilities.json` in the smoke artifact directory.
  - Local workstation verification passed with bundled Python
    `compileall app src tests scripts` and `git diff --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `51ad833 Add BIBER agent client helper`.
  - Vast checkout was fast-forwarded to `51ad833`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_agent_capabilities.py tests/test_agent_session.py -q`
    with `11 passed`, and the live BIBER agent smoke.
  - Restarted only the FastAPI process because the server-side `pytest-core`
    allowlist changed. vLLM stayed running with pid `5802`. New FastAPI pid:
    `50453`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T000619Z-50478`.
    It confirmed the helper capabilities path, capability presets
    `default_coding_session` and `xriq_private_devnet_review`, session id
    `36c0098f-d4a6-4674-9e58-88925bfb3d31`, step order `xriq_context`, then
    `chat`, and `xriq_context_height=2`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP agent-client create-session smoke checkpoint:
  - Extended `scripts/vast_biber_agent_smoke.sh` so the live smoke now calls
    `scripts/biber_agent_client.py --json create-session` with
    `--preset default_coding_session`, `--repo-context README.md`, `--no-test`,
    and a small `--max-tokens` value.
  - Added `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS`, defaulting to `24`,
    so future live client-session smokes stay cheap on the local GPU.
  - The smoke writes `agent-client-create-session.json` and records the
    stdlib-client-created session id/steps in `summary.json`.
  - Added focused unit coverage in `tests/test_biber_agent_client.py` for the
    create-session CLI flow and documented the smoke coverage in
    `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall scripts tests` and `git diff --check`. Local pytest is still
    unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `6317641 Add agent client create-session smoke`.
  - Vast checkout was fast-forwarded to `6317641`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_agent_session.py tests/test_agent_capabilities.py -q`
    with `13 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T100959Z-54048`.
    It confirmed the stdlib helper can create a tracked session through the
    real API: client session id `9b57e6a5-07da-458c-803a-702db6577d32` with
    step `chat`, plus XRIQ-context session id
    `562987a8-6003-4f21-b839-42ebefe28d2d` with steps `xriq_context`, then
    `chat`.
  - No service restart, credential change, model training, or OpenAI mentor
    call was needed.
- BIBER MVP agent-client session-history commands checkpoint:
  - Added `list-sessions` and `get-session` commands to
    `scripts/biber_agent_client.py`.
  - `list-sessions` wraps `GET /v1/agent/sessions?limit=N` and can print a
    compact session history summary or full JSON.
  - `get-session` wraps `GET /v1/agent/sessions/{id}` and can print the same
    concise session summary used by `create-session` or full JSON.
  - These commands intentionally do not call `GET /v1/agent/capabilities`
    first, so a future desktop/web client can inspect session history with one
    lightweight request.
  - Extended `scripts/vast_biber_agent_smoke.sh` so the live smoke now creates
    a session through the stdlib client, lists recent sessions, verifies the
    created id is present, and loads the created session by id.
  - Added focused unit coverage in `tests/test_biber_agent_client.py` and
    documented the new helper commands in `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall scripts tests`, `git diff --check`, and a tiny local parse/
    formatter smoke. Local pytest is still unavailable in the bundled
    workstation runtime.
  - Pushed implementation commit:
    `b8abdfb Add agent client session history commands`.
  - Vast checkout was fast-forwarded to `b8abdfb`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_agent_session.py tests/test_agent_capabilities.py -q`
    with `16 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T101616Z-54180`.
    It confirmed the stdlib helper can create, list, and load tracked sessions
    through the real API: client session id
    `3c113f71-e5ab-4ea4-8506-766dfc43a638`, listed sessions count `5`, loaded
    session id `3c113f71-e5ab-4ea4-8506-766dfc43a638`, plus XRIQ-context
    session id `c107be8f-5d8d-495c-ac3b-8fe4d056266a`.
  - No service restart, credential change, model training, or OpenAI mentor
    call was needed.
- BIBER MVP agent-client repo-context planning checkpoint:
  - Added `plan-context` to `scripts/biber_agent_client.py`.
  - The command wraps `POST /v1/repo/context/plan` with `--instruction`,
    repeatable `--pinned-path`, repeatable `--changed-path`, `--max-files`, and
    `--max-scan-files`.
  - The concise output lists the planner summary, detected project types,
    stack-profile ids, and selected workspace-relative context paths. `--json`
    returns the raw server response for client UIs.
  - The command intentionally does not call `GET /v1/agent/capabilities` first,
    so a future desktop/web client can plan context with one lightweight
    request.
  - Extended `scripts/vast_biber_agent_smoke.sh` so the live smoke now calls
    the stdlib client `plan-context`, verifies the pinned `README.md` is
    selected, and writes `agent-client-plan-context.json`.
  - Added focused unit coverage in `tests/test_biber_agent_client.py` and
    documented the new helper command in `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall scripts tests`, `git diff --check`, and a tiny local
    `plan-context` parse/formatter smoke. Local pytest is still unavailable in
    the bundled workstation runtime.
  - Pushed implementation commit:
    `775b278 Add agent client repo context planning`.
  - Vast checkout was fast-forwarded to `775b278`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_repo_context.py -q`
    with `30 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T105117Z-54319`.
    It confirmed the stdlib helper can create/list/load tracked sessions and
    plan repo context through the real API. The plan selected `README.md`,
    `docs/API_EXAMPLES.md`, `pyproject.toml`, `xriq/Cargo.lock`, and
    `xriq/Cargo.toml`; client session id
    `a8f0e071-16ed-4536-83cd-1d249e51491d`; XRIQ-context session id
    `37f417a1-92da-4be3-b39d-f7b67f0a53c0`.
  - No service restart, credential change, model training, or OpenAI mentor
    call was needed.
- BIBER MVP agent-client workspace-edit commands checkpoint:
  - Added `plan-edit` and `apply-edit` to `scripts/biber_agent_client.py`.
  - `plan-edit` wraps `POST /v1/files/edit/plan` with repeatable
    `--edit-json`, optional `--edits-file`, and `--max-files`, then prints a
    concise no-write edit plan or raw JSON with `--json`.
  - `apply-edit` wraps `POST /v1/files/edit/apply` with the same edit inputs
    plus required `--plan-hash`, preserving the server-side hash gate so stale
    or altered edit plans are rejected.
  - Edit files can contain one edit object, an array of edits, or an object with
    an `edits` array. Inline `--edit-json` intentionally accepts one edit
    object at a time to keep command-line usage explicit.
  - Extended `scripts/vast_biber_agent_smoke.sh` so the live smoke now plans a
    temporary workspace edit through the stdlib client, confirms planning does
    not write the file, applies it with the returned hash, verifies exact
    content, removes the smoke file, and writes
    `agent-client-plan-edit.json` plus `agent-client-apply-edit.json`.
  - Added focused unit coverage in `tests/test_biber_agent_client.py` and
    documented the helper commands in `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall scripts tests` and `git diff --check`. Local `bash -n` could
    not run because WSL has no installed distro on this workstation; the same
    syntax check passed on Vast. Local pytest is still unavailable in the
    bundled workstation runtime.
  - Pushed implementation commit:
    `12450e2 Add agent client workspace edit commands`.
  - Vast checkout was fast-forwarded to `12450e2`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_workspace_edit.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_repo_context.py -q`
    with `49 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T110521Z-54464`.
    It confirmed create/list/load session helpers, repo-context planning, and
    safe workspace edit planning/apply through the real API. The temporary edit
    path was
    `.biber-runtime/agent-client-edit-smoke-20260519T110521Z-54464.txt`; plan
    hash was
    `f3204a5f2d64818d3cc416b4b2c61884b4244199aa656a8f0d0f7ddc777161ec`;
    stdlib-client session id was
    `ea849ac2-627c-4bb4-9547-185bf7b554b2`; XRIQ-context session id was
    `f03f2123-2fa0-4cb7-b16a-e8e5d3c21d2a`.
  - No service restart, credential change, model training, or OpenAI mentor
    call was needed.
- BIBER MVP agent-client test/diagnosis commands checkpoint:
  - Added `list-tests`, `run-test`, and `diagnose-test` to
    `scripts/biber_agent_client.py`.
  - `list-tests` wraps `GET /v1/tests` so client tools can discover fixed
    server-side allowlisted test IDs without submitting arbitrary commands.
  - `run-test` wraps `POST /v1/tests/run` with `--test-id`, optional
    `--dry-run`, and optional `--diagnose-on-failure`. When diagnosis is
    requested and the test executes with `ok=false`, the client calls
    `POST /v1/tests/diagnose` and embeds the deterministic diagnosis in the
    returned JSON.
  - `diagnose-test` wraps `POST /v1/tests/diagnose` for raw output supplied by
    `--stdout`, `--stderr`, `--stdout-file`, `--stderr-file`, `--command-json`,
    or repeated `--command-part`. It is deterministic and does not call a
    model.
  - Extended `scripts/vast_biber_agent_smoke.sh` so the live smoke now verifies
    `list-tests`, runs `python-compileall-api` through the stdlib client, and
    classifies synthetic `.NET` compiler output through the stdlib client.
    Artifacts now include `agent-client-list-tests.json`,
    `agent-client-run-test.json`, and `agent-client-diagnose-test.json`.
  - Added focused unit coverage in `tests/test_biber_agent_client.py` and
    documented the helper commands in `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall scripts tests`, `git diff --check`, and a tiny local helper
    smoke. Local pytest is still unavailable in the bundled workstation
    runtime.
  - Pushed implementation commit:
    `b0d1df6 Add agent client test diagnosis commands`.
  - Vast checkout was fast-forwarded to `b0d1df6`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `67 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T111231Z-54617`.
    It confirmed create/list/load session helpers, repo-context planning, safe
    workspace edit planning/apply, allowlisted test discovery/execution, and
    deterministic failure diagnosis through the real API. The stdlib client ran
    `python-compileall-api` with `ok=true`, diagnosed synthetic `.NET` output
    as `compile_error` on stack `dotnet`, created client session id
    `0f1873b5-631c-4353-8dab-dfd6a89134aa`, and created XRIQ-context session
    id `d93e5d5a-5482-47ce-b628-c99cf3e7b88f`.
  - No service restart, credential change, model training, or OpenAI mentor
    call was needed.
- BIBER MVP agent-client GitHub workflow commands checkpoint:
  - Added `save-github` and `create-pr` to `scripts/biber_agent_client.py`.
  - `save-github` wraps `POST /v1/save/github` with explicit `--path`,
    `--content` or `--content-file`, optional `--owner`, optional `--repo`,
    `--branch`, optional `--base-branch`, `--create-branch-if-missing`, and
    `--commit-message`. The command does not read or manage GitHub tokens;
    server-side `.env` remains the only GitHub credential source.
  - `create-pr` wraps `POST /v1/github/pull-request` with explicit `--head`,
    `--base`, `--title`, optional `--body` or `--body-file`, optional
    `--owner`, optional `--repo`, and `--ready` for non-draft PRs. Draft PR is
    the default.
  - Updated `scripts/vast_biber_agent_smoke.sh` so when
    `BIBER_AGENT_SMOKE_GITHUB=1` and GitHub is configured, the smoke uses the
    stdlib client for GitHub save/PR and writes `agent-client-github-save.json`
    plus `agent-client-github-pr.json`. In the current Vast state GitHub is
    not configured, so the live smoke keeps this path skipped.
  - Added focused unit coverage in `tests/test_biber_agent_client.py` and
    documented the helper commands in `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall scripts tests`, `git diff --check`, and a tiny local helper
    smoke. Local pytest is still unavailable in the bundled workstation
    runtime.
  - Pushed implementation commit:
    `a3ba952 Add agent client GitHub workflow commands`.
  - Vast checkout was fast-forwarded to `a3ba952`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `79 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T111822Z-54777`.
    It confirmed create/list/load session helpers, repo-context planning, safe
    workspace edit planning/apply, allowlisted test discovery/execution, and
    deterministic failure diagnosis through the real API. GitHub workflow was
    deliberately skipped because `github_configured=false`; no GitHub
    credential was added or rotated. The stdlib-client session id was
    `a341fcf1-1402-41d6-a90b-f89203150590`; XRIQ-context session id was
    `bb4844af-6db9-4d43-a21b-f577c8847b54`.
  - No service restart, credential change, model training, or OpenAI mentor
    call was needed.
- BIBER MVP agent-client MVP-loop command checkpoint:
  - Added `mvp-loop` to `scripts/biber_agent_client.py` as a thin convenience
    wrapper over existing safe client primitives. It does not add a new server
    endpoint or a new orchestration layer.
  - The command always starts with `POST /v1/repo/context/plan` and can
    optionally chain no-write edit planning, hash-gated edit apply, allowlisted
    test execution, deterministic failure diagnosis, GitHub save, and draft PR
    creation.
  - Writes remain explicit: `--apply-edits` is required before planned edits
    are applied, `--test-id` is required before tests run, `--save-github-path`
    plus content is required before GitHub save, and `--create-pr` plus
    `--pr-title` is required before PR creation. GitHub credentials remain
    server-side only.
  - `mvp-loop` returns one JSON object with `ok`, `selected_context_paths`,
    `steps`, optional `edit_plan_hash`, optional `test_ok`, optional
    `diagnosis_summary`, and optional GitHub/PR URLs. A failed test sets
    `ok=false` and embeds deterministic diagnosis when available.
  - Extended `scripts/vast_biber_agent_smoke.sh` so the live smoke now runs
    `mvp-loop` against a temporary `.biber-runtime` file, verifies context,
    edit plan/apply, and `python-compileall-api`, then removes the temporary
    file. Artifact: `agent-client-mvp-loop.json`.
  - Added focused unit coverage in `tests/test_biber_agent_client.py` and
    documented the helper command in `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall scripts tests`, `git diff --check`, and a tiny local helper
    smoke. Local pytest is still unavailable in the bundled workstation
    runtime.
  - Pushed implementation commit:
    `1ce9f60 Add agent client MVP loop command`.
  - Vast checkout was fast-forwarded to `1ce9f60`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall scripts tests app src`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_github_client.py tests/test_agent_session.py tests/test_agent_capabilities.py tests/test_test_runner.py tests/test_test_diagnosis.py tests/test_workspace_edit.py tests/test_repo_context.py -q`
    with `81 passed`, and live
    `BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS=24 bash scripts/vast_biber_agent_smoke.sh`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T113714Z-54934`.
    It confirmed create/list/load session helpers, repo-context planning, safe
    workspace edit planning/apply, allowlisted test discovery/execution,
    deterministic failure diagnosis, and `mvp-loop` through the real API.
    `mvp-loop` completed `context_plan`, `edit_plan`, `edit_apply`, and
    `test_run` with `test_ok=true`; temporary path was
    `.biber-runtime/agent-client-mvp-loop-smoke-20260519T113714Z-54934.txt`.
    GitHub workflow was deliberately skipped because `github_configured=false`.
  - No service restart, credential change, model training, or OpenAI mentor
    call was needed.
- BIBER MVP repo-adaptation checkpoint:
  - Added `training/repo_adaptation_plan.py`, a conservative helper for
    preparing repo-specific BIBER adaptation work from a GitHub checkout or
    local repo without copying source code into a training file.
  - The helper scans metadata only: selected relative paths, size, SHA-256,
    language, and role. It skips `.git`, dependency/build directories,
    binary-looking files, secret-looking filenames, and files with
    secret-looking contents.
  - The emitted strategy defaults to repo-context-first. Fine-tuning is
    explicitly gated on repeated model failures, curated examples, held-out eval
    prompts, and a candidate model beating the current served baseline.
  - Added generated eval-prompt output so future BIBER sessions can test repo
    understanding before paying for a training run.
  - Added `docs/BIBER_REPO_ADAPTATION.md`, documented the CLI in
    `docs/API_EXAMPLES.md`, and added `tests/test_repo_adaptation_plan.py`.
  - Added the repo-adaptation test to the `pytest-core` allowlist in both
    `app/test_runner.py` and `src/biber_api/test_runner.py`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests scripts training`, `git diff --check`, a touched
    file long-line scan, and a real local plan smoke against this repo writing
    `.biber-runtime/repo-adaptation-smoke.json` plus
    `.biber-runtime/repo-adaptation-smoke-eval.jsonl`. Local pytest is still
    unavailable in the bundled workstation runtime.
  - Pushed implementation/fix commits:
    `9126fdd Add BIBER repo adaptation plan` and
    `2efa65b Fix repo adaptation relative role detection`.
  - Vast checkout was fast-forwarded to `2efa65b`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests scripts training`,
    focused pytest
    `tests/test_repo_adaptation_plan.py tests/test_training_dataset.py -q`
    with `7 passed`, and a real repo-adaptation plan smoke against this repo
    writing `/workspace/outputs/repo-adaptation-plan-smoke.json` plus
    `/workspace/outputs/repo-adaptation-eval-smoke.jsonl`.
  - Restarted only the FastAPI process because the server-side `pytest-core`
    allowlist changed. vLLM stayed running with pid `5802`. New FastAPI pid:
    `50843`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP repo-context planner checkpoint:
  - Added deterministic `plan_repo_context` support in both the packaged API
    and the current direct Vast app copy.
  - Added authenticated `POST /v1/repo/context/plan`. The endpoint returns
    `selected_paths`, `detected_project_types`, candidate reasons/priorities,
    skipped paths, and a concise summary. It does not return file contents.
  - The planner keeps user-pinned paths first, then changed files, related
    tests, project manifests, README files, and instruction-term matches.
  - It detects starter stack signals for `.NET`, Java/Spring-style Gradle or
    Maven repos, Rust, Node/React, and Python.
  - It filters secret-looking paths, dependency folders, build outputs, common
    binary suffixes, and paths outside `BIBER_REPO_CONTEXT_ROOT`.
  - `GET /v1/agent/capabilities` now advertises planner support and the
    `POST /v1/repo/context/plan` endpoint.
  - Added tests in `tests/test_repo_context.py` and
    `tests/test_agent_capabilities.py`, and documented the endpoint in
    `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests`, `git diff --check`, and a lightweight planner
    smoke. Local pytest is still unavailable in the bundled workstation
    runtime.
  - Pushed implementation commit:
    `1cc790a Add BIBER repo context planner`.
  - Vast checkout was fast-forwarded to `1cc790a`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests`,
    focused pytest
    `tests/test_repo_context.py tests/test_agent_capabilities.py -q` with
    `12 passed`, and a live authenticated planner endpoint smoke.
  - Restarted only the FastAPI process because API code changed. vLLM stayed
    running with pid `5802`. New FastAPI pid: `51098`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP multi-file edit planner checkpoint:
  - Added deterministic `plan_workspace_edits` support in both the packaged
    API and the current direct Vast app copy.
  - Added authenticated `POST /v1/files/edit/plan`. The endpoint validates a
    small batch of proposed edits without writing anything.
  - The response returns accepted edit previews, rejected edit reasons,
    old/new hashes, byte counts, replacement counts, simple risk markers,
    touched-file count, and a concise summary.
  - It reuses the existing single-file workspace edit guardrails: workspace
    path bounds, denied secret/build/binary paths, byte limits, exact
    replacement-count checks, and create-only-when-explicit behavior.
  - It rejects duplicate target paths within the same plan and caps the plan
    size through `max_files`/schema limits.
  - `GET /v1/agent/capabilities` now advertises `edit_plan`,
    `POST /v1/files/edit/plan`, and multi-file plan support.
  - Added tests in `tests/test_workspace_edit.py` and
    `tests/test_agent_capabilities.py`, and documented the endpoint in
    `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests`, `git diff --check`, and a lightweight planner
    smoke confirming no file was written. Local pytest is still unavailable in
    the bundled workstation runtime.
  - Pushed implementation commit:
    `70e6320 Add BIBER multi-file edit planner`.
  - Vast checkout was fast-forwarded to `70e6320`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests`,
    focused pytest
    `tests/test_workspace_edit.py tests/test_agent_capabilities.py -q` with
    `12 passed`, and a live authenticated edit-plan endpoint smoke.
  - Restarted only the FastAPI process because API code changed. vLLM stayed
    running with pid `5802`. New FastAPI pid: `51376`.
  - Confirmed the live smoke's planned create file was not written.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP test-failure diagnosis checkpoint:
  - Added deterministic `diagnose_test_failure` support in both the packaged
    API and the current direct Vast app copy.
  - Added authenticated `POST /v1/tests/diagnose`. The endpoint accepts
    stdout/stderr, command, test id, exit code, timeout status, and a small
    context-line budget. It does not call a model.
  - The first parser classifies common `.NET`, Java/Maven/Gradle, Rust/Cargo,
    Python/pytest, and Node/Jest/Vitest failure signals.
  - Response fields include `has_failure`, `primary_category`,
    `detected_stack`, structured signal evidence, `relevant_output`,
    `suggested_next_actions`, and a concise summary.
  - Supported categories include `timeout`, `compile_error`,
    `missing_dependency`, `configuration_error`, `assertion_failure`,
    `runtime_error`, `test_failure`, and `unknown`.
  - `GET /v1/agent/capabilities` now advertises
    `POST /v1/tests/diagnose`, supported stacks, and failure-diagnosis support.
  - Added `tests/test_test_diagnosis.py`, updated
    `tests/test_agent_capabilities.py`, added the diagnosis test to the
    `pytest-core` allowlist in both `app/test_runner.py` and
    `src/biber_api/test_runner.py`, and documented the endpoint in
    `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests`, `git diff --check`, and a lightweight `.NET`
    compiler-error diagnosis smoke. Local pytest is still unavailable in the
    bundled workstation runtime.
  - Pushed implementation commit:
    `1fd510f Add BIBER test failure diagnosis`.
  - Vast checkout was fast-forwarded to `1fd510f`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests`,
    focused pytest
    `tests/test_test_diagnosis.py tests/test_agent_capabilities.py -q` with
    `8 passed`, and a live authenticated diagnosis endpoint smoke.
  - Restarted only the FastAPI process because API code and `pytest-core`
    allowlist changed. vLLM stayed running with pid `5802`. New FastAPI pid:
    `51639`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP agent-session test-diagnosis checkpoint:
  - Tracked agent sessions now attach deterministic `diagnosis` output to the
    persisted `test_run` step whenever an allowlisted test fails or times out.
  - Passing tests and dry-run test steps remain unchanged; only failed/timed-out
    test results get the extra compact diagnosis object.
  - The embedded diagnosis includes detected stack, primary category,
    structured signals, relevant output, suggested next actions, and summary.
  - This makes the BIBER agent flow cheaper and more useful: client tools can
    send one agent-session artifact back into the local model instead of doing a
    separate failure-parsing pass.
  - Added focused coverage in `tests/test_agent_session.py` and documented the
    behavior in `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`. Local pytest is still
    unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `3069a50 Add agent-session test diagnosis`.
  - Vast checkout was fast-forwarded to `3069a50`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests` and
    focused pytest
    `tests/test_agent_session.py tests/test_test_diagnosis.py -q` with
    `11 passed`.
  - Restarted only the FastAPI process because API runtime logic changed. vLLM
    stayed running with pid `5802`. New FastAPI pid: `51901`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP `.NET`/Java allowlisted test-command checkpoint:
  - Added fixed stack-oriented test-runner IDs to both the packaged API and the
    direct Vast app copy:
    `dotnet-test`, `maven-test`, `gradle-test`, and `gradle-wrapper-test`.
  - These remain allowlisted commands, not arbitrary shell execution. They are
    intended for target repos that already contain the relevant `.NET`, Maven,
    or Gradle project/toolchain.
  - Discovery and dry-run behavior are tested so agent clients can inspect the
    exact command before executing it. Actual execution still depends on the
    target repo and installed toolchain.
  - Updated `GET /v1/agent/capabilities`, `GET /v1/tests`, focused tests in
    `tests/test_test_runner.py` and `tests/test_agent_capabilities.py`, and
    `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests`, `git diff --check`, and a dry-run smoke for
    `dotnet-test`. Local pytest is still unavailable in the bundled
    workstation runtime.
  - Pushed implementation commit:
    `c5f7235 Add dotnet and java test commands`.
  - Vast checkout was fast-forwarded to `c5f7235`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests`,
    focused pytest
    `tests/test_test_runner.py tests/test_agent_capabilities.py -q` with
    `9 passed`, and a live authenticated `/v1/tests` smoke listing all four
    new stack IDs.
  - Restarted only the FastAPI process because the API command allowlist
    changed. vLLM stayed running with pid `5802`. New FastAPI pid: `52412`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP repo-context stack-profile checkpoint:
  - Added deterministic repo-context stack profiles for `.NET / ASP.NET Core`
    and `Java / Spring Boot`.
  - `POST /v1/repo/context/plan` now returns `stack_profiles` for detected
    stacks. Profiles include preferred manifest patterns, entrypoint patterns,
    related-test patterns, and matching allowlisted test IDs.
  - `GET /v1/agent/capabilities` now advertises the supported repo-context
    stack profiles so client tools can plan repo context before calling chat or
    agent sessions.
  - The planner now selects common stack entrypoints when present:
    `.NET` `Program.cs`/`Startup.cs`, and Java/Spring
    `*Application.java`/`*Application.kt` under `src/main`.
  - The planner still avoids secrets and intentionally does not auto-include
    appsettings/application config files because those can contain credentials.
  - Added focused coverage in `tests/test_repo_context.py` and
    `tests/test_agent_capabilities.py`; updated `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests`, `git diff --check`, and a lightweight Java
    planner smoke. Local pytest is still unavailable in the bundled
    workstation runtime.
  - Pushed implementation commit:
    `6050bd0 Add repo context stack profiles`.
  - Vast checkout was fast-forwarded to `6050bd0`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests`,
    focused pytest
    `tests/test_repo_context.py tests/test_agent_capabilities.py -q` with
    `13 passed`, and live authenticated smokes for
    `GET /v1/agent/capabilities` and `POST /v1/repo/context/plan`.
  - Restarted only the FastAPI process because API response metadata changed.
    vLLM stayed running with pid `5802`. New FastAPI pid: `52785`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP hash-gated multi-file edit-apply checkpoint:
  - Added `plan_hash` to `POST /v1/files/edit/plan` responses.
  - Added authenticated `POST /v1/files/edit/apply`. The endpoint recomputes
    the requested edit plan against the current workspace, requires the
    supplied `plan_hash` to match, refuses dirty/rejected plans, and applies all
    edits as one bounded transaction.
  - If a file changed after planning, the apply endpoint returns a plan-hash
    mismatch and writes nothing. If a write fails mid-apply, touched files are
    rolled back from captured snapshots.
  - `GET /v1/agent/capabilities` now advertises `edit_apply`,
    `multi_file_apply_supported`, and `plan_hash_required`.
  - Updated `src/biber_api/workspace_edit.py`, the direct Vast app copy,
    schemas, tests, and `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests`, `git diff --check`, a matching-hash apply
    smoke, and a stale-hash smoke. Local pytest is still unavailable in the
    bundled workstation runtime.
  - Pushed implementation/fix commits:
    `0f9a450 Add hash-gated workspace edit apply` and
    `79aad96 Fix stale workspace edit apply hash check`.
  - Vast checkout was fast-forwarded to `79aad96`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests`,
    focused pytest
    `tests/test_workspace_edit.py tests/test_agent_capabilities.py -q` with
    `16 passed`, and a live authenticated plan/apply smoke using a temporary
    `.biber-runtime/workspace-edit-apply-smoke.txt` file that was cleaned up.
  - Restarted only the FastAPI process because API response metadata and route
    surface changed. vLLM stayed running with pid `5802`. New FastAPI pid:
    `53128`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP repo-adaptation live-eval wrapper checkpoint:
  - Added `training/repo_adaptation_eval.py`, a small wrapper around the
    existing live BIBER eval runner for JSONL prompts generated by
    `training/repo_adaptation_plan.py`.
  - The wrapper writes full eval results, a compact summary, and an optional
    failures JSONL that can be reviewed before creating curated training
    records. Do not fine-tune directly from the failures file.
  - Added `scripts/vast_eval_repo_adaptation_direct.sh` for direct Vast
    deployments. It uses the local BIBER API and the configured demo/test API
    key without printing secrets.
  - Added focused tests in `tests/test_repo_adaptation_eval.py`, added that
    test to the `pytest-core` allowlist, and documented the workflow in
    `docs/BIBER_REPO_ADAPTATION.md` and `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests training`, `git diff --check`, and a fake-runner
    repo-adaptation eval smoke. Local pytest is still unavailable in the
    bundled workstation runtime. Local `bash -n` could not run because the
    workstation WSL shim has no installed distribution, so shell syntax was
    checked on Vast.
  - Pushed implementation/fix commits:
    `8fca321 Add repo adaptation live eval wrapper` and
    `81b9dd5 Fix repo adaptation eval direct execution`.
  - Vast checkout was fast-forwarded to `81b9dd5`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall training tests app src`,
    focused pytest
    `tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_plan.py tests/test_live_model_eval.py tests/test_agent_capabilities.py -q`
    with `17 passed`, and `bash -n scripts/vast_eval_repo_adaptation_direct.sh`.
  - Live smoke generated one repo-adaptation prompt from this repo and ran it
    through the wrapper. The wrapper succeeded with `1/1` model responses and
    wrote summary/results/failures artifacts under `/workspace/outputs/evals`;
    the generated smoke prompt had `0/1` expectation checks passed, so the
    failure artifact is available as example adaptation signal.
  - Restarted only the FastAPI process because `pytest-core` allowlist changed.
    vLLM stayed running with pid `5802`. New FastAPI pid: `53552`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP repo-adaptation failure-review checkpoint:
  - Added `training/repo_adaptation_failure_review.py`, a conservative helper
    that groups repo-adaptation eval failures by prompt, language, task type,
    and missing expectations.
  - The helper writes a compact review JSON and can write candidate JSONL rows
    marked `quality: needs_review`. Candidate rows intentionally keep
    `output` empty, so they are review queue items and must not be promoted to
    `/workspace/data/biber_train.jsonl` until a reviewer writes a verified
    answer or patch and changes the quality to `reviewed` or `verified`.
  - Runtime/API errors and secret-like text are blocked from candidate
    generation. The default repeat threshold is `--min-repeats 2`; the live
    smoke used `--min-repeats 1` only to prove the wrapper on the existing
    one-row smoke artifact.
  - Added focused tests in `tests/test_repo_adaptation_failure_review.py`,
    added that test to the `pytest-core` allowlist, and documented the workflow
    in `docs/BIBER_REPO_ADAPTATION.md`, `docs/API_EXAMPLES.md`, and
    `training/dataset_format.md`.
  - Local workstation verification passed with bundled Python
    `compileall training tests app src`, `git diff --check`, and a tiny
    failure-review smoke. Local pytest is still unavailable in the bundled
    workstation runtime.
  - Pushed implementation commit:
    `68479ad Add repo adaptation failure review`.
  - Vast checkout was fast-forwarded to `68479ad`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall training tests app src`
    and focused pytest
    `tests/test_repo_adaptation_failure_review.py tests/test_repo_adaptation_eval.py tests/test_repo_adaptation_plan.py tests/test_agent_capabilities.py -q`
    with `13 passed`.
  - Live smoke reviewed
    `/workspace/outputs/evals/repo-adaptation-smoke.failures.jsonl` and wrote
    `/workspace/outputs/evals/repo-adaptation-smoke.review.json` plus
    `/workspace/outputs/evals/repo-adaptation-smoke.training-candidates.jsonl`.
    The candidate row had `quality=needs_review` and an empty `output`.
  - Restarted only the FastAPI process because `pytest-core` allowlist changed.
    vLLM stayed running with pid `5802`. New FastAPI pid: `53902`.
  - No credential change, model training, or OpenAI mentor call was needed.
- XRIQ snapshot export/import checkpoint:
  - Added private-devnet `xriq-node snapshot-export` and
    `xriq-node snapshot-import`.
  - Export writes a new snapshot directory containing `manifest.json`,
    `chain.bin`, and optional `pending.tsv`. The manifest records
    `xriq-private-devnet-snapshot-v1`, chain id, height, latest block hash,
    state root, pending count, and stored block count.
  - Import restores into fresh target chain/pending files only and refuses to
    overwrite existing targets, so it can be used for cheap Vast GPU/volume
    moves without accidentally replacing a live chain.
  - Added design/operations doc:
    `docs/XRIQ_SNAPSHOT_EXPORT_IMPORT.md`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`,
    `docs/XRIQ_TECHNICAL_SPEC.md`, and
    `scripts/xriq_private_devnet_smoke.sh`.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    focused `cargo test -p xriq-node snapshot -j 1`,
    focused `cargo test -p xriq-node checked_fixture -j 1`,
    full isolated `cargo test -j 1` with `136` passing workspace tests, and
    `cargo clippy -- -D warnings`. The default Windows target had a transient
    locked test binary, so full tests were run with an isolated target dir,
    then generated target files were removed.
  - Pushed implementation/docs/smoke commit:
    `fba4a1d Add XRIQ snapshot export import`.
  - Vast checkout was fast-forwarded to `fba4a1d`; verification passed with
    `bash -n scripts/xriq_private_devnet_smoke.sh`, `cargo fmt --check`,
    focused snapshot tests, focused checked-fixture tests, full
    `cargo test -j 1` with `136` passing workspace tests,
    `cargo clippy -- -D warnings`, and full
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest private-devnet smoke artifact:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260518T203806Z-44845`.
  - No FastAPI/vLLM restart, credential change, model training, or OpenAI
    mentor call was needed.
- BIBER XRIQ snapshot API wrapper checkpoint:
  - Added server-side snapshot roots:
    `BIBER_XRIQ_SNAPSHOT_ROOT_DIR` and
    `BIBER_XRIQ_SNAPSHOT_IMPORT_ROOT_DIR`.
  - Added authenticated endpoints:
    `POST /v1/xriq/private-devnet/snapshots/export` and
    `POST /v1/xriq/private-devnet/snapshots/import`.
  - Clients can provide only a safe snapshot name and options. Export writes
    under the configured snapshot root; import defaults to `target: staging`
    under the configured import root so normal smoke tests do not overwrite
    live private-devnet files. `target: configured` is available only as an
    explicit restore path, and the Rust runner still refuses existing targets.
  - Updated `docs/API_EXAMPLES.md`,
    `tests/test_xriq_preflight_api.py`, and
    `scripts/vast_xriq_api_smoke.sh`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`. Local pytest remains
    unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `4dbe7a0 Add BIBER XRIQ snapshot API wrapper`.
  - Vast checkout was fast-forwarded to `4dbe7a0`; verification passed with
    `/workspace/biber-venv/bin/python -m compileall app src tests`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest
    `tests/test_xriq_preflight_api.py -q` with `14 passed`.
  - Restarted only FastAPI; vLLM stayed running with pid `5802`. New FastAPI
    pid: `46258`.
  - Live consolidated API smoke passed, including snapshot export and safe
    staging import. Artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T210223Z-46283`.
    Snapshot name: `api-smoke-20260518T210223Z-46283`; height `2`; state root
    `578bdd2affeece78c7949d34da08391c797b363b045c3cff6c999868e0baa2d6`;
    pending transactions `0`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER XRIQ snapshot discovery checkpoint:
  - Added authenticated read-only endpoints:
    `GET /v1/xriq/private-devnet/snapshots?limit=<n>` and
    `GET /v1/xriq/private-devnet/snapshots/{snapshot_name}`.
  - The endpoints read only `manifest.json` files below the configured
    snapshot root, validate safe snapshot names, and expose summary/detail
    metadata for snapshots created by the server-side export endpoint.
  - Updated `docs/API_EXAMPLES.md`,
    `tests/test_xriq_preflight_api.py`, and
    `scripts/vast_xriq_api_smoke.sh`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`.
  - Pushed implementation commit:
    `fc03d6d Add XRIQ snapshot discovery API`.
  - Vast checkout was fast-forwarded to `fc03d6d`; verification passed with
    `/workspace/biber-venv/bin/python -m compileall app src tests`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest
    `tests/test_xriq_preflight_api.py -q` with `18 passed`.
  - Restarted only FastAPI; vLLM stayed running with pid `5802`. New FastAPI
    pid: `46758`.
  - Live consolidated API smoke passed, including snapshot export, safe
    staging import, snapshot list, and snapshot detail. Artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T220342Z-46783`.
    Snapshot name: `api-smoke-20260518T220342Z-46783`; height `2`; list count
    `2`; state root
    `578bdd2affeece78c7949d34da08391c797b363b045c3cff6c999868e0baa2d6`;
    detail reported manifest, chain, and pending files present.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER XRIQ private-devnet overview checkpoint:
  - Added authenticated read-only endpoint:
    `GET /v1/xriq/private-devnet/overview?explorer_limit=<n>&snapshot_limit=<n>`.
  - The endpoint consolidates existing server-side wrappers for status,
    explorer overview, durable mempool detail, and snapshot list into one
    wallet/explorer-friendly payload with a short summary.
  - Updated `docs/API_EXAMPLES.md`,
    `tests/test_xriq_preflight_api.py`, and
    `scripts/vast_xriq_api_smoke.sh`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`.
  - Pushed implementation commit:
    `716e9c1 Add XRIQ private devnet overview API`.
  - Vast checkout was fast-forwarded to `716e9c1`; verification passed with
    `/workspace/biber-venv/bin/python -m compileall app src tests`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest
    `tests/test_xriq_preflight_api.py -q` with `19 passed`.
  - Restarted only FastAPI; vLLM stayed running with pid `5802`. New FastAPI
    pid: `47248`.
  - Live consolidated API smoke passed, including the new overview endpoint.
    Artifact: `/workspace/outputs/xriq-api-smoke-20260518T223059Z-47273`.
    Overview summary: height `2`, pending count `0`, snapshot count `3`,
    latest snapshot `api-smoke-20260518T223059Z-47273`, state root
    `578bdd2affeece78c7949d34da08391c797b363b045c3cff6c999868e0baa2d6`.
  - No credential change, model training, or OpenAI mentor call was needed.

## Repo State

- Local branch: `main`
- Remote: `origin` points to `https://github.com/selvasmallive/biber-ai-platform.git`
- GitHub `origin/main` was pushed from this workstation on 2026-05-18 and now
  includes the live deployment hardening, GitHub save hardening, pytest
  verification, BIBER XRIQ preflight/read wrappers, the durable mempool
  wrapper, BIBER XRIQ snapshot wrapper/discovery endpoints, the consolidated
  private-devnet overview endpoint, allowlisted BIBER test-runner API,
  persisted BIBER agent-session artifacts, and handoff updates.
- The pushed history includes at least:
  - `b782c05 Harden Vast direct service binding`
  - `b0462e6 Update Vast handoff state`
  - `73bd171 Refresh Vast deployment handoff`
  - `97094ea Harden GitHub save integration`
  - `0272643 Update Vast handoff after GitHub save deploy`
  - `fae51c2 Record pytest availability in handoff`
  - `fc6b1ba Record Vast pytest verification`
  - `b3a7456 Record GitHub CLI auth setup`
  - `86129dc Smoke test BIBER GitHub save`
  - `8ae20ad Prepare Vast QLoRA training path`
  - `5f10d3f Add approved internet data ingestion`
  - `7d9446f Add bounded Hugging Face ingestion source`
  - `0e7fb30 Avoid training requirements transformer downgrade`
  - `e6a6339 Record Vast CodeInstruct dataset prep`
  - `1623c50 Harden Vast QLoRA launcher`
  - `fb97271 Add Vast LoRA serving start path`
  - `89ecb0b Record Vast LoRA training deploy`
  - `46f66c8 Add live LoRA eval runner`
  - `b25e68e Increase approved CodeInstruct ingest cap`
  - `4d76cf6 Relax React live eval heuristic`
  - `aa1f8d6 Add targeted eval training source`
  - `4c77e23 Record targeted LoRA improvement`
  - `1b6e073 Expand live eval prompt set`
  - `0d6b0b7 Relax rate limit eval heuristic`
  - `045d377 Relax API key eval heuristic`
  - `5f2e9de Add XRIQ Rust future track`
  - `d1dc0c5 Prioritize Rust XRIQ capability`
  - `fb5bb0f Add Rust XRIQ eval harness`
  - `11c3358 Add Vast Rust toolchain helper`
  - `14b89fb Fix Rust eval fixture formatting`
  - `fe75bce Harden Rust eval code validation`
  - `ca51c6e Add targeted Rust XRIQ dataset`
  - `4015d92 Record Rust XRIQ training results`
  - `9e5099c Confirm Rust XRIQ broad eval`
  - `17eebc9 Add HashSet Rust XRIQ examples`
  - `457155c Record Rust HashSet eval success`
  - `6482059 Add XRIQ spec and mentor strategy`
  - `ddc5dc8 Add BIBER XRIQ preflight API wrapper`
  - `67ce353 Add XRIQ wrapper Rust environment config`
  - `4d8c251 Add BIBER XRIQ read wrappers`
  - `690df43 Record BIBER XRIQ read wrapper checkpoint`
  - `81824b3 Add XRIQ durable mempool wrapper`
  - `0fffb80 Record XRIQ mempool wrapper checkpoint`
  - `32909e8 Add BIBER XRIQ explorer wrappers`
  - `4610a32 Record XRIQ explorer wrapper checkpoint`
  - `16e506b Add BIBER XRIQ API smoke script`
  - `a193478 Record XRIQ API smoke checkpoint`
  - `6205b66 Expose XRIQ block transaction hashes`
  - `d4df8c0 Add allowlisted BIBER test runner API`
  - `992890b Add bounded BIBER workspace edit API`
  - `552220b Add BIBER GitHub PR workflow support`
  - `179f58b Clarify GitHub workflow test label`
  - `28ebe62 Add BIBER agent smoke script`
  - `b280d49 Add BIBER agent session API`
  - `786ec51 Persist BIBER agent sessions`
  - `fba4a1d Add XRIQ snapshot export import`
  - `4dbe7a0 Add BIBER XRIQ snapshot API wrapper`
  - `fc03d6d Add XRIQ snapshot discovery API`
  - `716e9c1 Add XRIQ private devnet overview API`
- Later local/Vast handoff commits may exist on top of those; verify with Git
  before acting on branch state.
- Use `git status --short --branch`, `git log --oneline -1`, and
  `git ls-remote origin refs/heads/main` for authoritative current Git state.
- Keep the Vast.ai checkout at `/workspace/biber-ai-platform` fast-forwarded
  with `git pull --ff-only origin main` after documentation or deployment
  commits are pushed.
- Prefer `git status --short --branch` and `git log --oneline -1` over this
  file for authoritative current Git state.
- GitHub CLI was installed on this workstation at
  `C:\Program Files\GitHub CLI\gh.exe` and authenticated as `selvasmallive`.
  `gh auth setup-git` was run, and `git push origin main` verified GitHub auth
  with `Everything up-to-date`. In this Codex process, `gh` may not be on
  `PATH` until the app/session is restarted; use the full path if needed.
- Real GitHub generated-code save was smoke-tested from the live Vast.ai API
  using a temporary GitHub CLI token from this workstation. The token was not
  written to the live `.env`, temporary files were removed, and FastAPI was
  restarted back to normal no-token configuration after the test.

## Completed

- Fast-forwarded the Vast.ai checkout from `4044c5b` to `5798c7f`.
- Bootstrapped the no-Docker direct deployment path on Vast.ai.
- Verified the instance has two GPUs:
  - GPU 0: NVIDIA GeForce RTX 5060 Ti, 16311 MiB
  - GPU 1: NVIDIA GeForce RTX 5060 Ti, 16311 MiB
- Confirmed Docker is not present on the instance; the direct deployment path is
  the correct path.
- Verified local scaffold validation passes with the bundled Codex Python runtime.
- Verified local Python syntax compile checks pass for `app`, `src`, `worker`,
  `training`, and `scripts`.
- Verified remote `pip check` reports no broken requirements after dependency
  pin updates.
- Verified remote direct smoke test passes:
  - `GET /health`
  - `GET /v1/runtime`
  - `GET /v1/models`
  - `POST /v1/chat`
- `/v1/chat` returned model content `ok` from `biber-dev-core`.
- Verified a richer live `/v1/chat` prompt through FastAPI produced a real
  Python `fib(n)` implementation from `biber-dev-core`.
- Hardened the direct deployment so FastAPI and vLLM bind to `127.0.0.1` by
  default. Use SSH tunnels unless the `.env` credentials have been replaced and
  public binding is intentionally configured.
- Restarted the live Vast.ai services after applying explicit loopback values in
  `.env`. Final `ss` output showed both listeners on `127.0.0.1` only.
- Re-verified the live Vast.ai deployment on 2026-05-16:
  - Vast checkout: `main...origin/main [ahead 2]` at that time
  - vLLM pid: `5634`
  - FastAPI pid: `6039`
  - both services listening only on `127.0.0.1`
  - `bash scripts/vast_test_direct.sh` passed
  - `/v1/chat` returned model content `ok` from `biber-dev-core`
- Hardened the GitHub generated-code save integration in `97094ea`:
  - GitHub target paths are normalized and reject empty/parent-directory paths.
  - missing GitHub owner/repo now returns a controlled configuration error
    instead of an unhandled exception.
  - GitHub API and network failures are wrapped as controlled save errors.
  - `/v1/chat` save-to-GitHub and `/v1/save/github` map disabled/config/API
    failures to clear HTTP responses.
  - added mocked client tests in `tests/test_github_client.py`.
- Deployed `97094ea` to the Vast.ai checkout through a Git bundle because
  GitHub push was blocked by credentials. Vast is now ahead of `origin/main`.
- Restarted only FastAPI after deploying `97094ea`; vLLM stayed warm.
  - vLLM pid: `5634`
  - FastAPI pid: `6759`
- Verified on Vast.ai after the FastAPI restart:
  - `/workspace/biber-venv/bin/python -m compileall app src tests` passed.
  - mocked GitHub client checks passed against the Vast virtualenv.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/save/github` without `GITHUB_TOKEN` returns
    `HTTP 503 {"detail":"GitHub saving is not configured."}`.
- Installed `pytest>=8,<9` into the Vast.ai virtualenv and verified
  `tests/test_github_client.py` passes:
  - Python: `/workspace/biber-venv/bin/python`
  - pytest: `8.4.2`
  - result: `5 passed`
- Verified GitHub caught up through `fc6b1ba`, then fetched `origin/main` on
  Vast.ai. Vast checkout showed `main...origin/main` with no ahead count.
- Verified real `/v1/save/github` from Vast.ai with temporary GitHub credentials:
  - FastAPI was restarted with transient `GITHUB_TOKEN`,
    `GITHUB_DEFAULT_OWNER=selvasmallive`, and
    `GITHUB_DEFAULT_REPO=biber-ai-platform`.
  - `/v1/save/github` returned `HTTP 200`.
  - GitHub URL:
    `https://github.com/selvasmallive/biber-ai-platform/blob/main/generated/github-save-smoke.md`
  - Resulting Git commit: `86129dc Smoke test BIBER GitHub save`
  - Local and Vast.ai checkouts were fast-forwarded to include the generated
    smoke-test file.
  - FastAPI was restarted back to normal mode after the smoke test:
    vLLM pid `5634`, FastAPI pid `7818`.
  - `bash scripts/vast_test_direct.sh` passed after the normal restart.
  - `/v1/runtime` reports `github_configured=false` again because no GitHub
    token is currently persisted in `.env`.
- Prepared and verified the custom-model QLoRA training path in `8ae20ad`:
  - added JSONL dataset validation utilities and tests.
  - replaced the QLoRA placeholder with a dry-runnable training entrypoint.
  - added `scripts/vast_train_qlora_tmux.sh` for long GPU jobs on the 500 GB
    Vast volume.
  - added `requirements-training.txt` without forcing a Torch/CUDA replacement.
  - local bundled-Python compile, dataset validation, and QLoRA dry-run passed.
  - local pytest was not available in the bundled Python runtime, so pytest was
    verified on the Vast virtualenv instead.
  - Vast pytest for `tests/test_training_dataset.py` passed with `4 passed`.
  - Vast compile, sample dataset validation, and QLoRA dry-run also passed.
  - no real fine-tuning job was started.
- Added the approved internet dataset ingestion pipeline in `5f10d3f`:
  - approved-source manifest: `training/approved_sources.json`
  - ingestion CLI: `training/internet_ingest.py`
  - Vast helper: `scripts/vast_ingest_internet_dataset.sh`
  - tests: `tests/test_internet_ingest.py`
  - generated datasets, raw downloads, provenance, outputs, and adapters are
    ignored by Git.
- Verified internet ingestion on Vast after pulling `5f10d3f`:
  - compile checks for `training`, `scripts`, and `tests` passed.
  - Vast pytest for `tests/test_internet_ingest.py` and
    `tests/test_training_dataset.py` passed with `8 passed`.
  - approved internet-smoke ingestion wrote
    `/workspace/data/biber_train_internet_smoke.jsonl` with 2 records.
  - raw source was stored at
    `/workspace/data/raw/biber-platform-sample-jsonl.jsonl`.
  - provenance was written to `/workspace/outputs/dataset-provenance.json`.
  - validation report was written to
    `/workspace/outputs/internet-dataset-validation.json`.
  - QLoRA dry-run accepted the internet-smoke dataset.
  - no real fine-tuning job was started.
- Added and verified a bounded Hugging Face rows source in `7d9446f`:
  - enabled `SoyMaycol/CodeInstruct-20K` with `cc-by-4.0` metadata,
    `question` -> `instruction`, and `answer` -> `output`.
  - bounded source limit is currently 200 records.
  - Vast ingestion wrote
    `/workspace/data/biber_train_internet_codeinstruct_200.jsonl`.
  - resulting dataset had 200 records: 2 project-owned smoke records and 198
    CodeInstruct records.
  - provenance:
    `/workspace/outputs/dataset-provenance-codeinstruct-200.json`.
  - validation report:
    `/workspace/outputs/internet-dataset-validation-codeinstruct-200.json`.
  - canonical training dataset was promoted to `/workspace/data/biber_train.jsonl`
    and validated with 0 errors.
  - QLoRA dry-run accepted `/workspace/data/biber_train.jsonl`.
- Hardened `requirements-training.txt` in `0e7fb30` so it does not pin or
  downgrade Transformers. Vast already has `torch 2.11.0+cu130` and
  `transformers 5.8.1` from the live vLLM environment.
- Installed QLoRA extras into `/workspace/biber-venv` after a pip dry-run showed
  no Torch/Transformers downgrade:
  - `accelerate 1.13.0`
  - `bitsandbytes 0.49.2`
  - `peft 0.19.1`
  - `pip check` reported no broken requirements.
  - `training.qlora_train_biber_dev_core.require_training_dependencies()`
    imported all required training objects successfully.
  - vLLM and FastAPI remained running and healthy after install.
- Hardened the Vast QLoRA launcher in `1623c50`:
  - training jobs default Hugging Face and pip caches to `/workspace`.
  - `scripts/vast_train_qlora_tmux.sh` supports bounded smoke runs with
    `BIBER_TRAIN_MAX_STEPS`, `BIBER_TRAIN_LIMIT_SAMPLES`, `BIBER_TRAIN_SAVE_STEPS`,
    and related environment knobs.
  - long training jobs still run in `tmux` on the Vast GPU so Codex does not need
    to stay active while the GPU works.
- Added the LoRA serving start path in `fb97271`:
  - `scripts/vast_start_lora_direct.sh` serves `/workspace/adapters/biber-dev-core-lora`
    as `biber-dev-core`.
  - vLLM serves the base model separately as `biber-dev-core-base`.
  - `scripts/vast_start_direct.sh` accepts `BIBER_VLLM_LORA_MODULES` and passes
    `--enable-lora --lora-modules` to vLLM.
- Completed real starter QLoRA training on Vast.ai:
  - stopped direct services first to free GPU memory.
  - one-step smoke run completed and wrote
    `/workspace/adapters/biber-dev-core-lora-smoke`.
  - full starter run completed 25 steps in about 73.18 seconds with train loss
    about `0.8886`.
  - saved the trained adapter at `/workspace/adapters/biber-dev-core-lora`.
  - direct PEFT/Transformers adapter-load smoke generated a correct Python
    `add(a, b)` function.
- Restarted the live Vast.ai direct deployment with the trained LoRA adapter:
  - vLLM pid: `9923`
  - FastAPI pid: `10535`
  - both services listen only on `127.0.0.1`.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/models` reports both `biber-dev-core-base` and the LoRA adapter model
    `biber-dev-core`.
  - `/v1/chat` returned model content `ok` from `biber-dev-core`.
- Added a fixed live LoRA evaluation runner in `46f66c8`:
  - prompt set: `training/eval_prompts.jsonl`
  - Python runner: `training/live_model_eval.py`
  - Vast wrapper: `scripts/vast_eval_lora_direct.sh`
  - outputs stay on the 500 GB Vast volume under `/workspace/outputs/evals`.
  - Vast verification passed:
    `/workspace/biber-venv/bin/python -m compileall training scripts tests`,
    `bash -n scripts/vast_eval_lora_direct.sh`, and
    `tests/test_live_model_eval.py` with `4 passed`.
- Ran the first live LoRA baseline eval against `biber-dev-core`:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T184927Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T184927Z.jsonl`
  - result: `6/6` prompts returned responses, `3/6` simple expectation checks
    passed.
  - passed: Python add function, subtract-bug fix, iterative Fibonacci.
  - weak spots: pytest generation returned an implementation instead of tests,
    React component used `interface` while the simple check expected `type`, and
    the API error-shape answer omitted `status`.
- Increased the approved `SoyMaycol/CodeInstruct-20K` ingest cap to 1000 in
  `b25e68e`; the Vast wrapper still keeps an explicit total cap and the source
  remains approved, license-allowlisted, and domain-allowlisted.
- Ingested and promoted a larger approved internet dataset:
  - candidate:
    `/workspace/data/biber_train_internet_codeinstruct_1000.jsonl`
  - canonical dataset:
    `/workspace/data/biber_train.jsonl`
  - result: `998` clean records, `0` validation errors.
  - provenance:
    `/workspace/outputs/dataset-provenance-codeinstruct-1000.json`
  - validation:
    `/workspace/outputs/internet-dataset-validation-codeinstruct-1000.json`
    and `/workspace/outputs/dataset-validation.json`.
  - first strict `min-records=1000` attempt failed because filtering left 998
    valid records; rerun accepted the dataset with `min-records=990`.
- Trained a new one-epoch LoRA adapter from the 998-record dataset:
  - services were stopped first to free GPU memory.
  - tmux session: `biber-qlora-codeinstruct-998`.
  - log: `/workspace/outputs/qlora-codeinstruct-998/qlora-20260516T185433Z.log`
  - output adapter:
    `/workspace/adapters/biber-dev-core-lora-codeinstruct-998`
  - steps: `125`
  - runtime: about `360.7` seconds.
  - train loss: about `0.7911`.
  - saved checkpoints: `checkpoint-50`, `checkpoint-100`, `checkpoint-125`.
- Restarted the live Vast.ai direct deployment with the 998-record LoRA adapter:
  - vLLM pid: `11462`
  - FastAPI pid: `11958`
  - both services listen only on `127.0.0.1`.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/models` reports `biber-dev-core` rooted at
    `/workspace/adapters/biber-dev-core-lora-codeinstruct-998`.
- Corrected the React eval heuristic in `4d76cf6` to accept `ButtonProps`
  rather than requiring the literal word `type`.
- Latest corrected live eval against the 998-record adapter:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T190402Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T190402Z.jsonl`
  - result: `6/6` prompts returned responses, `4/6` simple expectation checks
    passed.
  - passed: Python add function, subtract-bug fix, iterative Fibonacci, and
    TypeScript React Button component.
  - remaining weak spots: pytest generation still returned an implementation
    instead of tests, and the API error-shape answer still omitted `status`.
- Added the project-owned targeted eval-improvement source in `aa1f8d6`:
  - file: `training/targeted_eval_dataset.jsonl`
  - manifest source: `biber-targeted-eval-jsonl`
  - content: 27 verified records, focused on pytest/test generation and API
    error-response shapes with `status` and `detail`.
  - local and Vast validation reported 27 records, 0 errors, 0 warnings.
- Ingested and promoted the combined targeted approved dataset:
  - candidate:
    `/workspace/data/biber_train_targeted_codeinstruct_1000.jsonl`
  - canonical dataset:
    `/workspace/data/biber_train.jsonl`
  - result: `1000` clean records, `0` validation errors.
  - source mix: 2 project smoke records, 27 targeted project-owned records, and
    971 CodeInstruct records.
  - provenance:
    `/workspace/outputs/dataset-provenance-targeted-codeinstruct-1000.json`
  - validation:
    `/workspace/outputs/internet-dataset-validation-targeted-codeinstruct-1000.json`
    and `/workspace/outputs/dataset-validation.json`.
  - first ingest attempt hit a transient Hugging Face rows API `HTTP 502`; rerun
    succeeded.
- Trained a targeted-priority LoRA adapter:
  - services were stopped first to free GPU memory.
  - tmux session: `biber-qlora-targeted-350`.
  - log: `/workspace/outputs/qlora-targeted-350/qlora-20260516T191155Z.log`
  - output adapter: `/workspace/adapters/biber-dev-core-lora-targeted-350`
  - training used the canonical 1000-record dataset for validation, then
    `BIBER_TRAIN_LIMIT_SAMPLES=350` and `BIBER_TRAIN_NUM_EPOCHS=2` to keep the
    run low-cost while emphasizing the targeted examples.
  - steps: `88`
  - runtime: about `255.3` seconds.
  - train loss: about `0.7927`.
  - saved checkpoints: `checkpoint-50`, `checkpoint-75`, `checkpoint-88`.
- Restarted the live Vast.ai direct deployment with the targeted-priority LoRA
  adapter:
  - vLLM pid: `12793`
  - FastAPI pid: `13134`
  - both services listen only on `127.0.0.1`.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/models` reports `biber-dev-core` rooted at
    `/workspace/adapters/biber-dev-core-lora-targeted-350`.
- Latest corrected live eval against the targeted-priority adapter:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T191829Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T191829Z.jsonl`
  - result: `6/6` prompts returned responses, `6/6` simple expectation checks
    passed.
  - the previously weak pytest-generation and API error-shape prompts now pass
    the fixed baseline checks.
- Expanded the live eval prompt set in `1b6e073` from 6 to 18 prompts across
  Python, pytest, FastAPI, API error shapes, React, TypeScript, SQL, JSONL, and
  retry-helper tasks. This gives the next improvement loop broader coverage than
  the targeted 6-prompt smoke baseline.
- Ran the expanded live eval against the targeted-priority adapter:
  - first broad run produced `18/18` responses and `17/18` simple expectation
    checks because the rate-limit prompt used `rate_limit_exceeded`, which was
    acceptable but too strict for the old literal check.
  - after `0d6b0b7`, a second broad run produced `18/18` responses and `17/18`
    checks because the missing-API-key prompt used `api_key_missing`, again
    acceptable but too strict for the old literal check.
  - after `045d377`, the latest broad run produced `18/18` responses and
    `18/18` simple expectation checks.
  - latest summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T192652Z.summary.json`
  - latest detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T192652Z.jsonl`
  - note: this is still a lightweight substring/regex baseline, not a full
    execution-quality guarantee.
- Started the Rust/XRIQ capability track:
  - Rust/XRIQ prompt file: `training/eval_prompts_rust_xriq.jsonl`.
  - Vast wrapper: `scripts/vast_eval_rust_xriq_direct.sh`.
  - Vast Rust toolchain helper: `scripts/vast_install_rust_toolchain.sh`.
  - `training/live_model_eval.py` now supports optional code validators.
  - Rust validators create temporary cargo projects and run
    `cargo fmt --check`, `cargo check`, and `cargo test --lib`.
  - Rust/XRIQ evals are separate from `training/eval_prompts.jsonl` so the
    existing `18/18` broad baseline remains comparable.
  - The Rust toolchain helper installs to `/workspace/.cargo` and
    `/workspace/.rustup` so toolchain files stay on the 500 GB Vast volume.
- Completed the first Rust/XRIQ improvement loop:
  - Rust toolchain installed on Vast under `/workspace/.cargo` and
    `/workspace/.rustup`.
  - Pre-training Rust/XRIQ eval against
    `/workspace/adapters/biber-dev-core-lora-targeted-350`:
    `6/6` responses, `6/6` substring expectations, `2/6` cargo validators.
  - Added project-owned targeted Rust/XRIQ data:
    `training/targeted_rust_xriq_dataset.jsonl`.
  - Added approved-source manifest entry:
    `biber-rust-xriq-targeted-jsonl`.
  - Ingested candidate:
    `/workspace/data/biber_train_rust_xriq_targeted_codeinstruct_1000.jsonl`.
  - Candidate mix: 2 project smoke records, 27 Python/API targeted records, 10
    Rust/XRIQ targeted records, and 961 CodeInstruct records.
  - Candidate validation: `1000` records, `0` errors, `0` warnings.
  - Candidate provenance:
    `/workspace/outputs/dataset-provenance-rust-xriq-targeted-codeinstruct-1000.json`.
  - Candidate validation report:
    `/workspace/outputs/internet-dataset-validation-rust-xriq-targeted-codeinstruct-1000.json`.
  - Promoted candidate to `/workspace/data/biber_train.jsonl` and validated it
    with `1000` records, `0` errors, `0` warnings.
  - Stopped services before training to free GPU memory.
  - Trained Rust/XRIQ-priority adapter in tmux session
    `biber-qlora-rust-xriq-400`.
  - Training log:
    `/workspace/outputs/qlora-rust-xriq-400/qlora-20260516T195917Z.log`.
  - Output adapter:
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - Training used the canonical 1000-record dataset for validation, then
    `BIBER_TRAIN_LIMIT_SAMPLES=400` and `BIBER_TRAIN_NUM_EPOCHS=2`.
  - Steps: `100`.
  - Runtime: about `290.5` seconds.
  - Train loss: about `0.7752`.
  - Saved checkpoints include `checkpoint-50`, `checkpoint-75`, and
    `checkpoint-100`.
  - Restarted live serving with the Rust/XRIQ adapter:
    `biber-dev-core=/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - Last confirmed pids after restart: vLLM `16407`, FastAPI `16748`.
  - `bash scripts/vast_test_direct.sh` passed after restart.
  - Post-training Rust/XRIQ eval:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260516T200642Z.summary.json`.
  - Post-training Rust/XRIQ result: `6/6` responses, `6/6` substring
    expectations, `5/6` cargo validators.
  - Remaining Rust/XRIQ weak spot: `rust_xriq_mempool_insert` still omitted
    `use std::collections::HashSet;`, causing `cargo check` failure.
  - Added six extra project-owned HashSet-focused Rust/XRIQ source examples and
    tightened the held-out `rust_xriq_mempool_insert` eval prompt so it
    explicitly requires `use std::collections::HashSet;`.
  - Verified the updated Rust/XRIQ targeted source locally and on Vast:
    `16` records, `0` errors, `0` warnings.
  - Reran the Rust/XRIQ eval against the existing live adapter without
    retraining:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260517T001354Z.summary.json`.
  - HashSet follow-up result: `6/6` responses, `6/6` substring expectations,
    and `6/6` cargo validators. No new adapter was trained because the current
    live adapter passed the tightened Rust/XRIQ eval.
  - A first broad 18-prompt eval attempt after Rust/XRIQ retraining wrote
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T000202Z.summary.json`
    with `0/18` responses because FastAPI was not listening yet
    (`Connection refused`). Treat that as an infrastructure failure, not a
    model-quality result.
  - After restarting services with the Rust/XRIQ adapter, the confirmed broad
    18-prompt eval passed:
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T000637Z.summary.json`.
  - Confirmed broad result after Rust/XRIQ retraining: `18/18` responses and
    `18/18` simple expectation checks.
  - Confirmed detailed broad JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T000637Z.jsonl`.
- Started XRIQ Phase 2 design documentation:
  - technical spec draft: `docs/XRIQ_TECHNICAL_SPEC.md`.
  - current draft direction: private-devnet first, account-based first
    prototype, Rust workspace with small crates, deterministic authority
    consensus for the initial private devnet, wallet CLI, and private explorer.
  - public launch, public token distribution, exchange/custody/payment use, and
    production security claims remain out of scope until separate security and
    legal/compliance review.
- Added BIBER agent API and OpenAI/Codex mentor strategy:
  `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md`.
  - BIBER remains the default low-cost GPU-backed inference engine.
  - OpenAI/Codex mentor remains optional and disabled by default unless the user
    explicitly enables it for quality review.
  - Future agent-client work should move toward database-backed API keys,
    repo-agent sessions, patch-oriented responses, streaming, usage logging, and
    explicit mentor review gates.
- Added explicit OpenAI mentor trigger plumbing:
  - `OPENAI_API_KEY` must stay server-side in `.env` or a secret manager; do
    not commit it, train on it, or send it to the local model.
  - When `BIBER_MENTOR_ENABLED=true`, `OPENAI_API_KEY` is present, and
    `OPENAI_MODEL` is set, BIBER calls the OpenAI Responses API only if a user
    prompt includes `Review with OpenAI mentor`.
  - Routine inference still stays on the local Vast GPU-backed model, and
    `use_mentor=false` disables the mentor call even if the phrase appears.
  - Local Python verification passed with `pytest`: `27` tests.
  - Vast checkout was fast-forwarded to `859df96`.
  - Vast syntax verification passed with `/venv/main/bin/python -m compileall
    app src tests training`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `14596`.
  - `bash scripts/vast_test_direct.sh` passed. Runtime now reports
    `mentor_trigger_phrase="Review with OpenAI mentor"`, with
    `mentor_enabled=false` and `mentor_configured=false` until server-side
    OpenAI credentials are deliberately added.
- Added the first BIBER model registry/provider abstraction checkpoint:
  - `app/model_registry.py` and `src/biber_api/model_registry.py` define a
    config-driven registry for logical BIBER model IDs.
  - Default stable logical model: `biber-dev-core-v1`, backed by the existing
    local vLLM served model `biber-dev-core` and upstream
    `Qwen/Qwen2.5-Coder-7B-Instruct`.
  - Default candidate logical model: `biber-dev-core-v2-candidate`, disabled
    until a Qwen3-Coder/Qwen3-Coder-Next or newer endpoint is configured and
    benchmarked.
  - `/v1/models` now returns stable/candidate model metadata instead of only
    static model-name strings.
  - `/v1/chat` resolves requested logical model IDs through the registry and
    returns the resolved logical model ID in the response.
  - Backward-compatible alias: requests for `biber-dev-core` resolve to
    `biber-dev-core-v1`.
  - Local Python verification passed with `pytest`: `31` tests.
  - Vast checkout was fast-forwarded to `328ab3f`.
  - Vast syntax verification passed with `/venv/main/bin/python -m compileall
    app src tests training`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `14815`.
  - `bash scripts/vast_test_direct.sh` passed. `/v1/chat` returned
    `model="biber-dev-core-v1"` and `mentor_used=false`.
  - Live `/v1/models` now reports `biber-dev-core-v1` as stable/enabled backed
    by provider model `biber-dev-core`, and `biber-dev-core-v2-candidate` as a
    disabled candidate for future Qwen3/newer-model evaluation.
- Added selected-file repo context for the BIBER MVP:
  - `app/repo_context.py` and `src/biber_api/repo_context.py` provide bounded
    selected-file context ingestion for `/v1/chat`.
  - Request field: `repo_context_paths`, with workspace-relative file paths.
  - The context loader rejects paths outside the configured repo root, obvious
    secret paths such as `.env`, private-key-looking files, binary-looking
    files, and common cache/VCS directories.
  - Context is bounded by `BIBER_REPO_CONTEXT_MAX_FILES`,
    `BIBER_REPO_CONTEXT_MAX_BYTES_PER_FILE`, and
    `BIBER_REPO_CONTEXT_MAX_TOTAL_BYTES`.
  - This is intentionally not full RAG or automatic repo crawling. It is the
    minimal repo-aware step before file edit/test execution workflows.
  - Local Python verification passed with `pytest`: `38` tests.
  - Vast checkout was fast-forwarded to `7e66a7f`.
  - Vast syntax verification passed with `/venv/main/bin/python -m compileall
    app src tests training`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `15053`.
  - `bash scripts/vast_test_direct.sh` passed. `/v1/chat` returned
    `model="biber-dev-core-v1"` and `mentor_used=false`.
  - Live repo-context smoke passed: a valid `repo_context_paths=["README.md"]`
    request returned from `biber-dev-core-v1`, and an absolute path was rejected
    with HTTP `400` and `Repo context path must be workspace-relative`.
- Started and expanded the Rust private-devnet prototype workspace:
  - workspace path: `xriq/`.
  - implemented crates:
    - `xriq/crates/xriq-core`
    - `xriq/crates/xriq-consensus`
    - `xriq/crates/xriq-ledger`
    - `xriq/crates/xriq-mempool`
    - `xriq/crates/xriq-node`
    - `xriq/crates/xriq-rpc`
    - `xriq/crates/xriq-storage`
    - `xriq/crates/xriq-wallet`
  - implemented dependency-free private-devnet primitives for checked
    `XriqAmount`, validated devnet `Address`, `Hash32`, basic transaction
    validation, and block-header validation.
  - implemented account ledger state transitions for balances, nonces, minimum
    fees, fee-sink crediting, and atomic mutation.
  - implemented deterministic mempool checks for duplicate transaction hashes,
    duplicate account nonces, minimum fee, zero amount, removal, and
    fee/order/hash ordering.
  - implemented deterministic single-authority block production with parent
    checks, explicit roots, signature requirement, transaction cap enforcement,
    and mempool-based transaction selection.
  - implemented dependency-free local RPC endpoint behavior for health, chain
    status, account lookup, mempool listing, pending transaction lookup, and
    transaction submission.
  - implemented local block storage and a minimal node loop for transaction
    submission, block production, ledger application, mempool cleanup, block
    persistence, replay startup from persisted canonical blocks, and
    RPC-visible state.
  - implemented private-devnet wallet CLI baseline for deterministic test
    identity generation and transfer draft construction.
  - latest local validation passed: `cd xriq && cargo fmt --check && cargo test`.
  - latest local Rust test result: `56` passed.
  - latest local clippy validation passed:
    `cd xriq && cargo clippy -- -D warnings`.
  - latest Vast Rust validation passed with the toolchain stored under
    `/workspace`: `cargo fmt --check`, `cargo test` with `56` passing tests,
    `cargo clippy -- -D warnings`, and wallet CLI `key generate`/`transfer`
    smokes.
  - Installed the `clippy` Rust component into `/workspace/.rustup` and updated
    `scripts/vast_install_rust_toolchain.sh` so future Rust setup includes it.
  - No Vast GPU/model training was needed for this step.

## Live Vast.ai Deployment Status

- Host: `70.30.158.46`
- SSH port: `61995`
- SSH key path on this workstation: `C:\Users\vselv\.ssh\biber_vast_ed25519`
- Remote repo path: `/workspace/biber-ai-platform`
- Runtime root: `/workspace`
- Storage:
  - `/workspace` is mounted from `/dev/md0[/volumes/V.36840046/_data]`
    as XFS.
  - Size at last check: `499G`, used `31G`, available `469G`.
  - BIBER runtime, model cache, venv, pip cache, logs, pid files, future
    datasets, checkpoints, adapters, and outputs should stay under
    `/workspace` to use the 500 GB Vast volume and avoid the small root
    filesystem.
- Virtualenv: `/workspace/biber-venv`
- Logs:
  - `/workspace/biber-logs/vllm.log`
  - `/workspace/biber-logs/api.log`
- Pid files:
  - `/workspace/biber-pids/vllm.pid`
  - `/workspace/biber-pids/api.pid`
- vLLM:
  - URL: `http://127.0.0.1:8001/v1`
  - Model: `Qwen/Qwen2.5-Coder-7B-Instruct`
  - Base served model name: `biber-dev-core-base`
  - LoRA adapter model name: `biber-dev-core`
  - LoRA modules:
    `biber-dev-core=/workspace/adapters/biber-dev-core-lora-rust-xriq-400`
  - Tensor parallel size: `2`
  - Max model length: `8192`
  - Current pid at last confirmed check: `1558`
- BIBER FastAPI:
  - URL: `http://127.0.0.1:8000`
  - Environment: `gpu`
  - Chat mode: `infer`
  - Local model name: `biber-dev-core`
  - Current pid at last confirmed check: `1914`
  - Run `bash scripts/vast_status_direct.sh` for current PIDs and bind details.
- Persistent training/output directories created on the 500 GB volume:
  - `/workspace/data`
  - `/workspace/checkpoints`
  - `/workspace/adapters`
  - `/workspace/outputs`
  - `/workspace/.cargo`
  - `/workspace/.rustup`
- Current generated artifact sizes at last check:
  - `/workspace/data`: `3.2M`
  - `/workspace/.cargo`: `20M`
  - `/workspace/.rustup`: `594M`
  - `/workspace/.hf_home`: `15G`
  - `/workspace/outputs`: `304K`
  - `/workspace/adapters`: `3.5G`
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`: `896M`, trained
    and served successfully.
  - `/workspace/adapters/biber-dev-core-lora-targeted-350`: `896M`
  - `/workspace/adapters/biber-dev-core-lora-codeinstruct-998`: `896M`
  - `/workspace/adapters/biber-dev-core-lora`: `409M`
  - `/workspace/adapters/biber-dev-core-lora-smoke`: `409M`
- Current Rust/XRIQ adapter contents should include:
  - `adapter_model.safetensors`: `155M`
  - `adapter_config.json`
  - `tokenizer.json`: `11M`
  - `chat_template.jinja`
  - checkpoints including `checkpoint-50`, `checkpoint-75`, and
    `checkpoint-100`

## Custom Model Training Prep

- A conservative QLoRA training path is now working on the user's own GPU.
  It is meant to keep Codex usage low: Codex prepares and verifies scripts, then
  long fine-tuning runs happen inside `tmux` on Vast.ai.
- Real training data should live on the 500 GB Vast volume at:
  - `/workspace/data/biber_train.jsonl`
- Do not commit real datasets, checkpoints, adapters, or evaluation outputs to
  Git. Keep generated model artifacts under:
  - `/workspace/checkpoints`
  - `/workspace/adapters`
  - `/workspace/outputs`
- Dataset format and validation notes are in `training/dataset_format.md`.
- The tiny `training/sample_dataset.jsonl` file is only for smoke tests.
- Dataset validation entrypoint:

```bash
cd /workspace/biber-ai-platform
/workspace/biber-venv/bin/python training/validate_dataset.py \
  --dataset /workspace/data/biber_train.jsonl \
  --min-records 10 \
  --report /workspace/outputs/dataset-validation.json \
  --print-sample
```

- QLoRA dry-run entrypoint for script/dataset plumbing:

```bash
cd /workspace/biber-ai-platform
/workspace/biber-venv/bin/python training/qlora_train_biber_dev_core.py \
  --dataset training/sample_dataset.jsonl \
  --output-dir /workspace/adapters/dry-run \
  --logging-dir /workspace/outputs/dry-run \
  --dry-run
```

- Long training launcher:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_train_qlora_tmux.sh /workspace/data/biber_train.jsonl
```

- Install `requirements-training.txt` only when preparing an actual training
  run. It intentionally avoids replacing Torch/CUDA by default; preserve the
  working vLLM CUDA stack unless a compatibility issue requires a planned
  change.
- Real starter fine-tuning has completed once. The next training milestone is to
  grow or improve the approved dataset, validate it, then launch a longer QLoRA
  run in `tmux` when the user is ready to spend the GPU time.
- Verified on Vast after pulling `8ae20ad`: compile, sample dataset validation,
  QLoRA dry-run, and `tests/test_training_dataset.py` all passed under
  `/workspace/biber-venv`.
- Internet-sourced training data must use the approved-source ingestion
  pipeline, not broad scraping:
  - manifest: `training/approved_sources.json`
  - script: `training/internet_ingest.py`
  - Vast helper: `scripts/vast_ingest_internet_dataset.sh`
  - raw downloads: `/workspace/data/raw`
  - processed JSONL: `/workspace/data/biber_train_internet.jsonl`
  - provenance: `/workspace/outputs/dataset-provenance.json`
  - validation report: `/workspace/outputs/internet-dataset-validation.json`
- The ingestion pipeline requires each enabled source to be explicitly
  `approved`, license-allowlisted, domain-allowlisted, and attributed. It also
  deduplicates records, filters likely secrets, caps record size, and validates
  the final JSONL before use.
- The current enabled internet sources are the small project-owned smoke
  dataset, the project-owned targeted eval dataset, the project-owned
  Rust/XRIQ targeted dataset, and a bounded 1000-record cap from
  `SoyMaycol/CodeInstruct-20K`. Increase real approved source limits only after
  reviewing license/provenance and storage impact.
- The tracked source file `training/targeted_rust_xriq_dataset.jsonl` now has
  `16` validated project-owned Rust/XRIQ records after adding HashSet-focused
  examples. The canonical `/workspace/data/biber_train.jsonl` was not
  regenerated for this follow-up because the existing live adapter passed the
  tightened Rust/XRIQ eval without another training run.
- Only promote an internet-ingested dataset to `/workspace/data/biber_train.jsonl`
  after reviewing provenance and validation output.
- Current canonical dataset: `/workspace/data/biber_train.jsonl`
  - 1000 records
  - about 2.6M for `/workspace/data` overall
  - validated with 0 errors
  - provenance for its internet candidate:
    `/workspace/outputs/dataset-provenance-rust-xriq-targeted-codeinstruct-1000.json`
- Current trained adapter:
  `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`
  - produced by a 100-step, two-epoch QLoRA run over the first 400 records of
    the Rust/XRIQ-targeted 1000-record dataset.
  - last confirmed served live as `biber-dev-core`.
- Current broad live eval baseline after Rust/XRIQ profile refinement:
  - runner: `bash scripts/vast_eval_lora_direct.sh`
  - result: `18/18` responses, `18/18` simple expectation checks passed.
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260519T125356Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260519T125356Z.jsonl`
  - quality caveat: the current runner checks simple expected substrings or
    regexes. Treat the score as a regression signal, then add stronger
    execution/type/lint validators before trusting it as a quality score.
- Current Rust/XRIQ eval baseline after the codegen-profile follow-up:
  - runner: `bash scripts/vast_eval_rust_xriq_direct.sh`
  - result: `7/7` responses, `7/7` substring expectations, `7/7` cargo
    validators.
  - summary:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260519T125323Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260519T125323Z.jsonl`
  - the `rust_xriq_apply_ledger_transaction` prompt now uses
    `training/rust_xriq_codegen_profile.txt` by default, while the rest of the
    Rust/XRIQ eval remains unprefixed.
- The Rust/XRIQ adapter is the current confirmed live candidate: the adapter
  training improved the Rust/XRIQ cargo baseline from `2/6` to `5/6` while
  preserving the broad `18/18` regression baseline. After the HashSet source,
  eval-prompt, and targeted codegen-profile follow-ups, the current live path
  reaches `7/7` cargo validators. These follow-ups did not change model
  weights.
- The current serving process holds about 14 GB on each 16 GB GPU. Before
  starting another QLoRA run on this instance, stop the direct services with
  `bash scripts/vast_stop_direct.sh`, or run training on a separate GPU.

## Important Fixes Made During Deployment

### Bootstrap script execution

`scripts/vast_bootstrap_direct.sh` now starts services with:

```bash
exec bash "${SCRIPT_DIR}/vast_start_direct.sh"
```

This avoids `Permission denied` on filesystems where the checked-out script is
not executable.

### Shared venv dependency pins

The direct deployment shares one virtualenv between FastAPI and vLLM. The older
API pins downgraded packages below what vLLM `0.21.0` expects. The current API
requirements now include:

```text
fastapi==0.136.1
starlette==0.52.1
pydantic==2.13.4
```

Remote `pip check` passed after applying these pins.

### Loopback bind defaults

`scripts/lib/vast_direct_common.sh` defaults both services to loopback:

```text
BIBER_API_HOST=127.0.0.1
BIBER_VLLM_HOST=127.0.0.1
```

Set either host to `0.0.0.0` only after replacing the starter credentials and
intentionally exposing the instance.

## Moving To A New Vast GPU

Use this section when replacing the current Vast.ai GPU. The goal is to avoid
re-downloading or rebuilding large assets when the current GPU or its storage is
still reachable, while keeping the new instance reproducible from GitHub if the
current GPU is unavailable.

### If the current GPU is still available

1. First make GitHub authoritative for code:

```bash
cd /workspace/biber-ai-platform
git status --short --branch
git log --oneline -1
```

From this workstation, push any local commits before moving:

```powershell
cd C:\Users\vselv\OneDrive\Biber\biber-ai-platform
git push origin main
```

2. Rent the new Vast.ai GPU. Prefer the same OS/template family and enough disk
   space for the existing runtime, model cache, datasets, and checkpoints.

3. Bootstrap code on the new GPU from GitHub:

```bash
cd /workspace
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
```

4. Copy only state that saves real time or cannot be recreated. Important paths:

```text
/workspace/biber-ai-platform/.env     # secrets/config; copy carefully
/workspace/.hf_home                   # Hugging Face/model cache; saves download time
/workspace/pip-cache                  # optional; saves pip download time
/workspace/data                       # future datasets, if present
/workspace/checkpoints                # future training checkpoints, if present
/workspace/adapters                   # future LoRA/QLoRA adapters, if present
/workspace/outputs                    # future evaluation/training outputs, if present
```

Do not copy pid files:

```text
/workspace/biber-pids
```

Logs are optional:

```text
/workspace/biber-logs
```

5. Prefer Vast.ai's instance/volume copy tools or same-provider local network
   copy when available, because that can be faster and may avoid routing large
   transfers through this workstation.

If both old and new instances are reachable to Vast's copy service, use command
shapes like these with the actual Vast instance IDs:

```bash
vastai copy C.<OLD_INSTANCE_ID>:/workspace/.hf_home/ C.<NEW_INSTANCE_ID>:/workspace/.hf_home/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/pip-cache/ C.<NEW_INSTANCE_ID>:/workspace/pip-cache/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/data/ C.<NEW_INSTANCE_ID>:/workspace/data/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/checkpoints/ C.<NEW_INSTANCE_ID>:/workspace/checkpoints/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/adapters/ C.<NEW_INSTANCE_ID>:/workspace/adapters/
```

For a Vast 500 GB volume, remember that Vast volumes are local to the machine
where they were created. If the same machine can still be used, rent the new
instance using the existing volume. If moving to a different machine, create a
new destination volume/instance and copy data instead of assuming the old volume
can be attached directly:

```bash
vastai copy V.<OLD_VOLUME_ID>:/data/ V.<NEW_VOLUME_ID>:/data/
vastai copy V.<OLD_VOLUME_ID>:/data/ C.<NEW_INSTANCE_ID>:/workspace/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/ V.<NEW_VOLUME_ID>:/data/
```

If using manual SSH copy, run it from a Linux shell that can reach both
instances. Example shape:

```bash
rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/.hf_home/ /workspace/.hf_home/

rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/pip-cache/ /workspace/pip-cache/

rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/biber-ai-platform/.env /workspace/biber-ai-platform/.env
```

For training datasets/checkpoints, copy the relevant directories only if they
exist:

```bash
rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/data/ /workspace/data/

rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/checkpoints/ /workspace/checkpoints/

rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/adapters/ /workspace/adapters/
```

If a training job is actively writing checkpoints, stop or pause the job first,
or run `rsync` twice so the second pass catches changed files.

6. Start the new GPU direct deployment:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_bootstrap_direct.sh
bash scripts/vast_test_direct.sh
bash scripts/vast_status_direct.sh
```

7. Update this handoff immediately with the new host, SSH port, runtime paths,
PIDs, bind status, test result, and whether caches/datasets/checkpoints were
copied or rebuilt.

8. Keep the old GPU only until the new GPU is verified. After verification,
stop or destroy the old instance according to the user's cost/risk preference.
Remember: stopped storage can still cost money; destroyed instance storage is
not recoverable unless copied/backed up first.

### If the current GPU is not available

1. Treat the new GPU as a clean rebuild from GitHub:

```bash
cd /workspace
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
cp .env.example .env
```

2. Recreate `.env` from the user's secure password manager or prior private
backup. Do not paste secrets into chat or docs. Keep loopback values unless
public exposure is intentionally configured:

```text
BIBER_API_HOST=127.0.0.1
BIBER_VLLM_HOST=127.0.0.1
```

3. Rebuild runtime and re-download model cache:

```bash
bash scripts/vast_bootstrap_direct.sh
bash scripts/vast_test_direct.sh
bash scripts/vast_status_direct.sh
```

4. Restore datasets/checkpoints/adapters from whatever backup exists. If no
backup exists, assume training data/checkpoints on the unavailable GPU are lost
and continue from GitHub plus any local/cloud copies.

5. Update this handoff with the new state and explicitly mark which assets were
rebuilt, restored, or lost.

## Reconnect And Test

From Windows PowerShell:

```powershell
ssh -i C:\Users\vselv\.ssh\biber_vast_ed25519 -p 61995 root@70.30.158.46 -L 8080:localhost:8080 -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

Then open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8001/v1/models
http://127.0.0.1:8080
```

Do not paste private key contents, Vast API keys, Jupyter tokens, or `.env`
secrets into chat or docs.

## Useful Remote Commands

After SSH:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
bash scripts/vast_eval_lora_direct.sh
```

Restart only the BIBER direct services:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_stop_direct.sh
bash scripts/vast_start_lora_direct.sh
```

Start base-model-only serving, if adapter serving must be bypassed. The LoRA
start path persists `BIBER_VLLM_LORA_MODULES` in `.env`, so remove that line
before using the plain direct start:

```bash
cd /workspace/biber-ai-platform
sed -i '/^BIBER_VLLM_LORA_MODULES=/d' .env
BIBER_VLLM_SERVED_MODEL_NAME=biber-dev-core bash scripts/vast_start_direct.sh
```

Rerun bootstrap if the environment is partially missing:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_bootstrap_direct.sh
```

Follow logs:

```bash
tail -f /workspace/biber-logs/api.log
tail -f /workspace/biber-logs/vllm.log
```

## Important Config Notes

- `.env` exists on the Vast.ai instance.
- `.env` explicitly contains:
  - `BIBER_API_HOST=127.0.0.1`
  - `BIBER_VLLM_HOST=127.0.0.1`
  - `BIBER_LOCAL_MODEL_NAME=biber-dev-core`
  - `BIBER_VLLM_SERVED_MODEL_NAME=biber-dev-core-base`
  - `BIBER_VLLM_LORA_MODULES=biber-dev-core=/workspace/adapters/biber-dev-core-lora-rust-xriq-400`
- A redacted credential audit on 2026-05-16 showed the live `.env` still uses
  starter values for sensitive placeholders. Live rotation was not performed
  because changing running API credentials requires explicit user approval.
- Before public exposure, replace all starter credentials in `.env`:
  - `BIBER_ADMIN_PASSWORD`
  - `BIBER_DEMO_API_KEY`
  - `BIBER_API_KEYS`
  - `BIBER_PASSCODE_FULL_GPU`
  - `BIBER_PASSCODE_20_GPU`
  - `BIBER_PASSCODE_QUEUE_PRIORITY`
  - `BIBER_PRIORITY_PASSCODES`
  - `MYSQL_ROOT_PASSWORD`
  - `MYSQL_PASSWORD`
- The direct path currently starts:
  - `biber-dev-core-base` through vLLM as the base model.
  - `biber-dev-core` through vLLM as the LoRA adapter model.
  - BIBER FastAPI, configured to use `biber-dev-core`.
- Agent-session artifacts are local JSON files. `BIBER_AGENT_SESSION_DIR` is
  optional; when omitted on Vast, the API stores them under
  `/workspace/outputs/agent-sessions`.
- The direct path does not start MySQL, Redis, or Adminer.
- Optional integrations are currently not configured on the live instance:
  - OpenAI mentor
  - durable GitHub generated-code save credentials
  - Azure Blob backups

## Operating Notes For Future Codex Sessions

- Do not rotate live credentials routinely. Treat credential rotation as an
  explicit, infrequent operation that requires user approval and a plan for
  preserving the new secrets outside chat.
- Keep the deployment loopback-only while starter credentials remain in place.
- Cost-saving strategy: use Codex minimally for engineering setup, script
  changes, error diagnosis, evaluation/deployment glue, and handoff updates.
  Run long model work directly on the user's Vast.ai GPU instead of keeping a
  Codex session active. Start training, fine-tuning, batch evaluation, and other
  multi-hour jobs in `tmux`/`screen` on the GPU; disconnect while they run; bring
  Codex back only for failures, log review, result interpretation, or the next
  code/deployment change. Follow the explicit `Cost-Control Execution Policy`
  near the top of this handoff.
- Future custom-model phases should prefer the user's own GPU and eventual
  fine-tuned `biber-dev-core` model over paid external model APIs. Keep optional
  mentor APIs disabled unless the user explicitly wants them for quality review.
- Future BIBER API-key agent-client and mentor work is documented in
  `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md`. Treat BIBER as the default
  engine and OpenAI/Codex as an optional mentor/reviewer for architecture,
  security-sensitive Rust/crypto review, eval design, failure diagnosis, and
  curated training-data review.
- Repo-specific adaptation is documented in `docs/BIBER_REPO_ADAPTATION.md`.
  Use `training/repo_adaptation_plan.py` against the user's target GitHub repo
  first, run the generated eval prompts through the current served BIBER model,
  and fine-tune on Vast only after repeatable failures are converted into
  curated examples with a held-out eval set. Do not treat arbitrary repo source
  dumps as training data.
- Future Rust/XRIQ work is now an explicit project track documented in
  `docs/XRIQ_RUST_TRACK.md`. Treat it as a phased path: first prove BIBER's
  Rust capability with `cargo`-backed evals, then design XRIQ, then build a
  private Rust devnet, then wallet/explorer tools, and only later consider any
  public network or cryptocurrency launch after separate security and
  legal/compliance review.
- XRIQ legal-risk reduction is now a hard design guardrail documented in
  `docs/XRIQ_LEGAL_RISK_REDUCTION.md`. Do not implement or generate
  market-facing public token, DEX, custody, bridge, stablecoin, payment,
  airdrop, liquidity, listing, validator-yield, or investment-promotion features
  unless the required review status is explicitly recorded in docs.
- XRIQ privacy direction is now explicit in `docs/XRIQ_TECHNICAL_SPEC.md`,
  `docs/XRIQ_PHASE3_DECISIONS.md`, `docs/XRIQ_LEGAL_RISK_REDUCTION.md`, and
  `docs/XRIQ_RUST_TRACK.md`: keep the MVP transparent, reserve future
  Zcash-like selective privacy with viewing keys/payment disclosure/audit
  receipts, and avoid Monero-style mandatory privacy while DEX usability and
  AML-friendly posture remain goals.
- Near-term language priority is Rust/XRIQ first because the user's first major
  inference use case for BIBER AI is developing the XRIQ cryptocurrency
  blockchain. Defer .NET, Spring Boot Java, broader Python expansion, and other
  language-specific fine-tuning until Rust/XRIQ evals and private-devnet support
  are established, unless the user explicitly changes priority.
- Broader post-Rust capability order is now explicit in
  `docs/BIBER_CAPABILITY_ROADMAP.md`. After Rust/XRIQ, prioritize PostgreSQL,
  React, TypeScript, JavaScript, jQuery, CSS, HTML, Docker, GitHub Actions
  CI/CD, WASM, Bash scripts, security engineering, cryptography concepts,
  Kubernetes, distributed systems optimization, and TensorFlow/Keras ML
  engineering before lower-priority generic SQL, YAML, .NET, Spring Boot Java,
  Python expansion, or other stacks.
- TensorFlow is now explicitly in scope as a user-development capability track:
  BIBER should eventually help with TensorFlow/Keras model code, dataset
  preprocessing, training/evaluation scripts, GPU/CUDA troubleshooting,
  TensorBoard workflows, SavedModel export, and FastAPI-style inference APIs.
  This does not change BIBER's own model-training stack; keep BIBER's own
  near-term model path on Qwen/vLLM plus targeted LoRA/QLoRA on Vast.ai.
- Apply the capability roadmap through inference/evals first and targeted GPU
  fine-tuning only for repeatable gaps. This preserves the cost-saving strategy:
  Vast.ai does the long GPU work, while Codex is used only where it preserves
  quality and momentum.
- Update this handoff at important points so a new Codex session can resume
  accurately from the current Vast.ai state. Important points include:
  - live service restarts or failures
  - host, SSH port, key path, runtime path, pid, or log path changes
  - Git commit/branch/remote state changes
  - dependency, model, port, bind, or environment changes
  - smoke test, runtime test, mentor, GitHub save, Azure backup, MySQL, or Redis
    status changes
  - credential status changes, without recording secret values

## Recommended Next Steps

Active Phase 1 override as of 2026-05-26: while the user is asking to continue
the current project, treat "the project" as XRIQ private-devnet Phase 1 only.
Do not follow BIBER MVP, Vast, adapter, runtime-profile, model-training, or
candidate-promotion steps in this section unless the user explicitly resumes
Phase 2. Phase 1 private-devnet RC1 has now been approved, tagged, and pushed
as `phase1-xriq-private-devnet-rc1` at commit `688bf913`. Do not recreate or
move the RC1 tag unless the user explicitly requests a corrective tag operation.
The pre-tag command with `--require-rc-tag-available` should now report that
the RC1 tag already exists; that is expected after a successful tag. For any
post-RC Phase 1 patch, keep using
`python scripts/xriq_phase1_local_check.py` as the one-command CPU-only
verification gate before handoff/commit/push. Use
`docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md` as the go/no-go checklist for deciding
whether a future post-RC patch should become a new tag such as RC2; if RC2 is
needed, add a deliberate RC2 readiness/tag step instead of moving RC1. Public
XRIQ and BIBER MVP remain deferred unless the user explicitly starts Phase 2.

Historical Phase 2/BIBER notes remain below for later reference only. Ignore
any "current immediate next step" language below while Phase 1 override remains
active.

Current immediate next step: continue narrow BIBER MVP client workflow work on
top of the stable adapter. The latest v4 retry prompt/context was
rule-prioritized and compact, but the local model still repeated the forbidden
edit in JSON. Do not keep rerunning the same retry prompt and do not plan/apply
any repeated-edit extraction artifact. The next useful code step is to add a
small model-gap review/export helper for repeated-forbidden retry attempts,
capturing the repair prompt, forbidden edit, model JSON, model prose, and guard
rejection as review-only eval/training evidence. Keep it non-trainable until
human review and dataset validation. Use the offline repair-attempt inspection
path if repair artifacts need review:
`show-repair-attempt`,
`list-repair-attempts`, `extract-repair-edits`,
`show-repair-edit-extraction`, `list-repair-edit-extractions`, then
`plan-repair-edits`, `show-repair-edit-plan`, `list-repair-edit-plans`, then
`apply-repair-edits --approve` only after review, `show-repair-edit-apply`,
`list-repair-edit-applies`, then `verify-repair-edits`,
`show-repair-test-verification`, `list-repair-test-verifications`, and finally
`export-verified-repair`, `review-verified-repairs`,
`show-verified-repair-review`, `list-verified-repair-reviews`, then the
existing `show-repair-chain` / `list-repair-chains` review path,
`export-ready-repair-chains`, `review-ready-repair-chains`,
`show-ready-repair-chain-review`, `list-ready-repair-chain-reviews`, then
manual decision recording only after review,
`review-ready-repair-chain-decisions`,
`show-ready-repair-chain-decision-review`,
`list-ready-repair-chain-decision-reviews`, then
`export-ready-repair-chain-eval-candidates` only for explicit
`approve_for_eval` decisions, `review-ready-repair-chain-eval-candidates`,
`show-ready-repair-chain-eval-candidate-review`, and
`list-ready-repair-chain-eval-candidate-reviews`, then manual dataset-review
decision recording only after review,
`review-ready-repair-chain-eval-dataset-decisions`,
`show-ready-repair-chain-eval-dataset-decision-review`, and
`list-ready-repair-chain-eval-dataset-decision-reviews`, then final
eval-dataset export only after review, `validate-ready-repair-chain-eval-dataset`,
`show-ready-repair-chain-eval-dataset-validation`, and
`list-ready-repair-chain-eval-dataset-validations`, then held-out eval prompt
export only after validation inspection with
`export-ready-repair-chain-eval-prompts`, followed by
`show-ready-repair-chain-eval-prompts` and
`list-ready-repair-chain-eval-prompts`, then a live held-out eval run through
`scripts/vast_eval_repair_chain_prompts_direct.sh` when needed, then
`review-repair-chain-heldout-eval-results`, followed by
`show-repair-chain-heldout-eval-review` and
`list-repair-chain-heldout-eval-reviews` before any manual held-out eval
decision is recorded, then `record-repair-chain-heldout-eval-decision`,
`review-repair-chain-heldout-eval-decisions`,
`show-repair-chain-heldout-eval-decision-review`, and
`list-repair-chain-heldout-eval-decision-reviews` before any baseline-candidate
export. Do not train again and do not promote
from a generic "continue". The API error-response and Rust/XRIQ codegen profiles
are enabled on the live Vast API, exposed through
`/v1/agent/capabilities`, and the stable served adapter has passed the
profile-enabled client/eval baseline. If model promotion is desired, ask the
user for explicit candidate-promotion approval using
`/workspace/outputs/evals/profiled-antireg-candidate-20260521T0315Z/profiled-candidate-promotion-review.json`.
Serving must remain on `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`
unless the user explicitly approves candidate promotion.

1. Keep `/workspace/adapters/biber-dev-core-lora-rust-xriq-400` served unless a
   future adapter beats both gates: current Rust/XRIQ cargo validators and the
   broad regression eval.
2. Reconnect and verify current service state with:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
```

3. If serving is not on the broad-safe adapter, restore it:

```bash
cd /workspace/biber-ai-platform
BIBER_LORA_ADAPTER_DIR=/workspace/adapters/biber-dev-core-lora-rust-xriq-400 \
  bash scripts/vast_start_lora_direct.sh
bash scripts/vast_test_direct.sh
```

4. Treat runtime profiles as the current low-cost path for this narrow model
   gap. They are now enabled live with `BIBER_RUNTIME_PROFILES_ENABLED=true`;
   verify with `bash scripts/vast_runtime_profile_smoke.sh` after API restarts,
   or run the full stable baseline with
   `bash scripts/vast_profile_baseline_direct.sh` after serving or profile
   contract changes. Do not promote the profiled candidate without explicit
   user approval.
5. If a future Rust/XRIQ eval regresses, prefer a deterministic repair loop
   before GPU training: run `cargo fmt`, `cargo check`, and targeted tests,
   feed the concise compiler/test failure back to the local model, and save
   only reviewed failures as future training/eval candidates.
6. Run the two current evals after any serving change:

```bash
cd /workspace/biber-ai-platform
BIBER_EVAL_FAIL_ON_VALIDATORS=0 bash scripts/vast_eval_rust_xriq_direct.sh
bash scripts/vast_eval_lora_direct.sh
```

7. Promote a new adapter only if it improves beyond the current served baseline:
   at least `7/7` current Rust/XRIQ cargo validators and `18/18` broad
   expectation checks.
8. If a future training run fails, inspect the QLoRA log and do not leave an
   unverified adapter served. Restore `biber-dev-core-lora-rust-xriq-400` unless
   a better verified candidate exists.
9. If the current Vast instance is unavailable, follow the
   `Moving To A New Vast GPU` section. Prefer attaching or copying the existing
   500 GB volume/state if it is still available; otherwise rebuild from GitHub
   and regenerate datasets from the approved sources.
10. Update this handoff immediately after SSH is restored, training finishes,
   serving restarts, evals complete, or the instance is moved.
11. After future local XRIQ prototype changes, fast-forward the Vast checkout
   and rerun Rust validation there:

```bash
cd /workspace/biber-ai-platform
git pull --ff-only origin main
cd xriq
export RUSTUP_HOME=/workspace/.rustup
export CARGO_HOME=/workspace/.cargo
export PATH=/workspace/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cargo fmt --check
cargo test -j 1
cargo clippy -- -D warnings
cd /workspace/biber-ai-platform
bash -n scripts/xriq_private_devnet_smoke.sh
bash scripts/xriq_private_devnet_smoke.sh
```

12. Treat these as first-class BIBER MVP/Replit-replacement workflow goals
   before broad language expansion:
   - More reliable repo-context selection: detect project type, include
     relevant manifests/config/tests/changed files, support pinned files, and
     avoid secrets, dependency folders, build outputs, and binaries. The first
     deterministic planner endpoint, `POST /v1/repo/context/plan`, is now
     implemented and Vast-verified. It now also returns `.NET` and Java stack
     profiles and selects common stack entrypoints when present.
   - Safer multi-file editing: produce an edit plan, enforce workspace/path
     bounds, limit touched files, apply patch-style changes, and run formatting
     or targeted tests after edits. The first no-write multi-file planner
     endpoint, `POST /v1/files/edit/plan`, is now implemented and
     Vast-verified. The first hash-gated apply endpoint,
     `POST /v1/files/edit/apply`, is also implemented and Vast-verified. The
     stdlib agent client now wraps both with `plan-edit` and `apply-edit`.
   - Better test-failure diagnosis loops: parse failures for `.NET`, Java,
     Rust, Node/React, and Python incrementally; classify compile/test/config
   failures; extract concise model context; rerun targeted tests; and save
   useful failure/fix pairs as future eval or training candidates. The first
   deterministic diagnosis endpoint, `POST /v1/tests/diagnose`, is now
   implemented and Vast-verified. The stdlib agent client now wraps it with
   `diagnose-test` and can attach it automatically to failed `run-test`
    output. The stdlib agent client also has `prepare-repair`, which converts a
    failed `mvp-loop` artifact into a bounded local-model repair request with
    `training_allowed=false`, and `attempt-repair`, which sends that bounded
    request to the local BIBER model through `/v1/chat` with mentor disabled by
    default and saves an inspectable proposal without applying edits.
    `attempt-repair` now accepts either the original failed `mvp-loop` artifact
    or the prepared `prepare-repair` artifact. `mvp-loop` can now record
    runtime profile IDs and repair attempts inherit those profiles unless
    explicitly overridden. It also
    has `extract-repair-edits`, which parses conservative JSON edit candidates
    from a repair-attempt artifact into a reviewable `plan-edit` payload while
    keeping `apply_allowed=false`, and `plan-repair-edits`, which sends that
    payload through the server-side planner without applying changes. It now
    also has `apply-repair-edits`, which applies a planned repair only when the
    caller passes `--approve`; without that flag it refuses before API auth or
    file changes, and `verify-repair-edits`, which reruns the selected
    allowlisted test from the approved apply artifact without saving or training
    from the result, plus `export-verified-repair`, which writes a JSONL
    human-review record from a passed verification while keeping
    `eligible_for_training=false`, and `review-verified-repairs`, which
    summarizes one or more verified-repair JSONL queues without promoting them.
    The stdlib agent client also has `show-repair-chain`, which summarizes the
    whole saved repair-artifact sequence and marks it only as
    `ready_for_human_review`; it keeps `safe_to_train=false` and
    `github_save_ready=false`. It also has `list-repair-chains`, which scans a
    directory for saved repair-chain summaries so future sessions can find
    ready-for-review chains without rerunning model calls, and
    `export-ready-repair-chains`, which exports those ready chains to a JSONL
    human-review queue while still blocking automatic training and GitHub save
    readiness. It also has `review-ready-repair-chains`, which summarizes one
    or more ready repair-chain JSONL queues without promoting them, and
    `record-ready-repair-chain-decision`, which records a human
    defer/reject/approve-for-eval decision while still blocking automatic
    training and GitHub save promotion. It also has
    `review-ready-repair-chain-decisions`, which summarizes those human
    decision queues while keeping `safe_to_train=false`, and
    `export-ready-repair-chain-eval-candidates`, which exports only
    `approve_for_eval` decisions into eval candidates while still requiring
    dataset review and blocking training. It also has
    `review-ready-repair-chain-eval-candidates`, which summarizes those eval
    candidate queues while keeping `eval_dataset_ready=false`. It also has
    `show-ready-repair-chain-eval-candidate-review` and
    `list-ready-repair-chain-eval-candidate-reviews`, which inspect saved
    eval-candidate review artifacts offline without API auth before any
    dataset-review decision is recorded. It also has
    `record-ready-repair-chain-eval-candidate-decision`, which records a
    manual dataset-review decision and can mark eval-dataset readiness while
    still blocking training and GitHub save promotion, and
    `review-ready-repair-chain-eval-dataset-decisions`, which summarizes those
    eval-dataset decision queues before any final eval-dataset export while
    keeping training and GitHub save blocked. It also has
    `show-ready-repair-chain-eval-dataset-decision-review` and
    `list-ready-repair-chain-eval-dataset-decision-reviews`, which inspect
    saved eval-dataset decision review artifacts offline without API auth
    before final eval-dataset export. It now also has
    `export-ready-repair-chain-eval-dataset`, which exports only approved
    eval-dataset decisions into a validation-only eval-dataset JSONL while
    keeping training and GitHub save blocked, and
    `validate-ready-repair-chain-eval-dataset`, which validates that exported
    queue's safety/provenance fields while still keeping it out of training.
    It also has `show-ready-repair-chain-eval-dataset-validation` and
    `list-ready-repair-chain-eval-dataset-validations`, which inspect saved
    validation artifacts offline without API auth before held-out prompt
    export. It now also has `export-ready-repair-chain-eval-prompts`, which turns
    validated eval-dataset rows into live-eval-compatible held-out prompts
    while keeping them out of training and GitHub-save paths, plus
    `show-ready-repair-chain-eval-prompts` and
    `list-ready-repair-chain-eval-prompts`, which inspect those prompt JSONL
    queues offline before any live held-out eval run. Vast now also
    has `scripts/vast_eval_repair_chain_prompts_direct.sh`, which finds the
    latest exported repair-chain held-out prompt JSONL under `/workspace`
    outputs and runs it through `training/live_model_eval.py`. It now also has
    `review-repair-chain-heldout-eval-results`, which reviews those live-eval
    result JSONL artifacts and optional summary JSON without making them
    training-eligible, plus `show-repair-chain-heldout-eval-review` and
    `list-repair-chain-heldout-eval-reviews`, which inspect saved held-out eval
    review artifacts offline before any manual decision is recorded, and
    `record-repair-chain-heldout-eval-decision`, which
    records defer/reject/accept-for-baseline decisions while still blocking
    training, GitHub save, and automatic model promotion. It also has
    `review-repair-chain-heldout-eval-decisions`, which summarizes those
    decision JSONL queues without enabling training, GitHub save, or model
    promotion, plus `show-repair-chain-heldout-eval-decision-review` and
    `list-repair-chain-heldout-eval-decision-reviews`, which inspect saved
    decision-review artifacts offline before any baseline-candidate export. It
    also has
    `export-repair-chain-heldout-baseline-candidates`, which exports only
    `accept_for_baseline` held-out eval decisions into a baseline-candidate
    JSONL queue while still blocking training, GitHub save, and automatic model
    promotion. It also has
    `review-repair-chain-heldout-baseline-candidates`, which summarizes those
    baseline-candidate queues while still blocking training, GitHub save, and
    automatic model promotion, plus
    `show-repair-chain-heldout-baseline-candidate-review` and
    `list-repair-chain-heldout-baseline-candidate-reviews`, which inspect saved
    baseline-candidate review artifacts offline before any baseline-candidate
    decision is recorded. It also has
    `record-repair-chain-heldout-baseline-candidate-decision`, which records a
    manual defer/reject/approve-as-baseline decision while still blocking
    training, GitHub save, and automatic model promotion. It also has
    `review-repair-chain-heldout-baseline-decisions`, which summarizes those
    baseline-decision queues while still blocking training, GitHub save, and
    automatic model promotion, plus
    `show-repair-chain-heldout-baseline-decision-review` and
    `list-repair-chain-heldout-baseline-decision-reviews`, which inspect saved
    baseline-decision review artifacts offline before any training-readiness
    review. It also has
    `review-repair-chain-training-readiness`, which summarizes one or more
    held-out baseline decision-review artifacts and reports explicit training
    blockers while still keeping training, GitHub save, and model promotion
    blocked, plus `show-repair-chain-training-readiness` and
    `list-repair-chain-training-readiness`, which inspect saved
    training-readiness artifacts offline before any training-candidate export.
    It also has `export-repair-chain-training-candidates`, which
    writes only human-review candidate rows from a passing readiness gate. The
    rows keep `output` empty and `quality=needs_review`, so they are not a
    trainable dataset until a reviewer fills verified answers and validates the
    final JSONL. It also has `review-repair-chain-training-candidates`, which
    summarizes those candidate queues and reports whether any filled
    reviewed/verified rows are ready for dataset validation while still keeping
    training and model promotion blocked, plus
    `show-repair-chain-training-candidate-review` and
    `list-repair-chain-training-candidate-reviews`, which inspect saved
    candidate-review artifacts offline before any pipeline or dataset
    validation decision. It also has
    `review-repair-chain-training-pipeline`, which reads the standard
    repair-chain training artifacts from one smoke/output directory and reports
    the current missing or blocked step without resolving API auth or starting
    training, plus `show-repair-chain-training-pipeline`, which inspects saved
    pipeline status artifacts offline without recomputing the review. It also
    has `list-repair-chain-training-pipelines`, which scans
    output directories for saved pipeline status artifacts and reports how many
    are blocked versus ready for dataset validation.
   - Stack-specific test execution: keep execution allowlisted and predictable.
     The test runner now exposes `dotnet-test`, `maven-test`, `gradle-test`,
     and `gradle-wrapper-test` for target repos that already include the
     matching project files and toolchains. The stdlib agent client now wraps
     test discovery and execution with `list-tests` and `run-test`.
   - GitHub save/PR workflow: keep GitHub operations explicit and server-side
     credential gated. The stdlib agent client now wraps save and draft PR
     creation with `save-github` and `create-pr`, while GitHub remains disabled
     on the current Vast service until credentials are deliberately configured.
   - End-to-end MVP client loop: keep orchestration thin and inspectable. The
     stdlib agent client now has `mvp-loop`, which chains context planning,
     optional edit planning/apply, optional allowlisted test execution,
     deterministic diagnosis, and optional GitHub save/PR using only existing
     safe API endpoints.
13. Continue the XRIQ private-devnet prototype after the Rust/XRIQ model loop is
   stable. `xriq/` is already the separate Rust workspace inside this repo, and
   it is preferred over creating a second top-level Rust workspace unless the
   project later needs independent release/versioning. The next protocol target
   after `xriq-core`, `xriq-ledger`, `xriq-mempool`, `xriq-consensus`,
   `xriq-rpc`, `xriq-storage`, `xriq-node`, `xriq-wallet`, and
   `xriq-explorer`, canonical hash API wiring, genesis/root strategy,
   deterministic replay startup, the local `xriq-node status`,
   `xriq-node produce-transfer-block`, `xriq-node produce-draft-block`,
   `xriq-node explorer-overview`, `xriq-node block-detail`,
   `xriq-node account-detail`, `xriq-node mempool-detail`, and
   `xriq-node transaction-detail` runner commands,
   `scripts/xriq_private_devnet_smoke.sh`,
   `xriq-node serve-readonly`, `xriq-node serve-private`, and
   durable pending HTTP state, pending-block production, and
   `xriq-node preflight-transfer`, is to keep the local file-backed workflow
   small and deterministic. The thin BIBER preflight wrapper and read wrappers
   for status/explorer/block/account/transaction/mempool are now done, and
   `scripts/vast_xriq_api_smoke.sh` provides a consolidated live API smoke
   that follows block transaction hashes into transaction detail and checks the
   snapshot wrapper through safe staging import. The
   status state-root marker, deterministic replay smoke, the first allowlisted
   BIBER test-execution API slice, and bounded workspace-edit API slice are now
   done. The branch-aware GitHub save plus draft-PR path, a small BIBER MVP
   end-to-end agent smoke, the tracked agent-session endpoint, and the
   file-backed persisted agent-session artifact layer are now implemented and
   Vast-verified. XRIQ private-devnet snapshot export/import is also
   implemented and Vast-verified for cheap chain/pending state moves, with the
   thin BIBER API wrapper, snapshot discovery endpoints, and consolidated
   private-devnet overview endpoint now live. The minimal stdlib client and
   same-origin browser dashboard for the BIBER/XRIQ private-devnet overview,
   snapshot, preflight-transfer, transaction-detail, and account-detail
   endpoints are now also implemented and Vast-verified. The tracked BIBER
   agent-session flow can now opt into XRIQ private-devnet overview context
   before chat, and client tools can discover agent capabilities and the
   `xriq_private_devnet_review` request template through
   `GET /v1/agent/capabilities`. The stdlib
   `scripts/biber_agent_client.py` helper can now consume capabilities and
   create sessions from presets. Repo-specific adaptation now has a conservative
   metadata/eval scaffold in `training/repo_adaptation_plan.py`, a live
   eval-run wrapper in `training/repo_adaptation_eval.py`, and docs in
   `docs/BIBER_REPO_ADAPTATION.md`; use them against the user's actual target
   GitHub repo before considering Vast fine-tuning. The first repo-context
   planner endpoint, no-write multi-file edit-plan endpoint, and deterministic
   test-failure diagnosis endpoint are live. Failed/timed-out agent-session
   test steps now embed that diagnosis in the persisted session artifact. The
   test runner now includes `.NET` and Java stack IDs for target repos. The
   repo-context planner now exposes `.NET` and Java stack profiles. The
   hash-gated multi-file edit apply endpoint is live, and the stdlib agent
   client can now plan/apply those edits through the real API. The stdlib agent
   client can also list/run allowlisted tests and diagnose test failures through
   the real API, and it now wraps GitHub save/draft-PR workflow commands while
   leaving credentials server-side. The stdlib client now has `mvp-loop` as a
   single inspectable wrapper over the MVP repo workflow, plus
   `prepare-repair` and `attempt-repair` to turn failed loop artifacts into
   local-model repair proposals without approving them for training or applying
   edits automatically. It now also has `extract-repair-edits`, which creates a
   bounded `plan-edit` payload from conservative JSON repair proposals while
   keeping direct apply disabled, and `plan-repair-edits`, which validates that
   payload through the server-side edit planner without applying changes. It
   now also has `apply-repair-edits`, which applies only a successful planned
   repair artifact and only when the caller passes `--approve`, plus
   `verify-repair-edits`, which reruns the selected allowlisted test and
   records a no-save/no-training verification artifact, plus
   `show-repair-test-verification` and `list-repair-test-verifications`, which
   inspect saved verification artifacts without resolving API auth, and
   `export-verified-repair`, which exports a passed verification into a JSONL
   human-review queue without training eligibility, and
   `review-verified-repairs`, which summarizes those queues for human review
   while keeping them out of training, plus `show-verified-repair-review` and
   `list-verified-repair-reviews`, which inspect saved review-summary
   artifacts without resolving API auth. It now also has `show-repair-chain`,
   which summarizes the full saved repair-artifact chain and confirms whether
   it is ready for human review while still blocking automatic training or
   GitHub save readiness, and `list-repair-chains`, which scans saved artifact
   directories for ready repair-chain summaries without resolving API auth. It
   also has `export-ready-repair-chains`, which exports those ready summaries
   to a JSONL human-review queue while keeping `training_allowed=false`,
   `safe_to_train=false`, and `github_save_ready=false`, plus
   `review-ready-repair-chains`, which summarizes those queues while keeping
   them out of training and GitHub-save paths, plus
   `show-ready-repair-chain-review` and `list-ready-repair-chain-reviews`,
   which inspect saved ready repair-chain review summaries without resolving
   API auth, and
   `record-ready-repair-chain-decision`, which records manual
   defer/reject/approve-for-eval decisions without making the chain eligible
   for training or GitHub save, and `review-ready-repair-chain-decisions`,
   which summarizes those decision queues before any future eval-dataset
   curation, plus `show-ready-repair-chain-decision-review` and
   `list-ready-repair-chain-decision-reviews`, which inspect saved
   decision-review summaries without resolving API auth, plus
   `export-ready-repair-chain-eval-candidates`, which exports
   only `approve_for_eval` decisions as eval candidates while keeping
   `eval_dataset_ready=false` and `training_allowed=false`, plus
   `review-ready-repair-chain-eval-candidates`, which summarizes eval
   candidate queues before any dataset curation, plus
   `record-ready-repair-chain-eval-candidate-decision`, which records a manual
   dataset-review decision without making anything training-eligible, plus
   `review-ready-repair-chain-eval-dataset-decisions`, which summarizes
   eval-dataset decision queues before final eval-dataset export while keeping
   training and GitHub save blocked, plus
   `export-ready-repair-chain-eval-dataset`, which writes approved
   eval-dataset decisions to a validation-only eval-dataset JSONL while
   keeping training and GitHub save blocked, plus
   `validate-ready-repair-chain-eval-dataset`, which validates the exported
   eval-dataset queue without making it training-eligible, plus
   `export-ready-repair-chain-eval-prompts`, which converts validated
   eval-dataset rows into live-eval-compatible held-out prompts while keeping
   them out of training and GitHub-save paths, plus
   `show-ready-repair-chain-eval-prompts` and
   `list-ready-repair-chain-eval-prompts`, which inspect the exported prompt
   queues offline before any live held-out eval run. The direct Vast runner
   `scripts/vast_eval_repair_chain_prompts_direct.sh` now scores the latest
   exported repair-chain held-out prompt JSONL through the current local BIBER
   API without using OpenAI, and `review-repair-chain-heldout-eval-results`
   summarizes those result JSONL artifacts as eval-only pass/fail evidence
   before any human review. `show-repair-chain-heldout-eval-review` and
   `list-repair-chain-heldout-eval-reviews` inspect the saved review artifacts
   offline before any baseline decision is recorded.
   `record-repair-chain-heldout-eval-decision` then
   records a manual decision such as `defer`, `reject`, or
   `accept_for_baseline` while keeping `training_allowed=false`,
   `safe_to_train=false`, and `github_save_ready=false`.
   `review-repair-chain-heldout-eval-decisions` summarizes those decision
   queues while still keeping training, GitHub save, and automatic model
   promotion blocked.
   `show-repair-chain-heldout-eval-decision-review` and
   `list-repair-chain-heldout-eval-decision-reviews` inspect the saved
   decision-review artifacts offline before any baseline-candidate export.
   `export-repair-chain-heldout-baseline-candidates` then exports only accepted
   held-out decisions into baseline candidates that still require manual
   baseline review and still keep training, GitHub save, and automatic model
   promotion blocked.
   `review-repair-chain-heldout-baseline-candidates` summarizes those
   baseline-candidate queues and reports `baseline_ready_records` while still
   blocking training and promotion.
   `show-repair-chain-heldout-baseline-candidate-review` and
   `list-repair-chain-heldout-baseline-candidate-reviews` inspect saved
   baseline-candidate review artifacts offline before any manual baseline
   decision is recorded.
   `record-repair-chain-heldout-baseline-candidate-decision` records manual
   baseline decisions and can mark rows `baseline_ready=true`, but it still
   keeps `training_allowed=false`, `safe_to_train=false`,
   `github_save_ready=false`, and `approved_for_training=false`.
   `review-repair-chain-heldout-baseline-decisions` summarizes those manual
   baseline-decision queues and reports `baseline_ready_records` while still
   blocking training, GitHub save, and automatic model promotion.
   `show-repair-chain-heldout-baseline-decision-review` and
   `list-repair-chain-heldout-baseline-decision-reviews` inspect saved
   baseline-decision review artifacts offline before any training-readiness
   review.
   `review-repair-chain-training-readiness` then turns those reviewed baseline
   decisions into an explicit training gate, including `hard_blockers`, while
   still keeping `training_allowed=false`, `safe_to_train=false`, and
   `approved_for_training=false`.
   `show-repair-chain-training-readiness` and
   `list-repair-chain-training-readiness` inspect those saved readiness
   artifacts offline before any training-candidate export.
   `export-repair-chain-training-candidates` then exports only
   human-review-only candidate rows from a passing readiness gate and keeps
   `training_dataset_ready=false` until a reviewer writes verified outputs and
   validates the final dataset.
   `review-repair-chain-training-candidates` then checks whether any candidate
   rows have non-empty outputs and `quality` set to `reviewed` or `verified`;
   even when ready for dataset validation, it keeps `training_allowed=false`
   and requires a separate validation/promote step before training.
   `show-repair-chain-training-candidate-review` and
   `list-repair-chain-training-candidate-reviews` inspect the saved
   candidate-review artifacts offline before any training-pipeline or dataset
   validation decision.
   `review-repair-chain-training-pipeline` then summarizes the standard
   artifacts in a single output directory and points to the next blocked step.
   The latest standard Vast smoke still reports `baseline_ready_records` as the
   blocker, while the controlled baseline-candidate evidence directory
   `/workspace/outputs/biber-baseline-candidate-20260521T190501Z-94473`
   reports `baseline_ready_records=1` and is now blocked at
   `candidate_outputs_missing`, so no training should start yet. The single
   controlled row is smoke metadata only and must not be manually filled just
   to clear the gate.
   A disposable Vast fixture repair-chain run was completed on 2026-05-21 at
   `/workspace/outputs/biber-real-repair-fixture-20260521T192710Z-94786`
   using a temporary API rooted at that fixture repo and the live local vLLM
   model. It created a real Python compile failure, ran `mvp-loop`,
   `prepare-repair`, `attempt-repair`, `extract-repair-edits`,
   `plan-repair-edits`, approved `apply-repair-edits` only inside the
   disposable fixture, and `verify-repair-edits`. Readback confirmed
   extraction `ready_for_plan_edit`, plan/apply `ok=true`, verification
   `passed`, and repair-chain `chain_status=ready_for_human_review` with
   `verification_passed=true`, `training_allowed=false`,
   `safe_to_train=false`, and `github_save_ready=false`. A ready repair-chain
   decision was recorded as `defer` in
   `/workspace/outputs/biber-real-repair-fixture-20260521T192710Z-94786/agent-client-mvp-loop-real-fixture-ready-repair-chain-decision-review.json`;
   this fixture validates plumbing only and must not be approved for eval,
   GitHub save, or training. The temporary API process was stopped and the live
   API/vLLM service was not changed.
   Follow-up hardening added a client-side provenance guard to
   `export-ready-repair-chain-eval-candidates`: known disposable fixture,
   smoke, and controlled-baseline artifact paths are classified as
   `fixture_or_smoke` and skipped with `reason=non_real_repo_evidence`, even
   if someone accidentally records `approve_for_eval`. Real repo evidence is
   still classified as `real_repo_candidate`. This keeps fixture/smoke plumbing
   checks from flowing into held-out evals or future training queues.
   A second guard now requires
   `record-ready-repair-chain-decision --decision approve_for_eval` to include
   `--evidence-source-type real_repo_candidate`; otherwise the decision command
   fails before writing an eval-approval row. Export also skips legacy or
   handcrafted approve rows that lack confirmed real-repo provenance with
   `reason=real_repo_evidence_not_confirmed`. Use `defer` for fixture/smoke
   validation artifacts and reserve `approve_for_eval` for concrete real repo
   repair-chain evidence only.
   On 2026-05-21, a bounded expanded repo-adaptation eval was run on the live
   Vast local model against this real `biber-ai-platform` repo, without
   OpenAI mentor calls and without training. Artifacts:
   `/workspace/outputs/repo-adapt-realrepo-20260521T203421Z-95017.plan.json`,
   `/workspace/outputs/repo-adapt-realrepo-20260521T203421Z-95017.prompts.jsonl`,
   and `/workspace/outputs/evals/repo-adapt-realrepo-20260521T203421Z-95017/`.
   It included `151` files, emitted `32` prompts, received `32/32` responses,
   passed `17/32` expectation checks, and produced `15` single-occurrence
   failure groups with `0` repeated training candidates. The current curated
   repo-adaptation queue was rechecked at
   `/workspace/outputs/evals/repo-adapt-realrepo-20260521T203421Z-95017/current-curated-queue-readiness.json`
   and now reports `review_status=manual_training_review_required`,
   `ready_records=56`, `min_records=50`, and `record_gap=0`.
   A manual pre-training review artifact was then created at
   `/workspace/outputs/evals/repo-adapt-training-approval-20260521T203547Z-95083/repo-adaptation-manual-training-review.json`.
   It reports `review_status=ready_for_user_training_approval`,
   `ready_records=56`, `category_count=7`, required category counts
   `bash=5`, `markdown=8`, `python=22`, and `sql=3`, with
   `hard_blockers=[]`. It still keeps `training_allowed=false`,
   `safe_to_train=false`, and `approved_for_training=false`. The user
   explicitly approved this guarded command on 2026-05-22, and it has already
   been run. Do not rerun it automatically:
   `BIBER_TRAIN_APPROVED=1 BIBER_TRAIN_DATASET=/workspace/data/repo_adaptation/reviewed_candidates.jsonl BIBER_TRAIN_OUTPUT_DIR=/workspace/adapters/biber-dev-core-repo-adapt-next-20260521T203547Z-95083 BIBER_TRAIN_SESSION=biber-repo-adapt-next-20260521T203547Z-95083 BIBER_TRAIN_MIN_RECORDS=50 bash scripts/vast_train_qlora_tmux.sh /workspace/data/repo_adaptation/reviewed_candidates.jsonl`.
   Serving was stopped first to free GPU memory, then the QLoRA run completed
   successfully on Vast with `56` records, `7` steps, `train_loss=2.464`, and
   runtime about `37s`. Artifacts: adapter
   `/workspace/adapters/biber-dev-core-repo-adapt-next-20260521T203547Z-95083`,
   log `/workspace/outputs/qlora-20260522T092807Z.log`, and run script
   `/workspace/outputs/qlora-20260522T092807Z.sh`.
   Post-training candidate review was then run with
   `BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-repo-adapt-next-20260521T203547Z-95083`,
   the manual training-review artifact above, repo prompts
   `/workspace/outputs/repo-adapt-realrepo-20260521T203421Z-95017.prompts.jsonl`,
   and session `biber-repo-adapt-next-review-20260522T092807Z`. Artifacts are
   under
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/`.
   Results: stable repo held-out `32/32` responses and `18/32` expectation
   checks; candidate broad eval `18/18` responses and `15/18` expectation
   checks; candidate Rust/XRIQ eval `7/7` responses and `7/7` expectation
   checks with `5/7` cargo validators; candidate repo held-out `32/32`
   responses and `25/32` expectation checks. Promotion review:
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/candidate-promotion-review.json`
   with `review_status=promotion_blocked`,
   `hard_blockers=["broad_expectations_below_threshold","rust_validators_below_threshold"]`,
   `repo_baseline_improvement` passing with `delta=7`,
   `promotion_allowed=false`, `safe_to_promote=false`, and
   `serving_changed=false`. The candidate improved repo-adaptation evidence but
   must not be promoted unless broad and Rust/XRIQ gates are fixed and a later
   promotion-review artifact passes.
   The candidate-review wrapper restored stable serving afterward. Current live
   Vast service is healthy on stable adapter
   `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`; `bash
   scripts/vast_status_direct.sh` showed vLLM pid `97357`, FastAPI pid
   `97679`, `/health` OK, and `/v1/models` rooted at the stable adapter.
   Regression review was run immediately and wrote
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/candidate-regression-review.json`
   plus
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/anti-regression-candidates.jsonl`.
   It found `5` regressions and `5` review-only anti-regression candidates:
   three API error-shape rows missing `status`/`detail` shape requirements and
   two Rust/XRIQ validator failures (`rust_xriq_fee_calculation` type
   inference and `rust_xriq_next_height` free-function mismatch). Next action:
   fill verified outputs for those five anti-regression candidates, run
   `training/repo_adaptation_candidate_review.py`, apply/validate/merge only if
   review passes, and require a fresh explicit user approval before any further
   QLoRA training.
   The five anti-regression rows were then filled with verified outputs and
   applied through the existing decision gate:
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/anti-regression-decisions.json`.
   Decision review:
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/anti-regression-decisions.review.json`
   with `5/5` approved. Candidate review:
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/anti-regression-reviewed-candidate-review.json`
   with `5/5` ready and `0` pending. Merge review:
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/anti-regression-dataset-merge.review.json`
   with `0` added, `5` duplicates, and `56` total records. This means the
   same five anti-regression lessons were already present in the curated queue,
   so repeating the same QLoRA pattern would likely waste GPU time. Readiness
   and manual training reviews were still regenerated:
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/anti-regression-curated-queue-readiness.json`
   and
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/anti-regression-manual-training-review.json`,
   both with `56/50` ready records and no hard blockers, but they do not
   approve or start training.
   Training-outcome review was then written to
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/training-outcome-review.json`.
   It reports `review_status=training_strategy_blocked`,
   `persistent_trained_failures=5`, and
   `next_review_action=change_prompt_or_dataset_strategy_before_more_training`.
   Do not start another QLoRA run from this same artifact pattern.
   A profile-aware candidate eval was run instead against candidate adapter
   `/workspace/adapters/biber-dev-core-repo-adapt-next-20260521T203547Z-95083`
   under `/workspace/outputs/evals/profiled-repo-adapt-next-20260522T0958Z/`.
   The profile run used `training/api_error_response_profile.txt` for
   `api_error_shape`, `api_missing_key_error_shape`, and
   `api_rate_limit_error_shape`, plus the expanded Rust/XRIQ profile IDs
   `rust_xriq_validate_transaction`, `rust_xriq_fee_calculation`,
   `rust_xriq_next_height`, and `rust_xriq_apply_ledger_transaction`. Results:
   profiled broad eval `18/18` responses and `18/18` expectation checks;
   profiled Rust/XRIQ eval `7/7` responses, `7/7` expectation checks, and
   `7/7` cargo validators. Profile-aware promotion review:
   `/workspace/outputs/evals/profiled-repo-adapt-next-20260522T0958Z/profiled-candidate-promotion-review.json`
   with `review_status=ready_for_user_promotion_approval`,
   `hard_blockers=[]`, and `ready_for_user_promotion_approval=true`. It still
   keeps `promotion_allowed=false`, `safe_to_promote=false`, and
   `auto_promoted=false`; do not promote unless the user explicitly approves
   serving this candidate adapter under the existing runtime-profile contract.
   The script restored stable serving afterward. Current live Vast service is
   healthy on stable adapter
   `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`; `bash
   scripts/vast_test_direct.sh` showed runtime profiles enabled, `/health` OK,
   chat smoke OK, vLLM pid `99538`, FastAPI pid `99860`, and `/v1/models`
   rooted at the stable adapter.
   The user later explicitly approved the latest regenerated guarded
   repo-adaptation QLoRA command despite the strategy-blocked warning. The
   command came from
   `/workspace/outputs/evals/biber-repo-adapt-next-review-20260522T092807Z/anti-regression-manual-training-review.json`:
   `BIBER_TRAIN_APPROVED=1 BIBER_TRAIN_DATASET=/workspace/data/repo_adaptation/reviewed_candidates.jsonl BIBER_TRAIN_OUTPUT_DIR=/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z BIBER_TRAIN_SESSION=biber-repo-adapt-next2-20260522T0950Z BIBER_TRAIN_MIN_RECORDS=50 bash scripts/vast_train_qlora_tmux.sh /workspace/data/repo_adaptation/reviewed_candidates.jsonl`.
   Serving was stopped first to free GPU memory. Training tmux session
   `biber-repo-adapt-next2-20260522T0950Z` completed successfully and saved
   adapter
   `/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z`.
   Training log: `/workspace/outputs/qlora-20260522T102158Z.log`; run script:
   `/workspace/outputs/qlora-20260522T102158Z.sh`; summary: `56` records,
   `7` steps, `train_loss=2.465`, runtime about `37s`.
   Standard candidate review was then run with session
   `biber-repo-adapt-next2-review-20260522T102158Z`. Artifacts are under
   `/workspace/outputs/evals/biber-repo-adapt-next2-review-20260522T102158Z/`.
   Results: stable repo held-out `32/32` responses and `17/32` expectation
   checks; candidate broad eval `18/18` responses and `15/18` expectation
   checks; candidate Rust/XRIQ eval `7/7` responses and `7/7` expectation
   checks with `5/7` cargo validators; candidate repo held-out `32/32`
   responses and `24/32` expectation checks. Promotion review:
   `/workspace/outputs/evals/biber-repo-adapt-next2-review-20260522T102158Z/candidate-promotion-review.json`
   with `review_status=promotion_blocked`,
   `hard_blockers=["broad_expectations_below_threshold","rust_validators_below_threshold"]`,
   `promotion_allowed=false`, and `safe_to_promote=false`.
   Training-outcome review:
   `/workspace/outputs/evals/biber-repo-adapt-next2-review-20260522T102158Z/training-outcome-review.json`
   with `review_status=training_strategy_blocked` and
   `persistent_trained_failures=5`. This confirms another same-pattern QLoRA
   run did not fix the unprofiled broad/Rust blockers; do not run additional
   duplicate QLoRA jobs from this dataset pattern.
   A profile-aware candidate eval was then run against
   `/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z` under
   `/workspace/outputs/evals/profiled-repo-adapt-next2-20260522T1032Z/`.
   Profiled broad eval passed `18/18` expectation checks; profiled Rust/XRIQ
   eval passed `7/7` expectation checks and `7/7` cargo validators. Profiled
   promotion review:
   `/workspace/outputs/evals/profiled-repo-adapt-next2-20260522T1032Z/profiled-candidate-promotion-review.json`
   with `review_status=ready_for_user_promotion_approval`,
   `hard_blockers=[]`, and `ready_for_user_promotion_approval=true`; it still
   keeps `promotion_allowed=false`, `safe_to_promote=false`, and
   `auto_promoted=false`. The script restored stable serving afterward. The
   user then explicitly approved promoting
   `/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z` under
   the runtime-profile contract. Promotion was performed by stopping the stable
   API/vLLM service and starting
   `BIBER_LORA_ADAPTER_DIR=/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z bash scripts/vast_start_lora_direct.sh`.
   Live verification passed `bash scripts/vast_test_direct.sh` and
   `bash scripts/vast_runtime_profile_smoke.sh`. `/v1/models` now shows
   `biber-dev-core` rooted at
   `/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z`;
   runtime profiles are enabled; profile smoke returned valid
   `api-error-response`, `rust-xriq-codegen`, and session outputs. Current
   live Vast service is healthy with vLLM pid `104769`, FastAPI pid `105366`,
   and the promoted adapter above. Next action is not more same-pattern
   training; continue BIBER MVP/XRIQ work while using runtime profiles for the
   relevant client paths, or collect new real repo repair-chain evidence before
   any future training.
   Follow-up BIBER MVP frontend/TypeScript test-diagnosis work added
   deterministic Node, React Testing Library, TypeScript, Vite, and Jest
   failure classification in both the `src/biber_api` and `app` mirrors.
   Local compile and inline assertions passed; Vast focused pytest
   `tests/test_test_diagnosis.py -q` passed with `9` tests after
   fast-forwarding to `bec42c8`. An API-only restart loaded the live app
   change without unloading the promoted adapter; vLLM stayed at pid `104769`,
   FastAPI restarted to pid `105366`, and smoke remained OK.
   Follow-up BIBER MVP agent-smoke safety fix `2afa40e` changed
   `scripts/vast_biber_agent_smoke.sh` so synthetic smoke repair-chain
   evidence proves the `approve_for_eval` guard blocks non-real repo evidence
   instead of trying to approve it. Vast fast-forwarded to `2afa40e`,
   `bash -n scripts/vast_biber_agent_smoke.sh` passed, and the live smoke
   passed with artifact directory
   `/workspace/outputs/biber-agent-smoke-20260522T122454Z-105580`. The smoke
   summary reported `ok=biber-agent-smoke`, `agent_client_mvp_loop_test_ok=true`,
   `agent_client_mvp_loop_ready_repair_chain_decision_value=defer`,
   `agent_client_mvp_loop_ready_repair_chain_eval_candidate_records=0`, and
   training pipeline `blocked` with blocker
   `synthetic_smoke_not_real_repo_candidate`. The promoted adapter stayed
   loaded; no OpenAI mentor call or training run was used.
   Follow-up real-repo approval guard `d9448ec` tightened
   `record-ready-repair-chain-decision`: even with
   `--evidence-source-type real_repo_candidate`, `approve_for_eval` now rejects
   records whose artifact paths, notes, or prior provenance prove smoke/fixture
   evidence. Local `compileall` and direct inline guard assertion passed. Vast
   focused pytest passed with `3 passed, 136 deselected` for
   `record_ready_repair_chain_approve_for_eval` and
   `export_ready_repair_chain_eval_candidates_blocks_fixture_evidence`. Live
   Vast agent smoke passed with artifact directory
   `/workspace/outputs/biber-agent-smoke-20260522T124907Z-105799`; summary
   again kept eval-candidate records at `0` and training pipeline `blocked`
   with `synthetic_smoke_not_real_repo_candidate`.
   Follow-up repo-provenance approval guard `23d5977` now requires explicit
   real repo source provenance before `approve_for_eval` evidence can become an
   eval candidate. `show-repair-chain` accepts `--source-repo-root`,
   `--source-repo-url`, `--source-repo-commit`, and `--source-repo-branch`; real
   repo eval approval needs at least `root` and `commit`. `4508e67` then fixed
   the decision JSONL path so normalized `repo_provenance` is preserved on the
   recorded decision row and can flow into later eval-candidate export. Local
   verification passed `git diff --check`, bundled-Python `compileall`, and a
   direct inline assertion for real-repo provenance preservation; local pytest
   was unavailable in the bundled Python. Vast fast-forwarded to `4508e67`, and
   focused pytest passed with `8 passed, 132 deselected` for the
   repair-chain provenance and eval-candidate paths. Live Vast agent smoke
   passed with artifact directory
   `/workspace/outputs/biber-agent-smoke-20260522T130706Z-106028`; summary kept
   the synthetic chain deferred, eval-candidate records at `0`, dataset export
   blocked, and training pipeline blocked with
   `synthetic_smoke_not_real_repo_candidate`. The verified live Vast code
   checkpoint is `4508e67`; docs-only handoff commits can be fast-forwarded
   after it without a service restart. Current vLLM pid is `104769`, FastAPI
   pid is `105366`, and the promoted adapter remains
   `/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z`. No
   training run or OpenAI mentor call was used for this checkpoint.
   Follow-up repair-chain git-provenance helper `71119b7` makes
   `show-repair-chain --source-repo-root <git-checkout>` auto-fill missing
   source repo URL, commit, and branch from Git; explicit manual
   `--source-repo-url`, `--source-repo-commit`, and `--source-repo-branch`
   values still override derived values. This reduces accidental bad evidence
   and keeps `approve_for_eval` blocked unless root plus commit provenance is
   present. Local verification passed `git diff --check`, bundled-Python
   `compileall`, and a direct git-provenance assertion against the local repo.
   Vast fast-forwarded to `71119b7`; focused pytest passed with
   `7 passed, 133 deselected`, and direct Vast git-provenance assertion found
   URL, branch, and commit. Live Vast agent smoke passed with artifact
   directory `/workspace/outputs/biber-agent-smoke-20260522T131704Z-106296`;
   summary kept the synthetic chain deferred, eval-candidate records at `0`,
   dataset export blocked, and training pipeline blocked with
   `synthetic_smoke_not_real_repo_candidate`. No training run or OpenAI mentor
   call was used for this checkpoint.
   Follow-up ready repair-chain provenance review counter `56687b7` surfaces
   `repo_provenance_ready`, `repo_provenance_missing`, and
   `eval_approval_requires_repo_provenance` in
   `export-ready-repair-chains`, `review-ready-repair-chains`,
   `show-ready-repair-chain-review`, and
   `list-ready-repair-chain-reviews`. This lets future sessions see whether a
   ready repair-chain queue has root-plus-commit evidence before attempting
   `approve_for_eval`. Local verification passed `git diff --check`,
   bundled-Python `compileall`, and a direct ready-review assertion. Vast
   fast-forwarded to `56687b7`; focused pytest passed with
   `5 passed, 135 deselected`, and live Vast agent smoke passed with artifact
   directory `/workspace/outputs/biber-agent-smoke-20260522T134502Z-106503`.
   The smoke kept synthetic evidence deferred, eval-candidate records at `0`,
   dataset export blocked, and training pipeline blocked with
   `synthetic_smoke_not_real_repo_candidate`. No training run or OpenAI mentor
   call was used for this checkpoint.
   Follow-up repair-chain decision provenance counter `dc255bb` surfaces
   `repo_provenance_ready`, `repo_provenance_missing`,
   `rejected_repo_provenance_ready`,
   `rejected_repo_provenance_missing`, and
   `eval_approval_requires_repo_provenance` in
   `record-ready-repair-chain-decision` output and recorded decision rows. This
   keeps the final manual approval gate explicit about whether a row has root
   plus commit provenance or was rejected before eval-candidate export. Local
   verification passed `git diff --check`, bundled-Python `compileall`, and a
   direct decision-record assertion. Vast fast-forwarded to `dc255bb`; focused
   pytest passed with `4 passed, 136 deselected`, and live Vast agent smoke
   passed with artifact directory
   `/workspace/outputs/biber-agent-smoke-20260522T140209Z-106710`. The smoke
   kept synthetic evidence deferred, eval-candidate records at `0`, dataset
   export blocked, and training pipeline blocked with
   `synthetic_smoke_not_real_repo_candidate`. No training run or OpenAI mentor
   call was used for this checkpoint.
   Follow-up eval-candidate provenance counter `b138544` surfaces
   `repo_provenance_ready`, `repo_provenance_missing`,
   `skipped_repo_provenance_ready`,
   `skipped_repo_provenance_missing`, and
   `eval_approval_requires_repo_provenance` in
   `export-ready-repair-chain-eval-candidates`,
   `review-ready-repair-chain-eval-candidates`,
   `show-ready-repair-chain-eval-candidate-review`, and
   `list-ready-repair-chain-eval-candidate-reviews`. This keeps root-plus-commit
   provenance visible after the manual decision gate and before dataset review.
   Local verification passed `git diff --check`, bundled-Python `compileall`,
   and a direct eval-candidate export/review assertion. Vast fast-forwarded to
   `b138544`; focused pytest passed with `7 passed, 133 deselected`, and live
   Vast agent smoke passed with artifact directory
   `/workspace/outputs/biber-agent-smoke-20260522T173404Z-106929`. The smoke
   kept synthetic evidence deferred, eval-candidate records at `0`, dataset
   export blocked, and training pipeline blocked with
   `synthetic_smoke_not_real_repo_candidate`. No training run or OpenAI mentor
   call was used for this checkpoint.
   Follow-up repair-chain list provenance counter `80cee7b` surfaces
   `repo_provenance_ready`, `repo_provenance_missing`, and
   `eval_approval_requires_repo_provenance` in `list-repair-chains`, plus a
   per-artifact `repo_provenance_ready` marker. This makes the real-candidate
   bottleneck visible before export/review: after Vast fast-forward, live
   `/workspace/outputs` listing reported `58` ready repair chains,
   `repo_provenance_ready: 0`, and `repo_provenance_missing: 58`. Local
   verification passed `git diff --check`, bundled-Python `compileall`, and a
   direct no-pytest assertion. Vast verification passed bundled venv
   `compileall`, focused pytest with `1 passed, 139 deselected`, and the live
   `list-repair-chains /workspace/outputs --ready-only --limit 5` check. No
   training run or OpenAI mentor call was used for this checkpoint.
   Follow-up repair-edit extraction compatibility commit `87f0f24` accepts the
   common model alias `file` as an edit target path, while still rejecting
   conflicting `path`/`file` values before any plan/apply step. This came from
   a real Vast local-model repair attempt whose proposed JSON used `file`
   instead of `path`. Local verification passed `git diff --check`,
   bundled-Python `compileall`, and a direct no-pytest assertion. Vast
   fast-forwarded to `87f0f24`; focused pytest passed with
   `2 passed, 140 deselected`.
   After that fix, a real repo-provenanced repair-chain candidate was produced
   on Vast without training or OpenAI mentor use:
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-review.json`.
   It used temporary worktree
   `/workspace/biber-real-repo-candidates/real-repo-candidate-20260522T184002Z-107220/repo`,
   source repo URL `https://github.com/selvasmallive/biber-ai-platform.git`,
   source commit `897f99b67d6bae20c6c8af8b91883de53394c1c0`, and branch
   `biber/real-repo-candidate-20260522T184002Z-107220`. The local model
   proposed the repair, the extractor accepted it, `apply-repair-edits
   --approve` applied it only in the temporary worktree, and
   `verify-repair-edits` passed `python-compileall-api`. The ready repair-chain
   review reports `records: 1`, `repo_provenance_ready: 1`,
   `repo_provenance_missing: 0`, and `review_status: needs_human_review`.
   This candidate is not approved for eval/dataset/training yet; the next
   manual gate is `record-ready-repair-chain-decision --decision
   approve_for_eval --evidence-source-type real_repo_candidate` only if the
   human reviewer accepts the candidate.
   Follow-up eval-only review step on Vast accepted that real repo candidate
   for held-out eval curation only, not dataset/training.
   `record-ready-repair-chain-decision` wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-decisions.jsonl`
   with `decision=approve_for_eval`, `records: 1`,
   `repo_provenance_ready: 1`, `rejected_records: 0`,
   `training_allowed: False`, `safe_to_train: False`, and
   `approved_for_training: False`. `export-ready-repair-chain-eval-candidates`
   then wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-candidates.jsonl`
   with `eval_candidates: 1`, `blocked_non_real_repo_records: 0`, and
   `blocked_unconfirmed_real_repo_records: 0`. The eval-candidate review at
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-candidate-review.json`
   reports `records: 1`, `ready_for_dataset_review: 1`,
   `repo_provenance_ready: 1`,
   `review_status: eval_candidates_need_dataset_review`,
   `requires_dataset_review: True`, `eval_dataset_ready: False`, and
   `approved_for_training: False`. No training run or OpenAI mentor call was
   used. The next manual gate is dataset review via
   `record-ready-repair-chain-eval-candidate-decision`; do not approve
   dataset/training from a generic continue unless the reviewer accepts the
   eval-candidate contents.
   Follow-up eval-dataset curation step on Vast accepted the same single real
   repo-provenanced candidate for held-out eval dataset use only. The candidate
   was inspected before decision recording: `test_id=python-compileall-api`,
   `chain_status=ready_for_human_review`, `verification_passed=True`, and
   `approved_for_training=False`. `record-ready-repair-chain-eval-candidate-decision`
   wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-dataset-decisions.jsonl`
   with `decision=approve_for_eval_dataset`, `records: 1`,
   `approved_for_eval_dataset_records: 1`, `eval_dataset_ready: True`,
   `training_allowed: False`, `safe_to_train: False`, and
   `approved_for_training: False`. Decision review wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-dataset-decision-review.json`
   with `eval_dataset_ready_records: 1`. Final eval-dataset export wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-dataset.jsonl`;
   validation wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-dataset-validation.json`
   with `ok: True`, `records: 1`, `valid_records: 1`, and
   `invalid_records: 0`. Prompt export wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-ready-repair-chain-eval-prompts.jsonl`
   with `eval_prompts: 1`, `eval_only: True`, `training_allowed: False`,
   `safe_to_train: False`, and `approved_for_training: False`. No training run
   or OpenAI mentor call was used.
   Follow-up held-out eval on Vast ran the single exported real-repo prompt
   through the live `biber-dev-core-v1` local model without training or OpenAI
   mentor use. The live eval wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-eval.jsonl`
   and
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-eval.summary.json`
   with `1/1` responses and `1/1` expectation checks passed. Held-out review
   wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-eval-review.json`
   with `ok: True`, `review_status: heldout_eval_passed`, `records: 1`,
   `passed_records: 1`, `failed_records: 0`,
   `expectation_failed_records: 0`, `model_counts: {'biber-dev-core-v1': 1}`,
   `eval_only: True`, `training_allowed: False`, `safe_to_train: False`, and
   `approved_for_training: False`. The next narrow gate is a manual
   `record-repair-chain-heldout-eval-decision` of `defer`, `reject`, or
   `accept_for_baseline`; do not create baseline/training approvals from a
   generic continue.
   Follow-up user-approved baseline bookkeeping recorded
   `accept_for_baseline` for that latest held-out eval review artifact and
   exported one held-out baseline candidate without training or OpenAI mentor
   use. Decision export wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-eval-decisions.jsonl`
   with `records: 1`, `accepted_for_baseline_records: 1`, and
   `baseline_candidate_ready: True`. Decision review wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-eval-decision-review.json`
   with `decision_counts: {'accept_for_baseline': 1}` and
   `baseline_candidate_ready_records: 1`. Baseline-candidate export wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-baseline-candidates.jsonl`
   with `baseline_candidates: 1`, `baseline_ready: False`, and
   `requires_baseline_review: True`. Baseline-candidate review wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-baseline-candidate-review.json`
   with `records: 1`, `baseline_candidate_ready_records: 1`,
   `baseline_ready_records: 0`, `requires_baseline_review_records: 1`,
   `training_allowed: False`, `safe_to_train: False`, and
   `approved_for_training: False`. The next narrow gate is a manual
   `record-repair-chain-heldout-baseline-candidate-decision` of `defer`,
   `reject`, or `approve_as_baseline`; do not start training or mark a
   training dataset ready from a generic continue.
   Follow-up user-approved baseline decision recorded `approve_as_baseline` for
   that latest held-out baseline-candidate review artifact. Baseline decision
   export wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-baseline-decisions.jsonl`
   with `records: 1`, `approved_as_baseline_records: 1`, and
   `baseline_ready: True`. Baseline decision review wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-heldout-baseline-decision-review.json`
   with `decision_counts: {'approve_as_baseline': 1}`,
   `baseline_ready_records: 1`, `requires_baseline_review_records: 0`,
   `training_allowed: False`, `safe_to_train: False`, and
   `approved_for_training: False`. Training-readiness review wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-training-readiness.json`
   with `review_status: baseline_ready_manual_training_review_required`,
   `training_gate_status: manual_review_required`,
   `baseline_ready_records: 1`, and
   `ready_for_manual_training_dataset_review: True`. Its required manual
   actions are `human_training_dataset_review`,
   `explicit_user_approval_before_any_training_job`, and
   `separate_vast_gpu_training_run_outside_codex_loop`. No training run or
   OpenAI mentor call was used. The next narrow gate is review-queue work only:
   export/review training candidates from the readiness artifact, then manually
   review/fill candidate outputs and validate a training dataset. Do not start
   QLoRA or any training job until the user explicitly approves training again.
   Follow-up review-queue export on Vast wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-training-candidates.jsonl`
   with `export_status: training_candidates_need_human_review`,
   `records: 1`, `training_candidate_records: 1`,
   `requires_human_training_dataset_review: True`,
   `training_dataset_ready: False`, and `review_queue_only: True`. Candidate
   review wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-training-candidate-review.json`
   with `review_status: training_candidates_need_review`, `records: 1`,
   `reviewed_records: 0`, `pending_review_records: 1`,
   `empty_output_records: 1`, `unreviewed_quality_records: 1`,
   `ready_for_dataset_validation: False`, and hard blockers
   `candidate_outputs_missing`, `candidate_quality_not_reviewed`, and
   `below_min_ready_records`. Pipeline review wrote
   `/workspace/outputs/biber-real-repo-candidate-real-repo-candidate-20260522T184002Z-107220/agent-client-mvp-loop-repair-chain-training-pipeline.json`
   with `training_pipeline_status: blocked`,
   `missing_or_blocked_step: candidate_outputs_missing`,
   `baseline_ready_records: 1`, `training_candidate_records: 1`,
   `ready_for_dataset_validation: False`, and all training/promotion/GitHub
   flags false. The single candidate row has `output: ""`,
   `quality: needs_review`, and `review_required: true`; it is not trainable.
   Next narrow gate: inspect the underlying real-repo repair artifacts and only
   fill a verified candidate output if it clearly improves repo-specific coding
   behavior without leaking private code or secrets. Otherwise leave it pending
   and collect richer real-repo repair examples. Do not start training.
   Follow-up inspection on 2026-05-23 reviewed the underlying artifacts:
   `agent-client-mvp-loop-output.json`,
   `agent-client-mvp-loop-repair-attempt.json`,
   `agent-client-mvp-loop-repair-edit-extraction.json`,
   `agent-client-mvp-loop-repair-edit-plan.json`,
   `agent-client-mvp-loop-repair-edit-apply.json`,
   `agent-client-mvp-loop-repair-test-verification.json`, and
   `agent-client-mvp-loop-repair-chain.json`. The local model proposed the
   correct smallest edit for `app/real_repo_candidate_syntax_error.py`, changing
   `return "ready\n` to `return "ready"`, and `python-compileall-api` passed
   after the approved temporary-worktree apply. However, this is a toy
   one-line syntax fixture whose value is mainly pipeline validation. Leave the
   training-candidate row unfilled with `output: ""` and
   `quality: needs_review`; do not mark it `reviewed` or `verified` just to
   clear `candidate_outputs_missing`. The next useful step is to collect a
   richer real-repo repair-chain example with concrete task/failure/diagnosis,
   a non-trivial patch, and verified tests, or continue improving the
   deterministic repo-context/edit/test workflow. No training run or OpenAI
   mentor call was used for this inspection.
   `show-repair-chain-training-pipeline` inspects the saved pipeline status
   artifact offline without recomputing the review.
   `list-repair-chain-training-pipelines` then scans output directories for
   those status artifacts so future sessions can find whether any run is ready
   before touching training. The repo-adaptation live eval wrapper and the
   conservative
   repo-adaptation failure-review, candidate-review, and regression-review
   helpers are also live. Good next targets are running the full repair sequence
   (`mvp-loop`, `attempt-repair`, `extract-repair-edits`, `plan-repair-edits`,
   approved `apply-repair-edits`, `verify-repair-edits`, and
   `export-verified-repair`, followed by `review-verified-repairs` and
   `show-repair-chain`, then `list-repair-chains --ready-only` and
   `export-ready-repair-chains`, then `review-ready-repair-chains`, then
   `record-ready-repair-chain-decision`, then
   `review-ready-repair-chain-decisions`, then
   `export-ready-repair-chain-eval-candidates`, then
   `review-ready-repair-chain-eval-candidates`, then
   `record-ready-repair-chain-eval-candidate-decision`, then
   `review-ready-repair-chain-eval-dataset-decisions`, then
   `export-ready-repair-chain-eval-dataset`, then
   `validate-ready-repair-chain-eval-dataset`, then
   `export-ready-repair-chain-eval-prompts`) against a real user repo when
   provided, then run
   `bash scripts/vast_eval_repair_chain_prompts_direct.sh` on the held-out
   prompt JSONL, then run `review-repair-chain-heldout-eval-results` on the
   result JSONL and summary, then inspect it with
   `show-repair-chain-heldout-eval-review` and
   `list-repair-chain-heldout-eval-reviews`, then record a
   defer/reject/accept-for-baseline
   decision with `record-repair-chain-heldout-eval-decision`, then summarize
   that decision queue with `review-repair-chain-heldout-eval-decisions`, then
   inspect it with `show-repair-chain-heldout-eval-decision-review` and
   `list-repair-chain-heldout-eval-decision-reviews`, then
   export accepted baseline candidates with
   `export-repair-chain-heldout-baseline-candidates`, then review those
   baseline candidates with
   `review-repair-chain-heldout-baseline-candidates`, then inspect the saved
   baseline-candidate review with
   `show-repair-chain-heldout-baseline-candidate-review` and
   `list-repair-chain-heldout-baseline-candidate-reviews`, then record manual
   baseline decisions with
   `record-repair-chain-heldout-baseline-candidate-decision`, then summarize
   those manual baseline decisions with
   `review-repair-chain-heldout-baseline-decisions`, then inspect the saved
   baseline-decision review with
   `show-repair-chain-heldout-baseline-decision-review` and
   `list-repair-chain-heldout-baseline-decision-reviews`, then run
   `review-repair-chain-training-readiness`, then inspect the saved
   training-readiness artifact with
   `show-repair-chain-training-readiness` and
   `list-repair-chain-training-readiness`, then run
   `export-repair-chain-training-candidates`, then run
   `review-repair-chain-training-candidates`, then inspect the saved
   training-candidate review artifact with
   `show-repair-chain-training-candidate-review` and
   `list-repair-chain-training-candidate-reviews`, then run
   `review-repair-chain-training-pipeline`, then inspect the saved pipeline
   status artifact with `show-repair-chain-training-pipeline`, then run
   `list-repair-chain-training-pipelines`, then collect a real repo
   repair-chain candidate with concrete task/failure/patch evidence and
   explicit source repo root plus commit provenance before
   manually filling any training-candidate `output`, rerun
   `review-repair-chain-training-candidates`, validate a reviewed dataset, and
   require explicit user approval before any Vast training job. There is now a
   repeated repo-adaptation failure-review artifact with four review-only candidates at
   `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.repeat-training-candidates.jsonl`.
   Those four rows have been manually reviewed into
   `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.reviewed-candidates.jsonl`,
   and validation passed with `ok=true`, `records=4`, and `errors=[]`. They
   are now merged into the cumulative curated queue at
   `/workspace/data/repo_adaptation/reviewed_candidates.jsonl`, which also
   validates with `ok=true`, `records=4`, and `errors=[]`. Readiness review at
   `/workspace/outputs/evals/repo-adapt-repeat-20260520T142227Z-70388.curated-queue-readiness.json`
   reports `training_blocked`, `ready_records=4`, `min_records=50`, and
   `record_gap=46`. Expanded prompt mode has now produced another repeatable
   failure candidate queue at
   `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.repeat-training-candidates.jsonl`
   with `13` pending `needs_review` candidates and `0` ready rows. Batches 1,
   2, and 3 reviewed and merged all `13` of those Python rows, bringing the
   cumulative queue to `17` reviewed rows. The latest readiness artifact is
   `/workspace/outputs/evals/repo-adapt-expanded-repeat-20260520T155919Z.batch3-curated-queue-readiness.json`
   and reports `training_blocked`, `ready_records=17`, `min_records=50`, and
   `record_gap=33`. Next, collect more diversified repo-adaptation eval signal;
   do not start training from unreviewed or tiny artifacts automatically.
   Public XRIQ launch, exchange
   listing, custody, liquidity, bridges, and market-facing work remain blocked.
14. Keep reviewing and refining `docs/XRIQ_TECHNICAL_SPEC.md` as the prototype
   clarifies open decisions. Do not treat the private devnet as public launch
   readiness.
15. Use BIBER AI for XRIQ through inference first: spec drafting, Rust module
   scaffolding, tests, review prompts, and private-devnet tooling. Fine-tune
   only after Rust/XRIQ evals show repeatable gaps.
16. After the Rust/XRIQ baseline is stable, follow
   `docs/BIBER_CAPABILITY_ROADMAP.md` in order: PostgreSQL, React, TypeScript,
   JavaScript, jQuery, CSS, HTML, Docker, GitHub Actions CI/CD, WASM, Bash,
   security engineering, cryptography concepts, Kubernetes, and distributed
   systems optimization, then TensorFlow/Keras ML engineering before
   lower-priority stacks.
17. Add new training data only through approved/provenance-tracked sources, then
   validate and promote to `/workspace/data/biber_train.jsonl`.
18. Keep the cost-saving pattern: Codex changes scripts, docs, evals, and
   diagnoses failures; Vast.ai runs long GPU jobs in `tmux`.
19. Keep the API private over SSH tunnels unless credentials are deliberately
   rotated and public binding is intentionally enabled.
20. Keep the Vast.ai checkout fast-forwarded with local/GitHub `main`.
21. Add optional OpenAI mentor credentials to the server-side `.env` only if
    desired and cost-approved. The code path is already gated by
    `BIBER_MENTOR_ENABLED=true`, `OPENAI_API_KEY`, `OPENAI_MODEL`, and the
    prompt phrase `Review with OpenAI mentor`.
22. Add database-backed API keys and agent-client sessions per
    `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md`.
23. Add a durable fine-grained GitHub token to Vast `.env` if persistent
   generated-code save should stay enabled.
24. Add Azure Blob connection string and test backups.
25. Replace demo API key/passcode auth with database-backed credentials.
26. Add real MySQL persistence and Redis worker integration.

## Resume Prompt For A New Chat

```text
Read docs/CODEX_HANDOFF.md and continue biber-ai-platform from the current
GitHub main branch. Vast may be stopped or terminated; do not assume
/workspace, vLLM, FastAPI, or live Vast SSH access exists unless I provide a
fresh Vast instance.
```
