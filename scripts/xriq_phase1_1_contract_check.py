from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "xriq" / "db" / "schema.sql"
FIXTURE_DIR = ROOT / "xriq" / "fixtures" / "phase1_1"

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


def verify_fixture(name: str, required_fields: list[str]) -> None:
    path = FIXTURE_DIR / name
    payload = load_json(path)

    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ContractError(f"{name} missing fields: {missing}")

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


def verify_fixtures() -> dict[str, int]:
    if not FIXTURE_DIR.exists():
        raise ContractError(f"fixture dir missing: {FIXTURE_DIR}")

    for name, fields in REQUIRED_FIXTURES.items():
        verify_fixture(name, fields)

    return {"fixtures": len(REQUIRED_FIXTURES)}


def main() -> int:
    schema_result = verify_schema()
    fixture_result = verify_fixtures()
    report = {
        "ok": "xriq-phase1-1-contract-check",
        "schema": str(SCHEMA_PATH),
        "fixture_dir": str(FIXTURE_DIR),
        **schema_result,
        **fixture_result,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
