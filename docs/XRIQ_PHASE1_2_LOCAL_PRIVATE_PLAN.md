# XRIQ Phase 1.2 Local Private Plan

Status: post-Phase 1.1 RC1 planning scope for local/private development only.

Phase 1.2 starts after:

- `phase1-xriq-private-devnet-rc1`
- `phase1-1-xriq-local-e2e-rc1`

The goal is to move from read-only/local preview surfaces toward a safer
private-devnet execution loop, without public launch, custody, DEX, bridge,
mainnet, or production infrastructure work.

## Goal

Build the next local/private development layer around the tagged Phase 1.1
baseline:

- safer private-devnet wallet action contracts
- explicit local-only mutation gates
- auditable local admin actions
- stronger smoke coverage for action refusal and preview behavior
- clearer handoff from read-only UI panels to future private-devnet actions

Phase 1.2 should make the prototype more useful for developer testing while
keeping all irreversible or public-facing behavior blocked.

## Non-Goals

Do not include these in Phase 1.2 unless a later explicit approval and review
document changes the scope:

- public mainnet or community devnet launch
- public token distribution, tokenomics, validator rewards, or governance
- DEX trading, liquidity pools, bridges, wrapped assets, or exchange listings
- custody, hosted wallets, seed phrase storage, private-key persistence, or
  managed signing services
- production GCP/Vast/server infrastructure, public auth, TLS, rate limits, or
  monitoring
- ISO 20022 certification, bank connectivity, SWIFT connectivity, fiat
  settlement, or payment-network claims
- smart-contract VM, XRC asset issuance, or native DEX modules

Keep `docs/XRIQ_LEGAL_RISK_REDUCTION.md` as the controlling guardrail for any
request that touches public tokens, privacy, DEX, bridges, custody, listings,
payments, or market-facing claims.

## Implementation Ladder

Use this order unless the user explicitly chooses a different narrow milestone.

1. Phase 1.2 contract update.
   Define local-only request/response shapes for future wallet submit,
   block-production, snapshot mutation, and admin action audit surfaces before
   implementing mutation. Include disabled-by-default behavior in fixtures.

2. Wallet action safety boundary.
   Add private-devnet-only submit/send planning behind explicit local flags.
   The first implementation should prove refusal behavior, validation errors,
   and audit logging before accepting a transaction. Do not persist private
   keys or seed phrases.

3. Local pending-to-confirmed loop.
   Add a controlled developer path that can take a local pending transaction,
   produce a private-devnet block, and show the confirmed result through the
   existing indexer/API/UI path. Keep this local-only and test-identity-only.

4. Admin action audit hardening.
   Add audit-event coverage for any local mutation or operator action. Admin UI
   controls should remain disabled until the API refusal and audit behavior are
   covered by tests.

5. Snapshot operation hardening.
   Design snapshot export/import as local developer operations with dry-run,
   refusal, overwrite protection, and audit-event requirements before adding
   any UI control.

6. Phase 1.2 smoke expansion.
   Extend the local smoke with refusal-path checks first, then add successful
   private-devnet-only action checks only after the contract and audit behavior
   are stable.

## Required Gates Before Mutating Code

Before implementing any mutating product API endpoint, update or add:

- contract documentation
- fixture examples for disabled/refused behavior
- tests for invalid input and unauthorized/disabled mode
- audit-event expectations
- smoke-script coverage
- handoff notes with exact commands and scope boundaries

Mutating endpoints must be disabled by default. They must require explicit
local/private-devnet flags or config names that cannot be confused with
production mode.

## Recommended First Implementation

The first code checkpoint should be small:

- update Phase 1.1 contracts with a Phase 1.2 local mutation preflight section
- add fixtures for disabled wallet submit/send responses
- extend the local contract checker to validate those fixtures
- do not yet enable transaction submission in the API or UI

This gives the project a safe target before any real mutation is wired.

Current checkpoint: the disabled wallet submit/send preflight fixtures now live
under `xriq/fixtures/phase1_2/`, and
`scripts/xriq_phase1_1_contract_check.py` validates that they remain disabled,
non-mutating, local/private, audit-gated, and test-identity-only.

Current refusal-smoke checkpoint: `scripts/xriq_phase1_2_refusal_smoke.py`
validates those preflight fixtures independently and writes a local smoke
summary under `xriq/target/xriq-phase1-2-refusal-smoke-*`.

Current API refusal checkpoint: `xriq-api` returns HTTP `403 Forbidden`
disabled responses for
`POST /api/v1/wallet/transfers/submit` and
`POST /api/v1/wallet/transfers/send`. The local smoke records
`api/wallet-submit-disabled.json` and `api/wallet-send-disabled.json` and
verifies `enabled: false`, `mutation: "none"`, explicit local enablement
flags, audit-event requirements, test-identity-only boundaries, refusal
guards, and no signing/custody/transaction-hash response fields.

