# BIBER Live Provider Runbook

Use this runbook only for BIBER MVP live local-model work. Do not use it for
XRIS-Coin/XRIQ work.

## Default: Stay Local

Do not ask for Vast/GPU details for routine source edits, docs, local repair
loop work, or no-API validation. First run the combined local confidence gate:

```bash
python scripts/biber_local_confidence_smoke.py
```

This proves the local provider wrapper, mocked readiness probe, and local repair
loop without external network, OpenAI mentor, GPU, API auth, or training.

## When To Ask For Vast/GPU Details

Ask the user for Vast/GPU connection details only when the next BIBER task
requires at least one of these:

- live local-model inference through a Qwen/vLLM/OpenAI-compatible endpoint
- batch evals against a live served model or adapter
- adapter restore or Hugging Face cache restore on a GPU volume
- QLoRA/training after reviewed eval/training readiness says it is needed
- debugging a live provider readiness failure that cannot be reproduced locally

Do not ask for GPU details just because the user says "continue."

## What To Ask The User For

Ask for connection metadata, not secret values:

- Vast instance id
- copied SSH connection command from the Vast.ai instance connect screen
- SSH private key path on this workstation, if not the default
- whether a persistent volume is attached
- whether the model endpoint is already running
- the local or tunneled OpenAI-compatible base URL, usually
  `http://127.0.0.1:8001/v1`
- the served model or adapter alias expected in `/v1/models`
- whether the endpoint requires a token

If a token is required, tell the user to set it locally as
`BIBER_LOCAL_OPENAI_API_KEY`. Do not ask them to paste the token into chat or
commit it.

## SSH Tunnel Shape

Prefer private loopback tunnels over public exposure. A typical tunnel shape is:

```bash
ssh -i <path-to-key> -p <port> \
  -L 8001:127.0.0.1:8001 \
  -L 8000:127.0.0.1:8000 \
  root@<host>
```

Port `8001` is the local OpenAI-compatible model endpoint. Port `8000` is only
needed when using the BIBER API service directly.

## Readiness Check

After the endpoint or tunnel exists, set local provider variables on the
workstation.

PowerShell:

```powershell
$env:BIBER_LOCAL_OPENAI_BASE_URL = "http://127.0.0.1:8001/v1"
$env:BIBER_LOCAL_OPENAI_MODEL = "<served-model-or-adapter-alias>"
```

Bash:

```bash
export BIBER_LOCAL_OPENAI_BASE_URL="http://127.0.0.1:8001/v1"
export BIBER_LOCAL_OPENAI_MODEL="<served-model-or-adapter-alias>"
```

Then run:

```bash
python scripts/biber_live_provider_readiness.py \
  --model <served-model-or-adapter-alias> \
  --require-ready \
  --require-model
```

This uses `GET /v1/models` only. It does not send a repair request, does not
send a chat completion, does not use OpenAI mentor, and does not train.

## Live Repair-Loop Provider Command

After readiness passes, the local repair loop can use the swappable provider
wrapper:

```bash
python scripts/biber_agent_client.py --json local-repair-chain prepared-repair.json \
  --model-command "[\"python\",\"scripts/biber_local_openai_provider.py\"]" \
  --target-root /path/to/repo \
  --output /tmp/local-repair-chain.json
```

The provider wrapper resolves logical BIBER model IDs such as
`biber-dev-core-v1` through the local registry/env defaults before it sends the
OpenAI-compatible request. If a live endpoint must use a specific served alias,
set `BIBER_LOCAL_OPENAI_MODEL` or pass `--model <served-alias>` inside the
model-command JSON array.

Continue with the existing deterministic gates:

```bash
python scripts/biber_agent_client.py --json review-local-repair-chain /tmp/local-repair-chain.json \
  --output /tmp/local-repair-chain-review.json
```

Apply still requires an explicit approved plan/review gate. Do not auto-apply
or train from live model output.

## If Readiness Fails

Keep the failure cheap and local first:

- verify the tunnel is still open
- verify `BIBER_LOCAL_OPENAI_BASE_URL`
- verify the model endpoint listens on the expected port
- verify the requested model or adapter alias appears in `/v1/models`
- verify `BIBER_LOCAL_OPENAI_API_KEY` is set locally only if auth is enabled
- rerun `python scripts/biber_live_provider_readiness.py --model <alias>`

Only then ask the user for updated Vast connection metadata.
