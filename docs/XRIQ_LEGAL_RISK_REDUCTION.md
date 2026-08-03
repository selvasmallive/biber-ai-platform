# XRIQ Engineering, Governance, and Risk-Reduction Policy

Version: 2.0

Status: controlling engineering and deployment-policy document
Governance model: permissioned and administrator-managed

## 1. Purpose and document authority

This document defines the engineering, governance, operational, and deployment
rules for XRIQ. It replaces the former legal-review-driven hard-gate model with a
phased deployment model administered by the Network Governance Authority. XRIQ
deployment is governed by the active deployment phase, and implementations MUST
enforce that phase in protocol behavior, operational controls, and public-facing
software.

This document is not legal, tax, accounting, compliance, or regulatory advice.
 Qualified advice and
independent review remain useful risk-reduction measures, but neither is made an
absolute engineering prerequisite by this document.

If another project document conflicts with this Version 2 policy, this document
controls deployment-phase behavior unless the Network Governance Authority adopts
a later, expressly superseding policy through auditable change control.

## 2. Definitions

- **Network Governance Authority (NGA):** the protocol governance role initially
  exercised by the company administrator.
- **Active deployment phase:** the currently authorized Phase 1, 2, or 3 policy
  recorded in canonical network configuration.
- **Approved wallet:** an address whose relevant role and permissions are active in
  the authoritative approval registry.
- **Company wallet:** a company-owned wallet approved by the NGA.
- **Partner organization:** an external organization approved by the NGA for Phase 2.
- **Partner wallet:** a wallet individually approved for an active partner
  organization.
- **System address:** a pool, router, settlement, treasury, fee, burn, mint, or other
  protocol address explicitly required for an authorized transaction path.
- **Beneficial holding:** economic ownership or control of XRIQ, whether direct or
  through an intermediary or contract.
- **Genesis supply:** the total quantity of XRIQ created at network genesis.
- **Genesis allocation:** the distribution of genesis supply among named accounts.
- **Initial exchange ratio:** the ratio implied by the quantities initially deposited
  into an approved XRIQ liquidity pool.
- **Ongoing market price:** the exchange rate produced after activation by the DEX or
  AMM mechanism, liquidity, fees, and permitted trading activity.

RFC 2119-style terms `MUST`, `MUST NOT`, `SHOULD`, and `MAY` are normative.

## 3. Network Governance Authority

The NGA is initially exercised by the company administrator. It MUST NOT be assumed
that a single personal administrator key will permanently control the network. The
role MAY later be implemented through a multisignature account, a governance
council, another formally approved governance mechanism, or a decentralized
governance system.

The NGA controls or authorizes:

- the active deployment phase and every phase transition;
- company-wallet, partner-organization, and partner-wallet approval;
- wallet suspension and revocation;
- genesis configuration, genesis supply, and genesis allocations;
- company treasury configuration;
- permitted liquidity pools and paired cryptocurrencies;
- transfer-policy configuration;
- protocol upgrades;
- emergency pause and recovery actions; and
- administrative role assignment.

Every governance action MUST be authenticated, authorized, logged, timestamped,
attributable to an accountable actor or governance body, and auditable. Privileged
roles MUST follow least privilege and separation of duties where practical. A change
of governance mechanism MUST preserve an auditable chain of authority.

## 4. Deployment phases

### Phase 1 — Internal Company Production

XRIQ MAY operate in production with real economic value. Only company-owned,
NGA-approved wallets MAY hold, receive, transfer, or swap XRIQ. The company MAY
operate production validators, nodes, APIs, wallets, treasury wallets, monitoring,
backups, and recovery infrastructure.

The company MAY create a real-value liquidity pool paired with an NGA-approved
cryptocurrency. DEX swaps are allowed only when all wallet, address-path, and
transfer-authorization requirements are satisfied. No unauthorized external wallet
MAY receive, beneficially hold, or retain XRIQ.

