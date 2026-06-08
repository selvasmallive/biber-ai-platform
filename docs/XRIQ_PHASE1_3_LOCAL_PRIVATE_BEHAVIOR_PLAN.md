# XRIQ Phase 1.3 Local/Private Behavior Plan

Status: post-Phase 1.2 RC1 planning scope. Phase 1.2 RC1 is already tagged as
`phase1-2-xriq-local-private-hardening-rc1` at commit `b3a2fe4`; do not move,
delete, recreate, or repush that tag unless explicitly asked for that exact tag
maintenance operation.

## Goal

Phase 1.3 turns the Phase 1.2 local/private mutation controls into repeatable
behavioral testing for a wallet user journey:

1. prepare a local/private devnet state,
2. create one explicit local wallet send,
3. produce exactly one local block from pending transactions,
4. refresh wallet, explorer, mempool, Admin, and audit views,
5. verify balances, transaction status, block inclusion, pending-state cleanup,
   and refusal/audit behavior.

This is still local/private developer validation. It is not a public launch,
hosted wallet, exchange, DEX, smart-contract, custody, validator, bridge, or
production-infrastructure phase.

## Non-Negotiable Boundaries

- Do not enable wallet submit UI mutation.
- Do not store private keys, seed phrases, mnemonics, raw signatures, signed
  transactions, custody fields, or production wallet material.
- Do not introduce public mainnet behavior, token sale language, exchange
  readiness claims, DEX/liquidity modules, bridges, validator economics,
  public governance, or smart-contract VM work.
- Do not provision GCP/Vast/production infrastructure for Phase 1.3 unless the
  user explicitly approves that separate scope.
- Keep all successful mutation paths behind explicit local/private feature
  switches and matching local API flags.
- Keep default UI mutation controls disabled.

## Approved Local Switches

Phase 1.3 may reuse only the accepted Phase 1.2 local/private switches:

- `--enable-local-wallet-send true`
- `--enable-local-block-production true`
- `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true`
- `VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true`

Do not add broader mutation flags in this phase. UI mutation code must continue
to use the shared TypeScript API client rather than direct `fetch(` calls.

## Milestone A: Behavior Fixture Inventory

Create or document the canonical local/private behavior fixture set used for
wallet testing:

- starting chain state,
- deterministic funded sender,
- deterministic recipient,
- expected fee/amount/nonce values,
- expected pre-send balances,
- expected pending transaction hash,
- expected produced block height/hash,
- expected post-block balances and wallet transaction status,
- expected Admin/audit rows.

This milestone is documentation and fixture inventory only. It must not add new
mutation capability.

Initial checkpoint:

- canonical fixture:
  `xriq/fixtures/phase1_3/local-wallet-behavior-v1.json`
- executable contract check:
  `python scripts/xriq_phase1_3_behavior_contract_check.py`

## Milestone B: One-Shot Behavior Smoke

Add a local CPU-only smoke that runs the full behavior loop without external
services:

- start from temporary local chain/pending files,
- call the guarded wallet-send path with explicit local/private enablement,
- call the guarded block-production path with explicit local/private enablement,
- verify the pending file is cleaned only for confirmed transactions,
- verify network height increments by exactly one block,
- verify wallet transaction status is confirmed,
- verify balances/history update as expected,
- verify the mempool is empty after block production,
- write a timestamped summary under `xriq/target/`.

The smoke should be deterministic and suitable for low-cost local execution.

Initial checkpoint:

- executable smoke:
  `python scripts/xriq_phase1_3_wallet_behavior_smoke.py`
- latest passing artifact:
  `xriq/target/xriq-phase1-3-wallet-behavior-smoke-20260607T131636Z/summary.json`

## Milestone C: UI-Backed Behavior Smoke

After Milestone B is stable, add or extend a Vite SSR/browser-compatible smoke
that proves the same behavior through the shared TypeScript API client and the
local/private UI helper paths:

- wallet send is explicit and feature-gated,
- block production is explicit and feature-gated,
- wallet submit remains deferred,
- refresh views show the transaction moving from pending to confirmed,
- Admin/audit rows show local-only mutation and refusal expectations.

This milestone must continue to avoid direct mutation `fetch(` calls from UI
source files and must keep default controls disabled.

