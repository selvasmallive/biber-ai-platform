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
- Do not implement privacy cryptography in the first private-devnet phase.
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

Current Phase 3 protocol decisions are recorded in
`docs/XRIQ_PHASE3_DECISIONS.md`. Treat that document as the active decision
record for consensus, supply, governance, and public-readiness scope.

Future centralized-exchange compatibility is tracked in
`docs/XRIQ_EXCHANGE_READINESS_CHECKLIST.md`. Treat it as a future-facing
engineering checklist only; it does not make XRIQ listing-ready.

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
- future centralized-exchange compatibility: keep the protocol directionally
  compatible with later exchange review by preserving transparent MVP
  accounting, stable node/RPC behavior, deposit/withdrawal integration paths,
  clear tokenomics, no default mandatory privacy, auditability, and legal/security
  review gates. This is a design posture only; XRIQ is not exchange-listing
  ready.
- selective privacy roadmap: keep the base devnet transparent now, but reserve
  future protocol space for Zcash-like shielded transfers, viewing keys, and
  payment/audit disclosure. Do not make Monero-style mandatory privacy the
  default XRIQ design if DEX usability and AML-friendly posture remain project
  goals.
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

## Future Selective Privacy Roadmap

The initial XRIQ private devnet remains transparent: accounts, balances,
transfers, blocks, and explorer output should stay inspectable while the core
ledger, wallet, storage, and node behavior mature.

If XRIQ later adds privacy, prefer a Zcash-like selective-disclosure design over
a Monero-like mandatory-privacy design:

- shielded/private transfer support is a later protocol module, not part of the
  current MVP
- transparent DEX pools, liquidity accounting, bridges, reserves, and explorer
  data should remain possible
- users or regulated services should be able to disclose activity through
  viewing keys, payment disclosure, audit receipts, or similar read-only proofs
  without exposing spend authority
- privacy features must be crypto-agile and versioned so proof systems and key
  formats can evolve
- privacy code must use reviewed libraries and external cryptography review;
  do not invent custom zero-knowledge, ring-signature, or stealth-address
  primitives in BIBER/Codex-generated code
- wallet, frontend, bridge, exchange, and business-service layers remain the
  right place for AML/KYC/sanctions controls; the base chain should not claim to
  be AML compliant by itself

Monero-style ideas are useful as research inspiration for strong fungibility and
default user privacy, but XRIQ should not adopt mandatory opaque transfers as
the default public design while DEX use, future listings, and lower legal-risk
posture are goals.

## Future Centralized Exchange Compatibility

XRIQ does not currently meet centralized exchange listing requirements. The
private devnet has no production mainnet, no public tokenomics, no audited
wallet/custody path, no real signature scheme, no public liquidity, and no legal
listing opinion.

The detailed future-facing checklist is
`docs/XRIQ_EXCHANGE_READINESS_CHECKLIST.md`.

Keep the architecture directionally compatible with future review by preserving:

- transparent MVP state, transaction, mempool, block, and explorer visibility
- stable node software that can later support reliable deposit and withdrawal
  infrastructure
- deterministic chain replay, storage validation, and clear error handling
- versioned/crypto-agile address, signature, and proof metadata
- optional/selective privacy only after review, never default mandatory opacity
- clear supply, fee, and governance documents before any public network
- security policy, open-source license, reproducible tests, and external audits
  before public exposure
- service-layer AML/KYC/sanctions/Travel Rule integration points for wallets,
  exchanges, bridges, custodians, and frontends, without claiming the base chain
  is AML compliant by itself

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

Current Phase 3 decision: public supply, emissions, burns, treasury allocation,
validator rewards, and token distribution remain unset and blocked until the
review gates in `docs/XRIQ_PHASE3_DECISIONS.md` and
`docs/XRIQ_LEGAL_RISK_REDUCTION.md` are satisfied.

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

Current Phase 3 decision: keep deterministic authority consensus for private
tests, add explicit chain/validator configuration before networked peers, and
defer public validator economics.

