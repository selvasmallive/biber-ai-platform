#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

[ -x "${VENV_DIR}/bin/python" ] || die "Virtualenv not found at ${VENV_DIR}."

DEFAULT_PROMPTS="${BIBER_RUNTIME_ROOT}/outputs/repo-adaptation-eval-prompts.jsonl"
DEFAULT_OUTPUT_DIR="${BIBER_RUNTIME_ROOT}/outputs/evals"
PROMPTS="${BIBER_REPO_ADAPTATION_EVAL_PROMPTS:-$DEFAULT_PROMPTS}"
EVAL_OUTPUT_DIR="${BIBER_REPO_ADAPTATION_EVAL_OUTPUT_DIR:-$DEFAULT_OUTPUT_DIR}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEFAULT_OUTPUT="${EVAL_OUTPUT_DIR}/biber-repo-adaptation-${TIMESTAMP}.jsonl"
DEFAULT_SUMMARY="${EVAL_OUTPUT_DIR}/biber-repo-adaptation-${TIMESTAMP}.summary.json"
DEFAULT_FAILURES="${EVAL_OUTPUT_DIR}/biber-repo-adaptation-${TIMESTAMP}.failures.jsonl"
OUTPUT_JSONL="${BIBER_REPO_ADAPTATION_EVAL_OUTPUT_JSONL:-$DEFAULT_OUTPUT}"
SUMMARY_JSON="${BIBER_REPO_ADAPTATION_EVAL_SUMMARY_JSON:-$DEFAULT_SUMMARY}"
FAILURES_JSONL="${BIBER_REPO_ADAPTATION_EVAL_FAILURES_JSONL:-$DEFAULT_FAILURES}"
API_KEY="${BIBER_TEST_API_KEY:-$(read_env_value BIBER_DEMO_API_KEY)}"

if [ -z "$API_KEY" ]; then
  API_KEY="dev-api-key-change-me"
fi

if [ ! -f "$PROMPTS" ]; then
  die "Repo-adaptation eval prompts not found: ${PROMPTS}."
fi

mkdir -p "$EVAL_OUTPUT_DIR"

EXTRA_ARGS=()
if [ -n "${BIBER_REPO_ADAPTATION_EVAL_LIMIT:-}" ]; then
  EXTRA_ARGS+=(--limit "$BIBER_REPO_ADAPTATION_EVAL_LIMIT")
fi
if [ "${BIBER_REPO_ADAPTATION_EVAL_FAIL_ON_EXPECTATIONS:-0}" != "0" ]; then
  EXTRA_ARGS+=(--fail-on-failed-expectations)
fi

log "Running repo-adaptation live BIBER eval"
"${VENV_DIR}/bin/python" training/repo_adaptation_eval.py \
  --prompts "$PROMPTS" \
  --base-url "http://127.0.0.1:${BIBER_API_PORT}" \
  --api-key "$API_KEY" \
  --output "$OUTPUT_JSONL" \
  --summary "$SUMMARY_JSON" \
  --failures-output "$FAILURES_JSONL" \
  "${EXTRA_ARGS[@]}" \
  ${BIBER_REPO_ADAPTATION_EVAL_EXTRA_ARGS:-}

echo
echo "Repo-adaptation eval artifacts:"
echo "  ${OUTPUT_JSONL}"
echo "  ${SUMMARY_JSON}"
echo "  ${FAILURES_JSONL}"
