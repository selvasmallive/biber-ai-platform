# XRIQ Production Cryptography Migration

Version: 1.0 (design — not yet implemented)

## Purpose

Design the replacement of the **test-only** signature scheme with production
digital signatures, as required by Phase 1 of
`docs/XRIQ_PRODUCTION_READINESS_ROADMAP.md` ("replace ALL placeholder
implementations with Ed25519 or secp256k1 using mature Rust crypto libraries. No
custom cryptography. Every signature verified; every transaction authenticated").

This is a **security-critical** change. It must be done to audit-quality standards
with AI-assisted security review after the feature lands (roadmap Phase 8), and it
must not ship half-done. This document is the architecture/design gate that
precedes any code.

> Status: DESIGN ONLY. No production crypto is implemented yet. The current build
> uses `xriq_crypto::TestOnlySignatureVerifier` — a placeholder that is **not**
> secure and must never be run on a value-bearing network.

## Current state (what is being replaced)

- `xriq-crypto` exposes `TestOnlySignatureVerifier` and
  `test_only_signature_for_hash(hash)` — a deterministic, non-secret
  "signature" derived from the signing hash. It authenticates nothing.
- Signing hashes are already canonical and domain-separated:
  `transaction_signing_hash(&Transaction)` and
  `block_header_signing_hash(&BlockHeader)` (SHA-256). These are the messages a
  real scheme will sign; **they do not change**.
- Call sites: transaction submission validation (`xriq-node`
  `submit_transaction` → `TestOnlySignatureVerifier.verify_transaction`), block
  production (`produce_next_block_with_private_devnet_signature` signs the header
  with the test-only signature), the faucet core (signs a faucet→recipient
  transfer), and every test that builds a signed transaction/block.
- Identities today: addresses are opaque `xriqdev1<payload>` strings unrelated to
  any key; the single-authority producer is an address, not a public key.

## Chosen scheme

**Ed25519** (via `ed25519-dalek` v2, which wraps the audited `curve25519-dalek`).

Rationale:
- Deterministic signatures (no per-signature RNG failure mode), fast verification,
  small 32-byte public keys / 64-byte signatures, wide ecosystem + hardware-wallet
  support, and a mature, audited Rust implementation. No custom cryptography.
- secp256k1 (via the `k256`/`secp256k1` crates) is the alternative if
  Ethereum/Bitcoin tooling compatibility becomes a requirement; the trait seam
  below keeps that option open. Pick ONE for mainnet; Ed25519 is the default
  recommendation.

Hashing stays SHA-256 (already used); Ed25519 signs the 32-byte signing hash.

## Address ↔ key binding

Introduce a real account identity: an address is derived from a public key so a
signature can be checked against the `from` address without a separate registry.

- `address = "xriq1" + bech32(version || sha256(pubkey)[..20])` (or keep the
  existing 24–96 char payload format but define it as
  `hex(sha256(pubkey)[..N])`). Exact encoding is a sub-decision; the invariant is
  **address is a function of the public key**, verifiable offline.
- The genesis `authority` (block producer) and `fee_sink` become **public keys**
  (or key-derived addresses) fixed in `GenesisConfig`. The testnet/devnet genesis
  specs (`docs/XRIQ_TESTNET_CHAINSPEC.md`) get a new `authority_pubkey` field →
  the `genesis_spec_hash` changes (a deliberate, one-time new-chain event).

Migration keeps the current `xriqdev1…` addresses working on devnet by treating
them as opaque during a transition window ONLY if signatures are disabled there;
the testnet/mainnet genesis uses key-derived addresses from day one.

## Trait seam (how it plugs in without a big-bang)

Add a scheme abstraction in `xriq-crypto` so the verifier is selectable and the
test-only path can coexist during migration and in unit tests:

```rust
pub trait SignatureScheme {
    fn verify(&self, pubkey: &PublicKey, message: &Hash32, sig: &SignatureBytes)
        -> Result<(), SignatureVerificationError>;
}

pub struct Ed25519Scheme;      // production
pub struct TestOnlyScheme;     // existing placeholder, gated to test/devnet
```

- `Transaction`/`BlockHeader` gain (or reinterpret) a `public_key` field alongside
  the existing `signature` bytes so verification is self-contained.
- Node/consensus/faucet take the scheme by dependency injection (config-selected),
  defaulting to `Ed25519Scheme` for testnet/mainnet and `TestOnlyScheme` only for
  `--network devnet` unit tests.
- A signing helper (CLI/wallet side) produces real signatures given a private key;
  the browser wallet MUST sign locally and stay non-custodial (see below).

## Wallet (non-custodial, unchanged guarantee)

Per `docs/XRIQ_LEGAL_RISK_REDUCTION.md` and the wallet key-safety guard, the
browser must never hold keys server-side. Real signing in the browser uses a
vetted client library (e.g. `@noble/ed25519`) entirely client-side; the server /
API never receives a private key, seed, or mnemonic. The existing
`scripts/check-wallet-key-safety.mjs` guard stays and is extended to forbid any
new key-handling anti-patterns.

## Phased plan (each phase is CI-green and reviewable)

1. **Deps + primitives.** — **DONE.** Added `ed25519-dalek = "2"` to `xriq-crypto`
   (Cargo.lock updated) and an `Ed25519Verifier` (`verify_hash(msg, pubkey, sig)`
   via `verify_strict`) plus test/key-management helpers
   (`ed25519_signing_key_from_seed`, `ed25519_public_key`, `ed25519_sign_hash`).
   Unit tests cover sign/verify round-trip, tampered message/signature, wrong key,
   malformed-length inputs (no panic), and determinism. It slots into the crate's
   existing `SignatureAlgorithm::Ed25519` / `SignatureEnvelope { public_key }`
   agility scaffolding. NOT yet wired into node/consensus/wallet.
2. **Address derivation.** — **primitive DONE (2a).** `xriq_crypto::ed25519_address(
   &[u8; 32]) -> Address` = `xriqdev1` + 20 bytes of a domain-separated
   (`xriq:v1:ed25519-address`) SHA-256 of the key as lowercase hex (a pure,
   offline-verifiable function of the public key), with a pinned golden vector +
   determinism/format tests. **(2b) DONE.** `GenesisConfig` gained
   `authority_pubkey: [u8; 32]`; the public testnet authority is now key-derived
   (`PUBLIC_TESTNET_AUTHORITY_PUBKEY` fixed in genesis, `authority` =
   `ed25519_address(pubkey)` = `xriqdev186bb85c…17e3c`), bound by an xriq-crypto
   test (`ed25519_address(pubkey) == authority`) since xriq-core cannot depend on
   xriq-crypto. `authority_pubkey` is folded into `genesis_spec_hash` and surfaced
   by `testnet-genesis`; the golden regenerated to
   `8849162ec39e556f0bbf1d60ca0b38ea3f93c9d2bea341c2c21129b10642188b` (node test +
   chainspec doc updated). Devnet keeps an all-zero `authority_pubkey` and the
   test-only scheme (its authority address is unchanged, so its large producer
   test suite stays green). `fee_sink` remains a fixed non-signing sink (no key
   needed). NOT yet used for verification — that is Phase 3.
3. **Wire verification (behind a flag).** — **seam DONE (3a).** `xriq-crypto` now
   has a `SignatureScheme` trait with `TestOnlyScheme` + `Ed25519Scheme` impls
   (verifying a `SignatureEnvelope` = algorithm + public key + signature), plus a
   `SignatureSchemeKind { TestOnly, Ed25519 }` selector (`parse` for the
   `--signature-scheme` flag, `verify_envelope` dispatch that only accepts its own
   algorithm — it never trusts the envelope's self-declared algorithm). Tests
   cover matching/mismatched algorithms, tampered signature, wrong message, and
   flag parsing. **(3b, step 1) DONE.** `xriq-crypto` now applies the seam to the
   real protocol types: `verify_transaction_with_scheme(scheme, &Transaction,
   public_key)` and `verify_block_header_with_scheme(scheme, &BlockHeader,
   public_key)` build an envelope from the item's own signature over its canonical
   signing hash and dispatch under the *configured* scheme (never the item's
   self-declared algorithm), so a test-only signature can never pass an ed25519
   node and vice versa. Tests cover a real ed25519-signed transaction/header
   verifying, plus wrong-key / tampered-body / wrong-scheme rejection
   (`InvalidSignature`). In step 1 the public key was a caller parameter (no
   struct change). xriq-crypto: 19 tests. **(3b, step 2) DONE.** `Transaction` and
   `BlockHeader` gained a `public_key: Vec<u8>` field (empty under test-only; the
   32-byte Ed25519 key once signed), and the two `verify_*_with_scheme` helpers now
   read the key from the item itself — verification is **self-contained**. This was
   kept deliberately **additive**: `public_key` is NOT yet in the canonical
   signing/hash encoding, so no transaction/block/genesis golden changed and the
   whole workspace stays green (the ~85 struct literals across the workspace gained
   `public_key: Vec::new()`; the ledger/mempool/consensus/node producer + faucet +
   API + wallet paths all keep an empty key under the test-only scheme). The
   storage / JSON / pending-record codecs do not persist the field yet — they set
   it empty on decode (flagged in-code). **(3b, step 3 — canonical encoding) DONE.**
   `public_key` is now folded into `encode_transaction_without_signature` /
   `encode_header_without_signature`, so it is part of BOTH the signing hash and
   the item hash — a signature is now cryptographically **bound** to the key that
   produced it (a crypto test asserts changing `public_key` changes both hashes;
   the ed25519 helpers had to set the key *before* signing, which the change
   surfaced). The persistence/wire codecs were updated to carry it: the storage
   binary codec (`write_byte_vec`/`read_vec`), and the node + API pending-record
   TSV format (`public_key` added as a field, placed *before* the always-present
   `signature` so an empty key can't become a trailing tab a line-trimming reader
   drops). Every shifted golden was regenerated deterministically: the api
   signed-submit signing/tx-hash fixtures, the main.rs URL fixtures, and the six
   `fixtures/private-devnet/*.json` node/wallet fixtures (hash-only diffs). Full
   workspace: 325 tests green; fmt clean; genesis_spec_hash is config-only so it
   did NOT move. **(3b, step 4 — scheme threading + flag) DONE.** `XriqNode` now
   carries a `signature_scheme: SignatureSchemeKind` (default `TestOnly`, set via a
   `with_signature_scheme` builder so no constructor signature changed) and its
   three verify sites — `submit_transaction`, and peer-block-import transaction +
   header verification — call `verify_transaction_with_scheme` /
   `verify_block_header_with_scheme` under that scheme instead of a hardcoded
   `TestOnlySignatureVerifier`. A `--signature-scheme test-only|ed25519` runner flag
   (default `test-only`, via `parse_signature_scheme` → new
   `NodeRunnerError::InvalidSignatureScheme`) is wired into the peer-sync follower
   command and applied to its node. A node test asserts the default is `TestOnly`,
   that an `Ed25519` node rejects a test-only signature (`InvalidSignature`), and
   that a genuine ed25519-signed transaction (key set *before* signing) verifies and
   submits. Signing still uses the test-only scheme, so `ed25519` today means
   "require ed25519 on verify" (test-only-signed blocks are then correctly
   rejected); real ed25519 *signing* is Phase 4. 326 tests green. **(3b, step 5 —
   ed25519 end-to-end import) DONE.**
   `ed25519_signed_block_imports_and_applies_end_to_end_under_ed25519_scheme` drives
   the real import path: an ed25519 producer accepts an ed25519-signed transaction,
   produces a canonical-roots block, the header is re-signed with ed25519 (roots
   unaffected — the signature is not in the signing hash, and the key is set before
   signing), and an ed25519 follower verifies both the transaction and the header
   and applies the block (`import_block_with_canonical_hash` → height advances,
   store gains the block). The same block is rejected by a test-only follower
   (`TransactionSignature(InvalidSignature)`), confirming the scheme is what gates
   acceptance. 327 tests green. **Phase 3b is now complete** — the verification
   pipeline is fully scheme-aware end-to-end (submit + peer import), bound by a
   self-contained on-chain public key, and flag-selectable. REMAINING (optional
   polish, not blocking): extend the scheme to the indexer/rpc verify sites
   (currently still test-only; harmless because the node already enforced the
   scheme on import).
4. **Real producer + faucet signing.** Block producer and faucet sign with an
   Ed25519 key (test keypair fixed in test vectors, real key via a
   `--producer-key-file` on operator nodes — key files gitignored, never
   committed). **(4a — signing seam) DONE.** `xriq-crypto` now has `SchemeSigner`
   (`TestOnly` | `Ed25519(Box<SigningKey>)`), the signing counterpart to the verify
   seam: `scheme()`, `public_key()` (empty for test-only, the 32-byte key
   otherwise), `sign_hash(hash)`, and correct-by-construction `sign_transaction` /
   `sign_block_header` helpers that set the object's `public_key` *before* signing
   its canonical hash (encapsulating the ordering the encoding change surfaced).
   Tested round-trip: a `SchemeSigner`-signed transaction/header verifies under
   `verify_*_with_scheme(signer.scheme(), …)` and is rejected under the other
   scheme; test-only yields an empty key, ed25519 records its public key.
   xriq-crypto: 21 tests. The `TestOnly` signer produces byte-identical output to
   the current `test_only_signature_for_hash` path, so wiring it in is golden-neutral.
   **(4b — producer signing) DONE.** `XriqNode` gained `producer_signer:
   SchemeSigner` (default `TestOnly`, set via a `with_producer_signer` builder;
   `producer_signer_scheme()` accessor). Header signing now happens *inside*
   `produce_next_block_inner`: after the producer builds the block (canonical roots
   + height set), the node's `producer_signer.sign_block_header(&mut block.header)`
   stamps the `public_key` + `signature` before the block is hashed and stored —
   gated by a `sign_with_producer_signer` flag so only the dedicated signing entry
   point (`produce_next_block_with_private_devnet_signature`) uses it; the
   explicit-signature paths (`produce_next_block`, canonical-hash/roots) are
   unchanged. (`produce_block` rejects an empty signature, so a non-empty placeholder
   is passed and fully replaced by the signer.) `SchemeSigner` got manual `Clone` /
   `Debug` (redacted — never prints key bytes) / `PartialEq`+`Eq` (compares scheme +
   public key only, never secret bytes) so it can live in the derive-heavy node
   struct. Default nodes stay byte-identical (golden-neutral: all fixtures unchanged).
   New test `producer_signer_signs_produced_blocks_under_its_scheme`: an ed25519
   producer node produces a header that records the producer public key, verifies
   under the ed25519 scheme, and imports into a fresh ed25519 follower — a producer
   now signs ed25519 through the real production path. 329 tests green. **(4d —
   `--producer-key-file` + runner wiring) DONE.** A `--producer-key-file <path>`
   flag (parsed by `parse_producer_signer`) loads a 32-byte Ed25519 seed as 64
   lowercase hex from a gitignored file (`.gitignore`: `*.producer.key`,
   `*producer-key*.key`, `xriq/**/*.key`, `xriq/**/keys/`) into a
   `SchemeSigner::ed25519`; absent → the test-only signer. New
   `NodeRunnerError::{ProducerKeyFileRead, InvalidProducerKeyFile}` cover read /
   hex / length errors. Wired into `produce-transfer-block`: the loaded signer
   signs **both** the constructed transfer transaction (via a new
   `XriqNode::sign_transaction_with_producer_signer`, used by
   `private_devnet_runner_transaction`, which the faucet dispense path also uses)
   **and** the block header, and the node verifies under the signer's scheme — a
   coherent single-scheme producer (all-test-only by default → golden-neutral;
   all-ed25519 with a key file). A delegate keeps the existing
   `private_devnet_file_produce_transfer_block` (test-only) for other callers.
   Tests: `parse_producer_signer_loads_ed25519_key_or_defaults_to_test_only`
   (default / valid key / bad length / missing file), and end-to-end
   `produce_transfer_block_signs_with_producer_key_file` (runs the CLI with a key
   file, reopens the store, and verifies the stored header + transaction under
   ed25519). 331 tests green; fmt clean; no new clippy. **(4c —
   produce-pending-block + faucet ed25519) DONE. Phase 4 complete.** The
   `--producer-key-file` flag is now wired into `produce-pending-block` and
   `faucet-dispense` too. The replay-ordering was handled:
   `private_devnet_node_with_pending_file_and_producer_signer` applies the scheme +
   signer *before* the pending records are replayed, so ed25519 pending
   transactions verify under the ed25519 scheme during replay (a test-only node
   rejects them). The faucet's `public_testnet_file_faucet_dispense` gained a
   signer-aware variant (no replay, so the signer is applied after construction).
   Both use the delegate pattern (existing helpers stay test-only for their
   xriq-api / other callers). End-to-end test
   `produce_pending_block_replays_and_signs_ed25519_with_producer_key_file`: an
   ed25519-signed pending transaction (a distinct "wallet" key) is written to the
   pending file, the CLI produces a block with `--producer-key-file`, and the
   reopened store's header (producer key) + transaction (wallet key) both verify
   under ed25519. 332 tests green; fmt clean; no new clippy. NOTE the devnet
   producer self-signs the constructed transfer/faucet transaction (test identity
   only); real per-account signing is Phase 5 (wallet client-side signing).
5. **Flip testnet default to ed25519**; keep test-only for pure unit tests only.
   Migrate the wallet to client-side ed25519 signing + submit-signed path.
   **(5b — testnet default flipped to ed25519) DONE.** Public-testnet nodes now
   verify AND produce ed25519 out of the box (devnet unchanged). Mechanism: a
   per-network default signer `runner_default_producer_signer(selection)` — ed25519
   from the well-known authority seed (`PUBLIC_TESTNET_AUTHORITY_SEED =
   *b"xriq-testnet-authority-test-0001"`, whose public key is the genesis
   `PUBLIC_TESTNET_AUTHORITY_PUBKEY`; TEST-ONLY, published on purpose, never guards
   value) for the testnet, test-only for devnet. `XriqNode::
   from_genesis_replaying_store` gained a `_with_producer_signer` variant that
   applies the scheme + signer BEFORE the stored-block replay (so ed25519 stored
   blocks verify during replay); `runner_node` and the ~9 `runner_file_*` read
   helpers use it with the network default. The `--signature-scheme` /
   `--producer-key-file` flags became **network-aware** (absent → the network
   default; explicit value overrides), and the faucet default became the authority
   signer. The **indexer** read-model re-verification is now scheme-aware too
   (`indexed_genesis_scheme` picks ed25519 when `genesis.authority_pubkey` is
   non-zero) — required, since it re-verifies the now-ed25519 testnet blocks.
   Test `public_testnet_defaults_to_ed25519_producer_matching_genesis_authority`:
   the testnet default signer's public key equals the genesis authority pubkey
   (binding the seed), devnet stays test-only, and a testnet faucet dispense with no
   key file produces an ed25519 block (header + transaction) verifying under ed25519.
   334 tests green; fmt clean; no new clippy. REMAINING Phase 5: (5c) browser-wallet
   client-side ed25519 signing + submit-signed path (the CLI wallet already signs
   client-side; the xriq-api signed-submit route exists — wire the browser wallet to
   sign locally with `@noble/ed25519` and POST the signed envelope, keeping the
   key-safety guard). Optionally make the xriq-rpc submit verify site scheme-aware
   too (still test-only; only matters if rpc is used on testnet).
   **(5a — wallet client-side signing) DONE.** `xriq-wallet` `build_test_transfer`
   now delegates to a new `build_transfer_with_signer(request, &SchemeSigner)` that
   signs the transaction locally via the signer; a `--signing-key-file <path>` flag
   on the `transfer` command (`parse_wallet_signer`, 64-hex seed → `SchemeSigner::
   ed25519`) makes signing **non-custodial** — the key stays in the operator's file,
   the wallet signs client-side, and only the signed transaction leaves the wallet.
   New `WalletError::{SigningKeyFileRead, InvalidSigningKeyFile}`. Default (no flag)
   is the test-only self-sign, byte-identical to before (golden-neutral). Test
   `transfer_signs_client_side_with_ed25519_key_or_defaults_to_test_only`: default
   draft matches the historical signature; an ed25519 key records the signer's
   public key and the transaction verifies under the ed25519 scheme; the key file
   loads (absent → test-only). 333 tests green; fmt clean; no new clippy. This is
   the CLI wallet; the **browser wallet** must sign locally with a vetted client
   library (`@noble/ed25519`) — a separate UI step. REMAINING Phase 5: (5b) flip the
   public-testnet default to ed25519 (genesis/producer/faucet run ed25519 by
   default, with operator keys), and (5c) the browser-wallet client-side signing +
   submit-signed path. Accounts still can't fully self-serve until the testnet
   default flips and the browser wallet signs locally.
6. **AI-assisted security review** (Claude + Codex) of consensus/crypto/replay/
   serialization per roadmap Phase 8; record in `SECURITY_REVIEW.md`. Only after
   this may any value-bearing use be *considered* (still gated by legal review).

## Test strategy

- Unit: Ed25519 known-answer vectors; sign→verify round-trip; tamper (flip a byte
  in message/sig/pubkey → reject); wrong-key reject; malleability check.
- Property/fuzz: random messages/keys, and malformed signature/pubkey bytes never
  panic (return `SignatureVerificationError`).
- Integration: a transaction/block signed by ed25519 imports and verifies through
  the real node path; a bad signature is rejected without mutating state (mirrors
  the existing `rejects_peer_block_with_bad_*_signature` tests).
- Keep the test-only path's tests under `--network devnet` so the large existing
  suite stays green during migration.

## Non-goals / guardrails

- No custom cryptography; only audited crates.
- No key custody (server or browser) — non-custodial invariant preserved.
- This does not authorize a value-bearing mainnet: real crypto is *necessary but
  not sufficient*; legal review (`docs/XRIQ_LEGAL_COUNSEL_QUESTIONS.md`) and the
  independent security audit remain hard gates.