Current UI/client action-guard checkpoint: the React wallet shell includes
disabled `Submit Draft` and `Send Transfer` controls and an explicit
`Check Guards` action that calls the disabled submit/send endpoints through the
client API layer. The client accepts only HTTP `403` refusal responses and
validates the disabled contract before marking either guard ready. This is
still non-mutating and does not sign, send, submit, persist, or manage secrets.

Current audit expectation checkpoint: Phase 1.2 now has
`wallet-transfer-submit-audit-expectation.json` and
`wallet-transfer-send-audit-expectation.json` under `xriq/fixtures/phase1_2/`.
They define local actor, action, resource, refused-by-default behavior,
accepted-only local flag requirements, audit metadata requirements, forbidden
secret/signing/transaction-hash metadata, and test-identity-only scope.
`scripts/xriq_phase1_1_contract_check.py` and
`scripts/xriq_phase1_2_refusal_smoke.py` validate these fixtures.

Current API-local audit checkpoint: the disabled submit/send fixtures and
`xriq-api` `403` responses now include
`audit_scope: "api-local-refusal"`, `audit_event_recorded: true`, and a deterministic
`audit_event` object for refused wallet attempts. The audit record uses the
local private-devnet operator actor, wallet transfer attempt action,
`wallet_transfer` resource type, refused outcome metadata, explicit local flag,
local request id placeholder, and request-fields-only metadata policy. It still
does not write chain state, pending state, signing material, custody material,
transaction hashes, or accepted mutation results.

Current audit visibility checkpoint: `/api/v1/admin/audit-events?limit=...`
now keeps indexed read-model audit rows in `audit_events` and adds a separate
`local_refusal_audit_events` array with the deterministic refused wallet
submit/send audit records. The same local refusal section is rendered by the
file-backed API and the explicitly configured Postgres read-model API path.
It remains visibility-only; the records are not persisted chain/indexer rows
and no successful submit/send, pending mutation, chain mutation, signing, or
custody behavior is enabled.

Current block-production preflight checkpoint:
`xriq/fixtures/phase1_2/block-production-disabled.json` and
`xriq/fixtures/phase1_2/block-production-audit-expectation.json` define the
disabled-by-default contract for `POST /api/v1/blocks/produce`. They require
`--enable-local-block-production`, API-local refusal audit visibility, a local
operator actor, `block_production_attempt` action, `block_production` resource
type, request-fields-only metadata, test-identity-only scope, and no pending or
chain mutation in the default path. The contract and refusal-smoke scripts
validate these fixtures.

Current block-production API refusal checkpoint: `xriq-api` now returns HTTP
`403 Forbidden` for `POST /api/v1/blocks/produce` using the same disabled,
non-mutating, audit-gated response shape as the wallet submit/send refusals.
The disabled response includes the block-production local actor/action/resource,
`--enable-local-block-production`, request field names, refusal guards, and no
pending or chain mutation. `/api/v1/admin/audit-events?limit=...` now exposes
three local refusal records: wallet submit, wallet send, and block production.
These records remain API-local response visibility only, not persistent
chain/indexer audit rows.

Current UI/client block-production guard checkpoint: the React Admin Status
surface now includes an `Admin Action Guards` section with a disabled `Produce
Block` control and an explicit `Check Guard` action. The client calls the
disabled `POST /api/v1/blocks/produce` endpoint only through the API layer,
accepts only HTTP `403` refusal responses, validates the disabled/non-mutating
contract, shows `block_production_disabled`,
`--enable-local-block-production`, and `mutation: "none"`, and keeps the block
production action disabled. The admin audit section also surfaces the local
block-production refusal audit record.

Recommended next implementation: start the first local pending-to-confirmed
loop contract/implementation path behind explicit local-private-devnet gates.
Begin with request/response shape, test-identity-only validation, audit
expectations, and refusal/disabled coverage before accepting any successful
pending or chain mutation.

## Validation

For Phase 1.2 docs-only planning checkpoints, use:

```bash
git diff --check
```

For the first fixture/contract checkpoint, also use:

```bash
python scripts/xriq_phase1_1_contract_check.py
python scripts/xriq_phase1_2_refusal_smoke.py
python scripts/xriq_phase1_1_rc_readiness.py --latest-summary
```

For Rust behavior changes, run focused package tests first, then the local smoke
script. Use Docker live smoke only when the change touches Postgres-backed
behavior.
