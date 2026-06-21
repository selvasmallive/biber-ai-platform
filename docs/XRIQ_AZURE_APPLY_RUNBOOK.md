# XRIQ Azure Apply Runbook (Human-Operated)

Status: operator runbook for provisioning the XRIQ `staging-devnet` on Azure.

These steps are run **by the human maintainer**, not by automation or by the
assistant. The assistant never runs `az login`, `terraform apply`, or handles
secrets. The repository and CI only run `terraform fmt`/`validate`.

Prerequisites:

- Azure CLI (`az`) and Terraform `>= 1.6` installed locally.
- An Azure subscription owned by `selva@kani.network` (or a least-privilege
  service principal) with rights to create the resources below.
- The SSH **public** key you will use for the node VM (the private key stays on
  your machine).

The provisioned footprint (region `eastus`, budget USD 150/mo with 80%/100%
alerts) is: resource group, VNet + subnets + NSG, Key Vault + workload identity +
container registry, private PostgreSQL Flexible Server + object storage, a small
Linux node VM, and Log Analytics + Application Insights + a consumption budget.
Estimated cost at the default SKUs is roughly USD 50-70/month; review with
`terraform plan` and the Azure pricing calculator before applying.

## 1. Authenticate and select the subscription

```bash
az login
az account set --subscription "<your-subscription-id>"
az account show --query "{name:name, id:id, tenant:tenantId}" -o table
```

## 2. Configure variables

```bash
cd infra/azure
cp terraform.tfvars.example terraform.tfvars   # terraform.tfvars is gitignored
```

Edit `terraform.tfvars`:

- `name_suffix` — a short unique suffix (3-8 lowercase alphanumeric).
- `ssh_public_key` — your SSH public key (e.g. contents of `~/.ssh/id_ed25519.pub`).
- `budget_contact_emails` — at least one address for budget alerts.
- `budget_start_date` — the first of the current month, e.g. `2026-06-01T00:00:00Z`.
- `operator_allowed_cidr` — optional; your IP as `x.x.x.x/32` to open inbound SSH.

## 3. Provide the database password out of band (not in git)

Generate a strong password and export it as an environment variable so it never
lands in a file. Optionally store it in Key Vault after the first apply.

```bash
export TF_VAR_postgres_admin_password="$(openssl rand -base64 24)"
```

## 4. Plan and review

State backend: this repo ships with **local state** (no backend block, so the
config validates without cloud access). For a first staging apply, local state is
fine — keep `infra/azure/terraform.tfstate` secure and backed up. To use remote
Azure Blob state instead, create a state storage account/container and add a
local (gitignored) `backend "azurerm"` configuration before `init`; do not commit
that backend block (the repo guard intentionally forbids it in tracked files).

```bash
terraform init
terraform plan -out tfplan
```

Read the plan carefully. Provider versions or region-specific constraints may
require small adjustments (for example a different VM size or PostgreSQL SKU if a
default is unavailable in your region/quota). Re-run `plan` until it is clean.

## 5. Apply

```bash
terraform apply tfplan
```

## 6. Post-apply

- Store the PostgreSQL admin password in Key Vault:

  ```bash
  az keyvault secret set --vault-name "<key-vault-name-from-output>" \
    --name postgres-admin-password --value "$TF_VAR_postgres_admin_password"
  ```

- Confirm the budget and alerts exist in Cost Management.
- Confirm the database has no public endpoint (private access only).
- Note the outputs (`terraform output`) for the node VM private IP, Key Vault,
  registry login server, and PostgreSQL FQDN.

## Teardown

```bash
terraform destroy
```

`purge_protection_enabled` is on for Key Vault; a destroyed vault is recoverable
during the soft-delete window. Remove the `terraform.tfvars` and any exported
password from your shell history when finished.

## Safety reminders

- Never commit `terraform.tfvars`, `*.tfstate`, the database password, or any
  secret. They are gitignored; keep them that way.
- Keep `staging-devnet` separate from any future `production-candidate`/`mainnet`
  subscription; do not share credentials, keys, or databases across environments.
- This is a private staging environment with no public financial claims.
