# Codex Handoff

Last updated: 2026-05-16

## Current Goal

Continue the live Vast.ai deployment and development of the BIBER AI Platform from
the current GPU-backed direct vLLM/FastAPI state.

## Repo State

- Local branch: `main`
- Local last known base commit: `5798c7f Avoid stale handoff commit hash`
- Remote: `origin` points to `https://github.com/selvasmallive/biber-ai-platform.git`
- Local working tree is intentionally dirty with deployment fixes:
  - `requirements-api.txt`
  - `scripts/vast_bootstrap_direct.sh`
  - `docs/CODEX_HANDOFF.md`
- The Vast.ai checkout at `/workspace/biber-ai-platform` also has the same
  uncommitted changes to `requirements-api.txt` and
  `scripts/vast_bootstrap_direct.sh`.
- Commit and push these changes before doing a future `git pull` on the Vast.ai
  instance, or copy them up again if the instance is replaced.

## Completed

- Fast-forwarded the Vast.ai checkout from `4044c5b` to `5798c7f`.
- Bootstrapped the no-Docker direct deployment path on Vast.ai.
- Verified the instance has two GPUs:
  - GPU 0: NVIDIA GeForce RTX 5060 Ti, 16311 MiB
  - GPU 1: NVIDIA GeForce RTX 5060 Ti, 16311 MiB
- Confirmed Docker is not present on the instance; the direct deployment path is
  the correct path.
- Verified local scaffold validation passes with the bundled Codex Python runtime.
- Verified local Python syntax compile checks pass for `app`, `src`, `worker`,
  `training`, and `scripts`.
- Verified remote `pip check` reports no broken requirements after dependency
  pin updates.
- Verified remote direct smoke test passes:
  - `GET /health`
  - `GET /v1/runtime`
  - `GET /v1/models`
  - `POST /v1/chat`
- `/v1/chat` returned model content `ok` from `biber-dev-core`.

## Live Vast.ai Deployment Status

- Host: `70.30.158.46`
- SSH port: `61995`
- SSH key path on this workstation: `C:\Users\vselv\.ssh\biber_vast_ed25519`
- Remote repo path: `/workspace/biber-ai-platform`
- Runtime root: `/workspace`
- Virtualenv: `/workspace/biber-venv`
- Logs:
  - `/workspace/biber-logs/vllm.log`
  - `/workspace/biber-logs/api.log`
- Pid files:
  - `/workspace/biber-pids/vllm.pid`
  - `/workspace/biber-pids/api.pid`
- vLLM:
  - URL: `http://127.0.0.1:8001/v1`
  - Current pid at last check: `2524`
  - Model: `Qwen/Qwen2.5-Coder-7B-Instruct`
  - Served model name: `biber-dev-core`
  - Tensor parallel size: `2`
  - Max model length: `8192`
- BIBER FastAPI:
  - URL: `http://127.0.0.1:8000`
  - Current pid at last check: `5015`
  - Environment: `gpu`
  - Chat mode: `infer`

## Important Fixes Made During Deployment

### Bootstrap script execution

`scripts/vast_bootstrap_direct.sh` now starts services with:

```bash
exec bash "${SCRIPT_DIR}/vast_start_direct.sh"
```

This avoids `Permission denied` on filesystems where the checked-out script is
not executable.

### Shared venv dependency pins

The direct deployment shares one virtualenv between FastAPI and vLLM. The older
API pins downgraded packages below what vLLM `0.21.0` expects. The current API
requirements now include:

```text
fastapi==0.136.1
starlette==0.52.1
pydantic==2.13.4
```

Remote `pip check` passed after applying these pins.

## Reconnect And Test

From Windows PowerShell:

```powershell
ssh -i C:\Users\vselv\.ssh\biber_vast_ed25519 -p 61995 root@70.30.158.46 -L 8080:localhost:8080 -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

Then open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8001/v1/models
http://127.0.0.1:8080
```

Do not paste private key contents, Vast API keys, Jupyter tokens, or `.env`
secrets into chat or docs.

## Useful Remote Commands

After SSH:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
```

Restart only the BIBER direct services:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_stop_direct.sh
bash scripts/vast_start_direct.sh
```

Rerun bootstrap if the environment is partially missing:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_bootstrap_direct.sh
```

Follow logs:

```bash
tail -f /workspace/biber-logs/api.log
tail -f /workspace/biber-logs/vllm.log
```

## Important Config Notes

- `.env` exists on the Vast.ai instance.
- Before public exposure, replace demo credentials in `.env`:
  - `BIBER_DEMO_API_KEY`
  - `BIBER_API_KEYS`
  - `BIBER_PASSCODE_FULL_GPU`
  - `BIBER_PASSCODE_20_GPU`
  - `BIBER_PASSCODE_QUEUE_PRIORITY`
- The direct path starts only:
  - `biber-dev-core` through vLLM
  - BIBER FastAPI
- The direct path does not start MySQL, Redis, or Adminer.
- Optional integrations are currently not configured on the live instance:
  - OpenAI mentor
  - GitHub generated-code save
  - Azure Blob backups

## Recommended Next Steps

1. Commit the local deployment fixes and handoff update.
2. Push the commit to `origin/main`.
3. Pull the commit on the Vast.ai instance once the remote dirty state is handled.
4. Replace demo `.env` credentials before exposing the API publicly.
5. Test richer `/v1/chat` prompts against the live GPU model.
6. Add optional OpenAI mentor credentials if desired.
7. Add GitHub token and test generated-code save.
8. Add Azure Blob connection string and test backups.
9. Replace demo API key/passcode auth with database-backed credentials.
10. Add real MySQL persistence and Redis worker integration.

## Resume Prompt For A New Chat

```text
Read docs/CODEX_HANDOFF.md and continue the Vast.ai deployment and development
of biber-ai-platform from the current live GPU state.
```
