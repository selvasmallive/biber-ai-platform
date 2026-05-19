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
from pathlib import Path
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


def write_json_artifact(payload: Mapping[str, Any], output_path: str) -> str:
    path = Path(output_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
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


def normalize_mvp_loop_artifact(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    if isinstance(payload.get("steps"), dict):
        return dict(payload)
    body = payload.get("body")
    if isinstance(body, dict) and isinstance(body.get("steps"), dict):
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


def list_mvp_loop_artifacts(
    *,
    directory: str,
    pattern: str,
    limit: int,
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
        artifacts.append(summarize_mvp_loop_artifact(path, normalized))

    artifacts.sort(key=lambda item: float(item.get("modified_epoch") or 0.0), reverse=True)
    return {
        "directory": str(root),
        "pattern": pattern,
        "scanned": scanned,
        "artifacts": artifacts[:limit],
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


def format_github_pull_request_summary(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            "BIBER GitHub pull request",
            f"url: {payload.get('url', '-')}",
            f"number: {payload.get('number', '-')}",
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
    if payload.get("edit_plan_hash"):
        lines.append(f"edit_plan_hash: {payload.get('edit_plan_hash')}")
    if "test_ok" in payload:
        lines.append(f"test_ok: {payload.get('test_ok')}")
    if payload.get("diagnosis_summary"):
        lines.append(f"diagnosis: {payload.get('diagnosis_summary')}")
    if payload.get("github_url"):
        lines.append(f"github_url: {payload.get('github_url')}")
    if payload.get("pull_request_url"):
        lines.append(f"pull_request_url: {payload.get('pull_request_url')}")
    if payload.get("artifact_path"):
        lines.append(f"artifact_path: {payload.get('artifact_path')}")
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
    lines = [
        "BIBER workspace edit plan",
        f"ok: {bool(payload.get('ok'))}",
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"summary: {payload.get('summary', '-')}",
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
    mvp_loop.add_argument("--max-context-files", type=int)
    mvp_loop.add_argument("--max-scan-files", type=int)
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
        )
        return (
            json.dumps(artifacts, indent=2, sort_keys=True)
            if args.print_json
            else format_mvp_loop_artifact_list_summary(artifacts)
        )

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
        context_plan = plan_repo_context(
            base_url=base_url,
            api_key=api_key,
            payload=build_repo_context_payload(
                instruction=args.instruction,
                pinned_paths=args.pinned_path,
                changed_paths=args.changed_path,
                max_files=args.max_context_files,
                max_scan_files=args.max_scan_files,
            ),
            timeout_seconds=args.timeout_seconds,
        )
        steps["context_plan"] = context_plan

        selected_context_paths = [
            str(path) for path in require_list(context_plan.get("selected_paths"))
        ]
        summary: dict[str, Any] = {
            "ok": True,
            "selected_context_paths": selected_context_paths,
            "steps": steps,
        }

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
            edit_plan = plan_workspace_edit(
                base_url=base_url,
                api_key=api_key,
                payload=edit_payload,
                timeout_seconds=args.timeout_seconds,
            )
            steps["edit_plan"] = edit_plan
            summary["edit_plan_hash"] = edit_plan.get("plan_hash")
            if edit_plan.get("ok") is not True:
                summary["ok"] = False
            elif args.apply_edits:
                plan_hash = str(edit_plan.get("plan_hash") or "")
                if len(plan_hash) != 64:
                    raise BiberAgentClientError(
                        "mvp-loop edit plan returned an invalid plan_hash."
                    )
                edit_apply = apply_workspace_edit_plan(
                    base_url=base_url,
                    api_key=api_key,
                    payload=build_workspace_edit_payload(
                        edits=edits,
                        max_files=args.max_edit_files,
                        plan_hash=plan_hash,
                    ),
                    timeout_seconds=args.timeout_seconds,
                )
                steps["edit_apply"] = edit_apply
                if edit_apply.get("ok") is not True:
                    summary["ok"] = False
        elif args.apply_edits:
            raise BiberAgentClientError("--apply-edits requires --edit-json or --edits-file.")

        if args.test_id:
            test_run = run_allowlisted_test(
                base_url=base_url,
                api_key=api_key,
                payload=build_test_run_payload(
                    test_id=args.test_id,
                    dry_run=args.test_dry_run,
                ),
                timeout_seconds=args.timeout_seconds,
            )
            steps["test_run"] = test_run
            summary["test_ok"] = test_run.get("ok")
            if test_run.get("executed") is True and test_run.get("ok") is False:
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
            github_save = save_to_github(
                base_url=base_url,
                api_key=api_key,
                payload=build_github_save_payload(
                    path=args.save_github_path,
                    content=content,
                    owner=args.github_owner,
                    repo=args.github_repo,
                    branch=args.github_branch,
                    base_branch=args.github_base_branch,
                    create_branch_if_missing=args.create_branch_if_missing,
                    commit_message=args.commit_message,
                ),
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
            pull_request = create_github_pull_request(
                base_url=base_url,
                api_key=api_key,
                payload=build_github_pull_request_payload(
                    head=pr_head,
                    base=args.pr_base,
                    title=args.pr_title,
                    body=pr_body,
                    owner=args.github_owner,
                    repo=args.github_repo,
                    draft=not args.pr_ready,
                ),
                timeout_seconds=args.timeout_seconds,
            )
            steps["github_pull_request"] = pull_request
            summary["pull_request_url"] = pull_request.get("url")
            summary["pull_request_number"] = pull_request.get("number")
        elif args.pr_head or args.pr_title or args.pr_body or args.pr_body_file:
            raise BiberAgentClientError("PR arguments require --create-pr.")

        if args.output:
            summary["artifact_path"] = str(Path(args.output))
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
