# Phase 1 Vast.ai Deploy Notes

This deploy path assumes the Vast.ai instance has Docker, the NVIDIA container runtime, and a CUDA-capable GPU image.

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
BIBER_PRIORITY_PASSCODES=<owner-passcode>:100
BIBER_MENTOR_ENABLED=true
OPENAI_API_KEY=<optional-openai-key>
OPENAI_MODEL=<mentor-model-name>
GITHUB_TOKEN=<optional-github-token>
AZURE_STORAGE_CONNECTION_STRING=<optional-azure-blob-connection-string>
```

Keep `BIBER_MENTOR_ENABLED=false` if you want all prompts to stay on the GPU-only path.

## 4. Run

```bash
docker compose -f docker-compose.gpu.yml up -d --build
docker compose -f docker-compose.gpu.yml logs -f biber-dev-core
```

Once vLLM finishes loading the model, test:

```bash
curl -H "x-api-key: <strong-api-key>" http://localhost:8080/health
```

## 5. Chat

```bash
curl -X POST http://localhost:8080/v1/chat \
  -H "content-type: application/json" \
  -H "x-api-key: <strong-api-key>" \
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

## 6. Useful Checks

```bash
nvidia-smi
docker ps
docker compose -f docker-compose.gpu.yml logs --tail=100 biber-api
docker compose -f docker-compose.gpu.yml logs --tail=100 biber-dev-core
```

## Information Needed From Vast

Send the SSH command from the Vast instance page, for example:

```text
ssh -p 12345 root@12.34.56.78
```

If it requires a local key, send only the key path, not the key contents.
