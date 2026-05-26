# XRIQ Phase 1 RC Report

Status: release-candidate decision packet for the local/private XRIQ prototype.

This report summarizes the current Phase 1 private-devnet state for a human
decision about whether to create the `phase1-xriq-private-devnet-rc1` Git tag.
It is not a public launch document, token launch approval, legal opinion,
security audit, mainnet readiness statement, exchange-readiness statement, or
production custody approval.

## Candidate Scope

The candidate covers only the local/private Rust devnet prototype:

- dependency-free Rust workspace under `xriq/`
- deterministic private-devnet ledger, mempool, block production, storage, and
  replay checks
- private-devnet wallet CLI for test identities and local test transfers
- local file-backed node runner and submit-capable HTTP wrapper
- local explorer/account/block/transaction/mempool/snapshot views
- snapshot export/import/discovery/check/latest/latest-check flows
- GPU/Vast-independent local validation and smoke artifacts

## Latest Validation

The latest full local validation gate was:

```bash
python scripts/xriq_phase1_local_check.py
```

Latest generated summary:

```text
xriq/target/xriq-phase1-local-check-20260526T164037/summary.json
```

That summary reports:

- `ok: xriq-phase1-local-check`
- `skipped: []`
- 8 completed gate steps
- 15 checked smoke artifact files

The gate covers:

- Rust format check
- Python smoke syntax check
- full XRIQ workspace tests
- full XRIQ workspace clippy with warnings denied
- isolated transfer/replay/snapshot smoke
- local submit-capable HTTP smoke
- transfer smoke artifact checks
- HTTP smoke artifact checks

## Readiness Check

After this report and handoff are committed and pushed, run:

```bash
python scripts/xriq_phase1_rc_readiness.py --require-clean-git --require-origin-main
```

The expected result before asking for tag approval is:

```json
{
  "ok": "xriq-phase1-rc-readiness",
  "origin_main_matches_head": true,
  "ready_for_rc_tag": true
}
```

The readiness checker validates the latest local-check summary, required
completed steps, checked artifact files, clean git state, local HEAD matching
`origin/main`, and the documentation references needed for future sessions to
resume safely.

## Explicit Non-Production Boundaries

This Phase 1 candidate does not include:

- public p2p networking
- public validator admission or token economics
- smart contract VM or XRC token module
- bridges, exchange listing, liquidity, custody, payments, or stablecoin flows
- production key management
- audited cryptography or audited protocol security
- production privacy implementation
- mainnet readiness
- BIBER MVP, model training, Vast/vLLM runtime, or repo-agent workflows

## Tag Decision

Only after the readiness checker passes with `--require-clean-git
--require-origin-main`, ask the user for explicit approval to create:

```text
phase1-xriq-private-devnet-rc1
```

Do not create or push that tag from a general "continue" request. The approval
must clearly say that the user approves marking the XRIQ private-devnet
prototype as Phase 1 RC1.
