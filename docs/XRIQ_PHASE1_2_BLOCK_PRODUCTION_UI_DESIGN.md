# XRIQ Phase 1.2 Block-Production UI Design

Design Status: Review Only - Not Approved For Implementation

This document defines a possible future local/private-devnet UI mutation
control for producing one block from pending transactions. It does not approve
implementation and does not enable any UI block-production action.

## Candidate Scope

Candidate: local block production only.

This candidate would be separate from wallet send. Wallet send must never
silently produce a block after creating a pending transaction.

The current UI may continue to show the disabled `Produce Block` guard and the
active `Check Guard` action. The disabled guard proves the default route still
refuses mutation. It is not an enabled block-production control.

## Preconditions Before Implementation

Implementation is not allowed unless all of these are true:

- `scripts/xriq_phase1_2_block_production_ui_design_check.py` passes.
- `scripts/xriq_phase1_2_ui_mutation_gate_check.py` passes.
- `scripts/xriq_phase1_2_wallet_send_refresh_smoke.py` passes.
- The user gives explicit approval naming this gate and the exact local block
  production UI mutation control.

Required approval phrase:

```text
I explicitly approve implementing the Phase 1.2 local/private-devnet
block-production UI mutation control behind the UI mutation-control gate.
```

## Allowed Future Implementation Shape

If explicit approval is later given, the implementation must remain narrow:

- Add only a local/private-devnet block-production UI path.
- Require a clearly named UI feature switch:
  `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`.
- Require the API server to be started with
  `--enable-local-block-production true`.
- Use a shared API client helper instead of direct Admin UI `fetch(` calls.
- Validate accepted responses with
  `validateLocalBlockProductionAcceptedContract`.
- Render local request id, audit event id, produced block height/hash,
  confirmed transaction hashes, pending before/after counts, chain
  previous/current height, and mutation status.
- Keep wallet send separate and explicit.
- Keep wallet submit deferred unless separately approved.
- Never run block production automatically after wallet send.

## Non-Negotiable Limits

- No block-production UI implementation in this review-only checkpoint.
- No default-enabled `Produce Block` action.
- No direct `fetch(` calls from Admin UI source.
- No hard-coded `/api/v1/blocks/produce` path in Admin UI source.
- No browser persistence for block-production request fields.
- No signing/custody material in browser UI.
- No public mainnet, DEX, bridge, custody, exchange-listing, smart-contract, or
  production behavior.
- No snapshot import/export mutation.

## Required Future Smoke

If implementation is later approved, the first implementation must include a
local live smoke that proves:

- the feature switch is required,
- the explicit API flag is required,
- one pending wallet-send transaction can be produced into exactly one local
  block,
- the pending file removes only confirmed transaction hashes,
- chain height advances exactly one block,
- wallet transaction status changes from pending to confirmed,
- audit metadata is recorded,
- wallet submit remains deferred, and
- no signing or custody fields exist in source or artifacts.

## Validation

Run this review-only design check after edits:

```bash
python scripts/xriq_phase1_2_block_production_ui_design_check.py
```
