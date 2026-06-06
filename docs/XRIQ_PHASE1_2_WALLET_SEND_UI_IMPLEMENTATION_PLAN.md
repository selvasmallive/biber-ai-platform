# XRIQ Phase 1.2 Wallet-Send UI Implementation Plan

Plan Status: Approved And Implemented Behind Feature Switch

This document defines the first allowed UI mutation candidate after the
Phase 1.2 UI mutation-control gate. The user explicitly approved this exact
wallet-send implementation on 2026-06-06. It does not approve wallet submit or
any broader mutation scope.

## First Candidate

First candidate: wallet send only.

Wallet submit remains deferred. Wallet send is the safer first UI mutation
candidate because the local API already has:

- a guarded local/private-devnet accepted response,
- a shared TypeScript accepted-response validator,
- local E2E artifact coverage,
- pending-to-confirmed lifecycle smoke coverage,
- readiness-summary coverage, and
- UI mutation-control gate coverage.

## Preconditions

Implementation was allowed only after all of these were true:

- `scripts/xriq_phase1_2_readiness_summary.py` passes.
- `scripts/xriq_phase1_2_ui_mutation_gate_check.py` passes.
- `scripts/xriq_phase1_2_wallet_send_ui_plan_check.py` passes.
- The user gives explicit approval naming the UI mutation-control gate and
  wallet send as the exact local/private action.

## Current Implementation

Current implementation:

- `xriq/apps/explorer-ui/src/api.ts` exposes `sendLocalWalletTransfer`.
- `sendLocalWalletTransfer` posts only to the local wallet-send API path,
  expects HTTP `201`, and validates the response with
  `validateLocalWalletSendAcceptedContract`.
- `xriq/apps/explorer-ui/src/wallet.tsx` renders `Local Wallet Send`.
- `Local Wallet Send` is active only when
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`.
- The send button is disabled by default, disabled during validation failures,
  and disabled while a local send is in flight.
- The UI renders local request id, audit event id, pending transaction hash,
  pending file marker, chain file marker, mutation, status, and chain unchanged
  state after an accepted local send.
- Wallet submit remains disabled and deferred.
- Block production remains separate and explicit.

Current live UI smoke:

- `xriq/apps/explorer-ui/scripts/check-wallet-send-ui-live.mjs` imports the
  real `sendLocalWalletTransfer` helper through Vite SSR and calls a live
  local/private `xriq-api serve-readonly` endpoint.
- `scripts/xriq_phase1_2_wallet_send_ui_live_smoke.py` starts the temporary API
  with `--enable-local-wallet-send true` only, sets
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`, and verifies exactly one
  pending wallet-send response through the shared UI client.
- The smoke verifies the pending file gains the accepted transaction, the chain
  height remains unchanged, wallet submit still returns the disabled/refused
  response, and block production still returns the disabled/refused response.

## Allowed Implementation Shape

After explicit approval, the implementation must remain narrow:

- Add only a local/private-devnet wallet-send UI path.
- Keep wallet submit disabled and deferred.
- Add a clearly named local-only UI feature switch, such as
  `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`.
- Use the shared API client instead of direct wallet UI `fetch(` calls.
- Validate successful responses with `validateLocalWalletSendAcceptedContract`.
- Render the local request id, audit event id, pending transaction hash,
  pending file marker, chain file marker, and pending-state-only mutation.
- Keep block production as a separate explicit local action.
- Do not silently produce a block after wallet send.
- Keep the default UI state disabled when the feature switch is absent.

## Non-Negotiable Limits

- No wallet submit UI mutation in this step.
- No signing/custody material in browser UI.
- No private key, seed phrase, mnemonic, raw signature, or signed transaction
  fields.
- No browser persistence for wallet-send inputs.
- No public mainnet, DEX, bridge, custody, exchange-listing, or production
  behavior.
- No snapshot import/export mutation.
- No smart-contract behavior.
- No implicit block production.

## Required Smoke After Implementation

The first implementation adds `check-wallet-send-ui-control.mjs` to prove:

- default UI remains disabled without the feature switch,
- wallet submit remains disabled even with wallet-send UI enabled,
- wallet send can call only the local/private-devnet accepted API path through
  the shared API client,
- the accepted response validates through the shared client validator,
- one pending transaction is rendered after send,
- the audit event id and local request id are visible,
- the chain remains unchanged immediately after send,
- no private key, seed phrase, mnemonic, raw signature, or signed transaction
  fields exist in source or artifacts, and
- block production remains a separate explicit local action.

## Explicit Approval Record

The implementation was approved with this exact approval:

```text
I explicitly approve implementing the Phase 1.2 local/private-devnet wallet-send
UI mutation control behind the UI mutation-control gate.
```

## Validation

Run this implementation check after changes:

```bash
python scripts/xriq_phase1_2_wallet_send_ui_plan_check.py
```

Run this local live smoke when refreshing the server-backed UI evidence:

```bash
python scripts/xriq_phase1_2_wallet_send_ui_live_smoke.py
```
