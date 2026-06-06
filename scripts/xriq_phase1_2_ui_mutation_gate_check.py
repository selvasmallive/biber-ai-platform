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
GATE_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_UI_MUTATION_CONTROL_GATE.md"
PLAN_DOC = ROOT / "docs" / "XRIQ_PHASE1_2_LOCAL_PRIVATE_PLAN.md"
HANDOFF_DOC = ROOT / "docs" / "CODEX_HANDOFF.md"
WALLET_UI = ROOT / "xriq" / "apps" / "explorer-ui" / "src" / "wallet.tsx"
STATIC_CHECK = ROOT / "xriq" / "apps" / "explorer-ui" / "scripts" / "check-static.mjs"
API_CLIENT = ROOT / "xriq" / "apps" / "explorer-ui" / "src" / "api.ts"

REQUIRED_GATE_MARKERS = [
    "Gate Status: Design Review Only",
    "UI mutation controls remain disabled.",
    "ready_for_ui_mutation_design_review: true",
    "ui_mutation_controls_enabled: false",
    "safe_to_enable_ui_mutation_controls: false",
    "approval_required_before_ui_mutation_controls: true",
    "No private key, seed phrase, mnemonic, raw signature, or signed transaction",
    "No direct `fetch(` calls from wallet UI source.",
    "No hard-coded wallet submit/send endpoint strings in wallet UI source.",
    "No default-enabled submit/send controls.",
    "Explicit user approval is required",
    "local/private-devnet wallet-send",
]

REQUIRED_PLAN_MARKERS = [
    "Current Phase 1.2 readiness summary checkpoint:",
    "Current UI mutation-control design gate checkpoint:",
    "Recommended next implementation: wait for explicit user approval",
]

REQUIRED_WALLET_MARKERS = [
    "Wallet Action Guards",
    "disabled submit/send",
    "Submit Draft",
    "Send Transfer",
    "Check Guards",
    "loadWalletMutationRefusal",
    "validateActionRefusalContract",
    "--enable-local-wallet-submit",
    "--enable-local-wallet-send",
    "local-private-devnet-preflight-only",
]

REQUIRED_STATIC_CHECK_MARKERS = [
    "Wallet Action Guards",
    "disabled submit/send",
    "Submit Draft",
    "Send Transfer",
    "Check Guards",
    "loadWalletMutationRefusal",
    "validateActionRefusalContract",
    "wallet_submit_disabled",
    "wallet_send_disabled",
    "/transfers/submit",
    "/transfers/send",
    "fetch(",
    "private_key",
    "seed_phrase",
]

REQUIRED_API_MARKERS = [
    "validateLocalWalletSubmitAcceptedContract",
    "validateLocalWalletSendAcceptedContract",
    "LocalWalletSubmitAcceptedResponse",
    "LocalWalletSendAcceptedResponse",
    "wallet_submit_accepted_local_only",
    "wallet_send_accepted_local_only",
]

