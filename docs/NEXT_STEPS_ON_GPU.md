# Next Steps on Your Logged-In GPU Server

You said you already logged into the GPU. Run these steps.

---

## 1. Confirm GPU

```bash
nvidia-smi
```

You should see your RTX GPUs.

---

## 2. Install basics

```bash
apt update
apt install -y git curl nano htop tmux unzip jq
```

---

## 3. Clone Or Upload This Repo To The GPU

Preferred GitHub clone:

```bash
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
```

Or upload from your local machine:

```bash
scp -P <PORT> -r biber-ai-platform root@ssh*.vast.ai:/root/
ssh -p <PORT> root@ssh*.vast.ai
cd /root/biber-ai-platform
```

---

## 4. Start the stack

### Preferred on Vast.ai no-Docker templates

If `docker --version` says `command not found`, use the direct vLLM/FastAPI path:

```bash
cp .env.example .env
bash scripts/vast_bootstrap_direct.sh
```

This installs into `/workspace`, starts vLLM on `8001`, starts the BIBER API on `8000`, and can be rerun on a replacement GPU.

### Docker-capable templates

If Docker and the NVIDIA container runtime are available:

```bash
cp .env.example .env
bash scripts/01_check_gpu.sh
bash scripts/02_start.sh
```

The first model startup can take time while vLLM pulls `BIBER_HF_MODEL`.

---

## 5. Test API

```bash
bash scripts/03_test_api.sh
```

For direct deploys, wait until `bash scripts/vast_status_direct.sh` shows both HTTP checks responding. For Docker deploys, wait until `docker compose logs -f biber-dev-core` shows the model is ready.

---

## 6. Open API docs

```text
http://<GPU_PUBLIC_IP>:8000/docs
```

If Vast.ai does not expose port 8000 directly, add port mapping/expose port in Vast.ai instance settings.

For SSH tunneling from your local machine:

```bash
ssh -i <path-to-key> -p <port> root@<host> -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

Then open `http://127.0.0.1:8000/docs`.

---

## 7. What to build next

Priority order:

1. Bring up `biber-dev-core` through vLLM and verify `/v1/chat`.
2. Add OpenAI mentor credentials if desired.
3. Add GitHub token and test generated-code save.
4. Add Azure Blob connection string and test backups.
5. Replace demo API key auth with DB-backed API keys.
6. Implement real MySQL persistence for jobs.
7. Connect worker to Redis queue.
8. Add QLoRA training pipeline.
9. Build React admin dashboard.
10. Add FFmpeg/video processing workers.
11. Add proctoring event pipeline.
