# XRIQ Private Devnet Prototype

This subtree contains the Rust prototype for XRIQ. It is private-devnet code
only until security and legal/compliance review says otherwise.

## Current Scope

- `xriq-core`: dependency-free protocol types and validation helpers.
- `xriq-consensus`: deterministic private-devnet block production.
- `xriq-crypto`: canonical hashing and test-only signature verification boundary.
- `xriq-api`: product-facing private-devnet API response models, read-only
  `/api/v1/...` route/render behavior for indexed explorer/admin data, and a
  local read-only socket server for Phase 1.1 smoke testing.
- `xriq-explorer`: read-only private-devnet explorer view models and text UI.
- `xriq-indexer`: deterministic Phase 1.1 read-model indexing scaffold for the
  future PostgreSQL-backed explorer/admin/API surfaces.
- `xriq-iso20022`: private-devnet ISO 20022-aligned preview mappings with
  explicit non-certification and unsupported-field markers.
- `xriq-ledger`: deterministic private-devnet account state transitions.
- `xriq-mempool`: deterministic pending-transaction checks and ordering.
- `xriq-node`: minimal local private-devnet node loop with deterministic replay
  startup from persisted canonical blocks plus a startup consistency guard, a
  private-devnet status runner, a
  local transfer-to-block runner, wallet draft-file block production, and a
  file-backed explorer overview with state-root marker plus
  block/account/mempool detail runners with optional stable JSON output and a
  read-only local HTTP wrapper.
- `xriq-rpc`: local private-devnet RPC endpoint behavior.
- `xriq-storage`: local block storage for private-devnet tests.
- `xriq-wallet`: private-devnet wallet CLI for test identities, local account
  status, local account list, balance lookup, account history lookup,
  transaction status lookup, chain verification, pending inspection/submission,
  direct pending sends, and transfers.

## Commands

```bash
cd xriq
cargo fmt --check
cargo test
cargo clippy -- -D warnings
```

From the repo root, the full CPU-only Phase 1 local check runs the Rust
format/test/clippy set plus the isolated transfer and HTTP smokes, then verifies
the critical generated snapshot/restore/check artifacts:

```bash
python scripts/xriq_phase1_local_check.py
```

The Phase 1 release-candidate checklist is documented at
`../docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md`.
The current RC decision report is documented at
`../docs/XRIQ_PHASE1_RC_REPORT.md`.
The post-RC end-to-end Phase 1.1 plan is documented at
`../docs/XRIQ_PHASE1_1_END_TO_END_PLAN.md`.
The post-Phase 1.1 RC1 local/private Phase 1.2 plan is documented at
`../docs/XRIQ_PHASE1_2_LOCAL_PRIVATE_PLAN.md`.
The first Phase 1.2 wallet mutation preflight fixtures live in
`fixtures/phase1_2/`; they are disabled/refusal contracts only and do not enable
wallet submit/send behavior.
The first Phase 1.1 indexer scaffold can be checked with:

```bash
cargo test -p xriq-indexer
```

The first Phase 1.1 API service-boundary scaffold can be checked with:

```bash
cargo test -p xriq-api
```

After producing a local private-devnet chain file, the product API route layer
can be smoke-tested without opening a socket:

```bash
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/health
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --target '/api/v1/mempool?limit=5'
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target '/api/v1/iso20022/transactions/<confirmed-tx-hash>/status'
```

From the repo root, the current Phase 1.1 local product surface can be checked
with one CPU-only end-to-end smoke. It runs the contract and UI static
guardrails, builds the local Rust binaries, creates a confirmed transfer plus
one durable pending transfer, validates indexer replay plus PostgreSQL
apply/verify dry-runs, and verifies the product API routes used by the explorer,
wallet, mempool, snapshot, audit, admin, and ISO preview panels, including
wallet draft-preview validation failures. By default, PostgreSQL remains
dry-run-only:

```bash
python scripts/xriq_phase1_1_local_e2e_smoke.py
```

When Docker Desktop is running and live local SQL validation is intentionally
wanted, the same smoke can start/use the root Compose `postgres` service,
reset only a dedicated `xriq_phase1_1_smoke` database schema, apply the schema
and generated write plan through container-local `psql`, import the generated
durable pending TSV row into `xriq_mempool_entries`, verify indexed counts,
and write `indexer/postgres-docker-live.json` under the smoke artifact
directory:

