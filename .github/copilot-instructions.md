# Copilot Instructions For BIBER/XRIQ

These repository instructions are for GitHub Copilot agents and Copilot Chat.
Follow them for all work in this repo unless a human maintainer explicitly
overrides them in an issue or pull request.

## Current Strategy

- Treat **XRIQ private-devnet prototype** as the current completed-by-Codex base.
- Treat **production XRIQ work** as Phase 2 through Phase 6 in
  `docs/XRIQ_PRODUCTION_ROADMAP.md`.
- Use this same GitHub repository as the source of truth for production work.
- Keep Codex/OpenAI usage minimal after the private-devnet prototype; prefer
  Copilot PRs, local tests, CI, and human review for production hardening.

## Required Reading Before Changes

Read the relevant parts of these files before implementing changes:

- `docs/CODEX_HANDOFF.md`
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
```

For UI changes, run the existing frontend check/build commands and local smoke
scripts referenced by the changed docs. If a check cannot run, explain why in
the PR.

## PR Requirements

Every Copilot PR should include:

- what changed,
- why it is within the requested phase,
- tests/checks run,
- risks or skipped checks,
- confirmation that no secrets, custody behavior, public network behavior, or
  production claims were added unless explicitly requested.

Prefer small PRs that can be reviewed and reverted independently.