Initial checkpoint:

- executable UI-backed smoke:
  `python scripts/xriq_phase1_3_wallet_behavior_ui_smoke.py`
- matching npm/Vite SSR client check:
  `npm run check:phase1-3-wallet-behavior-live`
- latest passing artifact:
  `xriq/target/xriq-phase1-3-wallet-behavior-ui-smoke-20260607T132901Z/summary.json`

## Milestone D: Negative Behavior Matrix

Keep the negative cases current:

- default wallet send disabled,
- default block production disabled,
- wallet submit deferred,
- no-pending block production returns `no_pending_transactions`,
- invalid local/private request fields are refused without chain or pending
  mutation,
- public/production/custody/sensitive-key markers remain absent.

Negative cases should write summary artifacts and should be included in a cheap
Phase 1.3 readiness summary before any future post-RC tag is considered.

Initial checkpoint:

- executable readiness/negative-matrix consolidation guard:
  `python scripts/xriq_phase1_3_readiness_summary.py`
- the guard reads the latest fixture contract check, CPU behavior smoke, and
  UI-backed behavior smoke summaries, verifies the negative matrix, and reports
  that no Phase 1.3 tag may be created from a generic continue request.
- latest passing artifact:
  `xriq/target/xriq-phase1-3-readiness-summary-20260607T134243Z/summary.json`

## Validation Plan

The first implementation checkpoint should add the cheapest local checks before
any browser or Docker run:

```bash
python scripts/xriq_phase1_3_behavior_contract_check.py
python scripts/xriq_phase1_3_wallet_behavior_smoke.py
git diff --check
```

The behavior contract check now exists and writes timestamped artifacts under
`xriq/target/xriq-phase1-3-*`.
On this Windows workstation, use the bundled Codex Python if `python` is not on
PATH.
The CPU-only wallet behavior smoke also now exists and should stay cheap:

```bash
python scripts/xriq_phase1_3_wallet_behavior_smoke.py --skip-build
```

The UI-backed behavior smoke now starts a temporary local/private API, runs the
shared TypeScript client path through Vite SSR, verifies wallet/Admin refresh
rows, balances, history, wallet-submit refusal, and no-pending block-production
refusal, and still avoids browser, Docker, GCP, Vast, public, DEX, custody, and
production scope:

```bash
python scripts/xriq_phase1_3_wallet_behavior_ui_smoke.py --skip-build
```

Consolidate Phase 1.3 behavior readiness and negative-matrix evidence with:

```bash
python scripts/xriq_phase1_3_readiness_summary.py
```

Prepare or launch the manual browser demo with:

```bash
python scripts/xriq_phase1_3_demo_launcher.py --skip-build --launch --auto-port
```

The click path and demo boundaries live in
`docs/XRIQ_PHASE1_3_DEMO_RUNBOOK.md`.

The Phase 1.3 RC candidate report/checklist is documented at:

```text
docs/XRIQ_PHASE1_3_RC_CANDIDATE_REPORT.md
```

The approved Phase 1.3 RC tag is
`phase1-3-xriq-local-private-behavior-rc1` at commit `345d353`. Do not move,
delete, recreate, or repush that tag without an exact tag-maintenance request.

## Completion Criteria

Phase 1.3 is ready for a later RC decision only when:

- the behavior fixture inventory is documented or encoded,
- one-shot local wallet send plus one-block production smoke passes,
- UI-backed local/private behavior smoke passes with explicit feature switches,
- wallet status, balances, history, mempool, explorer, Admin, and audit views
  refresh consistently after the block is produced,
- disabled/default and invalid-input negative paths are covered,
- no public, custody, DEX, smart-contract, production, or exchange-listing
  scope is introduced.

## Future Tag Rule

Phase 1.3 did not automatically create a release tag; the tag was created only
after exact explicit approval. If future work needs another post-RC tag, use a
new deliberate tag name only after:

- a candidate report is written,
- the non-mutating Phase 1.3 readiness summary passes from a clean checkout,
- the user explicitly approves the exact tag name.

Do not create, move, delete, recreate, or push any tag from a generic continue
request. Do not move, delete, recreate, or repush
`phase1-3-xriq-local-private-behavior-rc1` without an exact tag-maintenance
request.
