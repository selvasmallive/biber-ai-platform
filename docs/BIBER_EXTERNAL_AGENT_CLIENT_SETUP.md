# BIBER External Agent Client Setup

Use this runbook when a generic IDE agent, conversational agent, gateway, or
internal app needs to use BIBER as an OpenAI-compatible model source.

This is for BIBER MVP only. It keeps the local model provider swappable, keeps
OpenAI mentor disabled by default, and avoids exposing raw vLLM directly.

## Required Settings

External clients should use:

```text
OpenAI-compatible base URL: <openai_base_url from external-agent-connection>
Model: <default_model from external-agent-connection>
API key: a BIBER user API key
Chat endpoint: /v1/chat/completions
Streaming: disabled for the MVP
```

Do not configure clients against `local_model_base_url`; that is the private GPU
provider behind BIBER.

## Private Vast Or SSH Tunnel

When BIBER runs on Vast, keep the API private and expose it through an SSH
tunnel from the workstation or gateway host:

```bash
ssh -i ~/.ssh/biber_vast_ed25519 -p <vast-ssh-port> \
  -L 8000:127.0.0.1:8000 root@<vast-public-ip>
```

Then, in another terminal from the repo checkout:

```bash
export BIBER_API_BASE_URL="http://127.0.0.1:8000"
export BIBER_API_KEY="<user-api-key>"

python scripts/biber_agent_client.py external-agent-readiness \
  --client-base-url "$BIBER_API_BASE_URL" \
  --output /workspace/outputs/biber-external-agent-readiness.json

python scripts/biber_agent_client.py external-agent-connection \
  --client-base-url "$BIBER_API_BASE_URL" \
  --output /workspace/outputs/biber-external-agent-connection.json

python scripts/biber_agent_client.py external-agent-bundle \
  --client-base-url "$BIBER_API_BASE_URL" \
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

python scripts/biber_agent_client.py capabilities \
  --output /workspace/outputs/biber-capabilities.json

python scripts/biber_agent_client.py runtime \
  --output /workspace/outputs/biber-runtime.json

python scripts/biber_agent_client.py models \
  --output /workspace/outputs/biber-models.json
```

The readiness and connection artifacts are safe to share with a local agent
setup because they do not contain the API key. The API key must be configured
separately in the client's secret or environment setting.
The bundle artifact is the preferred handoff file for another client: it
includes the non-secret env values, docs/examples paths, and validation commands
without embedding the API key. It also includes non-secret admin/user API-key
management metadata so gateway builders know the MVP uses
`GET/POST/DELETE /v1/admin/api-keys` guarded by `BIBER_ADMIN_API_KEY`.
Run `external-agent-bundle-health-check` before handing the bundle to another
client or gateway; it verifies the bundle is non-secret, internally consistent,
and points at docs/examples that exist in the repo.
Run `external-agent-client-contract-report` to produce a compact non-secret
setup sheet for another gateway or client engineer: URL, model, auth headers,
endpoints, validation commands, and readiness status.
Run `external-agent-bundle-chat-smoke` when you want a live proof that the saved
bundle's `BIBER_OPENAI_BASE_URL` and `BIBER_MODEL` can complete one
OpenAI-compatible chat request with OpenAI mentor off.
Run `external-agent-handoff-package` when another gateway/client needs one
non-secret index artifact linking the bundle, health report, contract report,
optional chat-smoke proof, and API-key management metadata.
Run `show-external-agent-handoff-package` to inspect the saved package summary
without opening JSON and without resolving API keys.
Run `external-client-readiness-bundle` when a Copilot, Gemini Code Assist,
custom IDE agent, gateway, or conversational app needs one non-secret checklist
combining the model-source handoff package with the admin key-management smoke
status. If the admin key is not configured yet, use the blocked
`admin-api-key-contract-smoke --allow-missing-admin-key` artifact; the bundle can
still be ready for client configuration while reporting
`admin_key_management_ready=false`.
Run `show-external-client-readiness-bundle` to inspect the saved checklist later
without rebuilding it, resolving API keys, or opening JSON.
Run `external-client-env-template` to generate a non-secret `.env.example`
template for IDE agents, gateways, or conversational clients. Replace only the
`BIBER_API_KEY` placeholder from the client secret manager; do not commit real
keys.
Run `show-external-client-env-template` to inspect the saved template artifact
later without regenerating it, resolving API keys, or opening JSON.
Run `external-client-quickstart-verify` before handing the setup to another
engineer or agent. It checks the saved readiness bundle against the repo
docs/examples quickstart contract without calling BIBER or resolving API keys.
Run `show-external-client-quickstart-verification` to inspect that saved
verification summary later without rerunning the checks or resolving API keys.
Run `external-client-integration-package` after readiness, env-template, and
quickstart verification are complete. It creates one non-secret package linking
the setup artifacts and next client steps for IDE agents, gateways, or
conversational apps.
Run `show-external-client-integration-package` to inspect the saved integration
package later without regenerating it, resolving API keys, or opening JSON.
Run `external-client-live-smoke-plan` to generate the non-secret curl/Python
commands to run later from the consuming client host after a user
`BIBER_API_KEY` is configured.
Run `show-external-client-live-smoke-plan` to inspect the saved live-smoke plan
later without regenerating it, resolving keys, or calling BIBER.
Run `show-latest-external-client-live-smoke-plan` to find the newest saved
live-smoke plan under an outputs directory and print the same read-only summary.