```bash
python scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live
```

The Phase 1.1 RC readiness checklist and route-parity matrix live in
`../docs/XRIQ_PHASE1_1_RC_READINESS.md`. After a Docker live smoke, run the
cheap guardrail from the repo root:

```bash
python scripts/xriq_phase1_1_rc_readiness.py --latest-summary
```

The Phase 1.1 RC candidate report is in
`../docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md`. The approved Phase 1.1 RC1 tag
`phase1-1-xriq-local-e2e-rc1` is pushed at commit `6a38a51a`; do not move,
delete, or recreate it without an explicit tag-maintenance request.

That live smoke also verifies the first explicit Postgres-backed API read paths,
including `/api/v1/admin/postgres/read-model-status` and the opt-in
Postgres-backed `/api/v1/admin/node/status`, `/api/v1/admin/indexer/status`,
`/api/v1/explorer/overview`, `/api/v1/blocks?limit=5`,
`/api/v1/blocks/1`, `/api/v1/transactions?limit=5`,
`/api/v1/mempool?limit=5`, and `/api/v1/wallet/status` plus
`/api/v1/wallet/transfers/draft-preview?...` plus
`/api/v1/transactions/{tx_hash}` and
`/api/v1/wallet/transactions/{tx_hash}/status` for confirmed and pending hashes, plus
`/api/v1/iso20022/transactions/{tx_hash}/status` plus
`/api/v1/iso20022/payment-initiation/preview?tx_hash=...` plus
`/api/v1/iso20022/accounts/{address}/statement?from=...&to=...` plus
`/api/v1/accounts?limit=5` plus `/api/v1/accounts/{address}` and
`/api/v1/accounts/{address}/transactions?limit=5` plus
`/api/v1/wallet/accounts?limit=5` plus
`/api/v1/wallet/accounts/{address}/balance` plus
`/api/v1/wallet/accounts/{address}/history?limit=5` plus
`/api/v1/admin/audit-events?limit=5` plus `/api/v1/snapshots?limit=5`
and `/api/v1/snapshots/current-indexed-chain`,
plus the Admin UI's
Postgres read-model row mapping. It writes
`indexer/postgres-api-explorer-overview.json`,
`indexer/postgres-server-explorer-overview.json`,
`indexer/postgres-api-blocks.json`, `indexer/postgres-server-blocks.json`,
`indexer/postgres-api-block-detail.json`,
`indexer/postgres-server-block-detail.json`,
`indexer/postgres-api-transactions.json`,
`indexer/postgres-server-transactions.json`,
`indexer/postgres-api-mempool.json`,
`indexer/postgres-server-mempool.json`,
`indexer/postgres-api-wallet-status.json`,
`indexer/postgres-server-wallet-status.json`,
`indexer/postgres-api-wallet-draft-preview.json`,
`indexer/postgres-server-wallet-draft-preview.json`,
`indexer/postgres-api-transaction-detail.json`,
`indexer/postgres-server-transaction-detail.json`,
`indexer/postgres-api-wallet-transaction-status.json`,
`indexer/postgres-server-wallet-transaction-status.json`,
`indexer/postgres-api-iso-transaction-status.json`,
`indexer/postgres-server-iso-transaction-status.json`,
`indexer/postgres-api-iso-payment-initiation.json`,
`indexer/postgres-server-iso-payment-initiation.json`,
`indexer/postgres-api-iso-account-statement.json`,
`indexer/postgres-server-iso-account-statement.json`,
`indexer/postgres-api-wallet-pending-transaction-status.json`,
`indexer/postgres-server-wallet-pending-transaction-status.json`,
`indexer/postgres-api-accounts.json`, `indexer/postgres-server-accounts.json`,
`indexer/postgres-api-wallet-accounts.json`,
`indexer/postgres-server-wallet-accounts.json`,
`indexer/postgres-api-account-detail.json`,
`indexer/postgres-server-account-detail.json`,
`indexer/postgres-api-wallet-balance.json`,
`indexer/postgres-server-wallet-balance.json`,
`indexer/postgres-api-account-history.json`,
`indexer/postgres-server-account-history.json`,
`indexer/postgres-api-wallet-account-history.json`,
`indexer/postgres-server-wallet-account-history.json`,
`indexer/postgres-api-node-status.json`,
`indexer/postgres-server-node-status.json`,
`indexer/postgres-api-indexer-status.json`,
`indexer/postgres-server-indexer-status.json`,
`indexer/postgres-api-audit-events.json`,
`indexer/postgres-server-audit-events.json`,
`indexer/postgres-api-snapshots.json`,
`indexer/postgres-server-snapshots.json`,
`indexer/postgres-api-snapshot-detail.json`,
`indexer/postgres-server-snapshot-detail.json`,
and
`indexer/postgres-admin-ui-read-model-status.json` under the smoke output
directory.
The default `xriq-api request` and `serve-readonly` flows still use file-backed
chain replay. The command below is local-only and reads the Compose Postgres
read model through container-local `psql`:

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

