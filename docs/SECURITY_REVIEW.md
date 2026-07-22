# XRIQ Security Review — Production-Cryptography Migration

Status: **Review complete. HARD GATE: NOT ready for any value-bearing use.**
Review type: AI-assisted adversarial review (roadmap Phase 8 / crypto-migration Phase 6).
Network status at review time: **test-only, explicitly valueless, not deployed.**

## Scope

The Ed25519 production-cryptography migration, commits `a3118c0` … `02ccb15`
(Phases 1–5c), covering:

- `xriq-crypto` — Ed25519 primitive (`verify_strict`), signature-scheme seam,
  canonical signing/hash encoding (with `public_key` now folded in), `SchemeSigner`.
- `xriq-node` / `xriq-consensus` / `xriq-ledger` — transaction submission, block
  production, peer/stored-block import + replay, ledger application.
- Serialization — the storage binary codec, the pending-transaction TSV codec, the
  API pending-mempool parser.
- `xriq-api` — the signed-submit route (real Ed25519 acceptance), the
  prepare-signing-hash endpoint.
- `xriq-indexer` — read-model re-verification + scheme selection.
- Producer/faucet key handling (`--producer-key-file`, the published test authority
  seed) and the non-custodial browser wallet (`explorer-ui`).

## Methodology

Four independent adversarial reviewers examined disjoint surfaces (crypto
primitives + encoding; consensus + import/replay; serialization/codecs + indexer;
signed-submit + keys + browser) with a mandate to produce concrete exploit
scenarios, severity ratings, and to distinguish real vulnerabilities from
defense-in-depth. Their findings were then verified against the code by the
integrator (grep of the identified call paths, confirmation of the missing checks).
**All four reviewers independently identified the same top finding**, which was
confirmed directly in the source.

## Findings

| # | Severity (test-only → value-bearing) | Title | Status |
|---|---|---|---|
| 1 | **Info now → CRITICAL if value-bearing** | Signature not bound to claimed identity (`from`/`producer` ↔ `public_key`) | **Producer↔key FIXED; sender↔key open (needs key-derived accounts)** |
| 2 | Low now → Medium | Unbounded allocation from unvalidated length/count prefixes (import DoS) | Open — hardening |
| 3 | Low → High | Browser signs a server-provided signing hash without local recomputation | Open — hardening |
| 4 | Low → Medium | Mempool dedup keyed on signature-dependent tx hash, not `(from, nonce)` | Open — hardening |
| 5 | Info | Signed-submit picks algorithm from the envelope, not the node scheme; test-only path is public | Documented (test-only) |
| 6 | Info | `--signature-scheme test-only` can downgrade a testnet follower's live verification | Documented (operator footgun) |
| 7 | Info | `memo_hash` not carried in the pending TSV (availability, not soundness) | Open — future-proofing |
| 8 | Info | Wallet key-safety guard is a textual lint, not a data-flow boundary | Documented |

### 1 — Signature is not bound to the claimed identity (the headline finding)

`verify_transaction_with_scheme` / `verify_block_header_with_scheme`
(`xriq-crypto/src/lib.rs`) build the verification envelope from the item's **own**
`public_key` field and verify the signature against **that** key. The signing hash
includes `public_key`, so the signature is internally consistent — but **nothing
checks that `ed25519_address(public_key)` equals the claimed identity**
(`tx.from` for transactions, `header.producer` for blocks). Confirmed: `ed25519_address`
is used only in genesis config and unit tests, never in the verification path;
`validate_next_block_state` authorizes the producer by an **address-string compare**
(`block.header.producer != self.producer.config().producer`) only, and
`Transaction::validate_basic` performs no key binding at all.

Consequences under the Ed25519 scheme (the public-testnet default since Phase 5b):

- **Authority block forgery.** The authority address is public. An attacker sets
  `producer = <authority address>`, `public_key = <attacker key>`, recomputes the
  roots, and signs with their **own** key. The address compare passes; the signature
  verifies against the attacker's key; the block is accepted as canonical.
  Single-authority consensus is bypassed by any peer.
- **Sender forgery.** An attacker sets `from = <victim>`, `public_key = <attacker
  key>`, signs with their own key. Verification passes; the ledger debits the victim.

