#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

[ -x "${VENV_DIR}/bin/python" ] || die "Virtualenv not found at ${VENV_DIR}. Run scripts/vast_bootstrap_direct.sh first."

PROMPTS="${BIBER_EVAL_PROMPTS:-training/eval_prompts.jsonl}"
PROMPT_PREFIX="${BIBER_EVAL_PROMPT_PREFIX:-}"
PROMPT_PREFIX_IDS="${BIBER_EVAL_PROMPT_PREFIX_IDS:-}"
EVAL_OUTPUT_DIR="${BIBER_EVAL_OUTPUT_DIR:-${BIBER_RUNTIME_ROOT}/outputs/evals}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_JSONL="${BIBER_EVAL_OUTPUT_JSONL:-${EVAL_OUTPUT_DIR}/biber-dev-core-lora-${TIMESTAMP}.jsonl}"
SUMMARY_JSON="${BIBER_EVAL_SUMMARY_JSON:-${EVAL_OUTPUT_DIR}/biber-dev-core-lora-${TIMESTAMP}.summary.json}"
API_KEY="${BIBER_TEST_API_KEY:-$(read_env_value BIBER_DEMO_API_KEY)}"

if [ -z "$API_KEY" ]; then
  API_KEY="dev-api-key-change-me"
fi

mkdir -p "$EVAL_OUTPUT_DIR"

PROMPT_PREFIX_ARGS=()
if [ -n "$PROMPT_PREFIX" ]; then
  PROMPT_PREFIX_ARGS+=(--prompt-prefix-file "$PROMPT_PREFIX")
  if [ -n "$PROMPT_PREFIX_IDS" ]; then
    for prompt_id in ${PROMPT_PREFIX_IDS//,/ }; do
      PROMPT_PREFIX_ARGS+=(--prompt-prefix-id "$prompt_id")
    done
  fi
fi

log "Running live BIBER LoRA eval"
"${VENV_DIR}/bin/python" training/live_model_eval.py \
  --prompts "$PROMPTS" \
  "${PROMPT_PREFIX_ARGS[@]}" \
  --base-url "http://127.0.0.1:${BIBER_API_PORT}" \
  --api-key "$API_KEY" \
  --output "$OUTPUT_JSONL" \
  --summary "$SUMMARY_JSON" \
  ${BIBER_EVAL_EXTRA_ARGS:-}

echo
echo "Eval artifacts:"
echo "  ${OUTPUT_JSONL}"
echo "  ${SUMMARY_JSON}"
