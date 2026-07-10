# XRIQ GCP Public Edge (TLS + WAF)

Status: optional public HTTPS edge for the GCP `staging-devnet`. IaC only,
disabled by default, apply is human/agent-operated.

## Posture warning (read first)

Enabling this edge makes the XRIQ API **publicly reachable on the internet**. That
is a deliberate change from the private-staging posture in
`docs/XRIQ_LEGAL_RISK_REDUCTION.md`. Keep it conservative:

- The edge is **read-only**: Cloud Armor allows only `GET`/`HEAD`/`OPTIONS`, so all
  mutations (wallet transfers, block production, signed submit — all POST) are
  blocked at the edge, and `/api/v1/admin` is blocked entirely.
- It is **per-IP rate-limited** (`edge_rate_limit_per_minute`, default 600/min).
- It exposes a **private, non-production test devnet** with no monetary value.
  Do not add investment, token-sale, or exchange-readiness language.
- Public network operation, a faucet, tokenomics, and any public claims remain
  Phase 3+ work behind the roadmap's security/legal review — this edge does not
  authorize them.

The edge is **off by default** (`enable_public_edge = false`); nothing is created
unless you explicitly opt in and supply a domain.

## What it creates (when enabled)

`infra/gcp/modules/edge`: a global external Application Load Balancer with a
Google-managed TLS certificate, a Cloud Armor security policy (rate limit +
read-only + admin block), a health check on `/api/v1/health`, an instance group
containing the node VM, and a firewall rule allowing the Google Front End /
health-check ranges to reach the VM on `:8090`.

## Apply

1. Choose a domain you control (you own `kani.network`), e.g.
   `staging-api.xriq.kani.network`. In `terraform.tfvars`:

   ```hcl
   enable_public_edge = true
   api_domain         = "staging-api.xriq.kani.network"
   ```

2. Apply Terraform (creates the edge and reserves a static IP; the managed cert
   starts in `PROVISIONING`):

   ```bash
   cd infra/gcp
   terraform workspace select xriq-project-dev
   export TF_VAR_postgres_admin_password="$(gcloud secrets versions access latest \
     --secret=xriq-staging-devnet-db-password --project=xriq-project-dev)"
   terraform apply
   EDGE_IP="$(terraform output -raw edge_ip)"
   echo "point DNS A record for the domain at: $EDGE_IP"
   ```

3. Create a **DNS A record** for `api_domain` pointing at `$EDGE_IP` (in your
   `kani.network` DNS). The managed certificate only provisions once the domain
   resolves to the edge IP; this can take up to ~30-60 minutes.

4. Verify certificate provisioning and reachability:

   ```bash
   gcloud compute ssl-certificates describe xriq-staging-devnet-edge-cert \
     --project xriq-project-dev --format='value(managed.status)'
   # wait for ACTIVE, then:
   curl -fsS "https://$api_domain/api/v1/health" && echo
   # mutations are blocked at the edge (expect 403):
   curl -s -o /dev/null -w '%{http_code}\n' -X POST "https://$api_domain/api/v1/blocks/produce"
   ```

## Disable

Set `enable_public_edge = false` and `terraform apply` to remove the edge (the API
returns to VPC-private). This does not touch the node/DB.

## Follow-ups before any real public use

- A security review of the exposed surface (Phase 4 in the roadmap).
- Public disclaimers / terms on any user-facing page.
- Deciding whether a public testnet (Phase 3) is warranted at all.
