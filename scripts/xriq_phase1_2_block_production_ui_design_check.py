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
DESIGN_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_BLOCK_PRODUCTION_UI_DESIGN.md"
GATE_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_UI_MUTATION_CONTROL_GATE.md"
PHASE_PLAN_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_LOCAL_PRIVATE_PLAN.md"
HANDOFF_DOC = ROOT / "docs" / "CODEX_HANDOFF.md"
ADMIN_UI = ROOT / "xriq" / "apps" / "explorer-ui" / "src" / "admin.tsx"
API_CLIENT = ROOT / "xriq" / "apps" / "explorer-ui" / "src" / "api.ts"
STATIC_CHECK = ROOT / "xriq" / "apps" / "explorer-ui" / "scripts" / "check-static.mjs"
PACKAGE_JSON = ROOT / "xriq" / "apps" / "explorer-ui" / "package.json"
LIVE_UI_CHECK = (
    ROOT / "xriq" / "apps" / "explorer-ui" / "scripts" / "check-block-production-ui-live.mjs"
)
ADMIN_REFRESH_UI_CHECK = (
    ROOT
    / "xriq"
    / "apps"
    / "explorer-ui"
    / "scripts"
    / "check-block-production-admin-refresh-live.mjs"
)
LIVE_SMOKE = ROOT / "scripts" / "xriq_phase1_2_block_production_ui_live_smoke.py"
ADMIN_REFRESH_SMOKE = (
    ROOT / "scripts" / "xriq_phase1_2_block_production_admin_refresh_smoke.py"
)

REQUIRED_DESIGN_MARKERS = [
    "Design Status: Approved And Implemented Behind Feature Switch",
    "Candidate: local block production only.",
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
    "--enable-local-block-production true",
    "validateLocalBlockProductionAcceptedContract",
    "Never run block production automatically after wallet send.",
    "No default-enabled `Produce Block` action.",
    "I explicitly approve implementing the Phase 1.2 local/private-devnet",
    "block-production UI mutation control behind the UI mutation-control gate.",
    "Current implementation:",
    "Current live UI smoke:",
    "Current Admin refresh smoke:",
]

REQUIRED_GATE_MARKERS = [
    "Gate Status: Approved For Wallet Send And Block Production",
    "Default UI mutation controls remain disabled.",
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
    "local/private-devnet block-production",
    "wallet submit remains deferred",
]

REQUIRED_PHASE_PLAN_MARKERS = [
    "Current wallet-send read-only refresh smoke checkpoint:",
    "Current block-production UI design checkpoint:",
    "Current block-production UI live smoke checkpoint:",
    "Current block-production Admin refresh smoke checkpoint:",
]

REQUIRED_HANDOFF_MARKERS = [
    "Latest native XRIQ Phase 1.2 wallet-send read-only refresh smoke checkpoint:",
    "Latest native XRIQ Phase 1.2 block-production UI design checkpoint:",
    "Latest native XRIQ Phase 1.2 block-production UI live smoke checkpoint:",
    "Latest native XRIQ Phase 1.2 block-production Admin refresh smoke checkpoint:",
]

REQUIRED_ADMIN_DISABLED_MARKERS = [
    "Admin Action Guards",
    "Block Production Guard",
    "Produce Block",
    "Check Guard",
    "block production disabled",
    "loadBlockProductionRefusal",
    "validateBlockProductionRefusalContract",
    "block_production_disabled",
    "--enable-local-block-production",
    'button type="button" disabled',
]

REQUIRED_ADMIN_IMPLEMENTATION_MARKERS = [
    "LOCAL_BLOCK_PRODUCTION_UI_ENABLED",
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI",
    "Local Block Production",
    "block-production local-only guard",
    "Produce Local",
    "chain_and_pending_state_local_only",
    "wallet send remains separate",
    "wallet submit deferred",
    "explicit local action",
    "produceLocalBlock",
    "validateLocalBlockProductionAcceptedContract",
    "adminSnapshotRows",
    "AdminSnapshotRows",
    'const produceDisabled = !enabled || pendingCount <= 0 || state.status === "loading";',
]

