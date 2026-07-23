# XRIQ Key-Derived Accounts — Design / Scoping

Status: **DESIGN ONLY. Not implemented.** This is the architecture gate for the
remaining half of security-review finding 1 (sender↔key binding); see
`docs/SECURITY_REVIEW.md` and `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`.

## Purpose

Close the one substantive gap left by the crypto migration: under the Ed25519
scheme, a transaction's `from` account is **not bound** to the key that signs it
(`ed25519_address(tx.public_key) == tx.from` is never enforced), so a signature
authenticates possession of *an* arbitrary key, not authority over `from`. The block
producer half is already fixed and tested; this document scopes the sender half.

The enforcement is a few lines. The blocker is that it can only be turned on once
**an account's address is a function of its public key** — today regular accounts are
opaque padded literals (`xriqdev1alice00000000000`), so the check would reject every
legitimate transaction (including the faucet's own dispense).

## Current state

- **Address** (`xriq-core/src/address.rs`): `xriqdev1` + a 16–96 char lowercase
  alphanumeric payload. Opaque test identities use short labels
  (`xriqdev1alice00000000000`). `ed25519_address(pubkey)` already exists
  (`xriq-crypto`, Phase 2a): `xriqdev1` + 40 hex chars (20 bytes of a
  domain-separated SHA-256 of the key) — a valid address, a pure function of the key.
- **Genesis** funds addresses directly (`GenesisAccount { address, balance, nonce }`).
  The devnet authority is opaque; the **testnet authority is already key-derived**
  (`PUBLIC_TESTNET_AUTHORITY_ADDRESS == ed25519_address(PUBLIC_TESTNET_AUTHORITY_PUBKEY)`).
  The testnet **faucet** account (`xriqdev1testnetfaucet00000000`) is opaque.
- **Ripple if done naively:** ~303 opaque address literals + ~156 `address("…")`
  test-helper calls + many JSON fixtures. This is why it must be scoped, not a
  blanket rename.

## Scope boundary (the key decision that makes this tractable)

**Only Ed25519 chains get key-derived accounts. The test-only devnet keeps opaque
accounts, unchanged.**

- **Devnet** (`--network devnet`, test-only scheme): accounts stay opaque; the
  sender↔key check is **not** applied (test-only is insecure by design). This leaves
  the ~300 opaque devnet literals and their fixtures untouched.
- **Ed25519 chains** (public testnet, and the ed25519 unit/integration tests):
  every account that can send is key-derived; the sender↔key check is enforced.

This restricts the change to the (small) set of ed25519 genesis accounts + the
ed25519 tests, not the whole codebase.

## Target model

For an Ed25519 chain, an account's address MUST equal `ed25519_address(public_key)`.
A transaction is authorized iff:

```
ed25519_address(tx.public_key) == tx.from   (32-byte key required)
AND  verify_transaction_with_scheme(Ed25519, tx) == Ok
```

The faucet becomes a key-derived account: `PUBLIC_TESTNET_FAUCET_ADDRESS =
ed25519_address(PUBLIC_TESTNET_FAUCET_PUBKEY)`, and faucet dispenses are signed by the
matching faucet key (a published, valueless well-known test key, exactly like
`PUBLIC_TESTNET_AUTHORITY_SEED`). The browser/CLI wallet's `from` is the derived
address of its own signer, not a fixed literal.

## Phased plan (each phase CI-green and reviewable)

1. **Primitive — DONE already.** `ed25519_address(&[u8;32]) -> Address` exists and is
   golden-tested (Phase 2a). No work.
2. **Well-known key-derived test accounts + genesis builder.** Add published
   TEST-ONLY seeds for the testnet faucet (and any other funded testnet account), fix
   their key-derived addresses/pubkeys in `GenesisConfig::public_testnet()`, and add a
   reusable key-derived-account genesis builder for tests
   (extend the existing `ed25519_authority_genesis` test helper into a fixture that
   funds `ed25519_address(seed)` accounts). Additive; regenerates the testnet
   genesis_spec_hash + testnet fixtures (a deliberate new-chain event). No enforcement
   yet.
3. **Faucet signs from its key-derived identity.** Route the faucet dispense so
   `from = PUBLIC_TESTNET_FAUCET_ADDRESS = ed25519_address(faucet_pubkey)` and the
   transaction is signed by the faucet key (so `ed25519_address(from_key) == from`).
   Decide: keep the faucet key distinct from the authority key (recommended — separate
   roles) — the faucet signs faucet txs, the authority signs block headers.
4. **Wallet uses its own derived address.** CLI + browser: the signer's `from` is
   `ed25519_address(signer.public_key)`; drop the fixed `PRIVATE_DEVNET_TEST_SENDER`
   restriction on the ed25519 signed-submit path (the binding check replaces it).
   Fund a key-derived account in the ed25519 test genesis so the wallet can transfer.
5. **Enforce sender↔key.** Under the Ed25519 scheme, add
   `ed25519_address(tx.public_key) == tx.from` (reject empty/non-32-byte, wrong
   address) in `submit_transaction`, the per-transaction loop in
   `validate_next_block_state`, and the indexer's `replay_private_devnet_block` —
   mirroring the producer↔key fix. Rework the ed25519 tests to key-derived senders
   (they currently send from opaque `alice`). Test-only devnet skips the check.
6. **Regenerate affected fixtures + re-review.** Regenerate only the ed25519/testnet
   fixtures whose addresses/hashes change; devnet fixtures are untouched. Update
   `SECURITY_REVIEW.md` (finding 1 fully closed) and re-run the adversarial review on
   the changed surfaces.

## Hard decisions to confirm before coding

- **Published test keys are acceptable** for the testnet faucet/accounts (as for the
  authority seed), because the network is explicitly valueless and undeployed. A real
  deployment fixes real operator public keys in genesis and never a seed in source.
- **Devnet is intentionally NOT migrated** — it stays opaque + test-only. If devnet
  should also become key-derived later, that is a separate, larger follow-up (it
  touches the ~300 literals); it is out of scope here.
- **Faucet vs authority key:** keep them separate (faucet key signs faucet
  transactions; authority key signs block headers). Merging them would make the faucet
  the block producer, conflating roles.
- **No backward compatibility needed:** chains are ephemeral and valueless; changing
  genesis addresses/hashes is a deliberate new-chain event.

## Test strategy

- Unit: `ed25519_address(pubkey) == funded genesis account`; a transaction from a
  key-derived account signed by the matching key verifies and applies; a transaction
  whose `public_key` does not derive `from` is rejected (`from`/authorization error)
  under ed25519, and is *ignored* (still test-only) under devnet.
- Integration: a testnet faucet dispense (key-derived faucet, no `--producer-key-file`
  override) produces a block whose transaction passes the sender↔key binding; a forged
  transaction (attacker key, victim `from`) is rejected end-to-end through submit +
  import + indexer.
- Keep the entire opaque-devnet suite green unchanged (the boundary check: devnet
  behaviour is byte-identical).

## Non-goals / guardrails

- No change to the devnet account model or its fixtures.
- No custom cryptography; reuse `ed25519_address` + the existing scheme seam.
- This does not authorize value-bearing use: it closes finding 1, but the independent
  human security audit and legal review remain hard gates
  (`docs/XRIQ_LEGAL_RISK_REDUCTION.md`).

## First bounded step (when implementation starts)

Phase 2 above, additive and golden-neutral for devnet: add the published faucet test
seed + its key-derived address/pubkey constants and the key-derived-account genesis
test builder, WITHOUT any enforcement — establishing the identities the later phases
bind against. This mirrors how the crypto migration began (a primitive + fixtures
before any behaviour change).
