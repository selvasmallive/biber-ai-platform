# Codex Handoff

Last updated: 2026-05-16

## Current Goal

Deploy the BIBER AI Platform onto a newly rented Vast.ai GPU instance and verify the
direct vLLM/FastAPI path.

## Repo State

- Branch: `main`
- Last known checkpoint commit: run `git log -1 --oneline` after cloning or pulling.
- Working tree after this handoff file was added: clean
- Remote: `origin` points to `https://github.com/selvasmallive/biber-ai-platform.git`

## Completed

- Added a repeatable no-Docker Vast.ai deployment path.
- Added direct deployment scripts:
  - `scripts/vast_bootstrap_direct.sh`
  - `scripts/vast_start_direct.sh`
  - `scripts/vast_status_direct.sh`
  - `scripts/vast_stop_direct.sh`
  - `scripts/vast_test_direct.sh`
  - `scripts/lib/vast_direct_common.sh`
- Added the runbook at `docs/VAST_DIRECT_DEPLOY.md`.
- Updated GPU next steps at `docs/NEXT_STEPS_ON_GPU.md`.
- Updated Phase 1 gap notes at `docs/PHASE1_GAP_ANALYSIS.md`.
- Confirmed local scaffold validation passes with the bundled Codex Python runtime.
- Confirmed Python syntax compile checks pass for `app`, `src`, `worker`,
  `training`, and `scripts`.

## Current Vast Deployment Status

- No live Vast.ai GPU deployment has been run yet in this chat.
- Next expected action is to rent or open a fresh Vast.ai GPU instance, SSH into it,
  clone this repo under `/workspace`, and run the direct bootstrap script.

## Next Exact Steps On Vast.ai

After connecting to the Vast.ai GPU instance:

```bash
cd /workspace
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
bash scripts/vast_bootstrap_direct.sh
```

When bootstrap finishes:

```bash
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
```

Expected local service URLs on the GPU:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
http://127.0.0.1:8001/v1/models
```

## SSH Tunnel Template

Use the SSH command from Vast.ai and add these forwards:

```bash
ssh -i <path-to-key> -p <port> root@<host> -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

Then open these locally:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8001/v1/models
```

Do not paste private key contents into chat.

## Important Config Notes

- `scripts/vast_bootstrap_direct.sh` creates `.env` from `.env.example` if needed.
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

## Known Follow-Ups After GPU Smoke Test

1. Test `/v1/chat` against the live GPU model.
2. Add optional OpenAI mentor credentials if desired.
3. Add GitHub token and test generated-code save.
4. Add Azure Blob connection string and test backups.
5. Replace demo API key/passcode auth with database-backed credentials.
6. Add real MySQL persistence and Redis worker integration.

## Resume Prompt For A New Chat

```text
Read docs/CODEX_HANDOFF.md and continue the Vast.ai deployment from the current state.
```
