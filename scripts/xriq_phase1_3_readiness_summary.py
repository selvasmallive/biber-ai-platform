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

from xriq_phase1_3_behavior_contract_check import FIXTURE_PATH, verify_contract


ROOT = Path(__file__).resolve().parents[1]
TARGET_DIR = ROOT / "xriq" / "target"
PROPOSED_TAG = "phase1-3-xriq-local-private-behavior-rc1"
APPROVAL_PHRASE = (
    "I explicitly approve creating and pushing the Phase 1.3 RC tag "
    "phase1-3-xriq-local-private-behavior-rc1."
)

SENSITIVE_KEY_RE = re.compile(
    r"(private[_-]?key|seed[_-]?phrase|mnemonic|signature|signed[_-]?transaction)",
    re.IGNORECASE,
)

REQUIRED_CPU_COMPLETED = [
    "validated Phase 1.3 behavior fixture",
    "created base confirmed transfer",
    "wallet send accepted to pending",
    "wallet send pending status",
    "produced one local block",
    "wallet send confirmed status",
    "mempool empty after production",
    "network height after production",
    "explorer overview after production",
    "wallet account balances after production",
    "wallet history after production",
    "admin audit visibility",
    "negative behavior matrix",
]

REQUIRED_CPU_GUARDS = [
    "CPU-only request-mode smoke",
    "wallet send requires --enable-local-wallet-send true",
    "block production requires --enable-local-block-production true",
    "wallet submit UI remains deferred",
    "default mutation paths remain refused",
    "no Docker, browser, server, GCP, Vast, tag, public, DEX, or custody scope",
]

REQUIRED_UI_COMPLETED = [
    "validated Phase 1.3 behavior fixture",
    "created base confirmed transfer",
    "serve-readonly wallet-send and block-production API started",
    "UI shared-client behavior smoke passed",
    "pending file cleared after produced block",
    "API network and mempool remain consistent after UI smoke",
]

REQUIRED_UI_GUARDS = [
    "UI behavior smoke requires both Phase 1.3 Vite feature switches",
    "temporary API enables only local wallet-send and block-production flags",
    "wallet submit remains disabled and deferred",
    "UI source uses shared TypeScript API client helpers",
    "wallet and Admin UI source have no direct mutation fetch calls",
    "wallet rows show pending before the block and confirmed after the block",
    "Admin rows show pending count moving from one to zero",
    "no-pending block-production refusal leaves state unchanged",
    "no signing material or custody material is accepted",
    "no Docker, browser, GCP, Vast, public, DEX, or custody scope",
]

REQUIRED_UI_ARTIFACT_KEYS = [
    "contract_fixture",
    "base_confirmed_transfer",
    "ui_summary",
    "ui_wallet_send",
    "ui_produced_block",
    "ui_confirmed_status",
    "ui_balances",
    "ui_histories",
    "ui_no_pending_refusal",
    "network_after_ui_behavior",
    "mempool_empty_after_ui_behavior",
]

REQUIRED_UI_LIVE_ARTIFACT_KEYS = [
    "wallet_submit_refusal",
    "wallet_send",
    "snapshot_before",
    "pending_status",
    "wallet_rows_before",
    "admin_rows_before",
    "produced_block",
    "confirmed_status",
    "snapshot_after",
    "wallet_rows_after",
    "admin_rows_after",
    "balances",
    "histories",
    "no_pending_refusal",
    "snapshot_after_no_pending_refusal",
]

NEGATIVE_CASE_FILES = {
    "default_wallet_send_disabled": "default-wallet-send-disabled.json",
    "default_block_production_disabled": "default-block-production-disabled.json",
    "wallet_submit_ui_deferred": "wallet-submit-deferred.json",
    "no_pending_block_production": "no-pending-block-production.json",
    "invalid_wallet_send_request": "invalid-wallet-send-request.json",
}

REQUIRED_DOC_REFERENCES = {
    "README.md": [
        "scripts/xriq_phase1_3_readiness_summary.py",
        "xriq/fixtures/phase1_3/local-wallet-behavior-v1.json",
    ],
    "xriq/README.md": [
        "../scripts/xriq_phase1_3_readiness_summary.py",
        "fixtures/phase1_3/local-wallet-behavior-v1.json",
    ],
    "docs/XRIQ_PHASE1_3_LOCAL_PRIVATE_BEHAVIOR_PLAN.md": [
        "python scripts/xriq_phase1_3_readiness_summary.py",
        PROPOSED_TAG,
        "Do not create, move, delete, recreate, or push any tag",
    ],
    "docs/CODEX_HANDOFF.md": [
        "scripts/xriq_phase1_3_readiness_summary.py",
        PROPOSED_TAG,
        "generic continue",
    ],
}


