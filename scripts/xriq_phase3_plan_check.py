#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "xriq" / "target"
PLAN_DOC = ROOT / "docs" / "XRIQ_PHASE3_PUBLIC_TESTNET_PLAN.md"

REQUIRED_PLAN_MARKERS = [
    "# XRIQ Phase 3 Public Testnet Plan",
    "Status: active Phase 3 planning checkpoint.",
    "docs/XRIQ_PRODUCTION_ROADMAP.md",
    "docs/XRIQ_PHASE3_DECISIONS.md",
    "docs/XRIQ_LEGAL_RISK_REDUCTION.md",
    "## Goal",
    "## Non-Negotiable Guardrails",
    "## Phase 3 Acceptance Criteria",
    "## Milestones",
    "## Hard Scope Boundaries",
    "## Security And Legal Gate",
    "## Recommended First Milestone",
    "Networked multi-node sync",
    "two independent nodes can sync",
    "no monetary value",
    "regulated-product review items",
    "roadmap Phase 4 review",
    "allowlist",
    "scripts/xriq_phase3_plan_check.py",
]

REQUIRED_BOUNDARY_MARKERS = [
    "operate a public mainnet",
    "DEX, liquidity pool, token listing, bridge",
    "custody, stablecoin, tokenomics",
    "investment, yield, price-support",
    "privacy/shielded transfers, mixers",
    "browser-held key material",
    "change the cloud provider",
    "create, move, or delete tags from a generic continue",
]

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "docs/XRIQ_PHASE3_PUBLIC_TESTNET_PLAN.md",
        "scripts/xriq_phase3_plan_check.py",
    ],
    "xriq/README.md": [
        "../docs/XRIQ_PHASE3_PUBLIC_TESTNET_PLAN.md",
        "scripts/xriq_phase3_plan_check.py",
    ],
    "docs/CODEX_HANDOFF.md": [
        "docs/XRIQ_PHASE3_PUBLIC_TESTNET_PLAN.md",
        "Phase 3",
    ],
}


class PlanCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the XRIQ Phase 3 public testnet plan guardrails."
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
    return TARGET_DIR / f"xriq-phase3-plan-check-{timestamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PlanCheckError(f"required file is missing: {path}") from error


def require_markers(text: str, markers: list[str], context: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise PlanCheckError(f"{context}: missing markers {missing}")


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
    require_markers(plan_text, REQUIRED_BOUNDARY_MARKERS, f"{PLAN_DOC} boundaries")
    return {
        "ok": "xriq-phase3-plan-check",
        "completed_at": datetime.now(UTC).isoformat(),
        "plan_doc": str(PLAN_DOC.relative_to(ROOT)),
        "phase": "phase-3-public-testnet",
        "public_network_operated": False,
        "markers_checked": {
            "plan": len(REQUIRED_PLAN_MARKERS),
            "boundaries": len(REQUIRED_BOUNDARY_MARKERS),
        },
        "doc_references": verify_doc_references(),
        "next_allowed_without_explicit_approval": [
            "docs updates and milestone planning",
            "networked multi-node sync design and prototypes on the private/staging path",
            "test-only faucet/abuse-control design",
            "guard/checker expansion without cloud or tag actions",
        ],
        "prohibited_without_explicit_approval": [
            "public mainnet or monetary-value testnet coins",
            "DEX, tokenomics, bridge, custody, stablecoin, or privacy protocol",
            "investment/yield/price/exchange-listing claims",
            "cloud provider change, terraform apply, or deploys from automation",
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
