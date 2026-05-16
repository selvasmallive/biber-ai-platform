# BIBER AI Platform

Phase 1 scaffold for `biber-dev-core`, the first BIBER AI development assistant running on your own GPU infrastructure.

## What This Starts

- `biber-api`: FastAPI service with `/v1/chat`.
- `biber-dev-core`: local OpenAI-compatible GPU model served by vLLM.
- OpenAI mentor adapter, disabled by default until `BIBER_MENTOR_ENABLED=true` and API credentials are set.
- API key authentication and priority passcodes.
- GitHub save endpoint for generated code.
- Azure Blob backup endpoint for model outputs and records.
- Vast.ai deployment notes in `docs/phase1-vast-deploy.md`.

## Local Shape

```text
User / Developer
    -> biber-api
    -> optional OpenAI mentor service
    -> local GPU model served as biber-dev-core
    -> GitHub and Azure Blob integrations
```

## Quick Start On A GPU Host

```powershell
Copy-Item .env.example .env
docker compose -f docker-compose.gpu.yml up -d --build
```

Then test the API:

```powershell
curl.exe -H "x-api-key: dev-biber-key-change-me" http://localhost:8080/health
```

Chat example:

```powershell
curl.exe -X POST http://localhost:8080/v1/chat `
  -H "content-type: application/json" `
  -H "x-api-key: dev-biber-key-change-me" `
  -d "{\"messages\":[{\"role\":\"user\",\"content\":\"Write a tiny TypeScript debounce function.\"}],\"language\":\"TypeScript\"}"
```

## Vast Connection Needed

To deploy this to your Vast.ai GPU, I need the instance SSH command or the equivalent pieces:

```text
ssh -p <port> <user>@<host>
```

If the instance uses an SSH key, I also need the local key path. Do not paste private key contents into chat.

## Phase 1 Success Criteria Mapping

```text
1. BIBER API runs on GPU              -> docker-compose.gpu.yml biber-api service
2. /v1/chat endpoint works            -> src/biber_api/main.py
3. OpenAI mentor service is connected -> src/biber_api/llm.py optional mentor client
4. biber-dev-core can generate code   -> vLLM served model name biber-dev-core
5. Code output can be saved to GitHub -> /v1/save/github and chat save option
6. Models/data backed up to Azure     -> /v1/backup/azure and chat backup option
```
