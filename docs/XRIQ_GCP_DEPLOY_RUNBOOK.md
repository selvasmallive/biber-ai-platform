# XRIQ GCP Deploy Runbook (Agent-Executable)

Status: runbook for an autonomous agent (e.g. Codex) to deploy the XRIQ services
onto the already-provisioned GCP `staging-devnet`.

Preconditions: the infra is applied (`infra/gcp`, Terraform workspace
`xriq-project-dev`), `gcloud` and `terraform` are available, and the agent may
authenticate and run cloud operations. Provisioned facts used below:

- Project: `xriq-project-dev`, region `northamerica-northeast2`, zone
  `northamerica-northeast2-a`.
- Node VM: `xriq-staging-devnet-node` (no external IP; reach it via IAP).
- Cloud SQL private IP `10.103.0.3`, db `xriq`, user `xriqpgadmin`, password in
  Secret Manager `xriq-staging-devnet-db-password`.
- Artifact Registry repo `xriq-staging-devnet-containers`.

Safety: never commit or print secrets. Do not commit `terraform.tfvars`,
`*.tfstate`, `tfplan`, `/etc/xriq/xriq.env`, or the DB password. Do not `git push`
unless asked.

Set these shell variables first:

```bash
export PROJECT_ID=xriq-project-dev
export REGION=northamerica-northeast2
export ZONE=northamerica-northeast2-a
export VM=xriq-staging-devnet-node
export IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/xriq-staging-devnet-containers/xriq:latest"
gcloud config set project "$PROJECT_ID"
```

## 1. Add the IAP SSH firewall rule (Terraform)

The VM has no public IP; SSH goes through IAP, which needs a firewall rule
(`enable_iap_ssh`, default true). Re-apply to create it. Reuse the existing DB
password from Secret Manager so the Cloud SQL user is unchanged.

```bash
cd infra/gcp
terraform workspace select xriq-project-dev
export TF_VAR_postgres_admin_password="$(gcloud secrets versions access latest \
  --secret=xriq-staging-devnet-db-password --project="$PROJECT_ID")"
terraform apply -auto-approve
cd ../..
```

Grant yourself IAP access if needed:

```bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/iap.tunnelResourceAccessor"
```

## 2. Build and push the image (Cloud Build)

```bash
gcloud services enable cloudbuild.googleapis.com --project "$PROJECT_ID"
gcloud builds submit xriq --tag "$IMAGE" --project "$PROJECT_ID"
```

`gcloud builds submit xriq` uses `xriq/` as the build context and
`xriq/Dockerfile`, then pushes to Artifact Registry.

## 3. Copy the deploy files to the VM (over IAP)

```bash
gcloud compute scp --recurse deploy/gcp "xriqop@${VM}:~/deploy-gcp" \
  --tunnel-through-iap --zone "$ZONE" --project "$PROJECT_ID"
```

## 4. Run the bootstrap on the VM (over IAP)

```bash
gcloud compute ssh "xriqop@${VM}" --tunnel-through-iap --zone "$ZONE" \
  --project "$PROJECT_ID" --command \
  "sudo PROJECT_ID='${PROJECT_ID}' REGION='${REGION}' IMAGE='${IMAGE}' bash ~/deploy-gcp/vm-bootstrap.sh"
```

The bootstrap installs Docker, authenticates to Artifact Registry (as the VM's
service account, which has `artifactregistry.reader` and
`secretmanager.secretAccessor`), pulls the image, writes `/etc/xriq/xriq.env`
(mode 600) with the DB URL from Secret Manager, initializes the chain with
deterministic genesis, installs the systemd units, and starts `xriq-api.service`
plus the `xriq-indexer.timer`.

## 5. Verify

```bash
gcloud compute ssh "xriqop@${VM}" --tunnel-through-iap --zone "$ZONE" \
  --project "$PROJECT_ID" --command '
    set -e
    systemctl is-active xriq-api
    curl -fsS http://127.0.0.1:8090/api/v1/health && echo
    systemctl list-timers xriq-indexer.timer --no-pager | head
    sudo systemctl start xriq-indexer.service
    journalctl -u xriq-indexer -n 20 --no-pager
  '
```

Then confirm the Cloud SQL read model was populated (from the VM, which can reach
the private DB):

```bash
gcloud compute ssh "xriqop@${VM}" --tunnel-through-iap --zone "$ZONE" \
  --project "$PROJECT_ID" --command '
    . /etc/xriq/xriq.env
    docker run --rm --network host -e XRIQ_POSTGRES_URL="$XRIQ_POSTGRES_URL" \
      "$XRIQ_IMAGE" xriq-indexer verify-postgres \
      --database-url-env XRIQ_POSTGRES_URL --dry-run false
  '
```

Report to the user: API health, indexer last run, and the verify-postgres output
(table row counts). Do not print `XRIQ_POSTGRES_URL` or the password.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `gcloud compute ssh ... IAP` fails to connect | Ensure step 1 applied the IAP rule and you have `roles/iap.tunnelResourceAccessor` |
| `docker pull` denied on the VM | The VM SA needs `artifactregistry.reader` (granted by Terraform); re-run `gcloud auth configure-docker ${REGION}-docker.pkg.dev` |
| `xriq-api` container exits immediately | `journalctl -u xriq-api -n 50`; check `/etc/xriq/xriq.env` and that `/var/lib/xriq` is owned by uid 10001 |
| indexer `psql: could not connect` | Confirm Cloud SQL private IP `10.103.0.3` is reachable from the VM (same VPC) and the password in Secret Manager is current |
| Cloud Build permission denied pushing to AR | Grant the Cloud Build service account `roles/artifactregistry.writer` on the repo, re-run the build |

## Teardown of the services (infra stays)

```bash
gcloud compute ssh "xriqop@${VM}" --tunnel-through-iap --zone "$ZONE" \
  --project "$PROJECT_ID" --command \
  "sudo systemctl disable --now xriq-api.service xriq-indexer.timer"
```