To expose the same Postgres read-model status, explorer overview, block list/detail,
transaction list, mempool, wallet status, wallet draft-preview, transaction detail, wallet transaction status,
ISO 20022 transaction status, ISO 20022 payment initiation, ISO 20022 account statement, account list,
account detail, and account history plus wallet account list, wallet balance,
wallet account history, audit events, snapshot list/detail, node status, and
indexer status through the local read-only HTTP server, pass both explicit
Postgres flags.
Without these flags, the Postgres status route remains disabled and the normal
file-backed routes keep working.

```bash
cargo run -p xriq-api -- serve-readonly --chain-file target/xriq-indexer-replay-smoke.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --bind 127.0.0.1:8090 --postgres-docker-container xriq-postgres --postgres-database xriq_phase1_1_smoke
```

To expose the same product API routes over localhost for a browser/client
smoke, run. The optional `--pending-file` is read-only in `xriq-api`: it lets
the Admin panel inspect durable private-devnet pending entries while wallet
submit and block production remain disabled in the product API. The same
pending file also lets
`/api/v1/wallet/transactions/{hash}/status` report pending transaction hashes
with null block fields until a private-devnet block confirms them.

```bash
cargo run -p xriq-api -- serve-readonly --chain-file target/xriq-indexer-replay-smoke.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --bind 127.0.0.1:8090
```

The first Phase 1.1 ISO 20022 compatibility adapter scaffold can be checked
with:

```bash
cargo test -p xriq-iso20022
```

The product API exposes the adapter through GET-only/read-only preview routes:
`/api/v1/iso20022/payment-initiation/preview?tx_hash=<hash>`,
`/api/v1/iso20022/transactions/{hash}/status`, and
`/api/v1/iso20022/accounts/{address}/statement?from=<ts>&to=<ts>`. These are
private-devnet previews only and do not claim ISO certification, bank/SWIFT
connectivity, legal compliance, or production payment-network support.

The first React + TypeScript explorer, wallet-preview, and admin-status UI shell
lives at `apps/explorer-ui`. It reads the product API through the dev server's
same-origin `/api` proxy, shows basic block, transaction, and account detail
panels, includes a preview-only wallet transfer draft surface wired to the
product wallet draft-preview API, includes a read-only ISO 20022 preview panel
wired to the product ISO routes, and shows a read-only admin status panel for
node, network, indexer, wallet capability, mempool status, snapshot catalog, and
audit-event state. It also shows an optional read-only Postgres read-model
status block that reports `disabled` when `serve-readonly` was not launched
with explicit Postgres flags. The wallet panel also shows read-only confirmed and pending
activity detail plus product API transaction-status detail for the selected
local account, and a product API account-history table for confirmed wallet
history. It does not sign, submit, persist, or manage private keys.

```powershell
cargo run -p xriq-api -- serve-readonly --chain-file target\xriq-indexer-replay-smoke.bin --pending-file target\xriq-devnet-pending.tsv --alice-balance 100 --bind 127.0.0.1:8090
cd apps\explorer-ui
npm.cmd install
npm.cmd run check
npm.cmd run check:postgres-ui -- --base-url http://127.0.0.1:8090 --expect disabled
npm.cmd run build
npm.cmd run dev -- --port 5173
```

When the local API was launched with explicit Postgres flags, the same UI logic
smoke can validate the Admin panel's live read-model rows:

