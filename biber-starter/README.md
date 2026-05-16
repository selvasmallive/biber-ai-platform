# BIBER Starter Repo

Private GPU-backed AI platform starter for:

- `biber-dev-core` software-development model
- `biber-video-core` video processing
- `biber-audio-core` audio processing
- `biber-proctor-core` online proctoring workflows
- API key + passcode access
- GPU-priority job scheduling

This starter is designed to run first on your GPU server, such as Vast.ai.

---

## 1. Quick Start on GPU Server

After SSH login to your Vast.ai GPU instance:

```bash
apt update
apt install -y git curl nano htop tmux unzip mysql-client
```

Upload or clone this repo, then run:

```bash
cd biber-starter
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

Starter API key in `.env.example`:

```text
dev-api-key-change-me
```

Starter passcodes:

```text
BIBER_FULL_GPU_DEMO
BIBER_20_GPU_DEMO
BIBER_QUEUE_PRIORITY_DEMO
```

---

## 5. Important Production Notes

This starter is intentionally simple. Before production:

- Hash API keys and passcodes
- Replace demo auth with database-backed auth
- Add HTTPS
- Add proper queue workers
- Add model weights volume
- Add audit logs to database
- Use Kubernetes/AKS for multi-node production
- Add real GPU quota/preemption logic using containers/MIG/Kubernetes device plugins
