# XRIQ GCP shutdown and restore handoff

Date prepared: 2026-08-09  
Project: `xriq-project-dev`  
Region: `northamerica-northeast2`  
Zone: `northamerica-northeast2-a`

## Safety and scope

This folder is the secret-free GitHub recovery record for the XRIQ
`staging-devnet`. It intentionally excludes `terraform.tfstate`,
`terraform.tfvars`, database contents, credentials, tokens, and Secret Manager
values.

The shutdown is reversible and does not destroy infrastructure:

- create an on-demand Cloud SQL backup;
- create a snapshot of the node VM boot disk;
- stop the node VM;
- set the Cloud SQL activation policy to `never`;
- retain the VPC, persistent disk, snapshots, Cloud Storage, Artifact Registry,
  Secret Manager, monitoring configuration, service accounts, and Terraform
  state.

Retained storage and network objects can continue to incur small charges. Do not
delete the project, Cloud SQL instance, VM disk, backup, snapshot, artifact
bucket, Secret Manager secret, or local Terraform state until a separate,
verified archival and destruction plan is approved.

## Current infrastructure

- Cloud SQL: `xriq-staging-devnet-postgres` (`POSTGRES_16`, database `xriq`)
- VM: `xriq-staging-devnet-node`
- Artifact bucket: `xriq-staging-devnet-artifacts-dev01a`
- Artifact Registry: `xriq-staging-devnet-containers`
- VPC: `xriq-staging-devnet-vpc`
- Database secret: `xriq-staging-devnet-db-password`
- Terraform workspace: `xriq-project-dev`

The authoritative infrastructure code remains under `infra/gcp/`. The local
Terraform state is gitignored because it contains sensitive values. Back it up
only to encrypted private storage.

## Shutdown

From the repository root, authenticate the account with access to the project:

```powershell
gcloud auth login
gcloud config set account selva@kani.network
gcloud config set project xriq-project-dev
gcloud projects describe xriq-project-dev
```

Then run:

```powershell
./backups/gcp-xriq-project-dev-2026-08-09/shutdown.ps1
```

Record the generated Cloud SQL backup ID and disk snapshot name in the execution
record below and commit this folder.

## Restore

Authenticate and select the same account/project, then run:

```powershell
./backups/gcp-xriq-project-dev-2026-08-09/restore.ps1
```

After startup, follow `docs/XRIQ_GCP_LIVE_CHAIN_SMOKE.md` to verify the node,
indexer, Cloud SQL read model, and API. If the retained instance or disk is ever
lost, recreate the infrastructure with the `xriq-project-dev` Terraform
workspace, restore the Cloud SQL backup/export and VM disk snapshot, then rerun
`deploy/gcp/vm-bootstrap.sh`.

### Portable database archive

Before project deletion, the `xriq` PostgreSQL database was exported and
downloaded outside GCP:

- Local path: `C:\Users\vselv\OneDrive\Biber\gcp-offline-backups\xriq-project-dev-2026-08-09\xriq.sql.gz`
- Compressed size: `3331` bytes
- Verified decompressed size: `19748` bytes
- SHA-256: `0DA74A24E2AA9EB8178A0DA3E589BFB4F2BD6A3A8B2574D7BB48A78251E06DE1`
- Gzip integrity: verified

The Cloud SQL service account temporarily received
`roles/storage.objectAdmin` on the artifact bucket for this export. The binding
was revoked and its absence verified immediately after download.

To restore after recreating the project and Cloud SQL instance, upload
`xriq.sql.gz` to a private bucket, grant the new Cloud SQL service account the
minimum temporary import permission, run `gcloud sql import sql`, and revoke the
permission after verification.

## Complete project cancellation

The execution environment blocked automated deletion of the whole project as an
irreversible destructive action. As of the final verification, the deletion
request had **not** reached Google. The VM was `TERMINATED` and Cloud SQL was
`STOPPED` with activation policy `NEVER`.

The project owner must run the following command directly and acknowledge its
prompt:

```powershell
gcloud config set account selva@kani.network
gcloud projects delete xriq-project-dev
```

Alternatively, shut down `xriq-project-dev` from Google Cloud Console under
IAM & Admin > Settings. Confirm the project lifecycle state afterward with
`gcloud projects describe xriq-project-dev`.

## Execution record

- Prepared by: Codex
- Shutdown status: **COMPLETED 2026-08-09**
- Cloud SQL backup ID: `1786248777582` (`ON_DEMAND`, `SUCCESSFUL`)
- Cloud SQL backup window: `2026-08-09T04:12:57.588Z` to `2026-08-09T04:13:38.146Z`
- VM disk snapshot: `xriq-staging-devnet-node-20260809-001251` (`READY`, 20 GB)
- VM post-shutdown state: `TERMINATED`
- Cloud SQL post-shutdown state: `STOPPED`, activation policy `NEVER`
- Verified account: `selva@kani.network`
- Portable database export: verified outside GCP (details above)
- Temporary export permission: revoked and verified absent
- Whole-project deletion: **PENDING MANUAL OWNER ACTION**

## Authentication blocker observed

On 2026-08-09, `selva@kani.network` was reauthenticated and used to complete the
backup, shutdown, and verification. `xriq@kani.network` was also tested but did
not have access to `xriq-project-dev` at that time.
