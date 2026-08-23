# BIBER Public Domain Setup

Use this runbook when exposing the BIBER MVP API through the real domain
`beaverapi.com`.

## Target Endpoint

Recommended public client base URL:

```text
https://api.beaverapi.com/v1
```

External clients should call OpenAI-compatible endpoints such as:

```text
GET  https://api.beaverapi.com/v1/models
POST https://api.beaverapi.com/v1/chat/completions
```

Use `Authorization: Bearer <user-biber-api-key>`. Do not expose or commit admin
keys, user keys, Cloudflare tokens, or Vast credentials.

## Recommended Architecture

Use Cloudflare Tunnel in front of the Vast GPU:

```text
Client
  -> https://api.beaverapi.com/v1
  -> Cloudflare HTTPS edge
  -> Cloudflare Tunnel
  -> Vast container localhost:8000
  -> BIBER API
  -> local vLLM on localhost:8001
```

Keep vLLM private. Public clients should reach only the BIBER API gateway on
`127.0.0.1:8000` through the tunnel.

## Why Not Namecheap DNS Only

Namecheap can create DNS records for `beaverapi.com`, but DNS records do not
proxy HTTP traffic or hide Vast's random public ports. A direct Namecheap `A`
record to the Vast IP would still need a URL like:

```text
http://api.beaverapi.com:<vast-public-port>/v1
```

That is not the desired MVP endpoint because it is not clean HTTPS and may break
when the Vast instance, public IP, or port mapping changes.

## One-Time Domain Steps

Keep Namecheap as the registrar. Move DNS hosting for `beaverapi.com` to
Cloudflare:

1. In Cloudflare, add the site `beaverapi.com`.
2. Cloudflare will show two nameservers.
3. In Namecheap, open Domain List -> `beaverapi.com` -> Manage.
4. Change Nameservers to Custom DNS and enter the two Cloudflare nameservers.
5. Wait until Cloudflare shows the zone as active.

### Current Setup Status

As of 2026-08-17, Cloudflare Zero Trust Free activation is complete. The
Cloudflare Tunnel named `biber-vast-api` has been created with tunnel ID
`eb224344-06e9-4b30-ac79-9844ac83867f`. The public hostname route
`api.beaverapi.com` has been created with service type `HTTP` and origin
`localhost:8000`. The Vast connector has been installed with the tunnel token
and is running under supervisor as `biber_public_api_tunnel`.

Public route verification passed from the workstation:
`https://api.beaverapi.com/health` returned HTTP 200 with BIBER health JSON.
Unauthenticated `https://api.beaverapi.com/v1/models` returned HTTP 401, which
is expected because OpenAI-compatible routes require
`Authorization: Bearer <user-biber-api-key>`.

Current remaining step: run a public OpenAI-compatible smoke with a user BIBER
API key. Do not paste the key into chat, docs, git, shell history, or
browser-state files.

Authenticated smoke was completed on 2026-08-17 through
`https://api.beaverapi.com/v1`. `/v1/models` returned stable model
`biber-dev-core-v1` and candidate model `biber-dev-core-v2-candidate`.
`/v1/chat/completions` returned `Biber public domain smoke test confirmed.`
with `mentor_used=false`. Non-secret artifacts are on Vast under:

```text
/workspace/outputs/biber-public-domain-smoke-20260817T042616Z/
```

Vast DNS note: Python/curl DNS inside the Vast container may fail for
`api.beaverapi.com` even when public DNS works from the workstation. For the
saved Vast smoke, `curl --resolve api.beaverapi.com:443:172.67.128.89` was used
to force the Cloudflare IPv4 edge while still exercising HTTPS, Cloudflare
Tunnel, the public hostname, and the BIBER API. External clients should use the
normal URL without `--resolve`.

As of 2026-08-16, `beaverapi.com` has been added to Cloudflare on the Free
website plan. Cloudflare assigned:

```text
darwin.ns.cloudflare.com
jewel.ns.cloudflare.com
```

Namecheap was updated for `beaverapi.com` to Custom DNS with exactly those two
nameservers, and Namecheap accepted the save. Cloudflare is currently waiting
for registrar nameserver propagation. Cloudflare Zone ID:

```text
8f4368cb2812a7c668eaa645833cde08
```

Cloudflare Zero Trust Free activation was completed by the user on 2026-08-17.
Future Codex sessions must still not authorize billing, paid upgrades, overage
billing, or paid add-ons for the user.

Cloudflare tunnel setup checklist:

1. In Cloudflare Zero Trust, go to Networks -> Tunnels & Mesh.
2. Create a tunnel named `biber-vast-api`. Done on 2026-08-17.
3. Add a public hostname. Done on 2026-08-17:
   - Subdomain: `api`
   - Domain: `beaverapi.com`
   - Service type: `HTTP`
   - Service URL: `localhost:8000`
4. Copy the connector token from Connectors / Add a connector. Treat it as a
   secret. Done on 2026-08-17; do not rotate it unless needed.

## Vast Setup

The connector is already installed on the current Vast GPU. Re-run this section
only if the connector is missing, unhealthy, or the Vast instance is replaced.