FORBIDDEN_WALLET_MARKERS = [
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


class GateCheckError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the XRIQ Phase 1.2 UI mutation-control design gate."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for gate-check artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument("--readiness-summary", type=Path, default=None)
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase1-2-ui-mutation-gate-check-{timestamp}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as error:
        raise GateCheckError(f"required file is missing: {path}") from error


def require_markers(text: str, markers: list[str], context: str) -> list[str]:
    missing = [marker for marker in markers if marker not in text]
    if missing:
        raise GateCheckError(f"{context}: missing markers {missing}")
    return markers


def require_absent(text: str, markers: list[str], context: str) -> list[str]:
    found = [marker for marker in markers if marker.lower() in text.lower()]
    if found:
        raise GateCheckError(f"{context}: forbidden markers found {found}")
    return markers


def latest(pattern: str, description: str) -> Path:
    candidates = list(TARGET_DIR.glob(pattern))
    if not candidates:
        raise GateCheckError(f"no {description} found under {TARGET_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise GateCheckError(f"{description} does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise GateCheckError(f"{description} is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise GateCheckError(f"{description} must be a JSON object: {path}")
    return payload


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise GateCheckError(f"{context}: expected {key}={expected!r}, got {actual!r}")


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


def verify_readiness_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.2 readiness summary")
    require_equal(payload, "ok", "xriq-phase1-2-readiness-summary", "readiness")
    require_equal(payload, "ready_for_ui_mutation_design_review", True, "readiness")
    require_equal(payload, "ui_mutation_controls_enabled", False, "readiness")
    require_equal(payload, "safe_to_enable_ui_mutation_controls", False, "readiness")
    require_equal(payload, "approval_required_before_ui_mutation_controls", True, "readiness")
    require_equal(payload, "scope", "local-private-post-rc-hardening", "readiness")

    sensitive_fields = find_sensitive_fields(payload)
    if sensitive_fields:
        raise GateCheckError(f"readiness summary contains sensitive fields {sensitive_fields}")

    for key in ["refusal_summary", "wallet_send_accepted", "wallet_send_lifecycle"]:
        if not isinstance(payload.get(key), dict):
            raise GateCheckError(f"readiness: expected object at {key}")

    return {
        "path": str(path),
        "ready_for_ui_mutation_design_review": True,
        "ui_mutation_controls_enabled": False,
        "safe_to_enable_ui_mutation_controls": False,
        "approval_required_before_ui_mutation_controls": True,
        "wallet_send_tx_hash": payload["wallet_send_lifecycle"].get("wallet_send_tx_hash"),
    }


def verify_wallet_ui_source(text: str) -> dict[str, Any]:
    require_markers(text, REQUIRED_WALLET_MARKERS, "wallet UI")
    require_absent(text, FORBIDDEN_WALLET_MARKERS, "wallet UI")
    if 'type="button" disabled' not in text:
        raise GateCheckError("wallet UI: disabled submit/send button marker is missing")
    if 'onClick={onCheck} disabled={isChecking}' not in text:
        raise GateCheckError("wallet UI: guard-check button loading disable marker is missing")
    return {
        "required_markers_checked": len(REQUIRED_WALLET_MARKERS),
        "forbidden_markers_checked": len(FORBIDDEN_WALLET_MARKERS),
        "submit_send_buttons_disabled": True,
        "guard_check_only_active_action": True,
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
    try:
        gate_doc = read_text(GATE_DOC)
        plan_doc = read_text(PLAN_DOC)
        handoff_doc = read_text(HANDOFF_DOC)
        wallet_source = read_text(WALLET_UI)
        static_check = read_text(STATIC_CHECK)
        api_client = read_text(API_CLIENT)
        readiness_path = args.readiness_summary or latest(
            "xriq-phase1-2-readiness-summary-*/summary.json",
            "Phase 1.2 readiness summary",
        )

        require_markers(gate_doc, REQUIRED_GATE_MARKERS, "gate doc")
        require_markers(plan_doc, REQUIRED_PLAN_MARKERS, "Phase 1.2 plan")
        require_markers(
            handoff_doc,
            [
                "Latest native XRIQ Phase 1.2 readiness-summary checkpoint:",
                "Latest native XRIQ Phase 1.2 UI mutation-control gate checkpoint:",
                "Recommended next narrow step: wait for the user to explicitly approve",
                "local/private-devnet wallet-send UI mutation control behind the UI",
            ],
            "handoff",
        )
        wallet_check = verify_wallet_ui_source(wallet_source)
        require_markers(static_check, REQUIRED_STATIC_CHECK_MARKERS, "static UI guard")
        require_markers(api_client, REQUIRED_API_MARKERS, "API client")
        readiness = verify_readiness_summary(readiness_path)

        report = {
            "ok": "xriq-phase1-2-ui-mutation-control-gate-check",
            "artifact_dir": str(artifact_dir),
            "phase": "1.2",
            "scope": "local-private-post-rc-hardening",
            "gate_doc": str(GATE_DOC),
            "readiness_summary": readiness,
            "wallet_ui": wallet_check,
            "static_ui_guard_markers_checked": len(REQUIRED_STATIC_CHECK_MARKERS),
            "api_client_markers_checked": len(REQUIRED_API_MARKERS),
            "ui_mutation_controls_enabled": False,
            "safe_to_enable_ui_mutation_controls": False,
            "approval_required_before_ui_mutation_controls": True,
            "next": (
                "review the wallet-send UI implementation plan and require "
                "explicit approval before implementing any local/private wallet "
                "submit/send UI mutation control"
            ),
        }
        write_summary(artifact_dir / "summary.json", report)
    except GateCheckError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
