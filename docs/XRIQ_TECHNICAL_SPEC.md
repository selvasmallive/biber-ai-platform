# XRIQ Technical Specification

Draft version: `0.1`

Status: design draft for private development only. This document is not a
public launch plan, investment document, token-sale plan, or legal/compliance
assessment.

## Purpose

XRIQ is planned as a Rust-based blockchain and cryptocurrency project developed
with BIBER AI as the primary coding assistant. The first goal is a private,
test-only devnet that proves the core engineering pieces:

- deterministic transaction and block validation
- a local chain state model
- a mempool with duplicate and fee checks
- a node RPC API
- a wallet CLI for test keys and test transfers
- an explorer API/UI for private-devnet visibility
- reproducible tests and CI

The near-term purpose is to build engineering capability and a private
prototype. Public token distribution, exchange listing, fundraising, payments,
custody, or production network operation are out of scope until separate
security, legal, tax, AML, securities, and consumer-protection review is
completed.

## Non-Goals

- Do not create a public mainnet in the first implementation phase.
- Do not market or sell tokens from the prototype.
- Do not implement custom cryptography.
- Do not promise monetary value, returns, yield, rewards, or investment utility.
- Do not add custody, exchange, bridge, stablecoin, or payment features before
  independent review.
- Do not rely on model-generated security-critical code without human review,
  tests, and external audit before any public exposure.

## Legal-Risk Reduction Guardrail

All XRIQ design and implementation work must follow
`docs/XRIQ_LEGAL_RISK_REDUCTION.md`. If a requested feature touches public
tokens, DEXs, custody, bridges, stablecoins, payments, liquidity incentives,
airdrops, validator rewards, market listings, or investment-facing messaging,
pause the feature until the required review gates in that document are satisfied.

## Target Design Advantages

XRIQ should be designed around a focused set of advantages instead of trying to
clone Ethereum feature-for-feature:

- no mining: use validator-based private-devnet consensus first, with public
  proof-of-stake or BFT-style consensus treated as a later design phase.
- predictable fees: start with simple minimum fees and deterministic mempool
  ordering, then evolve toward a transparent fee market only after the basic
  ledger and wallet flows are proven.
- Rust-first implementation: keep the protocol core in Rust with small crates,
  strong tests, and future WASM support for wallet, light-client, or contract
  tooling.
- clean token issuance: support protocol-governed native supply and future
  XRC-style token modules instead of mining-based coin creation.
- DEX and BTC-swap friendliness: prefer non-custodial atomic-swap and
  interoperability designs before bridges, wrapped assets, or custodial
  services.
- crypto agility: make key, address, and signature formats versioned so the
  network can migrate algorithms and later support hybrid or post-quantum
  signatures without redesigning the whole chain.
- compliance-minimizing posture: keep the first network private and test-only,
  avoid fundraising or profit promises, and require legal/security review before
  any public token, bridge, exchange, or payment feature.
- vertical integration with BIBER: use BIBER to help build the node, wallet,
  explorer, SDKs, tests, and future custom agent workflows around the chain.

## Architecture Overview

The private prototype should be a Rust workspace with small crates that can be
tested independently:

```text
xriq-core      chain types, hashes, amounts, addresses, serialization
xriq-crypto    approved key/signature wrappers, no custom primitives
xriq-ledger    accounts, balances, nonces, transaction application
xriq-mempool   pending transaction validation and ordering
xriq-consensus private-devnet block production and finality rules
xriq-storage   chain database abstraction and local storage backend
xriq-node      node service, networking facade, block production loop
xriq-rpc       HTTP/JSON RPC API
xriq-wallet    wallet CLI for test keys, signing, and transfers
xriq-explorer  explorer API/UI integration layer
```

For the first prototype, prefer correctness and testability over performance.
Keep network behavior minimal until the single-node and local multi-node tests
are deterministic.

## Chain Model

Use an account-based model for the first private devnet.

