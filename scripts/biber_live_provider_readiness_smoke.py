#!/usr/bin/env python3
"""Smoke-test live provider readiness against a localhost /v1/models mock."""

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


def make_handler(requests: list[dict[str, Any]]) -> type[BaseHTTPRequestHandler]:
    class MockModelsHandler(BaseHTTPRequestHandler):
        server_version = "BiberReadinessSmoke/1.0"

        def log_message(self, format: str, *args: object) -> None:
            return

        def do_GET(self) -> None:
            requests.append(
                {
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                }
            )
            if self.path != "/v1/models":
                self.send_error(404, "unexpected path")
                return
            payload = {
                "object": "list",
                "data": [
                    {"id": "biber-dev-core-v1", "object": "model"},
                    {"id": "qwen-smoke", "object": "model"},
                ],
            }
            data = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return MockModelsHandler


def run_readiness(
    *,
    repo_root: Path,
    base_url: str,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["BIBER_LOCAL_OPENAI_API_KEY"] = "readiness-smoke-token"
    with tempfile.TemporaryDirectory(prefix="biber-live-readiness-pycache-") as tmp:
        env["PYTHONPYCACHEPREFIX"] = tmp
        return subprocess.run(
            [
                sys.executable,
                str(repo_root / "scripts" / "biber_live_provider_readiness.py"),
                "--base-url",
                base_url,
                "--model",
                "qwen-smoke",
                "--require-model",
                "--require-ready",
                "--timeout-seconds",
                "10",
            ],
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
        completed = run_readiness(repo_root=repo_root, base_url=base_url)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    if completed.returncode != 0:
        raise RuntimeError(
            "readiness command failed: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("readiness command did not print a JSON object")
    if len(requests) != 1:
        raise RuntimeError(f"expected exactly one mock request, got {len(requests)}")
    request = requests[0]
    summary = {
        "source": "biber_live_provider_readiness_smoke",
        "ok": (
            payload.get("ok") is True
            and payload.get("endpoint_reachable") is True
            and payload.get("models_endpoint_ok") is True
            and payload.get("requested_model") == "qwen-smoke"
            and payload.get("model_available") is True
            and payload.get("repair_request_sent") is False
            and payload.get("chat_completion_sent") is False
            and payload.get("mentor_used") is False
            and payload.get("training_allowed") is False
            and request.get("path") == "/v1/models"
            and request.get("authorization") == "Bearer readiness-smoke-token"
        ),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "request_path": request.get("path"),
        "auth_header_present": bool(request.get("authorization")),
        "requested_model": payload.get("requested_model"),
        "model_available": payload.get("model_available"),
        "available_model_count": payload.get("available_model_count"),
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a localhost /v1/models mock and verify live provider readiness."
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
