# XRIQ Phase 1.1 Contracts

Status: Milestone A contract baseline for the local/private end-to-end XRIQ
prototype.

This document defines the first product-facing API and database contracts for
Phase 1.1. It does not change the Phase 1 RC1 tag, create a production API,
launch a public network, approve custody, or enable trading.

## Contract Principles

- Rust node state remains the source of truth.
- PostgreSQL is an indexed read model for explorer, analytics, and audit views.
- UI clients should read from stable product APIs, not directly from chain files.
- All Phase 1.1 endpoints are private-devnet/local unless a later document says
  otherwise.
- All money-like fields use integer base units encoded as strings in JSON.
- All hashes are lowercase 64-character hex strings.
- All timestamps are UTC ISO 8601 strings in product APIs; node-internal
  millisecond timestamps can remain implementation details.
- Do not expose private keys, seed phrases, real custody controls, or production
  signing flows.

## API Groups

### Health And Metadata

```text
GET /api/v1/health
GET /api/v1/version
GET /api/v1/network
```

Purpose:

- confirm the private service is running
- identify chain/network metadata
- show whether the service is local/private-devnet

Minimum fields:

```json
{
  "ok": true,
  "network": "xriq-devnet",
  "environment": "private-devnet",
  "service": "xriq-api",
  "version": "phase1.1-dev"
}
```

### Explorer Read APIs

```text
GET /api/v1/explorer/overview
GET /api/v1/blocks?limit=25&cursor=<cursor>
GET /api/v1/blocks/{height-or-hash}
GET /api/v1/transactions?limit=25&cursor=<cursor>
GET /api/v1/transactions/{tx_hash}
GET /api/v1/accounts?limit=25&cursor=<cursor>
GET /api/v1/accounts/{address}
GET /api/v1/accounts/{address}/transactions?limit=25&cursor=<cursor>
GET /api/v1/mempool
GET /api/v1/snapshots
GET /api/v1/snapshots/{snapshot_name}
```

Purpose:

- serve React explorer UI
- serve admin/operator inspection views
- read from PostgreSQL indexer tables when available
- fall back to node read wrappers only during early local development

Required behavior:

- pagination must be deterministic
- indexer status must be visible in overview responses
- every response must include `environment: "private-devnet"`
- missing records return stable `not_found` errors

### Wallet APIs

```text
GET  /api/v1/wallet/status
GET  /api/v1/wallet/accounts
GET  /api/v1/wallet/accounts/{address}/balance
GET  /api/v1/wallet/accounts/{address}/history
POST /api/v1/wallet/transfers/draft
POST /api/v1/wallet/transfers/submit
POST /api/v1/wallet/transfers/send
GET  /api/v1/wallet/transactions/{tx_hash}/status
```

Purpose:

- serve a private-devnet wallet UI
- wrap existing wallet CLI/node flows behind stable service contracts
- keep test identity and private-devnet warnings visible

Required behavior:

- no private key or seed phrase material in responses
- all transfer responses include `warning`
- all submitted transfers include `tx_hash`
- `draft` does not mutate chain or pending state
- `submit` creates pending state
- `send` is allowed only for private-devnet test identities

### Admin APIs

```text
GET  /api/v1/admin/node/status
GET  /api/v1/admin/indexer/status
POST /api/v1/admin/indexer/replay
GET  /api/v1/admin/audit-events
POST /api/v1/admin/snapshots/export
POST /api/v1/admin/snapshots/import
```

Purpose:

- serve local admin portal
- control local/private indexer replay
- expose snapshot operations for development only
- record audit events for operator actions

Required behavior:

- mutating admin endpoints are disabled by default in production-like configs
- every mutating endpoint writes an audit event
- snapshot import must refuse unsafe overwrite by default

### ISO 20022 Mapping APIs

```text
POST /api/v1/iso20022/payment-initiation/preview
GET  /api/v1/iso20022/transactions/{tx_hash}/status
GET  /api/v1/iso20022/accounts/{address}/statement?from=<ts>&to=<ts>
```

Purpose:

- preview ISO 20022-aligned shapes from XRIQ private-devnet data
- test mappings before any real financial integration
- support future payment/status/reporting adapters

Required behavior:

- map only fields XRIQ actually has
- mark unsupported fields explicitly
- include `not_certified: true`
- include `environment: "private-devnet"`
- do not claim SWIFT, bank, legal, compliance, or payment-network approval

### Future Decentralized Exchange APIs

The exchange UI is intended to become a decentralized exchange UI later, but
real DEX behavior is deferred. Phase 1.1 may document placeholder contracts,
but must not implement live trading, liquidity pools, custody, bridges, or
market-facing claims.

Deferred future groups:

```text
GET  /api/v1/dex/pairs
GET  /api/v1/dex/pools
POST /api/v1/dex/swaps/quote
POST /api/v1/dex/swaps/submit
POST /api/v1/dex/liquidity/add
POST /api/v1/dex/liquidity/remove
```

Do not implement these until token/XRC assets, smart contracts or native DEX
modules, legal-risk review, and security review exist.

## PostgreSQL Read Model

PostgreSQL stores indexed private-devnet data. It is not consensus state.

### Core Tables

