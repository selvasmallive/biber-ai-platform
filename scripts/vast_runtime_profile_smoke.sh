#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

API_KEY="${BIBER_TEST_API_KEY:-$(read_env_file_value BIBER_DEMO_API_KEY)}"
if [ -z "$API_KEY" ]; then
  API_KEY="dev-api-key-change-me"
fi

PYTHON_BIN="${BIBER_RUNTIME_PROFILE_SMOKE_PYTHON:-${VENV_DIR}/bin/python}"
[ -x "$PYTHON_BIN" ] || die "Python not found at ${PYTHON_BIN}. Run scripts/vast_bootstrap_direct.sh first."

API_BASE_URL="${BIBER_RUNTIME_PROFILE_SMOKE_URL:-http://127.0.0.1:${BIBER_API_PORT}}"
SMOKE_ID="${BIBER_RUNTIME_PROFILE_SMOKE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
ARTIFACT_DIR="${BIBER_RUNTIME_PROFILE_SMOKE_ARTIFACT_DIR:-${BIBER_RUNTIME_ROOT}/outputs/runtime-profile-smoke-${SMOKE_ID}}"
CHAT_MAX_TOKENS="${BIBER_RUNTIME_PROFILE_SMOKE_CHAT_MAX_TOKENS:-80}"
SESSION_MAX_TOKENS="${BIBER_RUNTIME_PROFILE_SMOKE_SESSION_MAX_TOKENS:-60}"
TIMEOUT_SECONDS="${BIBER_RUNTIME_PROFILE_SMOKE_TIMEOUT_SECONDS:-180}"

mkdir -p "$ARTIFACT_DIR"
export BIBER_API_KEY="$API_KEY"

CLIENT=(
  "$PYTHON_BIN"
  "${SCRIPT_DIR}/biber_agent_client.py"
  --json
  --base-url "$API_BASE_URL"
  --timeout-seconds "$TIMEOUT_SECONDS"
)

"${CLIENT[@]}" capabilities > "${ARTIFACT_DIR}/capabilities.json"

"${CLIENT[@]}" chat \
  --message "Return only: BIBER_RUNTIME_PROFILE_RUST_OK" \
  --language Rust \
  --task-type xriq_private_devnet_review \
  --runtime-profile-id rust-xriq-codegen \
  --max-tokens "$CHAT_MAX_TOKENS" \
  > "${ARTIFACT_DIR}/rust-chat.json"

"${CLIENT[@]}" create-session \
  --preset xriq_private_devnet_review \
  --instruction "Return one concise sentence that starts with BIBER_RUNTIME_PROFILE_SESSION_OK." \
  --runtime-profile-id rust-xriq-codegen \
  --no-test \
  --max-tokens "$SESSION_MAX_TOKENS" \
  > "${ARTIFACT_DIR}/rust-session.json"

"${CLIENT[@]}" chat \
  --message "Return a JSON example for a missing API key error. Include only JSON." \
  --language Python \
  --task-type api_error_design \
  --runtime-profile-id api-error-response \
  --max-tokens "$CHAT_MAX_TOKENS" \
  > "${ARTIFACT_DIR}/api-error-chat.json"

"$PYTHON_BIN" - "$ARTIFACT_DIR" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path


artifact_dir = Path(sys.argv[1])


def load(name: str) -> dict[str, object]:
    with (artifact_dir / name).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise SystemExit(f"{name} did not contain a JSON object")
    return payload


capabilities = load("capabilities.json")
features = capabilities.get("features")
if not isinstance(features, dict):
    raise SystemExit("capabilities response omitted features")
runtime_profiles = features.get("runtime_profiles")
if not isinstance(runtime_profiles, dict):
    raise SystemExit("capabilities response omitted runtime_profiles")
if runtime_profiles.get("enabled") is not True:
    raise SystemExit("runtime profiles are not enabled on the live API")

available_profiles = runtime_profiles.get("available_profiles")
if not isinstance(available_profiles, list):
    raise SystemExit("runtime_profiles.available_profiles was not a list")
profile_ids = [
    str(profile.get("id"))
    for profile in available_profiles
    if isinstance(profile, dict) and profile.get("id")
]
required_ids = {"api-error-response", "rust-xriq-codegen"}
if not required_ids.issubset(set(profile_ids)):
    raise SystemExit(f"runtime profile ids missing from capabilities: {profile_ids}")

summaries: dict[str, object] = {
    "artifact_dir": str(artifact_dir),
    "runtime_profiles_enabled": True,
    "available_profile_ids": profile_ids,
}
for name in ["rust-chat", "rust-session", "api-error-chat"]:
    payload = load(f"{name}.json")
    content = str(payload.get("content") or "")
    if not content.strip():
        raise SystemExit(f"{name} returned empty content")
    if payload.get("mentor_used") is not False:
        raise SystemExit(f"{name} unexpectedly used mentor")
    summaries[name] = {
        "model": payload.get("model"),
        "id": payload.get("id"),
        "mentor_used": payload.get("mentor_used"),
        "content_prefix": content[:180],
    }

api_content = str(load("api-error-chat.json").get("content") or "").casefold()
if "status" not in api_content or "detail" not in api_content:
    raise SystemExit("api-error-response profile smoke did not include status/detail")

print(json.dumps(summaries, sort_keys=True))
PY
