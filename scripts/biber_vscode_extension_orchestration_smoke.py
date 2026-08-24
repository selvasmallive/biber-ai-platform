#!/usr/bin/env python3
"""Exercise the VS Code extension-style BIBER orchestration plan request."""

from __future__ import annotations

import argparse
import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "https://api.beaverapi.com/v1"
ORCHESTRATION_PATH = "/agent/orchestration/plan"
CLIENT_NAME = "biber-vscode-extension-mvp"
CLIENT_USER_AGENT = "BIBER-VSCode-Extension-MVP/0.1"
DEFAULT_INSTRUCTION = "Plan one narrow safe BIBER MVP documentation improvement."
DEFAULT_CHANGED_PATH = "docs/BIBER_ONLY_WORKSPACE.md"


def redact(value: Any) -> Any:
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            if any(
                marker in key.lower()
                for marker in ("api_key", "apikey", "authorization", "token", "secret")
            ):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = redact(nested)
        return redacted
    return value


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def validate_extension_base_url(base_url: str) -> None:
    parsed = urllib.parse.urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("BIBER API base URL is not a valid absolute URL.")
    host = (parsed.hostname or "").lower()
    localhost = host in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "https" or (parsed.scheme == "http" and localhost):
        return
    raise ValueError("BIBER API URL must use HTTPS, except localhost development tunnels.")


def build_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def bounded_paths(paths: list[str], max_changed_paths: int) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = raw_path.strip().replace("\\", "/")
        if not path or path.startswith("/") or ".." in Path(path).parts:
            continue
        key = path.lower()
        if key in seen:
            continue
        seen.add(key)
        selected.append(path)
        if len(selected) >= max_changed_paths:
            break
    return selected


def build_orchestration_payload(
    *,
    instruction: str,
    changed_paths: list[str],
    model: str,
    max_prompt_chars: int,
    max_changed_paths: int,
    max_context_files: int,
    max_rag_results: int,
    max_scan_files: int,
) -> dict[str, Any]:
    return {
        "instruction": instruction[:max_prompt_chars],
        "changed_paths": bounded_paths(changed_paths, max_changed_paths),
        "test_id": None,
        "max_context_files": max_context_files,
        "max_rag_results": max_rag_results,
        "max_scan_files": max_scan_files,
        "client": {
            "name": CLIENT_NAME,
            "model": model,
            "sends_file_contents": False,
            "openai_mentor": False,
        },
    }


def summarize_orchestration(payload: dict[str, Any]) -> dict[str, Any]:
    repo_rag = object_value(payload.get("repo_rag"))
    repo_context = object_value(payload.get("repo_context"))
    agents = [object_value(item).get("id") for item in list_value(payload.get("agents"))]
    workflow_steps = [
        object_value(item).get("name")
        for item in list_value(payload.get("workflow_steps"))
    ]
    return redact(
        {
            "source": payload.get("source"),
            "ok": payload.get("ok"),
            "orchestration_version": payload.get("orchestration_version"),
            "agent_ids": [item for item in agents if item],
            "workflow_steps": [item for item in workflow_steps if item],
            "repo_rag_ok": repo_rag.get("ok"),
            "repo_rag_selected_count": len(list_value(repo_rag.get("selected_paths"))),
            "repo_context_selected_paths": repo_context.get("selected_paths", []),
            "required_gates": payload.get("required_gates", []),
            "hard_blockers": payload.get("hard_blockers", []),
            "safe_to_apply": payload.get("safe_to_apply"),
            "mentor_required": payload.get("mentor_required"),
            "mentor_optional": payload.get("mentor_optional"),
            "next_action_count": len(list_value(payload.get("next_actions"))),
        }
    )


