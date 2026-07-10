# XRIQ — Questions for Legal Counsel

Purpose: a briefing and question list to take to qualified crypto/securities +
fintech counsel. It gives counsel the project facts they need and the specific
questions the team needs answered before moving XRIQ from a private/test-only
prototype toward any public or economic activity.

This document is **not legal advice** and is **not written by a lawyer**. It is
prepared by the engineering team to make a counsel engagement efficient. It
complements `docs/XRIQ_LEGAL_RISK_REDUCTION.md` (the team's conservative
engineering guardrails) and `docs/XRIQ_PRODUCTION_ROADMAP.md`.

How to use: fill in the "Facts to confirm" placeholders, then walk counsel
through the questions in each section. Where a question's answer changes what the
team may build, note it back into `docs/XRIQ_LEGAL_RISK_REDUCTION.md`.

---

## 1. Project facts for counsel

Confirm/correct these before the engagement.

- **What XRIQ is:** an experimental account-based blockchain implemented in Rust.
  Today it is a **private, test-only devnet** — no public network, no issued
  token, no monetary value, no custody, no exchange, no DEX.
- **Current technical state:**
  - Deterministic single-authority consensus (moving toward a small multi-node
    test topology); account-based ledger; SHA-256 canonical hashing.
  - Signature verification is currently **test-only** (a placeholder verifier),
    not production cryptography.
  - The ledger is fully **transparent** (no privacy features).
  - A native unit ("XRIQ") exists only as a **functional network unit** for fees
    and spam prevention in tests; there is **no public supply, emission, sale,
    airdrop, or distribution**.
  - Wallet tooling is **non-custodial**; the browser never holds private keys,
    seed phrases, mnemonics, or signatures.
  - Deployed as a private staging environment on Google Cloud (region
    `northamerica-northeast2`, Toronto). An optional public HTTPS edge exists but
    is off by default and, when enabled, is **read-only** (rate-limited, mutations
    blocked).
- **Intended direction (subject to your advice):**
  1. A **public test network with no monetary value** (a "testnet"), including a
     faucet dispensing **valueless** test units.
  2. Possibly, later, a public production network ("mainnet").
  3. The team has expressed interest in **decentralized exchange (DEX)**
     compatibility. (See Section 8 — the team currently believes a DEX may lower
     legal requirements; we need this checked, as our own risk doc and the
     Treasury DeFi guidance suggest the opposite.)
- **People / entity — FACTS TO CONFIRM:**
  - Operator / owner: __________ (individual? company?).
  - Legal entity, if any, and country/state of formation: __________.
  - Principal place of business / residence of the operator(s): __________
    (cloud region and domain suggest Canada/Toronto — confirm).
  - Domain: `kani.network`.
  - Funding to date and any outside investors/contributors: __________.
- **Target users / geographies — FACTS TO CONFIRM:** who is intended to access a
  public testnet/mainnet, and from which countries? __________.

---

## 2. Entity, jurisdiction, and liability

1. What legal entity structure (and where) best fits a public open-source
   blockchain project operated from Canada that may reach U.S. and global users?
2. Which jurisdictions' laws most likely apply given the operator location, the
   cloud region, the domain, and globally-reachable public endpoints?
3. What personal-liability exposure do the individual operator(s) have for
   operating public nodes, a faucet, an explorer/API, and a website?
4. What contributor/committer arrangements (CLA, license) reduce liability for an
   open-source release?

## 3. Securities law (SEC / investment-contract analysis)

Context: the native unit is designed as a functional network unit, not an
investment; there is no sale, no promise of profit, and no marketing.

1. Under the Howey / investment-contract analysis, is a **valueless testnet**
   unit a security? Is a future **mainnet** native unit at risk of being treated
   as a security given the current no-sale, no-profit-promise design?
2. What specific facts (distribution method, marketing language, secondary
   trading, team retention of units) would most increase or decrease securities
   risk?
3. Does distributing units via a **faucet** (free, valueless, testnet) or a
   future **airdrop** change the analysis?
4. What documentation/disclaimers, if any, meaningfully reduce securities risk?

## 4. Commodities and market-integrity (CFTC)

1. Would the native unit likely be treated as a commodity, and what
   anti-fraud/market-manipulation obligations would attach to the project or its
   operators — including for a public testnet?

## 5. Money transmission / MSB (FinCEN, state)

1. Does operating any of the following make the project or operators a money
   transmitter / MSB (federal and/or state): running public nodes, a faucet, a
   non-custodial wallet, an explorer/API, or (future) a bridge or swap function?
2. Where is the line between **non-custodial software provision** (lower risk)
   and **accepting/transmitting value** (money transmission)?
