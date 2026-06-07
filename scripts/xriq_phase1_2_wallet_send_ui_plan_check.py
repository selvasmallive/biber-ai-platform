#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "xriq" / "target"
PLAN_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_WALLET_SEND_UI_IMPLEMENTATION_PLAN.md"
GATE_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_UI_MUTATION_CONTROL_GATE.md"
HANDOFF_DOC = ROOT / "docs" / "CODEX_HANDOFF.md"
PHASE_PLAN_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_LOCAL_PRIVATE_PLAN.md"
WALLET_UI = ROOT / "xriq" / "apps" / "explorer-ui" / "src" / "wallet.tsx"
API_CLIENT = ROOT / "xriq" / "apps" / "explorer-ui" / "src" / "api.ts"
STATIC_CHECK = ROOT / "xriq" / "apps" / "explorer-ui" / "scripts" / "check-static.mjs"
PACKAGE_JSON = ROOT / "xriq" / "apps" / "explorer-ui" / "package.json"
LIVE_UI_CHECK = (
    ROOT / "xriq" / "apps" / "explorer-ui" / "scripts" / "check-wallet-send-ui-live.mjs"
)
REFRESH_UI_CHECK = (
    ROOT / "xriq" / "apps" / "explorer-ui" / "scripts" / "check-wallet-send-refresh-live.mjs"
)
LIVE_SMOKE = ROOT / "scripts" / "xriq_phase1_2_wallet_send_ui_live_smoke.py"
REFRESH_SMOKE = ROOT / "scripts" / "xriq_phase1_2_wallet_send_refresh_smoke.py"

REQUIRED_PLAN_MARKERS = [
    "Plan Status: Approved And Implemented Behind Feature Switch",
    "First candidate: wallet send only.",
    "Wallet submit remains deferred.",
    "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
    "validateLocalWalletSendAcceptedContract",
    "No implicit block production.",
    "I explicitly approve implementing the Phase 1.2 local/private-devnet wallet-send",
    "Current implementation:",
    "Current live UI smoke:",
    "Current read-only refresh smoke:",
]

REQUIRED_GATE_MARKERS = [
    "Gate Status: Approved For Wallet Send And Block Production",
    "Default UI mutation controls remain disabled.",
    "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
    "Explicit user approval is required",
    "local/private-devnet wallet-send",
]

REQUIRED_PHASE_PLAN_MARKERS = [
    "Current UI mutation-control design gate checkpoint:",
    "Current wallet-send UI implementation checkpoint:",
    "Current wallet-send UI live smoke checkpoint:",
    "Current wallet-send read-only refresh smoke checkpoint:",
]

REQUIRED_HANDOFF_MARKERS = [
    "Latest native XRIQ Phase 1.2 UI mutation-control gate checkpoint:",
    "Latest native XRIQ Phase 1.2 wallet-send UI implementation checkpoint:",
    "Latest native XRIQ Phase 1.2 wallet-send UI live smoke checkpoint:",
    "Latest native XRIQ Phase 1.2 wallet-send read-only refresh smoke checkpoint:",
]

REQUIRED_WALLET_UI_MARKERS = [
    "Wallet Action Guards",
    "disabled submit/send",
    "Submit Draft",
    "Send Transfer",
    "Check Guards",
    "loadWalletMutationRefusal",
    "LOCAL_WALLET_SEND_UI_ENABLED",
    "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI",
    "Local Wallet Send",
    "Wallet send local-only guard",
    "Send Local",
    "wallet submit deferred",
    "pending_state_only",
    "no implicit block production",
    "sendLocalWalletTransfer",
    "LocalWalletSendAcceptedResponse",
    "export function walletActivityRows",
]

REQUIRED_API_MARKERS = [
    "LocalWalletSendAcceptedResponse",
    "LocalWalletSendAcceptedExpectations",
    "LocalWalletSendRequest",
    "sendLocalWalletTransfer",
    "validateLocalWalletSendAcceptedContract",
    "LOCAL_WALLET_SEND_ACCEPTED_CODE",
    "LOCAL_WALLET_SEND_ACCEPTED_MUTATION",
    "acceptedStatuses: [201]",
]

REQUIRED_PACKAGE_MARKERS = [
    "check:wallet-send-ui-live",
    "check-wallet-send-ui-live.mjs",
    "check:wallet-send-refresh-live",
    "check-wallet-send-refresh-live.mjs",
]