Rationale:

- simpler wallet UX for end users
- easier explorer views for account balances and transactions
- straightforward nonce-based replay protection
- fewer moving parts for BIBER-assisted code generation than a UTXO model

Each account has:

- address
- balance
- nonce
- optional metadata reserved for future protocol versions

Account state must be modified only by validated transactions applied through
the ledger state transition function.

## Native Asset

Native asset symbol: `XRIQ`.

Prototype denomination:

- `1 XRIQ = 1_000_000_000 base units`
- store all amounts as unsigned integer base units
- reject floating-point amounts in protocol code

Use a Rust newtype for amounts:

```rust
pub struct XriqAmount(u128);
```

All arithmetic must use checked operations.

## Supply Policy

XRIQ does not use mining for coin creation in the planned design.

For the private devnet, use deterministic test allocation only:

- genesis creates test balances for configured devnet accounts
- no public sale
- no mining reward promise
- no staking yield promise

Open decision for later phases:

- fixed supply, capped emissions, or validator reward schedule
- whether transaction fees are burned, paid to block producers, or split
- whether supply policy should be upgradeable
- whether future application tokens use a native XRC-style token module, smart
  contracts, or both

Do not finalize a public supply policy without legal and economic review.

## Address And Key Model

Prototype key type:

- use a mature Rust crypto crate for Ed25519 or secp256k1
- do not implement signature algorithms manually
- keep key generation in wallet tooling, not in node consensus code

Address format:

- derive address bytes from the public key using a standard hash function from
  a reviewed crate
- encode addresses with a human-safe encoding such as bech32m or base58check
- include an XRIQ-specific network prefix for private devnet addresses

Required checks:

- reject malformed addresses
- reject wrong network prefixes
- reject invalid public keys or signatures
- never log private keys or seed phrases

Crypto-agility requirements:

- include an algorithm identifier in signature verification metadata
- use versioned address formats so future key types can coexist
- keep signature verification behind a small protocol interface
- allow a future policy layer to reject deprecated algorithms by block height
- design room for hybrid signatures, such as classical plus post-quantum
  signatures, after mature libraries and audits are available

## Transaction Format

Minimum transfer transaction:

```text
version
chain_id
from
to
amount
fee
nonce
memo_hash optional
expires_at_height optional
signature
```

Validation rules:

- transaction version is supported
- chain id matches the local chain
- sender and recipient addresses are valid
- sender and recipient are not blank and not malformed
- amount is greater than zero
- fee meets the minimum fee rule
- nonce equals the sender account nonce
- sender has enough balance for amount plus fee
- signature verifies against canonical transaction bytes
- transaction hash is not already in the mempool or current block
- transaction is not expired

Canonical serialization must be deterministic. The same transaction fields must
always produce the same signing bytes and hash.

## Block Format

Minimum block header:

```text
version
chain_id
height
previous_block_hash
state_root
transactions_root
timestamp_ms
producer_address
consensus_round
signature
```

Minimum block body:

```text
transactions
evidence optional
```

Validation rules:

- height is parent height plus one
- previous block hash matches the local tip or selected fork parent
- timestamp is within allowed drift
- producer is authorized for the private devnet
- transaction root matches the body
- resulting state root matches deterministic execution
- block signature is valid
- all included transactions pass validation in order

## Mempool Rules

The first mempool should be simple and deterministic:

- reject duplicate transaction hashes
- reject malformed or invalid transactions
- reject transactions with stale nonces
- keep at most one transaction per account nonce
- sort by fee amount, then arrival time, then transaction hash in the first
  dependency-free prototype
- revisit fee-per-byte ordering after canonical serialization size is available
- cap maximum transaction count and memory usage
- expose pending transaction count through RPC

The mempool should be easy to clear between tests.

## Fees

Prototype fee model:

- minimum flat fee plus optional fee-per-byte
- checked arithmetic only
- fee is deducted from sender during transaction application
- fee destination is a protocol account or block producer account, configurable
  for private-devnet experiments

