from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "xriq" / "db" / "schema.sql"
FIXTURE_DIR = ROOT / "xriq" / "fixtures" / "phase1_1"
PHASE1_2_FIXTURE_DIR = ROOT / "xriq" / "fixtures" / "phase1_2"

REQUIRED_TABLES: dict[str, list[str]] = {
    "xriq_blocks": [
        "height",
        "block_hash",
        "previous_block_hash",
        "state_root",
        "transactions_root",
        "transaction_count",
        "timestamp_utc",
        "indexed_at",
    ],
    "xriq_transactions": [
        "tx_hash",
        "block_height",
        "block_hash",
        "transaction_index",
        "status",
        "from_address",
        "to_address",
        "amount_base_units",
        "fee_base_units",
        "nonce",
        "created_at",
        "indexed_at",
    ],
    "xriq_accounts": [
        "address",
        "first_seen_height",
        "last_seen_height",
        "created_at",
        "updated_at",
    ],
    "xriq_account_balances": [
        "address",
        "balance_base_units",
        "nonce",
        "height",
        "state_root",
        "updated_at",
    ],
    "xriq_account_transactions": [
        "address",
        "tx_hash",
        "direction",
        "block_height",
        "transaction_index",
        "amount_base_units",
        "fee_base_units",
        "indexed_at",
    ],
    "xriq_mempool_entries": [
        "tx_hash",
        "from_address",
        "to_address",
        "amount_base_units",
        "fee_base_units",
        "nonce",
        "status",
        "first_seen_at",
        "last_seen_at",
    ],
    "xriq_snapshots": [
        "snapshot_name",
        "snapshot_dir",
        "chain_id",
        "current_height",
        "latest_block_hash",
        "state_root",
        "pending_transactions",
        "created_at",
        "indexed_at",
    ],
    "xriq_indexer_runs": [
        "run_id",
        "started_at",
        "completed_at",
        "status",
        "from_height",
        "to_height",
        "blocks_indexed",
        "transactions_indexed",
        "error",
    ],
    "xriq_audit_events": [
        "event_id",
        "occurred_at",
        "actor",
        "action",
        "resource_type",
        "resource_id",
        "environment",
        "metadata_json",
    ],
    "xriq_iso20022_messages": [
        "message_id",
        "tx_hash",
        "account_address",
        "message_type",
        "mapping_version",
        "environment",
        "not_certified",
        "payload_json",
        "created_at",
    ],
}

REQUIRED_FIXTURES: dict[str, list[str]] = {
    "explorer-overview.json": ["environment", "network", "chain", "indexer", "totals"],
    "block-list.json": ["environment", "network", "blocks"],
    "block-detail.json": ["environment", "network", "block_hash", "transactions"],
    "transaction-detail.json": ["environment", "network", "tx_hash", "status"],
    "account-detail.json": ["environment", "network", "address", "balance_base_units"],
    "account-history.json": ["environment", "network", "address", "transactions"],
    "wallet-transfer-draft.json": ["environment", "network", "warning", "draft"],
    "wallet-transfer-submit.json": ["environment", "network", "warning", "tx_hash"],
    "wallet-transfer-send.json": ["environment", "network", "warning", "tx_hash"],
    "wallet-transaction-status.json": ["environment", "network", "warning", "tx_hash"],
    "admin-indexer-status.json": ["environment", "service", "status", "last_run"],
    "iso20022-payment-initiation-preview.json": [
        "environment",
        "not_certified",
        "mapping_version",
        "message_type",
        "iso20022_aligned",
        "unsupported_fields",
    ],
    "iso20022-transaction-status.json": [
        "environment",
        "not_certified",
        "mapping_version",
        "message_type",
        "iso20022_aligned",
        "unsupported_fields",
    ],
    "iso20022-account-statement.json": [
        "environment",
        "not_certified",
        "mapping_version",
        "message_type",
        "entries",
        "unsupported_fields",
    ],
}

