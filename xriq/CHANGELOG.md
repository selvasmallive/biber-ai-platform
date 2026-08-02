# Changelog

All notable changes to the XRIQ workspace are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **TEST-ONLY AND VALUELESS.** XRIQ is an experimental, undeployed, valueless test
> chain. Nothing here authorizes value-bearing use. An independent third-party
> security audit and a legal review remain hard gates before any such use.

## [Unreleased]

### Security & test-hardening pass

Closed the outstanding identity-binding gap from the AI-assisted security review and
added adversarial fuzz + property coverage across every attacker-facing decoder and
every block-applying execution path. No behaviour change to valid paths; the test
suite grew from ~343 to 377 workspace tests, all deterministic (seeded, no new
dependencies) and each suite teeth-checked (a deliberate defect was confirmed to fail
the assertion, then reverted).

#### Security

- **Sender↔key binding enforced under Ed25519**, closing the remaining half of
  security-review finding 1 (a signature authenticated possession of *a* key, not
  authority over the claimed `from`). `ed25519_address(tx.public_key) == tx.from` is
  now required at all four layers — the API preview, `XriqNode::submit_transaction`,
  `validate_next_block_state` (block import), and the indexer's
  `replay_private_devnet_block` — via `UnauthorizedSender`. Both halves of finding 1
  (producer↔key and sender↔key) are now closed. The test-only devnet scheme
  deliberately skips the check (insecure by design; opaque accounts unchanged).
- **Peer-sync hardened against adversarial peers** (transport/DoS/SSRF):
  - Bounded HTTP response reads — a 64 MiB body cap and a 30 s total read deadline
    replace the previous unbounded `read_to_end` (memory / slowloris DoS).
  - `--max-rounds` clamped so a pathological value cannot spin the pull loop
    unbounded.
  - SSRF guard on **discovered** peers: peer-advertised hosts resolving to link-local
    / cloud-metadata (`169.254.0.0/16`, `fe80::/10`) or unspecified (`0.0.0.0` / `::`)
    addresses are refused. Loopback/private stay allowed (local testing); an
    operator's own `--peer` / `--peers-file` entries are trusted and not filtered.

#### Added

- **Fuzz harnesses** (deterministic, seeded) for every attacker-controlled decoder:
  - Peer-block wire decoder (`decode_peer_blocks`) — never-panic on arbitrary bytes,
    encode/decode round-trip, canonical-acceptance, and mutation resistance.
  - On-disk chain-store reload (`decode_store` / `FileChainStore::open`) — never-panic,
    record round-trip, mutation resistance, and a real-filesystem reload round-trip.
  - Untrusted wire-text parsers — peer HTTP response parsers and the inbound HTTP
    request line/headers — never-panic plus well-formed-body round-trips.
  - Snapshot manifest parser — never-panic on hostile manifest text.
  - Wallet transfer-draft parser (`parse_private_devnet_transfer_body`, a hand-written
    flat-JSON object parser plus the `field=value` draft parser) — never-panic on
    arbitrary bytes/escapes/multibyte input, plus well-formed JSON and draft
    round-trips.
- **Property tests** for every block-applying path and the core state machines:
  - Ledger `apply_transaction` — total-supply conservation, failure atomicity, nonce
    increment, exact amount/fee routing, determinism.
  - Mempool — capacity, `(from, nonce)` uniqueness, deterministic fee ordering,
    insert/remove inverse, no-mutation on rejected insert.
  - Block validation (`validate_next_block_state`) — a validly produced block is
    accepted; any single-field mutation is rejected atomically.
  - Indexer replay (`replay_private_devnet_store`) — reconstructs exactly the produced
    ledger, conserves supply, is deterministic, and rejects any tampered block.
  - Snapshot export/import — round-trip preserves node status and chain bytes; a
    tampered/missing manifest is rejected on import.
  - RPC response shaping (`RpcService`) — chain-status / account / accounts / mempool /
    transaction responses faithfully mirror ledger and mempool state (ordering,
    address-order, limit caps), and `submit_transaction` is atomic with a
    `pending_count` that matches the post-state.

### Notes

This pass corresponds to commits starting at `d6ff2ca` on `main`. The running engineering
narrative is in [`docs/CODEX_HANDOFF.md`](../docs/CODEX_HANDOFF.md); the review status
is in [`docs/SECURITY_REVIEW.md`](../docs/SECURITY_REVIEW.md) and the design in
[`docs/XRIQ_KEY_DERIVED_ACCOUNTS.md`](../docs/XRIQ_KEY_DERIVED_ACCOUNTS.md).
