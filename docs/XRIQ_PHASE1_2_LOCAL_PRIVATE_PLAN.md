# XRIQ Phase 1.2 Local Private Plan

Status: post-Phase 1.1 RC1 local/private hardening scope; first local
block-production API path is implemented behind explicit enablement.

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

## Implementation Checkpoints

The first code checkpoint was intentionally small:

- update Phase 1.1 contracts with a Phase 1.2 local mutation preflight section
- add fixtures for disabled wallet submit/send responses
- extend the local contract checker to validate those fixtures
- do not yet enable transaction submission in the API or UI

This gave the project a safe target before any real mutation was wired.

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

Current pending-to-confirmed loop API checkpoint:
`xriq/fixtures/phase1_2/pending-to-confirmed-loop-contract.json` defines the
local action that turns pending transactions into a confirmed private-devnet
block. `xriq-api request` and `xriq-api serve-readonly` now keep the default
path refused, but accept `POST /api/v1/blocks/produce` when
`--enable-local-block-production true` is explicitly supplied with
`local_request_id`, the configured test authority producer, `max_transactions=4`,
and `timestamp_ms`. The accepted local path appends one block, clears only the
confirmed pending hashes, and returns block, confirmed transaction,
pending-state, chain-state, and API-local audit metadata. It still does not
enable wallet submit/send success, UI mutation controls, custody, signing,
snapshot mutation, DEX/smart contracts, public network behavior, or production
infrastructure.

Current smoke checkpoint: `scripts/xriq_phase1_1_local_e2e_smoke.py` now covers
both the one-shot `xriq-api request` accepted path and a temporary
`xriq-api serve-readonly` HTTP POST accepted path on copied local chain/pending
files. The server smoke verifies the refreshed server state reports height `2`
and mempool count `0` after block production.

Current client contract checkpoint: `xriq/apps/explorer-ui/src/api.ts` now
defines the accepted local block-production response type, accepted-code,
audit-scope and mutation constants, and
`validateLocalBlockProductionAcceptedContract()`. The static UI guard requires
those accepted-response markers, but no UI POST function or enabled mutation
control is exposed.

Current wallet-submit accepted contract checkpoint:
`xriq/fixtures/phase1_2/wallet-transfer-submit-to-pending-contract.json`
now defines the guarded local-only accepted response shape for
`POST /api/v1/wallet/transfers/submit` with
`status: guarded-local-api-implemented` and
`implementation_status: request-and-serve-explicit-local-flag`. It requires
`--enable-local-wallet-submit`, local/private-devnet mode, audit events, a
configured local test sender, pending-file mutation only, unchanged chain
state, no signing material, no custody material, and no UI mutation control.
`scripts/xriq_phase1_1_contract_check.py` validates this fixture.

Current wallet-submit client contract checkpoint:
`xriq/apps/explorer-ui/src/api.ts` now defines the wallet-submit accepted
response type, accepted-code/mutation constants, and
`validateLocalWalletSubmitAcceptedContract()`. The static UI guard requires
those markers. No UI POST function or enabled wallet mutation control is
exposed.

Current wallet-send accepted contract checkpoint:
`xriq/fixtures/phase1_2/wallet-transfer-send-to-pending-contract.json` defines
the guarded local-only accepted response shape for
`POST /api/v1/wallet/transfers/send` with
`status: guarded-local-api-implemented` and
`implementation_status: request-and-serve-explicit-local-flag`. It requires
`--enable-local-wallet-send`, local/private-devnet mode, audit events, a
configured local test sender, pending-file mutation only, unchanged chain
state, no signing material, no custody material, and no UI mutation control.
Unlike submit, `draft_id` is optional and the audit resource is
`local_request_id`. `scripts/xriq_phase1_1_contract_check.py` now validates
both wallet pending contracts and reports
`phase1_2_wallet_pending_contract_fixtures: 2`.

Current wallet-send client contract checkpoint:
`xriq/apps/explorer-ui/src/api.ts` now defines the wallet-send accepted
response type, accepted-code/mutation constants, endpoint constant, and
`validateLocalWalletSendAcceptedContract()`. The static UI guard requires those
markers. No UI POST function or enabled wallet mutation control is exposed.

Current wallet-submit Rust/API checkpoint: `xriq-api request` and
`xriq-api serve-readonly` now parse `--enable-local-wallet-submit true`. The
default `POST /api/v1/wallet/transfers/submit` path remains HTTP `403`
`wallet_submit_disabled`. With explicit local enablement and local
private-devnet query fields, the accepted path appends exactly one pending
transaction to the specified pending file, leaves the chain file unchanged, and
returns HTTP `201 Created` with `code: wallet_submit_accepted_local_only`,
`mutation: pending_state_only`, pending/chain state summaries, and accepted
audit metadata. The local E2E smoke writes
`api/wallet-submit-accepted-local.json`. UI submit/send controls remain
disabled.

