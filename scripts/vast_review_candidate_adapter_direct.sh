#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

[ -x "${VENV_DIR}/bin/python" ] || die "Virtualenv not found at ${VENV_DIR}. Run scripts/vast_bootstrap_direct.sh first."

CANDIDATE_ADAPTER="${BIBER_CANDIDATE_ADAPTER_DIR:-}"
STABLE_ADAPTER="${BIBER_STABLE_ADAPTER_DIR:-/workspace/adapters/biber-dev-core-lora-rust-xriq-400}"
TRAINING_REVIEW_JSON="${BIBER_TRAINING_REVIEW_JSON:-}"
REPO_EVAL_PROMPTS="${BIBER_REPO_EVAL_PROMPTS:-}"
EVAL_OUTPUT_DIR="${BIBER_EVAL_OUTPUT_DIR:-${BIBER_RUNTIME_ROOT}/outputs/evals}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
SESSION="${BIBER_CANDIDATE_EVAL_SESSION:-candidate-adapter-${TIMESTAMP}}"
SESSION_DIR="${BIBER_CANDIDATE_EVAL_DIR:-${EVAL_OUTPUT_DIR}/${SESSION}}"
DRY_RUN="${BIBER_CANDIDATE_EVAL_DRY_RUN:-0}"
RESTORE_STABLE="${BIBER_RESTORE_STABLE_AFTER_EVAL:-1}"
ALLOW_STABLE_AS_CANDIDATE="${BIBER_ALLOW_STABLE_AS_CANDIDATE:-0}"

BASELINE_REPO_SUMMARY="${BIBER_BASELINE_REPO_SUMMARY:-${SESSION_DIR}/stable-repo-heldout.summary.json}"
BASELINE_REPO_OUTPUT="${BIBER_BASELINE_REPO_OUTPUT:-${SESSION_DIR}/stable-repo-heldout.jsonl}"
BASELINE_REPO_FAILURES="${BIBER_BASELINE_REPO_FAILURES:-${SESSION_DIR}/stable-repo-heldout.failures.jsonl}"
CANDIDATE_BROAD_SUMMARY="${BIBER_CANDIDATE_BROAD_SUMMARY:-${SESSION_DIR}/candidate-broad.summary.json}"
CANDIDATE_BROAD_OUTPUT="${BIBER_CANDIDATE_BROAD_OUTPUT:-${SESSION_DIR}/candidate-broad.jsonl}"
CANDIDATE_RUST_SUMMARY="${BIBER_CANDIDATE_RUST_SUMMARY:-${SESSION_DIR}/candidate-rust-xriq.summary.json}"
CANDIDATE_RUST_OUTPUT="${BIBER_CANDIDATE_RUST_OUTPUT:-${SESSION_DIR}/candidate-rust-xriq.jsonl}"
CANDIDATE_REPO_SUMMARY="${BIBER_CANDIDATE_REPO_SUMMARY:-${SESSION_DIR}/candidate-repo-heldout.summary.json}"
CANDIDATE_REPO_OUTPUT="${BIBER_CANDIDATE_REPO_OUTPUT:-${SESSION_DIR}/candidate-repo-heldout.jsonl}"
CANDIDATE_REPO_FAILURES="${BIBER_CANDIDATE_REPO_FAILURES:-${SESSION_DIR}/candidate-repo-heldout.failures.jsonl}"
PROMOTION_REVIEW_JSON="${BIBER_PROMOTION_REVIEW_JSON:-${SESSION_DIR}/candidate-promotion-review.json}"

latest_file() {
  local dir="$1"
  local pattern="$2"
  find "$dir" -maxdepth 1 -type f -name "$pattern" -printf '%T@\t%p\n' 2>/dev/null \
    | sort -n \
    | tail -n 1 \
    | cut -f2-
}

