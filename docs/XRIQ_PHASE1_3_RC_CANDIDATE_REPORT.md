# XRIQ Phase 1.3 RC Candidate Report

Status: candidate report only. No Phase 1.3 RC tag has been created by this
report.

Proposed tag, only after exact explicit user approval:
`phase1-3-xriq-local-private-behavior-rc1`

Required approval phrase:

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

The local/private Phase 1.3 candidate is ready for user review. The next action
is a human decision, not more automatic implementation:

- approve creating and pushing `phase1-3-xriq-local-private-behavior-rc1`, or
- request another narrow local/private fix before tagging.

Before any tag action, rerun the readiness summary from the repo root:

```bash
python scripts/xriq_phase1_3_readiness_summary.py --cpu-smoke-summary xriq/target/xriq-phase1-3-wallet-behavior-smoke-20260607T131636Z/summary.json
```

Do not tag from a generic continue request. Do not create, move, delete,
recreate, or push the proposed tag unless the user explicitly says:

```text
I explicitly approve creating and pushing the Phase 1.3 RC tag phase1-3-xriq-local-private-behavior-rc1.
```

After that exact approval, run only:

```bash
git tag phase1-3-xriq-local-private-behavior-rc1
git push origin phase1-3-xriq-local-private-behavior-rc1
```

If there is no exact tag approval, keep Phase 1.3 local/private and choose only
one next narrow task: manual demo follow-up, another local/private evidence fix,
or post-RC planning outside this candidate.
