# XRIQ Phase 1.2 UI Mutation-Control Gate

Gate Status: Design Review Only

This document is the Phase 1.2 gate that must be reviewed before any wallet
submit/send mutation control is enabled in the React UI. It does not approve
UI mutation controls and does not change runtime behavior.

## Scope

This gate applies only to the local/private-devnet wallet submit/send flow.
It is not public mainnet, DEX, custody, bridge, exchange-listing, smart
contract, production infrastructure, or snapshot-mutation scope.

## Current Decision

UI mutation controls remain disabled.

The current wallet UI may show disabled `Submit Draft` and `Send Transfer`
controls only as guard indicators. The only active wallet action button may be
`Check Guards`, which must call disabled/refusal checks and must not submit,
send, sign, persist secrets, or mutate pending/chain state.

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
- No public-network, DEX, custody, bridge, exchange-listing, or production
  language in the local wallet mutation UI.
- No local storage, session storage, indexed DB, or cookie persistence for
  wallet mutation inputs.
- No mutation request unless the server is explicitly started with the matching
  local/private flag.
- No mutation request unless the UI is in a clearly marked local/private-devnet
  mode and shows refusal/audit expectations.

## Future Implementation Review Checklist

When the user explicitly approves implementation after this gate, the first UI
implementation review should be narrow:

- Add a local/private-devnet-only UI path for one action first, preferably
  wallet send.
- Keep wallet submit deferred unless wallet send passes review and smoke tests.
- Require an explicit local UI feature flag or review-only route marker.
- Use the shared API client and accepted-response validators.
- Show pending-state-only mutation language before and after the request.
- Render the audit event id, local request id, pending file marker, chain file
  marker, and resulting pending transaction hash.
- Keep block production a separate explicit local action; wallet send must not
  silently produce blocks.
- Add a local UI smoke artifact before any RC or tag.

## Approval Required

Explicit user approval is required before enabling any wallet submit/send UI
mutation control. The approval must name this gate and the exact action being
enabled.

Acceptable approval shape:

```text
I explicitly approve implementing the Phase 1.2 local/private-devnet wallet-send
UI mutation control behind the UI mutation-control gate.
```

## Validation

Run the gate check before any UI mutation-control implementation:

```bash
python scripts/xriq_phase1_2_ui_mutation_gate_check.py
```
