#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

API_KEY="${BIBER_TEST_API_KEY:-$(read_env_value BIBER_DEMO_API_KEY)}"
if [ -z "$API_KEY" ]; then
  API_KEY="dev-api-key-change-me"
fi

PYTHON_BIN="${BIBER_AGENT_SMOKE_PYTHON:-${VENV_DIR}/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    die "Python is required for BIBER agent smoke validation."
  fi
fi

SMOKE_ID="${BIBER_AGENT_SMOKE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
ARTIFACT_DIR="${BIBER_AGENT_SMOKE_ARTIFACT_DIR:-${BIBER_RUNTIME_ROOT}/outputs/biber-agent-smoke-${SMOKE_ID}}"
API_BASE_URL="${BIBER_AGENT_SMOKE_URL:-http://127.0.0.1:${BIBER_API_PORT}}"
CHAT_MAX_TOKENS="${BIBER_AGENT_SMOKE_CHAT_MAX_TOKENS:-64}"
CLIENT_SESSION_MAX_TOKENS="${BIBER_AGENT_SMOKE_CLIENT_SESSION_MAX_TOKENS:-24}"
CLIENT_REPAIR_MAX_TOKENS="${BIBER_AGENT_SMOKE_CLIENT_REPAIR_MAX_TOKENS:-96}"
GITHUB_MODE="${BIBER_AGENT_SMOKE_GITHUB:-skip}"

mkdir -p "$ARTIFACT_DIR"

export API_BASE_URL
export API_KEY
export ARTIFACT_DIR
export CHAT_MAX_TOKENS
export CLIENT_SESSION_MAX_TOKENS
export CLIENT_REPAIR_MAX_TOKENS
export GITHUB_MODE
export SMOKE_ID
export SCRIPT_DIR

"$PYTHON_BIN" <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


api_base_url = os.environ["API_BASE_URL"].rstrip("/")
api_key = os.environ["API_KEY"]
artifact_dir = Path(os.environ["ARTIFACT_DIR"])
chat_max_tokens = int(os.environ["CHAT_MAX_TOKENS"])
client_session_max_tokens = int(os.environ["CLIENT_SESSION_MAX_TOKENS"])
client_repair_max_tokens = int(os.environ["CLIENT_REPAIR_MAX_TOKENS"])
github_mode = os.environ["GITHUB_MODE"].strip().lower()
smoke_id = os.environ["SMOKE_ID"]
script_dir = Path(os.environ["SCRIPT_DIR"])
client_edit_smoke_path = f".biber-runtime/agent-client-edit-smoke-{smoke_id}.txt"
client_mvp_loop_smoke_path = f".biber-runtime/agent-client-mvp-loop-smoke-{smoke_id}.txt"
client_mvp_loop_output_path = artifact_dir / "agent-client-mvp-loop-output.json"
client_mvp_loop_failures_path = artifact_dir / "agent-client-mvp-loop-failures.jsonl"
client_mvp_loop_repair_source_path = artifact_dir / "agent-client-repair-source-mvp-loop.json"
client_mvp_loop_repair_output_path = artifact_dir / "agent-client-mvp-loop-repair-output.json"
client_mvp_loop_repair_attempt_path = artifact_dir / "agent-client-mvp-loop-repair-attempt.json"
client_mvp_loop_repair_extract_source_path = artifact_dir / "agent-client-repair-extract-source.json"
client_mvp_loop_repair_extraction_path = artifact_dir / "agent-client-mvp-loop-repair-edit-extraction.json"
client_mvp_loop_repair_edits_path = artifact_dir / "agent-client-mvp-loop-repair-edits.json"
client_mvp_loop_repair_plan_path = artifact_dir / "agent-client-mvp-loop-repair-edit-plan.json"
client_mvp_loop_repair_apply_path = artifact_dir / "agent-client-mvp-loop-repair-edit-apply.json"
client_mvp_loop_repair_verify_path = artifact_dir / "agent-client-mvp-loop-repair-test-verification.json"
client_mvp_loop_verified_repair_review_path = artifact_dir / "agent-client-mvp-loop-verified-repairs.jsonl"
client_mvp_loop_verified_repair_review_summary_path = artifact_dir / "agent-client-mvp-loop-verified-repair-review.json"


def fail(message: str) -> None:
    print(f"error={message}", file=sys.stderr)
    sys.exit(1)


