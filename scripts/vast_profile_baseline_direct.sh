#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

PYTHON_BIN="${BIBER_PROFILE_BASELINE_PYTHON:-${VENV_DIR}/bin/python}"
[ -x "$PYTHON_BIN" ] || die "Python not found at ${PYTHON_BIN}. Run scripts/vast_bootstrap_direct.sh first."

BASELINE_ID="${BIBER_PROFILE_BASELINE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
ARTIFACT_DIR="${BIBER_PROFILE_BASELINE_ARTIFACT_DIR:-${BIBER_RUNTIME_ROOT}/outputs/profile-baseline-${BASELINE_ID}}"
BROAD_SUMMARY="${ARTIFACT_DIR}/biber-dev-core-lora-profiled.summary.json"
BROAD_JSONL="${ARTIFACT_DIR}/biber-dev-core-lora-profiled.jsonl"
RUST_SUMMARY="${ARTIFACT_DIR}/biber-dev-core-rust-xriq-profiled.summary.json"
RUST_JSONL="${ARTIFACT_DIR}/biber-dev-core-rust-xriq-profiled.jsonl"
RUNTIME_SMOKE_DIR="${ARTIFACT_DIR}/runtime-profile-smoke"
SUMMARY_JSON="${ARTIFACT_DIR}/profile-baseline.summary.json"

mkdir -p "$ARTIFACT_DIR"

log "Running stable BIBER profile baseline"
echo "Artifact directory: ${ARTIFACT_DIR}"
echo "This script does not train, reload a candidate adapter, or promote an adapter."

bash "${SCRIPT_DIR}/vast_status_direct.sh"

BIBER_RUNTIME_PROFILE_SMOKE_ARTIFACT_DIR="$RUNTIME_SMOKE_DIR" \
BIBER_RUNTIME_PROFILE_SMOKE_CHAT_MAX_TOKENS="${BIBER_PROFILE_BASELINE_CHAT_MAX_TOKENS:-120}" \
BIBER_RUNTIME_PROFILE_SMOKE_SESSION_MAX_TOKENS="${BIBER_PROFILE_BASELINE_SESSION_MAX_TOKENS:-60}" \
  bash "${SCRIPT_DIR}/vast_runtime_profile_smoke.sh"

BIBER_EVAL_OUTPUT_JSONL="$BROAD_JSONL" \
BIBER_EVAL_SUMMARY_JSON="$BROAD_SUMMARY" \
BIBER_EVAL_PROMPT_PREFIX="${BIBER_PROFILE_BASELINE_BROAD_PROMPT_PREFIX:-training/api_error_response_profile.txt}" \
BIBER_EVAL_PROMPT_PREFIX_IDS="${BIBER_PROFILE_BASELINE_BROAD_PROMPT_PREFIX_IDS:-api_error_shape,api_missing_key_error_shape,api_rate_limit_error_shape}" \
  bash "${SCRIPT_DIR}/vast_eval_lora_direct.sh"

BIBER_EVAL_OUTPUT_JSONL="$RUST_JSONL" \
BIBER_EVAL_SUMMARY_JSON="$RUST_SUMMARY" \
BIBER_EVAL_FAIL_ON_VALIDATORS="${BIBER_PROFILE_BASELINE_FAIL_ON_VALIDATORS:-1}" \
  bash "${SCRIPT_DIR}/vast_eval_rust_xriq_direct.sh"

"$PYTHON_BIN" - "$ARTIFACT_DIR" "$RUNTIME_SMOKE_DIR" "$BROAD_SUMMARY" "$RUST_SUMMARY" "$SUMMARY_JSON" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


artifact_dir = Path(sys.argv[1])
runtime_smoke_dir = Path(sys.argv[2])
broad_summary_path = Path(sys.argv[3])
rust_summary_path = Path(sys.argv[4])
summary_path = Path(sys.argv[5])


def load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} did not contain a JSON object")
    return payload


broad = load(broad_summary_path)
rust = load(rust_summary_path)
summary = {
    "source": "biber_stable_profile_baseline",
    "artifact_dir": str(artifact_dir),
    "runtime_profile_smoke_dir": str(runtime_smoke_dir),
    "broad_summary": str(broad_summary_path),
    "rust_xriq_summary": str(rust_summary_path),
    "broad_ok": broad.get("failed") == 0 and broad.get("expectation_failed") == 0,
    "broad_responses": broad.get("ok"),
    "broad_expectation_ok": broad.get("expectation_ok"),
    "broad_expectation_failed": broad.get("expectation_failed"),
    "rust_xriq_ok": (
        rust.get("failed") == 0
        and rust.get("expectation_failed") == 0
        and rust.get("validation_failed") == 0
    ),
    "rust_xriq_responses": rust.get("ok"),
    "rust_xriq_expectation_ok": rust.get("expectation_ok"),
    "rust_xriq_validation_ok": rust.get("validation_ok"),
    "rust_xriq_validation_failed": rust.get("validation_failed"),
    "training_started": False,
    "candidate_reloaded": False,
    "adapter_promoted": False,
}
summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, sort_keys=True))

if summary["broad_ok"] is not True:
    raise SystemExit("broad profile baseline failed")
if summary["rust_xriq_ok"] is not True:
    raise SystemExit("Rust/XRIQ profile baseline failed")
PY

echo
echo "Profile baseline artifacts:"
echo "  ${RUNTIME_SMOKE_DIR}"
echo "  ${BROAD_SUMMARY}"
echo "  ${RUST_SUMMARY}"
echo "  ${SUMMARY_JSON}"
