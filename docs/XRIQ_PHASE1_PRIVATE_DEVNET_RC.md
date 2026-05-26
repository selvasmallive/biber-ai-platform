# XRIQ Phase 1 Private-Devnet Release Candidate Checklist

Status: Phase 1 readiness checklist for the local/private XRIQ prototype.

This document is the go/no-go checklist for calling **Phase 1: XRIQ
private-devnet prototype** complete. It does not approve public XRIQ launch,
mainnet, token distribution, exchange listing, DEX liquidity, custody, legal
claims, audited cryptography, public validator economics, or production API
exposure.

## Scope

Phase 1 covers only the local/private Rust devnet implementation:

- dependency-free Rust workspace under `xriq/`
- deterministic private-devnet account ledger, mempool, storage, consensus, and
  canonical hashing
- file-backed node runner with replay verification
- private-devnet wallet CLI with test identities and no real custody
- local read-only and submit-capable HTTP wrappers
- snapshot export/import/discovery/check flows
- local smoke/regression coverage that runs without Vast, vLLM, BIBER API, or
  model training

## Required Validation

Before declaring Phase 1 complete, run the CPU-only local gate from the repo
root:

```bash
python scripts/xriq_phase1_local_check.py
```

The gate must complete all default steps without skips:

- `cargo fmt check`
- `python smoke syntax check`
- `cargo test workspace`
- `cargo clippy workspace`
- `transfer smoke`
- `transfer smoke artifact check`
- `http smoke`
- `http smoke artifact check`

The generated `summary.json` under `xriq/target/xriq-phase1-local-check-*`
must report:

```json
{
  "ok": "xriq-phase1-local-check",
  "skipped": []
}
```

The same summary must also include non-empty `artifact_checks` entries for the
generated transfer and HTTP smoke JSON artifacts that prove snapshot export,
latest discovery, latest replay check, explicit snapshot check, snapshot import,
restored chain check, and wallet-flow post-block verification.

After committing the RC checkpoint, run the cheap readiness checker before
asking the user for tag approval:

```bash
python scripts/xriq_phase1_rc_readiness.py --require-clean-git
```

The current human-readable decision report is
`docs/XRIQ_PHASE1_RC_REPORT.md`.

## Functional Checklist

- [x] Rust workspace is split into small crates for core, crypto, ledger,
      mempool, consensus, storage, RPC, explorer, node, and wallet.
- [x] Private-devnet genesis/config is explicit and test-only.
- [x] Canonical transaction hashes, block hashes, state roots, and transaction
      roots exist for the private-devnet baseline.
- [x] Ledger transfer validation covers nonce, fee, balance, missing sender,
      recipient creation, and atomic failure behavior.
- [x] Mempool validation covers duplicates, account nonce conflicts, low-fee
      rejection, deterministic ordering, and capacity behavior.
- [x] Single-authority block production is deterministic and verifies parent,
      transaction root, state root, capacity, and test-only signatures.
- [x] File-backed storage can persist and replay canonical blocks.
- [x] `xriq-node chain-check` verifies replayed chain and durable pending state.
- [x] `xriq-node produce-transfer-block`, `produce-draft-block`, and
      `produce-pending-block` are covered by tests/smokes.
- [x] Wallet transfer, submit, send, status, check, pending, balance, accounts,
      history, and transaction-status flows are covered by tests/smokes.
- [x] Local HTTP read endpoints cover chain status/check, explorer overview,
      blocks, transactions, accounts, mempool, and snapshots.
- [x] Local HTTP submit endpoints cover pending submission, block production,
      direct transaction submission, snapshot export, and snapshot import.
- [x] Snapshot export/import/discovery/detail/check/latest/latest-check flows
      are covered by tests/smokes.
- [x] Checked JSON fixtures cover selected stable wallet/node private-devnet
      response shapes.
- [x] Private-devnet warnings are visible in wallet/node responses.
- [x] Legal-risk guardrails and public-scope deferrals are documented.
- [x] GPU/Vast-independent local validation exists and passes.

## Release Candidate Conditions

Phase 1 can be called an RC only when all of these are true:

- `python scripts/xriq_phase1_local_check.py` passes with no skipped steps.
- The local gate's `artifact_checks` list is non-empty and all listed files
  exist under the generated Phase 1 check artifact root.
- `git status --short` is clean after committing/pushing the RC checkpoint.
- `python scripts/xriq_phase1_rc_readiness.py --require-clean-git` reports
  `ready_for_rc_tag: true`.
- `docs/CODEX_HANDOFF.md` records the latest validation artifact path and Phase
  1 percentage/status.
- `README.md`, `xriq/README.md`, and this checklist point future sessions to the
  local validation gate.
- `docs/XRIQ_PHASE1_RC_REPORT.md` summarizes the candidate scope, latest
  validation artifact, non-production boundaries, and explicit tag-approval
  rule.
- No Phase 1 claim mentions public launch, legal approval, exchange listing,
  audited security, production custody, production privacy, or mainnet readiness.

## Known Non-Production Limitations

These are not Phase 1 blockers because they belong to later phases:

- no public p2p network
- no public validator admission
- no production key management or seed phrase handling
- no audited signature scheme for production custody
- no smart contract VM or XRC token module
- no public tokenomics, treasury, bridge, or liquidity design
- no production monitoring, rate limits, auth, TLS, or abuse controls
- no external audit
- no Zcash-like shielded pool implementation yet

## Phase 1 Exit Note

After this checklist passes and is committed, the next recommended checkpoint is
a `phase1-xriq-private-devnet-rc1` Git tag on the passing commit. Do not create
that tag until the readiness checker passes with `--require-clean-git` and the
user explicitly agrees that the private-devnet prototype is ready to be marked
as an RC.
