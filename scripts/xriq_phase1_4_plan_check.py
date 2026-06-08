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
PLAN_DOC = ROOT / "docs" / "XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md"
PHASE1_3_TAG = "phase1-3-xriq-local-private-behavior-rc1"
PHASE1_3_TAG_COMMIT = "345d353"

REQUIRED_PLAN_MARKERS = [
    "# XRIQ Phase 1.4 Local Signing Plan",
    "Status: active local/private implementation checkpoint.",
    PHASE1_3_TAG,
    "deterministic local/private signing intent",
    "test-only signed transfer envelope",
    "xriq-wallet",
    "xriq-api",
    "explorer-ui",
    "Signed-transfer contract inventory.",
    "CLI-only test signing path.",
    "API signed-submit refusal/audit path.",
    "API signed-submit verifier.",
    "Local signed-send smoke.",
    "UI design review only.",
    "POST /api/v1/wallet/transfers/submit-signed",
    "signed_submit_disabled",
    "signed-submit-negative-cases.json",
    "malformed envelope fields",
    "duplicate pending transaction",
    "scripts/xriq_phase1_4_signed_submit_negative_smoke.py",
    "parse/verify-only",
    "wallet-transfer-signed-submit:local_request_id",
    "scripts/xriq_phase1_4_signed_submit_refusal_smoke.py",
    "Mutating signed-submit endpoints must remain disabled by default.",
    "Do not create, move, delete, recreate, or push any tag from a generic continue",
]

REQUIRED_BOUNDARY_MARKERS = [
    "No accepted signed-submit mutation, wallet submit UI,",
    "production private-key generation",
    "browser-held private keys",
    "hosted wallet custody",
    "public mainnet",
    "DEX trading",
    "smart-contract VM",
    "production GCP/Vast/server infrastructure",
    "ISO 20022 certification",
    "docs/XRIQ_LEGAL_RISK_REDUCTION.md",
]

REQUIRED_UI_RULE_MARKERS = [
    "generate private keys",
    "store private keys",
    "seed phrases or mnemonics",
    "localStorage",
    "sessionStorage",
    "IndexedDB",
    "cookies",
    "direct",
    "fetch(",
]

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "docs/XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md",
        "scripts/xriq_phase1_4_plan_check.py",
    ],
    "xriq/README.md": [
        "../docs/XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md",
        "scripts/xriq_phase1_4_plan_check.py",
    ],
    "docs/CODEX_HANDOFF.md": [
        "docs/XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md",
        "scripts/xriq_phase1_4_plan_check.py",
        "Phase 1.4",
        "local/private signed-transfer",
    ],
}


class PlanCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the XRIQ Phase 1.4 local signing plan guardrails."
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
    return TARGET_DIR / f"xriq-phase1-4-plan-check-{timestamp}"


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


def verify_phase1_3_tag() -> dict[str, Any]:
    tag_commit = run_git(["rev-list", "-n", "1", PHASE1_3_TAG])
    if not tag_commit.startswith(PHASE1_3_TAG_COMMIT):
        raise PlanCheckError(
            f"{PHASE1_3_TAG} points to {tag_commit}, expected {PHASE1_3_TAG_COMMIT}"
        )
    return {
        "tag": PHASE1_3_TAG,
        "expected_commit_prefix": PHASE1_3_TAG_COMMIT,
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
    require_markers(plan_text, REQUIRED_BOUNDARY_MARKERS, f"{PLAN_DOC} boundaries")
    require_markers(plan_text, REQUIRED_UI_RULE_MARKERS, f"{PLAN_DOC} UI rules")
    return {
        "ok": "xriq-phase1-4-plan-check",
        "completed_at": datetime.now(UTC).isoformat(),
        "plan_doc": str(PLAN_DOC.relative_to(ROOT)),
        "phase1_3_tag": verify_phase1_3_tag(),
        "markers_checked": {
            "plan": len(REQUIRED_PLAN_MARKERS),
            "boundaries": len(REQUIRED_BOUNDARY_MARKERS),
            "ui_rules": len(REQUIRED_UI_RULE_MARKERS),
        },
        "doc_references": verify_doc_references(),
        "next_allowed_without_explicit_implementation_approval": [
            "docs updates",
            "fixture design",
            "contract/checker expansion",
            "negative-case planning",
        ],
        "prohibited_without_explicit_approval": [
            "wallet submit UI mutation",
            "browser key generation or storage",
            "custody or hosted signing",
            "public network behavior",
            "DEX, bridge, smart-contract, or asset issuance scope",
            "production infrastructure",
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