```powershell
npm.cmd run check:postgres-ui -- --base-url http://127.0.0.1:8090 --expect available --expected-database xriq_phase1_1_smoke --expected-blocks 1 --expected-transactions 1 --expected-accounts 3 --expected-account-history 2 --expected-audit-events 1
```

After producing a local private-devnet chain file, replay it through the
indexer read model with:

```bash
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format json
```

To inspect the idempotent PostgreSQL write plan without requiring a running
database, use:

```bash
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format sql
```

To dry-run the local PostgreSQL apply path without invoking `psql`, use:

```bash
cargo run -p xriq-indexer -- apply-postgres --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --schema-file db/schema.sql --dry-run true
```

The root `docker-compose.yml` includes an optional local-only Postgres service
named `postgres` for the Phase 1.1 read model. Real local database application
is explicit only: start Postgres, set `XRIQ_POSTGRES_URL`, make sure `psql` is
installed, and pass `--dry-run false`.

```powershell
docker compose up -d postgres
$env:XRIQ_POSTGRES_URL = "postgresql://xriq:xriq-local-dev-password@localhost:5433/xriq_private_dev"
cargo run -p xriq-indexer -- apply-postgres --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --schema-file db/schema.sql --dry-run false
cargo run -p xriq-indexer -- verify-postgres --database-url-env XRIQ_POSTGRES_URL --dry-run false
```

The verification command also supports a dry run when a database is not
available:

```bash
cargo run -p xriq-indexer -- verify-postgres --dry-run true
```

After the local check has passed and the RC checkpoint is committed, the latest
summary can be re-checked without rerunning Rust:

```bash
python scripts/xriq_phase1_rc_readiness.py --require-clean-git --require-origin-main --require-rc-tag-available
```

Private-devnet node status smoke:

```bash
cargo run -p xriq-node -- status --chain-file target/xriq-devnet-chain.bin

cargo run -p xriq-node -- chain-check \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --format json
```

Private-devnet transfer/block smoke:

```bash
cargo run -p xriq-node -- produce-transfer-block \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --from xriqdev1alice00000000000 \
  --to xriqdev1bobbb00000000000 \
  --amount 25 \
  --fee 2 \
  --nonce 0 \
  --expires-at-height 100 \
  --timestamp-ms 1000
```

Private-devnet file explorer smoke:

```bash
cargo run -p xriq-node -- explorer-overview \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --limit 5

cargo run -p xriq-node -- block-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --height 1

cargo run -p xriq-node -- block-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --height latest

cargo run -p xriq-node -- block-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --block-hash <hash-from-block-detail-or-overview>

cargo run -p xriq-node -- account-list \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --limit 10

cargo run -p xriq-node -- account-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --address xriqdev1alice00000000000

cargo run -p xriq-node -- account-transactions \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --address xriqdev1alice00000000000 \
  --limit 10

cargo run -p xriq-node -- transaction-list \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --limit 10

cargo run -p xriq-node -- mempool-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --draft-file target/xriq-wallet-transfer-draft.txt \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100

cargo run -p xriq-node -- transaction-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --draft-file target/xriq-wallet-transfer-draft.txt \
  --alice-balance 100 \
  --tx-hash <hash-from-mempool-detail> \
  --format json

cargo run -p xriq-node -- explorer-overview \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --limit 5 \
  --format json

cargo run -p xriq-node -- block-list \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --limit 5 \
  --format json
```

Private-devnet wallet-draft-to-block smoke:

```bash
cargo run -p xriq-wallet -- transfer \
  --chain-id xriq-devnet \
  --from xriqdev1alice00000000000 \
  --to xriqdev1bobbb00000000000 \
  --amount 25 \
  --fee 2 \
  --nonce 0 \
  --expires-at-height 100 \
  > target/xriq-wallet-transfer-draft.txt

cargo run -p xriq-node -- produce-draft-block \
  --chain-file target/xriq-devnet-chain.bin \
  --draft-file target/xriq-wallet-transfer-draft.txt \
  --alice-balance 100 \
  --timestamp-ms 1000
```

Private-devnet durable pending-file block smoke:

```bash
cargo run -p xriq-node -- produce-pending-block \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --timestamp-ms 1000
```

