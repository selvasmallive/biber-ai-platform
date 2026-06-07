# XRIQ Phase 1.2 UI Mutation-Control Gate

Gate Status: Approved For Wallet Send And Block Production

This document is the Phase 1.2 gate that must be reviewed before any wallet
submit/send or block-production mutation control is enabled in the React UI.
The user explicitly approved the local/private-devnet wallet-send UI mutation
control behind this gate on 2026-06-06. The user explicitly approved the
local/private-devnet block-production UI mutation control behind this gate on
2026-06-07. This does not approve wallet submit or any broader mutation scope.

## Scope

This gate applies only to local/private-devnet wallet send and local/private
block production from pending transactions. It is not public mainnet, DEX,
custody, bridge, exchange-listing, smart contract, production infrastructure,
or snapshot-mutation scope.

## Current Decision

Default UI mutation controls remain disabled.

In default mode, the current wallet UI may show disabled `Submit Draft` and
`Send Transfer` controls only as guard indicators. The only active wallet
action button in default mode may be `Check Guards`, which must call
disabled/refusal checks and must not submit, send, sign, persist secrets, or
mutate pending/chain state.

Approved exception: wallet send may be enabled only when
`VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true` is set and the local API is
started with `--enable-local-wallet-send true`. The wallet-send UI path must
use the shared API client, validate `wallet_send_accepted_local_only`, mutate
pending state only, keep wallet submit deferred, and ensure wallet submit
remains deferred.

Approved exception: block production may be enabled only when
`VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true` is set and the local API is
started with `--enable-local-block-production true`. The block-production UI
path must use the shared API client, validate
`block_production_accepted_local_only`, mutate only local chain and pending
state, keep wallet send separate and explicit, and keep wallet submit
deferred.

wallet submit remains deferred.

## Required Evidence Before Implementation Review

Before any implementation review may start, the repo must have passing evidence
for all of the following:

- Phase 1.2 refusal smoke for wallet submit, wallet send, and block production.
- Phase 1.2 accepted wallet-submit and wallet-send local artifacts.
- Phase 1.2 wallet-send lifecycle evidence proving pending-to-confirmed flow.
- Phase 1.2 readiness summary with
  `ready_for_ui_mutation_design_review: true`.
- The same readiness summary must still report
  `ui_mutation_controls_enabled: false`,
  `safe_to_enable_ui_mutation_controls: false`, and
  `approval_required_before_ui_mutation_controls: true`.

## Non-Negotiable UI Rules

Any future UI mutation-control implementation must keep these rules until a
later explicit approval changes them:

- No private key, seed phrase, mnemonic, raw signature, or signed transaction
  fields in the browser UI.
- No direct `fetch(` calls from wallet UI source.
- No hard-coded wallet submit/send endpoint strings in wallet UI source.
- No default-enabled submit/send controls.
- No default-enabled block-production control.
- No public-network, DEX, custody, bridge, exchange-listing, or production
  language in the local wallet mutation UI.
- No local storage, session storage, indexed DB, or cookie persistence for
  wallet mutation inputs.
- No mutation request unless the server is explicitly started with the matching
  local/private flag.
- No mutation request unless the UI is in a clearly marked local/private-devnet
  mode and shows refusal/audit expectations.

## Future Implementation Review Checklist

The approved wallet-send and block-production implementation must stay narrow:

- Add a local/private-devnet-only UI path for one action first, preferably
  wallet send.
- Keep wallet submit deferred unless wallet send passes review and smoke tests.
- Require `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`.
- Use the shared API client and accepted-response validators.
- Show pending-state-only mutation language before and after the request.
- Render the audit event id, local request id, pending file marker, chain file
  marker, and resulting pending transaction hash.
- Keep block production a separate explicit local action; wallet send must not
  silently produce blocks.
- Keep a local UI smoke artifact current before any RC or tag. The current
  live-smoke path is `scripts/xriq_phase1_2_wallet_send_ui_live_smoke.py`.
- Keep read-only refresh evidence current before any additional mutation UI is
  considered. The current refresh-smoke path is
  `scripts/xriq_phase1_2_wallet_send_refresh_smoke.py`.
- Keep block-production UI live-smoke evidence current. The current live-smoke
  path is `scripts/xriq_phase1_2_block_production_ui_live_smoke.py`.

## Approval Required

Explicit user approval is required before enabling any additional wallet submit,
snapshot mutation, DEX, smart-contract, public-network, or production mutation
control. The approval must name this gate and the exact action being enabled.

Acceptable approval shape:

```text
I explicitly approve implementing the Phase 1.2 local/private-devnet wallet-send
UI mutation control behind the UI mutation-control gate.
```

Accepted approval shape for the block-production local control:

```text
I explicitly approve implementing the Phase 1.2 local/private-devnet
block-production UI mutation control behind the UI mutation-control gate.
```

## Validation

Run the gate check before any UI mutation-control implementation:

```bash
python scripts/xriq_phase1_2_ui_mutation_gate_check.py
```
