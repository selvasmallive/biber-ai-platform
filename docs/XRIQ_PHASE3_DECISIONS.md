# XRIQ Phase 3 Decision Record

Status: active private-devnet engineering decision record.

This document is not legal, tax, compliance, investment, or launch advice. It
records conservative engineering decisions for the current XRIQ prototype so
future Codex and BIBER sessions can keep moving without turning the private
devnet into a public cryptocurrency product by accident.

All work here remains subject to `docs/XRIQ_LEGAL_RISK_REDUCTION.md`.

## Scope

These decisions apply to the current Rust workspace in `xriq/` and to any
private-devnet tooling built around it.

They do not approve:

- public mainnet
- public token distribution
- token sale, airdrop, reward campaign, or liquidity program
- project-operated DEX, bridge, custody, payment, or stablecoin service
- investment, yield, price, listing, or profit-facing messaging

## Decision Summary

| Area | Current Decision | What This Allows Now | What Remains Blocked |
| --- | --- | --- | --- |
| Consensus | Keep deterministic authority consensus for private devnet. | Single-authority and in-process multi-node tests. | Public proof of stake, validator rewards, slashing, public validator admission. |
| Supply | Use deterministic test allocation only. | Local genesis/test balances and fee accounting. | Public supply, emissions, burns, treasury, sale, airdrop, reward schedule. |
| Governance | Use project-owner engineering governance for the private prototype. | Git-reviewed specs, tests, and explicit decision records. | Token governance, treasury rights, revenue rights, or public upgrade promises. |
| Public readiness | Treat public launch as blocked. | Private tests, security hardening, model/eval work, local tooling. | Mainnet, public explorer/API, public wallet, exchange/DEX activity, production custody. |

## Consensus Decision

For Phase 3, XRIQ stays on deterministic authority consensus.

Current allowed path:

- keep `xriq-consensus` single-authority block production as the baseline
- keep `xriq-node` in-process local multi-node import tests
- add explicit chain and validator configuration before adding networked peers
- keep peer admission allowlist-only for private tests
- require every imported block to pass local validation before ledger/storage
  commit

Deferred decisions:

- public consensus family
- BFT quorum design
- proof-of-stake economics
- validator admission and removal
- slashing, rewards, or penalties
- fork choice beyond the current single-chain private test path

Do not add economic validator incentives until legal, economic, and security
review is complete.

## Supply Decision

For Phase 3, XRIQ supply is test-only.

Current allowed path:

- deterministic private-devnet genesis allocations
- integer-only base-unit accounting
- explicit fee debit and fee-sink crediting in tests
- fixture accounts for node, wallet, explorer, and RPC testing

Blocked until review:

- public native supply number
- emissions schedule
- token sale or allocation to purchasers
- public airdrop or promotional rewards
- burns marketed as price-support
- validator rewards marketed as yield
- treasury, reserve, or liquidity allocation

Future implementation should add a `GenesisConfig` or equivalent before any
more serious network simulation. The config should support test allocations and
technical fee policy, while leaving public economics unset.

## Governance Decision

For Phase 3, governance is ordinary private engineering governance.

Current allowed path:

- decisions recorded in docs
- code reviewed through Git commits
- changes verified by local and Vast Rust checks
- explicit handoff updates after important checkpoints
- no public governance promises

Blocked until review:

- token-holder voting
- revenue, profit, asset, debt, equity, or management rights
- public treasury control
- governance-mined rewards
- emergency controls presented as decentralized when they are not

Before any community devnet, add a public-governance design document that
separates technical upgrade control from token economics and public messaging.

## Public-Readiness Decision

XRIQ is not public-ready.

Before any public XRIQ token, wallet, API, explorer, validator, bridge, DEX, or
mainnet work, the project needs at least:

- canonical serialization and hashing
- real reviewed signature verification
- versioned crypto-agile key/signature metadata
- genesis and chain configuration
- deterministic state-root and transaction-root calculation
- persistent account/state replay or snapshot strategy
- private peer identity and allowlist networking
- threat model
- dependency audit
- cryptography review
- wallet key-management review
- fuzz/property tests for parsers and validation
- external security review for security-critical code
- open-source license, security policy, and contribution policy
- legal, tax, AML/CFT, sanctions, securities, commodities, consumer-protection,
  privacy, and cybersecurity review

## Current Crypto/Hashing Checkpoint

`xriq-crypto` now exists as the Phase 3 crypto boundary. It provides:

- SHA-256 canonical transaction signing hashes
- SHA-256 canonical transaction hashes
- SHA-256 canonical block-header signing hashes
- SHA-256 canonical block/header hashes
- deterministic transaction-list roots over transaction hashes
- explicit signature algorithm identifiers for crypto agility
- a hash-bound `TestOnlySignatureVerifier` for private-devnet tests

This is not production signature verification or wallet custody. The only
accepted verifier currently implemented is test-only, and wallet drafts remain
private-devnet-only.

## Next Engineering Step

The next implementation target should wire canonical hashes into the existing
node/RPC/storage path:

- derive transaction hashes from `xriq-crypto` instead of accepting caller
  supplied transaction hashes in higher-level APIs where possible
- derive block/header hashes from `xriq-crypto` when producing and importing
  blocks
- keep manual hash inputs only where tests need explicit fixture control
- keep test-only signature verification separate from production crypto
  verification

Wallet private-key custody should remain test-only until the crypto and
key-management boundary is reviewed.

## Instructions For Future Codex/BIBER Sessions

- Prefer private-devnet infrastructure, tests, and security hardening.
- Do not implement public launch, market, reward, yield, DEX, bridge, custody,
  or public-token features without recorded review status.
- Use this decision record with `docs/XRIQ_LEGAL_RISK_REDUCTION.md` before
  interpreting any XRIQ roadmap item.
- Update this document when a decision changes.
- Update `docs/CODEX_HANDOFF.md` after every meaningful implementation,
  verification, deployment, or decision checkpoint.
