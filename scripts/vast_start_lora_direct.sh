#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ADAPTER_DIR="${BIBER_LORA_ADAPTER_DIR:-/workspace/adapters/biber-dev-core-lora-codeinstruct-998}"
LORA_MODEL_NAME="${BIBER_LORA_MODEL_NAME:-biber-dev-core}"
BASE_SERVED_MODEL_NAME="${BIBER_VLLM_BASE_MODEL_NAME:-biber-dev-core-base}"

[ -d "$ADAPTER_DIR" ] || {
  echo "LoRA adapter not found: ${ADAPTER_DIR}" >&2
  exit 1
}

export BIBER_LOCAL_MODEL_NAME="$LORA_MODEL_NAME"
export BIBER_VLLM_SERVED_MODEL_NAME="$BASE_SERVED_MODEL_NAME"
export BIBER_VLLM_LORA_MODULES="${LORA_MODEL_NAME}=${ADAPTER_DIR}"

exec bash "${SCRIPT_DIR}/vast_start_direct.sh"
