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
SENSITIVE_KEY_RE = re.compile(
    r"(private[_-]?key|seed[_-]?phrase|mnemonic|signature|signed[_-]?transaction)",
    re.IGNORECASE,
)

REQUIRED_REFUSAL_GUARDS = [
    "disabled_by_default",
    "mutation_none",
    "explicit_local_private_flag_required",
    "audit_event_required",
    "api_local_refusal_audit_recorded",
    "test_identity_only",
    "no_signing_or_custody_fields",
    "audit_event_expectations_present",
    "audit_metadata_forbids_sensitive_material",
    "block_production_disabled_by_default",
]

REQUIRED_LIFECYCLE_COMPLETED = [
    "wallet-send accepted",
    "wallet-send produced into local block",
    "wallet-send confirmed wallet status",
    "wallet-send lifecycle mempool empty",
    "serve-readonly wallet-send accepted",
    "serve-readonly wallet-send produced into local block",
    "serve-readonly wallet-send confirmed wallet status",
    "serve-readonly wallet-send lifecycle mempool empty",
    "serve-readonly wallet-send lifecycle network height",
]

REQUIRED_LIFECYCLE_ARTIFACTS = [
    "wallet_send_accepted",
    "wallet_send_produced_block",
    "wallet_send_confirmed_status",
    "mempool_empty",
    "serve_readonly_wallet_send_accepted",
    "serve_readonly_wallet_send_produced_block",
    "serve_readonly_wallet_send_confirmed_status",
    "serve_readonly_mempool_empty",
    "serve_readonly_network",
]


class ReadinessError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize XRIQ Phase 1.2 local/private readiness evidence without "
            "enabling UI mutation controls."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for readiness summary artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument("--refusal-summary", type=Path, default=None)
    parser.add_argument("--wallet-send-accepted", type=Path, default=None)
    parser.add_argument("--lifecycle-summary", type=Path, default=None)
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase1-2-readiness-summary-{timestamp}"


