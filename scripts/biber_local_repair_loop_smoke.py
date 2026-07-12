#!/usr/bin/env python3
"""Run a no-API BIBER local repair-loop smoke test.

This script creates a temporary target repository and artifact directory, then
walks the local repair flow through prepare, local model response, review,
guarded apply, verification, and loop status. It is intentionally CPU-only and
does not resolve BIBER/OpenAI credentials.
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


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object in {path}")
    return payload


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
        check=True,
        env=env,
        text=True,
    )
    return json.loads(completed.stdout)


def create_target_repo(target_root: Path) -> None:
    (target_root / "app").mkdir(parents=True)
    (target_root / "src").mkdir(parents=True)
    (target_root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (target_root / "src" / "app.py").write_text(
        "def answer():\n"
        "    return 1\n",
        encoding="utf-8",
    )


def create_failure_artifact(path: Path, target_root: Path) -> None:
    write_json(
        path,
        {
            "ok": False,
            "instruction": "Fix the local Python answer implementation.",
            "steps": {
                "context_plan": {
                    "ok": True,
                    "selected_context_paths": ["src/app.py"],
                },
                "test_run": {
                    "ok": False,
                    "test_id": "python-compileall-api",
                    "command": ["python", "-m", "compileall", "app", "src"],
                    "exit_code": 1,
                    "timed_out": False,
                    "stdout": "Assertion-style fixture expects answer() to return 2.\n",
                    "stderr": "",
                },
                "test_diagnosis": {
                    "primary_category": "assertion_failure",
                    "detected_stack": "python",
                    "summary": "Synthetic local repair-loop smoke failure.",
                    "suggested_next_actions": [
                        "Update src/app.py so answer() returns 2."
                    ],
                },
            },
            "selected_context_paths": ["src/app.py"],
            "target_root": str(target_root),
            "test_ok": False,
        },
    )


def run_smoke(work_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = work_root / "artifacts"
    target_root = work_root / "target-repo"
    artifact_dir.mkdir(parents=True)
    create_target_repo(target_root)

    failure = artifact_dir / "failure-mvp-loop.json"
    prepared = artifact_dir / "prepared-repair.json"
    model_response = artifact_dir / "model-response.json"
    local_chain = artifact_dir / "local-repair-chain.json"
    local_review = artifact_dir / "local-repair-chain-review.json"
    repair_plan = artifact_dir / "repair-edit-plan.json"
    repair_apply = artifact_dir / "repair-edit-apply.json"
    local_verify = artifact_dir / "local-verify-chain.json"
    loop_status = artifact_dir / "local-repair-loop-status.json"

    create_failure_artifact(failure, target_root)
    run_client(
        repo_root,
        artifact_dir,
        "prepare-repair",
        str(failure),
        "--output",
        str(prepared),
    )
    write_json(
        model_response,
        {
            "edits": [
                {
                    "path": "src/app.py",
                    "old_text": "return 1",
                    "new_text": "return 2",
                    "expected_replacements": 1,
                }
            ]
        },
    )
    chain = run_client(
        repo_root,
        artifact_dir,
        "local-repair-chain",
        str(prepared),
        "--model-response-file",
        str(model_response),
        "--target-root",
        str(target_root),
        "--output",
        str(local_chain),
    )
    review = run_client(
        repo_root,
        artifact_dir,
        "review-local-repair-chain",
        str(local_chain),
        "--output",
        str(local_review),
    )
    plan = chain.get("repair_edit_plan")
    if not isinstance(plan, dict):
        raise RuntimeError("local-repair-chain did not produce repair_edit_plan")
    write_json(repair_plan, plan)
    apply_result = run_client(
        repo_root,
        artifact_dir,
        "apply-repair-edits",
        str(repair_plan),
        "--approve",
        "--review-artifact",
        str(local_review),
        "--output",
        str(repair_apply),
    )
    verification = run_client(
        repo_root,
        artifact_dir,
        "local-verify-chain",
        str(repair_apply),
        "--diagnose-on-failure",
        "--output",
        str(local_verify),
    )
    status = run_client(
        repo_root,
        artifact_dir,
        "local-repair-loop-status",
        str(artifact_dir),
        "--output",
        str(loop_status),
    )

    final_source = (target_root / "src" / "app.py").read_text(encoding="utf-8")
    summary = {
        "source": "biber_local_repair_loop_smoke",
        "ok": (
            chain.get("chain_status") == "planned"
            and review.get("review_status") == "ready_for_explicit_apply_approval"
            and review.get("apply_recommendation")
            == "ready_for_explicit_apply_approval"
            and apply_result.get("apply_status") == "applied"
            and verification.get("chain_status") == "verified"
            and "return 2" in final_source
        ),
        "training_allowed": False,
        "auto_applied": False,
        "auto_saved": False,
        "api_required": False,
        "artifact_dir": str(artifact_dir),
        "target_root": str(target_root),
        "final_file_contains_return_2": "return 2" in final_source,
        "chain_status": verification.get("chain_status"),
        "verification_ok": verification.get("ok") is True,
        "status_next_action": (status.get("next_step") or {}).get("action"),
        "artifacts": {
            "failure": str(failure),
            "prepared": str(prepared),
            "model_response": str(model_response),
            "local_chain": str(local_chain),
            "local_review": str(local_review),
            "repair_plan": str(repair_plan),
            "repair_apply": str(repair_apply),
            "local_verify": str(local_verify),
            "loop_status": str(loop_status),
        },
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a no-API BIBER local repair-loop smoke test."
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
    if args.keep_temp:
        work_root = Path(tempfile.mkdtemp(prefix="biber-local-loop-smoke-"))
        cleanup = False
    else:
        work_root = Path(tempfile.mkdtemp(prefix="biber-local-loop-smoke-"))
        cleanup = True

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
        if cleanup:
            shutil.rmtree(work_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
