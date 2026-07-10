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
DECISION_DOC = ROOT / "docs" / "XRIQ_GCP_PROVIDER_DECISION.md"
INFRA_DIR = ROOT / "infra" / "gcp"

REQUIRED_DECISION_MARKERS = [
    "# XRIQ Cloud Provider Decision: Google Cloud Platform",
    "Status: provider decision recorded. No cloud resources created.",
    "Google Cloud Platform",
    "xriq@kani.network",
    "northamerica-northeast2",
    "USD 150",
    "80%",
    "staging-devnet",
    "Secret Manager",
    "Cloud SQL for PostgreSQL",
    "No resource creation, modification, or destruction from automation.",
    "infra/gcp/",
    "scripts/xriq_gcp_provider_decision_check.py",
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

# Modules define real Terraform resources (validated, not applied from
# automation). Each must declare at least one google resource.
RESOURCE_MODULE_FILES = [
    "modules/network/main.tf",
    "modules/security/main.tf",
    "modules/data/main.tf",
    "modules/compute/main.tf",
    "modules/observability/main.tf",
]

# Static-validation must stay offline and secret-free: no remote backend and no
# service-account key or private key material in-repo.
FORBIDDEN_INFRA_SUBSTRINGS = [
    "client_secret",
    "private_key_id",
    "-----BEGIN",
    'backend "gcs"',
    'backend "local"',
]

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "docs/XRIQ_GCP_PROVIDER_DECISION.md",
        "infra/gcp",
    ],
    "xriq/README.md": [
        "../docs/XRIQ_GCP_PROVIDER_DECISION.md",
        "infra/gcp",
    ],
    "docs/CODEX_HANDOFF.md": [
        "docs/XRIQ_GCP_PROVIDER_DECISION.md",
        "infra/gcp",
        "GCP",
    ],
}


class DecisionCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the XRIQ GCP provider decision and infra resources."
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
    return TARGET_DIR / f"xriq-gcp-provider-decision-check-{timestamp}"


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
            raise DecisionCheckError(f"infra/gcp: missing required file {relative}")
        checked.append(relative)
    for relative in RESOURCE_MODULE_FILES:
        text = read_text(INFRA_DIR / relative)
        if 'resource "google_' not in text:
            raise DecisionCheckError(
                f"infra/gcp module {relative} must declare at least one google resource"
            )
    return checked


def git_tracked_infra_paths() -> list[Path]:
    # Scan only git-tracked files so local operator artifacts (a real
    # terraform.tfvars, tfstate, or plan produced by running the apply runbook,
    # all gitignored) do not false-positive this guard.
    result = subprocess.run(
        ["git", "ls-files", "--", str(INFRA_DIR)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise DecisionCheckError(f"git ls-files failed: {result.stderr.strip()}")
    return [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def verify_no_secret_or_apply_material() -> None:
    tracked = git_tracked_infra_paths()
    tracked_rel = {path.relative_to(ROOT).as_posix() for path in tracked}
    if "infra/gcp/terraform.tfvars" in tracked_rel:
        raise DecisionCheckError("infra/gcp: terraform.tfvars must not be committed (use the .example)")
    for rel in tracked_rel:
        if rel.endswith(".tfstate") or ".tfstate." in rel:
            raise DecisionCheckError(f"infra/gcp: terraform state must not be committed: {rel}")
    for path in tracked:
        if path.suffix == ".tf" or path.name.endswith(".example"):
            try:
                text = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                continue
            for forbidden in FORBIDDEN_INFRA_SUBSTRINGS:
                if forbidden in text:
                    raise DecisionCheckError(
                        f"infra/gcp: forbidden content '{forbidden}' in {path.relative_to(ROOT)}"
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
        "ok": "xriq-gcp-provider-decision-check",
        "completed_at": datetime.now(UTC).isoformat(),
        "decision_doc": str(DECISION_DOC.relative_to(ROOT)),
        "infra_dir": str(INFRA_DIR.relative_to(ROOT)),
        "selected_provider": "gcp",
        "region": "northamerica-northeast2",
        "environment": "staging-devnet",
        "cloud_resources_created": False,
        "markers_checked": {
            "decision": len(REQUIRED_DECISION_MARKERS),
            "infra_files": len(infra_files),
            "resource_modules": len(RESOURCE_MODULE_FILES),
        },
        "infra_files": infra_files,
        "doc_references": verify_doc_references(),
        "guardrails": [
            "no cloud resources created, modified, or destroyed",
            "no gcloud auth, terraform apply, or cloud deletion from automation",
            "no secrets, project keys, or service-account keys in git",
            "no remote backend configured in-repo (static validation stays offline)",
            "module resources are validated only; apply is human-gated",
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
