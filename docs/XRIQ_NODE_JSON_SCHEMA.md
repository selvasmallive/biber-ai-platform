# XRIQ Node JSON Output Contract

Status: private-devnet runner contract.

This document describes the successful `--format json` output emitted by the
file-backed `xriq-node` runner. It is for local private-devnet tooling, BIBER
agents, scripts, and future HTTP/RPC adapters. It is not a public API, mainnet
API, wallet-custody interface, or exchange-listing interface.

Current format version: `xriq-node-json-v1`.

Checked examples live in `xriq/fixtures/private-devnet/` and are compared by
Rust tests so schema drift is intentional. The current checked set covers fresh
node status, empty mempool detail, initial Alice account detail, wallet transfer
submit body, and produced transfer block JSON.

## Compatibility Rules

- Text output remains the default. Consumers that need machine-readable output
  must pass `--format json`.
- Every successful JSON response includes `format_version` and `command`.
- Every successful private-devnet response includes the warning value
  `private-devnet-only-no-public-token`.
- Hashes are lowercase 64-character hexadecimal strings.
- Addresses are strings.
- XRIQ amounts are decimal strings named `*_base_units`. They are strings so
  JavaScript and TypeScript clients do not lose precision for future `u128`
  values.
- Heights, nonces, counts, timestamps, and received-order values are JSON
  numbers while the private-devnet values remain within ordinary integer
  ranges.
- Optional heights are either a JSON number or `null`.
- Unknown fields may be added in a later format version. Consumers should ignore
  fields they do not understand and should branch on `format_version` before
  relying on changed semantics.
- When `--format json` is present and the runner fails, the CLI prints a JSON
  error response to stderr and exits nonzero. Without `--format json`, errors
  remain human-readable text plus help output.

## Status

Command:

```bash
cargo run -p xriq-node -- status \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --format json
```

Shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "status",
  "warning": "private-devnet-only-no-public-token",
  "chain_id": "xriq-devnet",
  "current_height": 0,
  "latest_block_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "pending_transactions": 0,
  "stored_blocks": 0
}
```

## Produced Block

Used by both `produce-transfer-block --format json` and
`produce-draft-block --format json`.

Shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "produce-draft-block",
  "warning": "private-devnet-only-no-public-token",
  "transaction_hash": "64-hex-character-transaction-hash",
  "block_hash": "64-hex-character-block-hash",
  "applied_transactions": 1,
  "chain_id": "xriq-devnet",
  "current_height": 1,
  "latest_block_hash": "64-hex-character-block-hash",
  "pending_transactions": 0,
  "stored_blocks": 1
}
```

## Explorer Overview

Command:

```bash
cargo run -p xriq-node -- explorer-overview \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --limit 5 \
  --format json
```

Shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "explorer-overview",
  "warning": "private-devnet-only-no-public-token",
  "chain_id": "xriq-devnet",
  "current_height": 1,
  "latest_block_hash": "64-hex-character-block-hash",
  "pending_transactions": 0,
  "stored_blocks": 1,
  "latest_blocks": [
    {
      "height": 1,
      "block_hash": "64-hex-character-block-hash",
      "transaction_count": 1,
      "producer": "xriqdev1authority000000000",
      "timestamp_ms": 1000
    }
  ]
}
```

## Block Detail

Command:

```bash
cargo run -p xriq-node -- block-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --height 1 \
  --format json
```

Shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "block-detail",
  "warning": "private-devnet-only-no-public-token",
  "height": 1,
  "block_hash": "64-hex-character-block-hash",
  "previous_block_hash": "64-hex-character-parent-hash",
  "state_root": "64-hex-character-state-root",
  "transactions_root": "64-hex-character-transactions-root",
  "transaction_count": 1,
  "producer": "xriqdev1authority000000000",
  "timestamp_ms": 1000,
  "transactions": [
    {
      "index": 0,
      "from": "xriqdev1alice00000000000",
      "to": "xriqdev1bobbb00000000000",
      "amount_base_units": "25",
      "fee_base_units": "2",
      "nonce": 0,
      "expires_at_height": 100
    }
  ]
}
```

