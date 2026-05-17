# API Examples

## List Models

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer dev-api-key-change-me"
```

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
    "task_type": "code_generation",
    "messages": [
      {
        "role": "user",
        "content": "Create a React hook that debounces a search query."
      }
    ]
  }'
```

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
