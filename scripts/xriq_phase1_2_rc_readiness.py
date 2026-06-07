from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SUMMARY_ROOT = ROOT / "xriq" / "target"
CANDIDATE_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_RC_CANDIDATE_REPORT.md"
PROPOSED_TAG = "phase1-2-xriq-local-private-hardening-rc1"
APPROVAL_PHRASE = (
    "I explicitly approve creating and pushing the Phase 1.2 RC tag "
    "phase1-2-xriq-local-private-hardening-rc1."
)

REQUIRED_CANDIDATE_MARKERS = [
    "# XRIQ Phase 1.2 RC Candidate Report",
    "Status: candidate report only. No Phase 1.2 RC tag has been created by this",
    PROPOSED_TAG,
    "Pre-report implementation checkpoint reviewed for this candidate: `d206b78`.",
    "Latest Phase 1.2 readiness summary:",
    "Latest UI mutation-control gate:",
    "Latest block-production UI design check:",
    "Required local smoke evidence:",
    "## RC Go/No-Go Checklist",
    "## Non-Production Boundaries",
    "Do not tag from a generic continue request.",
    APPROVAL_PHRASE,
]

REQUIRED_CANDIDATE_ARTIFACT_PATHS = [
    "xriq/target/xriq-phase1-2-readiness-summary-20260607T115109Z/summary.json",
    "xriq/target/xriq-phase1-2-ui-mutation-gate-check-20260607T115109Z/summary.json",
    "xriq/target/xriq-phase1-2-block-production-ui-design-check-20260607T115109Z/summary.json",
    "xriq/target/xriq-phase1-2-wallet-send-lifecycle-smoke-20260606T213131Z/summary.json",
    "xriq/target/xriq-phase1-2-wallet-send-ui-live-smoke-20260606T232950Z/summary.json",
    "xriq/target/xriq-phase1-2-wallet-send-refresh-smoke-20260607T005924Z/summary.json",
    "xriq/target/xriq-phase1-2-block-production-ui-live-smoke-20260607T105329Z/summary.json",
    "xriq/target/xriq-phase1-2-block-production-admin-refresh-smoke-20260607T110810Z/summary.json",
    "xriq/target/xriq-phase1-2-block-production-no-pending-smoke-20260607T112046Z/summary.json",
]

REQUIRED_DOC_REFERENCES = {
    "docs/CODEX_HANDOFF.md": [
        "Latest native XRIQ Phase 1.2 RC candidate report checkpoint:",
        "docs/XRIQ_PHASE1_2_RC_CANDIDATE_REPORT.md",
        PROPOSED_TAG,
        APPROVAL_PHRASE,
        "Recommended next narrow step: ask the user for a decision on the Phase 1.2 RC",
    ],
    "docs/XRIQ_PHASE1_2_LOCAL_PRIVATE_PLAN.md": [
        "Current Phase 1.2 RC candidate report checkpoint:",
        "docs/XRIQ_PHASE1_2_RC_CANDIDATE_REPORT.md",
        PROPOSED_TAG,
        "no tag may be",
    ],
    "docs/XRIQ_PHASE1_2_UI_MUTATION_CONTROL_GATE.md": [
        "block-production UI live evidence",
        "block-production Admin refresh evidence",
        "block-production no-pending negative evidence",
        "ready_for_phase1_2_rc_decision: false",
    ],
}


class RcReadinessError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check local/private XRIQ Phase 1.2 RC candidate readiness guardrails."
    )
    parser.add_argument(
        "--readiness-summary",
        type=Path,
        default=None,
        help="Path to a Phase 1.2 readiness summary.json.",
    )
    parser.add_argument(
        "--latest-summary",
        action="store_true",
        help="Use the latest xriq-phase1-2-readiness-summary under xriq/target.",
    )
    parser.add_argument(
        "--ui-gate-summary",
        type=Path,
        default=None,
        help="Path to a Phase 1.2 UI mutation-control gate summary.json.",
    )
    parser.add_argument(
        "--latest-ui-gate-summary",
        action="store_true",
        help="Use the latest xriq-phase1-2-ui-mutation-gate-check summary.",
    )
    parser.add_argument(
        "--block-production-design-summary",
        type=Path,
        default=None,
        help="Path to a Phase 1.2 block-production UI design summary.json.",
    )
    parser.add_argument(
        "--latest-block-production-design-summary",
        action="store_true",
        help="Use the latest xriq-phase1-2-block-production-ui-design-check summary.",
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
        "--require-tag-absent",
        action="store_true",
        help=f"Fail if local or remote tag {PROPOSED_TAG} already exists.",
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
        help=(
            "Directory for --write-summary output. Defaults to a timestamped "
            "xriq/target/xriq-phase1-2-rc-readiness-* directory."
        ),
    )
    return parser.parse_args(argv)


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_artifact_dir() -> Path:
    return SUMMARY_ROOT / f"xriq-phase1-2-rc-readiness-{utc_timestamp()}"


