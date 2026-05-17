# XRIQ Legal-Risk Reduction Design Principles

Status: project design guardrail for private development.

This document is not legal advice, tax advice, compliance advice, or a public
launch plan. It is a conservative engineering checklist that future Codex and
BIBER sessions must follow until qualified legal, tax, AML, sanctions,
securities, commodities, consumer-protection, and cybersecurity reviewers approve
a different path in writing.

## Must-Follow Rule

When building XRIQ, choose the design that reduces legal, compliance, consumer,
and security risk, even if it slows the roadmap. If a requested feature conflicts
with this document, pause the feature and record the issue in the handoff instead
of implementing it.

## Current Regulatory Anchors

Use these sources as orientation, then verify current law before any public
release because crypto regulation changes quickly:

- SEC: crypto assets may be involved in securities transactions when sold as
  investment contracts, especially where purchasers expect profits from the
  essential managerial efforts of others.
- SEC/CFTC: a non-security crypto asset can still be subject to other regimes,
  including commodities, anti-fraud, and market-integrity rules.
- FinCEN: administrators and exchangers of convertible virtual currency can be
  money transmitters depending on whether they accept/transmit, buy/sell, issue,
  redeem, or exchange value as a business.
- U.S. Treasury: DeFi services can create AML/CFT and sanctions risk, and
  claiming decentralization does not by itself remove obligations.
- IRS/Treasury: digital asset broker reporting focuses on custodial or
  possession-taking broker activity in the current final rules, while future
  rules for decentralized or non-custodial brokers may change obligations.
- OFAC: virtual-currency projects and services need sanctions-risk awareness,
  especially if they operate hosted services, interfaces, relays, bridges, or
  other infrastructure.

## Hard No-Go Items Before Review

Do not build, ship, market, or enable any of the following for XRIQ without
separate written review:

- public mainnet
- token sale, presale, ICO, IDO, SAFT, fundraiser, investment round tied to XRIQ
  tokens, or paid whitelist
- public airdrop, referral reward, promotional reward, bounty token campaign, or
  liquidity-mining campaign
- promise or implication of profit, yield, passive income, price support,
  buyback value, guaranteed rewards, or investment utility
- centralized exchange, broker, dealer, market maker, hosted swap desk, or
  project-operated order-matching service
- custodial wallet, custody service, managed validator key service, escrow,
  pooled staking, hosted treasury, or customer fund control
- fiat on-ramp, fiat off-ramp, payment processor, merchant settlement, remittance
  flow, or stablecoin issuance
- bridge, wrapped asset, synthetic asset, cross-chain custody, or BTC reserve
  product
- mixer, tumbler, stealth transfer, default privacy pool, sanctions-evasion
  feature, or tool primarily useful for hiding source/destination of funds
- public DEX launch, liquidity-pool launch, token listing, or market-liquidity
  support
- governance that gives token holders rights to revenue, profits, dividends,
  assets, debt, equity, or management of a business entity

## Token And Supply Principles

- XRIQ's native asset should be designed as a functional network asset, not as
  an investment product.
- Token language must focus on protocol operation, fees, spam prevention,
  validator mechanics, and technical access.
- Do not describe XRIQ as a store of value, profit opportunity, appreciating
  asset, dividend-bearing token, passive-income asset, or way to get rich.
- Do not finalize public supply, emissions, burns, treasury allocation, validator
  rewards, or public distribution until legal and economic review is complete.
- Treat burns, fees, and validator rewards as technical mechanisms only; do not
  market them as price-support or yield mechanisms.
- If validator rewards are ever added, design them as protocol compensation for
  active network work, not passive investment yield.

## DEX And Interoperability Principles

The lowest-risk early posture is protocol research, not project-operated
exchange activity.

- Prefer non-custodial, user-directed, non-discretionary software designs.
- Prefer atomic-swap research and open protocol specifications before bridges or
  wrapped assets.
- Do not let XRIQ project services take possession of user assets.
- Do not operate liquidity pools, route orders, guarantee execution, set market
  prices, custody paired assets, or run a hosted market-making service.
- Do not integrate sanctioned addresses, mixers, ransomware-linked services, or
  known illicit-finance infrastructure.
- Any public DEX interface, aggregator, relayer, bridge, or liquidity program is
  a separate regulated-product review item, not a default protocol feature.

## Decentralization And Open-Source Principles

- Keep XRIQ private-devnet-only until the core protocol, wallet, and node
  security posture are credible.
- Plan a separate public XRIQ repository before community devnet or public trust
  work, but do not treat publishing code as public launch approval.
- Open-source code should include a license, security policy, contribution
  policy, risk disclaimer, reproducible tests, and no secrets.
- Do not claim decentralization while the project or a small team controls
  issuance, validators, upgrade keys, hosted endpoints, liquidity, or user asset
  flows.
- Any upgrade key, validator admission, treasury control, or emergency pause
  authority must be disclosed and reviewed before public use.

## Product And Messaging Principles

All public-facing and generated text must avoid investment framing.

Allowed framing:

- private devnet
- experimental protocol
- developer tooling
- research prototype
- self-custody wallet tooling
- technical network utility

Avoid:

- guaranteed value
- investment
- passive income
- APY
- yield
- moonshot
- price floor
- buyback
- profit sharing
- dividends
- official listing soon
- safest investment

## Compliance-Aware Engineering Gates

Before any public XRIQ token, DEX, wallet, validator, bridge, listing, or
mainnet step, create and review:

- jurisdiction list and launch entity plan
- securities analysis
- commodities/market-integrity analysis
- money-transmission/MSB analysis
- sanctions and AML/CFT risk assessment
- tax reporting analysis
- consumer-protection and marketing review
- data/privacy review
- open-source license and contribution review
- threat model, dependency audit, cryptography review, and external security
  audit
- incident response, vulnerability disclosure, and emergency upgrade process

## Codex And BIBER Instructions

Future Codex and BIBER sessions must:

- keep XRIQ public-launch work blocked until this document's gates are satisfied
- update this document when legal-risk assumptions change
- avoid generating investment, token-sale, exchange-listing, or yield-marketing
  content
- refuse to implement custody, exchange, bridge, mixer, stablecoin, or public
  sale features without explicit review status recorded in docs
- prefer private-devnet code, tests, docs, and security hardening over public
  market-facing features
- record legal-risk-sensitive decisions in `docs/CODEX_HANDOFF.md`

## Reference Sources

- SEC, "Transactions Involving Crypto Assets":
  https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/transactions-involving-crypto-assets
- SEC, "Crypto Assets and the Federal Securities Laws":
  https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/crypto-assets-federal-securities-laws
- SEC, "Application of the Federal Securities Laws to Certain Types of Crypto
  Assets and Certain Transactions Involving Crypto Assets":
  https://www.sec.gov/rule-release/33-11412
- FinCEN, "Application of FinCEN's Regulations to Persons Administering,
  Exchanging, or Using Virtual Currencies":
  https://www.fincen.gov/resources/statutes-regulations/guidance/application-fincens-regulations-persons-administering
- U.S. Treasury, "Treasury Releases 2023 DeFi Illicit Finance Risk Assessment":
  https://home.treasury.gov/news/press-releases/jy1391
- IRS, "Final regulations and related IRS guidance for reporting by brokers on
  sales and exchanges of digital assets":
  https://www.irs.gov/newsroom/final-regulations-and-related-irs-guidance-for-reporting-by-brokers-on-sales-and-exchanges-of-digital-assets
- OFAC, "Sanctions Compliance Guidance for the Virtual Currency Industry":
  https://ofac.treasury.gov/recent-actions/20211015
