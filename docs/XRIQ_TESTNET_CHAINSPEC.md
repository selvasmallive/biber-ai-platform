# XRIQ Public Testnet Chain Spec

Version: 1.0 (genesis spec v1)

> **TEST-ONLY.** The XRIQ public testnet is a test network. Its native units are
> **valueless test units** with **no monetary value**. There is no sale, ICO,
> emission, airdrop, or distribution beyond the fixed genesis faucet allocation
> below, and the faucet dispenses clearly-labeled valueless test units. This
> document is engineering documentation, not an offer, security, or investment.
> Legally-gated steps (public mainnet with value, token sale, DEX, custody)
> remain blocked pending counsel — see `docs/XRIQ_LEGAL_RISK_REDUCTION.md` and
> `docs/XRIQ_LEGAL_COUNSEL_QUESTIONS.md`.

This is the canonical, reproducible genesis configuration for the XRIQ public
test network. It is defined in code as `xriq_core::GenesisConfig::public_testnet()`
and printed by `xriq-node testnet-genesis --format json`. Two nodes must compute
the same `genesis_spec_hash` to be on the same chain.

## Parameters

| Field | Value |
| --- | --- |
| `chain_id` | `xriq-testnet` |
| `initial_height` | `0` |
| `genesis_block_hash` | `0000…0000` (all-zero; genesis is the implicit parent of block 1) |
| `min_fee_base_units` | `2` |
| `fee_sink` | `xriqdev1testnetfees0000000000` |
| `authority` | `xriqdev1testnetauthority00000` |
| `mempool_max_transactions` | `4096` |
| `max_transactions_per_block` | `512` |

Addresses use the fixed `xriqdev1` address-format prefix (this is the wire
address format, not a per-network marker); the `xriq-testnet` `chain_id` is what
separates the testnet from the `xriq-devnet` devnet.

## Genesis allocation

Exactly one account is funded at genesis — the faucet:

| Account | Address | Balance (base units) | Nonce |
| --- | --- | --- | --- |
| Faucet | `xriqdev1testnetfaucet00000000` | `1000000000000` | `0` |

The faucet balance is the only source of dispensable test units. It is **not** a
supply, sale, or distribution; it exists so the faucet can hand out valueless
test units for experimentation.

### Faucet dispense

`xriq-node faucet-dispense --chain-file <testnet-path> --to <address>` sends a
fixed drip of valueless test units from the faucet account to a recipient as a
normal signed transaction, confirmed in a freshly produced block. Policy:

| Setting | Default | Override |
| --- | --- | --- |
| Drip per request | `1000` base units | `--amount` |
| Recipient balance cap | `10000` base units | `--max-balance` |

Abuse control is a **balance cap**: the faucet refuses a recipient already at or
above the cap (a chain-derived, deterministic rate limit that needs no side
state), and refuses when the faucet account cannot cover the amount plus fee.
The command runs against its own testnet-genesis chain file; an HTTP faucet
endpoint with additional per-IP rate limiting will arrive with genesis-parametrized
testnet nodes.

## Genesis spec hash

```
genesis_spec_hash = af01fa096c41538735cae46a6f9a7cb052bb198b1dd33316f905e46ec7ad1580
```

The hash is `SHA-256` over a domain-separated (`xriq-genesis-spec:v1`), canonical,
length-prefixed encoding of every parameter above plus each genesis account
(address, balance, nonce), in order. Any change to the chain id, policy limits,
authority/fee-sink, or genesis allocation changes this hash — i.e. it would be a
new chain (a hard fork). The value is pinned by a golden test in
`xriq/crates/xriq-node/src/lib.rs`.

## Status

This spec defines the testnet genesis and a CLI faucet; it does **not** start a
public network by itself. Running public testnet nodes (genesis-parametrized,
exposing the faucet and peer sync over HTTP) and the public explorer/wallet are
later Phase 3 milestones (see `docs/XRIQ_PHASE3_PUBLIC_TESTNET_PLAN.md`), each
still test-only with no value.
