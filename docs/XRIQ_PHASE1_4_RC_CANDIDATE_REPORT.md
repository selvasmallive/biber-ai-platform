# XRIQ Phase 1.4 RC Candidate Report

Status: candidate report only. No Phase 1.4 RC tag has been created by this
document.

Proposed RC tag:
`phase1-4-xriq-local-signed-submit-rc1`

Pre-report implementation checkpoint reviewed for this candidate: `50b8281`.

Exact approval phrase required before creating or pushing the proposed tag:

```text
I explicitly approve creating and pushing the Phase 1.4 RC tag phase1-4-xriq-local-signed-submit-rc1.
```

Do not tag from a generic continue request.

## Candidate Scope

This candidate covers the local/private XRIQ Phase 1.4 signed-submit wallet
prototype scope:

- signed-transfer fixture inventory for local signing intent, test-only signed
  envelope, disabled response, invalid signature response, negative cases, and
  accepted local/private response
- CLI-only `xriq-wallet signed-transfer` test artifact generation and
  inspection, with no persistent key storage
- default-disabled `POST /api/v1/wallet/transfers/submit-signed` route with
  local refusal/audit visibility
- Rust-side signed-submit parse/verify preview for transaction hash, signing
  hash, chain id, nonce, expiry, duplicate pending state, and test-only
  signature metadata
- accepted local/private pending-file mutation only behind
  `--enable-local-wallet-submit-signed true`
- CPU-only lifecycle smoke proving a CLI-only signed artifact can move through
  accepted signed submit, pending status, local block production, confirmed
  wallet/explorer/mempool/Admin read-back, and disabled/invalid refusal checks

## Latest Validation Evidence

Latest Phase 1.4 signed-submit lifecycle smoke:

```text
xriq/target/xriq-phase1-4-signed-submit-lifecycle-smoke-20260609T024220Z/summary.json
```

The lifecycle summary reports:

- `ok`: `xriq-phase1-4-signed-submit-lifecycle-smoke`
- signed-submit transaction hash:
  `628ac2587bbae121654089ffb42cd1e2b1a59384c8e9b9206c925873783d40f7`
- signed-submit signing hash:
  `3c0f7f54bca53ad4c49ff98ba9ba2930ac6147a3cb510ead3265c894fcf1850b`
- produced block hash:
  `47172db5651427f6a35a1e5199e71899afc6a7daf3bea800b8c0d3d1990241db`

Latest Phase 1.4 plan check:

```text
xriq/target/xriq-phase1-4-plan-check-20260609T030347Z/summary.json
```

Latest Phase 1.4 CLI-only signed artifact check:

```text
xriq/target/xriq-phase1-4-signed-artifact-check-20260609T024602Z/summary.json
```

Required supporting evidence:

```text
xriq/target/xriq-phase1-4-contract-check-20260608T231501Z/summary.json
xriq/target/xriq-phase1-4-signed-submit-negative-smoke-20260608T231551Z/summary.json
xriq/target/xriq-phase1-4-signed-submit-refusal-smoke-20260608T231601Z/summary.json
```

Rust accepted-mutation validation also passed:

```text
cargo test --target-dir target-codex-phase14-signed-accepted -p xriq-api -j 1
```

## RC Go/No-Go Checklist

- [x] Scope remains local/private and non-production.
- [x] Signed-transfer fixtures and contract checks pass.
- [x] CLI-only test signing creates a verifiable local artifact.
- [x] Signed-submit API refuses by default with `signed_submit_disabled`.
- [x] Accepted signed-submit requires
      `--enable-local-wallet-submit-signed true`.
- [x] Accepted signed-submit verifies before pending-state mutation.
- [x] Accepted signed-submit appends exactly one verified pending transaction.
- [x] Disabled/default and invalid-input paths are non-mutating.
- [x] A signed transfer moves from signed artifact to pending to confirmed in
      the lifecycle smoke.
- [x] Wallet, mempool, explorer, Admin, and audit read-back are covered.
- [x] Block production remains explicitly gated with
      `--enable-local-block-production true`.
- [x] No wallet submit UI mutation is included.
- [x] No browser key generation, browser key storage, seed phrase handling,
      custody, hosted signing, raw signature logging, public network behavior,
      DEX, bridge, smart contract, production infrastructure, or exchange
      listing scope is included.
- [x] A generic continue request is explicitly not approval to create or push
      the proposed RC tag.

## Pre-Tag Readiness Guard

Run the cheap readiness guard from the repo root:

```bash
python scripts/xriq_phase1_4_rc_readiness.py
```

After the candidate report checkpoint is committed and pushed, a stricter local
check can be run without rerunning Rust:

```bash
python scripts/xriq_phase1_4_rc_readiness.py --require-clean-git --require-origin-main --require-tag-absent --write-summary
```

This guard checks the candidate report, selected evidence summaries, required
docs references, local tag absence, and the explicit no-generic-approval rule.
It does not create, move, delete, recreate, or push any tag.

## Non-Production Boundaries

This RC candidate does not approve or include:

- public mainnet, public devnet, validator admission, tokenomics, governance,
  launch claims, or public API exposure
- DEX trading, liquidity pools, bridges, wrapped assets, CEX listings, custody,
  payment processing, stablecoins, market-facing claims, or exchange-readiness
  claims
- production signing, seed phrase handling, private-key persistence, hosted
  wallet custody, HSM/KMS integration, or production key management
- wallet submit UI mutation, browser-held key material, snapshot
  import/export mutation, smart-contract VM, XRC asset issuance, native DEX
  modules, or asset-issuance economics
- production GCP/Vast/server resources, TLS, public auth, rate limits,
  monitoring, external audit, legal approval, ISO certification, bank
  connectivity, SWIFT connectivity, fiat settlement, or payment-network
  settlement

## Candidate Decision

This is ready for a human Phase 1.4 RC decision after the pre-tag readiness
guard passes from a clean pushed checkout.

If the user wants the tag created and pushed, they must approve the exact tag
name with:

```text
I explicitly approve creating and pushing the Phase 1.4 RC tag phase1-4-xriq-local-signed-submit-rc1.
```

Until that approval is given, leave
`phase1-4-xriq-local-signed-submit-rc1` uncreated.
