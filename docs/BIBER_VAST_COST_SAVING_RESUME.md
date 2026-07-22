# BIBER Vast Cost-Saving Resume Guide

Use this guide for BIBER MVP only. Do not use it for XRIQ/XRIS-Coin work.

## Minimum Practical Vast Profile

The current BIBER stable path defaults to `Qwen/Qwen2.5-Coder-7B-Instruct`
served as `biber-dev-core-v1` when GPU memory allows it. On 16 GB GPUs, use the
3B fallback unless a quantized 7B path is deliberately configured. For the next
live held-out eval and basic inference, choose the cheapest reliable instance
that meets this floor:

```text
GPU: 1x NVIDIA GPU with 16 GB VRAM for 3B fallback, 24 GB+ preferred for 7B
Container disk: 80 GB minimum, 120 GB safer
Persistent volume: 250 GB minimum, 500 GB safer
System RAM: 32 GB minimum, 64 GB safer
CPU: 6-8 vCPU minimum
CUDA: 12.8 or newer preferred
```

Good low-cost choices:

- `1x RTX 5060 Ti 16GB`
- `1x RTX 4060 Ti 16GB`
- another 16 GB NVIDIA GPU with recent CUDA support and good reliability

Treat 16 GB cards as low-cost 3B inference cards for now. The 7B BF16 path can
fail during vLLM initialization on 16 GB because model weights plus compile/KV
memory leave almost no headroom. Avoid 8 GB GPUs unless deliberately switching
to a smaller/quantized model such as a 1.5B coding model. Avoid renting `2x`
GPUs just for the next held-out eval unless the price is close to `1x`; two 16
GB GPUs do not automatically behave like one 32 GB GPU unless serving or
training is configured for multi-GPU parallelism.

## Storage Choices

Use container disk for disposable setup files and use the persistent volume for
runtime state:

```text
/workspace/biber-ai-platform  # Git checkout
/workspace/.hf_home           # Hugging Face model cache
/workspace/adapters           # LoRA/QLoRA adapters
/workspace/outputs            # eval outputs and review artifacts
/workspace/biber-logs         # runtime logs
/workspace/data               # datasets, if any
```

Cost-minimum setup:

```text
Container disk: 80-120 GB
Volume: 250-300 GB
```

Safer setup that reduces rebuild/redownload time:

```text
Container disk: 120-160 GB
Volume: 500 GB
```

Choose `500 GB` if restoring prior `.hf_home`, adapters, datasets, or eval
outputs. Choose `250-300 GB` only if the goal is a short live eval/inference
session and the model cache can be redownloaded later.

## If Switching GPUs Later

Future sessions should continue from GitHub and restore runtime artifacts only
when they are available. The source of truth for code/docs is the current GitHub
branch:

```text
repo: https://github.com/selvasmallive/biber-ai-platform.git
branch: biber/mvp-resume-20260712
```

On a new Vast instance:

```bash
mkdir -p /workspace
cd /workspace
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
git checkout biber/mvp-resume-20260712
git pull --ff-only origin biber/mvp-resume-20260712
```

If a previous volume or backup is available, restore these paths to save time:

```text
/workspace/.hf_home
/workspace/adapters
/workspace/outputs
/workspace/biber-logs
/workspace/biber-ai-platform/.env
```

Do not paste `.env`, private keys, Vast API keys, Hugging Face tokens, or
OpenAI keys into chat or commit them to GitHub.

If no volume/backup is available, rebuild from GitHub:

```bash
cd /workspace/biber-ai-platform
BIBER_START_AFTER_BOOTSTRAP=false bash scripts/vast_bootstrap_direct.sh
bash scripts/vast_start_direct.sh
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
```

If a 16 GB GPU fails the 7B start with CUDA out-of-memory during vLLM/Torch
Inductor initialization, switch to the 3B fallback while keeping the public
served alias stable:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_stop_direct.sh || true
BIBER_HF_MODEL=Qwen/Qwen2.5-Coder-3B-Instruct \
  BIBER_VLLM_SERVED_MODEL_NAME=biber-dev-core \
  BIBER_LOCAL_MODEL_NAME=biber-dev-core \
  BIBER_MAX_MODEL_LEN=4096 \
  bash scripts/vast_start_direct.sh
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
```

For CUDA 12.8 Vast hosts, the bootstrap path intentionally pins the default
vLLM install to a CUDA 12.8-compatible stack:

```text
BIBER_VLLM_PACKAGE=vllm==0.10.2
BIBER_VLLM_PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu128
BIBER_VLLM_TRANSFORMERS_PACKAGE=transformers>=4.55.2,<5.0.0
```

This avoids accidentally installing a newer CUDA 13 PyTorch/vLLM stack that
cannot run on a host driver exposing CUDA 12.8. If that already happened, move
`/workspace/biber-venv` aside and rerun bootstrap after pulling the latest
branch.

If vLLM starts but fails with
`Qwen2Tokenizer has no attribute all_special_tokens_extended`, the runtime has
pulled an incompatible Transformers 5.x tokenizer API. Pull the latest branch
and rerun bootstrap once; it will reinstall the compatible Transformers 4.x
range and restore BIBER API dependency pins before start.

If a restored adapter exists, prefer adapter serving:

```bash
cd /workspace/biber-ai-platform
BIBER_LORA_ADAPTER_DIR=/workspace/adapters/biber-dev-core-repo-adapt-next2-20260522T0950Z \
  bash scripts/vast_start_lora_direct.sh
bash scripts/vast_test_direct.sh
```

If that adapter is missing, use the base model first. Do not start QLoRA or any
training job without a fresh explicit user approval.

## What To Give Codex

When Codex reaches a GPU boundary, provide only connection metadata:

- Vast instance id
- copied SSH command from Vast.ai's SSH/connect screen
- SSH private-key path on the workstation, usually
  `C:\Users\vselv\.ssh\biber_vast_ed25519`
- whether a persistent volume is attached
- whether prior artifacts were restored

Codex should then run the live-provider readiness checks from
`docs/BIBER_LIVE_PROVIDER_RUNBOOK.md`, fast-forward the Git checkout, and only
then run the narrow live eval wrapper:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
bash scripts/vast_eval_repair_chain_prompts_direct.sh
```
