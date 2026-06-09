# XRIQ Private-Devnet Wrap-Up

Status: Codex private-devnet prototype wrap-up checkpoint.

This document consolidates the local/private XRIQ work completed through Phase
1.4. It is a non-production handoff, not a public launch, mainnet, exchange,
custody, legal, compliance, ISO certification, or cloud deployment approval.

## Completion Status

The Codex-focused XRIQ private-devnet prototype base is complete for the
local/private scope currently agreed in this repo.

Completion estimate for this scope: `100%`.

This percentage applies only to the non-production private-devnet prototype
baseline through Phase 1.4:

- Phase 1: Rust private-devnet foundation and release-candidate guardrails.
- Phase 1.1: local/private end-to-end API, UI, PostgreSQL indexing, and ISO
  20022 preview adapter.
- Phase 1.2: local/private mutation hardening, explicit gates, UI controls, and
  negative-path checks.
- Phase 1.3: local/private wallet behavior testing, browser demo runbook, and
  wallet/explorer/Admin refresh coverage.
- Phase 1.4: local/private CLI-only signed-transfer artifact, default-refused
  signed-submit API, accepted signed-submit behind an explicit local flag, and
  signed-submit lifecycle smoke.

It does not include production hardening, public testnet, public mainnet, public
token economics, DEX, bridges, CEX listing, privacy protocol implementation,
custody, smart-contract VM, production cloud infrastructure, external security
audit, legal approval, or exchange readiness.

## Source-Control Anchors

The completed private-devnet baseline is anchored by these tags:

| Scope | Tag | Commit |
|---|---|---|
| Phase 1 private-devnet RC1 | `phase1-xriq-private-devnet-rc1` | `688bf91` |
| Phase 1.1 local/e2e RC1 | `phase1-1-xriq-local-e2e-rc1` | `6a38a51a` |
| Phase 1.2 local/private hardening RC1 | `phase1-2-xriq-local-private-hardening-rc1` | `b3a2fe4` |
| Phase 1.3 local/private behavior RC1 | `phase1-3-xriq-local-private-behavior-rc1` | `345d353` |
| Phase 1.4 local/private signed-submit RC1 | `phase1-4-xriq-local-signed-submit-rc1` | `45be474` |

Do not move, delete, recreate, or repush these tags unless the user explicitly
asks for that exact tag maintenance operation.

## Cheap Verification

Run the wrap-up guard from the repository root:

```bash
python scripts/xriq_private_devnet_wrapup_check.py
```

After the wrap-up checkpoint is committed and pushed, a stricter local check is:

```bash
python scripts/xriq_private_devnet_wrapup_check.py --require-clean-git --require-origin-main --require-tags-present
```

To also verify remote tag visibility, run:

```bash
python scripts/xriq_private_devnet_wrapup_check.py --require-clean-git --require-origin-main --require-tags-present --require-origin-tags
```

This guard does not run heavy Rust tests, create tags, touch cloud resources, or
change runtime state. It validates the wrap-up document, source-control tags,
and handoff references.

## Optional Local Re-Checks

Use these only when code changes affect the related area:

```bash
python scripts/xriq_phase1_rc_readiness.py
python scripts/xriq_phase1_4_rc_readiness.py --require-tag-present
python scripts/xriq_production_roadmap_check.py
```

For behavior-level validation, the most useful existing checks remain:

```bash
python scripts/xriq_phase1_3_demo_launcher.py --skip-build --launch --auto-port
python scripts/xriq_phase1_4_signed_submit_lifecycle_smoke.py
```

The first command prepares the local browser demo path. The second command is a
CPU-only signed-submit lifecycle smoke that proves a CLI-only signed artifact
can move through accepted local signed submit, pending state, local block
production, and confirmed wallet/explorer/mempool/Admin read-back.

## Production Handoff

Use this private-devnet baseline as the source for later GitHub Copilot
production work.

Required production handoff reading:

- `.github/copilot-instructions.md`
- `docs/XRIQ_PRODUCTION_ROADMAP.md`
- `docs/XRIQ_LEGAL_RISK_REDUCTION.md`
- `docs/CODEX_HANDOFF.md`
- this document

Production work remains Phase 2 through Phase 6 in
`docs/XRIQ_PRODUCTION_ROADMAP.md`. Copilot agents must keep public network,
tokenomics, DEX, bridge, privacy, custody, legal/compliance, exchange, and
cloud-resource work behind the roadmap acceptance gates and explicit human
issue approval.

## Next Human Decision

The next decision is not another Phase 1.4 tag. It is one of:

- move production hardening to GitHub Copilot using the roadmap,
- start a new local/private Phase 1.5 only if a specific non-production gap is
  identified,
- resume BIBER MVP/model work as Phase 2 for the broader BIBER project,
- run a manual private-devnet demo for confidence before switching tools.

Until the user chooses one, future Codex sessions should avoid expanding scope.
