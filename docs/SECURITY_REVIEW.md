# XRIQ Security Review — Production Cryptography and Phased Deployment

Version: 2.0

Status: review complete; phase-specific implementation verification required

Review type: AI-assisted adversarial review plus deployment-control extension
Governance model: permissioned and administrator-managed

## 1. Executive security status

The reviewed Ed25519 migration has sound primitives, canonical signing, identity
binding, import validation, and several completed remediations. Historical findings
1–3 are fixed; finding 4 is addressed; findings 5, 6, and 8 remain documented risks;
finding 7 remains open. These statuses are not changed by this Version 2 rewrite.

The original review covered a test-only, explicitly valueless, undeployed network.
The repository now contains key-derived-account implementation recorded after that
review, but this document does not claim that the new wallet allowlist, governance,
treasury, permissioned DEX, liquidity, or phase-control mechanisms already exist or
have been verified. Those controls MUST be implemented and validated for the actual
chain and DEX architecture before their corresponding deployment gate can pass.

XRIQ deployment is governed by the active deployment phase. The Network Governance
Authority may authorize progression after confirming that the documented engineering,
operational, governance, and security criteria for the target phase are satisfied.
An independent review is recommended for additional assurance but is not an absolute
engineering prerequisite imposed by this document.

## 2. Scope

The original review covered the Ed25519 production-cryptography migration, commits
`a3118c0` through `02ccb15` (Phases 1–5c):

- `xriq-crypto`: Ed25519 `verify_strict`, the signature-scheme seam, canonical
  signing/hash encoding including `public_key`, and `SchemeSigner`;
- `xriq-node`, `xriq-consensus`, and `xriq-ledger`: submission, block production,
  peer/stored-block import and replay, and ledger application;
- `xriq-storage`, pending-transaction TSV, and API mempool codecs;
- `xriq-api`: signed submit and prepare-signing-hash routes;
- `xriq-indexer`: read-model re-verification and scheme selection;
- producer/faucet key handling, including `--producer-key-file` and the published
  test authority seed; and
- the non-custodial browser wallet in `xriq/apps/explorer-ui`.

Version 2 extends the security model to governance, genesis, treasury, wallet and
organization approvals, permissioned DEX paths, liquidity, operations, recovery, and
phase transitions. These extensions are requirements and threat-model conclusions,
not claims of completed implementation.

## 3. Methodology

Four independent adversarial reviewers originally examined disjoint surfaces:
cryptographic primitives and encoding; consensus and import/replay; serialization,
codecs, and indexer; and signed submission, keys, and browser behavior. Reviewers
produced exploit scenarios and severity ratings and distinguished vulnerabilities
from defense in depth. The integrator verified call paths in source. All four found
the original identity-binding issue independently.

For Version 2, repository documents and source references were rechecked, original
statuses were preserved, and the required phased-deployment controls were analyzed
as trust boundaries. No source-code change or new penetration test is implied.

Status terms mean:

- **Fixed:** the stated defect has a code remediation and test evidence in the
  reviewed history.
- **Addressed:** the exploitable consequence is controlled, with a residual design or
  operational consideration.
- **Documented:** known behavior or risk remains and operators MUST account for it.
- **Accepted risk:** the NGA has explicitly accepted a bounded risk; none is newly
  designated by this document.
- **Open:** remediation is incomplete.
- **Requires implementation verification:** a Version 2 control is specified but not
  established as implemented by this review.

## 4. Original findings and current status

| # | Severity (test-only → value-bearing) | Finding | Current status |
|---|---|---|---|
| 1 | Info → Critical | Signature not bound to claimed `from`/`producer` identity | **Fixed under Ed25519** for both producer and sender |
| 2 | Low → Medium | Unbounded allocation from unvalidated import prefixes | **Fixed** |
| 3 | Low → High | Browser signed server-provided hash without recomputation | **Fixed** |
| 4 | Low → Medium | Signature-dependent hash did not itself deduplicate `(from, nonce)` | **Addressed** |
| 5 | Info | Signed-submit algorithm selected from envelope; test-only path public | **Documented; unresolved for value-bearing use** |
| 6 | Info | `--signature-scheme test-only` permits follower downgrade | **Documented operator footgun; unresolved** |
| 7 | Info | `memo_hash` omitted from pending TSV | **Open** |
| 8 | Info | Wallet key-safety check is textual, not data-flow enforcement | **Documented; requires continuing verification** |

