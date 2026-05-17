# XRIQ Node JSON Output Contract

Status: private-devnet runner contract.

This document describes the successful `--format json` output emitted by the
file-backed `xriq-node` runner. It is for local private-devnet tooling, BIBER
agents, scripts, and future HTTP/RPC adapters. It is not a public API, mainnet
API, wallet-custody interface, or exchange-listing interface.

Current format version: `xriq-node-json-v1`.

## Compatibility Rules

- Text output remains the default. Consumers that need machine-readable output
  must pass `--format json`.
- Every successful JSON response includes `format_version`.
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
- Error output is not JSON yet. On errors, the current CLI prints `error=...`
  and help text to stderr and exits nonzero.

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

## Next Schema Work

Before exposing these shapes through HTTP/RPC, add:

- JSON error responses for runner/API failures
- machine-readable command names in each response
- explicit schema tests if the JSON surface grows beyond this small contract
- response examples generated from the smoke script artifacts

