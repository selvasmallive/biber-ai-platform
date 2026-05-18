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
GITHUB_MODE="${BIBER_AGENT_SMOKE_GITHUB:-skip}"

mkdir -p "$ARTIFACT_DIR"

export API_BASE_URL
export API_KEY
export ARTIFACT_DIR
export CHAT_MAX_TOKENS
export GITHUB_MODE
export SMOKE_ID

"$PYTHON_BIN" <<'PY'
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


api_base_url = os.environ["API_BASE_URL"].rstrip("/")
api_key = os.environ["API_KEY"]
artifact_dir = Path(os.environ["ARTIFACT_DIR"])
chat_max_tokens = int(os.environ["CHAT_MAX_TOKENS"])
github_mode = os.environ["GITHUB_MODE"].strip().lower()
smoke_id = os.environ["SMOKE_ID"]


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
    "chat_content_prefix": chat.get("content", "")[:120],
    "file_edit_dry_run": edit.get("dry_run"),
    "test_id": test_run.get("test_id"),
    "test_ok": test_run.get("ok"),
    "github": github_result,
}
write_artifact("summary.json", summary)
print(json.dumps(summary, sort_keys=True))
PY
