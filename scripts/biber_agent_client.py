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


def compact_text(value: object, *, max_chars: int = 2000) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


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


def is_failed_mvp_loop_artifact(payload: Mapping[str, Any]) -> bool:
    return payload.get("ok") is not True or payload.get("test_ok") is False


def build_mvp_loop_failure_record(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    steps = require_mapping(payload.get("steps"))
    test_run = require_mapping(steps.get("test_run"))
    diagnosis = require_mapping(steps.get("test_diagnosis"))
    relevant_output = (
        diagnosis.get("relevant_output")
        or test_run.get("stdout")
        or test_run.get("stderr")
        or ""
    )
    return {
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
        "next_review_action": "review_failure_before_eval_or_training",
    }


def build_repair_prompt(
    *,
    instruction: str,
    original_instruction: object,
    selected_context_paths: list[str],
    failure: Mapping[str, Any],
    suggested_next_actions: list[str],
) -> str:
    context_lines = "\n".join(f"- {path}" for path in selected_context_paths) or "- none"
    action_lines = "\n".join(f"- {action}" for action in suggested_next_actions) or "- none"
    command = " ".join(str(part) for part in require_list(failure.get("command"))) or "-"
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
            "- Preserve the existing project style and use existing APIs/helpers.",
            "- Return a patch-style or old_text/new_text edit proposal before explaining.",
            "",
            f"Original MVP instruction: {original_instruction or '-'}",
            "",
            "Selected repository context paths:",
            context_lines,
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
    all_context_paths = [
        str(item) for item in require_list(payload.get("selected_context_paths"))
    ]
    selected_context_paths = (
        all_context_paths[:max_context_paths]
        if max_context_paths is not None
        else all_context_paths
    )
    relevant_output = (
        diagnosis.get("relevant_output")
        or test_run.get("stdout")
        or test_run.get("stderr")
        or ""
    )
    suggested_next_actions = [
        str(item) for item in require_list(diagnosis.get("suggested_next_actions"))
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
    repair_prompt = build_repair_prompt(
        instruction=repair_instruction,
        original_instruction=payload.get("instruction"),
        selected_context_paths=selected_context_paths,
        failure=failure,
        suggested_next_actions=suggested_next_actions,
    )
    return {
        "source": "biber_mvp_loop_repair_request",
        "repair_loop_version": "mvp-v1",
        "repair_status": "ready_for_local_model",
        "training_allowed": False,
        "source_artifact": str(path),
        "ok": False,
        "instruction": repair_instruction,
        "repair_prompt": repair_prompt,
        "selected_context_paths": selected_context_paths,
        "selected_context_paths_truncated": len(selected_context_paths)
        < len(all_context_paths),
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
    return payload


def build_repair_attempt_result(
    *,
    repair_request: Mapping[str, Any],
    chat_payload: Mapping[str, Any],
    model_response: Mapping[str, Any],
) -> dict[str, Any]:
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
        "repair_content": str(model_response.get("content") or ""),
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
    candidate_index = 0
    for value in json_values:
        for candidate in extract_edit_objects_from_value(value):
            candidate_index += 1
            edit, rejection = validate_repair_edit_candidate(
                candidate,
                index=candidate_index,
            )
            if edit is not None:
                accepted.append(edit)
            elif rejection is not None:
                rejected.append(rejection)
            if len(accepted) >= max_edits:
                break
        if len(accepted) >= max_edits:
            break

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
        "json_values_found": len(json_values),
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


def build_plan_repair_edits_result(
    *,
    extraction_path: Path,
    extraction: Mapping[str, Any],
    plan_payload: Mapping[str, Any],
    edit_plan: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "source": "biber_mvp_loop_repair_edit_plan",
        "repair_loop_version": "mvp-v1",
        "source_artifact": str(extraction_path),
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
) -> dict[str, Any]:
    ok = edit_apply.get("ok") is True
    return {
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
    return "\n".join(
        [
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
    )


def format_mvp_loop_repair_attempt_summary(payload: Mapping[str, Any]) -> str:
    repair_request = require_mapping(payload.get("repair_request"))
    model_response = require_mapping(payload.get("model_response"))
    return "\n".join(
        [
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
    )


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
        f"edits_output: {payload.get('edits_output', '-')}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(f"- {edit.get('path', '-')}" for edit in edits[:8])
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
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"planned: {len(planned)}",
        f"rejected: {len(rejected)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(f"- {item.get('path', '-')}" for item in planned[:8])
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
        f"plan_hash: {payload.get('plan_hash', '-')}",
        f"applied: {len(applied)}",
        f"artifact_path: {payload.get('artifact_path', '-')}",
    ]
    lines.extend(
        f"- {item.get('path', '-')} changed={item.get('changed', False)}"
        for item in applied[:8]
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
    list_mvp_loops.add_argument(
        "--failed-only",
        action="store_true",
        help="Only list saved loop artifacts where ok is false or the test failed.",
    )

    export_mvp_failures = subparsers.add_parser(
        "export-mvp-failures",
        help="Export failed mvp-loop artifacts to a JSONL review queue.",
    )
    export_mvp_failures.add_argument("directory")
    export_mvp_failures.add_argument("--output", required=True)
    export_mvp_failures.add_argument("--pattern", default="*mvp-loop*.json")
    export_mvp_failures.add_argument("--limit", type=int, default=100)

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
            "Send a failed mvp-loop repair request to the local BIBER model and "
            "save an inspectable proposal without applying edits."
        ),
    )
    attempt_repair.add_argument("artifact")
    attempt_repair.add_argument("--instruction")
    attempt_repair.add_argument("--max-relevant-output-chars", type=int, default=4000)
    attempt_repair.add_argument("--max-context-paths", type=int)
    attempt_repair.add_argument("--model")
    attempt_repair.add_argument("--max-tokens", type=int, default=700)
    attempt_repair.add_argument("--temperature", type=float, default=0.2)
    attempt_repair.add_argument(
        "--use-mentor",
        action="store_true",
        help="Allow the OpenAI mentor path if server-side mentor config is enabled.",
    )
    attempt_repair.add_argument("--output")

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
    apply_repair_edits_parser.add_argument("--output")

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

    if args.command == "apply-repair-edits" and not args.approve:
        raise BiberAgentClientError(
            "apply-repair-edits requires --approve before any files can be changed."
        )

    api_key = resolve_api_key(args.api_key)
    base_url = args.base_url.rstrip("/")
    if args.command == "attempt-repair":
        artifact_path = Path(args.artifact)
        artifact = load_json_artifact(str(artifact_path), label="mvp-loop artifact")
        normalized = normalize_mvp_loop_artifact(artifact)
        if normalized is None:
            raise BiberAgentClientError(
                "attempt-repair artifact must contain a saved MVP loop JSON object."
            )
        repair_request = build_mvp_loop_repair_request(
            path=artifact_path,
            payload=normalized,
            instruction=args.instruction,
            max_relevant_output_chars=args.max_relevant_output_chars,
            max_context_paths=args.max_context_paths,
        )
        chat_payload = build_repair_chat_payload(
            repair_request=repair_request,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            use_mentor=args.use_mentor,
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
        plan_payload = build_plan_repair_edits_payload(
            extraction,
            max_files=args.max_files,
        )
        edit_plan = plan_workspace_edit(
            base_url=base_url,
            api_key=api_key,
            payload=plan_payload,
            timeout_seconds=args.timeout_seconds,
        )
        result = build_plan_repair_edits_result(
            extraction_path=artifact_path,
            extraction=extraction,
            plan_payload=plan_payload,
            edit_plan=edit_plan,
        )
        if args.output:
            result["artifact_path"] = str(Path(args.output))
            write_json_artifact(result, args.output)
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_plan_summary(result)
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
        )
        if args.output:
            result["artifact_path"] = str(Path(args.output))
            write_json_artifact(result, args.output)
        return (
            json.dumps(result, indent=2, sort_keys=True)
            if args.print_json
            else format_repair_edit_apply_summary(result)
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
            "instruction": args.instruction,
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
