#!/usr/bin/env python3
"""Smoke-test the BIBER local OpenAI-compatible provider wrapper."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_biber_command_request() -> dict[str, Any]:
    return {
        "source": "biber_local_model_command_request",
        "repair_loop_version": "mvp-v1",
        "model": "biber-dev-core-v1",
        "mentor_used": False,
        "training_allowed": False,
        "api_required": False,
        "chat_payload": {
            "model": "biber-dev-core-v1",
            "messages": [
                {
                    "role": "user",
                    "content": "Return strict JSON edits for src/app.py.",
                }
            ],
            "temperature": 0.2,
            "max_tokens": 96,
        },
    }


def make_handler(requests: list[dict[str, Any]]) -> type[BaseHTTPRequestHandler]:
    class MockOpenAIHandler(BaseHTTPRequestHandler):
        server_version = "BiberLocalProviderSmoke/1.0"

        def log_message(self, format: str, *args: object) -> None:
            return

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                self.send_error(400, "invalid json")
                return
            requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "payload": payload,
                }
            )
            if self.path != "/v1/chat/completions":
                self.send_error(404, "unexpected path")
                return
            content = json.dumps(
                {
                    "edits": [
                        {
                            "path": "src/app.py",
                            "old_text": "return 1",
                            "new_text": "return 2",
                        }
                    ]
                },
                sort_keys=True,
            )
            response = {
                "id": "biber-local-openai-provider-smoke",
                "object": "chat.completion",
                "model": payload.get("model"),
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 9},
            }
            data = json.dumps(response).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return MockOpenAIHandler


def run_provider(
    *,
    repo_root: Path,
    base_url: str,
    request_payload: dict[str, Any],
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["BIBER_LOCAL_OPENAI_API_KEY"] = "smoke-token"
    with tempfile.TemporaryDirectory(prefix="biber-local-openai-provider-pycache-") as tmp:
        env["PYTHONPYCACHEPREFIX"] = tmp
        return subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "biber_local_openai_provider.py"),
                "--base-url",
                base_url,
                "--model",
                "qwen-smoke",
                "--timeout-seconds",
                "10",
            ],
            input=json.dumps(request_payload),
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )


def run_provider_dry_run(
    *,
    repo_root: Path,
    base_url: str,
    request_payload: dict[str, Any],
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("BIBER_MODEL_REGISTRY_JSON", None)
    env.pop("BIBER_LOCAL_OPENAI_MODEL", None)
    env.pop("BIBER_CANDIDATE_MODEL_ENABLED", None)
    env["BIBER_LOCAL_MODEL_NAME"] = "qwen-stable-registry-smoke"
    with tempfile.TemporaryDirectory(
        prefix="biber-local-openai-provider-dry-run-pycache-"
    ) as tmp:
        env["PYTHONPYCACHEPREFIX"] = tmp
        return subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "biber_local_openai_provider.py"),
                "--base-url",
                base_url,
                "--timeout-seconds",
                "10",
                "--dry-run",
            ],
            input=json.dumps(request_payload),
            capture_output=True,
            check=False,
            env=env,
            text=True,
        )


def run_smoke() -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    requests: list[dict[str, Any]] = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(requests))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        base_url = f"http://{host}:{port}/v1"
        request_payload = build_biber_command_request()
        completed = run_provider(
            repo_root=repo_root,
            base_url=base_url,
            request_payload=request_payload,
        )
        dry_run_completed = run_provider_dry_run(
            repo_root=repo_root,
            base_url=base_url,
            request_payload=request_payload,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    if completed.returncode != 0:
        raise RuntimeError(
            "provider wrapper failed: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    if dry_run_completed.returncode != 0:
        raise RuntimeError(
            "provider wrapper dry run failed: "
            f"stdout={dry_run_completed.stdout!r} stderr={dry_run_completed.stderr!r}"
        )
    output = json.loads(completed.stdout)
    dry_run_output = json.loads(dry_run_completed.stdout)
    if not isinstance(output, dict):
        raise RuntimeError("provider wrapper did not return a JSON object")
    if not isinstance(dry_run_output, dict):
        raise RuntimeError("provider wrapper dry run did not return a JSON object")
    if len(requests) != 1:
        raise RuntimeError(f"expected exactly one mock request, got {len(requests)}")
    recorded = requests[0]
    provider_payload = recorded["payload"]
    content = json.loads(str(output.get("content") or "{}"))
    edit_paths = [
        str(edit.get("path"))
        for edit in content.get("edits", [])
        if isinstance(edit, dict)
    ]
    dry_run_payload = json.loads(str(dry_run_output.get("content") or "{}"))
    dry_selection = dry_run_output.get("provider_selection")
    if not isinstance(dry_selection, dict):
        dry_selection = {}
    summary = {
        "source": "biber_local_openai_provider_http_smoke",
        "ok": (
            recorded.get("path") == "/v1/chat/completions"
            and recorded.get("authorization") == "Bearer smoke-token"
            and provider_payload.get("model") == "qwen-smoke"
            and provider_payload.get("stream") is False
            and output.get("provider") == "openai-compatible-local"
            and output.get("mentor_used") is False
            and output.get("training_allowed") is False
            and output.get("api_required") is False
            and edit_paths == ["src/app.py"]
            and dry_run_payload.get("model") == "qwen-stable-registry-smoke"
            and dry_selection.get("logical_model") == "biber-dev-core-v1"
            and dry_selection.get("provider_model") == "qwen-stable-registry-smoke"
            and dry_selection.get("selection_source") == "default:stable-model"
        ),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "request_path": recorded.get("path"),
        "request_model": provider_payload.get("model"),
        "response_model": output.get("response_model"),
        "auth_header_present": bool(recorded.get("authorization")),
        "content_edit_paths": edit_paths,
        "registry_resolution_model": dry_run_payload.get("model"),
        "registry_resolution_source": dry_selection.get("selection_source"),
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a localhost mock /v1/chat/completions endpoint and verify "
            "scripts/biber_local_openai_provider.py against it."
        )
    )
    parser.add_argument("--output", help="Optional path for the smoke summary JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_smoke()
    if args.output:
        write_json(Path(args.output), summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