After the Cloudflare tunnel token exists, run this on the Vast GPU from the repo.
This command accepts either the raw token or the full copied connector command
and extracts the token locally:

```bash
cd /workspace/biber-ai-platform

read -rsp "Paste Cloudflare tunnel token or full connector command: " CF_TUNNEL_INPUT
echo
CF_TUNNEL_TOKEN="$CF_TUNNEL_INPUT"
case "$CF_TUNNEL_TOKEN" in
  *"--token "*) CF_TUNNEL_TOKEN="${CF_TUNNEL_TOKEN##*--token }" ;;
  *" tunnel run "*) CF_TUNNEL_TOKEN="${CF_TUNNEL_TOKEN##* tunnel run }" ;;
  *" service install "*) CF_TUNNEL_TOKEN="${CF_TUNNEL_TOKEN##* service install }" ;;
esac
CF_TUNNEL_TOKEN="${CF_TUNNEL_TOKEN%\"}"
CF_TUNNEL_TOKEN="${CF_TUNNEL_TOKEN#\"}"
CF_TUNNEL_TOKEN="${CF_TUNNEL_TOKEN%\'}"
CF_TUNNEL_TOKEN="${CF_TUNNEL_TOKEN#\'}"
export CF_TUNNEL_TOKEN
export BIBER_PUBLIC_API_HOSTNAME=api.beaverapi.com
export BIBER_PUBLIC_API_BASE_URL=https://api.beaverapi.com/v1
export BIBER_PERSIST_CF_TUNNEL_TOKEN=1
export BIBER_CONFIGURE_PUBLIC_TUNNEL_APPROVED=1

bash scripts/vast_configure_cloudflare_tunnel.sh

unset CF_TUNNEL_TOKEN CF_TUNNEL_INPUT
```

The script:

- Verifies BIBER API health at `http://127.0.0.1:8000/health`.
- Installs `/opt/supervisor-scripts/biber_public_api_tunnel.sh`.
- Installs `/etc/supervisor/conf.d/biber_public_api_tunnel.conf`.
- Starts/restarts the supervisor-managed `cloudflared` tunnel.
- Writes only non-secret public domain settings plus the token if
  `BIBER_PERSIST_CF_TUNNEL_TOKEN=1` is set.
- Never prints the tunnel token.

For a dry run that does not install or restart anything:

```bash
cd /workspace/biber-ai-platform
export CF_TUNNEL_TOKEN="<redacted>"
bash scripts/vast_configure_cloudflare_tunnel.sh
```

## Smoke Test

### Public Client API Keys

The current bootstrap `BIBER_API_KEYS` value can be used for private smoke
testing, but do not give the bootstrap key to users or client apps. For real
client access, deliberately configure an admin key once, then issue per-user
keys through the admin API. Do not rotate credentials casually; add or revoke
keys only when there is a concrete reason.

First configure admin key support on Vast. Paste the admin key only into the
terminal prompt:

```bash
cd /workspace/biber-ai-platform

read -rsp "Paste BIBER_ADMIN_API_KEY: " BIBER_ADMIN_API_KEY
echo
export BIBER_ADMIN_API_KEY
export BIBER_PERSIST_ADMIN_API_KEY=1
export BIBER_CONFIGURE_ADMIN_API_KEY_APPROVED=1

bash scripts/vast_configure_admin_api_key.sh

unset BIBER_ADMIN_API_KEY
```

The guarded script writes `BIBER_API_KEY_STORE_PATH` to `.env`, writes
`BIBER_ADMIN_API_KEY` only when `BIBER_PERSIST_ADMIN_API_KEY=1`, and restarts
only FastAPI so vLLM/model runtime stays running. For a dry run that does not
write `.env` or restart anything:

```bash
cd /workspace/biber-ai-platform
export BIBER_ADMIN_API_KEY="<redacted>"
bash scripts/vast_configure_admin_api_key.sh
unset BIBER_ADMIN_API_KEY
```

Then issue a per-user API key. The plaintext user key is shown once; save it in
a password manager or secret manager, not in chat, docs, git, logs, or shell
history:

```bash
cd /workspace/biber-ai-platform

read -rsp "Paste BIBER_ADMIN_API_KEY: " BIBER_ADMIN_API_KEY
echo
export BIBER_ADMIN_API_KEY
export BIBER_OPENAI_BASE_URL=https://api.beaverapi.com/v1

python scripts/biber_agent_client.py issue-api-key \
  --user-id user-1 \
  --label "IDE agent"

unset BIBER_ADMIN_API_KEY
```

Use the returned user key as `BIBER_API_KEY` in external clients.

The same user-key workflow is available in the MVP admin console:

```text
https://api.beaverapi.com/admin
https://api.beaverapi.com/admin/api-keys
```

The console accepts `BIBER_ADMIN_API_KEY`, calls the same
`/v1/admin/api-keys` endpoints, displays a newly issued user API key once, and
keeps the admin key only in browser memory for that page session. It also
includes connection checks, no-secret Vast setup snippets, and an external
agent client environment template. Before giving anyone else access, protect
`/admin` and `/admin/*` with Cloudflare Access, a VPN, or an equivalent
admin-only edge rule. Keep `/v1/chat/completions` public only behind user
API-key auth.

