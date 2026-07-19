#!/usr/bin/env python3
"""Run BIBER's no-GPU local confidence smokes as one pre-live-provider check."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_smoke_script(
    *,
    repo_root: Path,
    script_name: str,
    pycache_root: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(pycache_root / Path(script_name).stem)
    completed = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / script_name)],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{script_name} failed with exit code {completed.returncode}: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"{script_name} did not print a JSON object: {completed.stdout!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{script_name} did not print a JSON object.")
    return payload


def compact_check(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "source": payload.get("source"),
        "ok": payload.get("ok") is True,
        "api_required": payload.get("api_required") is True,
        "gpu_required": payload.get("gpu_required") is True,
        "mentor_used": payload.get("mentor_used") is True,
        "training_allowed": payload.get("training_allowed") is True,
    }


def run_confidence_smoke(timeout_seconds: float) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="biber-local-confidence-pycache-") as tmp:
        pycache_root = Path(tmp)
        provider = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_openai_provider_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        readiness = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_live_provider_readiness_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        mvp_loop = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_mvp_loop_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        mvp_loop_failure = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_mvp_loop_failure_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        mvp_loop_repo_probe = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_mvp_loop_repo_probe_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        mvp_loop_full_repair = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_mvp_loop_full_repair_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        verified_repair_github_dry_run = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_verified_repair_github_dry_run_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        github_dry_run_artifacts = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_github_dry_run_artifacts_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )
        repair_loop = run_smoke_script(
            repo_root=repo_root,
            script_name="biber_local_repair_loop_smoke.py",
            pycache_root=pycache_root,
            timeout_seconds=timeout_seconds,
        )

    checks = [
        compact_check("local_openai_provider_http", provider),
        compact_check("live_provider_readiness_mock", readiness),
        compact_check("local_mvp_loop", mvp_loop),
        compact_check("local_mvp_loop_failure", mvp_loop_failure),
        compact_check("local_mvp_loop_repo_probe", mvp_loop_repo_probe),
        compact_check("local_mvp_loop_full_repair", mvp_loop_full_repair),
        compact_check(
            "local_verified_repair_github_dry_run",
            verified_repair_github_dry_run,
        ),
        compact_check("local_github_dry_run_artifacts", github_dry_run_artifacts),
        compact_check("local_repair_loop", repair_loop),
    ]
    summary = {
        "source": "biber_local_confidence_smoke",
        "ok": all(check["ok"] for check in checks),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "checks": checks,
        "provider": {
            "request_path": provider.get("request_path"),
            "request_model": provider.get("request_model"),
            "response_model": provider.get("response_model"),
            "content_edit_paths": provider.get("content_edit_paths"),
        },
        "readiness": {
            "request_path": readiness.get("request_path"),
            "requested_model": readiness.get("requested_model"),
            "model_available": readiness.get("model_available"),
            "available_model_count": readiness.get("available_model_count"),
        },
        "mvp_loop": {
            "agent_report_status": mvp_loop.get("agent_report_status"),
            "edit_review_status": mvp_loop.get("edit_review_status"),
            "edit_ready_for_apply": mvp_loop.get("edit_ready_for_apply"),
            "edit_planned_count": mvp_loop.get("edit_planned_count"),
            "edit_applied_count": mvp_loop.get("edit_applied_count"),
            "test_ok": mvp_loop.get("test_ok"),
        },
        "mvp_loop_failure": {
            "agent_report_status": mvp_loop_failure.get("agent_report_status"),
            "repair_hint_status": mvp_loop_failure.get("repair_hint_status"),
            "primary_category": mvp_loop_failure.get("primary_category"),
            "detected_stack": mvp_loop_failure.get("detected_stack"),
            "test_ok": mvp_loop_failure.get("test_ok"),
            "repair_status": mvp_loop_failure.get("repair_status"),
            "repair_prompt_has_hint": mvp_loop_failure.get("repair_prompt_has_hint"),
            "list_failed_artifacts": mvp_loop_failure.get("list_failed_artifacts"),
            "list_repair_hint_status": mvp_loop_failure.get(
                "list_repair_hint_status"
            ),
            "list_repair_next_step": mvp_loop_failure.get("list_repair_next_step"),
            "show_list_artifact_ok": mvp_loop_failure.get("show_list_artifact_ok"),
        },
        "mvp_loop_repo_probe": {
            "agent_report_status": mvp_loop_repo_probe.get("agent_report_status"),
            "git_branch": mvp_loop_repo_probe.get("git_branch"),
            "git_dirty": mvp_loop_repo_probe.get("git_dirty"),
            "path_list_files_used": mvp_loop_repo_probe.get("path_list_files_used"),
            "path_file_selected_paths": mvp_loop_repo_probe.get(
                "path_file_selected_paths"
            ),
            "selected_context_paths": mvp_loop_repo_probe.get("selected_context_paths"),
            "detected_project_types": mvp_loop_repo_probe.get("detected_project_types"),
            "test_id": mvp_loop_repo_probe.get("test_id"),
            "test_executed": mvp_loop_repo_probe.get("test_executed"),
            "repo_status_unchanged": mvp_loop_repo_probe.get("repo_status_unchanged"),
        },
        "mvp_loop_full_repair": {
            "agent_report_status": mvp_loop_full_repair.get("agent_report_status"),
            "repair_hint_status": mvp_loop_full_repair.get("repair_hint_status"),
            "repair_prompt_has_hint": mvp_loop_full_repair.get("repair_prompt_has_hint"),
            "chain_status": mvp_loop_full_repair.get("chain_status"),
            "review_status": mvp_loop_full_repair.get("review_status"),
            "apply_status": mvp_loop_full_repair.get("apply_status"),
            "verification_status": mvp_loop_full_repair.get("verification_status"),
            "status_next_action": mvp_loop_full_repair.get("status_next_action"),
        },
        "verified_repair_github_dry_run": {
            "repair_verification_status": verified_repair_github_dry_run.get(
                "repair_verification_status"
            ),
            "save_dry_run_source": verified_repair_github_dry_run.get(
                "save_dry_run_source"
            ),
            "save_target_path": verified_repair_github_dry_run.get("save_target_path"),
            "save_branch": verified_repair_github_dry_run.get("save_branch"),
            "pull_request_dry_run_source": verified_repair_github_dry_run.get(
                "pull_request_dry_run_source"
            ),
            "pull_request_head": verified_repair_github_dry_run.get(
                "pull_request_head"
            ),
            "pull_request_draft": verified_repair_github_dry_run.get(
                "pull_request_draft"
            ),
            "github_request_sent": verified_repair_github_dry_run.get(
                "github_request_sent"
            ),
            "mvp_loop_github_dry_run": verified_repair_github_dry_run.get(
                "mvp_loop_github_dry_run"
            ),
            "mvp_loop_github_request_sent": verified_repair_github_dry_run.get(
                "mvp_loop_github_request_sent"
            ),
            "mvp_loop_save_source": verified_repair_github_dry_run.get(
                "mvp_loop_save_source"
            ),
            "mvp_loop_pull_request_source": verified_repair_github_dry_run.get(
                "mvp_loop_pull_request_source"
            ),
        },
        "github_dry_run_artifacts": {
            "matched": github_dry_run_artifacts.get("matched"),
            "scanned": github_dry_run_artifacts.get("scanned"),
            "dry_run_types": github_dry_run_artifacts.get("dry_run_types"),
            "github_request_sent": github_dry_run_artifacts.get(
                "github_request_sent"
            ),
            "save_source": github_dry_run_artifacts.get("save_source"),
            "pull_request_source": github_dry_run_artifacts.get(
                "pull_request_source"
            ),
            "list_source": github_dry_run_artifacts.get("list_source"),
        },
        "repair_loop": {
            "chain_status": repair_loop.get("chain_status"),
            "verification_ok": repair_loop.get("verification_ok"),
            "status_next_action": repair_loop.get("status_next_action"),
            "model_response_source": repair_loop.get("model_response_source"),
        },
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run BIBER's local provider, readiness, local MVP-loop success/failure, "
            "real-repo probe, full local MVP repair, GitHub dry-run handoff, "
            "GitHub dry-run artifact, and local repair-loop smokes as one "
            "no-GPU confidence gate."
        )
    )
    parser.add_argument("--output", help="Optional path for the confidence summary JSON.")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = run_confidence_smoke(args.timeout_seconds)
    if args.output:
        write_json(Path(args.output), summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
