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
GITHUB_MODE="${BIBER_AGENT_SMOKE_GITHUB:-skip}"

mkdir -p "$ARTIFACT_DIR"

export API_BASE_URL
export API_KEY
export ARTIFACT_DIR
export CHAT_MAX_TOKENS
export CLIENT_SESSION_MAX_TOKENS
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
github_mode = os.environ["GITHUB_MODE"].strip().lower()
smoke_id = os.environ["SMOKE_ID"]
script_dir = Path(os.environ["SCRIPT_DIR"])


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
    save_payload = {
        "target": {
            "path": f"generated/biber-agent-smoke-{smoke_id}.txt",
            "branch": branch,
            "base_branch": "main",
            "create_branch_if_missing": True,
            "commit_message": "Save BIBER agent smoke artifact",
        },
        "content": f"BIBER agent smoke {smoke_id}\n",
    }
    _, save = request_json("POST", "/v1/save/github", "github-save.json", save_payload)
    pr_payload = {
        "head": branch,
        "base": "main",
        "title": "BIBER agent smoke",
        "body": "Generated by the BIBER agent smoke script.",
        "draft": True,
    }
    _, pull_request = request_json(
        "POST",
        "/v1/github/pull-request",
        "github-pr.json",
        pr_payload,
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
    "xriq_context_height": summary.get("current_height"),
    "github": github_result,
}
write_artifact("summary.json", summary)
print(json.dumps(summary, sort_keys=True))
PY
