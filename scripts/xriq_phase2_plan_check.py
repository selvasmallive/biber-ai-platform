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
PLAN_DOC = ROOT / "docs" / "XRIQ_PHASE2_STAGING_DEVNET_PLAN.md"
PHASE1_4_TAG = "phase1-4-xriq-local-signed-submit-rc1"
PHASE1_4_TAG_COMMIT = "45be474"

REQUIRED_PLAN_MARKERS = [
    "# XRIQ Phase 2 Hardened Private/Staging Devnet Plan",
    "Status: active Phase 2 planning checkpoint, no production resources created.",
    "docs/XRIQ_PRODUCTION_ROADMAP.md",
    "docs/XRIQ_PRIVATE_DEVNET_WRAPUP.md",
    "docs/XRIQ_LEGAL_RISK_REDUCTION.md",
    PHASE1_4_TAG,
    "commit `45be474`",
    "## Goal",
    "## Phase 2 Acceptance Criteria",
    "## Production-Hardening Gaps From The Private-Devnet Prototype",
    "## Environment Boundaries",
    "## Required Operational Design Decisions",
    "## Hard Scope Boundaries",
    "## Recommended Phase 2 PR Sequence",
    "## Cheap Verification",
    "Restart and replay recovery tests pass",
    "expiry, and persistence are hardened",
    "no provider is chosen here",
    "scripts/xriq_phase2_plan_check.py",
]

REQUIRED_ENVIRONMENT_MARKERS = [
    "`local`",
    "`staging-devnet`",
    "`public-testnet`",
    "`production-candidate`",
    "`mainnet`",
    "hard isolation between environments",
]

REQUIRED_BOUNDARY_MARKERS = [
    "public mainnet or public testnet behavior",
    "DEX trading",
    "bridge",
    "custody",
    "privacy protocol",
    "smart-contract VM",
    "browser-held private keys",
    "seed phrases",
    "create, modify, or destroy Azure, AWS, GCP",
    "terraform apply",
    "commit secrets or rotate credentials",
    "legal, compliance, exchange, or production readiness",
    "push any tag from a generic continue",
]

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "docs/XRIQ_PHASE2_STAGING_DEVNET_PLAN.md",
        "scripts/xriq_phase2_plan_check.py",
    ],
    "xriq/README.md": [
        "../docs/XRIQ_PHASE2_STAGING_DEVNET_PLAN.md",
        "scripts/xriq_phase2_plan_check.py",
    ],
    "docs/CODEX_HANDOFF.md": [
        "docs/XRIQ_PHASE2_STAGING_DEVNET_PLAN.md",
        "scripts/xriq_phase2_plan_check.py",
        "Phase 2",
    ],
}


class PlanCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the XRIQ Phase 2 staging-devnet plan guardrails."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for plan-check output. Defaults under xriq/target/.",
    )
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase2-plan-check-{timestamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PlanCheckError(f"required file is missing: {path}") from error


def require_markers(text: str, markers: list[str], context: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise PlanCheckError(f"{context}: missing markers {missing}")


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PlanCheckError(
            f"git {' '.join(args)} failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def verify_phase1_4_tag() -> dict[str, Any]:
    tag_commit = run_git(["rev-list", "-n", "1", PHASE1_4_TAG])
    if not tag_commit.startswith(PHASE1_4_TAG_COMMIT):
        raise PlanCheckError(
            f"{PHASE1_4_TAG} points to {tag_commit}, expected {PHASE1_4_TAG_COMMIT}"
        )
    return {
        "tag": PHASE1_4_TAG,
        "expected_commit_prefix": PHASE1_4_TAG_COMMIT,
        "actual_commit": tag_commit,
    }


def verify_doc_references() -> dict[str, list[str]]:
    checked: dict[str, list[str]] = {}
    for relative_path, markers in REQUIRED_DOC_REFERENCES.items():
        text = read_text(ROOT / relative_path)
        require_markers(text, markers, relative_path)
        checked[relative_path] = markers
    return checked


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    plan_text = read_text(PLAN_DOC)
    require_markers(plan_text, REQUIRED_PLAN_MARKERS, str(PLAN_DOC))
    require_markers(plan_text, REQUIRED_ENVIRONMENT_MARKERS, f"{PLAN_DOC} environments")
    require_markers(plan_text, REQUIRED_BOUNDARY_MARKERS, f"{PLAN_DOC} boundaries")
    return {
        "ok": "xriq-phase2-plan-check",
        "completed_at": datetime.now(UTC).isoformat(),
        "plan_doc": str(PLAN_DOC.relative_to(ROOT)),
        "phase1_4_tag": verify_phase1_4_tag(),
        "markers_checked": {
            "plan": len(REQUIRED_PLAN_MARKERS),
            "environments": len(REQUIRED_ENVIRONMENT_MARKERS),
            "boundaries": len(REQUIRED_BOUNDARY_MARKERS),
        },
        "doc_references": verify_doc_references(),
        "phase": "phase-2-hardened-private-staging-devnet",
        "cloud_provider_selected": False,
        "next_allowed_without_explicit_approval": [
            "docs updates",
            "Phase 2 acceptance-criteria refinement",
            "provider-neutral operational design drafting",
            "local/private hardening planning and fixtures",
            "guard/checker expansion without cloud or tag actions",
        ],
        "prohibited_without_explicit_approval": [
            "public mainnet or public testnet behavior",
            "DEX, bridge, custody, privacy, smart-contract, or asset issuance scope",
            "cloud resource creation, modification, or destruction",
            "provider-specific IaC before a documented provider decision",
            "secrets commit or credential rotation",
            "tag creation or tag maintenance",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(args)
        artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
        summary["artifact_dir"] = str(artifact_dir)
        write_json(artifact_dir / "summary.json", summary)
    except PlanCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