## Minimal Client Examples

Use `examples/external_agent/` when wiring a generic client or gateway. The
examples only need `BIBER_OPENAI_BASE_URL`, `BIBER_MODEL`, and `BIBER_API_KEY`;
they call `/v1/chat/completions` with `stream=false` and OpenAI mentor disabled.

Validate the examples offline before pointing them at the live GPU:

```bash
python scripts/biber_external_agent_examples_smoke.py
```

## Public HTTPS Gateway Later

A domain is not required for local MVP work. If an internet-accessible endpoint
is needed later, place HTTPS in front of BIBER with a reverse proxy, load
balancer, or cloud API gateway, then generate the profile with the public URL:

```bash
python scripts/biber_agent_client.py external-agent-readiness \
  --client-base-url https://api.example.com \
  --output /workspace/outputs/biber-external-agent-readiness-public.json

python scripts/biber_agent_client.py external-agent-connection \
  --client-base-url https://api.example.com \
  --output /workspace/outputs/biber-external-agent-connection-public.json
```

Keep the GPU/vLLM port private. Public clients should reach only the BIBER API
gateway.

For the real `beaverapi.com` domain, use
[`docs/BIBER_PUBLIC_DOMAIN_SETUP.md`](BIBER_PUBLIC_DOMAIN_SETUP.md). The
recommended MVP endpoint is `https://api.beaverapi.com/v1` through Cloudflare
Tunnel to the Vast BIBER API on `127.0.0.1:8000`.

## Smoke Test

After the connection profile, run one readiness-plus-chat smoke:

```bash
python scripts/biber_agent_client.py external-agent-smoke \
  --client-base-url "$BIBER_API_BASE_URL" \
  --output /workspace/outputs/biber-external-agent-smoke.json
```

This writes one non-secret proof artifact with readiness checks, selected model
metadata, and one short OpenAI-compatible chat-completions response.
When validating a saved handoff bundle specifically, prefer
`external-agent-bundle-chat-smoke`; it starts from the bundle artifact that a
future gateway or conversational agent will consume.

You can also send a raw OpenAI-compatible request when debugging a specific
prompt or model:

```bash
python scripts/biber_agent_client.py chat-completions \
  --model biber-dev-core-v1 \
  --message "Write one concise Rust review note." \
  --max-tokens 120 \
  --output /workspace/outputs/biber-chat-completions-smoke.json
```

This uses the local BIBER model source. It does not call OpenAI mentor unless a
caller explicitly opts in through BIBER's mentor controls.

## Troubleshooting

- `401` or `403`: check the BIBER user API key. Do not use the admin key for
  ordinary model requests.
- `404`: check whether the client expects the root API URL or the OpenAI-style
  `/v1` URL. Use `openai_base_url` from the connection artifact for generic
  OpenAI-compatible clients.
- `model not found`: run `models --output ...` and use an enabled model ID.
- `context length` errors: reduce prompt/context size or use a model/runtime
  profile with a larger context window later.
- GitHub Copilot may require an extension or gateway before it can use a custom
  model source directly. Keep BIBER's side generic: HTTPS, bearer API key,
  `/v1/models`, and `/v1/chat/completions`.