def latest(pattern: str, description: str) -> Path:
    candidates = list(TARGET_DIR.glob(pattern))
    if not candidates:
        raise ReadinessError(f"no {description} found under {TARGET_DIR}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_json_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ReadinessError(f"{description} does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ReadinessError(f"{description} is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ReadinessError(f"{description} must be a JSON object: {path}")
    return payload


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise ReadinessError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_hash(value: Any, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ReadinessError(f"{context}: expected 64-character lowercase hash, got {value!r}")
    return value


def existing_path(path_text: Any, context: str) -> Path:
    if not isinstance(path_text, str) or not path_text:
        raise ReadinessError(f"{context}: expected non-empty artifact path")
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise ReadinessError(f"{context}: artifact does not exist: {path}")
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


def verify_refusal_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.2 refusal summary")
    require_equal(payload, "ok", "xriq-phase1-2-refusal-smoke", "refusal summary")
    require_equal(payload, "disabled_fixtures_checked", 3, "refusal summary")
    require_equal(payload, "audit_expectations_checked", 3, "refusal summary")
    require_equal(payload, "fixtures_checked", 6, "refusal summary")

    guards = payload.get("guards")
    if not isinstance(guards, list):
        raise ReadinessError("refusal summary: guards must be a list")
    missing_guards = [guard for guard in REQUIRED_REFUSAL_GUARDS if guard not in guards]
    if missing_guards:
        raise ReadinessError(f"refusal summary: missing guards {missing_guards}")

    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list):
        raise ReadinessError("refusal summary: fixtures must be a list")
    fixture_codes = {fixture.get("code") for fixture in fixtures if isinstance(fixture, dict)}
    expected_codes = {
        "wallet_submit_disabled",
        "wallet_send_disabled",
        "block_production_disabled",
    }
    if fixture_codes != expected_codes:
        raise ReadinessError(f"refusal summary: expected fixture codes {expected_codes}")

    audit_expectations = payload.get("audit_expectations")
    if not isinstance(audit_expectations, list):
        raise ReadinessError("refusal summary: audit_expectations must be a list")
    audit_actions = {
        item.get("action") for item in audit_expectations if isinstance(item, dict)
    }
    expected_actions = {
        "wallet_transfer_submit_attempt",
        "wallet_transfer_send_attempt",
        "block_production_attempt",
    }
    if audit_actions != expected_actions:
        raise ReadinessError(f"refusal summary: expected audit actions {expected_actions}")

    return {
        "path": str(path),
        "disabled_fixtures_checked": payload["disabled_fixtures_checked"],
        "audit_expectations_checked": payload["audit_expectations_checked"],
        "guards_checked": len(REQUIRED_REFUSAL_GUARDS),
    }


def verify_wallet_send_accepted(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "wallet-send accepted artifact")
    require_equal(payload, "environment", "private-devnet", "wallet-send accepted")
    require_equal(payload, "network", "xriq-devnet", "wallet-send accepted")
    require_equal(
        payload,
        "endpoint",
        "POST /api/v1/wallet/transfers/send",
        "wallet-send accepted",
    )
    require_equal(payload, "code", "wallet_send_accepted_local_only", "wallet-send accepted")
    require_equal(payload, "status", "pending", "wallet-send accepted")
    require_equal(payload, "mutation", "pending_state_only", "wallet-send accepted")
    require_equal(payload, "audit_event_recorded", True, "wallet-send accepted")

    transaction = payload.get("transaction")
    pending_state = payload.get("pending_state")
    chain_state = payload.get("chain_state")
    audit_event = payload.get("audit_event")
    if not all(isinstance(item, dict) for item in [transaction, pending_state, chain_state, audit_event]):
        raise ReadinessError("wallet-send accepted: expected transaction, state, and audit objects")
    tx_hash = require_hash(transaction.get("tx_hash"), "wallet-send accepted tx_hash")
    require_equal(transaction, "status", "pending", "wallet-send accepted transaction")
    require_equal(transaction, "block_height", None, "wallet-send accepted transaction")
    require_equal(transaction, "transaction_index", None, "wallet-send accepted transaction")
    require_equal(pending_state, "before_count", 0, "wallet-send accepted pending")
    require_equal(pending_state, "after_count", 1, "wallet-send accepted pending")
    require_equal(pending_state, "added_tx_hash", tx_hash, "wallet-send accepted pending")
    require_equal(chain_state, "chain_unchanged", True, "wallet-send accepted chain")
    require_equal(audit_event, "action", "wallet_transfer_send_attempt", "wallet-send audit")
    require_equal(audit_event, "resource_id", "local_request_id", "wallet-send audit")

    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise ReadinessError("wallet-send accepted: expected audit metadata object")
    require_equal(metadata, "explicit_flag", "--enable-local-wallet-send", "wallet-send audit")
    require_equal(metadata, "outcome", "accepted", "wallet-send audit")
    require_equal(metadata, "status", "pending", "wallet-send audit")
    require_equal(metadata, "added_tx_hash", tx_hash, "wallet-send audit")

    sensitive_fields = find_sensitive_fields(payload)
    if sensitive_fields:
        raise ReadinessError(f"wallet-send accepted: sensitive fields found {sensitive_fields}")

    existing_path(pending_state.get("pending_file"), "wallet-send accepted pending file")
    existing_path(chain_state.get("chain_file"), "wallet-send accepted chain file")
    return {
        "path": str(path),
        "tx_hash": tx_hash,
        "pending_file": pending_state["pending_file"],
        "chain_file": chain_state["chain_file"],
    }


def verify_confirmed_status(path: Path, tx_hash: str, context: str) -> None:
    payload = load_json_object(path, context)
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "tx_hash", tx_hash, context)
    require_equal(payload, "status", "confirmed", context)
    require_equal(payload, "block_height", 2, context)
    require_hash(payload.get("block_hash"), f"{context} block_hash")
    require_equal(payload, "transaction_index", 0, context)


def verify_block(path: Path, tx_hash: str, context: str) -> None:
    payload = load_json_object(path, context)
    require_equal(payload, "code", "block_production_accepted_local_only", context)
    require_equal(payload, "status", "confirmed", context)
    require_equal(payload, "mutation", "chain_and_pending_state_local_only", context)
    confirmed_transactions = payload.get("confirmed_transactions")
    if not isinstance(confirmed_transactions, list) or len(confirmed_transactions) != 1:
        raise ReadinessError(f"{context}: expected exactly one confirmed transaction")
    confirmed = confirmed_transactions[0]
    if not isinstance(confirmed, dict):
        raise ReadinessError(f"{context}: confirmed transaction must be an object")
    require_equal(confirmed, "tx_hash", tx_hash, context)
    require_equal(confirmed, "status", "confirmed", context)
    require_equal(confirmed, "block_height", 2, context)
    pending_state = payload.get("pending_state")
    if not isinstance(pending_state, dict):
        raise ReadinessError(f"{context}: expected pending_state object")
    require_equal(pending_state, "before_count", 1, context)
    require_equal(pending_state, "after_count", 0, context)
    if pending_state.get("removed_tx_hashes") != [tx_hash]:
        raise ReadinessError(f"{context}: removed_tx_hashes did not match {tx_hash}")


def verify_mempool_empty(path: Path, context: str) -> None:
    payload = load_json_object(path, context)
    require_equal(payload, "pending_count", 0, context)
    entries = payload.get("entries")
    if entries != []:
        raise ReadinessError(f"{context}: expected empty entries list")


def verify_lifecycle_summary(path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "wallet-send lifecycle summary")
    require_equal(payload, "ok", "xriq-phase1-2-wallet-send-lifecycle-smoke", "lifecycle")
    tx_hash = require_hash(payload.get("wallet_send_tx_hash"), "lifecycle wallet_send_tx_hash")
    server_tx_hash = require_hash(
        payload.get("serve_readonly_wallet_send_tx_hash"),
        "lifecycle serve_readonly_wallet_send_tx_hash",
    )
    if server_tx_hash != tx_hash:
        raise ReadinessError("lifecycle: request-mode and serve-readonly tx hashes differ")

    completed = payload.get("completed")
    if not isinstance(completed, list):
        raise ReadinessError("lifecycle: completed must be a list")
    missing_completed = [step for step in REQUIRED_LIFECYCLE_COMPLETED if step not in completed]
    if missing_completed:
        raise ReadinessError(f"lifecycle: missing completed steps {missing_completed}")

    guards = payload.get("guards")
    if not isinstance(guards, list):
        raise ReadinessError("lifecycle: guards must be a list")
    for guard in [
        "wallet send requires --enable-local-wallet-send",
        "block production requires --enable-local-block-production",
        "serve-readonly uses explicit local wallet-send and block-production flags",
        "no UI mutation control is enabled",
        "no signing material or custody material is accepted",
    ]:
        if guard not in guards:
            raise ReadinessError(f"lifecycle: missing guard {guard!r}")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ReadinessError("lifecycle: artifacts must be an object")
    artifact_paths: dict[str, Path] = {}
    for key in REQUIRED_LIFECYCLE_ARTIFACTS:
        artifact_paths[key] = existing_path(artifacts.get(key), f"lifecycle artifact {key}")

    verify_block(artifact_paths["wallet_send_produced_block"], tx_hash, "request block")
    verify_confirmed_status(
        artifact_paths["wallet_send_confirmed_status"],
        tx_hash,
        "request confirmed status",
    )
    verify_mempool_empty(artifact_paths["mempool_empty"], "request mempool empty")
    verify_block(
        artifact_paths["serve_readonly_wallet_send_produced_block"],
        tx_hash,
        "serve-readonly block",
    )
    verify_confirmed_status(
        artifact_paths["serve_readonly_wallet_send_confirmed_status"],
        tx_hash,
        "serve-readonly confirmed status",
    )
    verify_mempool_empty(
        artifact_paths["serve_readonly_mempool_empty"],
        "serve-readonly mempool empty",
    )
    network = load_json_object(artifact_paths["serve_readonly_network"], "serve-readonly network")
    require_equal(network, "current_height", 2, "serve-readonly network")

    for path_value, context in [
        (payload.get("chain_file"), "request chain file"),
        (payload.get("pending_file"), "request pending file"),
        (payload.get("serve_readonly_chain_file"), "serve-readonly chain file"),
        (payload.get("serve_readonly_pending_file"), "serve-readonly pending file"),
    ]:
        existing_path(path_value, context)

    return {
        "path": str(path),
        "wallet_send_tx_hash": tx_hash,
        "completed_steps": len(completed),
        "artifacts_checked": len(REQUIRED_LIFECYCLE_ARTIFACTS),
        "serve_readonly_verified": True,
    }


def write_summary(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
    try:
        refusal_summary = args.refusal_summary or latest(
            "xriq-phase1-2-refusal-smoke-*/summary.json",
            "Phase 1.2 refusal smoke summary",
        )
        wallet_send_accepted = args.wallet_send_accepted or latest(
            "xriq-phase1-2-wallet-send-smoke-*/api/wallet-send-accepted-local.json",
            "Phase 1.2 wallet-send accepted artifact",
        )
        lifecycle_summary = args.lifecycle_summary or latest(
            "xriq-phase1-2-wallet-send-lifecycle-smoke-*/summary.json",
            "Phase 1.2 wallet-send lifecycle summary",
        )
        refusal = verify_refusal_summary(refusal_summary)
        accepted = verify_wallet_send_accepted(wallet_send_accepted)
        lifecycle = verify_lifecycle_summary(lifecycle_summary)
        if accepted["tx_hash"] != lifecycle["wallet_send_tx_hash"]:
            raise ReadinessError(
                "accepted wallet-send tx hash does not match latest lifecycle tx hash"
            )
        report = {
            "ok": "xriq-phase1-2-readiness-summary",
            "artifact_dir": str(artifact_dir),
            "phase": "1.2",
            "scope": "local-private-post-rc-hardening",
            "refusal_summary": refusal,
            "wallet_send_accepted": accepted,
            "wallet_send_lifecycle": lifecycle,
            "ready_for_ui_mutation_design_review": True,
            "ui_mutation_controls_enabled": False,
            "safe_to_enable_ui_mutation_controls": False,
            "approval_required_before_ui_mutation_controls": True,
            "blocked_scope": [
                "public mainnet",
                "DEX",
                "bridges",
                "custody",
                "smart contracts",
                "snapshot mutation",
                "exchange listings",
                "production infrastructure",
            ],
            "next": (
                "run the wallet-send UI implementation, live-smoke, refresh-smoke, "
                "and block-production UI design checks before considering any "
                "additional UI mutation-control scope"
            ),
        }
        write_summary(artifact_dir / "summary.json", report)
    except ReadinessError as error:
        print(json.dumps({"ok": False, "error": str(error)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
