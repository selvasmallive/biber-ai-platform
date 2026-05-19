#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
API_KEY_ENV_NAMES = ("BIBER_API_KEY", "BIBER_TEST_API_KEY", "BIBER_DEMO_API_KEY")


class BiberAgentClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body_snippet: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body_snippet = body_snippet


def build_url(
    base_url: str,
    path: str,
    query: Mapping[str, object | None] | None = None,
) -> str:
    clean_base_url = base_url.rstrip("/")
    clean_path = path if path.startswith("/") else f"/{path}"
    query_items = {
        key: value
        for key, value in (query or {}).items()
        if value is not None
    }
    if not query_items:
        return f"{clean_base_url}{clean_path}"
    return f"{clean_base_url}{clean_path}?{urllib.parse.urlencode(query_items)}"


def resolve_api_key(cli_api_key: str | None = None) -> str:
    if cli_api_key:
        return cli_api_key
    for env_name in API_KEY_ENV_NAMES:
        api_key = os.environ.get(env_name)
        if api_key:
            return api_key
    raise BiberAgentClientError(
        "API key required. Set BIBER_API_KEY or pass --api-key."
    )


def request_json(
    *,
    base_url: str,
    api_key: str,
    path: str,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
    query: Mapping[str, object | None] | None = None,
    timeout_seconds: float = 180.0,
) -> dict[str, Any]:
    data = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-API-Key": api_key,
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        build_url(base_url, path, query),
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        snippet = body[:500]
        raise BiberAgentClientError(
            f"{path} returned HTTP {exc.code}: {snippet}",
            status_code=int(exc.code),
            body_snippet=snippet,
        ) from exc
    except urllib.error.URLError as exc:
        raise BiberAgentClientError(f"{path} request failed: {exc}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BiberAgentClientError(f"{path} returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise BiberAgentClientError(f"{path} returned non-object JSON")
    return parsed


def fetch_capabilities(
    *,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/agent/capabilities",
        timeout_seconds=timeout_seconds,
    )


def create_agent_session(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/agent/sessions",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def list_agent_sessions(
    *,
    base_url: str,
    api_key: str,
    limit: int | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/agent/sessions",
        query={"limit": limit},
        timeout_seconds=timeout_seconds,
    )


def get_agent_session(
    *,
    base_url: str,
    api_key: str,
    session_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    quoted_id = urllib.parse.quote(session_id, safe="")
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path=f"/v1/agent/sessions/{quoted_id}",
        timeout_seconds=timeout_seconds,
    )


def require_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def require_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def get_preset(capabilities: Mapping[str, Any], preset_id: str) -> dict[str, Any]:
    for preset in require_list(capabilities.get("presets")):
        if isinstance(preset, dict) and preset.get("id") == preset_id:
            return preset
    raise BiberAgentClientError(f"Unknown preset: {preset_id}")


def build_session_payload(
    *,
    capabilities: Mapping[str, Any],
    preset_id: str,
    instruction: str,
    model: str | None = None,
    language: str | None = None,
    task_type: str | None = None,
    repo_context_paths: list[str] | None = None,
    test_id: str | None = None,
    no_test: bool = False,
    include_xriq_context: bool | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    preset = get_preset(capabilities, preset_id)
    template = require_mapping(preset.get("request_template")).copy()
    template["instruction"] = instruction
    if model:
        template["model"] = model
    if language:
        template["language"] = language
    if task_type:
        template["task_type"] = task_type
    if repo_context_paths is not None:
        template["repo_context_paths"] = repo_context_paths
    if no_test:
        template["test_id"] = None
    elif isinstance(test_id, str):
        template["test_id"] = test_id
    if include_xriq_context is not None:
        template["include_xriq_context"] = include_xriq_context
    if max_tokens is not None:
        template["max_tokens"] = max_tokens
    return template


def format_capabilities_summary(payload: Mapping[str, Any]) -> str:
    features = require_mapping(payload.get("features"))
    test_runner = require_mapping(features.get("test_runner"))
    tests = [
        str(command.get("test_id"))
        for command in require_list(test_runner.get("commands"))
        if isinstance(command, dict) and command.get("test_id")
    ]
    presets = [
        str(preset.get("id"))
        for preset in require_list(payload.get("presets"))
        if isinstance(preset, dict) and preset.get("id")
    ]
    xriq = require_mapping(features.get("xriq_private_devnet"))
    mentor = require_mapping(features.get("openai_mentor"))
    lines = [
        "BIBER agent capabilities",
        f"service: {payload.get('service', '-')}",
        f"version: {payload.get('version', '-')}",
        f"default_model: {payload.get('default_model', '-')}",
        f"presets: {', '.join(presets) if presets else '-'}",
        f"tests: {', '.join(tests) if tests else '-'}",
        f"xriq_context: {bool(xriq.get('context_supported'))}",
        f"mentor_configured: {bool(mentor.get('configured'))}",
    ]
    return "\n".join(lines)


def format_session_summary(payload: Mapping[str, Any]) -> str:
    steps = [
        str(step.get("name"))
        for step in require_list(payload.get("steps"))
        if isinstance(step, dict) and step.get("name")
    ]
    return "\n".join(
        [
            "BIBER agent session",
            f"id: {payload.get('id', '-')}",
            f"model: {payload.get('model', '-')}",
            f"mentor_used: {payload.get('mentor_used', False)}",
            f"steps: {', '.join(steps) if steps else '-'}",
            f"artifact_path: {payload.get('artifact_path', '-')}",
        ]
    )


def format_session_list_summary(payload: Mapping[str, Any]) -> str:
    sessions = [
        item
        for item in require_list(payload.get("sessions"))
        if isinstance(item, dict)
    ]
    lines = [f"BIBER agent sessions ({len(sessions)})"]
    for session in sessions:
        steps = require_list(session.get("steps"))
        lines.append(
            " ".join(
                [
                    f"id={session.get('id', '-')}",
                    f"model={session.get('model', '-')}",
                    f"steps={','.join(str(step) for step in steps) if steps else '-'}",
                    f"artifact={session.get('artifact_path', '-')}",
                ]
            )
        )
    return "\n".join(lines)


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BIBER_API_BASE_URL", DEFAULT_BASE_URL),
        help="BIBER API base URL. Defaults to BIBER_API_BASE_URL or localhost.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="BIBER API key. Prefer BIBER_API_KEY so it is not visible in shell history.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument(
        "--json",
        action="store_true",
        dest="print_json",
        help="Print full JSON instead of a concise summary.",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal stdlib client for BIBER agent MVP workflows."
    )
    add_common_args(parser)
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("capabilities", help="Discover BIBER agent capabilities.")

    session = subparsers.add_parser(
        "create-session",
        help="Create a tracked agent session from a discovered preset.",
    )
    session.add_argument("--preset", default="default_coding_session")
    session.add_argument("--instruction", required=True)
    session.add_argument("--model")
    session.add_argument("--language")
    session.add_argument("--task-type")
    session.add_argument("--repo-context", action="append", default=None)
    session.add_argument("--test-id")
    session.add_argument("--no-test", action="store_true")
    session.add_argument("--include-xriq-context", action="store_true")
    session.add_argument("--max-tokens", type=int)

    list_sessions = subparsers.add_parser(
        "list-sessions",
        help="List recent persisted agent sessions.",
    )
    list_sessions.add_argument("--limit", type=int, default=10)

    get_session = subparsers.add_parser(
        "get-session",
        help="Load one persisted agent session by id.",
    )
    get_session.add_argument("session_id")

    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "capabilities"
    return args


def run(args: argparse.Namespace) -> str:
    api_key = resolve_api_key(args.api_key)
    base_url = args.base_url.rstrip("/")
    if args.command == "capabilities":
        capabilities = fetch_capabilities(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(capabilities, indent=2, sort_keys=True)
            if args.print_json
            else format_capabilities_summary(capabilities)
        )
    if args.command == "create-session":
        capabilities = fetch_capabilities(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
        include_xriq = True if args.include_xriq_context else None
        payload = build_session_payload(
            capabilities=capabilities,
            preset_id=args.preset,
            instruction=args.instruction,
            model=args.model,
            language=args.language,
            task_type=args.task_type,
            repo_context_paths=args.repo_context,
            test_id=args.test_id,
            no_test=args.no_test,
            include_xriq_context=include_xriq,
            max_tokens=args.max_tokens,
        )
        session = create_agent_session(
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(session, indent=2, sort_keys=True)
            if args.print_json
            else format_session_summary(session)
        )
    if args.command == "list-sessions":
        sessions = list_agent_sessions(
            base_url=base_url,
            api_key=api_key,
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(sessions, indent=2, sort_keys=True)
            if args.print_json
            else format_session_list_summary(sessions)
        )
    if args.command == "get-session":
        session = get_agent_session(
            base_url=base_url,
            api_key=api_key,
            session_id=args.session_id,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(session, indent=2, sort_keys=True)
            if args.print_json
            else format_session_summary(session)
        )
    raise BiberAgentClientError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    try:
        output = run(parse_args(argv))
    except BiberAgentClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
