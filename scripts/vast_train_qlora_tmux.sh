#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SESSION="${BIBER_TRAIN_SESSION:-biber-qlora}"
DATASET="${1:-${BIBER_TRAIN_DATASET:-/workspace/data/biber_train.jsonl}}"
BASE_MODEL="${BIBER_TRAIN_BASE_MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"
OUTPUT_DIR="${BIBER_TRAIN_OUTPUT_DIR:-/workspace/adapters/biber-dev-core-lora}"
LOG_DIR="${BIBER_TRAIN_LOG_DIR:-/workspace/outputs}"
VENV_PYTHON="${BIBER_TRAIN_PYTHON:-/workspace/biber-venv/bin/python}"

command -v tmux >/dev/null 2>&1 || {
  echo "tmux is required. Install it or run the training command manually." >&2
  exit 1
}

[ -x "$VENV_PYTHON" ] || {
  echo "Python not found at ${VENV_PYTHON}. Run scripts/vast_bootstrap_direct.sh first." >&2
  exit 1
}

[ -f "$DATASET" ] || {
  echo "Dataset not found: ${DATASET}" >&2
  echo "Put the real JSONL dataset under /workspace/data on the 500 GB volume." >&2
  exit 1
}

mkdir -p /workspace/data /workspace/checkpoints /workspace/adapters "$LOG_DIR"

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session already exists: ${SESSION}" >&2
  echo "Attach with: tmux attach -t ${SESSION}" >&2
  exit 1
fi

LOG_FILE="${LOG_DIR}/qlora-$(date -u +%Y%m%dT%H%M%SZ).log"

cat <<EOF
Starting QLoRA training in tmux.

Session: ${SESSION}
Dataset: ${DATASET}
Base model: ${BASE_MODEL}
Output: ${OUTPUT_DIR}
Log: ${LOG_FILE}

Attach: tmux attach -t ${SESSION}
Detach: Ctrl-b then d

If GPU memory is tight, stop serving first:
  cd ${REPO_ROOT}
  bash scripts/vast_stop_direct.sh
EOF

tmux new-session -d -s "$SESSION" "
  set -euo pipefail
  cd '${REPO_ROOT}'
  '${VENV_PYTHON}' training/validate_dataset.py --dataset '${DATASET}' --min-records 1
  '${VENV_PYTHON}' training/qlora_train_biber_dev_core.py \
    --base-model '${BASE_MODEL}' \
    --dataset '${DATASET}' \
    --output-dir '${OUTPUT_DIR}' \
    --logging-dir '${LOG_DIR}/qlora-logs' \
    --gradient-checkpointing \
    2>&1 | tee '${LOG_FILE}'
"
