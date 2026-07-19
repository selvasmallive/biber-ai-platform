#!/usr/bin/env python3
"""Run a no-API BIBER local MVP-loop failure-path smoke test.

This smoke creates a temporary target repository with a Python syntax error,
runs scripts/biber_agent_client.py mvp-loop against it with --local-target-root,
and verifies that the failed artifact exposes agent_report.repair_hint. It then
runs prepare-repair locally to prove the hint is preserved for the next local
model repair step. It is CPU-only and does not resolve API credentials.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_client(repo_root: Path, artifact_dir: Path, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(artifact_dir / "pycache")
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


def create_target_repo(target_root: Path) -> None:
    (target_root / "app").mkdir(parents=True)
    (target_root / "src").mkdir(parents=True)
    (target_root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (target_root / "src" / "app.py").write_text(
        "def broken(:\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (target_root / "README.md").write_text("# Failing fixture repo\n", encoding="utf-8")


def run_smoke(work_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = work_root / "artifacts"
    target_root = work_root / "target-repo"
    artifact_dir.mkdir(parents=True)
    create_target_repo(target_root)

    mvp_output_path = artifact_dir / "local-mvp-loop-failure.json"
    mvp_result = run_client(
        repo_root,
        artifact_dir,
        "mvp-loop",
        "--instruction",
        "Diagnose the local fixture syntax failure.",
        "--local-target-root",
        str(target_root),
        "--changed-path",
        "src/app.py",
        "--test-id",
        "python-compileall-api",
        "--output",
        str(mvp_output_path),
    )
    saved_mvp = json.loads(mvp_output_path.read_text(encoding="utf-8"))
    if saved_mvp != mvp_result:
        raise RuntimeError("mvp-loop failure artifact did not match stdout JSON")

    agent_report = mvp_result.get("agent_report")
    if not isinstance(agent_report, dict):
        raise RuntimeError("failed mvp-loop did not include agent_report")
    repair_hint = agent_report.get("repair_hint")
    if not isinstance(repair_hint, dict):
        raise RuntimeError("failed mvp-loop did not include agent_report.repair_hint")

    repair_output_path = artifact_dir / "prepared-repair.json"
    repair_request = run_client(
        repo_root,
        artifact_dir,
        "prepare-repair",
        str(mvp_output_path),
        "--output",
        str(repair_output_path),
    )
    saved_repair = json.loads(repair_output_path.read_text(encoding="utf-8"))
    if saved_repair != repair_request:
        raise RuntimeError("prepare-repair artifact did not match stdout JSON")
    prepared_hint = repair_request.get("repair_hint")
    if not isinstance(prepared_hint, dict):
        raise RuntimeError("prepared repair did not include repair_hint")
    repair_prompt = str(repair_request.get("repair_prompt") or "")

    failure_list_output_path = artifact_dir / "failed-mvp-loop-list.json"
    failure_list = run_client(
        repo_root,
        artifact_dir,
        "list-mvp-loops",
        str(artifact_dir),
        "--failed-only",
        "--output",
        str(failure_list_output_path),
    )
    saved_failure_list = json.loads(
        failure_list_output_path.read_text(encoding="utf-8")
    )
    if saved_failure_list != failure_list:
        raise RuntimeError("list-mvp-loops artifact did not match stdout JSON")
    shown_failure_list = run_client(
        repo_root,
        artifact_dir,
        "show-mvp-loop-list",
        str(failure_list_output_path),
    )
    if shown_failure_list != saved_failure_list:
        raise RuntimeError("show-mvp-loop-list output did not match saved list JSON")
    listed_failures = [
        item
        for item in failure_list.get("artifacts", [])
        if isinstance(item, dict)
    ]
    listed_failure = listed_failures[0] if listed_failures else {}

    next_workflow = [str(item) for item in repair_hint.get("next_workflow", [])]
    next_command = str(repair_hint.get("next_command") or "")
    listed_next_command = str(listed_failure.get("repair_next_command") or "")
    summary = {
        "source": "biber_local_mvp_loop_failure_smoke",
        "ok": (
            mvp_result.get("ok") is False
            and mvp_result.get("test_ok") is False
            and agent_report.get("status") == "test_failed"
            and repair_hint.get("status") == "ready_for_prepare_repair"
            and repair_hint.get("api_required") is False
            and repair_hint.get("mentor_used") is False
            and repair_hint.get("training_allowed") is False
            and repair_hint.get("test_id") == "python-compileall-api"
            and bool(repair_hint.get("primary_category"))
            and "prepare-repair" in next_workflow
            and "prepare-repair" in next_command
            and str(mvp_output_path) in next_command
            and str(repair_output_path) in next_command
            and repair_request.get("repair_status") == "ready_for_local_model"
            and prepared_hint.get("status") == "ready_for_prepare_repair"
            and "repair_hint: status=ready_for_prepare_repair" in repair_prompt
            and "category=compile_error" in repair_prompt
            and len(listed_failures) == 1
            and listed_failure.get("repair_hint_status")
            == "ready_for_prepare_repair"
            and listed_failure.get("repair_primary_category") == "compile_error"
            and listed_failure.get("repair_detected_stack") == "python"
            and listed_failure.get("repair_next_step") == "prepare-repair"
            and "prepare-repair" in listed_next_command
            and failure_list.get("artifact_path") == str(failure_list_output_path)
            and shown_failure_list.get("source") == "biber_mvp_loop_artifact_list"
        ),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "mvp_artifact": str(mvp_output_path),
        "repair_artifact": str(repair_output_path),
        "target_root": str(target_root),
        "agent_report_status": agent_report.get("status"),
        "repair_hint_status": repair_hint.get("status"),
        "primary_category": repair_hint.get("primary_category"),
        "detected_stack": repair_hint.get("detected_stack"),
        "test_ok": mvp_result.get("test_ok"),
        "repair_status": repair_request.get("repair_status"),
        "repair_prompt_has_hint": (
            "repair_hint: status=ready_for_prepare_repair" in repair_prompt
        ),
        "repair_hint_next_command": next_command,
        "next_workflow": next_workflow,
        "list_failed_artifacts": len(listed_failures),
        "list_repair_hint_status": listed_failure.get("repair_hint_status"),
        "list_repair_primary_category": listed_failure.get("repair_primary_category"),
        "list_repair_detected_stack": listed_failure.get("repair_detected_stack"),
        "list_repair_next_step": listed_failure.get("repair_next_step"),
        "list_repair_next_command_has_prepare": (
            "prepare-repair" in listed_next_command
        ),
        "list_artifact": str(failure_list_output_path),
        "show_list_artifact_ok": (
            shown_failure_list.get("source") == "biber_mvp_loop_artifact_list"
        ),
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a no-API BIBER local MVP-loop failure-path smoke test."
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary target repo and artifacts after the smoke run.",
    )
    parser.add_argument("--output", help="Optional path for the smoke summary JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work_root = Path(tempfile.mkdtemp(prefix="biber-local-mvp-loop-failure-smoke-"))
    try:
        summary = run_smoke(work_root)
        if args.keep_temp:
            summary["kept_temp"] = True
            summary["work_root"] = str(work_root)
        if args.output:
            write_json(Path(args.output), summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    finally:
        if not args.keep_temp:
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
