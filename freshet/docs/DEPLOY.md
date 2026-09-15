# Deploying the site, and the DNS to go with it

Everything here is yours to run. The parts involving credentials, terms of
service, or spend are deliberately not automated.

## Order

The signing key comes first and is the one irreversible step.

### 1. The signing key — generated and in Secret Manager

Generated 2026-08-16. Its public half is in `crates/freshet-license/src/sign.rs`
and a test fails if it ever reverts to the placeholder.

Checked 2026-09-15: secret `freshet-signing-key` exists in `freshet-licence`,
version 1, enabled, created 2026-08-16T17:14:27 — about half an hour after the
local file was written. Billing is linked and `secretmanager.googleapis.com` is
enabled. **Nothing further to run here.**

The private half is also still at
**`C:\Users\vselv\.freshet\freshet-signing-key.hex`** — deliberately outside
OneDrive, so it is not being synced to a cloud folder.

**The one thing still outstanding is a copy that is not Google.** Secret
Manager is where the *service* reads the key from; it is not a backup, because
losing access to the project loses the key with it. Put a second copy in a
password manager, or print it and file it.

Only once that exists should the local file be deleted.

**This key cannot be rotated cheaply.** Its public half is compiled into every
installed copy of Freshet, so replacing it invalidates every licence already in
customers' hands. The keygen refuses to write inside a git working tree for
that reason, and the key has never been committed.

The service refuses to start if the key it holds does not match the key the app
trusts, so a mismatch is a failed deploy rather than a month of customers who
paid and cannot file.

### 2. Sign in — and know which failure you are looking at

Checked on 2026-09-15: **authentication works.** `gcloud projects list` returns
`freshet-licence` against `selva@freshettax.ca`. If you are staring at this
after running `gcloud auth login`, read the next paragraph before running it a
fourth time.

`gcloud auth login` completes the browser flow, saves the credential, and
*then* fails with:

```
ERROR: (gcloud.auth.login) Error saving Application Default Credentials:
Unable to create private file [...\legacy_credentials\selva@freshettax.ca\adc.json]:
[Errno 13] Permission denied
```

This is a local filesystem problem, not an authentication one, and **it does
not block anything in this runbook.** Application Default Credentials are what
client *libraries* read; `deploy.sh` and every command here use the gcloud CLI,
which reads a different store that saved fine. The sign-in you just did
worked — the error at the end is about a file written afterwards.

The cause is a broken ACL on one directory. Its parent grants
`SELVA-DESKT-W11\vselv:(I)(OI)(CI)(F)`, but the account subdirectory denies
even reading its own ACL, and the parent's ACL carries a
`Selva-Deskt-W11\CodexSandboxUsers` entry — something running sandboxed
appears to have created it. `vselv` is not a local administrator, so repairing
the ACL in place needs elevation.

Fix it only if you need ADC (Terraform, or running the service locally against
Cloud SQL). Deleting the directory is enough, because it holds a derived cache
rather than the authoritative credential, and the parent grants you the rights
to remove it:

```powershell
Remove-Item -Recurse -Force "$env:APPDATA\gcloud\legacy_credentials\selva@freshettax.ca"
gcloud auth application-default login
```

### 2a. Use the freshet configuration, not the default

`deploy.sh` takes its project from `gcloud config get-value project`, and the
**default** configuration on this machine points at `biber-499407` — a
different product. Running the deploy under it would put the licence service,
its database and its secrets in the wrong project, all billable.

A separate configuration now exists so the two cannot be confused, and the
default is left alone:

```bash
gcloud config configurations activate freshet
gcloud config get-value project     # must print freshet-licence
```

It holds project `freshet-licence`, account `selva@freshettax.ca`, and region
`northamerica-northeast1`. Switch back with `gcloud config configurations
activate default`.

**On the duplicate project.** The billing console showed two licence-shaped
projects. `freshet-licence-508706` is already `DELETE_REQUESTED` (created
2026-09-15 06:14) and will fall off the billing account on its own. The live
one is `freshet-licence`, created 2026-08-16, `ACTIVE`. Nothing to do.

Billing is enabled on the account. Enabling any further paid API is a spend
decision and a terms acceptance, so those stay yours.

### 3. Deploy

