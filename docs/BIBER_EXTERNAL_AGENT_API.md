# BIBER External Agent API

This is the MVP contract for using BIBER as a model source from an IDE agent,
custom conversational agent, internal app, or a future GitHub Copilot extension
or agent gateway.

For the step-by-step client setup flow, see
`docs/BIBER_EXTERNAL_AGENT_CLIENT_SETUP.md`.

## MVP Contract

BIBER exposes an authenticated OpenAI-compatible chat-completions surface:

```text
GET  /v1/models
POST /v1/chat/completions
GET  /v1/agent/capabilities
```

For Copilot-style clients, custom IDE agents, and other agent gateways, BIBER
also exposes planning helpers around the model surface:

```text
POST /v1/repo/rag/index
POST /v1/repo/rag/search
POST /v1/repo/context/plan
POST /v1/agent/orchestration/plan
POST /v1/files/edit/plan
POST /v1/files/edit/apply
POST /v1/tests/run
POST /v1/tests/diagnose
```

Authentication accepts either header form:

```text
Authorization: Bearer <api-key>
x-api-key: <api-key>
```

The bootstrap key source is `BIBER_API_KEYS`. Put comma-separated bootstrap
keys in the server environment or `.env` file. Do not commit `.env` or paste
keys into chat.

The MVP also supports issued per-user API keys through a hashed file-backed
store at `BIBER_API_KEY_STORE_PATH`. If that variable is not set, the direct
Vast path defaults to `/workspace/outputs/biber-api-keys.json`; local CPU runs
default to `.biber-runtime/biber-api-keys.json` under the repo context root.
The store records key hashes and safe metadata only. The plaintext API key is
returned once when the admin issues it.

The BIBER API also has an MVP server-side guard for public client paths. It
applies to `/v1/*`, rejects oversized requests by `Content-Length`, and rate
limits by API-key hash when a key is present or by client IP before auth. The
defaults are intentionally conservative and configurable:

```text
BIBER_API_GUARD_ENABLED=true
BIBER_API_MAX_REQUEST_BYTES=1048576
BIBER_API_RATE_LIMIT_REQUESTS_PER_MINUTE=120
```

The rate-limit state is in-memory per API process in this MVP. For production,
put Cloudflare/WAF limits and a shared store such as Redis in front of this
guard, but do not remove the in-app checks.

`POST /v1/chat/completions` defaults to the configured swappable BIBER model
registry. The raw GPU runtime remains behind BIBER; external clients should talk
to the BIBER API, not directly to vLLM. OpenAI mentor is optional and disabled
by default for this endpoint. Streaming is intentionally not part of this MVP
contract yet.

Example:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "biber-dev-core-v1",
    "messages": [
      {"role": "user", "content": "Write one concise Rust review note."}
    ],
    "max_tokens": 120
  }'
```

## Client Compatibility

Any client that supports an OpenAI-compatible base URL and API key can point at
the BIBER API base URL and use `/v1/models` plus `/v1/chat/completions`.

For a VS Code client, use `examples/vscode_extension/` as the MVP starting
point. It stores per-user keys in VS Code SecretStorage, has a
`BIBER: Test API Connection` command that calls `/v1/agent/capabilities`
without sending repository data, calls the planning-only orchestration endpoint
by explicit user command, sends bounded path hints instead of file contents in
the first MVP command, and includes client-side single-flight, per-minute
request limiting, HTTPS-or-localhost URL enforcement, and request timeouts.
These editor-side controls are only a first shield; the BIBER API must still
enforce authentication, server-side rate limits, quotas, payload size limits,
logging redaction, and abuse monitoring.

Clients that want a richer coding-agent flow should use the planning helpers
before calling the model: run `/v1/repo/rag/search` to select candidate files
from the full allowed repository tree, pass those files through
`/v1/repo/context/plan`, ask the model for strict JSON edits, validate them with
`/v1/files/edit/plan`, apply only with the matching `plan_hash`, then run and
diagnose tests. `/v1/agent/orchestration/plan` packages that intended flow into
a single planning-only response and performs no model call, file mutation,
GitHub save, training, or OpenAI mentor call.

The current RAG layer is an MVP lexical/symbol/import index. It improves
repository context selection and cost control, but it is not yet a production
vector database, persistent embedding store, or autonomous multi-agent runtime.

The stdlib BIBER agent client can exercise the same OpenAI-compatible endpoint:

```bash
export BIBER_API_KEY="<user-api-key>"
python scripts/biber_agent_client.py repo-rag-search \
  --query "Find the files needed for the requested repo change." \
  --changed-path src/biber_api/main.py \
  --max-results 8 \
  --output /workspace/outputs/biber-repo-rag-search.json