### Phase 2 — Partner Network

Approved external organizations MAY participate. Each organization MUST be approved
by the NGA, and every participating partner wallet MUST be individually approved and
linked to that organization. Company and active partner wallets MAY hold, transfer,
and swap XRIQ according to the active policy.

Organization and wallet approvals MAY expire and MUST be suspendable and revocable.
DEX swaps remain permissioned and subject to the active transfer policy, including
system-address rules.

### Phase 3 — Public Network

Public participation is disabled by default. Phase 3 is optional and MUST NOT be
assumed to activate automatically. The NGA MAY activate it only through the
documented governance process after satisfying the Phase 3 deployment gate.

The NGA MAY remove, relax, or retain wallet restrictions according to the configured
public-network policy. Activation and every later policy change MUST be auditable and
treated as a formal network configuration change.

## 5. Phase-transition procedure

A phase transition MUST include:

1. a written proposal identifying the target phase, policy changes, risks, and owner;
2. evidence that target-phase engineering, security, governance, and operational
   criteria are satisfied;
3. approval under the current governance mechanism;
4. staged testing, including authorization paths, failure modes, emergency pause,
   and rollback from an incorrectly activated phase;
5. a configuration version, activation time or height, and integrity identifier;
6. advance operational communication to affected operators and partners;
7. authenticated activation with immutable or tamper-evident audit records; and
8. post-activation verification and monitoring.

A transition MUST fail closed. An incomplete, ambiguous, or unauthenticated phase
configuration MUST NOT broaden participation. Rollback procedures MUST preserve
ledger integrity and MUST NOT silently erase completed transfers.

## 6. Wallet and organization approval

Approval records MUST identify wallet address, owner class, organization where
applicable, allowed roles, effective time, expiry or review date, status, approver,
and reason. Phase 1 approvals MUST be limited to verified company-owned wallets.
Phase 2 partner approval MUST include organization due diligence appropriate to the
company's risk program, an accountable contact, wallet-control verification, and
separate approval of each wallet.

Approval, suspension, revocation, and reactivation MUST be authenticated and logged.
Revocation MUST take effect consistently across nodes, APIs, routers, pools, and
pending-transaction processing. Pending activity MUST be re-evaluated at execution or
settlement time; prior admission to a mempool or interface MUST NOT guarantee later
execution. Periodic review and approval expiry SHOULD be configured for partners.

## 7. Genesis and supply governance

The NGA determines the genesis supply and initial allocation. Genesis configuration
MUST specify chain identity, supply, allocations, authority keys or roles, treasury
and fee addresses, transfer-policy bootstrap state, and a reproducible integrity
hash. No deployment tooling MAY substitute test-only keys or allocations into a
value-bearing network.

Changes to genesis supply or allocation create a new network identity unless the
protocol explicitly defines and governs another mechanism. Minting, burning,
emissions, rewards, or supply changes after genesis MUST be separately authorized,
bounded by protocol rules, and auditable. Token mechanisms SHOULD serve documented
network functions such as fees, spam resistance, and validator operations rather
than promotional price support.

## 8. Treasury governance

Treasury wallets MUST be company wallets or expressly governed system addresses.
Treasury configuration MUST define permitted assets, transaction limits, approval
thresholds, signing roles, destination policy, reconciliation, and emergency
controls. High-value actions SHOULD require multisignature approval and separation
between proposal, approval, and execution.

Treasury keys MUST use production-grade custody controls appropriate to value at
risk. Treasury transfers, liquidity contributions and withdrawals, fee receipts,
minting, burning, and administrative movements MUST follow the active wallet policy
and generate complete audit records.

## 9. Permissioned DEX architecture

XRIQ is transferable only according to the active deployment-phase policy. During
Phases 1 and 2, only approved wallets MAY beneficially hold or receive XRIQ. A public
DEX contract may be visible and callable on-chain, but unauthorized swaps MUST fail.
Authorization MUST be enforced in protocol or token-transfer logic and MUST NOT rely
only on a website, wallet, router UI, or off-chain precheck.