### Finding 1 — identity binding

Originally, `verify_transaction_with_scheme` and
`verify_block_header_with_scheme` in `xriq-crypto/src/lib.rs` verified against the
item's own `public_key`, while nothing required
`ed25519_address(public_key) == tx.from` or `header.producer`. An attacker could copy
an authority or victim address, insert an attacker key, recompute roots, and sign with
that key. Signature verification passed while claimed authority did not.

**Producer binding is fixed.** Under Ed25519, `validate_next_block_state` in
`xriq-node` and `replay_private_devnet_block` in `xriq-indexer` require the producer
key to derive the producer address via `producer_public_key_derives_address`; mismatch
returns `UnauthorizedProducer` before mutation. The historical negative test is
`ed25519_block_with_producer_key_not_deriving_the_authority_address_is_rejected`.
Test-only mode carries no key and deliberately skips this protection.

**Sender binding is fixed.** `docs/XRIQ_KEY_DERIVED_ACCOUNTS.md` records the migration
to key-derived Ed25519 accounts. Binding is enforced by the API preview (mismatch code
`sender_key_mismatch`), `XriqNode::submit_transaction`, the transaction loop in
`validate_next_block_state`, and indexer replay, with node/indexer mismatch represented
as `UnauthorizedSender`. Tests include
`ed25519_transaction_whose_key_does_not_derive_from_is_rejected_as_unauthorized_sender`
and `replay_rejects_ed25519_transaction_whose_key_does_not_derive_from`.

The re-review found one special seam: `fund_runner_ed25519_sender`. It is reachable
only from devnet CLI `produce-transfer-block` and `produce-pending-block`, which use
`private_devnet_runner_genesis` and reject `--network`. Public-testnet faucet paths use
`public_testnet_file_faucet_dispense_*` → `public_testnet_node`, the canonical testnet
genesis, and a genuinely funded key-derived faucet. No minting bypass was found.

### Finding 2 — allocation-bomb import denial of service

`decode_peer_blocks`, `read_block_record`, and `read_vec` in `xriq-storage` formerly
allocated from raw `u32` count/length prefixes before checking remaining input. A tiny
hostile peer message with `0xFFFFFFFF` could panic or attempt multi-gigabyte
allocation. The fix bounds prefixes using `cursor_remaining()`, returns `CorruptData`
for overlong data, and clamps capacity to remaining bytes. Test:
`decode_peer_blocks_rejects_oversized_prefixes_without_allocating`.

### Finding 3 — browser signing-hash trust

The browser formerly signed a hash returned by the prepare endpoint. A hostile server
or network intermediary controlling prepare and submit could obtain a signature over
different content. This is fixed by `src/canonical.ts`, a TypeScript port of
`transaction_signing_hash` using SHA-256 via `@noble/hashes`; the wallet recomputes and
compares before signing. `scripts/check-canonical-signing-hash.mjs`, included in
`npm run check`, cross-checks Rust and TypeScript encoders.

### Finding 4 — mempool nonce handling

Because `transaction_hash` includes a signature, a key holder can create multiple
hashes for the same body. `verify_strict` prevents classic S-malleability but not a
signer's intentional variation. The mempool already enforces one transaction for
each `(from, nonce)` through `account_nonces` and `DuplicateAccountNonce`, preventing
double debit. Replay now skips duplicate account nonces first-wins, as well as
`DuplicateTransaction`, so a crafted pending file cannot brick startup. Test:
`pending_replay_tolerates_duplicate_account_nonce_without_bricking`.

### Findings 5–8 — unresolved or documented

5. The signed-submit API historically selects Ed25519 versus test-only from the
   envelope's declared algorithm, and the test-only signature is publicly computable.
   This is acceptable only on the flag-gated, valueless, single-sender devnet path. A
   value-bearing deployment MUST pin accepted algorithms to trusted node/network
   configuration and MUST NOT expose test-only acceptance.
