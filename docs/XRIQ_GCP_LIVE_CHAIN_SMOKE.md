# XRIQ GCP Live-Chain Smoke (Agent-Executable)

Status: runbook for an agent (e.g. Codex) to redeploy the updated image/config and
exercise the deployed XRIQ staging-devnet so the chain advances past genesis and
the Cloud SQL read model reflects it.

This applies two code/config updates and then smokes the live chain:

- `xriq-api` can now serve the Postgres read model directly from Cloud SQL
  (`--postgres-database-url-env XRIQ_POSTGRES_URL`); the API run wrapper enables it
  automatically when `XRIQ_POSTGRES_URL` is set.
- Staging mutation flags now include `--enable-local-wallet-send` so a block can be
  produced without a client-side signed artifact.

Preconditions: infra applied and previously deployed (project `xriq-project-dev`,
VM `xriq-staging-devnet-node`, workspace `xriq-project-dev`). Safety: never commit
or print secrets; do not print `XRIQ_POSTGRES_URL` or the DB password; do not
`git push` unless asked.

```bash
export PROJECT_ID=xriq-project-dev
export REGION=northamerica-northeast2
export ZONE=northamerica-northeast2-a
export VM=xriq-staging-devnet-node
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/xriq-staging-devnet-containers/xriq:latest"
gcloud config set project "$PROJECT_ID"
git -C "$(git rev-parse --show-toplevel)" pull --ff-only
```

## 1. Rebuild and push the image (xriq-api Cloud SQL support)

```bash
gcloud builds submit xriq --tag "$IMAGE" --project "$PROJECT_ID"
```

## 2. Redeploy (new image + updated mutation/Postgres flags)

```bash
gcloud compute scp --recurse deploy/gcp "xriqop@${VM}:~/deploy-gcp" \
  --tunnel-through-iap --zone "$ZONE" --project "$PROJECT_ID"
gcloud compute ssh "xriqop@${VM}" --tunnel-through-iap --zone "$ZONE" \
  --project "$PROJECT_ID" --command \
  "sudo PROJECT_ID='${PROJECT_ID}' REGION='${REGION}' IMAGE='${IMAGE}' bash ~/deploy-gcp/vm-bootstrap.sh"
```

`vm-bootstrap.sh` pulls the new image, rewrites `/etc/xriq/xriq.env`, and restarts
the API (now serving the read model from Cloud SQL) and the indexer timer.

## 3. Run the live-chain smoke on the VM

```bash
gcloud compute ssh "xriqop@${VM}" --tunnel-through-iap --zone "$ZONE" \
  --project "$PROJECT_ID" --command "bash ~/deploy-gcp/bin/xriq-live-smoke.sh"
```

It sends a local transfer (server-side test signing), produces a block, and
prints `OK: chain advanced from <h> to <h+1>`.

## 4. Refresh and verify the Cloud SQL read model

```bash
gcloud compute ssh "xriqop@${VM}" --tunnel-through-iap --zone "$ZONE" \
  --project "$PROJECT_ID" --command '
    sudo systemctl start xriq-indexer.service
    sleep 5
    . /etc/xriq/xriq.env
    docker run --rm --network host -e XRIQ_POSTGRES_URL="$XRIQ_POSTGRES_URL" \
      "$XRIQ_IMAGE" xriq-indexer verify-postgres \
      --database-url-env XRIQ_POSTGRES_URL --dry-run false
  '
```

## 5. Confirm the API now serves the read model from Cloud SQL

```bash
gcloud compute ssh "xriqop@${VM}" --tunnel-through-iap --zone "$ZONE" \
  --project "$PROJECT_ID" --command \
  "curl -fsS http://127.0.0.1:8090/api/v1/admin/postgres/read-model-status && echo"
```

Expect `"source": "postgres-read-model"`, `"status": "available"`, and counts with
`blocks` >= 1 and `latest_height` >= 1. Report the smoke result, the
verify-postgres counts, and the read-model-status JSON. Do not print the DB URL or
password.

## Troubleshooting

| Symptom | Fix |
|---|---|
| send returns `stale_nonce` | The smoke reads the current nonce; if you hand-craft a request, use the sender's current nonce |
| produce returns `no_pending_transactions` | Run the send step first (the smoke does this in order) |
| read-model-status 503 / env not set | Confirm `XRIQ_POSTGRES_URL` is in `/etc/xriq/xriq.env` and the API container gets `-e XRIQ_POSTGRES_URL` (it does via the wrapper) |
| `psql: connection refused` from the API | Cloud SQL private IP must be reachable from the VM (same VPC); confirm the instance is running |
