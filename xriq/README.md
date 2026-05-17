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
  local transfer-to-block runner, and a file-backed explorer overview runner.
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
```

Keep generated chain data, node databases, wallets, and testnet artifacts out of
Git.