6. `--signature-scheme test-only` can cause a testnet follower to accept forgeable
   newly synced history. Production startup SHOULD reject test-only when genesis has
   a nonzero `authority_pubkey`; this document does not claim that check is fixed.
7. `memo_hash` is not carried in pending TSV. Hash recomputation prevents injection,
   but a future memo-bearing transaction may disappear on reload. This remains open
   and MUST be fixed before memo-bearing production transactions are supported.
8. `check-wallet-key-safety.mjs` is identifier-based lint, not data-flow proof. The
   practical non-custodial property relies on `signing.ts` retaining the seed in a
   closure. Changes to wallet signing MUST receive data-flow review and tests.

## 5. Cryptographic security

Ed25519 verification uses `verify_strict`; canonical `S`, small-order, and mixed-order
public-key checks reject known malleability cases. Malformed key and signature bytes
return `InvalidSignature` without panic. Canonical encodings length-prefix variable
fields, use distinct length-prefixed preambles for six hash domains, and encode
`Option` with a 0/1 tag.

`public_key`, `chain_id`, `nonce`, and `expires_at_height` are included in the signing
hash. `SchemeSigner` sets `public_key` before hashing and signing. Production networks
MUST pin allowed algorithms, domains, chain identity, and key types in trusted
configuration; test-only schemes and published test seeds MUST NOT be used.

## 6. Identity and authorization binding

Ed25519 sender and producer identities MUST equal the address derived from the
verified public key. Signature validity alone is insufficient. This check MUST run on
submission, block import, stored replay, index replay, and any future native execution
path before state mutation. Validator admission and production authority MUST also be
bound to the active genesis/governance configuration.

Wallet approval is an additional authorization layer: a cryptographically valid key
does not imply phase permission. Identity binding and active wallet/system-address
authorization MUST both succeed.

## 7. Transaction security

The reviewed code binds chain, nonce, expiry, and public key; recomputes transaction
hashes; and enforces account nonces. Transaction admission MUST fail closed on
malformed encoding, invalid signature, identity mismatch, expired transaction,
incorrect chain, insufficient funds, duplicate nonce, inactive phase permission,
revoked wallet, or emergency pause.

Approval MUST be rechecked at execution rather than trusted only at initial mempool
admission. Allowances and delegated `transferFrom` operations MUST authorize owner,
spender, source, recipient, system addresses, and phase. Batch and atomic transaction
behavior MUST avoid partial authorization or partial state changes.

## 8. Consensus and block-import security

The reviewed import/replay paths select the verification scheme before replay,
recompute `transactions_root`, `state_root`, and `block_hash`, and validate height,
parent, nonce, and duplicate rules. Ledger application is atomic: a cloned state is
committed only after full success. Placeholder producer signatures cannot survive
into stored blocks.

Production consensus MUST additionally validate the active validator set, phase and
policy version, governance-authorized upgrades, and any network-specific finality or
reorganization rule. Peer input MUST remain bounded before allocation. Operators MUST
detect divergent genesis, policy, and upgrade identifiers before peering or import.

## 9. Wallet and key security

The reviewed browser seed comes from the platform CSPRNG, remains in a closure, and is
not returned, persisted, logged, or transmitted; only public key and signature leave
the wallet. This property MUST be preserved and verified beyond textual lint.

Value-bearing company, treasury, validator, governance, and emergency keys MUST use
production key generation, encrypted or hardware-backed storage, access logging,
backup, rotation, and recovery. Roles SHOULD use separate keys. Browser, CLI, server,
and hardware-wallet signing MUST display or independently derive the transaction
being signed. Published seeds such as `xriq-testnet-authority-test-0001` are test-only.
`--producer-key-file` parsing is strict (64 hex characters to 32 bytes), but file
parsing alone is not production custody.

## 10. Genesis and treasury security

Genesis MUST canonically commit to chain identity, supply, allocations, authority
keys, treasury and fee addresses, bootstrap phase, and authorization-policy roots or
identifiers. The Network Governance Authority (NGA) MUST approve genesis supply and
allocations. Value-bearing deployments MUST verify reproducible genesis artifacts
out of band and MUST NOT inherit test faucet, authority, or auto-funding behavior.