REQUIRED_LIVE_UI_CHECK_MARKERS = [
    "xriq-wallet-send-ui-live",
    "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI",
    "sendLocalWalletTransfer",
    "--expected-chain-file",
    "--expected-pending-file",
    "wallet_submit_deferred",
    "block_production_separate",
    "direct_wallet_fetch",
    "direct_wallet_endpoint_strings",
]

REQUIRED_LIVE_SMOKE_MARKERS = [
    "xriq-phase1-2-wallet-send-ui-live-smoke",
    "check:wallet-send-ui-live",
    "enable_local_wallet_send=True",
    "enable_local_wallet_submit",
    "enable_local_block_production",
    "wallet submit remains refused",
    "block production remains refused",
]

REQUIRED_REFRESH_UI_CHECK_MARKERS = [
    "xriq-wallet-send-refresh-live",
    "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI",
    "sendLocalWalletTransfer",
    "loadExplorerSnapshot",
    "loadWalletTransactionStatus",
    "walletActivityRows",
    "snapshot_loaded",
    "sender_activity_direction",
    "recipient_activity_direction",
    "wallet_submit_deferred",
    "block_production_separate",
]

REQUIRED_REFRESH_SMOKE_MARKERS = [
    "xriq-phase1-2-wallet-send-refresh-smoke",
    "check:wallet-send-refresh-live",
    "enable_local_wallet_send=True",
    "wallet-send refresh visible in snapshot and activity rows",
    "wallet submit remains refused",
    "block production remains refused",
]

REQUIRED_STATIC_MARKERS = [
    "Wallet Action Guards",
    "disabled submit/send",
    "Submit Draft",
    "Send Transfer",
    "Check Guards",
    "/transfers/submit",
    "/transfers/send",
    "fetch(",
    "private_key",
    "seed_phrase",
]

FORBIDDEN_WALLET_UI_MARKERS = [
    "fetch(",
    "/transfers/submit",
    "/transfers/send",
    "private_key",
    "seed_phrase",
    "mnemonic",
    "signed_transaction",
    "localStorage",
    "sessionStorage",
    "indexedDB",
    "document.cookie",
]

SENSITIVE_KEY_RE = re.compile(
    r"(private[_-]?key|seed[_-]?phrase|mnemonic|signature|signed[_-]?transaction)",
    re.IGNORECASE,
)


class PlanCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the review-only XRIQ Phase 1.2 wallet-send UI plan."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for plan-check artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument("--gate-summary", type=Path, default=None)
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase1-2-wallet-send-ui-plan-check-{timestamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise PlanCheckError(f"required file is missing: {path}") from error


def require_markers(text: str, markers: list[str], context: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise PlanCheckError(f"{context}: missing markers {missing}")


def require_absent(text: str, markers: list[str], context: str) -> None:
    found = [marker for marker in markers if marker.lower() in text.lower()]
    if found:
        raise PlanCheckError(f"{context}: forbidden markers found {found}")


def latest(pattern: str, description: str) -> Path:
    candidates = list(TARGET_DIR.glob(pattern))
    if not candidates:
        raise PlanCheckError(f"no {description} found under {TARGET_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise PlanCheckError(f"{description} does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise PlanCheckError(f"{description} is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise PlanCheckError(f"{description} must be a JSON object: {path}")
    return payload


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise PlanCheckError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def find_sensitive_fields(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}" if path else key
            if SENSITIVE_KEY_RE.search(key):
                found.append(child_path)
            found.extend(find_sensitive_fields(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(find_sensitive_fields(child, f"{path}[{index}]"))
    return found


def verify_gate_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.2 UI mutation gate summary")
    require_equal(payload, "ok", "xriq-phase1-2-ui-mutation-control-gate-check", "gate")
    require_equal(payload, "default_ui_mutation_controls_enabled", False, "gate")
    require_equal(payload, "wallet_send_ui_feature_switch_required", True, "gate")
    require_equal(payload, "wallet_submit_deferred", True, "gate")
    require_equal(payload, "approval_required_before_ui_mutation_controls", True, "gate")
    require_equal(payload, "scope", "local-private-post-rc-hardening", "gate")
    sensitive_fields = find_sensitive_fields(payload)
    if sensitive_fields:
        raise PlanCheckError(f"gate summary contains sensitive fields {sensitive_fields}")
    return {
        "path": str(path),
        "default_ui_mutation_controls_enabled": False,
        "wallet_send_ui_feature_switch_required": True,
        "wallet_submit_deferred": True,
        "approval_required_before_ui_mutation_controls": True,
    }


def verify_wallet_ui_implementation(text: str) -> dict[str, Any]:
    require_markers(text, REQUIRED_WALLET_UI_MARKERS, "wallet UI")
    require_absent(text, FORBIDDEN_WALLET_UI_MARKERS, "wallet UI")
    if 'type="button" disabled' not in text:
        raise PlanCheckError("wallet UI: disabled button marker is missing")
    if "onClick={onCheck}" not in text:
        raise PlanCheckError("wallet UI: guard check action is missing")
    if (
        'const sendDisabled = !enabled || errors.length > 0 || state.status === "loading";'
        not in text
    ):
        raise PlanCheckError("wallet UI: local send button must be feature-switch gated")
    return {
        "required_markers_checked": len(REQUIRED_WALLET_UI_MARKERS),
        "forbidden_markers_checked": len(FORBIDDEN_WALLET_UI_MARKERS),
        "implementation_started": True,
        "feature_switch_required": True,
        "wallet_submit_deferred": True,
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
    try:
        plan_doc = read_text(PLAN_DOC)
        gate_doc = read_text(GATE_DOC)
        phase_plan_doc = read_text(PHASE_PLAN_DOC)
        handoff_doc = read_text(HANDOFF_DOC)
        wallet_ui = read_text(WALLET_UI)
        api_client = read_text(API_CLIENT)
        static_check = read_text(STATIC_CHECK)
        package_json = read_text(PACKAGE_JSON)
        live_ui_check = read_text(LIVE_UI_CHECK)
        refresh_ui_check = read_text(REFRESH_UI_CHECK)
        live_smoke = read_text(LIVE_SMOKE)
        refresh_smoke = read_text(REFRESH_SMOKE)
        gate_summary = args.gate_summary or latest(
            "xriq-phase1-2-ui-mutation-gate-check-*/summary.json",
            "Phase 1.2 UI mutation gate summary",
        )

        require_markers(plan_doc, REQUIRED_PLAN_MARKERS, "wallet-send UI plan")
        require_markers(gate_doc, REQUIRED_GATE_MARKERS, "UI mutation gate")
        require_markers(phase_plan_doc, REQUIRED_PHASE_PLAN_MARKERS, "Phase 1.2 plan")
        require_markers(handoff_doc, REQUIRED_HANDOFF_MARKERS, "handoff")
        require_markers(api_client, REQUIRED_API_MARKERS, "API client")
        require_markers(static_check, REQUIRED_STATIC_MARKERS, "static UI check")
        require_markers(package_json, REQUIRED_PACKAGE_MARKERS, "package scripts")
        require_markers(live_ui_check, REQUIRED_LIVE_UI_CHECK_MARKERS, "live UI check")
        require_markers(live_smoke, REQUIRED_LIVE_SMOKE_MARKERS, "live UI smoke")
        require_markers(
            refresh_ui_check,
            REQUIRED_REFRESH_UI_CHECK_MARKERS,
            "refresh UI check",
        )
        require_markers(refresh_smoke, REQUIRED_REFRESH_SMOKE_MARKERS, "refresh smoke")
        wallet_check = verify_wallet_ui_implementation(wallet_ui)
        gate = verify_gate_summary(gate_summary)

        report = {
            "ok": "xriq-phase1-2-wallet-send-ui-implementation-plan-check",
            "artifact_dir": str(artifact_dir),
            "phase": "1.2",
            "scope": "local-private-post-rc-hardening",
            "plan_doc": str(PLAN_DOC),
            "gate_summary": gate,
            "wallet_ui": wallet_check,
            "wallet_send_candidate": True,
            "wallet_submit_deferred": True,
            "implementation_started": True,
            "live_smoke_defined": True,
            "refresh_smoke_defined": True,
            "approval_recorded": True,
            "required_approval": (
                "I explicitly approve implementing the Phase 1.2 "
                "local/private-devnet wallet-send UI mutation control behind "
                "the UI mutation-control gate."
            ),
            "next": "keep local wallet-send live and refresh smoke evidence current",
        }
        write_summary(artifact_dir / "summary.json", report)
    except PlanCheckError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
