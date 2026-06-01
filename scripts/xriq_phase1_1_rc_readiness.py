from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_ROOT = ROOT / "xriq" / "target"
READINESS_DOC = ROOT / "docs" / "XRIQ_PHASE1_1_RC_READINESS.md"

REQUIRED_ROUTES = [
    "/api/v1/health",
    "/api/v1/network",
    "/api/v1/explorer/overview",
    "/api/v1/blocks?limit=5",
    "/api/v1/blocks/1",
    "/api/v1/transactions?limit=5",
    "/api/v1/transactions/{tx_hash}",
    "/api/v1/accounts?limit=5",
    "/api/v1/accounts/{address}",
    "/api/v1/accounts/{address}/transactions?limit=5",
    "/api/v1/mempool?limit=5",
    "/api/v1/wallet/status",
    "/api/v1/wallet/accounts?limit=5",
    "/api/v1/wallet/accounts/{address}/balance",
    "/api/v1/wallet/accounts/{address}/history?limit=5",
    "/api/v1/wallet/transactions/{tx_hash}/status",
    "/api/v1/wallet/transfers/draft-preview?...",
    "/api/v1/admin/node/status",
    "/api/v1/admin/indexer/status",
    "/api/v1/admin/audit-events?limit=5",
    "/api/v1/snapshots",
    "/api/v1/snapshots/current-indexed-chain",
    "/api/v1/iso20022/payment-initiation/preview?tx_hash={tx_hash}",
    "/api/v1/iso20022/transactions/{tx_hash}/status",
    "/api/v1/iso20022/accounts/{address}/statement?from=...&to=...",
    "/api/v1/admin/postgres/read-model-status",
]

REQUIRED_ARTIFACT_KEYS = [
    "postgres_docker_live",
    "postgres_api_read_model_status",
    "postgres_server_read_model_status",
    "postgres_api_explorer_overview",
    "postgres_server_explorer_overview",
    "postgres_api_wallet_draft_preview",
    "postgres_server_wallet_draft_preview",
    "postgres_api_iso_transaction_status",
    "postgres_server_iso_transaction_status",
    "postgres_api_iso_payment_initiation",
    "postgres_server_iso_payment_initiation",
    "postgres_api_iso_account_statement",
    "postgres_server_iso_account_statement",
    "postgres_admin_ui_read_model_status",
]

REQUIRED_COMPLETED_STEPS = [
    "phase1.1 contract check",
    "explorer UI static guardrail",
    "indexer replay and postgres dry-run",
    "postgres docker live smoke",
    "postgres-backed api iso20022 account statement",
    "postgres-backed server iso20022 account statement",
    "postgres-backed admin UI read-model status",
    "product API route smoke",
    "wallet draft failure smoke",
]

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "docs/XRIQ_PHASE1_1_RC_READINESS.md",
        "docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md",
        "scripts/xriq_phase1_1_rc_readiness.py --latest-summary",
    ],
    "xriq/README.md": [
        "../docs/XRIQ_PHASE1_1_RC_READINESS.md",
        "../docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md",
        "scripts/xriq_phase1_1_rc_readiness.py --latest-summary",
    ],
    "docs/CODEX_HANDOFF.md": [
        "docs/XRIQ_PHASE1_1_RC_READINESS.md",
        "docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md",
        "scripts/xriq_phase1_1_rc_readiness.py --latest-summary",
        "Phase 1.1 estimated completion: about `95%`",
        "phase1-1-xriq-local-e2e-rc1",
    ],
    "docs/XRIQ_PHASE1_1_END_TO_END_PLAN.md": [
        "docs/XRIQ_PHASE1_1_RC_READINESS.md",
        "docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md",
        "route-parity matrix",
    ],
    "docs/XRIQ_PHASE1_1_CONTRACTS.md": [
        "docs/XRIQ_PHASE1_1_RC_READINESS.md",
        "docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md",
        "route-parity matrix",
    ],
    "docs/XRIQ_PHASE1_1_RC_CANDIDATE_REPORT.md": [
        "phase1-1-xriq-local-e2e-rc1",
        "I explicitly approve creating and pushing the Phase 1.1 RC tag phase1-1-xriq-local-e2e-rc1.",
        "Do not tag from a generic continue request.",
        "xriq-phase1-1-local-e2e-smoke-20260531T223438Z",
        "not_certified: true",
        "No RC tag has been created by this report.",
    ],
}


