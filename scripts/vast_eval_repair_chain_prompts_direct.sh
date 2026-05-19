#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

[ -x "${VENV_DIR}/bin/python" ] || die "Virtualenv not found at ${VENV_DIR}. Run scripts/vast_bootstrap_direct.sh first."

find_latest_repair_chain_eval_prompts() {
  local search_root="${BIBER_REPAIR_CHAIN_EVAL_SEARCH_ROOT:-${BIBER_RUNTIME_ROOT}/outputs}"
  [ -d "$search_root" ] || return 0
  find "$search_root" -type f -name 'agent-client-mvp-loop-ready-repair-chain-eval-prompts.jsonl' \
    -printf '%T@\t%p\n' 2>/dev/null \
    | sort -nr \
    | awk -F '\t' 'NR == 1 { print $2 }'
}

PROMPTS="${BIBER_REPAIR_CHAIN_EVAL_PROMPTS:-}"
if [ -z "$PROMPTS" ]; then
  PROMPTS="$(find_latest_repair_chain_eval_prompts)"
fi
[ -n "$PROMPTS" ] || die "No repair-chain eval prompt JSONL found. Run scripts/vast_biber_agent_smoke.sh first, or set BIBER_REPAIR_CHAIN_EVAL_PROMPTS."
[ -f "$PROMPTS" ] || die "Repair-chain eval prompts not found: ${PROMPTS}."

EVAL_OUTPUT_DIR="${BIBER_REPAIR_CHAIN_EVAL_OUTPUT_DIR:-${BIBER_RUNTIME_ROOT}/outputs/evals}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_JSONL="${BIBER_REPAIR_CHAIN_EVAL_OUTPUT_JSONL:-${EVAL_OUTPUT_DIR}/biber-repair-chain-heldout-${TIMESTAMP}.jsonl}"
SUMMARY_JSON="${BIBER_REPAIR_CHAIN_EVAL_SUMMARY_JSON:-${EVAL_OUTPUT_DIR}/biber-repair-chain-heldout-${TIMESTAMP}.summary.json}"
API_KEY="${BIBER_TEST_API_KEY:-$(read_env_value BIBER_DEMO_API_KEY)}"

if [ -z "$API_KEY" ]; then
  API_KEY="dev-api-key-change-me"
fi

mkdir -p "$EVAL_OUTPUT_DIR"

FAIL_EXPECTATIONS_ARGS=()
if [ "${BIBER_REPAIR_CHAIN_EVAL_FAIL_ON_EXPECTATIONS:-1}" != "0" ]; then
  FAIL_EXPECTATIONS_ARGS+=(--fail-on-failed-expectations)
fi

log "Running repair-chain held-out live BIBER eval"
"${VENV_DIR}/bin/python" training/live_model_eval.py \
  --prompts "$PROMPTS" \
  --base-url "http://127.0.0.1:${BIBER_API_PORT}" \
  --api-key "$API_KEY" \
  --output "$OUTPUT_JSONL" \
  --summary "$SUMMARY_JSON" \
  "${FAIL_EXPECTATIONS_ARGS[@]}" \
  ${BIBER_REPAIR_CHAIN_EVAL_EXTRA_ARGS:-}

echo
echo "Repair-chain held-out eval prompts:"
echo "  ${PROMPTS}"
echo "Repair-chain held-out eval artifacts:"
echo "  ${OUTPUT_JSONL}"
echo "  ${SUMMARY_JSON}"