Treasury controls MUST include least privilege, transaction limits, destination
policy, reconciliation, separation of proposal/approval/execution, and preferably
multisignature for material value. Genesis allocation, mint, burn, liquidity funding,
fee collection, and treasury transfer MUST be authenticated and audited.

## 11. Administrator and governance security

The NGA is the protocol governance role initially exercised by the company
administrator. It MAY migrate to multisignature, a council, another formally approved
mechanism, or decentralized governance; a single personal key MUST NOT be assumed to
remain permanent.

Governance MUST control active phase; company wallets; partner organizations and
wallets; suspension and revocation; genesis, supply, allocations, and treasury;
approved pools and paired assets; transfer policy; upgrades; emergency actions;
administrative roles; and phase transitions. Every action MUST be authenticated,
authorized, timestamped, attributable, logged, and auditable. High-impact actions
SHOULD require quorum, delay, independent confirmation, and protected break-glass
procedures.

## 12. Wallet-allowlist security

During Phases 1 and 2, only active approved wallets may beneficially hold or receive
XRIQ. The allowlist MUST be enforced in protocol or token transfer logic, not only in
an API or interface. Records MUST be versioned and include owner class, roles,
effective and expiry times, approver, status, and reason.

Approval changes MUST propagate consistently. Revocation during pending activity MUST
prevent execution where policy requires it. Cache, replica, reorganization, and node
restart behavior MUST not resurrect stale authorization. Failures and suspicious
denials MUST be monitored without leaking unnecessary personal data.

## 13. Partner-organization security

Phase 2 requires organization approval plus individual approval of every partner
wallet. Organization and wallet permissions MUST remain separable from company roles.
Onboarding MUST verify an accountable organization, wallet control, intended roles,
and operational contacts. Approval expiry or periodic review, rate limits, abuse
controls, suspension, revocation, and incident communications MUST be tested.

Compromise of one partner MUST NOT grant company privileges or another partner's
rights. Suspending an organization SHOULD suspend its wallets unless an explicitly
documented safe exception applies.

## 14. Permissioned DEX threat model

A public contract can be visible and callable while transfers remain permissioned.
Unauthorized swaps MUST fail on-chain. An AMM swap is not a direct buyer-to-seller
transfer: the actual path can include trader, allowance spender, router, pool,
callback, settlement, treasury, and fee addresses. Every actual XRIQ movement MUST be
authorized.

Threats include UI bypass, direct pool calls, alternate routers, transfer proxies,
malicious callbacks, flash swaps, delegated transfers, stale allowlists, forged phase
state, unapproved recipients, exemption abuse, reentrancy, price manipulation,
front-running, sandwiching, liquidity withdrawal, oracle manipulation, and admin-key
compromise. The system MUST fail closed without relying on the official interface.
Public software MUST disclose restrictions and MUST NOT call the pool permissionless
while allowlists apply.

## 15. Liquidity-pool security

The NGA MUST approve each pool, paired cryptocurrency, network, factory, router, fee
tier, system address, operator, liquidity limit, and treasury source. Initial pool
ratio is determined by deposited quantities; it is not a guaranteed value. Monitoring
MUST cover reserves, depth, price impact, slippage, abnormal routes, oracle divergence,
fees, upgrades, and large liquidity changes.

Liquidity addition and removal MUST enforce phase, wallet, treasury, and recipient
rules. Contract provenance and upgradeability MUST be known. Emergency handling MUST
consider whether pausing XRIQ strands paired assets or prevents safe withdrawal.

## 16. Smart-contract or protocol-address exemptions

Pools, routers, settlement addresses, fee recipients, treasury, mint, and burn
addresses require explicit treatment. An exemption MUST be narrowly scoped by chain,
address, role, direction, operation, and phase. It MUST NOT confer general holding or
transfer rights and MUST NOT be inheritable through proxies or delegate calls unless
explicitly designed and tested.

Approval checks MUST consistently cover `transfer`, `transferFrom`, mint, burn,
liquidity addition/removal, fees, treasury operations, and equivalent native-chain
paths. Upgradeable contracts MUST trigger revalidation of code identity and exemptions.

## 17. Logging and auditability

