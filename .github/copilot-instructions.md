# Copilot Instructions For BIBER/XRIQ

These repository instructions are for GitHub Copilot agents and Copilot Chat.
Follow them for all work in this repo unless a human maintainer explicitly
overrides them in an issue or pull request.

## Current Strategy

- Treat **XRIQ private-devnet prototype** as the current completed-by-Codex base.
- Treat `docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md` as the completed private-devnet
  baseline handoff.
- Treat **production XRIQ work** as Phase 2 through Phase 6 in
  `docs/XRIQ_PRODUCTION_ROADMAP.md`.
- Use this same GitHub repository as the source of truth for production work.
- Keep Codex/OpenAI usage minimal after the private-devnet prototype; prefer
  Copilot PRs, local tests, CI, and human review for production hardening.

## Required Reading Before Changes

Read the relevant parts of these files before implementing changes:

- `docs/CODEX_HANDOFF.md`
- `docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md`
- `docs/XRIQ_PRODUCTION_ROADMAP.md`
- `docs/XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md`
- `docs/XRIQ_LEGAL_RISK_REDUCTION.md`
- `README.md`
- `xriq/README.md`

For changes touching a subsystem, inspect nearby Rust/TypeScript tests and
fixtures before editing.

## Scope Discipline

- Keep PRs narrow and issue-scoped.
- Do not mix production roadmap phases in one PR unless the issue explicitly
  requests it.
- Do not add public-mainnet, public token, DEX, bridge, smart-contract,
  privacy, custody, KYC/AML, CEX-listing, or production infrastructure behavior
  unless the issue references the roadmap phase and acceptance gates.
- Do not create, move, delete, or push release tags unless the issue explicitly
  asks for the exact tag action.
- Do not rotate credentials or change secrets. Never commit secrets.
- Do not create, modify, or destroy Azure, AWS, GCP, DNS, registrar, payment,
  exchange, or production resources unless the issue explicitly approves the
  provider, account/project/subscription, region, environment, and exact action.

## XRIQ Safety Rules

- Default behavior must remain local/private unless the roadmap phase and issue
  explicitly authorize broader exposure.
- Wallet/browser UI must not generate, store, or manage private keys, seed
  phrases, mnemonics, raw signatures, custody accounts, or signing material.
- Accepted mutation paths must be explicit, auditable, tested, and impossible to
  confuse with production mode.
- Public-network, DEX, bridge, asset-issuance, exchange-readiness, privacy, and
  compliance claims must stay conservative and match
  `docs/XRIQ_LEGAL_RISK_REDUCTION.md`.
- Prefer crypto-agile interfaces and clearly named algorithm/version fields.
- Privacy features should be directionally compatible with selective disclosure
  and auditability; do not implement Monero-like default opacity as the public
  default without explicit human approval and legal review.

## Cloud Production Rules

The production roadmap supports Azure, AWS, or Google Cloud Platform. Copilot
must not choose a provider by default. If a cloud task does not state the
provider, create provider-neutral docs or interfaces and ask for a human
decision in the PR summary.

When production infrastructure is requested, prefer infrastructure-as-code and
reviewable plans over manual console steps. Terraform is the default IaC choice
unless an issue explicitly chooses another tool. Do not run `terraform apply`,
`pulumi up`, cloud deletion commands, or production deployment commands unless
the issue explicitly authorizes that exact action.

Production cloud PRs must preserve these boundaries:

- separate accounts/projects/subscriptions for dev, staging, public testnet,
  production candidate, and mainnet;
- least-privilege IAM/service accounts;
- private networking for databases and internal node services;
- TLS at public edges;
- managed secrets storage and KMS/HSM-backed key protection where available;
- encrypted storage and backups;
- container/image signing or provenance when available;
- centralized logs, metrics, traces, and alerts;
- DDoS/WAF/rate-limit controls for public APIs;
- documented rollback and disaster-recovery procedures;
- no production custody or managed user-key service unless a later human issue
  explicitly approves custody architecture and legal review.

Credential changes must be rare, deliberate, and documented. Do not implement
frequent automatic credential rotation unless the issue explicitly asks for it
and explains the operational plan.

## Engineering Standards

- Prefer existing repo patterns over new frameworks.
- Keep Rust code idiomatic, typed, deterministic, and testable.
- Avoid broad refactors unless necessary for the issue.
- Add or update tests for behavior changes.
- Keep generated fixtures deterministic.
- Use structured parsers and typed data where practical.
- Do not silently change public response contracts, fixture formats, or CLI
  flags without updating docs and tests.

## Verification Expectations

Run the narrowest relevant checks locally before opening a PR. Common commands:

```bash
cd xriq
cargo fmt
cargo test -p xriq-api -j 1
cargo test --workspace -j 1
```

From the repository root, use the bundled or local Python interpreter:

```bash
python scripts/xriq_phase1_4_plan_check.py
python scripts/xriq_phase1_4_contract_check.py
python scripts/xriq_phase1_4_signed_submit_negative_smoke.py
python scripts/xriq_phase1_4_signed_submit_refusal_smoke.py
python scripts/xriq_production_roadmap_check.py
```

For UI changes, run the existing frontend check/build commands and local smoke
scripts referenced by the changed docs. If a check cannot run, explain why in
the PR.

For cloud/IaC changes, include the safe validation command output in the PR.
Examples:

```bash
terraform fmt -check
terraform validate
terraform plan
```

Only run a plan against a real cloud account/project/subscription when the issue
explicitly approves that target. Otherwise use static validation and document
what was not run.

## PR Requirements

Every Copilot PR should include:

- what changed,
- why it is within the requested phase,
- tests/checks run,
- risks or skipped checks,
- cloud provider/environment affected, or `none`,
- confirmation that no secrets, custody behavior, public network behavior, or
  production claims were added unless explicitly requested.

Prefer small PRs that can be reviewed and reverted independently.
