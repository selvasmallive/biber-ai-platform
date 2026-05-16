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

Upload or clone this repo, then run:

```bash
cd biber-ai-platform
cp .env.example .env
bash scripts/01_check_gpu.sh
bash scripts/02_start.sh
```

Open API docs:

```text
http://<YOUR_SERVER_IP>:8000/docs
```

If you are using Vast.ai SSH port forwarding, expose port `8000`.

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
