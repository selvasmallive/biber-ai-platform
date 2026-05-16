# Vast.ai Direct GPU Deploy

This is the repeatable path for Vast.ai templates that expose GPUs but do not provide Docker inside the instance. It runs:

- `biber-dev-core` through vLLM on port `8001`
- BIBER FastAPI on port `8000`
- runtime files under `/workspace` so the small root filesystem stays clean

Both services bind to `127.0.0.1` by default. Use an SSH tunnel for access while
the starter credentials are present.

Use this path when `docker --version` returns `command not found`.

---

## 1. Start From A Fresh GPU

In Vast.ai, choose a GPU instance with SSH or Jupyter terminal access. After you connect:

```bash
cd /workspace
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
bash scripts/vast_bootstrap_direct.sh
```

The bootstrap script is idempotent. It can be rerun on the same instance and will reuse:

```text
/workspace/biber-venv
/workspace/.hf_home
/workspace/pip-cache
/workspace/biber-logs
/workspace/biber-pids
```

First startup may take several minutes while vLLM installs packages, downloads the model, compiles kernels, and warms the GPU.

---

## 2. Configure Before Public Use

The first run creates `.env` from `.env.example` if needed. Replace demo values before exposing the API outside an SSH tunnel:

```bash
nano .env
```

Minimum values to change:

```text
BIBER_DEMO_API_KEY=<strong-api-key>
BIBER_API_KEYS=<strong-api-key>
BIBER_PASSCODE_FULL_GPU=<owner-passcode>
BIBER_PASSCODE_20_GPU=<limited-passcode>
BIBER_PASSCODE_QUEUE_PRIORITY=<queue-passcode>
```

To intentionally expose a hardened instance on the Vast.ai host network, set the
bind hosts after replacing the starter credentials:

```text
BIBER_API_HOST=0.0.0.0
BIBER_VLLM_HOST=0.0.0.0
```

Optional integrations:

```text
BIBER_MENTOR_ENABLED=true
OPENAI_API_KEY=<optional-openai-key>
OPENAI_MODEL=<mentor-model-name>
GITHUB_TOKEN=<optional-github-token>
AZURE_STORAGE_CONNECTION_STRING=<optional-azure-blob-connection-string>
HF_TOKEN=<optional-huggingface-token>
```

Keep `.env` out of git.

---

## 3. Useful Commands

Start or restart services:

```bash
bash scripts/vast_start_direct.sh
```

Check status:

```bash
bash scripts/vast_status_direct.sh
```

Run smoke tests:

```bash
bash scripts/vast_test_direct.sh
```

Stop services:

```bash
bash scripts/vast_stop_direct.sh
```

Follow logs:

```bash
tail -f /workspace/biber-logs/vllm.log
tail -f /workspace/biber-logs/api.log
```

---

## 4. Local SSH Tunnel

Use the SSH command shown by Vast.ai and add local forwards:

```bash
ssh -i <path-to-key> -p <port> root@<host> \
  -L 8000:127.0.0.1:8000 \
  -L 8001:127.0.0.1:8001
```

Then open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8001/v1/models
```

For Windows PowerShell, keep the same command on one line:

```powershell
ssh -i C:\Users\vselv\.ssh\biber_vast_ed25519 -p <port> root@<host> -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

Do not paste private key contents into chat or docs.

---

## 5. Moving To A Different GPU

On the new Vast.ai instance:

1. Add your public SSH key to the instance.
2. SSH into the instance.
3. Clone the repo into `/workspace`.
4. Restore or recreate `.env`.
5. Run `bash scripts/vast_bootstrap_direct.sh`.
6. Run `bash scripts/vast_test_direct.sh`.
7. Create a new SSH tunnel using the new host and port.

The model cache is not portable unless you copy `/workspace/.hf_home`; on a fresh GPU the model will download again.

---

## 6. GPU Sizing Controls

The start script uses all visible GPUs by default:

```text
BIBER_VLLM_TENSOR_PARALLEL_SIZE=<gpu-count>
CUDA_VISIBLE_DEVICES=0,1,...
```

For a single 16 GB GPU, reduce sequence length:

```bash
BIBER_VLLM_TENSOR_PARALLEL_SIZE=1 BIBER_MAX_MODEL_LEN=4096 bash scripts/vast_start_direct.sh
```

For a smaller model:

```bash
BIBER_HF_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct bash scripts/vast_bootstrap_direct.sh
```

For private or rate-limited Hugging Face models:

```bash
export HF_TOKEN=<your-token>
bash scripts/vast_bootstrap_direct.sh
```

---

## 7. What This Does Not Start

The direct path does not start Docker services, so it does not launch MySQL, Redis, or Adminer. The current Phase 1 API still works for `/health`, `/v1/runtime`, `/v1/models`, `/v1/chat`, queue placeholders, GitHub save, and Azure backup when configured.

Use `docker compose up -d --build` only on GPU templates where Docker and the NVIDIA container runtime are available.