Open decision:

- whether fees are burned, paid to producer, or split in later phases

## Consensus

Phase 3 private devnet should start with deterministic authority consensus:

- a fixed validator set in genesis config
- round-robin or single-authority block production for local tests
- signed blocks
- no proof-of-work mining
- no public validator admission
- no economic staking until a later design review

This keeps the first implementation testable. More advanced consensus choices
such as proof of stake or BFT finality should be treated as later design
decisions, not Phase 3 defaults.

## Finality

Prototype finality:

- single-node devnet: block is final immediately after local validation
- local multi-node devnet: block is final after the configured authority quorum
  signs or accepts it

Open decision:

- public-network finality model
- fork-choice rules
- slashing or validator penalties

## Networking

Phase 3 networking should start local and conservative:

- single-node mode first
- local multi-node mode second
- peer identity with public keys
- explicit allowlist for private test nodes
- no public peer discovery in the first prototype

Required future concerns:

- peer scoring
- rate limiting
- message size limits
- replay protection
- chain id isolation
- ban/denylist controls

## Storage

Prototype storage should support:

- chain metadata
- block headers
- block bodies
- transaction index
- account state
- nonce state
- state root snapshots or replayable journals

Start with a local embedded database or file-backed store that is easy to reset
in tests. Keep generated chain data out of Git.

## RPC API

Minimum node RPC:

```text
GET  /health
GET  /v1/chain/status
GET  /v1/blocks/{height_or_hash}
GET  /v1/transactions/{hash}
GET  /v1/accounts/{address}
GET  /v1/mempool
POST /v1/transactions
```

Minimum wallet-facing RPC behavior:

- fetch chain id
- fetch account nonce and balance
- submit signed transaction
- return transaction status

Production-facing API concerns such as auth, quotas, TLS, monitoring, and abuse
controls are out of scope for the first private devnet but must be designed
before public exposure.

## Wallet CLI

Minimum private-devnet wallet commands:

```text
xriq-wallet key generate
xriq-wallet key import
xriq-wallet key export-public
xriq-wallet balance
xriq-wallet transfer
xriq-wallet tx status
```

Wallet requirements:

- never print private keys unless explicitly requested
- prefer encrypted local key storage
- require confirmation before signing transfers
- support offline transaction signing as a later milestone
- keep seed phrases and private keys out of logs, docs, generated artifacts, and
  Codex/BIBER prompts

## Explorer

Private explorer scope:

- chain status
- latest blocks
- block detail
- transaction detail
- account balance and transaction list
- mempool size

The explorer should display private-devnet data only until public launch review
is complete.

## BIBER Usage For XRIQ

BIBER should be used through inference first:

- draft Rust module skeletons
- generate unit-test candidates
- review validation rules
- explain compiler errors
- propose RPC schemas
- produce migration or CI snippets

Do not fine-tune immediately for every XRIQ need. Add held-out eval prompts and
validators first. Fine-tune only when BIBER repeatedly fails a useful Rust/XRIQ
task.

## Security Gates

Before any public network, require:

- threat model
- dependency audit
- cryptography review
- key management review
- consensus safety review
- wallet signing review
- fuzz/property testing for parsers and validation
- external audit for security-critical components
- incident response and upgrade plan

## Prototype Milestones

1. Approve this technical spec direction. Current status: in progress.
2. Create the Rust workspace skeleton. Current status: done in `xriq/`.
3. Implement `xriq-core` amount, address, hash, and serialization types.
   Current status: done for the dependency-free private-devnet baseline.
4. Implement transaction validation with unit tests. Current status: done for
   basic signed transfers.
5. Implement account ledger state transitions. Current status: done for basic
   transfer, nonce, fee, and atomic-state checks.
6. Implement mempool duplicate and fee checks. Current status: done for the
   dependency-free private-devnet baseline.
