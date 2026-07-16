#!/usr/bin/env python3
"""Verify a local repaired file can flow into GitHub save/PR dry-runs.

This smoke first runs the full no-API local MVP-loop repair smoke with a kept
temporary workspace. It then points save-github --dry-run at the verified
repaired file and create-pr --dry-run at a review branch. No BIBER API key,
GitHub token, OpenAI mentor, Vast GPU, or training is used.
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


def run_python_json(repo_root: Path, artifact_dir: Path, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(artifact_dir / "pycache")
    cmd = [sys.executable, *args]
    completed = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{' '.join(cmd)} failed with exit code {completed.returncode}: "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        )
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{' '.join(cmd)} did not return a JSON object")
    return parsed


def run_client(repo_root: Path, artifact_dir: Path, *args: str) -> dict[str, Any]:
    return run_python_json(
        repo_root,
        artifact_dir,
        str(repo_root / "scripts" / "biber_agent_client.py"),
        "--json",
        *args,
    )


def run_smoke(work_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True)

    repair = run_python_json(
        repo_root,
        artifact_dir,
        str(repo_root / "scripts" / "biber_local_mvp_loop_full_repair_smoke.py"),
        "--keep-temp",
    )
    repair_work_root_value = str(repair.get("work_root") or "")
    repair_work_root = Path(repair_work_root_value) if repair_work_root_value else None
    try:
        target_root = Path(str(repair.get("target_root") or ""))
        repaired_file = target_root / "src" / "app.py"
        if not repaired_file.is_file():
            raise RuntimeError(f"Verified repair file not found: {repaired_file}")
        repaired_source = repaired_file.read_text(encoding="utf-8")

        pr_body = artifact_dir / "github-dry-run-pr-body.md"
        pr_body.write_text(
            "Verified local BIBER repair smoke output; dry-run only.\n",
            encoding="utf-8",
        )
        save = run_client(
            repo_root,
            artifact_dir,
            "save-github",
            "--dry-run",
            "--path",
            "src/app.py",
            "--content-file",
            str(repaired_file),
            "--owner",
            "acme",
            "--repo",
            "biber-generated",
            "--branch",
            "biber/local-verified-repair",
            "--base-branch",
            "main",
            "--create-branch-if-missing",
            "--commit-message",
            "Save verified local BIBER repair",
        )
        pull_request = run_client(
            repo_root,
            artifact_dir,
            "create-pr",
            "--dry-run",
            "--head",
            "biber/local-verified-repair",
            "--base",
            "main",
            "--title",
            "Save verified local BIBER repair",
            "--body-file",
            str(pr_body),
            "--owner",
            "acme",
            "--repo",
            "biber-generated",
        )
        mvp_handoff = run_client(
            repo_root,
            artifact_dir,
            "mvp-loop",
            "--instruction",
            "Prepare a GitHub dry-run handoff for the verified local repair.",
            "--local-target-root",
            str(target_root),
            "--changed-path",
            "src/app.py",
            "--save-github-path",
            "src/app.py",
            "--save-content-file",
            str(repaired_file),
            "--github-owner",
            "acme",
            "--github-repo",
            "biber-generated",
            "--github-branch",
            "biber/local-verified-repair",
            "--github-base-branch",
            "main",
            "--create-branch-if-missing",
            "--commit-message",
            "Save verified local BIBER repair",
            "--github-dry-run",
            "--create-pr",
            "--pr-title",
            "Save verified local BIBER repair",
            "--pr-body-file",
            str(pr_body),
        )

        save_target = save.get("target")
        if not isinstance(save_target, dict):
            save_target = {}
        pr_payload = pull_request.get("pull_request")
        if not isinstance(pr_payload, dict):
            pr_payload = {}
        mvp_save = mvp_handoff.get("steps", {}).get("github_save", {})
        if not isinstance(mvp_save, dict):
            mvp_save = {}
        mvp_pr = mvp_handoff.get("steps", {}).get("github_pull_request", {})
        if not isinstance(mvp_pr, dict):
            mvp_pr = {}

        summary = {
            "source": "biber_local_verified_repair_github_dry_run_smoke",
            "ok": (
                repair.get("ok") is True
                and repair.get("verification_status") == "verified"
                and "def answer():" in repaired_source
                and "return 2" in repaired_source
                and save.get("source") == "biber_github_save_dry_run"
                and save.get("dry_run") is True
                and save.get("api_required") is False
                and save.get("github_request_sent") is False
                and save_target.get("path") == "src/app.py"
                and save_target.get("branch") == "biber/local-verified-repair"
                and int(save.get("content_bytes") or 0) > 0
                and pull_request.get("source") == "biber_github_pull_request_dry_run"
                and pull_request.get("dry_run") is True
                and pull_request.get("api_required") is False
                and pull_request.get("github_request_sent") is False
                and pr_payload.get("head") == "biber/local-verified-repair"
                and pr_payload.get("base") == "main"
                and pr_payload.get("draft") is True
                and mvp_handoff.get("github_dry_run") is True
                and mvp_handoff.get("github_request_sent") is False
                and mvp_save.get("source") == "biber_github_save_dry_run"
                and mvp_save.get("github_request_sent") is False
                and mvp_pr.get("source") == "biber_github_pull_request_dry_run"
                and mvp_pr.get("github_request_sent") is False
            ),
            "external_network_required": False,
            "gpu_required": False,
            "api_required": False,
            "mentor_used": False,
            "training_allowed": False,
            "auto_applied": False,
            "auto_saved": False,
            "github_request_sent": False,
            "repair_source": repair.get("source"),
            "repair_verification_status": repair.get("verification_status"),
            "repair_work_root": str(repair_work_root) if repair_work_root else None,
            "target_root": str(target_root),
            "repaired_file": str(repaired_file),
            "save_dry_run_source": save.get("source"),
            "save_target_path": save_target.get("path"),
            "save_branch": save_target.get("branch"),
            "save_content_bytes": save.get("content_bytes"),
            "pull_request_dry_run_source": pull_request.get("source"),
            "pull_request_head": pr_payload.get("head"),
            "pull_request_base": pr_payload.get("base"),
            "pull_request_draft": pr_payload.get("draft"),
            "mvp_loop_github_dry_run": mvp_handoff.get("github_dry_run"),
            "mvp_loop_github_request_sent": mvp_handoff.get("github_request_sent"),
            "mvp_loop_save_source": mvp_save.get("source"),
            "mvp_loop_pull_request_source": mvp_pr.get("source"),
        }
        if not summary["ok"]:
            raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
        return summary
    finally:
        if repair_work_root is not None and repair_work_root.exists():
            shutil.rmtree(repair_work_root, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a no-credential BIBER verified-repair to GitHub dry-run handoff smoke."
        )
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
    work_root = Path(tempfile.mkdtemp(prefix="biber-local-github-dry-run-smoke-"))
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
