# XRIQ Private-Devnet Snapshot Export/Import

Status: private-devnet continuity design and MVP runner contract.

This document defines the small, file-backed snapshot workflow for the XRIQ
private devnet. It is intended to reduce Vast.ai move/rebuild time and make
local development reproducible without introducing a database, public network
sync, validator protocol, or production backup system.

## Goals

- Keep snapshots deterministic and cheap: copy the replayable chain file, the
  optional durable pending file, and a manifest.
- Make move/restore safe by default: import writes only to fresh target files
  and refuses to overwrite existing chain or pending files.
- Keep the source of truth replayable: restored chain state must pass the same
  replay/startup checks as normal `xriq-node status`.
- Preserve the current private-devnet warning and avoid public launch claims.

## Snapshot Contents

An exported snapshot directory contains:

```text
manifest.json
chain.bin
pending.tsv    # present only when --pending-file is supplied
```

The manifest uses snapshot format version
`xriq-private-devnet-snapshot-v1`. It records the chain id, current height,
latest block hash, state root, pending count, and stored block count so a future
session can compare the exported and imported state quickly.

## Commands

Export:

```bash
cargo run -p xriq-node -- snapshot-export \
  --chain-file target/xriq-devnet-chain.bin \
  --pending-file target/xriq-devnet-pending.tsv \
  --snapshot-dir target/xriq-devnet-snapshot \
  --alice-balance 100 \
  --format json
```

Import into fresh target files:

```bash
cargo run -p xriq-node -- snapshot-import \
  --snapshot-dir target/xriq-devnet-snapshot \
  --chain-file target/xriq-devnet-restored-chain.bin \
  --pending-file target/xriq-devnet-restored-pending.tsv \
  --alice-balance 100 \
  --format json
```

List and inspect local snapshots before restore:

```bash
cargo run -p xriq-node -- snapshot-list \
  --snapshot-root target \
  --limit 10 \
  --format json

cargo run -p xriq-node -- snapshot-detail \
  --snapshot-dir target/xriq-devnet-snapshot \
  --format json

cargo run -p xriq-node -- snapshot-check \
  --snapshot-dir target/xriq-devnet-snapshot \
  --alice-balance 100 \
  --format json
```

`snapshot-list` scans immediate child directories under the supplied root for
XRIQ manifests. `snapshot-detail` reads one manifest and reports the same
height/hash/state-root fields used for restore checks. `snapshot-check`
replays the snapshot's chain and optional pending file, then compares the
replayed status to the manifest before restore.

The local HTTP wrapper can expose the same discovery surface when started with
`--snapshot-root <path>`:

```bash
cargo run -p xriq-node -- serve-readonly \
  --chain-file target/xriq-devnet-chain.bin \
  --snapshot-root target

curl http://127.0.0.1:8787/v1/snapshots?limit=10
curl http://127.0.0.1:8787/v1/snapshots/xriq-devnet-snapshot
curl http://127.0.0.1:8787/v1/snapshots/xriq-devnet-snapshot/check
```

The HTTP `/check` route returns the same `snapshot-check` JSON shape as the
CLI, so operators can verify a snapshot through the local HTTP surface before
choosing to import it.

After import, verify:

```bash
cargo run -p xriq-node -- chain-check \
  --chain-file target/xriq-devnet-restored-chain.bin \
  --pending-file target/xriq-devnet-restored-pending.tsv \
  --alice-balance 100 \
  --format json
```

This replays the restored chain and validates any restored pending records.
For a read-only status view without pending validation, use:

```bash
cargo run -p xriq-node -- status \
  --chain-file target/xriq-devnet-restored-chain.bin \
  --alice-balance 100 \
  --format json
```

## Vast.ai Move Pattern

When the current GPU is still reachable, export a snapshot from the current
instance, copy the snapshot directory to the new instance or attached volume,
then import into fresh target paths on the new instance. This is cheaper than
regenerating chain state and safer than copying a live mutable chain file while
the server is writing.

Stop or pause any private-devnet writer before exporting. If a service is using
`serve-private`, stop it first or export during a known idle window.

## Non-Goals

- This is not a public-network state sync protocol.
- This is not a validator snapshot, pruning, archival-node, bridge, custody, or
  exchange-listing feature.
- This does not back up wallets, private keys, credentials, Vast SSH keys, API
  keys, `.env`, model adapters, training datasets, or OpenAI/Azure/GitHub
  credentials.
- This does not make XRIQ public-launch ready.
