#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "xriq" / "target"
CANDIDATE_DOC = ROOT / "docs" / "XRIQ_PHASE1_4_RC_CANDIDATE_REPORT.md"
PROPOSED_TAG = "phase1-4-xriq-local-signed-submit-rc1"
PRE_REPORT_COMMIT = "50b8281"
APPROVAL_PHRASE = (
    "I explicitly approve creating and pushing the Phase 1.4 RC tag "
    "phase1-4-xriq-local-signed-submit-rc1."
)
DEFAULT_LIFECYCLE_SUMMARY = Path(
    "xriq/target/xriq-phase1-4-signed-submit-lifecycle-smoke-20260609T024220Z/summary.json"
)
DEFAULT_PLAN_SUMMARY = Path(
    "xriq/target/xriq-phase1-4-plan-check-20260609T030347Z/summary.json"
)
DEFAULT_SIGNED_ARTIFACT_SUMMARY = Path(
    "xriq/target/xriq-phase1-4-signed-artifact-check-20260609T024602Z/summary.json"
)
DEFAULT_CONTRACT_SUMMARY = Path(
    "xriq/target/xriq-phase1-4-contract-check-20260608T231501Z/summary.json"
)
DEFAULT_NEGATIVE_SUMMARY = Path(
    "xriq/target/xriq-phase1-4-signed-submit-negative-smoke-20260608T231551Z/summary.json"
)
DEFAULT_REFUSAL_SUMMARY = Path(
    "xriq/target/xriq-phase1-4-signed-submit-refusal-smoke-20260608T231601Z/summary.json"
)

EXPECTED_NEGATIVE_CASES = [
    "duplicate_pending_transaction",
    "expired_transaction",
    "invalid_test_signature",
    "malformed_envelope_missing_format_version",
    "malformed_envelope_missing_hashes",
    "stale_nonce",
    "transaction_hash_mismatch",
    "transaction_signing_hash_mismatch",
    "unsupported_signature_algorithm",
    "wrong_chain_id",
]

REQUIRED_CANDIDATE_MARKERS = [
    "# XRIQ Phase 1.4 RC Candidate Report",
    "Status: candidate report only. No Phase 1.4 RC tag has been created by this",
    PROPOSED_TAG,
    f"Pre-report implementation checkpoint reviewed for this candidate: `{PRE_REPORT_COMMIT}`.",
    APPROVAL_PHRASE,
    "Do not tag from a generic continue request.",
    "## Candidate Scope",
    "## Latest Validation Evidence",
    "## RC Go/No-Go Checklist",
    "## Pre-Tag Readiness Guard",
    "## Non-Production Boundaries",
    "## Candidate Decision",
    "xriq-phase1-4-signed-submit-lifecycle-smoke",
    "xriq-phase1-4-plan-check",
    "xriq-phase1-4-signed-artifact-check",
    "xriq-phase1-4-contract-check",
    "xriq-phase1-4-signed-submit-negative-smoke",
    "xriq-phase1-4-signed-submit-refusal-smoke",
    "--enable-local-wallet-submit-signed true",
    "--enable-local-block-production true",
    "No wallet submit UI mutation is included.",
    "No browser key generation",
    "no-generic-approval rule",
]

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "docs/XRIQ_PHASE1_4_RC_CANDIDATE_REPORT.md",
        "scripts/xriq_phase1_4_rc_readiness.py",
        PROPOSED_TAG,
        APPROVAL_PHRASE,
    ],
    "xriq/README.md": [
        "../docs/XRIQ_PHASE1_4_RC_CANDIDATE_REPORT.md",
        "scripts/xriq_phase1_4_rc_readiness.py",
        PROPOSED_TAG,
        APPROVAL_PHRASE,
    ],
    "docs/XRIQ_PHASE1_4_LOCAL_SIGNING_PLAN.md": [
        "Current RC candidate report checkpoint:",
        "docs/XRIQ_PHASE1_4_RC_CANDIDATE_REPORT.md",
        "scripts/xriq_phase1_4_rc_readiness.py",
        PROPOSED_TAG,
        APPROVAL_PHRASE,
    ],
    "docs/CODEX_HANDOFF.md": [
        "Latest native XRIQ Phase 1.4 RC candidate report checkpoint:",
        "docs/XRIQ_PHASE1_4_RC_CANDIDATE_REPORT.md",
        "scripts/xriq_phase1_4_rc_readiness.py",
        PROPOSED_TAG,
        APPROVAL_PHRASE,
    ],
}