**Why the real-world impact is nil *today*:** the network is test-only and valueless;
it is not deployed; regular accounts are opaque padded literals (not key-derived), so
there is no key to bind them to and no value to steal; and under the legacy test-only
scheme these paths were forgeable by design. The finding is that the Ed25519 migration
presents the *appearance* of authentication without the *substance* of identity
binding.

**Remediation:**

- **Producer ↔ key — FIXED** (commit following this review). Under the Ed25519 scheme,
  `validate_next_block_state` (`xriq-node`) and `replay_private_devnet_block`
  (`xriq-indexer`) now require `ed25519_address(header.public_key) == header.producer`
  via `producer_public_key_derives_address`; a non-deriving key → `UnauthorizedProducer`
  before any state mutation. This closes authority-block forgery: an attacker can no
  longer forge an authority block by copying the public authority address while signing
  with their own key. The ed25519 producer/import tests were reworked onto a
  key-derived-authority genesis (`ed25519_authority_genesis`), and a new negative test
  (`ed25519_block_with_producer_key_not_deriving_the_authority_address_is_rejected`)
  proves a forged block is rejected. Test-only carries no key and skips the check.
- **Sender ↔ key — OPEN (requires an architectural step).** Enforcing
  `ed25519_address(tx.public_key) == tx.from` **cannot** be turned on against the current
  account model — regular accounts (alice, the faucet, recipients) are opaque addresses,
  not key-derived, so the check would reject every legitimate transaction (including the
  faucet's own dispense). It needs a prior "key-derived accounts" phase that makes an
  account address a function of its public key. Until then, transaction-sender
  authenticity is NOT enforced under Ed25519 — a hard blocker before any value-bearing
  use.

### 2 — Unbounded allocation from unvalidated length/count prefixes (import DoS)

`decode_peer_blocks` / `read_block_record` / `read_vec` (`xriq-storage`) allocate
`Vec::with_capacity(count)` / `vec![0; len]` from raw `read_u32` prefixes **before**
validating them against the remaining input. `import_peer_blocks` feeds peer-supplied
bytes straight in, so a ~10-byte hostile message with `count = 0xFFFFFFFF` triggers a
capacity-overflow panic or a multi-GB allocation → process abort. `checked_len` on the
encode side likewise `expect()`s. Not a memory-safety or spoofing issue; a
denial-of-service on block sync. **Fix:** bound each count/length against the cursor's
remaining bytes before allocating; return `CorruptData` on over-long prefixes.

### 3 — Browser signs a server-provided signing hash without local recomputation

The non-custodial wallet asks the server for the `transaction_signing_hash` (the
`prepare` step) and signs whatever hash is returned, with no client-side
recomputation. A hostile server (or MITM over the plain `fetch`) that controls both
`prepare` and `submit` could get the wallet to sign a different transaction than the
user intended. Mitigated today by the key being ephemeral, single-use, and bound to no
funded account (finding 1). **Fix before value:** recompute the canonical signing hash
in the browser (a vetted encoder) and sign only the locally-computed hash. This is the
tradeoff that was accepted to avoid a hand-rolled TS canonical encoder.

### 4 — Mempool dedup keyed on signature-dependent tx hash

`transaction_hash` includes the signature; a key holder can produce many distinct
canonical Ed25519 signatures for the same body, each a different tx hash, so the
duplicate-pending check does not prevent multiple pending entries for one
`(from, nonce)`. `verify_strict` closes classic S-malleability, but not
signer-chosen-nonce multiplicity. Whether this becomes a double-debit depends on nonce
enforcement at production. **Fix:** dedup by `(from, nonce)` (or by the signing hash,
which excludes the signature).

### 5–8 — Informational / documented

- **5:** the signed-submit API selects ed25519-vs-test-only from the *envelope's*
  self-declared algorithm, and the test-only branch reconstructs a publicly-computable
  signature — so the endpoint provides no real authentication. Acceptable because it is
  a test-only, valueless, single-sender (`xriqdev1alice…`), flag-gated devnet endpoint;
  it must never be read as a security control. Before value: pin the accepted algorithm
  to the node's configured scheme and drop test-only acceptance.
- **6:** an operator can pass `--signature-scheme test-only` to a testnet follower and
  silently accept forgeable blocks for newly-synced history. Consider rejecting
  `test-only` when the genesis carries a non-zero `authority_pubkey`.
- **7:** `memo_hash` is not carried in the pending TSV; the recompute-and-compare gate
  keeps this *sound* (no injection), but a future memo-bearing transaction would be
  silently dropped on reload. Carry `memo_hash` for a lossless record.
- **8:** `check-wallet-key-safety.mjs` matches identifiers, not data flow; it is a
  regression tripwire, not a guarantee. The actual non-custodial guarantee rests on
  `signing.ts` keeping the seed in a closure (which it does).

## Properties confirmed SOUND (positive results)

These were adversarially probed and found correct — the review is not only a defect
list:

- **Ed25519 verification uses `verify_strict`** — canonical `S`, small-order and
  mixed-order public keys rejected; classic malleability closed. Malformed key/signature
  bytes return `InvalidSignature` and never panic.
- **Canonical encoding is injective and fully domain-separated** — every
  variable-length field is `u32`-length-prefixed; each of the six hashing domains has a
  distinct length-prefixed preamble; `Option` uses a 0/1 tag. Two distinct
  transactions/headers cannot collide.
- **`public_key`, `chain_id`, `nonce`, `expires_at_height` are all bound into the
  signing hash** — a signature cannot be replayed under a different key or on a
  different chain, nor can those fields be tampered post-signature.
- **Signing order is correct** — `SchemeSigner` sets `public_key` before computing the
  hash and signing, so the signature commits to the key.
- **Verification runs on every state-mutating import/replay path**, the scheme is
  applied **before** stored-block/pending replay, block/tx application is **atomic on
  failure** (cloned ledger committed only on full success), and `transactions_root` /
  `state_root` / `block_hash` are recomputed and compared. Height/nonce/parent/duplicate
  handling is correct; the block-producer placeholder signature cannot survive into a
  stored block.
- **Scheme is code-selected inside `xriq-crypto`** (not trusted from the envelope's
  self-declared algorithm), so a test-only signature cannot pass an Ed25519 node and
  vice versa.
- **Serialization round-trips losslessly** with `public_key` added; the pending-TSV
  codec is injection-resistant (strict field count + `tx_hash` recompute gate;
  `public_key` placed before the always-non-empty `signature` so trimming can't drop
  it); the indexer's scheme selection (`authority_pubkey == [0;32] → test-only`, else
  ed25519) is sound.
