# XRIQ Phase 1.1 End-To-End Plan

Status: post-RC1 planning scope for the local/private XRIQ end-to-end
prototype.

Phase 1.1 starts after the approved `phase1-xriq-private-devnet-rc1` tag. Its
goal is to turn the Rust private-devnet core into a local end-to-end product
prototype without making public-mainnet, exchange-listing, custody, legal,
banking, or investment claims.

## Phase 1.1 Goal

Build a local end-to-end XRIQ prototype with:

- Rust node/backend APIs as the source of truth
- React + TypeScript user interfaces for private-devnet operation
- PostgreSQL indexing for explorer, analytics, and audit views
- ISO 20022 compatibility adapter for future financial-system integration
  mapping
- optional Google Cloud deployment later, following
  `docs/XRIQ_GCP_RESOURCE_PLAN.md`

Phase 1.1 remains private/local. It should not launch a public cryptocurrency,
public DEX, token sale, custody product, or production payment rail.

## ISO 20022 Compatibility Scope

ISO 20022 is part of Phase 1.1 as an adapter and mapping layer, not as a claim
that XRIQ is bank-approved, legally compliant, or connected to regulated
payment networks.

Phase 1.1 should add:

- an `xriq-iso20022` Rust crate or module
- deterministic mappings from XRIQ private-devnet transfers to ISO
  20022-aligned payment initiation/status/reporting shapes
- JSON fixtures for the supported mapping subset
- tests that prove XRIQ transaction IDs, account identifiers, amounts, fees,
  confirmations, failures, and timestamps map consistently
- explicit unsupported-field handling instead of silently inventing banking
  data XRIQ does not have

Recommended first subset:

- payment/credit-transfer style mapping for a submitted XRIQ transfer
- payment-status style mapping for pending, confirmed, and rejected transfers
- account/statement/reporting style mapping for explorer-indexed account
  activity

Out of scope for Phase 1.1:

- real bank connectivity
- SWIFT connectivity
- legal compliance certification
- production payment processing
- custody or fiat settlement
- pretending XRIQ is an ISO 20022-certified network

## Architecture Status

Current status after Phase 1 RC1:

```text
Rust
 |-- Blockchain node        ~70% for private-devnet; RC1 baseline exists
 |-- Consensus engine       ~60% for private-devnet; single-authority baseline
 |-- Wallet backend         ~51%; CLI flows plus product read/preview/pending-status routes exist
 |-- APIs                   ~58%; local HTTP wrappers plus wallet/admin/node/pending-file mempool/pending-status/ISO preview read routes and explicit Postgres read-model status CLI/server paths exist
 `-- Smart contracts        0%; defer VM until core/app flow is stable

React + TypeScript
 |-- Wallet UI              ~24%; preview shell plus read-only confirmed/pending activity, API status, and API history detail
 |-- Explorer               ~27%; shell plus detail, pending transaction, snapshot, ISO preview, and optional Postgres status panels read product API
 |-- Exchange UI            0%; deferred high legal/compliance-risk surface
 `-- Admin portal           ~28%; read-only node/status, pending mempool, pending wallet status, optional Postgres read-model status, snapshot catalog, and audit events panels exist

SQL/PostgreSQL
 |-- Explorer indexing      ~33%; schema, indexer, SQL plan, verify path, Docker live smoke, and first Postgres-backed API/server status read exist
 |-- Analytics              ~5%; read-model totals exist, deeper analytics deferred
 `-- Audit data             ~20%; schema, indexed block audit events, read API, and UI panel exist

ISO 20022
 `-- Compatibility adapter  ~27%; preview crate, product API read routes, and UI panel exist
```

Initial post-RC1 Phase 1.1 baseline status was about `15%`. Most of that value
came from the completed Rust private-devnet foundation. At that point, the
actual end-to-end product surfaces, especially PostgreSQL indexing and React
UI, were still at the starting line.

