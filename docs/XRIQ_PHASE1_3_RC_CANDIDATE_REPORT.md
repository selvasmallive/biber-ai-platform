# XRIQ Phase 1.3 RC Candidate Report

Status: candidate report with completed RC tag action.

Approved RC tag:
`phase1-3-xriq-local-private-behavior-rc1`

Post-report tag status: after exact explicit user approval on 2026-06-08, the
tag `phase1-3-xriq-local-private-behavior-rc1` was created and pushed at
commit `345d353`.

Historical approval phrase used:

```text
I explicitly approve creating and pushing the Phase 1.3 RC tag phase1-3-xriq-local-private-behavior-rc1.
```

Pre-report implementation checkpoint reviewed for this candidate: `605ec1e`.

## Candidate Scope

This candidate covers the local/private XRIQ Phase 1.3 behavioral wallet testing
scope:

- canonical local/private behavior fixture for Alice, Bob, Carol, fee sink, and
  test producer identities
- CPU-only wallet behavior smoke for one local wallet-send request, pending
  state, one local block production, confirmed state, account balances, history,
  mempool, explorer, Admin, and audit visibility
- UI-backed shared TypeScript client behavior smoke over local `xriq-api`
  request paths
- negative/default behavior coverage for disabled wallet send, disabled block
  production, invalid wallet send, no-pending block production, and deferred
  wallet submit
- consolidated readiness and negative-matrix summary
- local/private browser demo launcher and runbook for the manual wallet
  send-to-confirmed walkthrough

## Latest Validation Evidence

Latest Phase 1.3 readiness summary:

```text
xriq/target/xriq-phase1-3-readiness-summary-20260608T135807Z/summary.json
```

The summary reports:

- `ok`: `xriq-phase1-3-readiness-summary`
- `behavioral_readiness_ok`: `true`
- `ready_for_phase1_3_candidate_report`: `true`
- `ready_to_create_tag_now`: `false`
- `generic_continue_is_approval`: `false`
- proposed future tag: `phase1-3-xriq-local-private-behavior-rc1`

Required local/private evidence:

```text
xriq/target/xriq-phase1-3-behavior-contract-check-ui-smoke-final2/summary.json
xriq/target/xriq-phase1-3-wallet-behavior-smoke-20260607T131636Z/summary.json
xriq/target/xriq-phase1-3-wallet-behavior-ui-smoke-20260607T132901Z/summary.json
xriq/target/xriq-phase1-3-demo-20260607T135028Z/summary.json
```

The selected smoke evidence proves:

- base confirmed transfer hash:
  `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`
- local wallet-send behavior transaction hash:
  `628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7`
- produced local block hash:
  `47172db5651427f6a35a1e5199e71899afc6a7daf3bea800b8c0d3d1990241db`
- negative cases checked: disabled wallet send, disabled block production,
  invalid wallet send, no-pending block production, and deferred wallet submit

## RC Go/No-Go Checklist

- [x] Scope remains local/private and non-production.
- [x] The behavior fixture is documented and contract-checked.
- [x] CPU-only one-shot wallet send plus one-block production smoke passes.
- [x] UI-backed shared-client behavior smoke passes with explicit local/private
      feature switches.
- [x] Wallet status, balances, history, mempool, explorer, Admin, and audit
      state are covered by the selected evidence.
- [x] Disabled/default and invalid-input negative paths are covered.
- [x] Wallet submit UI remains deferred.
- [x] Browser demo runbook and launcher exist for a human walkthrough.
- [x] No private keys, seed phrases, signing, custody, public networking, DEX,
      smart contracts, GCP, Vast, Docker, exchange-listing, or production
      infrastructure scope is introduced.
- [x] A generic continue request is explicitly not approval to create or push
      the proposed RC tag.

## Manual Browser Demo

Run the local/private browser demo from the repo root:

```powershell
python scripts\xriq_phase1_3_demo_launcher.py --skip-build --launch --auto-port
```

Then follow `docs/XRIQ_PHASE1_3_DEMO_RUNBOOK.md`.

The expected final state after the manual demo is:

- chain height `2`
- mempool pending count `0`
- wallet pending count `0`
- Alice balance `66` with nonce `2`
- Bob balance `25`
- Carol balance `5`
- fee sink balance `4`
- the behavior transaction is confirmed at block height `2`, transaction index
  `0`

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

The local/private Phase 1.3 candidate was reviewed as a documentation and
evidence checkpoint. The human decision was completed after exact explicit user
approval on 2026-06-08.

Pre-tag validation passed:

```bash
python scripts/xriq_phase1_3_readiness_summary.py --cpu-smoke-summary xriq/target/xriq-phase1-3-wallet-behavior-smoke-20260607T131636Z/summary.json
```

Then the tag was created and pushed:

```bash
git tag phase1-3-xriq-local-private-behavior-rc1
git push origin phase1-3-xriq-local-private-behavior-rc1
```

Do not move, delete, recreate, or repush
`phase1-3-xriq-local-private-behavior-rc1` unless the user explicitly asks for
that exact tag maintenance operation.

Next scope is post-RC or next-phase work only, still local/private unless the
user explicitly approves broader scope.
