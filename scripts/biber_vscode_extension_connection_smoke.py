#!/usr/bin/env python3
"""Exercise the VS Code extension-style BIBER API connection test."""

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
CAPABILITIES_PATH = "/agent/capabilities"
CLIENT_NAME = "biber-vscode-extension-mvp"
CLIENT_USER_AGENT = "BIBER-VSCode-Extension-MVP/0.1"


def redact(value: Any) -> Any:
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            if any(marker in key.lower() for marker in ("api_key", "apikey", "authorization", "token", "secret")):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = redact(nested)
        return redacted
    return value


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def summarize_capabilities(payload: dict[str, Any]) -> dict[str, Any]:
    features = object_value(payload.get("features"))
    external_agent = object_value(features.get("external_agent_api"))
    protections = object_value(external_agent.get("server_side_protections"))
    endpoints = object_value(payload.get("endpoints"))
    return redact(
        {
            "service": payload.get("service"),
            "version": payload.get("version"),
            "default_model": payload.get("default_model"),
            "capabilities_endpoint": endpoints.get("agent_capabilities"),
            "server_side_protections": {
                "api_guard_enabled": protections.get("api_guard_enabled"),
                "scope": protections.get("scope"),
                "identity": protections.get("identity"),
                "max_request_bytes": protections.get("max_request_bytes"),
                "rate_limit_requests_per_minute": protections.get(
                    "rate_limit_requests_per_minute"
                ),
                "client_side_guards_are_not_trusted": protections.get(
                    "client_side_guards_are_not_trusted"
                ),
            },
        }
    )


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


def fetch_capabilities(base_url: str, api_key: str, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(
        build_url(base_url, CAPABILITIES_PATH),
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": CLIENT_USER_AGENT,
            "X-BIBER-Client": CLIENT_NAME,
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise ValueError("Capabilities response must be a JSON object.")
    return payload


def check(condition: bool, name: str, detail: str = "") -> dict[str, Any]:
    return {"name": name, "ok": bool(condition), "detail": detail}


def run_connection_check(
    *,
    base_url: str,
    api_key: str | None,
    timeout_seconds: float,
    allow_missing_api_key: bool,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []
    request_sent = False
    payload: dict[str, Any] | None = None
    error: str | None = None

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

    if error is None and api_key:
        try:
            request_sent = True
            payload = fetch_capabilities(base_url, api_key, timeout_seconds)
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:400]}"
        except Exception as exc:  # noqa: BLE001 - artifact should preserve concise failure cause.
            error = str(exc)

    summary = summarize_capabilities(payload or {})
    protections = object_value(summary.get("server_side_protections"))
    checks.extend(
        [
            check(payload is not None, "capabilities_response_received"),
            check(summary.get("service") == "biber-agent", "service_is_biber_agent"),
            check(
                protections.get("scope") == "/v1/*",
                "server_guard_scope_v1",
            ),
            check(
                protections.get("client_side_guards_are_not_trusted") is True,
                "client_side_guards_not_trusted",
            ),
            check(
                protections.get("api_guard_enabled") is True,
                "api_guard_enabled",
            ),
        ]
    )

    ok = all(item["ok"] for item in checks) and not blockers and error is None
    status = "passed" if ok else ("blocked" if blockers and not request_sent else "failed")
    if allow_missing_api_key and blockers == ["missing_api_key"] and not request_sent:
        status = "blocked"

    return {
        "source": "biber_vscode_extension_connection_smoke",
        "ok": ok,
        "status": status,
        "api_required": True,
        "base_url": base_url,
        "capabilities_url": build_url(base_url, CAPABILITIES_PATH),
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
        "summary": summary,
        "checks": checks,
        "blockers": blockers,
        "error": error,
        "failed": [item for item in checks if not item["ok"]],
    }


def mock_capabilities() -> dict[str, Any]:
    return {
        "service": "biber-agent",
        "version": "mvp-v1",
        "default_model": "biber-dev-core-v1",
        "endpoints": {"agent_capabilities": "GET /v1/agent/capabilities"},
        "features": {
            "external_agent_api": {
                "server_side_protections": {
                    "api_guard_enabled": True,
                    "scope": "/v1/*",
                    "identity": "api_key_hash_or_client_ip",
                    "max_request_bytes": 1048576,
                    "rate_limit_requests_per_minute": 120,
                    "client_side_guards_are_not_trusted": True,
                }
            }
        },
    }


class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - stdlib handler method name.
        if self.path != "/v1/agent/capabilities":
            self.send_response(404)
            self.end_headers()
            return
        if self.headers.get("Authorization") != "Bearer mock-biber-api-key":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"detail":"unauthorized"}')
            return
        body = json.dumps(mock_capabilities()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature.
        return


def run_mock_connection_check(timeout_seconds: float) -> dict[str, Any]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        return run_connection_check(
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key="mock-biber-api-key",
            timeout_seconds=timeout_seconds,
            allow_missing_api_key=False,
        )
    finally:
        server.shutdown()
        server.server_close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("BIBER_OPENAI_BASE_URL") or DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=os.getenv("BIBER_API_KEY"))
    parser.add_argument("--output", help="Optional JSON artifact path.")
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--mock", action="store_true", help="Use a local mock BIBER API.")
    parser.add_argument(
        "--allow-missing-api-key",
        action="store_true",
        help="Write a blocked artifact and exit 0 when no API key is configured.",
    )
    args = parser.parse_args()

    result = (
        run_mock_connection_check(args.timeout_seconds)
        if args.mock
        else run_connection_check(
            base_url=args.base_url,
            api_key=args.api_key,
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