After the first local Phase 1.1 Postgres-enabled Admin UI smoke checkpoint,
Phase 1.1 status is about `69%`: the contract document, PostgreSQL read-model schema, JSON
fixtures, local contract validation script, deterministic Rust read-model
indexer scaffold, local chain replay command, idempotent PostgreSQL SQL
write-plan export, dry-run database apply path, optional local Postgres
service, `verify-postgres` verification command, opt-in Docker-backed live
smoke application through container-local `psql`, explicit `xriq-api`
Postgres read-model status command for
`/api/v1/admin/postgres/read-model-status`, explicitly configured
`xriq-api serve-readonly` support for the same local Postgres read-model status
route, `xriq-api` read-only product response boundary with `/api/v1/...`
route/render behavior, a local `serve-readonly` socket wrapper, a `request` CLI
smoke path, and
`xriq-iso20022` preview mapping crate exist. The local Phase 1.1 smoke now also
builds `xriq-indexer`, validates indexer replay JSON, writes the SQL write-plan
artifact, validates apply/verify PostgreSQL dry-runs without requiring a
live database, and can optionally apply/verify against a dedicated local Docker
Postgres smoke database when `--postgres-docker-live` is explicitly passed.
`xriq-api` now calls the ISO
adapter through private-devnet GET-only payment-initiation, payment-status,
and account-statement preview routes. `xriq-api` now includes
private-devnet wallet status, account list, balance, history, transaction
status, pending-file transaction status with null block fields, and
non-mutating transfer draft-preview routes. The first React + TypeScript
explorer shell in `xriq/apps/explorer-ui` can render health, network totals,
blocks, confirmed transactions, pending transactions, snapshot catalog,
audit events, accounts, block detail, transaction detail, selected pending
wallet transaction status, selected snapshot detail, selected audit-event
detail, account detail, and account transaction history from the local product
API. The same
app now includes a preview-only wallet panel that selects local indexed
accounts, shows balance/debit/remaining math, and renders a deterministic
draft JSON preview without signing, submission, key handling, or persistence.
That wallet panel can now call the product wallet draft-preview API and render
the server validation/balance response, and now includes a read-only Wallet
Activity panel that combines confirmed product transaction rows with durable
pending mempool rows for the selected account and shows selected status,
direction, counterparty, amount, fee, nonce, pending-block, and transaction-index
detail. The selected wallet activity row now calls the product wallet
transaction-status API and renders API-backed status, block height/hash,
transaction index, and preview warning without enabling submit/send behavior.
The wallet shell now also calls the product wallet account-history route for
the selected local account and renders a read-only Wallet API History table.
The same React app now includes a
read-only ISO 20022 Preview panel that calls the product ISO preview routes
for the selected transaction/account and renders payment initiation, payment
status, account statement, mapping-version, not-certified, and unsupported
field markers. The same React app now includes a
read-only Admin Status panel that summarizes network tip state, indexer
current/last-run status, node health/read-only mode, wallet draft/submit/send
capability flags, read-only durable pending-file mempool status, the first
pending wallet transaction status with null block/index fields, a read-only
optional Postgres read-model status block that tolerates disabled `404`
responses, snapshot catalog, and indexed audit events from the product API. The optional
Docker-backed live database smoke has passed once on this workstation against a
dedicated `xriq_phase1_1_smoke` database. Real wallet submission APIs, mutating
admin controls, block-production controls, real snapshot export/import
controls, deeper ISO adapter integration, and repeated live database smoke in
CI or a longer-running dev loop are still pending. The local
`scripts/xriq_phase1_1_local_e2e_smoke.py` command now checks the current
contract fixtures, React UI guardrails, indexer replay/SQL/apply/verify
dry-runs, 26 product API success routes, and three wallet draft-preview failure
routes across the explorer, wallet, mempool, snapshot, audit, admin, and ISO
preview surfaces without opening a socket or using cloud/GPU resources. Passing
`--postgres-docker-live` starts/uses the local Compose Postgres service, resets
a dedicated `xriq_phase1_1_smoke` database schema, applies the schema plus
generated write plan through container-local `psql`, verifies indexed counts,
calls `xriq-api request-postgres`, and writes
`indexer/postgres-docker-live.json` plus
`indexer/postgres-api-read-model-status.json`. The same live mode now starts a
temporary local `serve-readonly` server with explicit Postgres flags, verifies
`/api/v1/admin/postgres/read-model-status` over HTTP, and writes
`indexer/postgres-server-read-model-status.json`. It also runs
`npm.cmd run check:postgres-ui` against that temporary server to validate the
Admin UI's Postgres read-model rows for the live `available` state and writes
`indexer/postgres-admin-ui-read-model-status.json`.

## Phase 1.1 Build Order

1. Define API and database contracts before building UI.
2. Add PostgreSQL schema and indexer for blocks, transactions, accounts,
   balances, mempool snapshots, and audit events.
3. Add a Rust API service boundary for wallet/explorer/admin reads and safe
   private-devnet submissions.
