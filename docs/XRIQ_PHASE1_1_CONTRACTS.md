# XRIQ Phase 1.1 Contracts

Status: Milestone A contract baseline for the local/private end-to-end XRIQ
prototype.

This document defines the first product-facing API and database contracts for
Phase 1.1. It does not change the Phase 1 RC1 tag, create a production API,
launch a public network, approve custody, or enable trading.

Current implementation scaffold: `xriq/crates/xriq-api` defines the first
read-only Rust service boundary and `/api/v1/...` route/render behavior for
these contracts over the indexed private-devnet read model. It also includes a
local read-only `serve-readonly` socket wrapper and `request` smoke command for
Phase 1.1 private-devnet development.
The `xriq/crates/xriq-iso20022` crate defines the first ISO 20022-aligned
preview mappings for payment initiation, payment status, and account statement
responses. These mappings remain private-devnet-only and explicitly not
certified. `xriq-api` now exposes the first GET-only ISO preview routes by
calling that adapter from the product API boundary.

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
GET  /api/v1/wallet/transfers/draft-preview?from_address=<address>&to_address=<address>&amount_base_units=<n>&fee_base_units=<n>&nonce=<n>&expires_at_height=<height>
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
- `draft-preview` is an early read-only scaffold; it validates transfer fields
  and reports balance/debit/remaining math with `mutation: "none"`
- `draft` does not mutate chain or pending state
- `submit` creates pending state
- `send` is allowed only for private-devnet test identities

### Phase 1.2 Wallet Mutation Preflight

Phase 1.2 adds preflight contracts before any successful product API mutation
is enabled. These fixtures and API responses only enable disabled/refused
behavior; they do not enable wallet submission in `xriq-api` or the React UI.

Default product behavior for mutating wallet endpoints must be:

```text
POST /api/v1/wallet/transfers/submit -> disabled/refused
POST /api/v1/wallet/transfers/send   -> disabled/refused
```

Required disabled response behavior:

- HTTP `403 Forbidden`
- `environment: "private-devnet"`
- `network: "xriq-devnet"`
- `endpoint`
- `enabled: false`
- `mutation: "none"`
- `status: "disabled"`
- stable refusal `code`
- `warning: "local-private-devnet-preflight-only"`
- explicit `required_enablement.mode: "local-private-devnet"`
- explicit local-only flag name before any future mutation is accepted
- `audit_event_required: true`
- `test_identity_only: true`
- request field names only, not signing material
- refusal guards that state default mutation refusal and no custody/signing
- no signing material, custody material, or seed material in the request or
  response

The Phase 1.2 preflight fixtures are:

```text
xriq/fixtures/phase1_2/wallet-transfer-submit-disabled.json
xriq/fixtures/phase1_2/wallet-transfer-send-disabled.json
xriq/fixtures/phase1_2/wallet-transfer-submit-audit-expectation.json
xriq/fixtures/phase1_2/wallet-transfer-send-audit-expectation.json
```

The first implementation after these fixtures should test refusal behavior
before adding any successful submit/send path. The first API implementation now
returns stable `403` refusal bodies for submit/send and is covered by
`scripts/xriq_phase1_1_local_e2e_smoke.py`; successful submit/send remains out
of scope.

The first UI/client implementation consumes those refusal contracts only. The
React wallet shell must keep submit/send controls disabled, offer only an
explicit guard-check action, accept only `403` disabled responses for submit/send
checks, and validate the returned disabled contract before showing a ready guard
state. It must not include direct submit/send endpoint strings in the wallet UI
component, raw wallet-local `fetch(` calls, signing material, seed material, or
successful mutation controls.

The audit expectation fixtures define the future audit event contract before
any accepted mutation exists. Future submit/send attempts must use
`local-private-devnet-operator` as the local actor, wallet-transfer attempt
actions, `wallet_transfer` as the resource type, refused-by-default behavior,
explicit local flags for accepted attempts, and required audit metadata such as
endpoint, outcome, status, refusal code, local request id, addresses, amount,
fee, nonce, and expiry. Audit metadata must forbid private keys, seed phrases,
mnemonics, signatures, signed transactions, and transaction hashes before
accepted mutation. The fixtures are expectations only; they do not write audit
events yet.

### Admin APIs