class RcReadinessError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check local/private XRIQ Phase 1.4 RC candidate readiness guardrails."
    )
    parser.add_argument("--lifecycle-summary", type=Path, default=None)
    parser.add_argument("--plan-summary", type=Path, default=None)
    parser.add_argument("--signed-artifact-summary", type=Path, default=None)
    parser.add_argument("--contract-summary", type=Path, default=None)
    parser.add_argument("--negative-summary", type=Path, default=None)
    parser.add_argument("--refusal-summary", type=Path, default=None)
    parser.add_argument(
        "--require-clean-git",
        action="store_true",
        help="Fail unless git status --short is clean.",
    )
    parser.add_argument(
        "--require-origin-main",
        action="store_true",
        help="Fail unless local HEAD matches the current local origin/main ref.",
    )
    parser.add_argument(
        "--require-tag-absent",
        action="store_true",
        help=f"Fail if local tag {PROPOSED_TAG} already exists.",
    )
    parser.add_argument(
        "--write-summary",
        action="store_true",
        help="Write the readiness report to summary.json under xriq/target.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for --write-summary output. Defaults under xriq/target/.",
    )
    return parser.parse_args(argv)


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_artifact_dir() -> Path:
    return TARGET_DIR / f"xriq-phase1-4-rc-readiness-{utc_timestamp()}"


