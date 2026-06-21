# XRIQ Node / Operator Runbook (Local / Staging-Devnet)

Status: Phase 2 operator runbook for the local/private and staging-devnet
profiles. Local/private only.

This runbook describes how to build, run, observe, and recover the XRIQ
private-devnet node and API on a developer machine. It covers the `local` and
`staging-devnet` environment profiles. It does **not** deploy to any cloud, run
public-network behavior, handle secrets or keys, or create cloud resources.
Actual cloud deployment (Azure) is a later, human-gated step; see
`docs/XRIQ_AZURE_PROVIDER_DECISION.md` and the "Cloud deployment" note at the
end.

## Safety boundaries

- All commands run locally. No `az login`, `terraform apply`, secrets, or
  credentials are involved.
- The wallet/browser never holds private keys, seed phrases, mnemonics, or raw
  signatures. Signing is test-only and server/CLI-side.
- Accepted mutations are disabled by default and require explicit local flags.
- `staging-devnet` is a production-like *profile label*, not a public network. It
  must never be described as mainnet, exchange-ready, or custody-ready.

## Prerequisites

- Rust toolchain (stable; this repo builds with cargo `1.95`).
- Python 3.12+ for the smokes and guard scripts (uses only the standard library).
- Node.js 22+ only if working on the explorer-ui.
- Windows + OneDrive note: set `CARGO_TARGET_DIR` to a path outside the OneDrive
  tree to avoid transient `LNK1104` linker locks, e.g.
  `export CARGO_TARGET_DIR="$HOME/xriq-target"`.

## Build

```bash
cd xriq
cargo build -p xriq-node -p xriq-api -p xriq-wallet
```

## Environment profiles

Both binaries accept an optional `--environment local|staging-devnet` flag. It is
fail-closed: `production`, `mainnet`, `public-testnet`, and unknown values are
rejected. It defaults to `local`, so omitting it preserves existing behavior.

```bash
# accepted
xriq-api  request --chain-file <path> --target /api/v1/health --environment staging-devnet
xriq-node status  --chain-file <path> --environment staging-devnet

# rejected (exits non-zero)
xriq-api  request --chain-file <path> --target /api/v1/health --environment production
```

See `docs/XRIQ_PHASE2_CONFIG_SEPARATION.md` for the design.

## Run the node

Read-only HTTP server (no mutations):

```bash
xriq-node serve-readonly --chain-file target/xriq-devnet.bin --alice-balance 100 --bind 127.0.0.1:8787
```

Common read CLI commands (text or `--format json`):

```bash
xriq-node status            --chain-file target/xriq-devnet.bin --alice-balance 100 --format json
xriq-node chain-check       --chain-file target/xriq-devnet.bin --pending-file target/xriq-devnet-pending.tsv
xriq-node mempool-detail    --chain-file target/xriq-devnet.bin --pending-file target/xriq-devnet-pending.tsv --format json
xriq-node explorer-overview --chain-file target/xriq-devnet.bin --format json
```

Run `xriq-node help` for the full command and flag list.

## Run the API

One-shot request mode (used by the smokes; each call is a fresh process):

```bash
xriq-api request --chain-file <chain> --pending-file <pending> --alice-balance 100 \
  --target /api/v1/health
```

Read-only server:

```bash
xriq-api serve-readonly --chain-file <chain> --pending-file <pending> --alice-balance 100 \
  --bind 127.0.0.1:8090
```

### Accepted local mutations (disabled by default)

Each accepted mutation path is off unless its explicit flag is set, and is only
usable under a non-production profile:

- `--enable-local-wallet-submit true`
- `--enable-local-wallet-send true`
- `--enable-local-wallet-submit-signed true`
- `--enable-local-block-production true`

The signed-submit lifecycle (CLI-only signed artifact -> accepted pending submit
-> local block -> confirmed read-back) is exercised end to end by
`scripts/xriq_phase1_4_signed_submit_lifecycle_smoke.py`.

## Pending file: format and recovery

Pending transactions persist as tab-separated `xriq-pending-transaction-v1`
records in the pending file. On startup/replay the node is resilient:

- **Duplicate entries** (e.g. a crash mid-append) replay idempotently and do not
  brick startup.
- **Corrupt/unparseable lines** are quarantined to a `<pending-file>.quarantine`
  sidecar (with a `xriq-pending-quarantine-v1` marker) and self-healed out of the
  live pending file exactly once. This is recovery, not silent loss: the original
  content is preserved in the sidecar.

Recovery procedure for a suspect pending file:

1. Stop any running node/API process.
2. Run a read command (for example `xriq-node mempool-detail ...`). The node
   recovers automatically: duplicates are skipped and corrupt lines are moved to
   the sidecar.
3. Inspect `<pending-file>.quarantine` to review anything that was quarantined.
4. Re-run the smokes (below) to confirm a healthy state.

## Snapshots

The node supports snapshot export/import for chain and pending state
(`xriq-node snapshot-export`, `snapshot-import`, `snapshot-list`,
`snapshot-check`, ...). Run `xriq-node help` for exact flags. Snapshots are the
local backup/restore mechanism for the devnet state.

## Smokes and guards

Clean-clone staging smokes (build once; lifecycle local + restart/recovery under
staging-devnet):

```bash
python scripts/xriq_phase2_staging_smokes.py
```

Individual smokes:

```bash
python scripts/xriq_phase1_4_signed_submit_lifecycle_smoke.py
python scripts/xriq_phase2_restart_recovery_smoke.py --environment staging-devnet
```

Cheap documentation/guard checks (no build required):

```bash
python scripts/xriq_phase2_plan_check.py
python scripts/xriq_azure_provider_decision_check.py
python scripts/xriq_production_roadmap_check.py
python scripts/xriq_private_devnet_wrapup_check.py
```

Rust tests and explorer-ui checks:

```bash
cd xriq && cargo test --workspace -j 1
cd xriq/apps/explorer-ui && npm ci && npm run check && npm run build
```

CI runs all of the above on every push (see `.github/workflows/ci.yml`).

## Incident quick reference

| Symptom | Action |
|---|---|
| Node won't start on a pending file | A read command auto-recovers; check `<pending-file>.quarantine` for moved lines. |
| Unexpected `unsupported_environment` error | The `--environment` value is not `local`/`staging-devnet`; production-class values are rejected by design. |
| Accepted mutation returns a `*_disabled` refusal | The matching `--enable-local-*` flag was not set; this is the safe default. |
| Windows `LNK1104` during build | Point `CARGO_TARGET_DIR` outside OneDrive and rebuild. |
| Need to verify end-to-end health | Run `python scripts/xriq_phase2_staging_smokes.py`. |

## Cloud deployment (Azure) — not part of this runbook

This runbook is local/staging only. Azure is the selected provider
(`docs/XRIQ_AZURE_PROVIDER_DECISION.md`) with provider-neutral Terraform module
boundaries under `infra/azure/`, but **no cloud resources are created** and the
modules are boundaries only. Standing up Azure is a later, human-gated step:
implement the module resources, then a human runs `az login` and
`terraform plan`/`apply` against an approved subscription. None of that is
required to operate the local/staging devnet described here.