```text
xriq_blocks
xriq_transactions
xriq_accounts
xriq_account_balances
xriq_account_transactions
xriq_mempool_entries
xriq_snapshots
xriq_indexer_runs
xriq_audit_events
xriq_iso20022_messages
```

### xriq_blocks

Required columns:

- `height bigint primary key`
- `block_hash text unique not null`
- `previous_block_hash text not null`
- `state_root text not null`
- `transactions_root text not null`
- `transaction_count integer not null`
- `timestamp_utc timestamptz null`
- `indexed_at timestamptz not null default now()`

### xriq_transactions

Required columns:

- `tx_hash text primary key`
- `block_height bigint null`
- `block_hash text null`
- `transaction_index integer null`
- `status text not null`
- `from_address text not null`
- `to_address text not null`
- `amount_base_units numeric(78,0) not null`
- `fee_base_units numeric(78,0) not null`
- `nonce bigint not null`
- `created_at timestamptz null`
- `indexed_at timestamptz not null default now()`

### xriq_accounts

Required columns:

- `address text primary key`
- `first_seen_height bigint null`
- `last_seen_height bigint null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

### xriq_account_balances

Required columns:

- `address text primary key`
- `balance_base_units numeric(78,0) not null`
- `nonce bigint not null`
- `height bigint not null`
- `state_root text not null`
- `updated_at timestamptz not null default now()`

### xriq_account_transactions

Required columns:

- `address text not null`
- `tx_hash text not null`
- `direction text not null`
- `block_height bigint null`
- `transaction_index integer null`
- `amount_base_units numeric(78,0) not null`
- `fee_base_units numeric(78,0) not null`
- `indexed_at timestamptz not null default now()`

Primary key:

- `(address, tx_hash, direction)`

### xriq_mempool_entries

Required columns:

- `tx_hash text primary key`
- `from_address text not null`
- `to_address text not null`
- `amount_base_units numeric(78,0) not null`
- `fee_base_units numeric(78,0) not null`
- `nonce bigint not null`
- `status text not null`
- `first_seen_at timestamptz not null default now()`
- `last_seen_at timestamptz not null default now()`

### xriq_snapshots

Required columns:

- `snapshot_name text primary key`
- `snapshot_dir text not null`
- `chain_id text not null`
- `current_height bigint not null`
- `latest_block_hash text not null`
- `state_root text not null`
- `pending_transactions integer not null`
- `created_at timestamptz null`
- `indexed_at timestamptz not null default now()`

### xriq_indexer_runs

Required columns:

- `run_id text primary key`
- `started_at timestamptz not null`
- `completed_at timestamptz null`
- `status text not null`
- `from_height bigint null`
- `to_height bigint null`
- `blocks_indexed integer not null default 0`
- `transactions_indexed integer not null default 0`
- `error text null`

### xriq_audit_events

Required columns:

- `event_id text primary key`
- `occurred_at timestamptz not null default now()`
- `actor text not null`
- `action text not null`
- `resource_type text not null`
- `resource_id text null`
- `environment text not null`
- `metadata_json text null`

### xriq_iso20022_messages

Required columns:

- `message_id text primary key`
- `tx_hash text null`
- `account_address text null`
- `message_type text not null`
- `mapping_version text not null`
- `environment text not null`
- `not_certified boolean not null default true`
- `payload_json text not null`
- `created_at timestamptz not null default now()`

## Fixture Requirements

Milestone A should add stable fixture examples for:

- explorer overview
- block list/detail
- transaction detail
- account detail/history
- wallet transfer draft/submit/send/status
- admin indexer status
- ISO 20022 payment initiation preview
- ISO 20022 transaction status
- ISO 20022 account statement

Fixtures should live under a deterministic path such as:

```text
xriq/fixtures/phase1_1/
```

## Next Implementation Step

Continue Milestone B by wiring the deterministic indexer scaffold to a
PostgreSQL-backed persistence adapter:

1. Keep `xriq-indexer` as the pure, deterministic read-model layer.
2. Keep using the local replay command to validate file-backed chain replay and
   read-model counts before database work.
3. Add PostgreSQL integration only after replay behavior stays idempotent in
   local tests.

## Concrete Artifacts

The first local contract artifacts now exist:

```text
xriq/db/schema.sql
xriq/fixtures/phase1_1/
xriq/crates/xriq-indexer/
scripts/xriq_phase1_1_contract_check.py
```

Run the local contract check from the repo root:

```bash
python scripts/xriq_phase1_1_contract_check.py
```

The check validates that the PostgreSQL read-model schema contains the required
10 tables and that the 14 Phase 1.1 JSON fixtures parse, declare
`environment: "private-devnet"`, avoid sensitive key/seed fields, and keep
money-like values as integer base-unit strings.

Run the focused Rust indexer scaffold tests from `xriq/`:

```bash
cargo test -p xriq-indexer
```

Run the local replay command from `xriq/` against an existing private-devnet
chain file:

```bash
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format json
```

The indexer scaffold currently builds a PostgreSQL-facing in-memory read model
for blocks, confirmed transactions, accounts, balances, account transaction
history, and audit events. It detects conflicting replay at the same block
height, validates canonical private-devnet block replay for the command path,
and keeps repeat replay idempotent.
