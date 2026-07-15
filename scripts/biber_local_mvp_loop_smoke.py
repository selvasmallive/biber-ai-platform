#!/usr/bin/env python3
"""Run a no-API BIBER local MVP-loop smoke test.

This smoke creates a temporary target repository, runs
scripts/biber_agent_client.py mvp-loop against it with --local-target-root, and
verifies that the resulting artifact exposes workspace edit review metadata in
agent_report.edit. It is CPU-only and does not resolve BIBER/OpenAI credentials.
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
        check=True,
        env=env,
        text=True,
    )
    parsed = json.loads(completed.stdout)
    if not isinstance(parsed, dict):
        raise RuntimeError("biber_agent_client.py mvp-loop did not return a JSON object")
    return parsed


def create_target_repo(target_root: Path) -> None:
    (target_root / "app").mkdir(parents=True)
    (target_root / "src").mkdir(parents=True)
    (target_root / "docs").mkdir(parents=True)
    (target_root / "app" / "__init__.py").write_text("", encoding="utf-8")
    (target_root / "src" / "app.py").write_text(
        "def answer():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    (target_root / "README.md").write_text("# Fixture repo\n", encoding="utf-8")


def run_smoke(work_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    artifact_dir = work_root / "artifacts"
    target_root = work_root / "target-repo"
    artifact_dir.mkdir(parents=True)
    create_target_repo(target_root)

    output_path = artifact_dir / "local-mvp-loop.json"
    edit_one = json.dumps(
        {
            "path": "src/app.py",
            "old_text": "return 1",
            "new_text": "return 2",
            "expected_replacements": 1,
        },
        sort_keys=True,
    )
    edit_two = json.dumps(
        {
            "path": "docs/notes.md",
            "new_text": "Local MVP loop smoke note.\n",
            "create_if_missing": True,
        },
        sort_keys=True,
    )
    result = run_client(
        repo_root,
        artifact_dir,
        "mvp-loop",
        "--instruction",
        "Apply a tiny local fixture change and verify the edit review report.",
        "--local-target-root",
        str(target_root),
        "--changed-path",
        "src/app.py",
        "--edit-json",
        edit_one,
        "--edit-json",
        edit_two,
        "--apply-edits",
        "--max-edit-files",
        "4",
        "--test-id",
        "python-compileall-api",
        "--output",
        str(output_path),
    )
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    if saved != result:
        raise RuntimeError("mvp-loop output artifact did not match stdout JSON")

    agent_report = result.get("agent_report")
    if not isinstance(agent_report, dict):
        raise RuntimeError("mvp-loop did not include agent_report")
    edit_report = agent_report.get("edit")
    if not isinstance(edit_report, dict):
        raise RuntimeError("agent_report did not include edit metadata")
    final_source = (target_root / "src" / "app.py").read_text(encoding="utf-8")
    created_note = target_root / "docs" / "notes.md"

    summary = {
        "source": "biber_local_mvp_loop_smoke",
        "ok": (
            result.get("ok") is True
            and result.get("test_ok") is True
            and edit_report.get("review_status") == "ready_for_hash_guarded_apply"
            and edit_report.get("ready_for_apply") is True
            and edit_report.get("planned_count") == 2
            and edit_report.get("applied_count") == 2
            and edit_report.get("changed_count") == 2
            and "creates_new_file:docs/notes.md"
            in [str(item) for item in edit_report.get("warnings", [])]
            and "return 2" in final_source
            and created_note.exists()
        ),
        "external_network_required": False,
        "gpu_required": False,
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "artifact": str(output_path),
        "target_root": str(target_root),
        "agent_report_status": agent_report.get("status"),
        "edit_review_status": edit_report.get("review_status"),
        "edit_ready_for_apply": edit_report.get("ready_for_apply"),
        "edit_planned_count": edit_report.get("planned_count"),
        "edit_applied_count": edit_report.get("applied_count"),
        "edit_changed_count": edit_report.get("changed_count"),
        "edit_warnings": edit_report.get("warnings", []),
        "test_ok": result.get("test_ok"),
    }
    if not summary["ok"]:
        raise RuntimeError(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a no-API BIBER local MVP-loop smoke test."
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
    work_root = Path(tempfile.mkdtemp(prefix="biber-local-mvp-loop-smoke-"))
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