Current wallet-submit client smoke checkpoint:
`xriq/apps/explorer-ui/scripts/check-wallet-submit-accepted-contract.mjs` now
uses Vite SSR to load the real `src/api.ts`
`validateLocalWalletSubmitAcceptedContract()` function and validates both the
guarded submit fixture example and the latest local E2E
`api/wallet-submit-accepted-local.json` artifact when present. `npm run check`
runs this smoke after the static guard. UI submit/send controls remain
disabled.

Current wallet-send Rust/API checkpoint: `xriq-api request` and
`xriq-api serve-readonly` now parse `--enable-local-wallet-send true`. The
default `POST /api/v1/wallet/transfers/send` path remains HTTP `403`
`wallet_send_disabled`. With explicit local enablement and local private-devnet
query fields, the accepted path appends exactly one pending transaction to the
specified pending file, leaves the chain file unchanged, and returns HTTP
`201 Created` with `code: wallet_send_accepted_local_only`,
`mutation: pending_state_only`, pending/chain state summaries, and accepted
audit metadata. The local E2E smoke writes
`api/wallet-send-accepted-local.json`. UI submit/send controls remain disabled.

Current wallet-send client smoke checkpoint:
`xriq/apps/explorer-ui/scripts/check-wallet-send-accepted-contract.mjs` now uses
Vite SSR to load the real `src/api.ts`
`validateLocalWalletSendAcceptedContract()` function and validates both the
guarded send fixture example and the latest local E2E
`api/wallet-send-accepted-local.json` artifact when present. `npm run check`
runs this smoke after the static and wallet-submit guards. UI submit/send
controls remain disabled.

Current wallet-send lifecycle smoke checkpoint:
`scripts/xriq_phase1_2_wallet_send_lifecycle_smoke.py` now creates a fresh
local/private chain, uses guarded `POST /api/v1/wallet/transfers/send` with
`--enable-local-wallet-send true` to append one pending transaction, uses
guarded `POST /api/v1/blocks/produce` with
`--enable-local-block-production true` to confirm that exact transaction in a
new block, and verifies `/api/v1/wallet/transactions/{tx_hash}/status` returns
the same transaction as confirmed at block height `2`. It also checks the
local pending file is empty afterward. The same smoke now also starts a
temporary `xriq-api serve-readonly` process with explicit local wallet-send and
block-production flags, repeats the wallet-send -> block-production ->
confirmed-status flow through HTTP, verifies server network height `2`, and
then stops the process. UI submit/send controls remain disabled.

Current Phase 1.2 readiness summary checkpoint:
`scripts/xriq_phase1_2_readiness_summary.py` now checks the latest refusal
summary, the latest accepted local wallet-send artifact, and the latest
wallet-send lifecycle summary before any UI mutation-control milestone is
considered. The summary validates fixture/refusal guards, audit expectation
coverage, accepted wallet-send response fields, absence of signing/custody
field names, request-mode lifecycle evidence, temporary `serve-readonly`
lifecycle evidence, and required artifact file paths. It reports
`ready_for_ui_mutation_design_review: true`, while keeping
`ui_mutation_controls_enabled: false`,
`safe_to_enable_ui_mutation_controls: false`, and
`approval_required_before_ui_mutation_controls: true`.

Current UI mutation-control design gate checkpoint:
`docs/XRIQ_PHASE1_2_UI_MUTATION_CONTROL_GATE.md` now defines the approved
local/private gate for wallet send and block production. It still excludes
wallet submit, snapshot mutation, DEX, smart-contract, public-network, and
production behavior. `scripts/xriq_phase1_2_ui_mutation_gate_check.py`
validates the gate document, the latest readiness summary, the existing wallet
and Admin UI guard source, the static UI guardrails, and the shared
accepted-response validators. It also verifies no direct wallet submit/send or
block-production endpoint strings are used from UI components, no direct
`fetch(` appears in the mutation UI sources, no browser persistence markers are
present, and no sensitive signing/custody field names are present. Default UI
mutation controls remain disabled; the approved wallet-send and block-production
UI paths are feature-switched only.

Current wallet-send UI implementation checkpoint:
`docs/XRIQ_PHASE1_2_WALLET_SEND_UI_IMPLEMENTATION_PLAN.md` now records the
approved local/private-devnet wallet-send UI implementation behind
`VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`, with wallet submit deferred.
`xriq/apps/explorer-ui/src/api.ts` exposes `sendLocalWalletTransfer`, which
uses the shared API client and validates accepted responses with
`validateLocalWalletSendAcceptedContract`. `xriq/apps/explorer-ui/src/wallet.tsx`
renders `Local Wallet Send`; the button is disabled by default, disabled unless
the feature switch is on, disabled on validation failures, and disabled while a
send is in flight. The UI renders the local request id, audit event id, pending
transaction hash, pending file marker, chain file marker, mutation, status, and
chain unchanged state after an accepted send.
`xriq/apps/explorer-ui/scripts/check-wallet-send-ui-control.mjs` is now part of
`npm run check` and validates that the wallet UI uses the shared client, has no
direct submit/send endpoint strings, no direct `fetch(`, no browser persistence
markers, and no sensitive signing/custody field names.
`scripts/xriq_phase1_2_wallet_send_ui_plan_check.py` validates the gate, docs,
source markers, and feature-switch constraint.

