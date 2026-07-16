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
2. **Address derivation.** Implement key→address; add genesis `authority_pubkey`;
   regenerate the testnet `genesis_spec_hash` golden.
3. **Wire verification (devnet behind a flag).** Node/consensus/faucet accept a
   `SignatureScheme`; add `--signature-scheme test-only|ed25519`. Keep default
   `test-only` so nothing breaks; add ed25519 end-to-end tests.
4. **Real producer + faucet signing.** Block producer and faucet sign with an
   Ed25519 key (test keypair fixed in test vectors, real key via a
   `--producer-key-file` on operator nodes — key files gitignored, never
   committed).
5. **Flip testnet default to ed25519**; keep test-only for pure unit tests only.
   Migrate the wallet to client-side ed25519 signing + submit-signed path.
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