def post_orchestration(
    *,
    base_url: str,
    api_key: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        build_url(base_url, ORCHESTRATION_PATH),
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": CLIENT_USER_AGENT,
            "X-BIBER-Client": CLIENT_NAME,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        response_body = response.read().decode("utf-8")
    response_payload = json.loads(response_body)
    if not isinstance(response_payload, dict):
        raise ValueError("Orchestration response must be a JSON object.")
    return response_payload


def request_has_no_file_contents(value: Any) -> bool:
    forbidden_keys = {"file_contents", "file_content", "source_text", "repo_file_text"}
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in forbidden_keys:
                return False
            if not request_has_no_file_contents(nested):
                return False
    if isinstance(value, list):
        return all(request_has_no_file_contents(item) for item in value)
    return True


def run_orchestration_check(
    *,
    base_url: str,
    api_key: str | None,
    instruction: str,
    changed_paths: list[str],
    model: str,
    max_prompt_chars: int,
    max_changed_paths: int,
    max_context_files: int,
    max_rag_results: int,
    max_scan_files: int,
    timeout_seconds: float,
    allow_missing_api_key: bool,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    request_sent = False
    response_payload: dict[str, Any] | None = None
    error: str | None = None

    request_payload = build_orchestration_payload(
        instruction=instruction,
        changed_paths=changed_paths,
        model=model,
        max_prompt_chars=max_prompt_chars,
        max_changed_paths=max_changed_paths,
        max_context_files=max_context_files,
        max_rag_results=max_rag_results,
        max_scan_files=max_scan_files,
    )

    try:
        validate_extension_base_url(base_url)
        checks.append(check(True, "base_url_allowed"))
    except ValueError as exc:
        checks.append(check(False, "base_url_allowed", str(exc)))
        error = str(exc)

    if not api_key:
        blockers.append("missing_api_key")
        checks.append(check(False, "api_key_configured"))
    else:
        checks.append(check(True, "api_key_configured"))

    checks.extend(
        [
            check(
                len(request_payload["instruction"]) <= max_prompt_chars,
                "instruction_bounded",
            ),
            check(
                len(request_payload["changed_paths"]) <= max_changed_paths,
                "changed_paths_bounded",
            ),
            check(
                request_payload["client"]["sends_file_contents"] is False,
                "client_declares_no_file_contents",
            ),
            check(
                request_payload["client"]["openai_mentor"] is False,
                "client_openai_mentor_disabled",
            ),
            check(request_has_no_file_contents(request_payload), "request_has_no_file_contents"),
            check(not request_payload.get("proposed_edits"), "no_proposed_edits_by_default"),
        ]
    )

    if error is None and api_key:
        try:
            request_sent = True
            response_payload = post_orchestration(
                base_url=base_url,
                api_key=api_key,
                payload=request_payload,
                timeout_seconds=timeout_seconds,
            )
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:400]}"
        except Exception as exc:  # noqa: BLE001 - artifact should preserve concise failure cause.
            error = str(exc)

    summary = summarize_orchestration(response_payload or {})
    required_gates = set(list_value(summary.get("required_gates")))
    checks.extend(
        [
            check(response_payload is not None, "orchestration_response_received"),
            check(summary.get("source") == "biber_agent_orchestration_plan", "source_is_orchestration_plan"),
            check(summary.get("ok") is True, "orchestration_ok"),
            check(summary.get("safe_to_apply") is False, "safe_to_apply_false"),
            check(summary.get("mentor_required") is False, "mentor_not_required"),
            check(summary.get("mentor_optional") is True, "mentor_optional"),
            check(
                "bounded_repo_context_before_model_edit" in required_gates,
                "gate_bounded_repo_context",
            ),
            check(
                "github_save_or_pr_only_when_explicitly_requested" in required_gates,
                "gate_github_explicit_only",
            ),
            check(
                "openai_mentor_optional_and_disabled_by_default" in required_gates,
                "gate_openai_mentor_optional",
            ),
        ]
    )

    ok = all(item["ok"] for item in checks) and not blockers and error is None
    status = "passed" if ok else ("blocked" if blockers and not request_sent else "failed")
    if allow_missing_api_key and blockers == ["missing_api_key"] and not request_sent:
        status = "blocked"

    return {
        "source": "biber_vscode_extension_orchestration_smoke",
        "ok": ok,
        "status": status,
        "api_required": True,
        "base_url": base_url,
        "orchestration_url": build_url(base_url, ORCHESTRATION_PATH),
        "client_name": CLIENT_NAME,
        "client_user_agent": CLIENT_USER_AGENT,
        "api_key_configured": bool(api_key),
        "request_sent": request_sent,
        "external_network_required": not base_url.startswith("http://127.0.0.1")
        and not base_url.startswith("http://localhost"),
        "github_request_sent": False,
        "gpu_required": False,
        "model_request_sent": False,
        "mentor_used": False,
        "training_allowed": False,
        "request_summary": {
            "instruction_chars": len(request_payload["instruction"]),
            "changed_paths": request_payload["changed_paths"],
            "max_context_files": request_payload["max_context_files"],
            "max_rag_results": request_payload["max_rag_results"],
            "max_scan_files": request_payload["max_scan_files"],
            "client": request_payload["client"],
        },
        "summary": summary,
        "checks": checks,
        "blockers": blockers,
        "error": error,
        "failed": [item for item in checks if not item["ok"]],
    }