```text
GET  /api/v1/admin/node/status
GET  /api/v1/admin/indexer/status
GET  /api/v1/admin/postgres/read-model-status
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
- Postgres read-model routes are local/private-devnet read-only and must not
  print database passwords, mutate schema, or replace default file-backed API
  paths unless explicitly configured
- `xriq-api serve-readonly` exposes Postgres read-model routes only when both
  `--postgres-docker-container` and `--postgres-database` are passed; without
  those flags the Postgres status route remains disabled and ordinary
  file-backed API routes, including `/api/v1/explorer/overview`,
  `/api/v1/blocks?limit=...`, `/api/v1/blocks/{height-or-hash}`,
  `/api/v1/transactions?limit=...`, and
  `/api/v1/mempool?limit=...`, and `/api/v1/wallet/status`, and
  `/api/v1/wallet/transfers/draft-preview?...`, and
  `/api/v1/iso20022/transactions/{tx_hash}/status`, and
  `/api/v1/iso20022/payment-initiation/preview?tx_hash=...`, and
  `/api/v1/iso20022/accounts/{address}/statement?from=...&to=...`, and
  `/api/v1/transactions/{tx_hash}`, `/api/v1/accounts?limit=...`, and
  `/api/v1/accounts/{address}`, and
  `/api/v1/accounts/{address}/transactions?limit=...`, and
  `/api/v1/snapshots`, and `/api/v1/snapshots/{snapshot_name}`, keep working

### ISO 20022 Mapping APIs

```text
GET  /api/v1/iso20022/payment-initiation/preview?tx_hash=<tx_hash>
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
- keep the current implementation GET-only/read-only until explicit mutating
  payment-initiation preview bodies are needed

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

Continue Milestone B/C by gradually moving read-only product routes onto the
opt-in PostgreSQL read model after the deterministic indexer scaffold has been
validated against the local Docker Postgres service:

1. Keep `xriq-indexer` as the pure, deterministic read-model layer.
2. Keep using the local replay command to validate file-backed chain replay and
   read-model counts before database work.
3. Use `--format sql` to inspect the idempotent SQL write plan before applying
   it to a local database.
4. Use `apply-postgres --dry-run true` as the default safety check.
5. Use `apply-postgres --dry-run false` only with a local database URL and
   installed `psql`.
6. Keep `/api/v1/explorer/overview`, `/api/v1/blocks?limit=...`,
   `/api/v1/blocks/{height-or-hash}`,
   `/api/v1/transactions?limit=...`, `/api/v1/mempool?limit=...`,
   `/api/v1/wallet/status`,
   `/api/v1/wallet/transfers/draft-preview?...`,
   `/api/v1/transactions/{tx_hash}`, and
   `/api/v1/wallet/transactions/{tx_hash}/status`, and
   `/api/v1/iso20022/transactions/{tx_hash}/status`, and
   `/api/v1/iso20022/payment-initiation/preview?tx_hash=...`, and
   `/api/v1/iso20022/accounts/{address}/statement?from=...&to=...`, and
   `/api/v1/accounts?limit=...` plus `/api/v1/accounts/{address}`,
   `/api/v1/accounts/{address}/transactions?limit=...`, and
   `/api/v1/wallet/accounts?limit=...` plus
   `/api/v1/wallet/accounts/{address}/balance` and
   `/api/v1/wallet/accounts/{address}/history?limit=...` as the first
   Postgres-backed product data routes. The wallet transaction-status route now
   covers confirmed rows and pending `xriq_mempool_entries` rows in Postgres
   mode without enabling mutation. The wallet draft-preview route now validates
   from Postgres account-balance/nonce/current-height data while remaining
   read-only/no-signing/no-submit. The ISO 20022 transaction-status route now
   maps confirmed and pending read-model transaction status into
   `not_certified: true` preview JSON without certification or payment-network
   claims. The ISO 20022 payment-initiation route now maps confirmed
   read-model transaction fields into `not_certified: true` preview JSON
   without certification or payment-network claims. The ISO 20022 account
   statement route now maps read-model account history and balance fields into
   `not_certified: true` preview JSON without certification or payment-network
   claims. Before starting mutating wallet submit, block-production, snapshot
   import/export, DEX, or smart-contract work, use the Phase 1.1 RC readiness
   checklist and route-parity matrix in `docs/XRIQ_PHASE1_1_RC_READINESS.md`.
   Also review the RC candidate report in
   `docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md` before any Phase 1.1 RC tag
   decision.
   The cheap guardrail is
   `python scripts/xriq_phase1_1_rc_readiness.py --latest-summary`.
7. If host `psql` is unavailable but Docker Desktop is running, use
   `python scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live` to
   apply and verify the generated SQL inside the local Compose Postgres
   container against the dedicated `xriq_phase1_1_smoke` database.

## Concrete Artifacts

The first local contract artifacts now exist:

```text
xriq/db/schema.sql
xriq/fixtures/phase1_1/
xriq/fixtures/phase1_2/
xriq/crates/xriq-indexer/
scripts/xriq_phase1_1_contract_check.py
```

Run the local contract check from the repo root:

```bash
python scripts/xriq_phase1_1_contract_check.py
```

The check validates that the PostgreSQL read-model schema contains the required
10 tables, that the 14 Phase 1.1 JSON fixtures parse, declare
`environment: "private-devnet"`, avoid sensitive key/seed fields, and keep
money-like values as integer base-unit strings, and that the Phase 1.2 wallet
mutation preflight fixtures remain disabled with `mutation: "none"`, explicit
local enablement flags, audit requirements, test-identity-only boundaries, and
audit expectation fixtures that require local actor/action/resource metadata
while forbidding secret/signing/transaction-hash metadata.

