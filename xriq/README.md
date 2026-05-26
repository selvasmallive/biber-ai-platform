# XRIQ Private Devnet Prototype

This subtree contains the Rust prototype for XRIQ. It is private-devnet code
only until security and legal/compliance review says otherwise.

## Current Scope

- `xriq-core`: dependency-free protocol types and validation helpers.
- `xriq-consensus`: deterministic private-devnet block production.
- `xriq-crypto`: canonical hashing and test-only signature verification boundary.
- `xriq-explorer`: read-only private-devnet explorer view models and text UI.
- `xriq-ledger`: deterministic private-devnet account state transitions.
- `xriq-mempool`: deterministic pending-transaction checks and ordering.
- `xriq-node`: minimal local private-devnet node loop with deterministic replay
  startup from persisted canonical blocks plus a startup consistency guard, a
  private-devnet status runner, a
  local transfer-to-block runner, wallet draft-file block production, and a
  file-backed explorer overview plus block/account/mempool detail runners with
  optional stable JSON output and a read-only local HTTP wrapper.
- `xriq-rpc`: local private-devnet RPC endpoint behavior.
- `xriq-storage`: local block storage for private-devnet tests.
- `xriq-wallet`: private-devnet wallet CLI for test identities and transfers.

## Commands

```bash
cd xriq
cargo fmt --check
cargo test
cargo clippy -- -D warnings
```

Private-devnet node status smoke:

```bash
cargo run -p xriq-node -- status --chain-file target/xriq-devnet-chain.bin
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
```

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
transaction/block/account detail, exports/imports a snapshot, and leaves any
live/restored BIBER API chain files untouched.

Windows-friendly local HTTP/RPC smoke from the repo root:

```bash
python scripts/xriq_private_devnet_http_smoke.py
```

This builds the local Rust binaries, starts a real `xriq-node serve-private`
process on a temporary localhost port, submits a wallet transfer through
`POST /v1/mempool`, restarts the server to verify durable pending state,
produces a block through `POST /v1/blocks`, and verifies transaction, block,
account, account transaction history, latest transaction list, mempool,
explorer overview, snapshot export, and snapshot import endpoints.

The current machine-readable runner contract is documented in
`../docs/XRIQ_NODE_JSON_SCHEMA.md`.

`xriq-node status --format json` includes a replayed `state_root` in addition
to height, latest block hash, pending transaction count, and stored block count.
Use it as the compact deterministic marker when comparing a chain before and
after restart, copy, or future snapshot/export work.

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
```

The snapshot workflow copies `chain.bin`, optional `pending.tsv`, and
`manifest.json` into a new snapshot directory. Import refuses to overwrite
existing target files. See `../docs/XRIQ_SNAPSHOT_EXPORT_IMPORT.md`.

Checked private-devnet JSON fixtures live in `fixtures/private-devnet/`.
They are used by Rust tests as golden examples for wallet/node schema drift.
Current checked fixtures cover fresh node status, empty mempool detail, initial
Alice account detail, wallet transfer submit body, produced transfer block
JSON, block detail JSON with transaction hashes, produced pending-block JSON,
and preflight transfer JSON.

Private-devnet read-only HTTP wrapper:

```bash
cargo run -p xriq-node -- serve-readonly \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --bind 127.0.0.1:8787
```

Private-devnet submit-capable HTTP wrapper:

```bash
cargo run -p xriq-node -- serve-private \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --alice-balance 100 \
  --bind 127.0.0.1:8787
```

Initial read-only endpoints:

```text
GET /health
GET /v1/chain/status
GET /v1/explorer/overview?limit=5
GET /v1/blocks/{height-or-hash-or-latest}
GET /v1/transactions?limit=5
GET /v1/transactions/{hash}
GET /v1/accounts/{address}
GET /v1/accounts/{address}/transactions?limit=5
GET /v1/mempool
POST /v1/mempool
POST /v1/blocks
POST /v1/snapshots/export?snapshot_dir=<path>
POST /v1/snapshots/import?snapshot_dir=<path>
```

`GET /v1/blocks/{height-or-hash-or-latest}` returns the same block-detail JSON
shape for either a decimal block height, `latest`, or a 64-character lowercase
hex block hash.

`GET /v1/transactions/{hash}` scans confirmed transactions in persisted blocks.
When `serve-private --pending-file <path>` is used, it checks confirmed blocks
first, then durable pending state. The local runner can also preview a pending
transaction from a wallet draft with
`xriq-node transaction-detail --draft-file <path> --tx-hash <hash>`.

`GET /v1/transactions?limit=<n>` scans confirmed persisted blocks in descending
height order and returns recent transparent private-devnet transactions.

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
returns the same JSON shape as `xriq-node snapshot-import --format json`.

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