3. What must be avoided in the wallet/faucet design to stay non-custodial?

## 6. AML/CFT and sanctions (OFAC, FinCEN)

1. What AML/CFT and sanctions obligations attach to operating a **public
   testnet** vs a **public mainnet** with value?
2. Given the Treasury DeFi risk assessment (claiming decentralization does not by
   itself remove obligations), what controls should a public interface, relay,
   faucet, or API have (e.g. geoblocking, sanctioned-address screening, IP
   controls)?
3. What sanctions-screening is expected for a faucet or any value-dispensing
   function?

## 7. Tax reporting (IRS / CRA)

1. Do the digital-asset broker reporting rules (or Canadian equivalents) create
   obligations for the project, given it is non-custodial and takes no
   possession of user assets?
2. What tax-reporting posture applies to a future faucet, airdrop, or native
   unit?

## 8. Decentralized exchange (DEX) and exchange activity

Context: the team asked whether **building a DEX lowers legal requirements**. Our
own `docs/XRIQ_LEGAL_RISK_REDUCTION.md` and the cited Treasury guidance suggest a
DEX generally **raises** exposure (securities, money transmission, sanctions) and
that "decentralized" does not remove obligations. We need this confirmed.

1. **Does building or facilitating a DEX lower or raise the project's legal
   requirements?** Please address the common misconception directly.
2. What is the difference in legal exposure between: (a) publishing open-source,
   non-custodial, non-discretionary swap software, (b) operating a hosted DEX
   interface/relayer/aggregator, and (c) running or seeding liquidity pools?
3. Which DEX-related activities would create securities, money-transmission,
   broker-dealer, or sanctions obligations for the project or operators?
4. What would need to be true (reviews, structure, controls) before any
   DEX-related feature could be built or exposed?

## 9. Custody and key management

1. What custody-related obligations attach if the project ever holds user keys or
   funds, or offers a hosted/managed signing or validator-key service?
2. Confirm that a strictly non-custodial design (no server or browser custody of
   user keys) avoids custody obligations, and what would break that.

## 10. Tokenomics, supply, and distribution

1. If a public native unit is ever created, what distribution methods (sale,
   airdrop, reward, faucet) carry the least legal risk, and which are unsafe
   without further review?
2. What governance features would risk creating investment/security
   characteristics (revenue/profit/asset/voting rights)?

## 11. Privacy features (future)

1. If selective-disclosure privacy (Zcash-like, with viewing keys/audit receipts)
   is added later, what AML/sanctions/privacy-law considerations apply, and what
   must be avoided (e.g. Monero-style mandatory privacy, mixers)?

## 12. Public testnet specifics

1. What disclaimers and terms should a **public testnet** display so that testnet
   units are clearly non-production and non-investment?
2. What faucet abuse controls, rate limits, and geoblocking are advisable?
3. Is "public test network with no monetary value" language sufficient, and what
   phrasing should be avoided?

## 13. Consumer protection and marketing

1. What public-facing language is safe vs prohibited (the team currently avoids
   "investment", "yield", "APY", "profit", "listing soon", etc.)?
2. What claims about security, decentralization, or compliance can be made given
   the current (test-only, unaudited) state?

## 14. Data protection and privacy law

1. What data-protection obligations (e.g. PIPEDA in Canada, GDPR for EU visitors)
   attach to a public explorer/API/website that may log IPs and requests?

## 15. Open-source, security, and disclosure

1. What license, security policy, vulnerability-disclosure process, and risk
   disclaimer should accompany a public open-source release?
2. What should an incident-response and emergency-upgrade posture look like from a
   liability standpoint?

---

## 16. Decisions blocked pending counsel

These roadmap steps should not proceed until counsel advises (they map to the
Phase 4 security/legal/economic review in `docs/XRIQ_PRODUCTION_ROADMAP.md`):

- Any **public mainnet** launch or attaching real value to any unit.
- Any **token sale, airdrop, reward, or public distribution**.
- Any **DEX, liquidity, bridge, custody, stablecoin, or exchange** activity.
- Any **investment/yield/price/listing** messaging.
- Any **privacy/shielded** feature exposed beyond private research.

Green-lit now (test-only, no value, no custody): the public **testnet**
engineering, multi-node networking, monitoring, and conservative documentation —
provided the testnet framing and controls above are acceptable to counsel.

---

## 17. Reference regulatory sources (from the team's risk doc)

See `docs/XRIQ_LEGAL_RISK_REDUCTION.md` for links to the SEC crypto-asset
guidance, FinCEN virtual-currency guidance, the U.S. Treasury 2023 DeFi illicit
finance risk assessment, IRS broker-reporting rules, and OFAC virtual-currency
sanctions guidance that motivate these questions.