REQUIRED_PHASE1_2_PREFLIGHT_FIXTURES: dict[str, dict[str, str]] = {
    "wallet-transfer-submit-disabled.json": {
        "endpoint": "POST /api/v1/wallet/transfers/submit",
        "code": "wallet_submit_disabled",
        "explicit_flag": "--enable-local-wallet-submit",
        "action": "wallet_transfer_submit_attempt",
        "resource_type": "wallet_transfer",
        "event_id": "wallet-transfer-submit:local_request_id",
        "resource_id_policy": "draft_id_or_local_request_id",
    },
    "wallet-transfer-send-disabled.json": {
        "endpoint": "POST /api/v1/wallet/transfers/send",
        "code": "wallet_send_disabled",
        "explicit_flag": "--enable-local-wallet-send",
        "action": "wallet_transfer_send_attempt",
        "resource_type": "wallet_transfer",
        "event_id": "wallet-transfer-send:local_request_id",
        "resource_id_policy": "local_request_id",
    },
    "block-production-disabled.json": {
        "endpoint": "POST /api/v1/blocks/produce",
        "code": "block_production_disabled",
        "explicit_flag": "--enable-local-block-production",
        "action": "block_production_attempt",
        "resource_type": "block_production",
        "event_id": "block-production:local_request_id",
        "resource_id_policy": "local_request_id",
    },
}

REQUIRED_PHASE1_2_AUDIT_EXPECTATION_FIXTURES: dict[str, dict[str, str]] = {
    "wallet-transfer-submit-audit-expectation.json": {
        "endpoint": "POST /api/v1/wallet/transfers/submit",
        "action": "wallet_transfer_submit_attempt",
        "explicit_flag": "--enable-local-wallet-submit",
        "refusal_code": "wallet_submit_disabled",
        "resource_type": "wallet_transfer",
        "resource_id_policy": "draft_id_or_local_request_id",
    },
    "wallet-transfer-send-audit-expectation.json": {
        "endpoint": "POST /api/v1/wallet/transfers/send",
        "action": "wallet_transfer_send_attempt",
        "explicit_flag": "--enable-local-wallet-send",
        "refusal_code": "wallet_send_disabled",
        "resource_type": "wallet_transfer",
        "resource_id_policy": "local_request_id",
    },
    "block-production-audit-expectation.json": {
        "endpoint": "POST /api/v1/blocks/produce",
        "action": "block_production_attempt",
        "explicit_flag": "--enable-local-block-production",
        "refusal_code": "block_production_disabled",
        "resource_type": "block_production",
        "resource_id_policy": "local_request_id",
    },
}

REQUIRED_PHASE1_2_LOOP_CONTRACT_FIXTURES: dict[str, dict[str, str]] = {
    "pending-to-confirmed-loop-contract.json": {
        "endpoint": "POST /api/v1/blocks/produce",
        "contract": "pending-to-confirmed-loop-v1",
        "explicit_flag": "--enable-local-block-production",
        "default_refusal_code": "block_production_disabled",
        "accepted_mutation": "chain_and_pending_state_local_only",
        "action": "block_production_attempt",
        "resource_type": "block_production",
    },
}

HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
SENSITIVE_FIELD_PATTERN = re.compile(r"(private[_-]?key|seed[_-]?phrase|mnemonic)", re.IGNORECASE)


