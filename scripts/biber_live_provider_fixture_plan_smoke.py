#!/usr/bin/env python3
"""Run a live-provider plan-only smoke against a disposable fixture target."""

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


DEFAULT_BASE_URL = "http://127.0.0.1:8001/v1"
DEFAULT_MODEL = "biber-dev-core"
DEFAULT_OLD_TOKEN = "BIBER_FIXTURE_OLD_TOKEN"
DEFAULT_NEW_TOKEN = "BIBER_FIXTURE_NEW_TOKEN"
DEFAULT_REQUIRED_PATH = "docs/BIBER_ONLY_WORKSPACE.md"


def timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def default_output_root() -> Path:
    env_root = os.getenv("BIBER_LIVE_FIXTURE_PLAN_SMOKE_OUTPUT_ROOT")
    if env_root:
        return Path(env_root)
    workspace_outputs = Path("/workspace/outputs")
    if workspace_outputs.is_dir():
        return workspace_outputs
    return Path(tempfile.gettempdir())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def create_fixture_target(target_root: Path, *, old_token: str) -> None:
    target_file = target_root / DEFAULT_REQUIRED_PATH
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(f"{old_token}\n", encoding="utf-8")
    (target_root / "README.md").write_text(
        "BIBER_FIXTURE_README\n",
        encoding="utf-8",
    )


def run_real_repo_plan(
    *,
    repo_root: Path,
    work_root: Path,
    target_root: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(repo_root / "scripts" / "biber_live_provider_real_repo_plan_smoke.py"),
        "--mode",
        args.mode,
        "--base-url",
        args.base_url,
        "--model",
        args.model,
        "--target-root",
        str(target_root),
        "--required-path",
        DEFAULT_REQUIRED_PATH,
        "--required-old-text",
        args.old_token,
        "--required-new-text",
        args.new_token,
        "--changed-path",
        DEFAULT_REQUIRED_PATH,
        "--pinned-path",
        "README.md",
        "--max-context-files",
        str(args.max_context_files),
        "--output-root",
        str(work_root),
    ]
    if args.require_ready:
        cmd.append("--require-ready")
    else:
        cmd.append("--no-require-ready")
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(work_root / "pycache")
    completed = subprocess.run(
        cmd,
        cwd=str(repo_root),
        capture_output=True,
        check=False,
        env=env,
        text=True,
        timeout=args.timeout_seconds,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "biber_live_provider_real_repo_plan_smoke.py did not return JSON: "
            f"exit={completed.returncode} stdout={completed.stdout!r} "
            f"stderr={completed.stderr!r}"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeError("biber_live_provider_real_repo_plan_smoke.py returned non-object JSON")
    if completed.returncode != 0 and payload.get("ok") is True:
        raise RuntimeError("real-repo plan smoke returned success payload with nonzero exit")
    return payload


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    output_root = Path(args.output_root) if args.output_root else default_output_root()
    work_root = output_root / f"biber-live-fixture-plan-{timestamp()}"
    target_root = work_root / "target"
    artifact_dir = work_root / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    create_fixture_target(target_root, old_token=args.old_token)

    plan = run_real_repo_plan(
        repo_root=repo_root,
        work_root=work_root,
        target_root=target_root,
        args=args,
    )
    ok = (
        plan.get("ok") is True
        and plan.get("mode") == args.mode
        and plan.get("chain_status") == "planned"
        and plan.get("planned") == 1
        and plan.get("rejected") == 0
        and plan.get("review_status") == "ready_for_explicit_apply_approval"
        and plan.get("mutation_performed") is False
        and plan.get("github_request_sent") is False
        and plan.get("mentor_used") is False
        and plan.get("training_allowed") is False
        and (plan.get("required_target_probe") or {}).get("ok") is True
    )
    summary = {
        "source": "biber_live_provider_fixture_plan_smoke",
        "ok": ok,
        "mode": args.mode,
        "base_url": args.base_url,
        "model": args.model,
        "external_network_required": False,
        "gpu_required": args.mode == "live",
        "api_required": False,
        "live_provider_required": args.mode == "live",
        "mentor_used": False,
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "github_request_sent": False,
        "target_is_disposable": True,
        "work_root": str(work_root),
        "artifact_dir": str(artifact_dir),
        "target_root": str(target_root),
        "real_repo_plan_work_root": plan.get("work_root"),
        "real_repo_plan_artifact_dir": plan.get("artifact_dir"),
        "readiness_ok": plan.get("readiness_ok"),
        "chain_status": plan.get("chain_status"),
        "plan_outcome": plan.get("plan_outcome"),
        "review_status": plan.get("review_status"),
        "apply_recommendation": plan.get("apply_recommendation"),
        "planned": plan.get("planned"),
        "rejected": plan.get("rejected"),
        "plan_hash": plan.get("plan_hash"),
        "repo_status_unchanged": plan.get("repo_status_unchanged"),
        "mutation_performed": plan.get("mutation_performed"),
        "required_target_probe": plan.get("required_target_probe"),
        "selected_context_paths": plan.get("selected_context_paths"),
        "model_response_content_preview": plan.get("model_response_content_preview"),
        "real_repo_plan": plan,
        "next_action": (
            "review_plan_artifacts_only_no_apply"
            if ok
            else "inspect_live_fixture_plan_artifacts"
        ),
    }
    if args.output:
        write_json(Path(args.output), summary)
    if args.cleanup and ok:
        shutil.rmtree(work_root)
        summary["work_root_cleanup"] = "deleted_after_success"
    if not ok:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a disposable fixture through the live-provider real-repo "
            "plan-only path. It never applies edits, saves to GitHub, calls "
            "OpenAI mentor, or trains."
        )
    )
    parser.add_argument("--mode", choices=["live", "mock"], default="live")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIBER_LOCAL_OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument(
        "--model",
        default=(
            os.getenv("BIBER_LOCAL_OPENAI_MODEL")
            or os.getenv("BIBER_LOCAL_MODEL_NAME")
            or DEFAULT_MODEL
        ),
    )
    parser.add_argument("--old-token", default=DEFAULT_OLD_TOKEN)
    parser.add_argument("--new-token", default=DEFAULT_NEW_TOKEN)
    parser.add_argument("--max-context-files", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--require-ready", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--output-root")
    parser.add_argument("--output")
    parser.add_argument("--cleanup", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = run_smoke(args)
    except Exception as exc:
        print(f"biber_live_provider_fixture_plan_smoke: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