Governance, phase, wallet, organization, treasury, pool, paired-asset, exemption,
upgrade, pause, recovery, key-role, and configuration actions MUST be logged with
actor, authorization evidence, timestamp, request, prior state, result, network, and
policy version. Logs MUST be access-controlled, integrity-protected, time-synchronized,
retained, searchable, and exportable for review.

Sensitive data and secrets MUST NOT enter logs. On-chain and off-chain audit records
SHOULD be correlatable. Audit failure MUST alert and SHOULD fail closed for critical
administrative actions.

## 18. Monitoring and alerting

Production monitoring MUST cover node and consensus health, peer anomalies, failed
signature and identity checks, nonce abuse, approval denials, revocations, phase and
configuration drift, privileged actions, treasury movements, DEX routes and reserves,
RPC abuse, backup success, and log-pipeline health. Alerts MUST have owners, severity,
escalation, and tested response procedures.

Phase 2 requires partner-specific baselines and increased abuse monitoring. Phase 3
requires public RPC capacity, denial-of-service, bot, spam, exploit, and disclosure
monitoring at public scale.

## 19. Backup and disaster recovery

Backups MUST cover canonical chain data, configuration, policy registries, governance
records, approval evidence, logs, and protected key-recovery material as appropriate.
They MUST be encrypted, access-controlled, integrity-checked, geographically or
administratively separated, and tested through restoration.

Recovery procedures MUST establish trusted genesis, latest authorized phase and
policy, safe replay point, key availability, and reconciliation before reopening
value transfer. Recovery MUST NOT revert approvals or silently reactivate revoked
wallets.

## 20. Incident response

The incident plan MUST define detection, triage, authority, containment, evidence
preservation, communications, recovery, and lessons learned for key compromise,
unauthorized transfer, consensus failure, corrupted storage, approval bypass, DEX
exploit, partner compromise, governance misuse, and data exposure. Roles and contact
paths MUST be tested.

Phase 2 MUST include partner communication. Phase 3 MUST include broader public
communications, vulnerability intake, coordinated disclosure, and ecosystem
coordination. Incident handling MUST not promise reversal when the protocol cannot
provide it.

## 21. Emergency pause and recovery

Emergency authority MUST be narrowly defined, authenticated, logged, and protected
against unilateral misuse. Scope SHOULD distinguish transfers, swaps, liquidity,
administration, RPC, and block production. Pause behavior MUST be tested at every
transaction path, including pending operations and callbacks.

Recovery MUST require explicit authorization, cause remediation, state and policy
reconciliation, key review, staged re-enable, monitoring, and a recorded decision.
Rollback from an incorrectly activated phase MUST fail closed and preserve ledger
integrity.

## 22. Key rotation and administrator recovery

Rotation MUST be supported for governance, validator, treasury, approval, emergency,
service, and partner keys without weakening identity binding. Procedures MUST cover
scheduled rotation, suspected compromise, lost key, signer unavailability, quorum
change, and migration to multisignature or another governance mechanism.

Recovery material MUST be protected separately from active keys. Compromise
simulation MUST verify containment, revocation, replacement, audit continuity, and
safe restoration of authority. No undocumented personal key may be the sole permanent
recovery mechanism.

## 23. Phase-specific deployment requirements

### Phase 1 — Internal Company Production

Before real-value internal operation, the NGA MUST confirm company-controlled
production validators, nodes, APIs, wallets, monitoring, backups and recovery;
approved company wallets; production cryptography; treasury-key protection;
permissioned liquidity; restricted swaps; transfer-path authorization;
administrative audit logs; and tested emergency procedures.

### Phase 2 — Partner Network

Phase 2 MUST additionally provide organization onboarding, partner-wallet control
verification, separation of company and partner permissions, expiry or periodic
review, organization and wallet suspension/revocation, increased monitoring, rate
limits, abuse controls, and incident communications.

### Phase 3 — Public Network

Phase 3 is disabled by default and optional. It MUST additionally address public
scalability and attack surface, public RPC protection, permission-policy transition
and rollback tests, governance security, broader incident response, public disclosure
and vulnerability handling, and decentralization and upgrade-control considerations.
Activation MUST be a formal, auditable network configuration change.

## 24. Deployment gates

Deployment gates are administered by the NGA and apply to the target phase. Evidence
MUST show that required controls are implemented, configured, tested, monitored, and
owned. A written risk acceptance MAY address a bounded residual risk, but MUST NOT
misrepresent missing authorization enforcement or a known critical exploit as safe.