Current wallet-send UI live smoke checkpoint:
`xriq/apps/explorer-ui/scripts/check-wallet-send-ui-live.mjs` now imports the
real `sendLocalWalletTransfer` helper through Vite SSR and calls a temporary
local/private `xriq-api serve-readonly` endpoint. The orchestrator
`scripts/xriq_phase1_2_wallet_send_ui_live_smoke.py` creates a fresh temporary
private-devnet chain, starts `serve-readonly` with
`--enable-local-wallet-send true` only, sets
`VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`, and verifies that the
feature-switched UI client accepts exactly one pending wallet-send response.
The smoke verifies that the pending file gains the accepted transaction, the
chain height remains unchanged, wallet submit remains refused without
`--enable-local-wallet-submit`, and block production remains refused without
`--enable-local-block-production`.

Current wallet-send read-only refresh smoke checkpoint:
`xriq/apps/explorer-ui/src/wallet.tsx` now exports the existing pure
`walletActivityRows` helper so smoke tooling can validate the same
read-only wallet activity shaping used by the UI. The new
`xriq/apps/explorer-ui/scripts/check-wallet-send-refresh-live.mjs` sends one
local/private wallet transfer through `sendLocalWalletTransfer`, reloads the
existing `loadExplorerSnapshot` read-only view, checks the pending transaction
in `snapshot.mempool`, checks `loadWalletTransactionStatus` still reports the
transaction as pending, and checks wallet activity rows for both sender and
recipient. The orchestrator
`scripts/xriq_phase1_2_wallet_send_refresh_smoke.py` runs this against a fresh
temporary `serve-readonly` API with only `--enable-local-wallet-send true` and
verifies wallet submit and block production remain refused.

Current block-production UI design checkpoint:
`docs/XRIQ_PHASE1_2_BLOCK_PRODUCTION_UI_DESIGN.md` now records the approved
local/private-devnet block-production UI implementation behind
`VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`. The implementation requires
the API to be started with `--enable-local-block-production true`, uses the
shared API helper `produceLocalBlock`, validates accepted responses with
`validateLocalBlockProductionAcceptedContract`, renders local request/audit
metadata plus produced block and pending/chain transition details, keeps wallet
send separate, and keeps wallet submit deferred.

Current block-production UI live smoke checkpoint:
`xriq/apps/explorer-ui/scripts/check-block-production-ui-live.mjs` imports the
real `sendLocalWalletTransfer`, `produceLocalBlock`,
`loadExplorerSnapshot`, and `loadWalletTransactionStatus` helpers through Vite
SSR and calls a temporary local/private `xriq-api serve-readonly` endpoint. The
orchestrator `scripts/xriq_phase1_2_block_production_ui_live_smoke.py` creates
a fresh temporary private-devnet chain, starts `serve-readonly` with
`--enable-local-wallet-send true` and `--enable-local-block-production true`,
sets `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`, sends one pending
wallet transaction, produces exactly one local block, verifies the pending file
is cleared, verifies network height advances from `1` to `2`, verifies the
wallet transaction becomes confirmed, and verifies wallet submit remains
refused without `--enable-local-wallet-submit`.

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

For the current wallet-send lifecycle checkpoint, use:

```bash
python scripts/xriq_phase1_2_wallet_send_lifecycle_smoke.py
```

For the current readiness-summary checkpoint, use:

```bash
python scripts/xriq_phase1_2_readiness_summary.py
```

For the current UI mutation-control gate checkpoint, use:

```bash
python scripts/xriq_phase1_2_ui_mutation_gate_check.py
```

For the current wallet-send UI implementation checkpoint, use:

```bash
python scripts/xriq_phase1_2_wallet_send_ui_plan_check.py
npm run check
```

For the current wallet-send UI live smoke checkpoint, use:

```bash
python scripts/xriq_phase1_2_wallet_send_ui_live_smoke.py
```

For the current wallet-send read-only refresh smoke checkpoint, use:

```bash
python scripts/xriq_phase1_2_wallet_send_refresh_smoke.py
```

For the current block-production UI design checkpoint, use:

```bash
python scripts/xriq_phase1_2_block_production_ui_design_check.py
```

For the current block-production UI live smoke checkpoint, use:

```bash
python scripts/xriq_phase1_2_block_production_ui_live_smoke.py
```