- **Non-custodial key handling** (`signing.ts`) — the seed comes from the platform
  CSPRNG, lives only in a closure, and is never returned, persisted, logged, or
  transmitted; only the public key and signature leave the wallet.
- **Producer/faucet key handling** — the published `xriq-testnet-authority-test-0001`
  seed is clearly scoped test-only-and-valueless; devnet never uses it; the testnet
  authority address is the key-derived `ed25519_address` of its pubkey; `--producer-key-file`
  parsing is strict (64-hex → 32 bytes, typed errors) and overrides the default.

## Conclusion — HARD GATE

Real Ed25519 cryptography is now correctly built at the primitive and encoding level,
and the import/replay/serialization plumbing is solid. **However, the migration does
not yet bind signing keys to on-chain identities (finding 1), so under the Ed25519
scheme the authentication is not yet real.** This, plus findings 2–4, means:

> **XRIQ must remain test-only and valueless.** Real cryptography is *necessary but
> not sufficient*. Before any value-bearing use, the following are hard gates:
> 1. Identity binding (finding 1) — producer↔key is now **fixed and tested**; sender↔key
>    still requires a key-derived-accounts phase — plus findings 2–4 remediated and
>    re-reviewed.
> 2. An **independent, human, third-party security audit** (this AI-assisted review does
>    not replace it).
> 3. **Legal review** per `docs/XRIQ_LEGAL_RISK_REDUCTION.md` /
>    `docs/XRIQ_LEGAL_COUNSEL_QUESTIONS.md`.

No finding is exploitable for real-world loss in the current test-only, undeployed,
valueless configuration.