def mock_orchestration_response() -> dict[str, Any]:
    return {
        "source": "biber_agent_orchestration_plan",
        "ok": True,
        "orchestration_version": "agent-orchestration-plan-v1",
        "instruction": DEFAULT_INSTRUCTION,
        "agents": [
            {"id": "planner", "mutation_allowed": False},
            {"id": "repo_retriever", "mutation_allowed": False},
            {"id": "coder", "mutation_allowed": False},
            {"id": "edit_guard", "mutation_allowed": False},
            {"id": "test_diagnoser", "mutation_allowed": False},
            {"id": "reviewer", "mutation_allowed": False},
            {"id": "git_saver", "mutation_allowed": False},
        ],
        "workflow_steps": [
            {"name": "repo_rag_search", "status": "ok"},
            {"name": "repo_context_plan", "status": "ok"},
            {"name": "model_edit_proposal", "status": "next"},
            {"name": "workspace_edit_plan", "status": "not_requested"},
            {"name": "test_and_diagnose", "status": "not_requested"},
        ],
        "repo_rag": {"ok": True, "selected_paths": [DEFAULT_CHANGED_PATH]},
        "repo_context": {"selected_paths": [DEFAULT_CHANGED_PATH]},
        "edit_plan": None,
        "test_plan": None,
        "required_gates": [
            "bounded_repo_context_before_model_edit",
            "no_secret_paths_in_context_or_edits",
            "github_save_or_pr_only_when_explicitly_requested",
            "openai_mentor_optional_and_disabled_by_default",
        ],
        "hard_blockers": [],
        "safe_to_apply": False,
        "mentor_required": False,
        "mentor_optional": True,
        "next_actions": ["Send bounded context to the local model."],
        "summary": "Mock orchestration plan; no model call or mutation.",
    }


class MockHandler(BaseHTTPRequestHandler):
    received: dict[str, Any] = {}

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler method name.
        if self.path != "/v1/agent/orchestration/plan":
            self.send_response(404)
            self.end_headers()
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        MockHandler.received = {
            "authorization": self.headers.get("Authorization"),
            "user_agent": self.headers.get("User-Agent"),
            "client": self.headers.get("X-BIBER-Client"),
            "content_type": self.headers.get("Content-Type"),
            "payload": json.loads(body.decode("utf-8")),
        }
        if self.headers.get("Authorization") != "Bearer mock-biber-api-key":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"detail":"unauthorized"}')
            return
        response = mock_orchestration_response()
        response["instruction"] = MockHandler.received["payload"].get("instruction")
        body_out = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body_out)))
        self.end_headers()
        self.wfile.write(body_out)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature.
        return


def run_mock_orchestration_check(timeout_seconds: float) -> dict[str, Any]:
    MockHandler.received = {}
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = run_orchestration_check(
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key="mock-biber-api-key",
            instruction=DEFAULT_INSTRUCTION,
            changed_paths=[DEFAULT_CHANGED_PATH],
            model="biber-dev-core-v1",
            max_prompt_chars=4000,
            max_changed_paths=20,
            max_context_files=8,
            max_rag_results=8,
            max_scan_files=2000,
            timeout_seconds=timeout_seconds,
            allow_missing_api_key=False,
        )
        received = MockHandler.received
        header_checks = [
            check(
                received.get("user_agent") == CLIENT_USER_AGENT,
                "mock_received_client_user_agent",
            ),
            check(
                received.get("client") == CLIENT_NAME,
                "mock_received_client_identity_header",
            ),
            check(
                received.get("content_type") == "application/json",
                "mock_received_json_content_type",
            ),
        ]
        result["checks"].extend(header_checks)
        result["failed"] = [item for item in result["checks"] if not item["ok"]]
        result["ok"] = result["ok"] and not result["failed"]
        result["status"] = "passed" if result["ok"] else "failed"
        result["mock_received_headers_verified"] = result["ok"]
        return result
    finally:
        server.shutdown()
        server.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("BIBER_OPENAI_BASE_URL") or DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=os.getenv("BIBER_API_KEY"))
    parser.add_argument("--model", default=os.getenv("BIBER_MODEL") or "biber-dev-core-v1")
    parser.add_argument("--instruction", default=DEFAULT_INSTRUCTION)
    parser.add_argument(
        "--changed-path",
        action="append",
        dest="changed_paths",
        default=[],
        help="Repo-relative changed path hint. Can be repeated.",
    )
    parser.add_argument("--max-prompt-chars", type=int, default=4000)
    parser.add_argument("--max-changed-paths", type=int, default=20)
    parser.add_argument("--max-context-files", type=int, default=8)
    parser.add_argument("--max-rag-results", type=int, default=8)
    parser.add_argument("--max-scan-files", type=int, default=2000)
    parser.add_argument("--output", help="Optional JSON artifact path.")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--mock", action="store_true", help="Use a local mock BIBER API.")
    parser.add_argument(
        "--allow-missing-api-key",
        action="store_true",
        help="Write a blocked artifact and exit 0 when no API key is configured.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changed_paths = args.changed_paths or [DEFAULT_CHANGED_PATH]
    result = (
        run_mock_orchestration_check(args.timeout_seconds)
        if args.mock
        else run_orchestration_check(
            base_url=args.base_url,
            api_key=args.api_key,
            instruction=args.instruction,
            changed_paths=changed_paths,
            model=args.model,
            max_prompt_chars=args.max_prompt_chars,
            max_changed_paths=args.max_changed_paths,
            max_context_files=args.max_context_files,
            max_rag_results=args.max_rag_results,
            max_scan_files=args.max_scan_files,
            timeout_seconds=args.timeout_seconds,
            allow_missing_api_key=args.allow_missing_api_key,
        )
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["ok"] or (
        args.allow_missing_api_key and result["blockers"] == ["missing_api_key"]
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