def read_text(relative_path: str) -> str:
    path = ROOT / relative_path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RcReadinessError(f"required document is missing: {relative_path}") from error


def latest_readiness_summary_path() -> Path:
    return latest_summary_path(
        "xriq-phase1-2-readiness-summary-*/summary.json",
        "Phase 1.2 readiness summary",
        "python scripts/xriq_phase1_2_readiness_summary.py",
    )


def latest_summary_path(pattern: str, label: str, command: str) -> Path:
    candidates = list(SUMMARY_ROOT.glob(pattern))
    if not candidates:
        raise RcReadinessError(
            f"no {label} found under xriq/target; run {command} first"
        )
    return max(candidates, key=lambda path: path.stat().st_mtime)


def latest_ui_gate_summary_path() -> Path:
    return latest_summary_path(
        "xriq-phase1-2-ui-mutation-gate-check-*/summary.json",
        "Phase 1.2 UI mutation-control gate summary",
        "python scripts/xriq_phase1_2_ui_mutation_gate_check.py",
    )


def latest_block_production_design_summary_path() -> Path:
    return latest_summary_path(
        "xriq-phase1-2-block-production-ui-design-check-*/summary.json",
        "Phase 1.2 block-production UI design summary",
        "python scripts/xriq_phase1_2_block_production_ui_design_check.py",
    )


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RcReadinessError(f"summary file does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise RcReadinessError(f"summary file is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise RcReadinessError(f"summary file is not a JSON object: {path}")
    return payload


def existing_path(path_text: str) -> Path:
    if not path_text:
        raise RcReadinessError("listed artifact path is empty")
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise RcReadinessError(f"listed artifact does not exist: {path}")
    return path


def same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except FileNotFoundError:
        return left.absolute() == right.absolute()


def run_git(args: list[str], *, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 and not allow_failure:
        raise RcReadinessError(
            f"git {' '.join(args)} failed with exit code {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    return completed


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


def verify_candidate_report(
    readiness_summary: Path,
    ui_gate_summary: Path,
    block_production_design_summary: Path,
) -> dict[str, Any]:
    try:
        text = CANDIDATE_DOC.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise RcReadinessError(f"candidate report is missing: {CANDIDATE_DOC}") from error

    missing = [marker for marker in REQUIRED_CANDIDATE_MARKERS if marker not in text]
    if missing:
        raise RcReadinessError(f"candidate report missing markers: {missing}")

    missing_paths = [path for path in REQUIRED_CANDIDATE_ARTIFACT_PATHS if path not in text]
    if missing_paths:
        raise RcReadinessError(f"candidate report missing artifact paths: {missing_paths}")
    for path_text in REQUIRED_CANDIDATE_ARTIFACT_PATHS:
        existing_path(path_text)

    selected_evidence = {
        "readiness_summary": verify_candidate_path_reference(
            text, "readiness summary", readiness_summary
        ),
        "ui_gate_summary": verify_candidate_path_reference(
            text, "UI mutation-control gate summary", ui_gate_summary
        ),
        "block_production_design_summary": verify_candidate_path_reference(
            text,
            "block-production UI design summary",
            block_production_design_summary,
        ),
    }

    return {
        "candidate_report": str(CANDIDATE_DOC.relative_to(ROOT)),
        "proposed_tag": PROPOSED_TAG,
        "required_approval_phrase": APPROVAL_PHRASE,
        "artifact_paths_checked": len(REQUIRED_CANDIDATE_ARTIFACT_PATHS),
        "selected_evidence": selected_evidence,
        "tag_created_by_report": False,
    }


def verify_doc_references() -> list[str]:
    checked: list[str] = []
    for relative_path, required_texts in REQUIRED_DOC_REFERENCES.items():
        text = read_text(relative_path)
        missing = [required for required in required_texts if required not in text]
        if missing:
            raise RcReadinessError(f"{relative_path} missing references: {missing}")
        checked.append(relative_path)
    return checked


def require_bool(payload: dict[str, Any], key: str, expected: bool, context: str) -> None:
    actual = payload.get(key)
    if actual is not expected:
        raise RcReadinessError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_object(payload: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise RcReadinessError(f"{context}: expected object at {key}")
    return value


def verify_readiness_summary(summary_path: Path) -> dict[str, Any]:
    payload = load_json_object(summary_path)
    if payload.get("ok") != "xriq-phase1-2-readiness-summary":
        raise RcReadinessError(
            f"summary ok marker is not xriq-phase1-2-readiness-summary: {payload.get('ok')!r}"
        )
    if payload.get("scope") != "local-private-post-rc-hardening":
        raise RcReadinessError(f"summary scope is unexpected: {payload.get('scope')!r}")

    for key, expected in [
        ("ready_for_ui_mutation_design_review", True),
        ("ui_mutation_controls_enabled", False),
        ("safe_to_enable_ui_mutation_controls", False),
        ("approval_required_before_ui_mutation_controls", True),
        ("block_production_evidence_required_for_rc", True),
        ("block_production_evidence_current", True),
        ("ready_for_phase1_2_rc_decision", False),
        ("phase1_2_rc_approval_required", True),
    ]:
        require_bool(payload, key, expected, "readiness summary")

    required_objects = [
        "refusal_summary",
        "wallet_send_accepted",
        "wallet_send_lifecycle",
        "block_production_ui_live",
        "block_production_admin_refresh",
        "block_production_no_pending",
    ]
    for key in required_objects:
        require_object(payload, key, "readiness summary")

    no_pending = payload["block_production_no_pending"]
    if no_pending.get("no_pending_refusal_code") != "no_pending_transactions":
        raise RcReadinessError("readiness summary: no-pending refusal code is not stable")
    require_bool(no_pending, "chain_and_pending_unchanged", True, "readiness no-pending")
    require_bool(no_pending, "wallet_send_enabled", False, "readiness no-pending")
    require_bool(no_pending, "wallet_submit_enabled", False, "readiness no-pending")

    live = payload["block_production_ui_live"]
    admin_refresh = payload["block_production_admin_refresh"]
    if live.get("wallet_send_tx_hash") != admin_refresh.get("wallet_send_tx_hash"):
        raise RcReadinessError("block-production UI live and Admin refresh tx hashes differ")
    if live.get("produced_block_hash") != admin_refresh.get("produced_block_hash"):
        raise RcReadinessError("block-production UI live and Admin refresh block hashes differ")

    for object_key in required_objects:
        object_path = payload[object_key].get("path")
        if isinstance(object_path, str):
            existing_path(object_path)

    return {
        "summary": str(summary_path),
        "required_objects_checked": len(required_objects),
        "block_production_evidence_current": True,
        "ready_for_phase1_2_rc_decision": False,
        "phase1_2_rc_approval_required": True,
    }


def verify_ui_gate_summary(gate_path: Path, readiness_path: Path) -> dict[str, Any]:
    payload = load_json_object(gate_path)
    if payload.get("ok") != "xriq-phase1-2-ui-mutation-control-gate-check":
        raise RcReadinessError(
            "UI gate ok marker is not xriq-phase1-2-ui-mutation-control-gate-check: "
            f"{payload.get('ok')!r}"
        )
    if payload.get("scope") != "local-private-post-rc-hardening":
        raise RcReadinessError(f"UI gate scope is unexpected: {payload.get('scope')!r}")

    for key, expected in [
        ("default_ui_mutation_controls_enabled", False),
        ("approval_required_before_ui_mutation_controls", True),
        ("wallet_submit_deferred", True),
        ("wallet_send_ui_feature_switch_required", True),
        ("block_production_ui_feature_switch_required", True),
        ("block_production_ui_default_enabled", False),
    ]:
        require_bool(payload, key, expected, "UI mutation gate summary")

    readiness = require_object(payload, "readiness_summary", "UI mutation gate summary")
    readiness_summary_path = existing_path(readiness.get("path", ""))
    if not same_path(readiness_summary_path, readiness_path):
        raise RcReadinessError("UI gate references a different readiness summary")
    for key, expected in [
        ("ready_for_ui_mutation_design_review", True),
        ("ui_mutation_controls_enabled", False),
        ("safe_to_enable_ui_mutation_controls", False),
        ("approval_required_before_ui_mutation_controls", True),
        ("block_production_evidence_current", True),
        ("ready_for_phase1_2_rc_decision", False),
    ]:
        require_bool(readiness, key, expected, "UI gate readiness summary")

    wallet_ui = require_object(payload, "wallet_ui", "UI mutation gate summary")
    admin_ui = require_object(payload, "admin_ui", "UI mutation gate summary")
    require_bool(wallet_ui, "default_wallet_send_disabled", True, "UI gate wallet_ui")
    require_bool(wallet_ui, "wallet_send_feature_switch_required", True, "UI gate wallet_ui")
    require_bool(wallet_ui, "wallet_submit_deferred", True, "UI gate wallet_ui")
    require_bool(admin_ui, "default_block_production_disabled", True, "UI gate admin_ui")
    require_bool(
        admin_ui,
        "block_production_feature_switch_required",
        True,
        "UI gate admin_ui",
    )
    require_bool(admin_ui, "wallet_submit_deferred", True, "UI gate admin_ui")

    return {
        "summary": str(gate_path),
        "readiness_summary": str(readiness_summary_path),
        "default_ui_mutation_controls_enabled": False,
        "approval_required_before_ui_mutation_controls": True,
    }


def verify_block_production_design_summary(design_path: Path) -> dict[str, Any]:
    payload = load_json_object(design_path)
    if payload.get("ok") != "xriq-phase1-2-block-production-ui-design-check":
        raise RcReadinessError(
            "block-production design ok marker is not "
            f"xriq-phase1-2-block-production-ui-design-check: {payload.get('ok')!r}"
        )
    if payload.get("scope") != "local-private-post-rc-hardening":
        raise RcReadinessError(
            f"block-production design scope is unexpected: {payload.get('scope')!r}"
        )

    for key, expected in [
        ("approval_recorded", True),
        ("implementation_allowed", True),
        ("review_only", False),
        ("admin_disabled_guard_present", True),
        ("live_smoke_verified", True),
        ("admin_refresh_smoke_verified", True),
        ("no_pending_smoke_verified", True),
        ("block_production_ui_default_enabled", False),
        ("block_production_ui_feature_switch_required", True),
    ]:
        require_bool(payload, key, expected, "block-production design summary")

    live = require_object(payload, "live_summary", "block-production design summary")
    admin_refresh = require_object(
        payload, "admin_refresh_summary", "block-production design summary"
    )
    no_pending = require_object(
        payload, "no_pending_summary", "block-production design summary"
    )
    refresh = require_object(payload, "refresh_summary", "block-production design summary")

    for summary_object in [live, admin_refresh, no_pending, refresh]:
        object_path = summary_object.get("path")
        if not isinstance(object_path, str):
            raise RcReadinessError("block-production design summary missing artifact path")
        existing_path(object_path)

    if live.get("wallet_send_tx_hash") != admin_refresh.get("wallet_send_tx_hash"):
        raise RcReadinessError(
            "block-production design live and Admin refresh tx hashes differ"
        )
    if live.get("produced_block_hash") != admin_refresh.get("produced_block_hash"):
        raise RcReadinessError(
            "block-production design live and Admin refresh block hashes differ"
        )
    for context, summary in [
        ("block-production design live", live),
        ("block-production design Admin refresh", admin_refresh),
    ]:
        require_bool(summary, "wallet_submit_enabled", False, context)
    require_bool(live, "block_production_enabled", True, "block-production design live")
    require_bool(refresh, "block_production_enabled", False, "block-production refresh")
    require_bool(no_pending, "block_production_enabled", True, "block-production no-pending")
    require_bool(no_pending, "chain_and_pending_unchanged", True, "block-production no-pending")
    require_bool(no_pending, "wallet_send_enabled", False, "block-production no-pending")
    require_bool(no_pending, "wallet_submit_enabled", False, "block-production no-pending")
    if no_pending.get("no_pending_refusal_code") != "no_pending_transactions":
        raise RcReadinessError("block-production design no-pending refusal code is not stable")

    return {
        "summary": str(design_path),
        "live_smoke_verified": True,
        "admin_refresh_smoke_verified": True,
        "no_pending_smoke_verified": True,
        "block_production_ui_default_enabled": False,
    }


def verify_tag_absent() -> dict[str, bool]:
    local = run_git(["tag", "--list", PROPOSED_TAG], allow_failure=True)
    if local.returncode != 0:
        raise RcReadinessError(f"local tag check failed: {local.stderr.strip()}")
    if local.stdout.strip():
        raise RcReadinessError(f"local tag already exists: {PROPOSED_TAG}")

    remote = run_git(["ls-remote", "--tags", "origin", PROPOSED_TAG], allow_failure=True)
    if remote.returncode != 0:
        raise RcReadinessError(f"remote tag check failed: {remote.stderr.strip()}")
    if remote.stdout.strip():
        raise RcReadinessError(f"remote tag already exists: {PROPOSED_TAG}")
    return {"local_tag_absent": True, "remote_tag_absent": True}


def verify_git(require_clean: bool, require_origin_main: bool) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if require_clean:
        status = run_git(["status", "--short"]).stdout.strip()
        if status:
            raise RcReadinessError(f"git working tree is not clean:\n{status}")
        result["clean_git"] = True
    if require_origin_main:
        head = run_git(["rev-parse", "HEAD"]).stdout.strip()
        origin = run_git(["rev-parse", "origin/main"]).stdout.strip()
        if head != origin:
            raise RcReadinessError("local HEAD does not match origin/main")
        result["origin_main_matches_head"] = True
    return result


def release_decision() -> dict[str, Any]:
    return {
        "human_decision_required": True,
        "generic_continue_is_approval": False,
        "exact_approval_phrase_required": APPROVAL_PHRASE,
        "proposed_tag": PROPOSED_TAG,
        "tag_created_by_this_guard": False,
        "allowed_without_exact_approval": [
            "run non-mutating readiness guardrails",
            "save ignored readiness evidence under xriq/target",
            "ask the user for the Phase 1.2 RC decision",
            "make one more narrow local/private hardening fix",
        ],
        "allowed_after_exact_approval": [
            (
                "python scripts/xriq_phase1_2_rc_readiness.py "
                "--require-clean-git --require-origin-main --require-tag-absent "
                "--write-summary"
            ),
            f"git tag {PROPOSED_TAG}",
            f"git push origin {PROPOSED_TAG}",
        ],
        "prohibited_without_exact_approval": [
            f"git tag {PROPOSED_TAG}",
            f"git push origin {PROPOSED_TAG}",
            f"moving or recreating {PROPOSED_TAG}",
            "broadening scope into public mainnet, DEX, custody, smart contracts, or production infrastructure",
        ],
    }


def verify_release_decision(decision: dict[str, Any]) -> dict[str, Any]:
    expected_after_approval = [
        (
            "python scripts/xriq_phase1_2_rc_readiness.py "
            "--require-clean-git --require-origin-main --require-tag-absent "
            "--write-summary"
        ),
        f"git tag {PROPOSED_TAG}",
        f"git push origin {PROPOSED_TAG}",
    ]
    expected_prohibited = [
        f"git tag {PROPOSED_TAG}",
        f"git push origin {PROPOSED_TAG}",
        f"moving or recreating {PROPOSED_TAG}",
    ]
    if decision.get("human_decision_required") is not True:
        raise RcReadinessError("release decision must require a human decision")
    if decision.get("generic_continue_is_approval") is not False:
        raise RcReadinessError("release decision must reject generic continue as approval")
    if decision.get("exact_approval_phrase_required") != APPROVAL_PHRASE:
        raise RcReadinessError("release decision approval phrase drifted")
    if decision.get("proposed_tag") != PROPOSED_TAG:
        raise RcReadinessError("release decision proposed tag drifted")
    if decision.get("tag_created_by_this_guard") is not False:
        raise RcReadinessError("release decision must state this guard creates no tag")

    allowed_after = decision.get("allowed_after_exact_approval")
    if allowed_after != expected_after_approval:
        raise RcReadinessError("release decision post-approval commands drifted")

    allowed_without = decision.get("allowed_without_exact_approval")
    if not isinstance(allowed_without, list) or not allowed_without:
        raise RcReadinessError("release decision must list no-approval actions")
    if not any("ask the user" in str(item) for item in allowed_without):
        raise RcReadinessError("release decision must allow asking for the RC decision")
    if any(PROPOSED_TAG in str(item) for item in allowed_without):
        raise RcReadinessError("release decision must not allow tag commands before approval")

    prohibited = decision.get("prohibited_without_exact_approval")
    if not isinstance(prohibited, list):
        raise RcReadinessError("release decision must list prohibited no-approval actions")
    missing_prohibited = [item for item in expected_prohibited if item not in prohibited]
    if missing_prohibited:
        raise RcReadinessError(
            f"release decision missing prohibited actions: {missing_prohibited}"
        )

    return {
        "human_decision_required": True,
        "generic_continue_is_approval": False,
        "post_approval_commands_checked": len(expected_after_approval),
        "prohibited_actions_checked": len(expected_prohibited),
    }


def resolve_output_dir(path: Path | None) -> Path:
    output_dir = path or default_artifact_dir()
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    return output_dir


def write_summary(report: dict[str, Any], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "summary.json"
    report["artifact_dir"] = str(output_dir)
    report["summary"] = str(summary_path)
    summary_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.latest_summary and args.readiness_summary is not None:
            raise RcReadinessError("use either --readiness-summary or --latest-summary, not both")
        if args.latest_ui_gate_summary and args.ui_gate_summary is not None:
            raise RcReadinessError(
                "use either --ui-gate-summary or --latest-ui-gate-summary, not both"
            )
        if (
            args.latest_block_production_design_summary
            and args.block_production_design_summary is not None
        ):
            raise RcReadinessError(
                "use either --block-production-design-summary or "
                "--latest-block-production-design-summary, not both"
            )
        readiness_summary = (
            latest_readiness_summary_path()
            if args.latest_summary or args.readiness_summary is None
            else args.readiness_summary
        )
        ui_gate_summary = (
            latest_ui_gate_summary_path()
            if args.latest_ui_gate_summary or args.ui_gate_summary is None
            else args.ui_gate_summary
        )
        block_production_design_summary = (
            latest_block_production_design_summary_path()
            if (
                args.latest_block_production_design_summary
                or args.block_production_design_summary is None
            )
            else args.block_production_design_summary
        )
        report: dict[str, Any] = {
            "ok": "xriq-phase1-2-rc-readiness",
            "created_at": datetime.now(UTC).isoformat(),
            "script": str(Path(__file__).resolve().relative_to(ROOT)),
            "scope": "local-private-post-rc-hardening",
            "non_mutating": True,
            "tag_created": False,
            "candidate": verify_candidate_report(
                readiness_summary,
                ui_gate_summary,
                block_production_design_summary,
            ),
            "doc_references": verify_doc_references(),
            "readiness_summary": verify_readiness_summary(readiness_summary),
            "ui_gate_summary": verify_ui_gate_summary(ui_gate_summary, readiness_summary),
            "block_production_design_summary": verify_block_production_design_summary(
                block_production_design_summary
            ),
            "git": verify_git(args.require_clean_git, args.require_origin_main),
            "tag_checks": {},
        }
        decision = release_decision()
        report["release_decision"] = decision
        report["release_decision_check"] = verify_release_decision(decision)
        if args.require_tag_absent:
            report["tag_checks"] = verify_tag_absent()
        if args.write_summary or args.artifact_dir is not None:
            write_summary(report, resolve_output_dir(args.artifact_dir))
    except RcReadinessError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
