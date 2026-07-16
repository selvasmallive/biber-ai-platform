#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Sequence


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
API_KEY_ENV_NAMES = ("BIBER_API_KEY", "BIBER_TEST_API_KEY", "BIBER_DEMO_API_KEY")
DEFAULT_REPAIR_INSTRUCTION = (
    "Repair the failed BIBER MVP loop using the smallest safe code change. "
    "Use the selected repository context, diagnosis, and relevant test output. "
    "Return a concise repair plan with exact file edit suggestions where possible, "
    "then name the test that should be rerun."
)


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


def plan_repo_context(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/repo/context/plan",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def plan_workspace_edit(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/files/edit/plan",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def apply_workspace_edit_plan(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/files/edit/apply",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def list_test_commands(
    *,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/tests",
        timeout_seconds=timeout_seconds,
    )


def run_allowlisted_test(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/tests/run",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def chat_with_biber(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/chat",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def diagnose_test_failure(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/tests/diagnose",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def validate_local_target_root(target_root: Path) -> Path:
    try:
        resolved = target_root.resolve()
    except OSError as exc:
        raise BiberAgentClientError(
            f"Repair edit target root could not be resolved: {target_root}"
        ) from exc
    if not resolved.is_dir():
        raise BiberAgentClientError(
            f"Repair edit target root is not a directory: {resolved}"
        )
    return resolved


def _run_git_local_target(
    target_root: Path,
    args: Sequence[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(target_root), *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    )


def _git_output_or_none(target_root: Path, args: Sequence[str]) -> str | None:
    completed = _run_git_local_target(target_root, args)
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return output or None


def git_status_local_target(target_root: Path) -> dict[str, Any]:
    root = validate_local_target_root(target_root)
    try:
        inside = _run_git_local_target(root, ["rev-parse", "--is-inside-work-tree"])
    except FileNotFoundError:
        return {
            "available": False,
            "reason": "git_unavailable",
            "target_root": str(root),
        }
    except (subprocess.SubprocessError, OSError) as exc:
        return {
            "available": False,
            "reason": "git_status_failed",
            "target_root": str(root),
            "error": str(exc),
        }
    if inside.returncode != 0 or inside.stdout.strip().lower() != "true":
        return {
            "available": False,
            "reason": "not_git_repo",
            "target_root": str(root),
        }
    try:
        branch = _git_output_or_none(root, ["branch", "--show-current"])
        head = _git_output_or_none(root, ["rev-parse", "--short", "HEAD"])
        status = _run_git_local_target(root, ["status", "--short"])
    except (subprocess.SubprocessError, OSError) as exc:
        return {
            "available": False,
            "reason": "git_status_failed",
            "target_root": str(root),
            "error": str(exc),
        }
    status_lines = (
        [line.rstrip() for line in status.stdout.splitlines() if line.strip()]
        if status.returncode == 0
        else []
    )
    return {
        "available": True,
        "target_root": str(root),
        "branch": branch,
        "head": head,
        "dirty": bool(status_lines),
        "status_short": status_lines,
        "modified_count": sum(1 for line in status_lines if not line.startswith("??")),
        "untracked_count": sum(1 for line in status_lines if line.startswith("??")),
    }


def ensure_local_src_import_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_root = repo_root / "src"
    if src_root.is_dir() and str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


def local_workspace_edit_settings(target_root: Path) -> object:
    ensure_local_src_import_path()
    from dataclasses import replace

    from biber_api.config import get_settings

    return replace(get_settings(), repo_context_root=str(target_root))


def plan_workspace_edit_local_target(
    *,
    target_root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ensure_local_src_import_path()
    from biber_api.workspace_edit import (
        WorkspaceEditConfigurationError,
        WorkspaceEditError,
        plan_workspace_edits,
    )

    settings = local_workspace_edit_settings(validate_local_target_root(target_root))
    max_files = int(payload.get("max_files") or 8)
    try:
        return plan_workspace_edits(
            edits=require_list(payload.get("edits")),
            settings=settings,  # type: ignore[arg-type]
            max_files=max_files,
        )
    except (WorkspaceEditConfigurationError, WorkspaceEditError) as exc:
        raise BiberAgentClientError(str(exc)) from exc


def plan_repo_context_local_target(
    *,
    target_root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ensure_local_src_import_path()
    from biber_api.repo_context import RepoContextError
    from biber_api.repo_context import plan_repo_context as local_plan_repo_context

    root = validate_local_target_root(target_root)
    try:
        return local_plan_repo_context(
            root=str(root),
            instruction=(
                str(payload["instruction"])
                if isinstance(payload.get("instruction"), str)
                else None
            ),
            pinned_paths=[
                str(item) for item in require_list(payload.get("pinned_paths"))
            ],
            changed_paths=[
                str(item) for item in require_list(payload.get("changed_paths"))
            ],
            max_files=int(payload.get("max_files") or 12),
            max_scan_files=int(payload.get("max_scan_files") or 2000),
        )
    except (RepoContextError, TypeError, ValueError) as exc:
        raise BiberAgentClientError(str(exc)) from exc


def apply_workspace_edit_plan_local_target(
    *,
    target_root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ensure_local_src_import_path()
    from biber_api.workspace_edit import (
        WorkspaceEditConfigurationError,
        WorkspaceEditError,
        apply_workspace_edit_plan as local_apply_workspace_edit_plan,
    )

    settings = local_workspace_edit_settings(validate_local_target_root(target_root))
    max_files = int(payload.get("max_files") or 8)
    plan_hash = payload.get("plan_hash")
    if not isinstance(plan_hash, str) or not plan_hash:
        raise BiberAgentClientError("Local repair edit apply requires plan_hash.")
    try:
        return local_apply_workspace_edit_plan(
            edits=require_list(payload.get("edits")),
            expected_plan_hash=plan_hash,
            settings=settings,  # type: ignore[arg-type]
            max_files=max_files,
        )
    except (WorkspaceEditConfigurationError, WorkspaceEditError) as exc:
        raise BiberAgentClientError(str(exc)) from exc


def run_allowlisted_test_local_target(
    *,
    target_root: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    ensure_local_src_import_path()
    from biber_api.test_runner import (
        TestRunnerConfigurationError,
        UnknownTestCommandError,
        run_test_command,
    )

    test_id = payload.get("test_id")
    if not isinstance(test_id, str) or not test_id.strip():
        raise BiberAgentClientError("Local test run requires test_id.")
    settings = local_workspace_edit_settings(validate_local_target_root(target_root))
    try:
        return run_test_command(
            test_id.strip(),
            settings=settings,
            dry_run=bool(payload.get("dry_run")),
        )
    except (TestRunnerConfigurationError, UnknownTestCommandError) as exc:
        raise BiberAgentClientError(str(exc)) from exc


def diagnose_test_failure_local(
    test_run: Mapping[str, Any],
    *,
    max_context_lines: int | None,
) -> dict[str, Any]:
    ensure_local_src_import_path()
    from biber_api.test_diagnosis import diagnose_test_failure as local_diagnose

    payload = build_diagnosis_payload_from_test_run(
        test_run,
        max_context_lines=max_context_lines,
    )
    return local_diagnose(
        stdout=str(payload.get("stdout") or ""),
        stderr=str(payload.get("stderr") or ""),
        exit_code=(
            int(payload["exit_code"])
            if isinstance(payload.get("exit_code"), int)
            else None
        ),
        timed_out=bool(payload.get("timed_out")),
        command=[
            str(part)
            for part in require_list(payload.get("command"))
            if isinstance(part, str)
        ],
        test_id=str(payload.get("test_id") or ""),
        max_context_lines=max_context_lines if max_context_lines is not None else 80,
    )


def save_to_github(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/save/github",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def create_github_pull_request(
    *,
    base_url: str,
    api_key: str,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/github/pull-request",
        method="POST",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def require_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def require_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def dedupe_strings(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = value.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def normalize_runtime_profile_ids(value: object) -> list[str] | None:
    if value is None:
        return None
    return dedupe_strings([str(item) for item in require_list(value)])


def get_preset(capabilities: Mapping[str, Any], preset_id: str) -> dict[str, Any]:
    for preset in require_list(capabilities.get("presets")):
        if isinstance(preset, dict) and preset.get("id") == preset_id:
            return preset
    raise BiberAgentClientError(f"Unknown preset: {preset_id}")


def available_runtime_profile_ids(capabilities: Mapping[str, Any]) -> set[str]:
    features = require_mapping(capabilities.get("features"))
    runtime_profiles = require_mapping(features.get("runtime_profiles"))
    profiles = require_list(runtime_profiles.get("available_profiles"))
    return {
        str(profile.get("id"))
        for profile in profiles
        if isinstance(profile, dict) and profile.get("id")
    }


def validate_runtime_profile_ids(
    *,
    capabilities: Mapping[str, Any],
    runtime_profile_ids: list[str] | None,
) -> None:
    if not runtime_profile_ids:
        return
    available = available_runtime_profile_ids(capabilities)
    if not available:
        raise BiberAgentClientError("Server does not advertise runtime profiles.")
    unknown = sorted(set(runtime_profile_ids) - available)
    if unknown:
        raise BiberAgentClientError(
            "Unknown runtime profile id(s): "
            f"{', '.join(unknown)}. Available: {', '.join(sorted(available))}."
        )


def build_chat_payload(
    *,
    message: str,
    model: str | None = None,
    language: str | None = None,
    task_type: str | None = None,
    repo_context_paths: list[str] | None = None,
    runtime_profile_ids: list[str] | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
    use_mentor: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "messages": [{"role": "user", "content": message}],
        "use_mentor": use_mentor,
    }
    if model:
        payload["model"] = model
    if language:
        payload["language"] = language
    if task_type:
        payload["task_type"] = task_type
    if repo_context_paths is not None:
        payload["repo_context_paths"] = repo_context_paths
    if runtime_profile_ids is not None:
        payload["runtime_profile_ids"] = runtime_profile_ids
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature
    return payload


def build_session_payload(
    *,
    capabilities: Mapping[str, Any],
    preset_id: str,
    instruction: str,
    model: str | None = None,
    language: str | None = None,
    task_type: str | None = None,
    repo_context_paths: list[str] | None = None,
    runtime_profile_ids: list[str] | None = None,
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
    if runtime_profile_ids is not None:
        template["runtime_profile_ids"] = runtime_profile_ids
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
    runtime_profiles = require_mapping(features.get("runtime_profiles"))
    runtime_profile_ids = [
        str(profile.get("id"))
        for profile in require_list(runtime_profiles.get("available_profiles"))
        if isinstance(profile, dict) and profile.get("id")
    ]
    lines = [
        "BIBER agent capabilities",
        f"service: {payload.get('service', '-')}",
        f"version: {payload.get('version', '-')}",
        f"default_model: {payload.get('default_model', '-')}",
        f"presets: {', '.join(presets) if presets else '-'}",
        f"tests: {', '.join(tests) if tests else '-'}",
        f"xriq_context: {bool(xriq.get('context_supported'))}",
        f"mentor_configured: {bool(mentor.get('configured'))}",
        f"runtime_profiles_enabled: {bool(runtime_profiles.get('enabled'))}",
        f"runtime_profiles: {', '.join(runtime_profile_ids) if runtime_profile_ids else '-'}",
    ]
    return "\n".join(lines)


def format_chat_summary(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "BIBER chat response",
            f"id: {payload.get('id', '-')}",
            f"model: {payload.get('model', '-')}",
            f"mentor_used: {payload.get('mentor_used', False)}",
            "content:",
            str(payload.get("content") or ""),
        ]
    )


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


def build_repo_context_payload(
    *,
    instruction: str | None,
    pinned_paths: list[str] | None,
    changed_paths: list[str] | None,
    max_files: int | None,
    max_scan_files: int | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if instruction:
        payload["instruction"] = instruction
    if pinned_paths is not None:
        payload["pinned_paths"] = pinned_paths
    if changed_paths is not None:
        payload["changed_paths"] = changed_paths
    if max_files is not None:
        payload["max_files"] = max_files
    if max_scan_files is not None:
        payload["max_scan_files"] = max_scan_files
    return payload


def format_repo_context_summary(payload: Mapping[str, Any]) -> str:
    selected_paths = [str(path) for path in require_list(payload.get("selected_paths"))]
    detected_project_types = [
        str(project_type)
        for project_type in require_list(payload.get("detected_project_types"))
    ]
    stack_profiles = [
        str(profile.get("id"))
        for profile in require_list(payload.get("stack_profiles"))
        if isinstance(profile, dict) and profile.get("id")
    ]
    lines = [
        "BIBER repo context plan",
        f"summary: {payload.get('summary', '-')}",
        (
            "detected_project_types: "
            f"{', '.join(detected_project_types) if detected_project_types else '-'}"
        ),
        f"stack_profiles: {', '.join(stack_profiles) if stack_profiles else '-'}",
        f"selected_paths ({len(selected_paths)}):",
    ]
    lines.extend(f"- {path}" for path in selected_paths)
    return "\n".join(lines)


def parse_json_object(value: str, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise BiberAgentClientError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise BiberAgentClientError(f"{label} must be a JSON object.")
    return parsed


def parse_json_list(value: str, *, label: str) -> list[Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise BiberAgentClientError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise BiberAgentClientError(f"{label} must be a JSON array.")
    return parsed


def load_text_argument(
    *,
    value: str | None,
    file_path: str | None,
    label: str,
) -> str:
    if value is not None and file_path:
        raise BiberAgentClientError(f"Use either {label} or {label}-file, not both.")
    if file_path:
        path = Path(file_path)
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BiberAgentClientError(f"Could not read {label}-file {path}: {exc}") from exc
    return value or ""


def parse_local_model_command(command: str) -> list[str]:
    command = command.strip()
    if not command:
        raise BiberAgentClientError("--model-command cannot be empty.")
    if command.startswith("["):
        parts = parse_json_list(command, label="--model-command")
        if not all(isinstance(part, str) and part.strip() for part in parts):
            raise BiberAgentClientError(
                "--model-command JSON array must contain non-empty strings."
            )
        return [str(part) for part in parts]
    try:
        parts = shlex.split(command, posix=os.name != "nt")
    except ValueError as exc:
        raise BiberAgentClientError(f"--model-command could not be parsed: {exc}") from exc
    if not parts:
        raise BiberAgentClientError("--model-command cannot be empty.")
    return parts


def write_json_artifact(payload: Mapping[str, Any], output_path: str) -> str:
    path = Path(output_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return str(path)


def write_jsonl_artifact(records: list[Mapping[str, Any]], output_path: str) -> str:
    path = Path(output_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    return str(path)


def load_json_artifact(artifact_path: str, *, label: str) -> dict[str, Any]:
    path = Path(artifact_path)
    try:
        parsed = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise BiberAgentClientError(f"Could not read {label} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BiberAgentClientError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise BiberAgentClientError(f"{label} must contain a JSON object.")
    return parsed


def format_cli_command(parts: Sequence[object]) -> str:
    return subprocess.list2cmdline([str(part) for part in parts])


def load_jsonl_artifact(jsonl_path: str, *, label: str) -> list[dict[str, Any]]:
    path = Path(jsonl_path)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise BiberAgentClientError(f"Could not read {label} {path}: {exc}") from exc
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise BiberAgentClientError(
                f"{label} {path} line {line_number} must be valid JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise BiberAgentClientError(
                f"{label} {path} line {line_number} must be a JSON object."
            )
        records.append(parsed)
    return records


def compact_text(value: object, *, max_chars: int = 2000) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


NON_REAL_REPAIR_EVIDENCE_MARKERS = {
    "biber-real-repair-fixture": "disposable_fixture_artifact",
    "agent-client-mvp-loop-smoke": "smoke_artifact",
    "biber-agent-smoke": "smoke_artifact",
    "biber-baseline-candidate": "controlled_baseline_artifact",
    "smoke metadata": "smoke_metadata",
    "smoke-only": "smoke_only_artifact",
}


def normalize_repo_provenance(value: object) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    provenance: dict[str, str] = {}
    aliases = {
        "root": ("root", "repo_root", "source_repo_root"),
        "url": ("url", "repo_url", "source_repo_url"),
        "commit": ("commit", "repo_commit", "source_repo_commit"),
        "branch": ("branch", "repo_branch", "source_repo_branch"),
    }
    for normalized_key, source_keys in aliases.items():
        for source_key in source_keys:
            raw_value = value.get(source_key)
            if isinstance(raw_value, str) and raw_value.strip():
                provenance[normalized_key] = raw_value.strip()
                break
    return provenance or None


def git_text(repo_root: str, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", repo_root, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def derive_repo_provenance_from_git(repo_root: str | None) -> dict[str, str] | None:
    if repo_root is None or not repo_root.strip():
        return None
    root_arg = repo_root.strip()
    root = git_text(root_arg, "rev-parse", "--show-toplevel") or root_arg
    commit = git_text(root_arg, "rev-parse", "HEAD")
    url = git_text(root_arg, "remote", "get-url", "origin")
    branch = git_text(root_arg, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        branch = None
    return normalize_repo_provenance(
        {
            "root": root,
            "url": url,
            "commit": commit,
            "branch": branch,
        }
    )


def complete_repo_provenance_from_git(value: object) -> dict[str, str] | None:
    manual = normalize_repo_provenance(value)
    if manual is None:
        return None
    derived = derive_repo_provenance_from_git(manual.get("root"))
    if derived is None:
        return manual
    merged = dict(derived)
    merged.update(manual)
    return normalize_repo_provenance(merged)


def repo_provenance_ok_for_eval(record: Mapping[str, Any]) -> bool:
    provenance = normalize_repo_provenance(record.get("repo_provenance"))
    if provenance is None:
        return False
    return bool(provenance.get("root") and provenance.get("commit"))


def classify_repair_chain_evidence_source(
    record: Mapping[str, Any],
    *,
    declared_source_type: str | None = None,
) -> dict[str, Any]:
    values: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            values.append(value.lower())
        elif isinstance(value, Mapping):
            for nested_value in value.values():
                collect(nested_value)
        elif isinstance(value, list | tuple):
            for nested_value in value:
                collect(nested_value)

    collect(
        {
            "source_artifact": record.get("source_artifact"),
            "jsonl_path": record.get("jsonl_path"),
            "decision_jsonl_path": record.get("decision_jsonl_path"),
            "notes": record.get("notes"),
            "artifacts": record.get("artifacts"),
            "repo_provenance": record.get("repo_provenance"),
        }
    )
    joined = "\n".join(values)
    declared = declared_source_type
    existing = record.get("evidence_source_type")
    if declared is None:
        if existing in {"real_repo_candidate", "fixture_or_smoke"}:
            declared = str(existing)
    marker_reasons = [
        reason
        for marker, reason in NON_REAL_REPAIR_EVIDENCE_MARKERS.items()
        if marker in joined
    ]
    reasons = list(marker_reasons)
    non_real_reasons = set(marker_reasons)
    if declared == "real_repo_candidate" and existing == "fixture_or_smoke":
        reasons.append("existing_fixture_or_smoke")
        non_real_reasons.add("existing_fixture_or_smoke")
    if declared == "fixture_or_smoke":
        reasons.append("declared_fixture_or_smoke")
        non_real_reasons.add("declared_fixture_or_smoke")
    if declared == "real_repo_candidate" and not repo_provenance_ok_for_eval(record):
        reasons.append("missing_repo_provenance")
    if declared == "real_repo_candidate" and non_real_reasons:
        reasons.append("real_repo_declaration_conflicts_with_markers")
    elif declared == "real_repo_candidate" and reasons:
        reasons.append("real_repo_declaration_not_confirmed")
    reasons = sorted(set(reasons))
    confirmed_real_repo = (
        declared == "real_repo_candidate"
        and not reasons
        and repo_provenance_ok_for_eval(record)
    )
    evidence_source_type = (
        "fixture_or_smoke"
        if non_real_reasons
        else "real_repo_candidate"
        if confirmed_real_repo
        else "unconfirmed_real_repo_candidate"
    )
    return {
        "evidence_source_type": evidence_source_type,
        "evidence_source_declaration": declared or "auto",
        "evidence_source_confirmed": confirmed_real_repo,
        "evidence_source_ok_for_eval": confirmed_real_repo,
        "evidence_source_reasons": reasons,
    }


def normalize_mvp_loop_artifact(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if isinstance(payload.get("steps"), dict):
        return dict(payload)
    body = payload.get("body")
    if isinstance(body, dict) and isinstance(body.get("steps"), dict):
        return dict(body)
    return None


def normalize_mvp_loop_repair_request_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_request":
        return dict(payload)
    body = payload.get("body")
    if isinstance(body, dict) and body.get("source") == "biber_mvp_loop_repair_request":
        return dict(body)
    return None


def summarize_mvp_loop_artifact(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    steps = require_mapping(payload.get("steps"))
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "ok": bool(payload.get("ok")),
        "test_ok": payload.get("test_ok"),
        "selected_context_paths": len(require_list(payload.get("selected_context_paths"))),
        "steps": list(steps.keys()),
        "modified_epoch": modified_epoch,
    }
    for key in ("artifact_path", "github_url", "pull_request_url"):
        if payload.get(key):
            summary[key] = payload.get(key)
    return summary


def step_command_text(step: Mapping[str, Any]) -> str | None:
    command = [str(part) for part in require_list(step.get("command"))]
    if not command:
        return None
    return " ".join(command)


def mvp_loop_prepare_repair_command(artifact_path: object) -> str | None:
    if not artifact_path:
        return None
    source = Path(str(artifact_path))
    output = source.with_name("prepared-repair.json")
    return format_cli_command(
        [
            "python",
            "scripts/biber_agent_client.py",
            "--json",
            "prepare-repair",
            source,
            "--output",
            output,
        ]
    )


def build_mvp_loop_repair_hint(
    *,
    test_run: Mapping[str, Any],
    diagnosis: Mapping[str, Any],
    next_actions: list[str],
    max_relevant_output_chars: int = 1200,
) -> dict[str, Any] | None:
    if not test_run or test_run.get("ok") is not False:
        return None
    relevant_output = (
        diagnosis.get("relevant_output")
        or test_run.get("stdout")
        or test_run.get("stderr")
        or ""
    )
    suggested_next_actions = dedupe_strings(
        [
            str(item)
            for item in (
                require_list(diagnosis.get("suggested_next_actions"))
                or next_actions
            )
            if str(item).strip()
        ]
    )
    return {
        "source": "biber_mvp_loop_repair_hint_v1",
        "status": "ready_for_prepare_repair",
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "test_id": test_run.get("test_id"),
        "command": step_command_text(test_run),
        "exit_code": test_run.get("exit_code"),
        "timed_out": bool(test_run.get("timed_out")),
        "diagnosis_summary": diagnosis.get("summary"),
        "primary_category": diagnosis.get("primary_category"),
        "detected_stack": diagnosis.get("detected_stack"),
        "relevant_output": compact_text(
            relevant_output,
            max_chars=max_relevant_output_chars,
        ),
        "suggested_next_actions": suggested_next_actions or [],
        "next_workflow": [
            "prepare-repair",
            "local-repair-chain",
            "review-local-repair-chain",
            "apply-repair-edits-only-after-explicit-approval",
            "local-verify-chain",
        ],
    }


def build_mvp_loop_agent_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    steps = require_mapping(payload.get("steps"))
    selected_context_paths = [
        str(path) for path in require_list(payload.get("selected_context_paths"))
    ]
    git_state = require_mapping(steps.get("git_state"))
    edit_plan = require_mapping(steps.get("edit_plan"))
    edit_apply = require_mapping(steps.get("edit_apply"))
    test_run = require_mapping(steps.get("test_run"))
    diagnosis = require_mapping(steps.get("test_diagnosis"))
    edit_review = require_mapping(edit_plan.get("review"))

    planned = [
        item for item in require_list(edit_plan.get("planned")) if isinstance(item, dict)
    ]
    rejected = [
        item for item in require_list(edit_plan.get("rejected")) if isinstance(item, dict)
    ]
    applied = [
        item for item in require_list(edit_apply.get("applied")) if isinstance(item, dict)
    ]
    changed = [item for item in applied if item.get("changed") is True]

    status = "ok" if payload.get("ok") is True else "needs_attention"
    if not test_run:
        status = "needs_test"
    if test_run and test_run.get("executed") is False:
        status = "dry_run_only"
    if diagnosis:
        status = "test_failed"
    if rejected or edit_plan.get("ok") is False or edit_apply.get("ok") is False:
        status = "edit_needs_review"

    next_actions: list[str] = []
    if git_state.get("dirty") is True:
        next_actions.append("Review local git dirty state before commit or PR.")
    if rejected:
        next_actions.append("Review rejected edit-plan entries before applying edits.")
    if diagnosis:
        diagnosis_actions = [
            str(item)
            for item in require_list(diagnosis.get("suggested_next_actions"))[:4]
        ]
        if diagnosis_actions:
            next_actions.extend(diagnosis_actions)
        else:
            next_actions.append("Review the failing test output and prepare a bounded repair edit.")
    elif test_run and test_run.get("executed") is False:
        next_actions.append("Run the selected allowlisted test without --test-dry-run.")
    elif test_run and test_run.get("ok") is True:
        next_actions.append("Ready for GitHub save/PR or the next narrow change.")
    elif not test_run:
        next_actions.append("Run an allowlisted test for the selected context.")

    deduped_next_actions = dedupe_strings(next_actions) or []
    repair_hint = build_mvp_loop_repair_hint(
        test_run=test_run,
        diagnosis=diagnosis,
        next_actions=deduped_next_actions,
    )
    if repair_hint is not None and payload.get("artifact_path"):
        next_command = mvp_loop_prepare_repair_command(payload.get("artifact_path"))
        if next_command:
            repair_hint = dict(repair_hint)
            repair_hint["next_command"] = next_command
    report = {
        "source": "biber_mvp_loop_agent_report_v1",
        "status": status,
        "ok": payload.get("ok") is True,
        "repo": {
            "target_root": payload.get("target_root"),
            "branch": payload.get("git_branch") or git_state.get("branch"),
            "head": payload.get("git_head") or git_state.get("head"),
            "dirty": payload.get("git_dirty")
            if "git_dirty" in payload
            else git_state.get("dirty"),
            "status_short": [
                str(item) for item in require_list(git_state.get("status_short"))
            ],
        },
        "context": {
            "mode": payload.get("context_mode"),
            "selected_count": len(selected_context_paths),
            "selected_paths": selected_context_paths,
        },
        "edit": {
            "mode": payload.get("edit_mode"),
            "plan_hash": payload.get("edit_plan_hash"),
            "planned_count": len(planned),
            "rejected_count": len(rejected),
            "applied_count": len(applied),
            "changed_count": len(changed),
            "ok": edit_apply.get("ok") if edit_apply else edit_plan.get("ok"),
            "review_status": edit_review.get("review_status"),
            "ready_for_apply": edit_review.get("ready_for_apply"),
            "risk_counts": edit_review.get("risk_counts") or {},
            "operation_counts": edit_review.get("operation_counts") or {},
            "warnings": [
                str(item) for item in require_list(edit_review.get("warnings"))
            ],
            "hard_blockers": [
                str(item) for item in require_list(edit_review.get("hard_blockers"))
            ],
        },
        "test": {
            "mode": payload.get("test_mode"),
            "test_id": test_run.get("test_id"),
            "executed": test_run.get("executed"),
            "ok": payload.get("test_ok"),
            "exit_code": test_run.get("exit_code"),
            "timed_out": test_run.get("timed_out"),
            "command": step_command_text(test_run),
        },
        "failure": {
            "diagnosis_summary": payload.get("diagnosis_summary")
            or diagnosis.get("summary"),
            "primary_category": diagnosis.get("primary_category"),
            "detected_stack": diagnosis.get("detected_stack"),
        },
        "next_actions": deduped_next_actions,
    }
    if repair_hint is not None:
        report["repair_hint"] = repair_hint
    return report


def is_failed_mvp_loop_artifact(payload: Mapping[str, Any]) -> bool:
    return payload.get("ok") is not True or payload.get("test_ok") is False


def build_mvp_loop_failure_record(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    steps = require_mapping(payload.get("steps"))
    test_run = require_mapping(steps.get("test_run"))
    diagnosis = require_mapping(steps.get("test_diagnosis"))
    agent_report = require_mapping(payload.get("agent_report"))
    if not agent_report:
        agent_report = build_mvp_loop_agent_report(payload)
    repair_hint = require_mapping(agent_report.get("repair_hint"))
    if not repair_hint:
        repair_hint = build_mvp_loop_repair_hint(
            test_run=test_run,
            diagnosis=diagnosis,
            next_actions=[
                str(item)
                for item in require_list(agent_report.get("next_actions"))
                if str(item).strip()
            ],
        ) or {}
    runtime_profile_ids = normalize_runtime_profile_ids(
        payload.get("runtime_profile_ids")
    )
    relevant_output = (
        repair_hint.get("relevant_output")
        or diagnosis.get("relevant_output")
        or test_run.get("stdout")
        or test_run.get("stderr")
        or ""
    )
    record: dict[str, Any] = {
        "source": "biber_mvp_loop_failure",
        "review_status": "needs_review",
        "training_allowed": False,
        "source_artifact": str(path),
        "ok": payload.get("ok"),
        "test_ok": payload.get("test_ok"),
        "selected_context_paths": require_list(payload.get("selected_context_paths")),
        "step_names": list(steps.keys()),
        "edit_plan_hash": payload.get("edit_plan_hash"),
        "failure": {
            "diagnosis_summary": payload.get("diagnosis_summary")
            or diagnosis.get("summary"),
            "primary_category": diagnosis.get("primary_category"),
            "detected_stack": diagnosis.get("detected_stack"),
            "test_id": test_run.get("test_id"),
            "exit_code": test_run.get("exit_code"),
            "timed_out": bool(test_run.get("timed_out")),
            "relevant_output": compact_text(relevant_output),
        },
        "repair_hint": repair_hint,
        "next_review_action": "review_failure_before_eval_or_training",
    }
    if runtime_profile_ids is not None:
        record["runtime_profile_ids"] = runtime_profile_ids
    return record


def build_repair_prompt(
    *,
    instruction: str,
    original_instruction: object,
    selected_context_paths: list[str],
    failure: Mapping[str, Any],
    suggested_next_actions: list[str],
    agent_report: Mapping[str, Any] | None = None,
    output_contract: Mapping[str, Any] | None = None,
) -> str:
    context_lines = "\n".join(f"- {path}" for path in selected_context_paths) or "- none"
    action_lines = "\n".join(f"- {action}" for action in suggested_next_actions) or "- none"
    command = " ".join(str(part) for part in require_list(failure.get("command"))) or "-"
    contract = require_mapping(output_contract) or build_repair_output_contract()
    contract_text = format_repair_output_contract(contract)
    report = require_mapping(agent_report)
    report_repo = require_mapping(report.get("repo"))
    report_edit = require_mapping(report.get("edit"))
    report_test = require_mapping(report.get("test"))
    report_failure = require_mapping(report.get("failure"))
    report_repair_hint = require_mapping(report.get("repair_hint"))
    report_next_actions = [
        str(action) for action in require_list(report.get("next_actions"))
    ]
    report_lines = [
        f"- status: {report.get('status', '-')}",
        (
            "- repo: "
            f"branch={report_repo.get('branch') or '-'} "
            f"head={report_repo.get('head') or '-'} "
            f"dirty={report_repo.get('dirty')}"
        ),
        (
            "- edit: "
            f"planned={report_edit.get('planned_count', 0)} "
            f"applied={report_edit.get('applied_count', 0)} "
            f"changed={report_edit.get('changed_count', 0)} "
            f"rejected={report_edit.get('rejected_count', 0)} "
            f"review={report_edit.get('review_status') or '-'} "
            f"ready_for_apply={report_edit.get('ready_for_apply')}"
        ),
        (
            "- test: "
            f"id={report_test.get('test_id') or '-'} "
            f"executed={report_test.get('executed')} "
            f"ok={report_test.get('ok')} "
            f"exit_code={report_test.get('exit_code')}"
        ),
    ]
    if report_failure:
        report_lines.append(
            "- failure: "
            f"stack={report_failure.get('detected_stack') or '-'} "
            f"category={report_failure.get('primary_category') or '-'}"
        )
    if report_repair_hint:
        workflow = ", ".join(
            str(item)
            for item in require_list(report_repair_hint.get("next_workflow"))[:5]
        )
        report_lines.append(
            "- repair_hint: "
            f"status={report_repair_hint.get('status') or '-'} "
            f"stack={report_repair_hint.get('detected_stack') or '-'} "
            f"category={report_repair_hint.get('primary_category') or '-'} "
            f"next={workflow or '-'}"
        )
    if report_next_actions:
        report_lines.append("- next_actions:")
        report_lines.extend(f"  - {action}" for action in report_next_actions[:5])
    report_text = "\n".join(report_lines) if report else "- not available"
    return "\n".join(
        [
            "BIBER deterministic repair request.",
            "",
            "Goal:",
            instruction,
            "",
            "Rules:",
            "- Prefer the smallest safe edit that fixes the failing test.",
            "- Do not change credentials, generated secrets, dependency folders, or unrelated files.",
            "- If the goal says not to change tests, propose only source/implementation edits.",
            "- Preserve the existing project style and use existing APIs/helpers.",
            (
                '- Return a strict JSON object first: {"edits":[{"path":"...",'
                '"old_text":"...","new_text":"...","expected_replacements":1}]}.'
            ),
            "- Explanations after the JSON edit object are optional.",
            "",
            f"Original MVP instruction: {original_instruction or '-'}",
            "",
            "Selected repository context paths:",
            context_lines,
            "",
            "Output contract:",
            contract_text,
            "",
            "Agent report:",
            report_text,
            "",
            "Failed test:",
            f"- test_id: {failure.get('test_id') or '-'}",
            f"- command: {command}",
            f"- exit_code: {failure.get('exit_code')}",
            f"- timed_out: {bool(failure.get('timed_out'))}",
            "",
            "Diagnosis:",
            f"- detected_stack: {failure.get('detected_stack') or '-'}",
            f"- primary_category: {failure.get('primary_category') or '-'}",
            f"- summary: {failure.get('diagnosis_summary') or '-'}",
            "",
            "Suggested next actions:",
            action_lines,
            "",
            "Relevant output:",
            str(failure.get("relevant_output") or ""),
        ]
    )


def build_repair_output_contract() -> dict[str, Any]:
    return {
        "source": "biber_repair_output_contract_v1",
        "response_format": "strict_json_object_first",
        "preferred_top_level_shape": (
            '{"edits":[{"path":"src/file.ext","old_text":"old",'
            '"new_text":"new","expected_replacements":1}]}'
        ),
        "accepted_top_level_shapes": [
            "object_with_edits_array",
            "single_edit_object",
            "array_of_edit_objects",
        ],
        "required_edit_keys": ["path", "new_text"],
        "recommended_edit_keys": ["old_text", "expected_replacements"],
        "optional_edit_keys": ["create_if_missing", "dry_run"],
        "accepted_path_aliases": ["path", "file"],
        "path_rules": [
            "relative_repo_path_only",
            "no_absolute_paths",
            "no_parent_traversal",
            "no_home_or_drive_prefixes",
        ],
        "empty_safe_response": {"edits": []},
        "next_command": "extract-repair-edits",
        "plan_command": "plan-repair-edits",
        "apply_allowed": False,
        "training_allowed": False,
    }


def format_repair_output_contract(contract: Mapping[str, Any]) -> str:
    preferred_shape = contract.get("preferred_top_level_shape") or "{}"
    required = ", ".join(
        str(item) for item in require_list(contract.get("required_edit_keys"))
    )
    recommended = ", ".join(
        str(item) for item in require_list(contract.get("recommended_edit_keys"))
    )
    optional = ", ".join(
        str(item) for item in require_list(contract.get("optional_edit_keys"))
    )
    return "\n".join(
        [
            "- Return strict JSON as the first response content, without Markdown fences.",
            f"- Preferred shape: {preferred_shape}",
            '- If no safe edit exists, return exactly {"edits":[]}.',
            f"- Required edit keys: {required or '-'}",
            f"- Recommended replacement keys: {recommended or '-'}",
            f"- Optional edit keys: {optional or '-'}",
            "- Use relative repository paths only; no absolute paths or parent traversal.",
            "- Do not include secrets, generated dependency folders, or unrelated files.",
            "- `extract-repair-edits` is the next command; apply is never automatic.",
        ]
    )


def build_mvp_loop_repair_request(
    *,
    path: Path,
    payload: Mapping[str, Any],
    instruction: str | None,
    max_relevant_output_chars: int,
    max_context_paths: int | None,
) -> dict[str, Any]:
    if max_relevant_output_chars < 1:
        raise BiberAgentClientError("--max-relevant-output-chars must be at least 1.")
    if max_context_paths is not None and max_context_paths < 1:
        raise BiberAgentClientError("--max-context-paths must be at least 1.")
    if not is_failed_mvp_loop_artifact(payload):
        raise BiberAgentClientError(
            "prepare-repair requires a failed mvp-loop artifact."
        )

    steps = require_mapping(payload.get("steps"))
    test_run = require_mapping(steps.get("test_run"))
    diagnosis = require_mapping(steps.get("test_diagnosis"))
    agent_report = require_mapping(payload.get("agent_report"))
    if not agent_report:
        agent_report = build_mvp_loop_agent_report(payload)
    repair_hint = require_mapping(agent_report.get("repair_hint"))
    if not repair_hint:
        repair_hint = build_mvp_loop_repair_hint(
            test_run=test_run,
            diagnosis=diagnosis,
            next_actions=[
                str(item)
                for item in require_list(agent_report.get("next_actions"))
                if str(item).strip()
            ],
        ) or {}
        if repair_hint:
            agent_report = dict(agent_report)
            agent_report["repair_hint"] = repair_hint
    all_context_paths = [
        str(item) for item in require_list(payload.get("selected_context_paths"))
    ]
    selected_context_paths = (
        all_context_paths[:max_context_paths]
        if max_context_paths is not None
        else all_context_paths
    )
    relevant_output = (
        repair_hint.get("relevant_output")
        or diagnosis.get("relevant_output")
        or test_run.get("stdout")
        or test_run.get("stderr")
        or ""
    )
    suggested_next_actions = [
        str(item) for item in require_list(diagnosis.get("suggested_next_actions"))
    ]
    if not suggested_next_actions:
        suggested_next_actions = [
            str(item)
            for item in require_list(repair_hint.get("suggested_next_actions"))
            if str(item).strip()
        ]
    if not suggested_next_actions:
        suggested_next_actions = [
            str(item)
            for item in require_list(agent_report.get("next_actions"))
            if str(item).strip()
        ]
    failure = {
        "diagnosis_summary": payload.get("diagnosis_summary")
        or diagnosis.get("summary"),
        "primary_category": diagnosis.get("primary_category"),
        "detected_stack": diagnosis.get("detected_stack"),
        "test_id": test_run.get("test_id"),
        "command": require_list(test_run.get("command")),
        "exit_code": test_run.get("exit_code"),
        "timed_out": bool(test_run.get("timed_out")),
        "relevant_output": compact_text(
            relevant_output,
            max_chars=max_relevant_output_chars,
        ),
    }
    repair_instruction = instruction or DEFAULT_REPAIR_INSTRUCTION
    runtime_profile_ids = normalize_runtime_profile_ids(
        payload.get("runtime_profile_ids")
    )
    repair_output_contract = build_repair_output_contract()
    repair_prompt = build_repair_prompt(
        instruction=repair_instruction,
        original_instruction=payload.get("instruction"),
        selected_context_paths=selected_context_paths,
        failure=failure,
        suggested_next_actions=suggested_next_actions,
        agent_report=agent_report,
        output_contract=repair_output_contract,
    )
    repair: dict[str, Any] = {
        "source": "biber_mvp_loop_repair_request",
        "repair_loop_version": "mvp-v1",
        "repair_status": "ready_for_local_model",
        "training_allowed": False,
        "source_artifact": str(path),
        "ok": False,
        "instruction": repair_instruction,
        "repair_prompt": repair_prompt,
        "repair_output_contract": repair_output_contract,
        "selected_context_paths": selected_context_paths,
        "selected_context_paths_truncated": len(selected_context_paths)
        < len(all_context_paths),
        "agent_report": agent_report,
        "repair_hint": repair_hint,
        "failure": failure,
        "suggested_next_actions": suggested_next_actions,
        "next_test_id": test_run.get("test_id"),
        "next_workflow": [
            "send_repair_prompt_to_local_biber_model",
            "convert_response_to_bounded_plan_edit_payload",
            "run_plan_edit_then_apply_edit_if_hash_matches",
            "rerun_next_test_id",
            "diagnose_again_if_still_failing",
        ],
    }
    if runtime_profile_ids is not None:
        repair["runtime_profile_ids"] = runtime_profile_ids
    return repair


def ensure_repair_request_output_contract(
    repair_request: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(repair_request)
    contract = require_mapping(result.get("repair_output_contract"))
    if not contract:
        contract = build_repair_output_contract()
        result["repair_output_contract"] = contract
    prompt = str(result.get("repair_prompt") or "")
    if prompt and "Output contract:" not in prompt:
        result["repair_prompt"] = "\n\n".join(
            [
                prompt.rstrip(),
                "Output contract:",
                format_repair_output_contract(contract),
            ]
        )
    return result


def build_or_load_repair_request(
    *,
    path: Path,
    artifact: Mapping[str, Any],
    instruction: str | None,
    max_relevant_output_chars: int,
    max_context_paths: int | None,
) -> dict[str, Any]:
    prepared = normalize_mvp_loop_repair_request_artifact(artifact)
    if prepared is not None:
        return ensure_repair_request_output_contract(prepared)
    mvp_loop = normalize_mvp_loop_artifact(artifact)
    if mvp_loop is None:
        raise BiberAgentClientError(
            "attempt-repair artifact must contain a saved MVP loop JSON object "
            "or a prepared repair request JSON object."
        )
    return build_mvp_loop_repair_request(
        path=path,
        payload=mvp_loop,
        instruction=instruction,
        max_relevant_output_chars=max_relevant_output_chars,
        max_context_paths=max_context_paths,
    )


def language_for_detected_stack(stack: object) -> str | None:
    normalized = str(stack or "").strip().lower()
    return {
        "dotnet": "C#/.NET",
        "java": "Java",
        "rust": "Rust",
        "python": "Python",
        "node": "JavaScript/TypeScript",
        "react": "React/TypeScript",
    }.get(normalized)


def build_repair_chat_payload(
    *,
    repair_request: Mapping[str, Any],
    model: str | None,
    max_tokens: int | None,
    temperature: float,
    use_mentor: bool,
    runtime_profile_ids: list[str] | None = None,
) -> dict[str, Any]:
    failure = require_mapping(repair_request.get("failure"))
    payload: dict[str, Any] = {
        "messages": [
            {
                "role": "user",
                "content": str(repair_request.get("repair_prompt") or ""),
            }
        ],
        "task_type": "mvp_loop_repair",
        "temperature": temperature,
        "use_mentor": use_mentor,
        "repo_context_paths": [
            str(path)
            for path in require_list(repair_request.get("selected_context_paths"))
        ],
    }
    language = language_for_detected_stack(failure.get("detected_stack"))
    if language:
        payload["language"] = language
    if model:
        payload["model"] = model
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if runtime_profile_ids is not None:
        payload["runtime_profile_ids"] = runtime_profile_ids
    return payload


def build_repair_attempt_extraction_hint(
    *,
    content: str,
    output_contract: Mapping[str, Any],
) -> dict[str, Any]:
    stripped = content.strip()
    json_values = extract_json_values_from_text(stripped) if stripped else []
    return {
        "source": "biber_repair_attempt_extraction_hint_v1",
        "ready_for_extraction": bool(stripped),
        "expected_content_field": "repair_content",
        "json_values_found": len(json_values),
        "output_contract": output_contract.get("source"),
        "next_command": output_contract.get("next_command") or "extract-repair-edits",
        "plan_command": output_contract.get("plan_command") or "plan-repair-edits",
        "apply_allowed": False,
        "training_allowed": False,
    }


def build_repair_attempt_result(
    *,
    repair_request: Mapping[str, Any],
    chat_payload: Mapping[str, Any],
    model_response: Mapping[str, Any],
) -> dict[str, Any]:
    repair_content = str(model_response.get("content") or "")
    output_contract = require_mapping(repair_request.get("repair_output_contract"))
    if not output_contract:
        output_contract = build_repair_output_contract()
    return {
        "source": "biber_mvp_loop_repair_attempt",
        "repair_loop_version": "mvp-v1",
        "repair_status": "model_repair_proposed",
        "training_allowed": False,
        "auto_applied": False,
        "ready_for_edit_review": True,
        "source_artifact": repair_request.get("source_artifact"),
        "repair_request": dict(repair_request),
        "chat_request": dict(chat_payload),
        "model_response": dict(model_response),
        "repair_content": repair_content,
        "repair_output_contract": output_contract,
        "extraction_hint": build_repair_attempt_extraction_hint(
            content=repair_content,
            output_contract=output_contract,
        ),
        "next_test_id": repair_request.get("next_test_id"),
        "next_workflow": [
            "review_model_repair_content",
            "convert_response_to_bounded_plan_edit_payload",
            "run_plan_edit_then_apply_edit_if_hash_matches",
            "rerun_next_test_id",
            "diagnose_again_if_still_failing",
        ],
    }


def normalize_repair_attempt_artifact(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_attempt":
        return dict(payload)
    body = payload.get("body")
    if isinstance(body, dict) and body.get("source") == "biber_mvp_loop_repair_attempt":
        return dict(body)
    return None


def repair_attempt_runtime_profile_ids(payload: Mapping[str, Any]) -> list[str] | None:
    chat_request = require_mapping(payload.get("chat_request"))
    repair_request = require_mapping(payload.get("repair_request"))
    for source in (chat_request, repair_request, payload):
        runtime_profile_ids = normalize_runtime_profile_ids(
            source.get("runtime_profile_ids")
        )
        if runtime_profile_ids:
            return runtime_profile_ids
    return None


def summarize_repair_attempt_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    model_response = require_mapping(payload.get("model_response"))
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "repair_status": payload.get("repair_status"),
        "training_allowed": payload.get("training_allowed") is True,
        "auto_applied": payload.get("auto_applied") is True,
        "ready_for_edit_review": payload.get("ready_for_edit_review") is True,
        "model": model_response.get("model"),
        "mentor_used": model_response.get("mentor_used") is True,
        "next_test_id": payload.get("next_test_id"),
        "source_artifact": payload.get("source_artifact"),
        "runtime_profile_ids": repair_attempt_runtime_profile_ids(payload) or [],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_attempt_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Repair attempt artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Repair attempt artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(str(path), label="repair-attempt artifact")
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_attempt_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_repair_attempt_artifact(path, normalized)
        if ready_only and summary.get("ready_for_edit_review") is not True:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    ready_count = sum(
        1 for item in artifacts if item.get("ready_for_edit_review") is True
    )
    return {
        "source": "biber_mvp_loop_repair_attempt_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ready_for_edit_review": ready_count,
        "training_allowed": False,
        "auto_applied": False,
        "artifacts": artifacts[:limit],
    }


def extract_json_values_from_text(text: str, *, limit: int = 20) -> list[Any]:
    decoder = json.JSONDecoder()
    values: list[Any] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char not in "{[":
            index += 1
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            index += 1
            continue
        if isinstance(value, (dict, list)):
            values.append(value)
        if len(values) >= limit:
            break
        index += max(end, 1)
    return values


def extract_edit_objects_from_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        edits = value.get("edits")
        if isinstance(edits, list):
            return [item for item in edits if isinstance(item, dict)]
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def validate_repair_edit_candidate(
    candidate: Mapping[str, Any],
    *,
    index: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    allowed_keys = {
        "path",
        "file",
        "old_text",
        "new_text",
        "expected_replacements",
        "create_if_missing",
        "dry_run",
    }
    unknown_keys = sorted(str(key) for key in set(candidate) - allowed_keys)
    if unknown_keys:
        return None, {
            "index": index,
            "reason": "unknown_keys",
            "unknown_keys": unknown_keys,
        }

    path = candidate.get("path")
    file_path = candidate.get("file")
    if (
        isinstance(path, str)
        and isinstance(file_path, str)
        and path.strip()
        and file_path.strip()
        and path.strip() != file_path.strip()
    ):
        return None, {
            "index": index,
            "reason": "conflicting_path_aliases",
            "path": path,
            "file": file_path,
        }
    if (not isinstance(path, str) or not path.strip()) and isinstance(file_path, str):
        path = file_path
    if not isinstance(path, str) or not path.strip():
        return None, {"index": index, "reason": "missing_path"}
    clean_path = path.strip().replace("\\", "/")
    path_parts = [part for part in clean_path.split("/") if part]
    if (
        clean_path.startswith("/")
        or clean_path.startswith("~")
        or ":" in clean_path
        or ".." in path_parts
    ):
        return None, {
            "index": index,
            "reason": "unsafe_path",
            "path": path,
        }

    if "new_text" not in candidate or not isinstance(candidate.get("new_text"), str):
        return None, {"index": index, "reason": "missing_new_text", "path": path}

    edit: dict[str, Any] = {
        "path": clean_path,
        "new_text": candidate.get("new_text"),
    }
    old_text = candidate.get("old_text")
    if old_text is not None:
        if not isinstance(old_text, str):
            return None, {"index": index, "reason": "invalid_old_text", "path": path}
        edit["old_text"] = old_text

    expected_replacements = candidate.get("expected_replacements")
    if expected_replacements is not None:
        if (
            isinstance(expected_replacements, bool)
            or not isinstance(expected_replacements, int)
            or expected_replacements < 1
            or expected_replacements > 20
        ):
            return None, {
                "index": index,
                "reason": "invalid_expected_replacements",
                "path": path,
            }
        edit["expected_replacements"] = expected_replacements

    for key in ("create_if_missing", "dry_run"):
        if key not in candidate:
            continue
        value = candidate.get(key)
        if not isinstance(value, bool):
            return None, {
                "index": index,
                "reason": f"invalid_{key}",
                "path": path,
            }
        edit[key] = value
    return edit, None


def repair_request_blocks_test_edits(payload: Mapping[str, Any]) -> bool:
    repair_request = payload.get("repair_request")
    fields: list[object] = [
        payload.get("instruction"),
        payload.get("repair_prompt"),
    ]
    if isinstance(repair_request, Mapping):
        fields.extend(
            [
                repair_request.get("instruction"),
                repair_request.get("repair_prompt"),
            ]
        )
    text = "\n".join(str(value).lower() for value in fields if value)
    return any(
        phrase in text
        for phrase in (
            "do not change tests",
            "do not edit tests",
            "without changing tests",
            "do not change test files",
            "do not edit test files",
        )
    )


def repair_edit_signature(edit: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        edit.get("path"),
        edit.get("old_text"),
        edit.get("new_text"),
        edit.get("expected_replacements"),
        edit.get("create_if_missing"),
        edit.get("dry_run"),
    )


def previous_failed_repair_edit_signatures(
    payload: Mapping[str, Any],
) -> set[tuple[object, ...]]:
    repair_request = require_mapping(payload.get("repair_request"))
    if repair_request.get("retry_of_failed_verification") is not True:
        return set()
    previous_attempt = require_mapping(repair_request.get("previous_attempt"))
    signatures: set[tuple[object, ...]] = set()
    for index, candidate in enumerate(
        require_list(previous_attempt.get("attempted_edits")),
        start=1,
    ):
        if not isinstance(candidate, Mapping):
            continue
        edit, _ = validate_repair_edit_candidate(candidate, index=index)
        if edit is not None:
            signatures.add(repair_edit_signature(edit))
    return signatures


def is_test_edit_path(path: str) -> bool:
    clean_path = path.replace("\\", "/").strip().lower()
    parts = [part for part in clean_path.split("/") if part]
    if not parts:
        return False
    if any(part in {"tests", "test", "__tests__"} for part in parts[:-1]):
        return True
    filename = parts[-1]
    return any(
        marker in filename
        for marker in (
            ".test.",
            ".spec.",
            "_test.",
            "-test.",
            "_spec.",
            "-spec.",
        )
    )


def freeform_test_edit_paths(content: str) -> list[str]:
    paths: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        clean_path = path.strip().strip("`'\"").replace("\\", "/")
        if not clean_path or clean_path in seen or not is_test_edit_path(clean_path):
            return
        seen.add(clean_path)
        paths.append(clean_path)

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("diff --git "):
            for token in stripped.split():
                if token.startswith(("a/", "b/")):
                    add(token[2:])
            continue
        if stripped.startswith(("--- a/", "+++ b/")):
            add(stripped[6:].split(maxsplit=1)[0])
            continue
        for match in re.finditer(
            r"(?:^|[\s`'\"])([A-Za-z0-9_.\-/]*(?:tests|test|__tests__)/"
            r"[A-Za-z0-9_.\-/]+)",
            stripped,
        ):
            add(match.group(1))
    return paths


def normalize_unified_diff_path(value: str) -> str | None:
    path = value.strip().split(maxsplit=1)[0].strip("`'\"")
    if not path or path == "/dev/null":
        return None
    if path.startswith(("a/", "b/")):
        path = path[2:]
    return path.replace("\\", "/")


def unified_diff_file_path(line: str) -> str | None:
    parts = line.strip().split()
    if len(parts) < 4 or parts[0] != "diff" or parts[1] != "--git":
        return None
    return normalize_unified_diff_path(parts[3])


def extract_unified_diff_edit_candidates(content: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    current_path: str | None = None
    in_hunk = False
    old_lines: list[str] = []
    new_lines: list[str] = []
    has_removed = False
    has_added = False

    def flush_hunk() -> None:
        nonlocal in_hunk, old_lines, new_lines, has_removed, has_added
        if current_path and in_hunk and has_removed and has_added:
            old_text = "".join(f"{line}\n" for line in old_lines)
            new_text = "".join(f"{line}\n" for line in new_lines)
            if old_text and old_text != new_text:
                candidates.append(
                    {
                        "path": current_path,
                        "old_text": old_text,
                        "new_text": new_text,
                        "expected_replacements": 1,
                    }
                )
        in_hunk = False
        old_lines = []
        new_lines = []
        has_removed = False
        has_added = False

    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_hunk()
            continue
        if line.startswith("diff --git "):
            flush_hunk()
            current_path = unified_diff_file_path(line) or current_path
            continue
        if line.startswith("--- "):
            flush_hunk()
            continue
        if line.startswith("+++ "):
            flush_hunk()
            parsed_path = normalize_unified_diff_path(line[4:])
            if parsed_path:
                current_path = parsed_path
            continue
        if line.startswith("@@"):
            flush_hunk()
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("\\ No newline"):
            continue
        if line.startswith(" "):
            old_lines.append(line[1:])
            new_lines.append(line[1:])
        elif line.startswith("-"):
            old_lines.append(line[1:])
            has_removed = True
        elif line.startswith("+"):
            new_lines.append(line[1:])
            has_added = True
        else:
            flush_hunk()

    flush_hunk()
    return candidates


def extract_repair_edits(
    *,
    path: Path,
    payload: Mapping[str, Any],
    max_edits: int,
    max_files: int | None,
) -> dict[str, Any]:
    if max_edits < 1:
        raise BiberAgentClientError("--max-edits must be at least 1.")
    if max_files is not None and max_files < 1:
        raise BiberAgentClientError("--max-files must be at least 1.")

    content = str(payload.get("repair_content") or "")
    if not content:
        model_response = require_mapping(payload.get("model_response"))
        content = str(model_response.get("content") or "")
    json_values = extract_json_values_from_text(content)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    source_only_guard_enabled = repair_request_blocks_test_edits(payload)
    repeated_failed_edit_signatures = previous_failed_repair_edit_signatures(payload)
    candidate_index = 0
    for value in json_values:
        for candidate in extract_edit_objects_from_value(value):
            candidate_index += 1
            edit, rejection = validate_repair_edit_candidate(
                candidate,
                index=candidate_index,
            )
            if (
                edit is not None
                and source_only_guard_enabled
                and is_test_edit_path(str(edit.get("path") or ""))
            ):
                rejected.append(
                    {
                        "index": candidate_index,
                        "reason": "test_file_edit_blocked_by_source_only_instruction",
                        "path": edit.get("path"),
                    }
                )
            elif (
                edit is not None
                and repair_edit_signature(edit) in repeated_failed_edit_signatures
            ):
                rejected.append(
                    {
                        "index": candidate_index,
                        "reason": "repeated_failed_repair_edit",
                        "path": edit.get("path"),
                    }
                )
            elif edit is not None:
                accepted.append(edit)
            elif rejection is not None:
                rejected.append(rejection)
            if len(accepted) >= max_edits:
                break
        if len(accepted) >= max_edits:
            break

    unified_diff_candidates = extract_unified_diff_edit_candidates(content)
    for candidate in unified_diff_candidates:
        if len(accepted) >= max_edits:
            break
        candidate_index += 1
        edit, rejection = validate_repair_edit_candidate(
            candidate,
            index=candidate_index,
        )
        if (
            edit is not None
            and source_only_guard_enabled
            and is_test_edit_path(str(edit.get("path") or ""))
        ):
            rejected.append(
                {
                    "index": candidate_index,
                    "reason": "test_file_edit_blocked_by_source_only_instruction",
                    "path": edit.get("path"),
                }
            )
        elif (
            edit is not None
            and repair_edit_signature(edit) in repeated_failed_edit_signatures
        ):
            rejected.append(
                {
                    "index": candidate_index,
                    "reason": "repeated_failed_repair_edit",
                    "path": edit.get("path"),
                }
            )
        elif edit is not None:
            accepted.append(edit)
        elif rejection is not None:
            rejected.append(rejection)

    if source_only_guard_enabled:
        rejected_paths = {
            str(item.get("path") or "")
            for item in rejected
            if item.get("reason")
            in {
                "test_file_edit_blocked_by_source_only_instruction",
                "freeform_test_file_edit_blocked_by_source_only_instruction",
            }
        }
        for blocked_path in freeform_test_edit_paths(content):
            if blocked_path in rejected_paths:
                continue
            rejected.append(
                {
                    "reason": (
                        "freeform_test_file_edit_blocked_by_source_only_instruction"
                    ),
                    "path": blocked_path,
                }
            )
            rejected_paths.add(blocked_path)

    plan_edit_payload: dict[str, Any] = {"edits": accepted}
    if max_files is not None:
        plan_edit_payload["max_files"] = max_files
    return {
        "source": "biber_mvp_loop_repair_edit_extraction",
        "repair_loop_version": "mvp-v1",
        "source_artifact": str(path),
        "extraction_status": "ready_for_plan_edit" if accepted else "no_valid_edits",
        "ok": bool(accepted),
        "training_allowed": False,
        "auto_applied": False,
        "apply_allowed": False,
        "review_status": "needs_review",
        "edits": accepted,
        "rejected": rejected,
        "source_only_guard": {
            "enabled": source_only_guard_enabled,
            "blocked_test_edits": sum(
                1
                for item in rejected
                if item.get("reason")
                in {
                    "test_file_edit_blocked_by_source_only_instruction",
                    "freeform_test_file_edit_blocked_by_source_only_instruction",
                }
            ),
        },
        "repeat_failed_edit_guard": {
            "enabled": bool(repeated_failed_edit_signatures),
            "blocked_repeated_edits": sum(
                1
                for item in rejected
                if item.get("reason") == "repeated_failed_repair_edit"
            ),
        },
        "json_values_found": len(json_values),
        "unified_diff_candidates_found": len(unified_diff_candidates),
        "max_edits": max_edits,
        "max_files": max_files,
        "plan_edit_payload": plan_edit_payload,
        "next_test_id": payload.get("next_test_id"),
        "next_workflow": [
            "review_extracted_edits",
            "run_plan_edit_with_plan_edit_payload",
            "apply_only_after_human_or_policy_approval",
            "rerun_next_test_id",
            "diagnose_again_if_still_failing",
        ],
    }


def normalize_repair_edit_extraction_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_edit_extraction":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_repair_edit_extraction"
    ):
        return dict(body)
    return None


def normalize_retry_repair_edit_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_retry_repair_edit_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_retry_repair_edit_review"
    ):
        return dict(body)
    return None


def summarize_repair_edit_extraction_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    edits = [
        item for item in require_list(payload.get("edits")) if isinstance(item, dict)
    ]
    rejected = [
        item for item in require_list(payload.get("rejected")) if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "extraction_status": payload.get("extraction_status"),
        "ok": payload.get("ok") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "auto_applied": payload.get("auto_applied") is True,
        "apply_allowed": payload.get("apply_allowed") is True,
        "review_status": payload.get("review_status"),
        "edits": len(edits),
        "rejected": len(rejected),
        "json_values_found": int_count(payload.get("json_values_found")),
        "next_test_id": payload.get("next_test_id"),
        "source_artifact": payload.get("source_artifact"),
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    if payload.get("edits_output"):
        summary["edits_output"] = payload.get("edits_output")
    return summary


def list_repair_edit_extraction_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Repair edit extraction artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Repair edit extraction artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair-edit extraction artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_edit_extraction_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_repair_edit_extraction_artifact(path, normalized)
        if ready_only and summary.get("extraction_status") != "ready_for_plan_edit":
            continue
        artifacts.append(summary)

    artifacts.sort(key=lambda item: float(item.get("modified_epoch") or 0.0), reverse=True)
    ready_count = sum(
        1
        for item in artifacts
        if item.get("extraction_status") == "ready_for_plan_edit"
    )
    return {
        "source": "biber_mvp_loop_repair_edit_extraction_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ready_for_plan_edit": ready_count,
        "training_allowed": False,
        "auto_applied": False,
        "apply_allowed": False,
        "artifacts": artifacts[:limit],
    }


def repair_edit_same_previous_target(
    edit: Mapping[str, Any],
    previous_edits: list[Mapping[str, Any]],
) -> bool:
    edit_path = str(edit.get("path") or "")
    edit_old_text = str(edit.get("old_text") or "")
    if not edit_path or not edit_old_text:
        return False
    return any(
        str(previous.get("path") or "") == edit_path
        and str(previous.get("old_text") or "") == edit_old_text
        for previous in previous_edits
    )


def failure_expected_literals(*failures: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for failure in failures:
        primary_category = str(failure.get("primary_category") or "").strip()
        if primary_category:
            values.append(primary_category)
        relevant_output = str(failure.get("relevant_output") or "")
        for match in re.finditer(
            r"assert\s+['\"]([^'\"]+)['\"]\s+==\s+['\"]([^'\"]+)['\"]",
            relevant_output,
        ):
            values.extend([match.group(1), match.group(2)])
    return dedupe_strings(values) or []


def failure_assertion_diffs(*failures: Mapping[str, Any]) -> list[dict[str, str]]:
    diffs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for failure in failures:
        relevant_output = str(failure.get("relevant_output") or "")
        for match in re.finditer(
            r"assert\s+['\"]([^'\"]+)['\"]\s+==\s+['\"]([^'\"]+)['\"]",
            relevant_output,
        ):
            actual = match.group(1)
            expected = match.group(2)
            key = (actual, expected)
            if key in seen:
                continue
            seen.add(key)
            diffs.append({"actual": actual, "expected": expected})
    return diffs


def strip_line_numbered_snippet_line(line: str) -> str:
    return re.sub(r"^\s*\d+:\s?", "", line).rstrip()


def retry_rule_category_edit_suggestions(
    *,
    source_context_snippets: list[Mapping[str, Any]],
    original_failure: Mapping[str, Any],
    verification_failure: Mapping[str, Any],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for diff in failure_assertion_diffs(original_failure, verification_failure):
        actual = diff.get("actual")
        expected = diff.get("expected")
        if not actual or not expected or actual == expected:
            continue
        suggestion_added = False
        for snippet in source_context_snippets:
            if snippet.get("snippet_kind") != "rule":
                continue
            path = str(snippet.get("path") or "")
            if not path:
                continue
            for raw_line in str(snippet.get("snippet") or "").splitlines():
                old_text = strip_line_numbered_snippet_line(raw_line)
                if "_Rule(" not in old_text:
                    continue
                matches = list(re.finditer(r"([\"'])([^\"']+)\1", old_text))
                if len(matches) < 2 or matches[1].group(2) != actual:
                    continue
                category_match = matches[1]
                new_text = (
                    old_text[: category_match.start(2)]
                    + expected
                    + old_text[category_match.end(2) :]
                )
                suggestions.append(
                    {
                        "path": path,
                        "old_text": old_text,
                        "new_text": new_text,
                        "expected_replacements": 1,
                        "reason": (
                            "assertion_diff_category_mismatch_in_rule_context"
                        ),
                    }
                )
                suggestion_added = True
                break
            if suggestion_added:
                break
    return suggestions[:4]


def retry_rule_pattern_matches_terms(pattern: str, terms: list[str]) -> bool:
    pattern_text = pattern.strip()
    if not pattern_text:
        return False
    lowered_pattern = pattern_text.lower()
    if any(lowered_pattern in term.lower() for term in terms):
        return True
    try:
        compiled = re.compile(pattern_text, flags=re.IGNORECASE)
    except re.error:
        return False
    return any(compiled.search(term) for term in terms)


def retry_rule_category_edit_suggestions_from_sources(
    *,
    source_root: Path,
    selected_context_paths: list[str],
    original_failure: Mapping[str, Any],
    verification_failure: Mapping[str, Any],
    failure_line_refs_by_path: Mapping[str, set[int]],
    context_lines: int,
) -> list[dict[str, Any]]:
    try:
        root = source_root.resolve()
    except OSError:
        root = source_root
    terms = retry_context_terms(
        attempted_edits=[],
        original_failure=original_failure,
        verification_failure=verification_failure,
    )
    terms = dedupe_strings(
        [
            *terms,
            *retry_failure_line_context_terms(
                source_root=root,
                failure_line_refs_by_path=failure_line_refs_by_path,
                context_lines=max(context_lines, 4),
            ),
        ]
    ) or []

    suggestions: list[dict[str, Any]] = []
    for diff in failure_assertion_diffs(original_failure, verification_failure):
        actual = diff.get("actual")
        expected = diff.get("expected")
        if not actual or not expected or actual == expected:
            continue
        suggestion_added = False
        for raw_path in selected_context_paths:
            clean_path = safe_repo_relative_path(raw_path)
            if clean_path is None or is_test_edit_path(clean_path):
                continue
            file_path = (root / clean_path).resolve()
            if file_path != root and root not in file_path.parents:
                continue
            if not file_path.is_file():
                continue
            try:
                lines = file_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).splitlines()
            except OSError:
                continue
            for line in lines:
                old_text = line.rstrip()
                if "_Rule(" not in old_text:
                    continue
                matches = list(re.finditer(r"([\"'])([^\"']+)\1", old_text))
                if len(matches) < 2 or matches[1].group(2) != actual:
                    continue
                pattern = matches[0].group(2)
                if not retry_rule_pattern_matches_terms(pattern, terms):
                    continue
                category_match = matches[1]
                new_text = (
                    old_text[: category_match.start(2)]
                    + expected
                    + old_text[category_match.end(2) :]
                )
                suggestions.append(
                    {
                        "path": clean_path,
                        "old_text": old_text,
                        "new_text": new_text,
                        "expected_replacements": 1,
                        "reason": (
                            "assertion_diff_category_mismatch_in_rule_context"
                        ),
                    }
                )
                suggestion_added = True
                break
            if suggestion_added:
                break
    return suggestions[:4]


def dedupe_rule_category_edit_suggestions(
    suggestions: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[object, ...]] = set()
    for suggestion in suggestions:
        edit = {
            key: suggestion.get(key)
            for key in (
                "path",
                "old_text",
                "new_text",
                "expected_replacements",
                "create_if_missing",
                "dry_run",
            )
            if key in suggestion
        }
        signature = repair_edit_signature(edit)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(dict(suggestion))
    return deduped[:4]


def plan_safe_repair_edits_from_candidates(
    candidates: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    for candidate in candidates:
        edit = {
            key: candidate.get(key)
            for key in (
                "path",
                "old_text",
                "new_text",
                "expected_replacements",
                "create_if_missing",
                "dry_run",
            )
            if key in candidate
        }
        edits.append(edit)
    return edits


def build_retry_repair_edit_review(
    *,
    extraction_path: Path,
    extraction: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        extraction.get("ok") is not True
        or extraction.get("extraction_status") != "ready_for_plan_edit"
    ):
        raise BiberAgentClientError(
            "review-retry-repair-edits requires a ready_for_plan_edit extraction artifact."
        )

    attempt_path, attempt, attempt_error = load_linked_artifact(
        extraction.get("source_artifact"),
        base_path=extraction_path,
        label="repair-attempt artifact",
        normalizer=normalize_repair_attempt_artifact,
    )
    if attempt_error is not None or attempt_path is None or attempt is None:
        raise BiberAgentClientError(
            "Could not load linked repair-attempt artifact for retry edit review: "
            f"{attempt_error or 'missing source_artifact'}"
        )

    repair_request = require_mapping(attempt.get("repair_request"))
    if repair_request.get("retry_of_failed_verification") is not True:
        raise BiberAgentClientError(
            "review-retry-repair-edits requires a retry repair attempt."
        )

    edits = [
        dict(item)
        for item in require_list(extraction.get("edits"))
        if isinstance(item, Mapping)
    ]
    previous_attempt = require_mapping(repair_request.get("previous_attempt"))
    previous_edits = [
        dict(item)
        for item in require_list(previous_attempt.get("attempted_edits"))
        if isinstance(item, Mapping)
    ]
    forbidden_edits = [
        dict(item)
        for item in require_list(repair_request.get("forbidden_edits"))
        if isinstance(item, Mapping)
    ] or previous_edits
    source_context_snippets = [
        dict(item)
        for item in require_list(repair_request.get("source_context_snippets"))
        if isinstance(item, Mapping)
    ]
    rule_snippets = [
        item
        for item in source_context_snippets
        if item.get("snippet_kind") == "rule"
    ]
    test_expectation_with_refs = [
        item
        for item in source_context_snippets
        if item.get("snippet_kind") == "test_expectation"
        and require_list(item.get("failure_line_refs"))
    ]
    original_failure = require_mapping(repair_request.get("original_failure"))
    verification_failure = require_mapping(repair_request.get("failure"))
    expected_literals = failure_expected_literals(
        original_failure,
        verification_failure,
    )

    hard_blockers: list[str] = []
    review_hints: list[str] = []
    candidate_reviews: list[dict[str, Any]] = []

    if rule_snippets:
        review_hints.append("source_rule_context_present")
    if test_expectation_with_refs:
        review_hints.append("failure_line_test_expectation_present")

    for index, edit in enumerate(edits, start=1):
        path = str(edit.get("path") or "")
        old_text = str(edit.get("old_text") or "")
        new_text = str(edit.get("new_text") or "")
        same_previous_target = repair_edit_same_previous_target(
            edit,
            forbidden_edits,
        )
        path_rule_snippets = [
            item for item in rule_snippets if str(item.get("path") or "") == path
        ]
        old_text_in_rule_context = any(
            old_text and old_text in str(item.get("snippet") or "")
            for item in path_rule_snippets
        )
        candidate_hints: list[str] = []
        candidate_blockers: list[str] = []

        if same_previous_target:
            candidate_hints.append("candidate_reuses_previous_failed_target_line")
        if (
            same_previous_target
            and path_rule_snippets
            and not old_text_in_rule_context
            and test_expectation_with_refs
        ):
            candidate_blockers.append(
                "retry_edit_changes_previous_failed_target_outside_rule_context"
            )
        if (
            same_previous_target
            and " else " in f" {new_text.lower()} "
            and any(literal and literal in new_text for literal in expected_literals)
        ):
            candidate_hints.append("expected_literal_fallback_candidate")
        if path_rule_snippets and old_text_in_rule_context:
            candidate_hints.append("candidate_edits_rule_context")

        hard_blockers.extend(candidate_blockers)
        review_hints.extend(candidate_hints)
        candidate_reviews.append(
            {
                "index": index,
                "path": path,
                "allowed_for_plan": not candidate_blockers,
                "hard_blockers": candidate_blockers,
                "review_hints": candidate_hints,
                "same_previous_failed_target": same_previous_target,
                "rule_context_for_path": bool(path_rule_snippets),
                "old_text_in_rule_context": old_text_in_rule_context,
            }
        )

    hard_blockers = dedupe_strings(hard_blockers) or []
    review_hints = dedupe_strings(review_hints) or []
    plan_allowed = bool(edits) and not hard_blockers
    reviewed_plan_edit_payload: dict[str, Any] = {
        "edits": edits if plan_allowed else []
    }
    max_files = extraction.get("max_files")
    if max_files is not None:
        reviewed_plan_edit_payload["max_files"] = max_files

    return {
        "source": "biber_mvp_loop_retry_repair_edit_review",
        "repair_loop_version": extraction.get("repair_loop_version")
        or attempt.get("repair_loop_version"),
        "source_artifact": str(extraction_path),
        "repair_attempt_artifact": str(attempt_path),
        "repair_request_source_artifact": repair_request.get("source_artifact"),
        "review_status": (
            "retry_edit_ready_for_plan_review"
            if plan_allowed
            else "retry_edit_blocked_needs_human_review"
        ),
        "ok": plan_allowed,
        "plan_allowed": plan_allowed,
        "apply_allowed": False,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_applied": False,
        "auto_saved": False,
        "next_test_id": extraction.get("next_test_id") or attempt.get("next_test_id"),
        "edits": edits,
        "reviewed_plan_edit_payload": reviewed_plan_edit_payload,
        "candidate_reviews": candidate_reviews,
        "hard_blockers": hard_blockers,
        "review_hints": review_hints,
        "forbidden_edits": forbidden_edits,
        "source_context_snippets": source_context_snippets,
        "model": require_mapping(attempt.get("model_response")).get("model"),
        "mentor_used": require_mapping(attempt.get("model_response")).get("mentor_used")
        is True,
        "runtime_profile_ids": repair_attempt_runtime_profile_ids(attempt) or [],
        "next_workflow": (
            [
                "run_plan_repair_edits_only_after_review_acceptance",
                "apply_only_after_human_or_policy_approval",
                "rerun_next_test_id",
                "export_verified_repair_only_if_verification_passes",
            ]
            if plan_allowed
            else [
                "do_not_plan_or_apply_this_retry_candidate",
                "human_review_or_improve_prompt_context",
                "capture_as_review_only_failure_evidence_if_repeated",
            ]
        ),
    }


def build_plan_repair_edits_payload(
    extraction: Mapping[str, Any],
    *,
    max_files: int | None,
) -> dict[str, Any]:
    payload = require_mapping(extraction.get("plan_edit_payload")).copy()
    edits = require_list(payload.get("edits"))
    if not edits:
        raise BiberAgentClientError(
            "plan-repair-edits requires an extraction artifact with at least one edit."
        )
    if max_files is not None:
        if max_files < 1:
            raise BiberAgentClientError("--max-files must be at least 1.")
        payload["max_files"] = max_files
    return payload


def artifact_path_matches(expected_path: Path, reference: object) -> bool:
    linked_path = resolve_linked_artifact_path(reference, base_path=expected_path)
    if linked_path is None:
        return False
    try:
        return expected_path.resolve() == linked_path.resolve()
    except OSError:
        return str(expected_path) == str(linked_path)


def repair_extraction_is_retry_attempt(
    *,
    extraction_path: Path,
    extraction: Mapping[str, Any],
) -> bool:
    if extraction.get("retry_of_failed_verification") is True:
        return True
    reference = extraction.get("source_artifact")
    if not isinstance(reference, str) or not reference.strip():
        return False
    _, attempt, attempt_error = load_linked_artifact(
        reference,
        base_path=extraction_path,
        label="repair-attempt artifact",
        normalizer=normalize_repair_attempt_artifact,
    )
    if attempt_error is not None or attempt is None:
        return False
    repair_request = require_mapping(attempt.get("repair_request"))
    return repair_request.get("retry_of_failed_verification") is True


def build_plan_repair_edits_payload_with_retry_review(
    *,
    extraction_path: Path,
    extraction: Mapping[str, Any],
    max_files: int | None,
    retry_review_artifact: str | None,
) -> dict[str, Any]:
    if not repair_extraction_is_retry_attempt(
        extraction_path=extraction_path,
        extraction=extraction,
    ):
        return build_plan_repair_edits_payload(extraction, max_files=max_files)

    if not retry_review_artifact:
        raise BiberAgentClientError(
            "plan-repair-edits requires --retry-review-artifact for retry repair "
            "edit extractions. Run review-retry-repair-edits first and pass an "
            "accepted review artifact."
        )

    review_path = Path(retry_review_artifact)
    raw_review = load_json_artifact(
        str(review_path),
        label="retry repair edit review artifact",
    )
    review = normalize_retry_repair_edit_review_artifact(raw_review)
    if review is None:
        raise BiberAgentClientError(
            "--retry-review-artifact must contain a saved review-retry-repair-edits "
            "JSON object."
        )
    if not artifact_path_matches(extraction_path, review.get("source_artifact")):
        raise BiberAgentClientError(
            "--retry-review-artifact does not review the provided extraction artifact."
        )
    if (
        review.get("ok") is not True
        or review.get("plan_allowed") is not True
        or require_list(review.get("hard_blockers"))
    ):
        raise BiberAgentClientError(
            "Retry repair edit review does not allow planning: "
            f"{review.get('review_status') or 'review_not_accepted'}."
        )

    payload = require_mapping(review.get("reviewed_plan_edit_payload")).copy()
    edits = require_list(payload.get("edits"))
    if not edits:
        raise BiberAgentClientError(
            "Accepted retry repair edit review did not include any reviewed edits."
        )
    if max_files is not None:
        if max_files < 1:
            raise BiberAgentClientError("--max-files must be at least 1.")
        payload["max_files"] = max_files
    return payload


def infer_retry_repair_target_root(
    *,
    extraction_path: Path,
    extraction: Mapping[str, Any],
) -> tuple[Path | None, str | None]:
    attempt_path, attempt, attempt_error = load_linked_artifact(
        extraction.get("source_artifact"),
        base_path=extraction_path,
        label="repair-attempt artifact",
        normalizer=normalize_repair_attempt_artifact,
    )
    if attempt_error is not None or attempt_path is None or attempt is None:
        return None, None
    repair_request = require_mapping(attempt.get("repair_request"))
    if repair_request.get("retry_of_failed_verification") is not True:
        return None, None
    source_context = require_mapping(repair_request.get("source_context"))
    raw_source_root = source_context.get("source_root")
    if not isinstance(raw_source_root, str) or not raw_source_root.strip():
        return None, None
    target_root = Path(raw_source_root.strip())
    if not target_root.is_dir():
        return None, None
    return target_root, "retry_source_context"


def resolve_repair_target_root(
    *,
    cli_target_root: str | None,
    extraction_path: Path,
    extraction: Mapping[str, Any],
) -> tuple[Path | None, str | None]:
    if cli_target_root:
        return validate_local_target_root(Path(cli_target_root)), "cli_target_root"
    target_root, target_source = infer_retry_repair_target_root(
        extraction_path=extraction_path,
        extraction=extraction,
    )
    if target_root is not None:
        return validate_local_target_root(target_root), target_source
    return None, None


def resolve_apply_target_root(
    *,
    cli_target_root: str | None,
    plan: Mapping[str, Any],
) -> tuple[Path | None, str | None]:
    if cli_target_root:
        return validate_local_target_root(Path(cli_target_root)), "cli_target_root"
    raw_target_root = plan.get("target_root")
    if isinstance(raw_target_root, str) and raw_target_root.strip():
        return (
            validate_local_target_root(Path(raw_target_root.strip())),
            str(plan.get("target_root_source") or "plan_target_root"),
        )
    return None, None


def apply_repair_edits_has_local_target(args: argparse.Namespace) -> bool:
    if args.command != "apply-repair-edits" or not args.approve:
        return False
    if args.target_root:
        return True
    try:
        artifact = load_json_artifact(
            str(Path(args.artifact)),
            label="repair-edit plan artifact",
        )
    except BiberAgentClientError:
        return False
    plan = normalize_repair_edit_plan_artifact(artifact)
    if plan is None:
        return False
    target_root = plan.get("target_root")
    return isinstance(target_root, str) and bool(target_root.strip())


def build_local_model_command_request(
    *,
    repair_request: Mapping[str, Any],
    model: str | None,
) -> dict[str, Any]:
    runtime_profile_ids = normalize_runtime_profile_ids(
        repair_request.get("runtime_profile_ids")
    )
    chat_payload = build_repair_chat_payload(
        repair_request=repair_request,
        model=model,
        max_tokens=None,
        temperature=0.0,
        use_mentor=False,
        runtime_profile_ids=runtime_profile_ids,
    )
    return {
        "source": "biber_local_model_command_request",
        "repair_loop_version": "mvp-v1",
        "model": model or "local-command-provider",
        "mentor_used": False,
        "training_allowed": False,
        "api_required": False,
        "stdin_contract": "json",
        "stdout_contract": "raw model text or JSON object with a string content field",
        "repair_request": dict(repair_request),
        "chat_payload": chat_payload,
        "response_guidance": {
            "preferred": {"edits": [{"path": "...", "old_text": "...", "new_text": "..."}]},
            "accepted_stdout": [
                "raw repair text",
                "JSON object with content/text/repair_content",
                "JSON object or array that is itself the model response",
            ],
        },
    }


def normalize_local_model_command_stdout(stdout: str) -> tuple[str, dict[str, Any]]:
    content = stdout.strip()
    if not content:
        raise BiberAgentClientError("--model-command produced empty stdout.")
    metadata: dict[str, Any] = {
        "stdout_format": "raw_text",
        "stdout_json_keys": [],
    }
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return content, metadata
    metadata["stdout_format"] = "json"
    if isinstance(parsed, dict):
        metadata["stdout_json_keys"] = sorted(str(key) for key in parsed)
        for key in ("content", "text", "repair_content"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                metadata["content_field"] = key
                return value, metadata
        return json.dumps(parsed, sort_keys=True), metadata
    if isinstance(parsed, list):
        metadata["stdout_format"] = "json_array"
        return json.dumps(parsed, sort_keys=True), metadata
    return str(parsed), metadata


def run_local_model_command(
    *,
    command: str,
    request: Mapping[str, Any],
    timeout_seconds: float,
) -> tuple[str, dict[str, Any]]:
    if timeout_seconds <= 0:
        raise BiberAgentClientError("--model-command-timeout-seconds must be greater than 0.")
    command_parts = parse_local_model_command(command)
    request_text = json.dumps(request, indent=2, sort_keys=True)
    try:
        completed = subprocess.run(
            command_parts,
            input=request_text,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise BiberAgentClientError(
            f"--model-command executable not found: {command_parts[0]}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise BiberAgentClientError(
            f"--model-command timed out after {timeout_seconds} seconds."
        ) from exc
    except OSError as exc:
        raise BiberAgentClientError(f"--model-command failed to start: {exc}") from exc
    stderr_snippet = completed.stderr.strip()[:1000]
    if completed.returncode != 0:
        suffix = f" stderr: {stderr_snippet}" if stderr_snippet else ""
        raise BiberAgentClientError(
            f"--model-command exited with code {completed.returncode}.{suffix}"
        )
    content, output_metadata = normalize_local_model_command_stdout(completed.stdout)
    metadata = {
        "source": "local_model_command",
        "command": command_parts,
        "exit_code": completed.returncode,
        "timeout_seconds": timeout_seconds,
        "stderr_snippet": stderr_snippet,
        "request_source": request.get("source"),
        **output_metadata,
    }
    return content, metadata


def resolve_verify_target_root(
    *,
    cli_target_root: str | None,
    repair_apply: Mapping[str, Any],
) -> tuple[Path | None, str | None]:
    if cli_target_root:
        return validate_local_target_root(Path(cli_target_root)), "cli_target_root"
    raw_target_root = repair_apply.get("target_root")
    if isinstance(raw_target_root, str) and raw_target_root.strip():
        return (
            validate_local_target_root(Path(raw_target_root.strip())),
            str(repair_apply.get("target_root_source") or "apply_target_root"),
        )
    return None, None


def build_plan_repair_edits_result(
    *,
    extraction_path: Path,
    extraction: Mapping[str, Any],
    plan_payload: Mapping[str, Any],
    edit_plan: Mapping[str, Any],
    plan_mode: str = "api_workspace_root",
    target_root: Path | None = None,
    target_root_source: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source": "biber_mvp_loop_repair_edit_plan",
        "repair_loop_version": "mvp-v1",
        "source_artifact": str(extraction_path),
        "plan_mode": plan_mode,
        "plan_status": "planned" if edit_plan.get("ok") is True else "rejected",
        "ok": edit_plan.get("ok") is True,
        "training_allowed": False,
        "auto_applied": False,
        "apply_allowed": False,
        "review_status": "needs_review",
        "plan_hash": edit_plan.get("plan_hash"),
        "next_test_id": extraction.get("next_test_id"),
        "plan_edit_payload": dict(plan_payload),
        "edit_plan": dict(edit_plan),
        "next_workflow": [
            "review_server_side_edit_plan",
            "apply_only_after_human_or_policy_approval",
            "rerun_next_test_id",
            "diagnose_again_if_still_failing",
        ],
    }
    if target_root is not None:
        result["target_root"] = str(target_root)
        result["target_root_source"] = target_root_source or "unknown"
    return result


def build_local_repair_chain_result(
    *,
    source_path: Path,
    repair_request: Mapping[str, Any],
    model_response_text: str,
    model_response_source: Mapping[str, Any] | None,
    model: str | None,
    max_edits: int,
    max_files: int | None,
    target_root: Path | None,
) -> dict[str, Any]:
    content = model_response_text.strip()
    if not content:
        raise BiberAgentClientError(
            "local-repair-chain requires --model-response or --model-response-file."
        )
    runtime_profile_ids = normalize_runtime_profile_ids(
        repair_request.get("runtime_profile_ids")
    )
    chat_payload = build_repair_chat_payload(
        repair_request=repair_request,
        model=model,
        max_tokens=None,
        temperature=0.0,
        use_mentor=False,
        runtime_profile_ids=runtime_profile_ids,
    )
    model_response = {
        "model": model or "local-supplied-response",
        "content": content,
        "mentor_used": False,
        "local_supplied": True,
        "local_response_source": dict(
            model_response_source or {"source": "local_supplied_response"}
        ),
    }
    repair_attempt = build_repair_attempt_result(
        repair_request=repair_request,
        chat_payload=chat_payload,
        model_response=model_response,
    )
    repair_attempt["artifact_ref"] = "local_repair_chain.repair_attempt"
    extraction = extract_repair_edits(
        path=source_path,
        payload=repair_attempt,
        max_edits=max_edits,
        max_files=max_files,
    )
    extraction["source_artifact"] = "local_repair_chain.repair_attempt"
    extraction["artifact_ref"] = "local_repair_chain.repair_edit_extraction"

    plan_result: dict[str, Any] | None = None
    plan_skipped_reason: str | None = None
    if target_root is not None and extraction.get("ok") is True:
        plan_payload = build_plan_repair_edits_payload(extraction, max_files=max_files)
        edit_plan = plan_workspace_edit_local_target(
            target_root=target_root,
            payload=plan_payload,
        )
        plan_result = build_plan_repair_edits_result(
            extraction_path=Path("local_repair_chain.repair_edit_extraction"),
            extraction=extraction,
            plan_payload=plan_payload,
            edit_plan=edit_plan,
            plan_mode="local_target_root",
            target_root=target_root,
            target_root_source="cli_target_root",
        )
    elif target_root is not None:
        plan_skipped_reason = "no_valid_edits"
    else:
        plan_skipped_reason = "target_root_not_supplied"

    chain_status = (
        "planned"
        if plan_result is not None and plan_result.get("ok") is True
        else "plan_rejected"
        if plan_result is not None
        else "extracted"
        if extraction.get("ok") is True
        else "no_valid_edits"
    )
    result: dict[str, Any] = {
        "source": "biber_local_repair_chain",
        "repair_loop_version": "mvp-v1",
        "source_artifact": str(source_path),
        "chain_status": chain_status,
        "ok": chain_status in {"planned", "extracted"},
        "training_allowed": False,
        "auto_applied": False,
        "apply_allowed": False,
        "mentor_used": False,
        "model_response_source": dict(
            model_response_source or {"source": "local_supplied_response"}
        ),
        "repair_request": dict(repair_request),
        "repair_attempt": repair_attempt,
        "repair_edit_extraction": extraction,
        "next_test_id": repair_request.get("next_test_id"),
        "next_workflow": [
            "review_local_repair_chain",
            "run_plan_repair_edits_with_target_root_if_not_already_planned",
            "apply_only_after_human_or_policy_approval",
            "rerun_next_test_id",
            "diagnose_again_if_still_failing",
        ],
    }
    if plan_result is not None:
        result["repair_edit_plan"] = plan_result
    if plan_skipped_reason is not None:
        result["plan_skipped_reason"] = plan_skipped_reason
    if target_root is not None:
        result["target_root"] = str(target_root)
        result["target_root_source"] = "cli_target_root"
    return result


def normalize_local_repair_chain_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_local_repair_chain":
        return dict(payload)
    body = payload.get("body")
    if isinstance(body, dict) and body.get("source") == "biber_local_repair_chain":
        return dict(body)
    return None


def review_local_repair_chain(chain: Mapping[str, Any]) -> dict[str, Any]:
    extraction = require_mapping(chain.get("repair_edit_extraction"))
    plan = require_mapping(chain.get("repair_edit_plan"))
    edit_plan = require_mapping(plan.get("edit_plan"))
    edits = [
        item for item in require_list(extraction.get("edits")) if isinstance(item, dict)
    ]
    extraction_rejected = [
        item
        for item in require_list(extraction.get("rejected"))
        if isinstance(item, dict)
    ]
    planned = [
        item for item in require_list(edit_plan.get("planned")) if isinstance(item, dict)
    ]
    plan_rejected = [
        item for item in require_list(edit_plan.get("rejected")) if isinstance(item, dict)
    ]
    blockers: list[str] = []
    warnings: list[str] = []

    if chain.get("ok") is not True:
        blockers.append("chain_not_ok")
    if chain.get("chain_status") != "planned":
        blockers.append("chain_not_planned")
    if chain.get("training_allowed") is True:
        blockers.append("training_allowed_true")
    if chain.get("auto_applied") is True:
        blockers.append("auto_applied_true")
    if chain.get("apply_allowed") is True:
        blockers.append("apply_allowed_true")
    if extraction.get("ok") is not True:
        blockers.append("extraction_not_ok")
    if extraction.get("extraction_status") != "ready_for_plan_edit":
        blockers.append("extraction_not_ready")
    if not edits:
        blockers.append("no_extracted_edits")

    if not plan:
        blockers.append("missing_local_plan")
    else:
        plan_hash = plan.get("plan_hash")
        edit_plan_hash = edit_plan.get("plan_hash")
        if plan.get("ok") is not True:
            blockers.append("plan_not_ok")
        if plan.get("plan_status") != "planned":
            blockers.append("plan_not_planned")
        if not isinstance(plan_hash, str) or len(plan_hash) != 64:
            blockers.append("invalid_plan_hash")
        if isinstance(edit_plan_hash, str) and edit_plan_hash != plan_hash:
            blockers.append("plan_hash_mismatch")
        if not planned:
            blockers.append("no_planned_edits")
        if plan_rejected:
            blockers.append("plan_has_rejections")
        if plan.get("training_allowed") is True:
            blockers.append("plan_training_allowed_true")
        if plan.get("auto_applied") is True:
            blockers.append("plan_auto_applied_true")
        if plan.get("apply_allowed") is True:
            blockers.append("plan_apply_allowed_true")
        if len(planned) != len(edits):
            warnings.append("planned_edit_count_differs")

    if extraction_rejected:
        warnings.append("extraction_has_rejections")
    if not (chain.get("target_root") or plan.get("target_root")):
        warnings.append("target_root_missing")

    ok = not blockers
    review_status = (
        "ready_for_explicit_apply_approval" if ok else "blocked_before_apply"
    )
    return {
        "source": "biber_local_repair_chain_review",
        "repair_loop_version": "mvp-v1",
        "source_artifact": chain.get("artifact_path") or chain.get("source_artifact"),
        "chain_source_artifact": chain.get("source_artifact"),
        "review_status": review_status,
        "ok": ok,
        "apply_recommendation": (
            "ready_for_explicit_apply_approval" if ok else "do_not_apply"
        ),
        "training_allowed": False,
        "auto_applied": False,
        "apply_allowed": False,
        "approval_required": True,
        "approval_received": False,
        "mentor_used": False,
        "blockers": blockers,
        "warnings": warnings,
        "chain_status": chain.get("chain_status"),
        "extraction_status": extraction.get("extraction_status"),
        "plan_status": plan.get("plan_status") if plan else None,
        "edits": len(edits),
        "planned": len(planned),
        "rejected": len(extraction_rejected) + len(plan_rejected),
        "plan_hash": plan.get("plan_hash") if plan else None,
        "target_root": chain.get("target_root") or plan.get("target_root"),
        "next_test_id": chain.get("next_test_id") or plan.get("next_test_id"),
        "next_workflow": [
            "human_review_plan_hash_and_paths",
            "only_then_run_apply-repair-edits_with_--approve",
            "rerun_next_test_id",
            "diagnose_again_if_still_failing",
        ],
    }


def normalize_local_repair_chain_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_local_repair_chain_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_local_repair_chain_review"
    ):
        return dict(body)
    return None


def normalize_optional_path_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return str(Path(value.strip()).expanduser().resolve())


def validate_local_repair_chain_review_for_apply(
    *,
    review_path: Path,
    review: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    plan_hash = plan.get("plan_hash")
    review_plan_hash = review.get("plan_hash")
    blockers = require_list(review.get("blockers"))
    if review.get("ok") is not True:
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact requires an ok "
            "review-local-repair-chain artifact."
        )
    if review.get("review_status") != "ready_for_explicit_apply_approval":
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact is not ready for explicit apply approval."
        )
    if review.get("apply_recommendation") != "ready_for_explicit_apply_approval":
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact does not recommend explicit apply approval."
        )
    if blockers:
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact still has blockers."
        )
    if review.get("training_allowed") is True:
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact unexpectedly allows training."
        )
    if review.get("auto_applied") is True:
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact unexpectedly auto-applied edits."
        )
    if review.get("apply_allowed") is True:
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact must be pre-apply only."
        )
    if not isinstance(plan_hash, str) or len(plan_hash) != 64:
        raise BiberAgentClientError(
            "apply-repair-edits requires a repair edit plan artifact with a valid plan_hash."
        )
    if review_plan_hash != plan_hash:
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact plan_hash does not match the repair plan."
        )

    plan_target_root = normalize_optional_path_text(plan.get("target_root"))
    review_target_root = normalize_optional_path_text(review.get("target_root"))
    if plan_target_root and review_target_root and plan_target_root != review_target_root:
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact target_root does not match the repair plan."
        )
    plan_next_test_id = plan.get("next_test_id")
    review_next_test_id = review.get("next_test_id")
    if (
        isinstance(plan_next_test_id, str)
        and plan_next_test_id
        and isinstance(review_next_test_id, str)
        and review_next_test_id
        and plan_next_test_id != review_next_test_id
    ):
        raise BiberAgentClientError(
            "apply-repair-edits --review-artifact next_test_id does not match the repair plan."
        )

    return {
        "status": "accepted",
        "review_artifact": str(review_path),
        "review_status": review.get("review_status"),
        "apply_recommendation": review.get("apply_recommendation"),
        "plan_hash": plan_hash,
        "target_root": review.get("target_root"),
        "next_test_id": review.get("next_test_id"),
        "blockers": [],
        "warnings": [
            str(item) for item in require_list(review.get("warnings"))
        ],
    }


def normalize_repair_edit_plan_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_edit_plan":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_repair_edit_plan"
    ):
        return dict(body)
    return None


def summarize_repair_edit_plan_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    edit_plan = require_mapping(payload.get("edit_plan"))
    planned = [
        item for item in require_list(edit_plan.get("planned")) if isinstance(item, dict)
    ]
    rejected = [
        item for item in require_list(edit_plan.get("rejected")) if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "plan_status": payload.get("plan_status"),
        "ok": payload.get("ok") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "auto_applied": payload.get("auto_applied") is True,
        "apply_allowed": payload.get("apply_allowed") is True,
        "review_status": payload.get("review_status"),
        "plan_hash": payload.get("plan_hash"),
        "planned": len(planned),
        "rejected": len(rejected),
        "next_test_id": payload.get("next_test_id"),
        "source_artifact": payload.get("source_artifact"),
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_edit_plan_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    planned_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Repair edit plan artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Repair edit plan artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(str(path), label="repair-edit plan artifact")
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_edit_plan_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_repair_edit_plan_artifact(path, normalized)
        if planned_only and summary.get("plan_status") != "planned":
            continue
        artifacts.append(summary)

    artifacts.sort(key=lambda item: float(item.get("modified_epoch") or 0.0), reverse=True)
    planned_count = sum(1 for item in artifacts if item.get("plan_status") == "planned")
    return {
        "source": "biber_mvp_loop_repair_edit_plan_list",
        "directory": str(root),
        "pattern": pattern,
        "planned_only": planned_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "planned": planned_count,
        "training_allowed": False,
        "auto_applied": False,
        "apply_allowed": False,
        "artifacts": artifacts[:limit],
    }


def build_apply_repair_edits_payload(plan: Mapping[str, Any]) -> dict[str, Any]:
    if plan.get("plan_status") != "planned" or plan.get("ok") is not True:
        raise BiberAgentClientError(
            "apply-repair-edits requires a successful repair edit plan artifact."
        )
    plan_hash = plan.get("plan_hash")
    if not isinstance(plan_hash, str) or not plan_hash:
        raise BiberAgentClientError(
            "apply-repair-edits requires a repair edit plan artifact with plan_hash."
        )
    edit_plan_hash = require_mapping(plan.get("edit_plan")).get("plan_hash")
    if isinstance(edit_plan_hash, str) and edit_plan_hash != plan_hash:
        raise BiberAgentClientError(
            "apply-repair-edits requires matching top-level and edit_plan hashes."
        )
    plan_payload = require_mapping(plan.get("plan_edit_payload")).copy()
    edits = require_list(plan_payload.get("edits"))
    if not edits:
        raise BiberAgentClientError(
            "apply-repair-edits requires a repair edit plan artifact with edits."
        )
    plan_payload["plan_hash"] = plan_hash
    return plan_payload


def build_apply_repair_edits_result(
    *,
    plan_path: Path,
    plan: Mapping[str, Any],
    apply_payload: Mapping[str, Any],
    edit_apply: Mapping[str, Any],
    review_gate: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ok = edit_apply.get("ok") is True
    result: dict[str, Any] = {
        "source": "biber_mvp_loop_repair_edit_apply",
        "repair_loop_version": "mvp-v1",
        "source_artifact": str(plan_path),
        "apply_status": "applied" if ok else "failed",
        "ok": ok,
        "training_allowed": False,
        "auto_applied": False,
        "approval_required": True,
        "approval_received": True,
        "apply_allowed": True,
        "review_status": "approved_apply_succeeded" if ok else "approved_apply_failed",
        "plan_hash": plan.get("plan_hash"),
        "next_test_id": plan.get("next_test_id"),
        "apply_payload": dict(apply_payload),
        "edit_apply": dict(edit_apply),
        "next_workflow": [
            "rerun_next_test_id",
            "diagnose_again_if_still_failing",
            "save_successful_fix_as_verified_candidate_if_repeatable",
        ],
    }
    if plan.get("plan_mode"):
        result["plan_mode"] = plan.get("plan_mode")
    if plan.get("target_root"):
        result["target_root"] = plan.get("target_root")
        result["target_root_source"] = plan.get("target_root_source")
    if review_gate is not None:
        result["pre_apply_review_gate"] = dict(review_gate)
        result["pre_apply_review_status"] = review_gate.get("review_status")
        result["pre_apply_review_artifact"] = review_gate.get("review_artifact")
    return result


def normalize_repair_edit_apply_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_edit_apply":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_repair_edit_apply"
    ):
        return dict(body)
    return None


def summarize_repair_edit_apply_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    edit_apply = require_mapping(payload.get("edit_apply"))
    applied = [
        item for item in require_list(edit_apply.get("applied")) if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "apply_status": payload.get("apply_status"),
        "ok": payload.get("ok") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "auto_applied": payload.get("auto_applied") is True,
        "approval_required": payload.get("approval_required") is True,
        "approval_received": payload.get("approval_received") is True,
        "apply_allowed": payload.get("apply_allowed") is True,
        "review_status": payload.get("review_status"),
        "plan_hash": payload.get("plan_hash"),
        "applied": len(applied),
        "next_test_id": payload.get("next_test_id"),
        "source_artifact": payload.get("source_artifact"),
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_edit_apply_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    applied_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Repair edit apply artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Repair edit apply artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(str(path), label="repair-edit apply artifact")
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_edit_apply_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_repair_edit_apply_artifact(path, normalized)
        if applied_only and summary.get("apply_status") != "applied":
            continue
        artifacts.append(summary)

    artifacts.sort(key=lambda item: float(item.get("modified_epoch") or 0.0), reverse=True)
    applied_count = sum(1 for item in artifacts if item.get("apply_status") == "applied")
    return {
        "source": "biber_mvp_loop_repair_edit_apply_list",
        "directory": str(root),
        "pattern": pattern,
        "applied_only": applied_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "applied": applied_count,
        "training_allowed": False,
        "auto_applied": False,
        "artifacts": artifacts[:limit],
    }


def build_verify_repair_edits_payload(
    repair_apply: Mapping[str, Any],
    *,
    test_id: str | None,
    dry_run: bool,
) -> dict[str, Any]:
    if (
        repair_apply.get("apply_status") != "applied"
        or repair_apply.get("ok") is not True
    ):
        raise BiberAgentClientError(
            "verify-repair-edits requires a successful repair edit apply artifact."
        )
    selected_test_id = test_id or repair_apply.get("next_test_id")
    if not isinstance(selected_test_id, str) or not selected_test_id.strip():
        raise BiberAgentClientError(
            "verify-repair-edits requires next_test_id in the apply artifact or --test-id."
        )
    return build_test_run_payload(test_id=selected_test_id.strip(), dry_run=dry_run)


def build_verify_repair_edits_result(
    *,
    apply_path: Path,
    repair_apply: Mapping[str, Any],
    test_payload: Mapping[str, Any],
    test_run: Mapping[str, Any],
    test_mode: str = "api_workspace_root",
    target_root: Path | None = None,
    target_root_source: str | None = None,
) -> dict[str, Any]:
    passed = test_run.get("executed") is True and test_run.get("ok") is True
    if passed:
        verification_status = "passed"
    elif test_run.get("executed") is False:
        verification_status = "not_executed"
    else:
        verification_status = "failed"
    result: dict[str, Any] = {
        "source": "biber_mvp_loop_repair_test_verification",
        "repair_loop_version": "mvp-v1",
        "source_artifact": str(apply_path),
        "verification_status": verification_status,
        "ok": passed,
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "plan_hash": repair_apply.get("plan_hash"),
        "test_id": test_payload.get("test_id"),
        "test_payload": dict(test_payload),
        "test_run": dict(test_run),
        "next_workflow": (
            [
                "review_verified_repair",
                "save_to_github_only_if_requested",
                "record_verified_candidate_only_after_human_review",
            ]
            if passed
            else [
                "diagnose_test_failure",
                "prepare_next_repair_request",
                "do_not_save_or_train_from_unverified_repair",
            ]
        ),
    }
    if test_mode:
        result["test_mode"] = test_mode
    if target_root is not None:
        result["target_root"] = str(target_root)
        result["target_root_source"] = target_root_source or "unknown"
    return result


def build_local_repair_verification_chain_result(
    *,
    apply_path: Path,
    repair_apply: Mapping[str, Any],
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    test_run = require_mapping(verification.get("test_run"))
    diagnosis = require_mapping(test_run.get("diagnosis"))
    if verification.get("ok") is True:
        chain_status = "verified"
    elif verification.get("verification_status") == "not_executed":
        chain_status = "not_executed"
    else:
        chain_status = "still_failing"

    relevant_output = diagnosis.get("relevant_output") or "\n".join(
        item
        for item in [str(test_run.get("stdout") or ""), str(test_run.get("stderr") or "")]
        if item
    )
    result: dict[str, Any] = {
        "source": "biber_local_repair_verification_chain",
        "repair_loop_version": "mvp-v1",
        "source_artifact": str(apply_path),
        "chain_status": chain_status,
        "ok": verification.get("ok") is True,
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "apply_allowed": False,
        "plan_hash": verification.get("plan_hash") or repair_apply.get("plan_hash"),
        "test_id": verification.get("test_id") or test_run.get("test_id"),
        "verification_status": verification.get("verification_status"),
        "test_mode": verification.get("test_mode"),
        "test_executed": test_run.get("executed"),
        "test_ok": test_run.get("ok"),
        "exit_code": test_run.get("exit_code"),
        "timed_out": bool(test_run.get("timed_out")),
        "target_root": verification.get("target_root") or repair_apply.get("target_root"),
        "target_root_source": verification.get("target_root_source")
        or repair_apply.get("target_root_source"),
        "diagnosis_summary": diagnosis.get("summary"),
        "primary_category": diagnosis.get("primary_category"),
        "detected_stack": diagnosis.get("detected_stack"),
        "relevant_output": compact_text(relevant_output, max_chars=1600),
        "verification": dict(verification),
        "next_workflow": (
            [
                "human_review_verified_fix",
                "save_to_github_only_if_requested",
                "record_verified_candidate_only_after_human_review",
            ]
            if verification.get("ok") is True
            else [
                "prepare_repair_from_verification_artifact",
                "run_local_repair_chain_again_with_new_model_response",
                "do_not_save_or_train_from_unverified_repair",
            ]
        ),
    }
    return result


def normalize_local_repair_verification_chain_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_local_repair_verification_chain":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_local_repair_verification_chain"
    ):
        return dict(body)
    return None


def repair_apply_attempted_edits(repair_apply: Mapping[str, Any]) -> list[dict[str, Any]]:
    apply_payload = require_mapping(repair_apply.get("apply_payload"))
    edits = [
        dict(item)
        for item in require_list(apply_payload.get("edits"))
        if isinstance(item, Mapping)
    ]
    if edits:
        return edits
    attempted: list[dict[str, Any]] = []
    edit_apply = require_mapping(repair_apply.get("edit_apply"))
    for item in require_list(edit_apply.get("applied")):
        if not isinstance(item, Mapping):
            continue
        path = item.get("path")
        if isinstance(path, str) and path.strip():
            attempted.append({"path": path.strip()})
    return attempted


def repair_apply_context_paths(repair_apply: Mapping[str, Any]) -> list[str]:
    paths: list[str] = []
    for edit in repair_apply_attempted_edits(repair_apply):
        path = edit.get("path") or edit.get("file")
        if isinstance(path, str) and path.strip():
            paths.append(path.strip())
    edit_apply = require_mapping(repair_apply.get("edit_apply"))
    for item in require_list(edit_apply.get("applied")):
        if not isinstance(item, Mapping):
            continue
        path = item.get("path")
        if isinstance(path, str) and path.strip():
            paths.append(path.strip())
    return dedupe_strings(paths) or []


def build_local_verification_repair_request(
    *,
    path: Path,
    chain: Mapping[str, Any],
    repair_apply: Mapping[str, Any] | None,
    instruction: str | None,
    max_relevant_output_chars: int,
    max_context_paths: int | None,
) -> dict[str, Any]:
    if max_relevant_output_chars < 1:
        raise BiberAgentClientError("--max-relevant-output-chars must be at least 1.")
    if max_context_paths is not None and max_context_paths < 1:
        raise BiberAgentClientError("--max-context-paths must be at least 1.")
    if chain.get("chain_status") == "verified" or chain.get("ok") is True:
        raise BiberAgentClientError(
            "prepare-local-verify-repair requires a failed local verification chain."
        )

    verification = require_mapping(chain.get("verification"))
    test_run = require_mapping(verification.get("test_run"))
    diagnosis = require_mapping(test_run.get("diagnosis"))
    attempted_edits = repair_apply_attempted_edits(repair_apply or {})
    all_context_paths = repair_apply_context_paths(repair_apply or {})
    selected_context_paths = (
        all_context_paths[:max_context_paths]
        if max_context_paths is not None
        else all_context_paths
    )
    relevant_output = (
        chain.get("relevant_output")
        or diagnosis.get("relevant_output")
        or test_run.get("stdout")
        or test_run.get("stderr")
        or ""
    )
    failure = {
        "diagnosis_summary": chain.get("diagnosis_summary")
        or diagnosis.get("summary"),
        "primary_category": chain.get("primary_category")
        or diagnosis.get("primary_category"),
        "detected_stack": chain.get("detected_stack")
        or diagnosis.get("detected_stack"),
        "test_id": chain.get("test_id") or verification.get("test_id"),
        "command": require_list(test_run.get("command")),
        "exit_code": (
            chain.get("exit_code")
            if "exit_code" in chain
            else test_run.get("exit_code")
        ),
        "timed_out": bool(chain.get("timed_out") or test_run.get("timed_out")),
        "relevant_output": compact_text(
            relevant_output,
            max_chars=max_relevant_output_chars,
        ),
    }
    suggested_next_actions = [
        "The previous approved edit did not pass local verification.",
        "Do not repeat the failed exact edit unchanged.",
        "Propose the smallest safe follow-up source edit or return empty edits.",
    ]
    repair_instruction = instruction or (
        "Repair the failed local post-apply verification using the smallest safe "
        "follow-up source edit."
    )
    agent_report = {
        "source": "biber_local_verification_agent_report_v1",
        "status": str(chain.get("chain_status") or "still_failing"),
        "ok": False,
        "repo": {
            "target_root": chain.get("target_root"),
            "branch": None,
            "head": None,
            "dirty": None,
            "status_short": [],
        },
        "edit": {
            "mode": "local_target_root",
            "plan_hash": chain.get("plan_hash"),
            "planned_count": len(attempted_edits),
            "applied_count": len(attempted_edits),
            "changed_count": len(attempted_edits),
            "rejected_count": 0,
            "ok": repair_apply.get("ok") if repair_apply else None,
        },
        "test": {
            "mode": chain.get("test_mode") or verification.get("test_mode"),
            "test_id": failure.get("test_id"),
            "executed": chain.get("test_executed"),
            "ok": chain.get("test_ok"),
            "exit_code": failure.get("exit_code"),
            "timed_out": failure.get("timed_out"),
            "command": " ".join(
                str(part) for part in require_list(test_run.get("command"))
            ),
        },
        "failure": {
            "diagnosis_summary": failure.get("diagnosis_summary"),
            "primary_category": failure.get("primary_category"),
            "detected_stack": failure.get("detected_stack"),
        },
        "next_actions": suggested_next_actions,
    }
    repair_output_contract = build_repair_output_contract()
    repair_prompt = build_repair_prompt(
        instruction=repair_instruction,
        original_instruction=None,
        selected_context_paths=selected_context_paths,
        failure=failure,
        suggested_next_actions=suggested_next_actions,
        agent_report=agent_report,
        output_contract=repair_output_contract,
    )
    if attempted_edits:
        repair_prompt = "\n\n".join(
            [
                repair_prompt.rstrip(),
                "Previous failed exact edits JSON:",
                json.dumps(attempted_edits, indent=2, sort_keys=True),
                "Do not return the same old_text/new_text edit unchanged.",
            ]
        )

    repair: dict[str, Any] = {
        "source": "biber_mvp_loop_repair_request",
        "repair_loop_version": "mvp-v1",
        "repair_status": "ready_for_local_model",
        "training_allowed": False,
        "source_artifact": str(path),
        "ok": False,
        "instruction": repair_instruction,
        "repair_prompt": repair_prompt,
        "repair_output_contract": repair_output_contract,
        "selected_context_paths": selected_context_paths,
        "selected_context_paths_truncated": len(selected_context_paths)
        < len(all_context_paths),
        "agent_report": agent_report,
        "failure": failure,
        "suggested_next_actions": suggested_next_actions,
        "retry_of_failed_verification": True,
        "retry_of_failed_local_verification": True,
        "previous_attempt": {
            "source_artifact": chain.get("source_artifact"),
            "plan_hash": chain.get("plan_hash"),
            "attempted_edits": attempted_edits,
            "verification_status": chain.get("verification_status"),
        },
        "forbidden_edits": attempted_edits,
        "verification_chain": {
            "chain_status": chain.get("chain_status"),
            "source_artifact": chain.get("source_artifact"),
            "target_root": chain.get("target_root"),
            "test_id": chain.get("test_id"),
            "test_ok": chain.get("test_ok"),
        },
        "next_test_id": failure.get("test_id"),
        "next_workflow": [
            "send_repair_prompt_to_local_biber_model",
            "run_local_repair_chain_with_target_root",
            "review_local_repair_chain",
            "apply_only_after_explicit_approval_with_review_artifact",
            "run_local_verify_chain_again",
        ],
    }
    runtime_profile_ids = normalize_runtime_profile_ids(chain.get("runtime_profile_ids"))
    if runtime_profile_ids is not None:
        repair["runtime_profile_ids"] = runtime_profile_ids
    if chain.get("target_root"):
        repair["target_root"] = chain.get("target_root")
    return repair


def local_loop_output_path(directory: Path, filename: str) -> str:
    return str(directory / filename)


def local_repair_loop_artifact_record(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0

    local_verification = normalize_local_repair_verification_chain_artifact(payload)
    if local_verification is not None:
        return {
            "path": str(path),
            "artifact_type": "local_verification_chain",
            "source": local_verification.get("source"),
            "status": local_verification.get("chain_status"),
            "ok": local_verification.get("ok") is True,
            "plan_hash": local_verification.get("plan_hash"),
            "test_id": local_verification.get("test_id"),
            "target_root": local_verification.get("target_root"),
            "modified_epoch": modified_epoch,
        }

    local_review = normalize_local_repair_chain_review_artifact(payload)
    if local_review is not None:
        return {
            "path": str(path),
            "artifact_type": "local_repair_chain_review",
            "source": local_review.get("source"),
            "status": local_review.get("review_status"),
            "ok": local_review.get("ok") is True,
            "plan_hash": local_review.get("plan_hash"),
            "test_id": local_review.get("next_test_id"),
            "target_root": local_review.get("target_root"),
            "modified_epoch": modified_epoch,
        }

    local_chain = normalize_local_repair_chain_artifact(payload)
    if local_chain is not None:
        return {
            "path": str(path),
            "artifact_type": "local_repair_chain",
            "source": local_chain.get("source"),
            "status": local_chain.get("chain_status"),
            "ok": local_chain.get("ok") is True,
            "plan_hash": require_mapping(local_chain.get("repair_edit_plan")).get(
                "plan_hash"
            ),
            "test_id": local_chain.get("next_test_id"),
            "target_root": local_chain.get("target_root"),
            "modified_epoch": modified_epoch,
        }

    repair_apply = normalize_repair_edit_apply_artifact(payload)
    if repair_apply is not None:
        return {
            "path": str(path),
            "artifact_type": "repair_edit_apply",
            "source": repair_apply.get("source"),
            "status": repair_apply.get("apply_status"),
            "ok": repair_apply.get("ok") is True,
            "plan_hash": repair_apply.get("plan_hash"),
            "test_id": repair_apply.get("next_test_id"),
            "target_root": repair_apply.get("target_root"),
            "modified_epoch": modified_epoch,
        }

    repair_plan = normalize_repair_edit_plan_artifact(payload)
    if repair_plan is not None:
        return {
            "path": str(path),
            "artifact_type": "repair_edit_plan",
            "source": repair_plan.get("source"),
            "status": repair_plan.get("plan_status"),
            "ok": repair_plan.get("ok") is True,
            "plan_hash": repair_plan.get("plan_hash"),
            "test_id": repair_plan.get("next_test_id"),
            "target_root": repair_plan.get("target_root"),
            "modified_epoch": modified_epoch,
        }

    repair_request = normalize_mvp_loop_repair_request_artifact(payload)
    if repair_request is not None:
        agent_report = require_mapping(repair_request.get("agent_report"))
        repair_hint = require_mapping(repair_request.get("repair_hint"))
        if not repair_hint:
            repair_hint = require_mapping(agent_report.get("repair_hint"))
        failure = require_mapping(repair_request.get("failure"))
        return {
            "path": str(path),
            "artifact_type": "repair_request",
            "source": repair_request.get("source"),
            "status": repair_request.get("repair_status"),
            "ok": repair_request.get("ok") is True,
            "plan_hash": None,
            "test_id": repair_request.get("next_test_id"),
            "target_root": repair_request.get("target_root"),
            "repair_hint_status": repair_hint.get("status"),
            "primary_category": repair_hint.get("primary_category")
            or failure.get("primary_category"),
            "detected_stack": repair_hint.get("detected_stack")
            or failure.get("detected_stack"),
            "repair_next_workflow": [
                str(item) for item in require_list(repair_hint.get("next_workflow"))
            ],
            "modified_epoch": modified_epoch,
        }

    repair_attempt = normalize_repair_attempt_artifact(payload)
    if repair_attempt is not None:
        return {
            "path": str(path),
            "artifact_type": "repair_attempt",
            "source": repair_attempt.get("source"),
            "status": repair_attempt.get("repair_status"),
            "ok": repair_attempt.get("ok") is True,
            "plan_hash": None,
            "test_id": repair_attempt.get("next_test_id"),
            "target_root": repair_attempt.get("target_root"),
            "modified_epoch": modified_epoch,
        }

    extraction = normalize_repair_edit_extraction_artifact(payload)
    if extraction is not None:
        return {
            "path": str(path),
            "artifact_type": "repair_edit_extraction",
            "source": extraction.get("source"),
            "status": extraction.get("extraction_status"),
            "ok": extraction.get("ok") is True,
            "plan_hash": None,
            "test_id": extraction.get("next_test_id"),
            "target_root": extraction.get("target_root"),
            "modified_epoch": modified_epoch,
        }

    mvp_loop = normalize_mvp_loop_artifact(payload)
    if mvp_loop is not None:
        agent_report = require_mapping(mvp_loop.get("agent_report"))
        if not agent_report:
            agent_report = build_mvp_loop_agent_report(mvp_loop)
        repair_hint = require_mapping(agent_report.get("repair_hint"))
        failure = require_mapping(agent_report.get("failure"))
        return {
            "path": str(path),
            "artifact_type": "mvp_loop",
            "source": "biber_mvp_loop",
            "status": "completed" if mvp_loop.get("ok") is True else "failed",
            "ok": mvp_loop.get("ok") is True,
            "plan_hash": mvp_loop.get("edit_plan_hash"),
            "test_id": require_mapping(
                require_mapping(mvp_loop.get("steps")).get("test_run")
            ).get("test_id"),
            "target_root": mvp_loop.get("target_root"),
            "repair_hint_status": repair_hint.get("status"),
            "primary_category": repair_hint.get("primary_category")
            or failure.get("primary_category"),
            "detected_stack": repair_hint.get("detected_stack")
            or failure.get("detected_stack"),
            "repair_next_workflow": [
                str(item) for item in require_list(repair_hint.get("next_workflow"))
            ],
            "modified_epoch": modified_epoch,
        }

    return None


def find_local_loop_record(
    records: list[Mapping[str, Any]],
    *,
    artifact_type: str,
    plan_hash: object,
) -> Mapping[str, Any] | None:
    if not isinstance(plan_hash, str) or not plan_hash:
        return None
    for record in records:
        if (
            record.get("artifact_type") == artifact_type
            and record.get("plan_hash") == plan_hash
        ):
            return record
    return None


def local_repair_loop_next_step(
    current: Mapping[str, Any],
    *,
    records: list[Mapping[str, Any]],
    directory: Path,
) -> dict[str, Any]:
    artifact_type = current.get("artifact_type")
    path = str(current.get("path") or "")
    target_root = current.get("target_root") or "<TARGET_ROOT>"
    model_response_path = directory / "model-response.json"
    model_command_placeholder = '["python","scripts/biber_local_openai_provider.py"]'

    if artifact_type == "mvp_loop":
        if current.get("ok") is True:
            return {
                "action": "done_or_start_next_task",
                "reason": "latest_mvp_loop_ok",
                "command": None,
            }
        return {
            "action": "prepare_repair",
            "reason": "latest_mvp_loop_failed",
            "command": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "prepare-repair",
                    path,
                    "--output",
                    local_loop_output_path(directory, "prepared-repair.json"),
                ]
            ),
        }

    if artifact_type == "repair_request":
        return {
            "action": "run_local_repair_chain",
            "reason": "prepared_repair_request_ready_for_local_model_response",
            "command": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "local-repair-chain",
                    path,
                    "--model-response-file",
                    model_response_path,
                    "--target-root",
                    target_root,
                    "--output",
                    local_loop_output_path(directory, "local-repair-chain.json"),
                ]
            ),
            "model_command_alternative": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "local-repair-chain",
                    path,
                    "--model-command",
                    model_command_placeholder,
                    "--model-command-timeout-seconds",
                    120,
                    "--target-root",
                    target_root,
                    "--output",
                    local_loop_output_path(directory, "local-repair-chain.json"),
                ]
            ),
        }

    if artifact_type == "repair_attempt":
        return {
            "action": "extract_repair_edits",
            "reason": "repair_attempt_needs_edit_extraction",
            "command": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "extract-repair-edits",
                    path,
                    "--output",
                    local_loop_output_path(directory, "repair-edit-extraction.json"),
                ]
            ),
        }

    if artifact_type == "repair_edit_extraction":
        return {
            "action": "plan_repair_edits",
            "reason": "extracted_edits_need_local_plan",
            "command": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "plan-repair-edits",
                    path,
                    "--target-root",
                    target_root,
                    "--output",
                    local_loop_output_path(directory, "repair-edit-plan.json"),
                ]
            ),
        }

    if artifact_type == "local_repair_chain":
        if current.get("status") == "planned":
            return {
                "action": "review_local_repair_chain",
                "reason": "local_chain_has_plan",
                "command": format_cli_command(
                    [
                        "python",
                        "scripts/biber_agent_client.py",
                        "--json",
                        "review-local-repair-chain",
                        path,
                        "--output",
                        local_loop_output_path(
                            directory,
                            "local-repair-chain-review.json",
                        ),
                    ]
                ),
            }
        return {
            "action": "rerun_local_repair_chain_with_target_root",
            "reason": "local_chain_not_planned",
            "command": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "local-repair-chain",
                    "<REPAIR_REQUEST_ARTIFACT>",
                    "--model-response-file",
                    model_response_path,
                    "--target-root",
                    target_root,
                    "--output",
                    local_loop_output_path(directory, "local-repair-chain.json"),
                ]
            ),
            "model_command_alternative": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "local-repair-chain",
                    "<REPAIR_REQUEST_ARTIFACT>",
                    "--model-command",
                    model_command_placeholder,
                    "--model-command-timeout-seconds",
                    120,
                    "--target-root",
                    target_root,
                    "--output",
                    local_loop_output_path(directory, "local-repair-chain.json"),
                ]
            ),
        }

    if artifact_type == "local_repair_chain_review":
        matching_plan = find_local_loop_record(
            records,
            artifact_type="repair_edit_plan",
            plan_hash=current.get("plan_hash"),
        )
        if current.get("ok") is True and matching_plan is not None:
            return {
                "action": "apply_reviewed_repair",
                "reason": "review_ready_and_matching_plan_found",
                "command": format_cli_command(
                    [
                        "python",
                        "scripts/biber_agent_client.py",
                        "--json",
                        "apply-repair-edits",
                        str(matching_plan.get("path")),
                        "--approve",
                        "--review-artifact",
                        path,
                        "--output",
                        local_loop_output_path(directory, "repair-edit-apply.json"),
                    ]
                ),
            }
        if current.get("ok") is True:
            return {
                "action": "save_matching_repair_plan_then_apply",
                "reason": "review_ready_but_matching_plan_artifact_not_found",
                "command": None,
            }
        return {
            "action": "fix_blocked_review_before_apply",
            "reason": "review_not_ready_for_apply",
            "command": None,
        }

    if artifact_type == "repair_edit_plan":
        matching_review = find_local_loop_record(
            records,
            artifact_type="local_repair_chain_review",
            plan_hash=current.get("plan_hash"),
        )
        if matching_review is not None and matching_review.get("ok") is True:
            return {
                "action": "apply_reviewed_repair",
                "reason": "matching_ready_review_found",
                "command": format_cli_command(
                    [
                        "python",
                        "scripts/biber_agent_client.py",
                        "--json",
                        "apply-repair-edits",
                        path,
                        "--approve",
                        "--review-artifact",
                        str(matching_review.get("path")),
                        "--output",
                        local_loop_output_path(directory, "repair-edit-apply.json"),
                    ]
                ),
            }
        return {
            "action": "review_or_create_local_chain_review",
            "reason": "plan_exists_without_matching_ready_review",
            "command": None,
        }

    if artifact_type == "repair_edit_apply":
        return {
            "action": "run_local_verify_chain",
            "reason": "repair_applied_needs_local_verification",
            "command": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "local-verify-chain",
                    path,
                    "--diagnose-on-failure",
                    "--output",
                    local_loop_output_path(directory, "local-verify-chain.json"),
                ]
            ),
        }

    if artifact_type == "local_verification_chain":
        if current.get("status") == "verified":
            return {
                "action": "human_review_verified_fix",
                "reason": "local_verification_passed",
                "command": None,
            }
        return {
            "action": "prepare_local_verify_repair",
            "reason": "local_verification_failed_or_not_executed",
            "command": format_cli_command(
                [
                    "python",
                    "scripts/biber_agent_client.py",
                    "--json",
                    "prepare-local-verify-repair",
                    path,
                    "--output",
                    local_loop_output_path(
                        directory,
                        "prepared-local-verify-repair.json",
                    ),
                ]
            ),
        }

    return {
        "action": "inspect_artifacts",
        "reason": "no_known_next_step_for_latest_artifact",
        "command": None,
    }


def build_local_repair_loop_status(
    *,
    directory: str,
    pattern: str,
    limit: int,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(f"Artifact directory does not exist: {root}")
    if not root.is_dir():
        raise BiberAgentClientError(f"Artifact path is not a directory: {root}")

    records: list[dict[str, Any]] = []
    scanned = 0
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            payload = load_json_artifact(str(path), label="local repair loop artifact")
        except BiberAgentClientError:
            continue
        record = local_repair_loop_artifact_record(path, payload)
        if record is not None:
            records.append(record)

    records.sort(
        key=lambda item: (
            float(item.get("modified_epoch") or 0.0),
            str(item.get("path") or ""),
        ),
        reverse=True,
    )
    current = records[0] if records else None
    next_step = (
        local_repair_loop_next_step(current, records=records, directory=root)
        if current is not None
        else {
            "action": "create_or_point_to_artifacts",
            "reason": "no_known_biber_repair_loop_artifacts_found",
            "command": None,
        }
    )
    return {
        "source": "biber_local_repair_loop_status",
        "directory": str(root),
        "pattern": pattern,
        "scanned": scanned,
        "matched": len(records),
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "apply_allowed": False,
        "current": current,
        "next_step": next_step,
        "artifacts": records[:limit],
    }


def normalize_repair_test_verification_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_test_verification":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_repair_test_verification"
    ):
        return dict(body)
    return None


def summarize_repair_test_verification_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    test_run = require_mapping(payload.get("test_run"))
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "verification_status": payload.get("verification_status"),
        "ok": payload.get("ok") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "auto_applied": payload.get("auto_applied") is True,
        "auto_saved": payload.get("auto_saved") is True,
        "plan_hash": payload.get("plan_hash"),
        "test_id": payload.get("test_id"),
        "test_executed": test_run.get("executed"),
        "test_ok": test_run.get("ok"),
        "source_artifact": payload.get("source_artifact"),
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_test_verification_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    passed_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Repair test verification artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Repair test verification artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair test verification artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_test_verification_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_repair_test_verification_artifact(path, normalized)
        if passed_only and summary.get("verification_status") != "passed":
            continue
        artifacts.append(summary)

    artifacts.sort(key=lambda item: float(item.get("modified_epoch") or 0.0), reverse=True)
    passed_count = sum(
        1 for item in artifacts if item.get("verification_status") == "passed"
    )
    return {
        "source": "biber_mvp_loop_repair_test_verification_list",
        "directory": str(root),
        "pattern": pattern,
        "passed_only": passed_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "passed": passed_count,
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "artifacts": artifacts[:limit],
    }


def resolve_linked_artifact_path(
    reference: object,
    *,
    base_path: Path,
) -> Path | None:
    if not isinstance(reference, str) or not reference.strip():
        return None
    linked = Path(reference.strip())
    if linked.exists() or linked.is_absolute():
        return linked
    local_linked = base_path.parent / linked
    if local_linked.exists():
        return local_linked
    return linked


def load_linked_artifact(
    reference: object,
    *,
    base_path: Path,
    label: str,
    normalizer: object,
) -> tuple[Path | None, dict[str, Any] | None, str | None]:
    linked_path = resolve_linked_artifact_path(reference, base_path=base_path)
    if linked_path is None:
        return None, None, f"{label} reference is missing."
    try:
        raw_payload = load_json_artifact(str(linked_path), label=label)
    except BiberAgentClientError as exc:
        return linked_path, None, str(exc)
    normalized = normalizer(raw_payload)  # type: ignore[operator]
    if normalized is None:
        return linked_path, None, f"{label} has an unexpected artifact source."
    return linked_path, normalized, None


def repair_edit_candidates_from_payload(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    for item in require_list(payload.get("edits")):
        if not isinstance(item, Mapping):
            continue
        edit: dict[str, Any] = {}
        for key in ("path", "old_text", "new_text", "expected_replacements"):
            if key in item:
                edit[key] = item.get(key)
        if edit:
            edits.append(edit)
    return edits


def retry_context_terms(
    *,
    attempted_edits: list[Mapping[str, Any]],
    original_failure: Mapping[str, Any],
    verification_failure: Mapping[str, Any],
) -> list[str]:
    values: list[object] = [
        original_failure.get("diagnosis_summary"),
        original_failure.get("primary_category"),
        original_failure.get("detected_stack"),
        original_failure.get("relevant_output"),
        verification_failure.get("diagnosis_summary"),
        verification_failure.get("primary_category"),
        verification_failure.get("detected_stack"),
        verification_failure.get("relevant_output"),
    ]
    for edit in attempted_edits:
        values.extend([edit.get("old_text"), edit.get("new_text")])

    terms: list[str] = []
    seen: set[str] = set()

    def add(term: object) -> None:
        text = str(term or "").strip()
        if len(text) < 3 or len(text) > 200:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        terms.append(text)

    for value in values:
        text = str(value or "")
        add(text)
        for match in re.finditer(r"['\"]([^'\"]{3,80})['\"]", text):
            add(match.group(1))
        for token in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{4,}\b", text):
            if token.lower() in {"assert", "expected", "actual", "failure"}:
                continue
            add(token)
    return terms[:24]


def retry_failure_line_references(
    *,
    selected_context_paths: list[str],
    original_failure: Mapping[str, Any],
    verification_failure: Mapping[str, Any],
) -> dict[str, set[int]]:
    selected_paths = {
        clean_path
        for path in selected_context_paths
        if (clean_path := safe_repo_relative_path(path)) is not None
    }
    references: dict[str, set[int]] = {}
    texts = [
        original_failure.get("relevant_output"),
        verification_failure.get("relevant_output"),
    ]
    for text_value in texts:
        text = str(text_value or "")
        for match in re.finditer(r"([A-Za-z0-9_.\-/]+):(\d+)", text):
            clean_path = safe_repo_relative_path(match.group(1))
            if clean_path is None or clean_path not in selected_paths:
                continue
            line_number = int(match.group(2))
            references.setdefault(clean_path, set()).add(line_number)
    return references


def retry_failure_line_context_terms(
    *,
    source_root: Path,
    failure_line_refs_by_path: Mapping[str, set[int]],
    context_lines: int,
) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: object) -> None:
        text = str(term or "").strip()
        if len(text) < 3 or len(text) > 120:
            return
        key = text.lower()
        if key in seen:
            return
        seen.add(key)
        terms.append(text)

    try:
        root = source_root.resolve()
    except OSError:
        root = source_root

    for clean_path, line_numbers in failure_line_refs_by_path.items():
        file_path = (root / clean_path).resolve()
        if file_path != root and root not in file_path.parents:
            continue
        if not file_path.is_file():
            continue
        try:
            lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line_number in sorted(line_numbers):
            line_index = max(0, line_number - 1)
            window_start = max(0, line_index - context_lines)
            window_end = min(len(lines), line_index + context_lines + 1)
            window_text = "\n".join(lines[window_start:window_end])
            for match in re.finditer(r"['\"]([^'\"]{3,80})['\"]", window_text):
                add(match.group(1))
            for token in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]{3,}\b", window_text):
                if token.lower() in {"assert", "diagnosis", "relevant_output"}:
                    continue
                add(token)
    return terms[:24]


def safe_repo_relative_path(path: object) -> str | None:
    if not isinstance(path, str) or not path.strip():
        return None
    clean_path = path.strip().replace("\\", "/")
    path_parts = [part for part in clean_path.split("/") if part]
    if (
        clean_path.startswith("/")
        or clean_path.startswith("~")
        or ":" in clean_path
        or ".." in path_parts
    ):
        return None
    return clean_path


def line_numbered_snippet(
    lines: list[str],
    *,
    start_index: int,
    end_index: int,
) -> str:
    return "\n".join(
        f"{line_number}: {lines[line_number - 1]}"
        for line_number in range(start_index + 1, end_index + 1)
    )


def build_retry_source_context_snippets(
    *,
    source_root: Path,
    selected_context_paths: list[str],
    attempted_edits: list[Mapping[str, Any]],
    original_failure: Mapping[str, Any],
    verification_failure: Mapping[str, Any],
    max_snippets: int,
    context_lines: int,
) -> list[dict[str, Any]]:
    if max_snippets < 1 or context_lines < 0:
        return []
    terms = retry_context_terms(
        attempted_edits=attempted_edits,
        original_failure=original_failure,
        verification_failure=verification_failure,
    )
    failure_line_refs_by_path = retry_failure_line_references(
        selected_context_paths=selected_context_paths,
        original_failure=original_failure,
        verification_failure=verification_failure,
    )
    old_text_by_path: dict[str, list[str]] = {}
    for edit in attempted_edits:
        clean_path = safe_repo_relative_path(edit.get("path"))
        old_text = edit.get("old_text")
        if clean_path and isinstance(old_text, str) and old_text.strip():
            old_text_by_path.setdefault(clean_path, []).append(old_text.strip())

    try:
        root = source_root.resolve()
    except OSError:
        root = source_root
    terms = dedupe_strings(
        [
            *terms,
            *retry_failure_line_context_terms(
                source_root=root,
                failure_line_refs_by_path=failure_line_refs_by_path,
                context_lines=context_lines,
            ),
        ]
    ) or []

    candidates: list[dict[str, Any]] = []
    for raw_path in selected_context_paths:
        clean_path = safe_repo_relative_path(raw_path)
        if clean_path is None:
            continue
        file_path = (root / clean_path).resolve()
        if file_path != root and root not in file_path.parents:
            continue
        if not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        lowered_lines = [line.lower() for line in lines]
        for line_index, line in enumerate(lowered_lines):
            window_start = max(0, line_index - context_lines)
            window_end = min(len(lines), line_index + context_lines + 1)
            window_text = "\n".join(lowered_lines[window_start:window_end])
            matched_terms = [
                term
                for term in terms
                if term.lower() in window_text and len(term) <= 120
            ][:8]
            if not matched_terms:
                continue
            is_rule_snippet = "_rule(" in window_text
            contains_previous_failed_edit = any(
                old_text.lower() in window_text
                for old_text in old_text_by_path.get(clean_path, [])
            )
            is_test_expectation_snippet = (
                is_test_edit_path(clean_path)
                and any(marker in window_text for marker in ("assert", "expect("))
            )
            failure_line_refs = [
                line_number
                for line_number in sorted(failure_line_refs_by_path.get(clean_path, set()))
                if window_start < line_number <= window_end
            ]
            if is_test_expectation_snippet and failure_line_refs:
                priority_group = 0
                snippet_kind = "test_expectation"
            elif is_rule_snippet:
                priority_group = 1
                snippet_kind = "rule"
            elif is_test_expectation_snippet:
                priority_group = 2
                snippet_kind = "test_expectation"
            elif contains_previous_failed_edit:
                priority_group = 4
                snippet_kind = "previous_failed_edit_target"
            else:
                priority_group = 3
                snippet_kind = "context"
            score = len(matched_terms)
            if is_test_expectation_snippet:
                score += 7
                if "primary_category" in window_text:
                    score += 2
                if failure_line_refs:
                    score += 10
            if is_rule_snippet:
                score += 4
            if len(set(term.lower() for term in matched_terms)) >= 2:
                score += 2
            if contains_previous_failed_edit:
                score += 3
            candidates.append(
                {
                    "path": clean_path,
                    "start_line": window_start + 1,
                    "end_line": window_end,
                    "matched_terms": matched_terms,
                    "snippet_kind": snippet_kind,
                    "failure_line_refs": failure_line_refs,
                    "priority_group": priority_group,
                    "score": score,
                    "snippet": line_numbered_snippet(
                        lines,
                        start_index=window_start,
                        end_index=window_end,
                    ),
                }
            )

    candidates.sort(
        key=lambda item: (
            int(item.get("priority_group") or 0),
            -int(item.get("score") or 0),
            str(item.get("path") or ""),
            int(item.get("start_line") or 0),
        )
    )
    snippets: list[dict[str, Any]] = []
    seen_ranges: set[tuple[str, int, int]] = set()
    for candidate in candidates:
        path = str(candidate.get("path") or "")
        start_line = int(candidate.get("start_line") or 0)
        end_line = int(candidate.get("end_line") or 0)
        overlaps = any(
            path == seen_path and start_line <= seen_end and end_line >= seen_start
            for seen_path, seen_start, seen_end in seen_ranges
        )
        if overlaps:
            continue
        seen_ranges.add((path, start_line, end_line))
        candidate.pop("priority_group", None)
        candidate.pop("score", None)
        snippets.append(candidate)
        if len(snippets) >= max_snippets:
            break
    return snippets


def compact_repair_test_failure(
    test_run: Mapping[str, Any],
    *,
    max_relevant_output_chars: int,
) -> dict[str, Any]:
    diagnosis = test_run.get("diagnosis")
    diagnosis_payload = diagnosis if isinstance(diagnosis, Mapping) else {}
    relevant_output = (
        diagnosis_payload.get("relevant_output")
        or test_run.get("stdout")
        or test_run.get("stderr")
        or ""
    )
    return {
        "diagnosis_summary": diagnosis_payload.get("summary"),
        "primary_category": diagnosis_payload.get("primary_category"),
        "detected_stack": diagnosis_payload.get("detected_stack"),
        "test_id": test_run.get("test_id"),
        "command": require_list(test_run.get("command")),
        "exit_code": test_run.get("exit_code"),
        "timed_out": bool(test_run.get("timed_out")),
        "relevant_output": compact_text(
            relevant_output,
            max_chars=max_relevant_output_chars,
        ),
    }


def failed_repair_retry_source_context(
    *,
    requested_source_root: Path,
    test_run: Mapping[str, Any],
) -> tuple[Path, dict[str, Any]]:
    try:
        requested_root = requested_source_root.resolve()
    except OSError:
        requested_root = requested_source_root

    context: dict[str, Any] = {
        "source_root": str(requested_root),
        "requested_source_root": str(requested_root),
        "source_root_origin": "requested_source_root",
    }
    raw_cwd = test_run.get("cwd")
    if not isinstance(raw_cwd, str) or not raw_cwd.strip():
        return requested_root, context

    context["verification_test_cwd"] = raw_cwd.strip()
    verification_cwd = Path(raw_cwd.strip())
    try:
        verification_root = verification_cwd.resolve()
    except OSError:
        verification_root = verification_cwd

    if verification_root.is_dir():
        context.update(
            {
                "source_root": str(verification_root),
                "source_root_origin": "verification_test_cwd",
            }
        )
        if str(verification_root) != str(requested_root):
            context["source_root_note"] = (
                "using_failed_verification_workspace_for_retry_context"
            )
        return verification_root, context

    context["source_root_warning"] = (
        "verification_test_cwd_unavailable_falling_back_to_requested_source_root"
    )
    return requested_root, context


def build_failed_repair_retry_prompt(
    *,
    instruction: str,
    original_instruction: object,
    selected_context_paths: list[str],
    original_failure: Mapping[str, Any],
    attempted_edits: list[Mapping[str, Any]],
    forbidden_edits: list[Mapping[str, Any]],
    source_context_snippets: list[Mapping[str, Any]],
    verification_failure: Mapping[str, Any],
    suggested_next_actions: list[str],
    suggested_rule_category_edits: list[Mapping[str, Any]] | None = None,
) -> str:
    context_lines = "\n".join(f"- {path}" for path in selected_context_paths) or "- none"
    action_lines = "\n".join(f"- {action}" for action in suggested_next_actions) or "- none"
    attempted_lines = []
    for edit in attempted_edits[:8]:
        attempted_lines.append(
            "\n".join(
                [
                    f"- path: {edit.get('path') or '-'}",
                    f"  old_text: {compact_text(edit.get('old_text'), max_chars=500)}",
                    f"  new_text: {compact_text(edit.get('new_text'), max_chars=500)}",
                    (
                        "  expected_replacements: "
                        f"{edit.get('expected_replacements', '-')}"
                    ),
                ]
            )
        )
    attempted_text = "\n".join(attempted_lines) or "- none"
    forbidden_text = (
        json.dumps(forbidden_edits[:8], indent=2, sort_keys=True)
        if forbidden_edits
        else "[]"
    )
    assertion_diffs = failure_assertion_diffs(original_failure, verification_failure)
    has_rule_snippet = any(
        snippet.get("snippet_kind") == "rule" for snippet in source_context_snippets
    )
    retry_hint_lines: list[str] = []
    if has_rule_snippet:
        for diff in assertion_diffs[:4]:
            actual = diff.get("actual")
            expected = diff.get("expected")
            if actual and expected and actual != expected:
                retry_hint_lines.append(
                    "- Assertion diff shows actual "
                    f"{actual!r} but expected {expected!r}. If a rule snippet maps "
                    f"the failing evidence to {actual!r}, prefer changing that rule "
                    f"category to {expected!r}; do not patch fallback logic."
                )
    retry_hint_text = "\n".join(retry_hint_lines) or "- none"
    if suggested_rule_category_edits is None:
        suggested_rule_category_edits = retry_rule_category_edit_suggestions(
            source_context_snippets=source_context_snippets,
            original_failure=original_failure,
            verification_failure=verification_failure,
        )
    prompt_suggested_rule_category_edits = plan_safe_repair_edits_from_candidates(
        [dict(item) for item in suggested_rule_category_edits]
    )
    suggested_rule_category_text = (
        json.dumps(
            prompt_suggested_rule_category_edits,
            indent=2,
            sort_keys=True,
        )
        if prompt_suggested_rule_category_edits
        else "[]"
    )
    snippet_lines: list[str] = []
    for snippet in source_context_snippets[:6]:
        snippet_lines.extend(
            [
                (
                    f"- {snippet.get('path', '-')}:{snippet.get('start_line', '-')}"
                    f"-{snippet.get('end_line', '-')}"
                    f" kind={snippet.get('snippet_kind', 'context')}"
                ),
                str(snippet.get("snippet") or ""),
            ]
        )
    source_snippet_text = "\n".join(snippet_lines) or "- none"
    original_command = (
        " ".join(str(part) for part in require_list(original_failure.get("command")))
        or "-"
    )
    verification_command = (
        " ".join(str(part) for part in require_list(verification_failure.get("command")))
        or "-"
    )
    return "\n".join(
        [
            "BIBER deterministic repair retry request.",
            "",
            "Goal:",
            instruction,
            "",
            "Rules:",
            "- The previous approved source edit did not pass verification.",
            "- Do not repeat the failed edit unchanged.",
            "- Do not output any edit identical to a forbidden edit listed below.",
            '- If every candidate equals a forbidden edit, return {"edits":[]} as the first JSON object.',
            "- Review `rule` snippets before changing the previous failed target line.",
            "- If a referenced `test_expectation` and related `rule` snippet are present, treat the rule snippet as the primary repair target.",
            "- If suggested rule-category edits are listed and match the failure, copy the exact bounded edit into your first JSON object.",
            "- Do not add an `if ... else '<expected>'` fallback on the previous failed target line when that old_text is not shown inside a `rule` snippet.",
            "- The first JSON object is authoritative; do not put a different fix only in prose.",
            "- If your explanation identifies a better fix, the JSON edit must contain that better fix.",
            "- Before finalizing JSON, compare each edit to the forbidden exact edits and remove exact matches.",
            "- If no non-forbidden bounded source edit is available, return exactly {\"edits\":[]}.",
            "- Prefer the smallest safe source edit that fixes the failing test.",
            "- Do not change credentials, generated secrets, dependency folders, or unrelated files.",
            "- If the goal says not to change tests, propose only source/implementation edits.",
            (
                '- Return a strict JSON object first: {"edits":[{"path":"...",'
                '"old_text":"...","new_text":"...","expected_replacements":1}]}'
                "."
            ),
            "- Explanations after the JSON edit object are optional.",
            "",
            f"Original MVP instruction: {original_instruction or '-'}",
            "",
            "Selected repository context paths:",
            context_lines,
            "",
            "Original failing test:",
            f"- test_id: {original_failure.get('test_id') or '-'}",
            f"- command: {original_command}",
            f"- exit_code: {original_failure.get('exit_code')}",
            f"- timed_out: {bool(original_failure.get('timed_out'))}",
            f"- diagnosis: {original_failure.get('diagnosis_summary') or '-'}",
            f"- detected_stack: {original_failure.get('detected_stack') or '-'}",
            f"- primary_category: {original_failure.get('primary_category') or '-'}",
            "",
            "Previous attempted edit that failed verification:",
            attempted_text,
            "",
            "Forbidden exact edits JSON:",
            forbidden_text,
            "",
            "Retry diagnosis hints:",
            retry_hint_text,
            "",
            "Suggested rule-category edits JSON:",
            suggested_rule_category_text,
            "",
            "Compact source snippets for retry:",
            source_snippet_text,
            "",
            "Verification failure after the attempted edit:",
            f"- test_id: {verification_failure.get('test_id') or '-'}",
            f"- command: {verification_command}",
            f"- exit_code: {verification_failure.get('exit_code')}",
            f"- timed_out: {bool(verification_failure.get('timed_out'))}",
            f"- diagnosis: {verification_failure.get('diagnosis_summary') or '-'}",
            f"- detected_stack: {verification_failure.get('detected_stack') or '-'}",
            f"- primary_category: {verification_failure.get('primary_category') or '-'}",
            "",
            "Suggested next actions:",
            action_lines,
            "",
            "Original relevant output:",
            str(original_failure.get("relevant_output") or ""),
            "",
            "Verification relevant output:",
            str(verification_failure.get("relevant_output") or ""),
        ]
    )


def build_failed_repair_verification_review(
    *,
    path: Path,
    verification: Mapping[str, Any],
    max_relevant_output_chars: int,
    max_context_paths: int | None,
    source_root: Path,
    max_source_snippets: int,
    source_snippet_context_lines: int,
) -> dict[str, Any]:
    if max_relevant_output_chars < 1:
        raise BiberAgentClientError("--max-relevant-output-chars must be at least 1.")
    if max_context_paths is not None and max_context_paths < 1:
        raise BiberAgentClientError("--max-context-paths must be at least 1.")
    if max_source_snippets < 0:
        raise BiberAgentClientError("--max-source-snippets must be at least 0.")
    if source_snippet_context_lines < 0:
        raise BiberAgentClientError(
            "--source-snippet-context-lines must be at least 0."
        )
    if (
        verification.get("verification_status") == "passed"
        or verification.get("ok") is True
    ):
        raise BiberAgentClientError(
            "prepare-failed-repair-retry requires a failed repair verification artifact."
        )

    apply_path, repair_apply, apply_error = load_linked_artifact(
        verification.get("source_artifact"),
        base_path=path,
        label="repair-edit apply artifact",
        normalizer=normalize_repair_edit_apply_artifact,
    )
    plan_path = None
    repair_plan = None
    plan_error = None
    extraction_path = None
    repair_extraction = None
    extraction_error = None
    attempt_path = None
    repair_attempt = None
    attempt_error = None
    mvp_path = None
    mvp_loop = None
    mvp_error = None

    if repair_apply is not None:
        plan_path, repair_plan, plan_error = load_linked_artifact(
            repair_apply.get("source_artifact"),
            base_path=apply_path or path,
            label="repair-edit plan artifact",
            normalizer=normalize_repair_edit_plan_artifact,
        )
    if repair_plan is not None:
        extraction_path, repair_extraction, extraction_error = load_linked_artifact(
            repair_plan.get("source_artifact"),
            base_path=plan_path or path,
            label="repair-edit extraction artifact",
            normalizer=normalize_repair_edit_extraction_artifact,
        )
    if repair_extraction is not None:
        attempt_path, repair_attempt, attempt_error = load_linked_artifact(
            repair_extraction.get("source_artifact"),
            base_path=extraction_path or path,
            label="repair-attempt artifact",
            normalizer=normalize_repair_attempt_artifact,
        )
    if repair_attempt is not None:
        mvp_path, mvp_loop, mvp_error = load_linked_artifact(
            repair_attempt.get("source_artifact"),
            base_path=attempt_path or path,
            label="mvp-loop artifact",
            normalizer=normalize_mvp_loop_artifact,
        )

    repair_request = (
        require_mapping(repair_attempt.get("repair_request"))
        if repair_attempt is not None
        else {}
    )
    all_context_paths = [
        str(item) for item in require_list(repair_request.get("selected_context_paths"))
    ]
    if not all_context_paths and mvp_loop is not None:
        all_context_paths = [
            str(item) for item in require_list(mvp_loop.get("selected_context_paths"))
        ]
    selected_context_paths = (
        all_context_paths[:max_context_paths]
        if max_context_paths is not None
        else all_context_paths
    )

    original_failure = require_mapping(repair_request.get("failure"))
    if not original_failure and mvp_loop is not None:
        steps = require_mapping(mvp_loop.get("steps"))
        original_test_run = require_mapping(steps.get("test_run"))
        original_diagnosis = require_mapping(steps.get("test_diagnosis"))
        original_failure = {
            "diagnosis_summary": mvp_loop.get("diagnosis_summary")
            or original_diagnosis.get("summary"),
            "primary_category": original_diagnosis.get("primary_category"),
            "detected_stack": original_diagnosis.get("detected_stack"),
            "test_id": original_test_run.get("test_id"),
            "command": require_list(original_test_run.get("command")),
            "exit_code": original_test_run.get("exit_code"),
            "timed_out": bool(original_test_run.get("timed_out")),
            "relevant_output": compact_text(
                original_diagnosis.get("relevant_output")
                or original_test_run.get("stdout")
                or original_test_run.get("stderr")
                or "",
                max_chars=max_relevant_output_chars,
            ),
        }

    apply_payload = (
        require_mapping(repair_apply.get("apply_payload"))
        if repair_apply is not None
        else {}
    )
    attempted_edits = repair_edit_candidates_from_payload(apply_payload)
    if not attempted_edits and repair_plan is not None:
        attempted_edits = repair_edit_candidates_from_payload(
            require_mapping(repair_plan.get("plan_edit_payload"))
        )

    test_run = require_mapping(verification.get("test_run"))
    verification_failure = compact_repair_test_failure(
        test_run,
        max_relevant_output_chars=max_relevant_output_chars,
    )
    if not verification_failure.get("test_id"):
        verification_failure["test_id"] = verification.get("test_id")

    diagnosis = test_run.get("diagnosis")
    suggested_next_actions = (
        [str(item) for item in require_list(diagnosis.get("suggested_next_actions"))]
        if isinstance(diagnosis, Mapping)
        else []
    )
    if not suggested_next_actions:
        suggested_next_actions = [
            str(item) for item in require_list(repair_request.get("suggested_next_actions"))
        ]

    effective_source_root, source_context = failed_repair_retry_source_context(
        requested_source_root=source_root,
        test_run=test_run,
    )
    source_context["max_source_snippets"] = max_source_snippets
    source_context["source_snippet_context_lines"] = source_snippet_context_lines
    failure_line_refs_by_path = retry_failure_line_references(
        selected_context_paths=selected_context_paths,
        original_failure=original_failure,
        verification_failure=verification_failure,
    )

    forbidden_edits = [dict(edit) for edit in attempted_edits]
    source_context_snippets = build_retry_source_context_snippets(
        source_root=effective_source_root,
        selected_context_paths=selected_context_paths,
        attempted_edits=attempted_edits,
        original_failure=original_failure,
        verification_failure=verification_failure,
        max_snippets=max_source_snippets,
        context_lines=source_snippet_context_lines,
    )
    suggested_rule_category_edits = dedupe_rule_category_edit_suggestions(
        [
            *retry_rule_category_edit_suggestions(
                source_context_snippets=source_context_snippets,
                original_failure=original_failure,
                verification_failure=verification_failure,
            ),
            *retry_rule_category_edit_suggestions_from_sources(
                source_root=effective_source_root,
                selected_context_paths=selected_context_paths,
                original_failure=original_failure,
                verification_failure=verification_failure,
                failure_line_refs_by_path=failure_line_refs_by_path,
                context_lines=source_snippet_context_lines,
            ),
        ]
    )
    suggested_rule_category_plan_edit_payload = {
        "edits": plan_safe_repair_edits_from_candidates(
            suggested_rule_category_edits
        )
    }
    instruction = (
        "Retry the failed BIBER MVP repair using the smallest safe source edit. "
        "The previous approved edit failed verification; use the original "
        "failure, attempted edit, and verification failure to propose a better "
        "bounded edit."
    )
    original_instruction = (
        repair_request.get("original_instruction")
        or repair_request.get("instruction")
        or (mvp_loop.get("instruction") if mvp_loop is not None else None)
    )
    retry_prompt = build_failed_repair_retry_prompt(
        instruction=instruction,
        original_instruction=original_instruction,
        selected_context_paths=selected_context_paths,
        original_failure=original_failure,
        attempted_edits=attempted_edits,
        forbidden_edits=forbidden_edits,
        source_context_snippets=source_context_snippets,
        verification_failure=verification_failure,
        suggested_next_actions=suggested_next_actions,
        suggested_rule_category_edits=suggested_rule_category_edits,
    )
    runtime_profile_ids = normalize_runtime_profile_ids(
        repair_request.get("runtime_profile_ids")
    )
    retry_request: dict[str, Any] = {
        "source": "biber_mvp_loop_repair_request",
        "repair_loop_version": "mvp-v1",
        "repair_status": "ready_for_local_model",
        "retry_of_failed_verification": True,
        "training_allowed": False,
        "source_artifact": str(path),
        "ok": False,
        "instruction": instruction,
        "repair_prompt": retry_prompt,
        "selected_context_paths": selected_context_paths,
        "selected_context_paths_truncated": len(selected_context_paths)
        < len(all_context_paths),
        "failure": verification_failure,
        "original_failure": original_failure,
        "previous_attempt": {
            "repair_apply_artifact": str(apply_path) if apply_path else None,
            "repair_plan_artifact": str(plan_path) if plan_path else None,
            "repair_extraction_artifact": str(extraction_path)
            if extraction_path
            else None,
            "repair_attempt_artifact": str(attempt_path) if attempt_path else None,
            "attempted_edits": attempted_edits,
        },
        "forbidden_edits": forbidden_edits,
        "source_context_snippets": source_context_snippets,
        "source_context": source_context,
        "suggested_rule_category_edits": suggested_rule_category_edits,
        "suggested_rule_category_plan_edit_payload": (
            suggested_rule_category_plan_edit_payload
        ),
        "suggested_next_actions": suggested_next_actions,
        "next_test_id": verification.get("test_id") or verification_failure.get("test_id"),
        "next_workflow": [
            "send_retry_prompt_to_local_biber_model",
            "extract_repair_edits",
            "plan_repair_edits",
            "apply_only_after_human_or_policy_approval",
            "verify_repair_edits_again",
            "do_not_train_unless_retry_verifies_and_is_reviewed",
        ],
    }
    if runtime_profile_ids is not None:
        retry_request["runtime_profile_ids"] = runtime_profile_ids

    artifact_load_errors = [
        error
        for error in (
            apply_error,
            plan_error,
            extraction_error,
            attempt_error,
            mvp_error,
        )
        if error
    ]
    return {
        "source": "biber_mvp_loop_failed_repair_verification_review",
        "repair_loop_version": "mvp-v1",
        "review_status": "failed_repair_needs_retry",
        "ok": False,
        "safe_to_train": False,
        "training_allowed": False,
        "eligible_for_training": False,
        "auto_applied": False,
        "auto_saved": False,
        "source_artifact": str(path),
        "repair_apply_artifact": str(apply_path) if apply_path else None,
        "plan_hash": verification.get("plan_hash"),
        "test_id": verification.get("test_id") or verification_failure.get("test_id"),
        "verification": {
            "verification_status": verification.get("verification_status"),
            "ok": verification.get("ok"),
            "test_executed": test_run.get("executed"),
            "test_ok": test_run.get("ok"),
            "exit_code": test_run.get("exit_code"),
            "timed_out": bool(test_run.get("timed_out")),
        },
        "original_failure": original_failure,
        "attempted_edits": attempted_edits,
        "forbidden_edits": forbidden_edits,
        "source_context_snippets": source_context_snippets,
        "source_context": source_context,
        "suggested_rule_category_edits": suggested_rule_category_edits,
        "suggested_rule_category_plan_edit_payload": (
            suggested_rule_category_plan_edit_payload
        ),
        "verification_failure": verification_failure,
        "linked_artifacts": {
            "repair_apply": str(apply_path) if apply_path else None,
            "repair_plan": str(plan_path) if plan_path else None,
            "repair_extraction": str(extraction_path) if extraction_path else None,
            "repair_attempt": str(attempt_path) if attempt_path else None,
            "mvp_loop": str(mvp_path) if mvp_path else None,
        },
        "artifact_load_errors": artifact_load_errors,
        "retry_repair_request": retry_request,
        "next_workflow": [
            "run_attempt_repair_on_retry_repair_request",
            "extract_and_review_second_attempt_edits",
            "plan_then_apply_only_after_approval",
            "verify_again_before_exporting_any_success_candidate",
            "do_not_export_or_train_from_this_failed_review",
        ],
    }


def build_verified_repair_review_record(
    path: Path,
    verification: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        verification.get("verification_status") != "passed"
        or verification.get("ok") is not True
    ):
        raise BiberAgentClientError(
            "export-verified-repair requires a passed repair verification artifact."
        )
    test_run = require_mapping(verification.get("test_run"))
    command = [str(part) for part in require_list(test_run.get("command"))]
    relevant_output = test_run.get("stdout") or test_run.get("stderr") or ""
    return {
        "source": "biber_mvp_loop_verified_repair",
        "repair_loop_version": verification.get("repair_loop_version"),
        "review_status": "needs_human_review",
        "quality": "needs_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "auto_promoted": False,
        "auto_saved": False,
        "source_artifact": str(path),
        "repair_apply_artifact": verification.get("source_artifact"),
        "plan_hash": verification.get("plan_hash"),
        "test_id": verification.get("test_id") or test_run.get("test_id"),
        "verification": {
            "verification_status": verification.get("verification_status"),
            "ok": verification.get("ok"),
            "test_id": verification.get("test_id") or test_run.get("test_id"),
            "test_ok": test_run.get("ok"),
            "exit_code": test_run.get("exit_code"),
            "timed_out": bool(test_run.get("timed_out")),
        },
        "test": {
            "label": test_run.get("label"),
            "cwd": test_run.get("cwd"),
            "command": command,
            "duration_ms": test_run.get("duration_ms"),
            "relevant_output": compact_text(relevant_output),
        },
        "next_review_action": "human_review_before_eval_or_training",
    }


def export_verified_repair_review(
    *,
    artifact_path: str,
    output_path: str,
) -> dict[str, Any]:
    path = Path(artifact_path)
    artifact = load_json_artifact(str(path), label="repair verification artifact")
    verification = normalize_repair_test_verification_artifact(artifact)
    if verification is None:
        raise BiberAgentClientError(
            "export-verified-repair artifact must contain a saved repair verification JSON object."
        )
    record = build_verified_repair_review_record(path, verification)
    output = write_jsonl_artifact([record], output_path)
    return {
        "source": "biber_mvp_loop_verified_repair_export",
        "records": 1,
        "output": output,
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "source_artifact": str(path),
        "plan_hash": record.get("plan_hash"),
        "test_id": record.get("test_id"),
    }


def extract_model_edit_candidate_evidence(
    content: str,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    candidate_index = 0
    for value in extract_json_values_from_text(content):
        for candidate in extract_edit_objects_from_value(value):
            candidate_index += 1
            edit, rejection = validate_repair_edit_candidate(
                candidate,
                index=candidate_index,
            )
            item: dict[str, Any] = {
                "index": candidate_index,
                "source": "json",
                "candidate": dict(candidate),
            }
            if edit is not None:
                item["validated_edit"] = edit
            if rejection is not None:
                item["validation_rejection"] = rejection
            evidence.append(item)

    for candidate in extract_unified_diff_edit_candidates(content):
        candidate_index += 1
        edit, rejection = validate_repair_edit_candidate(
            candidate,
            index=candidate_index,
        )
        item = {
            "index": candidate_index,
            "source": "unified_diff",
            "candidate": dict(candidate),
        }
        if edit is not None:
            item["validated_edit"] = edit
        if rejection is not None:
            item["validation_rejection"] = rejection
        evidence.append(item)
    return evidence


def build_repeated_forbidden_retry_gap_record(
    *,
    extraction_path: Path,
    extraction: Mapping[str, Any],
    attempt_path: Path,
    attempt: Mapping[str, Any],
) -> dict[str, Any]:
    repeated_rejections = [
        dict(item)
        for item in require_list(extraction.get("rejected"))
        if isinstance(item, Mapping)
        and item.get("reason") == "repeated_failed_repair_edit"
    ]
    repeat_guard = require_mapping(extraction.get("repeat_failed_edit_guard"))
    if (
        extraction.get("ok") is True
        or extraction.get("extraction_status") != "no_valid_edits"
        or repeat_guard.get("enabled") is not True
        or not repeated_rejections
    ):
        raise BiberAgentClientError(
            "export-repeated-forbidden-retry-gap requires a no-valid-edits "
            "extraction artifact blocked by repeated_failed_repair_edit."
        )

    repair_request = require_mapping(attempt.get("repair_request"))
    if repair_request.get("retry_of_failed_verification") is not True:
        raise BiberAgentClientError(
            "export-repeated-forbidden-retry-gap requires a retry repair attempt."
        )

    model_response = require_mapping(attempt.get("model_response"))
    content = str(attempt.get("repair_content") or model_response.get("content") or "")
    model_candidates = extract_model_edit_candidate_evidence(content)
    repeated_indexes = {
        int(item.get("index"))
        for item in repeated_rejections
        if isinstance(item.get("index"), int)
        or (isinstance(item.get("index"), str) and str(item.get("index")).isdigit())
    }
    repeated_candidates = [
        item
        for item in model_candidates
        if int(item.get("index") or 0) in repeated_indexes
    ]
    previous_attempt = require_mapping(repair_request.get("previous_attempt"))
    forbidden_edits = [
        dict(item)
        for item in require_list(repair_request.get("forbidden_edits"))
        if isinstance(item, Mapping)
    ]
    if not forbidden_edits:
        forbidden_edits = [
            dict(item)
            for item in require_list(previous_attempt.get("attempted_edits"))
            if isinstance(item, Mapping)
        ]

    return {
        "source": "biber_mvp_loop_repeated_forbidden_retry_gap",
        "repair_loop_version": extraction.get("repair_loop_version")
        or attempt.get("repair_loop_version"),
        "gap_type": "repeated_forbidden_repair_edit",
        "failure_mode": "local_model_repeated_forbidden_edit_after_retry_instruction",
        "review_status": "needs_human_review",
        "quality": "needs_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "auto_applied": False,
        "apply_allowed": False,
        "source_artifact": str(extraction_path),
        "repair_attempt_artifact": str(attempt_path),
        "repair_request_source_artifact": repair_request.get("source_artifact"),
        "model": model_response.get("model"),
        "mentor_used": model_response.get("mentor_used") is True,
        "runtime_profile_ids": repair_attempt_runtime_profile_ids(attempt) or [],
        "next_test_id": extraction.get("next_test_id") or attempt.get("next_test_id"),
        "repair_prompt": repair_request.get("repair_prompt") or "",
        "forbidden_edits": forbidden_edits,
        "model_response_text": content,
        "model_response_preview": compact_text(content, max_chars=1000),
        "model_edit_candidates": model_candidates,
        "repeated_forbidden_candidates": repeated_candidates,
        "guard_rejection": {
            "repeat_failed_edit_guard": dict(repeat_guard),
            "rejected": repeated_rejections,
        },
        "original_failure": require_mapping(repair_request.get("original_failure")),
        "verification_failure": require_mapping(repair_request.get("failure")),
        "source_context_snippets": [
            dict(item)
            for item in require_list(repair_request.get("source_context_snippets"))
            if isinstance(item, Mapping)
        ],
        "next_review_action": (
            "human_review_repeated_forbidden_retry_gap_before_eval_or_training"
        ),
    }


def export_repeated_forbidden_retry_gap(
    *,
    artifact_path: str,
    output_path: str,
) -> dict[str, Any]:
    path = Path(artifact_path)
    artifact = load_json_artifact(str(path), label="repair edit extraction artifact")
    extraction = normalize_repair_edit_extraction_artifact(artifact)
    if extraction is None:
        raise BiberAgentClientError(
            "export-repeated-forbidden-retry-gap artifact must contain a saved "
            "extract-repair-edits JSON object."
        )
    attempt_path, attempt, attempt_error = load_linked_artifact(
        extraction.get("source_artifact"),
        base_path=path,
        label="repair-attempt artifact",
        normalizer=normalize_repair_attempt_artifact,
    )
    if attempt_error is not None or attempt_path is None or attempt is None:
        raise BiberAgentClientError(
            "Could not load linked repair-attempt artifact for repeated forbidden "
            f"retry gap export: {attempt_error or 'missing source_artifact'}"
        )

    record = build_repeated_forbidden_retry_gap_record(
        extraction_path=path,
        extraction=extraction,
        attempt_path=attempt_path,
        attempt=attempt,
    )
    output = write_jsonl_artifact([record], output_path)
    return {
        "source": "biber_mvp_loop_repeated_forbidden_retry_gap_export",
        "records": 1,
        "output": output,
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "source_artifact": str(path),
        "repair_attempt_artifact": str(attempt_path),
        "gap_type": record.get("gap_type"),
        "next_review_action": record.get("next_review_action"),
    }


def empty_edits_json_values(content: str) -> list[dict[str, Any]]:
    empty_values: list[dict[str, Any]] = []
    for index, value in enumerate(extract_json_values_from_text(content), start=1):
        if (
            isinstance(value, dict)
            and isinstance(value.get("edits"), list)
            and not value.get("edits")
        ):
            empty_values.append(
                {
                    "index": index,
                    "source": "json",
                    "value": {"edits": []},
                }
            )
    return empty_values


def empty_retry_gap_hints(
    *,
    content: str,
    forbidden_edits: list[Mapping[str, Any]],
) -> list[str]:
    lowered = content.lower()
    hints: list[str] = []
    if empty_edits_json_values(content):
        hints.append("empty_edits_json_returned")
    if any(
        phrase in lowered
        for phrase in (
            "to fix this",
            "need to",
            "different edit",
            "smallest safe source edit",
            "should fix",
            "will fix",
        )
    ):
        hints.append("prose_describes_fix_after_empty_edits")
    for edit in forbidden_edits:
        new_text = edit.get("new_text")
        if isinstance(new_text, str) and new_text and new_text.lower() in lowered:
            hints.append("prose_references_forbidden_edit_after_empty_edits")
            break
    return dedupe_strings(hints) or []


def build_empty_retry_gap_record(
    *,
    extraction_path: Path,
    extraction: Mapping[str, Any],
    attempt_path: Path,
    attempt: Mapping[str, Any],
) -> dict[str, Any]:
    edits = [item for item in require_list(extraction.get("edits")) if isinstance(item, Mapping)]
    rejected = [
        item for item in require_list(extraction.get("rejected")) if isinstance(item, Mapping)
    ]
    if (
        extraction.get("ok") is True
        or extraction.get("extraction_status") != "no_valid_edits"
        or edits
    ):
        raise BiberAgentClientError(
            "export-empty-retry-gap requires a no-valid-edits extraction artifact."
        )

    repair_request = require_mapping(attempt.get("repair_request"))
    if repair_request.get("retry_of_failed_verification") is not True:
        raise BiberAgentClientError(
            "export-empty-retry-gap requires a retry repair attempt."
        )

    model_response = require_mapping(attempt.get("model_response"))
    content = str(attempt.get("repair_content") or model_response.get("content") or "")
    empty_json_values = empty_edits_json_values(content)
    if not empty_json_values:
        raise BiberAgentClientError(
            "export-empty-retry-gap requires a model response with an empty edits JSON object."
        )

    previous_attempt = require_mapping(repair_request.get("previous_attempt"))
    forbidden_edits = [
        dict(item)
        for item in require_list(repair_request.get("forbidden_edits"))
        if isinstance(item, Mapping)
    ]
    if not forbidden_edits:
        forbidden_edits = [
            dict(item)
            for item in require_list(previous_attempt.get("attempted_edits"))
            if isinstance(item, Mapping)
        ]
    review_hints = empty_retry_gap_hints(
        content=content,
        forbidden_edits=forbidden_edits,
    )

    return {
        "source": "biber_mvp_loop_empty_retry_response_gap",
        "repair_loop_version": extraction.get("repair_loop_version")
        or attempt.get("repair_loop_version"),
        "gap_type": "empty_retry_response_with_unresolved_prose",
        "failure_mode": "local_model_returned_empty_edits_but_prose_still_described_fix",
        "review_status": "needs_human_review",
        "quality": "needs_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "auto_applied": False,
        "apply_allowed": False,
        "source_artifact": str(extraction_path),
        "repair_attempt_artifact": str(attempt_path),
        "repair_request_source_artifact": repair_request.get("source_artifact"),
        "model": model_response.get("model"),
        "mentor_used": model_response.get("mentor_used") is True,
        "runtime_profile_ids": repair_attempt_runtime_profile_ids(attempt) or [],
        "next_test_id": extraction.get("next_test_id") or attempt.get("next_test_id"),
        "repair_prompt": repair_request.get("repair_prompt") or "",
        "forbidden_edits": forbidden_edits,
        "model_response_text": content,
        "model_response_preview": compact_text(content, max_chars=1000),
        "empty_edit_json_values": empty_json_values,
        "model_edit_candidates": extract_model_edit_candidate_evidence(content),
        "extraction": {
            "extraction_status": extraction.get("extraction_status"),
            "ok": extraction.get("ok"),
            "edits": edits,
            "rejected": rejected,
            "source_only_guard": dict(require_mapping(extraction.get("source_only_guard"))),
            "repeat_failed_edit_guard": dict(
                require_mapping(extraction.get("repeat_failed_edit_guard"))
            ),
        },
        "original_failure": require_mapping(repair_request.get("original_failure")),
        "verification_failure": require_mapping(repair_request.get("failure")),
        "source_context_snippets": [
            dict(item)
            for item in require_list(repair_request.get("source_context_snippets"))
            if isinstance(item, Mapping)
        ],
        "review_hints": review_hints,
        "next_review_action": (
            "human_review_empty_retry_gap_before_prompt_or_context_changes"
        ),
    }


def export_empty_retry_gap(
    *,
    artifact_path: str,
    output_path: str,
) -> dict[str, Any]:
    path = Path(artifact_path)
    artifact = load_json_artifact(str(path), label="repair edit extraction artifact")
    extraction = normalize_repair_edit_extraction_artifact(artifact)
    if extraction is None:
        raise BiberAgentClientError(
            "export-empty-retry-gap artifact must contain a saved "
            "extract-repair-edits JSON object."
        )
    attempt_path, attempt, attempt_error = load_linked_artifact(
        extraction.get("source_artifact"),
        base_path=path,
        label="repair-attempt artifact",
        normalizer=normalize_repair_attempt_artifact,
    )
    if attempt_error is not None or attempt_path is None or attempt is None:
        raise BiberAgentClientError(
            "Could not load linked repair-attempt artifact for empty retry gap "
            f"export: {attempt_error or 'missing source_artifact'}"
        )

    record = build_empty_retry_gap_record(
        extraction_path=path,
        extraction=extraction,
        attempt_path=attempt_path,
        attempt=attempt,
    )
    output = write_jsonl_artifact([record], output_path)
    return {
        "source": "biber_mvp_loop_empty_retry_gap_export",
        "records": 1,
        "output": output,
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "source_artifact": str(path),
        "repair_attempt_artifact": str(attempt_path),
        "gap_type": record.get("gap_type"),
        "review_hints": record.get("review_hints"),
        "next_review_action": record.get("next_review_action"),
    }


def suggested_rule_category_edit_candidates_from_repair_request(
    repair_request: Mapping[str, Any],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for index, candidate in enumerate(
        require_list(repair_request.get("suggested_rule_category_edits")),
        start=1,
    ):
        if not isinstance(candidate, Mapping):
            continue
        edit_candidate = {
            key: candidate.get(key)
            for key in (
                "path",
                "file",
                "old_text",
                "new_text",
                "expected_replacements",
                "create_if_missing",
                "dry_run",
            )
            if key in candidate
        }
        edit, rejection = validate_repair_edit_candidate(
            edit_candidate,
            index=index,
        )
        item: dict[str, Any] = {
            "index": index,
            "candidate": dict(candidate),
            "reason": candidate.get("reason"),
        }
        if edit is not None:
            item["validated_edit"] = edit
        if rejection is not None:
            item["validation_rejection"] = rejection
        evidence.append(item)
    return evidence


def build_blocked_retry_edit_gap_record(
    *,
    review_path: Path,
    review: Mapping[str, Any],
    extraction_path: Path,
    extraction: Mapping[str, Any],
    attempt_path: Path,
    attempt: Mapping[str, Any],
) -> dict[str, Any]:
    hard_blockers = [
        str(item)
        for item in require_list(review.get("hard_blockers"))
        if str(item).strip()
    ]
    candidate_reviews = [
        dict(item)
        for item in require_list(review.get("candidate_reviews"))
        if isinstance(item, Mapping)
    ]
    blocked_candidates = [
        item
        for item in candidate_reviews
        if item.get("allowed_for_plan") is not True
        or require_list(item.get("hard_blockers"))
    ]
    if (
        review.get("ok") is True
        or review.get("plan_allowed") is True
        or not hard_blockers
        or not blocked_candidates
    ):
        raise BiberAgentClientError(
            "export-blocked-retry-edit-gap requires a blocked retry edit review "
            "with hard blockers."
        )

    repair_request = require_mapping(attempt.get("repair_request"))
    if repair_request.get("retry_of_failed_verification") is not True:
        raise BiberAgentClientError(
            "export-blocked-retry-edit-gap requires a retry repair attempt."
        )

    model_response = require_mapping(attempt.get("model_response"))
    content = str(attempt.get("repair_content") or model_response.get("content") or "")
    suggested_rule_category_edit_evidence = (
        suggested_rule_category_edit_candidates_from_repair_request(repair_request)
    )
    suggested_rule_category_edits = [
        dict(item.get("validated_edit"))
        for item in suggested_rule_category_edit_evidence
        if isinstance(item.get("validated_edit"), Mapping)
    ]
    suggested_rule_category_payload = {"edits": suggested_rule_category_edits}
    return {
        "source": "biber_mvp_loop_blocked_retry_edit_gap",
        "repair_loop_version": review.get("repair_loop_version")
        or extraction.get("repair_loop_version")
        or attempt.get("repair_loop_version"),
        "gap_type": "blocked_retry_repair_edit_candidate",
        "failure_mode": "deterministic_retry_review_blocked_candidate_before_planning",
        "review_status": "needs_human_review",
        "quality": "needs_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "auto_applied": False,
        "apply_allowed": False,
        "plan_allowed": False,
        "source_artifact": str(review_path),
        "retry_edit_review_artifact": str(review_path),
        "repair_edit_extraction_artifact": str(extraction_path),
        "repair_attempt_artifact": str(attempt_path),
        "repair_request_source_artifact": repair_request.get("source_artifact"),
        "model": model_response.get("model") or review.get("model"),
        "mentor_used": model_response.get("mentor_used") is True
        or review.get("mentor_used") is True,
        "runtime_profile_ids": repair_attempt_runtime_profile_ids(attempt) or [],
        "next_test_id": review.get("next_test_id")
        or extraction.get("next_test_id")
        or attempt.get("next_test_id"),
        "review_hard_blockers": hard_blockers,
        "review_hints": [
            str(item)
            for item in require_list(review.get("review_hints"))
            if str(item).strip()
        ],
        "candidate_reviews": candidate_reviews,
        "blocked_candidates": blocked_candidates,
        "edits": [
            dict(item)
            for item in require_list(review.get("edits"))
            if isinstance(item, Mapping)
        ],
        "reviewed_plan_edit_payload": dict(
            require_mapping(review.get("reviewed_plan_edit_payload"))
        ),
        "forbidden_edits": [
            dict(item)
            for item in require_list(review.get("forbidden_edits"))
            if isinstance(item, Mapping)
        ],
        "model_response_text": content,
        "model_response_preview": compact_text(content, max_chars=1000),
        "model_edit_candidates": extract_model_edit_candidate_evidence(content),
        "suggested_rule_category_edit_evidence": (
            suggested_rule_category_edit_evidence
        ),
        "suggested_rule_category_edits": suggested_rule_category_edits,
        "suggested_rule_category_plan_edit_payload": (
            suggested_rule_category_payload
        ),
        "repair_prompt": repair_request.get("repair_prompt") or "",
        "original_failure": require_mapping(repair_request.get("original_failure")),
        "verification_failure": require_mapping(repair_request.get("failure")),
        "source_context_snippets": [
            dict(item)
            for item in require_list(review.get("source_context_snippets"))
            if isinstance(item, Mapping)
        ],
        "next_review_action": (
            "human_review_blocked_retry_edit_gap_before_prompt_or_training_changes"
        ),
    }


def export_blocked_retry_edit_gap(
    *,
    artifact_path: str,
    output_path: str,
) -> dict[str, Any]:
    path = Path(artifact_path)
    artifact = load_json_artifact(str(path), label="retry repair edit review artifact")
    review = normalize_retry_repair_edit_review_artifact(artifact)
    if review is None:
        raise BiberAgentClientError(
            "export-blocked-retry-edit-gap artifact must contain a saved "
            "review-retry-repair-edits JSON object."
        )

    extraction_path, extraction, extraction_error = load_linked_artifact(
        review.get("source_artifact"),
        base_path=path,
        label="repair-edit extraction artifact",
        normalizer=normalize_repair_edit_extraction_artifact,
    )
    if extraction_error is not None or extraction_path is None or extraction is None:
        raise BiberAgentClientError(
            "Could not load linked repair-edit extraction artifact for blocked "
            f"retry edit gap export: {extraction_error or 'missing source_artifact'}"
        )

    attempt_reference = review.get("repair_attempt_artifact") or extraction.get(
        "source_artifact"
    )
    attempt_path, attempt, attempt_error = load_linked_artifact(
        attempt_reference,
        base_path=path,
        label="repair-attempt artifact",
        normalizer=normalize_repair_attempt_artifact,
    )
    if attempt_error is not None or attempt_path is None or attempt is None:
        raise BiberAgentClientError(
            "Could not load linked repair-attempt artifact for blocked retry "
            f"edit gap export: {attempt_error or 'missing repair_attempt_artifact'}"
        )

    record = build_blocked_retry_edit_gap_record(
        review_path=path,
        review=review,
        extraction_path=extraction_path,
        extraction=extraction,
        attempt_path=attempt_path,
        attempt=attempt,
    )
    output = write_jsonl_artifact([record], output_path)
    return {
        "source": "biber_mvp_loop_blocked_retry_edit_gap_export",
        "records": 1,
        "output": output,
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "source_artifact": str(path),
        "repair_edit_extraction_artifact": str(extraction_path),
        "repair_attempt_artifact": str(attempt_path),
        "gap_type": record.get("gap_type"),
        "review_hard_blockers": record.get("review_hard_blockers"),
        "next_review_action": record.get("next_review_action"),
    }


def blocked_retry_edit_gap_path(record: Mapping[str, Any]) -> str:
    blocked_candidates = [
        item
        for item in require_list(record.get("blocked_candidates"))
        if isinstance(item, Mapping)
    ]
    for candidate in blocked_candidates:
        path = candidate.get("path")
        if isinstance(path, str) and path:
            return path
    edits = [
        item for item in require_list(record.get("edits")) if isinstance(item, Mapping)
    ]
    for edit in edits:
        path = edit.get("path")
        if isinstance(path, str) and path:
            return path
    return ""


def blocked_retry_edit_gap_hints(record: Mapping[str, Any]) -> list[str]:
    hints = [
        str(item)
        for item in require_list(record.get("review_hints"))
        if isinstance(item, str) and item
    ]
    hard_blockers = require_list(record.get("review_hard_blockers"))
    if "retry_edit_changes_previous_failed_target_outside_rule_context" in hard_blockers:
        hints.append("previous_failed_target_retry_blocked_by_rule_context")
    if "source_rule_context_present" in hints and "failure_line_test_expectation_present" in hints:
        hints.append("rule_and_failure_line_context_available")
    suggested_edits = [
        item
        for item in require_list(record.get("suggested_rule_category_edits"))
        if isinstance(item, Mapping)
    ]
    if suggested_edits:
        hints.append("suggested_rule_category_edit_available")

    suggested_signatures = {
        repair_edit_signature(item) for item in suggested_edits
    }
    model_signatures = {
        repair_edit_signature(require_mapping(item.get("validated_edit")))
        for item in require_list(record.get("model_edit_candidates"))
        if isinstance(item, Mapping)
        and isinstance(item.get("validated_edit"), Mapping)
    }
    if suggested_signatures and model_signatures and not (
        suggested_signatures & model_signatures
    ):
        hints.append("model_json_candidate_differs_from_suggested_rule_category_edit")

    response_text = str(record.get("model_response_text") or "").lower()
    prose_mentions_rule_edit = any(
        phrase in response_text
        for phrase in (
            "suggested rule-category edit",
            "rule-category edit",
            "change the rule category",
            "changing the rule category",
            "rule category to",
        )
    )
    if suggested_edits and prose_mentions_rule_edit:
        hints.append("model_prose_mentions_suggested_rule_category_edit")
    if (
        "model_json_candidate_differs_from_suggested_rule_category_edit" in hints
        and "model_prose_mentions_suggested_rule_category_edit" in hints
    ):
        hints.append("json_candidate_conflicts_with_suggested_rule_category_edit")
    return dedupe_strings(hints) or []


def review_blocked_retry_edit_gap_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(jsonl_path, label="blocked retry edit gap JSONL"),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_blocked_retry_edit_gap":
                item = dict(row)
                item["jsonl_path"] = jsonl_path
                item["jsonl_index"] = index
                item["review_hints"] = blocked_retry_edit_gap_hints(item)
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    groups_by_key: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for record in records:
        hard_blockers = [
            str(item)
            for item in require_list(record.get("review_hard_blockers"))
            if str(item).strip()
        ]
        key = (
            str(record.get("model") or ""),
            str(record.get("next_test_id") or ""),
            blocked_retry_edit_gap_path(record),
            str(record.get("failure_mode") or ""),
            "|".join(hard_blockers),
        )
        group = groups_by_key.setdefault(
            key,
            {
                "model": key[0],
                "next_test_id": key[1],
                "path": key[2],
                "failure_mode": key[3],
                "hard_blockers": hard_blockers,
                "count": 0,
                "source_artifacts": [],
                "retry_edit_review_artifacts": [],
                "repair_edit_extraction_artifacts": [],
                "repair_attempt_artifacts": [],
                "jsonl_refs": [],
                "review_hints": [],
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
            },
        )
        group["count"] += 1
        group["source_artifacts"].append(record.get("source_artifact"))
        group["retry_edit_review_artifacts"].append(
            record.get("retry_edit_review_artifact")
        )
        group["repair_edit_extraction_artifacts"].append(
            record.get("repair_edit_extraction_artifact")
        )
        group["repair_attempt_artifacts"].append(record.get("repair_attempt_artifact"))
        suggested_rule_category_payload = require_mapping(
            record.get("suggested_rule_category_plan_edit_payload")
        )
        if suggested_rule_category_payload:
            group.setdefault(
                "suggested_rule_category_plan_edit_payloads",
                [],
            ).append(suggested_rule_category_payload)
        group["jsonl_refs"].append(
            {
                "jsonl_path": record.get("jsonl_path"),
                "jsonl_index": record.get("jsonl_index"),
            }
        )
        group["review_hints"] = dedupe_strings(
            [
                str(item)
                for item in [
                    *require_list(group.get("review_hints")),
                    *require_list(record.get("review_hints")),
                ]
                if item
            ]
        )

    groups = [
        group
        for group in groups_by_key.values()
        if int_count(group.get("count")) >= min_repeat
    ]
    groups.sort(
        key=lambda item: (
            -int_count(item.get("count")),
            str(item.get("model") or ""),
            str(item.get("next_test_id") or ""),
            str(item.get("path") or ""),
        )
    )
    review_hints = dedupe_strings(
        [
            str(hint)
            for record in records
            for hint in require_list(record.get("review_hints"))
            if hint
        ]
    )

    return {
        "source": "biber_mvp_loop_blocked_retry_edit_gap_review",
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "jsonl_paths": list(jsonl_paths),
        "records": len(records),
        "rejected_records": len(rejected),
        "min_repeat": min_repeat,
        "ready_for_human_review": len(records),
        "groups": groups,
        "review_hints": review_hints,
        "rejected": rejected,
        "next_review_action": (
            "human_review_blocked_retry_edit_gap_groups_before_prompt_or_training_changes"
        ),
    }


def empty_retry_gap_path(record: Mapping[str, Any]) -> str:
    forbidden_edits = [
        item
        for item in require_list(record.get("forbidden_edits"))
        if isinstance(item, Mapping)
    ]
    for edit in forbidden_edits:
        path = edit.get("path")
        if isinstance(path, str) and path:
            return path
    return ""


def empty_retry_gap_record_hints(record: Mapping[str, Any]) -> list[str]:
    hints = [
        str(item)
        for item in require_list(record.get("review_hints"))
        if isinstance(item, str) and item
    ]
    forbidden_edits = [
        dict(item)
        for item in require_list(record.get("forbidden_edits"))
        if isinstance(item, Mapping)
    ]
    hints.extend(
        empty_retry_gap_hints(
            content=str(record.get("model_response_text") or ""),
            forbidden_edits=forbidden_edits,
        )
    )
    return dedupe_strings(hints) or []


def review_empty_retry_gap_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(jsonl_path, label="empty retry gap JSONL"),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_empty_retry_response_gap":
                item = dict(row)
                item["jsonl_path"] = jsonl_path
                item["jsonl_index"] = index
                item["review_hints"] = empty_retry_gap_record_hints(item)
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    groups_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for record in records:
        key = (
            str(record.get("model") or ""),
            str(record.get("next_test_id") or ""),
            empty_retry_gap_path(record),
            str(record.get("failure_mode") or ""),
        )
        group = groups_by_key.setdefault(
            key,
            {
                "model": key[0],
                "next_test_id": key[1],
                "path": key[2],
                "failure_mode": key[3],
                "count": 0,
                "source_artifacts": [],
                "repair_attempt_artifacts": [],
                "jsonl_refs": [],
                "review_hints": [],
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
            },
        )
        group["count"] += 1
        group["source_artifacts"].append(record.get("source_artifact"))
        group["repair_attempt_artifacts"].append(record.get("repair_attempt_artifact"))
        group["jsonl_refs"].append(
            {
                "jsonl_path": record.get("jsonl_path"),
                "jsonl_index": record.get("jsonl_index"),
            }
        )
        group["review_hints"] = dedupe_strings(
            [
                str(item)
                for item in [
                    *require_list(group.get("review_hints")),
                    *require_list(record.get("review_hints")),
                ]
                if item
            ]
        )

    groups = [
        group
        for group in groups_by_key.values()
        if int_count(group.get("count")) >= min_repeat
    ]
    groups.sort(
        key=lambda item: (
            -int_count(item.get("count")),
            str(item.get("model") or ""),
            str(item.get("next_test_id") or ""),
            str(item.get("path") or ""),
        )
    )
    review_hints = dedupe_strings(
        [
            str(hint)
            for record in records
            for hint in require_list(record.get("review_hints"))
            if hint
        ]
    )

    return {
        "source": "biber_mvp_loop_empty_retry_gap_review",
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "jsonl_paths": list(jsonl_paths),
        "records": len(records),
        "rejected_records": len(rejected),
        "min_repeat": min_repeat,
        "ready_for_human_review": len(records),
        "groups": groups,
        "review_hints": review_hints,
        "rejected": rejected,
        "next_review_action": (
            "human_review_empty_retry_gap_groups_before_prompt_or_context_changes"
        ),
    }


def repeated_forbidden_gap_path(record: Mapping[str, Any]) -> str:
    repeated_candidates = [
        item
        for item in require_list(record.get("repeated_forbidden_candidates"))
        if isinstance(item, Mapping)
    ]
    for candidate in repeated_candidates:
        validated_edit = require_mapping(candidate.get("validated_edit"))
        path = validated_edit.get("path")
        if isinstance(path, str) and path:
            return path
    forbidden_edits = [
        item
        for item in require_list(record.get("forbidden_edits"))
        if isinstance(item, Mapping)
    ]
    for edit in forbidden_edits:
        path = edit.get("path")
        if isinstance(path, str) and path:
            return path
    return ""


def repeated_forbidden_gap_hints(record: Mapping[str, Any]) -> list[str]:
    hints: list[str] = []
    prompt = str(record.get("repair_prompt") or "").lower()
    response = str(record.get("model_response_text") or "").lower()
    repeated_candidates = require_list(record.get("repeated_forbidden_candidates"))
    if repeated_candidates and "forbidden edit" in prompt:
        hints.append("prompt_forbidden_edit_instruction_ignored")
    if repeated_candidates and '{"edits":[]}' in prompt:
        hints.append("empty_edits_escape_instruction_ignored")
    if repeated_candidates and (
        "root cause" in response
        or "different edit" in response
        or "instead" in response
        or "add a new rule" in response
    ):
        hints.append("json_candidate_conflicts_with_model_explanation")
    source_context_snippets = [
        item
        for item in require_list(record.get("source_context_snippets"))
        if isinstance(item, Mapping)
    ]
    if repeated_candidates and any(
        item.get("snippet_kind") == "rule" for item in source_context_snippets
    ):
        hints.append("rule_context_seen_but_repeated_target_edit")
    return dedupe_strings(hints) or []


def review_repeated_forbidden_retry_gap_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(jsonl_path, label="repeated forbidden gap JSONL"),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repeated_forbidden_retry_gap":
                item = dict(row)
                item["jsonl_path"] = jsonl_path
                item["jsonl_index"] = index
                item["review_hints"] = repeated_forbidden_gap_hints(item)
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    groups_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for record in records:
        path = repeated_forbidden_gap_path(record)
        key = (
            str(record.get("model") or ""),
            str(record.get("next_test_id") or ""),
            path,
            str(record.get("failure_mode") or ""),
        )
        group = groups_by_key.setdefault(
            key,
            {
                "model": key[0],
                "next_test_id": key[1],
                "path": key[2],
                "failure_mode": key[3],
                "count": 0,
                "source_artifacts": [],
                "repair_attempt_artifacts": [],
                "jsonl_refs": [],
                "review_hints": [],
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
            },
        )
        group["count"] += 1
        group["source_artifacts"].append(record.get("source_artifact"))
        group["repair_attempt_artifacts"].append(record.get("repair_attempt_artifact"))
        group["jsonl_refs"].append(
            {
                "jsonl_path": record.get("jsonl_path"),
                "jsonl_index": record.get("jsonl_index"),
            }
        )
        group["review_hints"] = dedupe_strings(
            [
                str(item)
                for item in [
                    *require_list(group.get("review_hints")),
                    *require_list(record.get("review_hints")),
                ]
                if item
            ]
        )

    groups = [
        group
        for group in groups_by_key.values()
        if int_count(group.get("count")) >= min_repeat
    ]
    groups.sort(
        key=lambda item: (
            -int_count(item.get("count")),
            str(item.get("model") or ""),
            str(item.get("next_test_id") or ""),
            str(item.get("path") or ""),
        )
    )
    review_hints = dedupe_strings(
        [
            str(hint)
            for record in records
            for hint in require_list(record.get("review_hints"))
            if hint
        ]
    )

    return {
        "source": "biber_mvp_loop_repeated_forbidden_retry_gap_review",
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "jsonl_paths": list(jsonl_paths),
        "records": len(records),
        "rejected_records": len(rejected),
        "min_repeat": min_repeat,
        "ready_for_human_review": len(records),
        "groups": groups,
        "review_hints": review_hints,
        "rejected": rejected,
        "next_review_action": (
            "human_review_repeated_forbidden_gap_groups_before_prompt_or_eval_changes"
        ),
    }


def review_verified_repair_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(jsonl_path, label="verified repair JSONL"),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_verified_repair":
                item = dict(row)
                item["jsonl_path"] = jsonl_path
                item["jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (
            str(record.get("test_id") or ""),
            str(record.get("plan_hash") or ""),
        )
        group = groups_by_key.setdefault(
            key,
            {
                "test_id": key[0],
                "plan_hash": key[1],
                "count": 0,
                "source_artifacts": [],
                "review_statuses": [],
                "eligible_for_training": False,
            },
        )
        group["count"] += 1
        group["source_artifacts"].append(record.get("source_artifact"))
        group["review_statuses"].append(record.get("review_status"))
    groups = [
        group
        for group in groups_by_key.values()
        if int(group.get("count") or 0) >= min_repeat
    ]
    groups.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("test_id") or "")))

    return {
        "source": "biber_mvp_loop_verified_repair_review",
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "records": len(records),
        "rejected_records": len(rejected),
        "min_repeat": min_repeat,
        "ready_for_human_review": len(records),
        "groups": groups,
        "rejected": rejected,
        "next_review_action": (
            "human_review_repeated_verified_repairs_before_eval_or_training"
        ),
    }


def normalize_verified_repair_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_verified_repair_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_verified_repair_review"
    ):
        return dict(body)
    return None


def summarize_verified_repair_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "ready_for_human_review": int_count(payload.get("ready_for_human_review")),
        "groups": len(groups),
        "min_repeat": max(1, int_count(payload.get("min_repeat") or 1)),
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_verified_repair_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Verified repair review artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Verified repair review artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="verified repair review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_verified_repair_review_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_verified_repair_review_artifact(path, normalized)
        if ready_only and int_count(summary.get("ready_for_human_review")) < 1:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_verified_repair_review_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ready_artifacts": sum(
            1
            for item in artifacts
            if int_count(item.get("ready_for_human_review")) > 0
        ),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "ready_for_human_review": sum(
            int_count(item.get("ready_for_human_review")) for item in artifacts
        ),
        "training_allowed": False,
        "eligible_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def load_repair_chain_artifact(
    *,
    artifact_path: str | None,
    label: str,
    normalizer: Any,
) -> dict[str, Any] | None:
    if artifact_path is None:
        return None
    raw_payload = load_json_artifact(artifact_path, label=label)
    normalized = normalizer(raw_payload)
    if normalized is None:
        raise BiberAgentClientError(f"{label} has an unsupported artifact shape.")
    return normalized


def optional_artifact_path(path: str | None) -> str | None:
    if path is None:
        return None
    return str(Path(path))


def artifact_status(
    payload: Mapping[str, Any] | None,
    key: str,
    *,
    missing: str = "not_supplied",
) -> object:
    if payload is None:
        return missing
    return payload.get(key, "unknown")


def int_count(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    try:
        return max(0, int(str(value)))
    except (TypeError, ValueError):
        return 0


def build_repair_chain_summary(
    *,
    mvp_loop_path: str | None,
    repair_path: str | None,
    attempt_path: str | None,
    extraction_path: str | None,
    plan_path: str | None,
    apply_path: str | None,
    verification_path: str | None,
    review_jsonl_paths: list[str],
    review_summary_path: str | None,
    repo_provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not any(
        [
            mvp_loop_path,
            repair_path,
            attempt_path,
            extraction_path,
            plan_path,
            apply_path,
            verification_path,
            review_jsonl_paths,
            review_summary_path,
        ]
    ):
        raise BiberAgentClientError(
            "show-repair-chain requires at least one artifact path."
        )

    mvp_loop = load_repair_chain_artifact(
        artifact_path=mvp_loop_path,
        label="mvp-loop artifact",
        normalizer=normalize_mvp_loop_artifact,
    )
    repair = load_repair_chain_artifact(
        artifact_path=repair_path,
        label="repair request artifact",
        normalizer=normalize_mvp_loop_repair_request_artifact,
    )
    attempt = load_repair_chain_artifact(
        artifact_path=attempt_path,
        label="repair attempt artifact",
        normalizer=normalize_repair_attempt_artifact,
    )
    extraction = load_repair_chain_artifact(
        artifact_path=extraction_path,
        label="repair edit extraction artifact",
        normalizer=normalize_repair_edit_extraction_artifact,
    )
    plan = load_repair_chain_artifact(
        artifact_path=plan_path,
        label="repair edit plan artifact",
        normalizer=normalize_repair_edit_plan_artifact,
    )
    repair_apply = load_repair_chain_artifact(
        artifact_path=apply_path,
        label="repair edit apply artifact",
        normalizer=normalize_repair_edit_apply_artifact,
    )
    verification = load_repair_chain_artifact(
        artifact_path=verification_path,
        label="repair test verification artifact",
        normalizer=normalize_repair_test_verification_artifact,
    )
    review_summary = load_repair_chain_artifact(
        artifact_path=review_summary_path,
        label="verified repair review summary artifact",
        normalizer=normalize_verified_repair_review_artifact,
    )

    review_records = 0
    ready_for_human_review_count = 0
    rejected_review_records = 0
    for jsonl_path in review_jsonl_paths:
        for row in load_jsonl_artifact(jsonl_path, label="verified repair JSONL"):
            if row.get("source") != "biber_mvp_loop_verified_repair":
                rejected_review_records += 1
                continue
            review_records += 1
            if row.get("review_status") == "needs_human_review":
                ready_for_human_review_count += 1

    if review_summary is not None:
        review_records = max(review_records, int_count(review_summary.get("records")))
        ready_for_human_review_count = max(
            ready_for_human_review_count,
            int_count(review_summary.get("ready_for_human_review")),
        )
        rejected_review_records = max(
            rejected_review_records,
            int_count(review_summary.get("rejected_records")),
        )

    plan_hashes = [
        str(value)
        for value in [
            plan.get("plan_hash") if plan is not None else None,
            repair_apply.get("plan_hash") if repair_apply is not None else None,
            verification.get("plan_hash") if verification is not None else None,
        ]
        if isinstance(value, str) and value
    ]
    plan_hash_consistent = len(set(plan_hashes)) <= 1
    verification_passed = (
        verification is not None
        and verification.get("verification_status") == "passed"
        and verification.get("ok") is True
    )
    chain_complete = all(
        artifact is not None
        for artifact in [repair, attempt, extraction, plan, repair_apply, verification]
    )
    auto_applied = any(
        artifact.get("auto_applied") is True
        for artifact in [
            repair,
            attempt,
            extraction,
            plan,
            repair_apply,
            verification,
        ]
        if artifact is not None
    )
    ready_for_human_review = (
        chain_complete
        and verification_passed
        and plan_hash_consistent
        and not auto_applied
        and ready_for_human_review_count > 0
    )

    statuses = {
        "mvp_loop_ok": mvp_loop.get("ok") if mvp_loop is not None else "not_supplied",
        "repair_status": artifact_status(repair, "repair_status"),
        "attempt_status": artifact_status(attempt, "repair_status"),
        "extraction_status": artifact_status(extraction, "extraction_status"),
        "plan_status": artifact_status(plan, "plan_status"),
        "apply_status": artifact_status(repair_apply, "apply_status"),
        "verification_status": artifact_status(
            verification,
            "verification_status",
        ),
        "review_records": review_records,
        "ready_for_human_review": ready_for_human_review_count,
        "rejected_review_records": rejected_review_records,
    }
    artifacts = {
        "mvp_loop": optional_artifact_path(mvp_loop_path),
        "repair": optional_artifact_path(repair_path),
        "attempt": optional_artifact_path(attempt_path),
        "extraction": optional_artifact_path(extraction_path),
        "plan": optional_artifact_path(plan_path),
        "apply": optional_artifact_path(apply_path),
        "verification": optional_artifact_path(verification_path),
        "review_jsonl": [str(Path(path)) for path in review_jsonl_paths],
        "review_summary": optional_artifact_path(review_summary_path),
    }
    missing_artifacts = [
        name
        for name in ["repair", "attempt", "extraction", "plan", "apply", "verification"]
        if artifacts[name] is None
    ]
    test_id = None
    for artifact in [verification, repair_apply, plan, extraction, repair]:
        if artifact is None:
            continue
        value = artifact.get("test_id") or artifact.get("next_test_id")
        if isinstance(value, str) and value:
            test_id = value
            break
    normalized_repo_provenance = normalize_repo_provenance(repo_provenance)
    if normalized_repo_provenance is None and mvp_loop is not None:
        normalized_repo_provenance = normalize_repo_provenance(
            mvp_loop.get("repo_provenance")
        )

    summary = {
        "source": "biber_mvp_loop_repair_chain_summary",
        "repair_loop_version": "mvp-v1",
        "ok": ready_for_human_review,
        "chain_status": (
            "ready_for_human_review"
            if ready_for_human_review
            else "incomplete_or_needs_repair"
        ),
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "auto_applied": auto_applied,
        "github_save_ready": False,
        "ready_for_human_review": ready_for_human_review,
        "chain_complete": chain_complete,
        "verification_passed": verification_passed,
        "plan_hash": plan_hashes[0] if plan_hashes else None,
        "plan_hash_consistent": plan_hash_consistent,
        "test_id": test_id,
        "statuses": statuses,
        "artifacts": artifacts,
        "missing_artifacts": missing_artifacts,
        "next_action": (
            "human_review_before_github_or_training"
            if ready_for_human_review
            else "continue_repair_loop_without_training_or_github_save"
        ),
    }
    if normalized_repo_provenance is not None:
        summary["repo_provenance"] = normalized_repo_provenance
    return summary


def normalize_repair_chain_summary_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_chain_summary":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_repair_chain_summary"
    ):
        return dict(body)
    return None


def summarize_repair_chain_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    statuses = payload.get("statuses")
    if not isinstance(statuses, dict):
        statuses = {}
    repo_provenance = normalize_repo_provenance(payload.get("repo_provenance"))
    summary = {
        "path": str(path),
        "chain_status": payload.get("chain_status"),
        "ready_for_human_review": payload.get("ready_for_human_review") is True,
        "chain_complete": payload.get("chain_complete") is True,
        "verification_passed": payload.get("verification_passed") is True,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "plan_hash": payload.get("plan_hash"),
        "test_id": payload.get("test_id"),
        "review_records": int_count(statuses.get("review_records")),
        "repo_provenance_ready": repo_provenance_ok_for_eval(payload),
        "eval_approval_requires_repo_provenance": True,
        "next_action": payload.get("next_action"),
        "modified_epoch": modified_epoch,
    }
    if repo_provenance is not None:
        summary["repo_provenance"] = repo_provenance
    return summary


def list_repair_chain_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(f"Repair chain artifact directory does not exist: {root}")
    if not root.is_dir():
        raise BiberAgentClientError(f"Repair chain artifact path is not a directory: {root}")

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(str(path), label="repair-chain artifact")
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_summary_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_repair_chain_artifact(path, normalized)
        if ready_only and summary.get("ready_for_human_review") is not True:
            continue
        artifacts.append(summary)

    artifacts.sort(key=lambda item: float(item.get("modified_epoch") or 0.0), reverse=True)
    ready_count = sum(
        1 for item in artifacts if item.get("ready_for_human_review") is True
    )
    repo_provenance_ready = sum(
        1 for item in artifacts if item.get("repo_provenance_ready") is True
    )
    return {
        "source": "biber_mvp_loop_repair_chain_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ready_for_human_review": ready_count,
        "repo_provenance_ready": repo_provenance_ready,
        "repo_provenance_missing": len(artifacts) - repo_provenance_ready,
        "eval_approval_requires_repo_provenance": True,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "artifacts": artifacts[:limit],
    }


def build_repair_chain_review_record(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    if (
        payload.get("chain_status") != "ready_for_human_review"
        or payload.get("ready_for_human_review") is not True
    ):
        raise BiberAgentClientError(
            "export-ready-repair-chains requires ready repair-chain summary artifacts."
        )
    statuses = payload.get("statuses")
    if not isinstance(statuses, dict):
        statuses = {}
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    repo_provenance = normalize_repo_provenance(payload.get("repo_provenance"))
    provenance = classify_repair_chain_evidence_source(
        {
            "source_artifact": str(path),
            "artifacts": artifacts,
            "repo_provenance": repo_provenance,
        }
    )
    record = {
        "source": "biber_mvp_loop_repair_chain_review",
        "repair_loop_version": payload.get("repair_loop_version"),
        "review_status": "needs_human_review",
        "quality": "needs_review",
        **provenance,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "auto_saved": False,
        "github_save_ready": False,
        "source_artifact": str(path),
        "plan_hash": payload.get("plan_hash"),
        "test_id": payload.get("test_id"),
        "chain": {
            "chain_status": payload.get("chain_status"),
            "chain_complete": payload.get("chain_complete"),
            "verification_passed": payload.get("verification_passed"),
            "plan_hash_consistent": payload.get("plan_hash_consistent"),
            "review_records": int_count(statuses.get("review_records")),
            "ready_for_human_review": payload.get("ready_for_human_review"),
        },
        "artifacts": dict(artifacts),
        "next_review_action": "human_review_repair_chain_before_github_or_training",
    }
    if repo_provenance is not None:
        record["repo_provenance"] = repo_provenance
    return record


def export_ready_repair_chain_reviews(
    *,
    directory: str,
    pattern: str,
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(f"Repair chain artifact directory does not exist: {root}")
    if not root.is_dir():
        raise BiberAgentClientError(f"Repair chain artifact path is not a directory: {root}")

    scanned = 0
    candidates: list[tuple[float, dict[str, Any]]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(str(path), label="repair-chain artifact")
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_summary_artifact(raw_payload)
        if normalized is None or normalized.get("ready_for_human_review") is not True:
            continue
        try:
            modified_epoch = path.stat().st_mtime
        except OSError:
            modified_epoch = 0.0
        candidates.append((modified_epoch, build_repair_chain_review_record(path, normalized)))

    candidates.sort(key=lambda item: item[0], reverse=True)
    records = [record for _, record in candidates[:limit]]
    repo_provenance_ready = sum(
        1 for record in records if repo_provenance_ok_for_eval(record)
    )
    output = write_jsonl_artifact(records, output_path)
    return {
        "source": "biber_mvp_loop_ready_repair_chain_export",
        "directory": str(root),
        "pattern": pattern,
        "scanned": scanned,
        "records": len(records),
        "repo_provenance_ready": repo_provenance_ready,
        "repo_provenance_missing": len(records) - repo_provenance_ready,
        "output": output,
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "next_review_action": "human_review_repair_chains_before_github_or_training",
    }


def review_ready_repair_chain_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(jsonl_path, label="ready repair-chain JSONL"),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repair_chain_review":
                item = dict(row)
                item["jsonl_path"] = jsonl_path
                item["jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (
            str(record.get("test_id") or ""),
            str(record.get("plan_hash") or ""),
        )
        group = groups_by_key.setdefault(
            key,
            {
                "test_id": key[0],
                "plan_hash": key[1],
                "count": 0,
                "source_artifacts": [],
                "review_statuses": [],
                "repo_provenance_ready": 0,
                "repo_provenance_missing": 0,
                "safe_to_train": False,
                "github_save_ready": False,
            },
        )
        group["count"] += 1
        group["source_artifacts"].append(record.get("source_artifact"))
        group["review_statuses"].append(record.get("review_status"))
        if repo_provenance_ok_for_eval(record):
            group["repo_provenance_ready"] += 1
        else:
            group["repo_provenance_missing"] += 1
    groups = [
        group
        for group in groups_by_key.values()
        if int(group.get("count") or 0) >= min_repeat
    ]
    groups.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("test_id") or "")))
    repo_provenance_ready = sum(
        1 for record in records if repo_provenance_ok_for_eval(record)
    )

    return {
        "source": "biber_mvp_loop_ready_repair_chain_review",
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "records": len(records),
        "rejected_records": len(rejected),
        "min_repeat": min_repeat,
        "ready_for_human_review": len(records),
        "repo_provenance_ready": repo_provenance_ready,
        "repo_provenance_missing": len(records) - repo_provenance_ready,
        "eval_approval_requires_repo_provenance": True,
        "groups": groups,
        "rejected": rejected,
        "next_review_action": (
            "human_review_repeated_repair_chains_before_github_or_training"
        ),
    }


def normalize_ready_repair_chain_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_ready_repair_chain_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_ready_repair_chain_review"
    ):
        return dict(body)
    return None


def summarize_ready_repair_chain_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "ready_for_human_review": int_count(payload.get("ready_for_human_review")),
        "repo_provenance_ready": int_count(payload.get("repo_provenance_ready")),
        "repo_provenance_missing": int_count(payload.get("repo_provenance_missing")),
        "eval_approval_requires_repo_provenance": (
            payload.get("eval_approval_requires_repo_provenance") is True
        ),
        "groups": len(groups),
        "min_repeat": max(1, int_count(payload.get("min_repeat") or 1)),
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_ready_repair_chain_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Ready repair-chain review artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Ready repair-chain review artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="ready repair-chain review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_ready_repair_chain_review_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_ready_repair_chain_review_artifact(path, normalized)
        if ready_only and int_count(summary.get("ready_for_human_review")) < 1:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_ready_repair_chain_review_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ready_artifacts": sum(
            1
            for item in artifacts
            if int_count(item.get("ready_for_human_review")) > 0
        ),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "ready_for_human_review": sum(
            int_count(item.get("ready_for_human_review")) for item in artifacts
        ),
        "repo_provenance_ready": sum(
            int_count(item.get("repo_provenance_ready")) for item in artifacts
        ),
        "repo_provenance_missing": sum(
            int_count(item.get("repo_provenance_missing")) for item in artifacts
        ),
        "eval_approval_requires_repo_provenance": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def build_ready_repair_chain_decision_record(
    *,
    record: Mapping[str, Any],
    jsonl_path: str,
    jsonl_index: int,
    decision: str,
    reviewer: str,
    notes: str,
    evidence_source_type: str,
) -> dict[str, Any]:
    if record.get("source") != "biber_mvp_loop_repair_chain_review":
        raise BiberAgentClientError(
            "record-ready-repair-chain-decision requires ready repair-chain review records."
        )
    next_action_by_decision = {
        "defer": "continue_human_review_before_github_or_training",
        "reject": "do_not_train_or_save_rejected_repair_chain",
        "approve_for_eval": "manual_eval_queue_only_no_training_or_github_save",
    }
    chain = record.get("chain")
    if not isinstance(chain, dict):
        chain = {}
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    declared_source_type = (
        evidence_source_type if evidence_source_type != "auto" else None
    )
    provenance = classify_repair_chain_evidence_source(
        record,
        declared_source_type=declared_source_type,
    )
    repo_provenance = normalize_repo_provenance(record.get("repo_provenance"))
    repo_provenance_ready = repo_provenance_ok_for_eval(record)
    decision_record = {
        "source": "biber_mvp_loop_repair_chain_decision",
        "decision_status": "recorded",
        "decision": decision,
        "review_status": f"human_{decision}",
        "reviewer": reviewer,
        "notes": notes,
        **provenance,
        "repo_provenance_ready": repo_provenance_ready,
        "eval_approval_requires_repo_provenance": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_eval": decision == "approve_for_eval",
        "approved_for_training": False,
        "auto_promoted": False,
        "auto_saved": False,
        "jsonl_path": jsonl_path,
        "jsonl_index": jsonl_index,
        "source_artifact": record.get("source_artifact"),
        "plan_hash": record.get("plan_hash"),
        "test_id": record.get("test_id"),
        "chain": dict(chain),
        "artifacts": dict(artifacts),
        "next_review_action": next_action_by_decision[decision],
    }
    if repo_provenance is not None:
        decision_record["repo_provenance"] = repo_provenance
    return decision_record


def record_ready_repair_chain_decisions(
    *,
    jsonl_paths: list[str],
    decision: str,
    reviewer: str,
    notes: str,
    evidence_source_type: str,
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    if decision not in {"defer", "reject", "approve_for_eval"}:
        raise BiberAgentClientError(
            "--decision must be one of defer, reject, or approve_for_eval."
        )
    if not reviewer.strip():
        raise BiberAgentClientError("--reviewer is required.")
    if evidence_source_type not in {"auto", "real_repo_candidate", "fixture_or_smoke"}:
        raise BiberAgentClientError(
            "--evidence-source-type must be auto, real_repo_candidate, or fixture_or_smoke."
        )
    if decision == "approve_for_eval" and evidence_source_type != "real_repo_candidate":
        raise BiberAgentClientError(
            "approve_for_eval requires --evidence-source-type real_repo_candidate."
        )
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(jsonl_path, label="ready repair-chain JSONL"),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_review":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue
            if decision == "approve_for_eval":
                declared_source_type = (
                    evidence_source_type if evidence_source_type != "auto" else None
                )
                provenance = classify_repair_chain_evidence_source(
                    row,
                    declared_source_type=declared_source_type,
                )
                if provenance.get("evidence_source_ok_for_eval") is not True:
                    reason = (
                        "non_real_repo_evidence"
                        if provenance.get("evidence_source_type") == "fixture_or_smoke"
                        else "real_repo_evidence_not_confirmed"
                    )
                    repo_provenance_ready = repo_provenance_ok_for_eval(row)
                    rejected.append(
                        {
                            "jsonl_path": jsonl_path,
                            "jsonl_index": index,
                            "reason": reason,
                            "repo_provenance_ready": repo_provenance_ready,
                            "eval_approval_requires_repo_provenance": True,
                            "evidence_source_type": provenance.get(
                                "evidence_source_type"
                            ),
                            "evidence_source_reasons": provenance.get(
                                "evidence_source_reasons"
                            ),
                        }
                    )
                    continue
            if len(records) >= limit:
                continue
            records.append(
                build_ready_repair_chain_decision_record(
                    record=row,
                    jsonl_path=jsonl_path,
                    jsonl_index=index,
                    decision=decision,
                    reviewer=reviewer.strip(),
                    notes=notes,
                    evidence_source_type=evidence_source_type,
                )
            )

    repo_provenance_ready = sum(
        1 for record in records if repo_provenance_ok_for_eval(record)
    )
    output = write_jsonl_artifact(records, output_path)
    return {
        "source": "biber_mvp_loop_ready_repair_chain_decision_export",
        "decision": decision,
        "reviewer": reviewer.strip(),
        "records": len(records),
        "rejected_records": len(rejected),
        "repo_provenance_ready": repo_provenance_ready,
        "repo_provenance_missing": len(records) - repo_provenance_ready,
        "rejected_repo_provenance_ready": sum(
            1 for record in rejected if record.get("repo_provenance_ready") is True
        ),
        "rejected_repo_provenance_missing": sum(
            1 for record in rejected if record.get("repo_provenance_ready") is False
        ),
        "eval_approval_requires_repo_provenance": True,
        "output": output,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_human_decision_recorded_without_training_or_github_save"
        ),
    }


def review_ready_repair_chain_decision_records(
    *,
    jsonl_paths: list[str],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(jsonl_path, label="ready repair-chain decision JSONL"),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repair_chain_decision":
                item = dict(row)
                item["decision_jsonl_path"] = jsonl_path
                item["decision_jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    decision_counts: dict[str, int] = {}
    groups_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    approved_for_eval_count = 0
    for record in records:
        decision = str(record.get("decision") or "missing")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        if record.get("approved_for_eval") is True or decision == "approve_for_eval":
            approved_for_eval_count += 1
        key = (
            str(record.get("test_id") or ""),
            str(record.get("plan_hash") or ""),
            decision,
        )
        group = groups_by_key.setdefault(
            key,
            {
                "test_id": key[0],
                "plan_hash": key[1],
                "decision": key[2],
                "count": 0,
                "reviewers": [],
                "source_artifacts": [],
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
        )
        group["count"] += 1
        reviewer = record.get("reviewer")
        if reviewer and reviewer not in group["reviewers"]:
            group["reviewers"].append(reviewer)
        group["source_artifacts"].append(record.get("source_artifact"))
    groups = list(groups_by_key.values())
    groups.sort(
        key=lambda item: (
            str(item.get("decision") or ""),
            -int(item.get("count") or 0),
            str(item.get("test_id") or ""),
        )
    )

    return {
        "source": "biber_mvp_loop_ready_repair_chain_decision_review",
        "review_status": "decision_summary_only",
        "records": len(records),
        "rejected_records": len(rejected),
        "decision_counts": decision_counts,
        "defer_records": decision_counts.get("defer", 0),
        "reject_records": decision_counts.get("reject", 0),
        "approved_for_eval_records": approved_for_eval_count,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "groups": groups,
        "rejected": rejected,
        "next_review_action": "human_review_decisions_before_eval_dataset_or_training",
    }


def normalize_ready_repair_chain_decision_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_ready_repair_chain_decision_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_ready_repair_chain_decision_review"
    ):
        return dict(body)
    return None


def summarize_ready_repair_chain_decision_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "defer_records": int_count(payload.get("defer_records")),
        "reject_records": int_count(payload.get("reject_records")),
        "approved_for_eval_records": int_count(
            payload.get("approved_for_eval_records")
        ),
        "groups": len(groups),
        "decision_counts": dict(decision_counts),
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_ready_repair_chain_decision_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    decision: str | None = None,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Ready repair-chain decision review artifact directory does not "
            f"exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Ready repair-chain decision review artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="ready repair-chain decision review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_ready_repair_chain_decision_review_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_ready_repair_chain_decision_review_artifact(
            path,
            normalized,
        )
        if decision:
            decision_counts = summary.get("decision_counts")
            if not isinstance(decision_counts, dict) or int_count(
                decision_counts.get(decision)
            ) < 1:
                continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_ready_repair_chain_decision_review_list",
        "directory": str(root),
        "pattern": pattern,
        "decision": decision,
        "scanned": scanned,
        "matched": len(artifacts),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "defer_records": sum(
            int_count(item.get("defer_records")) for item in artifacts
        ),
        "reject_records": sum(
            int_count(item.get("reject_records")) for item in artifacts
        ),
        "approved_for_eval_records": sum(
            int_count(item.get("approved_for_eval_records")) for item in artifacts
        ),
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def build_ready_repair_chain_eval_candidate_record(
    *,
    record: Mapping[str, Any],
    jsonl_path: str,
    jsonl_index: int,
) -> dict[str, Any]:
    if record.get("source") != "biber_mvp_loop_repair_chain_decision":
        raise BiberAgentClientError(
            "export-ready-repair-chain-eval-candidates requires decision records."
        )
    if record.get("decision") != "approve_for_eval":
        raise BiberAgentClientError(
            "export-ready-repair-chain-eval-candidates only accepts approve_for_eval decisions."
        )
    if record.get("approved_for_eval") is not True:
        raise BiberAgentClientError(
            "export-ready-repair-chain-eval-candidates requires approved_for_eval=true."
        )
    chain = record.get("chain")
    if not isinstance(chain, dict):
        chain = {}
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    provenance = classify_repair_chain_evidence_source(record)
    repo_provenance = normalize_repo_provenance(record.get("repo_provenance"))
    repo_provenance_ready = repo_provenance_ok_for_eval(record)
    candidate = {
        "source": "biber_mvp_loop_repair_chain_eval_candidate",
        "eval_candidate": True,
        "eval_status": "candidate_needs_dataset_review",
        "requires_dataset_review": True,
        "eval_dataset_ready": False,
        **provenance,
        "repo_provenance_ready": repo_provenance_ready,
        "eval_approval_requires_repo_provenance": True,
        "decision": "approve_for_eval",
        "decision_status": record.get("decision_status"),
        "reviewer": record.get("reviewer"),
        "notes": record.get("notes"),
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "auto_saved": False,
        "decision_jsonl_path": jsonl_path,
        "decision_jsonl_index": jsonl_index,
        "source_artifact": record.get("source_artifact"),
        "plan_hash": record.get("plan_hash"),
        "test_id": record.get("test_id"),
        "chain": dict(chain),
        "artifacts": dict(artifacts),
        "next_review_action": "manual_eval_dataset_review_before_training",
    }
    if repo_provenance is not None:
        candidate["repo_provenance"] = repo_provenance
    return candidate


def export_ready_repair_chain_eval_candidates(
    *,
    jsonl_paths: list[str],
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(jsonl_path, label="ready repair-chain decision JSONL"),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_decision":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue
            if (
                row.get("decision") != "approve_for_eval"
                or row.get("approved_for_eval") is not True
            ):
                skipped.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "not_approved_for_eval",
                        "decision": row.get("decision"),
                    }
                )
                continue
            provenance = classify_repair_chain_evidence_source(row)
            if provenance.get("evidence_source_ok_for_eval") is not True:
                repo_provenance_ready = repo_provenance_ok_for_eval(row)
                skip_reason = (
                    "non_real_repo_evidence"
                    if provenance.get("evidence_source_type") == "fixture_or_smoke"
                    else "real_repo_evidence_not_confirmed"
                )
                skipped.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": skip_reason,
                        "decision": row.get("decision"),
                        "repo_provenance_ready": repo_provenance_ready,
                        "eval_approval_requires_repo_provenance": True,
                        "evidence_source_type": provenance.get(
                            "evidence_source_type"
                        ),
                        "evidence_source_reasons": provenance.get(
                            "evidence_source_reasons"
                        ),
                    }
                )
                continue
            if len(records) >= limit:
                continue
            records.append(
                build_ready_repair_chain_eval_candidate_record(
                    record=row,
                    jsonl_path=jsonl_path,
                    jsonl_index=index,
                )
            )

    repo_provenance_ready = sum(
        1 for record in records if repo_provenance_ok_for_eval(record)
    )
    output = write_jsonl_artifact(records, output_path)
    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_candidate_export",
        "records": len(records),
        "skipped_records": len(skipped),
        "rejected_records": len(rejected),
        "repo_provenance_ready": repo_provenance_ready,
        "repo_provenance_missing": len(records) - repo_provenance_ready,
        "skipped_repo_provenance_ready": sum(
            1 for record in skipped if record.get("repo_provenance_ready") is True
        ),
        "skipped_repo_provenance_missing": sum(
            1 for record in skipped if record.get("repo_provenance_ready") is False
        ),
        "eval_approval_requires_repo_provenance": True,
        "blocked_non_real_repo_records": sum(
            1 for item in skipped if item.get("reason") == "non_real_repo_evidence"
        ),
        "blocked_unconfirmed_real_repo_records": sum(
            1
            for item in skipped
            if item.get("reason") == "real_repo_evidence_not_confirmed"
        ),
        "output": output,
        "eval_candidates": len(records),
        "eval_dataset_ready": False,
        "requires_dataset_review": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "skipped": skipped,
        "rejected": rejected,
        "next_review_action": "manual_eval_dataset_review_before_training",
    }


def review_ready_repair_chain_eval_candidate_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="ready repair-chain eval candidate JSONL",
            ),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repair_chain_eval_candidate":
                item = dict(row)
                item["eval_candidate_jsonl_path"] = jsonl_path
                item["eval_candidate_jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    eval_dataset_ready_records = 0
    for record in records:
        if record.get("eval_dataset_ready") is True:
            eval_dataset_ready_records += 1
        key = (
            str(record.get("test_id") or ""),
            str(record.get("plan_hash") or ""),
        )
        group = groups_by_key.setdefault(
            key,
            {
                "test_id": key[0],
                "plan_hash": key[1],
                "count": 0,
                "reviewers": [],
                "source_artifacts": [],
                "requires_dataset_review": True,
                "eval_dataset_ready": False,
                "repo_provenance_ready": 0,
                "repo_provenance_missing": 0,
                "eval_approval_requires_repo_provenance": True,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
        )
        group["count"] += 1
        reviewer = record.get("reviewer")
        if reviewer and reviewer not in group["reviewers"]:
            group["reviewers"].append(reviewer)
        group["source_artifacts"].append(record.get("source_artifact"))
        if repo_provenance_ok_for_eval(record):
            group["repo_provenance_ready"] += 1
        else:
            group["repo_provenance_missing"] += 1
    groups = [
        group
        for group in groups_by_key.values()
        if int(group.get("count") or 0) >= min_repeat
    ]
    groups.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("test_id") or "")))
    repo_provenance_ready = sum(
        1 for record in records if repo_provenance_ok_for_eval(record)
    )

    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_candidate_review",
        "review_status": "eval_candidates_need_dataset_review",
        "records": len(records),
        "rejected_records": len(rejected),
        "ready_for_dataset_review": len(records),
        "eval_dataset_ready_records": eval_dataset_ready_records,
        "repo_provenance_ready": repo_provenance_ready,
        "repo_provenance_missing": len(records) - repo_provenance_ready,
        "eval_approval_requires_repo_provenance": True,
        "min_repeat": min_repeat,
        "groups": groups,
        "requires_dataset_review": True,
        "eval_dataset_ready": False,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_dataset_review_before_training_or_eval_dataset_promotion"
        ),
    }


def normalize_ready_repair_chain_eval_candidate_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_ready_repair_chain_eval_candidate_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_ready_repair_chain_eval_candidate_review"
    ):
        return dict(body)
    return None


def summarize_ready_repair_chain_eval_candidate_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "ready_for_dataset_review": int_count(
            payload.get("ready_for_dataset_review")
        ),
        "eval_dataset_ready_records": int_count(
            payload.get("eval_dataset_ready_records")
        ),
        "repo_provenance_ready": int_count(payload.get("repo_provenance_ready")),
        "repo_provenance_missing": int_count(payload.get("repo_provenance_missing")),
        "eval_approval_requires_repo_provenance": (
            payload.get("eval_approval_requires_repo_provenance") is True
        ),
        "groups": len(groups),
        "min_repeat": int_count(payload.get("min_repeat")) or 1,
        "requires_dataset_review": payload.get("requires_dataset_review") is True,
        "eval_dataset_ready": payload.get("eval_dataset_ready") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_ready_repair_chain_eval_candidate_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Ready repair-chain eval-candidate review artifact directory does "
            f"not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            "Ready repair-chain eval-candidate review artifact path is not a "
            f"directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="ready repair-chain eval-candidate review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_ready_repair_chain_eval_candidate_review_artifact(
            raw_payload
        )
        if normalized is None:
            continue
        summary = summarize_ready_repair_chain_eval_candidate_review_artifact(
            path,
            normalized,
        )
        if ready_only and int_count(summary.get("ready_for_dataset_review")) < 1:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_candidate_review_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "ready_for_dataset_review": sum(
            int_count(item.get("ready_for_dataset_review")) for item in artifacts
        ),
        "repo_provenance_ready": sum(
            int_count(item.get("repo_provenance_ready")) for item in artifacts
        ),
        "repo_provenance_missing": sum(
            int_count(item.get("repo_provenance_missing")) for item in artifacts
        ),
        "eval_approval_requires_repo_provenance": True,
        "eval_dataset_ready": False,
        "requires_dataset_review": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def build_ready_repair_chain_eval_dataset_decision_record(
    *,
    record: Mapping[str, Any],
    jsonl_path: str,
    jsonl_index: int,
    decision: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    if record.get("source") != "biber_mvp_loop_repair_chain_eval_candidate":
        raise BiberAgentClientError(
            "record-ready-repair-chain-eval-candidate-decision requires eval candidate records."
        )
    next_action_by_decision = {
        "defer": "continue_dataset_review_before_eval_dataset_or_training",
        "reject": "do_not_use_rejected_eval_candidate",
        "approve_for_eval_dataset": (
            "manual_eval_dataset_queue_only_no_training_or_github_save"
        ),
    }
    chain = record.get("chain")
    if not isinstance(chain, dict):
        chain = {}
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    approved_for_eval_dataset = decision == "approve_for_eval_dataset"
    return {
        "source": "biber_mvp_loop_repair_chain_eval_dataset_decision",
        "decision_status": "recorded",
        "decision": decision,
        "review_status": f"human_{decision}",
        "reviewer": reviewer,
        "notes": notes,
        "eval_candidate": True,
        "approved_for_eval_dataset": approved_for_eval_dataset,
        "eval_dataset_ready": approved_for_eval_dataset,
        "requires_dataset_review": not approved_for_eval_dataset,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "auto_saved": False,
        "eval_candidate_jsonl_path": jsonl_path,
        "eval_candidate_jsonl_index": jsonl_index,
        "decision_jsonl_path": record.get("decision_jsonl_path"),
        "decision_jsonl_index": record.get("decision_jsonl_index"),
        "source_artifact": record.get("source_artifact"),
        "plan_hash": record.get("plan_hash"),
        "test_id": record.get("test_id"),
        "chain": dict(chain),
        "artifacts": dict(artifacts),
        "next_review_action": next_action_by_decision[decision],
    }


def record_ready_repair_chain_eval_candidate_decisions(
    *,
    jsonl_paths: list[str],
    decision: str,
    reviewer: str,
    notes: str,
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    valid_decisions = {"defer", "reject", "approve_for_eval_dataset"}
    if decision not in valid_decisions:
        raise BiberAgentClientError(
            "--decision must be one of defer, reject, or approve_for_eval_dataset."
        )
    if not reviewer.strip():
        raise BiberAgentClientError("--reviewer is required.")
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="ready repair-chain eval candidate JSONL",
            ),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_eval_candidate":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue
            if len(records) >= limit:
                continue
            records.append(
                build_ready_repair_chain_eval_dataset_decision_record(
                    record=row,
                    jsonl_path=jsonl_path,
                    jsonl_index=index,
                    decision=decision,
                    reviewer=reviewer.strip(),
                    notes=notes,
                )
            )

    output = write_jsonl_artifact(records, output_path)
    approved_for_eval_dataset = decision == "approve_for_eval_dataset"
    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_candidate_decision_export",
        "decision": decision,
        "reviewer": reviewer.strip(),
        "records": len(records),
        "rejected_records": len(rejected),
        "output": output,
        "approved_for_eval_dataset_records": (
            len(records) if approved_for_eval_dataset else 0
        ),
        "eval_dataset_ready": approved_for_eval_dataset and bool(records),
        "requires_dataset_review": not approved_for_eval_dataset,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_eval_dataset_decision_recorded_without_training_or_github_save"
        ),
    }


def review_ready_repair_chain_eval_dataset_decision_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="ready repair-chain eval dataset decision JSONL",
            ),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repair_chain_eval_dataset_decision":
                item = dict(row)
                item["eval_dataset_decision_jsonl_path"] = jsonl_path
                item["eval_dataset_decision_jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    decision_counts: dict[str, int] = {}
    groups_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    eval_dataset_ready_records = 0
    approved_for_eval_dataset_records = 0
    for record in records:
        decision = str(record.get("decision") or "missing")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        if record.get("eval_dataset_ready") is True:
            eval_dataset_ready_records += 1
        if (
            record.get("approved_for_eval_dataset") is True
            or decision == "approve_for_eval_dataset"
        ):
            approved_for_eval_dataset_records += 1
        key = (
            str(record.get("test_id") or ""),
            str(record.get("plan_hash") or ""),
            decision,
        )
        group = groups_by_key.setdefault(
            key,
            {
                "test_id": key[0],
                "plan_hash": key[1],
                "decision": key[2],
                "count": 0,
                "reviewers": [],
                "source_artifacts": [],
                "eval_dataset_ready": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
        )
        group["count"] += 1
        if record.get("eval_dataset_ready") is True:
            group["eval_dataset_ready"] = True
        reviewer = record.get("reviewer")
        if reviewer and reviewer not in group["reviewers"]:
            group["reviewers"].append(reviewer)
        group["source_artifacts"].append(record.get("source_artifact"))
    groups = [
        group
        for group in groups_by_key.values()
        if int(group.get("count") or 0) >= min_repeat
    ]
    groups.sort(
        key=lambda item: (
            str(item.get("decision") or ""),
            -int(item.get("count") or 0),
            str(item.get("test_id") or ""),
        )
    )

    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review",
        "review_status": "eval_dataset_decisions_need_final_dataset_export_review",
        "records": len(records),
        "rejected_records": len(rejected),
        "decision_counts": decision_counts,
        "defer_records": decision_counts.get("defer", 0),
        "reject_records": decision_counts.get("reject", 0),
        "approved_for_eval_dataset_records": approved_for_eval_dataset_records,
        "eval_dataset_ready_records": eval_dataset_ready_records,
        "min_repeat": min_repeat,
        "groups": groups,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_final_eval_dataset_export_review_before_training"
        ),
    }


def normalize_ready_repair_chain_eval_dataset_decision_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if (
        payload.get("source")
        == "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review"
    ):
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review"
    ):
        return dict(body)
    return None


def summarize_ready_repair_chain_eval_dataset_decision_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "defer_records": int_count(payload.get("defer_records")),
        "reject_records": int_count(payload.get("reject_records")),
        "approved_for_eval_dataset_records": int_count(
            payload.get("approved_for_eval_dataset_records")
        ),
        "eval_dataset_ready_records": int_count(
            payload.get("eval_dataset_ready_records")
        ),
        "groups": len(groups),
        "min_repeat": int_count(payload.get("min_repeat")) or 1,
        "decision_counts": dict(decision_counts),
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_ready_repair_chain_eval_dataset_decision_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    decision: str | None = None,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Ready repair-chain eval-dataset decision review artifact directory "
            f"does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            "Ready repair-chain eval-dataset decision review artifact path is "
            f"not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="ready repair-chain eval-dataset decision review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_ready_repair_chain_eval_dataset_decision_review_artifact(
            raw_payload
        )
        if normalized is None:
            continue
        summary = summarize_ready_repair_chain_eval_dataset_decision_review_artifact(
            path,
            normalized,
        )
        if decision:
            decision_counts = summary.get("decision_counts")
            if not isinstance(decision_counts, dict) or int_count(
                decision_counts.get(decision)
            ) < 1:
                continue
        if ready_only and int_count(summary.get("eval_dataset_ready_records")) < 1:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review_list",
        "directory": str(root),
        "pattern": pattern,
        "decision": decision,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "defer_records": sum(
            int_count(item.get("defer_records")) for item in artifacts
        ),
        "reject_records": sum(
            int_count(item.get("reject_records")) for item in artifacts
        ),
        "approved_for_eval_dataset_records": sum(
            int_count(item.get("approved_for_eval_dataset_records"))
            for item in artifacts
        ),
        "eval_dataset_ready_records": sum(
            int_count(item.get("eval_dataset_ready_records")) for item in artifacts
        ),
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def build_ready_repair_chain_eval_dataset_record(
    *,
    record: Mapping[str, Any],
    jsonl_path: str,
    jsonl_index: int,
) -> dict[str, Any]:
    if record.get("source") != "biber_mvp_loop_repair_chain_eval_dataset_decision":
        raise BiberAgentClientError(
            "export-ready-repair-chain-eval-dataset requires eval dataset decision records."
        )
    if (
        record.get("decision") != "approve_for_eval_dataset"
        or record.get("approved_for_eval_dataset") is not True
        or record.get("eval_dataset_ready") is not True
    ):
        raise BiberAgentClientError(
            "export-ready-repair-chain-eval-dataset only accepts approved eval dataset decisions."
        )
    chain = record.get("chain")
    if not isinstance(chain, dict):
        chain = {}
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    return {
        "source": "biber_mvp_loop_repair_chain_eval_dataset_record",
        "eval_dataset_record": True,
        "eval_dataset_status": "ready_for_eval_dataset_validation",
        "review_status": "eval_dataset_reviewed",
        "quality": "eval_dataset_reviewed",
        "decision": "approve_for_eval_dataset",
        "decision_status": record.get("decision_status"),
        "reviewer": record.get("reviewer"),
        "notes": record.get("notes"),
        "approved_for_eval_dataset": True,
        "eval_dataset_ready": True,
        "requires_dataset_review": False,
        "requires_eval_dataset_validation": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "auto_saved": False,
        "eval_dataset_decision_jsonl_path": jsonl_path,
        "eval_dataset_decision_jsonl_index": jsonl_index,
        "eval_candidate_jsonl_path": record.get("eval_candidate_jsonl_path"),
        "eval_candidate_jsonl_index": record.get("eval_candidate_jsonl_index"),
        "decision_jsonl_path": record.get("decision_jsonl_path"),
        "decision_jsonl_index": record.get("decision_jsonl_index"),
        "source_artifact": record.get("source_artifact"),
        "plan_hash": record.get("plan_hash"),
        "test_id": record.get("test_id"),
        "chain": dict(chain),
        "artifacts": dict(artifacts),
        "next_review_action": "validate_eval_dataset_before_training_or_model_promotion",
    }


def export_ready_repair_chain_eval_dataset(
    *,
    jsonl_paths: list[str],
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="ready repair-chain eval dataset decision JSONL",
            ),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_eval_dataset_decision":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue
            if (
                row.get("decision") != "approve_for_eval_dataset"
                or row.get("approved_for_eval_dataset") is not True
                or row.get("eval_dataset_ready") is not True
            ):
                skipped.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "not_approved_for_eval_dataset",
                        "decision": row.get("decision"),
                        "approved_for_eval_dataset": row.get(
                            "approved_for_eval_dataset"
                        ),
                        "eval_dataset_ready": row.get("eval_dataset_ready"),
                    }
                )
                continue
            if len(records) >= limit:
                continue
            records.append(
                build_ready_repair_chain_eval_dataset_record(
                    record=row,
                    jsonl_path=jsonl_path,
                    jsonl_index=index,
                )
            )

    output = write_jsonl_artifact(records, output_path)
    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_export",
        "records": len(records),
        "skipped_records": len(skipped),
        "rejected_records": len(rejected),
        "output": output,
        "eval_dataset_records": len(records),
        "eval_dataset_ready": bool(records),
        "requires_eval_dataset_validation": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "skipped": skipped,
        "rejected": rejected,
        "next_review_action": (
            "validate_eval_dataset_before_training_or_model_promotion"
        ),
    }


def validate_ready_repair_chain_eval_dataset_row(
    row: Mapping[str, Any],
) -> list[str]:
    row_errors: list[str] = []
    if row.get("eval_dataset_record") is not True:
        row_errors.append("eval_dataset_record_must_be_true")
    if row.get("eval_dataset_status") != "ready_for_eval_dataset_validation":
        row_errors.append("unexpected_eval_dataset_status")
    if row.get("approved_for_eval_dataset") is not True:
        row_errors.append("approved_for_eval_dataset_must_be_true")
    if row.get("eval_dataset_ready") is not True:
        row_errors.append("eval_dataset_ready_must_be_true")
    if row.get("requires_eval_dataset_validation") is not True:
        row_errors.append("requires_eval_dataset_validation_must_be_true")
    for key in (
        "training_allowed",
        "eligible_for_training",
        "safe_to_train",
        "github_save_ready",
        "approved_for_training",
        "auto_promoted",
        "auto_saved",
    ):
        if row.get(key) is not False:
            row_errors.append(f"{key}_must_be_false")
    for key in ("test_id", "plan_hash", "source_artifact"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            row_errors.append(f"{key}_is_required")
    if not isinstance(row.get("chain"), dict):
        row_errors.append("chain_must_be_object")
    if not isinstance(row.get("artifacts"), dict):
        row_errors.append("artifacts_must_be_object")
    return row_errors


def validate_ready_repair_chain_eval_dataset_records(
    *,
    jsonl_paths: list[str],
    min_records: int,
) -> dict[str, Any]:
    if min_records < 1:
        raise BiberAgentClientError("--min-records must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="ready repair-chain eval dataset JSONL",
            ),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_eval_dataset_record":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue

            item = dict(row)
            item["eval_dataset_jsonl_path"] = jsonl_path
            item["eval_dataset_jsonl_index"] = index
            records.append(item)

            row_errors = validate_ready_repair_chain_eval_dataset_row(row)
            if row_errors:
                errors.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "test_id": row.get("test_id"),
                        "plan_hash": row.get("plan_hash"),
                        "reasons": row_errors,
                    }
                )

    valid_records = len(records) - len(errors)
    validation_ok = valid_records >= min_records and not errors and not rejected
    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        key = (
            str(record.get("test_id") or ""),
            str(record.get("plan_hash") or ""),
        )
        group = groups_by_key.setdefault(
            key,
            {
                "test_id": key[0],
                "plan_hash": key[1],
                "count": 0,
                "source_artifacts": [],
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
        )
        group["count"] += 1
        group["source_artifacts"].append(record.get("source_artifact"))
    groups = list(groups_by_key.values())
    groups.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("test_id") or "")))

    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_validation",
        "validation_status": "valid_eval_only" if validation_ok else "invalid_or_incomplete",
        "ok": validation_ok,
        "records": len(records),
        "valid_records": valid_records,
        "invalid_records": len(errors),
        "rejected_records": len(rejected),
        "min_records": min_records,
        "groups": groups,
        "eval_dataset_ready": validation_ok,
        "requires_eval_dataset_validation": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "errors": errors,
        "rejected": rejected,
        "next_review_action": (
            "convert_validated_records_to_held_out_eval_prompts_before_training"
            if validation_ok
            else "fix_eval_dataset_records_before_eval_or_training"
        ),
    }


def normalize_ready_repair_chain_eval_dataset_validation_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_ready_repair_chain_eval_dataset_validation":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_ready_repair_chain_eval_dataset_validation"
    ):
        return dict(body)
    return None


def summarize_ready_repair_chain_eval_dataset_validation_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "validation_status": payload.get("validation_status"),
        "ok": payload.get("ok") is True,
        "records": int_count(payload.get("records")),
        "valid_records": int_count(payload.get("valid_records")),
        "invalid_records": int_count(payload.get("invalid_records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "groups": len(groups),
        "min_records": int_count(payload.get("min_records")) or 1,
        "eval_dataset_ready": payload.get("eval_dataset_ready") is True,
        "requires_eval_dataset_validation": (
            payload.get("requires_eval_dataset_validation") is True
        ),
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_ready_repair_chain_eval_dataset_validation_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ok_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Ready repair-chain eval-dataset validation artifact directory does "
            f"not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            "Ready repair-chain eval-dataset validation artifact path is not a "
            f"directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="ready repair-chain eval-dataset validation artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_ready_repair_chain_eval_dataset_validation_artifact(
            raw_payload
        )
        if normalized is None:
            continue
        summary = summarize_ready_repair_chain_eval_dataset_validation_artifact(
            path,
            normalized,
        )
        if ok_only and summary.get("ok") is not True:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_validation_list",
        "directory": str(root),
        "pattern": pattern,
        "ok_only": ok_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ok_artifacts": sum(1 for item in artifacts if item.get("ok") is True),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "valid_records": sum(
            int_count(item.get("valid_records")) for item in artifacts
        ),
        "invalid_records": sum(
            int_count(item.get("invalid_records")) for item in artifacts
        ),
        "rejected_records": sum(
            int_count(item.get("rejected_records")) for item in artifacts
        ),
        "eval_dataset_ready": any(
            item.get("eval_dataset_ready") is True for item in artifacts
        ),
        "requires_eval_dataset_validation": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def slugify_eval_prompt_id(value: object) -> str:
    cleaned = "".join(
        char.lower() if char.isalnum() else "_"
        for char in str(value or "")
    )
    parts = [part for part in cleaned.split("_") if part]
    return "_".join(parts)[:64] or "unknown"


def infer_eval_prompt_language(record: Mapping[str, Any]) -> str | None:
    test_id = str(record.get("test_id") or "").lower()
    if any(token in test_id for token in ("rust", "cargo", "xriq")):
        return "Rust"
    if any(token in test_id for token in ("dotnet", "csharp", "c#")):
        return "C#/.NET"
    if any(token in test_id for token in ("java", "maven", "gradle")):
        return "Java"
    if any(token in test_id for token in ("react", "typescript", "tsc")):
        return "TypeScript"
    if any(token in test_id for token in ("python", "pytest")):
        return "Python"
    return None


def build_repair_chain_eval_prompt_evidence(
    record: Mapping[str, Any],
) -> dict[str, Any]:
    artifacts = require_mapping(record.get("artifacts"))
    evidence: dict[str, Any] = {
        "artifact_paths": {
            key: value
            for key, value in artifacts.items()
            if isinstance(value, str) and value.strip()
        },
        "suggested_edits": [],
        "extracted_edits": [],
        "planned_edits": [],
        "applied_edits": [],
        "model_response_preview": "",
        "verification": {},
        "errors": [],
    }

    loaded: dict[str, dict[str, Any]] = {}
    for key in ("repair", "attempt", "extraction", "plan", "apply", "verification"):
        path = artifacts.get(key)
        if not isinstance(path, str) or not path.strip():
            continue
        try:
            loaded[key] = load_json_artifact(
                path.strip(),
                label=f"repair-chain {key} evidence artifact",
            )
        except BiberAgentClientError as exc:
            evidence["errors"].append(
                {
                    "artifact": key,
                    "artifact_path": path.strip(),
                    "reason": "artifact_load_failed",
                    "error": str(exc),
                }
            )

    repair = loaded.get("repair", {})
    for edit in require_list(repair.get("suggested_rule_category_edits"))[:5]:
        if not isinstance(edit, dict):
            continue
        evidence["suggested_edits"].append(
            {
                "path": edit.get("path"),
                "old_text": compact_text(edit.get("old_text"), max_chars=500),
                "new_text": compact_text(edit.get("new_text"), max_chars=500),
                "reason": edit.get("reason"),
            }
        )

    attempt = loaded.get("attempt", {})
    model_response = require_mapping(attempt.get("model_response"))
    if model_response:
        evidence["model_response_preview"] = compact_text(
            model_response.get("content"),
            max_chars=1200,
        )

    extraction = loaded.get("extraction", {})
    for edit in require_list(extraction.get("edits"))[:5]:
        if not isinstance(edit, dict):
            continue
        evidence["extracted_edits"].append(
            {
                "path": edit.get("path"),
                "old_text": compact_text(edit.get("old_text"), max_chars=500),
                "new_text": compact_text(edit.get("new_text"), max_chars=500),
                "expected_replacements": edit.get("expected_replacements"),
            }
        )

    plan = require_mapping(loaded.get("plan", {}).get("edit_plan"))
    for item in require_list(plan.get("planned"))[:5]:
        if not isinstance(item, dict):
            continue
        evidence["planned_edits"].append(
            {
                "path": item.get("path"),
                "operation": item.get("operation"),
                "replacements": item.get("replacements"),
                "risk_level": item.get("risk_level"),
                "changed": item.get("changed"),
            }
        )

    apply = require_mapping(loaded.get("apply", {}).get("edit_apply"))
    for item in require_list(apply.get("applied"))[:5]:
        if not isinstance(item, dict):
            continue
        evidence["applied_edits"].append(
            {
                "path": item.get("path"),
                "replacements": item.get("replacements"),
                "changed": item.get("changed"),
            }
        )

    verification = loaded.get("verification", {})
    test_run = require_mapping(verification.get("test_run"))
    if verification:
        evidence["verification"] = {
            "verification_status": verification.get("verification_status"),
            "ok": verification.get("ok"),
            "test_id": verification.get("test_id"),
            "test_mode": verification.get("test_mode"),
            "target_root_source": verification.get("target_root_source"),
            "test_stdout_preview": compact_text(
                test_run.get("stdout"),
                max_chars=500,
            ),
        }
    return evidence


def format_repair_chain_eval_prompt_evidence(evidence: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []

    suggested_edits = require_list(evidence.get("suggested_edits"))
    if suggested_edits:
        lines.append("Suggested source edits:")
        for edit in suggested_edits:
            if not isinstance(edit, dict):
                continue
            lines.extend(
                [
                    f"- path: {edit.get('path') or '-'}",
                    f"  old_text: {edit.get('old_text') or '-'}",
                    f"  new_text: {edit.get('new_text') or '-'}",
                    f"  reason: {edit.get('reason') or '-'}",
                ]
            )

    extracted_edits = require_list(evidence.get("extracted_edits"))
    if extracted_edits:
        lines.append("Extracted model edits:")
        for edit in extracted_edits:
            if not isinstance(edit, dict):
                continue
            lines.extend(
                [
                    f"- path: {edit.get('path') or '-'}",
                    f"  old_text: {edit.get('old_text') or '-'}",
                    f"  new_text: {edit.get('new_text') or '-'}",
                    f"  expected_replacements: {edit.get('expected_replacements')}",
                ]
            )

    planned_edits = require_list(evidence.get("planned_edits"))
    if planned_edits:
        lines.append("Plan/apply summary:")
        for item in planned_edits:
            if not isinstance(item, dict):
                continue
            lines.append(
                "- planned "
                f"{item.get('operation') or 'edit'} on {item.get('path') or '-'} "
                f"replacements={item.get('replacements')} "
                f"risk={item.get('risk_level') or '-'} "
                f"changed={item.get('changed')}"
            )
    applied_edits = require_list(evidence.get("applied_edits"))
    for item in applied_edits:
        if not isinstance(item, dict):
            continue
        lines.append(
            "- applied "
            f"{item.get('path') or '-'} replacements={item.get('replacements')} "
            f"changed={item.get('changed')}"
        )

    verification = require_mapping(evidence.get("verification"))
    if verification:
        lines.extend(
            [
                "Verification:",
                f"- status: {verification.get('verification_status')}",
                f"- ok: {verification.get('ok')}",
                f"- test_id: {verification.get('test_id')}",
                f"- test_mode: {verification.get('test_mode')}",
                f"- target_root_source: {verification.get('target_root_source')}",
            ]
        )
        stdout_preview = str(verification.get("test_stdout_preview") or "").strip()
        if stdout_preview:
            lines.append(f"- stdout_preview: {stdout_preview}")

    response_preview = str(evidence.get("model_response_preview") or "").strip()
    if response_preview:
        lines.extend(["Model response preview:", response_preview])

    errors = require_list(evidence.get("errors"))
    if errors:
        lines.append("Evidence load errors:")
        for error in errors:
            if isinstance(error, dict):
                lines.append(f"- {error.get('artifact')}: {error.get('reason')}")

    return lines or ["- no linked repair evidence loaded; use artifact paths only"]


def build_repair_chain_eval_prompt_record(
    *,
    record: Mapping[str, Any],
    jsonl_path: str,
    jsonl_index: int,
) -> dict[str, Any]:
    row_errors = validate_ready_repair_chain_eval_dataset_row(record)
    if row_errors:
        raise BiberAgentClientError(
            "export-ready-repair-chain-eval-prompts requires valid eval dataset records."
        )

    test_id = str(record.get("test_id") or "unknown")
    plan_hash = str(record.get("plan_hash") or "")
    prompt_id = (
        "repair_chain_"
        f"{slugify_eval_prompt_id(test_id)}_"
        f"{slugify_eval_prompt_id(plan_hash[:12] or jsonl_index)}"
    )
    chain = require_mapping(record.get("chain"))
    artifacts = require_mapping(record.get("artifacts"))
    artifact_lines = [
        f"- {key}: {value}"
        for key, value in sorted(artifacts.items())
        if isinstance(value, (str, int, float, bool)) or value is None
    ]
    if not artifact_lines:
        artifact_lines = ["- none"]
    evidence = build_repair_chain_eval_prompt_evidence(record)
    evidence_lines = format_repair_chain_eval_prompt_evidence(evidence)
    prompt = "\n".join(
        [
            "BIBER held-out repair-chain eval.",
            "Return a concise answer with exactly these headings: Repair, Test, Risk.",
            "Do not apply edits, save to GitHub, approve training, or mention credentials.",
            "",
            f"test_id: {test_id}",
            f"plan_hash: {plan_hash or '-'}",
            f"source_artifact: {record.get('source_artifact') or '-'}",
            "",
            "Repair-chain summary:",
            f"- chain_status: {chain.get('chain_status') or '-'}",
            f"- chain_complete: {chain.get('chain_complete')}",
            f"- verification_passed: {chain.get('verification_passed')}",
            f"- plan_hash_consistent: {chain.get('plan_hash_consistent')}",
            "",
            "Artifact paths:",
            *artifact_lines,
            "",
            "Repair evidence:",
            *evidence_lines,
            "",
            "Task:",
            (
                "Given this verified repair-chain context and repair evidence, "
                "propose the smallest safe repair plan. If an exact source edit "
                "is present, name the file and summarize that edit. Name the "
                "exact test that should be rerun. Keep the answer eval-only."
            ),
        ]
    )
    return {
        "source": "biber_mvp_loop_repair_chain_eval_prompt",
        "id": prompt_id,
        "language": infer_eval_prompt_language(record),
        "task_type": "mvp_loop_repair_eval",
        "prompt": prompt,
        "temperature": 0.0,
        "max_tokens": 320,
        "expect_contains": ["Repair", "Test", "Risk"],
        "eval_prompt_ready": True,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "eval_dataset_jsonl_path": jsonl_path,
        "eval_dataset_jsonl_index": jsonl_index,
        "source_artifact": record.get("source_artifact"),
        "plan_hash": record.get("plan_hash"),
        "test_id": record.get("test_id"),
        "evidence": evidence,
        "next_review_action": "run_held_out_eval_before_training_or_model_promotion",
    }


def export_ready_repair_chain_eval_prompts(
    *,
    jsonl_paths: list[str],
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="ready repair-chain eval dataset JSONL",
            ),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_eval_dataset_record":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue
            row_errors = validate_ready_repair_chain_eval_dataset_row(row)
            if row_errors:
                skipped.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "invalid_eval_dataset_record",
                        "reasons": row_errors,
                    }
                )
                continue
            if len(records) >= limit:
                continue
            records.append(
                build_repair_chain_eval_prompt_record(
                    record=row,
                    jsonl_path=jsonl_path,
                    jsonl_index=index,
                )
            )

    output = write_jsonl_artifact(records, output_path)
    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_prompt_export",
        "records": len(records),
        "skipped_records": len(skipped),
        "rejected_records": len(rejected),
        "output": output,
        "eval_prompts": len(records),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "skipped": skipped,
        "rejected": rejected,
        "next_review_action": "run_held_out_eval_before_training_or_model_promotion",
    }


def validate_ready_repair_chain_eval_prompt_row(
    row: Mapping[str, Any],
) -> list[str]:
    row_errors: list[str] = []
    if row.get("source") != "biber_mvp_loop_repair_chain_eval_prompt":
        row_errors.append("unexpected_source")
    if row.get("eval_prompt_ready") is not True:
        row_errors.append("eval_prompt_ready_must_be_true")
    if row.get("eval_only") is not True:
        row_errors.append("eval_only_must_be_true")
    for key in (
        "training_allowed",
        "eligible_for_training",
        "safe_to_train",
        "github_save_ready",
        "approved_for_training",
        "auto_promoted",
    ):
        if row.get(key) is not False:
            row_errors.append(f"{key}_must_be_false")
    for key in ("id", "task_type", "prompt"):
        value = row.get(key)
        if not isinstance(value, str) or not value.strip():
            row_errors.append(f"{key}_is_required")
    if not require_list(row.get("expect_contains")):
        row_errors.append("expect_contains_is_required")
    return row_errors


def inspect_ready_repair_chain_eval_prompt_records(
    *,
    jsonl_paths: list[str],
    min_records: int,
) -> dict[str, Any]:
    if min_records < 1:
        raise BiberAgentClientError("--min-records must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="ready repair-chain eval prompt JSONL",
            ),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_eval_prompt":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue

            item = dict(row)
            item["eval_prompt_jsonl_path"] = jsonl_path
            item["eval_prompt_jsonl_index"] = index
            records.append(item)

            row_errors = validate_ready_repair_chain_eval_prompt_row(row)
            if row_errors:
                errors.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "id": row.get("id"),
                        "test_id": row.get("test_id"),
                        "plan_hash": row.get("plan_hash"),
                        "reasons": row_errors,
                    }
                )

    valid_records = len(records) - len(errors)
    inspection_ok = valid_records >= min_records and not errors and not rejected
    language_counts: dict[str, int] = {}
    task_type_counts: dict[str, int] = {}
    prompt_ids: list[str] = []
    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        language = str(record.get("language") or "unknown")
        task_type = str(record.get("task_type") or "unknown")
        language_counts[language] = language_counts.get(language, 0) + 1
        task_type_counts[task_type] = task_type_counts.get(task_type, 0) + 1
        if record.get("id"):
            prompt_ids.append(str(record.get("id")))
        key = (
            str(record.get("test_id") or ""),
            str(record.get("plan_hash") or ""),
        )
        group = groups_by_key.setdefault(
            key,
            {
                "test_id": key[0],
                "plan_hash": key[1],
                "count": 0,
                "prompt_ids": [],
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
        )
        group["count"] += 1
        if record.get("id"):
            group["prompt_ids"].append(record.get("id"))
    groups = list(groups_by_key.values())
    groups.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("test_id") or "")))

    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_prompt_inspection",
        "inspection_status": "eval_prompts_ready" if inspection_ok else "eval_prompts_need_review",
        "ok": inspection_ok,
        "records": len(records),
        "valid_records": valid_records,
        "invalid_records": len(errors),
        "rejected_records": len(rejected),
        "eval_prompts": len(records),
        "eval_prompt_ready_records": sum(
            1 for record in records if record.get("eval_prompt_ready") is True
        ),
        "min_records": min_records,
        "language_counts": language_counts,
        "task_type_counts": task_type_counts,
        "prompt_ids": prompt_ids,
        "groups": groups,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "errors": errors,
        "rejected": rejected,
        "next_review_action": (
            "run_held_out_eval_before_training_or_model_promotion"
            if inspection_ok
            else "fix_eval_prompt_records_before_held_out_eval"
        ),
    }


def summarize_ready_repair_chain_eval_prompt_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "inspection_status": payload.get("inspection_status"),
        "ok": payload.get("ok") is True,
        "records": int_count(payload.get("records")),
        "valid_records": int_count(payload.get("valid_records")),
        "invalid_records": int_count(payload.get("invalid_records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "eval_prompts": int_count(payload.get("eval_prompts")),
        "eval_prompt_ready_records": int_count(
            payload.get("eval_prompt_ready_records")
        ),
        "groups": len(groups),
        "min_records": int_count(payload.get("min_records")) or 1,
        "eval_only": payload.get("eval_only") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "language_counts": require_mapping(payload.get("language_counts")),
        "task_type_counts": require_mapping(payload.get("task_type_counts")),
        "modified_epoch": modified_epoch,
    }
    return summary


def list_ready_repair_chain_eval_prompt_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Ready repair-chain eval prompt directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Ready repair-chain eval prompt path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            inspection = inspect_ready_repair_chain_eval_prompt_records(
                jsonl_paths=[str(path)],
                min_records=1,
            )
        except BiberAgentClientError:
            continue
        summary = summarize_ready_repair_chain_eval_prompt_artifact(
            path,
            inspection,
        )
        if ready_only and summary.get("ok") is not True:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_ready_repair_chain_eval_prompt_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ok_artifacts": sum(1 for item in artifacts if item.get("ok") is True),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "valid_records": sum(
            int_count(item.get("valid_records")) for item in artifacts
        ),
        "invalid_records": sum(
            int_count(item.get("invalid_records")) for item in artifacts
        ),
        "rejected_records": sum(
            int_count(item.get("rejected_records")) for item in artifacts
        ),
        "eval_prompts": sum(
            int_count(item.get("eval_prompts")) for item in artifacts
        ),
        "eval_prompt_ready_records": sum(
            int_count(item.get("eval_prompt_ready_records")) for item in artifacts
        ),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def is_repair_chain_heldout_eval_result(row: Mapping[str, Any]) -> bool:
    prompt_id = str(row.get("id") or "")
    return prompt_id.startswith("repair_chain_")


def summarize_repair_chain_heldout_eval_result(
    *,
    row: Mapping[str, Any],
    jsonl_path: str,
    jsonl_index: int,
) -> dict[str, Any]:
    matched = [str(item) for item in require_list(row.get("matched_expectations"))]
    missing = [str(item) for item in require_list(row.get("missing_expectations"))]
    validation_ok = row.get("validation_ok")
    passed = (
        row.get("ok") is True
        and row.get("expectation_ok") is True
        and validation_ok is not False
        and not row.get("error")
    )
    return {
        "id": str(row.get("id") or ""),
        "jsonl_path": jsonl_path,
        "jsonl_index": jsonl_index,
        "passed": passed,
        "ok": row.get("ok") is True,
        "expectation_ok": row.get("expectation_ok") is True,
        "validation_ok": validation_ok,
        "validation_skipped": row.get("validation_skipped") is True,
        "model": row.get("model"),
        "latency_seconds": row.get("latency_seconds"),
        "matched_expectations": matched,
        "missing_expectations": missing,
        "error": row.get("error"),
        "content_preview": compact_text(row.get("content"), max_chars=400),
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
    }


def review_repair_chain_heldout_eval_results(
    *,
    jsonl_paths: list[str],
    min_passes: int,
    summary_path: str | None,
) -> dict[str, Any]:
    if min_passes < 1:
        raise BiberAgentClientError("--min-passes must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="repair-chain held-out eval result JSONL",
            ),
            start=1,
        ):
            if not is_repair_chain_heldout_eval_result(row):
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_eval_result_id",
                        "id": row.get("id"),
                        "source": row.get("source"),
                    }
                )
                continue
            records.append(
                summarize_repair_chain_heldout_eval_result(
                    row=row,
                    jsonl_path=jsonl_path,
                    jsonl_index=index,
                )
            )

    passed_records = sum(1 for record in records if record.get("passed") is True)
    failed_records = len(records) - passed_records
    expectation_failed_records = sum(
        1 for record in records if record.get("expectation_ok") is not True
    )
    validation_failed_records = sum(
        1 for record in records if record.get("validation_ok") is False
    )
    error_records = sum(1 for record in records if record.get("error"))
    model_counts: dict[str, int] = {}
    for record in records:
        model = str(record.get("model") or "unknown")
        model_counts[model] = model_counts.get(model, 0) + 1
    records.sort(
        key=lambda item: (
            item.get("passed") is True,
            str(item.get("id") or ""),
            int(item.get("jsonl_index") or 0),
        )
    )

    summary = load_json_artifact(
        summary_path,
        label="repair-chain held-out eval summary",
    ) if summary_path else {}
    review_ok = (
        passed_records >= min_passes
        and failed_records == 0
        and len(rejected) == 0
    )
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_eval_review",
        "review_status": (
            "heldout_eval_passed" if review_ok else "heldout_eval_needs_review"
        ),
        "ok": review_ok,
        "records": len(records),
        "passed_records": passed_records,
        "failed_records": failed_records,
        "expectation_failed_records": expectation_failed_records,
        "validation_failed_records": validation_failed_records,
        "error_records": error_records,
        "rejected_records": len(rejected),
        "min_passes": min_passes,
        "model_counts": model_counts,
        "summary_path": summary_path,
        "summary_prompts": summary.get("prompts"),
        "summary_ok": summary.get("ok"),
        "summary_failed": summary.get("failed"),
        "summary_expectation_ok": summary.get("expectation_ok"),
        "summary_expectation_failed": summary.get("expectation_failed"),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "results": records,
        "rejected": rejected,
        "next_review_action": (
            "manual_review_heldout_eval_before_training_or_model_promotion"
        ),
    }


def normalize_repair_chain_heldout_eval_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_chain_heldout_eval_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_repair_chain_heldout_eval_review"
    ):
        normalized = dict(body)
        if payload.get("output") and not normalized.get("artifact_path"):
            normalized["artifact_path"] = payload.get("output")
        return normalized
    return None


def summarize_repair_chain_heldout_eval_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    results = [
        item
        for item in require_list(payload.get("results"))
        if isinstance(item, dict)
    ]
    result_ids = [
        str(item.get("id"))
        for item in results
        if item.get("id")
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "ok": payload.get("ok") is True,
        "records": int_count(payload.get("records")),
        "passed_records": int_count(payload.get("passed_records")),
        "failed_records": int_count(payload.get("failed_records")),
        "expectation_failed_records": int_count(
            payload.get("expectation_failed_records")
        ),
        "validation_failed_records": int_count(
            payload.get("validation_failed_records")
        ),
        "error_records": int_count(payload.get("error_records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "min_passes": int_count(payload.get("min_passes")) or 1,
        "result_count": len(results),
        "result_ids": result_ids,
        "model_counts": require_mapping(payload.get("model_counts")),
        "summary_path": payload.get("summary_path"),
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "eval_only": payload.get("eval_only") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_chain_heldout_eval_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ok_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Repair-chain held-out eval review artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Repair-chain held-out eval review artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    model_counts: dict[str, int] = {}
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair-chain held-out eval review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_heldout_eval_review_artifact(raw_payload)
        if normalized is None:
            continue
        if not normalized.get("artifact_path"):
            normalized["artifact_path"] = str(path)
        summary = summarize_repair_chain_heldout_eval_review_artifact(
            path,
            normalized,
        )
        if ok_only and summary.get("ok") is not True:
            continue
        for model, count in require_mapping(summary.get("model_counts")).items():
            model_key = str(model)
            model_counts[model_key] = model_counts.get(model_key, 0) + int_count(count)
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_eval_review_list",
        "directory": str(root),
        "pattern": pattern,
        "ok_only": ok_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ok_artifacts": sum(1 for item in artifacts if item.get("ok") is True),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "passed_records": sum(
            int_count(item.get("passed_records")) for item in artifacts
        ),
        "failed_records": sum(
            int_count(item.get("failed_records")) for item in artifacts
        ),
        "expectation_failed_records": sum(
            int_count(item.get("expectation_failed_records")) for item in artifacts
        ),
        "validation_failed_records": sum(
            int_count(item.get("validation_failed_records")) for item in artifacts
        ),
        "error_records": sum(
            int_count(item.get("error_records")) for item in artifacts
        ),
        "rejected_records": sum(
            int_count(item.get("rejected_records")) for item in artifacts
        ),
        "model_counts": model_counts,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def build_repair_chain_heldout_eval_decision_record(
    *,
    review: Mapping[str, Any],
    artifact_path: str,
    decision: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    if review.get("source") != "biber_mvp_loop_repair_chain_heldout_eval_review":
        raise BiberAgentClientError(
            "record-repair-chain-heldout-eval-decision requires held-out eval review artifacts."
        )
    accepted_for_baseline = decision == "accept_for_baseline"
    review_ok = review.get("ok") is True
    result_ids = [
        str(item.get("id"))
        for item in require_list(review.get("results"))
        if isinstance(item, dict) and item.get("id")
    ]
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_eval_decision",
        "decision_status": "recorded",
        "decision": decision,
        "review_status": f"human_{decision}",
        "reviewer": reviewer,
        "notes": notes,
        "accepted_for_baseline": accepted_for_baseline and review_ok,
        "baseline_candidate_ready": accepted_for_baseline and review_ok,
        "requires_follow_up": not (accepted_for_baseline and review_ok),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "heldout_eval_review_artifact": artifact_path,
        "heldout_eval_review_status": review.get("review_status"),
        "heldout_eval_review_ok": review_ok,
        "heldout_eval_records": review.get("records"),
        "heldout_eval_passed_records": review.get("passed_records"),
        "heldout_eval_failed_records": review.get("failed_records"),
        "heldout_eval_expectation_failed_records": review.get(
            "expectation_failed_records"
        ),
        "heldout_eval_rejected_records": review.get("rejected_records"),
        "heldout_eval_model_counts": require_mapping(review.get("model_counts")),
        "heldout_eval_summary_path": review.get("summary_path"),
        "heldout_eval_result_jsonl_paths": require_list(review.get("jsonl_paths")),
        "heldout_eval_result_ids": result_ids,
        "next_review_action": (
            "manual_baseline_review_before_training_or_model_promotion"
            if accepted_for_baseline and review_ok
            else "continue_heldout_eval_review_before_training_or_model_promotion"
        ),
    }


def record_repair_chain_heldout_eval_decisions(
    *,
    artifact_paths: list[str],
    decision: str,
    reviewer: str,
    notes: str,
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    valid_decisions = {"defer", "reject", "accept_for_baseline"}
    if decision not in valid_decisions:
        raise BiberAgentClientError(
            "--decision must be one of defer, reject, or accept_for_baseline."
        )
    if not reviewer.strip():
        raise BiberAgentClientError("--reviewer is required.")
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for artifact_path in artifact_paths:
        review = load_json_artifact(
            artifact_path,
            label="repair-chain held-out eval review artifact",
        )
        if review.get("source") != "biber_mvp_loop_repair_chain_heldout_eval_review":
            rejected.append(
                {
                    "artifact_path": artifact_path,
                    "reason": "unsupported_source",
                    "source": review.get("source"),
                }
            )
            continue
        if len(records) >= limit:
            continue
        records.append(
            build_repair_chain_heldout_eval_decision_record(
                review=review,
                artifact_path=artifact_path,
                decision=decision,
                reviewer=reviewer.strip(),
                notes=notes,
            )
        )

    output = write_jsonl_artifact(records, output_path)
    accepted_for_baseline_records = sum(
        1 for record in records if record.get("accepted_for_baseline") is True
    )
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_eval_decision_export",
        "decision": decision,
        "reviewer": reviewer.strip(),
        "records": len(records),
        "rejected_records": len(rejected),
        "output": output,
        "accepted_for_baseline_records": accepted_for_baseline_records,
        "baseline_candidate_ready": accepted_for_baseline_records > 0,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifact_paths": list(artifact_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_heldout_eval_decision_recorded_without_training_or_github_save"
        ),
    }


def review_repair_chain_heldout_eval_decision_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="repair-chain held-out eval decision JSONL",
            ),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repair_chain_heldout_eval_decision":
                item = dict(row)
                item["heldout_eval_decision_jsonl_path"] = jsonl_path
                item["heldout_eval_decision_jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    decision_counts: dict[str, int] = {}
    baseline_candidate_ready_records = 0
    accepted_for_baseline_records = 0
    follow_up_records = 0
    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        decision = str(record.get("decision") or "missing")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        if record.get("baseline_candidate_ready") is True:
            baseline_candidate_ready_records += 1
        if record.get("accepted_for_baseline") is True:
            accepted_for_baseline_records += 1
        if record.get("requires_follow_up") is True:
            follow_up_records += 1
        result_ids = [
            str(item)
            for item in require_list(record.get("heldout_eval_result_ids"))
            if item
        ]
        group_id = ",".join(result_ids) or str(record.get("heldout_eval_review_artifact") or "")
        key = (decision, group_id)
        group = groups_by_key.setdefault(
            key,
            {
                "decision": key[0],
                "heldout_eval_result_ids": result_ids,
                "heldout_eval_review_artifacts": [],
                "count": 0,
                "reviewers": [],
                "accepted_for_baseline": False,
                "baseline_candidate_ready": False,
                "requires_follow_up": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
        )
        group["count"] += 1
        if record.get("accepted_for_baseline") is True:
            group["accepted_for_baseline"] = True
        if record.get("baseline_candidate_ready") is True:
            group["baseline_candidate_ready"] = True
        if record.get("requires_follow_up") is True:
            group["requires_follow_up"] = True
        reviewer = record.get("reviewer")
        if reviewer and reviewer not in group["reviewers"]:
            group["reviewers"].append(reviewer)
        artifact = record.get("heldout_eval_review_artifact")
        if artifact and artifact not in group["heldout_eval_review_artifacts"]:
            group["heldout_eval_review_artifacts"].append(artifact)

    groups = [
        group
        for group in groups_by_key.values()
        if int(group.get("count") or 0) >= min_repeat
    ]
    groups.sort(
        key=lambda item: (
            str(item.get("decision") or ""),
            -int(item.get("count") or 0),
            ",".join(str(value) for value in require_list(item.get("heldout_eval_result_ids"))),
        )
    )

    return {
        "source": "biber_mvp_loop_repair_chain_heldout_eval_decision_review",
        "review_status": "heldout_eval_decision_summary_only",
        "records": len(records),
        "rejected_records": len(rejected),
        "decision_counts": decision_counts,
        "defer_records": decision_counts.get("defer", 0),
        "reject_records": decision_counts.get("reject", 0),
        "accepted_for_baseline_records": accepted_for_baseline_records,
        "baseline_candidate_ready_records": baseline_candidate_ready_records,
        "follow_up_records": follow_up_records,
        "min_repeat": min_repeat,
        "groups": groups,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_baseline_review_or_more_heldout_eval_before_training"
        ),
    }


def normalize_repair_chain_heldout_eval_decision_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if (
        payload.get("source")
        == "biber_mvp_loop_repair_chain_heldout_eval_decision_review"
    ):
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_repair_chain_heldout_eval_decision_review"
    ):
        normalized = dict(body)
        if payload.get("output") and not normalized.get("artifact_path"):
            normalized["artifact_path"] = payload.get("output")
        return normalized
    return None


def summarize_repair_chain_heldout_eval_decision_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "defer_records": int_count(payload.get("defer_records")),
        "reject_records": int_count(payload.get("reject_records")),
        "accepted_for_baseline_records": int_count(
            payload.get("accepted_for_baseline_records")
        ),
        "baseline_candidate_ready_records": int_count(
            payload.get("baseline_candidate_ready_records")
        ),
        "follow_up_records": int_count(payload.get("follow_up_records")),
        "groups": len(groups),
        "min_repeat": int_count(payload.get("min_repeat")) or 1,
        "decision_counts": dict(decision_counts),
        "eval_only": payload.get("eval_only") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_chain_heldout_eval_decision_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    decision: str | None = None,
    baseline_ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Repair-chain held-out eval decision review artifact directory "
            f"does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            "Repair-chain held-out eval decision review artifact path is not a "
            f"directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair-chain held-out eval decision review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_heldout_eval_decision_review_artifact(
            raw_payload
        )
        if normalized is None:
            continue
        summary = summarize_repair_chain_heldout_eval_decision_review_artifact(
            path,
            normalized,
        )
        if decision:
            decision_counts = summary.get("decision_counts")
            if not isinstance(decision_counts, dict) or int_count(
                decision_counts.get(decision)
            ) < 1:
                continue
        if baseline_ready_only and int_count(
            summary.get("baseline_candidate_ready_records")
        ) < 1:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_eval_decision_review_list",
        "directory": str(root),
        "pattern": pattern,
        "decision": decision,
        "baseline_ready_only": baseline_ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "defer_records": sum(
            int_count(item.get("defer_records")) for item in artifacts
        ),
        "reject_records": sum(
            int_count(item.get("reject_records")) for item in artifacts
        ),
        "accepted_for_baseline_records": sum(
            int_count(item.get("accepted_for_baseline_records"))
            for item in artifacts
        ),
        "baseline_candidate_ready_records": sum(
            int_count(item.get("baseline_candidate_ready_records"))
            for item in artifacts
        ),
        "follow_up_records": sum(
            int_count(item.get("follow_up_records")) for item in artifacts
        ),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def build_repair_chain_heldout_baseline_candidate_record(
    *,
    record: Mapping[str, Any],
    jsonl_path: str,
    jsonl_index: int,
) -> dict[str, Any]:
    if record.get("source") != "biber_mvp_loop_repair_chain_heldout_eval_decision":
        raise BiberAgentClientError(
            "export-repair-chain-heldout-baseline-candidates requires held-out eval decision records."
        )
    if (
        record.get("decision") != "accept_for_baseline"
        or record.get("accepted_for_baseline") is not True
        or record.get("baseline_candidate_ready") is not True
    ):
        raise BiberAgentClientError(
            "export-repair-chain-heldout-baseline-candidates only accepts baseline-approved held-out eval decisions."
        )
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_candidate",
        "heldout_baseline_candidate": True,
        "baseline_candidate_status": "candidate_needs_manual_baseline_review",
        "decision": "accept_for_baseline",
        "decision_status": record.get("decision_status"),
        "review_status": record.get("review_status"),
        "reviewer": record.get("reviewer"),
        "notes": record.get("notes"),
        "accepted_for_baseline": True,
        "baseline_candidate_ready": True,
        "baseline_ready": False,
        "requires_baseline_review": True,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "auto_saved": False,
        "heldout_eval_decision_jsonl_path": jsonl_path,
        "heldout_eval_decision_jsonl_index": jsonl_index,
        "heldout_eval_review_artifact": record.get("heldout_eval_review_artifact"),
        "heldout_eval_review_status": record.get("heldout_eval_review_status"),
        "heldout_eval_review_ok": record.get("heldout_eval_review_ok"),
        "heldout_eval_records": record.get("heldout_eval_records"),
        "heldout_eval_passed_records": record.get("heldout_eval_passed_records"),
        "heldout_eval_failed_records": record.get("heldout_eval_failed_records"),
        "heldout_eval_expectation_failed_records": record.get(
            "heldout_eval_expectation_failed_records"
        ),
        "heldout_eval_rejected_records": record.get("heldout_eval_rejected_records"),
        "heldout_eval_model_counts": require_mapping(
            record.get("heldout_eval_model_counts")
        ),
        "heldout_eval_summary_path": record.get("heldout_eval_summary_path"),
        "heldout_eval_result_jsonl_paths": require_list(
            record.get("heldout_eval_result_jsonl_paths")
        ),
        "heldout_eval_result_ids": require_list(record.get("heldout_eval_result_ids")),
        "next_review_action": (
            "manual_baseline_comparison_before_training_or_model_promotion"
        ),
    }


def export_repair_chain_heldout_baseline_candidates(
    *,
    jsonl_paths: list[str],
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="repair-chain held-out eval decision JSONL",
            ),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_heldout_eval_decision":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue
            if (
                row.get("decision") != "accept_for_baseline"
                or row.get("accepted_for_baseline") is not True
                or row.get("baseline_candidate_ready") is not True
            ):
                skipped.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "not_accepted_for_baseline",
                        "decision": row.get("decision"),
                        "accepted_for_baseline": row.get("accepted_for_baseline"),
                        "baseline_candidate_ready": row.get(
                            "baseline_candidate_ready"
                        ),
                    }
                )
                continue
            if len(records) >= limit:
                continue
            records.append(
                build_repair_chain_heldout_baseline_candidate_record(
                    record=row,
                    jsonl_path=jsonl_path,
                    jsonl_index=index,
                )
            )

    output = write_jsonl_artifact(records, output_path)
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_candidate_export",
        "records": len(records),
        "skipped_records": len(skipped),
        "rejected_records": len(rejected),
        "output": output,
        "baseline_candidates": len(records),
        "accepted_for_baseline_records": len(records),
        "baseline_candidate_ready": len(records) > 0,
        "baseline_ready": False,
        "requires_baseline_review": len(records) > 0,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "skipped": skipped,
        "rejected": rejected,
        "next_review_action": "manual_baseline_review_before_training",
    }


def review_repair_chain_heldout_baseline_candidate_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="repair-chain held-out baseline candidate JSONL",
            ),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repair_chain_heldout_baseline_candidate":
                item = dict(row)
                item["heldout_baseline_candidate_jsonl_path"] = jsonl_path
                item["heldout_baseline_candidate_jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    decision_counts: dict[str, int] = {}
    baseline_candidate_ready_records = 0
    baseline_ready_records = 0
    requires_baseline_review_records = 0
    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        decision = str(record.get("decision") or "missing")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        if record.get("baseline_candidate_ready") is True:
            baseline_candidate_ready_records += 1
        if record.get("baseline_ready") is True:
            baseline_ready_records += 1
        if record.get("requires_baseline_review") is True:
            requires_baseline_review_records += 1
        result_ids = [
            str(item)
            for item in require_list(record.get("heldout_eval_result_ids"))
            if item
        ]
        group_id = ",".join(result_ids) or str(record.get("heldout_eval_review_artifact") or "")
        key = (decision, group_id)
        group = groups_by_key.setdefault(
            key,
            {
                "decision": key[0],
                "heldout_eval_result_ids": result_ids,
                "heldout_eval_review_artifacts": [],
                "count": 0,
                "reviewers": [],
                "baseline_candidate_ready": False,
                "baseline_ready": False,
                "requires_baseline_review": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
        )
        group["count"] += 1
        if record.get("baseline_candidate_ready") is True:
            group["baseline_candidate_ready"] = True
        if record.get("baseline_ready") is True:
            group["baseline_ready"] = True
        if record.get("requires_baseline_review") is True:
            group["requires_baseline_review"] = True
        reviewer = record.get("reviewer")
        if reviewer and reviewer not in group["reviewers"]:
            group["reviewers"].append(reviewer)
        artifact = record.get("heldout_eval_review_artifact")
        if artifact and artifact not in group["heldout_eval_review_artifacts"]:
            group["heldout_eval_review_artifacts"].append(artifact)

    groups = [
        group
        for group in groups_by_key.values()
        if int(group.get("count") or 0) >= min_repeat
    ]
    groups.sort(
        key=lambda item: (
            str(item.get("decision") or ""),
            -int(item.get("count") or 0),
            ",".join(str(value) for value in require_list(item.get("heldout_eval_result_ids"))),
        )
    )

    return {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_candidate_review",
        "review_status": "heldout_baseline_candidate_summary_only",
        "records": len(records),
        "rejected_records": len(rejected),
        "baseline_candidates": len(records),
        "decision_counts": decision_counts,
        "accepted_for_baseline_records": decision_counts.get("accept_for_baseline", 0),
        "baseline_candidate_ready_records": baseline_candidate_ready_records,
        "baseline_ready_records": baseline_ready_records,
        "requires_baseline_review_records": requires_baseline_review_records,
        "min_repeat": min_repeat,
        "groups": groups,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_baseline_comparison_before_training_or_model_promotion"
        ),
    }


def normalize_repair_chain_heldout_baseline_candidate_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if (
        payload.get("source")
        == "biber_mvp_loop_repair_chain_heldout_baseline_candidate_review"
    ):
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_repair_chain_heldout_baseline_candidate_review"
    ):
        normalized = dict(body)
        if payload.get("output") and not normalized.get("artifact_path"):
            normalized["artifact_path"] = payload.get("output")
        return normalized
    return None


def summarize_repair_chain_heldout_baseline_candidate_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "baseline_candidates": int_count(payload.get("baseline_candidates")),
        "accepted_for_baseline_records": int_count(
            payload.get("accepted_for_baseline_records")
        ),
        "baseline_candidate_ready_records": int_count(
            payload.get("baseline_candidate_ready_records")
        ),
        "baseline_ready_records": int_count(payload.get("baseline_ready_records")),
        "requires_baseline_review_records": int_count(
            payload.get("requires_baseline_review_records")
        ),
        "groups": len(groups),
        "min_repeat": int_count(payload.get("min_repeat")) or 1,
        "decision_counts": dict(decision_counts),
        "eval_only": payload.get("eval_only") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_chain_heldout_baseline_candidate_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    candidate_ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Repair-chain held-out baseline candidate review artifact directory "
            f"does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            "Repair-chain held-out baseline candidate review artifact path is "
            f"not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair-chain held-out baseline candidate review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_heldout_baseline_candidate_review_artifact(
            raw_payload
        )
        if normalized is None:
            continue
        summary = summarize_repair_chain_heldout_baseline_candidate_review_artifact(
            path,
            normalized,
        )
        if candidate_ready_only and int_count(
            summary.get("baseline_candidate_ready_records")
        ) < 1:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_candidate_review_list",
        "directory": str(root),
        "pattern": pattern,
        "candidate_ready_only": candidate_ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "rejected_records": sum(
            int_count(item.get("rejected_records")) for item in artifacts
        ),
        "baseline_candidates": sum(
            int_count(item.get("baseline_candidates")) for item in artifacts
        ),
        "accepted_for_baseline_records": sum(
            int_count(item.get("accepted_for_baseline_records"))
            for item in artifacts
        ),
        "baseline_candidate_ready_records": sum(
            int_count(item.get("baseline_candidate_ready_records"))
            for item in artifacts
        ),
        "baseline_ready_records": sum(
            int_count(item.get("baseline_ready_records")) for item in artifacts
        ),
        "requires_baseline_review_records": sum(
            int_count(item.get("requires_baseline_review_records"))
            for item in artifacts
        ),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def build_repair_chain_heldout_baseline_decision_record(
    *,
    record: Mapping[str, Any],
    jsonl_path: str,
    jsonl_index: int,
    decision: str,
    reviewer: str,
    notes: str,
) -> dict[str, Any]:
    if record.get("source") != "biber_mvp_loop_repair_chain_heldout_baseline_candidate":
        raise BiberAgentClientError(
            "record-repair-chain-heldout-baseline-candidate-decision requires held-out baseline candidate records."
        )
    approved_as_baseline = decision == "approve_as_baseline"
    next_action_by_decision = {
        "defer": "continue_baseline_candidate_review_before_training",
        "reject": "do_not_use_rejected_baseline_candidate",
        "approve_as_baseline": (
            "manual_training_dataset_review_before_training_or_model_promotion"
        ),
    }
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision",
        "decision_status": "recorded",
        "decision": decision,
        "review_status": f"human_{decision}",
        "reviewer": reviewer,
        "notes": notes,
        "heldout_baseline_candidate": True,
        "approved_as_baseline": approved_as_baseline,
        "baseline_candidate_ready": record.get("baseline_candidate_ready") is True,
        "baseline_ready": approved_as_baseline,
        "requires_baseline_review": not approved_as_baseline,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "auto_saved": False,
        "heldout_baseline_candidate_jsonl_path": jsonl_path,
        "heldout_baseline_candidate_jsonl_index": jsonl_index,
        "heldout_eval_decision_jsonl_path": record.get(
            "heldout_eval_decision_jsonl_path"
        ),
        "heldout_eval_decision_jsonl_index": record.get(
            "heldout_eval_decision_jsonl_index"
        ),
        "heldout_eval_review_artifact": record.get("heldout_eval_review_artifact"),
        "heldout_eval_review_status": record.get("heldout_eval_review_status"),
        "heldout_eval_review_ok": record.get("heldout_eval_review_ok"),
        "heldout_eval_records": record.get("heldout_eval_records"),
        "heldout_eval_passed_records": record.get("heldout_eval_passed_records"),
        "heldout_eval_failed_records": record.get("heldout_eval_failed_records"),
        "heldout_eval_expectation_failed_records": record.get(
            "heldout_eval_expectation_failed_records"
        ),
        "heldout_eval_rejected_records": record.get("heldout_eval_rejected_records"),
        "heldout_eval_model_counts": require_mapping(
            record.get("heldout_eval_model_counts")
        ),
        "heldout_eval_summary_path": record.get("heldout_eval_summary_path"),
        "heldout_eval_result_jsonl_paths": require_list(
            record.get("heldout_eval_result_jsonl_paths")
        ),
        "heldout_eval_result_ids": require_list(record.get("heldout_eval_result_ids")),
        "next_review_action": next_action_by_decision[decision],
    }


def record_repair_chain_heldout_baseline_candidate_decisions(
    *,
    jsonl_paths: list[str],
    decision: str,
    reviewer: str,
    notes: str,
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    valid_decisions = {"defer", "reject", "approve_as_baseline"}
    if decision not in valid_decisions:
        raise BiberAgentClientError(
            "--decision must be one of defer, reject, or approve_as_baseline."
        )
    if not reviewer.strip():
        raise BiberAgentClientError("--reviewer is required.")
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="repair-chain held-out baseline candidate JSONL",
            ),
            start=1,
        ):
            if row.get("source") != "biber_mvp_loop_repair_chain_heldout_baseline_candidate":
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )
                continue
            if len(records) >= limit:
                continue
            records.append(
                build_repair_chain_heldout_baseline_decision_record(
                    record=row,
                    jsonl_path=jsonl_path,
                    jsonl_index=index,
                    decision=decision,
                    reviewer=reviewer.strip(),
                    notes=notes,
                )
            )

    output = write_jsonl_artifact(records, output_path)
    approved_as_baseline = decision == "approve_as_baseline"
    approved_as_baseline_records = len(records) if approved_as_baseline else 0
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision_export",
        "decision": decision,
        "reviewer": reviewer.strip(),
        "records": len(records),
        "rejected_records": len(rejected),
        "output": output,
        "approved_as_baseline_records": approved_as_baseline_records,
        "baseline_ready": approved_as_baseline and bool(records),
        "requires_baseline_review": not approved_as_baseline,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_baseline_decision_recorded_without_training_or_github_save"
        ),
    }


def review_repair_chain_heldout_baseline_decision_records(
    *,
    jsonl_paths: list[str],
    min_repeat: int,
) -> dict[str, Any]:
    if min_repeat < 1:
        raise BiberAgentClientError("--min-repeat must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="repair-chain held-out baseline decision JSONL",
            ),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repair_chain_heldout_baseline_decision":
                item = dict(row)
                item["heldout_baseline_decision_jsonl_path"] = jsonl_path
                item["heldout_baseline_decision_jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    decision_counts: dict[str, int] = {}
    approved_as_baseline_records = 0
    baseline_candidate_ready_records = 0
    baseline_ready_records = 0
    requires_baseline_review_records = 0
    groups_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        decision = str(record.get("decision") or "missing")
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        if record.get("approved_as_baseline") is True:
            approved_as_baseline_records += 1
        if record.get("baseline_candidate_ready") is True:
            baseline_candidate_ready_records += 1
        if record.get("baseline_ready") is True:
            baseline_ready_records += 1
        if record.get("requires_baseline_review") is True:
            requires_baseline_review_records += 1
        result_ids = [
            str(item)
            for item in require_list(record.get("heldout_eval_result_ids"))
            if item
        ]
        group_id = ",".join(result_ids) or str(record.get("heldout_eval_review_artifact") or "")
        key = (decision, group_id)
        group = groups_by_key.setdefault(
            key,
            {
                "decision": key[0],
                "heldout_eval_result_ids": result_ids,
                "heldout_eval_review_artifacts": [],
                "count": 0,
                "reviewers": [],
                "approved_as_baseline": False,
                "baseline_candidate_ready": False,
                "baseline_ready": False,
                "requires_baseline_review": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
        )
        group["count"] += 1
        if record.get("approved_as_baseline") is True:
            group["approved_as_baseline"] = True
        if record.get("baseline_candidate_ready") is True:
            group["baseline_candidate_ready"] = True
        if record.get("baseline_ready") is True:
            group["baseline_ready"] = True
        if record.get("requires_baseline_review") is True:
            group["requires_baseline_review"] = True
        reviewer = record.get("reviewer")
        if reviewer and reviewer not in group["reviewers"]:
            group["reviewers"].append(reviewer)
        artifact = record.get("heldout_eval_review_artifact")
        if artifact and artifact not in group["heldout_eval_review_artifacts"]:
            group["heldout_eval_review_artifacts"].append(artifact)

    groups = [
        group
        for group in groups_by_key.values()
        if int(group.get("count") or 0) >= min_repeat
    ]
    groups.sort(
        key=lambda item: (
            str(item.get("decision") or ""),
            -int(item.get("count") or 0),
            ",".join(str(value) for value in require_list(item.get("heldout_eval_result_ids"))),
        )
    )

    return {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision_review",
        "review_status": "heldout_baseline_decision_summary_only",
        "records": len(records),
        "rejected_records": len(rejected),
        "decision_counts": decision_counts,
        "defer_records": decision_counts.get("defer", 0),
        "reject_records": decision_counts.get("reject", 0),
        "approved_as_baseline_records": approved_as_baseline_records,
        "baseline_candidate_ready_records": baseline_candidate_ready_records,
        "baseline_ready_records": baseline_ready_records,
        "requires_baseline_review_records": requires_baseline_review_records,
        "min_repeat": min_repeat,
        "groups": groups,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "rejected": rejected,
        "next_review_action": (
            "manual_training_dataset_review_before_training_or_model_promotion"
        ),
    }


def normalize_repair_chain_heldout_baseline_decision_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if (
        payload.get("source")
        == "biber_mvp_loop_repair_chain_heldout_baseline_decision_review"
    ):
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_repair_chain_heldout_baseline_decision_review"
    ):
        normalized = dict(body)
        if payload.get("output") and not normalized.get("artifact_path"):
            normalized["artifact_path"] = payload.get("output")
        return normalized
    return None


def summarize_repair_chain_heldout_baseline_decision_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "defer_records": int_count(payload.get("defer_records")),
        "reject_records": int_count(payload.get("reject_records")),
        "approved_as_baseline_records": int_count(
            payload.get("approved_as_baseline_records")
        ),
        "baseline_candidate_ready_records": int_count(
            payload.get("baseline_candidate_ready_records")
        ),
        "baseline_ready_records": int_count(payload.get("baseline_ready_records")),
        "requires_baseline_review_records": int_count(
            payload.get("requires_baseline_review_records")
        ),
        "groups": len(groups),
        "min_repeat": int_count(payload.get("min_repeat")) or 1,
        "decision_counts": dict(decision_counts),
        "eval_only": payload.get("eval_only") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": [
            str(item)
            for item in require_list(payload.get("jsonl_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_chain_heldout_baseline_decision_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    decision: str | None = None,
    baseline_ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Repair-chain held-out baseline decision review artifact directory "
            f"does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            "Repair-chain held-out baseline decision review artifact path is "
            f"not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair-chain held-out baseline decision review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_heldout_baseline_decision_review_artifact(
            raw_payload
        )
        if normalized is None:
            continue
        summary = summarize_repair_chain_heldout_baseline_decision_review_artifact(
            path,
            normalized,
        )
        if decision:
            decision_counts = summary.get("decision_counts")
            if not isinstance(decision_counts, dict) or int_count(
                decision_counts.get(decision)
            ) < 1:
                continue
        if baseline_ready_only and int_count(
            summary.get("baseline_ready_records")
        ) < 1:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision_review_list",
        "directory": str(root),
        "pattern": pattern,
        "decision": decision,
        "baseline_ready_only": baseline_ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "rejected_records": sum(
            int_count(item.get("rejected_records")) for item in artifacts
        ),
        "defer_records": sum(
            int_count(item.get("defer_records")) for item in artifacts
        ),
        "reject_records": sum(
            int_count(item.get("reject_records")) for item in artifacts
        ),
        "approved_as_baseline_records": sum(
            int_count(item.get("approved_as_baseline_records"))
            for item in artifacts
        ),
        "baseline_candidate_ready_records": sum(
            int_count(item.get("baseline_candidate_ready_records"))
            for item in artifacts
        ),
        "baseline_ready_records": sum(
            int_count(item.get("baseline_ready_records")) for item in artifacts
        ),
        "requires_baseline_review_records": sum(
            int_count(item.get("requires_baseline_review_records"))
            for item in artifacts
        ),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def review_repair_chain_training_readiness(
    *,
    review_paths: list[str],
    min_baseline_ready: int,
) -> dict[str, Any]:
    if min_baseline_ready < 1:
        raise BiberAgentClientError("--min-baseline-ready must be at least 1.")

    supported_reviews: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    unsafe_review_flags: list[dict[str, Any]] = []
    baseline_ready_groups: list[dict[str, Any]] = []
    totals = {
        "records": 0,
        "approved_as_baseline_records": 0,
        "baseline_candidate_ready_records": 0,
        "baseline_ready_records": 0,
        "requires_baseline_review_records": 0,
    }
    for review_path in review_paths:
        artifact = load_json_artifact(
            review_path,
            label="repair-chain held-out baseline decision review artifact",
        )
        if (
            artifact.get("source")
            != "biber_mvp_loop_repair_chain_heldout_baseline_decision_review"
        ):
            rejected.append(
                {
                    "artifact_path": review_path,
                    "reason": "unsupported_source",
                    "source": artifact.get("source"),
                }
            )
            continue

        flagged = [
            flag
            for flag in (
                "training_allowed",
                "safe_to_train",
                "github_save_ready",
                "approved_for_training",
                "auto_promoted",
            )
            if artifact.get(flag) is True
        ]
        if flagged:
            unsafe_review_flags.append(
                {
                    "artifact_path": review_path,
                    "flags": flagged,
                }
            )

        supported_reviews.append(
            {
                "artifact_path": review_path,
                "records": int(artifact.get("records") or 0),
                "approved_as_baseline_records": int(
                    artifact.get("approved_as_baseline_records") or 0
                ),
                "baseline_candidate_ready_records": int(
                    artifact.get("baseline_candidate_ready_records") or 0
                ),
                "baseline_ready_records": int(
                    artifact.get("baseline_ready_records") or 0
                ),
                "requires_baseline_review_records": int(
                    artifact.get("requires_baseline_review_records") or 0
                ),
                "decision_counts": require_mapping(artifact.get("decision_counts")),
                "groups": len(require_list(artifact.get("groups"))),
                "review_status": artifact.get("review_status"),
            }
        )
        for key in totals:
            totals[key] += int(artifact.get(key) or 0)
        for group in require_list(artifact.get("groups")):
            if not isinstance(group, dict) or group.get("baseline_ready") is not True:
                continue
            baseline_ready_groups.append(
                {
                    "artifact_path": review_path,
                    "decision": group.get("decision"),
                    "count": int(group.get("count") or 0),
                    "heldout_eval_result_ids": require_list(
                        group.get("heldout_eval_result_ids")
                    ),
                    "reviewers": require_list(group.get("reviewers")),
                }
            )

    hard_blockers: list[str] = []
    if not supported_reviews:
        hard_blockers.append("no_supported_baseline_decision_reviews")
    if rejected:
        hard_blockers.append("unsupported_review_artifacts_present")
    if unsafe_review_flags:
        hard_blockers.append("input_review_has_training_or_promotion_flag")
    if totals["baseline_ready_records"] <= 0:
        hard_blockers.append("no_baseline_ready_records")
    elif totals["baseline_ready_records"] < min_baseline_ready:
        hard_blockers.append("below_min_baseline_ready_records")

    ready_for_manual_training_dataset_review = not hard_blockers
    review_status = (
        "baseline_ready_manual_training_review_required"
        if ready_for_manual_training_dataset_review
        else "training_blocked"
    )
    training_gate_status = (
        "manual_review_required"
        if ready_for_manual_training_dataset_review
        else "blocked"
    )

    return {
        "source": "biber_mvp_loop_repair_chain_training_readiness_review",
        "review_status": review_status,
        "training_gate_status": training_gate_status,
        "review_artifacts": len(review_paths),
        "supported_review_artifacts": len(supported_reviews),
        "rejected_artifacts": len(rejected),
        "min_baseline_ready": min_baseline_ready,
        "records": totals["records"],
        "approved_as_baseline_records": totals["approved_as_baseline_records"],
        "baseline_candidate_ready_records": totals[
            "baseline_candidate_ready_records"
        ],
        "baseline_ready_records": totals["baseline_ready_records"],
        "requires_baseline_review_records": totals[
            "requires_baseline_review_records"
        ],
        "baseline_ready_groups": baseline_ready_groups,
        "hard_blockers": hard_blockers,
        "required_manual_actions": [
            "human_training_dataset_review",
            "explicit_user_approval_before_any_training_job",
            "separate_vast_gpu_training_run_outside_codex_loop",
        ],
        "ready_for_manual_training_dataset_review": (
            ready_for_manual_training_dataset_review
        ),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "review_paths": list(review_paths),
        "reviews": supported_reviews,
        "rejected": rejected,
        "unsafe_review_flags": unsafe_review_flags,
        "next_review_action": (
            "manual_training_dataset_review_required_before_training"
            if ready_for_manual_training_dataset_review
            else "collect_baseline_ready_decision_reviews_before_training"
        ),
    }


def normalize_repair_chain_training_readiness_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_chain_training_readiness_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source") == "biber_mvp_loop_repair_chain_training_readiness_review"
    ):
        normalized = dict(body)
        if payload.get("output") and not normalized.get("artifact_path"):
            normalized["artifact_path"] = payload.get("output")
        return normalized
    return None


def summarize_repair_chain_training_readiness_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    hard_blockers = [
        str(item)
        for item in require_list(payload.get("hard_blockers"))
        if item
    ]
    ready_groups = [
        item
        for item in require_list(payload.get("baseline_ready_groups"))
        if isinstance(item, dict)
    ]
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "training_gate_status": payload.get("training_gate_status"),
        "review_artifacts": int_count(payload.get("review_artifacts")),
        "supported_review_artifacts": int_count(
            payload.get("supported_review_artifacts")
        ),
        "rejected_artifacts": int_count(payload.get("rejected_artifacts")),
        "min_baseline_ready": int_count(payload.get("min_baseline_ready")) or 1,
        "records": int_count(payload.get("records")),
        "approved_as_baseline_records": int_count(
            payload.get("approved_as_baseline_records")
        ),
        "baseline_candidate_ready_records": int_count(
            payload.get("baseline_candidate_ready_records")
        ),
        "baseline_ready_records": int_count(payload.get("baseline_ready_records")),
        "requires_baseline_review_records": int_count(
            payload.get("requires_baseline_review_records")
        ),
        "baseline_ready_groups": len(ready_groups),
        "hard_blockers": hard_blockers,
        "ready_for_manual_training_dataset_review": (
            payload.get("ready_for_manual_training_dataset_review") is True
        ),
        "eval_only": payload.get("eval_only") is True,
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "review_paths": [
            str(item)
            for item in require_list(payload.get("review_paths"))
            if isinstance(item, str)
        ],
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_chain_training_readiness_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Repair-chain training readiness artifact directory does not exist: "
            f"{root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            "Repair-chain training readiness artifact path is not a directory: "
            f"{root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair-chain training readiness artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_training_readiness_artifact(raw_payload)
        if normalized is None:
            continue
        summary = summarize_repair_chain_training_readiness_artifact(
            path,
            normalized,
        )
        if ready_only and summary.get("ready_for_manual_training_dataset_review") is not True:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_repair_chain_training_readiness_review_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "review_artifacts": sum(
            int_count(item.get("review_artifacts")) for item in artifacts
        ),
        "supported_review_artifacts": sum(
            int_count(item.get("supported_review_artifacts"))
            for item in artifacts
        ),
        "rejected_artifacts": sum(
            int_count(item.get("rejected_artifacts")) for item in artifacts
        ),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "approved_as_baseline_records": sum(
            int_count(item.get("approved_as_baseline_records"))
            for item in artifacts
        ),
        "baseline_candidate_ready_records": sum(
            int_count(item.get("baseline_candidate_ready_records"))
            for item in artifacts
        ),
        "baseline_ready_records": sum(
            int_count(item.get("baseline_ready_records")) for item in artifacts
        ),
        "requires_baseline_review_records": sum(
            int_count(item.get("requires_baseline_review_records"))
            for item in artifacts
        ),
        "ready_for_manual_training_dataset_review_records": sum(
            1
            for item in artifacts
            if item.get("ready_for_manual_training_dataset_review") is True
        ),
        "blocked_records": sum(
            1
            for item in artifacts
            if item.get("training_gate_status") == "blocked"
        ),
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def build_repair_chain_training_candidate_record(
    *,
    readiness_path: str,
    readiness: Mapping[str, Any],
    group: Mapping[str, Any],
    group_index: int,
) -> dict[str, Any]:
    result_ids = [
        str(item)
        for item in require_list(group.get("heldout_eval_result_ids"))
        if item
    ]
    reviewers = [
        str(item)
        for item in require_list(group.get("reviewers"))
        if item
    ]
    group_json = json.dumps(group, indent=2, sort_keys=True)
    evidence = build_repair_chain_training_candidate_evidence(group)
    evidence_json = json.dumps(evidence, indent=2, sort_keys=True)
    return {
        "instruction": (
            "Review this BIBER repair-chain baseline evidence and write a "
            "verified training answer only if it improves repo-specific coding "
            "behavior without leaking private code or secrets."
        ),
        "input": (
            "This is a BIBER repair-chain training candidate review item, not "
            "a training record yet.\n"
            f"readiness_artifact: {readiness_path}\n"
            f"training_gate_status: {readiness.get('training_gate_status')}\n"
            f"baseline_ready_records: {readiness.get('baseline_ready_records', 0)}\n"
            f"group_index: {group_index}\n"
            f"decision: {group.get('decision')}\n"
            f"count: {group.get('count', 0)}\n"
            f"heldout_eval_result_ids: {', '.join(result_ids) or 'none'}\n"
            f"reviewers: {', '.join(reviewers) or 'none'}\n\n"
            "Baseline-ready group JSON:\n"
            f"{group_json}\n\n"
            "Evidence summary for human review:\n"
            f"{evidence_json}"
        ),
        "output": "",
        "category": "repo_adaptation",
        "stack": ["repo_adaptation", "biber_repair_chain"],
        "quality": "needs_review",
        "source": "biber_mvp_loop_repair_chain_training_candidate",
        "training_candidate_status": "needs_human_training_dataset_review",
        "review_required": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "metadata": {
            "source": "biber_mvp_loop_repair_chain_training_candidate",
            "readiness_artifact": readiness_path,
            "group_index": group_index,
            "decision": group.get("decision"),
            "count": int(group.get("count") or 0),
            "heldout_eval_result_ids": result_ids,
            "reviewers": reviewers,
            "evidence_artifacts": evidence.get("artifact_paths", {}),
            "review_required": True,
            "promotion_rule": (
                "Fill output with a verified answer, remove unsafe content, "
                "change quality to reviewed or verified, validate the dataset, "
                "and get explicit user approval before any Vast training job."
            ),
        },
        "evidence": evidence,
    }


def build_repair_chain_training_candidate_evidence(
    group: Mapping[str, Any],
) -> dict[str, Any]:
    result_ids = [
        str(item)
        for item in require_list(group.get("heldout_eval_result_ids"))
        if item
    ]
    baseline_decision_review_path = str(group.get("artifact_path") or "").strip()
    evidence: dict[str, Any] = {
        "artifact_paths": {
            "baseline_decision_review": baseline_decision_review_path or None,
            "heldout_eval_reviews": [],
            "heldout_eval_results": [],
        },
        "heldout_eval_result_ids": result_ids,
        "baseline_decision_review": None,
        "heldout_eval_reviews": [],
        "errors": [],
    }
    heldout_eval_review_paths: list[str] = []
    if baseline_decision_review_path:
        try:
            baseline_review = load_json_artifact(
                baseline_decision_review_path,
                label="baseline decision review evidence",
            )
            evidence["baseline_decision_review"] = {
                "artifact_path": baseline_decision_review_path,
                "source": baseline_review.get("source"),
                "review_status": baseline_review.get("review_status"),
                "records": baseline_review.get("records"),
                "decision_counts": baseline_review.get("decision_counts"),
                "baseline_ready_records": baseline_review.get(
                    "baseline_ready_records"
                ),
                "training_allowed": baseline_review.get("training_allowed"),
                "safe_to_train": baseline_review.get("safe_to_train"),
            }
            for review_group in require_list(baseline_review.get("groups")):
                if not isinstance(review_group, dict):
                    continue
                for path in require_list(
                    review_group.get("heldout_eval_review_artifacts")
                ):
                    if isinstance(path, str) and path.strip():
                        heldout_eval_review_paths.append(path.strip())
        except BiberAgentClientError as exc:
            evidence["errors"].append(
                {
                    "artifact_path": baseline_decision_review_path,
                    "reason": "baseline_decision_review_load_failed",
                    "error": str(exc),
                }
            )

    seen_heldout_paths: set[str] = set()
    for heldout_path in heldout_eval_review_paths:
        if heldout_path in seen_heldout_paths:
            continue
        seen_heldout_paths.add(heldout_path)
        evidence["artifact_paths"]["heldout_eval_reviews"].append(heldout_path)
        try:
            heldout_review = load_json_artifact(
                heldout_path,
                label="held-out eval review evidence",
            )
        except BiberAgentClientError as exc:
            evidence["errors"].append(
                {
                    "artifact_path": heldout_path,
                    "reason": "heldout_eval_review_load_failed",
                    "error": str(exc),
                }
            )
            continue
        heldout_summary: dict[str, Any] = {
            "artifact_path": heldout_path,
            "source": heldout_review.get("source"),
            "review_status": heldout_review.get("review_status"),
            "ok": heldout_review.get("ok"),
            "records": heldout_review.get("records"),
            "passed_records": heldout_review.get("passed_records"),
            "failed_records": heldout_review.get("failed_records"),
            "expectation_failed_records": heldout_review.get(
                "expectation_failed_records"
            ),
            "model_counts": heldout_review.get("model_counts"),
            "training_allowed": heldout_review.get("training_allowed"),
            "safe_to_train": heldout_review.get("safe_to_train"),
            "results": [],
        }
        for result in require_list(heldout_review.get("results"))[:5]:
            if not isinstance(result, dict):
                continue
            result_id = str(result.get("id") or "")
            result_jsonl_path = str(result.get("jsonl_path") or "").strip()
            if result_jsonl_path:
                evidence["artifact_paths"]["heldout_eval_results"].append(
                    result_jsonl_path
                )
            heldout_summary["results"].append(
                {
                    "id": result_id,
                    "ok": result.get("ok"),
                    "passed": result.get("passed"),
                    "expectation_ok": result.get("expectation_ok"),
                    "model": result.get("model"),
                    "jsonl_path": result_jsonl_path or None,
                    "content_preview": compact_text(
                        result.get("content_preview"),
                        max_chars=800,
                    ),
                }
            )
        evidence["heldout_eval_reviews"].append(heldout_summary)
    evidence["artifact_paths"]["heldout_eval_results"] = sorted(
        set(evidence["artifact_paths"]["heldout_eval_results"])
    )
    return evidence


def export_repair_chain_training_candidates(
    *,
    readiness_paths: list[str],
    output_path: str,
    limit: int,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")

    records: list[dict[str, Any]] = []
    supported: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    blockers: list[str] = []
    for readiness_path in readiness_paths:
        readiness = load_json_artifact(
            readiness_path,
            label="repair-chain training readiness artifact",
        )
        if (
            readiness.get("source")
            != "biber_mvp_loop_repair_chain_training_readiness_review"
        ):
            rejected.append(
                {
                    "artifact_path": readiness_path,
                    "reason": "unsupported_source",
                    "source": readiness.get("source"),
                }
            )
            blockers.append("unsupported_readiness_artifacts_present")
            continue

        readiness_blockers = [
            str(item)
            for item in require_list(readiness.get("hard_blockers"))
            if item
        ]
        supported.append(
            {
                "artifact_path": readiness_path,
                "training_gate_status": readiness.get("training_gate_status"),
                "ready_for_manual_training_dataset_review": readiness.get(
                    "ready_for_manual_training_dataset_review"
                )
                is True,
                "baseline_ready_records": int(
                    readiness.get("baseline_ready_records") or 0
                ),
                "hard_blockers": readiness_blockers,
            }
        )
        if (
            readiness.get("ready_for_manual_training_dataset_review") is not True
            or readiness.get("training_gate_status") != "manual_review_required"
            or readiness_blockers
        ):
            skipped.append(
                {
                    "artifact_path": readiness_path,
                    "reason": "training_readiness_blocked",
                    "training_gate_status": readiness.get("training_gate_status"),
                    "hard_blockers": readiness_blockers,
                }
            )
            blockers.extend(readiness_blockers or ["training_readiness_blocked"])
            continue

        for group_index, group in enumerate(
            require_list(readiness.get("baseline_ready_groups")),
            start=1,
        ):
            if len(records) >= limit:
                break
            if not isinstance(group, dict):
                continue
            records.append(
                build_repair_chain_training_candidate_record(
                    readiness_path=readiness_path,
                    readiness=readiness,
                    group=group,
                    group_index=group_index,
                )
            )

    output = write_jsonl_artifact(records, output_path)
    unique_blockers = sorted({blocker for blocker in blockers if blocker})
    export_status = (
        "training_candidates_need_human_review"
        if records
        else "training_candidates_blocked"
    )
    return {
        "source": "biber_mvp_loop_repair_chain_training_candidate_export",
        "export_status": export_status,
        "records": len(records),
        "training_candidate_records": len(records),
        "review_artifacts": len(readiness_paths),
        "supported_review_artifacts": len(supported),
        "rejected_artifacts": len(rejected),
        "skipped_artifacts": len(skipped),
        "output": output,
        "quality": "needs_review" if records else None,
        "training_dataset_ready": False,
        "requires_human_training_dataset_review": bool(records),
        "manual_review_required": bool(records),
        "eval_only": False,
        "review_queue_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "readiness_paths": list(readiness_paths),
        "supported": supported,
        "skipped": skipped,
        "rejected": rejected,
        "hard_blockers": unique_blockers,
        "next_review_action": (
            "fill_reviewed_training_candidate_outputs_before_validation_or_training"
            if records
            else "collect_baseline_ready_decision_reviews_before_training"
        ),
    }


def review_repair_chain_training_candidate_records(
    *,
    jsonl_paths: list[str],
    min_ready: int,
) -> dict[str, Any]:
    if min_ready < 1:
        raise BiberAgentClientError("--min-ready must be at least 1.")

    records: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for jsonl_path in jsonl_paths:
        for index, row in enumerate(
            load_jsonl_artifact(
                jsonl_path,
                label="repair-chain training candidate JSONL",
            ),
            start=1,
        ):
            if row.get("source") == "biber_mvp_loop_repair_chain_training_candidate":
                item = dict(row)
                item["training_candidate_jsonl_path"] = jsonl_path
                item["training_candidate_jsonl_index"] = index
                records.append(item)
            else:
                rejected.append(
                    {
                        "jsonl_path": jsonl_path,
                        "jsonl_index": index,
                        "reason": "unsupported_source",
                        "source": row.get("source"),
                    }
                )

    reviewed_records: list[dict[str, Any]] = []
    pending_review_records: list[dict[str, Any]] = []
    empty_output_records = 0
    unreviewed_quality_records = 0
    quality_counts: dict[str, int] = {}
    for record in records:
        quality = str(record.get("quality") or "missing")
        quality_counts[quality] = quality_counts.get(quality, 0) + 1
        output_ready = bool(str(record.get("output") or "").strip())
        quality_ready = quality in {"reviewed", "verified"}
        if not output_ready:
            empty_output_records += 1
        if not quality_ready:
            unreviewed_quality_records += 1
        summary = {
            "jsonl_path": record.get("training_candidate_jsonl_path"),
            "jsonl_index": record.get("training_candidate_jsonl_index"),
            "quality": quality,
            "output_ready": output_ready,
            "quality_ready": quality_ready,
            "review_required": record.get("review_required") is True,
            "metadata": require_mapping(record.get("metadata")),
        }
        if output_ready and quality_ready:
            reviewed_records.append(summary)
        else:
            pending_review_records.append(summary)

    hard_blockers: list[str] = []
    if not records:
        hard_blockers.append("no_training_candidate_records")
    if rejected:
        hard_blockers.append("unsupported_candidate_records_present")
    if empty_output_records:
        hard_blockers.append("candidate_outputs_missing")
    if unreviewed_quality_records:
        hard_blockers.append("candidate_quality_not_reviewed")
    if len(reviewed_records) < min_ready:
        hard_blockers.append("below_min_ready_records")

    ready_for_dataset_validation = not hard_blockers
    review_status = (
        "training_candidates_ready_for_dataset_validation"
        if ready_for_dataset_validation
        else "training_candidates_need_review"
    )
    return {
        "source": "biber_mvp_loop_repair_chain_training_candidate_review",
        "review_status": review_status,
        "records": len(records),
        "rejected_records": len(rejected),
        "pending_review_records": len(pending_review_records),
        "reviewed_records": len(reviewed_records),
        "empty_output_records": empty_output_records,
        "unreviewed_quality_records": unreviewed_quality_records,
        "quality_counts": quality_counts,
        "min_ready": min_ready,
        "ready_for_dataset_validation": ready_for_dataset_validation,
        "training_dataset_ready": False,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": list(jsonl_paths),
        "ready_records": reviewed_records,
        "pending_review": pending_review_records,
        "rejected": rejected,
        "hard_blockers": hard_blockers,
        "next_review_action": (
            "validate_reviewed_training_dataset_before_training"
            if ready_for_dataset_validation
            else "fill_candidate_outputs_and_mark_quality_reviewed_or_verified"
        ),
    }


def normalize_repair_chain_training_candidate_review_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_chain_training_candidate_review":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_repair_chain_training_candidate_review"
    ):
        normalized = dict(body)
        if payload.get("output") and not normalized.get("artifact_path"):
            normalized["artifact_path"] = payload.get("output")
        return normalized
    return None


def summarize_repair_chain_training_candidate_review_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    hard_blockers = [
        str(item)
        for item in require_list(payload.get("hard_blockers"))
        if item
    ]
    jsonl_paths = [
        str(item)
        for item in require_list(payload.get("jsonl_paths"))
        if isinstance(item, str)
    ]
    summary: dict[str, Any] = {
        "path": str(path),
        "review_status": payload.get("review_status"),
        "records": int_count(payload.get("records")),
        "rejected_records": int_count(payload.get("rejected_records")),
        "pending_review_records": int_count(
            payload.get("pending_review_records")
        ),
        "reviewed_records": int_count(payload.get("reviewed_records")),
        "empty_output_records": int_count(payload.get("empty_output_records")),
        "unreviewed_quality_records": int_count(
            payload.get("unreviewed_quality_records")
        ),
        "min_ready": int_count(payload.get("min_ready")) or 1,
        "ready_for_dataset_validation": (
            payload.get("ready_for_dataset_validation") is True
        ),
        "training_dataset_ready": payload.get("training_dataset_ready") is True,
        "hard_blockers": hard_blockers,
        "training_allowed": payload.get("training_allowed") is True,
        "eligible_for_training": payload.get("eligible_for_training") is True,
        "safe_to_train": payload.get("safe_to_train") is True,
        "github_save_ready": payload.get("github_save_ready") is True,
        "approved_for_training": payload.get("approved_for_training") is True,
        "auto_promoted": payload.get("auto_promoted") is True,
        "jsonl_paths": jsonl_paths,
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_chain_training_candidate_review_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            "Repair-chain training candidate review artifact directory does "
            f"not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            "Repair-chain training candidate review artifact path is not a "
            f"directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair-chain training candidate review artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_training_candidate_review_artifact(
            raw_payload
        )
        if normalized is None:
            continue
        summary = summarize_repair_chain_training_candidate_review_artifact(
            path,
            normalized,
        )
        if ready_only and summary.get("ready_for_dataset_validation") is not True:
            continue
        artifacts.append(summary)

    artifacts.sort(
        key=lambda item: float(item.get("modified_epoch") or 0.0),
        reverse=True,
    )
    return {
        "source": "biber_mvp_loop_repair_chain_training_candidate_review_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "records": sum(int_count(item.get("records")) for item in artifacts),
        "rejected_records": sum(
            int_count(item.get("rejected_records")) for item in artifacts
        ),
        "pending_review_records": sum(
            int_count(item.get("pending_review_records")) for item in artifacts
        ),
        "reviewed_records": sum(
            int_count(item.get("reviewed_records")) for item in artifacts
        ),
        "empty_output_records": sum(
            int_count(item.get("empty_output_records")) for item in artifacts
        ),
        "unreviewed_quality_records": sum(
            int_count(item.get("unreviewed_quality_records"))
            for item in artifacts
        ),
        "ready_for_dataset_validation_records": sum(
            1
            for item in artifacts
            if item.get("ready_for_dataset_validation") is True
        ),
        "blocked_records": sum(
            1
            for item in artifacts
            if item.get("ready_for_dataset_validation") is not True
        ),
        "training_dataset_ready": False,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifacts": artifacts[:limit],
    }


def load_optional_training_pipeline_json(
    path: Path,
    *,
    label: str,
    expected_source: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    check: dict[str, Any] = {
        "id": label,
        "path": str(path),
        "present": path.exists(),
        "ok": False,
    }
    if not path.exists():
        check["reason"] = "missing"
        return None, check
    try:
        artifact = load_json_artifact(str(path), label=label)
    except BiberAgentClientError as exc:
        check["reason"] = "invalid_json"
        check["error"] = str(exc)
        return None, check
    source = artifact.get("source")
    check["source"] = source
    if source != expected_source:
        check["reason"] = "unsupported_source"
        return artifact, check
    check["ok"] = True
    return artifact, check


def load_optional_training_pipeline_jsonl(
    path: Path,
    *,
    label: str,
    expected_source: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    check: dict[str, Any] = {
        "id": label,
        "path": str(path),
        "present": path.exists(),
        "ok": False,
        "records": 0,
        "rejected_records": 0,
    }
    if not path.exists():
        check["reason"] = "missing"
        return [], check
    try:
        rows = load_jsonl_artifact(str(path), label=label)
    except BiberAgentClientError as exc:
        check["reason"] = "invalid_jsonl"
        check["error"] = str(exc)
        return [], check
    rejected = [
        {
            "jsonl_index": index,
            "source": row.get("source"),
            "reason": "unsupported_source",
        }
        for index, row in enumerate(rows, start=1)
        if row.get("source") != expected_source
    ]
    check["records"] = len(rows)
    check["rejected_records"] = len(rejected)
    if rejected:
        check["reason"] = "unsupported_source"
        check["rejected"] = rejected[:8]
        return rows, check
    check["ok"] = True
    return rows, check


def review_repair_chain_training_pipeline_status(
    *,
    artifact_dir: str,
) -> dict[str, Any]:
    root = Path(artifact_dir)
    artifact_paths = {
        "heldout_baseline_decision_review": root
        / "agent-client-mvp-loop-repair-chain-heldout-baseline-decision-review.json",
        "training_readiness": root
        / "agent-client-mvp-loop-repair-chain-training-readiness.json",
        "training_candidates": root
        / "agent-client-mvp-loop-repair-chain-training-candidates.jsonl",
        "training_candidate_review": root
        / "agent-client-mvp-loop-repair-chain-training-candidate-review.json",
    }

    baseline_review, baseline_check = load_optional_training_pipeline_json(
        artifact_paths["heldout_baseline_decision_review"],
        label="heldout_baseline_decision_review",
        expected_source=(
            "biber_mvp_loop_repair_chain_heldout_baseline_decision_review"
        ),
    )
    readiness, readiness_check = load_optional_training_pipeline_json(
        artifact_paths["training_readiness"],
        label="training_readiness",
        expected_source="biber_mvp_loop_repair_chain_training_readiness_review",
    )
    _candidate_rows, candidates_check = load_optional_training_pipeline_jsonl(
        artifact_paths["training_candidates"],
        label="training_candidates",
        expected_source="biber_mvp_loop_repair_chain_training_candidate",
    )
    candidate_review, candidate_review_check = load_optional_training_pipeline_json(
        artifact_paths["training_candidate_review"],
        label="training_candidate_review",
        expected_source="biber_mvp_loop_repair_chain_training_candidate_review",
    )

    baseline_ready_records = (
        int(baseline_review.get("baseline_ready_records") or 0)
        if baseline_review and baseline_check.get("ok") is True
        else 0
    )
    readiness_baseline_ready_records = (
        int(readiness.get("baseline_ready_records") or 0)
        if readiness and readiness_check.get("ok") is True
        else 0
    )
    readiness_hard_blockers = (
        [
            str(item)
            for item in require_list(readiness.get("hard_blockers"))
            if item
        ]
        if readiness and readiness_check.get("ok") is True
        else []
    )
    candidate_review_hard_blockers = (
        [
            str(item)
            for item in require_list(candidate_review.get("hard_blockers"))
            if item
        ]
        if candidate_review and candidate_review_check.get("ok") is True
        else []
    )
    candidate_review_records = (
        int(candidate_review.get("records") or 0)
        if candidate_review and candidate_review_check.get("ok") is True
        else 0
    )
    ready_for_dataset_validation = (
        bool(candidate_review.get("ready_for_dataset_validation"))
        if candidate_review and candidate_review_check.get("ok") is True
        else False
    )

    checks = [
        {
            **baseline_check,
            "baseline_ready_records": baseline_ready_records,
        },
        {
            **readiness_check,
            "training_gate_status": (
                readiness.get("training_gate_status")
                if readiness and readiness_check.get("ok") is True
                else None
            ),
            "ready_for_manual_training_dataset_review": (
                readiness.get("ready_for_manual_training_dataset_review") is True
                if readiness and readiness_check.get("ok") is True
                else False
            ),
            "baseline_ready_records": readiness_baseline_ready_records,
            "hard_blockers": readiness_hard_blockers,
        },
        candidates_check,
        {
            **candidate_review_check,
            "records": candidate_review_records,
            "ready_for_dataset_validation": ready_for_dataset_validation,
            "hard_blockers": candidate_review_hard_blockers,
        },
    ]

    hard_blockers: list[str] = []
    if baseline_check.get("ok") is not True:
        hard_blockers.append("missing_or_invalid_baseline_decision_review")
    if readiness_check.get("ok") is not True:
        hard_blockers.append("missing_or_invalid_training_readiness")
    if candidates_check.get("ok") is not True:
        hard_blockers.append("missing_or_invalid_training_candidates")
    if candidate_review_check.get("ok") is not True:
        hard_blockers.append("missing_or_invalid_training_candidate_review")
    if baseline_ready_records <= 0:
        hard_blockers.append("baseline_ready_records")
    hard_blockers.extend(readiness_hard_blockers)
    if int(candidates_check.get("records") or 0) <= 0:
        hard_blockers.append("training_candidate_records")
    hard_blockers.extend(candidate_review_hard_blockers)
    if not ready_for_dataset_validation:
        hard_blockers.append("dataset_validation_not_ready")
    unique_blockers = list(dict.fromkeys(item for item in hard_blockers if item))

    if baseline_check.get("ok") is not True:
        missing_or_blocked_step = "heldout_baseline_decision_review"
    elif baseline_ready_records <= 0:
        missing_or_blocked_step = "baseline_ready_records"
    elif readiness_check.get("ok") is not True:
        missing_or_blocked_step = "training_readiness"
    elif readiness_hard_blockers:
        missing_or_blocked_step = readiness_hard_blockers[0]
    elif candidates_check.get("ok") is not True:
        missing_or_blocked_step = "training_candidates"
    elif int(candidates_check.get("records") or 0) <= 0:
        missing_or_blocked_step = "training_candidate_records"
    elif candidate_review_check.get("ok") is not True:
        missing_or_blocked_step = "training_candidate_review"
    elif candidate_review_hard_blockers:
        missing_or_blocked_step = candidate_review_hard_blockers[0]
    elif not ready_for_dataset_validation:
        missing_or_blocked_step = "dataset_validation_not_ready"
    else:
        missing_or_blocked_step = None

    training_pipeline_status = (
        "ready_for_dataset_validation"
        if ready_for_dataset_validation and not unique_blockers
        else "blocked"
    )
    return {
        "source": "biber_mvp_loop_repair_chain_training_pipeline_status",
        "review_status": "training_pipeline_status_summary_only",
        "training_pipeline_status": training_pipeline_status,
        "missing_or_blocked_step": missing_or_blocked_step,
        "artifact_dir": str(root),
        "artifact_paths": {
            key: str(value)
            for key, value in artifact_paths.items()
        },
        "checks": checks,
        "baseline_ready_records": baseline_ready_records,
        "readiness_baseline_ready_records": readiness_baseline_ready_records,
        "training_gate_status": (
            readiness.get("training_gate_status")
            if readiness and readiness_check.get("ok") is True
            else None
        ),
        "ready_for_manual_training_dataset_review": (
            readiness.get("ready_for_manual_training_dataset_review") is True
            if readiness and readiness_check.get("ok") is True
            else False
        ),
        "training_candidate_records": int(candidates_check.get("records") or 0),
        "training_candidate_review_records": candidate_review_records,
        "ready_for_dataset_validation": ready_for_dataset_validation,
        "hard_blockers": unique_blockers,
        "eval_only": True,
        "review_queue_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "next_review_action": (
            "validate_reviewed_training_dataset_before_training"
            if training_pipeline_status == "ready_for_dataset_validation"
            else "collect_baseline_ready_decision_reviews_before_training"
        ),
    }


def normalize_repair_chain_training_pipeline_status_artifact(
    payload: Mapping[str, Any],
) -> dict[str, Any] | None:
    if payload.get("source") == "biber_mvp_loop_repair_chain_training_pipeline_status":
        return dict(payload)
    body = payload.get("body")
    if (
        isinstance(body, dict)
        and body.get("source")
        == "biber_mvp_loop_repair_chain_training_pipeline_status"
    ):
        normalized = dict(body)
        if payload.get("output") and not normalized.get("artifact_path"):
            normalized["artifact_path"] = payload.get("output")
        return normalized
    return None


def summarize_repair_chain_training_pipeline_status_artifact(
    path: Path,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        modified_epoch = path.stat().st_mtime
    except OSError:
        modified_epoch = 0.0
    hard_blockers = [
        str(item)
        for item in require_list(payload.get("hard_blockers"))
        if item
    ]
    ready_for_dataset_validation = (
        payload.get("ready_for_dataset_validation") is True
        or payload.get("training_pipeline_status") == "ready_for_dataset_validation"
    )
    summary: dict[str, Any] = {
        "path": str(path),
        "artifact_dir": payload.get("artifact_dir"),
        "training_pipeline_status": payload.get("training_pipeline_status"),
        "missing_or_blocked_step": payload.get("missing_or_blocked_step"),
        "baseline_ready_records": int(payload.get("baseline_ready_records") or 0),
        "training_candidate_records": int(
            payload.get("training_candidate_records") or 0
        ),
        "training_candidate_review_records": int(
            payload.get("training_candidate_review_records") or 0
        ),
        "ready_for_dataset_validation": ready_for_dataset_validation,
        "hard_blockers": hard_blockers,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "modified_epoch": modified_epoch,
    }
    if payload.get("artifact_path"):
        summary["artifact_path"] = payload.get("artifact_path")
    return summary


def list_repair_chain_training_pipeline_statuses(
    *,
    directory: str,
    pattern: str,
    limit: int,
    ready_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(
            f"Training pipeline artifact directory does not exist: {root}"
        )
    if not root.is_dir():
        raise BiberAgentClientError(
            f"Training pipeline artifact path is not a directory: {root}"
        )

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(
                str(path),
                label="repair-chain training pipeline artifact",
            )
        except BiberAgentClientError:
            continue
        normalized = normalize_repair_chain_training_pipeline_status_artifact(
            raw_payload
        )
        if normalized is None:
            continue
        summary = summarize_repair_chain_training_pipeline_status_artifact(
            path,
            normalized,
        )
        if ready_only and summary.get("ready_for_dataset_validation") is not True:
            continue
        artifacts.append(summary)

    artifacts.sort(key=lambda item: float(item.get("modified_epoch") or 0.0), reverse=True)
    ready_count = sum(
        1 for item in artifacts if item.get("ready_for_dataset_validation") is True
    )
    blocked_count = sum(
        1 for item in artifacts if item.get("training_pipeline_status") == "blocked"
    )
    return {
        "source": "biber_mvp_loop_repair_chain_training_pipeline_list",
        "directory": str(root),
        "pattern": pattern,
        "ready_only": ready_only,
        "scanned": scanned,
        "matched": len(artifacts),
        "ready_for_dataset_validation": ready_count,
        "blocked": blocked_count,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "artifacts": artifacts[:limit],
        "next_review_action": (
            "validate_reviewed_training_dataset_before_training"
            if ready_count
            else "collect_baseline_ready_decision_reviews_before_training"
        ),
    }


def list_mvp_loop_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
    failed_only: bool = False,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(f"MVP loop artifact directory does not exist: {root}")
    if not root.is_dir():
        raise BiberAgentClientError(f"MVP loop artifact path is not a directory: {root}")

    scanned = 0
    artifacts: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(str(path), label="mvp-loop artifact")
        except BiberAgentClientError:
            continue
        normalized = normalize_mvp_loop_artifact(raw_payload)
        if normalized is None:
            continue
        if failed_only and not is_failed_mvp_loop_artifact(normalized):
            continue
        artifacts.append(summarize_mvp_loop_artifact(path, normalized))

    artifacts.sort(key=lambda item: float(item.get("modified_epoch") or 0.0), reverse=True)
    return {
        "directory": str(root),
        "pattern": pattern,
        "failed_only": failed_only,
        "scanned": scanned,
        "artifacts": artifacts[:limit],
    }


def export_mvp_loop_failures(
    *,
    directory: str,
    pattern: str,
    limit: int,
    output_path: str,
) -> dict[str, Any]:
    if limit < 1:
        raise BiberAgentClientError("--limit must be at least 1.")
    root = Path(directory)
    if not root.exists():
        raise BiberAgentClientError(f"MVP loop artifact directory does not exist: {root}")
    if not root.is_dir():
        raise BiberAgentClientError(f"MVP loop artifact path is not a directory: {root}")

    scanned = 0
    records: list[dict[str, Any]] = []
    for path in root.rglob(pattern):
        if not path.is_file():
            continue
        scanned += 1
        try:
            raw_payload = load_json_artifact(str(path), label="mvp-loop artifact")
        except BiberAgentClientError:
            continue
        normalized = normalize_mvp_loop_artifact(raw_payload)
        if normalized is None or not is_failed_mvp_loop_artifact(normalized):
            continue
        records.append(build_mvp_loop_failure_record(path, normalized))

    records.sort(key=lambda item: str(item.get("source_artifact", "")), reverse=True)
    selected_records = records[:limit]
    output = write_jsonl_artifact(selected_records, output_path)
    return {
        "directory": str(root),
        "pattern": pattern,
        "scanned": scanned,
        "records": len(selected_records),
        "output": output,
        "review_status": "needs_review",
        "training_allowed": False,
    }


def load_workspace_edits(
    *,
    edit_json_values: list[str] | None,
    edits_file: str | None,
) -> list[dict[str, Any]]:
    edits: list[dict[str, Any]] = []
    if edits_file:
        path = Path(edits_file)
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise BiberAgentClientError(f"Could not read edits file {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise BiberAgentClientError(f"Edits file must be valid JSON: {exc}") from exc
        if isinstance(parsed, dict) and isinstance(parsed.get("edits"), list):
            raw_edits = parsed["edits"]
        elif isinstance(parsed, list):
            raw_edits = parsed
        elif isinstance(parsed, dict):
            raw_edits = [parsed]
        else:
            raise BiberAgentClientError(
                "Edits file must contain a JSON object, a JSON array, or an object with edits."
            )
        for index, item in enumerate(raw_edits, start=1):
            if not isinstance(item, dict):
                raise BiberAgentClientError(
                    f"Edits file item {index} must be a JSON object."
                )
            edits.append(item)

    for raw in edit_json_values or []:
        edit = parse_json_object(raw, label="--edit-json")
        if isinstance(edit.get("edits"), list):
            raise BiberAgentClientError(
                "--edit-json must contain one edit object; use --edits-file for arrays."
            )
        edits.append(edit)

    if not edits:
        raise BiberAgentClientError("At least one --edit-json or --edits-file is required.")
    return edits


def build_workspace_edit_payload(
    *,
    edits: list[dict[str, Any]],
    max_files: int | None,
    plan_hash: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"edits": edits}
    if max_files is not None:
        payload["max_files"] = max_files
    if plan_hash:
        payload["plan_hash"] = plan_hash
    return payload


def build_test_run_payload(*, test_id: str, dry_run: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {"test_id": test_id}
    if dry_run:
        payload["dry_run"] = True
    return payload


def build_test_diagnosis_payload(
    *,
    test_id: str | None,
    command_json: str | None = None,
    command_parts: list[str] | None = None,
    exit_code: int | None,
    timed_out: bool,
    stdout: str,
    stderr: str,
    max_context_lines: int | None,
) -> dict[str, Any]:
    if command_json and command_parts:
        raise BiberAgentClientError(
            "Use either --command-json or repeated --command-part, not both."
        )
    command: list[str] = []
    if command_json:
        parsed_command = parse_json_list(command_json, label="--command-json")
        if not all(isinstance(part, str) for part in parsed_command):
            raise BiberAgentClientError("--command-json must contain only strings.")
        command = parsed_command
    elif command_parts:
        command = command_parts

    payload: dict[str, Any] = {
        "command": command,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
    }
    if test_id is not None:
        payload["test_id"] = test_id
    if exit_code is not None:
        payload["exit_code"] = exit_code
    if max_context_lines is not None:
        payload["max_context_lines"] = max_context_lines
    return payload


def build_diagnosis_payload_from_test_run(
    payload: Mapping[str, Any],
    *,
    max_context_lines: int | None,
) -> dict[str, Any]:
    diagnosis: dict[str, Any] = {
        "test_id": payload.get("test_id"),
        "command": require_list(payload.get("command")),
        "exit_code": payload.get("exit_code"),
        "timed_out": bool(payload.get("timed_out")),
        "stdout": str(payload.get("stdout") or ""),
        "stderr": str(payload.get("stderr") or ""),
    }
    if max_context_lines is not None:
        diagnosis["max_context_lines"] = max_context_lines
    return diagnosis


def build_github_save_payload(
    *,
    path: str,
    content: str,
    owner: str | None,
    repo: str | None,
    branch: str,
    base_branch: str | None,
    create_branch_if_missing: bool,
    commit_message: str,
) -> dict[str, Any]:
    target: dict[str, Any] = {
        "path": path,
        "branch": branch,
        "create_branch_if_missing": create_branch_if_missing,
        "commit_message": commit_message,
    }
    if owner:
        target["owner"] = owner
    if repo:
        target["repo"] = repo
    if base_branch:
        target["base_branch"] = base_branch
    return {"target": target, "content": content}


def build_github_pull_request_payload(
    *,
    head: str,
    base: str,
    title: str,
    body: str,
    owner: str | None,
    repo: str | None,
    draft: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "head": head,
        "base": base,
        "title": title,
        "body": body,
        "draft": draft,
    }
    if owner:
        payload["owner"] = owner
    if repo:
        payload["repo"] = repo
    return payload


def format_github_save_summary(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "BIBER GitHub save",
            f"url: {payload.get('url', '-')}",
        ]
    )


def build_github_save_dry_run_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    content = str(payload.get("content") or "")
    return {
        "source": "biber_github_save_dry_run",
        "dry_run": True,
        "api_required": False,
        "github_request_sent": False,
        "training_allowed": False,
        "auto_applied": False,
        "target": require_mapping(payload.get("target")),
        "content_bytes": len(content.encode("utf-8")),
    }


def format_github_save_dry_run_summary(payload: Mapping[str, Any]) -> str:
    target = require_mapping(payload.get("target"))
    return "\n".join(
        [
            "BIBER GitHub save dry-run",
            f"dry_run: {payload.get('dry_run', False)}",
            f"api_required: {payload.get('api_required', True)}",
            f"github_request_sent: {payload.get('github_request_sent', True)}",
            f"path: {target.get('path', '-')}",
            f"owner: {target.get('owner', '-')}",
            f"repo: {target.get('repo', '-')}",
            f"branch: {target.get('branch', '-')}",
            f"base_branch: {target.get('base_branch', '-')}",
            f"create_branch_if_missing: {target.get('create_branch_if_missing', False)}",
            f"commit_message: {target.get('commit_message', '-')}",
            f"content_bytes: {payload.get('content_bytes', 0)}",
        ]
    )


def format_github_pull_request_summary(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "BIBER GitHub pull request",
            f"url: {payload.get('url', '-')}",
            f"number: {payload.get('number', '-')}",
        ]
    )


def build_github_pull_request_dry_run_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    body = str(payload.get("body") or "")
    return {
        "source": "biber_github_pull_request_dry_run",
        "dry_run": True,
        "api_required": False,
        "github_request_sent": False,
        "training_allowed": False,
        "auto_applied": False,
        "pull_request": dict(payload),
        "body_bytes": len(body.encode("utf-8")),
    }


def format_github_pull_request_dry_run_summary(payload: Mapping[str, Any]) -> str:
    pull_request = require_mapping(payload.get("pull_request"))
    return "\n".join(
        [
            "BIBER GitHub pull request dry-run",
            f"dry_run: {payload.get('dry_run', False)}",
            f"api_required: {payload.get('api_required', True)}",
            f"github_request_sent: {payload.get('github_request_sent', True)}",
            f"owner: {pull_request.get('owner', '-')}",
            f"repo: {pull_request.get('repo', '-')}",
            f"head: {pull_request.get('head', '-')}",
            f"base: {pull_request.get('base', '-')}",
            f"title: {pull_request.get('title', '-')}",
            f"draft: {pull_request.get('draft', True)}",
            f"body_bytes: {payload.get('body_bytes', 0)}",
        ]
    )


def format_mvp_loop_summary(payload: Mapping[str, Any]) -> str:
    steps = require_mapping(payload.get("steps"))
    lines = [
        "BIBER MVP loop",
        f"ok: {bool(payload.get('ok'))}",
        f"selected_context_paths: {len(require_list(payload.get('selected_context_paths')))}",
        f"steps: {', '.join(steps.keys()) if steps else '-'}",
    ]
    runtime_profile_ids = normalize_runtime_profile_ids(
        payload.get("runtime_profile_ids")
    )
    if runtime_profile_ids:
        lines.append(f"runtime_profiles: {', '.join(runtime_profile_ids)}")
    if payload.get("edit_plan_hash"):
        lines.append(f"edit_plan_hash: {payload.get('edit_plan_hash')}")
    if "test_ok" in payload:
        lines.append(f"test_ok: {payload.get('test_ok')}")
    if payload.get("diagnosis_summary"):
        lines.append(f"diagnosis: {payload.get('diagnosis_summary')}")
    if payload.get("github_dry_run"):
        lines.append(f"github_dry_run: {payload.get('github_dry_run')}")
        lines.append(f"github_request_sent: {payload.get('github_request_sent')}")
    if payload.get("github_url"):
        lines.append(f"github_url: {payload.get('github_url')}")
    if payload.get("pull_request_url"):
        lines.append(f"pull_request_url: {payload.get('pull_request_url')}")
    if payload.get("artifact_path"):
        lines.append(f"artifact_path: {payload.get('artifact_path')}")
    report = require_mapping(payload.get("agent_report"))
    if report:
        repo = require_mapping(report.get("repo"))
        edit = require_mapping(report.get("edit"))
        test = require_mapping(report.get("test"))
        lines.append("agent_report:")
        lines.append(f"- status: {report.get('status', '-')}")
        if repo:
            lines.append(
                "- repo: "
                f"branch={repo.get('branch') or '-'} "
                f"head={repo.get('head') or '-'} "
                f"dirty={repo.get('dirty')}"
            )
        if edit and any(value is not None for value in edit.values()):
            lines.append(
                "- edit: "
                f"planned={edit.get('planned_count', 0)} "
                f"applied={edit.get('applied_count', 0)} "
                f"changed={edit.get('changed_count', 0)} "
                f"rejected={edit.get('rejected_count', 0)}"
            )
        if test and any(value is not None for value in test.values()):
            lines.append(
                "- test: "
                f"id={test.get('test_id') or '-'} "
                f"executed={test.get('executed')} "
                f"ok={test.get('ok')} "
                f"exit_code={test.get('exit_code')}"
            )
        repair_hint = require_mapping(report.get("repair_hint"))
        if repair_hint:
            lines.append(
                "- repair_hint: "
                f"status={repair_hint.get('status') or '-'} "
                f"category={repair_hint.get('primary_category') or '-'} "
                f"stack={repair_hint.get('detected_stack') or '-'} "
                f"next={','.join(str(item) for item in require_list(repair_hint.get('next_workflow'))[:3]) or '-'}"
            )
            if repair_hint.get("next_command"):
                lines.append(f"- repair_next_command: {repair_hint.get('next_command')}")
        next_actions = [str(item) for item in require_list(report.get("next_actions"))]
        if next_actions:
            lines.append("agent_next_actions:")
            lines.extend(f"- {action}" for action in next_actions[:5])
    return "\n".join(lines)


def format_mvp_loop_artifact_summary(payload: Mapping[str, Any]) -> str:
    selected_paths = [
        str(path) for path in require_list(payload.get("selected_context_paths"))
    ]
    lines = [format_mvp_loop_summary(payload)]
    if selected_paths:
        lines.append("selected_context_paths:")
        lines.extend(f"- {path}" for path in selected_paths)

    step_summaries: list[str] = []
    for name, step in require_mapping(payload.get("steps")).items():
        if not isinstance(step, dict):
            continue
        parts = [f"- {name}"]
        if "ok" in step:
            parts.append(f"ok={step.get('ok')}")
        if "summary" in step:
            parts.append(f"summary={step.get('summary')}")
        if "test_id" in step:
            parts.append(f"test_id={step.get('test_id')}")
        step_summaries.append(" ".join(parts))
    if step_summaries:
        lines.append("step_summaries:")
        lines.extend(step_summaries)
    return "\n".join(lines)


def format_mvp_loop_artifact_list_summary(payload: Mapping[str, Any]) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER MVP loop artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"failed_only: {payload.get('failed_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
    ]
    for artifact in artifacts:
        steps = ", ".join(str(step) for step in require_list(artifact.get("steps")))
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"ok={artifact.get('ok')}",
                    f"test_ok={artifact.get('test_ok')}",
                    f"selected_context_paths={artifact.get('selected_context_paths', 0)}",
                    f"steps={steps or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_mvp_loop_failure_export_summary(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "BIBER MVP loop failure export",
            f"directory: {payload.get('directory', '-')}",
            f"pattern: {payload.get('pattern', '-')}",
            f"scanned: {payload.get('scanned', 0)}",
            f"records: {payload.get('records', 0)}",
            f"output: {payload.get('output', '-')}",
            f"review_status: {payload.get('review_status', '-')}",
            f"training_allowed: {payload.get('training_allowed', False)}",
        ]
    )


def format_mvp_loop_repair_request_summary(payload: Mapping[str, Any]) -> str:
    failure = require_mapping(payload.get("failure"))
    lines = [
        "BIBER MVP loop repair request",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"repair_status: {payload.get('repair_status', '-')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"selected_context_paths: {len(require_list(payload.get('selected_context_paths')))}",
        f"test_id: {failure.get('test_id') or '-'}",
        f"primary_category: {failure.get('primary_category') or '-'}",
        f"detected_stack: {failure.get('detected_stack') or '-'}",
        f"next_test_id: {payload.get('next_test_id') or '-'}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    runtime_profile_ids = normalize_runtime_profile_ids(
        payload.get("runtime_profile_ids")
    )
    if runtime_profile_ids:
        lines.append(f"runtime_profiles: {', '.join(runtime_profile_ids)}")
    agent_report = require_mapping(payload.get("agent_report"))
    if agent_report:
        repo = require_mapping(agent_report.get("repo"))
        lines.append(f"agent_report_status: {agent_report.get('status', '-')}")
        if repo:
            lines.append(
                "agent_report_repo: "
                f"branch={repo.get('branch') or '-'} "
                f"head={repo.get('head') or '-'} "
                f"dirty={repo.get('dirty')}"
            )
    return "\n".join(lines)


def format_mvp_loop_repair_attempt_summary(payload: Mapping[str, Any]) -> str:
    repair_request = require_mapping(payload.get("repair_request"))
    model_response = require_mapping(payload.get("model_response"))
    lines = [
        "BIBER MVP loop repair attempt",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"repair_status: {payload.get('repair_status', '-')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"ready_for_edit_review: {payload.get('ready_for_edit_review', False)}",
        f"model: {model_response.get('model', '-')}",
        f"mentor_used: {model_response.get('mentor_used', False)}",
        f"next_test_id: {payload.get('next_test_id') or '-'}",
        f"repair_request_status: {repair_request.get('repair_status', '-')}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    runtime_profile_ids = repair_attempt_runtime_profile_ids(payload)
    if runtime_profile_ids:
        lines.append(f"runtime_profiles: {', '.join(runtime_profile_ids)}")
    output_contract = require_mapping(payload.get("repair_output_contract"))
    if output_contract:
        lines.append(
            f"repair_output_contract: {output_contract.get('source', '-')}"
        )
    extraction_hint = require_mapping(payload.get("extraction_hint"))
    if extraction_hint:
        lines.append(
            "extraction_hint: "
            f"ready={extraction_hint.get('ready_for_extraction')} "
            f"json_values={extraction_hint.get('json_values_found', 0)} "
            f"next={extraction_hint.get('next_command', '-')}"
        )
    repair_content = compact_text(payload.get("repair_content"), max_chars=240).strip()
    if repair_content:
        lines.append("repair_content_preview:")
        lines.append(repair_content)
    return "\n".join(lines)


def format_repair_attempt_artifact_list_summary(payload: Mapping[str, Any]) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair attempt artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"ready_for_edit_review: {payload.get('ready_for_edit_review', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
    ]
    for artifact in artifacts:
        runtime_profiles = ", ".join(
            str(item) for item in require_list(artifact.get("runtime_profile_ids"))
        )
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('repair_status', '-')}",
                    f"ready={artifact.get('ready_for_edit_review', False)}",
                    f"model={artifact.get('model', '-')}",
                    f"mentor_used={artifact.get('mentor_used', False)}",
                    f"next_test_id={artifact.get('next_test_id') or '-'}",
                    f"runtime_profiles={runtime_profiles or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_edit_extraction_summary(payload: Mapping[str, Any]) -> str:
    edits = [item for item in require_list(payload.get("edits")) if isinstance(item, dict)]
    rejected = [
        item for item in require_list(payload.get("rejected")) if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair edit extraction",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"extraction_status: {payload.get('extraction_status', '-')}",
        f"ok: {bool(payload.get('ok'))}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"edits: {len(edits)}",
        f"rejected: {len(rejected)}",
        "source_only_guard: "
        f"{require_mapping(payload.get('source_only_guard')).get('enabled', False)}",
        "repeat_failed_edit_guard: "
        f"{require_mapping(payload.get('repeat_failed_edit_guard')).get('enabled', False)}",
        f"edits_output: {payload.get('edits_output', '-')}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(f"- {edit.get('path', '-')}" for edit in edits[:8])
    return "\n".join(lines)


def format_repair_edit_extraction_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair edit extraction artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"ready_for_plan_edit: {payload.get('ready_for_plan_edit', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('extraction_status', '-')}",
                    f"ok={artifact.get('ok', False)}",
                    f"edits={artifact.get('edits', 0)}",
                    f"rejected={artifact.get('rejected', 0)}",
                    f"next_test_id={artifact.get('next_test_id') or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_repeated_forbidden_retry_gap_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER repeated forbidden retry gap export",
            f"source_artifact: {payload.get('source_artifact', '-')}",
            f"repair_attempt_artifact: {payload.get('repair_attempt_artifact', '-')}",
            f"records: {payload.get('records', 0)}",
            f"output: {payload.get('output', '-')}",
            f"review_status: {payload.get('review_status', '-')}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"eligible_for_training: {payload.get('eligible_for_training', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"next_review_action: {payload.get('next_review_action', '-')}",
        ]
    )


def format_empty_retry_gap_export_summary(payload: Mapping[str, Any]) -> str:
    hints = ",".join(str(item) for item in require_list(payload.get("review_hints")))
    return "\n".join(
        [
            "BIBER empty retry response gap export",
            f"source_artifact: {payload.get('source_artifact', '-')}",
            f"repair_attempt_artifact: {payload.get('repair_attempt_artifact', '-')}",
            f"records: {payload.get('records', 0)}",
            f"output: {payload.get('output', '-')}",
            f"review_status: {payload.get('review_status', '-')}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"eligible_for_training: {payload.get('eligible_for_training', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"review_hints: {hints or '-'}",
            f"next_review_action: {payload.get('next_review_action', '-')}",
        ]
    )


def format_blocked_retry_edit_gap_export_summary(payload: Mapping[str, Any]) -> str:
    hard_blockers = ",".join(
        str(item) for item in require_list(payload.get("review_hard_blockers"))
    )
    return "\n".join(
        [
            "BIBER blocked retry edit gap export",
            f"source_artifact: {payload.get('source_artifact', '-')}",
            f"repair_edit_extraction_artifact: {payload.get('repair_edit_extraction_artifact', '-')}",
            f"repair_attempt_artifact: {payload.get('repair_attempt_artifact', '-')}",
            f"records: {payload.get('records', 0)}",
            f"output: {payload.get('output', '-')}",
            f"review_status: {payload.get('review_status', '-')}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"eligible_for_training: {payload.get('eligible_for_training', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"hard_blockers: {hard_blockers or '-'}",
            f"next_review_action: {payload.get('next_review_action', '-')}",
        ]
    )


def format_blocked_retry_edit_gap_review_summary(payload: Mapping[str, Any]) -> str:
    groups = [
        item for item in require_list(payload.get("groups")) if isinstance(item, dict)
    ]
    lines = [
        "BIBER blocked retry edit gap review",
        f"jsonl_paths: {len(require_list(payload.get('jsonl_paths')))}",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', 0)}",
        f"groups: {len(groups)}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"eligible_for_training: {payload.get('eligible_for_training', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    for group in groups[:8]:
        blockers = ",".join(
            str(item) for item in require_list(group.get("hard_blockers"))
        )
        hints = ",".join(str(item) for item in require_list(group.get("review_hints")))
        lines.append(
            " ".join(
                [
                    f"- model={group.get('model') or '-'}",
                    f"test={group.get('next_test_id') or '-'}",
                    f"path={group.get('path') or '-'}",
                    f"count={group.get('count', 0)}",
                    f"blockers={blockers or '-'}",
                    f"hints={hints or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_empty_retry_gap_review_summary(payload: Mapping[str, Any]) -> str:
    groups = [
        item for item in require_list(payload.get("groups")) if isinstance(item, dict)
    ]
    lines = [
        "BIBER empty retry response gap review",
        f"jsonl_paths: {len(require_list(payload.get('jsonl_paths')))}",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', 0)}",
        f"groups: {len(groups)}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"eligible_for_training: {payload.get('eligible_for_training', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    for group in groups[:8]:
        hints = ",".join(str(item) for item in require_list(group.get("review_hints")))
        lines.append(
            " ".join(
                [
                    f"- model={group.get('model') or '-'}",
                    f"test={group.get('next_test_id') or '-'}",
                    f"path={group.get('path') or '-'}",
                    f"count={group.get('count', 0)}",
                    f"hints={hints or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_repeated_forbidden_retry_gap_review_summary(
    payload: Mapping[str, Any],
) -> str:
    groups = [
        item for item in require_list(payload.get("groups")) if isinstance(item, dict)
    ]
    lines = [
        "BIBER repeated forbidden retry gap review",
        f"jsonl_paths: {len(require_list(payload.get('jsonl_paths')))}",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', 0)}",
        f"groups: {len(groups)}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"eligible_for_training: {payload.get('eligible_for_training', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    for group in groups[:8]:
        hints = ",".join(str(item) for item in require_list(group.get("review_hints")))
        lines.append(
            " ".join(
                [
                    f"- model={group.get('model') or '-'}",
                    f"test={group.get('next_test_id') or '-'}",
                    f"path={group.get('path') or '-'}",
                    f"count={group.get('count', 0)}",
                    f"hints={hints or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_retry_repair_edit_review_summary(payload: Mapping[str, Any]) -> str:
    edits = [item for item in require_list(payload.get("edits")) if isinstance(item, dict)]
    candidate_reviews = [
        item
        for item in require_list(payload.get("candidate_reviews"))
        if isinstance(item, dict)
    ]
    hard_blockers = require_list(payload.get("hard_blockers"))
    review_hints = require_list(payload.get("review_hints"))
    lines = [
        "BIBER retry repair edit review",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"repair_attempt_artifact: {payload.get('repair_attempt_artifact', '-')}",
        f"review_status: {payload.get('review_status', '-')}",
        f"ok: {bool(payload.get('ok'))}",
        f"plan_allowed: {payload.get('plan_allowed', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"eligible_for_training: {payload.get('eligible_for_training', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"edits: {len(edits)}",
        f"hard_blockers: {len(hard_blockers)}",
        f"review_hints: {','.join(str(item) for item in review_hints) or '-'}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    for candidate in candidate_reviews[:8]:
        blockers = ",".join(
            str(item) for item in require_list(candidate.get("hard_blockers"))
        )
        lines.append(
            " ".join(
                [
                    f"- index={candidate.get('index', '-')}",
                    f"path={candidate.get('path', '-')}",
                    f"allowed={candidate.get('allowed_for_plan', False)}",
                    f"blockers={blockers or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_edit_plan_summary(payload: Mapping[str, Any]) -> str:
    edit_plan = require_mapping(payload.get("edit_plan"))
    planned = [
        item
        for item in require_list(edit_plan.get("planned"))
        if isinstance(item, dict)
    ]
    rejected = [
        item
        for item in require_list(edit_plan.get("rejected"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair edit plan",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"plan_status: {payload.get('plan_status', '-')}",
        f"ok: {bool(payload.get('ok'))}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"plan_mode: {payload.get('plan_mode', '-')}",
        f"target_root: {payload.get('target_root', '-')}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"planned: {len(planned)}",
        f"rejected: {len(rejected)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(f"- {item.get('path', '-')}" for item in planned[:8])
    return "\n".join(lines)


def format_repair_edit_plan_artifact_list_summary(payload: Mapping[str, Any]) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair edit plan artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"planned_only: {payload.get('planned_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"planned: {payload.get('planned', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('plan_status', '-')}",
                    f"ok={artifact.get('ok', False)}",
                    f"planned={artifact.get('planned', 0)}",
                    f"rejected={artifact.get('rejected', 0)}",
                    f"plan_hash={artifact.get('plan_hash') or '-'}",
                    f"next_test_id={artifact.get('next_test_id') or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_local_repair_chain_summary(payload: Mapping[str, Any]) -> str:
    extraction = require_mapping(payload.get("repair_edit_extraction"))
    plan = require_mapping(payload.get("repair_edit_plan"))
    edit_plan = require_mapping(plan.get("edit_plan"))
    planned = [
        item for item in require_list(edit_plan.get("planned")) if isinstance(item, dict)
    ]
    lines = [
        "BIBER local repair chain",
        f"chain_status: {payload.get('chain_status', '-')}",
        f"ok: {payload.get('ok')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"extraction_status: {extraction.get('extraction_status', '-')}",
        f"edits: {len(require_list(extraction.get('edits')))}",
        f"rejected: {len(require_list(extraction.get('rejected')))}",
        f"json_values_found: {extraction.get('json_values_found', 0)}",
        f"plan_status: {plan.get('plan_status', '-') if plan else '-'}",
        f"plan_hash: {plan.get('plan_hash', '-') if plan else '-'}",
        f"target_root: {payload.get('target_root', '-')}",
        f"plan_skipped_reason: {payload.get('plan_skipped_reason', '-')}",
        f"next_test_id: {payload.get('next_test_id') or '-'}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    if planned:
        lines.append(f"planned ({len(planned)}):")
        lines.extend(f"- {item.get('path', '-')}" for item in planned[:8])
    return "\n".join(lines)


def format_local_repair_chain_review_summary(payload: Mapping[str, Any]) -> str:
    blockers = [str(item) for item in require_list(payload.get("blockers"))]
    warnings = [str(item) for item in require_list(payload.get("warnings"))]
    lines = [
        "BIBER local repair chain review",
        f"review_status: {payload.get('review_status', '-')}",
        f"ok: {payload.get('ok')}",
        f"apply_recommendation: {payload.get('apply_recommendation', '-')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"chain_status: {payload.get('chain_status', '-')}",
        f"extraction_status: {payload.get('extraction_status', '-')}",
        f"plan_status: {payload.get('plan_status', '-')}",
        f"edits: {payload.get('edits', 0)}",
        f"planned: {payload.get('planned', 0)}",
        f"rejected: {payload.get('rejected', 0)}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"target_root: {payload.get('target_root', '-')}",
        f"next_test_id: {payload.get('next_test_id') or '-'}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    if blockers:
        lines.append("blockers:")
        lines.extend(f"- {item}" for item in blockers)
    if warnings:
        lines.append("warnings:")
        lines.extend(f"- {item}" for item in warnings)
    return "\n".join(lines)


def format_repair_edit_apply_summary(payload: Mapping[str, Any]) -> str:
    edit_apply = require_mapping(payload.get("edit_apply"))
    applied = [
        item
        for item in require_list(edit_apply.get("applied"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair edit apply",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"apply_status: {payload.get('apply_status', '-')}",
        f"ok: {bool(payload.get('ok'))}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"approval_required: {payload.get('approval_required', True)}",
        f"approval_received: {payload.get('approval_received', False)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"pre_apply_review_status: {payload.get('pre_apply_review_status', '-')}",
        f"pre_apply_review_artifact: {payload.get('pre_apply_review_artifact', '-')}",
        f"plan_mode: {payload.get('plan_mode', '-')}",
        f"target_root: {payload.get('target_root', '-')}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"applied: {len(applied)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        f"- {item.get('path', '-')} changed={item.get('changed', False)}"
        for item in applied[:8]
    )
    return "\n".join(lines)


def format_repair_edit_apply_artifact_list_summary(payload: Mapping[str, Any]) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair edit apply artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"applied_only: {payload.get('applied_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"applied: {payload.get('applied', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('apply_status', '-')}",
                    f"ok={artifact.get('ok', False)}",
                    f"approval_received={artifact.get('approval_received', False)}",
                    f"applied={artifact.get('applied', 0)}",
                    f"plan_hash={artifact.get('plan_hash') or '-'}",
                    f"next_test_id={artifact.get('next_test_id') or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_test_verification_summary(payload: Mapping[str, Any]) -> str:
    test_run = require_mapping(payload.get("test_run"))
    lines = [
        "BIBER repair test verification",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"verification_status: {payload.get('verification_status', '-')}",
        f"ok: {bool(payload.get('ok'))}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"auto_saved: {payload.get('auto_saved', False)}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"test_id: {payload.get('test_id', '-')}",
        f"test_executed: {test_run.get('executed')}",
        f"test_ok: {test_run.get('ok')}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    diagnosis = test_run.get("diagnosis")
    if isinstance(diagnosis, dict):
        lines.extend(
            [
                f"diagnosis: {diagnosis.get('summary', '-')}",
                f"primary_category: {diagnosis.get('primary_category', '-')}",
                f"detected_stack: {diagnosis.get('detected_stack', '-')}",
            ]
        )
    return "\n".join(lines)


def format_local_repair_verification_chain_summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "BIBER local repair verification chain",
        f"chain_status: {payload.get('chain_status', '-')}",
        f"ok: {payload.get('ok')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"auto_saved: {payload.get('auto_saved', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
        f"source_artifact: {payload.get('source_artifact', '-')}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"test_id: {payload.get('test_id', '-')}",
        f"verification_status: {payload.get('verification_status', '-')}",
        f"test_mode: {payload.get('test_mode', '-')}",
        f"test_executed: {payload.get('test_executed')}",
        f"test_ok: {payload.get('test_ok')}",
        f"exit_code: {payload.get('exit_code')}",
        f"timed_out: {payload.get('timed_out', False)}",
        f"target_root: {payload.get('target_root', '-')}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    if payload.get("diagnosis_summary"):
        lines.append(f"diagnosis: {payload.get('diagnosis_summary')}")
    if payload.get("primary_category") or payload.get("detected_stack"):
        lines.append(
            " ".join(
                [
                    f"primary_category={payload.get('primary_category') or '-'}",
                    f"detected_stack={payload.get('detected_stack') or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_local_repair_loop_status_summary(payload: Mapping[str, Any]) -> str:
    current = require_mapping(payload.get("current"))
    next_step = require_mapping(payload.get("next_step"))
    command = next_step.get("command")
    model_command_alternative = next_step.get("model_command_alternative")
    lines = [
        "BIBER local repair loop status",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"auto_saved: {payload.get('auto_saved', False)}",
        f"apply_allowed: {payload.get('apply_allowed', False)}",
        f"current_type: {current.get('artifact_type', '-')}",
        f"current_status: {current.get('status', '-')}",
        f"current_ok: {current.get('ok')}",
        f"current_path: {current.get('path', '-')}",
        f"plan_hash: {current.get('plan_hash') or '-'}",
        f"test_id: {current.get('test_id') or '-'}",
        f"target_root: {current.get('target_root') or '-'}",
        f"next_action: {next_step.get('action', '-')}",
        f"next_reason: {next_step.get('reason', '-')}",
        f"next_command: {command or '-'}",
    ]
    if (
        current.get("repair_hint_status")
        or current.get("primary_category")
        or current.get("detected_stack")
    ):
        workflow = ",".join(
            str(item)
            for item in require_list(current.get("repair_next_workflow"))[:3]
        )
        lines.append(
            "repair_hint: "
            f"status={current.get('repair_hint_status') or '-'} "
            f"category={current.get('primary_category') or '-'} "
            f"stack={current.get('detected_stack') or '-'} "
            f"next={workflow or '-'}"
        )
    if model_command_alternative:
        lines.append(f"model_command_alternative: {model_command_alternative}")
    return "\n".join(lines)


def format_repair_test_verification_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair test verification artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"passed_only: {payload.get('passed_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"passed: {payload.get('passed', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"auto_saved: {payload.get('auto_saved', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('verification_status', '-')}",
                    f"ok={artifact.get('ok', False)}",
                    f"test_id={artifact.get('test_id') or '-'}",
                    f"test_executed={artifact.get('test_executed')}",
                    f"test_ok={artifact.get('test_ok')}",
                    f"plan_hash={artifact.get('plan_hash') or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_failed_repair_retry_review_summary(payload: Mapping[str, Any]) -> str:
    attempted_edits = [
        item
        for item in require_list(payload.get("attempted_edits"))
        if isinstance(item, dict)
    ]
    artifact_load_errors = require_list(payload.get("artifact_load_errors"))
    source_context = require_mapping(payload.get("source_context"))
    return "\n".join(
        [
            "BIBER failed repair retry review",
            f"source_artifact: {payload.get('source_artifact', '-')}",
            f"review_status: {payload.get('review_status', '-')}",
            f"ok: {bool(payload.get('ok'))}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"eligible_for_training: {payload.get('eligible_for_training', False)}",
            f"auto_applied: {payload.get('auto_applied', False)}",
            f"auto_saved: {payload.get('auto_saved', False)}",
            f"plan_hash: {payload.get('plan_hash', '-')}",
            f"test_id: {payload.get('test_id', '-')}",
            f"attempted_edits: {len(attempted_edits)}",
            f"artifact_load_errors: {len(artifact_load_errors)}",
            f"source_root_origin: {source_context.get('source_root_origin', '-')}",
            f"source_root: {source_context.get('source_root', '-')}",
            f"retry_repair_request_artifact: {payload.get('retry_repair_request_artifact', '-')}",
            f"artifact_path: {payload.get('artifact_path', '-')}",
        ]
    )


def format_verified_repair_export_summary(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "BIBER verified repair export",
            f"records: {payload.get('records', 0)}",
            f"output: {payload.get('output', '-')}",
            f"review_status: {payload.get('review_status', '-')}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"eligible_for_training: {payload.get('eligible_for_training', False)}",
            f"source_artifact: {payload.get('source_artifact', '-')}",
            f"plan_hash: {payload.get('plan_hash', '-')}",
            f"test_id: {payload.get('test_id', '-')}",
        ]
    )


def format_verified_repair_review_summary(payload: Mapping[str, Any]) -> str:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER verified repair review",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', 0)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"eligible_for_training: {payload.get('eligible_for_training', False)}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"groups: {len(groups)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- test_id={group.get('test_id', '-')} "
            f"plan_hash={group.get('plan_hash', '-')} "
            f"count={group.get('count', 0)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_verified_repair_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER verified repair review artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"ready_artifacts: {payload.get('ready_artifacts', 0)}",
        f"records: {payload.get('records', 0)}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"eligible_for_training: {payload.get('eligible_for_training', False)}",
        f"auto_promoted: {payload.get('auto_promoted', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"ready={artifact.get('ready_for_human_review', 0)}",
                    f"groups={artifact.get('groups', 0)}",
                    f"min_repeat={artifact.get('min_repeat', 1)}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_chain_summary(payload: Mapping[str, Any]) -> str:
    statuses = require_mapping(payload.get("statuses"))
    missing = [str(item) for item in require_list(payload.get("missing_artifacts"))]
    repo_provenance = normalize_repo_provenance(payload.get("repo_provenance"))
    lines = [
        "BIBER repair chain summary",
        f"chain_status: {payload.get('chain_status', '-')}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', False)}",
        f"chain_complete: {payload.get('chain_complete', False)}",
        f"verification_passed: {payload.get('verification_passed', False)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"auto_applied: {payload.get('auto_applied', False)}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"plan_hash_consistent: {payload.get('plan_hash_consistent', False)}",
        f"test_id: {payload.get('test_id', '-')}",
        f"review_records: {statuses.get('review_records', 0)}",
        f"next_action: {payload.get('next_action', '-')}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    if repo_provenance is not None:
        lines.extend(
            [
                f"repo_root: {repo_provenance.get('root', '-')}",
                f"repo_url: {repo_provenance.get('url', '-')}",
                f"repo_commit: {repo_provenance.get('commit', '-')}",
                f"repo_branch: {repo_provenance.get('branch', '-')}",
            ]
        )
    if missing:
        lines.append(f"missing_artifacts: {', '.join(missing)}")
    return "\n".join(lines)


def format_repair_chain_artifact_list_summary(payload: Mapping[str, Any]) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair chain artifacts",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', 0)}",
        f"repo_provenance_ready: {payload.get('repo_provenance_ready', 0)}",
        f"repo_provenance_missing: {payload.get('repo_provenance_missing', 0)}",
        "eval_approval_requires_repo_provenance: "
        f"{payload.get('eval_approval_requires_repo_provenance', False)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('chain_status', '-')}",
                    f"ready={artifact.get('ready_for_human_review', False)}",
                    f"test_id={artifact.get('test_id', '-')}",
                    f"reviews={artifact.get('review_records', 0)}",
                    "repo_provenance_ready="
                    f"{artifact.get('repo_provenance_ready', False)}",
                ]
            )
        )
    return "\n".join(lines)


def format_ready_repair_chain_export_summary(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "BIBER ready repair-chain export",
            f"directory: {payload.get('directory', '-')}",
            f"pattern: {payload.get('pattern', '-')}",
            f"scanned: {payload.get('scanned', 0)}",
            f"records: {payload.get('records', 0)}",
            f"repo_provenance_ready: {payload.get('repo_provenance_ready', 0)}",
            f"repo_provenance_missing: {payload.get('repo_provenance_missing', 0)}",
            f"output: {payload.get('output', '-')}",
            f"review_status: {payload.get('review_status', '-')}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
        ]
    )


def format_ready_repair_chain_review_summary(payload: Mapping[str, Any]) -> str:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER ready repair-chain review",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', 0)}",
        f"repo_provenance_ready: {payload.get('repo_provenance_ready', 0)}",
        f"repo_provenance_missing: {payload.get('repo_provenance_missing', 0)}",
        "eval_approval_requires_repo_provenance: "
        f"{payload.get('eval_approval_requires_repo_provenance', False)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"groups: {len(groups)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- test_id={group.get('test_id', '-')} "
            f"plan_hash={group.get('plan_hash', '-')} "
            f"count={group.get('count', 0)} "
            f"repo_provenance_ready={group.get('repo_provenance_ready', 0)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_ready_repair_chain_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER ready repair-chain review artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"ready_artifacts: {payload.get('ready_artifacts', 0)}",
        f"records: {payload.get('records', 0)}",
        f"ready_for_human_review: {payload.get('ready_for_human_review', 0)}",
        f"repo_provenance_ready: {payload.get('repo_provenance_ready', 0)}",
        f"repo_provenance_missing: {payload.get('repo_provenance_missing', 0)}",
        "eval_approval_requires_repo_provenance: "
        f"{payload.get('eval_approval_requires_repo_provenance', False)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"ready={artifact.get('ready_for_human_review', 0)}",
                    f"groups={artifact.get('groups', 0)}",
                    f"repo_provenance_ready={artifact.get('repo_provenance_ready', 0)}",
                    f"min_repeat={artifact.get('min_repeat', 1)}",
                ]
            )
        )
    return "\n".join(lines)


def format_ready_repair_chain_decision_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER ready repair-chain decision export",
            f"decision: {payload.get('decision', '-')}",
            f"reviewer: {payload.get('reviewer', '-')}",
            f"records: {payload.get('records', 0)}",
            f"rejected_records: {payload.get('rejected_records', 0)}",
            f"repo_provenance_ready: {payload.get('repo_provenance_ready', 0)}",
            f"repo_provenance_missing: {payload.get('repo_provenance_missing', 0)}",
            "rejected_repo_provenance_ready: "
            f"{payload.get('rejected_repo_provenance_ready', 0)}",
            "rejected_repo_provenance_missing: "
            f"{payload.get('rejected_repo_provenance_missing', 0)}",
            "eval_approval_requires_repo_provenance: "
            f"{payload.get('eval_approval_requires_repo_provenance', False)}",
            f"output: {payload.get('output', '-')}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
            f"approved_for_training: {payload.get('approved_for_training', False)}",
        ]
    )


def format_ready_repair_chain_decision_review_summary(
    payload: Mapping[str, Any],
) -> str:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER ready repair-chain decision review",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"defer_records: {payload.get('defer_records', 0)}",
        f"reject_records: {payload.get('reject_records', 0)}",
        f"approved_for_eval_records: {payload.get('approved_for_eval_records', 0)}",
        f"decision_counts: {decision_counts}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"groups: {len(groups)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- decision={group.get('decision', '-')} "
            f"test_id={group.get('test_id', '-')} "
            f"plan_hash={group.get('plan_hash', '-')} "
            f"count={group.get('count', 0)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_ready_repair_chain_decision_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER ready repair-chain decision review artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"decision: {payload.get('decision') or '-'}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"records: {payload.get('records', 0)}",
        f"defer_records: {payload.get('defer_records', 0)}",
        f"reject_records: {payload.get('reject_records', 0)}",
        f"approved_for_eval_records: {payload.get('approved_for_eval_records', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"defer={artifact.get('defer_records', 0)}",
                    f"approved_for_eval={artifact.get('approved_for_eval_records', 0)}",
                    f"groups={artifact.get('groups', 0)}",
                ]
            )
        )
    return "\n".join(lines)


def format_ready_repair_chain_eval_candidate_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER ready repair-chain eval candidate export",
            f"records: {payload.get('records', 0)}",
            f"skipped_records: {payload.get('skipped_records', 0)}",
            f"rejected_records: {payload.get('rejected_records', 0)}",
            f"repo_provenance_ready: {payload.get('repo_provenance_ready', 0)}",
            f"repo_provenance_missing: {payload.get('repo_provenance_missing', 0)}",
            "skipped_repo_provenance_ready: "
            f"{payload.get('skipped_repo_provenance_ready', 0)}",
            "skipped_repo_provenance_missing: "
            f"{payload.get('skipped_repo_provenance_missing', 0)}",
            "eval_approval_requires_repo_provenance: "
            f"{payload.get('eval_approval_requires_repo_provenance', False)}",
            (
                "blocked_non_real_repo_records: "
                f"{payload.get('blocked_non_real_repo_records', 0)}"
            ),
            (
                "blocked_unconfirmed_real_repo_records: "
                f"{payload.get('blocked_unconfirmed_real_repo_records', 0)}"
            ),
            f"output: {payload.get('output', '-')}",
            f"eval_candidates: {payload.get('eval_candidates', 0)}",
            f"eval_dataset_ready: {payload.get('eval_dataset_ready', False)}",
            f"requires_dataset_review: {payload.get('requires_dataset_review', True)}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
            f"approved_for_training: {payload.get('approved_for_training', False)}",
        ]
    )


def format_ready_repair_chain_eval_candidate_review_summary(
    payload: Mapping[str, Any],
) -> str:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER ready repair-chain eval candidate review",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"ready_for_dataset_review: {payload.get('ready_for_dataset_review', 0)}",
        f"eval_dataset_ready_records: {payload.get('eval_dataset_ready_records', 0)}",
        f"repo_provenance_ready: {payload.get('repo_provenance_ready', 0)}",
        f"repo_provenance_missing: {payload.get('repo_provenance_missing', 0)}",
        "eval_approval_requires_repo_provenance: "
        f"{payload.get('eval_approval_requires_repo_provenance', False)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"groups: {len(groups)}",
        f"requires_dataset_review: {payload.get('requires_dataset_review', True)}",
        f"eval_dataset_ready: {payload.get('eval_dataset_ready', False)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- test_id={group.get('test_id', '-')} "
            f"plan_hash={group.get('plan_hash', '-')} "
            f"count={group.get('count', 0)} "
            f"repo_provenance_ready={group.get('repo_provenance_ready', 0)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_ready_repair_chain_eval_candidate_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER ready repair-chain eval-candidate review artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"records: {payload.get('records', 0)}",
        f"ready_for_dataset_review: {payload.get('ready_for_dataset_review', 0)}",
        f"repo_provenance_ready: {payload.get('repo_provenance_ready', 0)}",
        f"repo_provenance_missing: {payload.get('repo_provenance_missing', 0)}",
        "eval_approval_requires_repo_provenance: "
        f"{payload.get('eval_approval_requires_repo_provenance', False)}",
        f"eval_dataset_ready: {payload.get('eval_dataset_ready', False)}",
        f"requires_dataset_review: {payload.get('requires_dataset_review', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"ready={artifact.get('ready_for_dataset_review', 0)}",
                    f"groups={artifact.get('groups', 0)}",
                    f"repo_provenance_ready={artifact.get('repo_provenance_ready', 0)}",
                    f"min_repeat={artifact.get('min_repeat', 1)}",
                ]
            )
        )
    return "\n".join(lines)


def format_ready_repair_chain_eval_candidate_decision_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER ready repair-chain eval candidate decision export",
            f"decision: {payload.get('decision', '-')}",
            f"reviewer: {payload.get('reviewer', '-')}",
            f"records: {payload.get('records', 0)}",
            f"rejected_records: {payload.get('rejected_records', 0)}",
            f"approved_for_eval_dataset_records: {payload.get('approved_for_eval_dataset_records', 0)}",
            f"output: {payload.get('output', '-')}",
            f"eval_dataset_ready: {payload.get('eval_dataset_ready', False)}",
            f"requires_dataset_review: {payload.get('requires_dataset_review', True)}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
            f"approved_for_training: {payload.get('approved_for_training', False)}",
        ]
    )


def format_ready_repair_chain_eval_dataset_decision_review_summary(
    payload: Mapping[str, Any],
) -> str:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER ready repair-chain eval dataset decision review",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"defer_records: {payload.get('defer_records', 0)}",
        f"reject_records: {payload.get('reject_records', 0)}",
        f"approved_for_eval_dataset_records: {payload.get('approved_for_eval_dataset_records', 0)}",
        f"eval_dataset_ready_records: {payload.get('eval_dataset_ready_records', 0)}",
        f"decision_counts: {decision_counts}",
        f"review_status: {payload.get('review_status', '-')}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"groups: {len(groups)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- decision={group.get('decision', '-')} "
            f"test_id={group.get('test_id', '-')} "
            f"plan_hash={group.get('plan_hash', '-')} "
            f"count={group.get('count', 0)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_ready_repair_chain_eval_dataset_decision_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        (
            "BIBER ready repair-chain eval-dataset decision review "
            f"artifacts ({len(artifacts)})"
        ),
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"decision: {payload.get('decision') or '-'}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"records: {payload.get('records', 0)}",
        f"defer_records: {payload.get('defer_records', 0)}",
        f"reject_records: {payload.get('reject_records', 0)}",
        f"approved_for_eval_dataset_records: {payload.get('approved_for_eval_dataset_records', 0)}",
        f"eval_dataset_ready_records: {payload.get('eval_dataset_ready_records', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"eval_ready={artifact.get('eval_dataset_ready_records', 0)}",
                    (
                        "approved_for_eval_dataset="
                        f"{artifact.get('approved_for_eval_dataset_records', 0)}"
                    ),
                    f"groups={artifact.get('groups', 0)}",
                ]
            )
        )
    return "\n".join(lines)


def format_ready_repair_chain_eval_dataset_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER ready repair-chain eval dataset export",
            f"records: {payload.get('records', 0)}",
            f"skipped_records: {payload.get('skipped_records', 0)}",
            f"rejected_records: {payload.get('rejected_records', 0)}",
            f"eval_dataset_records: {payload.get('eval_dataset_records', 0)}",
            f"eval_dataset_ready: {payload.get('eval_dataset_ready', False)}",
            (
                "requires_eval_dataset_validation: "
                f"{payload.get('requires_eval_dataset_validation', True)}"
            ),
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
            f"approved_for_training: {payload.get('approved_for_training', False)}",
            f"output: {payload.get('output', '-')}",
        ]
    )


def format_ready_repair_chain_eval_dataset_validation_summary(
    payload: Mapping[str, Any],
) -> str:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER ready repair-chain eval dataset validation",
        f"ok: {payload.get('ok', False)}",
        f"validation_status: {payload.get('validation_status', '-')}",
        f"records: {payload.get('records', 0)}",
        f"valid_records: {payload.get('valid_records', 0)}",
        f"invalid_records: {payload.get('invalid_records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"min_records: {payload.get('min_records', 1)}",
        f"groups: {len(groups)}",
        f"eval_dataset_ready: {payload.get('eval_dataset_ready', False)}",
        (
            "requires_eval_dataset_validation: "
            f"{payload.get('requires_eval_dataset_validation', True)}"
        ),
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- test_id={group.get('test_id', '-')} "
            f"plan_hash={group.get('plan_hash', '-')} "
            f"count={group.get('count', 0)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_ready_repair_chain_eval_dataset_validation_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER ready repair-chain eval-dataset validation artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ok_only: {payload.get('ok_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"ok_artifacts: {payload.get('ok_artifacts', 0)}",
        f"records: {payload.get('records', 0)}",
        f"valid_records: {payload.get('valid_records', 0)}",
        f"invalid_records: {payload.get('invalid_records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"eval_dataset_ready: {payload.get('eval_dataset_ready', False)}",
        (
            "requires_eval_dataset_validation: "
            f"{payload.get('requires_eval_dataset_validation', True)}"
        ),
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('validation_status', '-')}",
                    f"ok={artifact.get('ok', False)}",
                    f"records={artifact.get('records', 0)}",
                    f"valid={artifact.get('valid_records', 0)}",
                    f"invalid={artifact.get('invalid_records', 0)}",
                    f"groups={artifact.get('groups', 0)}",
                ]
            )
        )
    return "\n".join(lines)


def format_ready_repair_chain_eval_prompt_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER ready repair-chain eval prompt export",
            f"records: {payload.get('records', 0)}",
            f"skipped_records: {payload.get('skipped_records', 0)}",
            f"rejected_records: {payload.get('rejected_records', 0)}",
            f"eval_prompts: {payload.get('eval_prompts', 0)}",
            f"eval_only: {payload.get('eval_only', True)}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
            f"approved_for_training: {payload.get('approved_for_training', False)}",
            f"output: {payload.get('output', '-')}",
        ]
    )


def format_ready_repair_chain_eval_prompt_inspection_summary(
    payload: Mapping[str, Any],
) -> str:
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER ready repair-chain eval prompts",
        f"ok: {payload.get('ok', False)}",
        f"inspection_status: {payload.get('inspection_status', '-')}",
        f"records: {payload.get('records', 0)}",
        f"valid_records: {payload.get('valid_records', 0)}",
        f"invalid_records: {payload.get('invalid_records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"eval_prompts: {payload.get('eval_prompts', 0)}",
        f"eval_prompt_ready_records: {payload.get('eval_prompt_ready_records', 0)}",
        f"min_records: {payload.get('min_records', 1)}",
        f"language_counts: {payload.get('language_counts', {})}",
        f"task_type_counts: {payload.get('task_type_counts', {})}",
        f"groups: {len(groups)}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"jsonl_paths: {payload.get('jsonl_paths', [])}",
    ]
    lines.extend(
        (
            f"- test_id={group.get('test_id', '-')} "
            f"plan_hash={group.get('plan_hash', '-')} "
            f"count={group.get('count', 0)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_ready_repair_chain_eval_prompt_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER ready repair-chain eval prompt artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"ok_artifacts: {payload.get('ok_artifacts', 0)}",
        f"records: {payload.get('records', 0)}",
        f"valid_records: {payload.get('valid_records', 0)}",
        f"invalid_records: {payload.get('invalid_records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"eval_prompts: {payload.get('eval_prompts', 0)}",
        f"eval_prompt_ready_records: {payload.get('eval_prompt_ready_records', 0)}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('inspection_status', '-')}",
                    f"ok={artifact.get('ok', False)}",
                    f"records={artifact.get('records', 0)}",
                    f"valid={artifact.get('valid_records', 0)}",
                    f"eval_prompts={artifact.get('eval_prompts', 0)}",
                    f"groups={artifact.get('groups', 0)}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_chain_heldout_eval_review_summary(
    payload: Mapping[str, Any],
) -> str:
    results = [
        item
        for item in require_list(payload.get("results"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair-chain held-out eval review",
        f"ok: {payload.get('ok', False)}",
        f"review_status: {payload.get('review_status', '-')}",
        f"records: {payload.get('records', 0)}",
        f"passed_records: {payload.get('passed_records', 0)}",
        f"failed_records: {payload.get('failed_records', 0)}",
        f"expectation_failed_records: {payload.get('expectation_failed_records', 0)}",
        f"validation_failed_records: {payload.get('validation_failed_records', 0)}",
        f"error_records: {payload.get('error_records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"min_passes: {payload.get('min_passes', 1)}",
        f"model_counts: {payload.get('model_counts', {})}",
        f"summary_path: {payload.get('summary_path', '-')}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- id={result.get('id', '-')} "
            f"passed={result.get('passed', False)} "
            f"expectation_ok={result.get('expectation_ok', False)} "
            f"model={result.get('model', '-')}"
        )
        for result in results[:8]
    )
    return "\n".join(lines)


def format_repair_chain_heldout_eval_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair-chain held-out eval review artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ok_only: {payload.get('ok_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"ok_artifacts: {payload.get('ok_artifacts', 0)}",
        f"records: {payload.get('records', 0)}",
        f"passed_records: {payload.get('passed_records', 0)}",
        f"failed_records: {payload.get('failed_records', 0)}",
        (
            "expectation_failed_records: "
            f"{payload.get('expectation_failed_records', 0)}"
        ),
        (
            "validation_failed_records: "
            f"{payload.get('validation_failed_records', 0)}"
        ),
        f"error_records: {payload.get('error_records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"model_counts: {payload.get('model_counts', {})}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"ok={artifact.get('ok', False)}",
                    f"records={artifact.get('records', 0)}",
                    f"passed={artifact.get('passed_records', 0)}",
                    f"failed={artifact.get('failed_records', 0)}",
                    f"results={artifact.get('result_count', 0)}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_chain_heldout_eval_decision_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER repair-chain held-out eval decision export",
            f"decision: {payload.get('decision', '-')}",
            f"reviewer: {payload.get('reviewer', '-')}",
            f"records: {payload.get('records', 0)}",
            f"rejected_records: {payload.get('rejected_records', 0)}",
            (
                "accepted_for_baseline_records: "
                f"{payload.get('accepted_for_baseline_records', 0)}"
            ),
            f"baseline_candidate_ready: {payload.get('baseline_candidate_ready', False)}",
            f"eval_only: {payload.get('eval_only', True)}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
            f"approved_for_training: {payload.get('approved_for_training', False)}",
            f"output: {payload.get('output', '-')}",
        ]
    )


def format_repair_chain_heldout_eval_decision_review_summary(
    payload: Mapping[str, Any],
) -> str:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair-chain held-out eval decision review",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"defer_records: {payload.get('defer_records', 0)}",
        f"reject_records: {payload.get('reject_records', 0)}",
        f"accepted_for_baseline_records: {payload.get('accepted_for_baseline_records', 0)}",
        (
            "baseline_candidate_ready_records: "
            f"{payload.get('baseline_candidate_ready_records', 0)}"
        ),
        f"follow_up_records: {payload.get('follow_up_records', 0)}",
        f"decision_counts: {decision_counts}",
        f"review_status: {payload.get('review_status', '-')}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"groups: {len(groups)}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- decision={group.get('decision', '-')} "
            f"count={group.get('count', 0)} "
            f"baseline_ready={group.get('baseline_candidate_ready', False)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_repair_chain_heldout_eval_decision_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair-chain held-out eval decision review artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"decision: {payload.get('decision', '-')}",
        f"baseline_ready_only: {payload.get('baseline_ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"records: {payload.get('records', 0)}",
        f"defer_records: {payload.get('defer_records', 0)}",
        f"reject_records: {payload.get('reject_records', 0)}",
        f"accepted_for_baseline_records: {payload.get('accepted_for_baseline_records', 0)}",
        (
            "baseline_candidate_ready_records: "
            f"{payload.get('baseline_candidate_ready_records', 0)}"
        ),
        f"follow_up_records: {payload.get('follow_up_records', 0)}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"defer={artifact.get('defer_records', 0)}",
                    f"reject={artifact.get('reject_records', 0)}",
                    f"accepted={artifact.get('accepted_for_baseline_records', 0)}",
                    f"baseline_ready={artifact.get('baseline_candidate_ready_records', 0)}",
                    f"groups={artifact.get('groups', 0)}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_chain_heldout_baseline_candidate_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER repair-chain held-out baseline candidate export",
            f"records: {payload.get('records', 0)}",
            f"skipped_records: {payload.get('skipped_records', 0)}",
            f"rejected_records: {payload.get('rejected_records', 0)}",
            f"baseline_candidates: {payload.get('baseline_candidates', 0)}",
            (
                "accepted_for_baseline_records: "
                f"{payload.get('accepted_for_baseline_records', 0)}"
            ),
            f"baseline_candidate_ready: {payload.get('baseline_candidate_ready', False)}",
            f"baseline_ready: {payload.get('baseline_ready', False)}",
            f"requires_baseline_review: {payload.get('requires_baseline_review', False)}",
            f"eval_only: {payload.get('eval_only', True)}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
            f"approved_for_training: {payload.get('approved_for_training', False)}",
            f"output: {payload.get('output', '-')}",
        ]
    )


def format_repair_chain_heldout_baseline_candidate_review_summary(
    payload: Mapping[str, Any],
) -> str:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair-chain held-out baseline candidate review",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"baseline_candidates: {payload.get('baseline_candidates', 0)}",
        f"accepted_for_baseline_records: {payload.get('accepted_for_baseline_records', 0)}",
        (
            "baseline_candidate_ready_records: "
            f"{payload.get('baseline_candidate_ready_records', 0)}"
        ),
        f"baseline_ready_records: {payload.get('baseline_ready_records', 0)}",
        (
            "requires_baseline_review_records: "
            f"{payload.get('requires_baseline_review_records', 0)}"
        ),
        f"decision_counts: {decision_counts}",
        f"review_status: {payload.get('review_status', '-')}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"groups: {len(groups)}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- decision={group.get('decision', '-')} "
            f"count={group.get('count', 0)} "
            f"baseline_ready={group.get('baseline_ready', False)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_repair_chain_heldout_baseline_candidate_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        (
            "BIBER repair-chain held-out baseline candidate review artifacts "
            f"({len(artifacts)})"
        ),
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"candidate_ready_only: {payload.get('candidate_ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"baseline_candidates: {payload.get('baseline_candidates', 0)}",
        f"accepted_for_baseline_records: {payload.get('accepted_for_baseline_records', 0)}",
        (
            "baseline_candidate_ready_records: "
            f"{payload.get('baseline_candidate_ready_records', 0)}"
        ),
        f"baseline_ready_records: {payload.get('baseline_ready_records', 0)}",
        (
            "requires_baseline_review_records: "
            f"{payload.get('requires_baseline_review_records', 0)}"
        ),
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"candidates={artifact.get('baseline_candidates', 0)}",
                    (
                        "candidate_ready="
                        f"{artifact.get('baseline_candidate_ready_records', 0)}"
                    ),
                    f"baseline_ready={artifact.get('baseline_ready_records', 0)}",
                    (
                        "requires_review="
                        f"{artifact.get('requires_baseline_review_records', 0)}"
                    ),
                    f"groups={artifact.get('groups', 0)}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_chain_heldout_baseline_decision_export_summary(
    payload: Mapping[str, Any],
) -> str:
    return "\n".join(
        [
            "BIBER repair-chain held-out baseline decision export",
            f"decision: {payload.get('decision', '-')}",
            f"reviewer: {payload.get('reviewer', '-')}",
            f"records: {payload.get('records', 0)}",
            f"rejected_records: {payload.get('rejected_records', 0)}",
            (
                "approved_as_baseline_records: "
                f"{payload.get('approved_as_baseline_records', 0)}"
            ),
            f"baseline_ready: {payload.get('baseline_ready', False)}",
            f"requires_baseline_review: {payload.get('requires_baseline_review', True)}",
            f"eval_only: {payload.get('eval_only', True)}",
            f"training_allowed: {payload.get('training_allowed', False)}",
            f"safe_to_train: {payload.get('safe_to_train', False)}",
            f"github_save_ready: {payload.get('github_save_ready', False)}",
            f"approved_for_training: {payload.get('approved_for_training', False)}",
            f"output: {payload.get('output', '-')}",
        ]
    )


def format_repair_chain_heldout_baseline_decision_review_summary(
    payload: Mapping[str, Any],
) -> str:
    decision_counts = payload.get("decision_counts")
    if not isinstance(decision_counts, dict):
        decision_counts = {}
    groups = [
        item
        for item in require_list(payload.get("groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair-chain held-out baseline decision review",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"defer_records: {payload.get('defer_records', 0)}",
        f"reject_records: {payload.get('reject_records', 0)}",
        f"approved_as_baseline_records: {payload.get('approved_as_baseline_records', 0)}",
        (
            "baseline_candidate_ready_records: "
            f"{payload.get('baseline_candidate_ready_records', 0)}"
        ),
        f"baseline_ready_records: {payload.get('baseline_ready_records', 0)}",
        (
            "requires_baseline_review_records: "
            f"{payload.get('requires_baseline_review_records', 0)}"
        ),
        f"decision_counts: {decision_counts}",
        f"review_status: {payload.get('review_status', '-')}",
        f"min_repeat: {payload.get('min_repeat', 1)}",
        f"groups: {len(groups)}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- decision={group.get('decision', '-')} "
            f"count={group.get('count', 0)} "
            f"baseline_ready={group.get('baseline_ready', False)}"
        )
        for group in groups[:8]
    )
    return "\n".join(lines)


def format_repair_chain_heldout_baseline_decision_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        (
            "BIBER repair-chain held-out baseline decision review artifacts "
            f"({len(artifacts)})"
        ),
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"decision: {payload.get('decision', '-')}",
        f"baseline_ready_only: {payload.get('baseline_ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"records: {payload.get('records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"defer_records: {payload.get('defer_records', 0)}",
        f"reject_records: {payload.get('reject_records', 0)}",
        f"approved_as_baseline_records: {payload.get('approved_as_baseline_records', 0)}",
        (
            "baseline_candidate_ready_records: "
            f"{payload.get('baseline_candidate_ready_records', 0)}"
        ),
        f"baseline_ready_records: {payload.get('baseline_ready_records', 0)}",
        (
            "requires_baseline_review_records: "
            f"{payload.get('requires_baseline_review_records', 0)}"
        ),
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"approved={artifact.get('approved_as_baseline_records', 0)}",
                    (
                        "candidate_ready="
                        f"{artifact.get('baseline_candidate_ready_records', 0)}"
                    ),
                    f"baseline_ready={artifact.get('baseline_ready_records', 0)}",
                    (
                        "requires_review="
                        f"{artifact.get('requires_baseline_review_records', 0)}"
                    ),
                    f"groups={artifact.get('groups', 0)}",
                ]
            )
        )
    return "\n".join(lines)


def format_repair_chain_training_readiness_summary(
    payload: Mapping[str, Any],
) -> str:
    hard_blockers = [
        str(item)
        for item in require_list(payload.get("hard_blockers"))
        if item
    ]
    manual_actions = [
        str(item)
        for item in require_list(payload.get("required_manual_actions"))
        if item
    ]
    ready_groups = [
        item
        for item in require_list(payload.get("baseline_ready_groups"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair-chain training readiness review",
        f"review_status: {payload.get('review_status', '-')}",
        f"training_gate_status: {payload.get('training_gate_status', '-')}",
        f"review_artifacts: {payload.get('review_artifacts', 0)}",
        f"supported_review_artifacts: {payload.get('supported_review_artifacts', 0)}",
        f"rejected_artifacts: {payload.get('rejected_artifacts', 0)}",
        f"min_baseline_ready: {payload.get('min_baseline_ready', 1)}",
        f"baseline_ready_records: {payload.get('baseline_ready_records', 0)}",
        (
            "approved_as_baseline_records: "
            f"{payload.get('approved_as_baseline_records', 0)}"
        ),
        (
            "ready_for_manual_training_dataset_review: "
            f"{payload.get('ready_for_manual_training_dataset_review', False)}"
        ),
        (
            "hard_blockers: "
            f"{', '.join(hard_blockers) if hard_blockers else '-'}"
        ),
        (
            "required_manual_actions: "
            f"{', '.join(manual_actions) if manual_actions else '-'}"
        ),
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        (
            f"- decision={group.get('decision', '-')} "
            f"count={group.get('count', 0)} "
            f"ids={','.join(str(item) for item in require_list(group.get('heldout_eval_result_ids')))}"
        )
        for group in ready_groups[:8]
    )
    return "\n".join(lines)


def format_repair_chain_training_readiness_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair-chain training readiness artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"review_artifacts: {payload.get('review_artifacts', 0)}",
        f"supported_review_artifacts: {payload.get('supported_review_artifacts', 0)}",
        f"rejected_artifacts: {payload.get('rejected_artifacts', 0)}",
        f"records: {payload.get('records', 0)}",
        f"approved_as_baseline_records: {payload.get('approved_as_baseline_records', 0)}",
        (
            "baseline_candidate_ready_records: "
            f"{payload.get('baseline_candidate_ready_records', 0)}"
        ),
        f"baseline_ready_records: {payload.get('baseline_ready_records', 0)}",
        (
            "requires_baseline_review_records: "
            f"{payload.get('requires_baseline_review_records', 0)}"
        ),
        (
            "ready_for_manual_training_dataset_review_records: "
            f"{payload.get('ready_for_manual_training_dataset_review_records', 0)}"
        ),
        f"blocked_records: {payload.get('blocked_records', 0)}",
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        hard_blockers = [
            str(item)
            for item in require_list(artifact.get("hard_blockers"))
            if item
        ]
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"gate={artifact.get('training_gate_status', '-')}",
                    f"baseline_ready={artifact.get('baseline_ready_records', 0)}",
                    (
                        "manual_review_ready="
                        f"{artifact.get('ready_for_manual_training_dataset_review', False)}"
                    ),
                    (
                        "hard_blockers="
                        f"{','.join(hard_blockers) if hard_blockers else '-'}"
                    ),
                ]
            )
        )
    return "\n".join(lines)


def format_repair_chain_training_candidate_export_summary(
    payload: Mapping[str, Any],
) -> str:
    hard_blockers = [
        str(item)
        for item in require_list(payload.get("hard_blockers"))
        if item
    ]
    lines = [
        "BIBER repair-chain training candidate export",
        f"export_status: {payload.get('export_status', '-')}",
        f"records: {payload.get('records', 0)}",
        f"training_candidate_records: {payload.get('training_candidate_records', 0)}",
        f"review_artifacts: {payload.get('review_artifacts', 0)}",
        f"supported_review_artifacts: {payload.get('supported_review_artifacts', 0)}",
        f"skipped_artifacts: {payload.get('skipped_artifacts', 0)}",
        f"rejected_artifacts: {payload.get('rejected_artifacts', 0)}",
        (
            "hard_blockers: "
            f"{', '.join(hard_blockers) if hard_blockers else '-'}"
        ),
        (
            "requires_human_training_dataset_review: "
            f"{payload.get('requires_human_training_dataset_review', False)}"
        ),
        f"training_dataset_ready: {payload.get('training_dataset_ready', False)}",
        f"review_queue_only: {payload.get('review_queue_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"output: {payload.get('output', '-')}",
    ]
    return "\n".join(lines)


def format_repair_chain_training_candidate_review_summary(
    payload: Mapping[str, Any],
) -> str:
    hard_blockers = [
        str(item)
        for item in require_list(payload.get("hard_blockers"))
        if item
    ]
    quality_counts = payload.get("quality_counts")
    if not isinstance(quality_counts, dict):
        quality_counts = {}
    lines = [
        "BIBER repair-chain training candidate review",
        f"review_status: {payload.get('review_status', '-')}",
        f"records: {payload.get('records', 0)}",
        f"reviewed_records: {payload.get('reviewed_records', 0)}",
        f"pending_review_records: {payload.get('pending_review_records', 0)}",
        f"empty_output_records: {payload.get('empty_output_records', 0)}",
        f"unreviewed_quality_records: {payload.get('unreviewed_quality_records', 0)}",
        f"rejected_records: {payload.get('rejected_records', 0)}",
        f"quality_counts: {quality_counts}",
        f"min_ready: {payload.get('min_ready', 1)}",
        (
            "ready_for_dataset_validation: "
            f"{payload.get('ready_for_dataset_validation', False)}"
        ),
        f"training_dataset_ready: {payload.get('training_dataset_ready', False)}",
        (
            "hard_blockers: "
            f"{', '.join(hard_blockers) if hard_blockers else '-'}"
        ),
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    return "\n".join(lines)


def format_repair_chain_training_candidate_review_artifact_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        f"BIBER repair-chain training candidate review artifacts ({len(artifacts)})",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        f"records: {payload.get('records', 0)}",
        f"reviewed_records: {payload.get('reviewed_records', 0)}",
        f"pending_review_records: {payload.get('pending_review_records', 0)}",
        f"empty_output_records: {payload.get('empty_output_records', 0)}",
        (
            "unreviewed_quality_records: "
            f"{payload.get('unreviewed_quality_records', 0)}"
        ),
        f"rejected_records: {payload.get('rejected_records', 0)}",
        (
            "ready_for_dataset_validation_records: "
            f"{payload.get('ready_for_dataset_validation_records', 0)}"
        ),
        f"blocked_records: {payload.get('blocked_records', 0)}",
        f"training_dataset_ready: {payload.get('training_dataset_ready', False)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
    ]
    for artifact in artifacts:
        hard_blockers = [
            str(item)
            for item in require_list(artifact.get("hard_blockers"))
            if item
        ]
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('review_status', '-')}",
                    f"records={artifact.get('records', 0)}",
                    f"reviewed={artifact.get('reviewed_records', 0)}",
                    f"pending={artifact.get('pending_review_records', 0)}",
                    (
                        "ready_for_dataset_validation="
                        f"{artifact.get('ready_for_dataset_validation', False)}"
                    ),
                    (
                        "hard_blockers="
                        f"{','.join(hard_blockers) if hard_blockers else '-'}"
                    ),
                ]
            )
        )
    return "\n".join(lines)


def format_repair_chain_training_pipeline_status_summary(
    payload: Mapping[str, Any],
) -> str:
    hard_blockers = [
        str(item)
        for item in require_list(payload.get("hard_blockers"))
        if item
    ]
    lines = [
        "BIBER repair-chain training pipeline status",
        f"training_pipeline_status: {payload.get('training_pipeline_status', '-')}",
        f"missing_or_blocked_step: {payload.get('missing_or_blocked_step', '-')}",
        f"baseline_ready_records: {payload.get('baseline_ready_records', 0)}",
        f"training_gate_status: {payload.get('training_gate_status', '-')}",
        (
            "ready_for_manual_training_dataset_review: "
            f"{payload.get('ready_for_manual_training_dataset_review', False)}"
        ),
        f"training_candidate_records: {payload.get('training_candidate_records', 0)}",
        (
            "training_candidate_review_records: "
            f"{payload.get('training_candidate_review_records', 0)}"
        ),
        (
            "ready_for_dataset_validation: "
            f"{payload.get('ready_for_dataset_validation', False)}"
        ),
        (
            "hard_blockers: "
            f"{', '.join(hard_blockers) if hard_blockers else '-'}"
        ),
        f"eval_only: {payload.get('eval_only', True)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
        f"approved_for_training: {payload.get('approved_for_training', False)}",
        f"artifact_dir: {payload.get('artifact_dir', '-')}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    return "\n".join(lines)


def format_repair_chain_training_pipeline_list_summary(
    payload: Mapping[str, Any],
) -> str:
    artifacts = [
        item
        for item in require_list(payload.get("artifacts"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER repair-chain training pipeline artifacts",
        f"directory: {payload.get('directory', '-')}",
        f"pattern: {payload.get('pattern', '-')}",
        f"ready_only: {payload.get('ready_only', False)}",
        f"scanned: {payload.get('scanned', 0)}",
        f"matched: {payload.get('matched', 0)}",
        (
            "ready_for_dataset_validation: "
            f"{payload.get('ready_for_dataset_validation', 0)}"
        ),
        f"blocked: {payload.get('blocked', 0)}",
        f"training_allowed: {payload.get('training_allowed', False)}",
        f"safe_to_train: {payload.get('safe_to_train', False)}",
        f"github_save_ready: {payload.get('github_save_ready', False)}",
    ]
    for artifact in artifacts:
        blockers = [
            str(item)
            for item in require_list(artifact.get("hard_blockers"))
            if item
        ]
        lines.append(
            " ".join(
                [
                    f"- {artifact.get('path', '-')}",
                    f"status={artifact.get('training_pipeline_status', '-')}",
                    f"blocked_step={artifact.get('missing_or_blocked_step', '-')}",
                    f"baseline_ready={artifact.get('baseline_ready_records', 0)}",
                    f"candidates={artifact.get('training_candidate_records', 0)}",
                    f"ready={artifact.get('ready_for_dataset_validation', False)}",
                    f"blockers={','.join(blockers) if blockers else '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_test_list_summary(payload: Mapping[str, Any]) -> str:
    commands = [
        command
        for command in require_list(payload.get("commands"))
        if isinstance(command, dict)
    ]
    lines = [f"BIBER allowlisted tests ({len(commands)})"]
    for command in commands:
        argv = " ".join(str(part) for part in require_list(command.get("command")))
        lines.append(
            " ".join(
                [
                    f"- {command.get('test_id', '-')}:",
                    str(command.get("label", "-")),
                    f"cwd={command.get('cwd', '-')}",
                    f"command={argv or '-'}",
                ]
            )
        )
    return "\n".join(lines)


def format_test_run_summary(payload: Mapping[str, Any]) -> str:
    command = " ".join(str(part) for part in require_list(payload.get("command")))
    lines = [
        "BIBER test run",
        f"test_id: {payload.get('test_id', '-')}",
        f"label: {payload.get('label', '-')}",
        f"executed: {bool(payload.get('executed'))}",
        f"ok: {payload.get('ok')}",
        f"exit_code: {payload.get('exit_code')}",
        f"timed_out: {bool(payload.get('timed_out'))}",
        f"duration_ms: {payload.get('duration_ms', 0)}",
        f"cwd: {payload.get('cwd', '-')}",
        f"command: {command or '-'}",
    ]
    diagnosis = payload.get("diagnosis")
    if isinstance(diagnosis, dict):
        lines.extend(
            [
                f"diagnosis: {diagnosis.get('summary', '-')}",
                f"primary_category: {diagnosis.get('primary_category', '-')}",
                f"detected_stack: {diagnosis.get('detected_stack', '-')}",
            ]
        )
    return "\n".join(lines)


def format_test_diagnosis_summary(payload: Mapping[str, Any]) -> str:
    signals = [
        signal
        for signal in require_list(payload.get("signals"))
        if isinstance(signal, dict)
    ]
    lines = [
        "BIBER test failure diagnosis",
        f"has_failure: {bool(payload.get('has_failure'))}",
        f"primary_category: {payload.get('primary_category', '-')}",
        f"detected_stack: {payload.get('detected_stack', '-')}",
        f"summary: {payload.get('summary', '-')}",
        f"signals ({len(signals)}):",
    ]
    lines.extend(
        (
            f"- {signal.get('category', '-')} stack={signal.get('stack', '-')} "
            f"line={signal.get('line_number')} evidence={signal.get('evidence', '-')}"
        )
        for signal in signals[:8]
    )
    actions = [str(action) for action in require_list(payload.get("suggested_next_actions"))]
    if actions:
        lines.append("suggested_next_actions:")
        lines.extend(f"- {action}" for action in actions)
    return "\n".join(lines)


def format_workspace_edit_plan_summary(payload: Mapping[str, Any]) -> str:
    planned = [
        item
        for item in require_list(payload.get("planned"))
        if isinstance(item, dict)
    ]
    rejected = [
        item
        for item in require_list(payload.get("rejected"))
        if isinstance(item, dict)
    ]
    review = payload.get("review")
    review_payload = review if isinstance(review, Mapping) else {}
    ready_for_apply = review_payload.get("ready_for_apply")
    ready_for_apply_text = (
        str(ready_for_apply) if isinstance(ready_for_apply, bool) else "-"
    )
    lines = [
        "BIBER workspace edit plan",
        f"ok: {bool(payload.get('ok'))}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"summary: {payload.get('summary', '-')}",
        f"review_status: {review_payload.get('review_status', '-')}",
        f"ready_for_apply: {ready_for_apply_text}",
        f"planned ({len(planned)}):",
    ]
    lines.extend(
        (
            f"- {item.get('path', '-')} operation={item.get('operation', '-')} "
            f"risk={item.get('risk_level', '-')} changed={item.get('changed', False)}"
        )
        for item in planned
    )
    if rejected:
        lines.append(f"rejected ({len(rejected)}):")
        lines.extend(
            f"- {item.get('path', '-')} error={item.get('error', '-')}"
            for item in rejected
        )
    warnings = [str(item) for item in require_list(review_payload.get("warnings"))]
    hard_blockers = [
        str(item) for item in require_list(review_payload.get("hard_blockers"))
    ]
    if warnings:
        lines.append("review_warnings:")
        lines.extend(f"- {warning}" for warning in warnings[:8])
    if hard_blockers:
        lines.append("review_hard_blockers:")
        lines.extend(f"- {blocker}" for blocker in hard_blockers[:8])
    return "\n".join(lines)


def format_workspace_edit_apply_summary(payload: Mapping[str, Any]) -> str:
    applied = [
        item
        for item in require_list(payload.get("applied"))
        if isinstance(item, dict)
    ]
    lines = [
        "BIBER workspace edit apply",
        f"ok: {bool(payload.get('ok'))}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"summary: {payload.get('summary', '-')}",
        f"applied ({len(applied)}):",
    ]
    lines.extend(
        f"- {item.get('path', '-')} changed={item.get('changed', False)}"
        for item in applied
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

    chat = subparsers.add_parser(
        "chat",
        help="Send one direct /v1/chat request to BIBER.",
    )
    chat.add_argument("--message")
    chat.add_argument("--message-file")
    chat.add_argument("--model")
    chat.add_argument("--language")
    chat.add_argument("--task-type")
    chat.add_argument("--repo-context", action="append", default=None)
    chat.add_argument("--runtime-profile-id", action="append", default=None)
    chat.add_argument("--max-tokens", type=int)
    chat.add_argument("--temperature", type=float, default=0.2)
    chat.add_argument(
        "--use-mentor",
        action="store_true",
        help="Allow OpenAI mentor use when the server is configured and the prompt requests it.",
    )

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
    session.add_argument("--runtime-profile-id", action="append", default=None)
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

    plan_context = subparsers.add_parser(
        "plan-context",
        help="Ask BIBER to select safe repo context paths for a task.",
    )
    plan_context.add_argument("--instruction")
    plan_context.add_argument("--pinned-path", action="append", default=None)
    plan_context.add_argument("--changed-path", action="append", default=None)
    plan_context.add_argument("--max-files", type=int)
    plan_context.add_argument("--max-scan-files", type=int)

    plan_edit = subparsers.add_parser(
        "plan-edit",
        help="Validate a bounded workspace edit plan without writing files.",
    )
    plan_edit.add_argument("--edit-json", action="append", default=None)
    plan_edit.add_argument("--edits-file")
    plan_edit.add_argument("--max-files", type=int)

    apply_edit = subparsers.add_parser(
        "apply-edit",
        help="Apply a clean workspace edit plan using a fresh plan hash.",
    )
    apply_edit.add_argument("--edit-json", action="append", default=None)
    apply_edit.add_argument("--edits-file")
    apply_edit.add_argument("--max-files", type=int)
    apply_edit.add_argument("--plan-hash", required=True)

    subparsers.add_parser(
        "list-tests",
        help="List server-side allowlisted test commands.",
    )

    run_test = subparsers.add_parser(
        "run-test",
        help="Run one server-side allowlisted test command.",
    )
    run_test.add_argument("--test-id", required=True)
    run_test.add_argument("--dry-run", action="store_true")
    run_test.add_argument(
        "--diagnose-on-failure",
        action="store_true",
        help="Call /v1/tests/diagnose when the test executes and fails.",
    )
    run_test.add_argument("--max-context-lines", type=int)

    diagnose_test = subparsers.add_parser(
        "diagnose-test",
        help="Classify raw test output without calling a model.",
    )
    diagnose_test.add_argument("--test-id")
    diagnose_test.add_argument("--command-json")
    diagnose_test.add_argument("--command-part", action="append", default=None)
    diagnose_test.add_argument("--exit-code", type=int)
    diagnose_test.add_argument("--timed-out", action="store_true")
    diagnose_test.add_argument("--stdout")
    diagnose_test.add_argument("--stderr")
    diagnose_test.add_argument("--stdout-file")
    diagnose_test.add_argument("--stderr-file")
    diagnose_test.add_argument("--max-context-lines", type=int)

    save_github = subparsers.add_parser(
        "save-github",
        help="Save generated text through BIBER's configured GitHub workflow.",
    )
    save_github.add_argument("--path", required=True)
    save_github.add_argument("--content")
    save_github.add_argument("--content-file")
    save_github.add_argument("--owner")
    save_github.add_argument("--repo")
    save_github.add_argument("--branch", default="main")
    save_github.add_argument("--base-branch")
    save_github.add_argument("--create-branch-if-missing", action="store_true")
    save_github.add_argument(
        "--commit-message",
        default="Save BIBER generated code",
    )
    save_github.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the GitHub save payload without resolving API auth.",
    )

    create_pr = subparsers.add_parser(
        "create-pr",
        help="Create a GitHub pull request through BIBER's configured workflow.",
    )
    create_pr.add_argument("--head", required=True)
    create_pr.add_argument("--base", default="main")
    create_pr.add_argument("--title", required=True)
    create_pr.add_argument("--body", default=None)
    create_pr.add_argument("--body-file")
    create_pr.add_argument("--owner")
    create_pr.add_argument("--repo")
    create_pr.add_argument("--ready", action="store_true", help="Create a non-draft PR.")
    create_pr.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and print the pull-request payload without resolving API auth.",
    )

    mvp_loop = subparsers.add_parser(
        "mvp-loop",
        help=(
            "Run a bounded MVP client flow: context, optional edits, optional "
            "test/diagnosis, optional GitHub save/PR."
        ),
    )
    mvp_loop.add_argument("--instruction", required=True)
    mvp_loop.add_argument("--pinned-path", action="append", default=None)
    mvp_loop.add_argument("--changed-path", action="append", default=None)
    mvp_loop.add_argument(
        "--local-target-root",
        help=(
            "Run context, edit, test, and diagnosis steps directly against this "
            "local repo root without requiring a live BIBER API. GitHub save/PR "
            "steps still use the API."
        ),
    )
    mvp_loop.add_argument(
        "--include-git-state",
        action="store_true",
        help=(
            "With --local-target-root, record branch, HEAD, and dirty status in "
            "the loop artifact before edits/tests run."
        ),
    )
    mvp_loop.add_argument("--max-context-files", type=int)
    mvp_loop.add_argument("--max-scan-files", type=int)
    mvp_loop.add_argument("--runtime-profile-id", action="append", default=None)
    mvp_loop.add_argument("--edit-json", action="append", default=None)
    mvp_loop.add_argument("--edits-file")
    mvp_loop.add_argument("--apply-edits", action="store_true")
    mvp_loop.add_argument("--max-edit-files", type=int)
    mvp_loop.add_argument("--test-id")
    mvp_loop.add_argument("--test-dry-run", action="store_true")
    mvp_loop.add_argument("--max-context-lines", type=int)
    mvp_loop.add_argument("--save-github-path")
    mvp_loop.add_argument("--save-content")
    mvp_loop.add_argument("--save-content-file")
    mvp_loop.add_argument("--github-owner")
    mvp_loop.add_argument("--github-repo")
    mvp_loop.add_argument("--github-branch", default="main")
    mvp_loop.add_argument("--github-base-branch")
    mvp_loop.add_argument("--create-branch-if-missing", action="store_true")
    mvp_loop.add_argument(
        "--commit-message",
        default="Save BIBER MVP loop output",
    )
    mvp_loop.add_argument(
        "--github-dry-run",
        action="store_true",
        help=(
            "Build GitHub save/PR payloads inside the MVP loop without "
            "resolving API auth or sending GitHub requests."
        ),
    )
    mvp_loop.add_argument("--create-pr", action="store_true")
    mvp_loop.add_argument("--pr-head")
    mvp_loop.add_argument("--pr-base", default="main")
    mvp_loop.add_argument("--pr-title")
    mvp_loop.add_argument("--pr-body", default=None)
    mvp_loop.add_argument("--pr-body-file")
    mvp_loop.add_argument("--pr-ready", action="store_true")
    mvp_loop.add_argument(
        "--output",
        help="Write the MVP loop JSON summary to this local artifact path.",
    )

    show_mvp_loop = subparsers.add_parser(
        "show-mvp-loop",
        help="Summarize a saved local mvp-loop --output JSON artifact.",
    )
    show_mvp_loop.add_argument("artifact")

    list_mvp_loops = subparsers.add_parser(
        "list-mvp-loops",
        help="List saved local mvp-loop JSON artifacts under a directory.",
    )
    list_mvp_loops.add_argument("directory")
    list_mvp_loops.add_argument("--pattern", default="*mvp-loop*.json")
    list_mvp_loops.add_argument("--limit", type=int, default=10)
    list_mvp_loops.add_argument(
        "--failed-only",
        action="store_true",
        help="Only list saved loop artifacts where ok is false or the test failed.",
    )

    show_repair_attempt = subparsers.add_parser(
        "show-repair-attempt",
        help=(
            "Summarize a saved attempt-repair JSON artifact without resolving "
            "API auth."
        ),
    )
    show_repair_attempt.add_argument("artifact")

    list_repair_attempts = subparsers.add_parser(
        "list-repair-attempts",
        help=(
            "List saved attempt-repair JSON artifacts under a directory "
            "without resolving API auth."
        ),
    )
    list_repair_attempts.add_argument("directory")
    list_repair_attempts.add_argument("--pattern", default="*repair-attempt*.json")
    list_repair_attempts.add_argument("--limit", type=int, default=10)
    list_repair_attempts.add_argument("--ready-only", action="store_true")

    show_repair_edit_extraction = subparsers.add_parser(
        "show-repair-edit-extraction",
        help=(
            "Summarize a saved extract-repair-edits JSON artifact without "
            "resolving API auth."
        ),
    )
    show_repair_edit_extraction.add_argument("artifact")

    list_repair_edit_extractions = subparsers.add_parser(
        "list-repair-edit-extractions",
        help=(
            "List saved extract-repair-edits JSON artifacts under a directory "
            "without resolving API auth."
        ),
    )
    list_repair_edit_extractions.add_argument("directory")
    list_repair_edit_extractions.add_argument(
        "--pattern",
        default="*repair-edit-extraction*.json",
    )
    list_repair_edit_extractions.add_argument("--limit", type=int, default=10)
    list_repair_edit_extractions.add_argument("--ready-only", action="store_true")

    show_repair_edit_plan = subparsers.add_parser(
        "show-repair-edit-plan",
        help=(
            "Summarize a saved plan-repair-edits JSON artifact without "
            "resolving API auth."
        ),
    )
    show_repair_edit_plan.add_argument("artifact")

    list_repair_edit_plans = subparsers.add_parser(
        "list-repair-edit-plans",
        help=(
            "List saved plan-repair-edits JSON artifacts under a directory "
            "without resolving API auth."
        ),
    )
    list_repair_edit_plans.add_argument("directory")
    list_repair_edit_plans.add_argument(
        "--pattern",
        default="*repair-edit-plan*.json",
    )
    list_repair_edit_plans.add_argument("--limit", type=int, default=10)
    list_repair_edit_plans.add_argument("--planned-only", action="store_true")

    show_repair_edit_apply = subparsers.add_parser(
        "show-repair-edit-apply",
        help=(
            "Summarize a saved apply-repair-edits JSON artifact without "
            "resolving API auth."
        ),
    )
    show_repair_edit_apply.add_argument("artifact")

    list_repair_edit_applies = subparsers.add_parser(
        "list-repair-edit-applies",
        help=(
            "List saved apply-repair-edits JSON artifacts under a directory "
            "without resolving API auth."
        ),
    )
    list_repair_edit_applies.add_argument("directory")
    list_repair_edit_applies.add_argument(
        "--pattern",
        default="*repair-edit-apply*.json",
    )
    list_repair_edit_applies.add_argument("--limit", type=int, default=10)
    list_repair_edit_applies.add_argument("--applied-only", action="store_true")

    show_repair_test_verification = subparsers.add_parser(
        "show-repair-test-verification",
        help=(
            "Summarize a saved verify-repair-edits JSON artifact without "
            "resolving API auth."
        ),
    )
    show_repair_test_verification.add_argument("artifact")

    list_repair_test_verifications = subparsers.add_parser(
        "list-repair-test-verifications",
        help=(
            "List saved verify-repair-edits JSON artifacts under a directory "
            "without resolving API auth."
        ),
    )
    list_repair_test_verifications.add_argument("directory")
    list_repair_test_verifications.add_argument(
        "--pattern",
        default="*repair-test-verification*.json",
    )
    list_repair_test_verifications.add_argument("--limit", type=int, default=10)
    list_repair_test_verifications.add_argument(
        "--passed-only",
        action="store_true",
    )

    prepare_failed_repair_retry = subparsers.add_parser(
        "prepare-failed-repair-retry",
        help=(
            "Review a failed verify-repair-edits artifact and prepare a second "
            "bounded repair request without saving or training from the failure."
        ),
    )
    prepare_failed_repair_retry.add_argument("artifact")
    prepare_failed_repair_retry.add_argument("--output")
    prepare_failed_repair_retry.add_argument(
        "--retry-output",
        help="Optionally write the nested retry repair request as a standalone artifact.",
    )
    prepare_failed_repair_retry.add_argument(
        "--max-relevant-output-chars",
        type=int,
        default=4000,
    )
    prepare_failed_repair_retry.add_argument("--max-context-paths", type=int)
    prepare_failed_repair_retry.add_argument(
        "--source-root",
        default=".",
        help="Repository root used to collect compact retry source snippets.",
    )
    prepare_failed_repair_retry.add_argument(
        "--max-source-snippets",
        type=int,
        default=4,
    )
    prepare_failed_repair_retry.add_argument(
        "--source-snippet-context-lines",
        type=int,
        default=4,
    )

    export_repeated_forbidden_retry_gap_parser = subparsers.add_parser(
        "export-repeated-forbidden-retry-gap",
        help=(
            "Export a repeated-forbidden retry extraction failure to a JSONL "
            "model-gap review queue without making it trainable."
        ),
    )
    export_repeated_forbidden_retry_gap_parser.add_argument("artifact")
    export_repeated_forbidden_retry_gap_parser.add_argument("--output", required=True)

    export_empty_retry_gap_parser = subparsers.add_parser(
        "export-empty-retry-gap",
        help=(
            "Export an empty retry response with unresolved/confused prose to "
            "a JSONL model-gap review queue without making it trainable."
        ),
    )
    export_empty_retry_gap_parser.add_argument("artifact")
    export_empty_retry_gap_parser.add_argument("--output", required=True)

    export_blocked_retry_edit_gap_parser = subparsers.add_parser(
        "export-blocked-retry-edit-gap",
        help=(
            "Export a blocked retry edit review to a JSONL model-gap review "
            "queue without making it trainable."
        ),
    )
    export_blocked_retry_edit_gap_parser.add_argument("artifact")
    export_blocked_retry_edit_gap_parser.add_argument("--output", required=True)

    review_blocked_retry_edit_gaps_parser = subparsers.add_parser(
        "review-blocked-retry-edit-gaps",
        help=(
            "Summarize blocked retry edit gap JSONL queues without making "
            "them training-eligible."
        ),
    )
    review_blocked_retry_edit_gaps_parser.add_argument("jsonl", nargs="+")
    review_blocked_retry_edit_gaps_parser.add_argument("--min-repeat", type=int, default=1)
    review_blocked_retry_edit_gaps_parser.add_argument("--output")

    review_empty_retry_gaps_parser = subparsers.add_parser(
        "review-empty-retry-gaps",
        help=(
            "Summarize empty retry response gap JSONL queues without making "
            "them training-eligible."
        ),
    )
    review_empty_retry_gaps_parser.add_argument("jsonl", nargs="+")
    review_empty_retry_gaps_parser.add_argument("--min-repeat", type=int, default=1)
    review_empty_retry_gaps_parser.add_argument("--output")

    review_repeated_forbidden_retry_gaps_parser = subparsers.add_parser(
        "review-repeated-forbidden-retry-gaps",
        help=(
            "Summarize repeated-forbidden retry gap JSONL queues without "
            "making them training-eligible."
        ),
    )
    review_repeated_forbidden_retry_gaps_parser.add_argument("jsonl", nargs="+")
    review_repeated_forbidden_retry_gaps_parser.add_argument(
        "--min-repeat",
        type=int,
        default=1,
    )
    review_repeated_forbidden_retry_gaps_parser.add_argument("--output")

    review_retry_repair_edits_parser = subparsers.add_parser(
        "review-retry-repair-edits",
        help=(
            "Deterministically review a retry extract-repair-edits artifact "
            "before it can be planned or applied."
        ),
    )
    review_retry_repair_edits_parser.add_argument("artifact")
    review_retry_repair_edits_parser.add_argument("--output")

    export_mvp_failures = subparsers.add_parser(
        "export-mvp-failures",
        help="Export failed mvp-loop artifacts to a JSONL review queue.",
    )
    export_mvp_failures.add_argument("directory")
    export_mvp_failures.add_argument("--output", required=True)
    export_mvp_failures.add_argument("--pattern", default="*mvp-loop*.json")
    export_mvp_failures.add_argument("--limit", type=int, default=100)

    export_verified_repair = subparsers.add_parser(
        "export-verified-repair",
        help=(
            "Export one passed repair verification artifact to a JSONL human "
            "review queue without making it training-eligible."
        ),
    )
    export_verified_repair.add_argument("artifact")
    export_verified_repair.add_argument("--output", required=True)

    review_verified_repairs = subparsers.add_parser(
        "review-verified-repairs",
        help=(
            "Summarize verified repair JSONL review queues without making them "
            "training-eligible."
        ),
    )
    review_verified_repairs.add_argument("jsonl", nargs="+")
    review_verified_repairs.add_argument("--min-repeat", type=int, default=1)
    review_verified_repairs.add_argument("--output")

    show_verified_repair_review = subparsers.add_parser(
        "show-verified-repair-review",
        help=(
            "Summarize a saved review-verified-repairs JSON artifact without "
            "resolving API auth."
        ),
    )
    show_verified_repair_review.add_argument("artifact")

    list_verified_repair_reviews = subparsers.add_parser(
        "list-verified-repair-reviews",
        help=(
            "List saved review-verified-repairs JSON artifacts under a "
            "directory without resolving API auth."
        ),
    )
    list_verified_repair_reviews.add_argument("directory")
    list_verified_repair_reviews.add_argument(
        "--pattern",
        default="*verified-repair-review*.json",
    )
    list_verified_repair_reviews.add_argument("--limit", type=int, default=10)
    list_verified_repair_reviews.add_argument("--ready-only", action="store_true")

    show_repair_chain = subparsers.add_parser(
        "show-repair-chain",
        help=(
            "Summarize an MVP repair chain from saved artifacts without "
            "training, saving to GitHub, or resolving API auth."
        ),
    )
    show_repair_chain.add_argument("--mvp-loop")
    show_repair_chain.add_argument("--repair")
    show_repair_chain.add_argument("--attempt")
    show_repair_chain.add_argument("--extraction")
    show_repair_chain.add_argument("--plan")
    show_repair_chain.add_argument("--apply")
    show_repair_chain.add_argument("--verification")
    show_repair_chain.add_argument("--review-jsonl", action="append", default=None)
    show_repair_chain.add_argument("--review-summary")
    show_repair_chain.add_argument("--source-repo-root")
    show_repair_chain.add_argument("--source-repo-url")
    show_repair_chain.add_argument("--source-repo-commit")
    show_repair_chain.add_argument("--source-repo-branch")
    show_repair_chain.add_argument("--output")

    list_repair_chains = subparsers.add_parser(
        "list-repair-chains",
        help=(
            "List saved repair-chain summary artifacts under a directory "
            "without resolving API auth."
        ),
    )
    list_repair_chains.add_argument("directory")
    list_repair_chains.add_argument("--pattern", default="*repair-chain*.json")
    list_repair_chains.add_argument("--limit", type=int, default=10)
    list_repair_chains.add_argument("--ready-only", action="store_true")
    list_repair_chains.add_argument("--output")

    export_ready_repair_chains = subparsers.add_parser(
        "export-ready-repair-chains",
        help=(
            "Export ready repair-chain summaries from a directory to a JSONL "
            "human-review queue without training or GitHub save readiness."
        ),
    )
    export_ready_repair_chains.add_argument("directory")
    export_ready_repair_chains.add_argument("--pattern", default="*repair-chain*.json")
    export_ready_repair_chains.add_argument("--limit", type=int, default=100)
    export_ready_repair_chains.add_argument("--output", required=True)

    review_ready_repair_chains = subparsers.add_parser(
        "review-ready-repair-chains",
        help=(
            "Summarize ready repair-chain JSONL review queues without making "
            "them training-eligible or GitHub-save-ready."
        ),
    )
    review_ready_repair_chains.add_argument("jsonl", nargs="+")
    review_ready_repair_chains.add_argument("--min-repeat", type=int, default=1)
    review_ready_repair_chains.add_argument("--output")

    show_ready_repair_chain_review = subparsers.add_parser(
        "show-ready-repair-chain-review",
        help=(
            "Summarize a saved review-ready-repair-chains JSON artifact "
            "without resolving API auth."
        ),
    )
    show_ready_repair_chain_review.add_argument("artifact")

    list_ready_repair_chain_reviews = subparsers.add_parser(
        "list-ready-repair-chain-reviews",
        help=(
            "List saved review-ready-repair-chains JSON artifacts under a "
            "directory without resolving API auth."
        ),
    )
    list_ready_repair_chain_reviews.add_argument("directory")
    list_ready_repair_chain_reviews.add_argument(
        "--pattern",
        default="*ready-repair-chain-review*.json",
    )
    list_ready_repair_chain_reviews.add_argument("--limit", type=int, default=10)
    list_ready_repair_chain_reviews.add_argument("--ready-only", action="store_true")

    record_ready_repair_chain_decision = subparsers.add_parser(
        "record-ready-repair-chain-decision",
        help=(
            "Record a human decision for ready repair-chain review rows without "
            "training or GitHub save promotion."
        ),
    )
    record_ready_repair_chain_decision.add_argument("jsonl", nargs="+")
    record_ready_repair_chain_decision.add_argument(
        "--decision",
        choices=["defer", "reject", "approve_for_eval"],
        required=True,
    )
    record_ready_repair_chain_decision.add_argument("--reviewer", required=True)
    record_ready_repair_chain_decision.add_argument("--notes", default="")
    record_ready_repair_chain_decision.add_argument(
        "--evidence-source-type",
        choices=["auto", "real_repo_candidate", "fixture_or_smoke"],
        default="auto",
        help=(
            "Require explicit real_repo_candidate when recording approve_for_eval. "
            "Use auto for defer/reject review bookkeeping."
        ),
    )
    record_ready_repair_chain_decision.add_argument("--limit", type=int, default=100)
    record_ready_repair_chain_decision.add_argument("--output", required=True)

    review_ready_repair_chain_decisions = subparsers.add_parser(
        "review-ready-repair-chain-decisions",
        help=(
            "Summarize ready repair-chain human-decision JSONL queues without "
            "training or GitHub save promotion."
        ),
    )
    review_ready_repair_chain_decisions.add_argument("jsonl", nargs="+")
    review_ready_repair_chain_decisions.add_argument("--output")

    show_ready_repair_chain_decision_review = subparsers.add_parser(
        "show-ready-repair-chain-decision-review",
        help=(
            "Summarize a saved review-ready-repair-chain-decisions JSON "
            "artifact without resolving API auth."
        ),
    )
    show_ready_repair_chain_decision_review.add_argument("artifact")

    list_ready_repair_chain_decision_reviews = subparsers.add_parser(
        "list-ready-repair-chain-decision-reviews",
        help=(
            "List saved review-ready-repair-chain-decisions JSON artifacts "
            "under a directory without resolving API auth."
        ),
    )
    list_ready_repair_chain_decision_reviews.add_argument("directory")
    list_ready_repair_chain_decision_reviews.add_argument(
        "--pattern",
        default="*ready-repair-chain-decision-review*.json",
    )
    list_ready_repair_chain_decision_reviews.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_ready_repair_chain_decision_reviews.add_argument(
        "--decision",
        choices=["defer", "reject", "approve_for_eval"],
    )

    export_ready_repair_chain_eval_candidates = subparsers.add_parser(
        "export-ready-repair-chain-eval-candidates",
        help=(
            "Export approve_for_eval repair-chain decisions to an eval-candidate "
            "JSONL without training or GitHub save promotion."
        ),
    )
    export_ready_repair_chain_eval_candidates.add_argument("jsonl", nargs="+")
    export_ready_repair_chain_eval_candidates.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    export_ready_repair_chain_eval_candidates.add_argument("--output", required=True)

    review_ready_repair_chain_eval_candidates = subparsers.add_parser(
        "review-ready-repair-chain-eval-candidates",
        help=(
            "Summarize repair-chain eval-candidate JSONL queues without making "
            "them dataset-ready or training-eligible."
        ),
    )
    review_ready_repair_chain_eval_candidates.add_argument("jsonl", nargs="+")
    review_ready_repair_chain_eval_candidates.add_argument(
        "--min-repeat",
        type=int,
        default=1,
    )
    review_ready_repair_chain_eval_candidates.add_argument("--output")

    show_ready_repair_chain_eval_candidate_review = subparsers.add_parser(
        "show-ready-repair-chain-eval-candidate-review",
        help=(
            "Show a saved review-ready-repair-chain-eval-candidates JSON "
            "artifact without resolving API auth."
        ),
    )
    show_ready_repair_chain_eval_candidate_review.add_argument("artifact")

    list_ready_repair_chain_eval_candidate_reviews = subparsers.add_parser(
        "list-ready-repair-chain-eval-candidate-reviews",
        help=(
            "List saved review-ready-repair-chain-eval-candidates JSON "
            "artifacts under a directory without resolving API auth."
        ),
    )
    list_ready_repair_chain_eval_candidate_reviews.add_argument("directory")
    list_ready_repair_chain_eval_candidate_reviews.add_argument(
        "--pattern",
        default="*ready-repair-chain-eval-candidate-review*.json",
    )
    list_ready_repair_chain_eval_candidate_reviews.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_ready_repair_chain_eval_candidate_reviews.add_argument(
        "--ready-only",
        action="store_true",
    )

    record_ready_repair_chain_eval_candidate_decision = subparsers.add_parser(
        "record-ready-repair-chain-eval-candidate-decision",
        help=(
            "Record a human dataset-review decision for repair-chain eval "
            "candidates without making them training-eligible."
        ),
    )
    record_ready_repair_chain_eval_candidate_decision.add_argument("jsonl", nargs="+")
    record_ready_repair_chain_eval_candidate_decision.add_argument(
        "--decision",
        choices=["defer", "reject", "approve_for_eval_dataset"],
        required=True,
    )
    record_ready_repair_chain_eval_candidate_decision.add_argument(
        "--reviewer",
        required=True,
    )
    record_ready_repair_chain_eval_candidate_decision.add_argument(
        "--notes",
        default="",
    )
    record_ready_repair_chain_eval_candidate_decision.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    record_ready_repair_chain_eval_candidate_decision.add_argument(
        "--output",
        required=True,
    )

    review_ready_repair_chain_eval_dataset_decisions = subparsers.add_parser(
        "review-ready-repair-chain-eval-dataset-decisions",
        help=(
            "Summarize repair-chain eval-dataset decision JSONL queues without "
            "making them training-eligible."
        ),
    )
    review_ready_repair_chain_eval_dataset_decisions.add_argument("jsonl", nargs="+")
    review_ready_repair_chain_eval_dataset_decisions.add_argument(
        "--min-repeat",
        type=int,
        default=1,
    )
    review_ready_repair_chain_eval_dataset_decisions.add_argument("--output")

    show_ready_repair_chain_eval_dataset_decision_review = subparsers.add_parser(
        "show-ready-repair-chain-eval-dataset-decision-review",
        help=(
            "Show a saved review-ready-repair-chain-eval-dataset-decisions "
            "JSON artifact without resolving API auth."
        ),
    )
    show_ready_repair_chain_eval_dataset_decision_review.add_argument("artifact")

    list_ready_repair_chain_eval_dataset_decision_reviews = subparsers.add_parser(
        "list-ready-repair-chain-eval-dataset-decision-reviews",
        help=(
            "List saved review-ready-repair-chain-eval-dataset-decisions JSON "
            "artifacts under a directory without resolving API auth."
        ),
    )
    list_ready_repair_chain_eval_dataset_decision_reviews.add_argument("directory")
    list_ready_repair_chain_eval_dataset_decision_reviews.add_argument(
        "--pattern",
        default="*ready-repair-chain-eval-dataset-decision-review*.json",
    )
    list_ready_repair_chain_eval_dataset_decision_reviews.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_ready_repair_chain_eval_dataset_decision_reviews.add_argument(
        "--decision",
        choices=["defer", "reject", "approve_for_eval_dataset"],
    )
    list_ready_repair_chain_eval_dataset_decision_reviews.add_argument(
        "--ready-only",
        action="store_true",
    )

    export_ready_repair_chain_eval_dataset = subparsers.add_parser(
        "export-ready-repair-chain-eval-dataset",
        help=(
            "Export approved repair-chain eval-dataset decisions into a "
            "validation-only eval dataset JSONL."
        ),
    )
    export_ready_repair_chain_eval_dataset.add_argument("jsonl", nargs="+")
    export_ready_repair_chain_eval_dataset.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    export_ready_repair_chain_eval_dataset.add_argument("--output", required=True)

    validate_ready_repair_chain_eval_dataset = subparsers.add_parser(
        "validate-ready-repair-chain-eval-dataset",
        help=(
            "Validate repair-chain eval-dataset JSONL safety/provenance "
            "without making it training-eligible."
        ),
    )
    validate_ready_repair_chain_eval_dataset.add_argument("jsonl", nargs="+")
    validate_ready_repair_chain_eval_dataset.add_argument(
        "--min-records",
        type=int,
        default=1,
    )
    validate_ready_repair_chain_eval_dataset.add_argument("--output")

    show_ready_repair_chain_eval_dataset_validation = subparsers.add_parser(
        "show-ready-repair-chain-eval-dataset-validation",
        help=(
            "Show a saved validate-ready-repair-chain-eval-dataset JSON "
            "artifact without resolving API auth."
        ),
    )
    show_ready_repair_chain_eval_dataset_validation.add_argument("artifact")

    list_ready_repair_chain_eval_dataset_validations = subparsers.add_parser(
        "list-ready-repair-chain-eval-dataset-validations",
        help=(
            "List saved validate-ready-repair-chain-eval-dataset JSON artifacts "
            "under a directory without resolving API auth."
        ),
    )
    list_ready_repair_chain_eval_dataset_validations.add_argument("directory")
    list_ready_repair_chain_eval_dataset_validations.add_argument(
        "--pattern",
        default="*ready-repair-chain-eval-dataset-validation*.json",
    )
    list_ready_repair_chain_eval_dataset_validations.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_ready_repair_chain_eval_dataset_validations.add_argument(
        "--ok-only",
        action="store_true",
    )

    export_ready_repair_chain_eval_prompts = subparsers.add_parser(
        "export-ready-repair-chain-eval-prompts",
        help=(
            "Export validated repair-chain eval-dataset records into held-out "
            "live-eval prompts."
        ),
    )
    export_ready_repair_chain_eval_prompts.add_argument("jsonl", nargs="+")
    export_ready_repair_chain_eval_prompts.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    export_ready_repair_chain_eval_prompts.add_argument("--output", required=True)

    show_ready_repair_chain_eval_prompts = subparsers.add_parser(
        "show-ready-repair-chain-eval-prompts",
        help=(
            "Inspect a ready repair-chain eval prompt JSONL queue without "
            "resolving API auth."
        ),
    )
    show_ready_repair_chain_eval_prompts.add_argument("jsonl", nargs="+")
    show_ready_repair_chain_eval_prompts.add_argument(
        "--min-records",
        type=int,
        default=1,
    )

    list_ready_repair_chain_eval_prompts = subparsers.add_parser(
        "list-ready-repair-chain-eval-prompts",
        help=(
            "List ready repair-chain eval prompt JSONL queues under a directory "
            "without resolving API auth."
        ),
    )
    list_ready_repair_chain_eval_prompts.add_argument("directory")
    list_ready_repair_chain_eval_prompts.add_argument(
        "--pattern",
        default="*ready-repair-chain-eval-prompts*.jsonl",
    )
    list_ready_repair_chain_eval_prompts.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_ready_repair_chain_eval_prompts.add_argument(
        "--ready-only",
        action="store_true",
    )

    review_repair_chain_heldout_eval_results = subparsers.add_parser(
        "review-repair-chain-heldout-eval-results",
        help=(
            "Review repair-chain held-out live-eval results without promoting "
            "them to training or GitHub save."
        ),
    )
    review_repair_chain_heldout_eval_results.add_argument("jsonl", nargs="+")
    review_repair_chain_heldout_eval_results.add_argument("--summary")
    review_repair_chain_heldout_eval_results.add_argument(
        "--min-passes",
        type=int,
        default=1,
    )
    review_repair_chain_heldout_eval_results.add_argument("--output")

    show_repair_chain_heldout_eval_review = subparsers.add_parser(
        "show-repair-chain-heldout-eval-review",
        help=(
            "Inspect a saved repair-chain held-out eval review artifact "
            "without resolving API auth."
        ),
    )
    show_repair_chain_heldout_eval_review.add_argument("artifact")

    list_repair_chain_heldout_eval_reviews = subparsers.add_parser(
        "list-repair-chain-heldout-eval-reviews",
        help=(
            "List saved repair-chain held-out eval review artifacts under a "
            "directory without resolving API auth."
        ),
    )
    list_repair_chain_heldout_eval_reviews.add_argument("directory")
    list_repair_chain_heldout_eval_reviews.add_argument(
        "--pattern",
        default="*heldout-eval-review*.json",
    )
    list_repair_chain_heldout_eval_reviews.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_repair_chain_heldout_eval_reviews.add_argument(
        "--ok-only",
        action="store_true",
    )

    record_repair_chain_heldout_eval_decision = subparsers.add_parser(
        "record-repair-chain-heldout-eval-decision",
        help=(
            "Record a manual decision for held-out eval review artifacts "
            "without training or GitHub save promotion."
        ),
    )
    record_repair_chain_heldout_eval_decision.add_argument("artifact", nargs="+")
    record_repair_chain_heldout_eval_decision.add_argument(
        "--decision",
        choices=["defer", "reject", "accept_for_baseline"],
        required=True,
    )
    record_repair_chain_heldout_eval_decision.add_argument("--reviewer", required=True)
    record_repair_chain_heldout_eval_decision.add_argument("--notes", default="")
    record_repair_chain_heldout_eval_decision.add_argument("--limit", type=int, default=100)
    record_repair_chain_heldout_eval_decision.add_argument("--output", required=True)

    review_repair_chain_heldout_eval_decisions = subparsers.add_parser(
        "review-repair-chain-heldout-eval-decisions",
        help=(
            "Summarize held-out eval decision JSONL queues without training "
            "or model promotion."
        ),
    )
    review_repair_chain_heldout_eval_decisions.add_argument("jsonl", nargs="+")
    review_repair_chain_heldout_eval_decisions.add_argument(
        "--min-repeat",
        type=int,
        default=1,
    )
    review_repair_chain_heldout_eval_decisions.add_argument("--output")

    show_repair_chain_heldout_eval_decision_review = subparsers.add_parser(
        "show-repair-chain-heldout-eval-decision-review",
        help=(
            "Inspect a saved repair-chain held-out eval decision review "
            "artifact without resolving API auth."
        ),
    )
    show_repair_chain_heldout_eval_decision_review.add_argument("artifact")

    list_repair_chain_heldout_eval_decision_reviews = subparsers.add_parser(
        "list-repair-chain-heldout-eval-decision-reviews",
        help=(
            "List saved repair-chain held-out eval decision review artifacts "
            "under a directory without resolving API auth."
        ),
    )
    list_repair_chain_heldout_eval_decision_reviews.add_argument("directory")
    list_repair_chain_heldout_eval_decision_reviews.add_argument(
        "--pattern",
        default="*heldout-eval-decision-review*.json",
    )
    list_repair_chain_heldout_eval_decision_reviews.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_repair_chain_heldout_eval_decision_reviews.add_argument(
        "--decision",
        choices=["defer", "reject", "accept_for_baseline"],
    )
    list_repair_chain_heldout_eval_decision_reviews.add_argument(
        "--baseline-ready-only",
        action="store_true",
    )

    export_repair_chain_heldout_baseline_candidates = subparsers.add_parser(
        "export-repair-chain-heldout-baseline-candidates",
        help=(
            "Export accepted held-out eval decisions into baseline candidates "
            "without training or model promotion."
        ),
    )
    export_repair_chain_heldout_baseline_candidates.add_argument("jsonl", nargs="+")
    export_repair_chain_heldout_baseline_candidates.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    export_repair_chain_heldout_baseline_candidates.add_argument(
        "--output",
        required=True,
    )

    review_repair_chain_heldout_baseline_candidates = subparsers.add_parser(
        "review-repair-chain-heldout-baseline-candidates",
        help=(
            "Summarize held-out baseline candidate JSONL queues without "
            "training or model promotion."
        ),
    )
    review_repair_chain_heldout_baseline_candidates.add_argument("jsonl", nargs="+")
    review_repair_chain_heldout_baseline_candidates.add_argument(
        "--min-repeat",
        type=int,
        default=1,
    )
    review_repair_chain_heldout_baseline_candidates.add_argument("--output")

    show_repair_chain_heldout_baseline_candidate_review = subparsers.add_parser(
        "show-repair-chain-heldout-baseline-candidate-review",
        help=(
            "Show a held-out baseline candidate review artifact without "
            "training or model promotion."
        ),
    )
    show_repair_chain_heldout_baseline_candidate_review.add_argument("artifact")

    list_repair_chain_heldout_baseline_candidate_reviews = subparsers.add_parser(
        "list-repair-chain-heldout-baseline-candidate-reviews",
        help=(
            "List held-out baseline candidate review artifacts without "
            "training or model promotion."
        ),
    )
    list_repair_chain_heldout_baseline_candidate_reviews.add_argument("directory")
    list_repair_chain_heldout_baseline_candidate_reviews.add_argument(
        "--pattern",
        default="*heldout-baseline-candidate-review*.json",
    )
    list_repair_chain_heldout_baseline_candidate_reviews.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_repair_chain_heldout_baseline_candidate_reviews.add_argument(
        "--candidate-ready-only",
        action="store_true",
    )

    record_repair_chain_heldout_baseline_candidate_decision = subparsers.add_parser(
        "record-repair-chain-heldout-baseline-candidate-decision",
        help=(
            "Record a manual decision for held-out baseline candidates "
            "without training or model promotion."
        ),
    )
    record_repair_chain_heldout_baseline_candidate_decision.add_argument(
        "jsonl",
        nargs="+",
    )
    record_repair_chain_heldout_baseline_candidate_decision.add_argument(
        "--decision",
        choices=["defer", "reject", "approve_as_baseline"],
        required=True,
    )
    record_repair_chain_heldout_baseline_candidate_decision.add_argument(
        "--reviewer",
        required=True,
    )
    record_repair_chain_heldout_baseline_candidate_decision.add_argument(
        "--notes",
        default="",
    )
    record_repair_chain_heldout_baseline_candidate_decision.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    record_repair_chain_heldout_baseline_candidate_decision.add_argument(
        "--output",
        required=True,
    )

    review_repair_chain_heldout_baseline_decisions = subparsers.add_parser(
        "review-repair-chain-heldout-baseline-decisions",
        help=(
            "Summarize held-out baseline decision JSONL queues without "
            "training or model promotion."
        ),
    )
    review_repair_chain_heldout_baseline_decisions.add_argument("jsonl", nargs="+")
    review_repair_chain_heldout_baseline_decisions.add_argument(
        "--min-repeat",
        type=int,
        default=1,
    )
    review_repair_chain_heldout_baseline_decisions.add_argument("--output")

    show_repair_chain_heldout_baseline_decision_review = subparsers.add_parser(
        "show-repair-chain-heldout-baseline-decision-review",
        help=(
            "Show a held-out baseline decision review artifact without "
            "training or model promotion."
        ),
    )
    show_repair_chain_heldout_baseline_decision_review.add_argument("artifact")

    list_repair_chain_heldout_baseline_decision_reviews = subparsers.add_parser(
        "list-repair-chain-heldout-baseline-decision-reviews",
        help=(
            "List held-out baseline decision review artifacts without "
            "training or model promotion."
        ),
    )
    list_repair_chain_heldout_baseline_decision_reviews.add_argument("directory")
    list_repair_chain_heldout_baseline_decision_reviews.add_argument(
        "--pattern",
        default="*heldout-baseline-decision-review*.json",
    )
    list_repair_chain_heldout_baseline_decision_reviews.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_repair_chain_heldout_baseline_decision_reviews.add_argument(
        "--decision",
        choices=["defer", "reject", "approve_as_baseline"],
    )
    list_repair_chain_heldout_baseline_decision_reviews.add_argument(
        "--baseline-ready-only",
        action="store_true",
    )

    review_repair_chain_training_readiness_parser = subparsers.add_parser(
        "review-repair-chain-training-readiness",
        help=(
            "Summarize baseline decision-review artifacts and report whether "
            "training is still blocked."
        ),
    )
    review_repair_chain_training_readiness_parser.add_argument(
        "review_artifact",
        nargs="+",
    )
    review_repair_chain_training_readiness_parser.add_argument(
        "--min-baseline-ready",
        type=int,
        default=1,
    )
    review_repair_chain_training_readiness_parser.add_argument("--output")

    show_repair_chain_training_readiness_parser = subparsers.add_parser(
        "show-repair-chain-training-readiness",
        help=(
            "Show a repair-chain training readiness artifact without starting "
            "training."
        ),
    )
    show_repair_chain_training_readiness_parser.add_argument("artifact")

    list_repair_chain_training_readiness_parser = subparsers.add_parser(
        "list-repair-chain-training-readiness",
        help=(
            "List repair-chain training readiness artifacts without starting "
            "training."
        ),
    )
    list_repair_chain_training_readiness_parser.add_argument("directory")
    list_repair_chain_training_readiness_parser.add_argument(
        "--pattern",
        default="*training-readiness*.json",
    )
    list_repair_chain_training_readiness_parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_repair_chain_training_readiness_parser.add_argument(
        "--ready-only",
        action="store_true",
    )

    export_repair_chain_training_candidates_parser = subparsers.add_parser(
        "export-repair-chain-training-candidates",
        help=(
            "Export human-review-only training candidate rows from training "
            "readiness artifacts without making a trainable dataset."
        ),
    )
    export_repair_chain_training_candidates_parser.add_argument(
        "readiness_artifact",
        nargs="+",
    )
    export_repair_chain_training_candidates_parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    export_repair_chain_training_candidates_parser.add_argument(
        "--output",
        required=True,
    )

    review_repair_chain_training_candidates_parser = subparsers.add_parser(
        "review-repair-chain-training-candidates",
        help=(
            "Review repair-chain training candidate JSONL queues and report "
            "whether they are ready for dataset validation."
        ),
    )
    review_repair_chain_training_candidates_parser.add_argument("jsonl", nargs="+")
    review_repair_chain_training_candidates_parser.add_argument(
        "--min-ready",
        type=int,
        default=1,
    )
    review_repair_chain_training_candidates_parser.add_argument("--output")

    show_repair_chain_training_candidate_review_parser = subparsers.add_parser(
        "show-repair-chain-training-candidate-review",
        help=(
            "Show a repair-chain training candidate review artifact without "
            "starting training."
        ),
    )
    show_repair_chain_training_candidate_review_parser.add_argument("artifact")

    list_repair_chain_training_candidate_reviews_parser = subparsers.add_parser(
        "list-repair-chain-training-candidate-reviews",
        help=(
            "List repair-chain training candidate review artifacts without "
            "starting training."
        ),
    )
    list_repair_chain_training_candidate_reviews_parser.add_argument("directory")
    list_repair_chain_training_candidate_reviews_parser.add_argument(
        "--pattern",
        default="*training-candidate-review*.json",
    )
    list_repair_chain_training_candidate_reviews_parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_repair_chain_training_candidate_reviews_parser.add_argument(
        "--ready-only",
        action="store_true",
    )

    review_repair_chain_training_pipeline_parser = subparsers.add_parser(
        "review-repair-chain-training-pipeline",
        help=(
            "Summarize the repair-chain training gate artifacts in one directory "
            "without starting training."
        ),
    )
    review_repair_chain_training_pipeline_parser.add_argument(
        "--artifact-dir",
        required=True,
    )
    review_repair_chain_training_pipeline_parser.add_argument("--output")

    show_repair_chain_training_pipeline_parser = subparsers.add_parser(
        "show-repair-chain-training-pipeline",
        help=(
            "Show a saved repair-chain training pipeline status artifact "
            "without resolving API auth or starting training."
        ),
    )
    show_repair_chain_training_pipeline_parser.add_argument("artifact")

    list_repair_chain_training_pipelines_parser = subparsers.add_parser(
        "list-repair-chain-training-pipelines",
        help=(
            "List saved repair-chain training pipeline status artifacts under "
            "a directory without resolving API auth or starting training."
        ),
    )
    list_repair_chain_training_pipelines_parser.add_argument("directory")
    list_repair_chain_training_pipelines_parser.add_argument(
        "--pattern",
        default="agent-client-mvp-loop-repair-chain-training-pipeline.json",
    )
    list_repair_chain_training_pipelines_parser.add_argument(
        "--limit",
        type=int,
        default=10,
    )
    list_repair_chain_training_pipelines_parser.add_argument(
        "--ready-only",
        action="store_true",
    )
    list_repair_chain_training_pipelines_parser.add_argument("--output")

    prepare_repair = subparsers.add_parser(
        "prepare-repair",
        help="Build a local-model repair request from a failed mvp-loop artifact.",
    )
    prepare_repair.add_argument("artifact")
    prepare_repair.add_argument("--instruction")
    prepare_repair.add_argument("--max-relevant-output-chars", type=int, default=4000)
    prepare_repair.add_argument("--max-context-paths", type=int)
    prepare_repair.add_argument("--output")

    attempt_repair = subparsers.add_parser(
        "attempt-repair",
        help=(
            "Send a failed mvp-loop artifact or prepared repair request to the "
            "local BIBER model and save an inspectable proposal without "
            "applying edits."
        ),
    )
    attempt_repair.add_argument("artifact")
    attempt_repair.add_argument("--instruction")
    attempt_repair.add_argument("--max-relevant-output-chars", type=int, default=4000)
    attempt_repair.add_argument("--max-context-paths", type=int)
    attempt_repair.add_argument("--model")
    attempt_repair.add_argument("--max-tokens", type=int, default=700)
    attempt_repair.add_argument("--temperature", type=float, default=0.2)
    attempt_repair.add_argument("--runtime-profile-id", action="append", default=None)
    attempt_repair.add_argument(
        "--use-mentor",
        action="store_true",
        help="Allow the OpenAI mentor path if server-side mentor config is enabled.",
    )
    attempt_repair.add_argument("--output")

    local_repair_chain = subparsers.add_parser(
        "local-repair-chain",
        help=(
            "Run the local repair chain from a failed mvp-loop or prepared "
            "repair request plus supplied model response, extracting edits and "
            "optionally planning them locally without calling the BIBER API."
        ),
    )
    local_repair_chain.add_argument("artifact")
    local_repair_chain.add_argument("--instruction")
    local_repair_chain.add_argument("--max-relevant-output-chars", type=int, default=4000)
    local_repair_chain.add_argument("--max-context-paths", type=int)
    local_repair_chain.add_argument("--model")
    local_repair_chain.add_argument("--model-response")
    local_repair_chain.add_argument("--model-response-file")
    local_repair_chain.add_argument(
        "--model-command",
        help=(
            "Optional local provider command. It receives a JSON repair request on "
            "stdin and may print raw model text or JSON with a string content field."
        ),
    )
    local_repair_chain.add_argument(
        "--model-command-timeout-seconds",
        type=float,
        default=120.0,
    )
    local_repair_chain.add_argument("--max-edits", type=int, default=3)
    local_repair_chain.add_argument("--max-files", type=int)
    local_repair_chain.add_argument(
        "--target-root",
        help="Optional local repository root for plan validation. No apply occurs.",
    )
    local_repair_chain.add_argument("--output")

    review_local_repair_chain_parser = subparsers.add_parser(
        "review-local-repair-chain",
        help=(
            "Review a saved local-repair-chain artifact before any human-approved "
            "apply. This is deterministic and does not call the BIBER API."
        ),
    )
    review_local_repair_chain_parser.add_argument("artifact")
    review_local_repair_chain_parser.add_argument("--output")

    extract_repair_edits_parser = subparsers.add_parser(
        "extract-repair-edits",
        help=(
            "Extract conservative JSON edit candidates from a repair-attempt "
            "artifact for review and plan-edit validation."
        ),
    )
    extract_repair_edits_parser.add_argument("artifact")
    extract_repair_edits_parser.add_argument("--max-edits", type=int, default=3)
    extract_repair_edits_parser.add_argument("--max-files", type=int)
    extract_repair_edits_parser.add_argument("--output")
    extract_repair_edits_parser.add_argument(
        "--edits-output",
        help="Write only the plan-edit payload, suitable for --edits-file.",
    )

    plan_repair_edits_parser = subparsers.add_parser(
        "plan-repair-edits",
        help=(
            "Validate extracted repair edits through the server-side plan-edit "
            "endpoint without applying them."
        ),
    )
    plan_repair_edits_parser.add_argument("artifact")
    plan_repair_edits_parser.add_argument("--max-files", type=int)
    plan_repair_edits_parser.add_argument(
        "--target-root",
        help=(
            "Optional local repository root for offline plan validation. "
            "Retry artifacts default to their source_context.source_root when present."
        ),
    )
    plan_repair_edits_parser.add_argument(
        "--retry-review-artifact",
        help=(
            "Required for retry repair extractions; must be an accepted "
            "review-retry-repair-edits artifact."
        ),
    )
    plan_repair_edits_parser.add_argument("--output")

    apply_repair_edits_parser = subparsers.add_parser(
        "apply-repair-edits",
        help=(
            "Apply a planned repair edit only after explicit approval, using "
            "the plan hash from a repair-edit plan artifact."
        ),
    )
    apply_repair_edits_parser.add_argument("artifact")
    apply_repair_edits_parser.add_argument(
        "--approve",
        action="store_true",
        help="Required safety gate. Without this flag, no edits are applied.",
    )
    apply_repair_edits_parser.add_argument(
        "--target-root",
        help=(
            "Optional local repository root for offline apply. Defaults to the "
            "target_root recorded by plan-repair-edits when present."
        ),
    )
    apply_repair_edits_parser.add_argument(
        "--review-artifact",
        help=(
            "Optional review-local-repair-chain artifact that must be ready "
            "and match the repair plan hash before apply proceeds."
        ),
    )
    apply_repair_edits_parser.add_argument("--output")

    local_verify_chain_parser = subparsers.add_parser(
        "local-verify-chain",
        help=(
            "Run a local-only post-apply verification chain from a repair "
            "apply artifact and emit a compact verified/still-failing status."
        ),
    )
    local_verify_chain_parser.add_argument("artifact")
    local_verify_chain_parser.add_argument("--test-id")
    local_verify_chain_parser.add_argument(
        "--target-root",
        help=(
            "Optional local repository root for verification. Defaults to the "
            "target_root recorded by apply-repair-edits."
        ),
    )
    local_verify_chain_parser.add_argument("--dry-run", action="store_true")
    local_verify_chain_parser.add_argument(
        "--diagnose-on-failure",
        action="store_true",
        help="Run local deterministic failure diagnosis when the test executes and fails.",
    )
    local_verify_chain_parser.add_argument("--max-context-lines", type=int)
    local_verify_chain_parser.add_argument("--output")

    prepare_local_verify_repair_parser = subparsers.add_parser(
        "prepare-local-verify-repair",
        help=(
            "Build a local-model repair request from a failed local-verify-chain "
            "artifact without resolving API auth."
        ),
    )
    prepare_local_verify_repair_parser.add_argument("artifact")
    prepare_local_verify_repair_parser.add_argument("--instruction")
    prepare_local_verify_repair_parser.add_argument(
        "--max-relevant-output-chars",
        type=int,
        default=4000,
    )
    prepare_local_verify_repair_parser.add_argument("--max-context-paths", type=int)
    prepare_local_verify_repair_parser.add_argument("--output")

    local_repair_loop_status_parser = subparsers.add_parser(
        "local-repair-loop-status",
        help=(
            "Summarize the latest local BIBER repair-loop artifact in a "
            "directory and print the next no-API command to run."
        ),
    )
    local_repair_loop_status_parser.add_argument("directory")
    local_repair_loop_status_parser.add_argument("--pattern", default="*.json")
    local_repair_loop_status_parser.add_argument("--limit", type=int, default=10)
    local_repair_loop_status_parser.add_argument("--output")

    verify_repair_edits_parser = subparsers.add_parser(
        "verify-repair-edits",
        help=(
            "Rerun the selected allowlisted test after an approved repair apply "
            "artifact, without saving or training from the result."
        ),
    )
    verify_repair_edits_parser.add_argument("artifact")
    verify_repair_edits_parser.add_argument("--test-id")
    verify_repair_edits_parser.add_argument(
        "--target-root",
        help=(
            "Optional local repository root for offline verification. Defaults "
            "to the target_root recorded by apply-repair-edits when present."
        ),
    )
    verify_repair_edits_parser.add_argument("--dry-run", action="store_true")
    verify_repair_edits_parser.add_argument(
        "--diagnose-on-failure",
        action="store_true",
        help="Call /v1/tests/diagnose when the rerun executes and fails.",
    )
    verify_repair_edits_parser.add_argument("--max-context-lines", type=int)
    verify_repair_edits_parser.add_argument("--output")

    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "capabilities"
    return args


def run(args: argparse.Namespace) -> str:
    if args.command == "show-mvp-loop":
        artifact = load_json_artifact(args.artifact, label="mvp-loop artifact")
        normalized = normalize_mvp_loop_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "mvp-loop artifact must contain a saved MVP loop JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_artifact_summary(normalized)
        )
    if args.command == "list-mvp-loops":
        artifacts = list_mvp_loop_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            failed_only=args.failed_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_artifact_list_summary(artifacts)
        )
    if args.command == "show-repair-attempt":
        artifact = load_json_artifact(args.artifact, label="repair-attempt artifact")
        normalized = normalize_repair_attempt_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "repair-attempt artifact must contain a saved attempt-repair JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_repair_attempt_summary(normalized)
        )
    if args.command == "list-repair-attempts":
        artifacts = list_repair_attempt_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_attempt_artifact_list_summary(artifacts)
        )
    if args.command == "show-repair-edit-extraction":
        artifact = load_json_artifact(
            args.artifact,
            label="repair-edit extraction artifact",
        )
        normalized = normalize_repair_edit_extraction_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "repair-edit extraction artifact must contain a saved "
                "extract-repair-edits JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_extraction_summary(normalized)
        )
    if args.command == "list-repair-edit-extractions":
        artifacts = list_repair_edit_extraction_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_extraction_artifact_list_summary(artifacts)
        )
    if args.command == "show-repair-edit-plan":
        artifact = load_json_artifact(
            args.artifact,
            label="repair-edit plan artifact",
        )
        normalized = normalize_repair_edit_plan_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "repair-edit plan artifact must contain a saved "
                "plan-repair-edits JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_plan_summary(normalized)
        )
    if args.command == "list-repair-edit-plans":
        artifacts = list_repair_edit_plan_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            planned_only=args.planned_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_plan_artifact_list_summary(artifacts)
        )
    if args.command == "show-repair-edit-apply":
        artifact = load_json_artifact(
            args.artifact,
            label="repair-edit apply artifact",
        )
        normalized = normalize_repair_edit_apply_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "repair-edit apply artifact must contain a saved "
                "apply-repair-edits JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_apply_summary(normalized)
        )
    if args.command == "list-repair-edit-applies":
        artifacts = list_repair_edit_apply_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            applied_only=args.applied_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_apply_artifact_list_summary(artifacts)
        )
    if args.command == "show-repair-test-verification":
        artifact = load_json_artifact(
            args.artifact,
            label="repair test verification artifact",
        )
        normalized = normalize_repair_test_verification_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "repair test verification artifact must contain a saved "
                "verify-repair-edits JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_test_verification_summary(normalized)
        )
    if args.command == "list-repair-test-verifications":
        artifacts = list_repair_test_verification_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            passed_only=args.passed_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_test_verification_artifact_list_summary(artifacts)
        )
    if args.command == "prepare-failed-repair-retry":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="repair test verification artifact",
        )
        verification = normalize_repair_test_verification_artifact(artifact)
        if verification is None:
            raise BiberAgentClientError(
                "prepare-failed-repair-retry artifact must contain a saved "
                "verify-repair-edits JSON object."
            )
        review = build_failed_repair_verification_review(
            path=artifact_path,
            verification=verification,
            max_relevant_output_chars=args.max_relevant_output_chars,
            max_context_paths=args.max_context_paths,
            source_root=Path(args.source_root),
            max_source_snippets=args.max_source_snippets,
            source_snippet_context_lines=args.source_snippet_context_lines,
        )
        if args.retry_output:
            retry_request = dict(require_mapping(review.get("retry_repair_request")))
            retry_request["artifact_path"] = str(Path(args.retry_output))
            write_json_artifact(retry_request, args.retry_output)
            review["retry_repair_request"] = retry_request
            review["retry_repair_request_artifact"] = str(Path(args.retry_output))
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_failed_repair_retry_review_summary(review)
        )
    if args.command == "export-repeated-forbidden-retry-gap":
        export = export_repeated_forbidden_retry_gap(
            artifact_path=args.artifact,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_repeated_forbidden_retry_gap_export_summary(export)
        )
    if args.command == "export-empty-retry-gap":
        export = export_empty_retry_gap(
            artifact_path=args.artifact,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_empty_retry_gap_export_summary(export)
        )
    if args.command == "export-blocked-retry-edit-gap":
        export = export_blocked_retry_edit_gap(
            artifact_path=args.artifact,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_blocked_retry_edit_gap_export_summary(export)
        )
    if args.command == "review-blocked-retry-edit-gaps":
        review = review_blocked_retry_edit_gap_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_blocked_retry_edit_gap_review_summary(review)
        )
    if args.command == "review-empty-retry-gaps":
        review = review_empty_retry_gap_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_empty_retry_gap_review_summary(review)
        )
    if args.command == "review-repeated-forbidden-retry-gaps":
        review = review_repeated_forbidden_retry_gap_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repeated_forbidden_retry_gap_review_summary(review)
        )
    if args.command == "review-retry-repair-edits":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="repair-edit extraction artifact",
        )
        extraction = normalize_repair_edit_extraction_artifact(artifact)
        if extraction is None:
            raise BiberAgentClientError(
                "review-retry-repair-edits artifact must contain a saved "
                "extract-repair-edits JSON object."
            )
        review = build_retry_repair_edit_review(
            extraction_path=artifact_path,
            extraction=extraction,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_retry_repair_edit_review_summary(review)
        )
    if args.command == "export-mvp-failures":
        export = export_mvp_loop_failures(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_failure_export_summary(export)
        )
    if args.command == "export-verified-repair":
        export = export_verified_repair_review(
            artifact_path=args.artifact,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_verified_repair_export_summary(export)
        )
    if args.command == "review-verified-repairs":
        review = review_verified_repair_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_verified_repair_review_summary(review)
        )
    if args.command == "show-verified-repair-review":
        artifact = load_json_artifact(
            args.artifact,
            label="verified repair review artifact",
        )
        normalized = normalize_verified_repair_review_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "verified repair review artifact must contain a saved "
                "review-verified-repairs JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_verified_repair_review_summary(normalized)
        )
    if args.command == "list-verified-repair-reviews":
        artifacts = list_verified_repair_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_verified_repair_review_artifact_list_summary(artifacts)
        )
    if args.command == "show-repair-chain":
        repo_provenance = complete_repo_provenance_from_git(
            {
                "root": args.source_repo_root,
                "url": args.source_repo_url,
                "commit": args.source_repo_commit,
                "branch": args.source_repo_branch,
            }
        )
        summary = build_repair_chain_summary(
            mvp_loop_path=args.mvp_loop,
            repair_path=args.repair,
            attempt_path=args.attempt,
            extraction_path=args.extraction,
            plan_path=args.plan,
            apply_path=args.apply,
            verification_path=args.verification,
            review_jsonl_paths=args.review_jsonl or [],
            review_summary_path=args.review_summary,
            repo_provenance=repo_provenance,
        )
        if args.output:
            summary["artifact_path"] = str(Path(args.output))
            write_json_artifact(summary, args.output)
        return (
            json.dumps(summary, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_summary(summary)
        )
    if args.command == "list-repair-chains":
        artifacts = list_repair_chain_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        if args.output:
            artifacts["artifact_path"] = str(Path(args.output))
            write_json_artifact(artifacts, args.output)
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_artifact_list_summary(artifacts)
        )
    if args.command == "export-ready-repair-chains":
        export = export_ready_repair_chain_reviews(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_export_summary(export)
        )
    if args.command == "review-ready-repair-chains":
        review = review_ready_repair_chain_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_review_summary(review)
        )
    if args.command == "show-ready-repair-chain-review":
        artifact = load_json_artifact(
            args.artifact,
            label="ready repair-chain review artifact",
        )
        normalized = normalize_ready_repair_chain_review_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "ready repair-chain review artifact must contain a saved "
                "review-ready-repair-chains JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_review_summary(normalized)
        )
    if args.command == "list-ready-repair-chain-reviews":
        artifacts = list_ready_repair_chain_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_review_artifact_list_summary(artifacts)
        )
    if args.command == "record-ready-repair-chain-decision":
        decision = record_ready_repair_chain_decisions(
            jsonl_paths=args.jsonl,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
            evidence_source_type=args.evidence_source_type,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(decision, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_decision_export_summary(decision)
        )
    if args.command == "review-ready-repair-chain-decisions":
        decision_review = review_ready_repair_chain_decision_records(
            jsonl_paths=args.jsonl,
        )
        if args.output:
            decision_review["artifact_path"] = str(Path(args.output))
            write_json_artifact(decision_review, args.output)
        return (
            json.dumps(decision_review, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_decision_review_summary(decision_review)
        )
    if args.command == "show-ready-repair-chain-decision-review":
        artifact = load_json_artifact(
            args.artifact,
            label="ready repair-chain decision review artifact",
        )
        normalized = normalize_ready_repair_chain_decision_review_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "ready repair-chain decision review artifact must contain a "
                "saved review-ready-repair-chain-decisions JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_decision_review_summary(normalized)
        )
    if args.command == "list-ready-repair-chain-decision-reviews":
        artifacts = list_ready_repair_chain_decision_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            decision=args.decision,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_decision_review_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "export-ready-repair-chain-eval-candidates":
        export = export_ready_repair_chain_eval_candidates(
            jsonl_paths=args.jsonl,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_candidate_export_summary(export)
        )
    if args.command == "review-ready-repair-chain-eval-candidates":
        review = review_ready_repair_chain_eval_candidate_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_candidate_review_summary(review)
        )
    if args.command == "show-ready-repair-chain-eval-candidate-review":
        artifact = load_json_artifact(
            args.artifact,
            label="ready repair-chain eval-candidate review artifact",
        )
        normalized = normalize_ready_repair_chain_eval_candidate_review_artifact(
            artifact
        )
        if normalized is None:
            raise BiberAgentClientError(
                "ready repair-chain eval-candidate review artifact must contain "
                "a saved review-ready-repair-chain-eval-candidates JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_candidate_review_summary(normalized)
        )
    if args.command == "list-ready-repair-chain-eval-candidate-reviews":
        artifacts = list_ready_repair_chain_eval_candidate_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_candidate_review_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "record-ready-repair-chain-eval-candidate-decision":
        decision = record_ready_repair_chain_eval_candidate_decisions(
            jsonl_paths=args.jsonl,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(decision, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_candidate_decision_export_summary(
                decision
            )
        )
    if args.command == "review-ready-repair-chain-eval-dataset-decisions":
        review = review_ready_repair_chain_eval_dataset_decision_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_dataset_decision_review_summary(
                review
            )
        )
    if args.command == "show-ready-repair-chain-eval-dataset-decision-review":
        artifact = load_json_artifact(
            args.artifact,
            label="ready repair-chain eval-dataset decision review artifact",
        )
        normalized = normalize_ready_repair_chain_eval_dataset_decision_review_artifact(
            artifact
        )
        if normalized is None:
            raise BiberAgentClientError(
                "ready repair-chain eval-dataset decision review artifact must "
                "contain a saved review-ready-repair-chain-eval-dataset-decisions "
                "JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_dataset_decision_review_summary(
                normalized
            )
        )
    if args.command == "list-ready-repair-chain-eval-dataset-decision-reviews":
        artifacts = list_ready_repair_chain_eval_dataset_decision_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            decision=args.decision,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_dataset_decision_review_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "export-ready-repair-chain-eval-dataset":
        export = export_ready_repair_chain_eval_dataset(
            jsonl_paths=args.jsonl,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_dataset_export_summary(export)
        )
    if args.command == "validate-ready-repair-chain-eval-dataset":
        validation = validate_ready_repair_chain_eval_dataset_records(
            jsonl_paths=args.jsonl,
            min_records=args.min_records,
        )
        if args.output:
            validation["artifact_path"] = str(Path(args.output))
            write_json_artifact(validation, args.output)
        return (
            json.dumps(validation, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_dataset_validation_summary(
                validation
            )
        )
    if args.command == "show-ready-repair-chain-eval-dataset-validation":
        artifact = load_json_artifact(
            args.artifact,
            label="ready repair-chain eval-dataset validation artifact",
        )
        normalized = normalize_ready_repair_chain_eval_dataset_validation_artifact(
            artifact
        )
        if normalized is None:
            raise BiberAgentClientError(
                "ready repair-chain eval-dataset validation artifact must contain "
                "a saved validate-ready-repair-chain-eval-dataset JSON object."
            )
        return (
            json.dumps(normalized, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_dataset_validation_summary(
                normalized
            )
        )
    if args.command == "list-ready-repair-chain-eval-dataset-validations":
        artifacts = list_ready_repair_chain_eval_dataset_validation_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ok_only=args.ok_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_dataset_validation_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "export-ready-repair-chain-eval-prompts":
        export = export_ready_repair_chain_eval_prompts(
            jsonl_paths=args.jsonl,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_prompt_export_summary(export)
        )
    if args.command == "show-ready-repair-chain-eval-prompts":
        inspection = inspect_ready_repair_chain_eval_prompt_records(
            jsonl_paths=args.jsonl,
            min_records=args.min_records,
        )
        return (
            json.dumps(inspection, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_prompt_inspection_summary(
                inspection
            )
        )
    if args.command == "list-ready-repair-chain-eval-prompts":
        artifacts = list_ready_repair_chain_eval_prompt_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_ready_repair_chain_eval_prompt_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "review-repair-chain-heldout-eval-results":
        review = review_repair_chain_heldout_eval_results(
            jsonl_paths=args.jsonl,
            min_passes=args.min_passes,
            summary_path=args.summary,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_eval_review_summary(review)
        )
    if args.command == "show-repair-chain-heldout-eval-review":
        raw_payload = load_json_artifact(
            args.artifact,
            label="repair-chain held-out eval review artifact",
        )
        review = normalize_repair_chain_heldout_eval_review_artifact(raw_payload)
        if review is None:
            raise BiberAgentClientError(
                "show-repair-chain-heldout-eval-review requires a held-out eval review artifact."
            )
        if not review.get("artifact_path"):
            review["artifact_path"] = str(Path(args.artifact))
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_eval_review_summary(review)
        )
    if args.command == "list-repair-chain-heldout-eval-reviews":
        artifacts = list_repair_chain_heldout_eval_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ok_only=args.ok_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_eval_review_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "record-repair-chain-heldout-eval-decision":
        decision = record_repair_chain_heldout_eval_decisions(
            artifact_paths=args.artifact,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(decision, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_eval_decision_export_summary(decision)
        )
    if args.command == "review-repair-chain-heldout-eval-decisions":
        review = review_repair_chain_heldout_eval_decision_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_eval_decision_review_summary(review)
        )
    if args.command == "show-repair-chain-heldout-eval-decision-review":
        raw_payload = load_json_artifact(
            args.artifact,
            label="repair-chain held-out eval decision review artifact",
        )
        review = normalize_repair_chain_heldout_eval_decision_review_artifact(
            raw_payload
        )
        if review is None:
            raise BiberAgentClientError(
                "show-repair-chain-heldout-eval-decision-review requires a held-out eval decision review artifact."
            )
        if not review.get("artifact_path"):
            review["artifact_path"] = str(Path(args.artifact))
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_eval_decision_review_summary(review)
        )
    if args.command == "list-repair-chain-heldout-eval-decision-reviews":
        artifacts = list_repair_chain_heldout_eval_decision_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            decision=args.decision,
            baseline_ready_only=args.baseline_ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_eval_decision_review_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "export-repair-chain-heldout-baseline-candidates":
        export = export_repair_chain_heldout_baseline_candidates(
            jsonl_paths=args.jsonl,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_baseline_candidate_export_summary(
                export
            )
        )
    if args.command == "review-repair-chain-heldout-baseline-candidates":
        review = review_repair_chain_heldout_baseline_candidate_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_baseline_candidate_review_summary(
                review
            )
        )
    if args.command == "show-repair-chain-heldout-baseline-candidate-review":
        raw_payload = load_json_artifact(
            args.artifact,
            label="repair-chain held-out baseline candidate review artifact",
        )
        review = normalize_repair_chain_heldout_baseline_candidate_review_artifact(
            raw_payload
        )
        if review is None:
            raise BiberAgentClientError(
                "Artifact is not a repair-chain held-out baseline candidate review."
            )
        if not review.get("artifact_path"):
            review["artifact_path"] = str(Path(args.artifact))
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_baseline_candidate_review_summary(
                review
            )
        )
    if args.command == "list-repair-chain-heldout-baseline-candidate-reviews":
        artifacts = list_repair_chain_heldout_baseline_candidate_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            candidate_ready_only=args.candidate_ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_baseline_candidate_review_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "record-repair-chain-heldout-baseline-candidate-decision":
        decision = record_repair_chain_heldout_baseline_candidate_decisions(
            jsonl_paths=args.jsonl,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
            limit=args.limit,
            output_path=args.output,
        )
        return (
            json.dumps(decision, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_baseline_decision_export_summary(
                decision
            )
        )
    if args.command == "review-repair-chain-heldout-baseline-decisions":
        review = review_repair_chain_heldout_baseline_decision_records(
            jsonl_paths=args.jsonl,
            min_repeat=args.min_repeat,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_baseline_decision_review_summary(
                review
            )
        )
    if args.command == "show-repair-chain-heldout-baseline-decision-review":
        raw_payload = load_json_artifact(
            args.artifact,
            label="repair-chain held-out baseline decision review artifact",
        )
        review = normalize_repair_chain_heldout_baseline_decision_review_artifact(
            raw_payload
        )
        if review is None:
            raise BiberAgentClientError(
                "Artifact is not a repair-chain held-out baseline decision review."
            )
        if not review.get("artifact_path"):
            review["artifact_path"] = str(Path(args.artifact))
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_baseline_decision_review_summary(
                review
            )
        )
    if args.command == "list-repair-chain-heldout-baseline-decision-reviews":
        artifacts = list_repair_chain_heldout_baseline_decision_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            decision=args.decision,
            baseline_ready_only=args.baseline_ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_heldout_baseline_decision_review_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "review-repair-chain-training-readiness":
        review = review_repair_chain_training_readiness(
            review_paths=args.review_artifact,
            min_baseline_ready=args.min_baseline_ready,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_readiness_summary(review)
        )
    if args.command == "show-repair-chain-training-readiness":
        raw_payload = load_json_artifact(
            args.artifact,
            label="repair-chain training readiness artifact",
        )
        review = normalize_repair_chain_training_readiness_artifact(raw_payload)
        if review is None:
            raise BiberAgentClientError(
                "Artifact is not a repair-chain training readiness review."
            )
        if not review.get("artifact_path"):
            review["artifact_path"] = str(Path(args.artifact))
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_readiness_summary(review)
        )
    if args.command == "list-repair-chain-training-readiness":
        artifacts = list_repair_chain_training_readiness_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_readiness_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "export-repair-chain-training-candidates":
        export = export_repair_chain_training_candidates(
            readiness_paths=args.readiness_artifact,
            output_path=args.output,
            limit=args.limit,
        )
        return (
            json.dumps(export, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_candidate_export_summary(export)
        )
    if args.command == "review-repair-chain-training-candidates":
        review = review_repair_chain_training_candidate_records(
            jsonl_paths=args.jsonl,
            min_ready=args.min_ready,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_candidate_review_summary(review)
        )
    if args.command == "show-repair-chain-training-candidate-review":
        raw_payload = load_json_artifact(
            args.artifact,
            label="repair-chain training candidate review artifact",
        )
        review = normalize_repair_chain_training_candidate_review_artifact(
            raw_payload
        )
        if review is None:
            raise BiberAgentClientError(
                "Artifact is not a repair-chain training candidate review."
            )
        if not review.get("artifact_path"):
            review["artifact_path"] = str(Path(args.artifact))
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_candidate_review_summary(review)
        )
    if args.command == "list-repair-chain-training-candidate-reviews":
        artifacts = list_repair_chain_training_candidate_review_artifacts(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_candidate_review_artifact_list_summary(
                artifacts
            )
        )
    if args.command == "review-repair-chain-training-pipeline":
        review = review_repair_chain_training_pipeline_status(
            artifact_dir=args.artifact_dir,
        )
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_pipeline_status_summary(review)
        )
    if args.command == "show-repair-chain-training-pipeline":
        raw_payload = load_json_artifact(
            args.artifact,
            label="repair-chain training pipeline artifact",
        )
        review = normalize_repair_chain_training_pipeline_status_artifact(
            raw_payload
        )
        if review is None:
            raise BiberAgentClientError(
                "Artifact is not a repair-chain training pipeline status."
            )
        if not review.get("artifact_path"):
            review["artifact_path"] = str(Path(args.artifact))
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_pipeline_status_summary(review)
        )
    if args.command == "list-repair-chain-training-pipelines":
        artifacts = list_repair_chain_training_pipeline_statuses(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
            ready_only=args.ready_only,
        )
        if args.output:
            artifacts["artifact_path"] = str(Path(args.output))
            write_json_artifact(artifacts, args.output)
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_chain_training_pipeline_list_summary(artifacts)
        )
    if args.command == "prepare-repair":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(str(artifact_path), label="mvp-loop artifact")
        normalized = normalize_mvp_loop_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "prepare-repair artifact must contain a saved MVP loop JSON object."
            )
        repair = build_mvp_loop_repair_request(
            path=artifact_path,
            payload=normalized,
            instruction=args.instruction,
            max_relevant_output_chars=args.max_relevant_output_chars,
            max_context_paths=args.max_context_paths,
        )
        if args.output:
            repair["artifact_path"] = str(Path(args.output))
            write_json_artifact(repair, args.output)
        return (
            json.dumps(repair, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_repair_request_summary(repair)
        )
    if args.command == "local-repair-chain":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="mvp-loop or repair request artifact",
        )
        repair_request = build_or_load_repair_request(
            path=artifact_path,
            artifact=artifact,
            instruction=args.instruction,
            max_relevant_output_chars=args.max_relevant_output_chars,
            max_context_paths=args.max_context_paths,
        )
        response_source_count = sum(
            1
            for value in (args.model_response, args.model_response_file, args.model_command)
            if value
        )
        if response_source_count != 1:
            raise BiberAgentClientError(
                "local-repair-chain requires exactly one of --model-response, "
                "--model-response-file, or --model-command."
            )
        if args.model_command:
            local_model_request = build_local_model_command_request(
                repair_request=repair_request,
                model=args.model,
            )
            model_response_text, model_response_source = run_local_model_command(
                command=args.model_command,
                request=local_model_request,
                timeout_seconds=args.model_command_timeout_seconds,
            )
        else:
            model_response_text = load_text_argument(
                value=args.model_response,
                file_path=args.model_response_file,
                label="--model-response",
            )
            model_response_source = {
                "source": (
                    "local_model_response_file"
                    if args.model_response_file
                    else "local_model_response_inline"
                )
            }
        target_root = (
            validate_local_target_root(Path(args.target_root))
            if args.target_root
            else None
        )
        chain = build_local_repair_chain_result(
            source_path=artifact_path,
            repair_request=repair_request,
            model_response_text=model_response_text,
            model_response_source=model_response_source,
            model=args.model,
            max_edits=args.max_edits,
            max_files=args.max_files,
            target_root=target_root,
        )
        if args.output:
            chain["artifact_path"] = str(Path(args.output))
            write_json_artifact(chain, args.output)
        return (
            json.dumps(chain, indent=2, sort_keys=True)
            if args.print_json
            else format_local_repair_chain_summary(chain)
        )
    if args.command == "review-local-repair-chain":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="local-repair-chain artifact",
        )
        chain = normalize_local_repair_chain_artifact(artifact)
        if chain is None:
            raise BiberAgentClientError(
                "review-local-repair-chain artifact must contain a saved "
                "local-repair-chain JSON object."
            )
        review = review_local_repair_chain(chain)
        review["source_artifact"] = str(artifact_path)
        if args.output:
            review["artifact_path"] = str(Path(args.output))
            write_json_artifact(review, args.output)
        return (
            json.dumps(review, indent=2, sort_keys=True)
            if args.print_json
            else format_local_repair_chain_review_summary(review)
        )
    if args.command == "local-verify-chain":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="repair-edit apply artifact",
        )
        repair_apply = normalize_repair_edit_apply_artifact(artifact)
        if repair_apply is None:
            raise BiberAgentClientError(
                "local-verify-chain artifact must contain a saved repair-edit apply JSON object."
            )
        test_payload = build_verify_repair_edits_payload(
            repair_apply,
            test_id=args.test_id,
            dry_run=args.dry_run,
        )
        target_root, target_root_source = resolve_verify_target_root(
            cli_target_root=args.target_root,
            repair_apply=repair_apply,
        )
        if target_root is None:
            raise BiberAgentClientError(
                "local-verify-chain requires --target-root or target_root in the apply artifact."
            )
        test_run = run_allowlisted_test_local_target(
            target_root=target_root,
            payload=test_payload,
        )
        if (
            args.diagnose_on_failure
            and test_run.get("executed") is True
            and test_run.get("ok") is False
        ):
            diagnosis = diagnose_test_failure_local(
                test_run,
                max_context_lines=args.max_context_lines,
            )
            test_run = dict(test_run)
            test_run["diagnosis"] = diagnosis
        verification = build_verify_repair_edits_result(
            apply_path=artifact_path,
            repair_apply=repair_apply,
            test_payload=test_payload,
            test_run=test_run,
            test_mode="local_target_root",
            target_root=target_root,
            target_root_source=target_root_source,
        )
        chain = build_local_repair_verification_chain_result(
            apply_path=artifact_path,
            repair_apply=repair_apply,
            verification=verification,
        )
        if args.output:
            chain["artifact_path"] = str(Path(args.output))
            write_json_artifact(chain, args.output)
        return (
            json.dumps(chain, indent=2, sort_keys=True)
            if args.print_json
            else format_local_repair_verification_chain_summary(chain)
        )
    if args.command == "prepare-local-verify-repair":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="local verification chain artifact",
        )
        chain = normalize_local_repair_verification_chain_artifact(artifact)
        if chain is None:
            raise BiberAgentClientError(
                "prepare-local-verify-repair artifact must contain a saved "
                "local-verify-chain JSON object."
            )
        apply_path, repair_apply, apply_error = load_linked_artifact(
            chain.get("source_artifact"),
            base_path=artifact_path,
            label="repair-edit apply artifact",
            normalizer=normalize_repair_edit_apply_artifact,
        )
        repair = build_local_verification_repair_request(
            path=artifact_path,
            chain=chain,
            repair_apply=repair_apply,
            instruction=args.instruction,
            max_relevant_output_chars=args.max_relevant_output_chars,
            max_context_paths=args.max_context_paths,
        )
        if apply_path is not None:
            repair["linked_apply_artifact"] = str(apply_path)
        if apply_error is not None:
            repair["linked_apply_artifact_error"] = apply_error
        if args.output:
            repair["artifact_path"] = str(Path(args.output))
            write_json_artifact(repair, args.output)
        return (
            json.dumps(repair, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_repair_request_summary(repair)
        )
    if args.command == "local-repair-loop-status":
        status = build_local_repair_loop_status(
            directory=args.directory,
            pattern=args.pattern,
            limit=args.limit,
        )
        if args.output:
            status["artifact_path"] = str(Path(args.output))
            write_json_artifact(status, args.output)
        return (
            json.dumps(status, indent=2, sort_keys=True)
            if args.print_json
            else format_local_repair_loop_status_summary(status)
        )
    if args.command == "extract-repair-edits":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(str(artifact_path), label="repair-attempt artifact")
        normalized = normalize_repair_attempt_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "extract-repair-edits artifact must contain a saved repair-attempt JSON object."
            )
        extraction = extract_repair_edits(
            path=artifact_path,
            payload=normalized,
            max_edits=args.max_edits,
            max_files=args.max_files,
        )
        if args.edits_output:
            extraction["edits_output"] = write_json_artifact(
                require_mapping(extraction.get("plan_edit_payload")),
                args.edits_output,
            )
        if args.output:
            extraction["artifact_path"] = str(Path(args.output))
            write_json_artifact(extraction, args.output)
        return (
            json.dumps(extraction, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_extraction_summary(extraction)
        )
    if args.command == "plan-repair-edits":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="repair-edit extraction artifact",
        )
        extraction = normalize_repair_edit_extraction_artifact(artifact)
        if extraction is None:
            raise BiberAgentClientError(
                "plan-repair-edits artifact must contain a saved repair-edit extraction JSON object."
            )
        plan_payload = build_plan_repair_edits_payload_with_retry_review(
            extraction_path=artifact_path,
            extraction=extraction,
            max_files=args.max_files,
            retry_review_artifact=args.retry_review_artifact,
        )
        target_root, target_root_source = resolve_repair_target_root(
            cli_target_root=args.target_root,
            extraction_path=artifact_path,
            extraction=extraction,
        )
        if target_root is not None:
            edit_plan = plan_workspace_edit_local_target(
                target_root=target_root,
                payload=plan_payload,
            )
            plan_mode = "local_target_root"
        else:
            api_key = resolve_api_key(args.api_key)
            base_url = args.base_url.rstrip("/")
            edit_plan = plan_workspace_edit(
                base_url=base_url,
                api_key=api_key,
                payload=plan_payload,
                timeout_seconds=args.timeout_seconds,
            )
            plan_mode = "api_workspace_root"
        result = build_plan_repair_edits_result(
            extraction_path=artifact_path,
            extraction=extraction,
            plan_payload=plan_payload,
            edit_plan=edit_plan,
            plan_mode=plan_mode,
            target_root=target_root,
            target_root_source=target_root_source,
        )
        if args.output:
            result["artifact_path"] = str(Path(args.output))
            write_json_artifact(result, args.output)
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_plan_summary(result)
        )

    if args.command == "apply-repair-edits" and not args.approve:
        raise BiberAgentClientError(
            "apply-repair-edits requires --approve before any files can be changed."
        )
    if (
        args.command == "mvp-loop"
        and args.include_git_state
        and not args.local_target_root
    ):
        raise BiberAgentClientError(
            "mvp-loop --include-git-state requires --local-target-root."
        )

    if args.command == "save-github" and args.dry_run:
        content = load_text_argument(
            value=args.content,
            file_path=args.content_file,
            label="--content",
        )
        if not content:
            raise BiberAgentClientError("GitHub save requires --content or --content-file.")
        result = build_github_save_dry_run_result(
            build_github_save_payload(
                path=args.path,
                content=content,
                owner=args.owner,
                repo=args.repo,
                branch=args.branch,
                base_branch=args.base_branch,
                create_branch_if_missing=args.create_branch_if_missing,
                commit_message=args.commit_message,
            )
        )
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_github_save_dry_run_summary(result)
        )

    if args.command == "create-pr" and args.dry_run:
        if args.head == args.base:
            raise BiberAgentClientError("PR head and base branches must differ.")
        body = load_text_argument(
            value=args.body,
            file_path=args.body_file,
            label="--body",
        )
        result = build_github_pull_request_dry_run_result(
            build_github_pull_request_payload(
                head=args.head,
                base=args.base,
                title=args.title,
                body=body,
                owner=args.owner,
                repo=args.repo,
                draft=not args.ready,
            )
        )
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_github_pull_request_dry_run_summary(result)
        )

    mvp_loop_uses_only_local_steps = (
        args.command == "mvp-loop"
        and bool(args.local_target_root)
        and (not args.save_github_path or args.github_dry_run)
        and (not args.create_pr or args.github_dry_run)
    )
    apply_repair_edits_uses_only_local_steps = apply_repair_edits_has_local_target(args)
    if mvp_loop_uses_only_local_steps or apply_repair_edits_uses_only_local_steps:
        api_key = ""
        base_url = args.base_url.rstrip("/")
    else:
        api_key = resolve_api_key(args.api_key)
        base_url = args.base_url.rstrip("/")
    if args.command == "attempt-repair":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="mvp-loop or repair request artifact",
        )
        repair_request = build_or_load_repair_request(
            path=artifact_path,
            artifact=artifact,
            instruction=args.instruction,
            max_relevant_output_chars=args.max_relevant_output_chars,
            max_context_paths=args.max_context_paths,
        )
        cli_runtime_profile_ids = dedupe_strings(args.runtime_profile_id)
        inherited_runtime_profile_ids = normalize_runtime_profile_ids(
            repair_request.get("runtime_profile_ids")
        )
        runtime_profile_ids = (
            cli_runtime_profile_ids
            if cli_runtime_profile_ids is not None
            else inherited_runtime_profile_ids
        )
        if runtime_profile_ids:
            capabilities = fetch_capabilities(
                base_url=base_url,
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            validate_runtime_profile_ids(
                capabilities=capabilities,
                runtime_profile_ids=runtime_profile_ids,
            )
        chat_payload = build_repair_chat_payload(
            repair_request=repair_request,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            use_mentor=args.use_mentor,
            runtime_profile_ids=runtime_profile_ids,
        )
        model_response = chat_with_biber(
            base_url=base_url,
            api_key=api_key,
            payload=chat_payload,
            timeout_seconds=args.timeout_seconds,
        )
        attempt = build_repair_attempt_result(
            repair_request=repair_request,
            chat_payload=chat_payload,
            model_response=model_response,
        )
        if args.output:
            attempt["artifact_path"] = str(Path(args.output))
            write_json_artifact(attempt, args.output)
        return (
            json.dumps(attempt, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_repair_attempt_summary(attempt)
        )
    if args.command == "apply-repair-edits":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="repair-edit plan artifact",
        )
        plan = normalize_repair_edit_plan_artifact(artifact)
        if plan is None:
            raise BiberAgentClientError(
                "apply-repair-edits artifact must contain a saved repair-edit plan JSON object."
            )
        apply_payload = build_apply_repair_edits_payload(plan)
        review_gate: dict[str, Any] | None = None
        if args.review_artifact:
            review_path = Path(args.review_artifact)
            review_artifact = load_json_artifact(
                str(review_path),
                label="local repair chain review artifact",
            )
            review = normalize_local_repair_chain_review_artifact(review_artifact)
            if review is None:
                raise BiberAgentClientError(
                    "apply-repair-edits --review-artifact must contain a saved "
                    "review-local-repair-chain JSON object."
                )
            review_gate = validate_local_repair_chain_review_for_apply(
                review_path=review_path,
                review=review,
                plan=plan,
            )
        target_root, _target_root_source = resolve_apply_target_root(
            cli_target_root=args.target_root,
            plan=plan,
        )
        if target_root is not None:
            edit_apply = apply_workspace_edit_plan_local_target(
                target_root=target_root,
                payload=apply_payload,
            )
        else:
            edit_apply = apply_workspace_edit_plan(
                base_url=base_url,
                api_key=api_key,
                payload=apply_payload,
                timeout_seconds=args.timeout_seconds,
            )
        result = build_apply_repair_edits_result(
            plan_path=artifact_path,
            plan=plan,
            apply_payload=apply_payload,
            edit_apply=edit_apply,
            review_gate=review_gate,
        )
        if args.output:
            result["artifact_path"] = str(Path(args.output))
            write_json_artifact(result, args.output)
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_apply_summary(result)
        )
    if args.command == "verify-repair-edits":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(
            str(artifact_path),
            label="repair-edit apply artifact",
        )
        repair_apply = normalize_repair_edit_apply_artifact(artifact)
        if repair_apply is None:
            raise BiberAgentClientError(
                "verify-repair-edits artifact must contain a saved repair-edit apply JSON object."
            )
        test_payload = build_verify_repair_edits_payload(
            repair_apply,
            test_id=args.test_id,
            dry_run=args.dry_run,
        )
        target_root, target_root_source = resolve_verify_target_root(
            cli_target_root=args.target_root,
            repair_apply=repair_apply,
        )
        if target_root is not None:
            test_run = run_allowlisted_test_local_target(
                target_root=target_root,
                payload=test_payload,
            )
            test_mode = "local_target_root"
        else:
            test_run = run_allowlisted_test(
                base_url=base_url,
                api_key=api_key,
                payload=test_payload,
                timeout_seconds=args.timeout_seconds,
            )
            test_mode = "api_workspace_root"
        if (
            args.diagnose_on_failure
            and test_run.get("executed") is True
            and test_run.get("ok") is False
        ):
            if target_root is not None:
                diagnosis = diagnose_test_failure_local(
                    test_run,
                    max_context_lines=args.max_context_lines,
                )
            else:
                diagnosis = diagnose_test_failure(
                    base_url=base_url,
                    api_key=api_key,
                    payload=build_diagnosis_payload_from_test_run(
                        test_run,
                        max_context_lines=args.max_context_lines,
                    ),
                    timeout_seconds=args.timeout_seconds,
                )
            test_run = dict(test_run)
            test_run["diagnosis"] = diagnosis
        result = build_verify_repair_edits_result(
            apply_path=artifact_path,
            repair_apply=repair_apply,
            test_payload=test_payload,
            test_run=test_run,
            test_mode=test_mode,
            target_root=target_root,
            target_root_source=target_root_source,
        )
        if args.output:
            result["artifact_path"] = str(Path(args.output))
            write_json_artifact(result, args.output)
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_test_verification_summary(result)
        )
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
    if args.command == "chat":
        runtime_profile_ids = dedupe_strings(args.runtime_profile_id)
        if runtime_profile_ids:
            capabilities = fetch_capabilities(
                base_url=base_url,
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            validate_runtime_profile_ids(
                capabilities=capabilities,
                runtime_profile_ids=runtime_profile_ids,
            )
        message = load_text_argument(
            value=args.message,
            file_path=args.message_file,
            label="--message",
        )
        if not message:
            raise BiberAgentClientError("chat requires --message or --message-file.")
        response = chat_with_biber(
            base_url=base_url,
            api_key=api_key,
            payload=build_chat_payload(
                message=message,
                model=args.model,
                language=args.language,
                task_type=args.task_type,
                repo_context_paths=args.repo_context,
                runtime_profile_ids=runtime_profile_ids,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                use_mentor=args.use_mentor,
            ),
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(response, indent=2, sort_keys=True)
            if args.print_json
            else format_chat_summary(response)
        )
    if args.command == "create-session":
        capabilities = fetch_capabilities(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
        runtime_profile_ids = dedupe_strings(args.runtime_profile_id)
        validate_runtime_profile_ids(
            capabilities=capabilities,
            runtime_profile_ids=runtime_profile_ids,
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
            runtime_profile_ids=runtime_profile_ids,
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
    if args.command == "plan-context":
        payload = build_repo_context_payload(
            instruction=args.instruction,
            pinned_paths=args.pinned_path,
            changed_paths=args.changed_path,
            max_files=args.max_files,
            max_scan_files=args.max_scan_files,
        )
        plan = plan_repo_context(
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(plan, indent=2, sort_keys=True)
            if args.print_json
            else format_repo_context_summary(plan)
        )
    if args.command == "plan-edit":
        edits = load_workspace_edits(
            edit_json_values=args.edit_json,
            edits_file=args.edits_file,
        )
        payload = build_workspace_edit_payload(
            edits=edits,
            max_files=args.max_files,
        )
        plan = plan_workspace_edit(
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(plan, indent=2, sort_keys=True)
            if args.print_json
            else format_workspace_edit_plan_summary(plan)
        )
    if args.command == "apply-edit":
        edits = load_workspace_edits(
            edit_json_values=args.edit_json,
            edits_file=args.edits_file,
        )
        payload = build_workspace_edit_payload(
            edits=edits,
            max_files=args.max_files,
            plan_hash=args.plan_hash,
        )
        result = apply_workspace_edit_plan(
            base_url=base_url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_workspace_edit_apply_summary(result)
        )
    if args.command == "list-tests":
        tests = list_test_commands(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(tests, indent=2, sort_keys=True)
            if args.print_json
            else format_test_list_summary(tests)
        )
    if args.command == "run-test":
        result = run_allowlisted_test(
            base_url=base_url,
            api_key=api_key,
            payload=build_test_run_payload(
                test_id=args.test_id,
                dry_run=args.dry_run,
            ),
            timeout_seconds=args.timeout_seconds,
        )
        if (
            args.diagnose_on_failure
            and result.get("executed") is True
            and result.get("ok") is False
        ):
            diagnosis = diagnose_test_failure(
                base_url=base_url,
                api_key=api_key,
                payload=build_diagnosis_payload_from_test_run(
                    result,
                    max_context_lines=args.max_context_lines,
                ),
                timeout_seconds=args.timeout_seconds,
            )
            result = dict(result)
            result["diagnosis"] = diagnosis
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_test_run_summary(result)
        )
    if args.command == "diagnose-test":
        stdout = load_text_argument(
            value=args.stdout,
            file_path=args.stdout_file,
            label="--stdout",
        )
        stderr = load_text_argument(
            value=args.stderr,
            file_path=args.stderr_file,
            label="--stderr",
        )
        diagnosis = diagnose_test_failure(
            base_url=base_url,
            api_key=api_key,
            payload=build_test_diagnosis_payload(
                test_id=args.test_id,
                command_json=args.command_json,
                command_parts=args.command_part,
                exit_code=args.exit_code,
                timed_out=args.timed_out,
                stdout=stdout,
                stderr=stderr,
                max_context_lines=args.max_context_lines,
            ),
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(diagnosis, indent=2, sort_keys=True)
            if args.print_json
            else format_test_diagnosis_summary(diagnosis)
        )
    if args.command == "save-github":
        content = load_text_argument(
            value=args.content,
            file_path=args.content_file,
            label="--content",
        )
        if not content:
            raise BiberAgentClientError("GitHub save requires --content or --content-file.")
        result = save_to_github(
            base_url=base_url,
            api_key=api_key,
            payload=build_github_save_payload(
                path=args.path,
                content=content,
                owner=args.owner,
                repo=args.repo,
                branch=args.branch,
                base_branch=args.base_branch,
                create_branch_if_missing=args.create_branch_if_missing,
                commit_message=args.commit_message,
            ),
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_github_save_summary(result)
        )
    if args.command == "create-pr":
        body = load_text_argument(
            value=args.body,
            file_path=args.body_file,
            label="--body",
        )
        result = create_github_pull_request(
            base_url=base_url,
            api_key=api_key,
            payload=build_github_pull_request_payload(
                head=args.head,
                base=args.base,
                title=args.title,
                body=body,
                owner=args.owner,
                repo=args.repo,
                draft=not args.ready,
            ),
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_github_pull_request_summary(result)
        )
    if args.command == "mvp-loop":
        steps: dict[str, Any] = {}
        runtime_profile_ids = dedupe_strings(args.runtime_profile_id)
        target_root: Path | None = None
        target_root_source: str | None = None
        if args.local_target_root:
            target_root = validate_local_target_root(Path(args.local_target_root))
            target_root_source = "cli_local_target_root"
        if runtime_profile_ids and target_root is None:
            capabilities = fetch_capabilities(
                base_url=base_url,
                api_key=api_key,
                timeout_seconds=args.timeout_seconds,
            )
            validate_runtime_profile_ids(
                capabilities=capabilities,
                runtime_profile_ids=runtime_profile_ids,
            )
        git_state: dict[str, Any] | None = None
        if args.include_git_state and target_root is not None:
            git_state = git_status_local_target(target_root)
            steps["git_state"] = git_state
        context_payload = build_repo_context_payload(
            instruction=args.instruction,
            pinned_paths=args.pinned_path,
            changed_paths=args.changed_path,
            max_files=args.max_context_files,
            max_scan_files=args.max_scan_files,
        )
        if target_root is not None:
            context_plan = plan_repo_context_local_target(
                target_root=target_root,
                payload=context_payload,
            )
            context_mode = "local_target_root"
        else:
            context_plan = plan_repo_context(
                base_url=base_url,
                api_key=api_key,
                payload=context_payload,
                timeout_seconds=args.timeout_seconds,
            )
            context_mode = "api_workspace_root"
        steps["context_plan"] = context_plan

        selected_context_paths = [
            str(path) for path in require_list(context_plan.get("selected_paths"))
        ]
        summary: dict[str, Any] = {
            "ok": True,
            "instruction": args.instruction,
            "context_mode": context_mode,
            "selected_context_paths": selected_context_paths,
            "steps": steps,
        }
        if target_root is not None:
            summary["target_root"] = str(target_root)
            summary["target_root_source"] = target_root_source
        if git_state is not None:
            summary["git_dirty"] = git_state.get("dirty")
            summary["git_branch"] = git_state.get("branch")
            summary["git_head"] = git_state.get("head")
        if runtime_profile_ids is not None:
            summary["runtime_profile_ids"] = runtime_profile_ids

        has_edits = bool(args.edit_json or args.edits_file)
        if has_edits:
            edits = load_workspace_edits(
                edit_json_values=args.edit_json,
                edits_file=args.edits_file,
            )
            edit_payload = build_workspace_edit_payload(
                edits=edits,
                max_files=args.max_edit_files,
            )
            if target_root is not None:
                edit_plan = plan_workspace_edit_local_target(
                    target_root=target_root,
                    payload=edit_payload,
                )
                edit_mode = "local_target_root"
            else:
                edit_plan = plan_workspace_edit(
                    base_url=base_url,
                    api_key=api_key,
                    payload=edit_payload,
                    timeout_seconds=args.timeout_seconds,
                )
                edit_mode = "api_workspace_root"
            steps["edit_plan"] = edit_plan
            summary["edit_mode"] = edit_mode
            summary["edit_plan_hash"] = edit_plan.get("plan_hash")
            if edit_plan.get("ok") is not True:
                summary["ok"] = False
            elif args.apply_edits:
                plan_hash = str(edit_plan.get("plan_hash") or "")
                if len(plan_hash) != 64:
                    raise BiberAgentClientError(
                        "mvp-loop edit plan returned an invalid plan_hash."
                    )
                edit_apply_payload = build_workspace_edit_payload(
                    edits=edits,
                    max_files=args.max_edit_files,
                    plan_hash=plan_hash,
                )
                if target_root is not None:
                    edit_apply = apply_workspace_edit_plan_local_target(
                        target_root=target_root,
                        payload=edit_apply_payload,
                    )
                else:
                    edit_apply = apply_workspace_edit_plan(
                        base_url=base_url,
                        api_key=api_key,
                        payload=edit_apply_payload,
                        timeout_seconds=args.timeout_seconds,
                    )
                steps["edit_apply"] = edit_apply
                if edit_apply.get("ok") is not True:
                    summary["ok"] = False
        elif args.apply_edits:
            raise BiberAgentClientError("--apply-edits requires --edit-json or --edits-file.")

        if args.test_id:
            test_payload = build_test_run_payload(
                test_id=args.test_id,
                dry_run=args.test_dry_run,
            )
            if target_root is not None:
                test_run = run_allowlisted_test_local_target(
                    target_root=target_root,
                    payload=test_payload,
                )
                test_mode = "local_target_root"
            else:
                test_run = run_allowlisted_test(
                    base_url=base_url,
                    api_key=api_key,
                    payload=test_payload,
                    timeout_seconds=args.timeout_seconds,
                )
                test_mode = "api_workspace_root"
            steps["test_run"] = test_run
            summary["test_mode"] = test_mode
            summary["test_ok"] = test_run.get("ok")
            if test_run.get("executed") is True and test_run.get("ok") is False:
                if target_root is not None:
                    diagnosis = diagnose_test_failure_local(
                        test_run,
                        max_context_lines=args.max_context_lines,
                    )
                else:
                    diagnosis = diagnose_test_failure(
                        base_url=base_url,
                        api_key=api_key,
                        payload=build_diagnosis_payload_from_test_run(
                            test_run,
                            max_context_lines=args.max_context_lines,
                        ),
                        timeout_seconds=args.timeout_seconds,
                    )
                steps["test_diagnosis"] = diagnosis
                summary["diagnosis_summary"] = diagnosis.get("summary")
                summary["ok"] = False

        if args.save_github_path:
            content = load_text_argument(
                value=args.save_content,
                file_path=args.save_content_file,
                label="--save-content",
            )
            if not content:
                raise BiberAgentClientError(
                    "--save-github-path requires --save-content or --save-content-file."
                )
            github_save_payload = build_github_save_payload(
                path=args.save_github_path,
                content=content,
                owner=args.github_owner,
                repo=args.github_repo,
                branch=args.github_branch,
                base_branch=args.github_base_branch,
                create_branch_if_missing=args.create_branch_if_missing,
                commit_message=args.commit_message,
            )
            if args.github_dry_run:
                github_save = build_github_save_dry_run_result(github_save_payload)
                summary["github_dry_run"] = True
                summary["github_request_sent"] = False
            else:
                github_save = save_to_github(
                    base_url=base_url,
                    api_key=api_key,
                    payload=github_save_payload,
                    timeout_seconds=args.timeout_seconds,
                )
            steps["github_save"] = github_save
            summary["github_url"] = github_save.get("url")
        elif args.save_content or args.save_content_file:
            raise BiberAgentClientError(
                "--save-content and --save-content-file require --save-github-path."
            )

        if args.create_pr:
            pr_head = args.pr_head or (
                args.github_branch if args.save_github_path else None
            )
            if not pr_head:
                raise BiberAgentClientError("--create-pr requires --pr-head.")
            if pr_head == args.pr_base:
                raise BiberAgentClientError("PR head and base branches must differ.")
            if not args.pr_title:
                raise BiberAgentClientError("--create-pr requires --pr-title.")
            pr_body = load_text_argument(
                value=args.pr_body,
                file_path=args.pr_body_file,
                label="--pr-body",
            )
            pull_request_payload = build_github_pull_request_payload(
                head=pr_head,
                base=args.pr_base,
                title=args.pr_title,
                body=pr_body,
                owner=args.github_owner,
                repo=args.github_repo,
                draft=not args.pr_ready,
            )
            if args.github_dry_run:
                pull_request = build_github_pull_request_dry_run_result(
                    pull_request_payload
                )
                summary["github_dry_run"] = True
                summary["github_request_sent"] = False
            else:
                pull_request = create_github_pull_request(
                    base_url=base_url,
                    api_key=api_key,
                    payload=pull_request_payload,
                    timeout_seconds=args.timeout_seconds,
                )
            steps["github_pull_request"] = pull_request
            summary["pull_request_url"] = pull_request.get("url")
            summary["pull_request_number"] = pull_request.get("number")
        elif args.pr_head or args.pr_title or args.pr_body or args.pr_body_file:
            raise BiberAgentClientError("PR arguments require --create-pr.")

        if args.output:
            summary["artifact_path"] = str(Path(args.output))

        summary["agent_report"] = build_mvp_loop_agent_report(summary)

        if args.output:
            write_json_artifact(summary, args.output)

        return (
            json.dumps(summary, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_summary(summary)
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
