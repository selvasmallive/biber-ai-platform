# Resume BIBER From A Fresh GPU/Volume

Use this file when the old Vast.ai instance and its 500 GB volume have been
terminated.

## Resume Prompt For Future Codex

Copy this prompt into the next Codex session:

```text
Read readme-resume-biber.md and docs/CODEX_HANDOFF.md. Resume BIBER from the
current GitHub main branch on a brand-new GPU/volume. Do not assume any old
/workspace runtime artifacts exist. Keep OpenAI/Codex usage minimal. Do not
rotate credentials. Keep OpenAI mentor optional and disabled by default.
Current near-term priority is BIBER MVP only: swappable model providers, repo
context, safe file edits, test execution/diagnosis, GitHub save/PR workflow,
and the BIBER agent client flow. XRIQ work is now a separate XRIS-Coin project;
do not continue XRIQ from this repo unless I explicitly ask for it. Use GPU or
training only when a concrete BIBER eval/training need exists and current GPU
runtime access is available.
```

## What GitHub Preserves

The GitHub repo preserves the source and rebuild instructions:

- BIBER API/application code.
- XRIQ Rust private-devnet code and fixtures.
- Training/eval scripts and small checked datasets under `training/`.
- Vast deploy scripts under `scripts/`.
- Handoff and roadmap docs under `docs/`.
- XRIQ runbook in `xriq/README.md`.

Primary files to read first:

1. `docs/CODEX_HANDOFF.md`
2. `readme-resume-biber.md`
3. `readme-reinstantiate.md` if local runtime artifacts were backed up and
   should be uploaded to a new GPU/volume.
4. `README.md`
5. `docs/VAST_DIRECT_DEPLOY.md`
6. `xriq/README.md`

## What Is Not Preserved If The Vast Volume Is Destroyed

The following runtime artifacts were present on Vast before shutdown planning,
but are not suitable for committing to the normal GitHub repo:

```text
/workspace/adapters      about 8.6 GB
/workspace/.hf_home      about 15 GB
/workspace/outputs       about 31 MB
/workspace/biber-logs    about 156 KB
```

Important adapter path last served by the live Vast API:

```text
/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z
```

Why these are not committed to normal GitHub:

- Model caches and LoRA adapters are large binary artifacts.
- Hugging Face cache files can be redownloaded.
- Logs and outputs are generated artifacts.
- Runtime outputs may contain prompts, traces, local paths, or other material
  that should be reviewed before publication.
- `.env`, tokens, SSH keys, and credentials must never be committed.

If the exact LoRA adapter weights must be preserved, do not terminate the volume
until they are uploaded to an explicit artifact store such as Azure Blob,
Hugging Face, GitHub Release/LFS, or another approved storage location. If the
volume is destroyed first, resume from the base model and regenerate/retrain
adapters later from the tracked scripts/datasets and approved review artifacts.

## Fresh GPU Bootstrap

On a brand-new Vast.ai GPU/volume:

```bash
cd /workspace
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
git checkout main
cp .env.example .env
```

Edit `.env` with current credentials/API keys. Do not paste secrets into Codex
chat or commit `.env`.

Bootstrap the direct no-Docker Vast path:

```bash
bash scripts/vast_bootstrap_direct.sh
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
```

If the old LoRA adapter was not preserved, start with the base model path first.
Only use `scripts/vast_start_lora_direct.sh` after an adapter exists again.

## XRIQ Private-Devnet Resume

XRIQ private-devnet does not require a GPU. It can be developed and tested with
Rust/CPU:

```bash
cd /workspace/biber-ai-platform
python scripts/xriq_private_devnet_transfer_smoke.py
python scripts/xriq_private_devnet_http_smoke.py
cd xriq
cargo test
cd ..
bash scripts/xriq_private_devnet_smoke.sh
```

When the BIBER API is running, the API/client smoke path is:

```bash
bash scripts/vast_xriq_api_smoke.sh
python scripts/biber_xriq_private_devnet_client.py overview
python scripts/biber_xriq_private_devnet_client.py status
python scripts/biber_xriq_private_devnet_client.py account xriqdev1alice00000000000
python scripts/biber_xriq_private_devnet_client.py mempool
```