class ContractError(RuntimeError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ContractError(f"fixture missing: {path}") from error
    except json.JSONDecodeError as error:
        raise ContractError(f"fixture is not valid JSON: {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ContractError(f"fixture root must be a JSON object: {path}")
    return payload


def find_values(payload: Any, key_name: str) -> list[Any]:
    found: list[Any] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == key_name:
                found.append(value)
            found.extend(find_values(value, key_name))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(find_values(item, key_name))
    return found


def find_sensitive_keys(payload: Any) -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if SENSITIVE_FIELD_PATTERN.search(key):
                found.append(key)
            found.extend(find_sensitive_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(find_sensitive_keys(item))
    return found


def verify_schema() -> dict[str, int]:
    try:
        schema = SCHEMA_PATH.read_text(encoding="utf-8").lower()
    except FileNotFoundError as error:
        raise ContractError(f"schema missing: {SCHEMA_PATH}") from error

    for table, columns in REQUIRED_TABLES.items():
        if f"create table if not exists {table}" not in schema:
            raise ContractError(f"schema missing table: {table}")
        for column in columns:
            if not re.search(rf"\b{re.escape(column)}\b", schema):
                raise ContractError(f"schema missing column {table}.{column}")

    return {"tables": len(REQUIRED_TABLES)}


def verify_common_payload(name: str, payload: dict[str, Any]) -> None:
    environment = payload.get("environment")
    if environment != "private-devnet":
        raise ContractError(f"{name} must declare environment private-devnet")

    if name.startswith("iso20022-"):
        if payload.get("not_certified") is not True:
            raise ContractError(f"{name} must declare not_certified true")
        unsupported = payload.get("unsupported_fields")
        if not isinstance(unsupported, list) or not unsupported:
            raise ContractError(f"{name} must list unsupported_fields")

    for value in find_values(payload, "tx_hash"):
        if not isinstance(value, str) or not HASH_PATTERN.match(value):
            raise ContractError(f"{name} has invalid tx_hash: {value!r}")

    for value in find_values(payload, "block_hash"):
        if not isinstance(value, str) or not HASH_PATTERN.match(value):
            raise ContractError(f"{name} has invalid block_hash: {value!r}")

    for key in ("amount_base_units", "fee_base_units", "balance_base_units"):
        for value in find_values(payload, key):
            if not isinstance(value, str) or not value.isdigit():
                raise ContractError(f"{name} has invalid {key}: {value!r}")

    sensitive = find_sensitive_keys(payload)
    if sensitive:
        raise ContractError(f"{name} contains sensitive-looking fields: {sensitive}")


def verify_fixture(name: str, required_fields: list[str]) -> None:
    path = FIXTURE_DIR / name
    payload = load_json(path)

    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ContractError(f"{name} missing fields: {missing}")

    verify_common_payload(name, payload)


def verify_fixtures() -> dict[str, int]:
    if not FIXTURE_DIR.exists():
        raise ContractError(f"fixture dir missing: {FIXTURE_DIR}")

    for name, fields in REQUIRED_FIXTURES.items():
        verify_fixture(name, fields)

    return {"fixtures": len(REQUIRED_FIXTURES)}


def verify_phase1_2_preflight_fixture(name: str, expected: dict[str, str]) -> None:
    path = PHASE1_2_FIXTURE_DIR / name
    payload = load_json(path)

    required_fields = [
        "environment",
        "network",
        "endpoint",
        "enabled",
        "mutation",
        "status",
        "code",
        "error",
        "warning",
        "required_enablement",
        "audit_scope",
        "audit_event_recorded",
        "audit_event",
        "request_fields",
        "refusal_guards",
    ]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ContractError(f"{name} missing fields: {missing}")

    verify_common_payload(name, payload)

    if payload.get("endpoint") != expected["endpoint"]:
        raise ContractError(f"{name} has wrong endpoint: {payload.get('endpoint')!r}")
    if payload.get("enabled") is not False:
        raise ContractError(f"{name} must be disabled by default")
    if payload.get("mutation") != "none":
        raise ContractError(f"{name} must declare mutation none")
    if payload.get("status") != "disabled":
        raise ContractError(f"{name} must declare status disabled")
    if payload.get("code") != expected["code"]:
        raise ContractError(f"{name} has wrong code: {payload.get('code')!r}")

    enablement = payload.get("required_enablement")
    if not isinstance(enablement, dict):
        raise ContractError(f"{name} required_enablement must be an object")
    if enablement.get("mode") != "local-private-devnet":
        raise ContractError(f"{name} must require local-private-devnet mode")
    if enablement.get("explicit_flag") != expected["explicit_flag"]:
        raise ContractError(f"{name} has wrong explicit enablement flag")
    if enablement.get("audit_event_required") is not True:
        raise ContractError(f"{name} must require an audit event")
    if enablement.get("test_identity_only") is not True:
        raise ContractError(f"{name} must remain test-identity-only")

    if payload.get("audit_scope") != "api-local-refusal":
        raise ContractError(f"{name} must declare API-local refusal audit scope")
    if payload.get("audit_event_recorded") is not True:
        raise ContractError(f"{name} must record a refusal audit event")

    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise ContractError(f"{name} audit_event must be an object")
    expected_audit_fields = {
        "event_id": expected["event_id"],
        "actor": "local-private-devnet-operator",
        "action": expected["action"],
        "resource_type": expected["resource_type"],
        "resource_id": expected["resource_id_policy"],
        "environment": "private-devnet",
    }
    for field, expected_value in expected_audit_fields.items():
        if audit_event.get(field) != expected_value:
            raise ContractError(
                f"{name} audit_event.{field} must be {expected_value!r}, "
                f"got {audit_event.get(field)!r}"
            )

    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise ContractError(f"{name} audit_event.metadata must be an object")
    expected_metadata = {
        "endpoint": expected["endpoint"],
        "outcome": "refused",
        "status": "disabled",
        "refusal_code": expected["code"],
        "explicit_flag": expected["explicit_flag"],
        "local_request_id": "local_request_id",
        "resource_id_policy": expected["resource_id_policy"],
        "mutation": "none",
    }
    for field, expected_value in expected_metadata.items():
        if metadata.get(field) != expected_value:
            raise ContractError(
                f"{name} audit_event.metadata.{field} must be {expected_value!r}, "
                f"got {metadata.get(field)!r}"
            )
    metadata_policy = metadata.get("metadata_policy")
    if not isinstance(metadata_policy, str) or "request fields only" not in metadata_policy:
        raise ContractError(f"{name} audit metadata policy must be request-fields-only")

    for field in ("request_fields", "refusal_guards"):
        value = payload.get(field)
        if not isinstance(value, list) or not value:
            raise ContractError(f"{name} {field} must be a non-empty list")


def verify_phase1_2_preflight_fixtures() -> dict[str, int]:
    if not PHASE1_2_FIXTURE_DIR.exists():
        raise ContractError(f"Phase 1.2 fixture dir missing: {PHASE1_2_FIXTURE_DIR}")

    for name, expected in REQUIRED_PHASE1_2_PREFLIGHT_FIXTURES.items():
        verify_phase1_2_preflight_fixture(name, expected)

    return {"phase1_2_preflight_fixtures": len(REQUIRED_PHASE1_2_PREFLIGHT_FIXTURES)}


def verify_phase1_2_audit_expectation_fixture(name: str, expected: dict[str, str]) -> None:
    path = PHASE1_2_FIXTURE_DIR / name
    payload = load_json(path)

    required_fields = [
        "environment",
        "network",
        "endpoint",
        "action",
        "actor",
        "resource_type",
        "resource_id_policy",
        "status",
        "mutation",
        "default_outcome",
        "accepted_outcome",
        "audit_event_required",
        "test_identity_only",
        "required_enablement",
        "audit_event",
        "outcomes",
        "guards",
    ]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ContractError(f"{name} missing fields: {missing}")

    verify_common_payload(name, payload)

    if payload.get("network") != "xriq-devnet":
        raise ContractError(f"{name} must declare network xriq-devnet")
    if payload.get("endpoint") != expected["endpoint"]:
        raise ContractError(f"{name} has wrong endpoint: {payload.get('endpoint')!r}")
    if payload.get("action") != expected["action"]:
        raise ContractError(f"{name} has wrong action: {payload.get('action')!r}")
    if payload.get("actor") != "local-private-devnet-operator":
        raise ContractError(f"{name} must use the local private-devnet actor")
    if payload.get("resource_type") != expected["resource_type"]:
        raise ContractError(
            f"{name} must use {expected['resource_type']} resource type"
        )
    if payload.get("resource_id_policy") != expected["resource_id_policy"]:
        raise ContractError(f"{name} has wrong resource id policy")
    if payload.get("status") != "expectation":
        raise ContractError(f"{name} must declare expectation status")
    if payload.get("mutation") != "none":
        raise ContractError(f"{name} must remain non-mutating")
    if payload.get("default_outcome") != "refused":
        raise ContractError(f"{name} default outcome must be refused")
    if payload.get("audit_event_required") is not True:
        raise ContractError(f"{name} must require audit events")
    if payload.get("test_identity_only") is not True:
        raise ContractError(f"{name} must remain test-identity-only")

    enablement = payload.get("required_enablement")
    if not isinstance(enablement, dict):
        raise ContractError(f"{name} required_enablement must be an object")
    if enablement.get("mode") != "local-private-devnet":
        raise ContractError(f"{name} must require local-private-devnet mode")
    if enablement.get("explicit_flag") != expected["explicit_flag"]:
        raise ContractError(f"{name} has wrong explicit enablement flag")
    if enablement.get("audit_event_required") is not True:
        raise ContractError(f"{name} required_enablement must require audit event")
    if enablement.get("test_identity_only") is not True:
        raise ContractError(f"{name} required_enablement must remain test-identity-only")

    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise ContractError(f"{name} audit_event must be an object")
    for field in ("actor", "action", "resource_type", "environment"):
        if audit_event.get(field) != payload.get(field):
            raise ContractError(f"{name} audit_event.{field} must mirror top-level {field}")
    for field in ("metadata_required", "metadata_forbidden"):
        value = audit_event.get(field)
        if not isinstance(value, list) or not value:
            raise ContractError(f"{name} audit_event.{field} must be a non-empty list")

    required_metadata = {
        "endpoint",
        "outcome",
        "status",
        "refusal_code",
        "explicit_flag",
        "local_request_id",
    }
    if expected["resource_type"] == "wallet_transfer":
        required_metadata.update(
            {
                "from_address",
                "to_address",
                "amount_base_units",
                "fee_base_units",
                "nonce",
                "expires_at_height",
            }
        )
    elif expected["resource_type"] == "block_production":
        required_metadata.update(
            {
                "pending_file",
                "chain_file",
                "producer",
                "max_transactions",
                "timestamp_ms",
            }
        )
    else:
        raise ContractError(f"{name} has unsupported resource type")
    metadata_required = {str(item) for item in audit_event["metadata_required"]}
    missing_metadata = sorted(required_metadata.difference(metadata_required))
    if missing_metadata:
        raise ContractError(f"{name} missing audit metadata fields: {missing_metadata}")

    metadata_forbidden = {str(item) for item in audit_event["metadata_forbidden"]}
    for forbidden in (
        "private_key",
        "seed_phrase",
        "mnemonic",
        "signature",
        "signed_transaction",
        "tx_hash",
        "transaction_hash",
    ):
        if forbidden not in metadata_forbidden:
            raise ContractError(f"{name} must forbid audit metadata {forbidden}")

    outcomes = payload.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) < 2:
        raise ContractError(f"{name} outcomes must include refused and accepted cases")
    by_outcome = {
        str(outcome.get("outcome")): outcome
        for outcome in outcomes
        if isinstance(outcome, dict)
    }
    refused = by_outcome.get("refused")
    accepted = by_outcome.get("accepted")
    if not isinstance(refused, dict) or not isinstance(accepted, dict):
        raise ContractError(f"{name} outcomes must include refused and accepted objects")
    if refused.get("code") != expected["refusal_code"]:
        raise ContractError(f"{name} refused outcome has wrong code")
    if refused.get("mutation") != "none":
        raise ContractError(f"{name} refused outcome must be non-mutating")
    if refused.get("must_write_audit_event") is not True:
        raise ContractError(f"{name} refused outcome must write audit event")
    if accepted.get("requires_explicit_flag") != expected["explicit_flag"]:
        raise ContractError(f"{name} accepted outcome has wrong required flag")
    if accepted.get("must_write_audit_event") is not True:
        raise ContractError(f"{name} accepted outcome must write audit event")
    if accepted.get("scope") != "local-private-devnet-test-identity-only":
        raise ContractError(f"{name} accepted outcome must remain local/test-only")

    guards = payload.get("guards")
    if not isinstance(guards, list) or not guards:
        raise ContractError(f"{name} guards must be a non-empty list")
    guard_text = "\n".join(str(guard) for guard in guards)
    for required_guard in (
        "default outcome is refused",
        "accepted outcome requires explicit local flag",
        "audit event is required for refused and accepted attempts",
        "audit event must not contain signing material",
        "audit event must not contain transaction hash before accepted mutation",
    ):
        if required_guard not in guard_text:
            raise ContractError(f"{name} missing guard {required_guard!r}")


def verify_phase1_2_audit_expectation_fixtures() -> dict[str, int]:
    if not PHASE1_2_FIXTURE_DIR.exists():
        raise ContractError(f"Phase 1.2 fixture dir missing: {PHASE1_2_FIXTURE_DIR}")

    for name, expected in REQUIRED_PHASE1_2_AUDIT_EXPECTATION_FIXTURES.items():
        verify_phase1_2_audit_expectation_fixture(name, expected)

    return {
        "phase1_2_audit_expectation_fixtures": len(
            REQUIRED_PHASE1_2_AUDIT_EXPECTATION_FIXTURES
        )
    }


def verify_phase1_2_loop_contract_fixture(name: str, expected: dict[str, str]) -> None:
    path = PHASE1_2_FIXTURE_DIR / name
    payload = load_json(path)

    required_fields = [
        "environment",
        "network",
        "endpoint",
        "contract",
        "status",
        "implementation_status",
        "default_outcome",
        "accepted_outcome",
        "mutation",
        "warning",
        "default_refusal",
        "required_enablement",
        "request_schema",
        "accepted_response_schema",
        "example_accepted_response",
        "state_transition_guards",
        "ui_guards",
    ]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ContractError(f"{name} missing fields: {missing}")

    verify_common_payload(name, payload)

    if payload.get("network") != "xriq-devnet":
        raise ContractError(f"{name} must declare network xriq-devnet")
    if payload.get("endpoint") != expected["endpoint"]:
        raise ContractError(f"{name} has wrong endpoint: {payload.get('endpoint')!r}")
    if payload.get("contract") != expected["contract"]:
        raise ContractError(f"{name} has wrong contract id")
    if payload.get("status") != "api-local-implemented":
        raise ContractError(f"{name} must be api-local-implemented")
    if (
        payload.get("implementation_status")
        != "request-and-serve-readonly-explicit-local-flag"
    ):
        raise ContractError(f"{name} has wrong implementation_status")
    if payload.get("default_outcome") != "refused":
        raise ContractError(f"{name} default outcome must be refused")
    if payload.get("mutation") != "none-until-explicit-local-enable":
        raise ContractError(f"{name} must remain non-mutating until explicit local enable")

    default_refusal = payload.get("default_refusal")
    if not isinstance(default_refusal, dict):
        raise ContractError(f"{name} default_refusal must be an object")
    if default_refusal.get("fixture") != "block-production-disabled.json":
        raise ContractError(f"{name} must reference the disabled block-production fixture")
    if default_refusal.get("code") != expected["default_refusal_code"]:
        raise ContractError(f"{name} default refusal code is wrong")
    if default_refusal.get("mutation") != "none":
        raise ContractError(f"{name} default refusal must be non-mutating")

    enablement = payload.get("required_enablement")
    if not isinstance(enablement, dict):
        raise ContractError(f"{name} required_enablement must be an object")
    if enablement.get("mode") != "local-private-devnet":
        raise ContractError(f"{name} must require local-private-devnet mode")
    if enablement.get("explicit_flag") != expected["explicit_flag"]:
        raise ContractError(f"{name} has wrong explicit local flag")
    if enablement.get("audit_event_required") is not True:
        raise ContractError(f"{name} must require audit events")
    if enablement.get("test_identity_only") is not True:
        raise ContractError(f"{name} must remain test-identity-only")

    request_schema = payload.get("request_schema")
    if not isinstance(request_schema, dict):
        raise ContractError(f"{name} request_schema must be an object")
    required_request_fields = set(
        str(field) for field in request_schema.get("required_fields", [])
    )
    for field in (
        "local_request_id",
        "pending_file",
        "chain_file",
        "producer",
        "max_transactions",
        "timestamp_ms",
    ):
        if field not in required_request_fields:
            raise ContractError(f"{name} request_schema missing {field}")
    forbidden_request_fields = set(
        str(field) for field in request_schema.get("forbidden_fields", [])
    )
    for field in (
        "private_key",
        "seed_phrase",
        "mnemonic",
        "signature",
        "signed_transaction",
    ):
        if field not in forbidden_request_fields:
            raise ContractError(f"{name} request_schema must forbid {field}")

    accepted_schema = payload.get("accepted_response_schema")
    if not isinstance(accepted_schema, dict):
        raise ContractError(f"{name} accepted_response_schema must be an object")
    if accepted_schema.get("status") != "confirmed":
        raise ContractError(f"{name} accepted status must be confirmed")
    if accepted_schema.get("mutation") != expected["accepted_mutation"]:
        raise ContractError(f"{name} accepted mutation is wrong")
    required_response_fields = set(
        str(field) for field in accepted_schema.get("required_fields", [])
    )
    for field in (
        "block",
        "confirmed_transactions",
        "pending_state",
        "chain_state",
        "audit_event",
    ):
        if field not in required_response_fields:
            raise ContractError(f"{name} accepted_response_schema missing {field}")

    example = payload.get("example_accepted_response")
    if not isinstance(example, dict):
        raise ContractError(f"{name} example_accepted_response must be an object")
    if example.get("status") != "confirmed":
        raise ContractError(f"{name} example status must be confirmed")
    if example.get("mutation") != expected["accepted_mutation"]:
        raise ContractError(f"{name} example mutation is wrong")
    if example.get("audit_event_recorded") is not True:
        raise ContractError(f"{name} example must record an audit event")
    audit_event = example.get("audit_event")
    if not isinstance(audit_event, dict):
        raise ContractError(f"{name} example audit_event must be an object")
    if audit_event.get("action") != expected["action"]:
        raise ContractError(f"{name} example audit action is wrong")
    if audit_event.get("resource_type") != expected["resource_type"]:
        raise ContractError(f"{name} example audit resource type is wrong")
    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise ContractError(f"{name} example audit metadata must be an object")
    if metadata.get("explicit_flag") != expected["explicit_flag"]:
        raise ContractError(f"{name} example audit metadata explicit flag is wrong")
    if metadata.get("outcome") != "accepted":
        raise ContractError(f"{name} example audit metadata outcome must be accepted")
    if metadata.get("status") != "confirmed":
        raise ContractError(f"{name} example audit metadata status must be confirmed")
    if metadata.get("producer") != "xriqdev1author00000000000":
        raise ContractError(f"{name} example audit metadata producer is wrong")
    if metadata.get("max_transactions") != 4:
        raise ContractError(f"{name} example audit metadata max_transactions must be 4")

    guards = payload.get("state_transition_guards")
    if not isinstance(guards, list) or not guards:
        raise ContractError(f"{name} state_transition_guards must be a non-empty list")
    guard_text = "\n".join(str(guard) for guard in guards)
    for required_guard in (
        "default path remains refused and non-mutating",
        "accepted path requires explicit local flag",
        "accepted path requires test identity producer",
        "accepted path must remove only confirmed transactions from pending state",
        "accepted path must append exactly one block to the local chain file",
        "accepted path must write an audit event before reporting success",
    ):
        if required_guard not in guard_text:
            raise ContractError(f"{name} missing guard {required_guard!r}")


def verify_phase1_2_loop_contract_fixtures() -> dict[str, int]:
    if not PHASE1_2_FIXTURE_DIR.exists():
        raise ContractError(f"Phase 1.2 fixture dir missing: {PHASE1_2_FIXTURE_DIR}")

    for name, expected in REQUIRED_PHASE1_2_LOOP_CONTRACT_FIXTURES.items():
        verify_phase1_2_loop_contract_fixture(name, expected)

    return {
        "phase1_2_loop_contract_fixtures": len(
            REQUIRED_PHASE1_2_LOOP_CONTRACT_FIXTURES
        )
    }


def main() -> int:
    schema_result = verify_schema()
    fixture_result = verify_fixtures()
    phase1_2_result = verify_phase1_2_preflight_fixtures()
    phase1_2_audit_result = verify_phase1_2_audit_expectation_fixtures()
    phase1_2_loop_result = verify_phase1_2_loop_contract_fixtures()
    report = {
        "ok": "xriq-phase1-1-contract-check",
        "schema": str(SCHEMA_PATH),
        "fixture_dir": str(FIXTURE_DIR),
        "phase1_2_fixture_dir": str(PHASE1_2_FIXTURE_DIR),
        **schema_result,
        **fixture_result,
        **phase1_2_result,
        **phase1_2_audit_result,
        **phase1_2_loop_result,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