class ReadinessError(RuntimeError):
    pass


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize XRIQ Phase 1.3 local/private behavior readiness evidence "
            "without creating tags or enabling new product scope."
        )
    )
    parser.add_argument("--fixture", type=Path, default=FIXTURE_PATH)
    parser.add_argument("--contract-summary", type=Path, default=None)
    parser.add_argument("--cpu-smoke-summary", type=Path, default=None)
    parser.add_argument("--ui-smoke-summary", type=Path, default=None)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for readiness summary output. Defaults under xriq/target/.",
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


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return TARGET_DIR / f"xriq-phase1-3-readiness-summary-{timestamp}"


def latest_summary(pattern: str, description: str, command_hint: str) -> Path:
    candidates = list(TARGET_DIR.glob(pattern))
    if not candidates:
        raise ReadinessError(
            f"no {description} found under xriq/target; run {command_hint} first"
        )
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise ReadinessError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_hash(value: Any, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ReadinessError(f"{context}: expected 64-character lowercase hash, got {value!r}")
    return value


def require_list_contains(values: Any, required: list[str], context: str) -> None:
    if not isinstance(values, list):
        raise ReadinessError(f"{context}: expected list")
    missing = [item for item in required if item not in values]
    if missing:
        raise ReadinessError(f"{context}: missing items {missing}")


def require_path_exists(path_text: Any, context: str) -> Path:
    if not isinstance(path_text, str) or not path_text:
        raise ReadinessError(f"{context}: expected non-empty path")
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise ReadinessError(f"{context}: path does not exist: {path}")
    return path


def same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except FileNotFoundError:
        return left.absolute() == right.absolute()


def require_same_path(path_text: Any, expected: Path, context: str) -> Path:
    path = require_path_exists(path_text, context)
    expected_path = expected if expected.is_absolute() else ROOT / expected
    if not same_path(path, expected_path):
        raise ReadinessError(f"{context}: expected {expected_path}, got {path}")
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


def assert_no_sensitive_fields(payload: dict[str, Any], context: str) -> None:
    sensitive = find_sensitive_fields(payload)
    if sensitive:
        raise ReadinessError(f"{context}: sensitive field names found: {sensitive}")


def load_fixture(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = load_json_object(path, "Phase 1.3 behavior fixture")
    try:
        contract_result = verify_contract(payload)
    except Exception as error:
        raise ReadinessError(f"Phase 1.3 behavior fixture contract failed: {error}") from error
    return payload, contract_result


def fixture_step(fixture: dict[str, Any], step_name: str) -> dict[str, Any]:
    flow = fixture.get("behavior_flow")
    if not isinstance(flow, list):
        raise ReadinessError("fixture behavior_flow must be a list")
    for step in flow:
        if isinstance(step, dict) and step.get("step") == step_name:
            return step
    raise ReadinessError(f"fixture missing behavior step {step_name!r}")


def fixture_negative_cases(fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases = fixture.get("negative_matrix")
    if not isinstance(cases, list):
        raise ReadinessError("fixture negative_matrix must be a list")
    result: dict[str, dict[str, Any]] = {}
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("case"), str):
            raise ReadinessError("fixture negative_matrix entries must be objects with case")
        result[case["case"]] = case
    missing = sorted(set(NEGATIVE_CASE_FILES).difference(result))
    if missing:
        raise ReadinessError(f"fixture negative_matrix missing cases {missing}")
    return result


def verify_contract_summary(path: Path, fixture_path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.3 contract summary")
    require_equal(payload, "ok", "xriq-phase1-3-behavior-contract-check", "contract summary")
    require_equal(payload, "approved_local_switches_checked", 4, "contract summary")
    require_equal(payload, "behavior_steps_checked", 2, "contract summary")
    require_equal(payload, "negative_cases_checked", 5, "contract summary")
    require_equal(payload, "forbidden_scope_markers_checked", 11, "contract summary")
    require_equal(payload, "post_block_accounts_checked", 4, "contract summary")
    require_same_path(payload.get("fixture"), fixture_path, "contract summary fixture")
    require_path_exists(payload.get("artifact_dir"), "contract summary artifact_dir")
    assert_no_sensitive_fields(payload, "contract summary")
    return {
        "path": str(path),
        "approved_local_switches_checked": payload["approved_local_switches_checked"],
        "behavior_steps_checked": payload["behavior_steps_checked"],
        "negative_cases_checked": payload["negative_cases_checked"],
    }


def verify_cpu_smoke(path: Path, fixture: dict[str, Any], fixture_path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.3 CPU behavior smoke summary")
    require_equal(payload, "ok", "xriq-phase1-3-wallet-behavior-smoke", "CPU smoke")
    require_same_path(payload.get("fixture"), fixture_path, "CPU smoke fixture")
    require_list_contains(payload.get("completed"), REQUIRED_CPU_COMPLETED, "CPU smoke completed")
    require_list_contains(payload.get("guards"), REQUIRED_CPU_GUARDS, "CPU smoke guards")
    base_tx_hash = require_hash(payload.get("base_confirmed_tx_hash"), "CPU smoke base tx hash")
    tx_hash = require_hash(payload.get("wallet_send_tx_hash"), "CPU smoke behavior tx hash")
    block_hash = require_hash(payload.get("produced_block_hash"), "CPU smoke block hash")

    artifact_dir = require_path_exists(payload.get("artifact_dir"), "CPU smoke artifact_dir")
    pending_file = require_path_exists(payload.get("pending_file"), "CPU smoke pending_file")
    if pending_file.read_text(encoding="utf-8") != "":
        raise ReadinessError("CPU smoke pending file must be empty after block production")
    require_path_exists(payload.get("chain_file"), "CPU smoke chain_file")

    api_dir = artifact_dir / "api"
    negative_dir = artifact_dir / "negative"
    verify_cpu_positive_artifacts(api_dir, fixture, tx_hash, block_hash)
    negative_cases = verify_negative_matrix(negative_dir, fixture, tx_hash)
    assert_no_sensitive_fields(payload, "CPU smoke summary")

    return {
        "path": str(path),
        "artifact_dir": str(artifact_dir),
        "base_confirmed_tx_hash": base_tx_hash,
        "wallet_send_tx_hash": tx_hash,
        "produced_block_hash": block_hash,
        "completed_checks": len(REQUIRED_CPU_COMPLETED),
        "guards_checked": len(REQUIRED_CPU_GUARDS),
        "negative_cases": negative_cases,
    }


def verify_cpu_positive_artifacts(
    api_dir: Path,
    fixture: dict[str, Any],
    tx_hash: str,
    block_hash: str,
) -> None:
    send_step = fixture_step(fixture, "wallet_send_to_pending")
    block_step = fixture_step(fixture, "produce_one_block")
    post_block = fixture["post_block_expectations"]

    wallet_send = load_json_object(api_dir / "wallet-send-accepted-local.json", "CPU wallet send")
    require_equal(wallet_send, "code", send_step["expected"]["code"], "CPU wallet send")
    require_equal(wallet_send, "status", "pending", "CPU wallet send")
    require_equal(wallet_send, "mutation", "pending_state_only", "CPU wallet send")
    require_equal(wallet_send.get("transaction", {}), "tx_hash", tx_hash, "CPU wallet send")
    require_equal(wallet_send.get("audit_event", {}), "action", "wallet_transfer_send_attempt", "CPU wallet send")

    pending_status = load_json_object(api_dir / "wallet-send-pending-status.json", "CPU pending status")
    require_equal(pending_status, "tx_hash", tx_hash, "CPU pending status")
    require_equal(pending_status, "status", "pending", "CPU pending status")
    require_equal(pending_status, "block_height", None, "CPU pending status")

    produced_block = load_json_object(api_dir / "block-production-accepted-local.json", "CPU block")
    require_equal(produced_block, "code", block_step["expected"]["code"], "CPU block")
    require_equal(produced_block, "status", "confirmed", "CPU block")
    require_equal(produced_block, "mutation", "chain_and_pending_state_local_only", "CPU block")
    require_equal(produced_block.get("block", {}), "block_hash", block_hash, "CPU block")
    require_equal(produced_block.get("block", {}), "height", 2, "CPU block")

    confirmed_status = load_json_object(api_dir / "wallet-send-confirmed-status.json", "CPU confirmed status")
    require_equal(confirmed_status, "tx_hash", tx_hash, "CPU confirmed status")
    require_equal(confirmed_status, "status", "confirmed", "CPU confirmed status")
    require_equal(confirmed_status, "block_height", 2, "CPU confirmed status")
    require_equal(confirmed_status, "transaction_index", 0, "CPU confirmed status")

    mempool = load_json_object(api_dir / "mempool-empty-after-production.json", "CPU mempool")
    require_equal(mempool, "pending_count", 0, "CPU mempool")
    network = load_json_object(api_dir / "network-after-production.json", "CPU network")
    require_equal(network, "current_height", 2, "CPU network")
    overview = load_json_object(api_dir / "explorer-overview-after-production.json", "CPU overview")
    require_equal(overview.get("chain", {}), "current_height", 2, "CPU overview")
    require_equal(overview.get("totals", {}), "transactions", 2, "CPU overview")

    for account in post_block["accounts"]:
        balance = load_json_object(
            api_dir / f"wallet-balance-{account['address']}.json",
            f"CPU balance {account['address']}",
        )
        require_equal(balance, "balance_base_units", account["balance_base_units"], "CPU balance")
        require_equal(balance, "nonce", account["nonce"], "CPU balance")

    history_expected = post_block["wallet_history"]
    sender_history = load_json_object(api_dir / "wallet-history-sender.json", "CPU sender history")
    recipient_history = load_json_object(api_dir / "wallet-history-recipient.json", "CPU recipient history")
    require_history_row(sender_history, tx_hash, history_expected["behavior_transaction_direction"], "CPU sender history")
    require_history_row(recipient_history, tx_hash, history_expected["recipient_transaction_direction"], "CPU recipient history")

    admin_audit = load_json_object(api_dir / "admin-audit-events.json", "CPU admin audit")
    local_events = admin_audit.get("local_refusal_audit_events")
    if not isinstance(local_events, list) or len(local_events) < 3:
        raise ReadinessError("CPU admin audit: expected local refusal audit events")


def require_history_row(history: dict[str, Any], tx_hash: str, direction: str, context: str) -> None:
    transactions = history.get("transactions")
    if not isinstance(transactions, list):
        raise ReadinessError(f"{context}: transactions must be a list")
    if not any(
        isinstance(row, dict)
        and row.get("tx_hash") == tx_hash
        and row.get("direction") == direction
        for row in transactions
    ):
        raise ReadinessError(f"{context}: missing {direction} row for {tx_hash}")


def verify_negative_matrix(
    negative_dir: Path,
    fixture: dict[str, Any],
    tx_hash: str,
) -> dict[str, dict[str, Any]]:
    if not negative_dir.exists():
        raise ReadinessError(f"CPU negative directory missing: {negative_dir}")
    fixture_cases = fixture_negative_cases(fixture)
    result: dict[str, dict[str, Any]] = {}
    for case_name, file_name in NEGATIVE_CASE_FILES.items():
        case = fixture_cases[case_name]
        payload = load_json_object(negative_dir / file_name, f"negative case {case_name}")
        expected_code = case["expected_code"]
        error = payload.get("error")
        if isinstance(error, dict):
            require_equal(error, "code", expected_code, f"negative case {case_name}")
            observed_mutation = "none"
        else:
            require_equal(payload, "environment", "private-devnet", f"negative case {case_name}")
            require_equal(payload, "network", "xriq-devnet", f"negative case {case_name}")
            require_equal(payload, "code", expected_code, f"negative case {case_name}")
            require_equal(payload, "mutation", "none", f"negative case {case_name}")
            require_equal(payload, "enabled", False, f"negative case {case_name}")
            require_equal(payload, "audit_event_recorded", True, f"negative case {case_name}")
            observed_mutation = payload["mutation"]
        assert_no_sensitive_fields(payload, f"negative case {case_name}")
        result[case_name] = {
            "path": str(negative_dir / file_name),
            "expected_code": expected_code,
            "expected_mutation": case["expected_mutation"],
            "observed_mutation": observed_mutation,
            "endpoint": case["endpoint"],
        }

    empty_pending = negative_dir.parent / "phase1-3-empty-pending.tsv"
    if empty_pending.exists():
        empty_pending_text = empty_pending.read_text(encoding="utf-8")
        if empty_pending_text != "":
            raise ReadinessError("no-pending negative pending file must remain empty")
        if tx_hash and tx_hash in empty_pending_text:
            raise ReadinessError("no-pending negative pending file must not include behavior tx")
    return result


def verify_ui_smoke(path: Path, fixture: dict[str, Any], fixture_path: Path) -> dict[str, Any]:
    payload = load_json_object(path, "Phase 1.3 UI behavior smoke summary")
    require_equal(payload, "ok", "xriq-phase1-3-wallet-behavior-ui-smoke", "UI smoke")
    require_same_path(payload.get("fixture"), fixture_path, "UI smoke fixture")
    require_list_contains(payload.get("completed"), REQUIRED_UI_COMPLETED, "UI smoke completed")
    require_list_contains(payload.get("guards"), REQUIRED_UI_GUARDS, "UI smoke guards")
    base_tx_hash = require_hash(payload.get("base_confirmed_tx_hash"), "UI smoke base tx hash")
    tx_hash = require_hash(payload.get("wallet_send_tx_hash"), "UI smoke behavior tx hash")
    block_hash = require_hash(payload.get("produced_block_hash"), "UI smoke block hash")

    artifact_dir = require_path_exists(payload.get("artifact_dir"), "UI smoke artifact_dir")
    pending_file = require_path_exists(payload.get("pending_file"), "UI smoke pending_file")
    if pending_file.read_text(encoding="utf-8") != "":
        raise ReadinessError("UI smoke pending file must be empty after block production")
    require_path_exists(payload.get("chain_file"), "UI smoke chain_file")

    feature_switches = payload.get("feature_switches")
    if not isinstance(feature_switches, dict):
        raise ReadinessError("UI smoke feature_switches must be an object")
    require_equal(
        feature_switches,
        "wallet_send_ui",
        "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
        "UI smoke feature switches",
    )
    require_equal(
        feature_switches,
        "block_production_ui",
        "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "UI smoke feature switches",
    )

    flags = payload.get("serve_readonly_flags")
    if not isinstance(flags, dict):
        raise ReadinessError("UI smoke serve_readonly_flags must be an object")
    require_equal(flags, "enable_local_wallet_send", True, "UI smoke serve_readonly flags")
    require_equal(flags, "enable_local_wallet_submit", False, "UI smoke serve_readonly flags")
    require_equal(flags, "enable_local_block_production", True, "UI smoke serve_readonly flags")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ReadinessError("UI smoke artifacts must be an object")
    missing_keys = [key for key in REQUIRED_UI_ARTIFACT_KEYS if key not in artifacts]
    if missing_keys:
        raise ReadinessError(f"UI smoke artifacts missing keys {missing_keys}")
    artifact_paths = {key: require_path_exists(artifacts[key], f"UI smoke artifact {key}") for key in REQUIRED_UI_ARTIFACT_KEYS}

    ui_live = load_json_object(artifact_paths["ui_summary"], "UI live summary")
    verify_ui_live_summary(ui_live, fixture, tx_hash, block_hash)
    assert_no_sensitive_fields(payload, "UI smoke summary")

    return {
        "path": str(path),
        "artifact_dir": str(artifact_dir),
        "base_confirmed_tx_hash": base_tx_hash,
        "wallet_send_tx_hash": tx_hash,
        "produced_block_hash": block_hash,
        "completed_checks": len(REQUIRED_UI_COMPLETED),
        "guards_checked": len(REQUIRED_UI_GUARDS),
        "ui_live_summary": str(artifact_paths["ui_summary"]),
        "artifact_keys_checked": len(REQUIRED_UI_ARTIFACT_KEYS),
    }


def verify_ui_live_summary(
    payload: dict[str, Any],
    fixture: dict[str, Any],
    tx_hash: str,
    block_hash: str,
) -> None:
    require_equal(payload, "ok", "xriq-phase1-3-wallet-behavior-ui-live", "UI live summary")
    require_equal(payload, "shared_client_flow", True, "UI live summary")
    require_equal(payload, "wallet_submit_deferred", True, "UI live summary")
    require_equal(payload, "default_controls_disabled_by_source", True, "UI live summary")
    require_equal(payload, "wallet_send_tx_hash", tx_hash, "UI live summary")
    require_equal(payload, "produced_block_hash", block_hash, "UI live summary")

    send_step = fixture_step(fixture, "wallet_send_to_pending")
    block_step = fixture_step(fixture, "produce_one_block")
    require_equal(payload, "wallet_local_request_id", send_step["local_request_id"], "UI live summary")
    require_equal(payload, "block_local_request_id", block_step["local_request_id"], "UI live summary")

    before = payload.get("refresh_before_block")
    if not isinstance(before, dict):
        raise ReadinessError("UI live summary refresh_before_block must be an object")
    require_equal(before, "current_height", 1, "UI live before")
    require_equal(before, "mempool_pending_count", 1, "UI live before")
    require_equal(before, "wallet_pending_transactions", 1, "UI live before")
    require_equal(before, "transaction_status", "pending", "UI live before")
    require_equal(before, "sender_activity_source", "pending", "UI live before")
    require_equal(before, "recipient_activity_source", "pending", "UI live before")

    expected_explorer = fixture["post_block_expectations"]["explorer"]
    after = payload.get("refresh_after_block")
    if not isinstance(after, dict):
        raise ReadinessError("UI live summary refresh_after_block must be an object")
    require_equal(after, "current_height", expected_explorer["current_height"], "UI live after")
    require_equal(after, "stored_blocks", expected_explorer["stored_blocks"], "UI live after")
    require_equal(after, "confirmed_transactions", expected_explorer["confirmed_transactions"], "UI live after")
    require_equal(after, "mempool_pending_count", expected_explorer["pending_transactions"], "UI live after")
    require_equal(after, "wallet_pending_transactions", 0, "UI live after")
    require_equal(after, "transaction_status", "confirmed", "UI live after")
    require_equal(after, "transaction_block_height", expected_explorer["current_height"], "UI live after")
    require_equal(after, "transaction_index", 0, "UI live after")
    require_equal(after, "sender_activity_source", "confirmed", "UI live after")
    require_equal(after, "recipient_activity_source", "confirmed", "UI live after")

    balances = payload.get("balances")
    if not isinstance(balances, dict):
        raise ReadinessError("UI live summary balances must be an object")
    for account in fixture["post_block_expectations"]["accounts"]:
        balance = balances.get(account["address"])
        if not isinstance(balance, dict):
            raise ReadinessError(f"UI live summary missing balance for {account['address']}")
        require_equal(balance, "balance_base_units", account["balance_base_units"], "UI live balance")
        require_equal(balance, "nonce", account["nonce"], "UI live balance")

    no_pending = payload.get("no_pending_refusal")
    if not isinstance(no_pending, dict):
        raise ReadinessError("UI live summary no_pending_refusal must be an object")
    require_equal(no_pending, "code", "no_pending_transactions", "UI live no pending")
    require_equal(no_pending, "state_unchanged", True, "UI live no pending")

    source_guards = payload.get("source_guards")
    if not isinstance(source_guards, dict):
        raise ReadinessError("UI live summary source_guards must be an object")
    require_equal(source_guards, "shared_api_client", True, "UI live source guards")
    require_equal(source_guards, "direct_wallet_fetch", False, "UI live source guards")
    require_equal(source_guards, "direct_admin_fetch", False, "UI live source guards")
    require_equal(source_guards, "browser_persistence", False, "UI live source guards")
    require_equal(source_guards, "sensitive_signing_fields", False, "UI live source guards")

    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ReadinessError("UI live summary artifacts must be an object")
    missing_keys = [key for key in REQUIRED_UI_LIVE_ARTIFACT_KEYS if key not in artifacts]
    if missing_keys:
        raise ReadinessError(f"UI live summary artifacts missing keys {missing_keys}")
    for key in REQUIRED_UI_LIVE_ARTIFACT_KEYS:
        require_path_exists(artifacts[key], f"UI live artifact {key}")
    assert_no_sensitive_fields(payload, "UI live summary")


def verify_docs() -> dict[str, list[str]]:
    checked: dict[str, list[str]] = {}
    for relative_path, markers in REQUIRED_DOC_REFERENCES.items():
        path = ROOT / relative_path
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ReadinessError(f"required document is missing: {relative_path}") from error
        missing = [marker for marker in markers if marker not in text]
        if missing:
            raise ReadinessError(f"{relative_path}: missing markers {missing}")
        checked[relative_path] = markers
    return checked


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


def optional_git_checks(args: argparse.Namespace) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "require_clean_git": bool(args.require_clean_git),
        "require_origin_main": bool(args.require_origin_main),
    }
    if args.require_clean_git:
        status = run_git(["status", "--short"])
        if status:
            raise ReadinessError(f"git worktree is not clean:\n{status}")
        checks["clean_git"] = True
    if args.require_origin_main:
        head = run_git(["rev-parse", "HEAD"])
        origin_main = run_git(["rev-parse", "origin/main"])
        if head != origin_main:
            raise ReadinessError(
                f"HEAD does not match origin/main: HEAD={head}, origin/main={origin_main}"
            )
        checks["head_matches_origin_main"] = True
    return checks


def build_readiness_decision() -> dict[str, Any]:
    return {
        "phase": "Phase 1.3 local/private behavioral wallet testing",
        "behavioral_readiness_ok": True,
        "ready_for_phase1_3_candidate_report": True,
        "ready_to_create_tag_now": False,
        "generic_continue_is_approval": False,
        "proposed_future_tag": PROPOSED_TAG,
        "required_exact_tag_approval_phrase": APPROVAL_PHRASE,
        "allowed_without_explicit_tag_approval": [
            "readiness-summary checks",
            "docs updates",
            "candidate-report drafting",
            "additional local/private evidence collection",
        ],
        "prohibited_without_explicit_tag_approval": [
            "create local Phase 1.3 tag",
            "push Phase 1.3 tag",
            "move/delete/recreate any existing RC tag",
            "enable wallet submit UI",
            "add public mainnet, DEX, custody, smart-contract, or production infrastructure scope",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
    fixture_path = args.fixture.resolve()
    contract_summary = args.contract_summary.resolve() if args.contract_summary else latest_summary(
        "xriq-phase1-3-behavior-contract-check-*/summary.json",
        "Phase 1.3 contract summary",
        "python scripts/xriq_phase1_3_behavior_contract_check.py",
    )
    cpu_smoke_summary = args.cpu_smoke_summary.resolve() if args.cpu_smoke_summary else latest_summary(
        "xriq-phase1-3-wallet-behavior-smoke-*/summary.json",
        "Phase 1.3 CPU behavior smoke summary",
        "python scripts/xriq_phase1_3_wallet_behavior_smoke.py --skip-build",
    )
    ui_smoke_summary = args.ui_smoke_summary.resolve() if args.ui_smoke_summary else latest_summary(
        "xriq-phase1-3-wallet-behavior-ui-smoke-*/summary.json",
        "Phase 1.3 UI behavior smoke summary",
        "python scripts/xriq_phase1_3_wallet_behavior_ui_smoke.py --skip-build",
    )

    try:
        artifact_dir.mkdir(parents=True, exist_ok=False)
        fixture, fixture_contract = load_fixture(fixture_path)
        contract = verify_contract_summary(contract_summary, fixture_path)
        cpu = verify_cpu_smoke(cpu_smoke_summary, fixture, fixture_path)
        ui = verify_ui_smoke(ui_smoke_summary, fixture, fixture_path)
        docs = verify_docs()
        git_checks = optional_git_checks(args)

        if cpu["wallet_send_tx_hash"] != ui["wallet_send_tx_hash"]:
            raise ReadinessError("CPU and UI behavior smokes used different behavior tx hashes")
        if cpu["produced_block_hash"] != ui["produced_block_hash"]:
            raise ReadinessError("CPU and UI behavior smokes used different produced block hashes")

        summary = {
            "ok": "xriq-phase1-3-readiness-summary",
            "artifact_dir": str(artifact_dir),
            "completed_at": datetime.now(UTC).isoformat(),
            "fixture": {
                "path": str(fixture_path),
                **fixture_contract,
            },
            "selected_evidence": {
                "contract_summary": str(contract_summary),
                "cpu_smoke_summary": str(cpu_smoke_summary),
                "ui_smoke_summary": str(ui_smoke_summary),
            },
            "contract_summary": contract,
            "cpu_smoke": cpu,
            "ui_smoke": ui,
            "negative_matrix": {
                "cases_checked": len(cpu["negative_cases"]),
                "cases": cpu["negative_cases"],
            },
            "docs_checked": docs,
            "git_checks": git_checks,
            "readiness_decision": build_readiness_decision(),
            "scope_boundaries": [
                "local/private behavior only",
                "wallet submit UI remains deferred",
                "default mutation paths remain refused",
                "no Docker, GCP, Vast, GPU, public, DEX, custody, smart contracts, production infrastructure, or tag operation",
            ],
        }
        write_json(artifact_dir / "summary.json", summary)
    except ReadinessError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
