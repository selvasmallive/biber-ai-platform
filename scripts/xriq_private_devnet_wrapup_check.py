#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "xriq" / "target"
WRAPUP_DOC = ROOT / "docs" / "XRIQ_PRIVATE_DEVNET_WRAPUP.md"

REQUIRED_TAGS = {
    "phase1-xriq-private-devnet-rc1": "688bf91",
    "phase1-1-xriq-local-e2e-rc1": "6a38a51a",
    "phase1-2-xriq-local-private-hardening-rc1": "b3a2fe4",
    "phase1-3-xriq-local-private-behavior-rc1": "345d353",
    "phase1-4-xriq-local-signed-submit-rc1": "45be474",
}

WRAPUP_MARKERS = [
    "# XRIQ Private-Devnet Wrap-Up",
    "Status: Codex private-devnet prototype wrap-up checkpoint.",
    "Completion estimate for this scope: `100%`.",
    "phase1-xriq-private-devnet-rc1",
    "phase1-1-xriq-local-e2e-rc1",
    "phase1-2-xriq-local-private-hardening-rc1",
    "phase1-3-xriq-local-private-behavior-rc1",
    "phase1-4-xriq-local-signed-submit-rc1",
    "Do not move, delete, recreate, or repush these tags",
    "python scripts/xriq_private_devnet_wrapup_check.py",
    "docs/XRIQ_PRODUCTION_ROADMAP.md",
    ".github/copilot-instructions.md",
    "docs/XRIQ_LEGAL_RISK_REDUCTION.md",
    "Production work remains Phase 2 through Phase 6",
    "future Codex sessions should avoid expanding scope",
]

REFERENCE_MARKERS = {
    "README.md": [
        "docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md",
        "scripts/xriq_private_devnet_wrapup_check.py",
        "100%",
    ],
    "xriq/README.md": [
        "../docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md",
        "scripts/xriq_private_devnet_wrapup_check.py",
        "100%",
    ],
    "docs/CODEX_HANDOFF.md": [
        "docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md",
        "scripts/xriq_private_devnet_wrapup_check.py",
        "100%",
    ],
    "docs/XRIQ_PRODUCTION_ROADMAP.md": [
        "docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md",
        "private-devnet prototype wrap-up",
    ],
    ".github/copilot-instructions.md": [
        "docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md",
    ],
}


class WrapupCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate XRIQ private-devnet wrap-up handoff markers and tags."
    )
    parser.add_argument(
        "--require-clean-git",
        action="store_true",
        help="Fail unless git status --short is clean.",
    )
    parser.add_argument(
        "--require-origin-main",
        action="store_true",
        help="Fail unless local HEAD matches origin/main.",
    )
    parser.add_argument(
        "--require-tags-present",
        action="store_true",
        help="Fail unless all local private-devnet RC tags exist at expected commits.",
    )
    parser.add_argument(
        "--require-origin-tags",
        action="store_true",
        help="Fail unless all private-devnet RC tags are visible on origin.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for check output. Defaults under xriq/target/.",
    )
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-private-devnet-wrapup-check-{timestamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise WrapupCheckError(f"required file is missing: {path}") from error


def require_markers(text: str, markers: list[str], context: str) -> None:
    normalized = " ".join(text.split())
    missing = [
        marker
        for marker in markers
        if marker not in text and " ".join(marker.split()) not in normalized
    ]
    if missing:
        raise WrapupCheckError(f"{context}: missing markers {missing}")


def run_git(args: list[str], *, required: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 and required:
        raise WrapupCheckError(
            f"git {' '.join(args)} failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return completed


def verify_references() -> dict[str, list[str]]:
    checked: dict[str, list[str]] = {}
    for relative_path, markers in REFERENCE_MARKERS.items():
        text = read_text(ROOT / relative_path)
        require_markers(text, markers, relative_path)
        checked[relative_path] = markers
    return checked


def local_tag_commit(tag: str) -> str | None:
    result = run_git(["rev-list", "-n", "1", tag], required=False)
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def verify_local_tags(*, required: bool) -> dict[str, dict[str, Any]]:
    checked: dict[str, dict[str, Any]] = {}
    for tag, expected_prefix in REQUIRED_TAGS.items():
        commit = local_tag_commit(tag)
        if commit is None:
            if required:
                raise WrapupCheckError(f"local tag is missing: {tag}")
            checked[tag] = {"present": False, "expected_prefix": expected_prefix}
            continue
        if not commit.startswith(expected_prefix):
            raise WrapupCheckError(
                f"{tag} points to {commit}, expected prefix {expected_prefix}"
            )
        checked[tag] = {
            "present": True,
            "expected_prefix": expected_prefix,
            "actual_commit": commit,
        }
    return checked


def verify_origin_tags(*, required: bool) -> dict[str, dict[str, Any]]:
    checked: dict[str, dict[str, Any]] = {}
    for tag, expected_prefix in REQUIRED_TAGS.items():
        deref_result = run_git(
            ["ls-remote", "--tags", "origin", f"{tag}^{{}}"],
            required=False,
        )
        result = deref_result
        if deref_result.returncode != 0 or not deref_result.stdout.strip():
            result = run_git(["ls-remote", "--tags", "origin", tag], required=required)
        if result.returncode != 0:
            checked[tag] = {"checked": False, "expected_prefix": expected_prefix}
            continue
        output = result.stdout.strip()
        if not output:
            if required:
                raise WrapupCheckError(f"origin tag is missing: {tag}")
            checked[tag] = {"present": False, "expected_prefix": expected_prefix}
            continue
        commit = output.split()[0]
        if not commit.startswith(expected_prefix):
            raise WrapupCheckError(
                f"origin {tag} points to {commit}, expected prefix {expected_prefix}"
            )
        checked[tag] = {
            "present": True,
            "expected_prefix": expected_prefix,
            "actual_commit": commit,
        }
    return checked


def verify_git(args: argparse.Namespace) -> dict[str, Any]:
    status: dict[str, Any] = {}
    if args.require_clean_git:
        short_status = run_git(["status", "--short"]).stdout.strip()
        if short_status:
            raise WrapupCheckError(f"git worktree is not clean:\n{short_status}")
        status["clean"] = True
    if args.require_origin_main:
        head = run_git(["rev-parse", "HEAD"]).stdout.strip()
        origin_main = run_git(["rev-parse", "origin/main"]).stdout.strip()
        if head != origin_main:
            raise WrapupCheckError(f"HEAD {head} does not match origin/main {origin_main}")
        status["head_matches_origin_main"] = True
    return status


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    wrapup_text = read_text(WRAPUP_DOC)
    require_markers(wrapup_text, WRAPUP_MARKERS, str(WRAPUP_DOC.relative_to(ROOT)))
    return {
        "ok": "xriq-private-devnet-wrapup-check",
        "completed_at": datetime.now(UTC).isoformat(),
        "wrapup_doc": str(WRAPUP_DOC.relative_to(ROOT)),
        "completion_estimate": "100% for Codex private-devnet prototype scope",
        "local_tags": verify_local_tags(required=args.require_tags_present),
        "origin_tags": verify_origin_tags(required=args.require_origin_tags)
        if args.require_origin_tags
        else {},
        "doc_references": verify_references(),
        "git": verify_git(args),
        "scope_boundaries": [
            "non-production private-devnet only",
            "no public mainnet or public testnet",
            "no DEX, bridge, CEX listing, custody, smart-contract VM, or privacy protocol implementation",
            "no production cloud resources",
            "no tag maintenance without exact explicit approval",
        ],
        "next_decision_needed": [
            "move production hardening to GitHub Copilot",
            "define a narrow local/private Phase 1.5 gap if needed",
            "resume BIBER MVP/model work separately",
            "run a manual private-devnet demo",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(args)
        artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
        summary["artifact_dir"] = str(artifact_dir)
        write_json(artifact_dir / "summary.json", summary)
    except WrapupCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