An AMM swap is not a direct buyer-to-seller transfer. A trader interacts with a
router or pool, and the actual transfer path may include the trader, router, pool,
settlement address, treasury, and fee recipient. Authorization MUST cover every
address that participates in that path. The pool, router, settlement addresses,
treasury wallets, fee recipients, and other required protocol addresses MUST be
explicitly represented in the authorization design.

The implementation MUST prevent policy bypass through direct pool calls, alternate
routers, transfer proxies, callback contracts, flash-swap paths, delegated transfers,
or unapproved recipients. Public-facing software MUST disclose active restrictions
and MUST NOT imply that a pool is permissionless while an allowlist remains active.

Because transfer behavior depends on the actual chain and DEX implementation, the
permissioned design requires implementation validation for the selected architecture;
this document alone does not establish correctness.

## 10. Liquidity-pool governance

Only pools and paired cryptocurrencies approved by the NGA MAY be used. An approval
MUST identify chain, factory, pool, router, token contracts or native assets, fee tier,
oracle assumptions, allowed system addresses, liquidity limits, treasury source, and
authorized operators. The NGA MAY authorize the company's initial liquidity
contribution.

Liquidity addition and removal MUST obey wallet, treasury, and system-address rules.
Pool creation or migration MUST be change-controlled. Monitoring SHOULD cover depth,
price impact, slippage, reserves, abnormal routing, fee flows, oracle divergence,
contract upgrades, and unauthorized addresses. No operator may promise redemption,
price support, liquidity depth, or execution quality not technically guaranteed.

## 11. Token transfer and authorization rules

Approval checks MUST apply consistently to `transfer`, `transferFrom`, minting,
burning, liquidity addition, liquidity removal, fee distribution, treasury
operations, and every equivalent native-chain transaction path. Checks MUST evaluate
the active phase and current approval state at execution time.

In Phases 1 and 2:

- an ordinary sender and recipient MUST be active approved wallets;
- an allowance MUST NOT let a spender bypass sender, owner, recipient, or phase rules;
- an approved sender MUST NOT transfer to an unapproved recipient;
- an unapproved sender MUST NOT transfer to an approved recipient;
- mint destinations and liquidity-withdrawal recipients MUST be authorized; and
- suspension, revocation, and emergency pause MUST fail closed.

Any exemption for a system contract MUST be narrowly scoped to a specific address,
role, direction, function, phase, and network. Exemptions MUST be documented, tested,
reviewable, and incapable of turning a router, proxy, callback, or pool into a general
transfer bypass.

Required validation includes approved sender and recipient; approved trader through
the approved router; unapproved trader; both one-sided approval combinations; direct
pool transfer and invocation; alternate router; transfer proxy; liquidity addition
and removal; fee collection; treasury transfer; revocation during pending activity;
emergency pause; phase transition and rollback; allowance and `transferFrom`;
callback and flash-swap paths where supported; system-address exemption misuse; and
administrator-key compromise simulation.

## 12. Token-value principles

Genesis supply, genesis allocation, initial exchange ratio, and ongoing market price
are distinct concepts. The NGA sets genesis supply and allocations and may authorize
the company's initial liquidity contribution. The initial pool exchange ratio results
from the quantities of XRIQ and the paired cryptocurrency deposited in the pool; an
administrator does not simply declare an independently enforceable market value.

After activation, the exchange rate changes according to the DEX or AMM mechanism,
liquidity depth, fees, and permitted swaps. A quoted pool price does not guarantee
that the entire token supply can be redeemed at that price. Product materials MUST
explain liquidity and price-impact limitations and MUST NOT promise profit, yield,
price floors, buybacks, passive income, guaranteed value, or appreciation.

## 13. Custody and key-control principles