python scripts/biber_agent_client.py orchestration-plan \
  --instruction "Plan the repo change with bounded context, safe edits, and tests." \
  --changed-path src/biber_api/main.py \
  --test-id python-compileall-api \
  --output /workspace/outputs/biber-orchestration-plan.json
python scripts/biber_agent_client.py orchestration-plan \
  --local-target-root /workspace/biber-ai-platform \
  --instruction "Plan the repo change locally before spending live model time." \
  --changed-path src/biber_api/main.py \
  --no-test \
  --output /workspace/outputs/biber-local-orchestration-plan.json
python scripts/biber_agent_client.py external-agent-readiness \
  --client-base-url http://127.0.0.1:8000 \
  --output /workspace/outputs/biber-external-agent-readiness.json
python scripts/biber_agent_client.py external-agent-connection \
  --client-base-url http://127.0.0.1:8000 \
  --output /workspace/outputs/biber-external-agent-connection.json
python scripts/biber_agent_client.py external-agent-bundle \
  --client-base-url http://127.0.0.1:8000 \
  --output /workspace/outputs/biber-external-agent-bundle.json
python scripts/biber_agent_client.py external-agent-bundle-health-check \
  /workspace/outputs/biber-external-agent-bundle.json \
  --repo-root /workspace/biber-ai-platform \
  --output /workspace/outputs/biber-external-agent-bundle-health.json
python scripts/biber_agent_client.py external-agent-client-contract-report \
  /workspace/outputs/biber-external-agent-bundle.json \
  --repo-root /workspace/biber-ai-platform \
  --output /workspace/outputs/biber-external-agent-client-contract.json
python scripts/biber_agent_client.py external-agent-bundle-chat-smoke \
  /workspace/outputs/biber-external-agent-bundle.json \
  --repo-root /workspace/biber-ai-platform \
  --output /workspace/outputs/biber-external-agent-bundle-chat-smoke.json
python scripts/biber_agent_client.py external-agent-handoff-package \
  /workspace/outputs/biber-external-agent-bundle.json \
  --repo-root /workspace/biber-ai-platform \
  --health-artifact /workspace/outputs/biber-external-agent-bundle-health.json \
  --contract-report-artifact /workspace/outputs/biber-external-agent-client-contract.json \
  --chat-smoke-artifact /workspace/outputs/biber-external-agent-bundle-chat-smoke.json \
  --output /workspace/outputs/biber-external-agent-handoff-package.json
python scripts/biber_agent_client.py show-external-agent-handoff-package \
  /workspace/outputs/biber-external-agent-handoff-package.json
python scripts/biber_api_request_guard_smoke.py \
  --output /workspace/outputs/biber-api-request-guard-smoke.json
python scripts/biber_vscode_extension_contract_smoke.py \
  --output /workspace/outputs/biber-vscode-extension-contract-smoke.json
python scripts/biber_agent_client.py admin-api-key-contract-smoke \
  --allow-missing-admin-key \
  --output /workspace/outputs/biber-admin-api-key-contract-smoke.json
python scripts/biber_agent_client.py external-client-readiness-bundle \
  /workspace/outputs/biber-external-agent-handoff-package.json \
  --admin-smoke-artifact /workspace/outputs/biber-admin-api-key-contract-smoke.json \
  --output /workspace/outputs/biber-external-client-readiness-bundle.json
python scripts/biber_agent_client.py show-external-client-readiness-bundle \
  /workspace/outputs/biber-external-client-readiness-bundle.json
python scripts/biber_agent_client.py external-client-env-template \
  /workspace/outputs/biber-external-client-readiness-bundle.json \
  --output /workspace/outputs/biber-external-client-env-template.json \
  --env-output /workspace/outputs/biber-external-client.env.example
python scripts/biber_agent_client.py show-external-client-env-template \
  /workspace/outputs/biber-external-client-env-template.json
python scripts/biber_agent_client.py external-client-quickstart-verify \
  /workspace/outputs/biber-external-client-readiness-bundle.json \
  --repo-root /workspace/biber-ai-platform \
  --output /workspace/outputs/biber-external-client-quickstart-verification.json
python scripts/biber_agent_client.py show-external-client-quickstart-verification \
  /workspace/outputs/biber-external-client-quickstart-verification.json
