# Changelog

All notable changes to the XRIQ workspace are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **TEST-ONLY AND VALUELESS.** XRIQ is an experimental, undeployed, valueless test
> chain, and nothing here authorizes value-bearing use. Deployment-phase progression
> is governed by Network Governance Authority phase authorization; an independent
> third-party security audit and legal review are recommended risk-reduction measures,
> **not** absolute engineering prerequisites (see `docs/XRIQ_LEGAL_RISK_REDUCTION.md`
> §1 and `docs/SECURITY_REVIEW.md` §1). As a matter of fact, neither has been
> performed.

## [Unreleased]

### Authorized-wallet registry (test-only governance)

Added an on-chain authorized-wallet allowlist to ledger state, mutated by a new
authority-gated governance transaction and folded into the consensus state root
without shifting any existing golden. Still TEST-ONLY and VALUELESS: the registry
carries no value, governance transactions move no units, and nothing here changes
XRIQ's deployment-phase posture. The suite grew from 379 to 394 workspace tests, all
deterministic (seeded, no new dependencies) and each new suite teeth-checked.

#### Added

- **`TxAction` on `Transaction`** — an action enum (`xriq-core`) with the default
  `Transfer` plus governance variants `AuthorizeWallet { target }` /
  `RevokeWallet { target }`. Governance transactions are valueless and self-addressed
  (`amount == 0`, `to == from`), enforced by new `validate_basic` errors
  `GovernanceMustBeValueless` / `GovernanceRecipientNotSelf`.
- **On-chain registry in `LedgerState`** (`xriq-ledger`) — an ordered `BTreeSet`
  allowlist with `is_authorized` / `authorize` / `revoke` / `authorized_wallets`.
  `apply_transaction` applies a governance action atomically alongside the fee
  (registry + accounts commit together; a rejected transaction mutates neither).
- **Registry folded into the consensus state root** — a new
  `xriq_crypto::ledger_state_root(accounts, authorized)` and a single
  `LedgerState::state_root()` that every node (producer, importer, RPC, indexer) now
  routes through. The registry section is appended to the root preimage **only when
  non-empty**, so a chain that never authorizes a wallet keeps a byte-identical root;
  `account_state_root` is exactly the empty-registry case. `TxAction::Transfer`
  likewise encodes to zero trailing bytes, so every existing transfer hash and
  `transactions_root` is unchanged.

#### Security

- **Governance is authority-only**, enforced identically at every enforcement layer,
  mirroring the sender↔key binding: `XriqNode::submit_transaction`,
  `validate_next_block_state` (block import), and the indexer's
  `replay_private_devnet_block` reject a registry mutation whose sender is not the
  chain authority (`UnauthorizedGovernanceAuthority` /
  `IndexReplayError::UnauthorizedGovernanceAuthority`), atomically. The mempool admits
  valueless governance transactions (the zero-amount policy applies only to
  transfers); the fee floor still applies to both. The public wallet HTTP API surface
  is transfer-only by construction — no code path constructs a governance action and
  its parsers default to `Transfer` — so no registry mutation can be injected there.

#### Tests

- `xriq-ledger`: registry idempotency + authorize↔revoke inverse; governance apply
  (valueless, fee-charging, atomic); and two 20k-iteration seeded properties —
  registry-root stability (empty root == account-only root; authorize changes it;
  revoke restores it) and governance-apply atomicity/registry-only-movement.
- `xriq-crypto`: `ledger_state_root` empty-registry equality and sorted/deduped
  registry commitment.
- `xriq-storage`: governance actions survive the block codec round-trip.
- `xriq-node`: submit and import both reject non-authority governance atomically;
  authority governance applies end-to-end and is reflected in the state root and a
  follower's imported state.
- `xriq-indexer`: replay rejects non-authority governance.
- Each new suite teeth-checked (a deliberate defect was confirmed to fail the
  assertion, then reverted).

### Security & test-hardening pass

Closed the outstanding identity-binding gap from the AI-assisted security review and
added adversarial fuzz + property coverage across every attacker-facing decoder and
every block-applying execution path. No behaviour change to valid paths; the test
suite grew from ~343 to 379 workspace tests, all deterministic (seeded, no new
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
  - Audit-record path — the indexer emits exactly one idempotent `index_block` audit
    event per block (correct id/actor/resource), and the API's `admin_audit_events`
    response mirrors the read-model trail sorted by event id descending and truncated
    to the limit.

### Notes

This pass corresponds to commits starting at `d6ff2ca` on `main`. The running engineering
narrative is in [`docs/CODEX_HANDOFF.md`](../docs/CODEX_HANDOFF.md); the review status
is in [`docs/SECURITY_REVIEW.md`](../docs/SECURITY_REVIEW.md) and the design in
[`docs/XRIQ_KEY_DERIVED_ACCOUNTS.md`](../docs/XRIQ_KEY_DERIVED_ACCOUNTS.md).