The architecture SHOULD minimize custody and prefer user- or organization-controlled
keys within the active approval policy. Company-operated wallets and infrastructure
MUST define who controls each key, how it is generated, stored, backed up, rotated,
recovered, and revoked. Production keys MUST NOT be embedded in source code, logs,
images, or default configurations.

Administrative, validator, treasury, wallet-approval, and emergency roles SHOULD use
separate keys and least privilege. Hardware-backed storage, multisignature approval,
offline recovery material, access review, compromise drills, and dual control SHOULD
be applied in proportion to risk. A hosted or custodial service introduces additional
obligations and MUST receive its own risk assessment and NGA authorization.

## 14. Privacy and selective disclosure

XRIQ SHOULD favor transparent, auditable behavior for the permissioned phases. Any
future privacy design SHOULD support selective disclosure using viewing keys,
transaction disclosures, audit receipts, or comparable read-only proof without
revealing spend authority.

Custom zero-knowledge systems, ring signatures, stealth-address systems, mixers, or
privacy pools MUST NOT be deployed without architecture-specific cryptographic,
security, operational, and governance review. Privacy features MUST NOT be designed
or marketed for sanctions evasion or concealment of illicit finance. 

## 15. Open-source and decentralization roadmap

Open-source releases SHOULD include an appropriate license, security policy,
contribution process, vulnerability-disclosure process, reproducible tests, and no
secrets. Publishing code is not deployment authorization.

XRIQ MUST be described accurately as permissioned and administrator-managed while
the NGA controls approvals, liquidity, upgrades, validators, treasury, emergency
actions, or phase transitions. Decentralization is a roadmap possibility, not a
current property. Any transition to multisignature, council, formal governance, or
decentralized governance MUST document authority, upgrade control, capture and
collusion risks, emergency powers, and migration procedures.

## 16. Product and messaging principles

Product and generated text SHOULD frame XRIQ as a functional network asset used for
protocol operation, fees, spam prevention, validator mechanics, or technical access.
It MUST accurately disclose the active phase, participant restrictions, governance
control, pool restrictions, and material operational limits.

Messaging MUST NOT describe XRIQ as guaranteed value, an investment, passive income,
APY, yield, a moonshot, a price floor, profit sharing, dividends, the safest
investment, or guaranteed to list. Restricted trading MUST NOT be presented as proof
of legal or regulatory status. Sanctions and illicit-finance risks SHOULD be addressed
in service-layer onboarding, monitoring, and incident procedures appropriate to the
deployment.

## 17. Operational risk controls

Each active phase MUST have documented owners and tested procedures for monitoring,
alerting, reconciliation, access review, backups, restoration, incident response,
vulnerability handling, key compromise, emergency pause, recovery, and upgrades.
Logs MUST be access-controlled, integrity-protected, retained under an approved
policy, and sufficient to reconstruct governance and value movements.

Operators MUST monitor consensus health, validator identity, transfer denials,
approval changes, treasury activity, pool behavior, RPC abuse, configuration drift,
and backup success. Recovery tests MUST verify both data integrity and authority-key
availability. Dependencies and cryptographic components SHOULD receive ongoing
review. An independent assessment MAY be commissioned as a risk-reduction measure.

## 18. Deployment gates

XRIQ deployment is governed by the active deployment phase. The Network Governance
Authority may authorize progression after confirming that the documented engineering,
operational, governance, and security criteria for the target phase are satisfied.

### Phase 1 gate

The NGA MUST confirm company-controlled production infrastructure, production
cryptography, approved company wallets, treasury-key protection, tested transfer
authorization, restricted swaps, approved liquidity, monitoring, backups and restore,
administrative audit logs, incident response, and emergency procedures.

### Phase 2 gate

In addition to Phase 1, the NGA MUST confirm organization onboarding, partner-wallet
verification, separation of company and partner permissions, approval expiry or
periodic review, suspension and revocation, increased monitoring, rate limits and
abuse controls, and partner incident communications.