Private-devnet wallet pending-to-block lifecycle:

```bash
cargo run -p xriq-wallet -- send \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --chain-id xriq-devnet \
  --from xriqdev1alice00000000000 \
  --to xriqdev1bobbb00000000000 \
  --amount 25 \
  --fee 2 \
  --nonce auto \
  --alice-balance 100 \
  --expires-at-height 100 \
  --format json

cargo run -p xriq-node -- produce-pending-block \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --timestamp-ms 1000 \
  --format json

cargo run -p xriq-wallet -- tx status \
  --chain-file target/xriq-devnet-chain.bin \
  --tx-hash <hash-from-wallet-send> \
  --alice-balance 100 \
  --format json
```

Private-devnet client preflight transfer smoke:

```bash
cargo run -p xriq-node -- preflight-transfer \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --from xriqdev1alice00000000000 \
  --to xriqdev1bobbb00000000000 \
  --amount 25 \
  --fee 2 \
  --expires-at-height 100 \
  --timestamp-ms 1000 \
  --format json
```

BIBER API client private-devnet loop from the repo root:

```bash
python scripts/biber_xriq_private_devnet_client.py status
python scripts/biber_xriq_private_devnet_client.py account xriqdev1alice00000000000
python scripts/biber_xriq_private_devnet_client.py mempool
python scripts/biber_xriq_private_devnet_client.py preflight-transfer \
  --from xriqdev1alice00000000000 \
  --to xriqdev1bobbb00000000000 \
  --amount 25 \
  --fee 2 \
  --expires-at-height 100 \
  --timestamp-ms 1000
python scripts/biber_xriq_private_devnet_client.py transaction <hash-from-preflight>
python scripts/biber_xriq_private_devnet_client.py block <height-from-preflight>
python scripts/biber_xriq_private_devnet_client.py snapshot-export --snapshot-name api-smoke
python scripts/biber_xriq_private_devnet_client.py snapshots
python scripts/biber_xriq_private_devnet_client.py snapshot api-smoke
python scripts/biber_xriq_private_devnet_client.py snapshot-import api-smoke --target staging
```

Set `BIBER_API_KEY` or pass `--api-key`. Use `--json` on any client command to
print the full API response instead of the concise summary.

Private-devnet wallet chain status:

```bash
cargo run -p xriq-wallet -- status \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --format json
```

Private-devnet wallet chain verification:

```bash
cargo run -p xriq-wallet -- check \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --format json
```

Private-devnet wallet JSON submit body:

```bash
cargo run -p xriq-wallet -- transfer \
  --chain-id xriq-devnet \
  --from xriqdev1alice00000000000 \
  --to xriqdev1bobbb00000000000 \
  --amount 25 \
  --fee 2 \
  --nonce 0 \
  --expires-at-height 100 \
  --format json \
  > target/xriq-wallet-transfer-submit.json

cargo run -p xriq-wallet -- transfer \
  --chain-id xriq-devnet \
  --from xriqdev1alice00000000000 \
  --to xriqdev1bobbb00000000000 \
  --amount 5 \
  --fee 2 \
  --nonce auto \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --expires-at-height 100 \
  --format json
```

Private-devnet wallet local pending submit:

```bash
cargo run -p xriq-wallet -- submit \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --transfer-file target/xriq-wallet-transfer-submit.json \
  --alice-balance 100 \
  --format json

cargo run -p xriq-wallet -- pending \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --format json
```

Private-devnet wallet direct pending send:

```bash
cargo run -p xriq-wallet -- send \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --chain-id xriq-devnet \
  --from xriqdev1alice00000000000 \
  --to xriqdev1bobbb00000000000 \
  --amount 25 \
  --fee 2 \
  --nonce auto \
  --alice-balance 100 \
  --expires-at-height 100 \
  --format json

cargo run -p xriq-wallet -- pending \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --format json
```

Private-devnet wallet account list and balance lookup:

```bash
cargo run -p xriq-wallet -- accounts \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --limit 10 \
  --format json

cargo run -p xriq-wallet -- balance \
  --chain-file target/xriq-devnet-chain.bin \
  --address xriqdev1alice00000000000 \
  --alice-balance 100 \
  --format json
```

Private-devnet wallet account history lookup:

