# XRIQ Phase 3 Public Testnet Plan

Status: active Phase 3 planning checkpoint. No public network is operated. Test
only.

This document opens Phase 3 of `docs/XRIQ_PRODUCTION_ROADMAP.md` (Public Testnet).
It is a planning and acceptance-criteria checkpoint only: it does not launch a
public network, issue value, or authorize any economic feature. It builds on the
completed Phase 2 staging-devnet (deployed on GCP) and on the engineering
decisions in `docs/XRIQ_PHASE3_DECISIONS.md`. All work stays subject to
`docs/XRIQ_LEGAL_RISK_REDUCTION.md`.

This document is not legal, financial, securities, tax, banking, or compliance
advice. A public testnet has **no economic value**; do not attach investment,
token-sale, yield, price, or exchange-listing language to it.

## Goal

Expose a **test-only** public XRIQ network with no monetary value: at least two
independent nodes that sync and keep producing valid blocks, a public read
explorer/API, a faucet dispensing valueless test coins, and monitoring/abuse
controls — behind conservative disclaimers.

## Non-Negotiable Guardrails

- Test only: no public mainnet, no real value, no investment/yield/price/listing
  language. Allowed framing is "public test network", "test coins with no
  monetary value", "experimental protocol" (see
  `docs/XRIQ_LEGAL_RISK_REDUCTION.md`).
- No DEX, tokenomics, token sale, airdrop, bridge, custody, stablecoin, or
  privacy protocol. These stay blocked per `docs/XRIQ_PHASE3_DECISIONS.md` and
  are separate regulated-product review items — **being a DEX does not lower
  legal requirements**; a project-operated DEX generally raises securities,
  money-transmission, and sanctions exposure and requires qualified legal review
  first.
- Consensus stays deterministic single-authority for the testnet; peer admission
  is allowlist-first. No proof-of-stake, validator rewards, or slashing.
- No browser-held private keys, seed phrases, mnemonics, or custody material.
- The move from public testnet toward any production-candidate/mainnet, or any
  economic/DEX/token feature, is gated behind the roadmap **Phase 4 security,
  legal, and economic review**.
- No cloud provider change (GCP is selected); apply remains human-operated.

## Phase 3 Acceptance Criteria

Mirrors the roadmap Phase 3 exit criteria:

- At least two independent nodes can sync and continue producing valid blocks.
- Testnet reset/recovery procedure is documented and exercised.
- Testnet coins are clearly non-production and non-investment.
- The public testnet API is rate-limited and monitored.
- Backup/restore and rollback drills pass on GCP.

## Milestones (narrow, independently shippable)

1. **Networked multi-node sync (the crux).** A TCP peer protocol so two or more
   `xriq-node` instances relay blocks and pending transactions and stay in sync.
   Build on the existing in-process peer-block import and validation
   (`docs/XRIQ_PHASE3_DECISIONS.md`): every imported block must pass canonical
   root, state-root, and test-only signature checks before commit. Allowlist peer
   admission only.
2. **Peer identity and discovery.** A node identity model and a static peer list
   first, then bounded discovery. No open/anonymous admission yet.
3. **Explicit testnet chain/validator configuration.** A distinct testnet chain
   id and genesis separate from local/staging, with no public economics set.
4. **Faucet.** Dispense valueless test coins with strict rate/abuse limits, a
   reset procedure, and no monetary-value language.
5. **Public testnet explorer and wallet flow.** Extend the existing read-only UI;
   no key material in the browser.
6. **Monitoring, abuse controls, and rate limiting** for the public API (extend
   the Cloud Armor edge and the observability layer).
7. **Public testnet documentation and disclaimers** with conservative,
   non-investment framing.
8. **Testnet deployment topology on GCP** (multi-node), extending `infra/gcp/`.
9. **Testnet reset/recovery plus backup/restore/rollback drills.**

## Hard Scope Boundaries

Do not, without the matching roadmap phase and explicit human + legal approval:

- operate a public mainnet or attach any monetary value to testnet coins;
- build DEX, liquidity pool, token listing, bridge, wrapped/synthetic asset,
  custody, stablecoin, tokenomics, or public validator economics;
- add investment, yield, price-support, buyback, or exchange-listing claims;
- implement privacy/shielded transfers, mixers, or custom cryptography;
- generate or store browser-held key material;
- change the cloud provider or run `terraform apply`/deploys from repo automation;
- create, move, or delete tags from a generic continue.

## Security And Legal Gate

Before promoting the testnet toward production-candidate/mainnet, or enabling any
economic/DEX/token feature, complete the roadmap Phase 4 review: consensus threat
model, cryptography and key-management review, node/network abuse review, legal
and AML/CFT/sanctions/securities review, tokenomics/governance review, and an
external security audit. A separate public repository with a license, security
policy, and contribution policy is a precondition (see
`docs/XRIQ_LEGAL_RISK_REDUCTION.md`).

## Recommended First Milestone

Start with **networked multi-node sync** (milestone 1): it is the technical crux
and the primary Phase 3 exit criterion (two independent nodes syncing and
producing valid blocks), and it is buildable now on the existing in-process
import/validation without any public-economics or legal-gated feature.

## Cheap Verification

```bash
python scripts/xriq_phase3_plan_check.py
```

This guard validates the plan markers, scope boundaries, and cross-document
references. It does not run Rust tests, create tags, touch cloud resources, or
change runtime state. Also keep the prior guards green:

```bash
python scripts/xriq_production_roadmap_check.py
python scripts/xriq_private_devnet_wrapup_check.py
```
