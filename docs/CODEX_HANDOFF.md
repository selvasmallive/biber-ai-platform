# Codex Handoff

Last updated: 2026-05-16

## Current Goal

Continue the live Vast.ai deployment and development of the BIBER AI Platform from
the current GPU-backed direct vLLM/FastAPI state.

## Repo State

- Local branch: `main`
- Remote: `origin` points to `https://github.com/selvasmallive/biber-ai-platform.git`
- GitHub `origin/main` was pushed from this workstation on 2026-05-16 and now
  includes the live deployment hardening and handoff updates.
- The push included at least:
  - `b782c05 Harden Vast direct service binding`
  - `b0462e6 Update Vast handoff state`
  - `73bd171 Refresh Vast deployment handoff`
- Later local/Vast commits may exist on top of those; verify with Git before
  acting on branch state.
- GitHub push of later work was blocked in this Codex session by
  non-interactive Git Credential Manager credentials:
  `fatal: Cannot prompt because user interactivity has been disabled.`
- At the last GitHub check, `origin/main` remained at
  `c483bb1 Record Vast push state`.
- The local checkout and Vast.ai checkout were advanced beyond GitHub with:
  - `97094ea Harden GitHub save integration`
  - `0272643 Update Vast handoff after GitHub save deploy`
  - `fae51c2 Record pytest availability in handoff`
- A later handoff-only commit may exist on top of `fae51c2`.
- Use `git status --short --branch`, `git log --oneline -1`, and
  `git ls-remote origin refs/heads/main` for authoritative current Git state.
- Keep the Vast.ai checkout at `/workspace/biber-ai-platform` fast-forwarded
  with `git pull --ff-only origin main` after documentation or deployment
  commits are pushed.
- Prefer `git status --short --branch` and `git log --oneline -1` over this
  file for authoritative current Git state.

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
- Verified a richer live `/v1/chat` prompt through FastAPI produced a real
  Python `fib(n)` implementation from `biber-dev-core`.
- Hardened the direct deployment so FastAPI and vLLM bind to `127.0.0.1` by
  default. Use SSH tunnels unless the `.env` credentials have been replaced and
  public binding is intentionally configured.
- Restarted the live Vast.ai services after applying explicit loopback values in
  `.env`. Final `ss` output showed both listeners on `127.0.0.1` only.
- Re-verified the live Vast.ai deployment on 2026-05-16:
  - Vast checkout: `main...origin/main [ahead 2]`
  - vLLM pid: `5634`
  - FastAPI pid: `6039`
  - both services listening only on `127.0.0.1`
  - `bash scripts/vast_test_direct.sh` passed
  - `/v1/chat` returned model content `ok` from `biber-dev-core`
- Hardened the GitHub generated-code save integration in `97094ea`:
  - GitHub target paths are normalized and reject empty/parent-directory paths.
  - missing GitHub owner/repo now returns a controlled configuration error
    instead of an unhandled exception.
  - GitHub API and network failures are wrapped as controlled save errors.
  - `/v1/chat` save-to-GitHub and `/v1/save/github` map disabled/config/API
    failures to clear HTTP responses.
  - added mocked client tests in `tests/test_github_client.py`.
- Deployed `97094ea` to the Vast.ai checkout through a Git bundle because
  GitHub push was blocked by credentials. Vast is now ahead of `origin/main`.
- Restarted only FastAPI after deploying `97094ea`; vLLM stayed warm.
  - vLLM pid: `5634`
  - FastAPI pid: `6759`
- Verified on Vast.ai after the FastAPI restart:
  - `/workspace/biber-venv/bin/python -m compileall app src tests` passed.
  - mocked GitHub client checks passed against the Vast virtualenv.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/save/github` without `GITHUB_TOKEN` returns
    `HTTP 503 {"detail":"GitHub saving is not configured."}`.
- Installed `pytest>=8,<9` into the Vast.ai virtualenv and verified
  `tests/test_github_client.py` passes:
  - Python: `/workspace/biber-venv/bin/python`
  - pytest: `8.4.2`
  - result: `5 passed`

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
  - Model: `Qwen/Qwen2.5-Coder-7B-Instruct`
  - Served model name: `biber-dev-core`
  - Tensor parallel size: `2`
  - Max model length: `8192`
- BIBER FastAPI:
  - URL: `http://127.0.0.1:8000`
  - Environment: `gpu`
  - Chat mode: `infer`
  - Run `bash scripts/vast_status_direct.sh` for current PIDs and bind details.

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

### Loopback bind defaults

`scripts/lib/vast_direct_common.sh` defaults both services to loopback:

```text
BIBER_API_HOST=127.0.0.1
BIBER_VLLM_HOST=127.0.0.1
```

Set either host to `0.0.0.0` only after replacing the starter credentials and
intentionally exposing the instance.

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
- `.env` explicitly contains:
  - `BIBER_API_HOST=127.0.0.1`
  - `BIBER_VLLM_HOST=127.0.0.1`
- A redacted credential audit on 2026-05-16 showed the live `.env` still uses
  starter values for sensitive placeholders. Live rotation was not performed
  because changing running API credentials requires explicit user approval.
- Before public exposure, replace all starter credentials in `.env`:
  - `BIBER_ADMIN_PASSWORD`
  - `BIBER_DEMO_API_KEY`
  - `BIBER_API_KEYS`
  - `BIBER_PASSCODE_FULL_GPU`
  - `BIBER_PASSCODE_20_GPU`
  - `BIBER_PASSCODE_QUEUE_PRIORITY`
  - `BIBER_PRIORITY_PASSCODES`
  - `MYSQL_ROOT_PASSWORD`
  - `MYSQL_PASSWORD`
- The direct path starts only:
  - `biber-dev-core` through vLLM
  - BIBER FastAPI
- The direct path does not start MySQL, Redis, or Adminer.
- Optional integrations are currently not configured on the live instance:
  - OpenAI mentor
  - GitHub generated-code save credentials
  - Azure Blob backups

## Operating Notes For Future Codex Sessions

- Do not rotate live credentials routinely. Treat credential rotation as an
  explicit, infrequent operation that requires user approval and a plan for
  preserving the new secrets outside chat.
- Keep the deployment loopback-only while starter credentials remain in place.
- Update this handoff at important points so a new Codex session can resume
  accurately from the current Vast.ai state. Important points include:
  - live service restarts or failures
  - host, SSH port, key path, runtime path, pid, or log path changes
  - Git commit/branch/remote state changes
  - dependency, model, port, bind, or environment changes
  - smoke test, runtime test, mentor, GitHub save, Azure backup, MySQL, or Redis
    status changes
  - credential status changes, without recording secret values

## Recommended Next Steps

1. Keep the API private over SSH tunnels unless credentials are deliberately
   rotated and public binding is intentionally enabled.
2. Authenticate GitHub push from this workstation and push local `main` so
   `origin/main` includes the GitHub save hardening and this handoff state.
3. Keep the Vast.ai checkout fast-forwarded with local/GitHub `main`.
4. Add optional OpenAI mentor credentials if desired.
5. Add GitHub token and test real generated-code save.
6. Add Azure Blob connection string and test backups.
7. Replace demo API key/passcode auth with database-backed credentials.
8. Add real MySQL persistence and Redis worker integration.

## Resume Prompt For A New Chat

```text
Read docs/CODEX_HANDOFF.md and continue the Vast.ai deployment and development
of biber-ai-platform from the current live GPU state.
```