python scripts/biber_agent_client.py external-client-integration-package \
  /workspace/outputs/biber-external-client-readiness-bundle.json \
  --env-template-artifact /workspace/outputs/biber-external-client-env-template.json \
  --quickstart-verification-artifact /workspace/outputs/biber-external-client-quickstart-verification.json \
  --output /workspace/outputs/biber-external-client-integration-package.json
python scripts/biber_agent_client.py show-external-client-integration-package \
  /workspace/outputs/biber-external-client-integration-package.json
python scripts/biber_agent_client.py external-client-live-smoke-plan \
  /workspace/outputs/biber-external-client-integration-package.json \
  --output /workspace/outputs/biber-external-client-live-smoke-plan.json
python scripts/biber_agent_client.py show-external-client-live-smoke-plan \
  /workspace/outputs/biber-external-client-live-smoke-plan.json
python scripts/biber_agent_client.py show-latest-external-client-live-smoke-plan \
  /workspace/outputs
python scripts/biber_agent_client.py external-agent-smoke \
  --client-base-url http://127.0.0.1:8000 \
  --output /workspace/outputs/biber-external-agent-smoke.json
python scripts/biber_agent_client.py capabilities \
  --output /workspace/outputs/biber-capabilities.json
python scripts/biber_agent_client.py runtime
python scripts/biber_agent_client.py models
python scripts/biber_agent_client.py chat-completions \
  --model biber-dev-core-v1 \
  --message "Write one concise Rust review note." \
  --max-tokens 120 \
  --output /workspace/outputs/biber-chat-completions-smoke.json
