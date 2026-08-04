#!/usr/bin/env python3
"""Ask a live/swappable provider for a real-repo repair plan without applying it.

This is the first non-disposable BIBER planning gate. It points the local
MVP-loop at a real repo, captures bounded source snippets, asks the selected
provider for JSON edits, reviews the resulting hash-guarded plan, and then
stops before apply/save. In mock mode it is CPU-only and does not require a
GPU, API key, OpenAI mentor, or training.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import biber_agent_client as client
import biber_live_provider_readiness as live_readiness


DEFAULT_BASE_URL = "http://127.0.0.1:8001/v1"
DEFAULT_MODEL = "biber-dev-core"
DEFAULT_TIMEOUT_SECONDS = 180.0
DEFAULT_MAX_CONTEXT_FILES = 4
DEFAULT_CHANGED_PATH = "docs/BIBER_ONLY_WORKSPACE.md"
DEFAULT_TEST_ID = "python-compileall-api"
DEFAULT_OLD_TEXT = (
    "Use this document when continuing BIBER MVP from the dedicated BIBER-only sparse checkout at:\n"
)
DEFAULT_NEW_TEXT = (
    "Use this document when continuing BIBER MVP from the dedicated BIBER MVP-only sparse checkout at:\n"
)
DEFAULT_CONTEXT_INSTRUCTION = (
    "Select the narrow BIBER repo context needed for a safe plan-only "
    "local-provider edit review. Prioritize the required changed path."
)
CODE_PLAN_CONTEXT_INSTRUCTION = (
    "Select the narrow BIBER Python source context needed for a safe "
    "plan-only local-provider code edit review. Prioritize the required "
    "changed path and exact old_text."
)
SMOKE_PROFILES: dict[str, dict[str, str]] = {
    "docs-line": {
        "required_path": DEFAULT_CHANGED_PATH,
        "required_old_text": DEFAULT_OLD_TEXT,
        "required_new_text": DEFAULT_NEW_TEXT,
        "context_instruction": DEFAULT_CONTEXT_INSTRUCTION,
        "max_context_files": str(DEFAULT_MAX_CONTEXT_FILES),
    },
    "code-unused-timeout": {
        "required_path": "app/model_registry.py",
        "required_old_text": (
            '    timeout_seconds = getattr(settings, "local_model_timeout_seconds", 180)\n'
        ),
        "required_new_text": "",
        "context_instruction": CODE_PLAN_CONTEXT_INSTRUCTION,
        "max_context_files": "1",
    },
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def default_output_root() -> Path:
    env_root = os.getenv("BIBER_REAL_REPO_PLAN_SMOKE_OUTPUT_ROOT")
    if env_root:
        return Path(env_root)
    workspace_outputs = Path("/workspace/outputs")
    if workspace_outputs.is_dir():
        return workspace_outputs
    return Path(tempfile.gettempdir())


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def resolve_required_text(
    *,
    value: str | None,
    file_value: str | None,
    default: str,
    label: str,
) -> str:
    if value is not None and file_value is not None:
        raise RuntimeError(f"Use either --{label} or --{label}-file, not both.")
    if file_value is not None:
        return Path(file_value).read_text(encoding="utf-8")
    if value is not None:
        return value
    return default


def build_plan_instruction(
    *,
    required_path: str,
    required_old_text: str,
    required_new_text: str,
) -> str:
    required_edit_json = json.dumps(
        {
            "edits": [
                {
                    "path": required_path,
                    "old_text": required_old_text,
                    "new_text": required_new_text,
                    "expected_replacements": 1,
                }
            ]
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return (
        "Plan only, do not apply. This is a smoke test of the real-repo planning "
        f"bridge. If the exact old_text below appears in `{required_path}`, "
        "return exactly the preferred JSON edit object below. Do not rewrite, "
        "summarize, reformat the string values, or change the path. Return "
        "{\"edits\":[]} only if the exact old_text is absent from the supplied "
        "source snippets.\n\n"
        f"Required path: {required_path}\n"
        f"Required old_text:\n{required_old_text}\n"
        f"Required new_text:\n{required_new_text}\n"
        f"Preferred JSON edit:\n{required_edit_json}"
    )


def run_client(
    repo_root: Path,
    artifact_dir: Path,
    *args: str,
    env_updates: dict[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(artifact_dir / "pycache")
    if env_updates:
        env.update(env_updates)
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "biber_agent_client.py"),
        "--json",
        *args,
    ]
    completed = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"biber_agent_client.py failed with exit code {completed.returncode}: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError("biber_agent_client.py did not return a JSON object")
    return parsed


def git_status_short(target_root: Path) -> dict[str, Any]:
    try:
        safe_directory = str(target_root).replace("\\", "/")
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={safe_directory}",
                "-C",
                str(target_root),
                "status",
                "--short",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {
            "available": False,
            "reason": "git_status_failed",
            "target_root": str(target_root),
            "error": str(exc),
            "status_short": [],
        }
    return {
        "available": completed.returncode == 0,
        "returncode": completed.returncode,
        "target_root": str(target_root),
        "status_short": completed.stdout.splitlines(),
        "stderr": completed.stderr,
    }


def default_model_command(repo_root: Path) -> str:
    return json.dumps(
        [
            sys.executable,
            str(repo_root / "scripts" / "biber_local_openai_provider.py"),
        ]
    )


def create_mock_provider(
    *,
    path: Path,
    required_path: str,
    required_old_text: str,
    required_new_text: str,
    safe_noop: bool = False,
) -> None:
    edit_payload = (
        {"edits": []}
        if safe_noop
        else {
            "edits": [
                {
                    "path": required_path,
                    "old_text": required_old_text,
                    "new_text": required_new_text,
                    "expected_replacements": 1,
                }
            ]
        }
    )
    path.write_text(
        "import json\n"
        "import sys\n"
        "\n"
        "request = json.load(sys.stdin)\n"
        "repair = request.get('repair_request') or {}\n"
        "prompt = repair.get('repair_prompt') or ''\n"
        "normalized_prompt = prompt.replace('\\r\\n', '\\n')\n"
        "old_text = " + repr(required_old_text) + "\n"
        "normalized_old_text = old_text.replace('\\r\\n', '\\n')\n"
        "if request.get('source') != 'biber_local_model_command_request':\n"
        "    raise SystemExit('unexpected request source')\n"
        "if 'BIBER_FILE_CONTENT_START' not in prompt or normalized_old_text not in normalized_prompt:\n"
        "    raise SystemExit('real repo source context missing from prompt')\n"
        "content = " + repr(json.dumps(edit_payload, sort_keys=True)) + "\n"
        "print(json.dumps({'content': content, 'model': request.get('model')}))\n",
        encoding="utf-8",
    )


def build_plan_only_repair_request(
    *,
    target_root: Path,
    mvp_result: dict[str, Any],
    mvp_artifact: Path,
    instruction: str,
    test_id: str,
) -> dict[str, Any]:
    selected_context_paths = [
        str(path) for path in client.require_list(mvp_result.get("selected_context_paths"))
    ]
    source_context_snippets = client.build_repair_source_context_snippets(
        target_root=target_root,
        selected_context_paths=selected_context_paths,
    )
    context_plan = client.require_mapping(
        client.require_mapping(mvp_result.get("steps")).get("context_plan")
    )
    detected_stack = (
        client.require_list(context_plan.get("detected_project_types"))[0]
        if client.require_list(context_plan.get("detected_project_types"))
        else None
    )
    agent_report = client.require_mapping(mvp_result.get("agent_report"))
    if not agent_report:
        agent_report = client.build_mvp_loop_agent_report(mvp_result)
    repair_hint = {
        "source": "biber_real_repo_plan_only_repair_hint_v1",
        "status": "ready_for_plan_only_local_model",
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "test_id": test_id,
        "command": ["plan-only", "no-test-failure"],
        "exit_code": None,
        "timed_out": False,
        "diagnosis_summary": (
            "No failed test is being repaired. This is a real-repo plan-only "
            "safety gate that must stop before apply/save."
        ),
        "primary_category": "plan_only_no_failure",
        "detected_stack": detected_stack,
        "relevant_output": (
            "Plan-only request: propose an edit only when exact old_text is "
            "available in the source snippets; otherwise return {\"edits\":[]}."
        ),
        "suggested_next_actions": [
            "Generate a bounded edit proposal from exact source snippets.",
            "Review the hash-guarded plan.",
            "Stop before apply or GitHub save.",
        ],
        "next_workflow": [
            "local-repair-chain",
            "review-local-repair-chain",
            "stop_before_apply",
        ],
    }
    agent_report = dict(agent_report)
    agent_report["repair_hint"] = repair_hint
    failure = {
        "diagnosis_summary": repair_hint["diagnosis_summary"],
        "primary_category": repair_hint["primary_category"],
        "detected_stack": detected_stack,
        "test_id": test_id,
        "command": repair_hint["command"],
        "exit_code": None,
        "timed_out": False,
        "relevant_output": repair_hint["relevant_output"],
    }
    suggested_next_actions = [
        str(item) for item in client.require_list(repair_hint.get("suggested_next_actions"))
    ]
    output_contract = client.build_repair_output_contract()
    repair_prompt = client.build_repair_prompt(
        instruction=instruction,
        original_instruction=mvp_result.get("instruction"),
        selected_context_paths=selected_context_paths,
        source_context_snippets=source_context_snippets,
        failure=failure,
        suggested_next_actions=suggested_next_actions,
        agent_report=agent_report,
        output_contract=output_contract,
    )
    return {
        "source": "biber_mvp_loop_repair_request",
        "request_kind": "real_repo_plan_only",
        "repair_loop_version": "mvp-v1",
        "repair_status": "ready_for_local_model",
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "apply_allowed": False,
        "source_artifact": str(mvp_artifact),
        "ok": False,
        "target_root": str(target_root),
        "target_root_source": "cli_target_root",
        "instruction": instruction,
        "repair_prompt": repair_prompt,
        "repair_output_contract": output_contract,
        "selected_context_paths": selected_context_paths,
        "selected_context_paths_truncated": False,
        "source_context_snippets": source_context_snippets,
        "source_context_snippets_available": bool(source_context_snippets),
        "agent_report": agent_report,
        "repair_hint": repair_hint,
        "failure": failure,
        "suggested_next_actions": suggested_next_actions,
        "next_test_id": test_id,
        "next_workflow": [
            "send_repair_prompt_to_local_biber_model",
            "convert_response_to_bounded_plan_edit_payload",
            "review_local_repair_chain",
            "stop_before_apply",
        ],
    }


def plan_counts(chain: dict[str, Any]) -> tuple[int, int]:
    plan = chain.get("repair_edit_plan")
    if not isinstance(plan, dict):
        return 0, 0
    edit_plan = plan.get("edit_plan")
    if not isinstance(edit_plan, dict):
        return 0, 0
    planned = [item for item in client.require_list(edit_plan.get("planned")) if isinstance(item, dict)]
    rejected = [item for item in client.require_list(edit_plan.get("rejected")) if isinstance(item, dict)]
    return len(planned), len(rejected)


def compact_preview(value: object, *, max_chars: int = 600) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def repair_chain_diagnostics(chain: dict[str, Any]) -> dict[str, Any]:
    extraction = chain.get("repair_edit_extraction")
    if not isinstance(extraction, dict):
        extraction = {}
    attempt = chain.get("repair_attempt")
    if not isinstance(attempt, dict):
        attempt = {}
    model_response = attempt.get("model_response")
    if not isinstance(model_response, dict):
        model_response = {}
    plan = chain.get("repair_edit_plan")
    if not isinstance(plan, dict):
        plan = {}
    edit_plan = plan.get("edit_plan")
    if not isinstance(edit_plan, dict):
        edit_plan = {}
    content = str(model_response.get("content") or "")
    rejected = [
        item for item in client.require_list(extraction.get("rejected")) if isinstance(item, dict)
    ]
    edits = [
        item for item in client.require_list(extraction.get("edits")) if isinstance(item, dict)
    ]
    plan_rejected = [
        item for item in client.require_list(edit_plan.get("rejected")) if isinstance(item, dict)
    ]
    plan_planned = [
        item for item in client.require_list(edit_plan.get("planned")) if isinstance(item, dict)
    ]
    if plan_planned:
        outcome = "planned_for_review"
    elif plan_rejected:
        outcome = "blocked_plan_rejected"
    elif edits:
        outcome = "blocked_extracted_but_not_planned"
    elif rejected:
        outcome = "blocked_unusable_edits"
    elif int(extraction.get("json_values_found") or 0) > 0:
        outcome = "safe_noop_or_empty_edits"
    elif content.strip():
        outcome = "blocked_unparseable_model_response"
    else:
        outcome = "blocked_empty_model_response"
    return {
        "plan_outcome": outcome,
        "extraction_status": extraction.get("extraction_status"),
        "extracted_edits": len(edits),
        "extraction_rejected": len(rejected),
        "extraction_rejection_reasons": sorted(
            {
                str(item.get("reason"))
                for item in rejected
                if item.get("reason")
            }
        ),
        "plan_rejected": len(plan_rejected),
        "plan_rejection_reasons": sorted(
            {
                str(
                    item.get("reason")
                    or item.get("error")
                    or item.get("message")
                    or item.get("status")
                )
                for item in plan_rejected
                if (
                    item.get("reason")
                    or item.get("error")
                    or item.get("message")
                    or item.get("status")
                )
            }
        ),
        "json_values_found": extraction.get("json_values_found"),
        "unified_diff_candidates_found": extraction.get(
            "unified_diff_candidates_found"
        ),
        "model_response_content_chars": len(content),
        "model_response_content_preview": compact_preview(content),
    }


def required_old_text_probe(
    *,
    target_root: Path,
    required_path: str,
    required_old_text: str,
) -> dict[str, Any]:
    target_path = (target_root / required_path).resolve()
    try:
        relative = target_path.relative_to(target_root.resolve())
    except ValueError:
        return {
            "ok": False,
            "reason": "required_path_outside_target_root",
            "path": required_path,
        }
    if not target_path.is_file():
        return {
            "ok": False,
            "reason": "required_path_not_file",
            "path": str(relative),
        }
    try:
        text = target_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {
            "ok": False,
            "reason": "required_path_not_utf8",
            "path": str(relative),
        }
    exact_replacements = text.count(required_old_text)
    normalized_replacements = text.replace("\r\n", "\n").count(
        required_old_text.replace("\r\n", "\n")
    )
    return {
        "ok": exact_replacements == 1,
        "reason": "exactly_one_required_old_text"
        if exact_replacements == 1
        else "required_old_text_replacement_count_not_one",
        "path": str(relative).replace("\\", "/"),
        "exact_replacements": exact_replacements,
        "normalized_replacements": normalized_replacements,
    }


def required_edit_response_text(
    *,
    required_path: str,
    required_old_text: str,
    required_new_text: str,
) -> str:
    return json.dumps(
        {
            "edits": [
                {
                    "path": required_path,
                    "old_text": required_old_text,
                    "new_text": required_new_text,
                    "expected_replacements": 1,
                }
            ]
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def build_summary(
    *,
    args: argparse.Namespace,
    base_url: str,
    model: str,
    required_path: str,
    required_old_text: str,
    required_new_text: str,
    work_root: Path,
    artifact_dir: Path,
    target_root: Path,
    readiness: dict[str, Any] | None,
    git_before: dict[str, Any],
    git_after: dict[str, Any],
    mvp_result: dict[str, Any],
    repair_request: dict[str, Any],
    chain: dict[str, Any],
    review: dict[str, Any],
) -> dict[str, Any]:
    planned, rejected = plan_counts(chain)
    plan = chain.get("repair_edit_plan") if isinstance(chain.get("repair_edit_plan"), dict) else {}
    diagnostics = repair_chain_diagnostics(chain)
    readiness_ok = True if readiness is None else readiness.get("ok") is True
    repo_status_unchanged = git_before.get("status_short") == git_after.get("status_short")
    review_ready = (
        review.get("review_status") == "ready_for_explicit_apply_approval"
        and review.get("apply_recommendation") == "ready_for_explicit_apply_approval"
        and review.get("blockers") == []
    )
    ok = (
        readiness_ok
        and mvp_result.get("ok") is True
        and repair_request.get("request_kind") == "real_repo_plan_only"
        and repair_request.get("source_context_snippets_available") is True
        and chain.get("chain_status") == "planned"
        and review_ready
        and planned > 0
        and rejected == 0
        and plan.get("apply_allowed") is False
        and repo_status_unchanged
    )
    next_action = (
        "review_plan_artifacts_only_no_apply"
        if ok
        else "inspect_model_response_and_prompt_or_retry_with_stricter_instruction"
        if diagnostics["plan_outcome"]
        in {
            "safe_noop_or_empty_edits",
            "blocked_unparseable_model_response",
            "blocked_empty_model_response",
        }
        else "inspect_plan_rejections_or_retry_with_simpler_exact_old_text"
        if diagnostics["plan_outcome"] == "blocked_plan_rejected"
        else "inspect_rejected_edits_before_retry"
    )
    summary = {
        "source": "biber_live_provider_real_repo_plan_smoke",
        "ok": ok,
        "mode": args.mode,
        "base_url": base_url,
        "model": model,
        "external_network_required": args.mode == "live",
        "gpu_required": args.mode == "live",
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "live_provider_required": args.mode == "live",
        "target_is_disposable": False,
        "mutation_performed": False,
        "auto_applied": False,
        "auto_saved": False,
        "github_request_sent": False,
        "apply_status": None,
        "verification_status": None,
        "smoke_profile": args.smoke_profile,
        "required_edit": {
            "path": required_path,
            "old_text_chars": len(required_old_text),
            "new_text_chars": len(required_new_text),
            "old_text_preview": compact_preview(required_old_text),
            "new_text_preview": compact_preview(required_new_text),
        },
        "max_context_files": args.max_context_files,
        "max_scan_files": args.max_scan_files,
        "work_root": str(work_root),
        "artifact_dir": str(artifact_dir),
        "target_root": str(target_root),
        "readiness_ok": readiness_ok,
        "mvp_ok": mvp_result.get("ok"),
        "request_kind": repair_request.get("request_kind"),
        "source_context_snippets_available": repair_request.get(
            "source_context_snippets_available"
        ),
        "selected_context_paths": repair_request.get("selected_context_paths"),
        "chain_status": chain.get("chain_status"),
        "review_status": review.get("review_status"),
        "apply_recommendation": review.get("apply_recommendation"),
        "blockers": review.get("blockers"),
        "planned": planned,
        "rejected": rejected,
        "plan_hash": review.get("plan_hash"),
        "apply_allowed": plan.get("apply_allowed"),
        "required_edit_fallback_enabled": args.required_edit_fallback,
        "required_edit_fallback": chain.get("required_edit_fallback")
        if isinstance(chain.get("required_edit_fallback"), dict)
        else None,
        **diagnostics,
        "next_action": next_action,
        "repo_status_unchanged": repo_status_unchanged,
        "git_before": git_before,
        "git_after": git_after,
        "artifacts": {
            "mvp_loop": str(artifact_dir / "real-repo-mvp-loop.json"),
            "prepared_repair": str(artifact_dir / "real-repo-plan-only-repair.json"),
            "local_repair_chain": str(artifact_dir / "real-repo-local-repair-chain.json"),
            "local_repair_chain_model_attempt": str(
                artifact_dir / "real-repo-local-repair-chain-model-attempt.json"
            ),
            "required_edit_fallback_response": str(
                artifact_dir / "real-repo-required-edit-fallback-response.json"
            ),
            "local_repair_chain_review": str(
                artifact_dir / "real-repo-local-repair-chain-review.json"
            ),
            "repair_edit_plan": str(artifact_dir / "real-repo-repair-edit-plan.json"),
        },
    }
    if review_ready and planned > 0 and rejected == 0:
        apply_output = artifact_dir / "real-repo-repair-edit-apply.json"
        verify_output = artifact_dir / "real-repo-local-verify-chain.json"
        summary["explicit_apply_approval"] = {
            "required": True,
            "approved": False,
            "status": "requires_separate_explicit_user_approval_before_apply",
            "plan_hash": review.get("plan_hash"),
            "apply_output": str(apply_output),
            "verify_output": str(verify_output),
            "apply_command": [
                sys.executable,
                "scripts/biber_agent_client.py",
                "--json",
                "apply-repair-edits",
                str(artifact_dir / "real-repo-repair-edit-plan.json"),
                "--review-artifact",
                str(artifact_dir / "real-repo-local-repair-chain-review.json"),
                "--target-root",
                str(target_root),
                "--approve",
                "--output",
                str(apply_output),
            ],
            "verify_command_after_apply": [
                sys.executable,
                "scripts/biber_agent_client.py",
                "--json",
                "local-verify-chain",
                str(apply_output),
                "--test-id",
                args.test_id,
                "--target-root",
                str(target_root),
                "--output",
                str(verify_output),
            ],
        }
    if readiness is not None:
        summary["readiness"] = readiness
    return summary


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    target_root = Path(args.target_root).resolve() if args.target_root else repo_root
    if not target_root.is_dir():
        raise RuntimeError(f"Target root is not a directory: {target_root}")
    base_url = args.base_url or os.getenv("BIBER_LOCAL_OPENAI_BASE_URL", DEFAULT_BASE_URL)
    model = (
        args.model
        or os.getenv("BIBER_LOCAL_OPENAI_MODEL")
        or os.getenv("BIBER_LOCAL_MODEL_NAME")
        or DEFAULT_MODEL
    )
    profile = SMOKE_PROFILES[args.smoke_profile]
    context_instruction = (
        args.context_instruction
        or profile.get("context_instruction")
        or DEFAULT_CONTEXT_INSTRUCTION
    )
    required_path = args.required_path or profile["required_path"]
    if args.max_context_files is None:
        args.max_context_files = int(
            profile.get("max_context_files", str(DEFAULT_MAX_CONTEXT_FILES))
        )
    required_old_text = resolve_required_text(
        value=args.required_old_text,
        file_value=args.required_old_text_file,
        default=profile["required_old_text"],
        label="required-old-text",
    )
    required_new_text = resolve_required_text(
        value=args.required_new_text,
        file_value=args.required_new_text_file,
        default=profile["required_new_text"],
        label="required-new-text",
    )
    plan_instruction = args.plan_instruction or build_plan_instruction(
        required_path=required_path,
        required_old_text=required_old_text,
        required_new_text=required_new_text,
    )
    output_root = Path(args.output_root) if args.output_root else default_output_root()
    work_root = output_root / f"biber-real-repo-plan-smoke-{timestamp()}"
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=False)

    readiness: dict[str, Any] | None = None
    model_command = args.model_command
    if args.mode == "mock":
        mock_provider = work_root / "mock-real-repo-plan-provider.py"
        create_mock_provider(
            path=mock_provider,
            required_path=required_path,
            required_old_text=required_old_text,
            required_new_text=required_new_text,
            safe_noop=args.mock_safe_noop,
        )
        model_command = json.dumps([sys.executable, str(mock_provider)])
    else:
        readiness = live_readiness.readiness_summary(
            base_url=base_url,
            model=model,
            api_key_env=args.api_key_env,
            timeout_seconds=args.readiness_timeout_seconds,
            require_model=True,
        )
        write_json(artifact_dir / "live-provider-readiness.json", readiness)
        if args.require_ready and readiness.get("ok") is not True:
            return {
                "source": "biber_live_provider_real_repo_plan_smoke",
                "ok": False,
                "mode": args.mode,
                "base_url": base_url,
                "model": model,
                "work_root": str(work_root),
                "artifact_dir": str(artifact_dir),
                "target_root": str(target_root),
                "readiness": readiness,
                "readiness_ok": False,
                "live_provider_required": True,
                "gpu_required": True,
                "api_required": False,
                "mentor_used": False,
                "training_allowed": False,
                "mutation_performed": False,
            }
    if not model_command:
        model_command = default_model_command(repo_root)

    env_updates = {
        "BIBER_LOCAL_OPENAI_BASE_URL": base_url,
        "BIBER_LOCAL_OPENAI_MODEL": model,
    }
    git_before = git_status_short(target_root)
    changed_paths = args.changed_path or [required_path]
    pinned_paths = args.pinned_path or []
    mvp_args = [
        "mvp-loop",
        "--instruction",
        context_instruction,
        "--local-target-root",
        str(target_root),
        "--include-git-state",
        "--test-id",
        args.test_id,
        "--test-dry-run",
        "--max-context-files",
        str(args.max_context_files),
        "--max-scan-files",
        str(args.max_scan_files),
        "--output",
        str(artifact_dir / "real-repo-mvp-loop.json"),
    ]
    for path in changed_paths:
        mvp_args.extend(["--changed-path", path])
    for path in pinned_paths:
        mvp_args.extend(["--pinned-path", path])
    mvp_result = run_client(
        repo_root,
        artifact_dir,
        *mvp_args,
        env_updates=env_updates,
        timeout_seconds=args.command_timeout_seconds,
    )
    repair_request = build_plan_only_repair_request(
        target_root=target_root,
        mvp_result=mvp_result,
        mvp_artifact=artifact_dir / "real-repo-mvp-loop.json",
        instruction=plan_instruction,
        test_id=args.test_id,
    )
    write_json(artifact_dir / "real-repo-plan-only-repair.json", repair_request)
    chain = run_client(
        repo_root,
        artifact_dir,
        "local-repair-chain",
        str(artifact_dir / "real-repo-plan-only-repair.json"),
        "--model-command",
        model_command,
        "--model-command-timeout-seconds",
        str(int(args.model_command_timeout_seconds)),
        "--target-root",
        str(target_root),
        "--output",
        str(artifact_dir / "real-repo-local-repair-chain.json"),
        env_updates=env_updates,
        timeout_seconds=args.command_timeout_seconds + args.model_command_timeout_seconds,
    )
    model_attempt_diagnostics = repair_chain_diagnostics(chain)
    if (
        args.required_edit_fallback
        and model_attempt_diagnostics["plan_outcome"] == "safe_noop_or_empty_edits"
    ):
        fallback_probe = required_old_text_probe(
            target_root=target_root,
            required_path=required_path,
            required_old_text=required_old_text,
        )
        if fallback_probe.get("ok") is True:
            model_attempt_artifact = (
                artifact_dir / "real-repo-local-repair-chain-model-attempt.json"
            )
            write_json(model_attempt_artifact, chain)
            fallback_response_artifact = (
                artifact_dir / "real-repo-required-edit-fallback-response.json"
            )
            fallback_response_artifact.write_text(
                required_edit_response_text(
                    required_path=required_path,
                    required_old_text=required_old_text,
                    required_new_text=required_new_text,
                )
                + "\n",
                encoding="utf-8",
            )
            chain = run_client(
                repo_root,
                artifact_dir,
                "local-repair-chain",
                str(artifact_dir / "real-repo-plan-only-repair.json"),
                "--model-response-file",
                str(fallback_response_artifact),
                "--target-root",
                str(target_root),
                "--output",
                str(artifact_dir / "real-repo-local-repair-chain.json"),
                env_updates=env_updates,
                timeout_seconds=args.command_timeout_seconds,
            )
            chain["required_edit_fallback"] = {
                "used": True,
                "reason": "live_model_returned_safe_noop_for_exact_required_edit",
                "model_attempt_artifact": str(model_attempt_artifact),
                "model_attempt_plan_outcome": model_attempt_diagnostics["plan_outcome"],
                "model_attempt_preview": model_attempt_diagnostics[
                    "model_response_content_preview"
                ],
                "fallback_response_artifact": str(fallback_response_artifact),
                "target_probe": fallback_probe,
            }
            model_response_source = chain.get("model_response_source")
            if isinstance(model_response_source, dict):
                model_response_source["required_edit_fallback_used"] = True
                model_response_source["required_edit_fallback_reason"] = (
                    "live_model_returned_safe_noop_for_exact_required_edit"
                )
            write_json(artifact_dir / "real-repo-local-repair-chain.json", chain)
        else:
            chain["required_edit_fallback"] = {
                "used": False,
                "reason": "target_probe_not_safe_for_required_edit_fallback",
                "model_attempt_plan_outcome": model_attempt_diagnostics["plan_outcome"],
                "model_attempt_preview": model_attempt_diagnostics[
                    "model_response_content_preview"
                ],
                "target_probe": fallback_probe,
            }
            write_json(artifact_dir / "real-repo-local-repair-chain.json", chain)
    review = run_client(
        repo_root,
        artifact_dir,
        "review-local-repair-chain",
        str(artifact_dir / "real-repo-local-repair-chain.json"),
        "--output",
        str(artifact_dir / "real-repo-local-repair-chain-review.json"),
        env_updates=env_updates,
        timeout_seconds=args.command_timeout_seconds,
    )
    plan = chain.get("repair_edit_plan")
    if isinstance(plan, dict):
        write_json(artifact_dir / "real-repo-repair-edit-plan.json", plan)
    git_after = git_status_short(target_root)

    summary = build_summary(
        args=args,
        base_url=base_url,
        model=model,
        required_path=required_path,
        required_old_text=required_old_text,
        required_new_text=required_new_text,
        work_root=work_root,
        artifact_dir=artifact_dir,
        target_root=target_root,
        readiness=readiness,
        git_before=git_before,
        git_after=git_after,
        mvp_result=mvp_result,
        repair_request=repair_request,
        chain=chain,
        review=review,
    )
    write_json(artifact_dir / "real-repo-plan-smoke-summary.json", summary)
    if args.cleanup and summary.get("ok") is True:
        if isinstance(summary.get("explicit_apply_approval"), dict):
            summary["explicit_apply_approval"] = {
                "required": True,
                "approved": False,
                "status": "not_available_after_cleanup",
                "reason": "artifact_work_directory_removed",
            }
        shutil.rmtree(work_root, ignore_errors=True)
        summary["cleaned_up"] = True
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a real-repo BIBER provider planning smoke that stops before apply."
        )
    )
    parser.add_argument("--mode", choices=["live", "mock"], default="live")
    parser.add_argument(
        "--mock-safe-noop",
        action="store_true",
        help="In mock mode, return {\"edits\":[]} to exercise required-edit fallback.",
    )
    parser.add_argument(
        "--smoke-profile",
        choices=sorted(SMOKE_PROFILES),
        default="docs-line",
        help=(
            "Built-in exact-edit profile. Use code-unused-timeout for the first "
            "small real Python source planning proof."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIBER_LOCAL_OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument("--model")
    parser.add_argument(
        "--api-key-env",
        default="BIBER_LOCAL_OPENAI_API_KEY",
        help="Environment variable containing an optional provider bearer token.",
    )
    parser.add_argument("--target-root")
    parser.add_argument("--output-root")
    parser.add_argument("--changed-path", action="append", default=None)
    parser.add_argument("--pinned-path", action="append", default=None)
    parser.add_argument("--test-id", default=DEFAULT_TEST_ID)
    parser.add_argument("--context-instruction")
    parser.add_argument(
        "--plan-instruction",
        help=(
            "Optional full local-model instruction. Defaults to a guarded "
            "plan-only instruction built from --required-* values."
        ),
    )
    parser.add_argument(
        "--required-path",
        help=(
            "Workspace-relative path the provider should edit when exact old_text "
            "is present. Defaults to the selected --smoke-profile."
        ),
    )
    parser.add_argument(
        "--required-old-text",
        help="Exact old_text for the guarded edit. Use the file variant for multiline text.",
    )
    parser.add_argument(
        "--required-old-text-file",
        help="UTF-8 file containing exact old_text for the guarded edit.",
    )
    parser.add_argument(
        "--required-new-text",
        help="Exact new_text for the guarded edit. Use the file variant for multiline text.",
    )
    parser.add_argument(
        "--required-new-text-file",
        help="UTF-8 file containing exact new_text for the guarded edit.",
    )
    parser.add_argument(
        "--max-context-files",
        type=int,
        default=None,
        help=(
            "Maximum context files selected for the planning prompt. Defaults "
            "to the selected --smoke-profile."
        ),
    )
    parser.add_argument("--max-scan-files", type=int, default=2000)
    parser.add_argument(
        "--model-command",
        help=(
            "Optional JSON array command for local-repair-chain. Defaults to "
            "scripts/biber_local_openai_provider.py in live mode."
        ),
    )
    parser.add_argument("--model-command-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--command-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--readiness-timeout-seconds", type=float, default=10.0)
    parser.add_argument(
        "--required-edit-fallback",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "When the live provider returns a safe no-op for an exact required edit, "
            "build a review-only plan from the guarded required edit if the target "
            "file contains old_text exactly once. This never applies the edit."
        ),
    )
    parser.add_argument(
        "--require-ready",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="In live mode, stop when GET /v1/models readiness is not ok.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the artifact work directory after a successful run.",
    )
    parser.add_argument("--output", help="Optional path for a copy of the summary JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run_smoke(args)
    except Exception as exc:
        print(f"biber_live_provider_real_repo_plan_smoke: {exc}", file=sys.stderr)
        return 1
    if args.output:
        write_json(Path(args.output), summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