## Governance

Phase 3 governance is ordinary private engineering governance:

- decisions recorded in docs
- code reviewed through Git commits
- local and Vast verification before marking checkpoints complete
- no token-holder governance
- no public treasury, revenue, profit, asset, debt, equity, or management rights

Any public governance model is deferred until separate technical, legal, and
security review.

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
GET  /v1/chain/check
GET  /v1/blocks?limit=5
GET  /v1/blocks/{height_or_hash}
GET  /v1/transactions?limit=5
GET  /v1/transactions/{hash}
GET  /v1/accounts?limit=5
GET  /v1/accounts/{address}
GET  /v1/mempool
POST /v1/transactions
POST /v1/mempool
POST /v1/blocks
```

Current private-devnet implementation: `xriq-node serve-readonly` exposes a
loopback-first, dependency-free, read-only HTTP wrapper over the existing
file-backed JSON runner outputs. The current implemented endpoints are
`/health`, `/v1/chain/status`, `/v1/explorer/overview?limit=5`,
`/v1/chain/check`, `/v1/blocks?limit=5`, `/v1/blocks/{height_or_hash}`,
`/v1/transactions?limit=5`,
`/v1/transactions/{hash}`,
`/v1/accounts?limit=5`, `/v1/accounts/{address}`,
`/v1/accounts/{address}/transactions?limit=5`, `/v1/mempool`, and, when
`--snapshot-root <path>` is configured, `/v1/snapshots?limit=5` plus
`/v1/snapshots/latest`, `/v1/snapshots/latest/check`,
`/v1/snapshots/{snapshot_name}`, and `/v1/snapshots/{snapshot_name}/check`.
Transaction lookup scans confirmed transactions in persisted blocks. Account
list scans replayed private-devnet accounts in deterministic address order.
Block-list, transaction-list, and account-transaction lookup scan confirmed
persisted blocks in descending height order. When `--pending-file` is
configured, transaction lookup checks confirmed blocks first and then durable
pending state.

Explorer overview includes the replayed `state_root` so clients can compare
dashboard output against `/v1/chain/status`, restart checks, and snapshot
restore checks.

`/v1/chain/check` explicitly reports `verified: true` only after replaying the
chain file. When a durable pending file is configured, it also validates pending
records into the private-devnet mempool before returning status.

Block detail lookup accepts decimal heights, the `latest` selector, or
64-character lowercase hex block hashes.

`xriq-node serve-private` enables the same private-devnet HTTP surface plus
`POST /v1/transactions`, `POST /v1/mempool`, `POST /v1/blocks`,
`POST /v1/snapshots/export?snapshot_dir=<path>`, and
`POST /v1/snapshots/import?snapshot_dir=<path>`. The transaction POST body may
be either the existing wallet transfer draft text emitted by
`xriq-wallet transfer` or the flat
`xriq-node-transfer-submit-v1` JSON transfer body emitted by
`xriq-wallet transfer --format json`; the server validates it against the
replayed chain state, immediately produces one block, and persists that block to
the configured chain file. This is an MVP submit-and-block helper, not a
production mempool API or production signed-transaction format. This is still
private-devnet tooling, not a public API.

When `serve-private --pending-file <path>` is used, `POST /v1/mempool`
validates a wallet draft or JSON transfer body and appends it to durable
private-devnet pending state. `POST /v1/blocks` produces one block from that
pending file and compacts the file so included transactions are removed.
Snapshot export/import use the server's configured chain/pending files and
preserve the no-overwrite import guard. After HTTP import, `/v1/chain/check`
is the restored-server replay verification path for the fresh target files.

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
xriq-wallet accounts
xriq-wallet balance
xriq-wallet history
xriq-wallet pending
xriq-wallet status
xriq-wallet check
xriq-wallet submit
xriq-wallet send
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
- account list, balance, and transaction list
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
    private-devnet test identities, transfer drafts, and private-devnet JSON
    submit bodies.
11. Add explorer API/UI for private-devnet inspection. Current status: done for
    dependency-free private-devnet view models and text rendering.
12. Add local multi-node tests. Current status: done for in-process
    private-devnet block import and follower validation.
13. Revisit consensus, supply, governance, and public-readiness decisions.
    Current status: done in `docs/XRIQ_PHASE3_DECISIONS.md`.
14. Add `xriq-crypto` and canonical transaction/block hashing. Current status:
    done for SHA-256 canonical hashes and a test-only verifier boundary.
15. Wire canonical hashes into node/RPC/storage APIs. Current status: done for
    canonical RPC transaction submission, storage block append, node
    transaction submission, node block production, and node peer-block import
    helper paths.
16. Add private-devnet genesis/chain configuration and a deterministic root
    calculation strategy. Current status: done for shared private-devnet
    `GenesisConfig`, deterministic test allocations, genesis-derived ledger,
    mempool, consensus, and node constructors, account-state root entries, and
    SHA-256 account-state root calculation.
17. Enforce deterministic transaction-root and state-root validation on
    imported blocks, then wire the test-only block signature verifier at the
    node boundary. Current status: done for private-devnet peer-block import.
18. Wire hash-bound test-only transaction signature verification into RPC/node
    submission and imported-block transaction execution. Current status: done
    for private-devnet submission/import boundaries.
19. Add deterministic private-devnet chain replay startup. Current status: done
    for rebuilding ledger height, account state, and latest tip from persisted
    canonical blocks. Snapshot checkpointing remains deferred.
20. Wire replay startup into a local node runner path. Current status: done for
    private-devnet `xriq-node status --chain-file <path>` and
    `xriq-node produce-transfer-block --chain-file <path> ...` commands, plus
    a file-backed `xriq-node explorer-overview --chain-file <path>` command.
    HTTP/RPC serving remains deferred.
21. Wire wallet transfer drafts into local node block production. Current
    status: done for the wallet `key=value` transfer draft format consumed by
    `xriq-node produce-draft-block --chain-file <path> --draft-file <path>`.
    The parser tolerates UTF-8 BOMs from Windows PowerShell draft files,
    rejects malformed/wrong-chain drafts, and still uses private-devnet
    test-only signatures.
22. Add focused persisted-chain inspection commands. Current status: done for
    file-backed `xriq-node block-list --chain-file <path>`,
    `xriq-node block-detail --chain-file <path> --height <height>`
    / `--block-hash <64-hex>` and
    `xriq-node account-detail --chain-file <path> --address <address>`
    commands that replay canonical private-devnet chain files before rendering
    dependency-free explorer detail output.
23. Add a compact local private-devnet smoke script. Current status: done for
    `bash scripts/xriq_private_devnet_smoke.sh`, which chains wallet draft
    generation, wallet JSON submit body generation, mempool detail preview,
    draft-block production, explorer overview, block detail, account detail,
    and live HTTP JSON submit behavior over persisted private-devnet chain
    files.
24. Add read-only mempool inspection to the local runner. Current status: done
    for `xriq-node mempool-detail --chain-file <path> [--draft-file <path>]`,
    which replays a private-devnet chain file and can preview a wallet draft as
    a pending transaction without producing or persisting a block.

## Current Prototype Status

As of 2026-05-17:

- Rust workspace path: `xriq/`.
- Implemented crates:
  - `xriq/crates/xriq-core`
  - `xriq/crates/xriq-consensus`
  - `xriq/crates/xriq-crypto`
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
  - shared private-devnet `GenesisConfig` with explicit chain id, genesis
    block hash, fee policy, authority, mempool limits, block limits, and
    deterministic test allocations
- Implemented ledger state transitions:
  - account balances and nonces
  - minimum fee validation through transaction context
  - fee-sink crediting
  - atomic mutation by cloning state before commit
  - genesis-derived ledger construction
  - deterministic account-state entries for state-root calculation
- Implemented mempool rules:
  - duplicate transaction-hash rejection
  - one pending transaction per account nonce
  - minimum fee and zero-amount rejection
  - deterministic fee/order/hash transaction ordering
  - genesis-derived private-devnet mempool policy
- Implemented single-authority block production:
  - parent-height and parent-chain checks
  - explicit state-root and transactions-root inputs
  - producer identity from private-devnet config
  - mempool transaction selection by deterministic ordering
  - per-block transaction cap enforcement
  - genesis-derived private-devnet authority policy
- Implemented crypto/hash boundary:
  - SHA-256 canonical transaction signing hashes
  - SHA-256 canonical transaction hashes
  - SHA-256 canonical block-header signing hashes
  - SHA-256 canonical block/header hashes
  - deterministic transaction-list roots over transaction hashes
  - deterministic account-state roots over sorted account state
  - explicit signature algorithm identifiers for crypto agility
  - hash-bound `TestOnlySignatureVerifier` for private-devnet tests
- Canonical hashes are wired into higher-level local APIs:
  - RPC transaction submission can derive the transaction hash from canonical
    transaction bytes
  - storage can append blocks using the canonical block/header hash
  - node transaction submission can derive canonical transaction hashes
  - node block production can derive the transaction-list root and block hash
    for the produced block
  - node block production can derive the account-state root from the post-block
    ledger state
  - node peer-block import can derive the canonical block hash before storage
    commit
  - explicit manual hash APIs remain available for fixture control and
    negative tests
- Implemented local RPC endpoint behavior:
  - health response
  - chain status response
  - account lookup
  - mempool listing
  - pending transaction lookup
  - transaction submission with ledger-backed validation before mempool insert
  - transaction submission rejects invalid hash-bound test-only signatures
    before mempool insert
- Implemented local storage and node loop:
  - in-memory block index by hash and height
  - append-only local file store for block persistence and reload
  - deterministic startup replay through `XriqNode::from_genesis_replaying_store`
  - local private-devnet runner status command backed by replay startup
  - local private-devnet chain-check command that replays the persisted chain
    file, optionally validates durable pending-file records, and returns
    `verified: true` with deterministic tip/status fields
  - local private-devnet runner transfer/block command that creates a
    hash-bound test transaction, submits it through node validation, produces a
    canonical-root block with a hash-bound test block signature, persists it,
    and makes the result replayable from the chain file
  - local private-devnet runner draft-file command that consumes wallet
    `key=value` transfer drafts, rejects malformed or wrong-chain drafts before
    storage mutation, produces a canonical block from valid drafts, and
    tolerates UTF-8 BOMs from Windows-created draft files
  - local private-devnet explorer overview command that replays the persisted
    chain file and renders chain height, latest block hash, stored block count,
    replayed state root, pending count, and recent block summaries without
    starting HTTP/RPC serving
  - local private-devnet block detail command that replays the persisted chain
    file and renders one block by height, latest selector, or block hash,
    including transaction hashes and transfer summaries
- local private-devnet account detail command that replays the persisted
    chain file and renders one account balance and nonce by address
  - local private-devnet account list command that replays the persisted chain
    file and lists account balances/nonces in deterministic address order
  - local private-devnet account transaction history command that replays the
    persisted chain file and lists confirmed transactions involving one account
    in descending block order
  - local private-devnet transaction list command that replays the persisted
    chain file and lists recent confirmed transactions in descending block
    order
  - local private-devnet mempool detail command that replays the persisted
    chain file and can preview a wallet draft in the pending-transaction view
    without mutating storage
  - local private-devnet transaction detail command that replays the persisted
    chain file, returns confirmed transactions by hash, and can preview a
    matching wallet draft as pending without mutating storage
  - local private-devnet read-only HTTP wrapper through
    `xriq-node serve-readonly`, defaulting to `127.0.0.1:8787` and reusing the
    file-backed JSON runner responses for health/status/explorer/block/account
    transaction/mempool inspection; block detail accepts decimal height,
    `latest`, or a 64-character lowercase hex block hash; transaction list
    returns recent confirmed transactions; chain check returns `verified: true`
    after replay validation; account list returns replayed accounts in address
    order; explorer overview includes the replayed state root; without
    `--pending-file`, transaction lookup covers confirmed transactions in
    persisted blocks only
  - local private-devnet submit-capable HTTP wrapper through
    `xriq-node serve-private`; `POST /v1/transactions` accepts either the
    wallet draft text body or a flat JSON transfer body, validates it,
    immediately produces one block, and persists it to the file-backed chain
  - optional durable private-devnet pending HTTP state through
    `serve-private --pending-file <path>`; `POST /v1/mempool` validates a
    wallet draft or JSON transfer body, appends it to the pending file, and
    lets `GET /v1/chain/status`, `GET /v1/mempool`, and
    `GET /v1/transactions/{hash}` report pending state across requests and
    server restarts
  - durable pending mempool inspection through
    `xriq-node mempool-detail --pending-file <path>`
  - durable pending block production through
    `xriq-node produce-pending-block --pending-file <path>` and
    `POST /v1/blocks`, including pending-file compaction after included
    transactions are persisted to the chain file
  - local HTTP snapshot export/import through `POST /v1/snapshots/export` and
    `POST /v1/snapshots/import`
  - optional local HTTP snapshot discovery through `GET /v1/snapshots` and
    `GET /v1/snapshots/latest` / `GET /v1/snapshots/latest/check` /
    `GET /v1/snapshots/{snapshot_name}` when `--snapshot-root <path>` is
    configured, plus
    `GET /v1/snapshots/{snapshot_name}/check` for HTTP-accessible pre-restore
    replay verification
  - private-devnet client preflight transfer flow through
    `xriq-node preflight-transfer`, checking sender balance/nonce, submitting
    to durable pending state, producing a block, compacting pending state, and
    verifying confirmed transaction lookup
  - stable `--format json` output for status, block production, explorer
    overview, block detail, account detail, account transaction history,
    transaction list, mempool detail, and transaction detail runner commands,
    while preserving text output as the default; successful JSON responses
    include `command` names
  - structured JSON error responses for failed `xriq-node` commands when
    `--format json` is requested, while preserving human-readable text errors
    as the default
  - documented private-devnet JSON runner contract in
    `docs/XRIQ_NODE_JSON_SCHEMA.md`
  - checked private-devnet JSON fixtures under `xriq/fixtures/private-devnet`
    for selected wallet and node schema-drift tests, including block detail
    transaction hashes, wallet chain-check output, wallet direct-send pending
    output, pending-block production, and preflight transfer
  - one-command private-devnet smoke script that validates wallet draft,
    mempool detail preview, durable pending-file mempool detail, pending and
    confirmed transaction detail, selected JSON outputs, draft-block, durable
    HTTP pending state, durable
    pending-block production, client preflight transfer flow, explorer
    overview, block detail, account list/detail, transaction-list behavior, and
    snapshot list/latest/latest-check/detail/check flows against persisted chain files, plus a
    separate wallet pending-to-block lifecycle from wallet transfer JSON through
    durable pending submission, pending inspection, pending-block production,
    and confirmed wallet transaction status, and
    persists representative JSON response examples beside the smoke artifacts
    for future BIBER agents and HTTP/RPC adapters
  - CPU-only Phase 1 local verification wrapper through
    `scripts/xriq_phase1_local_check.py`, which runs XRIQ format checks,
    workspace tests, workspace clippy, and the transfer plus HTTP smokes
    without using Vast or BIBER runtime state
  - Phase 1 private-devnet release-candidate checklist in
    `docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md`
  - node transaction submission
  - node transaction submission rejects invalid hash-bound test-only signatures
    before mempool insert
  - pending transaction application into produced blocks
  - block persistence before node-state commit
  - RPC-visible node state after block production
  - peer block import for in-process private-devnet multi-node tests
  - follower-side parent, chain, signature, authorized-producer, and block-size
    checks before ledger/storage commit
  - follower-side deterministic transaction-root and state-root checks before
    storage commit
  - follower-side hash-bound test-only block-header signature verification
  - follower-side hash-bound test-only transaction signature verification
    before imported-block ledger execution
  - local mempool cleanup when imported peer blocks include pending transactions
  - replay validates contiguous stored heights, canonical stored block hashes,
    parent links, authorized producer, transaction roots, account-state roots,
    hash-bound test-only signatures, and final stored-count/tip-state
    consistency before restoring node tip/state
  - runner status exposes the replayed account-state root so deterministic
    restart, copy, and future snapshot checks can compare height, latest block
    hash, and state root together
  - private-devnet snapshot export/import through `xriq-node snapshot-export`
    and `xriq-node snapshot-import`; the MVP snapshot copies the replayable
    chain file, optional durable pending file, and manifest into a new
    directory, and import refuses to overwrite existing target files
  - private-devnet snapshot discovery and verification through `xriq-node
    snapshot-list`, `xriq-node snapshot-latest`,
    `xriq-node snapshot-latest-check`, `xriq-node snapshot-detail`, and
    `xriq-node snapshot-check`; discovery reads local snapshot manifests under
    an operator-provided root, and check replays the snapshot files to compare
    the deterministic tip/status fields before restore
  - post-restore snapshot regression through `xriq-node chain-check`, which
    replays imported chain and pending files before restored targets are used
- Implemented private-devnet wallet CLI baseline:
  - deterministic test identity generation from labels
  - file-backed local `xriq-wallet status` lookup for chain height, latest
    block hash, state root, pending count, and stored block count
  - file-backed local `xriq-wallet check` lookup that replays the chain and
    optional durable pending file before returning `verified: true` plus the
    same deterministic tip/status fields
  - file-backed local `xriq-wallet accounts` lookup for deterministic account
    list inspection
  - file-backed local `xriq-wallet balance` lookup for account balance and
    nonce inspection
  - file-backed local `xriq-wallet history` lookup for transparent account
    transaction history inspection
  - file-backed local `xriq-wallet tx status` lookup for confirmed transaction
    status inspection, plus pending status inspection from wallet drafts or
    durable pending files
  - file-backed local `xriq-wallet pending` lookup for durable private-devnet
    pending-file inspection
  - local `xriq-wallet submit` support that validates a wallet transfer draft
    or `xriq-node-transfer-submit-v1` JSON body against the replayed
    file-backed chain and appends it to a durable private-devnet pending file
    without producing a block
  - local `xriq-wallet send` support that constructs a private-devnet test
    transfer and submits it directly to a durable pending file in one command
    without requiring an intermediate transfer file
  - transfer draft construction
  - local `xriq-wallet transfer --nonce auto` support that replays the
    file-backed chain and derives the sender account nonce before constructing
    a private-devnet transfer draft
  - deterministic transaction-hash output for local status lookup
  - hash-bound test-only signatures through `xriq-crypto`
  - no real private-key, seed-phrase, or production custody support
- Implemented private-devnet explorer baseline:
  - read-only chain overview from local RPC snapshots
  - latest block listing from storage by descending height
  - state-root marker in explorer overview for restart/snapshot comparison
  - block detail with transaction hashes and transfer summaries
  - account listing in deterministic address order
  - account balance and nonce lookup
  - account transaction history with sent/received/self direction
  - recent confirmed transaction listing
  - pending mempool transaction detail and deterministic order
  - dependency-free text rendering for private-devnet inspection
  - dependency-free JSON rendering through the file-backed `xriq-node` runner
    for machine-readable private-devnet inspection
- Local verification:
  - `cargo fmt --check`
  - `cargo test -j 1` with `117` passing tests. On Windows, this was run with
    `CARGO_TARGET_DIR=target-codex-json-errors` to avoid default target binary
    locks.
  - `cargo clippy -- -D warnings`.
  - `cargo run -p xriq-wallet -- transfer --chain-id xriq-devnet --from xriqdev1alice00000000000 --to xriqdev1bobbb00000000000 --amount 25 --fee 2 --nonce 0 --expires-at-height 100` captured to `target/xriq-wallet-transfer-draft-20260517-codex.txt`.
  - `cargo run -p xriq-node -- produce-draft-block --chain-file target/xriq-node-draft-smoke-chain-20260517-codex.bin --draft-file target/xriq-wallet-transfer-draft-20260517-codex.txt --alice-balance 100 --timestamp-ms 1000`.
  - `cargo run -p xriq-node -- explorer-overview --chain-file target/xriq-node-draft-smoke-chain-20260517-codex.bin --alice-balance 100 --limit 5`.
  - `cargo run -p xriq-node -- block-detail --chain-file target/xriq-node-detail-smoke-chain-20260517-codex.bin --alice-balance 100 --height 1`.
  - `cargo run -p xriq-node -- block-detail --chain-file target/xriq-node-detail-smoke-chain-20260517-codex.bin --alice-balance 100 --block-hash <64-hex>`.
  - `cargo run -p xriq-node -- account-detail --chain-file target/xriq-node-detail-smoke-chain-20260517-codex.bin --alice-balance 100 --address xriqdev1alice00000000000`.
  - `cargo run -p xriq-node -- mempool-detail --chain-file target/xriq-node-mempool-smoke-chain-20260517-codex.bin --draft-file target/xriq-wallet-transfer-draft-20260517-codex.txt --alice-balance 100`.
  - JSON output coverage for `status`, `produce-draft-block`,
    `explorer-overview`, `block-detail`, `account-detail`, and
    `mempool-detail` through the Rust test suite, including successful
    response command names.
  - JSON error-response coverage for a missing required flag through the Rust
    test suite.
  - Local Windows Bash execution is unavailable on this workstation because
    `bash.exe` maps to WSL and no WSL distribution is installed; Bash script
    verification is therefore recorded under Vast verification.
- Latest Vast verification:
  - `bash -n scripts/xriq_private_devnet_smoke.sh`.
  - `cargo fmt --check`
  - `cargo test -j 1` with `117` passing tests.
  - `cargo clippy -- -D warnings`.
  - `xriq-node mempool-detail` through the one-command smoke path, verifying a
    wallet draft can be previewed in the local mempool before block production.
  - `xriq-node mempool-detail --format json`,
    `explorer-overview --format json`, and `account-detail --format json`
    through the one-command smoke path, including successful response command
    names.
  - `xriq-node status --format json` error output for a missing `--chain-file`
    through the one-command smoke path.
  - `xriq-node produce-draft-block`, `explorer-overview`, `block-detail`, and
    `account-detail` text output through the same smoke path.
  - `bash scripts/xriq_private_devnet_smoke.sh`, which wrote artifacts under
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T154848Z-22177`.
  - The smoke artifact directory includes generated JSON examples for
    mempool detail, explorer overview, account detail, and the status error
    response.

Next implementation target: keep the local file-backed workflow small and
deterministic. The first snapshot/export format is now present for the private
devnet; good next targets are either exposing it through a thin BIBER API
wrapper or continuing wallet/explorer workflow polish. Keep public XRIQ launch
or listing work blocked.

## Open Decisions

- final chain purpose beyond private engineering prototype
- detailed public supply model after review
- consensus model after private devnet
- validator admission rules after private-devnet config
- governance and upgrade process for any public network
- final wallet key format
- production signature verification algorithms and key formats
- explorer technology stack
- public API authentication and rate-limit model
- legal/compliance path for any public token use
