# BIBER AI Platform

Private GPU-backed AI platform for:

- `biber-dev-core` software-development model
- `biber-video-core` video processing
- `biber-audio-core` audio processing
- `biber-proctor-core` online proctoring workflows
- API key + passcode access
- GPU-priority job scheduling
- OpenAI-compatible local GPU inference through vLLM
- Optional OpenAI mentor layer
- GitHub save and Azure Blob backup hooks

This repo is intentionally separate from KANI/XRIQ. It is the standalone BIBER workspace and GitHub repo.

---

## 1. Quick Start On GPU Server

After SSH login to your Vast.ai GPU instance:

```bash
apt update
apt install -y git curl nano htop tmux unzip mysql-client
```

Upload or clone this repo, then run the direct Vast.ai path:

```bash
cd biber-ai-platform
cp .env.example .env
bash scripts/vast_bootstrap_direct.sh
```

If your GPU template has Docker and the NVIDIA container runtime available, the older Compose path is still available with `bash scripts/02_start.sh`.

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Use SSH port forwarding for local access:

```bash
ssh -i <path-to-key> -p <port> root@<host> -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

See `docs/VAST_DIRECT_DEPLOY.md` for the repeatable fresh-GPU deployment runbook.

---

## 2. Services

| Service | Purpose |
|---|---|
| `api` | FastAPI public/admin API |
| `worker` | GPU model worker placeholder |
| `biber-dev-core` | vLLM OpenAI-compatible coding model runtime |
| `mysql` | MySQL database |
| `redis` | Queue/cache |
| `adminer` | Web DB viewer |

On no-Docker Vast.ai templates, `scripts/vast_bootstrap_direct.sh` starts only `api` and `biber-dev-core`. MySQL, Redis, and Adminer remain Docker-only until a managed database/queue path is added.

---

## 3. Default Admin

```text
Username: biber_admin
Password: ChangeMeImmediately!123
```

Change this immediately before production use.

---

## 4. API Authentication

Public API requests require:

```http
Authorization: Bearer <API_KEY>
X-Biber-Passcode: <OPTIONAL_PASSCODE>
```

The API also accepts `x-api-key` for OpenAI-style clients. Starter API keys in `.env.example`:

```text
dev-api-key-change-me
dev-biber-key-change-me
```

Starter passcodes:

```text
BIBER_FULL_GPU_DEMO
BIBER_20_GPU_DEMO
BIBER_QUEUE_PRIORITY_DEMO
```

---

## 5. Phase 1 Success Criteria Mapping

```text
1. BIBER API runs on GPU              -> docker-compose.yml api service
2. /v1/chat endpoint works            -> app/main.py
3. OpenAI mentor service is connected -> app/llm.py optional mentor client
4. biber-dev-core can generate code   -> vLLM service named biber-dev-core
5. Code output can be saved to GitHub -> /v1/save/github and chat save option
6. Models/data can be backed up       -> /v1/backup/azure and chat backup option
```

## 6. Chat Example

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "TypeScript",
    "messages": [
      {
        "role": "user",
        "content": "Create a React hook that debounces a search query."
      }
    ]
  }'
```

OpenAI mentor review is optional and costed. Configure `BIBER_MENTOR_ENABLED`,
`OPENAI_API_KEY`, and `OPENAI_MODEL` on the server, then opt in per prompt with
the phrase `Review with OpenAI mentor`:

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "Rust",
    "messages": [
      {
        "role": "user",
        "content": "Review with OpenAI mentor: Review this XRIQ wallet signing plan."
      }
    ]
  }'
```

To use the older queue-only starter behavior:

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"message":"Create a FastAPI health endpoint","queue_only":true}'
```

## 7. Vast Connection Needed

To deploy this to your Vast.ai GPU, use the instance SSH command:

```text
ssh -p <port> <user>@<host>
```

If the instance uses an SSH key, use the local key path. Do not paste private key contents into chat.

## 8. Important Production Notes

This starter is intentionally simple. Before production:

- Hash API keys and passcodes
- Replace demo auth with database-backed auth
- Add HTTPS
- Add proper queue workers
- Add model weights volume
- Add audit logs to database
- Use Kubernetes/AKS for multi-node production
- Add real GPU quota/preemption logic using containers/MIG/Kubernetes device plugins