def load_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RcReadinessError(f"{description} does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise RcReadinessError(f"{description} is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise RcReadinessError(f"{description} must be a JSON object: {path}")
    return payload


def read_text(relative_path: str) -> str:
    path = ROOT / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RcReadinessError(f"required document is missing: {relative_path}") from error


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise RcReadinessError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_bool(payload: dict[str, Any], key: str, expected: bool, context: str) -> None:
    actual = payload.get(key)
    if actual is not expected:
        raise RcReadinessError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_hash(value: Any, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RcReadinessError(f"{context}: expected 64-character lowercase hash, got {value!r}")
    return value


def require_list_contains(values: Any, required: list[str], context: str) -> None:
    if not isinstance(values, list):
        raise RcReadinessError(f"{context}: expected list")
    missing = [item for item in required if item not in values]
    if missing:
        raise RcReadinessError(f"{context}: missing items {missing}")


def require_marker(text: str, marker: str, context: str) -> None:
    if marker not in text:
        raise RcReadinessError(f"{context}: missing marker {marker!r}")


def require_markers(text: str, markers: list[str], context: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise RcReadinessError(f"{context}: missing markers {missing}")


def resolve_summary_path(
    path: Path | None,
    default_path: Path,
    label: str,
    command_hint: str,
) -> Path:
    selected = path or default_path
    if not selected.is_absolute():
        selected = ROOT / selected
    if not selected.exists():
        raise RcReadinessError(f"{label} does not exist: {selected}; run {command_hint} first")
    return selected


def path_reference_markers(path: Path) -> list[str]:
    absolute_path = path if path.is_absolute() else ROOT / path
    markers = [str(absolute_path)]
    try:
        relative_path = absolute_path.resolve().relative_to(ROOT)
    except ValueError:
        return markers
    markers.extend([str(relative_path), relative_path.as_posix()])
    return list(dict.fromkeys(markers))


def verify_candidate_path_reference(text: str, label: str, path: Path) -> str:
    markers = path_reference_markers(path)
    if not any(marker in text for marker in markers):
        raise RcReadinessError(
            f"candidate report does not reference selected {label}: expected one of {markers}"
        )
    return markers[-1]


def verify_candidate_report(selected_paths: dict[str, Path]) -> dict[str, Any]:
    text = CANDIDATE_DOC.read_text(encoding="utf-8")
    require_markers(text, REQUIRED_CANDIDATE_MARKERS, str(CANDIDATE_DOC.relative_to(ROOT)))
    referenced = {
        label: verify_candidate_path_reference(text, label, path)
        for label, path in selected_paths.items()
    }
    return {
        "path": str(CANDIDATE_DOC.relative_to(ROOT)),
        "markers_checked": len(REQUIRED_CANDIDATE_MARKERS),
        "artifact_references": referenced,
        "proposed_tag": PROPOSED_TAG,
        "approval_phrase": APPROVAL_PHRASE,
        "generic_continue_is_approval": False,
        "tag_action_taken": False,
    }


def verify_doc_references() -> dict[str, list[str]]:
    checked: dict[str, list[str]] = {}
    for relative_path, markers in REQUIRED_DOC_REFERENCES.items():
        text = read_text(relative_path)
        require_markers(text, markers, relative_path)
        checked[relative_path] = markers
    return checked


def verify_lifecycle_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.4 lifecycle summary")
    require_equal(payload, "ok", "xriq-phase1-4-signed-submit-lifecycle-smoke", "lifecycle")
    require_list_contains(
        payload.get("completed"),
        [
            "created and validated signed-transfer artifact",
            "verified signed-submit default refusal",
            "verified invalid signed-submit refusal",
            "accepted signed-submit to pending",
            "verified signed-submit pending status",
            "produced signed-submit transaction into one local block",
            "verified signed-submit confirmed status",
            "verified admin audit catalog visibility",
        ],
        "lifecycle completed",
    )
    require_list_contains(
        payload.get("guards"),
        [
            "accepted signed-submit requires --enable-local-wallet-submit-signed true",
            "block production requires --enable-local-block-production true",
            "no UI mutation control is enabled",
            "no browser key material, custody material, public network, DEX, production infrastructure, or tag action",
        ],
        "lifecycle guards",
    )
    return {
        "path": path_reference_markers(path)[-1],
        "transaction_hash": require_hash(payload.get("signed_submit_tx_hash"), "lifecycle tx hash"),
        "signing_hash": require_hash(payload.get("signed_submit_signing_hash"), "lifecycle signing hash"),
        "produced_block_hash": require_hash(payload.get("produced_block_hash"), "lifecycle block hash"),
    }


def verify_plan_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.4 plan-check summary")
    require_equal(payload, "ok", "xriq-phase1-4-plan-check", "plan check")
    prohibited = payload.get("prohibited_without_explicit_approval")
    require_list_contains(
        prohibited,
        [
            "wallet submit UI mutation",
            "browser key generation or storage",
            "custody or hosted signing",
            "public network behavior",
            "DEX, bridge, smart-contract, or asset issuance scope",
            "production infrastructure",
            "tag creation or tag maintenance",
        ],
        "plan prohibited list",
    )
    return {
        "path": path_reference_markers(path)[-1],
        "markers_checked": payload.get("markers_checked"),
    }


def verify_signed_artifact_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.4 signed-artifact summary")
    require_equal(payload, "ok", "xriq-phase1-4-signed-artifact-check", "signed artifact")
    require_equal(payload, "format_version", "xriq-local-signed-transfer-envelope-v1", "signed artifact")
    require_equal(payload, "warning", "local-private-devnet-test-signature-only", "signed artifact")
    require_list_contains(
        payload.get("scope_boundaries"),
        [
            "CLI-only local/private test signed artifact",
            "no wallet submit UI mutation",
            "no browser key generation or storage",
            "no custody or hosted signing",
            "no public network, DEX, bridge, smart-contract, asset issuance, production infrastructure, or tag action",
        ],
        "signed artifact boundaries",
    )
    return {
        "path": path_reference_markers(path)[-1],
        "transaction_hash": require_hash(payload.get("transaction_hash"), "signed artifact tx hash"),
        "transaction_signing_hash": require_hash(
            payload.get("transaction_signing_hash"), "signed artifact signing hash"
        ),
    }


def verify_contract_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.4 contract summary")
    require_equal(payload, "ok", "xriq-phase1-4-contract-check", "contract")
    require_list_contains(payload.get("negative_cases"), EXPECTED_NEGATIVE_CASES, "contract negative cases")
    require_list_contains(
        payload.get("scope_boundaries"),
        [
            "local/private signed-transfer contract and accepted API mutation only",
            "accepted signed-submit mutation is explicit-flag local/private only",
            "no wallet submit UI mutation",
            "no browser key generation or storage",
            "no custody or hosted signing",
            "no public network, DEX, bridge, smart-contract, asset issuance, production infrastructure, or tag action",
        ],
        "contract boundaries",
    )
    return {
        "path": path_reference_markers(path)[-1],
        "negative_cases": payload.get("negative_cases"),
        "transaction_hash": require_hash(payload.get("transaction_hash"), "contract tx hash"),
    }


def verify_negative_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.4 negative-smoke summary")
    require_equal(payload, "ok", "xriq-phase1-4-signed-submit-negative-smoke", "negative smoke")
    require_equal(payload, "mutation", "none", "negative smoke")
    require_bool(payload, "pending_state_unchanged_on_failure", True, "negative smoke")
    require_bool(payload, "chain_state_unchanged_on_failure", True, "negative smoke")
    require_equal(payload, "pending_write_allowed", False, "negative smoke")
    require_list_contains(payload.get("case_ids"), EXPECTED_NEGATIVE_CASES, "negative smoke cases")
    return {
        "path": path_reference_markers(path)[-1],
        "cases_checked": payload.get("cases_checked"),
        "case_ids": payload.get("case_ids"),
    }


def verify_refusal_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.4 refusal-smoke summary")
    require_equal(payload, "ok", "xriq-phase1-4-signed-submit-refusal-smoke", "refusal smoke")
    require_equal(payload, "refusal_code", "signed_submit_disabled", "refusal smoke")
    require_bool(payload, "pending_file_created", False, "refusal smoke")
    require_list_contains(
        payload.get("scope_boundaries"),
        [
            "local/private signed-submit refusal smoke only",
            "no accepted signed-submit mutation in this refusal smoke",
            "no wallet submit UI mutation",
            "no browser key generation or storage",
            "no custody or hosted signing",
            "no public network, DEX, bridge, smart-contract, asset issuance, production infrastructure, or tag action",
        ],
        "refusal boundaries",
    )
    return {
        "path": path_reference_markers(path)[-1],
        "refusal_code": payload.get("refusal_code"),
        "pending_file_created": payload.get("pending_file_created"),
    }


def run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RcReadinessError(
            f"git {' '.join(args)} failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return completed


def verify_git(args: argparse.Namespace) -> dict[str, Any]:
    status: dict[str, Any] = {}
    if args.require_clean_git:
        short_status = run_git(["status", "--short"]).stdout.strip()
        if short_status:
            raise RcReadinessError(f"git worktree is not clean:\n{short_status}")
        status["clean"] = True
    if args.require_origin_main:
        head = run_git(["rev-parse", "HEAD"]).stdout.strip()
        origin_main = run_git(["rev-parse", "origin/main"]).stdout.strip()
        if head != origin_main:
            raise RcReadinessError(f"HEAD {head} does not match origin/main {origin_main}")
        status["head_matches_origin_main"] = True
    if args.require_tag_absent:
        local_tag = run_git(["tag", "--list", PROPOSED_TAG]).stdout.strip()
        if local_tag:
            raise RcReadinessError(f"local tag already exists: {PROPOSED_TAG}")
        status["local_tag_absent"] = True
    return status


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    selected_paths = {
        "lifecycle summary": resolve_summary_path(
            args.lifecycle_summary,
            DEFAULT_LIFECYCLE_SUMMARY,
            "Phase 1.4 lifecycle summary",
            "python scripts/xriq_phase1_4_signed_submit_lifecycle_smoke.py",
        ),
        "plan summary": resolve_summary_path(
            args.plan_summary,
            DEFAULT_PLAN_SUMMARY,
            "Phase 1.4 plan-check summary",
            "python scripts/xriq_phase1_4_plan_check.py",
        ),
        "signed artifact summary": resolve_summary_path(
            args.signed_artifact_summary,
            DEFAULT_SIGNED_ARTIFACT_SUMMARY,
            "Phase 1.4 signed-artifact summary",
            "python scripts/xriq_phase1_4_signed_artifact_check.py",
        ),
        "contract summary": resolve_summary_path(
            args.contract_summary,
            DEFAULT_CONTRACT_SUMMARY,
            "Phase 1.4 contract summary",
            "python scripts/xriq_phase1_4_contract_check.py",
        ),
        "negative summary": resolve_summary_path(
            args.negative_summary,
            DEFAULT_NEGATIVE_SUMMARY,
            "Phase 1.4 negative-smoke summary",
            "python scripts/xriq_phase1_4_signed_submit_negative_smoke.py",
        ),
        "refusal summary": resolve_summary_path(
            args.refusal_summary,
            DEFAULT_REFUSAL_SUMMARY,
            "Phase 1.4 refusal-smoke summary",
            "python scripts/xriq_phase1_4_signed_submit_refusal_smoke.py",
        ),
    }

    return {
        "ok": "xriq-phase1-4-rc-readiness",
        "completed_at": datetime.now(UTC).isoformat(),
        "proposed_tag": PROPOSED_TAG,
        "approval_phrase_required": APPROVAL_PHRASE,
        "ready_for_phase1_4_rc_decision": True,
        "ready_to_create_tag_now": False,
        "generic_continue_is_approval": False,
        "tag_action_taken": False,
        "completion_estimate_after_this_checkpoint": "about 95%",
        "candidate_report": verify_candidate_report(selected_paths),
        "evidence": {
            "lifecycle": verify_lifecycle_summary(selected_paths["lifecycle summary"]),
            "plan": verify_plan_summary(selected_paths["plan summary"]),
            "signed_artifact": verify_signed_artifact_summary(
                selected_paths["signed artifact summary"]
            ),
            "contract": verify_contract_summary(selected_paths["contract summary"]),
            "negative": verify_negative_summary(selected_paths["negative summary"]),
            "refusal": verify_refusal_summary(selected_paths["refusal summary"]),
        },
        "doc_references": verify_doc_references(),
        "git": verify_git(args),
        "prohibited_scope": [
            "wallet submit UI mutation",
            "browser key generation or storage",
            "custody or hosted signing",
            "public network behavior",
            "DEX, bridge, smart-contract, or asset issuance scope",
            "production infrastructure",
            "tag creation without exact explicit approval",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = build_summary(args)
        if args.write_summary:
            artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
            summary["artifact_dir"] = str(artifact_dir)
            write_json(artifact_dir / "summary.json", summary)
    except RcReadinessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