canonical_path() {
  local path="$1"
  if command -v readlink >/dev/null 2>&1; then
    readlink -f "$path"
    return
  fi
  local dir
  dir="$(cd "$(dirname "$path")" && pwd -P)"
  printf '%s/%s\n' "$dir" "$(basename "$path")"
}

run_step() {
  echo
  echo "+ $*"
  if [ "$DRY_RUN" = "1" ]; then
    return 0
  fi
  "$@"
}

run_may_fail() {
  echo
  echo "+ $*"
  if [ "$DRY_RUN" = "1" ]; then
    return 0
  fi
  set +e
  "$@"
  local code=$?
  set -e
  if [ "$code" -ne 0 ]; then
    warn "Command exited ${code}; continuing so promotion review can record blockers."
  fi
  return "$code"
}

restore_stable_adapter() {
  if [ "$RESTORE_STABLE" != "1" ] || [ "$DRY_RUN" = "1" ]; then
    return 0
  fi
  if [ -d "$STABLE_ADAPTER" ]; then
    echo
    echo "Restoring stable adapter: ${STABLE_ADAPTER}"
    bash "${SCRIPT_DIR}/vast_stop_direct.sh" || true
    BIBER_LORA_ADAPTER_DIR="$STABLE_ADAPTER" bash "${SCRIPT_DIR}/vast_start_lora_direct.sh" || true
  fi
}

start_adapter() {
  local adapter_dir="$1"
  run_step bash "${SCRIPT_DIR}/vast_stop_direct.sh"
  run_step env BIBER_LORA_ADAPTER_DIR="$adapter_dir" bash "${SCRIPT_DIR}/vast_start_lora_direct.sh"
}

[ -n "$CANDIDATE_ADAPTER" ] || die "Set BIBER_CANDIDATE_ADAPTER_DIR to the candidate LoRA adapter path."
[ -d "$CANDIDATE_ADAPTER" ] || die "Candidate adapter not found: ${CANDIDATE_ADAPTER}"
[ -f "${CANDIDATE_ADAPTER}/adapter_config.json" ] || die "Candidate adapter missing adapter_config.json: ${CANDIDATE_ADAPTER}"
[ -d "$STABLE_ADAPTER" ] || die "Stable adapter not found: ${STABLE_ADAPTER}"

CANDIDATE_ADAPTER_CANONICAL="$(canonical_path "$CANDIDATE_ADAPTER")"
STABLE_ADAPTER_CANONICAL="$(canonical_path "$STABLE_ADAPTER")"
if [ "$CANDIDATE_ADAPTER_CANONICAL" = "$STABLE_ADAPTER_CANONICAL" ]; then
  if [ "$ALLOW_STABLE_AS_CANDIDATE" != "1" ]; then
    die "Candidate adapter matches the stable adapter. Set BIBER_ALLOW_STABLE_AS_CANDIDATE=1 only for an explicit smoke test."
  fi
  warn "Candidate adapter matches stable adapter; continuing only because BIBER_ALLOW_STABLE_AS_CANDIDATE=1."
fi

if [ -z "$TRAINING_REVIEW_JSON" ]; then
  TRAINING_REVIEW_JSON="$(latest_file "$EVAL_OUTPUT_DIR" "repo-adapt-training-review-*.json")"
fi
[ -n "$TRAINING_REVIEW_JSON" ] || die "Set BIBER_TRAINING_REVIEW_JSON or create a repo-adapt-training-review artifact."
[ -f "$TRAINING_REVIEW_JSON" ] || die "Training review artifact not found: ${TRAINING_REVIEW_JSON}"

if [ -z "$REPO_EVAL_PROMPTS" ]; then
  REPO_EVAL_PROMPTS="$(latest_file "${BIBER_RUNTIME_ROOT}/outputs" "repo-adapt-*.prompts.jsonl")"
