#!/usr/bin/env python3
"""Verify standalone GitHub dry-run artifacts stay local and resumable.

This smoke creates save-github and create-pr dry-run artifacts, summarizes each
artifact, then lists the artifact directory. No BIBER API key, GitHub token,
OpenAI mentor, Vast GPU, live model endpoint, or training is used.
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


def run_client_text(repo_root: Path, artifact_dir: Path, *args: str) -> str:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(artifact_dir / "pycache")
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "biber_agent_client.py"),
        *args,
    ]
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
    return completed.stdout


def run_client_json(repo_root: Path, artifact_dir: Path, *args: str) -> dict[str, Any]:
    output = run_client_text(repo_root, artifact_dir, "--json", *args)
    parsed = json.loads(output)
    if not isinstance(parsed, dict):
        raise RuntimeError("BIBER client did not return a JSON object")
    return parsed


def read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{path} did not contain a JSON object")
    return parsed


def run_smoke(work_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True)

    pr_body = artifact_dir / "github-dry-run-pr-body.md"
    pr_body.write_text(
        "Dry-run PR body for local BIBER artifact listing.\n",
        encoding="utf-8",
    )
    save_artifact = artifact_dir / "github-save-dry-run.json"
    pr_artifact = artifact_dir / "github-pr-dry-run.json"
    list_artifact = artifact_dir / "github-dry-run-list.json"

    save = run_client_json(
        repo_root,
        artifact_dir,
        "save-github",
        "--dry-run",
        "--path",
        "generated/example.ts",
        "--content",
        "export const ok = true;\n",
        "--owner",
        "acme",
        "--repo",
        "biber-generated",
        "--branch",
        "biber/generated-example",
        "--base-branch",
        "main",
        "--create-branch-if-missing",
        "--commit-message",
        "Save generated BIBER example",
        "--output",
        str(save_artifact),
    )
    pull_request = run_client_json(
        repo_root,
        artifact_dir,
        "create-pr",
        "--dry-run",
        "--head",
        "biber/generated-example",
        "--base",
        "main",
        "--title",
        "Save generated BIBER example",
        "--body-file",
        str(pr_body),
        "--owner",
        "acme",
        "--repo",
        "biber-generated",
        "--output",
        str(pr_artifact),
    )
    save_summary = run_client_text(
        repo_root,
        artifact_dir,
        "show-github-dry-run",
        str(save_artifact),
    )
    pr_summary = run_client_text(
        repo_root,
        artifact_dir,
        "show-github-dry-run",
        str(pr_artifact),
    )
    listing = run_client_json(
        repo_root,
        artifact_dir,
        "list-github-dry-runs",
        str(artifact_dir),
        "--pattern",
        "*github-*-dry-run.json",
        "--output",
        str(list_artifact),
    )
    list_summary = run_client_text(
        repo_root,
        artifact_dir,
        "list-github-dry-runs",
        str(artifact_dir),
        "--pattern",
        "*github-*-dry-run.json",
    )

    listed_artifacts = [
        item for item in listing.get("artifacts", []) if isinstance(item, dict)
    ]
    dry_run_types = sorted(
        str(item.get("dry_run_type")) for item in listed_artifacts
    )
    summary = {
        "source": "biber_local_github_dry_run_artifacts_smoke",
        "ok": (
            save.get("source") == "biber_github_save_dry_run"
            and save.get("api_required") is False
            and save.get("github_request_sent") is False
            and save.get("artifact_path") == str(save_artifact)
            and read_json(save_artifact) == save
            and pull_request.get("source") == "biber_github_pull_request_dry_run"
            and pull_request.get("api_required") is False
            and pull_request.get("github_request_sent") is False
            and pull_request.get("artifact_path") == str(pr_artifact)
            and read_json(pr_artifact) == pull_request
            and "BIBER GitHub save dry-run" in save_summary
            and "github_request_sent: False" in save_summary
            and "BIBER GitHub pull request dry-run" in pr_summary
            and "github_request_sent: False" in pr_summary
            and listing.get("source") == "biber_github_dry_run_artifact_list"
            and listing.get("matched") == 2
            and listing.get("github_request_sent") is False
            and dry_run_types == ["pull_request", "save"]
            and listing.get("artifact_path") == str(list_artifact)
            and read_json(list_artifact) == listing
            and "BIBER GitHub dry-run artifacts (2)" in list_summary
            and "type=save" in list_summary
            and "type=pull_request" in list_summary
        ),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "github_request_sent": False,
        "save_artifact": str(save_artifact),
        "pull_request_artifact": str(pr_artifact),
        "list_artifact": str(list_artifact),
        "matched": listing.get("matched"),
        "scanned": listing.get("scanned"),
        "dry_run_types": dry_run_types,
        "save_source": save.get("source"),
        "pull_request_source": pull_request.get("source"),
        "list_source": listing.get("source"),
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a no-credential BIBER GitHub dry-run artifact smoke."
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
    work_root = Path(tempfile.mkdtemp(prefix="biber-local-github-dry-run-artifacts-"))
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
