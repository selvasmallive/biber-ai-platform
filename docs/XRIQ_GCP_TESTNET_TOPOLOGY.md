# XRIQ GCP Multi-Node Testnet Topology

Version: 1.0 (deployment plan — IaC/runbook to author; operator applies)

## Purpose

Deploy the peer-sync network built in Phase 3 milestone 1 (validated sync core →
peer HTTP endpoint → follower pull loop → discovery → genesis-parametrized testnet
node) as a small **multi-node testnet** on Google Cloud: one seed node that
produces blocks + runs the faucet, and N follower nodes that stay in sync via
`peer-sync`.

> Boundaries (unchanged all session):
> - This is a **plan + IaC/runbook**. I author Terraform and systemd units;
>   **the operator (you or Codex) runs `terraform apply` / `gcloud`.** I do not
>   apply cloud resources or handle secrets.
> - Standing up nodes needs your **explicit cloud go-ahead** (no cloud resources
>   without approval — see `docs/XRIQ_PRODUCTION_ROADMAP.md` guardrails).
> - TEST-ONLY: `--network testnet`, valueless units, no monetary value. Nodes are
>   **VPC-internal by default**; the public HTTPS edge stays OFF unless
>   deliberately enabled, and even then read-only + rate-limited.
> - Real production cryptography is NOT yet in place (see
>   `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`); this testnet runs the test-only
>   signature scheme and must never bear value.

## Topology

```
              VPC (northamerica-northeast2, private)
   ┌────────────────────────────────────────────────────────┐
   │  seed VM  (xriq-testnet-seed)                           │
   │    xriq-node serve-readonly --network testnet :8899     │
   │    faucet: xriq-api --enable-local-testnet-faucet       │
   │    produces blocks (faucet-dispense on a timer / on req)│
   │                         ▲   /v1/peer/identity,blocks,peers
   │        peer-sync pull   │                               │
   │  follower VM(s)  (xriq-testnet-follower-N)              │
   │    xriq-node serve-readonly --network testnet :8899     │
   │    xriq-peer-sync.timer: peer-sync --network testnet    │
   │      --peer http://<seed>:8899  (or --peers-file)       │
   └────────────────────────────────────────────────────────┘
```

- **Seed**: authoritative producer + faucet. Serves the read routes and the peer
  endpoints (`/v1/peer/identity`, `/v1/peer/blocks`, `/v1/peer/peers`).
- **Followers**: each runs a genesis-parametrized testnet node (`serve-readonly
  --network testnet`) for its local read view, plus a `peer-sync` systemd timer
  that pulls new blocks from the seed (or a peers file for discovery). Followers
  do not produce; they validate every imported block (network isolation via the
  `xriq-testnet` chain id + protocol handshake already enforced).

## Terraform (extend `infra/gcp`)

Add a `modules/testnet` (or reuse `modules/compute` with `count`) that provisions:

- `google_compute_instance` × (1 seed + `var.follower_count` followers), private
  IP only (no external IP; IAP SSH as today), each running `deploy/gcp/vm-bootstrap.sh`.
- A VPC-internal firewall rule allowing TCP `8899` (peer + read HTTP) **only from
  the VPC subnet** (never `0.0.0.0/0`). No public ingress by default.
- Reuse existing `modules/network` (VPC + NAT), `modules/security` (Secret Manager,
  IAP SSH firewall), `modules/observability` (Ops Agent metrics/logs, alerts).
- New variables: `enable_testnet` (gate, default false), `follower_count`
  (default 1), `testnet_image` (the container image tag from `image.yml`).
- Outputs: seed internal IP/DNS so followers' peer-sync units can target it.

Keep the `enable_budget` gate and the git-tracked-only guard conventions used by
the existing `infra/gcp` and `scripts/xriq_gcp_*_check.py`.

## systemd units (add under `deploy/gcp`)

- `xriq-testnet-node.service` — `xriq-node serve-readonly --network testnet
  --chain-file /var/lib/xriq/testnet/chain.bin --bind 0.0.0.0:8899
  [--node-seed <per-vm-seed>] [--peers-file /etc/xriq/testnet-peers]`.
- `xriq-peer-sync.service` + `.timer` (followers) — `xriq-node peer-sync
  --network testnet --chain-file …/chain.bin --peer http://<seed>:8899
  --max-rounds 64` on a short interval (e.g. every 15s), mirroring the existing
  `xriq-indexer.timer` pattern.
- `xriq-testnet-faucet.service` (seed, optional) — `xriq-api serve-readonly
  --network testnet --enable-local-testnet-faucet true
  --faucet-max-per-window 5 --faucet-window-ms 60000 --chain-file …/chain.bin`.
- `xriq-testnet-producer.timer` (seed, opt-in) — produces blocks (e.g. via
  `faucet-dispense` to a burn/sink address, or a future dedicated produce loop),
  reusing the opt-in pattern of the existing `xriq-producer.timer`.

Peer/producer keys and any operator credentials live only in Secret Manager /
gitignored files — never committed (same rule as the staging-devnet DB password).

## Apply runbook (operator runs; I do not)

1. Review `infra/gcp` plan: `terraform plan` with `enable_testnet=true`,
   `follower_count=1`. Confirm no public ingress and no unexpected cost.
2. `terraform apply` (operator). Provisions seed + follower VMs.
3. On the seed: initialize the testnet chain (`xriq-node testnet-genesis` to record
   the spec hash; start `xriq-testnet-node.service`; optionally the faucet).
4. Produce at least one block on the seed (faucet-dispense to a recipient).
5. On a follower: enable `xriq-peer-sync.timer`; confirm it converges —
   `GET http://<follower>:8899/v1/chain/status` reaches the same `current_height`
   and `latest_block_hash` as the seed, and `peer-sync` reports
   `network: xriq-testnet`, `applied ≥ 1`.
6. Smoke: a faucet dispense on the seed appears on the follower after the next
   peer-sync tick (extend `deploy/gcp/bin/xriq-live-smoke.sh`).
7. Observability: confirm Ops Agent metrics/logs + alerts for both VMs.

## Verification / acceptance

- Two nodes independently report the same tip and state root (validated sync).
- A follower rejects a devnet peer (cross-network isolation) — already unit-tested;
  confirm at the network level.
- Faucet dispenses propagate seed → follower within one sync interval.
- No public ingress; VPC-internal `8899` only; budget alert green.

## Out of scope (deliberate)

- Public internet exposure of nodes/faucet (needs the public-edge module ON +
  Cloud Armor + explicit review — off by default here).
- Real cryptography (separate migration; this topology runs test-only sigs).
- Any value-bearing use — blocked pending legal + security review.
