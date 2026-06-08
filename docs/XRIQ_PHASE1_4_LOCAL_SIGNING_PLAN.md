# XRIQ Phase 1.4 Local Signing Plan

Status: planning checkpoint only. No Phase 1.4 signing, wallet submit UI,
custody, public network, DEX, bridge, smart-contract, production
infrastructure, or key-management implementation is approved by this document.

Phase 1.4 starts after:

- `phase1-3-xriq-local-private-behavior-rc1`

The goal is to move the local/private wallet prototype one step closer to a
real wallet flow by defining a signed-transfer boundary, while keeping all key
material outside the browser and outside hosted custody.

## Goal

Design the next local/private development layer around signed transfer
artifacts:

- deterministic local/private signing intent and transaction digest contract
- test-only signed transfer envelope contract
- verification expectations before a signed transfer can enter pending state
- audit events for accepted and refused signed-submit attempts
- smoke coverage for draft, sign, submit, block production, and confirmation
- a future UI path that can inspect or submit a pre-signed local artifact without
  generating, storing, or managing keys in the browser

The phase should make the private-devnet wallet behavior more realistic without
claiming production wallet, custody, exchange, or public-chain readiness.

## Non-Goals

Do not include these in Phase 1.4 unless a later explicit approval and review
document changes the scope:

- production private-key generation, storage, recovery, backup, or custody
- browser-held private keys, seed phrases, mnemonics, raw signatures, or
  persisted signing material
- hosted wallet custody or managed signing services
- public mainnet, public devnet, validator admission, tokenomics, governance, or
  public API exposure
- DEX trading, liquidity pools, bridges, wrapped assets, CEX listings, or
  exchange-readiness claims
- smart-contract VM, XRC asset issuance, native DEX modules, or asset-issuance
  economics
- production GCP/Vast/server infrastructure, TLS, public auth, monitoring, or
  rate limits
- ISO 20022 certification, bank connectivity, SWIFT connectivity, fiat
  settlement, or payment-network claims

Keep `docs/XRIQ_LEGAL_RISK_REDUCTION.md` as the controlling guardrail for any
request that touches public tokens, privacy, DEX, bridges, custody, listings,
payments, or market-facing claims.

## Design Boundaries

Phase 1.4 must separate these responsibilities:

- `xriq-wallet`: local CLI-only test signer and signed-artifact inspector.
- `xriq-api`: local/private signed-submit verification and pending-state
  mutation behind explicit enablement.
- `explorer-ui`: read-only inspection by default; any future submit control must
  accept only a pre-signed local artifact and must not generate or persist keys.
- `xriq-node`: chain validation and block production over already-accepted local
  pending transactions.

The current `xriq-wallet` crate uses deterministic test identities and fake
signatures. Phase 1.4 may improve the shape of the signed artifact and verifier
contract, but production cryptography and production key management remain
separate future work.

## Implementation Ladder

Use this order unless the user explicitly chooses a different narrow milestone.

1. Signed-transfer contract inventory.
   Define fixtures for a local signing intent, transaction digest, test-only
   signed transfer envelope, refused invalid-signature submit, and accepted
   local/private signed-submit response. Keep all examples test-identity-only.

2. Contract and plan checker.
   Extend or add cheap validation scripts so the fixtures and docs prove that
   signed-submit behavior is disabled by default, local/private only, audit
   gated, and free of private key, seed phrase, mnemonic, custody, public, DEX,
   or production markers.

3. CLI-only test signing path.
   Add an explicit local CLI command that can create or inspect a test-only
   signed transfer artifact. It must print a test-only warning, avoid persistent
   key storage, and avoid browser or server-held key material.

4. API signed-submit verifier.
   Add an accepted local/private signed-submit path only behind explicit local
   enablement. The API should verify envelope shape, chain id, transaction hash,
   signing hash/digest, sender identity, signature bytes, nonce, fee, expiry,
   and duplicate pending state before writing to the pending file.

5. Local signed-send smoke.
   Add a CPU-only smoke that creates a draft, signs it with the local CLI test
   signer, submits the signed artifact, produces one local block, and confirms
   wallet balances/history/mempool/Admin/audit state. Negative cases must cover
   disabled submit, invalid signature, wrong chain id, stale nonce, duplicate
   pending transaction, expired transaction, and malformed envelope.

6. UI design review only.
   Before any UI mutation implementation, add a design-check document and guard
   proving the UI will not create, store, or manage key material. A future UI
   submit control may inspect and submit a pre-signed local artifact only after
   explicit approval.

## Required Gates Before Code

Before implementing signed-submit behavior, update or add:

- local/private signed-transfer fixtures
- contract validation
- negative case matrix
- audit-event expectations
- CLI warning and output contract
- API refusal and accepted response contracts
- smoke-script coverage
- handoff notes with exact commands and scope boundaries

Mutating signed-submit endpoints must remain disabled by default. They must
require explicit local/private-devnet flags or config names that cannot be
confused with production mode.

## UI Rules

The browser UI must not:

- generate private keys,
- store private keys,
- accept seed phrases or mnemonics,
- persist raw signatures or signed transactions in browser storage,
- use `localStorage`, `sessionStorage`, IndexedDB, or cookies for signing
  material,
- silently produce blocks after submit,
- send public-network requests, or
- claim production wallet, custody, privacy, DEX, CEX, legal, or compliance
  readiness.

Any future UI mutation control must remain behind an explicit local/private
feature switch and must use the shared TypeScript API client rather than direct
component-level mutation `fetch(` calls.

## Completion Criteria

Phase 1.4 is ready for a later RC decision only when:

- signed-transfer fixtures and contract checks pass,
- CLI-only test signing creates a verifiable local artifact,
- API signed-submit accepts only explicitly enabled local/private requests,
- negative cases prove no mutation on disabled or invalid input,
- one signed transfer can move from signed artifact to pending to confirmed,
- wallet, mempool, explorer, Admin, and audit views refresh consistently,
- no browser key material or custody behavior exists,
- no public, DEX, bridge, smart-contract, production, or exchange-listing scope
  is introduced.

## Future Tag Rule

Phase 1.4 must not create a release tag automatically. If future work needs a
new post-RC tag, use a new deliberate tag name only after:

- a candidate report is written,
- the relevant non-mutating readiness guard passes from a clean checkout,
- the user explicitly approves the exact tag name.

Do not create, move, delete, recreate, or push any tag from a generic continue
request. Do not move, delete, recreate, or repush existing Phase 1, Phase 1.1,
Phase 1.2, or Phase 1.3 tags without an exact tag-maintenance request.
