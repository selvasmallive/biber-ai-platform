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

## 3. Upload this zip to the GPU

From your local machine, use one of these:

```bash
scp -P <PORT> biber-starter.zip root@ssh*.vast.ai:/root/
```

Then on GPU:

```bash
cd /root
unzip biber-starter.zip
cd biber-starter
```

---

## 4. Start the stack

```bash
cp .env.example .env
bash scripts/01_check_gpu.sh
bash scripts/02_start.sh
```

---

## 5. Test API

```bash
bash scripts/03_test_api.sh
```

---

## 6. Open API docs

```text
http://<GPU_PUBLIC_IP>:8000/docs
```

If Vast.ai does not expose port 8000 directly, add port mapping/expose port in Vast.ai instance settings.

---

## 7. What to build next

Priority order:

1. Replace demo API key auth with DB-backed API keys.
2. Implement real MySQL persistence for jobs.
3. Connect worker to Redis queue.
4. Download a base coding model.
5. Load model in worker.
6. Add QLoRA training pipeline.
7. Build React admin dashboard.
8. Add FFmpeg/video processing workers.
9. Add proctoring event pipeline.