4. Add ISO 20022 mapping crate with fixtures and tests.
5. Build React + TypeScript explorer UI against the indexed API.
6. Build React + TypeScript wallet UI for test identities and private-devnet
   transfers only.
7. Build admin portal for local node/indexer health, snapshots, and audit logs.
8. Defer exchange UI until legal-risk, custody, DEX, market-abuse, and listing
   guardrails are separately reviewed.
9. Defer smart-contract VM until the node, indexer, wallet UI, and explorer UI
   are stable.

Use local development for Milestones A and B by default. Do not provision paid
GCP resources until the local contracts and first indexer replay tests are
stable enough to justify deployment.

Milestone A contract details are tracked in
`docs/XRIQ_PHASE1_1_CONTRACTS.md`.

## Recommended Phase 1.1 Milestones

### Milestone A: Contracts

- Document REST/JSON API shapes for wallet, explorer, indexer, admin, and ISO
  20022 mapping.
- Add checked fixtures for stable response examples.
- Keep all endpoints private-devnet/local.
- Treat exchange UI as future decentralized exchange UI, but defer real DEX
  trading/liquidity contracts until token, smart-contract/native-module,
  legal-risk, and security review gates exist.
- Current artifacts: `docs/XRIQ_PHASE1_1_CONTRACTS.md`,
  `xriq/db/schema.sql`, `xriq/fixtures/phase1_1/`, and
  `scripts/xriq_phase1_1_contract_check.py`.

### Milestone B: PostgreSQL Indexer

- Add XRIQ PostgreSQL schema.
- Add a local indexer command or service that reads the file-backed chain and
  writes indexed blocks, transactions, accounts, balances, and audit events.
- Add idempotent replay tests.
- Current scaffold: `xriq/crates/xriq-indexer` builds the PostgreSQL-facing
  in-memory read model from existing chain/ledger state, tests idempotent
  replay before wiring a database connection, exposes a local replay command,
  can emit an idempotent SQL write plan, and can dry-run the local apply and
  verify paths. The Phase 1.1 local e2e smoke now runs these dry-run checks on
  the chain generated by the smoke and has an explicit Docker live-smoke mode
  for a dedicated local Postgres smoke database:

```bash
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format json
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format sql
cargo run -p xriq-indexer -- apply-postgres --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --schema-file db/schema.sql --dry-run true
cargo run -p xriq-indexer -- verify-postgres --dry-run true
python scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live
cargo run -p xriq-api -- request-postgres --target /api/v1/admin/postgres/read-model-status
```

The root `docker-compose.yml` now includes an optional local Postgres service
named `postgres`; use it with `XRIQ_POSTGRES_URL` and `--dry-run false` only
when intentionally applying the read model to a local development database.
The Docker live-smoke path uses the same service but isolates itself to
`xriq_phase1_1_smoke` and resets only that smoke database schema.

### Milestone C: Rust API Service Boundary

- Add product-facing response models over the indexed read model.
- Keep this as a Rust service/route boundary first, then expose a localhost
  read-only socket wrapper for private-devnet smoke testing.
- Cover health, version, network, explorer overview, blocks, transactions,
  accounts, account history, and admin indexer status.
- Current scaffold: `xriq/crates/xriq-api` exposes read-only private-devnet
  response models, `/api/v1/...` route/render behavior over
  `IndexedChainSnapshot`, wallet status/account/balance/history/transaction
  status/draft-preview routes, a read-only `/api/v1/mempool` status route that
  can inspect an optional durable pending TSV through `--pending-file`,
  pending-file-aware wallet transaction status for
  `/api/v1/wallet/transactions/{hash}/status`,
  read-only admin node-status, audit events, snapshot catalog routes, GET-only
  ISO 20022 preview routes, and an explicit local Docker Postgres read-model
  status request path for `/api/v1/admin/postgres/read-model-status`, a
  `request` CLI smoke path, and a local `serve-readonly` socket wrapper. The
  pending-file path does not enable product API submit or block production.
  Focused verification is:

```bash
cargo test -p xriq-api
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/health
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/wallet/status
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/admin/node/status
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/mempool
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --target /api/v1/mempool?limit=5
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/admin/audit-events
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/snapshots
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target '/api/v1/iso20022/payment-initiation/preview?tx_hash=<confirmed-tx-hash>'
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target '/api/v1/iso20022/transactions/<confirmed-tx-hash>/status'
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target '/api/v1/iso20022/accounts/xriqdev1alice00000000000/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z'
```

