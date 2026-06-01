# XRIQ Phase 1.1 RC Readiness Checklist

Status: Phase 1.1 release-candidate readiness guardrail for the local/private
XRIQ end-to-end prototype after the Phase 1 private-devnet RC1 tag.

This document does not approve public XRIQ launch, mainnet, token distribution,
exchange listing, DEX liquidity, custody, legal claims, audited cryptography,
public validator economics, smart-contract production use, or production API
exposure.

## Scope

Phase 1.1 covers only local/private end-to-end development:

- Rust API/backend route boundaries over the private-devnet read model.
- PostgreSQL read-model indexing and opt-in Postgres-backed read routes.
- React + TypeScript explorer, wallet preview, ISO preview, and admin status UI.
- ISO 20022 compatibility preview mappings with `not_certified: true`.
- Local smoke validation with optional Docker Desktop Postgres.

Phase 1.1 explicitly excludes:

- public mainnet, public token launch, DEX trading, liquidity pools, bridges, or
  exchange integrations
- production custody, seed phrase handling, production signing services, or
  private-key persistence
- mutating product API wallet submit/send, block-production controls, snapshot
  import/export controls, or smart-contract execution unless separately planned
  after this RC readiness gate
- GCP, Vast GPU, production infrastructure, production monitoring, production
  auth, TLS, rate limits, external audits, or certification claims

## Required Validation Before RC Tag Proposal

Run the local Phase 1.1 smoke from the repo root:

```bash
python scripts/xriq_phase1_1_local_e2e_smoke.py
```

For the Postgres-backed route parity gate, Docker Desktop must be running and
the explicit live mode must pass:

```bash
python scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live
```

Then run the cheap RC readiness guardrail:

```bash
python scripts/xriq_phase1_1_rc_readiness.py --latest-summary
```

Before asking the user for any RC tag approval, also run the same checker after
commit/push with Git clean/origin checks:

```bash
python scripts/xriq_phase1_1_rc_readiness.py --latest-summary --require-clean-git --require-origin-main
```

Do not create, move, or push a Phase 1.1 RC tag from a generic "continue" or
"do next steps" request. A tag requires explicit user approval naming the tag.

## RC Go/No-Go Checklist

- [x] Scope is local/private and non-production.
- [x] `docs/CODEX_HANDOFF.md` names Phase 1.1 as the active goal and records
      the latest smoke artifact directory.
- [x] `docs/XRIQ_PHASE1_1_CONTRACTS.md` documents read-only product and
      Postgres-backed route behavior.
- [x] `docs/XRIQ_LEGAL_RISK_REDUCTION.md` remains the controlling public-risk
      design guardrail for later public-token, DEX, bridge, listing, custody,
      privacy, and payment-network work.
- [x] Product API routes remain file-backed by default.
- [x] Postgres-backed routes are opt-in only through `request-postgres` or
      `serve-readonly` with explicit Postgres flags.
- [x] Postgres-backed routes are GET-only/read-only and add
      `source: postgres-read-model`, `read_model_warning`, and
      `read_only: true`.
- [x] Wallet draft preview remains non-mutating: no signing, no submit, no send,
      no custody, no private-key persistence.
- [x] ISO 20022 routes remain preview-only and include `not_certified: true`.
- [x] ISO 20022 routes make no bank, SWIFT, certification, settlement,
      compliance, or payment-network connectivity claims.
- [x] Docker live smoke uses only the dedicated local
      `xriq_phase1_1_smoke` database and resets only that smoke schema.
- [x] Admin UI Postgres status smoke validates both disabled and available
      read-model states.
- [x] No GCP, Vast GPU, production server, credential rotation, or paid cloud
      resource is required for Phase 1.1 RC readiness.

## Route-Parity Matrix

`Product route` means the default file-backed `xriq-api request` and
`serve-readonly` path. `Postgres CLI` means `xriq-api request-postgres`.
`Postgres server` means `xriq-api serve-readonly` with both explicit Postgres
flags. All Postgres parity is local/private-devnet only.

