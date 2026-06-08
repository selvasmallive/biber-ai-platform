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
ROADMAP_DOC = ROOT / "docs" / "XRIQ_PRODUCTION_ROADMAP.md"
COPILOT_DOC = ROOT / ".github" / "copilot-instructions.md"

ROADMAP_MARKERS = [
    "# XRIQ Production Roadmap",
    "Azure, AWS, or Google Cloud Platform",
    "Cloud Provider Strategy",
    "Reference Production Architecture",
    "Environment Model",
    "Infrastructure-As-Code Policy",
    "Terraform is the default infrastructure-as-code tool",
    "Secrets And Key Management",
    "Observability And Operations",
    "Do not create, modify, or destroy cloud resources without explicit human approval",
    "AKS",
    "EKS",
    "GKE",
    "Phase 2: Hardened Private/Staging Devnet",
    "Phase 3: Public Testnet",
    "Phase 4: Security, Legal, And Economic Readiness",
    "Phase 5: Production Candidate",
    "Phase 6: Public Mainnet And Ecosystem",
    "docs/XRIQ_LEGAL_RISK_REDUCTION.md",
]

COPILOT_MARKERS = [
    "# Copilot Instructions For BIBER/XRIQ",
    "docs/XRIQ_PRODUCTION_ROADMAP.md",
    "Azure, AWS, GCP",
    "Do not create, modify, or destroy Azure, AWS, GCP",
    "Cloud Production Rules",
    "Terraform is the default IaC choice",
    "managed secrets storage and KMS/HSM-backed key protection",
    "Credential changes must be rare, deliberate, and documented",
    "cloud provider/environment affected, or `none`",
]

REFERENCE_MARKERS = {
    "README.md": [
        "docs/XRIQ_PRODUCTION_ROADMAP.md",
        ".github/copilot-instructions.md",
    ],
    "xriq/README.md": [
        "../docs/XRIQ_PRODUCTION_ROADMAP.md",
        "../.github/copilot-instructions.md",
    ],
    "docs/CODEX_HANDOFF.md": [
        ".github/copilot-instructions.md",
        "docs/XRIQ_PRODUCTION_ROADMAP.md",
    ],
}


class RoadmapCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate XRIQ production roadmap and Copilot cloud handoff markers."
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
    return TARGET_DIR / f"xriq-production-roadmap-check-{timestamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RoadmapCheckError(f"required file is missing: {path}") from error


def require_markers(text: str, markers: list[str], context: str) -> None:
    normalized = " ".join(text.split())
    missing = [
        marker
        for marker in markers
        if marker not in text and " ".join(marker.split()) not in normalized
    ]
    if missing:
        raise RoadmapCheckError(f"{context}: missing markers {missing}")


def verify_references() -> dict[str, list[str]]:
    checked: dict[str, list[str]] = {}
    for relative_path, markers in REFERENCE_MARKERS.items():
        text = read_text(ROOT / relative_path)
        require_markers(text, markers, relative_path)
        checked[relative_path] = markers
    return checked


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    roadmap_text = read_text(ROADMAP_DOC)
    copilot_text = read_text(COPILOT_DOC)
    require_markers(roadmap_text, ROADMAP_MARKERS, str(ROADMAP_DOC))
    require_markers(copilot_text, COPILOT_MARKERS, str(COPILOT_DOC))
    return {
        "ok": "xriq-production-roadmap-check",
        "completed_at": datetime.now(UTC).isoformat(),
        "roadmap_doc": str(ROADMAP_DOC.relative_to(ROOT)),
        "copilot_doc": str(COPILOT_DOC.relative_to(ROOT)),
        "markers_checked": {
            "roadmap": len(ROADMAP_MARKERS),
            "copilot": len(COPILOT_MARKERS),
        },
        "doc_references": verify_references(),
        "cloud_providers_supported_by_plan": ["azure", "aws", "gcp"],
        "guardrails": [
            "no cloud resources without explicit human approval",
            "provider decision required before provider-specific IaC",
            "secrets stay out of git",
            "custody and public financial claims require separate review",
            "current Codex scope remains XRIQ private-devnet prototype",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(args)
        artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
        summary["artifact_dir"] = str(artifact_dir)
        write_json(artifact_dir / "summary.json", summary)
    except RoadmapCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
