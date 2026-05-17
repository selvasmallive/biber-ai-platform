# XRIQ Private Devnet Prototype

This subtree contains the Rust prototype for XRIQ. It is private-devnet code
only until security and legal/compliance review says otherwise.

## Current Scope

- `xriq-core`: dependency-free protocol types and validation helpers.
- `xriq-ledger`: deterministic private-devnet account state transitions.

## Commands

```bash
cd xriq
cargo fmt --check
cargo test
```

Keep generated chain data, node databases, wallets, and testnet artifacts out of
Git.
