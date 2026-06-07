# XRIQ Phase 1.2 Block-Production UI Design

Design Status: Approved And Implemented Behind Feature Switch

This document defines a possible future local/private-devnet UI mutation
control for producing one block from pending transactions. The user explicitly
approved implementation of this narrow control behind the UI mutation-control
gate on 2026-06-07.

## Candidate Scope

Candidate: local block production only.

This candidate would be separate from wallet send. Wallet send must never
silently produce a block after creating a pending transaction.

The UI continues to show the disabled `Produce Block` guard and the active
`Check Guard` action. The disabled guard proves the default route still refuses
mutation. The approved implementation adds a separate `Local Block Production`
control that remains inert unless explicitly feature-switched on.

## Preconditions Before Implementation

Implementation was allowed only because all of these were true:

- `scripts/xriq_phase1_2_block_production_ui_design_check.py` passes.
- `scripts/xriq_phase1_2_ui_mutation_gate_check.py` passes.
- `scripts/xriq_phase1_2_wallet_send_refresh_smoke.py` passes.
- The user gave explicit approval naming this gate and the exact local block
  production UI mutation control.

Required approval phrase:

```text
I explicitly approve implementing the Phase 1.2 local/private-devnet
block-production UI mutation control behind the UI mutation-control gate.
```

Approval received:

```text
I explicitly approve implementing the Phase 1.2 local/private-devnet block-production UI mutation control behind the UI mutation-control gate.
```

## Current Implementation

Current implementation:

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

- No default-enabled `Produce Block` action.
- No direct `fetch(` calls from Admin UI source.
- No hard-coded `/api/v1/blocks/produce` path in Admin UI source.
- No browser persistence for block-production request fields.
- No signing/custody material in browser UI.
- No public mainnet, DEX, bridge, custody, exchange-listing, smart-contract, or
  production behavior.
- No snapshot import/export mutation.

## Current Live Smoke

Current live UI smoke:

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

The live smoke is:

```bash
python scripts/xriq_phase1_2_block_production_ui_live_smoke.py
```

Current Admin refresh smoke:

- uses the same exported `adminSnapshotRows` helper as the Admin UI,
- verifies Admin rows show one pending transaction before block production,
- verifies Admin rows show network height `2` and zero pending after block
  production,
- keeps the read-only status rows disabled even while the explicit local action
  helper is allowed by the server flags,
- verifies wallet submit remains deferred, and
- verifies no signing or custody fields exist in source or artifacts.

```bash
python scripts/xriq_phase1_2_block_production_admin_refresh_smoke.py
```

Current no-pending negative smoke:

- requires the feature switch so the local block-production control source is
  loaded,
- starts the API with `--enable-local-block-production true` but no pending
  transactions,
- calls the shared `produceLocalBlockNoPendingRefusal` helper,
- verifies HTTP `400` `no_pending_transactions`,
- verifies Admin rows stay at height `1` with zero pending transactions,
- verifies network, mempool, and pending-file state are unchanged, and
- keeps wallet send and wallet submit disabled in this smoke.

```bash
python scripts/xriq_phase1_2_block_production_no_pending_smoke.py
```

## Validation

Run this implementation design check after edits:

```bash
python scripts/xriq_phase1_2_block_production_ui_design_check.py
```
