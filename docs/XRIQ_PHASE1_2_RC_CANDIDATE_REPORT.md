# XRIQ Phase 1.2 RC Candidate Report

Status: candidate report only. No Phase 1.2 RC tag has been created by this
report.

Proposed tag, only after explicit user approval:
`phase1-2-xriq-local-private-hardening-rc1`

Pre-report implementation checkpoint reviewed for this candidate: `d206b78`.

## Candidate Scope

This candidate covers the local/private XRIQ Phase 1.2 post-RC hardening scope:

- disabled-by-default local mutation contracts for wallet submit, wallet send,
  and block production
- API-local refusal responses and audit visibility for disabled mutation
  attempts
- guarded local wallet-submit-to-pending and wallet-send-to-pending API paths
  behind explicit local/private flags
- wallet-send lifecycle evidence proving pending-to-confirmed flow in both
  request mode and temporary `serve-readonly` HTTP mode
- approved local wallet-send UI mutation control behind
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`
- approved local block-production UI mutation control behind
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`
- Admin refresh evidence proving block production moves the local view from
  one pending transaction at height `1` to zero pending transactions at height
  `2`
- no-pending negative evidence proving HTTP `400` `no_pending_transactions`
  leaves chain and pending state unchanged
- readiness and UI mutation-control gates requiring this evidence before any
  Phase 1.2 RC decision

## Latest Validation Evidence

Latest Phase 1.2 readiness summary:

```text
xriq/target/xriq-phase1-2-readiness-summary-20260607T115109Z/summary.json
```

The summary reports:

- `ok`: `xriq-phase1-2-readiness-summary`
- `ready_for_ui_mutation_design_review`: `true`
- `ui_mutation_controls_enabled`: `false`
- `safe_to_enable_ui_mutation_controls`: `false`
- `approval_required_before_ui_mutation_controls`: `true`
- `block_production_evidence_required_for_rc`: `true`
- `block_production_evidence_current`: `true`
- `ready_for_phase1_2_rc_decision`: `false`
- `phase1_2_rc_approval_required`: `true`

Latest UI mutation-control gate:

```text
xriq/target/xriq-phase1-2-ui-mutation-gate-check-20260607T115109Z/summary.json
```

Latest block-production UI design check:

```text
xriq/target/xriq-phase1-2-block-production-ui-design-check-20260607T115109Z/summary.json
```

Required local smoke evidence:

```text
xriq/target/xriq-phase1-2-wallet-send-lifecycle-smoke-20260606T213131Z/summary.json
xriq/target/xriq-phase1-2-wallet-send-ui-live-smoke-20260606T232950Z/summary.json
xriq/target/xriq-phase1-2-wallet-send-refresh-smoke-20260607T005924Z/summary.json
xriq/target/xriq-phase1-2-block-production-ui-live-smoke-20260607T105329Z/summary.json
xriq/target/xriq-phase1-2-block-production-admin-refresh-smoke-20260607T110810Z/summary.json
xriq/target/xriq-phase1-2-block-production-no-pending-smoke-20260607T112046Z/summary.json
```

## RC Go/No-Go Checklist

- [x] Scope is local/private and non-production.
- [x] Default UI mutation controls remain disabled.
- [x] Wallet send requires `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true` plus
      `--enable-local-wallet-send true`.
- [x] Block production requires
      `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true` plus
      `--enable-local-block-production true`.
- [x] Wallet submit remains deferred.
- [x] Wallet send and block production are separate explicit actions.
- [x] No browser persistence is used for mutation inputs.
- [x] No direct mutation `fetch(` calls are used from wallet/Admin UI sources.
- [x] No signing material, seed phrase, mnemonic, raw signature, signed
      transaction, custody field, DEX, public-network, or production language is
      introduced by the Phase 1.2 local UI controls.
- [x] Readiness summary requires block-production UI live, Admin refresh, and
      no-pending negative smoke evidence.
- [x] Phase 1.2 RC tag creation still requires explicit user approval naming
      the exact tag.

## Cheap RC Readiness Guardrail

Before any Phase 1.2 RC tag decision is acted on, run the non-mutating
guardrail:

```bash
python scripts/xriq_phase1_2_rc_readiness.py --require-tag-absent
```

The guard verifies this candidate report, the latest readiness summary, the
latest UI mutation-control gate, the latest block-production UI design check,
the required smoke evidence, the handoff/plan/gate doc references, and absence
of the proposed local/remote tag. It does not create, move, or push any tag.

## Non-Production Boundaries

This RC candidate does not approve or include:

- public mainnet, public token launch, validator admission, tokenomics, or
  governance
- DEX trading, liquidity pools, bridges, CEX listings, custody, payment
  processing, stablecoins, market-facing claims, or exchange-readiness claims
- production signing, seed phrase handling, private-key persistence, hosted
  wallet custody, or production key management
- wallet submit UI mutation, snapshot import/export mutation, smart-contract
  VM, XRC asset issuance, native DEX modules, or public API exposure
- production GCP/Vast/server resources, TLS, public auth, rate limits,
  monitoring, external audit, legal approval, ISO certification, bank
  connectivity, SWIFT connectivity, or payment-network settlement

## Candidate Decision

The local/private Phase 1.2 candidate is ready for user review as a
documentation and evidence checkpoint. The recommended next decision is a human
decision, not more implementation:

- approve creating and pushing `phase1-2-xriq-local-private-hardening-rc1`, or
- request another narrow local/private hardening fix before tagging.

Do not tag from a generic continue request. Do not create, move, or push the
proposed tag unless the user explicitly says:

```text
I explicitly approve creating and pushing the Phase 1.2 RC tag phase1-2-xriq-local-private-hardening-rc1.
```

After that explicit approval, first run the non-mutating guardrail from a clean
checkout:

```bash
python scripts/xriq_phase1_2_rc_readiness.py --require-clean-git --require-origin-main --require-tag-absent
```

If it passes, run only:

```bash
git tag phase1-2-xriq-local-private-hardening-rc1
git push origin phase1-2-xriq-local-private-hardening-rc1
```

If there is no explicit tag approval, keep Phase 1.2 local/private and choose
only one next narrow task: another local hardening fix, an RC-readiness
guardrail update, or a separately approved post-Phase 1.2 scope item.
