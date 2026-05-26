from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_ROOT = ROOT / "xriq" / "target"

REQUIRED_COMPLETED_STEPS = [
    "cargo fmt check",
    "python smoke syntax check",
    "cargo test workspace",
    "cargo clippy workspace",
    "transfer smoke",
    "transfer smoke artifact check",
    "http smoke",
    "http smoke artifact check",
]

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "scripts/xriq_phase1_local_check.py",
        "docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md",
    ],
    "xriq/README.md": [
        "scripts/xriq_phase1_local_check.py",
        "../docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md",
    ],
    "docs/XRIQ_PHASE1_PRIVATE_DEVNET_RC.md": [
        "artifact_checks",
        "docs/XRIQ_PHASE1_RC_REPORT.md",
        "phase1-xriq-private-devnet-rc1",
        "scripts/xriq_phase1_local_check.py",
    ],
    "docs/XRIQ_PHASE1_RC_REPORT.md": [
        "phase1-xriq-private-devnet-rc1",
        "xriq-phase1-local-check",
        "ready_for_rc_tag",
        "Do not create or push that tag from a general \"continue\" request.",
    ],
    "docs/CODEX_HANDOFF.md": [
        "Phase 1 goal: XRIQ private-devnet prototype only",
        "docs/XRIQ_PHASE1_RC_REPORT.md",
        "xriq-phase1-local-check",
    ],
}


class ReadinessError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether the latest local XRIQ Phase 1 validation summary is "
            "ready for an explicit user-approved RC tag decision."
        )
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Path to a xriq_phase1_local_check summary.json. Defaults to latest.",
    )
    parser.add_argument(
        "--require-clean-git",
        action="store_true",
        help="Fail unless git status --short is clean. Use after commit/push.",
    )
    return parser.parse_args(argv)


def latest_summary_path() -> Path:
    candidates = list(SUMMARY_ROOT.glob("xriq-phase1-local-check-*/summary.json"))
    if not candidates:
        raise ReadinessError(
            "no Phase 1 local-check summary found under xriq/target; "
            "run python scripts/xriq_phase1_local_check.py first"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ReadinessError(f"summary file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ReadinessError(f"summary file is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ReadinessError(f"summary file is not a JSON object: {path}")
    return payload


def existing_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise ReadinessError(f"listed artifact does not exist: {path}")
    return path


def verify_summary(summary_path: Path) -> dict[str, Any]:
    payload = load_json_object(summary_path)
    if payload.get("ok") != "xriq-phase1-local-check":
        raise ReadinessError(
            f"summary ok marker is not xriq-phase1-local-check: {payload.get('ok')!r}"
        )

    skipped = payload.get("skipped")
    if skipped != []:
        raise ReadinessError(f"summary has skipped validation steps: {skipped!r}")

    completed = payload.get("completed")
    if not isinstance(completed, list):
        raise ReadinessError("summary completed field must be a list")
    missing_steps = [
        step for step in REQUIRED_COMPLETED_STEPS if step not in completed
    ]
    if missing_steps:
        raise ReadinessError(f"summary is missing completed steps: {missing_steps}")

    artifact_checks = payload.get("artifact_checks")
    if not isinstance(artifact_checks, list) or not artifact_checks:
        raise ReadinessError("summary artifact_checks field must be a non-empty list")
    if len(artifact_checks) < 15:
        raise ReadinessError(
            f"summary has too few artifact checks: {len(artifact_checks)}"
        )

    checked_paths = []
    for item in artifact_checks:
        if not isinstance(item, str):
            raise ReadinessError(f"artifact_checks entry is not a string: {item!r}")
        checked_paths.append(str(existing_path(item)))

    return {
        "summary": str(summary_path),
        "completed_steps": len(completed),
        "artifact_checks": len(checked_paths),
    }


def verify_doc_references() -> list[str]:
    checked: list[str] = []
    for relative_path, required_texts in REQUIRED_DOC_REFERENCES.items():
        path = ROOT / relative_path
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ReadinessError(f"required document is missing: {relative_path}") from error
        missing = [needle for needle in required_texts if needle not in text]
        if missing:
            raise ReadinessError(
                f"{relative_path} is missing required references: {missing}"
            )
        checked.append(relative_path)
    return checked


def git_status_short() -> str:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ReadinessError(
            f"git status failed with exit code {result.returncode}: {result.stderr}"
        )
    return result.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary_path = (args.summary or latest_summary_path()).resolve()
    summary_result = verify_summary(summary_path)
    docs_checked = verify_doc_references()

    git_status = git_status_short()
    git_clean = git_status == ""
    if args.require_clean_git and not git_clean:
        raise ReadinessError(f"git working tree is not clean:\n{git_status}")

    report = {
        "ok": "xriq-phase1-rc-readiness",
        "ready_for_rc_tag": git_clean,
        "summary": summary_result["summary"],
        "completed_steps": summary_result["completed_steps"],
        "artifact_checks": summary_result["artifact_checks"],
        "docs_checked": docs_checked,
        "git_clean": git_clean,
    }
    if not git_clean:
        report["git_status"] = git_status

    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReadinessError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
