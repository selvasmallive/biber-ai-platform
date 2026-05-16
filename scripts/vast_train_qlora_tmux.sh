#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

SESSION="${BIBER_TRAIN_SESSION:-biber-qlora}"
DATASET="${1:-${BIBER_TRAIN_DATASET:-/workspace/data/biber_train.jsonl}}"
BASE_MODEL="${BIBER_TRAIN_BASE_MODEL:-Qwen/Qwen2.5-Coder-7B-Instruct}"
OUTPUT_DIR="${BIBER_TRAIN_OUTPUT_DIR:-/workspace/adapters/biber-dev-core-lora}"
LOG_DIR="${BIBER_TRAIN_LOG_DIR:-/workspace/outputs}"
VENV_PYTHON="${BIBER_TRAIN_PYTHON:-/workspace/biber-venv/bin/python}"
MIN_RECORDS="${BIBER_TRAIN_MIN_RECORDS:-1}"
MAX_STEPS="${BIBER_TRAIN_MAX_STEPS:-}"
LIMIT_SAMPLES="${BIBER_TRAIN_LIMIT_SAMPLES:-}"
NUM_EPOCHS="${BIBER_TRAIN_NUM_EPOCHS:-}"
MAX_SEQ_LENGTH="${BIBER_TRAIN_MAX_SEQ_LENGTH:-}"
SAVE_STEPS="${BIBER_TRAIN_SAVE_STEPS:-}"
LOGGING_STEPS="${BIBER_TRAIN_LOGGING_STEPS:-}"
SESSION_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

quote() {
  printf '%q' "$1"
}

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

LOG_FILE="${LOG_DIR}/qlora-${SESSION_TIMESTAMP}.log"
RUN_SCRIPT="${LOG_DIR}/qlora-${SESSION_TIMESTAMP}.sh"

TRAIN_ARGS=(
  --base-model "$BASE_MODEL"
  --dataset "$DATASET"
  --output-dir "$OUTPUT_DIR"
  --logging-dir "${LOG_DIR}/qlora-logs"
  --gradient-checkpointing
)

[ -n "$MAX_STEPS" ] && TRAIN_ARGS+=(--max-steps "$MAX_STEPS")
[ -n "$LIMIT_SAMPLES" ] && TRAIN_ARGS+=(--limit-samples "$LIMIT_SAMPLES")
[ -n "$NUM_EPOCHS" ] && TRAIN_ARGS+=(--num-train-epochs "$NUM_EPOCHS")
[ -n "$MAX_SEQ_LENGTH" ] && TRAIN_ARGS+=(--max-seq-length "$MAX_SEQ_LENGTH")
[ -n "$SAVE_STEPS" ] && TRAIN_ARGS+=(--save-steps "$SAVE_STEPS")
[ -n "$LOGGING_STEPS" ] && TRAIN_ARGS+=(--logging-steps "$LOGGING_STEPS")

printf -v TRAIN_ARGS_Q ' %q' "${TRAIN_ARGS[@]}"

cat > "$RUN_SCRIPT" <<EOF
#!/usr/bin/env bash
set -euo pipefail
export HF_HOME=$(quote "$HF_HOME")
export PIP_CACHE_DIR=$(quote "$PIP_CACHE_DIR")
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-0}"
cd $(quote "$REPO_ROOT")
$(quote "$VENV_PYTHON") training/validate_dataset.py \
  --dataset $(quote "$DATASET") \
  --min-records $(quote "$MIN_RECORDS")
$(quote "$VENV_PYTHON") training/qlora_train_biber_dev_core.py${TRAIN_ARGS_Q} \
  2>&1 | tee $(quote "$LOG_FILE")
EOF
chmod +x "$RUN_SCRIPT"

cat <<EOF
Starting QLoRA training in tmux.

Session: ${SESSION}
Dataset: ${DATASET}
Base model: ${BASE_MODEL}
Output: ${OUTPUT_DIR}
Log: ${LOG_FILE}
Run script: ${RUN_SCRIPT}
HF cache: ${HF_HOME}
Pip cache: ${PIP_CACHE_DIR}

Attach: tmux attach -t ${SESSION}
Detach: Ctrl-b then d

If GPU memory is tight, stop serving first:
  cd ${REPO_ROOT}
  bash scripts/vast_stop_direct.sh
EOF

tmux new-session -d -s "$SESSION" "bash $(quote "$RUN_SCRIPT")"
