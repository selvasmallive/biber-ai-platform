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
  startup from persisted canonical blocks, a private-devnet status runner, a
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

cargo run -p xriq-node -- account-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --address xriqdev1alice00000000000

cargo run -p xriq-node -- mempool-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --draft-file target/xriq-wallet-transfer-draft.txt \
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

The current machine-readable runner contract is documented in
`../docs/XRIQ_NODE_JSON_SCHEMA.md`.

Checked private-devnet JSON fixtures live in `fixtures/private-devnet/`.
They are used by Rust tests as golden examples for wallet/node schema drift.
Current checked fixtures cover fresh node status, empty mempool detail, initial
Alice account detail, wallet transfer submit body, and produced transfer block
JSON.

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
  --alice-balance 100 \
  --bind 127.0.0.1:8787
```

Initial read-only endpoints:

```text
GET /health
GET /v1/chain/status
GET /v1/explorer/overview?limit=5
GET /v1/blocks/{height}
GET /v1/transactions/{hash}
GET /v1/accounts/{address}
GET /v1/mempool
```

`GET /v1/transactions/{hash}` scans confirmed transactions in persisted blocks.
It does not report a durable pending status yet because the file-backed HTTP
wrapper does not persist a mempool across requests. The local runner can preview
a pending transaction from a wallet draft with
`xriq-node transaction-detail --draft-file <path> --tx-hash <hash>`.

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
  "signature_bytes": 48
}
```

Keep generated chain data, node databases, wallets, and testnet artifacts out of
Git.
