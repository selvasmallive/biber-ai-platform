# Resume BIBER From A Fresh GPU/Volume

Use this file when the old Vast.ai instance and its 500 GB volume have been
terminated.

## Resume Prompt For Future Codex

Copy this prompt into the next Codex session:

```text
Read readme-resume-biber.md and docs/CODEX_HANDOFF.md. Resume BIBER from the
current GitHub main branch on a brand-new GPU/volume. Do not assume any old
/workspace runtime artifacts exist. Keep OpenAI/Codex usage minimal. Do not
rotate credentials. Do not start training unless I explicitly approve it.
Current near-term priority is XRIQ private-devnet prototype first, while keeping
BIBER MVP stable.
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

The current XRIQ-only next step from the handoff is to add an isolated full
transfer runbook smoke that uses a fresh devnet chain file so repeated tests do
not consume the live Alice balance.

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

Do not run QLoRA or any training command from a generic "continue" request.
Training requires separate explicit user approval.

## Cost-Control Rules

- Prefer XRIQ Rust/CPU work while the GPU is offline.
- Use Codex for narrow patches, review, integration, and handoff updates.
- Use local deterministic tests and scripts for verification.
- Use OpenAI mentor only if the user explicitly requests it or the handoff says
  risk justifies it.
- Keep public XRIQ, DEX, tokenomics, production security audits, listings, and
  launch claims out of scope until the private-devnet prototype is complete.