def write_artifact(name: str, payload: object) -> None:
    (artifact_dir / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def request_json(
    method: str,
    path: str,
    artifact_name: str,
    payload: dict[str, Any] | None = None,
    expected_status: int = 200,
) -> tuple[int, dict[str, Any]]:
    data = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        api_base_url + path,
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            status = int(response.status)
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        body = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        fail(f"{path} request failed: {exc}")

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{path} returned invalid JSON: {exc}; body={body[:500]!r}")
    if not isinstance(parsed, dict):
        fail(f"{path} returned non-object JSON")
    write_artifact(artifact_name, {"status": status, "body": parsed})
    if status != expected_status:
        fail(f"{path} returned HTTP {status}, expected {expected_status}: {body[:500]}")
    return status, parsed


_, health = request_json("GET", "/health", "health.json")
if health.get("status") != "ok":
    fail(f"health status was not ok: {health!r}")

_, runtime = request_json("GET", "/v1/runtime", "runtime.json")
if runtime.get("service") != "biber-api":
    fail(f"runtime service was unexpected: {runtime!r}")

_, capabilities = request_json("GET", "/v1/agent/capabilities", "agent-capabilities.json")
if capabilities.get("service") != "biber-agent":
    fail(f"agent capabilities service was unexpected: {capabilities!r}")
features = capabilities.get("features")
if not isinstance(features, dict):
    fail(f"agent capabilities features were missing: {capabilities!r}")
xriq_feature = features.get("xriq_private_devnet")
if not isinstance(xriq_feature, dict) or xriq_feature.get("context_supported") is not True:
    fail(f"agent capabilities did not advertise XRIQ context: {xriq_feature!r}")
test_runner = features.get("test_runner")
commands = test_runner.get("commands") if isinstance(test_runner, dict) else None
if not isinstance(commands, list):
    fail(f"agent capabilities test commands were missing: {test_runner!r}")
test_ids = {
    command.get("test_id")
    for command in commands
    if isinstance(command, dict)
}
if "python-compileall-api" not in test_ids:
    fail(f"agent capabilities omitted python-compileall-api: {test_ids!r}")
presets = capabilities.get("presets")
if not isinstance(presets, list):
    fail(f"agent capabilities presets were missing: {capabilities!r}")
preset_ids = {
    preset.get("id")
    for preset in presets
    if isinstance(preset, dict)
}
if "xriq_private_devnet_review" not in preset_ids:
    fail(f"agent capabilities omitted XRIQ preset: {preset_ids!r}")

client_env = os.environ.copy()
client_env["BIBER_API_KEY"] = api_key
client_env["BIBER_API_BASE_URL"] = api_base_url
try:
    client_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "capabilities",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py capabilities failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py capabilities timed out: {exc}")
try:
    client_capabilities = json.loads(client_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py capabilities returned invalid JSON: {exc}")
if client_capabilities.get("service") != "biber-agent":
    fail(f"agent client capabilities service was unexpected: {client_capabilities!r}")
write_artifact(
    "agent-client-capabilities.json",
    {"status": 0, "body": client_capabilities},
)

try:
    client_tests_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "list-tests",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py list-tests failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py list-tests timed out: {exc}")
try:
    client_tests = json.loads(client_tests_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py list-tests returned invalid JSON: {exc}")
client_commands = client_tests.get("commands")
if not isinstance(client_commands, list):
    fail(f"agent client list-tests did not return commands: {client_tests!r}")
client_test_ids = {
    command.get("test_id")
    for command in client_commands
    if isinstance(command, dict)
}
if "python-compileall-api" not in client_test_ids:
    fail(f"agent client list-tests omitted python-compileall-api: {client_test_ids!r}")
write_artifact(
    "agent-client-list-tests.json",
    {"status": 0, "body": client_tests},
)

try:
    client_test_run_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "--timeout-seconds",
            "180",
            "run-test",
            "--test-id",
            "python-compileall-api",
        ],
        env=client_env,
        text=True,
        timeout=180,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py run-test failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py run-test timed out: {exc}")
try:
    client_test_run = json.loads(client_test_run_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py run-test returned invalid JSON: {exc}")
if client_test_run.get("executed") is not True or client_test_run.get("ok") is not True:
    fail(f"agent client run-test did not pass: {client_test_run!r}")
write_artifact(
    "agent-client-run-test.json",
    {"status": 0, "body": client_test_run},
)

try:
    client_diagnosis_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "diagnose-test",
            "--test-id",
            "dotnet-test",
            "--command-part",
            "dotnet",
            "--command-part",
            "test",
            "--exit-code",
            "1",
            "--stdout",
            "Example.cs(7,1): error CS1002: ; expected\n",
            "--max-context-lines",
            "40",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py diagnose-test failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py diagnose-test timed out: {exc}")
try:
    client_diagnosis = json.loads(client_diagnosis_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py diagnose-test returned invalid JSON: {exc}")
if client_diagnosis.get("has_failure") is not True:
    fail(f"agent client diagnose-test did not detect failure: {client_diagnosis!r}")
if client_diagnosis.get("primary_category") != "compile_error":
    fail(f"agent client diagnose-test returned wrong category: {client_diagnosis!r}")
if client_diagnosis.get("detected_stack") != "dotnet":
    fail(f"agent client diagnose-test returned wrong stack: {client_diagnosis!r}")
write_artifact(
    "agent-client-diagnose-test.json",
    {"status": 0, "body": client_diagnosis},
)

try:
    client_session_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "--timeout-seconds",
            "180",
            "create-session",
            "--preset",
            "default_coding_session",
            "--instruction",
            (
                "Use README.md context and return one concise sentence that "
                "begins with BIBER_AGENT_CLIENT_SESSION_OK."
            ),
            "--repo-context",
            "README.md",
            "--no-test",
            "--max-tokens",
            str(client_session_max_tokens),
        ],
        env=client_env,
        text=True,
        timeout=180,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py create-session failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py create-session timed out: {exc}")
try:
    client_session = json.loads(client_session_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py create-session returned invalid JSON: {exc}")
if client_session.get("mentor_used") is not False:
    fail("agent client create-session unexpectedly used mentor")
client_session_steps = client_session.get("steps")
if not isinstance(client_session_steps, list):
    fail(f"agent client create-session steps were not a list: {client_session!r}")
client_session_step_names = [
    step.get("name")
    for step in client_session_steps
    if isinstance(step, dict)
]
if "chat" not in client_session_step_names:
    fail(f"agent client create-session did not include chat: {client_session_step_names!r}")
write_artifact(
    "agent-client-create-session.json",
    {"status": 0, "body": client_session},
)

try:
    client_list_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "list-sessions",
            "--limit",
            "5",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py list-sessions failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py list-sessions timed out: {exc}")
try:
    client_session_list = json.loads(client_list_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py list-sessions returned invalid JSON: {exc}")
listed_sessions = client_session_list.get("sessions")
if not isinstance(listed_sessions, list):
    fail(f"agent client list-sessions did not return sessions: {client_session_list!r}")
listed_session_ids = [
    item.get("id")
    for item in listed_sessions
    if isinstance(item, dict)
]
if client_session.get("id") not in listed_session_ids:
    fail(
        "agent client list-sessions did not include created session: "
        f"{listed_session_ids!r}"
    )
write_artifact(
    "agent-client-list-sessions.json",
    {"status": 0, "body": client_session_list},
)

try:
    client_get_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "get-session",
            str(client_session.get("id")),
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py get-session failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py get-session timed out: {exc}")
try:
    client_loaded_session = json.loads(client_get_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py get-session returned invalid JSON: {exc}")
if client_loaded_session.get("id") != client_session.get("id"):
    fail(
        "agent client get-session returned wrong id: "
        f"{client_loaded_session.get('id')!r}"
    )
write_artifact(
    "agent-client-get-session.json",
    {"status": 0, "body": client_loaded_session},
)

try:
    client_context_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "plan-context",
            "--instruction",
            "Plan a small BIBER agent client documentation change.",
            "--pinned-path",
            "README.md",
            "--changed-path",
            "docs/API_EXAMPLES.md",
            "--max-files",
            "5",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py plan-context failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py plan-context timed out: {exc}")
try:
    client_context_plan = json.loads(client_context_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py plan-context returned invalid JSON: {exc}")
selected_context_paths = client_context_plan.get("selected_paths")
if not isinstance(selected_context_paths, list):
    fail(f"agent client plan-context did not return selected_paths: {client_context_plan!r}")
if "README.md" not in selected_context_paths:
    fail(f"agent client plan-context omitted pinned README.md: {selected_context_paths!r}")
write_artifact(
    "agent-client-plan-context.json",
    {"status": 0, "body": client_context_plan},
)

client_edit = {
    "path": client_edit_smoke_path,
    "new_text": f"BIBER agent client edit smoke {smoke_id}\n",
    "create_if_missing": True,
}
if Path(client_edit_smoke_path).exists():
    fail(f"agent client edit smoke path already exists: {client_edit_smoke_path}")

try:
    client_edit_plan_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "plan-edit",
            "--edit-json",
            json.dumps(client_edit),
            "--max-files",
            "2",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py plan-edit failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py plan-edit timed out: {exc}")
try:
    client_edit_plan = json.loads(client_edit_plan_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py plan-edit returned invalid JSON: {exc}")
if client_edit_plan.get("ok") is not True:
    fail(f"agent client plan-edit did not return ok=true: {client_edit_plan!r}")
client_edit_plan_hash = client_edit_plan.get("plan_hash")
if not isinstance(client_edit_plan_hash, str) or len(client_edit_plan_hash) != 64:
    fail(f"agent client plan-edit returned invalid plan_hash: {client_edit_plan_hash!r}")
if Path(client_edit_smoke_path).exists():
    fail(f"agent client plan-edit unexpectedly wrote {client_edit_smoke_path}")
write_artifact(
    "agent-client-plan-edit.json",
    {"status": 0, "body": client_edit_plan},
)

try:
    client_edit_apply_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "apply-edit",
            "--edit-json",
            json.dumps(client_edit),
            "--plan-hash",
            client_edit_plan_hash,
            "--max-files",
            "2",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py apply-edit failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py apply-edit timed out: {exc}")
try:
    client_edit_apply = json.loads(client_edit_apply_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py apply-edit returned invalid JSON: {exc}")
if client_edit_apply.get("ok") is not True:
    fail(f"agent client apply-edit did not return ok=true: {client_edit_apply!r}")
applied_path = Path(client_edit_smoke_path)
if not applied_path.exists():
    fail(f"agent client apply-edit did not write {client_edit_smoke_path}")
if applied_path.read_text(encoding="utf-8") != client_edit["new_text"]:
    fail(f"agent client apply-edit wrote unexpected content to {client_edit_smoke_path}")
applied_path.unlink()
write_artifact(
    "agent-client-apply-edit.json",
    {"status": 0, "body": client_edit_apply},
)

client_mvp_loop_edit = {
    "path": client_mvp_loop_smoke_path,
    "new_text": f"BIBER agent client MVP loop smoke {smoke_id}\n",
    "create_if_missing": True,
}
if Path(client_mvp_loop_smoke_path).exists():
    fail(f"agent client MVP loop smoke path already exists: {client_mvp_loop_smoke_path}")

try:
    client_mvp_loop_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "--timeout-seconds",
            "180",
            "mvp-loop",
            "--instruction",
            "Run a small MVP loop smoke with README.md context.",
            "--pinned-path",
            "README.md",
            "--changed-path",
            "docs/API_EXAMPLES.md",
            "--max-context-files",
            "5",
            "--edit-json",
            json.dumps(client_mvp_loop_edit),
            "--apply-edits",
            "--max-edit-files",
            "2",
            "--test-id",
            "python-compileall-api",
            "--max-context-lines",
            "40",
            "--output",
            str(client_mvp_loop_output_path),
        ],
        env=client_env,
        text=True,
        timeout=180,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py mvp-loop failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py mvp-loop timed out: {exc}")
try:
    client_mvp_loop = json.loads(client_mvp_loop_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py mvp-loop returned invalid JSON: {exc}")
if not client_mvp_loop_output_path.exists():
    fail(f"agent client mvp-loop did not write output artifact {client_mvp_loop_output_path}")
try:
    saved_client_mvp_loop = json.loads(
        client_mvp_loop_output_path.read_text(encoding="utf-8")
    )
except json.JSONDecodeError as exc:
    fail(f"agent client mvp-loop output artifact returned invalid JSON: {exc}")
if saved_client_mvp_loop != client_mvp_loop:
    fail("agent client mvp-loop output artifact did not match stdout JSON")
try:
    client_mvp_loop_report = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "show-mvp-loop",
            str(client_mvp_loop_output_path),
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py show-mvp-loop failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py show-mvp-loop timed out: {exc}")
if "BIBER MVP loop" not in client_mvp_loop_report:
    fail(f"show-mvp-loop report omitted heading: {client_mvp_loop_report!r}")
if str(client_mvp_loop_output_path) not in client_mvp_loop_report:
    fail(f"show-mvp-loop report omitted artifact path: {client_mvp_loop_report!r}")
try:
    client_mvp_loop_list_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "list-mvp-loops",
            str(artifact_dir),
            "--limit",
            "5",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py list-mvp-loops failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py list-mvp-loops timed out: {exc}")
try:
    client_mvp_loop_list = json.loads(client_mvp_loop_list_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py list-mvp-loops returned invalid JSON: {exc}")
client_mvp_loop_list_artifacts = client_mvp_loop_list.get("artifacts")
if not isinstance(client_mvp_loop_list_artifacts, list):
    fail(f"list-mvp-loops did not return artifacts: {client_mvp_loop_list!r}")
if not any(
    item.get("path") == str(client_mvp_loop_output_path)
    for item in client_mvp_loop_list_artifacts
    if isinstance(item, dict)
):
    fail(f"list-mvp-loops omitted {client_mvp_loop_output_path}: {client_mvp_loop_list!r}")
try:
    client_mvp_loop_failed_list_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "list-mvp-loops",
            str(artifact_dir),
            "--failed-only",
            "--limit",
            "5",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py list-mvp-loops --failed-only failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py list-mvp-loops --failed-only timed out: {exc}")
try:
    client_mvp_loop_failed_list = json.loads(client_mvp_loop_failed_list_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py list-mvp-loops --failed-only returned invalid JSON: {exc}")
client_mvp_loop_failed_artifacts = client_mvp_loop_failed_list.get("artifacts")
if not isinstance(client_mvp_loop_failed_artifacts, list):
    fail(f"list-mvp-loops --failed-only did not return artifacts: {client_mvp_loop_failed_list!r}")
if client_mvp_loop_failed_artifacts:
    fail(f"successful mvp-loop smoke appeared in failed-only list: {client_mvp_loop_failed_list!r}")
try:
    client_mvp_loop_failure_export_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "export-mvp-failures",
            str(artifact_dir),
            "--output",
            str(client_mvp_loop_failures_path),
            "--limit",
            "5",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py export-mvp-failures failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py export-mvp-failures timed out: {exc}")
try:
    client_mvp_loop_failure_export = json.loads(client_mvp_loop_failure_export_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py export-mvp-failures returned invalid JSON: {exc}")
if client_mvp_loop_failure_export.get("records") != 0:
    fail(f"successful smoke exported failure records: {client_mvp_loop_failure_export!r}")
if client_mvp_loop_failure_export.get("training_allowed") is not False:
    fail(f"failure export must remain training_allowed=false: {client_mvp_loop_failure_export!r}")
if not client_mvp_loop_failures_path.exists():
    fail(f"export-mvp-failures did not write {client_mvp_loop_failures_path}")
if client_mvp_loop_failures_path.read_text(encoding="utf-8") != "":
    fail(f"successful smoke wrote non-empty failure export: {client_mvp_loop_failures_path}")

client_mvp_loop_repair_source = {
    "ok": False,
    "instruction": "Fix a synthetic .NET compile error.",
    "diagnosis_summary": "Detected compile_error in dotnet output.",
    "steps": {
        "context_plan": {},
        "test_run": {
            "ok": False,
            "test_id": "dotnet-test",
            "command": ["dotnet", "test"],
            "exit_code": 1,
            "timed_out": False,
            "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
        },
        "test_diagnosis": {
            "primary_category": "compile_error",
            "detected_stack": "dotnet",
            "summary": "Detected compile_error in dotnet output.",
            "relevant_output": "Example.cs(7,1): error CS1002: ; expected\n",
            "suggested_next_actions": ["Fix compiler diagnostics first."],
        },
    },
    "selected_context_paths": ["README.md", "docs/API_EXAMPLES.md"],
    "test_ok": False,
}
client_mvp_loop_repair_source_path.write_text(
    json.dumps(client_mvp_loop_repair_source, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
try:
    client_mvp_loop_repair_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "prepare-repair",
            str(client_mvp_loop_repair_source_path),
            "--instruction",
            "Repair the synthetic compile error with the smallest safe edit.",
            "--output",
            str(client_mvp_loop_repair_output_path),
            "--max-context-paths",
            "2",
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py prepare-repair failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py prepare-repair timed out: {exc}")
try:
    client_mvp_loop_repair = json.loads(client_mvp_loop_repair_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py prepare-repair returned invalid JSON: {exc}")
if client_mvp_loop_repair.get("repair_status") != "ready_for_local_model":
    fail(f"prepare-repair returned unexpected status: {client_mvp_loop_repair!r}")
if client_mvp_loop_repair.get("training_allowed") is not False:
    fail(f"prepare-repair must keep training_allowed=false: {client_mvp_loop_repair!r}")
repair_failure = client_mvp_loop_repair.get("failure")
if not isinstance(repair_failure, dict) or repair_failure.get("test_id") != "dotnet-test":
    fail(f"prepare-repair omitted test failure details: {client_mvp_loop_repair!r}")
if not client_mvp_loop_repair_output_path.exists():
    fail(f"prepare-repair did not write {client_mvp_loop_repair_output_path}")
try:
    saved_client_mvp_loop_repair = json.loads(
        client_mvp_loop_repair_output_path.read_text(encoding="utf-8")
    )
except json.JSONDecodeError as exc:
    fail(f"prepare-repair output artifact returned invalid JSON: {exc}")
if saved_client_mvp_loop_repair != client_mvp_loop_repair:
    fail("prepare-repair output artifact did not match stdout JSON")

try:
    client_mvp_loop_repair_attempt_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "--timeout-seconds",
            "180",
            "attempt-repair",
            str(client_mvp_loop_repair_source_path),
            "--instruction",
            "Repair the synthetic compile error with the smallest safe edit.",
            "--max-context-paths",
            "2",
            "--max-tokens",
            str(client_repair_max_tokens),
            "--output",
            str(client_mvp_loop_repair_attempt_path),
        ],
        env=client_env,
        text=True,
        timeout=180,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py attempt-repair failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py attempt-repair timed out: {exc}")
try:
    client_mvp_loop_repair_attempt = json.loads(client_mvp_loop_repair_attempt_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py attempt-repair returned invalid JSON: {exc}")
if client_mvp_loop_repair_attempt.get("repair_status") != "model_repair_proposed":
    fail(f"attempt-repair returned unexpected status: {client_mvp_loop_repair_attempt!r}")
if client_mvp_loop_repair_attempt.get("training_allowed") is not False:
    fail(f"attempt-repair must keep training_allowed=false: {client_mvp_loop_repair_attempt!r}")
if client_mvp_loop_repair_attempt.get("auto_applied") is not False:
    fail(f"attempt-repair must not apply edits: {client_mvp_loop_repair_attempt!r}")
attempt_model_response = client_mvp_loop_repair_attempt.get("model_response")
if not isinstance(attempt_model_response, dict):
    fail(f"attempt-repair omitted model_response: {client_mvp_loop_repair_attempt!r}")
if attempt_model_response.get("mentor_used") is not False:
    fail(f"attempt-repair unexpectedly used mentor: {client_mvp_loop_repair_attempt!r}")
if not str(client_mvp_loop_repair_attempt.get("repair_content") or "").strip():
    fail(f"attempt-repair returned empty repair_content: {client_mvp_loop_repair_attempt!r}")
if not client_mvp_loop_repair_attempt_path.exists():
    fail(f"attempt-repair did not write {client_mvp_loop_repair_attempt_path}")
try:
    saved_client_mvp_loop_repair_attempt = json.loads(
        client_mvp_loop_repair_attempt_path.read_text(encoding="utf-8")
    )
except json.JSONDecodeError as exc:
    fail(f"attempt-repair output artifact returned invalid JSON: {exc}")
if saved_client_mvp_loop_repair_attempt != client_mvp_loop_repair_attempt:
    fail("attempt-repair output artifact did not match stdout JSON")

client_mvp_loop_repair_apply_text = (
    client_mvp_loop_edit["new_text"].rstrip("\n") + " repair-plan-only\n"
)
client_mvp_loop_repair_extract_source = {
    "source": "biber_mvp_loop_repair_attempt",
    "repair_status": "model_repair_proposed",
    "training_allowed": False,
    "auto_applied": False,
    "next_test_id": "python-compileall-api",
    "repair_content": json.dumps(
        {
            "edits": [
                {
                    "path": client_mvp_loop_smoke_path,
                    "old_text": client_mvp_loop_edit["new_text"],
                    "new_text": client_mvp_loop_repair_apply_text,
                    "expected_replacements": 1,
                }
            ]
        }
    ),
}
client_mvp_loop_repair_extract_source_path.write_text(
    json.dumps(client_mvp_loop_repair_extract_source, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
try:
    client_mvp_loop_repair_extraction_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "extract-repair-edits",
            str(client_mvp_loop_repair_extract_source_path),
            "--max-files",
            "2",
            "--output",
            str(client_mvp_loop_repair_extraction_path),
            "--edits-output",
            str(client_mvp_loop_repair_edits_path),
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py extract-repair-edits failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py extract-repair-edits timed out: {exc}")
try:
    client_mvp_loop_repair_extraction = json.loads(client_mvp_loop_repair_extraction_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py extract-repair-edits returned invalid JSON: {exc}")
if client_mvp_loop_repair_extraction.get("extraction_status") != "ready_for_plan_edit":
    fail(f"extract-repair-edits returned unexpected status: {client_mvp_loop_repair_extraction!r}")
if client_mvp_loop_repair_extraction.get("training_allowed") is not False:
    fail(f"extract-repair-edits must keep training_allowed=false: {client_mvp_loop_repair_extraction!r}")
if client_mvp_loop_repair_extraction.get("auto_applied") is not False:
    fail(f"extract-repair-edits must not apply edits: {client_mvp_loop_repair_extraction!r}")
if client_mvp_loop_repair_extraction.get("apply_allowed") is not False:
    fail(f"extract-repair-edits must not allow direct apply: {client_mvp_loop_repair_extraction!r}")
if not client_mvp_loop_repair_extraction_path.exists():
    fail(f"extract-repair-edits did not write {client_mvp_loop_repair_extraction_path}")
if not client_mvp_loop_repair_edits_path.exists():
    fail(f"extract-repair-edits did not write {client_mvp_loop_repair_edits_path}")
try:
    saved_client_mvp_loop_repair_extraction = json.loads(
        client_mvp_loop_repair_extraction_path.read_text(encoding="utf-8")
    )
    saved_client_mvp_loop_repair_edits = json.loads(
        client_mvp_loop_repair_edits_path.read_text(encoding="utf-8")
    )
except json.JSONDecodeError as exc:
    fail(f"extract-repair-edits wrote invalid JSON: {exc}")
if saved_client_mvp_loop_repair_extraction != client_mvp_loop_repair_extraction:
    fail("extract-repair-edits output artifact did not match stdout JSON")
if saved_client_mvp_loop_repair_edits != client_mvp_loop_repair_extraction.get("plan_edit_payload"):
    fail("extract-repair-edits edits payload did not match plan_edit_payload")

try:
    client_mvp_loop_repair_plan_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "--timeout-seconds",
            "180",
            "plan-repair-edits",
            str(client_mvp_loop_repair_extraction_path),
            "--max-files",
            "2",
            "--output",
            str(client_mvp_loop_repair_plan_path),
        ],
        env=client_env,
        text=True,
        timeout=180,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py plan-repair-edits failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py plan-repair-edits timed out: {exc}")
try:
    client_mvp_loop_repair_plan = json.loads(client_mvp_loop_repair_plan_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py plan-repair-edits returned invalid JSON: {exc}")
if client_mvp_loop_repair_plan.get("plan_status") != "planned":
    fail(f"plan-repair-edits returned unexpected status: {client_mvp_loop_repair_plan!r}")
if client_mvp_loop_repair_plan.get("training_allowed") is not False:
    fail(f"plan-repair-edits must keep training_allowed=false: {client_mvp_loop_repair_plan!r}")
if client_mvp_loop_repair_plan.get("auto_applied") is not False:
    fail(f"plan-repair-edits must not apply edits: {client_mvp_loop_repair_plan!r}")
if client_mvp_loop_repair_plan.get("apply_allowed") is not False:
    fail(f"plan-repair-edits must not allow direct apply: {client_mvp_loop_repair_plan!r}")
if not isinstance(client_mvp_loop_repair_plan.get("plan_hash"), str):
    fail(f"plan-repair-edits omitted plan_hash: {client_mvp_loop_repair_plan!r}")
if not client_mvp_loop_repair_plan_path.exists():
    fail(f"plan-repair-edits did not write {client_mvp_loop_repair_plan_path}")
try:
    saved_client_mvp_loop_repair_plan = json.loads(
        client_mvp_loop_repair_plan_path.read_text(encoding="utf-8")
    )
except json.JSONDecodeError as exc:
    fail(f"plan-repair-edits output artifact returned invalid JSON: {exc}")
if saved_client_mvp_loop_repair_plan != client_mvp_loop_repair_plan:
    fail("plan-repair-edits output artifact did not match stdout JSON")
if Path(client_mvp_loop_smoke_path).read_text(encoding="utf-8") != client_mvp_loop_edit["new_text"]:
    fail("plan-repair-edits unexpectedly changed the MVP loop smoke file")

if client_mvp_loop.get("ok") is not True:
    fail(f"agent client mvp-loop did not return ok=true: {client_mvp_loop!r}")
client_mvp_steps = client_mvp_loop.get("steps")
if not isinstance(client_mvp_steps, dict):
    fail(f"agent client mvp-loop did not return steps: {client_mvp_loop!r}")
for required_step in ("context_plan", "edit_plan", "edit_apply", "test_run"):
    if required_step not in client_mvp_steps:
        fail(f"agent client mvp-loop omitted {required_step}: {client_mvp_steps!r}")
if client_mvp_loop.get("test_ok") is not True:
    fail(f"agent client mvp-loop test did not pass: {client_mvp_loop!r}")
client_mvp_loop_applied_path = Path(client_mvp_loop_smoke_path)
if not client_mvp_loop_applied_path.exists():
    fail(f"agent client mvp-loop did not write {client_mvp_loop_smoke_path}")
if client_mvp_loop_applied_path.read_text(encoding="utf-8") != client_mvp_loop_edit["new_text"]:
    fail(f"agent client mvp-loop wrote unexpected content to {client_mvp_loop_smoke_path}")
try:
    client_mvp_loop_repair_apply_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "--timeout-seconds",
            "180",
            "apply-repair-edits",
            str(client_mvp_loop_repair_plan_path),
            "--approve",
            "--output",
            str(client_mvp_loop_repair_apply_path),
        ],
        env=client_env,
        text=True,
        timeout=180,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py apply-repair-edits failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py apply-repair-edits timed out: {exc}")
try:
    client_mvp_loop_repair_apply = json.loads(client_mvp_loop_repair_apply_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py apply-repair-edits returned invalid JSON: {exc}")
if client_mvp_loop_repair_apply.get("apply_status") != "applied":
    fail(f"apply-repair-edits returned unexpected status: {client_mvp_loop_repair_apply!r}")
if client_mvp_loop_repair_apply.get("training_allowed") is not False:
    fail(f"apply-repair-edits must keep training_allowed=false: {client_mvp_loop_repair_apply!r}")
if client_mvp_loop_repair_apply.get("auto_applied") is not False:
    fail(f"apply-repair-edits must not mark the repair as auto-applied: {client_mvp_loop_repair_apply!r}")
if client_mvp_loop_repair_apply.get("approval_required") is not True:
    fail(f"apply-repair-edits must require approval: {client_mvp_loop_repair_apply!r}")
if client_mvp_loop_repair_apply.get("approval_received") is not True:
    fail(f"apply-repair-edits must record approval: {client_mvp_loop_repair_apply!r}")
if client_mvp_loop_repair_apply.get("plan_hash") != client_mvp_loop_repair_plan.get("plan_hash"):
    fail(f"apply-repair-edits used unexpected plan hash: {client_mvp_loop_repair_apply!r}")
if not client_mvp_loop_repair_apply_path.exists():
    fail(f"apply-repair-edits did not write {client_mvp_loop_repair_apply_path}")
try:
    saved_client_mvp_loop_repair_apply = json.loads(
        client_mvp_loop_repair_apply_path.read_text(encoding="utf-8")
    )
except json.JSONDecodeError as exc:
    fail(f"apply-repair-edits output artifact returned invalid JSON: {exc}")
if saved_client_mvp_loop_repair_apply != client_mvp_loop_repair_apply:
    fail("apply-repair-edits output artifact did not match stdout JSON")
if client_mvp_loop_applied_path.read_text(encoding="utf-8") != client_mvp_loop_repair_apply_text:
    fail("apply-repair-edits wrote unexpected MVP loop smoke file content")
try:
    client_mvp_loop_repair_verify_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "--timeout-seconds",
            "180",
            "verify-repair-edits",
            str(client_mvp_loop_repair_apply_path),
            "--diagnose-on-failure",
            "--output",
            str(client_mvp_loop_repair_verify_path),
        ],
        env=client_env,
        text=True,
        timeout=180,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py verify-repair-edits failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py verify-repair-edits timed out: {exc}")
try:
    client_mvp_loop_repair_verify = json.loads(client_mvp_loop_repair_verify_output)
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py verify-repair-edits returned invalid JSON: {exc}")
if client_mvp_loop_repair_verify.get("verification_status") != "passed":
    fail(f"verify-repair-edits returned unexpected status: {client_mvp_loop_repair_verify!r}")
if client_mvp_loop_repair_verify.get("training_allowed") is not False:
    fail(f"verify-repair-edits must keep training_allowed=false: {client_mvp_loop_repair_verify!r}")
if client_mvp_loop_repair_verify.get("auto_applied") is not False:
    fail(f"verify-repair-edits must not apply edits: {client_mvp_loop_repair_verify!r}")
if client_mvp_loop_repair_verify.get("auto_saved") is not False:
    fail(f"verify-repair-edits must not save automatically: {client_mvp_loop_repair_verify!r}")
if client_mvp_loop_repair_verify.get("plan_hash") != client_mvp_loop_repair_apply.get("plan_hash"):
    fail(f"verify-repair-edits used unexpected plan hash: {client_mvp_loop_repair_verify!r}")
if client_mvp_loop_repair_verify.get("test_id") != "python-compileall-api":
    fail(f"verify-repair-edits used unexpected test id: {client_mvp_loop_repair_verify!r}")
if not client_mvp_loop_repair_verify_path.exists():
    fail(f"verify-repair-edits did not write {client_mvp_loop_repair_verify_path}")
try:
    saved_client_mvp_loop_repair_verify = json.loads(
        client_mvp_loop_repair_verify_path.read_text(encoding="utf-8")
    )
except json.JSONDecodeError as exc:
    fail(f"verify-repair-edits output artifact returned invalid JSON: {exc}")
if saved_client_mvp_loop_repair_verify != client_mvp_loop_repair_verify:
    fail("verify-repair-edits output artifact did not match stdout JSON")
try:
    client_mvp_loop_verified_repair_export_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "export-verified-repair",
            str(client_mvp_loop_repair_verify_path),
            "--output",
            str(client_mvp_loop_verified_repair_review_path),
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py export-verified-repair failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py export-verified-repair timed out: {exc}")
try:
    client_mvp_loop_verified_repair_export = json.loads(
        client_mvp_loop_verified_repair_export_output
    )
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py export-verified-repair returned invalid JSON: {exc}")
if client_mvp_loop_verified_repair_export.get("records") != 1:
    fail(f"export-verified-repair wrote unexpected records: {client_mvp_loop_verified_repair_export!r}")
if client_mvp_loop_verified_repair_export.get("training_allowed") is not False:
    fail(f"export-verified-repair must keep training_allowed=false: {client_mvp_loop_verified_repair_export!r}")
if client_mvp_loop_verified_repair_export.get("eligible_for_training") is not False:
    fail(f"export-verified-repair must not mark training eligibility: {client_mvp_loop_verified_repair_export!r}")
if not client_mvp_loop_verified_repair_review_path.exists():
    fail(f"export-verified-repair did not write {client_mvp_loop_verified_repair_review_path}")
verified_repair_review_lines = client_mvp_loop_verified_repair_review_path.read_text(
    encoding="utf-8"
).splitlines()
if len(verified_repair_review_lines) != 1:
    fail(f"export-verified-repair wrote unexpected JSONL line count: {verified_repair_review_lines!r}")
try:
    verified_repair_review_row = json.loads(verified_repair_review_lines[0])
except json.JSONDecodeError as exc:
    fail(f"export-verified-repair wrote invalid JSONL: {exc}")
if verified_repair_review_row.get("review_status") != "needs_human_review":
    fail(f"export-verified-repair wrote unexpected review status: {verified_repair_review_row!r}")
if verified_repair_review_row.get("eligible_for_training") is not False:
    fail(f"verified repair row must not be training-eligible: {verified_repair_review_row!r}")
if verified_repair_review_row.get("test_id") != "python-compileall-api":
    fail(f"verified repair row used unexpected test id: {verified_repair_review_row!r}")
try:
    client_mvp_loop_verified_repair_review_output = subprocess.check_output(
        [
            sys.executable,
            str(script_dir / "biber_agent_client.py"),
            "--json",
            "review-verified-repairs",
            str(client_mvp_loop_verified_repair_review_path),
            "--output",
            str(client_mvp_loop_verified_repair_review_summary_path),
        ],
        env=client_env,
        text=True,
        timeout=60,
    )
except subprocess.CalledProcessError as exc:
    fail(f"biber_agent_client.py review-verified-repairs failed: {exc}")
except subprocess.TimeoutExpired as exc:
    fail(f"biber_agent_client.py review-verified-repairs timed out: {exc}")
try:
    client_mvp_loop_verified_repair_review = json.loads(
        client_mvp_loop_verified_repair_review_output
    )
except json.JSONDecodeError as exc:
    fail(f"biber_agent_client.py review-verified-repairs returned invalid JSON: {exc}")
if client_mvp_loop_verified_repair_review.get("records") != 1:
    fail(f"review-verified-repairs saw unexpected record count: {client_mvp_loop_verified_repair_review!r}")
if client_mvp_loop_verified_repair_review.get("ready_for_human_review") != 1:
    fail(f"review-verified-repairs saw unexpected review count: {client_mvp_loop_verified_repair_review!r}")
if client_mvp_loop_verified_repair_review.get("training_allowed") is not False:
    fail(f"review-verified-repairs must keep training_allowed=false: {client_mvp_loop_verified_repair_review!r}")
if client_mvp_loop_verified_repair_review.get("eligible_for_training") is not False:
    fail(f"review-verified-repairs must not mark training eligibility: {client_mvp_loop_verified_repair_review!r}")
if not client_mvp_loop_verified_repair_review_summary_path.exists():
    fail(f"review-verified-repairs did not write {client_mvp_loop_verified_repair_review_summary_path}")
try:
    saved_client_mvp_loop_verified_repair_review = json.loads(
        client_mvp_loop_verified_repair_review_summary_path.read_text(encoding="utf-8")
    )
except json.JSONDecodeError as exc:
    fail(f"review-verified-repairs output artifact returned invalid JSON: {exc}")
if saved_client_mvp_loop_verified_repair_review != client_mvp_loop_verified_repair_review:
    fail("review-verified-repairs output artifact did not match stdout JSON")
client_mvp_loop_applied_path.unlink()
write_artifact(
    "agent-client-mvp-loop.json",
    {"status": 0, "body": client_mvp_loop, "output": str(client_mvp_loop_output_path)},
)
write_artifact(
    "agent-client-mvp-loop-report.json",
    {"status": 0, "body": client_mvp_loop_report},
)
write_artifact(
    "agent-client-mvp-loop-list.json",
    {"status": 0, "body": client_mvp_loop_list},
)
write_artifact(
    "agent-client-mvp-loop-failed-list.json",
    {"status": 0, "body": client_mvp_loop_failed_list},
)
write_artifact(
    "agent-client-mvp-loop-failure-export.json",
    {"status": 0, "body": client_mvp_loop_failure_export},
)
write_artifact(
    "agent-client-mvp-loop-repair.json",
    {
        "status": 0,
        "body": client_mvp_loop_repair,
        "output": str(client_mvp_loop_repair_output_path),
        "source": str(client_mvp_loop_repair_source_path),
    },
)
write_artifact(
    "agent-client-mvp-loop-repair-attempt.json",
    {
        "status": 0,
        "body": client_mvp_loop_repair_attempt,
        "output": str(client_mvp_loop_repair_attempt_path),
        "source": str(client_mvp_loop_repair_source_path),
    },
)
write_artifact(
    "agent-client-mvp-loop-repair-edit-extraction.json",
    {
        "status": 0,
        "body": client_mvp_loop_repair_extraction,
        "output": str(client_mvp_loop_repair_extraction_path),
        "edits_output": str(client_mvp_loop_repair_edits_path),
        "source": str(client_mvp_loop_repair_extract_source_path),
    },
)
write_artifact(
    "agent-client-mvp-loop-repair-edit-plan.json",
    {
        "status": 0,
        "body": client_mvp_loop_repair_plan,
        "output": str(client_mvp_loop_repair_plan_path),
        "source": str(client_mvp_loop_repair_extraction_path),
    },
)
write_artifact(
    "agent-client-mvp-loop-repair-edit-apply.json",
    {
        "status": 0,
        "body": client_mvp_loop_repair_apply,
        "output": str(client_mvp_loop_repair_apply_path),
        "source": str(client_mvp_loop_repair_plan_path),
    },
)
write_artifact(
    "agent-client-mvp-loop-repair-test-verification.json",
    {
        "status": 0,
        "body": client_mvp_loop_repair_verify,
        "output": str(client_mvp_loop_repair_verify_path),
        "source": str(client_mvp_loop_repair_apply_path),
    },
)
write_artifact(
    "agent-client-mvp-loop-verified-repair-export.json",
    {
        "status": 0,
        "body": client_mvp_loop_verified_repair_export,
        "output": str(client_mvp_loop_verified_repair_review_path),
        "source": str(client_mvp_loop_repair_verify_path),
    },
)
write_artifact(
    "agent-client-mvp-loop-verified-repair-review.json",
    {
        "status": 0,
        "body": client_mvp_loop_verified_repair_review,
        "output": str(client_mvp_loop_verified_repair_review_summary_path),
        "source": str(client_mvp_loop_verified_repair_review_path),
    },
)

chat_payload = {
    "language": "Rust",
    "model": "biber-dev-core-v1",
    "task_type": "repo_context_smoke",
    "max_tokens": chat_max_tokens,
    "use_mentor": False,
    "repo_context_paths": ["README.md"],
    "messages": [
        {
            "role": "user",
            "content": (
                "Using the selected repository context, return one concise "
                "sentence that begins with BIBER_AGENT_SMOKE_OK."
            ),
        }
    ],
}
_, chat = request_json("POST", "/v1/chat", "chat.json", chat_payload)
if not isinstance(chat.get("content"), str) or not chat["content"].strip():
    fail("chat smoke returned empty content")
if chat.get("model") != "biber-dev-core-v1":
    fail(f"chat smoke used unexpected model: {chat.get('model')!r}")
if chat.get("mentor_used") is not False:
    fail("chat smoke unexpectedly used mentor")

edit_payload = {
    "path": "generated/biber-agent-smoke.txt",
    "new_text": f"BIBER agent smoke {smoke_id}\n",
    "create_if_missing": True,
    "dry_run": True,
}
_, edit = request_json("POST", "/v1/files/edit", "file-edit-dry-run.json", edit_payload)
if edit.get("dry_run") is not True or edit.get("changed") is not True:
    fail(f"file edit dry-run response was unexpected: {edit!r}")

test_payload = {"test_id": "python-compileall-api"}
_, test_run = request_json("POST", "/v1/tests/run", "test-run.json", test_payload)
if test_run.get("executed") is not True or test_run.get("ok") is not True:
    fail(f"allowlisted test run failed: {test_run!r}")

agent_session_payload = {
    "instruction": (
        "Use the included XRIQ private-devnet context and return one concise "
        "sentence that begins with BIBER_XRIQ_AGENT_CONTEXT_OK."
    ),
    "language": "Rust",
    "model": "biber-dev-core-v1",
    "task_type": "xriq_agent_context_smoke",
    "max_tokens": chat_max_tokens,
    "use_mentor": False,
    "include_xriq_context": True,
    "xriq_explorer_limit": 3,
    "xriq_snapshot_limit": 3,
    "test_id": None,
}
_, agent_session = request_json(
    "POST",
    "/v1/agent/sessions",
    "agent-session-xriq-context.json",
    agent_session_payload,
)
steps = agent_session.get("steps")
if not isinstance(steps, list):
    fail(f"agent session steps were not a list: {agent_session!r}")
step_names = [step.get("name") for step in steps if isinstance(step, dict)]
if step_names[:2] != ["xriq_context", "chat"]:
    fail(f"agent session did not include xriq_context before chat: {step_names!r}")
xriq_step = steps[0] if isinstance(steps[0], dict) else {}
xriq_output = xriq_step.get("output") if isinstance(xriq_step, dict) else {}
overview = xriq_output.get("overview") if isinstance(xriq_output, dict) else {}
summary = overview.get("summary") if isinstance(overview, dict) else {}
if not isinstance(summary, dict) or summary.get("current_height") is None:
    fail(f"agent session XRIQ context summary was incomplete: {summary!r}")
if agent_session.get("mentor_used") is not False:
    fail("agent session XRIQ context smoke unexpectedly used mentor")

github_result: dict[str, Any] = {
    "mode": github_mode,
    "configured": bool(runtime.get("github_configured")),
    "status": "skipped",
}
if github_mode == "1":
    if not runtime.get("github_configured"):
        fail("BIBER_AGENT_SMOKE_GITHUB=1 but GitHub is not configured.")
    branch = f"biber/agent-smoke-{smoke_id}"
    try:
        github_save_output = subprocess.check_output(
            [
                sys.executable,
                str(script_dir / "biber_agent_client.py"),
                "--json",
                "save-github",
                "--path",
                f"generated/biber-agent-smoke-{smoke_id}.txt",
                "--branch",
                branch,
                "--base-branch",
                "main",
                "--create-branch-if-missing",
                "--commit-message",
                "Save BIBER agent smoke artifact",
                "--content",
                f"BIBER agent smoke {smoke_id}\n",
            ],
            env=client_env,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        fail(f"biber_agent_client.py save-github failed: {exc}")
    except subprocess.TimeoutExpired as exc:
        fail(f"biber_agent_client.py save-github timed out: {exc}")
    try:
        save = json.loads(github_save_output)
    except json.JSONDecodeError as exc:
        fail(f"biber_agent_client.py save-github returned invalid JSON: {exc}")
    if not isinstance(save.get("url"), str) or not save["url"]:
        fail(f"agent client save-github returned no url: {save!r}")
    write_artifact(
        "agent-client-github-save.json",
        {"status": 0, "body": save},
    )

    try:
        github_pr_output = subprocess.check_output(
            [
                sys.executable,
                str(script_dir / "biber_agent_client.py"),
                "--json",
                "create-pr",
                "--head",
                branch,
                "--base",
                "main",
                "--title",
                "BIBER agent smoke",
                "--body",
                "Generated by the BIBER agent smoke script.",
            ],
            env=client_env,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        fail(f"biber_agent_client.py create-pr failed: {exc}")
    except subprocess.TimeoutExpired as exc:
        fail(f"biber_agent_client.py create-pr timed out: {exc}")
    try:
        pull_request = json.loads(github_pr_output)
    except json.JSONDecodeError as exc:
        fail(f"biber_agent_client.py create-pr returned invalid JSON: {exc}")
    if not isinstance(pull_request.get("url"), str) or not pull_request["url"]:
        fail(f"agent client create-pr returned no url: {pull_request!r}")
    write_artifact(
        "agent-client-github-pr.json",
        {"status": 0, "body": pull_request},
    )
    github_result = {
        "mode": github_mode,
        "configured": True,
        "status": "created",
        "save_url": save.get("url"),
        "pull_request_url": pull_request.get("url"),
        "pull_request_number": pull_request.get("number"),
    }
elif github_mode not in {"", "skip", "0"}:
    fail("BIBER_AGENT_SMOKE_GITHUB must be skip, 0, or 1.")

summary = {
    "ok": "biber-agent-smoke",
    "artifacts": str(artifact_dir),
    "chat_model": chat.get("model"),
    "capability_presets": sorted(item for item in preset_ids if isinstance(item, str)),
    "chat_content_prefix": chat.get("content", "")[:120],
    "file_edit_dry_run": edit.get("dry_run"),
    "test_id": test_run.get("test_id"),
    "test_ok": test_run.get("ok"),
    "agent_session_id": agent_session.get("id"),
    "agent_session_steps": step_names,
    "agent_client_session_id": client_session.get("id"),
    "agent_client_session_steps": client_session_step_names,
    "agent_client_listed_sessions": len(listed_sessions),
    "agent_client_loaded_session_id": client_loaded_session.get("id"),
    "agent_client_context_paths": selected_context_paths,
    "agent_client_edit_path": client_edit_smoke_path,
    "agent_client_edit_plan_hash": client_edit_plan_hash,
    "agent_client_mvp_loop_path": client_mvp_loop_smoke_path,
    "agent_client_mvp_loop_output": str(client_mvp_loop_output_path),
    "agent_client_mvp_loop_steps": sorted(client_mvp_steps.keys()),
    "agent_client_mvp_loop_list_count": len(client_mvp_loop_list_artifacts),
    "agent_client_mvp_loop_failed_list_count": len(client_mvp_loop_failed_artifacts),
    "agent_client_mvp_loop_failure_export": str(client_mvp_loop_failures_path),
    "agent_client_mvp_loop_failure_export_records": client_mvp_loop_failure_export.get("records"),
    "agent_client_mvp_loop_repair_output": str(client_mvp_loop_repair_output_path),
    "agent_client_mvp_loop_repair_status": client_mvp_loop_repair.get("repair_status"),
    "agent_client_mvp_loop_repair_attempt": str(client_mvp_loop_repair_attempt_path),
    "agent_client_mvp_loop_repair_attempt_status": client_mvp_loop_repair_attempt.get("repair_status"),
    "agent_client_mvp_loop_repair_attempt_auto_applied": client_mvp_loop_repair_attempt.get("auto_applied"),
    "agent_client_mvp_loop_repair_attempt_mentor_used": attempt_model_response.get("mentor_used"),
    "agent_client_mvp_loop_repair_extraction": str(client_mvp_loop_repair_extraction_path),
    "agent_client_mvp_loop_repair_extraction_status": client_mvp_loop_repair_extraction.get("extraction_status"),
    "agent_client_mvp_loop_repair_extraction_apply_allowed": client_mvp_loop_repair_extraction.get("apply_allowed"),
    "agent_client_mvp_loop_repair_edits": str(client_mvp_loop_repair_edits_path),
    "agent_client_mvp_loop_repair_edits_count": len(client_mvp_loop_repair_extraction.get("edits") or []),
    "agent_client_mvp_loop_repair_plan": str(client_mvp_loop_repair_plan_path),
    "agent_client_mvp_loop_repair_plan_status": client_mvp_loop_repair_plan.get("plan_status"),
    "agent_client_mvp_loop_repair_plan_apply_allowed": client_mvp_loop_repair_plan.get("apply_allowed"),
    "agent_client_mvp_loop_repair_plan_hash": client_mvp_loop_repair_plan.get("plan_hash"),
    "agent_client_mvp_loop_repair_apply": str(client_mvp_loop_repair_apply_path),
    "agent_client_mvp_loop_repair_apply_status": client_mvp_loop_repair_apply.get("apply_status"),
    "agent_client_mvp_loop_repair_apply_approval_received": client_mvp_loop_repair_apply.get("approval_received"),
    "agent_client_mvp_loop_repair_apply_auto_applied": client_mvp_loop_repair_apply.get("auto_applied"),
    "agent_client_mvp_loop_repair_verify": str(client_mvp_loop_repair_verify_path),
    "agent_client_mvp_loop_repair_verify_status": client_mvp_loop_repair_verify.get("verification_status"),
    "agent_client_mvp_loop_repair_verify_test_id": client_mvp_loop_repair_verify.get("test_id"),
    "agent_client_mvp_loop_repair_verify_auto_saved": client_mvp_loop_repair_verify.get("auto_saved"),
    "agent_client_mvp_loop_verified_repair_review": str(client_mvp_loop_verified_repair_review_path),
    "agent_client_mvp_loop_verified_repair_records": client_mvp_loop_verified_repair_export.get("records"),
    "agent_client_mvp_loop_verified_repair_eligible_for_training": client_mvp_loop_verified_repair_export.get("eligible_for_training"),
    "agent_client_mvp_loop_verified_repair_review_summary": str(client_mvp_loop_verified_repair_review_summary_path),
    "agent_client_mvp_loop_verified_repair_review_records": client_mvp_loop_verified_repair_review.get("records"),
    "agent_client_mvp_loop_verified_repair_review_ready": client_mvp_loop_verified_repair_review.get("ready_for_human_review"),
    "agent_client_mvp_loop_report_ok": "BIBER MVP loop" in client_mvp_loop_report,
    "agent_client_mvp_loop_test_ok": client_mvp_loop.get("test_ok"),
    "agent_client_test_id": client_test_run.get("test_id"),
    "agent_client_test_ok": client_test_run.get("ok"),
    "agent_client_diagnosis_category": client_diagnosis.get("primary_category"),
    "agent_client_diagnosis_stack": client_diagnosis.get("detected_stack"),
    "xriq_context_height": summary.get("current_height"),
    "github": github_result,
}
write_artifact("summary.json", summary)
print(json.dumps(summary, sort_keys=True))
PY