For the permissioned DEX and phase system, tests MUST include:

- approved sender and approved recipient;
- approved trader through the approved router;
- unapproved trader;
- approved sender to unapproved recipient and the reverse;
- direct transfer to and direct invocation of the pool;
- alternate router and transfer proxy;
- liquidity addition and removal;
- fee collection and treasury transfer;
- wallet revocation during pending activity;
- emergency pause;
- phase transition and rollback after incorrect activation;
- allowance and `transferFrom` behavior;
- callback and flash-swap paths where supported;
- misuse of every system-address exemption; and
- administrator-key compromise simulation.

Implementation validation MUST use the actual chain, contracts, routers, proxy model,
callbacks, native transaction paths, and upgrade mechanism. Model-only or UI-only
tests are insufficient.

## 25. Residual risks

- Findings 5 and 6 remain documented test-only algorithm-selection and downgrade
  risks that MUST be closed or made unreachable in value-bearing configurations.
- Finding 7 remains open for future memo-bearing transactions.
- Finding 8 remains dependent on careful wallet data-flow review.
- The original review was AI-assisted and bounded to the listed commits and surfaces;
  it does not cover all later code, dependencies, infrastructure, or contracts.
- Version 2 governance, allowlist, DEX, liquidity, monitoring, and recovery controls
  require implementation verification.
- Centralized governance creates compromise, misuse, availability, and key-person
  risk even when technically secure.
- Allowlisted trading does not guarantee legal, regulatory, market, or economic
  outcomes.
- AMM price, liquidity, slippage, front-running, oracle, paired-asset, and contract
  risks remain.
- An independent security assessment can reduce risk but cannot guarantee security.

## 26. Security checklist

- [ ] Active phase and policy version are canonical, authenticated, and auditable.
- [ ] Production rejects test-only schemes, seeds, and auto-funding paths.
- [ ] Sender and producer key-derived identity checks pass on all mutation paths.
- [ ] Findings 5 and 6 are unreachable or remediated for value-bearing deployment.
- [ ] Finding 7 is resolved before memo-bearing production support.
- [ ] Wallet signing recomputes and displays canonical content locally.
- [ ] Genesis and supply are reproducible and approved.
- [ ] Treasury and governance keys have least privilege, rotation, and recovery.
- [ ] Company, partner, and system-address permissions are distinct.
- [ ] Revocation is enforced at execution and after restart/replay.
- [ ] DEX and liquidity paths pass every test in Section 24.
- [ ] Exemptions are narrow, documented, and resistant to proxy/callback misuse.
- [ ] Logs are attributable, integrity-protected, monitored, and retained.
- [ ] Backups restore chain, policy, approvals, governance evidence, and keys safely.
- [ ] Incident, pause, rollback, and administrator-compromise drills pass.
- [ ] Target-phase monitoring, rate limits, and communication procedures are live.
- [ ] Upgrade and phase-transition activation and rollback are verified.
- [ ] Residual risks and any NGA acceptance are recorded without unsupported claims.

## 27. Conclusion

The original review established strong Ed25519 primitive and encoding behavior,
confirmed identity binding after remediation, and preserved atomic validation across
important import and replay paths. It also left concrete unresolved or documented
items: envelope-selected test-only behavior, operator downgrade risk, pending TSV
`memo_hash` loss, and reliance on a textual wallet safety tripwire.

Those results support phased engineering but do not establish that a permissioned
value-bearing network is already ready. Each phase requires its own implemented and
verified governance, wallet authorization, treasury, DEX, liquidity, operations, and
recovery controls. The NGA may activate a phase only after its documented criteria
are satisfied and the decision is authenticated and auditable.

## 28. Version history

| Version | Date | Summary |
|---|---|---|
| 1.x | Historical | AI-assisted review of commits `a3118c0`–`02ccb15`; recorded eight findings and imposed external-audit/legal hard gates. |
| 2.0 | 2026-08-02 | Preserved technical findings and statuses; replaced universal hard gates with NGA-administered phase gates; added governance, allowlist, DEX, liquidity, operations, recovery, and required validation. |
