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

python scripts/biber_agent_client.py external-agent-connection \
  --client-base-url "$BIBER_API_BASE_URL" \
  --output /workspace/outputs/biber-external-agent-connection.json

python scripts/biber_agent_client.py capabilities \
  --output /workspace/outputs/biber-capabilities.json

python scripts/biber_agent_client.py runtime \
  --output /workspace/outputs/biber-runtime.json

python scripts/biber_agent_client.py models \
  --output /workspace/outputs/biber-models.json
```

The connection artifact is safe to share with a local agent setup because it
does not contain the API key. The API key must be configured separately in the
client's secret or environment setting.

## Public HTTPS Gateway Later

A domain is not required for local MVP work. If an internet-accessible endpoint
is needed later, place HTTPS in front of BIBER with a reverse proxy, load
balancer, or cloud API gateway, then generate the profile with the public URL:

```bash
python scripts/biber_agent_client.py external-agent-connection \
  --client-base-url https://api.example.com \
  --output /workspace/outputs/biber-external-agent-connection-public.json
```

Keep the GPU/vLLM port private. Public clients should reach only the BIBER API
gateway.

## Smoke Test

After the connection profile, send one short OpenAI-compatible request:

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
