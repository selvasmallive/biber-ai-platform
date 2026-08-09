#!/usr/bin/env python3
"""Create GitHub save/PR dry-runs from a verified live repair artifact.

This is a post-verification bridge for BIBER MVP. It takes a
``local-verify-chain`` artifact from a real repo repair, confirms the repair was
verified, then creates ``save-github --dry-run`` artifacts for the touched files
and one ``create-pr --dry-run`` artifact. It never sends a GitHub request, never
uses OpenAI mentor, and never trains.
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


DEFAULT_OWNER = "selvasmallive"
DEFAULT_REPO = "biber-ai-platform"
DEFAULT_BASE_BRANCH = "biber/mvp-resume-20260712"
DEFAULT_TEST_ID = "python-compileall-api"


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def default_output_root() -> Path:
    workspace_outputs = Path("/workspace/outputs")
    if workspace_outputs.is_dir():
        return workspace_outputs
    return Path(tempfile.gettempdir())


def read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{path} did not contain a JSON object")
    return parsed


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_client(repo_root: Path, artifact_dir: Path, *args: str) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(artifact_dir / "pycache")
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "biber_agent_client.py"),
            "--json",
            *args,
        ],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=180,
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


def ensure_relative_file(target_root: Path, relative_path: str) -> Path:
    target_root = target_root.resolve()
    file_path = (target_root / relative_path).resolve()
    try:
        file_path.relative_to(target_root)
    except ValueError as exc:
        raise RuntimeError(f"touched path escapes target root: {relative_path}") from exc
    if not file_path.is_file():
        raise RuntimeError(f"verified touched file is missing: {file_path}")
    return file_path


def create_fixture(work_root: Path) -> tuple[Path, Path]:
    target_root = work_root / "fixture-target"
    target_file = target_root / "src" / "app.py"
    target_file.parent.mkdir(parents=True)
    target_file.write_text("def answer():\n    return 2\n", encoding="utf-8")
    apply_artifact = work_root / "fixture-repair-edit-apply.json"
    verify_artifact = work_root / "fixture-local-verify-chain.json"
    write_json(
        apply_artifact,
        {
            "source": "biber_mvp_loop_repair_edit_apply",
            "ok": True,
            "apply_status": "applied",
            "plan_hash": "fixture-plan-hash",
            "target_root": str(target_root),
            "edit_apply": {
                "ok": True,
                "files_touched": 1,
                "applied": [
                    {
                        "path": "src/app.py",
                        "changed": True,
                        "created": False,
                        "replacements": 1,
                    }
                ],
            },
            "training_allowed": False,
        },
    )
    write_json(
        verify_artifact,
        {
            "source": "biber_local_repair_verification_chain",
            "ok": True,
            "chain_status": "verified",
            "verification_status": "passed",
            "test_ok": True,
            "test_id": DEFAULT_TEST_ID,
            "source_artifact": str(apply_artifact),
            "target_root": str(target_root),
            "training_allowed": False,
        },
    )
    return verify_artifact, target_root


def verified_apply_artifact(
    *, verification_artifact: Path, target_root_override: Path | None
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    verification = read_json(verification_artifact)
    if verification.get("ok") is not True:
        raise RuntimeError("verification artifact is not ok")
    if verification.get("chain_status") != "verified":
        raise RuntimeError("verification artifact is not a verified chain")
    if verification.get("test_ok") is not True:
        raise RuntimeError("verification artifact test did not pass")

    source_artifact = verification.get("source_artifact")
    if not source_artifact:
        raise RuntimeError("verification artifact does not reference source_artifact")
    apply_artifact = Path(str(source_artifact))
    if not apply_artifact.is_absolute():
        apply_artifact = (verification_artifact.parent / apply_artifact).resolve()
    apply_payload = read_json(apply_artifact)
    if apply_payload.get("ok") is not True:
        raise RuntimeError("apply artifact is not ok")
    if apply_payload.get("apply_status") != "applied":
        raise RuntimeError("apply artifact was not applied")

    target_root_value = (
        str(target_root_override)
        if target_root_override is not None
        else str(verification.get("target_root") or apply_payload.get("target_root") or "")
    )
    if not target_root_value:
        raise RuntimeError("target root is missing")
    target_root = Path(target_root_value).resolve()
    if not target_root.is_dir():
        raise RuntimeError(f"target root is not a directory: {target_root}")
    return verification, apply_payload, apply_artifact, target_root


def touched_paths(apply_payload: dict[str, Any], *, max_save_files: int) -> list[str]:
    edit_apply = apply_payload.get("edit_apply")
    if not isinstance(edit_apply, dict):
        raise RuntimeError("apply artifact missing edit_apply object")
    applied = edit_apply.get("applied")
    if not isinstance(applied, list):
        raise RuntimeError("apply artifact missing edit_apply.applied list")
    paths: list[str] = []
    for item in applied:
        if not isinstance(item, dict) or item.get("changed") is not True:
            continue
        path = item.get("path")
        if isinstance(path, str) and path:
            paths.append(path)
    if not paths:
        raise RuntimeError("apply artifact did not touch any changed files")
    if len(paths) > max_save_files:
        raise RuntimeError(
            f"verified repair touched {len(paths)} files, max_save_files={max_save_files}"
        )
    return paths


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = Path(args.output_root) if args.output_root else default_output_root()
    work_root = output_root / f"biber-live-verified-github-dry-run-{timestamp()}"
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=False)

    verification_artifact = Path(args.verification_artifact).resolve()
    target_root_override = Path(args.target_root).resolve() if args.target_root else None
    if args.mode == "fixture":
        verification_artifact, target_root_override = create_fixture(work_root)

    verification, apply_payload, apply_artifact, target_root = verified_apply_artifact(
        verification_artifact=verification_artifact,
        target_root_override=target_root_override,
    )
    paths = touched_paths(apply_payload, max_save_files=args.max_save_files)
    plan_hash = str(verification.get("plan_hash") or apply_payload.get("plan_hash") or "")
    branch = args.branch or f"biber/live-verified-repair-{timestamp()}"
    commit_message = args.commit_message or "Save verified BIBER live repair"
    pr_title = args.pr_title or "Save verified BIBER live repair"

    save_artifacts: list[dict[str, Any]] = []
    for index, relative_path in enumerate(paths, start=1):
        content_file = ensure_relative_file(target_root, relative_path)
        save_artifact = artifact_dir / f"github-save-dry-run-{index}.json"
        save = run_client(
            repo_root,
            artifact_dir,
            "save-github",
            "--dry-run",
            "--path",
            relative_path,
            "--content-file",
            str(content_file),
            "--owner",
            args.owner,
            "--repo",
            args.repo,
            "--branch",
            branch,
            "--base-branch",
            args.base_branch,
            "--create-branch-if-missing",
            "--commit-message",
            commit_message,
            "--output",
            str(save_artifact),
        )
        save_artifacts.append(
            {
                "path": relative_path,
                "content_file": str(content_file),
                "artifact": str(save_artifact),
                "source": save.get("source"),
                "dry_run": save.get("dry_run"),
                "github_request_sent": save.get("github_request_sent"),
                "content_bytes": save.get("content_bytes"),
            }
        )

    pr_body = artifact_dir / "github-dry-run-pr-body.md"
    pr_body.write_text(
        "\n".join(
            [
                "Verified BIBER live repair dry-run.",
                "",
                f"Plan hash: {plan_hash or 'unknown'}",
                f"Verification artifact: {verification_artifact}",
                f"Apply artifact: {apply_artifact}",
                f"Test id: {verification.get('test_id') or args.test_id}",
                "",
                "Files:",
                *[f"- {path}" for path in paths],
                "",
                "No GitHub request was sent by this smoke.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    pr_artifact = artifact_dir / "github-pr-dry-run.json"
    pull_request = run_client(
        repo_root,
        artifact_dir,
        "create-pr",
        "--dry-run",
        "--head",
        branch,
        "--base",
        args.base_branch,
        "--title",
        pr_title,
        "--body-file",
        str(pr_body),
        "--owner",
        args.owner,
        "--repo",
        args.repo,
        "--output",
        str(pr_artifact),
    )
    list_artifact = artifact_dir / "github-dry-run-list.json"
    listing = run_client(
        repo_root,
        artifact_dir,
        "list-github-dry-runs",
        str(artifact_dir),
        "--pattern",
        "*github-*-dry-run*.json",
        "--output",
        str(list_artifact),
    )
    dry_runs = [
        item for item in listing.get("artifacts", []) if isinstance(item, dict)
    ]
    request_sent = any(item.get("github_request_sent") is True for item in save_artifacts)
    request_sent = request_sent or pull_request.get("github_request_sent") is True
    ok = (
        verification.get("ok") is True
        and verification.get("chain_status") == "verified"
        and verification.get("test_ok") is True
        and apply_payload.get("apply_status") == "applied"
        and save_artifacts
        and all(item.get("source") == "biber_github_save_dry_run" for item in save_artifacts)
        and all(item.get("dry_run") is True for item in save_artifacts)
        and not request_sent
        and pull_request.get("source") == "biber_github_pull_request_dry_run"
        and pull_request.get("dry_run") is True
        and pull_request.get("github_request_sent") is False
        and listing.get("source") == "biber_github_dry_run_artifact_list"
        and int(listing.get("matched") or 0) >= len(paths) + 1
    )
    summary = {
        "source": "biber_live_verified_repair_github_dry_run_smoke",
        "ok": ok,
        "mode": args.mode,
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "live_provider_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "auto_saved": False,
        "github_request_sent": request_sent,
        "target_root": str(target_root),
        "verification_artifact": str(verification_artifact),
        "apply_artifact": str(apply_artifact),
        "verification_status": verification.get("verification_status"),
        "chain_status": verification.get("chain_status"),
        "test_id": verification.get("test_id") or args.test_id,
        "test_ok": verification.get("test_ok"),
        "plan_hash": plan_hash,
        "paths": paths,
        "owner": args.owner,
        "repo": args.repo,
        "branch": branch,
        "base_branch": args.base_branch,
        "work_root": str(work_root),
        "artifact_dir": str(artifact_dir),
        "save_artifacts": save_artifacts,
        "pull_request_artifact": str(pr_artifact),
        "pull_request_source": pull_request.get("source"),
        "pull_request_draft": (pull_request.get("pull_request") or {}).get("draft")
        if isinstance(pull_request.get("pull_request"), dict)
        else None,
        "list_artifact": str(list_artifact),
        "dry_run_artifacts_matched": listing.get("matched"),
        "dry_run_artifacts_scanned": listing.get("scanned"),
        "next_action": (
            "review_dry_run_artifacts_before_real_github_save_or_pr"
            if ok
            else "inspect_verified_artifact_and_dry_run_outputs"
        ),
    }
    if args.output:
        write_json(Path(args.output), summary)
    if not ok:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create no-request GitHub save/PR dry-runs from a verified repair."
    )
    parser.add_argument(
        "--mode",
        choices=["artifact", "fixture"],
        default="artifact",
        help="Use artifact mode for a real verification artifact or fixture mode for smoke validation.",
    )
    parser.add_argument("--verification-artifact", default="")
    parser.add_argument("--target-root")
    parser.add_argument("--owner", default=DEFAULT_OWNER)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--branch")
    parser.add_argument("--base-branch", default=DEFAULT_BASE_BRANCH)
    parser.add_argument("--commit-message")
    parser.add_argument("--pr-title")
    parser.add_argument("--test-id", default=DEFAULT_TEST_ID)
    parser.add_argument("--max-save-files", type=int, default=5)
    parser.add_argument("--output-root")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.mode == "artifact" and not args.verification_artifact:
        parser.error("--verification-artifact is required in artifact mode")
    return args


def main() -> int:
    args = parse_args()
    summary = run_smoke(args)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