Nothing is deployed yet, and the APIs a deploy needs are off: as of 2026-09-15
`run.googleapis.com` and `sqladmin.googleapis.com` are both disabled on
`freshet-licence`. `deploy.sh` will offer to enable them. That is the point
where this stops being free, so read the script before answering yes.

```bash
cd freshet/site/deploy && ./deploy.sh
```

The region defaults to `northamerica-northeast1` (Montréal). Customer records
for a Canadian tax product should stay in Canada — not strictly required by
PIPEDA, but it removes a question you would otherwise have to answer in public.

### 4. Load balancer, certificate, IAP

The admin pages trust an IAP-set header. **A header is only trustworthy if
nothing can reach the service without passing through IAP**, which is why the
deploy sets `--ingress internal-and-cloud-load-balancing`. Skipping the load
balancer does not merely lose HTTPS — it makes the admin area world-readable.

```bash
gcloud compute addresses create freshet-ip --global

gcloud compute network-endpoint-groups create freshet-neg \
  --region=northamerica-northeast1 \
  --network-endpoint-type=serverless \
  --cloud-run-service=freshet-site

gcloud compute backend-services create freshet-backend \
  --global --load-balancing-scheme=EXTERNAL_MANAGED

gcloud compute backend-services add-backend freshet-backend \
  --global --network-endpoint-group=freshet-neg \
  --network-endpoint-group-region=northamerica-northeast1

gcloud compute ssl-certificates create freshet-cert \
  --domains=freshettax.ca,www.freshettax.ca --global

gcloud compute url-maps create freshet-lb --default-service=freshet-backend
gcloud compute target-https-proxies create freshet-https \
  --url-map=freshet-lb --ssl-certificates=freshet-cert
gcloud compute forwarding-rules create freshet-fr \
  --global --target-https-proxy=freshet-https \
  --address=freshet-ip --ports=443
```

Then switch IAP on for `freshet-backend` in the console and grant
**IAP-secured Web App User** to `selva@freshettax.ca`.

Get the IP you will need for DNS:

```bash
gcloud compute addresses describe freshet-ip --global --format='value(address)'
```

The managed certificate stays `PROVISIONING` until DNS resolves to that IP.
That is expected — do the DNS below, then wait. It can take an hour.

## DNS at Namecheap

Domain List → **Manage** → **Advanced DNS**.

**Delete the default parking record first.** Namecheap ships a `CNAME` on `www`
pointing at `parkingpage.namecheap.com` and often a URL Redirect on `@`. Either
will silently win over what you add below.

Substitute the IP from the command above for `<LB_IP>`.

| Type | Host | Value | TTL |
|---|---|---|---|
| A Record | `@` | `<LB_IP>` | Automatic |
| A Record | `www` | `<LB_IP>` | Automatic |

### Email, which matters more than it looks

You are about to send licences to customers from a brand-new domain. Without
these, a good share of those emails go to spam — and a customer who paid and
did not receive their licence is a support ticket and a refund request.

Keep whatever `MX` records already serve `selva@freshettax.ca`. Add:

| Type | Host | Value | Note |
|---|---|---|---|
| TXT | `@` | `v=spf1 include:<your-mail-provider> ~all` | one SPF record only, ever |
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; rua=mailto:selva@freshettax.ca` | start here, tighten to `p=reject` later |
| TXT | (provider-supplied) | (provider-supplied DKIM) | from your mail provider's dashboard |

If a SPF record already exists, **edit it** rather than adding a second.
Two SPF records is a permanent error state, not a merge.

## Verifying

```bash
curl -sS https://freshettax.ca/healthz          # ok
curl -sS https://freshettax.ca/admin/licences   # 404 until IAP lets you in
```

The admin path returning 404 to the public is correct — it is not 403, because
a 403 would confirm there is an admin area worth attacking.

## What it costs

Cloud Run scales to zero, so it is near-free when idle. Cloud SQL `db-f1-micro`
does not — it bills hourly whether or not anyone visits, roughly CAD $10–15 a
month, and it is the only always-on cost here. The global load balancer adds a
few dollars more. Nothing else bills meaningfully below real traffic.

## The two things that are not automated, and why

**Billing and terms acceptance.** Enabling billing commits you to spend and
accepts Google's terms. Not mine to click.

**Namecheap.** I never had, and never asked for, credentials or an API key for
it. The records above are exact; entering them takes two minutes.