7. Implement deterministic single-node block production. Current status: done
   for the single-authority private-devnet baseline.
8. Add local RPC endpoints. Current status: done for the dependency-free local
   service baseline.
9. Add durable local storage and a node loop. Current status: done for the
   dependency-free local private-devnet baseline.
10. Add wallet CLI for test transfers. Current status: done for deterministic
    private-devnet test identities and transfer drafts.
11. Add explorer API/UI for private-devnet inspection. Current status: done for
    dependency-free private-devnet view models and text rendering.
12. Add local multi-node tests. Current status: done for in-process
    private-devnet block import and follower validation.
13. Revisit consensus, supply, governance, and public-readiness decisions.

## Current Prototype Status

As of 2026-05-17:

- Rust workspace path: `xriq/`.
- Implemented crates:
  - `xriq/crates/xriq-core`
  - `xriq/crates/xriq-consensus`
  - `xriq/crates/xriq-explorer`
  - `xriq/crates/xriq-ledger`
  - `xriq/crates/xriq-mempool`
  - `xriq/crates/xriq-node`
  - `xriq/crates/xriq-rpc`
  - `xriq/crates/xriq-storage`
  - `xriq/crates/xriq-wallet`
- Implemented dependency-free private-devnet core primitives:
  - checked `XriqAmount`
  - validated devnet `Address`
  - fixed-size `Hash32`
  - basic signed-transfer shape and validation context
  - block-header validation against a parent header view
- Implemented ledger state transitions:
  - account balances and nonces
  - minimum fee validation through transaction context
  - fee-sink crediting
  - atomic mutation by cloning state before commit
- Implemented mempool rules:
  - duplicate transaction-hash rejection
  - one pending transaction per account nonce
  - minimum fee and zero-amount rejection
  - deterministic fee/order/hash transaction ordering
- Implemented single-authority block production:
  - parent-height and parent-chain checks
  - explicit state-root and transactions-root inputs
  - producer identity from private-devnet config
  - mempool transaction selection by deterministic ordering
  - per-block transaction cap enforcement
- Implemented local RPC endpoint behavior:
  - health response
  - chain status response
  - account lookup
  - mempool listing
  - pending transaction lookup
  - transaction submission with ledger-backed validation before mempool insert
- Implemented local storage and node loop:
  - in-memory block index by hash and height
  - append-only local file store for block persistence and reload
  - node transaction submission
  - pending transaction application into produced blocks
  - block persistence before node-state commit
  - RPC-visible node state after block production
  - peer block import for in-process private-devnet multi-node tests
  - follower-side parent, chain, signature, authorized-producer, and block-size
    checks before ledger/storage commit
  - local mempool cleanup when imported peer blocks include pending transactions
- Implemented private-devnet wallet CLI baseline:
  - deterministic test identity generation from labels
  - transfer draft construction
  - fake nonempty test signatures only
  - no real private-key, seed-phrase, or production custody support
- Implemented private-devnet explorer baseline:
  - read-only chain overview from local RPC snapshots
  - latest block listing from storage by descending height
  - block detail and transfer summaries
  - account balance and nonce lookup
  - pending mempool transaction detail and deterministic order
  - dependency-free text rendering for private-devnet inspection
- Local verification:
  - `cargo fmt --check`
  - `cargo test -j 1` with `69` passing tests.
  - `cargo clippy -- -D warnings`.
- Latest Vast verification:
  - `cargo fmt --check`
  - `cargo test -j 1` with `69` passing tests.
  - `cargo clippy -- -D warnings`.

Next implementation target: revisit consensus, supply, governance, and
public-readiness decisions.

## Open Decisions

- final chain purpose beyond private engineering prototype
- public supply model
- consensus model after private devnet
- validator admission rules
- governance and upgrade process
- final wallet key format
- explorer technology stack
- public API authentication and rate-limit model
- legal/compliance path for any public token use