fi
[ -n "$REPO_EVAL_PROMPTS" ] || die "Set BIBER_REPO_EVAL_PROMPTS to a repo-adaptation held-out prompt JSONL."
[ -f "$REPO_EVAL_PROMPTS" ] || die "Repo eval prompts not found: ${REPO_EVAL_PROMPTS}"

mkdir -p "$SESSION_DIR"

cat <<EOF
Candidate adapter review.

Candidate:       ${CANDIDATE_ADAPTER}
Stable:          ${STABLE_ADAPTER}
Training review: ${TRAINING_REVIEW_JSON}
Repo prompts:    ${REPO_EVAL_PROMPTS}
Session dir:     ${SESSION_DIR}
Dry run:         ${DRY_RUN}
Restore stable:  ${RESTORE_STABLE}
Allow same path: ${ALLOW_STABLE_AS_CANDIDATE}

This script does not train or promote an adapter. It writes a promotion-review
artifact and restores the stable adapter by default.
EOF

trap restore_stable_adapter EXIT

start_adapter "$STABLE_ADAPTER"
run_may_fail bash "${SCRIPT_DIR}/vast_test_direct.sh" || true
run_may_fail "${VENV_DIR}/bin/python" training/repo_adaptation_eval.py \
  --prompts "$REPO_EVAL_PROMPTS" \
  --output "$BASELINE_REPO_OUTPUT" \
  --summary "$BASELINE_REPO_SUMMARY" \
  --failures-output "$BASELINE_REPO_FAILURES" || true

if start_adapter "$CANDIDATE_ADAPTER"; then
  run_may_fail bash "${SCRIPT_DIR}/vast_test_direct.sh" || true
  run_may_fail env \
    BIBER_EVAL_OUTPUT_JSONL="$CANDIDATE_BROAD_OUTPUT" \
    BIBER_EVAL_SUMMARY_JSON="$CANDIDATE_BROAD_SUMMARY" \
    bash "${SCRIPT_DIR}/vast_eval_lora_direct.sh" || true
  run_may_fail env \
    BIBER_EVAL_OUTPUT_JSONL="$CANDIDATE_RUST_OUTPUT" \
    BIBER_EVAL_SUMMARY_JSON="$CANDIDATE_RUST_SUMMARY" \
    BIBER_EVAL_FAIL_ON_VALIDATORS=0 \
    bash "${SCRIPT_DIR}/vast_eval_rust_xriq_direct.sh" || true
  run_may_fail "${VENV_DIR}/bin/python" training/repo_adaptation_eval.py \
    --prompts "$REPO_EVAL_PROMPTS" \
    --output "$CANDIDATE_REPO_OUTPUT" \
    --summary "$CANDIDATE_REPO_SUMMARY" \
    --failures-output "$CANDIDATE_REPO_FAILURES" || true
else
  warn "Candidate adapter failed to start; promotion review will block on missing candidate eval summaries."
fi

run_step "${VENV_DIR}/bin/python" training/adapter_promotion_review.py \
  --candidate-adapter "$CANDIDATE_ADAPTER" \
  --stable-adapter "$STABLE_ADAPTER" \
  --training-review "$TRAINING_REVIEW_JSON" \
  --broad-summary "$CANDIDATE_BROAD_SUMMARY" \
  --rust-summary "$CANDIDATE_RUST_SUMMARY" \
  --repo-summary "$CANDIDATE_REPO_SUMMARY" \
  --baseline-repo-summary "$BASELINE_REPO_SUMMARY" \
  --review-output "$PROMOTION_REVIEW_JSON"

echo
echo "Candidate review artifacts:"
echo "  Stable repo summary:    ${BASELINE_REPO_SUMMARY}"
echo "  Candidate broad summary:${CANDIDATE_BROAD_SUMMARY}"
echo "  Candidate Rust summary: ${CANDIDATE_RUST_SUMMARY}"
echo "  Candidate repo summary: ${CANDIDATE_REPO_SUMMARY}"
echo "  Promotion review:       ${PROMOTION_REVIEW_JSON}"
