# Phase 1 Vast.ai Deploy Notes

There are two supported Vast.ai deployment paths:

- Direct vLLM/FastAPI path for templates without Docker inside the instance.
- Docker Compose path for templates with Docker and the NVIDIA container runtime.

Use the direct path first unless `docker --version` and `docker compose version` both work.

## 1. Connect

Use the SSH command from the Vast.ai instance page:

```powershell
ssh -p <port> <user>@<host>
```

If Vast shows a key path, use:

```powershell
ssh -i <path-to-key> -p <port> <user>@<host>
```

## 2. Copy Project

From this machine, run:

```powershell
scp -P <port> -r .\biber-ai-platform <user>@<host>:/workspace/biber-ai-platform
```

With a key:

```powershell
scp -i <path-to-key> -P <port> -r .\biber-ai-platform <user>@<host>:/workspace/biber-ai-platform
```

## 3. Configure

On the Vast instance:

```bash
cd /workspace/biber-ai-platform
cp .env.example .env
```

Edit `.env` on the instance and set:

```text
BIBER_API_KEYS=<strong-api-key>
BIBER_PRIORITY_PASSCODES=<owner-passcode>:0
BIBER_MENTOR_ENABLED=true
OPENAI_API_KEY=<optional-openai-key>
OPENAI_MODEL=<mentor-model-name>
GITHUB_TOKEN=<optional-github-token>
AZURE_STORAGE_CONNECTION_STRING=<optional-azure-blob-connection-string>
```

Keep `BIBER_MENTOR_ENABLED=false` if you want all prompts to stay on the
GPU-only path. When mentor credentials are configured, BIBER still calls OpenAI
only for prompts that include `Review with OpenAI mentor`.

## 4. Run Directly Without Docker

This is the repeatable path for the current Vast.ai style of container:

```bash
bash scripts/vast_bootstrap_direct.sh
```

It installs a venv under `/workspace/biber-venv`, installs vLLM, downloads the model into `/workspace/.hf_home`, starts vLLM on port `8001`, and starts the API on port `8000`.

Useful follow-up commands:

```bash
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
bash scripts/vast_stop_direct.sh
```

See `docs/VAST_DIRECT_DEPLOY.md` for the full fresh-GPU runbook.

## 5. Run With Docker Compose

```bash
docker compose up -d --build
docker compose logs -f biber-dev-core
```

Once vLLM finishes loading the model, test:

```bash
curl -H "Authorization: Bearer <strong-api-key>" http://localhost:8000/health
```

## 6. Chat

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "content-type: application/json" \
  -H "Authorization: Bearer <strong-api-key>" \
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

## 7. Useful Checks

```bash
nvidia-smi
bash scripts/vast_status_direct.sh
docker ps
docker compose logs --tail=100 api
docker compose logs --tail=100 biber-dev-core
```

## Information Needed From Vast

Send the SSH command from the Vast instance page, for example:

```text
ssh -p 12345 root@12.34.56.78
```

If it requires a local key, send only the key path, not the key contents.
