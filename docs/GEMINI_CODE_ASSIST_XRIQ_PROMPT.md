# Gemini Code Assist Prompt: XRIQ Production

Use this prompt in Gemini Code Assist Enterprise for XRIQ production work.

```text
GitHub repo:
https://github.com/selvasmallive/biber-ai-platform

Project:
XRIQ production hardening from the completed XRIQ private-devnet prototype.

Base branch:
main

Backup branch that preserves the pre-Gemini handoff state:
backup/xriq-pre-gemini-20260614

First, read these files before proposing or changing code:
- docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md
- docs/XRIQ_PRODUCTION_ROADMAP.md
- .github/copilot-instructions.md
- docs/XRIQ_LEGAL_RISK_REDUCTION.md
- docs/CODEX_HANDOFF.md
- README.md
- xriq/README.md

Current state:
XRIQ private-devnet through Phase 1.4 is complete for the local/non-production
scope. The completed baseline is anchored by these tags:
- phase1-xriq-private-devnet-rc1
- phase1-1-xriq-local-e2e-rc1
- phase1-2-xriq-local-private-hardening-rc1
- phase1-3-xriq-local-private-behavior-rc1
- phase1-4-xriq-local-signed-submit-rc1

Do not move, delete, recreate, or repush any existing Phase 1 tags.

Goal:
Begin Phase 2 from docs/XRIQ_PRODUCTION_ROADMAP.md:
Hardened Private/Staging Devnet.

Cost-saving strategy:
Keep PRs narrow. Use Gemini Code Assist Enterprise for implementation help, but
avoid broad rewrites. Use deterministic local tests and scripts. Use Codex only
as an occasional monitor/reviewer between milestones.

Hard scope boundaries:
- Do not implement public mainnet.
- Do not implement DEX, bridge, CEX listing, custody, privacy protocol,
  smart-contract VM, tokenomics, or production cloud infrastructure unless the
  roadmap phase and a human issue explicitly approve it.
- Do not create, modify, or destroy Azure, AWS, GCP, DNS, payment, exchange, or
  production resources.
- Do not commit secrets or rotate credentials.
- Do not claim legal/compliance/exchange readiness.

Recommended first PR:
Create a narrow Phase 2 staging-devnet planning/checkpoint PR that:
1. Defines Phase 2 staging-devnet acceptance criteria.
2. Lists production-hardening gaps from the private-devnet prototype.
3. Defines environment boundaries: local, staging-devnet, public-testnet,
   production-candidate, mainnet.
4. Defines required config, secrets, IAM, deployment, observability, backup,
   rollback, and cloud-provider decisions without choosing Azure/AWS/GCP yet.
5. Adds a cheap validation guard script for the Phase 2 plan.
6. Updates README, xriq/README.md, and docs/CODEX_HANDOFF.md references.
7. Runs only cheap docs/script checks unless code changes require Rust tests.

Verification for the first PR:
- python scripts/xriq_private_devnet_wrapup_check.py --require-tags-present
- python scripts/xriq_production_roadmap_check.py
- the new Phase 2 plan guard script

PR summary must include:
- what changed
- what is still not production
- cloud resources touched: none
- tags touched: none
- secrets/credentials touched: none
- tests/checks run
- recommended next PR

Codex monitor checkpoint:
After each meaningful Gemini PR or roadmap phase, ask Codex to review the PR
for scope drift, production-risk drift, security boundaries, legal-risk
guardrails, test gaps, and whether Gemini is moving XRIQ in the intended
direction.
```
