# BIBER AI Platform

Private GPU-backed AI platform for:

- `biber-dev-core` software-development model
- `biber-video-core` video processing
- `biber-audio-core` audio processing
- `biber-proctor-core` online proctoring workflows
- API key + passcode access
- GPU-priority job scheduling
- OpenAI-compatible local GPU inference through vLLM
- Optional OpenAI mentor layer
- GitHub save and Azure Blob backup hooks

This repo is intentionally separate from KANI/XRIQ. It is the standalone BIBER workspace and GitHub repo.

---

## 1. Quick Start On GPU Server

After SSH login to your Vast.ai GPU instance:

```bash
apt update
apt install -y git curl nano htop tmux unzip mysql-client
```

Upload or clone this repo, then run the direct Vast.ai path:

```bash
cd biber-ai-platform
cp .env.example .env
bash scripts/vast_bootstrap_direct.sh
```

If your GPU template has Docker and the NVIDIA container runtime available, the older Compose path is still available with `bash scripts/02_start.sh`.

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Use SSH port forwarding for local access:

```bash
ssh -i <path-to-key> -p <port> root@<host> -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

See `docs/VAST_DIRECT_DEPLOY.md` for the repeatable fresh-GPU deployment runbook.

If the old Vast.ai instance and volume have been terminated, start with
`readme-resume-biber.md` before recreating the runtime.
If you backed up `/workspace` artifacts locally and want to upload them to a new
GPU/volume, use `readme-reinstantiate.md`.

---

## 2. Services

| Service | Purpose |
|---|---|
| `api` | FastAPI public/admin API |
| `worker` | GPU model worker placeholder |
| `biber-dev-core` | vLLM OpenAI-compatible coding model runtime |
| `mysql` | MySQL database |
| `redis` | Queue/cache |
| `adminer` | Web DB viewer |
| `postgres` | Optional local XRIQ Phase 1.1 PostgreSQL read model |

On no-Docker Vast.ai templates, `scripts/vast_bootstrap_direct.sh` starts only `api` and `biber-dev-core`. MySQL, Redis, and Adminer remain Docker-only until a managed database/queue path is added.

---

## 3. Default Admin

```text
Username: biber_admin
Password: ChangeMeImmediately!123
```

Change this immediately before production use.

---

## 4. API Authentication

Public API requests require:

```http
Authorization: Bearer <API_KEY>
X-Biber-Passcode: <OPTIONAL_PASSCODE>
```

The API also accepts `x-api-key` for OpenAI-style clients. Starter API keys in `.env.example`:

```text
dev-api-key-change-me
dev-biber-key-change-me
```

Starter passcodes:

```text
BIBER_FULL_GPU_DEMO
BIBER_20_GPU_DEMO
BIBER_QUEUE_PRIORITY_DEMO
```

---

## 5. Phase 1 Success Criteria Mapping

```text
1. BIBER API runs on GPU              -> docker-compose.yml api service
2. /v1/chat endpoint works            -> app/main.py
3. OpenAI mentor service is connected -> app/llm.py optional mentor client
4. biber-dev-core can generate code   -> vLLM service named biber-dev-core
5. Code output can be saved to GitHub -> /v1/save/github and chat save option
6. Models/data can be backed up       -> /v1/backup/azure and chat backup option
7. XRIQ private-devnet read/preflight flows -> /v1/xriq/private-devnet/*
```

## 6. Chat Example

`/v1/models` exposes logical BIBER model IDs separately from the served vLLM
model name. The stable model is `biber-dev-core-v1`, currently backed by the
local `biber-dev-core` Qwen2.5-Coder runtime. The disabled candidate slot
`biber-dev-core-v2-candidate` is reserved for Qwen3-Coder or a newer model after
benchmarks justify promoting it.

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "biber-dev-core-v1",
    "language": "TypeScript",
    "repo_context_paths": ["src/components/SearchBox.tsx"],
    "messages": [
      {
        "role": "user",
        "content": "Create a React hook that debounces a search query."
      }
    ]
  }'
```

`repo_context_paths` is intentionally selected-file context, not automatic repo
crawling. It is bounded by `BIBER_REPO_CONTEXT_MAX_FILES`,
`BIBER_REPO_CONTEXT_MAX_BYTES_PER_FILE`, and
`BIBER_REPO_CONTEXT_MAX_TOTAL_BYTES`; obvious secret paths such as `.env` and
private key files are rejected.

OpenAI mentor review is optional and costed. Configure `BIBER_MENTOR_ENABLED`,
`OPENAI_API_KEY`, and `OPENAI_MODEL` on the server, then opt in per prompt with
the phrase `Review with OpenAI mentor`:

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "Rust",
    "messages": [
      {
        "role": "user",
        "content": "Review with OpenAI mentor: Review this XRIQ wallet signing plan."
      }
    ]
  }'
```

To use the older queue-only starter behavior:

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"message":"Create a FastAPI health endpoint","queue_only":true}'
```

XRIQ private-devnet read and preflight flows are exposed through thin BIBER
wrappers around the local Rust runner. Chain and pending-file paths are
server-side configuration, so the request only supplies transfer values:

```bash
curl -X POST http://localhost:8000/v1/xriq/private-devnet/preflight-transfer \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "xriqdev1alice00000000000",
    "to": "xriqdev1bobbb00000000000",
    "amount_base_units": "25",
    "fee_base_units": "2",
    "expires_at_height": 100,
    "timestamp_ms": 1000
  }'
```

Read-only helpers are also available:

```bash
curl http://localhost:8000/v1/xriq/private-devnet/status \
  -H "Authorization: Bearer dev-api-key-change-me"

curl 'http://localhost:8000/v1/xriq/private-devnet/explorer?limit=5' \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/blocks/1 \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/accounts/xriqdev1alice00000000000 \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/transactions/<transaction-hash> \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/mempool \
  -H "Authorization: Bearer dev-api-key-change-me"
```

On the Vast direct deployment, the XRIQ API read wrappers can be checked
together without mutating the chain. The smoke follows a transaction hash from
the latest block when block detail exposes one:

```bash
bash scripts/vast_xriq_api_smoke.sh
```

For GPU-off XRIQ development, run the isolated Rust/Cargo transfer smoke. It
uses fresh chain files under `xriq/target/` and does not touch any restored
BIBER API runtime state:

```bash
python scripts/xriq_private_devnet_transfer_smoke.py
```

To also verify the local submit-capable HTTP/RPC path without Vast, run:

```bash
python scripts/xriq_private_devnet_http_smoke.py
```

That smoke also covers local HTTP snapshot export/import using fresh files under
`xriq/target/`, including confirmed transaction lookup and the latest
transaction-list endpoint.

To run the full CPU-only Phase 1 local validation set from this workstation,
including Rust format/test/clippy checks, the transfer and HTTP smokes, and the
critical smoke artifact checks for snapshot restore/latest/check outputs, run:

```bash
python scripts/xriq_phase1_local_check.py
```

The Phase 1 private-devnet release-candidate checklist is in
`docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md`.
The current RC decision report is in `docs/XRIQ_PHASE1_RC_REPORT.md`.
The post-RC end-to-end Phase 1.1 plan is in
`docs/XRIQ_PHASE1_1_END_TO_END_PLAN.md`.
The Phase 1.1 API/database contract baseline is in
`docs/XRIQ_PHASE1_1_CONTRACTS.md`.
The GCP resource plan for Phase 1.1 is in `docs/XRIQ_GCP_RESOURCE_PLAN.md`.
Validate the Phase 1.1 schema and fixtures locally with
`python scripts/xriq_phase1_1_contract_check.py`.
The first Rust Milestone B indexer scaffold is `xriq/crates/xriq-indexer`; test
it from `xriq/` with `cargo test -p xriq-indexer`.

The first Rust API service-boundary scaffold is `xriq/crates/xriq-api`; test it
from `xriq/` with `cargo test -p xriq-api`. It defines product-facing
private-devnet response models plus `/api/v1/...` route/render behavior over
the indexed read model, including read-only wallet status/account/transaction
status and draft-preview routes plus GET-only ISO 20022 preview routes. It
includes a local read-only socket server for private-devnet smoke testing. Pass
`--pending-file <path>` to inspect an
existing durable private-devnet pending TSV in `/api/v1/mempool`; this remains
read-only and lets `/api/v1/wallet/transactions/{hash}/status` report pending
transaction hashes without enabling wallet submission or block production in
`xriq-api`.

```bash
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/health
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target /api/v1/wallet/status
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target '/api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000&to_address=xriqdev1bobbb00000000000&amount_base_units=25&fee_base_units=2&nonce=1&expires_at_height=100'
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --target '/api/v1/mempool?limit=5'
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --target '/api/v1/wallet/transactions/<pending-tx-hash>/status'
cargo run -p xriq-api -- request --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --target '/api/v1/iso20022/transactions/<confirmed-tx-hash>/status'
cargo run -p xriq-api -- serve-readonly --chain-file target/xriq-indexer-replay-smoke.bin --pending-file target/xriq-devnet-pending.tsv --alice-balance 100 --bind 127.0.0.1:8090
```

The first ISO 20022 compatibility adapter scaffold is
`xriq/crates/xriq-iso20022`; test it from `xriq/` with
`cargo test -p xriq-iso20022`. It creates private-devnet preview mappings only;
`xriq-api` exposes those mappings through read-only private-devnet preview
routes. This does not claim ISO certification, bank connectivity, SWIFT
connectivity, or production payment-network support.

The first React + TypeScript explorer, wallet-preview, and admin-status UI shell
is in `xriq/apps/explorer-ui`. It is a local private-devnet dashboard that reads
the `xriq-api` `/api/v1/...` routes through Vite's same-origin `/api` proxy,
shows basic block, transaction, and account detail panels, includes a
preview-only wallet transfer draft surface wired to the product wallet
draft-preview API, includes a read-only ISO 20022 preview panel wired to the
product ISO routes, and shows a read-only admin status panel for node, network,
indexer, wallet capability, mempool status, optional Postgres read-model
status, snapshot catalog, and audit-event state. The wallet panel does not
sign, submit, persist, or manage private keys.

```powershell
cd xriq
cargo run -p xriq-api -- serve-readonly --chain-file target\xriq-indexer-replay-smoke.bin --pending-file target\xriq-devnet-pending.tsv --alice-balance 100 --bind 127.0.0.1:8090

cd apps\explorer-ui
npm.cmd install
npm.cmd run check
npm.cmd run check:postgres-ui -- --base-url http://127.0.0.1:8090 --expect disabled
npm.cmd run build
npm.cmd run dev -- --port 5173
```

To replay an existing local chain file into the current in-memory read model,
run:

```bash
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format json
```

To emit an idempotent local PostgreSQL write plan for the same replay, use:

```bash
cargo run -p xriq-indexer -- replay --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --format sql
```

To validate the local PostgreSQL apply path without touching a database:

```bash
cargo run -p xriq-indexer -- apply-postgres --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --schema-file db/schema.sql --dry-run true
```

The Phase 1.1 local smoke can also validate the generated SQL inside the
optional Compose Postgres container without host `psql`. This is explicit and
local-only: it starts/uses `postgres`, resets only the dedicated
`xriq_phase1_1_smoke` database schema, applies the generated write plan, and
writes a live-count artifact under the smoke output directory.

```powershell
python scripts\xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live
```

The same live smoke verifies the first explicit Postgres-backed API read paths,
including `/api/v1/admin/postgres/read-model-status` and the opt-in
Postgres-backed `/api/v1/admin/indexer/status`,
`/api/v1/explorer/overview`, `/api/v1/blocks?limit=5`, and
`/api/v1/transactions?limit=5` plus `/api/v1/transactions/{tx_hash}` and
`/api/v1/wallet/transactions/{tx_hash}/status` plus
`/api/v1/accounts?limit=5` plus `/api/v1/accounts/{address}` and
`/api/v1/accounts/{address}/transactions?limit=5` plus
`/api/v1/wallet/accounts?limit=5` plus
`/api/v1/wallet/accounts/{address}/balance` plus
`/api/v1/wallet/accounts/{address}/history?limit=5` plus
`/api/v1/admin/audit-events?limit=5`, plus the Admin UI's
Postgres read-model row mapping. It writes
`indexer/postgres-api-explorer-overview.json`,
`indexer/postgres-server-explorer-overview.json`,
`indexer/postgres-api-blocks.json`, `indexer/postgres-server-blocks.json`,
`indexer/postgres-api-transactions.json`,
`indexer/postgres-server-transactions.json`,
`indexer/postgres-api-transaction-detail.json`,
`indexer/postgres-server-transaction-detail.json`,
`indexer/postgres-api-wallet-transaction-status.json`,
`indexer/postgres-server-wallet-transaction-status.json`,
`indexer/postgres-api-accounts.json`, `indexer/postgres-server-accounts.json`,
`indexer/postgres-api-wallet-accounts.json`,
`indexer/postgres-server-wallet-accounts.json`,
`indexer/postgres-api-account-detail.json`,
`indexer/postgres-server-account-detail.json`,
`indexer/postgres-api-wallet-balance.json`,
`indexer/postgres-server-wallet-balance.json`,
`indexer/postgres-api-account-history.json`,
`indexer/postgres-server-account-history.json`,
`indexer/postgres-api-wallet-account-history.json`,
`indexer/postgres-server-wallet-account-history.json`,
`indexer/postgres-api-indexer-status.json`,
`indexer/postgres-server-indexer-status.json`,
`indexer/postgres-api-audit-events.json`,
`indexer/postgres-server-audit-events.json`,
and
`indexer/postgres-admin-ui-read-model-status.json` under the smoke output
directory:

```powershell
cd xriq
cargo run -p xriq-api -- request-postgres --target /api/v1/admin/postgres/read-model-status
cargo run -p xriq-api -- request-postgres --target /api/v1/admin/indexer/status
cargo run -p xriq-api -- request-postgres --target /api/v1/admin/audit-events?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/explorer/overview
cargo run -p xriq-api -- request-postgres --target /api/v1/blocks?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/transactions?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/transactions/<tx_hash>
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/transactions/<tx_hash>/status
cargo run -p xriq-api -- request-postgres --target /api/v1/accounts?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/accounts?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/accounts/<address>
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/accounts/<address>/balance
cargo run -p xriq-api -- request-postgres --target /api/v1/accounts/<address>/transactions?limit=5
cargo run -p xriq-api -- request-postgres --target /api/v1/wallet/accounts/<address>/history?limit=5
```

To expose that read-model status, explorer overview, block list, transaction
list, transaction detail, wallet transaction status, account list, wallet
account list, account detail, wallet balance, account history, and wallet
account history, audit events, and indexer status through the local read-only
HTTP server, pass both explicit Postgres flags.
Without these flags, `serve-readonly` stays file-backed and the Postgres status
route remains disabled.

```powershell
cargo run -p xriq-api -- serve-readonly --chain-file target\xriq-indexer-replay-smoke.bin --pending-file target\xriq-devnet-pending.tsv --alice-balance 100 --bind 127.0.0.1:8090 --postgres-docker-container xriq-postgres --postgres-database xriq_phase1_1_smoke
```

To start the optional local XRIQ PostgreSQL read model and verify counts after
an explicit apply, use the local-only dev URL below:

```powershell
docker compose up -d postgres
$env:XRIQ_POSTGRES_URL = "postgresql://xriq:xriq-local-dev-password@localhost:5433/xriq_private_dev"
cargo run -p xriq-indexer -- apply-postgres --chain-file target/xriq-indexer-replay-smoke.bin --alice-balance 100 --schema-file db/schema.sql --dry-run false
cargo run -p xriq-indexer -- verify-postgres --database-url-env XRIQ_POSTGRES_URL --dry-run false
```

After a clean local check, future sessions can cheaply re-check the latest
Phase 1 summary and checklist pointers without rerunning Rust:

```bash
python scripts/xriq_phase1_rc_readiness.py --require-clean-git --require-origin-main --require-rc-tag-available
```

## 7. Vast Connection Needed

To deploy this to your Vast.ai GPU, use the instance SSH command:

```text
ssh -p <port> <user>@<host>
```

If the instance uses an SSH key, use the local key path. Do not paste private key contents into chat.

## 8. Important Production Notes

This starter is intentionally simple. Before production:

- Hash API keys and passcodes
- Replace demo auth with database-backed auth
- Add HTTPS
- Add proper queue workers
- Add model weights volume
- Add audit logs to database
- Use Kubernetes/AKS for multi-node production
- Add real GPU quota/preemption logic using containers/MIG/Kubernetes device plugins