The isolated transfer smoke creates a fresh artifact directory under
`xriq/target/`, performs one private-devnet transfer, verifies transaction,
block, account, and snapshot import state, and avoids consuming any restored
BIBER API chain balance.

The local HTTP smoke starts a real `xriq-node serve-private` process on a
temporary localhost port, submits a wallet transfer through `POST /v1/mempool`,
restarts the server to prove durable pending state survives, produces a block
with `POST /v1/blocks`, and verifies transaction, block, account, mempool, and
overview endpoints, including the latest transaction-list endpoint. It also
exports a snapshot through local HTTP, starts a fresh local server against new
chain/pending files, imports that snapshot, and verifies the imported
transaction.

## BIBER Model Resume

On a fresh volume, expect to rebuild or redownload:

- Python virtualenv at `/workspace/biber-venv`.
- Hugging Face model cache at `/workspace/.hf_home`.
- vLLM runtime cache/kernels.
- Optional LoRA adapters under `/workspace/adapters`.
- Generated eval and smoke artifacts under `/workspace/outputs`.

The base local coding model can be restored by running the Vast bootstrap/start
scripts. Repo-adapted LoRA behavior is not available unless adapter artifacts
are restored or retrained.

## CPU-Local MVP Loop

Preferred local folder for BIBER-only work:

```text
C:\Users\vselv\OneDrive\Biber\biber-mvp-only
```

That folder is a sparse checkout of the BIBER branch and intentionally excludes
the XRIS-Coin/XRIQ tree. Read `docs/BIBER_ONLY_WORKSPACE.md` there before
continuing BIBER MVP.

Before provisioning a GPU, continue BIBER orchestration work locally. The agent
client can now run the cheap workflow directly against a local repository root
without a live BIBER API:

```bash
python scripts/biber_agent_client.py --json mvp-loop \
  --instruction "Plan or validate a narrow code change." \
  --local-target-root /path/to/repo \
  --changed-path src/example.py \
  --test-id python-compileall-api \
  --test-dry-run \
  --output /tmp/biber-mvp-loop.json
```

With `--local-target-root`, context selection, edit planning/apply, test
execution, and diagnosis use local source code. GitHub save and PR creation
still require the BIBER API because those are server-backed integrations.

Do not run QLoRA or any training command just because a session says
"continue." Training is appropriate only after the BIBER eval/review pipeline
shows a concrete repeatable model gap, the reviewed dataset is ready, and a
current GPU runtime is available. Keep source-level BIBER orchestration work
CPU/local-first until training is actually needed.

## When Vast GPU Credentials Are Needed

Do not collect or paste Vast credentials for routine BIBER source work. They are
needed only when a future step explicitly requires one of these:

- start or inspect a live Vast instance
- bootstrap `/workspace/biber-ai-platform`
- run vLLM/local-model inference through the BIBER API
- run batch evals on the GPU
- start a QLoRA/training job
- restore adapters or Hugging Face cache artifacts to a new volume

When that point arrives, collect these details from Vast.ai and provide them to
the session without pasting secret key values into chat:

- instance id
- copied SSH connection command from the instance SSH/connect screen
- SSH private-key path on this workstation, if not the default
- whether the instance has a persistent volume attached
- whether the Vast CLI is already authenticated locally

If CLI automation is required, create a Vast API key in the Vast console Keys
page and store it locally with `vastai set api-key YOUR_API_KEY` or in a local
environment variable. Do not commit it, paste it into docs, or include it in
training data.

## Cost-Control Rules

- Prefer CPU/local BIBER orchestration work while the GPU is offline.
- Use Codex for narrow patches, review, integration, and handoff updates.
- Use local deterministic tests and scripts for verification.
- Use OpenAI mentor only if the user explicitly requests it or the handoff says
  risk justifies it.
- Keep unrelated XRIQ/XRIS-Coin, public chain, DEX, tokenomics, production
  security audits, listings, and launch claims out of BIBER MVP scope unless
  explicitly requested.