### Cloudflare Access For Admin Routes

For the public MVP, prefer Cloudflare Access only for operator/admin paths.
Do not put normal model-source routes such as `/v1/models` and
`/v1/chat/completions` behind Cloudflare Access unless the client explicitly
supports Cloudflare Access service tokens. Those normal routes should remain
protected by BIBER user API keys.

Cloudflare UI checklist:

1. Open Cloudflare Zero Trust.
2. Go to Access -> Applications.
3. Add a self-hosted application named `BIBER Admin Console`.
4. Add these application domains/paths:
   - `api.beaverapi.com/admin`
   - `api.beaverapi.com/admin/*`
   - `api.beaverapi.com/v1/admin/*`
5. Add an Allow policy for the admin email address or admin identity group.
6. Keep the session duration short enough for operations, for example 8 hours.
7. Do not enable paid add-ons or authorize overage billing from this runbook.

The readiness smoke reports `public_admin_access.state` so future sessions can
quickly identify the public posture:

- `admin_console_edge_protected`: expected public posture after Cloudflare
  Access, WAF, or equivalent edge protection is active for admin routes.
- `admin_console_served_directly`: acceptable only for private/local testing;
  add Cloudflare Access or equivalent protection before real users.
- `admin_console_unreachable` or `admin_console_needs_review`: check DNS,
  tunnel health, and Cloudflare route/policy settings before using the console.

Run this no-secret readiness smoke after deployment or after DNS/tunnel changes:

```bash
python scripts/biber_admin_console_readiness.py \
  --base-url https://api.beaverapi.com \
  --output /workspace/outputs/biber-admin-console-readiness.json
```

The readiness artifact verifies the console pages, browser hardening headers,
or confirms that the admin console is protected at the edge, and verifies
anonymous admin API protection. It does not include admin keys, user API keys,
or raw key records. For a direct Vast/local check that requires the actual HTML
page to be served, add `--require-console-served`.

For a direct Vast/local authenticated console-list readiness check, pass the
admin key through an environment variable and require the list flow. This proves
that the served console and the authenticated `GET /v1/admin/api-keys` path are
ready without writing the admin key, user keys, key IDs, labels, or raw records
to the artifact:

Before configuring or using the admin key, run the no-secret setup-status check:

```bash
cd /workspace/biber-ai-platform

/workspace/biber-venv/bin/python scripts/biber_admin_key_setup_status.py \
  --dotenv .env \
  --allow-missing \
  --output /workspace/outputs/biber-admin-key-setup-status.json
```

The status artifact reports whether `BIBER_ADMIN_API_KEY` is configured and
prints the guarded setup/readiness commands, but never includes the key value and
never mutates `.env`, restarts FastAPI, or rotates credentials.

```bash
cd /workspace/biber-ai-platform
read -rsp "Paste BIBER_ADMIN_API_KEY: " BIBER_ADMIN_API_KEY
echo
export BIBER_ADMIN_API_KEY

/workspace/biber-venv/bin/python scripts/biber_admin_console_readiness.py \
  --base-url http://127.0.0.1:8000 \
  --admin-api-key-env BIBER_ADMIN_API_KEY \
  --admin-api-key-dotenv .env \
  --require-console-served \
  --require-authenticated-admin-list \
  --require-admin-console-list-flow \
  --output /workspace/outputs/biber-admin-console-list-flow-local.json

unset BIBER_ADMIN_API_KEY
```

Do not run this authenticated list-flow check against the public URL unless the
admin browser/session is deliberately allowed through Cloudflare Access. The
public no-secret check should normally report
`public_admin_access.state=admin_console_edge_protected`.

After DNS/tunnel propagation:

```bash
export BIBER_OPENAI_BASE_URL=https://api.beaverapi.com/v1
export BIBER_MODEL=biber-dev-core-v1
read -rsp "Paste user BIBER_API_KEY: " BIBER_API_KEY
echo
export BIBER_API_KEY

python examples/external_agent/python_minimal_client.py \
  --message "Reply with one concise BIBER public domain smoke confirmation."

unset BIBER_API_KEY
```

Or use the agent client:

```bash
python scripts/biber_agent_client.py external-agent-smoke \
  --client-base-url https://api.beaverapi.com/v1 \
  --output /workspace/outputs/biber-external-agent-smoke-beaverapi.json
```

## Security Notes

- Keep `OPENAI_MENTOR_ENABLED=false` unless explicitly testing mentor review.
- Keep `BIBER_ADMIN_API_KEY` separate from user API keys.
- Do not expose direct vLLM port `8001`.
- Prefer Cloudflare Access or WAF rules for `/admin`, `/admin/*`, and
  `/v1/admin/*` before inviting other users.
- Do not commit `.env`, tunnel tokens, API keys, or generated private artifacts.

## Resume Notes

If the Vast instance is replaced, repeat only the Vast Setup section after the
repo and `.env` are restored. Cloudflare DNS and the public hostname can stay the
same; update or recreate the tunnel token only if the old tunnel connector is
retired.