REQUIRED_API_MARKERS = [
    "LocalBlockProductionAcceptedResponse",
    "LocalBlockProductionConfirmedTransaction",
    "LocalBlockProductionAcceptedExpectations",
    "LocalBlockProductionRequest",
    "validateLocalBlockProductionAcceptedContract",
    "produceLocalBlock",
    "LOCAL_BLOCK_PRODUCTION_ACCEPTED_CODE",
    "LOCAL_BLOCK_PRODUCTION_ACCEPTED_MUTATION",
    "BLOCK_PRODUCTION_REFUSAL_ENDPOINT",
    "loadBlockProductionRefusal",
    "acceptedStatuses: [201]",
]

REQUIRED_STATIC_MARKERS = [
    "Admin Action Guards",
    "Block Production Guard",
    "Produce Block",
    "Check Guard",
    "loadBlockProductionRefusal",
    "validateBlockProductionRefusalContract",
    "Local Block Production",
    "Produce Local",
    "produceLocalBlock",
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI",
    "adminSnapshotRows",
    "check-block-production-admin-refresh-live.mjs",
    "/api/v1/blocks/produce",
    "fetch(",
]

REQUIRED_PACKAGE_MARKERS = [
    "check-block-production-ui-control.mjs",
    "check:block-production-ui-live",
    "check:block-production-admin-refresh-live",
]

REQUIRED_LIVE_UI_CHECK_MARKERS = [
    "xriq-block-production-ui-live",
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI",
    "produceLocalBlock",
    "validateLocalBlockProductionAcceptedContract",
    "block_production_explicit",
    "wallet_submit_deferred",
    "wallet_send_separate",
]

REQUIRED_ADMIN_REFRESH_UI_CHECK_MARKERS = [
    "xriq-block-production-admin-refresh-live",
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI",
    "adminSnapshotRows",
    "admin_rows_before",
    "wallet submit deferred",
    "Produce Local",
]

REQUIRED_LIVE_SMOKE_MARKERS = [
    "xriq-phase1-2-block-production-ui-live-smoke",
    "check:block-production-ui-live",
    "enable_local_wallet_send=True",
    "enable_local_block_production=True",
    "enable_local_wallet_submit",
    "block-production UI live produced one local block",
    "wallet submit remains refused",
]

REQUIRED_ADMIN_REFRESH_SMOKE_MARKERS = [
    "xriq-phase1-2-block-production-admin-refresh-smoke",
    "check:block-production-admin-refresh-live",
    "enable_local_wallet_send=True",
    "enable_local_block_production=True",
    "Admin rows refresh from pending to confirmed state",
    "wallet submit remains refused",
]

FORBIDDEN_ADMIN_BEHAVIOR_MARKERS = [
    "fetch(",
    "/api/v1/blocks/produce",
    "localStorage",
    "sessionStorage",
    "indexedDB",
    "document.cookie",
]

FORBIDDEN_API_IMPLEMENTATION_MARKERS = [
    "sendLocalBlockProduction",
    "produceBlockLocal",
]

SENSITIVE_KEY_RE = re.compile(
    r"(private[_-]?key|seed[_-]?phrase|mnemonic|signature|signed[_-]?transaction)",
    re.IGNORECASE,
)


class DesignCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the review-only XRIQ Phase 1.2 block-production UI design."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for design-check artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument("--refresh-summary", type=Path, default=None)
    parser.add_argument("--live-summary", type=Path, default=None)
    parser.add_argument("--admin-refresh-summary", type=Path, default=None)
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase1-2-block-production-ui-design-check-{timestamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise DesignCheckError(f"required file is missing: {path}") from error


def require_markers(text: str, markers: list[str], context: str) -> None:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise DesignCheckError(f"{context}: missing markers {missing}")


def require_absent(text: str, markers: list[str], context: str) -> None:
    found = [marker for marker in markers if marker.lower() in text.lower()]
    if found:
        raise DesignCheckError(f"{context}: forbidden implementation markers found {found}")


def latest(pattern: str, description: str) -> Path:
    candidates = list(TARGET_DIR.glob(pattern))
    if not candidates:
        raise DesignCheckError(f"no {description} found under {TARGET_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise DesignCheckError(f"{description} does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise DesignCheckError(f"{description} is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise DesignCheckError(f"{description} must be a JSON object: {path}")
    return payload


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise DesignCheckError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def existing_path(path_text: Any, context: str) -> Path:
    if not isinstance(path_text, str) or not path_text:
        raise DesignCheckError(f"{context}: expected non-empty artifact path")
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise DesignCheckError(f"{context}: artifact does not exist: {path}")
    return path


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


def verify_refresh_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "wallet-send refresh summary")
    require_equal(payload, "ok", "xriq-phase1-2-wallet-send-refresh-smoke", "refresh")
    require_equal(payload, "feature_switch", "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true", "refresh")

    flags = payload.get("serve_readonly_flags")
    if not isinstance(flags, dict):
        raise DesignCheckError("refresh: expected serve_readonly_flags object")
    require_equal(flags, "enable_local_wallet_send", True, "refresh flags")
    require_equal(flags, "enable_local_wallet_submit", False, "refresh flags")
    require_equal(flags, "enable_local_block_production", False, "refresh flags")

    completed = payload.get("completed")
    if not isinstance(completed, list):
        raise DesignCheckError("refresh: completed must be a list")
    for step in [
        "wallet-send refresh visible in snapshot and activity rows",
        "wallet submit remains refused",
        "block production remains refused",
    ]:
        if step not in completed:
            raise DesignCheckError(f"refresh: missing completed step {step!r}")

    guards = payload.get("guards")
    if not isinstance(guards, list):
        raise DesignCheckError("refresh: guards must be a list")
    for guard in [
        "wallet submit remains disabled without --enable-local-wallet-submit",
        "block production remains disabled without --enable-local-block-production",
        "accepted wallet-send mutation is pending_state_only",
        "no signing material or custody material is accepted",
    ]:
        if guard not in guards:
            raise DesignCheckError(f"refresh: missing guard {guard!r}")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise DesignCheckError("refresh: artifacts must be an object")
    for key in ["ui_summary", "ui_snapshot", "wallet_submit_refusal", "block_production_refusal"]:
        existing_path(artifacts.get(key), f"refresh artifact {key}")

    sensitive_fields = find_sensitive_fields(payload)
    if sensitive_fields:
        raise DesignCheckError(f"refresh summary contains sensitive fields {sensitive_fields}")

    return {
        "path": str(path),
        "wallet_send_tx_hash": payload.get("wallet_send_tx_hash"),
        "block_production_enabled": False,
        "wallet_submit_enabled": False,
    }


def verify_live_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "block-production UI live summary")
    require_equal(payload, "ok", "xriq-phase1-2-block-production-ui-live-smoke", "live")
    require_equal(
        payload,
        "feature_switch",
        "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "live",
    )

    flags = payload.get("serve_readonly_flags")
    if not isinstance(flags, dict):
        raise DesignCheckError("live: expected serve_readonly_flags object")
    require_equal(flags, "enable_local_wallet_send", True, "live flags")
    require_equal(flags, "enable_local_wallet_submit", False, "live flags")
    require_equal(flags, "enable_local_block_production", True, "live flags")

    completed = payload.get("completed")
    if not isinstance(completed, list):
        raise DesignCheckError("live: completed must be a list")
    for step in [
        "block-production UI live produced one local block",
        "pending file cleared after confirmed block production",
        "wallet submit remains refused",
        "network height advanced exactly one block",
        "mempool empty after local block production",
    ]:
        if step not in completed:
            raise DesignCheckError(f"live: missing completed step {step!r}")

    guards = payload.get("guards")
    if not isinstance(guards, list):
        raise DesignCheckError("live: guards must be a list")
    for guard in [
        "block-production UI requires VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "block-production UI uses the shared API client helper",
        "block production requires --enable-local-block-production",
        "wallet send remains separate and explicit",
        "wallet submit remains disabled without --enable-local-wallet-submit",
        "accepted block-production mutation is chain_and_pending_state_local_only",
        "pending file removes confirmed transaction hashes",
        "chain height advances exactly one block",
        "no signing material or custody material is accepted",
    ]:
        if guard not in guards:
            raise DesignCheckError(f"live: missing guard {guard!r}")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise DesignCheckError("live: artifacts must be an object")
    for key in [
        "ui_summary",
        "ui_wallet_send",
        "ui_produced_block",
        "ui_confirmed_status",
        "ui_snapshot_after",
        "wallet_submit_refusal",
        "network",
        "mempool_empty",
    ]:
        existing_path(artifacts.get(key), f"live artifact {key}")

    sensitive_fields = find_sensitive_fields(payload)
    if sensitive_fields:
        raise DesignCheckError(f"live summary contains sensitive fields {sensitive_fields}")

    return {
        "path": str(path),
        "wallet_send_tx_hash": payload.get("wallet_send_tx_hash"),
        "produced_block_hash": payload.get("produced_block_hash"),
        "block_production_enabled": True,
        "wallet_submit_enabled": False,
    }


def verify_admin_refresh_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "block-production Admin refresh summary")
    require_equal(
        payload,
        "ok",
        "xriq-phase1-2-block-production-admin-refresh-smoke",
        "admin refresh",
    )
    require_equal(
        payload,
        "feature_switch",
        "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "admin refresh",
    )

    flags = payload.get("serve_readonly_flags")
    if not isinstance(flags, dict):
        raise DesignCheckError("admin refresh: expected serve_readonly_flags object")
    require_equal(flags, "enable_local_wallet_send", True, "admin refresh flags")
    require_equal(flags, "enable_local_wallet_submit", False, "admin refresh flags")
    require_equal(flags, "enable_local_block_production", True, "admin refresh flags")

    completed = payload.get("completed")
    if not isinstance(completed, list):
        raise DesignCheckError("admin refresh: completed must be a list")
    for step in [
        "Admin rows refresh from pending to confirmed state",
        "pending file cleared after Admin refresh block production",
        "wallet submit remains refused",
    ]:
        if step not in completed:
            raise DesignCheckError(f"admin refresh: missing completed step {step!r}")

    guards = payload.get("guards")
    if not isinstance(guards, list):
        raise DesignCheckError("admin refresh: guards must be a list")
    for guard in [
        "Admin refresh uses the same adminSnapshotRows helper as the UI",
        "block-production Admin refresh requires VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "block production requires --enable-local-block-production",
        "wallet send remains separate and explicit",
        "wallet submit remains disabled without --enable-local-wallet-submit",
        "Admin rows show pending before block production",
        "Admin rows show height 2 and zero pending after block production",
        "no signing material or custody material is accepted",
    ]:
        if guard not in guards:
            raise DesignCheckError(f"admin refresh: missing guard {guard!r}")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise DesignCheckError("admin refresh: artifacts must be an object")
    for key in [
        "ui_summary",
        "ui_rows_before",
        "ui_rows_after",
        "ui_produced_block",
        "ui_confirmed_status",
        "wallet_submit_refusal",
    ]:
        existing_path(artifacts.get(key), f"admin refresh artifact {key}")

    sensitive_fields = find_sensitive_fields(payload)
    if sensitive_fields:
        raise DesignCheckError(f"admin refresh summary contains sensitive fields {sensitive_fields}")

    return {
        "path": str(path),
        "wallet_send_tx_hash": payload.get("wallet_send_tx_hash"),
        "produced_block_hash": payload.get("produced_block_hash"),
        "admin_rows_verified": True,
        "wallet_submit_enabled": False,
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
    try:
        design_doc = read_text(DESIGN_DOC)
        gate_doc = read_text(GATE_DOC)
        phase_plan_doc = read_text(PHASE_PLAN_DOC)
        handoff_doc = read_text(HANDOFF_DOC)
        admin_ui = read_text(ADMIN_UI)
        api_client = read_text(API_CLIENT)
        static_check = read_text(STATIC_CHECK)
        package_json = read_text(PACKAGE_JSON)
        live_ui_check = read_text(LIVE_UI_CHECK)
        admin_refresh_ui_check = read_text(ADMIN_REFRESH_UI_CHECK)
        live_smoke = read_text(LIVE_SMOKE)
        admin_refresh_smoke = read_text(ADMIN_REFRESH_SMOKE)
        refresh_summary = args.refresh_summary or latest(
            "xriq-phase1-2-wallet-send-refresh-smoke-*/summary.json",
            "wallet-send refresh summary",
        )
        live_summary = args.live_summary or latest(
            "xriq-phase1-2-block-production-ui-live-smoke-*/summary.json",
            "block-production UI live summary",
        )
        admin_refresh_summary = args.admin_refresh_summary or latest(
            "xriq-phase1-2-block-production-admin-refresh-smoke-*/summary.json",
            "block-production Admin refresh summary",
        )

        require_markers(design_doc, REQUIRED_DESIGN_MARKERS, "block-production UI design")
        require_markers(gate_doc, REQUIRED_GATE_MARKERS, "UI mutation gate")
        require_markers(phase_plan_doc, REQUIRED_PHASE_PLAN_MARKERS, "Phase 1.2 plan")
        require_markers(handoff_doc, REQUIRED_HANDOFF_MARKERS, "handoff")
        require_markers(admin_ui, REQUIRED_ADMIN_DISABLED_MARKERS, "Admin UI disabled guard")
        require_markers(admin_ui, REQUIRED_ADMIN_IMPLEMENTATION_MARKERS, "Admin UI implementation")
        require_markers(api_client, REQUIRED_API_MARKERS, "API client")
        require_markers(static_check, REQUIRED_STATIC_MARKERS, "static UI check")
        require_markers(package_json, REQUIRED_PACKAGE_MARKERS, "package scripts")
        require_markers(live_ui_check, REQUIRED_LIVE_UI_CHECK_MARKERS, "live UI check")
        require_markers(
            admin_refresh_ui_check,
            REQUIRED_ADMIN_REFRESH_UI_CHECK_MARKERS,
            "admin refresh UI check",
        )
        require_markers(live_smoke, REQUIRED_LIVE_SMOKE_MARKERS, "live UI smoke")
        require_markers(
            admin_refresh_smoke,
            REQUIRED_ADMIN_REFRESH_SMOKE_MARKERS,
            "admin refresh smoke",
        )
        require_absent(
            admin_ui,
            FORBIDDEN_ADMIN_BEHAVIOR_MARKERS,
            "Admin UI",
        )
        require_absent(
            api_client,
            FORBIDDEN_API_IMPLEMENTATION_MARKERS,
            "API client",
        )
        refresh = verify_refresh_summary(refresh_summary)
        live = verify_live_summary(live_summary)
        admin_refresh = verify_admin_refresh_summary(admin_refresh_summary)

        report = {
            "ok": "xriq-phase1-2-block-production-ui-design-check",
            "artifact_dir": str(artifact_dir),
            "phase": "1.2",
            "scope": "local-private-post-rc-hardening",
            "design_doc": str(DESIGN_DOC),
            "refresh_summary": refresh,
            "live_summary": live,
            "admin_refresh_summary": admin_refresh,
            "review_only": False,
            "implementation_allowed": True,
            "approval_recorded": True,
            "block_production_ui_feature_switch_required": True,
            "block_production_ui_default_enabled": False,
            "required_approval": (
                "I explicitly approve implementing the Phase 1.2 "
                "local/private-devnet block-production UI mutation control "
                "behind the UI mutation-control gate."
            ),
            "admin_disabled_guard_present": True,
            "live_smoke_verified": True,
            "admin_refresh_smoke_verified": True,
            "next": "keep block-production UI live smoke evidence current",
        }
        write_summary(artifact_dir / "summary.json", report)
    except DesignCheckError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