```

`external-agent-connection` writes a non-secret profile with the OpenAI-style
base URL, `/v1/models`, `/v1/chat/completions`, the selected stable model, and
auth header names. It never writes the API key into the artifact.
`external-agent-readiness` saves that profile together with capabilities,
runtime, and model metadata in one artifact.
`external-agent-bundle` saves the non-secret env values, docs/examples paths,
validation commands, and API-key management metadata that another client or
gateway needs for setup.
`external-agent-bundle-health-check` validates that saved bundle before handoff
without resolving any API key or calling the model.
`external-agent-client-contract-report` turns the saved bundle into a compact
non-secret setup report for a gateway/client: URL, model, auth headers,
endpoints, validation commands, and readiness status.
`external-agent-bundle-chat-smoke` loads that saved bundle and sends one short
chat-completions request through the bundle's `BIBER_OPENAI_BASE_URL` and
`BIBER_MODEL`, with OpenAI mentor off.
`external-agent-handoff-package` writes one non-secret index artifact for
another gateway/client, linking the bundle, health report, contract report, and
optional chat-smoke proof. It carries only metadata for admin/user API-key
management, never actual keys.
`show-external-agent-handoff-package` prints the saved package summary without
opening JSON and without resolving API keys.
`external-client-readiness-bundle` combines the saved handoff package with a
redacted `admin-api-key-contract-smoke` artifact into one non-secret checklist
for external IDE agents, conversational apps, and API gateways. If
`BIBER_ADMIN_API_KEY` is not configured yet, use
`admin-api-key-contract-smoke --allow-missing-admin-key`; the readiness bundle
can still confirm model-source client configuration while reporting admin
key-management as blocked.
`show-external-client-readiness-bundle` prints a saved readiness-bundle summary
without rebuilding it, resolving API keys, or opening JSON.
`external-client-env-template` creates a non-secret `.env.example` template from
the saved readiness bundle for IDE agents, gateways, or conversational clients.
Only replace `BIBER_API_KEY` from the client's secret manager; never commit real
keys.
`show-external-client-env-template` prints a saved env-template summary without
regenerating it, resolving API keys, or opening JSON.
`external-client-quickstart-verify` checks a saved readiness bundle against the
repo docs/examples quickstart contract without calling BIBER or resolving API
keys.
`show-external-client-quickstart-verification` prints a saved quickstart
verification summary without rerunning checks, calling BIBER, or resolving API
keys.
`external-client-integration-package` links the saved readiness bundle,
env-template artifact, and quickstart verification into one non-secret package
for IDE agents, gateways, and conversational apps.
`show-external-client-integration-package` prints the saved integration package
summary without regenerating it, resolving API keys, or opening JSON.
`external-client-live-smoke-plan` writes the non-secret commands to run later
after a user API key is configured. The plan itself does not call BIBER or
resolve keys.
`show-external-client-live-smoke-plan` prints a saved live-smoke-plan summary
without regenerating it, calling BIBER, or resolving keys.
`show-latest-external-client-live-smoke-plan` finds the newest saved live-smoke
plan under an outputs directory and prints the same read-only summary.
`external-agent-smoke` runs readiness plus one short chat-completions request
and saves a single non-secret end-to-end setup proof. It keeps OpenAI mentor
off.
Use `--client-base-url` when the URL an IDE should configure differs from the
private URL used by the smoke command, such as an SSH tunnel or HTTPS gateway.

Minimal dependency-free client examples live in `examples/external_agent/`.
They demonstrate the same contract with only `BIBER_OPENAI_BASE_URL`,
`BIBER_MODEL`, and `BIBER_API_KEY`. Run
`python scripts/biber_external_agent_examples_smoke.py` for an offline fake-server
check before testing against the live GPU.

GitHub Copilot itself may require a Copilot extension, approved integration, or
agent gateway rather than direct arbitrary model endpoint configuration. Keep
the BIBER side generic: OpenAI-compatible HTTP, bearer API key, stable model
metadata, and no provider-specific assumptions.

## Domain And Public HTTPS

A `.com` domain is not required for local MVP or private GPU testing. Use a
domain only when BIBER needs to be reachable by external clients over the
internet.

When public access is needed:

1. Buy a domain in Namecheap, for example `your-biber-domain.com`.
2. Choose the production host/API edge first: GCP, AWS, Azure, Cloudflare, or a
   reverse proxy VM/load balancer.
3. In Namecheap DNS, create either an `A` record to the public IP or a `CNAME`
   to the cloud load balancer/proxy hostname.
4. Enable HTTPS on the cloud edge or reverse proxy before allowing real users.
5. Route only BIBER API paths such as `/v1/*` to the BIBER API service.
6. Keep the GPU/vLLM port private where possible; expose BIBER API as the
   controlled gateway.
7. Configure API keys through environment/secret storage. Never place keys in
   GitHub.

For the real `beaverapi.com` domain, follow
[`docs/BIBER_PUBLIC_DOMAIN_SETUP.md`](BIBER_PUBLIC_DOMAIN_SETUP.md). The
recommended MVP shape is `https://api.beaverapi.com/v1` using Cloudflare Tunnel
to reach the Vast BIBER API on `127.0.0.1:8000` while keeping vLLM private.

## Public Client Key Management

For private smoke tests, the bootstrap `BIBER_API_KEYS` value may be used as the
client `BIBER_API_KEY`. For external users or IDE agents, configure
`BIBER_ADMIN_API_KEY` deliberately and issue per-user keys through
`/v1/admin/api-keys`. Keep the admin key separate from user keys and never put
real keys in git, docs, chat, logs, browser state, or generated artifacts.

On Vast, use the guarded setup script when admin key management is needed:

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

The script prints a redacted plan first, requires
`BIBER_CONFIGURE_ADMIN_API_KEY_APPROVED=1` before mutation, does not print the
admin key, and restarts only FastAPI. It does not rotate or generate
credentials by itself.

After admin key support is configured, issue user keys with the admin API or the
BIBER client:

```bash
read -rsp "Paste BIBER_ADMIN_API_KEY: " BIBER_ADMIN_API_KEY
echo
export BIBER_ADMIN_API_KEY
python scripts/biber_agent_client.py issue-api-key --user-id user-1 --label "IDE agent"
unset BIBER_ADMIN_API_KEY
```

The returned user API key is displayed once. Store it in the client secret
manager and configure the external client with:

```text
BIBER_OPENAI_BASE_URL=https://api.beaverapi.com/v1
BIBER_MODEL=biber-dev-core-v1
BIBER_API_KEY=<issued-user-api-key>
```

## Admin Console MVP

The admin console MVP is available at:

```text
GET /admin
GET /admin/api-keys
```

It is a FastAPI-served browser console for the existing admin API-key
management endpoints protected by `BIBER_ADMIN_API_KEY`:

```text
GET    /v1/admin/api-keys
POST   /v1/admin/api-keys
DELETE /v1/admin/api-keys/{key_id}
```

The console lets an admin sign in with the admin API key, list user keys, issue
per-user keys, copy the one-time plaintext key, and revoke active keys. It also
shows the detected API base, a direct health/admin connection check, no-secret
Vast setup commands, and an external-agent environment template for clients
such as Copilot-style tools, Gemini Code Assist workflows, or custom agents.
The admin key is held only in browser memory for the current page session. The
page does not store admin/user keys in git or generated artifacts, and the
server still stores only key hashes plus safe metadata.

Verify the console without secrets:

```bash
python scripts/biber_admin_console_readiness.py \
  --base-url https://api.beaverapi.com \
  --output /workspace/outputs/biber-admin-console-readiness.json
```

If the admin key is already configured and you want a redacted authenticated
list proof, pass the key only through an environment variable:

```bash
read -rsp "Paste BIBER_ADMIN_API_KEY: " BIBER_ADMIN_API_KEY
echo
export BIBER_ADMIN_API_KEY
python scripts/biber_admin_console_readiness.py \
  --base-url https://api.beaverapi.com \
  --admin-api-key-env BIBER_ADMIN_API_KEY \
  --require-authenticated-admin-list \
  --output /workspace/outputs/biber-admin-console-readiness-authenticated.json
unset BIBER_ADMIN_API_KEY
```

The artifact reports counts and status only; it does not include admin keys,
user API keys, or raw key records. Public checks allow `/admin` to be protected
by Cloudflare Access or a similar edge rule; direct Vast/local checks can add
`--require-console-served` to require the actual HTML console response.
The redacted readiness output includes `public_admin_access.state`; the desired
public MVP state is usually `admin_console_edge_protected` for `/admin`,
`/admin/*`, and `/v1/admin/*`, while `/v1/models` and `/v1/chat/completions`
remain protected by normal BIBER user API keys.
For a direct local/Vast proof that the admin GUI can list keys, add
`--require-admin-console-list-flow` together with `--admin-api-key-env`,
`--require-console-served`, and `--require-authenticated-admin-list`. On Vast,
add `--admin-api-key-dotenv .env` rather than shell-sourcing `.env`. That mode
records only status and counts; it still omits admin keys, user keys, key IDs,
labels, and raw key records from the artifact.
Use `scripts/biber_admin_key_setup_status.py --allow-missing` before any
credential-dependent admin step to write a redacted setup-status artifact and
confirm whether `BIBER_ADMIN_API_KEY` is deliberately configured.

Example:

```bash
curl -X POST http://localhost:8000/v1/admin/api-keys \
  -H "Authorization: Bearer <admin-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user-1","label":"IDE agent"}'
```

The response includes `api_key` one time plus a safe `record`. List/revoke
responses never include plaintext keys or key hashes.

The stdlib BIBER agent client wraps the same admin endpoints. Prefer setting
the admin key in the shell environment so it does not appear in command
history:

PowerShell:

```powershell
$env:BIBER_ADMIN_API_KEY = "<admin-api-key>"
python scripts/biber_agent_client.py admin-api-key-contract-smoke \
  --output /workspace/outputs/biber-admin-api-key-contract-smoke.json
python scripts/biber_agent_client.py list-api-keys
python scripts/biber_agent_client.py issue-api-key --user-id user-1 --label "IDE agent"
python scripts/biber_agent_client.py revoke-api-key <key_id>
```

Bash:

```bash
export BIBER_ADMIN_API_KEY="<admin-api-key>"
python scripts/biber_agent_client.py admin-api-key-contract-smoke \
  --output /workspace/outputs/biber-admin-api-key-contract-smoke.json
python scripts/biber_agent_client.py list-api-keys
python scripts/biber_agent_client.py issue-api-key --user-id user-1 --label "IDE agent"
python scripts/biber_agent_client.py revoke-api-key <key_id>
```

Use `admin-api-key-contract-smoke` before giving a gateway or admin UI the
full key-management flow. It calls only `GET /v1/admin/api-keys`, records counts
and field names, and redacts key IDs, user IDs, labels, plaintext keys, and the
admin key. Add `--allow-missing-admin-key` in CI or handoff runs when the admin
key is intentionally absent; it writes a redacted blocked artifact instead of
failing and still performs no mutation.

Before exposing the console to other people, put `/admin` and `/admin/*` behind
Cloudflare Access, a VPN, or equivalent admin-only edge protection. The admin
console is an MVP operational tool, not the production account portal.

The later production portal should add:

- Admin login with secure password or SSO.
- Registered users.
- Usage audit events.
- Rate limits and monthly quotas.
- Optional passcode or policy-based GPU priority scheduling.

Build those production account features only after the model-source API is
stable and useful from at least one real client.