Run the Phase 1.2 refusal smoke from the repo root:

```bash
python scripts/xriq_phase1_2_refusal_smoke.py
```

The refusal smoke writes a summary under
`xriq/target/xriq-phase1-2-refusal-smoke-*` and does not enable wallet
submission, sending, block production, pending-state mutation, signing, or
custody behavior. It validates both disabled response fixtures and the
audit-event expectation fixtures.

Run the local API refusal smoke from the repo root with a custom Phase 1.2
artifact directory:

```bash
python scripts/xriq_phase1_1_local_e2e_smoke.py --artifact-dir xriq/target/xriq-phase1-2-api-refusal-smoke-<timestamp>
```

This verifies `POST /api/v1/wallet/transfers/submit` and
`POST /api/v1/wallet/transfers/send` return disabled `403` responses and still
does not enable wallet submission, sending, block production, pending-state
mutation, signing, or custody behavior.

Run the React/static wallet guardrail from `xriq/apps/explorer-ui`:

```bash
npm run check
npm run build
```

The static check requires the Wallet Action Guards UI markers and the client
refusal-response helper while continuing to reject direct submit/send endpoint
strings, wallet-local raw fetches, and sensitive key/seed fields in the wallet
component.

Run the focused Rust indexer scaffold tests from `xriq/`:

```bash
cargo test -p xriq-indexer
```

The first explicit Postgres-backed API read paths are local-only and use the
Compose `postgres` container. They return status/count JSON plus the opt-in
explorer overview, block-list, block-detail, transaction-list, mempool, wallet-status, wallet draft-preview, transaction-detail, ISO 20022 transaction-status,
confirmed/pending wallet transaction-status, mempool, account-list, wallet account-list, account-detail, wallet
balance, account-history, wallet account-history, audit-events, snapshot-list,
snapshot-detail, indexer-status, and node-status shapes from the read model
without changing the default
file-backed API request/server path:

```bash
cargo run -p xriq-api -- request-postgres --target /api/v1/admin/postgres/read-model-status
cargo run -p xriq-api -- request-postgres --target /api/v1/admin/node/status
cargo run -p xriq-api -- request-postgres --target /api/v1/admin/indexer/status
cargo run -p xriq-api -- request-postgres --target /api/v1/admin/audit-events?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/explorer/overview
cargo run -p xriq-api -- request-postgres --target /api/v1/blocks?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/blocks/1
cargo run -p xriq-api -- request-postgres --target /api/v1/transactions?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/mempool?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/status
cargo run -p xriq-api -- request-postgres --target '/api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000&to_address=xriqdev1carol00000000000&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100'
cargo run -p xriq-api -- request-postgres --target /api/v1/transactions/<tx_hash>
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/transactions/<tx_hash>/status
cargo run -p xriq-api -- request-postgres --target /api/v1/iso20022/transactions/<tx_hash>/status
cargo run -p xriq-api -- request-postgres --target '/api/v1/iso20022/payment-initiation/preview?tx_hash=<tx_hash>'
cargo run -p xriq-api -- request-postgres --target '/api/v1/iso20022/accounts/<address>/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z'
cargo run -p xriq-api -- request-postgres --target /api/v1/accounts?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/accounts?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/accounts/<address>
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/accounts/<address>/balance
cargo run -p xriq-api -- request-postgres --target /api/v1/accounts/<address>/transactions?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/accounts/<address>/history?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/snapshots?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/snapshots/current-indexed-chain
```

The same routes can be exposed by the local read-only HTTP server only when the
Postgres source is explicitly configured:

```bash
cargo run -p xriq-api -- serve-readonly --chain-file target/xriq-indexer-replay-smoke.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --postgres-docker-container xriq-postgres --postgres-database xriq_phase1_1_smoke
```

Run the local replay command from `xriq/` against an existing private-devnet
chain file:

```bash
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format json
```

To emit the local PostgreSQL write plan without requiring a running database:

```bash
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format sql
```

To validate the local apply path without requiring a running database or `psql`:

```bash
cargo run -p xriq-indexer -- apply-postgres --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --schema-file db/schema.sql --dry-run true
```

To opt into Docker-backed local live SQL validation without requiring host
`psql`:

```bash
python scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live
```

That live smoke resets only the dedicated local smoke database, applies the
generated confirmed-chain read-model write plan, and imports the generated
durable `pending.tsv` row into `xriq_mempool_entries` so the opt-in Postgres
`/api/v1/mempool?limit=...` route can be validated without changing default
file-backed API behavior.

The indexer scaffold currently builds a PostgreSQL-facing in-memory read model
for blocks, confirmed transactions, accounts, balances, account transaction
history, audit events, and the current indexed-chain snapshot catalog row.
It detects conflicting replay at the same block
height, validates canonical private-devnet block replay for the command path,
keeps repeat replay idempotent, and renders `INSERT ... ON CONFLICT`
statements in foreign-key-safe order for the Phase 1.1 schema.
