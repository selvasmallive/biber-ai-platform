#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

MANIFEST="${BIBER_INGEST_MANIFEST:-${REPO_ROOT}/training/approved_sources.json}"
OUTPUT="${1:-${BIBER_INGEST_OUTPUT:-/workspace/data/biber_train_internet.jsonl}}"
RAW_DIR="${BIBER_INGEST_RAW_DIR:-/workspace/data/raw}"
PROVENANCE="${BIBER_INGEST_PROVENANCE:-/workspace/outputs/dataset-provenance.json}"
VALIDATION_REPORT="${BIBER_INGEST_VALIDATION_REPORT:-}"
MAX_RECORDS="${BIBER_INGEST_MAX_RECORDS:-1000}"
MIN_RECORDS="${BIBER_INGEST_MIN_RECORDS:-1}"
VENV_PYTHON="${BIBER_INGEST_PYTHON:-/workspace/biber-venv/bin/python}"

if [ -z "$VALIDATION_REPORT" ]; then
  VALIDATION_REPORT="/workspace/outputs/internet-dataset-validation.json"
fi

[ -x "$VENV_PYTHON" ] || {
  echo "Python not found at ${VENV_PYTHON}. Run scripts/vast_bootstrap_direct.sh first." >&2
  exit 1
}

mkdir -p /workspace/data /workspace/data/raw /workspace/outputs

cd "$REPO_ROOT"

"$VENV_PYTHON" training/internet_ingest.py \
  --manifest "$MANIFEST" \
  --output "$OUTPUT" \
  --raw-dir "$RAW_DIR" \
  --provenance "$PROVENANCE" \
  --max-records "$MAX_RECORDS" \
  --min-records "$MIN_RECORDS"

"$VENV_PYTHON" training/validate_dataset.py \
  --dataset "$OUTPUT" \
  --min-records "$MIN_RECORDS" \
  --report "$VALIDATION_REPORT"

cat <<EOF
Internet dataset is ready.

Output:     ${OUTPUT}
Raw dir:    ${RAW_DIR}
Provenance: ${PROVENANCE}
Validation: ${VALIDATION_REPORT}

For a long run, start this script inside tmux:
  tmux new -s biber-ingest -- bash scripts/vast_ingest_internet_dataset.sh ${OUTPUT}
EOF