| Surface | Product route | Postgres CLI | Postgres server | Smoke artifacts |
| --- | --- | --- | --- | --- |
| Health | `/api/v1/health` | n/a | file-backed | `api/health.json` |
| Network | `/api/v1/network` | n/a | file-backed | `api/network.json` |
| Explorer overview | `/api/v1/explorer/overview` | yes | yes | `api/explorer-overview.json`, `indexer/postgres-api-explorer-overview.json`, `indexer/postgres-server-explorer-overview.json` |
| Blocks list | `/api/v1/blocks?limit=5` | yes | yes | `api/blocks.json`, `indexer/postgres-api-blocks.json`, `indexer/postgres-server-blocks.json` |
| Block detail | `/api/v1/blocks/1` | yes | yes | `api/block-detail.json`, `indexer/postgres-api-block-detail.json`, `indexer/postgres-server-block-detail.json` |
| Transactions list | `/api/v1/transactions?limit=5` | yes | yes | `api/transactions.json`, `indexer/postgres-api-transactions.json`, `indexer/postgres-server-transactions.json` |
| Transaction detail | `/api/v1/transactions/{tx_hash}` | yes | yes | `api/transaction-detail.json`, `indexer/postgres-api-transaction-detail.json`, `indexer/postgres-server-transaction-detail.json` |
| Accounts list | `/api/v1/accounts?limit=5` | yes | yes | `api/accounts.json`, `indexer/postgres-api-accounts.json`, `indexer/postgres-server-accounts.json` |
| Account detail | `/api/v1/accounts/{address}` | yes | yes | `api/account-detail.json`, `indexer/postgres-api-account-detail.json`, `indexer/postgres-server-account-detail.json` |
| Account history | `/api/v1/accounts/{address}/transactions?limit=5` | yes | yes | `api/account-history.json`, `indexer/postgres-api-account-history.json`, `indexer/postgres-server-account-history.json` |
| Mempool | `/api/v1/mempool?limit=5` | yes | yes | `api/mempool.json`, `indexer/postgres-api-mempool.json`, `indexer/postgres-server-mempool.json` |
| Wallet status | `/api/v1/wallet/status` | yes | yes | `api/wallet-status.json`, `indexer/postgres-api-wallet-status.json`, `indexer/postgres-server-wallet-status.json` |
| Wallet accounts | `/api/v1/wallet/accounts?limit=5` | yes | yes | `api/wallet-accounts.json`, `indexer/postgres-api-wallet-accounts.json`, `indexer/postgres-server-wallet-accounts.json` |
| Wallet balance | `/api/v1/wallet/accounts/{address}/balance` | yes | yes | `api/wallet-balance.json`, `indexer/postgres-api-wallet-balance.json`, `indexer/postgres-server-wallet-balance.json` |
| Wallet history | `/api/v1/wallet/accounts/{address}/history?limit=5` | yes | yes | `api/wallet-history.json`, `indexer/postgres-api-wallet-account-history.json`, `indexer/postgres-server-wallet-account-history.json` |
| Wallet transaction status | `/api/v1/wallet/transactions/{tx_hash}/status` | yes | yes | `api/wallet-confirmed-tx-status.json`, `api/wallet-pending-tx-status.json`, `indexer/postgres-api-wallet-transaction-status.json`, `indexer/postgres-server-wallet-transaction-status.json` |
| Wallet draft preview | `/api/v1/wallet/transfers/draft-preview?...` | yes | yes | `api/wallet-draft-preview.json`, `api/wallet-draft-preview-combined-failure.json`, `api/wallet-draft-preview-balance-failure.json`, `api/wallet-draft-preview-malformed-request.json`, `indexer/postgres-api-wallet-draft-preview.json`, `indexer/postgres-server-wallet-draft-preview.json` |
| Admin node status | `/api/v1/admin/node/status` | yes | yes | `api/admin-node-status.json`, `indexer/postgres-api-node-status.json`, `indexer/postgres-server-node-status.json` |
| Admin indexer status | `/api/v1/admin/indexer/status` | yes | yes | `api/admin-indexer-status.json`, `indexer/postgres-api-indexer-status.json`, `indexer/postgres-server-indexer-status.json` |
| Admin audit events | `/api/v1/admin/audit-events?limit=5` | yes | yes | `api/admin-audit-events.json`, `indexer/postgres-api-audit-events.json`, `indexer/postgres-server-audit-events.json` |
| Snapshot list | `/api/v1/snapshots` | yes | yes | `api/snapshots.json`, `indexer/postgres-api-snapshots.json`, `indexer/postgres-server-snapshots.json` |
| Snapshot detail | `/api/v1/snapshots/current-indexed-chain` | yes | yes | `api/snapshot-detail.json`, `indexer/postgres-api-snapshot-detail.json`, `indexer/postgres-server-snapshot-detail.json` |
| ISO payment initiation | `/api/v1/iso20022/payment-initiation/preview?tx_hash={tx_hash}` | yes | yes | `api/iso-payment-initiation.json`, `indexer/postgres-api-iso-payment-initiation.json`, `indexer/postgres-server-iso-payment-initiation.json` |
| ISO payment status | `/api/v1/iso20022/transactions/{tx_hash}/status` | yes | yes | `api/iso-payment-status.json`, `indexer/postgres-api-iso-transaction-status.json`, `indexer/postgres-server-iso-transaction-status.json` |
| ISO account statement | `/api/v1/iso20022/accounts/{address}/statement?from=...&to=...` | yes | yes | `api/iso-account-statement.json`, `indexer/postgres-api-iso-account-statement.json`, `indexer/postgres-server-iso-account-statement.json` |
| Postgres read-model status | n/a | `/api/v1/admin/postgres/read-model-status` | yes | `indexer/postgres-api-read-model-status.json`, `indexer/postgres-server-read-model-status.json`, `indexer/postgres-admin-ui-read-model-status.json` |

## Deferred Until After RC Readiness Review

Do not start these from a generic continuation request:

- mutating wallet submit/send APIs in the product API
- block-production controls in the product API or admin UI
- snapshot export/import mutation through the product API or admin UI
- smart-contract VM, XRC assets, native DEX module, or liquidity pools
- public explorer/API, public wallet, validator admission, token economics, or
  governance mechanics
- production custody, privacy pools, bridges, stablecoins, payment processing,
  CEX/DEX listings, or market-facing claims

## Recommended Next Step After This Checklist

Use the Phase 1.1 RC candidate report at
`docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md` before any tag decision. The
proposed tag is `phase1-1-xriq-local-e2e-rc1`, but it must not be created,
moved, or pushed without explicit user approval naming that tag. If any route,
artifact, or guardrail is missing, fix that gap first instead of moving into
mutating features.
