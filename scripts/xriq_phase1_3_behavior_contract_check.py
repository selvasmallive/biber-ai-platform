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
FIXTURE_PATH = ROOT / "xriq" / "fixtures" / "phase1_3" / "local-wallet-behavior-v1.json"
SUMMARY_ROOT = ROOT / "xriq" / "target"

ALICE = "xriqdev1alice00000000000"
BOB = "xriqdev1bobbb00000000000"
CAROL = "xriqdev1carol00000000000"
PRODUCER = "xriqdev1author00000000000"
FEE_SINK = "xriqdev1fees000000000000"

EXPECTED_SWITCHES = [
    "--enable-local-wallet-send true",
    "--enable-local-block-production true",
    "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
]

EXPECTED_FORBIDDEN_SCOPE = {
    "wallet-submit-ui",
    "snapshot-import-export-mutation",
    "dex-liquidity",
    "smart-contract-vm",
    "custody",
    "public-mainnet",
    "validator-economics",
    "bridges",
    "exchange-listing-claims",
    "production-infrastructure",
    "gcp-or-vast-provisioning",
}

SENSITIVE_KEY_PATTERN = re.compile(
    r"(private[_-]?key|seed[_-]?phrase|mnemonic|signature|signed[_-]?transaction)",
    re.IGNORECASE,
)


class BehaviorContractError(RuntimeError):
    pass


