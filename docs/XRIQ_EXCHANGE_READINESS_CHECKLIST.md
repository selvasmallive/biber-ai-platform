# XRIQ Exchange-Readiness Compatibility Checklist

Status: future-facing engineering checklist for private development.

This document is not legal advice, exchange-listing advice, token-sale advice,
or a statement that XRIQ is listing-ready. It exists so future Codex and BIBER
sessions keep the protocol directionally compatible with later exchange review
while the current work remains limited to the private devnet.

XRIQ is not currently ready for a centralized exchange listing.

## Must-Follow Rule

Do not claim, imply, or prepare public listing readiness from the private-devnet
prototype alone. Before any exchange, broker, market maker, liquidity provider,
custodian, wallet provider, or public trading venue is contacted, the project
must complete the security, legal, compliance, tokenomics, operations, custody,
and exchange-specific review gates in this document and in
`docs/XRIQ_LEGAL_RISK_REDUCTION.md`.

## Current Allowed Scope

The current private-devnet work may stay directionally compatible by building:

- transparent account, block, transaction, mempool, and explorer visibility
- deterministic chain replay and storage validation
- stable local node and wallet runner commands
- versioned chain, address, signature, and proof metadata
- clear test-only genesis and fee configuration
- reproducible Rust tests, smoke scripts, and documented artifacts
- docs that state public supply, emissions, governance, privacy, legal review,
  and listing readiness are incomplete

This scope supports engineering maturity. It does not approve trading,
liquidity, fundraising, market making, custody, or public launch.

## Hard Blocks

Future sessions must not implement or prepare any of these without explicit
review status recorded in the docs:

- public mainnet or public token distribution
- token sale, airdrop, bounty token campaign, liquidity mining, or paid
  whitelist
- exchange listing application, listing pitch, market-maker onboarding, or
  liquidity program
- project-operated DEX, hosted swap desk, broker, dealer, order router, or
  matching service
- custodial wallet, managed validator keys, exchange custody adapter, or pooled
  staking service
- fiat on-ramp, fiat off-ramp, stablecoin, payment processor, or remittance
  flow
- bridge, wrapped asset, synthetic asset, BTC reserve, or cross-chain custody
  product
- Monero-style mandatory privacy, mixer, tumbler, default privacy pool, or
  sanctions-evasion feature
- public marketing that frames XRIQ as an investment, profit opportunity,
  yield source, price-appreciating asset, or soon-to-list asset

## Compatibility Gates

### Gate 1: Private-Devnet Engineering

Current target. Required before claiming a useful local prototype:

- deterministic genesis config for private tests
- canonical transaction hashes and block hashes
- deterministic state roots and transaction roots
- replayable local storage with corruption and gap rejection
- local wallet transfer drafts
- local mempool preview before block production
- local block production from wallet drafts
- explorer overview, block detail, account detail, and mempool detail
- smoke script that verifies the local flow on Vast
- no production custody, no public supply, and no public listing claim

### Gate 2: Public Testnet Candidate

Blocked for now. Required before any community or public testnet:

- real reviewed key management and signature verification
- documented chain id, address format, transaction format, and RPC versioning
- peer identity, allowlist, and network protocol design
- reorg/finality model and confirmation guidance
- persistent state snapshots or efficient replay strategy
- fuzz/property tests for parsing and validation paths
- threat model, dependency audit, and external security review plan
- open-source license, security policy, contribution policy, and vulnerability
  disclosure process
- written confirmation that public tokenomics, distribution, and legal review
  remain blocked

### Gate 3: Public Mainnet Candidate

Blocked for now. Required before a public network:

- production-grade node operations and monitoring
- audited wallet/key-management story
- audited consensus, storage, ledger, and networking behavior
- incident response and emergency upgrade process
- public tokenomics, supply, fee, governance, and validator documents
- legal, tax, AML/CFT, sanctions, securities, commodities,
  consumer-protection, privacy, and cybersecurity review
- selective-privacy design review if any shielded feature exists
- clear public messaging that avoids investment, yield, and listing promises

### Gate 4: Centralized-Exchange Review Candidate

Blocked for now. Required before any listing outreach:

- completed Gate 3 items
- stable deposit and withdrawal integration documentation
- clear confirmation/finality and reorg guidance
- exchange-facing node operations guide
- chain indexer or explorer API suitable for reconciliation
- address, memo/tag if applicable, transaction, and fee documentation
- wallet and custody integration review
- blockchain analytics, sanctions-screening, and monitoring integration plan
- market-quality, liquidity, and market-integrity plan reviewed by qualified
  advisors
- legal listing opinion and exchange-specific requirements review
- support, incident, upgrade, and chain-halt communication plan

## Directional Engineering Backlog

These items are compatible with the private-devnet MVP because they improve
future reviewability without launching a market:

- keep `xriq-node` file-backed commands deterministic and scriptable
- add minimal HTTP/RPC serving only when the local runner flow is stable enough
  to expose safely
- document confirmation/finality semantics before public integrations
- add stable JSON output for explorer/account/block/mempool views before
  building external clients
- add chain config export so future services can validate chain id, genesis,
  fee policy, and address rules
- add operational runbooks for backup, restore, replay, monitoring, and
  incident response
- add security docs before any public repository split or public testnet

## Codex And BIBER Instructions

Future Codex and BIBER sessions must:

- keep XRIQ directionally compatible with future exchange review, but never
  claim current listing readiness
- choose transparent, auditable MVP behavior over default opacity
- keep privacy future-facing and selective-disclosure oriented
- prefer private-devnet tests, docs, and deterministic tooling over public
  market-facing features
- update `docs/CODEX_HANDOFF.md` when any item materially changes readiness
- refresh this checklist against target-exchange and legal-review requirements
  before any public listing work

