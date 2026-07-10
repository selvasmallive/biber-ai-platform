# XRIQ Production Readiness Roadmap

Version: 1.0

## Purpose

This document is the master **engineering** roadmap for evolving XRIQ from an
experimental blockchain into a production-quality Layer-1 blockchain that could
eventually be a technically credible candidate for evaluation by major
centralized exchanges (Coinbase, Binance, Kraken, OKX, and similar).

Goals: production-grade engineering, maximum reliability, excellent security,
open-source quality, a conservative legal posture, excellent documentation, and
long-term maintainability. It intentionally avoids token speculation, ICOs,
investment language, and unnecessary legal risk.

Relationship to other docs: this is the engineering plan. It sits alongside, and
does not override, `docs/XRIQ_PRODUCTION_ROADMAP.md` (phase/gate model),
`docs/XRIQ_LEGAL_RISK_REDUCTION.md` (legal guardrails), and
`docs/XRIQ_LEGAL_COUNSEL_QUESTIONS.md` (questions for counsel). Legally-gated
items (public mainnet with value, token sale, DEX, bridge, custody, staking
rewards) remain blocked pending qualified legal review regardless of engineering
progress.

## Guiding Principles

Always prioritize, in order: security, correctness, reliability, simplicity,
determinism, maintainability, documentation, testability. Never prioritize hype
over engineering.

## Current State

Rust implementation; account-based blockchain; SHA-256 hashing; private test
network; no token sale, ICO, staking, or custody; transparent ledger;
non-custodial wallet; test-only signatures; functional fee unit only; Google
Cloud deployment.

---

## Phase 1 — Core Blockchain

Goal: production-grade blockchain.

- **Consensus:** replace prototype consensus with a production implementation —
  deterministic, a BFT roadmap, replay protection, finality, fork handling, state
  synchronization, node recovery.
- **Cryptography:** replace ALL placeholder implementations with Ed25519 or
  secp256k1 using mature Rust crypto libraries. No custom cryptography. Every
  signature verified; every transaction authenticated.
- **Hashing:** continue SHA-256 unless a strong reason exists. Hash all blocks,
  transactions, receipts, and state roots.
- **State:** deterministic state machine, state root, Merkle tree or Merkle
  Patricia Tree. State transitions must be deterministic.
- **Mempool:** transaction validation, nonce ordering, fee ordering, duplicate
  detection, eviction policy, memory limits.
- **Transaction validation:** verify signature, nonce, balance, gas, chain id,
  replay protection, and size limits. Reject invalid transactions immediately.

## Phase 2 — Networking

Peer discovery, secure P2P, node identity, encrypted communications, connection
limits, rate limiting, peer banning, DDoS resistance. Support IPv4 and IPv6.

## Phase 3 — Storage

Crash recovery, atomic commits, snapshots, pruning, backups. Support fast
startup.

## Phase 4 — Wallet

Must remain NON-CUSTODIAL. Never store private keys, seed phrases, or mnemonics.
The browser signs locally; the server never accesses keys. Support hardware
wallets (Ledger, Trezor) and WalletConnect (future).

## Phase 5 — RPC API

Stable, versioned APIs over JSON-RPC, REST, and WebSocket. Document every
endpoint.

## Phase 6 — Explorer

Production explorer: blocks, transactions, addresses, validators, balances,
statistics, supply, and API documentation.

## Phase 7 — SDK

Official SDKs, priority Rust, Java, TypeScript, Python, Go. Each with examples,
documentation, and tests.

## Phase 8 — Security

AI-assisted security review (Claude, OpenAI Codex) as continuous reviewers of
consensus, cryptography, memory safety, race conditions, replay attacks, integer
overflow, denial of service, transaction validation, serialization, networking,
RPC, and wallet. Run AI reviews after every major feature; generate reports;
maintain `SECURITY_REVIEW.md`.

Note: AI review improves quality but some exchanges may still require independent
third-party audits before listing. Write the engineering to audit-quality
standards.

## Phase 9 — Testing

Target > 95% unit coverage. Unit, integration, property, fuzz, stress, load,
chaos, network-partition, long-duration, validator-failure, and memory-leak
tests.

## Phase 10 — CI/CD

GitHub Actions running, on every commit: `cargo fmt`, `cargo clippy`,
`cargo audit`, `cargo deny`, `cargo test`, `cargo bench`, security scan,
dependency scan, and documentation build.

## Phase 11 — Documentation

Architecture, Consensus, Networking, State, RPC, Wallet, Security, DeveloperGuide,
OperatorGuide, ValidatorGuide, NodeSetup, APIReference, ThreatModel, Roadmap.

## Phase 12 — Developer Experience

One-command setup, Docker support, dev containers, sample applications, quick
start, tutorials.

## Phase 13 — Open Source

LICENSE, SECURITY.md, CODE_OF_CONDUCT.md, CONTRIBUTING.md, ROADMAP.md,
CHANGELOG.md, RELEASE.md.

## Phase 14 — Performance

Benchmark TPS, latency, block propagation, memory, disk, CPU, network. Optimize
bottlenecks; never optimize prematurely.

## Phase 15 — Reliability

Nodes must survive power loss, crashes, disk corruption, network partitions,
validator failures, clock drift, and unexpected shutdowns.

## Phase 16 — Monitoring

Prometheus metrics, Grafana dashboards, structured logging, OpenTelemetry, health
endpoints, alerts.

## Phase 17 — Public Testnet

Public nodes, explorer, faucet, and documentation; rate limiting; spam
protection; **test units only, clearly labeled as having no monetary value.**

## Phase 18 — Governance

Initially maintain centralized engineering decisions. Long term: validator
governance, community proposals, transparent roadmap, public issue tracking.

## Phase 19 — Exchange Readiness

Do NOT contact exchanges until ALL of the following are complete: stable mainnet,
stable explorer, stable wallet, public documentation, public GitHub, production
cryptography, comprehensive testing, high code quality, active development, SDKs,
API documentation, monitoring, security documentation, threat model, reproducible
builds, deterministic consensus, release process, semantic versioning, changelog,
public roadmap, and community support.

---

## Things to Avoid (until much later, and only after legal review)

ICO, token sale, yield, staking rewards, APY, profit promises, exchange price
discussion, DEX, bridge, stablecoin, privacy coins, mixers, custody, lending,
leverage, derivatives.

## AI Development Rules

Claude and Codex should behave as Principal Engineers. Before merging any
feature: review architecture; search for simpler solutions, security weaknesses,
performance bottlenecks, race conditions, and undefined behavior; improve
documentation and test coverage; remove dead code; ensure backward compatibility
where applicable. If uncertain, prefer correctness over speed.

## Success Criteria

XRIQ should demonstrate production-quality engineering, excellent documentation,
high reliability, strong security practices, an active developer ecosystem, a
stable public network, transparent governance, a conservative legal posture, and
professional release management — a mature codebase that could withstand rigorous
technical due diligence by major exchanges. The long-term objective is technical
credibility; listing decisions remain entirely at each exchange's discretion.
