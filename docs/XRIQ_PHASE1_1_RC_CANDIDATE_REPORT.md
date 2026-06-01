# XRIQ Phase 1.1 RC Candidate Report

Status: candidate report only. No RC tag has been created by this report.
Follow-up: after explicit user approval, the Phase 1.1 RC1 tag
`phase1-1-xriq-local-e2e-rc1` was created and pushed at commit `6a38a51a`.

Proposed tag, only after explicit user approval:
`phase1-1-xriq-local-e2e-rc1`

Pre-report implementation checkpoint reviewed for this candidate: `76b5d8c6`.

## Candidate Scope

This candidate covers the local/private XRIQ Phase 1.1 end-to-end prototype:

- Rust API/backend read boundary for private-devnet explorer, wallet preview,
  admin, snapshot catalog, audit, mempool, and ISO 20022 preview routes.
- PostgreSQL read-model schema, deterministic indexer replay, idempotent SQL
  write-plan export, dry-run apply/verify paths, and Docker live smoke against
  the dedicated `xriq_phase1_1_smoke` database.
- Opt-in Postgres-backed read routes through `xriq-api request-postgres` and
  explicitly Postgres-enabled `xriq-api serve-readonly`.
- React + TypeScript explorer/wallet/admin/ISO preview shell using read-only
  product APIs.
- ISO 20022 preview mappings for payment initiation, payment status, and
  account statement with `not_certified: true`.
- Phase 1.1 RC readiness checklist and route-parity matrix in
  `docs/XRIQ_PHASE1_1_RC_READINESS.md`.

## Latest Validation Evidence

Latest Docker live smoke artifact:

```text
xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T223438Z
```

Latest smoke summary:

```text
xriq/target/xriq-phase1-1-local-e2e-smoke-20260531T223438Z/summary.json
```

The summary reports:

- `ok`: `xriq-phase1-1-local-e2e-smoke`
- `skipped`: `[]`
- completed steps: 60
- Docker live Postgres database: `xriq_phase1_1_smoke`
- Docker live Postgres health: `healthy`
- indexed counts: 1 block, 1 confirmed transaction, 3 accounts, 3 account
  balances, 2 account-history rows, 1 pending mempool entry, 1 audit event, and
  1 indexer run

Cheap readiness guardrail:

```bash
python scripts/xriq_phase1_1_rc_readiness.py --latest-summary --require-clean-git --require-origin-main
```

The latest post-push run reported:

- `ok`: `xriq-phase1-1-rc-readiness`
- `clean_git`: `true`
- `origin_main_matches_head`: `true`
- readiness routes checked in the matrix: 26
- required latest-smoke artifact paths checked: 14

## Route-Parity Summary

The current route parity matrix is maintained in
`docs/XRIQ_PHASE1_1_RC_READINESS.md`. At this candidate point:

- Product file-backed API routes remain the default behavior.
- Postgres-backed routes are opt-in only.
- Postgres-backed routes are GET-only/read-only.
- The Docker live smoke verifies both `request-postgres` and explicit
  Postgres-enabled `serve-readonly` for explorer, block, transaction, mempool,
  wallet, admin, snapshot, audit, and ISO preview surfaces.
- ISO 20022 payment-initiation, payment-status, and account-statement preview
  routes have product and opt-in Postgres-backed coverage.
- Admin UI Postgres status smoke verifies the available read-model state.

## Non-Production Boundaries

This RC candidate does not approve or include:

- public mainnet, public token launch, validator admission, tokenomics, or
  governance
- DEX trading, liquidity pools, bridges, CEX listings, custody, payment
  processing, stablecoins, or market-facing claims
- production signing, seed phrase handling, private-key persistence, or
  production wallet custody
- mutating product API wallet submit/send, block-production controls, snapshot
  import/export controls, smart-contract VM, or XRC asset issuance
- production GCP/Vast/server resources, TLS, public auth, rate limits,
  monitoring, external audit, legal approval, ISO certification, bank
  connectivity, SWIFT connectivity, or payment-network settlement

## Candidate Decision

The local/private Phase 1.1 candidate was ready for user review. The original
recommended action was a human decision, not more implementation:

- approve creating and pushing `phase1-1-xriq-local-e2e-rc1`, or
- request another narrow local/private fix before tagging.

It is ready to ask for explicit RC tag approval if the current branch remains
pushed/clean and this command passes:

```bash
python scripts/xriq_phase1_1_rc_readiness.py --latest-summary --require-clean-git --require-origin-main
```

Do not tag from a generic continue request. Do not create, move, or push the
proposed tag unless the user explicitly says:

```text
I explicitly approve creating and pushing the Phase 1.1 RC tag phase1-1-xriq-local-e2e-rc1.
```

After that explicit approval, run only:

```bash
git tag phase1-1-xriq-local-e2e-rc1
git push origin phase1-1-xriq-local-e2e-rc1
```

If there is no explicit tag approval, keep Phase 1.1 local/private and choose
only one next narrow task: another final gap fix, post-RC mutating feature
design, or public-XRIQ planning outside this RC.
