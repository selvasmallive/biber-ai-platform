# XRIQ Production Roadmap

Status: planning guide for GitHub Copilot agents and future production work.
The current Codex focus remains the XRIQ private-devnet prototype. This roadmap
defines the later path from that prototype to a production public ecosystem.

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
- define staging deployment topology without public financial claims.

Exit criteria:

- clean clone can run local/staging smoke tests,
- restart/replay recovery tests pass,
- no unsafe key material enters browser or server custody paths,
- private/staging configuration is clearly separated from production.

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
- public testnet documentation and disclaimers.

Exit criteria:

- at least two independent nodes can sync and continue producing valid blocks,
- testnet reset/recovery procedure is documented,
- testnet coins are clearly non-production and non-investment,
- public testnet API is rate-limited and monitored.

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
- limited-user pilot plan.

Exit criteria:

- production-candidate network can run continuously with monitoring,
- rollback/recovery drills are completed,
- user-facing docs and risk disclosures are reviewed,
- launch/no-launch decision is made by humans.

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

Do not start public testnet work until Phase 2 exit criteria are met.

## Completion Principle

Production is not a single feature. XRIQ reaches production only when the code,
tests, operational runbooks, security review, legal-risk review, user-facing
docs, monitoring, and human approval all line up for the relevant phase.
