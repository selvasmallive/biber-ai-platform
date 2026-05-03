# API Examples

## List Models

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer dev-api-key-change-me"
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