### Milestone D: ISO 20022 Adapter

- Add `xriq-iso20022`.
- Add mapping structs, fixtures, and tests.
- Map only data XRIQ actually has.
- Current scaffold: `xriq/crates/xriq-iso20022` maps private-devnet
  transaction/account-history response models into payment initiation preview,
  payment status preview, and account statement preview shapes. It includes
  `not_certified: true` and explicit unsupported-field markers. The adapter is
  now dependency-direction friendly: `xriq-api` calls it for GET-only product
  routes without making ISO certification, bank, SWIFT, legal-compliance, or
  payment-network claims. Focused verification is:

```bash
cargo test -p xriq-iso20022
```

### Milestone E: Explorer UI

- Add a React + TypeScript explorer showing chain status, blocks,
  transactions, accounts, mempool, and snapshots from indexed data.
- Current scaffold: `xriq/apps/explorer-ui` is a Vite React + TypeScript
  local explorer shell. It reads `xriq-api` through a same-origin `/api` proxy
  and currently shows private-devnet health, height/totals, network metadata,
  latest blocks, latest confirmed transactions, read-only pending transactions
  from `/api/v1/mempool`, accounts, plus selected block, transaction, pending
  wallet status, snapshot catalog/detail, audit-event list/detail, account
  detail panels, and a read-only ISO 20022 preview panel for the selected
  transaction/account.

```bash
cd xriq/apps/explorer-ui
npm.cmd run check
npm.cmd run build
```

From the repo root, the current Phase 1.1 local product surface can be checked
with one CPU-only smoke. It creates a tiny confirmed transfer and one durable
pending transfer, then verifies the API routes that feed the explorer, wallet,
mempool, snapshot, audit, admin, and ISO preview panels, including wallet
draft-preview validation failures. By default, PostgreSQL remains dry-run-only:

```bash
python scripts/xriq_phase1_1_local_e2e_smoke.py
```

When Docker Desktop is running and live local SQL validation is intentionally
wanted, add:

```bash
python scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live
```

### Milestone F: Wallet UI

- Add a React + TypeScript private-devnet wallet UI for test identities,
  balance, transfer draft/submit/send, status, and history.
- Keep all copy visibly private-devnet/test-only.
- Current scaffold: `xriq/apps/explorer-ui` includes a preview-only wallet
  panel that uses indexed account data and renders
  `xriq-wallet-transfer-preview-v1` JSON. It can call the product
  `/api/v1/wallet/transfers/draft-preview` route for server-side validation,
  and it intentionally does not sign, submit, persist, or manage private keys.

### Milestone G: Admin Portal

- Add local admin views for node health, indexer status, snapshot export/import
  status, and audit events.
- Current scaffold: `xriq/apps/explorer-ui` includes a read-only Admin Status
  panel backed by `/api/v1/network`, `/api/v1/admin/indexer/status`, and
  `/api/v1/wallet/status`, plus a read-only node status section backed by
  `/api/v1/admin/node/status`, read-only snapshot catalog and audit-event
  sections backed by `/api/v1/snapshots` and `/api/v1/admin/audit-events`, and
  a read-only mempool status section backed by `/api/v1/mempool`. When the API
  is started with `--pending-file`, the panel shows the first pending
  transaction hash, amount, pending status, and the product wallet transaction
  status response for that pending hash. The separate Snapshot Catalog panel
  fetches `/api/v1/snapshots/{name}` for selected snapshot details and displays
  export/import statuses as disabled. The separate Audit Events panel displays
  indexed audit rows from `/api/v1/admin/audit-events` and selected event
  detail. It displays local private-devnet status only and has no mutating
  controls.

## Guardrails

- Do not add public trading, liquidity, custody, bridges, fiat ramps, or token
  sale behavior in Phase 1.1.
- Do not call the Exchange UI production-ready. Treat it as deferred until legal
  and compliance review.
- Do not implement smart contracts before the basic end-to-end wallet,
  explorer, indexer, and API flows are stable.
- Keep `docs/XRIQ_LEGAL_RISK_REDUCTION.md` as a hard guardrail.
- Keep `docs/XRIQ_GCP_RESOURCE_PLAN.md` as the cloud resource guardrail.
- Keep the RC1 tag fixed; Phase 1.1 work happens after RC1 on `main` or a
  future feature branch.
