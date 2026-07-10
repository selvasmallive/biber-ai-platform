# XRIQ GCP Staging-Devnet Deployment

Deploys the XRIQ node/API/indexer onto the provisioned GCP `staging-devnet`
(see `../../docs/XRIQ_GCP_PROVIDER_DECISION.md` and `../../infra/gcp/`).

What this deploys:

- A container image (`../../xriq/Dockerfile`) with `xriq-node`, `xriq-api`, and
  `xriq-indexer` plus the `psql` client, pushed to Artifact Registry.
- A single **`xriq-api serve-readonly`** service on the node VM (file-backed chain
  under `/var/lib/xriq`), bound on the VPC, with staging accepted-mutation flags.
  A single process is the sole writer of the chain files, so there is no shared
  file contention.
- A periodic **indexer** (`systemd` timer) that populates the private Cloud SQL
  read model via `xriq-indexer apply-postgres` (which supports a real connection
  string). The DB password comes from Secret Manager; it is never committed.

What is NOT deployed (documented follow-up): serving the read model *from* Cloud
SQL through `xriq-api`. That path is docker-only in the current code
(`--postgres-docker-container`) and needs a native PostgreSQL client added to
`xriq-api` before the API can read from Cloud SQL. Today the API serves a
file-backed read model, and the indexer writes chain data into Cloud SQL.

Files:

- `../../xriq/Dockerfile`, `../../xriq/.dockerignore` — the image.
- `bin/xriq-api-run.sh`, `bin/xriq-indexer-run.sh` — container run wrappers.
- `systemd/xriq-api.service`, `systemd/xriq-indexer.service`,
  `systemd/xriq-indexer.timer` — services.
- `xriq.env.example` — the `/etc/xriq/xriq.env` template (no secrets).
- `vm-bootstrap.sh` — installs Docker, pulls the image, writes the env file from
  Secret Manager, initializes the chain, and starts the services.

Run it with `../../docs/XRIQ_GCP_DEPLOY_RUNBOOK.md` (agent-executable).
