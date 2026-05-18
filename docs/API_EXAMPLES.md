# API Examples

## List Models

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer dev-api-key-change-me"
```

The response includes stable/candidate model metadata. By default
`biber-dev-core-v1` is enabled and backed by the current local Qwen2.5-Coder
runtime, while `biber-dev-core-v2-candidate` is disabled until a Qwen3 or newer
candidate endpoint is configured and benchmarked.

## Runtime Status

```bash
curl http://localhost:8000/v1/runtime \
  -H "Authorization: Bearer dev-api-key-change-me"
```

## Generate Code With biber-dev-core

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "X-Biber-Passcode: BIBER_QUEUE_PRIORITY_DEMO" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "TypeScript",
    "model": "biber-dev-core-v1",
    "task_type": "code_generation",
    "repo_context_paths": ["src/components/SearchBox.tsx"],
    "messages": [
      {
        "role": "user",
        "content": "Create a React hook that debounces a search query."
      }
    ]
}'
```

`repo_context_paths` accepts selected workspace-relative files only. The server
applies file-count and byte limits and rejects `.env`, private-key-looking
files, cache directories, and paths outside the configured repo context root.

## Queue Chat Job Instead Of Immediate Inference

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a FastAPI endpoint for health check",
    "queue_only": true
}'
```

## Request OpenAI Mentor Review

Set `BIBER_MENTOR_ENABLED=true`, `OPENAI_API_KEY`, and `OPENAI_MODEL` on the
server first. BIBER calls OpenAI only when the prompt includes the explicit
trigger phrase `Review with OpenAI mentor`.

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "Rust",
    "task_type": "security_review",
    "messages": [
      {
        "role": "user",
        "content": "Review with OpenAI mentor: Review this XRIQ transaction validation design."
      }
    ]
  }'
```

## Submit Code Task

```bash
curl http://localhost:8000/v1/code \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "X-Biber-Passcode: BIBER_QUEUE_PRIORITY_DEMO" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "prompt": "Create a FastAPI endpoint for health check",
    "model": "biber-dev-core"
  }'
```

## Save Generated Code To GitHub

Set `GITHUB_TOKEN`, `GITHUB_DEFAULT_OWNER`, and `GITHUB_DEFAULT_REPO` in `.env`, then:

```bash
curl -X POST http://localhost:8000/v1/save/github \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "target": {
      "path": "generated/example.ts",
      "branch": "main",
      "commit_message": "Save generated BIBER example"
    },
    "content": "export const hello = () => \"biber\";\n"
}'
```

## XRIQ Private-Devnet Preflight Transfer

This endpoint is a thin wrapper around the local Rust
`xriq-node preflight-transfer --format json` command. The chain file, pending
file, Rust workspace, and runner command are configured on the server with
`BIBER_XRIQ_*` settings. The request does not accept arbitrary file paths.

```bash
curl -X POST http://localhost:8000/v1/xriq/private-devnet/preflight-transfer \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "xriqdev1alice00000000000",
    "to": "xriqdev1bobbb00000000000",
    "amount_base_units": "25",
    "fee_base_units": "2",
    "expires_at_height": 100,
    "timestamp_ms": 1000
  }'
```

## XRIQ Private-Devnet Read Helpers

These endpoints are thin wrappers around the existing `xriq-node --format json`
read commands. Mempool detail is intentionally not exposed through BIBER yet
because the current CLI command does not read the durable pending file; add that
Rust support first so the API does not present misleading pending state.

```bash
curl http://localhost:8000/v1/xriq/private-devnet/status \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/accounts/xriqdev1alice00000000000 \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/transactions/<transaction-hash> \
  -H "Authorization: Bearer dev-api-key-change-me"
```

## Submit Proctoring Analysis

```bash
curl http://localhost:8000/v1/proctor/session/analyze \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "X-Biber-Passcode: BIBER_20_GPU_DEMO" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_001",
    "prompt": "Analyze for face missing, multiple faces, and speech events",
    "model": "biber-proctor-core"
  }'
```
