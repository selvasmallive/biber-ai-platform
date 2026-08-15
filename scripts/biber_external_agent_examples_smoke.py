#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXAMPLE = ROOT / "examples" / "external_agent" / "python_minimal_client.py"


class _Recorder:
    path = ""
    authorization = ""
    body: dict[str, Any] = {}


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8")
        _Recorder.path = self.path
        _Recorder.authorization = self.headers.get("Authorization", "")
        _Recorder.body = json.loads(raw_body)
        payload = {
            "id": "chatcmpl-example-smoke",
            "object": "chat.completion",
            "model": _Recorder.body.get("model"),
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "BIBER example client smoke passed.",
                    },
                }
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    if not PYTHON_EXAMPLE.exists():
        print(f"Missing Python example: {PYTHON_EXAMPLE}", file=sys.stderr)
        return 1
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        env = os.environ.copy()
        env["BIBER_API_KEY"] = "example-user-key"
        command = [
            sys.executable,
            str(PYTHON_EXAMPLE),
            "--base-url",
            f"http://127.0.0.1:{server.server_port}/v1",
            "--model",
            "biber-dev-core-v1",
            "--message",
            "Return one example smoke sentence.",
            "--max-tokens",
            "32",
            "--temperature",
            "0",
        ]
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    finally:
        server.shutdown()
        server.server_close()
    checks = {
        "exit_ok": completed.returncode == 0,
        "stdout_ok": "BIBER example client smoke passed." in completed.stdout,
        "path_ok": _Recorder.path == "/v1/chat/completions",
        "auth_ok": _Recorder.authorization == "Bearer example-user-key",
        "model_ok": _Recorder.body.get("model") == "biber-dev-core-v1",
        "message_ok": _Recorder.body.get("messages")
        == [{"role": "user", "content": "Return one example smoke sentence."}],
        "stream_ok": _Recorder.body.get("stream") is False,
        "mentor_ok": _Recorder.body.get("use_mentor") is False,
    }
    result = {
        "source": "biber_external_agent_examples_smoke",
        "ok": all(checks.values()),
        "checks": checks,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
