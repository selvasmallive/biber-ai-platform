#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

[ -x "${VENV_DIR}/bin/python" ] || die "Virtualenv not found at ${VENV_DIR}. Run scripts/vast_bootstrap_direct.sh first."

export CARGO_HOME="${CARGO_HOME:-${BIBER_RUNTIME_ROOT}/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-${BIBER_RUNTIME_ROOT}/.rustup}"
export PATH="${CARGO_HOME}/bin:${PATH}"

PROMPTS="${BIBER_RUST_XRIQ_EVAL_PROMPTS:-training/eval_prompts_rust_xriq.jsonl}"
EVAL_OUTPUT_DIR="${BIBER_EVAL_OUTPUT_DIR:-${BIBER_RUNTIME_ROOT}/outputs/evals}"
VALIDATOR_WORK_DIR="${BIBER_EVAL_VALIDATOR_WORK_DIR:-${EVAL_OUTPUT_DIR}/validator-work}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_JSONL="${BIBER_EVAL_OUTPUT_JSONL:-${EVAL_OUTPUT_DIR}/biber-dev-core-rust-xriq-${TIMESTAMP}.jsonl}"
SUMMARY_JSON="${BIBER_EVAL_SUMMARY_JSON:-${EVAL_OUTPUT_DIR}/biber-dev-core-rust-xriq-${TIMESTAMP}.summary.json}"
API_KEY="${BIBER_TEST_API_KEY:-$(read_env_value BIBER_DEMO_API_KEY)}"

if [ -z "$API_KEY" ]; then
  API_KEY="dev-api-key-change-me"
fi

mkdir -p "$EVAL_OUTPUT_DIR" "$VALIDATOR_WORK_DIR"

FAIL_VALIDATORS_ARGS=()
if [ "${BIBER_EVAL_FAIL_ON_VALIDATORS:-1}" != "0" ]; then
  FAIL_VALIDATORS_ARGS+=(--fail-on-failed-validators)
fi

log "Running Rust/XRIQ live BIBER eval with cargo validators"
"${VENV_DIR}/bin/python" training/live_model_eval.py \
  --prompts "$PROMPTS" \
  --base-url "http://127.0.0.1:${BIBER_API_PORT}" \
  --api-key "$API_KEY" \
  --output "$OUTPUT_JSONL" \
  --summary "$SUMMARY_JSON" \
  --run-code-validators \
  --validator-work-dir "$VALIDATOR_WORK_DIR" \
  --validator-timeout-seconds "${BIBER_EVAL_VALIDATOR_TIMEOUT_SECONDS:-45}" \
  "${FAIL_VALIDATORS_ARGS[@]}" \
  ${BIBER_EVAL_EXTRA_ARGS:-}

echo
echo "Rust/XRIQ eval artifacts:"
echo "  ${OUTPUT_JSONL}"
echo "  ${SUMMARY_JSON}"