```bash
cargo run -p xriq-wallet -- history \
  --chain-file target/xriq-devnet-chain.bin \
  --address xriqdev1alice00000000000 \
  --alice-balance 100 \
  --limit 10 \
  --format json
```

Private-devnet wallet transaction status lookup:

```bash
cargo run -p xriq-wallet -- tx status \
  --chain-file target/xriq-devnet-chain.bin \
  --tx-hash <hash-from-wallet-transfer-or-node-submit> \
  --alice-balance 100 \
  --format json

cargo run -p xriq-wallet -- tx status \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --tx-hash <pending-hash-from-mempool-submit> \
  --alice-balance 100 \
  --format json
```

These are local private-devnet helpers over the file-backed chain state. They do
not connect to a public network or manage production custody.

One-command private-devnet smoke from the repo root:

```bash
bash scripts/xriq_private_devnet_smoke.sh
```

This is a Bash script. On Windows workstations without Git Bash or a WSL
distribution, run it on the Vast workspace after `git pull`.

Windows-friendly isolated transfer/replay/snapshot smoke from the repo root:

```bash
python scripts/xriq_private_devnet_transfer_smoke.py
```

This uses only Python stdlib plus Cargo/Rust. It creates a fresh artifact
directory under `xriq/target/`, performs one private-devnet transfer, verifies
transaction/block/account detail, verifies `xriq-wallet accounts`,
`xriq-wallet balance`, confirmed `xriq-wallet history`,
`xriq-wallet tx status`, `xriq-wallet status`, `xriq-wallet check`,
`xriq-wallet transfer --nonce auto`, and
`xriq-wallet submit` plus `xriq-wallet send` and `xriq-wallet pending` against
a separate durable pending file, exports and imports a snapshot, verifies snapshot
list/latest/latest-check/detail/check flows, runs `chain-check` against the
restored snapshot targets, then runs a separate wallet pending-to-block lifecycle through
`xriq-node produce-pending-block`, and leaves any live/restored BIBER API chain
files untouched.

Windows-friendly local HTTP/RPC smoke from the repo root:

```bash
python scripts/xriq_private_devnet_http_smoke.py
```

This builds the local Rust binaries, starts a real `xriq-node serve-private`
process on a temporary localhost port, submits a wallet transfer through
`POST /v1/mempool`, restarts the server to verify durable pending state,
produces a block through `POST /v1/blocks`, and verifies transaction, block,
block list, account list/detail, account transaction history, latest
transaction list, mempool, explorer overview, chain check, snapshot export, and
snapshot list/latest/latest-check/detail/check, snapshot import, post-import
chain-check endpoints, and pending `xriq-wallet tx status` against the durable
pending file.

The current machine-readable runner contract is documented in
`../docs/XRIQ_NODE_JSON_SCHEMA.md`.

`xriq-node status --format json` includes a replayed `state_root` in addition
to height, latest block hash, pending transaction count, and stored block count.
`xriq-node explorer-overview --format json` exposes the same replayed
`state_root` for dashboard comparisons. Use it as the compact deterministic
marker when comparing a chain before and after restart, copy, or future
snapshot/export work.

Private-devnet snapshot export/import:

```bash
cargo run -p xriq-node -- snapshot-export \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --snapshot-dir target/xriq-devnet-snapshot \
  --alice-balance 100 \
  --format json

cargo run -p xriq-node -- snapshot-import \
  --snapshot-dir target/xriq-devnet-snapshot \
  --chain-file target/xriq-devnet-restored-chain.bin \
  --pending-file target/xriq-devnet-restored-pending.tsv \
  --alice-balance 100 \
  --format json

cargo run -p xriq-node -- snapshot-list \
  --snapshot-root target \
  --limit 10 \
  --format json

cargo run -p xriq-node -- snapshot-latest \
  --snapshot-root target \
  --format json

cargo run -p xriq-node -- snapshot-latest-check \
  --snapshot-root target \
  --alice-balance 100 \
  --format json

cargo run -p xriq-node -- snapshot-detail \
  --snapshot-dir target/xriq-devnet-snapshot \
  --format json

cargo run -p xriq-node -- snapshot-check \
  --snapshot-dir target/xriq-devnet-snapshot \
  --alice-balance 100 \
  --format json

cargo run -p xriq-node -- chain-check \
  --chain-file target/xriq-devnet-restored-chain.bin \
  --pending-file target/xriq-devnet-restored-pending.tsv \
  --alice-balance 100 \
  --format json
```