## Transaction Detail

Runner command:

```bash
cargo run -p xriq-node -- transaction-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --tx-hash 64-hex-character-transaction-hash \
  --alice-balance 100 \
  --format json
```

When `--draft-file <path>` is provided, the runner scans confirmed blocks first,
then previews the supplied wallet draft as an in-memory pending transaction and
returns it when the requested hash matches. This preview does not persist a
mempool entry.

HTTP endpoint:

```bash
GET /v1/transactions/{hash}
```

The read-only HTTP wrapper scans confirmed transactions in persisted blocks and
returns `404` when the hash is not found. It does not report durable pending
transactions yet because the file-backed HTTP wrapper does not persist mempool
state across requests.

Confirmed shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "transaction-detail",
  "warning": "private-devnet-only-no-public-token",
  "tx_hash": "64-hex-character-transaction-hash",
  "status": "confirmed",
  "block_height": 1,
  "block_hash": "64-hex-character-block-hash",
  "transaction_index": 0,
  "from": "xriqdev1alice00000000000",
  "to": "xriqdev1bobbb00000000000",
  "amount_base_units": "25",
  "fee_base_units": "2",
  "nonce": 0,
  "expires_at_height": 100
}
```

Pending preview shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "transaction-detail",
  "warning": "private-devnet-only-no-public-token",
  "tx_hash": "64-hex-character-transaction-hash",
  "status": "pending",
  "received_order": 0,
  "from": "xriqdev1alice00000000000",
  "to": "xriqdev1bobbb00000000000",
  "amount_base_units": "25",
  "fee_base_units": "2",
  "nonce": 0,
  "expires_at_height": 100
}
```

## Submit Private-Devnet Transaction

HTTP endpoint:

```bash
POST /v1/transactions
```

This endpoint is enabled only by `xriq-node serve-private`. `serve-readonly`
returns `501`.

The request body can be either the existing wallet transfer draft text emitted
by `xriq-wallet transfer` or the flat JSON transfer body emitted by
`xriq-wallet transfer --format json`. The file-backed private-devnet helper
immediately validates the transfer against the replayed chain state, produces
one block, and persists it to the configured chain file. It does not create a
durable pending mempool entry.

Example wallet draft request body:

```text
warning=private-devnet-test-identity-only
version=1
chain_id=xriq-devnet
from=xriqdev1alice00000000000
to=xriqdev1bobbb00000000000
amount=25
fee=2
nonce=0
expires_at_height=100
signature_bytes=48
```

Example JSON request body:

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

JSON notes:

- `amount_base_units` and `fee_base_units` may be strings or integer numbers.
- `expires_at_height` may be an integer, string, `null`, or omitted.
- `warning` and `signature_bytes` are metadata emitted by the private-devnet
  wallet for operator safety and are ignored by the submit helper.
- `timestamp_ms` and `consensus_round` are optional private-devnet block
  production helpers and default to `1000` and `0`.
- The server reconstructs the current test-only private-devnet signature path;
  this is not production custody or a public signed-transaction format.

Success status: `201 Created`.

Shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "submit-transaction",
  "warning": "private-devnet-only-no-public-token",
  "transaction_hash": "64-hex-character-transaction-hash",
  "block_hash": "64-hex-character-block-hash",
  "applied_transactions": 1,
  "chain_id": "xriq-devnet",
  "current_height": 1,
  "latest_block_hash": "64-hex-character-block-hash",
  "pending_transactions": 0,
  "stored_blocks": 1
}
```

## Account Detail

Command:

```bash
cargo run -p xriq-node -- account-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --alice-balance 100 \
  --address xriqdev1alice00000000000 \
  --format json
```

Shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "account-detail",
  "warning": "private-devnet-only-no-public-token",
  "address": "xriqdev1alice00000000000",
  "balance_base_units": "73",
  "nonce": 1
}
```

## Mempool Detail

Command:

```bash
cargo run -p xriq-node -- mempool-detail \
  --chain-file target/xriq-devnet-chain.bin \
  --draft-file target/xriq-wallet-transfer-draft.txt \
  --alice-balance 100 \
  --format json
```

Shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "command": "mempool-detail",
  "warning": "private-devnet-only-no-public-token",
  "pending_count": 1,
  "transactions": [
    {
      "tx_hash": "64-hex-character-transaction-hash",
      "from": "xriqdev1alice00000000000",
      "to": "xriqdev1bobbb00000000000",
      "amount_base_units": "25",
      "fee_base_units": "2",
      "nonce": 0,
      "received_order": 0,
      "expires_at_height": 100
    }
  ]
}
```

## Error Response

Errors are written to stderr and exit nonzero when `--format json` is present.
The response is intentionally small so scripts can branch on `error.code`.

Example command:

```bash
cargo run -p xriq-node -- status --format json
```

Shape:

```json
{
  "format_version": "xriq-node-json-v1",
  "warning": "private-devnet-only-no-public-token",
  "ok": false,
  "command": "status",
  "error": {
    "code": "missing_flag",
    "message": "missing required flag: --chain-file"
  }
}
```

When the runner cannot identify a command, `command` is `null`.

Current stable error codes:

- `missing_command`
- `unknown_command`
- `unknown_flag`
- `missing_flag`
- `duplicate_flag`
- `unexpected_argument`
- `draft_file_read`
- `invalid_draft_line`
- `unknown_draft_field`
- `duplicate_draft_field`
- `missing_draft_field`
- `unsupported_draft_version`
- `wrong_draft_chain_id`
- `invalid_json`
- `unknown_json_field`
- `duplicate_json_field`
- `missing_json_field`
- `invalid_number`
- `invalid_hash`
- `invalid_format`
- `invalid_address`
- `explorer_error`
- `node_error`

## Smoke Artifact Examples

The private-devnet smoke script persists representative JSON responses under
its artifact directory:

```bash
bash scripts/xriq_private_devnet_smoke.sh
```

The script prints the artifact directory and writes these files:

- `wallet-transfer-submit.json`
- `mempool-detail.json`
- `pending-transaction-detail.json`
- `confirmed-transaction-detail.json`
- `explorer-overview.json`
- `account-detail.json`
- `status-error.json`
- `http-json-submit.json`
- `http-json-transaction.json`
- `http-json-account.json`

Use these generated files as concrete examples for BIBER agents, future
contract tests, and later HTTP/RPC adapters. They are private-devnet examples,
not public API fixtures.

## Checked Fixtures

The repository also includes checked private-devnet golden files under
`xriq/fixtures/private-devnet/`:

- `wallet-transfer-submit.json`
- `node-produce-transfer-block.json`
- `node-status-empty.json`
- `node-mempool-empty.json`
- `node-account-alice-initial.json`

Rust tests compare selected wallet and node JSON output to these files exactly
so accidental schema drift is caught early. These fixtures are private-devnet
contract examples only; they are not public-mainnet API guarantees.

## Read-Only HTTP Wrapper

`xriq-node serve-readonly` exposes selected private-devnet JSON runner outputs
over local HTTP. The wrapper defaults to loopback binding and is still
private-devnet tooling.

Implemented read-only endpoints:

- `GET /health`
- `GET /v1/chain/status`
- `GET /v1/explorer/overview?limit=5`
- `GET /v1/blocks/{height}`
- `GET /v1/transactions/{hash}`
- `GET /v1/accounts/{address}`
- `GET /v1/mempool`

The read-only endpoints reuse the JSON bodies documented above where possible.
HTTP-only health and wrapper errors use
`format_version: xriq-node-http-v1`. `POST /v1/transactions` uses the success
body documented above only when the server is started with `serve-private`;
`serve-readonly` returns `501`. Submit-capable POST bodies may be wallet draft
text or `xriq-node-transfer-submit-v1` JSON.

## Next Schema Work

Before making the HTTP/RPC surface broader than the current private-devnet
read-only wrapper, add:

- explicit schema tests if the JSON surface grows beyond this small contract
- more checked-in fixtures only if consumers need stable golden files