class ReadinessError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check local/private XRIQ Phase 1.1 RC readiness guardrails."
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=None,
        help="Path to a Phase 1.1 local e2e smoke summary.json.",
    )
    parser.add_argument(
        "--latest-summary",
        action="store_true",
        help="Use the latest xriq-phase1-1-local-e2e-smoke summary under xriq/target.",
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
    return parser.parse_args(argv)


def read_text(relative_path: str) -> str:
    path = ROOT / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise ReadinessError(f"required document is missing: {relative_path}") from error


def latest_summary_path() -> Path:
    candidates = list(SUMMARY_ROOT.glob("xriq-phase1-1-local-e2e-smoke-*/summary.json"))
    if not candidates:
        raise ReadinessError(
            "no Phase 1.1 smoke summary found under xriq/target; run "
            "python scripts/xriq_phase1_1_local_e2e_smoke.py --postgres-docker-live first"
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


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ReadinessError(
            f"git {' '.join(args)} failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def verify_readiness_doc() -> dict[str, Any]:
    text = READINESS_DOC.read_text(encoding="utf-8")
    required_sections = [
        "# XRIQ Phase 1.1 RC Readiness Checklist",
        "## Scope",
        "## Required Validation Before RC Tag Proposal",
        "## RC Go/No-Go Checklist",
        "## Route-Parity Matrix",
        "## Deferred Until After RC Readiness Review",
    ]
    missing_sections = [section for section in required_sections if section not in text]
    if missing_sections:
        raise ReadinessError(f"readiness doc missing sections: {missing_sections}")

    missing_routes = [route for route in REQUIRED_ROUTES if route not in text]
    if missing_routes:
        raise ReadinessError(f"readiness doc missing route matrix entries: {missing_routes}")

    required_guardrails = [
        "Do not create, move, or push a Phase 1.1 RC tag",
        "mutating wallet submit/send APIs",
        "block-production controls",
        "snapshot export/import mutation",
        "smart-contract VM",
        "public mainnet",
        "not_certified: true",
    ]
    missing_guardrails = [item for item in required_guardrails if item not in text]
    if missing_guardrails:
        raise ReadinessError(f"readiness doc missing guardrails: {missing_guardrails}")

    return {"routes": len(REQUIRED_ROUTES), "guardrails": len(required_guardrails)}


def verify_doc_references() -> list[str]:
    checked: list[str] = []
    for relative_path, required_texts in REQUIRED_DOC_REFERENCES.items():
        text = read_text(relative_path)
        missing = [required for required in required_texts if required not in text]
        if missing:
            raise ReadinessError(f"{relative_path} missing references: {missing}")
        checked.append(relative_path)
    return checked


def verify_summary(summary_path: Path) -> dict[str, Any]:
    payload = load_json_object(summary_path)
    if payload.get("ok") != "xriq-phase1-1-local-e2e-smoke":
        raise ReadinessError(
            f"summary ok marker is not xriq-phase1-1-local-e2e-smoke: {payload.get('ok')!r}"
        )
    if payload.get("skipped") != []:
        raise ReadinessError(f"summary has skipped validation steps: {payload.get('skipped')!r}")

    completed = payload.get("completed")
    if not isinstance(completed, list):
        raise ReadinessError("summary completed field must be a list")
    missing_steps = [step for step in REQUIRED_COMPLETED_STEPS if step not in completed]
    if missing_steps:
        raise ReadinessError(f"summary is missing completed steps: {missing_steps}")

    artifacts = payload.get("indexer_artifacts")
    if not isinstance(artifacts, dict):
        raise ReadinessError("summary indexer_artifacts field must be an object")
    missing_artifacts = [
        key for key in REQUIRED_ARTIFACT_KEYS if not isinstance(artifacts.get(key), str)
    ]
    if missing_artifacts:
        raise ReadinessError(f"summary is missing artifact paths: {missing_artifacts}")
    for key in REQUIRED_ARTIFACT_KEYS:
        existing_path(artifacts[key])

    routes_checked = payload.get("routes_checked")
    if not isinstance(routes_checked, list):
        raise ReadinessError("summary routes_checked field must be a list")
    required_route_fragments = [
        "/api/v1/iso20022/payment-initiation/preview?tx_hash=",
        "/api/v1/iso20022/transactions/",
        "/api/v1/iso20022/accounts/",
    ]
    for fragment in required_route_fragments:
        if not any(isinstance(route, str) and fragment in route for route in routes_checked):
            raise ReadinessError(f"summary routes_checked missing fragment: {fragment}")

    return {
        "summary": str(summary_path),
        "completed_steps": len(completed),
        "artifact_paths": len(REQUIRED_ARTIFACT_KEYS),
    }


def verify_git(require_clean: bool, require_origin_main: bool) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if require_clean:
        status = run_git(["status", "--short"])
        if status:
            raise ReadinessError(f"git working tree is not clean:\n{status}")
        result["clean_git"] = True
    if require_origin_main:
        head = run_git(["rev-parse", "HEAD"])
        origin = run_git(["rev-parse", "origin/main"])
        if head != origin:
            raise ReadinessError("local HEAD does not match origin/main")
        result["origin_main_matches_head"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report: dict[str, Any] = {
            "ok": "xriq-phase1-1-rc-readiness",
            "readiness_doc": verify_readiness_doc(),
            "doc_references": verify_doc_references(),
        }
        if args.latest_summary and args.summary is not None:
            raise ReadinessError("use either --summary or --latest-summary, not both")
        if args.latest_summary:
            report["summary"] = verify_summary(latest_summary_path())
        elif args.summary is not None:
            report["summary"] = verify_summary(args.summary)
        report["git"] = verify_git(args.require_clean_git, args.require_origin_main)
    except ReadinessError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
