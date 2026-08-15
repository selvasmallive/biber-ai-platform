# BIBER External Agent Examples

These examples show the smallest client shape needed to use BIBER as an
OpenAI-compatible model source from an IDE agent, conversational agent, gateway,
or internal app.

Use only:

```text
BIBER_OPENAI_BASE_URL=https://your-biber-api.example.com/v1
BIBER_MODEL=biber-dev-core-v1
BIBER_API_KEY=<user-api-key>
```

For a private Vast SSH tunnel, `BIBER_OPENAI_BASE_URL` can be
`http://127.0.0.1:8000/v1`. Do not point external clients at the raw vLLM
provider URL.

OpenAI mentor stays disabled in these examples. They send `stream=false` and
`use_mentor=false`.

## Python

```bash
export BIBER_OPENAI_BASE_URL="http://127.0.0.1:8000/v1"
export BIBER_MODEL="biber-dev-core-v1"
export BIBER_API_KEY="<user-api-key>"

python examples/external_agent/python_minimal_client.py \
  --message "Write one concise TypeScript review note."
```

## JavaScript

Use Node.js 18+ or another runtime with `fetch`:

```bash
export BIBER_OPENAI_BASE_URL="http://127.0.0.1:8000/v1"
export BIBER_MODEL="biber-dev-core-v1"
export BIBER_API_KEY="<user-api-key>"

node examples/external_agent/javascript_fetch_client.mjs \
  "Write one concise Java review note."
```

## Validate The Examples

This offline smoke starts a local fake OpenAI-compatible server and verifies the
Python example sends the expected URL, bearer API key, model, message, and
mentor-disabled payload:

```bash
python scripts/biber_external_agent_examples_smoke.py
```

For live BIBER validation, use the project client:

```bash
python scripts/biber_agent_client.py external-agent-smoke \
  --client-base-url "$BIBER_OPENAI_BASE_URL" \
  --output /workspace/outputs/biber-external-agent-smoke.json
```