def default_artifact_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return SUMMARY_ROOT / f"xriq-phase1-3-behavior-contract-check-{timestamp}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise BehaviorContractError(f"fixture missing: {path}") from error
    except json.JSONDecodeError as error:
        raise BehaviorContractError(f"fixture is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise BehaviorContractError(f"fixture root must be a JSON object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise BehaviorContractError(
            f"{context}: expected {key}={expected!r}, got {actual!r}"
        )


def require_dict(payload: dict[str, Any], key: str, context: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise BehaviorContractError(f"{context}: expected {key} object")
    return value


def require_list(payload: dict[str, Any], key: str, context: str) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise BehaviorContractError(f"{context}: expected non-empty {key} list")
    return value


def find_sensitive_keys(payload: Any) -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if SENSITIVE_KEY_PATTERN.search(key):
                found.append(key)
            found.extend(find_sensitive_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(find_sensitive_keys(item))
    return found


def verify_top_level(payload: dict[str, Any]) -> None:
    context = "Phase 1.3 behavior fixture"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "fixture", "phase1-3-local-wallet-behavior-v1", context)
    require_equal(payload, "status", "contract-fixture", context)
    require_equal(payload, "scope", "local-private-behavior-only", context)

    source_tag = require_dict(payload, "source_phase1_2_tag", context)
    require_equal(source_tag, "tag", "phase1-2-xriq-local-private-hardening-rc1", context)
    require_equal(source_tag, "commit", "b3a2fe4", context)
    require_equal(
        source_tag,
        "tag_maintenance",
        "do-not-move-delete-recreate-or-repush",
        context,
    )

    switches = [str(item) for item in require_list(payload, "approved_local_switches", context)]
    if switches != EXPECTED_SWITCHES:
        raise BehaviorContractError(
            f"{context}: approved switches changed: expected {EXPECTED_SWITCHES!r}, "
            f"got {switches!r}"
        )

    forbidden_scope = {
        str(item) for item in require_list(payload, "forbidden_scope", context)
    }
    missing_scope = sorted(EXPECTED_FORBIDDEN_SCOPE.difference(forbidden_scope))
    if missing_scope:
        raise BehaviorContractError(f"{context}: missing forbidden scope {missing_scope}")


def verify_identities(payload: dict[str, Any]) -> None:
    context = "Phase 1.3 identities"
    identities = require_dict(payload, "identities", context)
    expected = {
        "sender": ALICE,
        "base_recipient": BOB,
        "behavior_recipient": CAROL,
        "producer": PRODUCER,
        "fee_sink": FEE_SINK,
    }
    for key, value in expected.items():
        require_equal(identities, key, value, context)


def verify_base_chain(payload: dict[str, Any]) -> None:
    context = "Phase 1.3 base chain"
    base = require_dict(payload, "base_chain_setup", context)
    require_equal(base, "command", "xriq-node preflight-transfer", context)
    require_equal(base, "starting_chain_height", 0, context)
    require_equal(base, "starting_pending_transactions", 0, context)
    require_equal(base, "sender_start_balance_base_units", "100", context)

    transfer = require_dict(base, "transfer", context)
    for key, expected in {
        "from_address": ALICE,
        "to_address": BOB,
        "amount_base_units": "25",
        "fee_base_units": "2",
        "nonce": 0,
        "expires_at_height": 100,
        "timestamp_ms": 1000,
    }.items():
        require_equal(transfer, key, expected, context)

    expected = require_dict(base, "expected", context)
    for key, value in {
        "confirmed_block_height": 1,
        "confirmed_transaction_index": 0,
        "sender_balance_base_units": "73",
        "sender_nonce": 1,
        "base_recipient_balance_base_units": "25",
        "pending_transactions": 0,
        "transaction_status": "confirmed",
    }.items():
        require_equal(expected, key, value, context)


def verify_behavior_flow(payload: dict[str, Any]) -> None:
    context = "Phase 1.3 behavior flow"
    flow = require_list(payload, "behavior_flow", context)
    by_step = {
        str(item.get("step")): item for item in flow if isinstance(item, dict)
    }
    if set(by_step) != {"wallet_send_to_pending", "produce_one_block"}:
        raise BehaviorContractError(
            f"{context}: expected wallet_send_to_pending and produce_one_block, "
            f"got {sorted(by_step)}"
        )

    send = by_step["wallet_send_to_pending"]
    require_equal(send, "endpoint", "POST /api/v1/wallet/transfers/send", context)
    require_equal(send, "required_switch", "--enable-local-wallet-send true", context)
    require_equal(send, "local_request_id", "phase1-3-wallet-send-1", context)
    request = require_dict(send, "request", context)
    for key, expected in {
        "from_address": ALICE,
        "to_address": CAROL,
        "amount_base_units": "5",
        "fee_base_units": "2",
        "nonce": 1,
        "expires_at_height": 100,
    }.items():
        require_equal(request, key, expected, context)
    expected = require_dict(send, "expected", context)
    for key, value in {
        "http_status": 201,
        "code": "wallet_send_accepted_local_only",
        "status": "pending",
        "mutation": "pending_state_only",
        "pending_before_count": 0,
        "pending_after_count": 1,
        "chain_unchanged": True,
        "wallet_transaction_status": "pending",
        "audit_recording": "accepted-audit-event",
        "audit_action": "wallet_transfer_send_attempt",
    }.items():
        require_equal(expected, key, value, context)

    produce = by_step["produce_one_block"]
    require_equal(produce, "endpoint", "POST /api/v1/blocks/produce", context)
    require_equal(produce, "required_switch", "--enable-local-block-production true", context)
    require_equal(produce, "local_request_id", "phase1-3-block-produce-1", context)
    request = require_dict(produce, "request", context)
    for key, expected in {
        "producer": PRODUCER,
        "max_transactions": 4,
        "timestamp_ms": 2000,
    }.items():
        require_equal(request, key, expected, context)
    expected = require_dict(produce, "expected", context)
    for key, value in {
        "http_status": 201,
        "code": "block_production_accepted_local_only",
        "status": "confirmed",
        "mutation": "chain_and_pending_state_local_only",
        "previous_height": 1,
        "current_height": 2,
        "confirmed_transaction_count": 1,
        "pending_before_count": 1,
        "pending_after_count": 0,
        "wallet_transaction_status": "confirmed",
        "mempool_pending_count": 0,
        "audit_scope": "api-local-accepted",
        "audit_action": "block_production_attempt",
    }.items():
        require_equal(expected, key, value, context)


def verify_post_block(payload: dict[str, Any]) -> None:
    context = "Phase 1.3 post-block expectations"
    post = require_dict(payload, "post_block_expectations", context)
    accounts = require_list(post, "accounts", context)
    by_address = {
        str(account.get("address")): account
        for account in accounts
        if isinstance(account, dict)
    }
    expected_accounts = {
        ALICE: ("66", 2),
        BOB: ("25", 0),
        CAROL: ("5", 0),
        FEE_SINK: ("4", 0),
    }
    if set(by_address) != set(expected_accounts):
        raise BehaviorContractError(
            f"{context}: expected accounts {sorted(expected_accounts)}, "
            f"got {sorted(by_address)}"
        )
    for address, (balance, nonce) in expected_accounts.items():
        account = by_address[address]
        require_equal(account, "balance_base_units", balance, context)
        require_equal(account, "nonce", nonce, context)

    wallet_history = require_dict(post, "wallet_history", context)
    require_equal(wallet_history, "sender_min_confirmed_rows", 2, context)
    require_equal(wallet_history, "behavior_transaction_direction", "sent", context)
    require_equal(wallet_history, "recipient_transaction_direction", "received", context)

    explorer = require_dict(post, "explorer", context)
    for key, value in {
        "current_height": 2,
        "stored_blocks": 2,
        "confirmed_transactions": 2,
        "pending_transactions": 0,
    }.items():
        require_equal(explorer, key, value, context)

    admin = require_dict(post, "admin", context)
    for key, value in {
        "node_pending": 0,
        "wallet_pending": 0,
        "mempool_pending": 0,
    }.items():
        require_equal(admin, key, value, context)
    accepted_audit_actions = {
        str(action) for action in require_list(admin, "accepted_response_audit_actions", context)
    }
    for required in {"wallet_transfer_send_attempt", "block_production_attempt"}:
        if required not in accepted_audit_actions:
            raise BehaviorContractError(
                f"{context}: missing accepted response audit action {required}"
            )
    refusal_audit_actions = {
        str(action) for action in require_list(admin, "required_refusal_audit_actions", context)
    }
    for required in {
        "wallet_transfer_submit_attempt",
        "wallet_transfer_send_attempt",
        "block_production_attempt",
    }:
        if required not in refusal_audit_actions:
            raise BehaviorContractError(
                f"{context}: missing required refusal audit action {required}"
            )

    audit = require_dict(post, "audit", context)
    policy = audit.get("metadata_policy")
    if not isinstance(policy, str) or "request fields" not in policy:
        raise BehaviorContractError(f"{context}: audit metadata policy is too broad")
    require_equal(audit, "sensitive_material", "absent", context)
    require_equal(audit, "custody_material", "absent", context)


def verify_negative_matrix(payload: dict[str, Any]) -> None:
    context = "Phase 1.3 negative matrix"
    cases = require_list(payload, "negative_matrix", context)
    by_case = {
        str(item.get("case")): item for item in cases if isinstance(item, dict)
    }
    expected = {
        "default_wallet_send_disabled": (
            "POST /api/v1/wallet/transfers/send",
            "wallet_send_disabled",
        ),
        "default_block_production_disabled": (
            "POST /api/v1/blocks/produce",
            "block_production_disabled",
        ),
        "wallet_submit_ui_deferred": (
            "POST /api/v1/wallet/transfers/submit",
            "wallet_submit_disabled",
        ),
        "no_pending_block_production": (
            "POST /api/v1/blocks/produce",
            "no_pending_transactions",
        ),
        "invalid_wallet_send_request": (
            "POST /api/v1/wallet/transfers/send",
            "zero_amount",
        ),
    }
    if set(by_case) != set(expected):
        raise BehaviorContractError(
            f"{context}: expected cases {sorted(expected)}, got {sorted(by_case)}"
        )
    for case, (endpoint, code) in expected.items():
        item = by_case[case]
        require_equal(item, "endpoint", endpoint, context)
        require_equal(item, "expected_code", code, context)
        require_equal(item, "expected_mutation", "none", context)


def verify_artifact_policy(payload: dict[str, Any]) -> None:
    context = "Phase 1.3 artifact policy"
    policy = require_dict(payload, "artifact_policy", context)
    require_equal(policy, "root", "xriq/target/xriq-phase1-3-*", context)
    for key in [
        "external_services",
        "gpu_required",
        "docker_required_by_default",
        "writes_public_state",
    ]:
        require_equal(policy, key, False, context)


def verify_contract(payload: dict[str, Any]) -> dict[str, Any]:
    sensitive_keys = find_sensitive_keys(payload)
    if sensitive_keys:
        raise BehaviorContractError(
            f"Phase 1.3 behavior fixture has sensitive key names: {sensitive_keys}"
        )

    verify_top_level(payload)
    verify_identities(payload)
    verify_base_chain(payload)
    verify_behavior_flow(payload)
    verify_post_block(payload)
    verify_negative_matrix(payload)
    verify_artifact_policy(payload)

    return {
        "fixture": str(FIXTURE_PATH),
        "behavior_steps_checked": 2,
        "negative_cases_checked": 5,
        "post_block_accounts_checked": 4,
        "approved_local_switches_checked": len(EXPECTED_SWITCHES),
        "forbidden_scope_markers_checked": len(EXPECTED_FORBIDDEN_SCOPE),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the XRIQ Phase 1.3 local/private behavior contract fixture."
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for behavior contract artifacts. Defaults under xriq/target/.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact_dir = (args.artifact_dir or default_artifact_dir()).resolve()
    try:
        artifact_dir.mkdir(parents=True, exist_ok=False)
        payload = load_json(FIXTURE_PATH)
        result = verify_contract(payload)
        summary = {
            "ok": "xriq-phase1-3-behavior-contract-check",
            "artifact_dir": str(artifact_dir),
            "completed_at": datetime.now(UTC).isoformat(),
            **result,
            "next": (
                "run the CPU-only Phase 1.3 wallet behavior smoke, then add "
                "the UI-backed local/private behavior smoke using this fixture"
            ),
        }
        write_json(artifact_dir / "summary.json", summary)
    except BehaviorContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