The snapshot workflow copies `chain.bin`, optional `pending.tsv`, and
`manifest.json` into a new snapshot directory. Import refuses to overwrite
existing target files. `snapshot-list` scans one snapshot root for immediate
child directories containing XRIQ snapshot manifests; `snapshot-latest` returns
the first snapshot using the same deterministic ordering; `snapshot-latest-check`
replays that latest snapshot before restore without requiring its name;
`snapshot-detail` reads one snapshot manifest and reports the deterministic
tip/status fields needed before restore. `snapshot-check` replays the snapshot
chain/pending files and confirms they still match the manifest before restore.
After import,
`chain-check` replays the restored chain/pending files to verify the fresh
targets before use. See
`../docs/XRIQ_SNAPSHOT_EXPORT_IMPORT.md`.

Checked private-devnet JSON fixtures live in `fixtures/private-devnet/`.
They are used by Rust tests as golden examples for wallet/node schema drift.
Current checked fixtures cover fresh node status, empty mempool detail, initial
Alice account detail, wallet transfer submit body, empty wallet chain-check
JSON, wallet direct-send pending JSON, produced transfer block JSON, block
detail JSON with transaction hashes, produced pending-block JSON, and preflight
transfer JSON.

Private-devnet read-only HTTP wrapper:

```bash
cargo run -p xriq-node -- serve-readonly \
  --chain-file target/xriq-devnet-chain.bin \
  --snapshot-root target \
  --alice-balance 100 \
  --bind 127.0.0.1:8787
```

Private-devnet submit-capable HTTP wrapper:

```bash
cargo run -p xriq-node -- serve-private \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --snapshot-root target \
  --alice-balance 100 \
  --bind 127.0.0.1:8787
```

Initial read-only endpoints:

```text
GET /health
GET /v1/chain/status
GET /v1/chain/check
GET /v1/explorer/overview?limit=5
GET /v1/blocks?limit=5
GET /v1/blocks/{height-or-hash-or-latest}
GET /v1/transactions?limit=5
GET /v1/transactions/{hash}
GET /v1/accounts?limit=5
GET /v1/accounts/{address}
GET /v1/accounts/{address}/transactions?limit=5
GET /v1/mempool
GET /v1/snapshots?limit=5
GET /v1/snapshots/latest
GET /v1/snapshots/latest/check
GET /v1/snapshots/{snapshot-name}
GET /v1/snapshots/{snapshot-name}/check
POST /v1/mempool
POST /v1/blocks
POST /v1/snapshots/export?snapshot_dir=<path>
POST /v1/snapshots/import?snapshot_dir=<path>
```

Product API read-only HTTP wrapper:

```bash
cargo run -p xriq-api -- serve-readonly \
  --chain-file target/xriq-indexer-replay-smoke.bin \
  --alice-balance 100 \
  --bind 127.0.0.1:8090
```

Initial product API endpoints:

```text
GET /api/v1/health
GET /api/v1/version
GET /api/v1/network
GET /api/v1/explorer/overview
GET /api/v1/blocks?limit=5
GET /api/v1/blocks/{height-or-hash}
GET /api/v1/transactions?limit=5
GET /api/v1/transactions/{hash}
GET /api/v1/accounts?limit=5
GET /api/v1/accounts/{address}
GET /api/v1/accounts/{address}/transactions?limit=5
GET /api/v1/wallet/status
GET /api/v1/wallet/accounts?limit=5
GET /api/v1/wallet/accounts/{address}/balance
GET /api/v1/wallet/accounts/{address}/history?limit=5
GET /api/v1/wallet/transactions/{hash}/status
GET /api/v1/wallet/transfers/draft-preview?from_address=<address>&to_address=<address>&amount_base_units=<n>&fee_base_units=<n>&nonce=<n>&expires_at_height=<height>
GET /api/v1/admin/indexer/status
```

The product wallet API routes are private-devnet preview/read routes only.
`draft-preview` validates transfer fields and reports balance/debit/remaining
math with `mutation: "none"`; it does not sign, submit, persist, or manage
private keys. The mutating wallet submit/send contract remains deferred.

