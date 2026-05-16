# Phase 1 Gap Analysis

This repo now combines the existing GitHub starter with the Phase 1 BIBER roadmap.

## Existing GitHub Starter Preserved

- FastAPI API service.
- API key and passcode access.
- In-memory priority scheduler.
- MySQL schema for users, API keys, passcodes, jobs, models, GPU nodes, media, proctoring, audit, and usage.
- Redis/MySQL/Adminer Docker stack.
- GPU worker placeholder.
- Video, audio, and proctoring starter endpoints.
- GPU check/start/test scripts.
- QLoRA training placeholder and dataset format notes.

## Phase 1 Gaps Found

- `/v1/chat` only queued a placeholder job; it did not call a local model.
- No OpenAI-compatible `biber-dev-core` runtime was wired into Docker Compose.
- No OpenAI mentor adapter existed.
- No runtime status endpoint existed.
- No GitHub save endpoint existed.
- No Azure Blob backup endpoint existed.
- Root `.env.example` was missing MySQL and starter passcode settings after the first local scaffold.
- Proctoring policy text used generic medium/high wording instead of the allowed advisory labels.

## Added In Integration

- `biber-dev-core` vLLM service in `docker-compose.yml`.
- Immediate `/v1/chat` inference path through `app/llm.py`.
- `queue_only` chat option to preserve the original scheduler behavior.
- Optional OpenAI mentor notes before local model generation.
- `/v1/runtime` configuration status endpoint.
- `/v1/save/github` endpoint and chat save option.
- `/v1/backup/azure` endpoint and chat backup option.
- Combined `.env.example` with API, model, mentor, GitHub, Azure, MySQL, and passcode settings.
- Updated docs and API examples for the merged behavior.

## Remaining Phase 1 Work On Vast.ai

- Provide the Vast.ai SSH command so the stack can be deployed.
- Start either the direct vLLM/FastAPI path or Docker Compose on the GPU instance.
- Wait for vLLM to load `BIBER_HF_MODEL`.
- Test `/v1/chat` against the live GPU model.
- Add real GitHub and Azure credentials if generated-code saving and backups should be enabled.
