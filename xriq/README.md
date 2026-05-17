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
  startup from persisted canonical blocks and a private-devnet status runner.
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

Keep generated chain data, node databases, wallets, and testnet artifacts out of
Git.
