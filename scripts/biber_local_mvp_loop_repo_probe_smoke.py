#!/usr/bin/env python3
"""Probe BIBER's local MVP-loop against this real repo without edits.

This smoke runs scripts/biber_agent_client.py mvp-loop with --local-target-root
pointing at the current BIBER checkout. It captures git state, selects repo
context, and dry-runs an allowlisted test without requiring BIBER API auth,
OpenAI mentor, Vast GPU, or training.
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


def git_status_short(repo_root: Path) -> dict[str, Any]:
    completed = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    return {
        "available": completed.returncode == 0,
        "returncode": completed.returncode,
        "status_short": completed.stdout.splitlines(),
        "stderr": completed.stderr,
    }


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
        timeout=120,
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


def run_smoke(work_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True)

    git_before = git_status_short(repo_root)
    mvp_output_path = artifact_dir / "real-repo-mvp-loop-probe.json"
    mvp_result = run_client(
        repo_root,
        artifact_dir,
        "mvp-loop",
        "--instruction",
        "Probe BIBER local MVP loop on the current repository without edits.",
        "--local-target-root",
        str(repo_root),
        "--include-git-state",
        "--changed-path",
        "scripts/biber_agent_client.py",
        "--changed-path",
        "docs/BIBER_ONLY_WORKSPACE.md",
        "--test-id",
        "python-compileall-api",
        "--test-dry-run",
        "--output",
        str(mvp_output_path),
    )
    git_after = git_status_short(repo_root)

    saved_mvp = json.loads(mvp_output_path.read_text(encoding="utf-8"))
    if saved_mvp != mvp_result:
        raise RuntimeError("mvp-loop repo probe artifact did not match stdout JSON")

    agent_report = mvp_result.get("agent_report")
    if not isinstance(agent_report, dict):
        raise RuntimeError("repo probe mvp-loop did not include agent_report")
    report_repo = agent_report.get("repo")
    if not isinstance(report_repo, dict):
        raise RuntimeError("repo probe mvp-loop did not include agent_report.repo")
    report_test = agent_report.get("test")
    if not isinstance(report_test, dict):
        raise RuntimeError("repo probe mvp-loop did not include agent_report.test")

    selected_paths = [str(path) for path in mvp_result.get("selected_context_paths", [])]
    git_state = mvp_result.get("steps", {}).get("git_state", {})
    if not isinstance(git_state, dict):
        git_state = {}
    context_plan = mvp_result.get("steps", {}).get("context_plan", {})
    if not isinstance(context_plan, dict):
        context_plan = {}

    summary = {
        "source": "biber_local_mvp_loop_repo_probe_smoke",
        "ok": (
            mvp_result.get("ok") is True
            and mvp_result.get("context_mode") == "local_target_root"
            and mvp_result.get("test_mode") == "local_target_root"
            and agent_report.get("status") == "dry_run_only"
            and report_test.get("executed") is False
            and report_test.get("test_id") == "python-compileall-api"
            and report_repo.get("branch")
            and git_state.get("available") is True
            and "scripts/biber_agent_client.py" in selected_paths
            and "docs/BIBER_ONLY_WORKSPACE.md" in selected_paths
            and git_before.get("status_short") == git_after.get("status_short")
        ),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "target_root": str(repo_root),
        "mvp_artifact": str(mvp_output_path),
        "agent_report_status": agent_report.get("status"),
        "git_branch": report_repo.get("branch"),
        "git_dirty": report_repo.get("dirty"),
        "selected_context_paths": len(selected_paths),
        "detected_project_types": context_plan.get("detected_project_types", []),
        "test_id": report_test.get("test_id"),
        "test_executed": report_test.get("executed"),
        "repo_status_unchanged": git_before.get("status_short") == git_after.get("status_short"),
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe BIBER's local MVP-loop against this real repo without edits."
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep the temporary artifact directory after the smoke run.",
    )
    parser.add_argument("--output", help="Optional path for the smoke summary JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    work_root = Path(tempfile.mkdtemp(prefix="biber-local-mvp-loop-repo-probe-smoke-"))
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
