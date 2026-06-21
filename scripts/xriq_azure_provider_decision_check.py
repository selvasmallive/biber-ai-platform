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
DECISION_DOC = ROOT / "docs" / "XRIQ_AZURE_PROVIDER_DECISION.md"
INFRA_DIR = ROOT / "infra" / "azure"

REQUIRED_DECISION_MARKERS = [
    "# XRIQ Cloud Provider Decision: Azure",
    "Status: provider decision recorded. No cloud resources created.",
    "Microsoft Azure",
    "selva@kani.network",
    "eastus",
    "USD 150",
    "80%",
    "staging-devnet",
    "Azure Key Vault",
    "Azure Database for PostgreSQL Flexible Server",
    "No resource creation, modification, or destruction from automation.",
    "infra/azure/",
    "scripts/xriq_azure_provider_decision_check.py",
    "docs/XRIQ_LEGAL_RISK_REDUCTION.md",
    "docs/XRIQ_PRODUCTION_ROADMAP.md",
    "terraform fmt -recursive -check",
]

REQUIRED_INFRA_FILES = [
    "versions.tf",
    "variables.tf",
    "main.tf",
    "outputs.tf",
    "README.md",
    "terraform.tfvars.example",
    "modules/network/main.tf",
    "modules/security/main.tf",
    "modules/data/main.tf",
    "modules/compute/main.tf",
    "modules/observability/main.tf",
]

# Modules must remain boundary-only (no resources) until a human implements and
# applies them deliberately.
BOUNDARY_MODULE_FILES = [
    "modules/network/main.tf",
    "modules/security/main.tf",
    "modules/data/main.tf",
    "modules/compute/main.tf",
    "modules/observability/main.tf",
]

# Static-validation must stay offline: no remote backend configured in-repo.
FORBIDDEN_INFRA_SUBSTRINGS = [
    "client_secret",
    "ARM_CLIENT_SECRET",
    "-----BEGIN",
    'backend "azurerm"',
    'backend "local"',
]

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "docs/XRIQ_AZURE_PROVIDER_DECISION.md",
        "infra/azure",
    ],
    "xriq/README.md": [
        "../docs/XRIQ_AZURE_PROVIDER_DECISION.md",
        "infra/azure",
    ],
    "docs/CODEX_HANDOFF.md": [
        "docs/XRIQ_AZURE_PROVIDER_DECISION.md",
        "infra/azure",
        "Azure",
    ],
}


class DecisionCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the XRIQ Azure provider decision and infra boundaries."
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
    return TARGET_DIR / f"xriq-azure-provider-decision-check-{timestamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise DecisionCheckError(f"required file is missing: {path}") from error


def require_markers(text: str, markers: list[str], context: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise DecisionCheckError(f"{context}: missing markers {missing}")


def verify_infra_layout() -> list[str]:
    checked: list[str] = []
    for relative in REQUIRED_INFRA_FILES:
        path = INFRA_DIR / relative
        if not path.is_file():
            raise DecisionCheckError(f"infra/azure: missing required file {relative}")
        checked.append(relative)
    for relative in BOUNDARY_MODULE_FILES:
        text = read_text(INFRA_DIR / relative)
        if "implemented = false" not in text:
            raise DecisionCheckError(
                f"infra/azure module {relative} must stay boundary-only (implemented = false)"
            )
    return checked


def verify_no_secret_or_apply_material() -> None:
    # A real terraform.tfvars (non-example) or state must not be committed.
    if (INFRA_DIR / "terraform.tfvars").exists():
        raise DecisionCheckError("infra/azure: terraform.tfvars must not be committed (use the .example)")
    for state in INFRA_DIR.rglob("*.tfstate"):
        raise DecisionCheckError(f"infra/azure: terraform state must not be committed: {state}")
    for source in list(INFRA_DIR.rglob("*.tf")) + list(INFRA_DIR.rglob("*.example")):
        text = source.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_INFRA_SUBSTRINGS:
            if forbidden in text:
                raise DecisionCheckError(
                    f"infra/azure: forbidden content '{forbidden}' in {source.relative_to(ROOT)}"
                )


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
    decision_text = read_text(DECISION_DOC)
    require_markers(decision_text, REQUIRED_DECISION_MARKERS, str(DECISION_DOC))
    infra_files = verify_infra_layout()
    verify_no_secret_or_apply_material()
    return {
        "ok": "xriq-azure-provider-decision-check",
        "completed_at": datetime.now(UTC).isoformat(),
        "decision_doc": str(DECISION_DOC.relative_to(ROOT)),
        "infra_dir": str(INFRA_DIR.relative_to(ROOT)),
        "selected_provider": "azure",
        "region": "eastus",
        "environment": "staging-devnet",
        "cloud_resources_created": False,
        "markers_checked": {
            "decision": len(REQUIRED_DECISION_MARKERS),
            "infra_files": len(infra_files),
            "boundary_modules": len(BOUNDARY_MODULE_FILES),
        },
        "infra_files": infra_files,
        "doc_references": verify_doc_references(),
        "guardrails": [
            "no cloud resources created, modified, or destroyed",
            "no az login, terraform apply, or cloud deletion from automation",
            "no secrets, subscription ids, or tenant ids in git",
            "no remote backend configured in-repo (static validation stays offline)",
            "modules remain boundary-only until human-implemented and applied",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(args)
        artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
        summary["artifact_dir"] = str(artifact_dir)
        write_json(artifact_dir / "summary.json", summary)
    except DecisionCheckError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