### Phase 3 gate

In addition to applicable earlier controls, the NGA MUST confirm public-network
scalability, public attack-surface and RPC review, permission-transition and rollback
testing, governance security, broader incident response, public vulnerability
handling and disclosure, and decentralization and upgrade-control decisions.

## 19. Codex and BIBER instructions

Future Codex and BIBER sessions MUST:

- determine the active deployment phase from authoritative configuration and docs;
- implement only capabilities allowed by that phase and fail closed when it is unclear;
- enforce authorization in protocol or token logic, not only in user interfaces;
- preserve the distinction among ordinary approved wallets and narrowly scoped system
  addresses;
- test every transfer path and the required adversarial cases in Section 11;
- avoid investment, token-sale, guaranteed-value, listing, and yield marketing claims;
- record material governance, risk, and deployment decisions in
  `docs/CODEX_HANDOFF.md`;
- update related specifications when genesis, approvals, DEX paths, or phase policy
  changes; and
- report conflicts with this policy instead of silently weakening controls.

Codex and BIBER MUST NOT refuse all real-value, DEX, liquidity, or production work
solely because legal review or an external audit has not occurred. They MUST refuse
or constrain capabilities prohibited by the active phase or lacking the applicable
deployment authorization. Separate features such as public sales, custody services,
bridges, mixers, stablecoins, fiat services, or customer-fund control require explicit
scope, controls, and authorization.

## 20. Change control and version history

Material changes MUST identify an owner, rationale, affected phases, compatibility
impact, security assessment, migration and rollback plan, approval record, and
effective version or height. Changes to genesis, supply, treasury, transfer policy,
system-address exemptions, liquidity, governance roles, upgrades, emergency powers,
or phase MUST receive formal NGA approval and auditable activation.

| Version | Date | Summary |
|---|---|---|
| 1.x | Historical | Private-development legal-risk guardrail with legal and external-review hard gates. |
| 2.0 | 2026-08-02 | Replaced hard gates with NGA-administered phased deployment; added wallet, genesis, treasury, permissioned DEX, liquidity, transfer, operational, and change-control rules. |

## 21. Reference sources

These sources are retained as risk-awareness references. They may change and MUST be
verified when relied upon; inclusion is not a legal conclusion about XRIQ.

- SEC, [Transactions Involving Crypto Assets](https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/transactions-involving-crypto-assets)
- SEC, [Crypto Assets and the Federal Securities Laws](https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/crypto-assets-federal-securities-laws)
- SEC, [Application of the Federal Securities Laws to Certain Types of Crypto Assets and Certain Transactions Involving Crypto Assets](https://www.sec.gov/rule-release/33-11412)
- FinCEN, [Application of FinCEN's Regulations to Persons Administering, Exchanging, or Using Virtual Currencies](https://www.fincen.gov/resources/statutes-regulations/guidance/application-fincens-regulations-persons-administering)
- U.S. Treasury, [2023 DeFi Illicit Finance Risk Assessment](https://home.treasury.gov/news/press-releases/jy1391)
- IRS, [Final regulations and related guidance for reporting by brokers on sales and exchanges of digital assets](https://www.irs.gov/newsroom/final-regulations-and-related-irs-guidance-for-reporting-by-brokers-on-sales-and-exchanges-of-digital-assets)
- OFAC, [Sanctions Compliance Guidance for the Virtual Currency Industry](https://ofac.treasury.gov/recent-actions/20211015)
- Project references: `docs/SECURITY_REVIEW.md`,
  `docs/XRIQ_KEY_DERIVED_ACCOUNTS.md`,
  `docs/XRIQ_EXCHANGE_READINESS_CHECKLIST.md`,
  `docs/XRIQ_TESTNET_CHAINSPEC.md`, and `docs/CODEX_HANDOFF.md`.
