# Deploying the site, and the DNS to go with it

Everything here is yours to run. The parts involving credentials, terms of
service, or spend are deliberately not automated.

## Order

The signing key comes first and is the one irreversible step.

### 1. The signing key — DONE, but not yet backed up

Generated on 2026-08-16. Its public half is already in
`crates/freshet-license/src/sign.rs`, and a test now fails if it ever reverts
to the placeholder.

The private half is at **`C:\Users\vselv\.freshet\freshet-signing-key.hex`** —
deliberately outside OneDrive, so it is not being synced to a cloud folder.

**It exists in exactly one place right now**, and still did as of
2026-09-15. Lose that file and you can never issue another licence for any
build already shipped.

Billing is now linked (confirmed in the console on 2026-09-15), so the first
command below is done. The other two are not:

```bash
gcloud services enable secretmanager.googleapis.com --project=freshet-licence
gcloud secrets create freshet-signing-key --project=freshet-licence \
  --data-file="$HOME/.freshet/freshet-signing-key.hex"
```

Then put a second copy somewhere offline that is not Google — a password
manager entry, or printed and filed. Secret Manager is where the *service*
reads it from; it is not a backup, because losing access to the project loses
the key with it.

Only once both copies exist should you delete the local file.

**This key cannot be rotated cheaply.** Its public half is compiled into every
installed copy of Freshet, so replacing it invalidates every licence already in
customers' hands. Lose it and you can never issue another licence for the
builds already shipped. Back it up somewhere that is not this repository — the
keygen refuses to write inside a git working tree for exactly that reason.

The service refuses to start if the key it holds does not match the key the app
trusts, so a mismatch is a failed deploy rather than a month of customers who
paid and cannot file.

### 2. Sign in, and check which project is selected

As of 2026-09-15 the active account is `selva@freshettax.ca`, which is right,
but the token has expired and cannot be refreshed non-interactively:

```bash
gcloud auth login
```

**Then set the project, and check it.** This is the step most likely to go
wrong quietly. `deploy.sh` takes its project from `gcloud config get-value
project`, and on this machine that is currently **`biber-499407`** — a
different product entirely. Running the deploy without changing it would put
the licence service, its database and its secrets into the BIBER project, all
billable and all in the wrong place.

```bash
gcloud config set project freshet-licence
gcloud config get-value project     # must print freshet-licence
```

**There are two licence-shaped projects on the billing account**, and only one
is the right one:

| Project name | Project ID | |
| --- | --- | --- |
| Freshet Licence | `freshet-licence` | the one every command here names |
| freshet-licence | `freshet-licence-508706` | a duplicate, created second |

Nothing has been deployed to either, so the duplicate is empty and costs
nothing — but leaving it linked to billing means a stray command can spend in
it. Confirm which is which before deleting anything:

```bash
gcloud projects describe freshet-licence --format='value(projectId,createTime)'
gcloud projects describe freshet-licence-508706 --format='value(projectId,createTime)'
gcloud services list --project=freshet-licence-508706   # expect: nothing enabled
```

If the second is empty, unlink it from billing and shut it down. That is a
decision about your account rather than about this code, so it is yours to
make.

Billing is enabled on the account. Enabling any further paid API is a spend
decision and a terms acceptance, so those stay yours too.

### 3. Deploy

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