`GET /v1/blocks/{height-or-hash-or-latest}` returns the same block-detail JSON
shape for either a decimal block height, `latest`, or a 64-character lowercase
hex block hash.

`GET /v1/blocks?limit=<n>` scans persisted blocks in descending height order
and returns compact private-devnet block summaries for explorer/operator views.

`GET /v1/chain/check` replays and validates the configured chain file, includes
durable pending-file validation when `serve-private --pending-file <path>` is
used, and returns `verified: true` plus the current deterministic tip/status.

`GET /v1/transactions/{hash}` scans confirmed transactions in persisted blocks.
When `serve-private --pending-file <path>` is used, it checks confirmed blocks
first, then durable pending state. The local runner can also preview a pending
transaction from a wallet draft with
`xriq-node transaction-detail --draft-file <path> --tx-hash <hash>`.

`GET /v1/transactions?limit=<n>` scans confirmed persisted blocks in descending
height order and returns recent transparent private-devnet transactions.

`GET /v1/accounts?limit=<n>` lists replayed private-devnet accounts in
deterministic address order for private explorer/operator inspection.

`GET /v1/accounts/{address}/transactions?limit=<n>` scans confirmed persisted
blocks in descending height order and returns transparent private-devnet
transactions involving that account.

When `serve-private` is started with `--pending-file <path>`,
`POST /v1/mempool` accepts the same wallet draft text or JSON transfer body and
persists it as private-devnet pending state. `GET /v1/mempool`,
`GET /v1/chain/status`, and `GET /v1/transactions/{hash}` then include that
durable pending state across requests and server restarts.

The local runner can inspect the same durable pending state with
`xriq-node mempool-detail --pending-file <path>`.

When the server is started with `--snapshot-root <path>`,
`GET /v1/snapshots?limit=<n>` lists immediate child snapshot directories under
that root, `GET /v1/snapshots/latest` returns the same detail shape for the
latest discovered snapshot, `GET /v1/snapshots/latest/check` replays that
latest snapshot before restore, `GET /v1/snapshots/{snapshot-name}` reads one
snapshot manifest, and `GET /v1/snapshots/{snapshot-name}/check` replays the
snapshot chain/pending files to verify them before restore. Snapshot names must
be a single safe path segment.

`POST /v1/blocks` is available only through `serve-private --pending-file
<path>`. It produces one private-devnet block from the durable pending file,
persists the block to the configured chain file, and compacts the pending file
so included transactions are removed.

`POST /v1/snapshots/export?snapshot_dir=<path>` is available only through
`serve-private`. It exports the configured chain file and optional pending file
into a new snapshot directory and returns the same JSON shape as
`xriq-node snapshot-export --format json`.

`POST /v1/snapshots/import?snapshot_dir=<path>` is available only through
`serve-private`. It imports a snapshot into the server's configured chain file
and optional pending file, refusing to overwrite existing target files, and
returns the same JSON shape as `xriq-node snapshot-import --format json`. After
import, call `GET /v1/chain/check` against the restored server to verify the
fresh chain and pending files before use.

`POST /v1/transactions` is available only through `serve-private`. It accepts
either the existing wallet transfer draft text or a private-devnet JSON transfer
body, then immediately produces a private-devnet block against the configured
chain file. This is an MVP submit-and-block helper, not a production mempool
API. The JSON body can be produced by `xriq-wallet transfer --format json`.

```json
{
  "format_version": "xriq-node-transfer-submit-v1",
  "warning": "private-devnet-test-identity-only",
  "version": 1,
  "chain_id": "xriq-devnet",
  "from": "xriqdev1alice00000000000",
  "to": "xriqdev1bobbb00000000000",
  "amount_base_units": "25",
  "fee_base_units": "2",
  "nonce": 0,
  "expires_at_height": 100,
  "transaction_hash": "64-hex-character-transaction-hash",
  "signature_bytes": 48
}
```

`transaction_hash` is emitted by the private-devnet wallet so local operators
can immediately query `GET /v1/transactions/{hash}` after submission. The node
still recomputes the canonical transaction hash during validation.

Keep generated chain data, node databases, wallets, and testnet artifacts out of
Git.
