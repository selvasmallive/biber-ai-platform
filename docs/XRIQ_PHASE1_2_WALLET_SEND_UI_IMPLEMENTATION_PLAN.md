# XRIQ Phase 1.2 Wallet-Send UI Implementation Plan

Plan Status: Review Only - Not Implemented

This document defines the first allowed UI mutation candidate after the
Phase 1.2 UI mutation-control gate. It does not approve implementation and does
not enable wallet submit/send controls.

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

Implementation must not start until all of these are true:

- `scripts/xriq_phase1_2_readiness_summary.py` passes.
- `scripts/xriq_phase1_2_ui_mutation_gate_check.py` passes.
- `scripts/xriq_phase1_2_wallet_send_ui_plan_check.py` passes.
- The user gives explicit approval naming the UI mutation-control gate and
  wallet send as the exact local/private action.

## Allowed Implementation Shape

After explicit approval, the implementation should be narrow:

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

The first implementation must add or extend a local UI smoke that proves:

- default UI remains disabled without the feature switch,
- wallet submit remains disabled even with wallet-send UI enabled,
- wallet send can call only the local/private-devnet accepted API path,
- the accepted response validates through the shared client validator,
- one pending transaction is rendered after send,
- the audit event id and local request id are visible,
- the chain remains unchanged immediately after send,
- no private key, seed phrase, mnemonic, raw signature, or signed transaction
  fields exist in source or artifacts, and
- block production remains a separate explicit local action.

## Explicit Approval Required

Use this exact approval shape before implementation starts:

```text
I explicitly approve implementing the Phase 1.2 local/private-devnet wallet-send
UI mutation control behind the UI mutation-control gate.
```

## Validation

Run this review-only plan check before requesting implementation approval:

```bash
python scripts/xriq_phase1_2_wallet_send_ui_plan_check.py
```
