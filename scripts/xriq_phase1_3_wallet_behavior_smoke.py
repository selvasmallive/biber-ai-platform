#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from xriq_phase1_1_local_e2e_smoke import (
    SmokeError,
    assert_api_method_status,
    assert_api_status,
    executable_path,
    repo_root,
    require_equal,
    require_hash,
    require_list,
    run_command,
    run_json,
    write_json,
)
from xriq_phase1_3_behavior_contract_check import FIXTURE_PATH, verify_contract


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-3-wallet-behavior-smoke-{timestamp}"


def load_fixture() -> dict[str, Any]:
    try:
        payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SmokeError(f"Phase 1.3 behavior fixture missing: {FIXTURE_PATH}") from error
    except json.JSONDecodeError as error:
        raise SmokeError(f"Phase 1.3 behavior fixture is invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise SmokeError("Phase 1.3 behavior fixture must be a JSON object")
    try:
        verify_contract(payload)
    except Exception as error:
        raise SmokeError(f"Phase 1.3 behavior fixture contract failed: {error}") from error
    return payload


def fixture_step(fixture: dict[str, Any], step_name: str) -> dict[str, Any]:
    flow = fixture.get("behavior_flow")
    if not isinstance(flow, list):
        raise SmokeError("Phase 1.3 fixture behavior_flow must be a list")
    for step in flow:
        if isinstance(step, dict) and step.get("step") == step_name:
            return step
    raise SmokeError(f"Phase 1.3 fixture missing behavior step {step_name!r}")


def expected_accounts(fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    post_block = fixture.get("post_block_expectations")
    if not isinstance(post_block, dict):
        raise SmokeError("Phase 1.3 fixture missing post_block_expectations")
    accounts = post_block.get("accounts")
    if not isinstance(accounts, list):
        raise SmokeError("Phase 1.3 fixture post_block accounts must be a list")
    result: dict[str, dict[str, Any]] = {}
    for account in accounts:
        if not isinstance(account, dict):
            raise SmokeError("Phase 1.3 fixture account must be an object")
        address = account.get("address")
        if not isinstance(address, str):
            raise SmokeError("Phase 1.3 fixture account address must be a string")
        result[address] = account
    return result


def query_string(values: dict[str, Any]) -> str:
    return "&".join(f"{key}={value}" for key, value in values.items())


def api_get(
    *,
    api_binary: Path,
    xriq_dir: Path,
    chain_file: Path,
    pending_file: Path,
    target: str,
    artifact_path: Path,
    validate: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    return assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        target,
        200,
        artifact_path,
        validate,
    )


def validate_base_transfer(payload: dict[str, Any], fixture: dict[str, Any]) -> str:
    base = fixture["base_chain_setup"]
    transfer = base["transfer"]
    expected = base["expected"]
    require_equal(payload, "command", "preflight-transfer", "Phase 1.3 base transfer")
    require_equal(
        payload,
        "confirmed_block_height",
        expected["confirmed_block_height"],
        "Phase 1.3 base transfer",
    )
    require_equal(
        payload,
        "confirmed_transaction_index",
        expected["confirmed_transaction_index"],
        "Phase 1.3 base transfer",
    )
    require_equal(
        payload,
        "final_balance_base_units",
        expected["sender_balance_base_units"],
        "Phase 1.3 base transfer",
    )
    require_equal(payload, "final_nonce", expected["sender_nonce"], "Phase 1.3 base transfer")
    require_equal(
        payload,
        "pending_transactions",
        expected["pending_transactions"],
        "Phase 1.3 base transfer",
    )
    require_equal(payload, "from", transfer["from_address"], "Phase 1.3 base transfer")
    require_equal(payload, "to", transfer["to_address"], "Phase 1.3 base transfer")
    tx_hash = require_hash(
        payload.get("transaction_hash") or payload.get("tx_hash"),
        "Phase 1.3 base transfer tx hash",
    )
    return tx_hash


def validate_wallet_send(
    payload: dict[str, Any],
    *,
    step: dict[str, Any],
    chain_file: Path,
    pending_file: Path,
) -> str:
    context = "Phase 1.3 wallet send"
    request = step["request"]
    expected = step["expected"]
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "endpoint", step["endpoint"], context)
    require_equal(payload, "code", expected["code"], context)
    require_equal(payload, "status", expected["status"], context)
    require_equal(payload, "mutation", expected["mutation"], context)
    require_equal(payload, "warning", "local-private-devnet-only", context)

    transaction = payload.get("transaction")
    if not isinstance(transaction, dict):
        raise SmokeError(f"{context}: expected transaction object")
    tx_hash = require_hash(transaction.get("tx_hash"), f"{context} tx hash")
    require_equal(transaction, "status", expected["wallet_transaction_status"], context)
    require_equal(transaction, "from_address", request["from_address"], context)
    require_equal(transaction, "to_address", request["to_address"], context)
    require_equal(transaction, "amount_base_units", request["amount_base_units"], context)
    require_equal(transaction, "fee_base_units", request["fee_base_units"], context)
    require_equal(transaction, "nonce", request["nonce"], context)
    require_equal(transaction, "expires_at_height", request["expires_at_height"], context)
    require_equal(transaction, "block_height", None, context)
    require_equal(transaction, "transaction_index", None, context)

    pending_state = payload.get("pending_state")
    if not isinstance(pending_state, dict):
        raise SmokeError(f"{context}: expected pending_state object")
    require_equal(pending_state, "before_count", expected["pending_before_count"], context)
    require_equal(pending_state, "after_count", expected["pending_after_count"], context)
    require_equal(pending_state, "added_tx_hash", tx_hash, context)
    require_equal(pending_state, "pending_file", str(pending_file), context)

    chain_state = payload.get("chain_state")
    if not isinstance(chain_state, dict):
        raise SmokeError(f"{context}: expected chain_state object")
    require_equal(chain_state, "chain_file", str(chain_file), context)
    require_equal(chain_state, "chain_unchanged", expected["chain_unchanged"], context)

    require_equal(expected, "audit_recording", "accepted-audit-event", context)
    require_equal(payload, "audit_event_recorded", True, context)
    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise SmokeError(f"{context}: expected audit_event object")
    require_equal(
        audit_event,
        "event_id",
        f"wallet-transfer-send:{step['local_request_id']}",
        context,
    )
    require_equal(audit_event, "action", expected["audit_action"], context)
    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise SmokeError(f"{context}: expected audit metadata object")
    require_equal(metadata, "local_request_id", step["local_request_id"], context)
    require_equal(metadata, "explicit_flag", "--enable-local-wallet-send", context)
    require_equal(metadata, "added_tx_hash", tx_hash, context)
    policy = metadata.get("metadata_policy")
    if not isinstance(policy, str) or "no signing material" not in policy:
        raise SmokeError(f"{context}: audit metadata policy must forbid signing material")
    if "custody material" not in policy:
        raise SmokeError(f"{context}: audit metadata policy must forbid custody material")
    return tx_hash


def validate_block_production(
    payload: dict[str, Any],
    *,
    step: dict[str, Any],
    tx_hash: str,
    chain_file: Path,
    pending_file: Path,
) -> str:
    context = "Phase 1.3 block production"
    expected = step["expected"]
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "endpoint", step["endpoint"], context)
    require_equal(payload, "code", expected["code"], context)
    require_equal(payload, "status", expected["status"], context)
    require_equal(payload, "mutation", expected["mutation"], context)
    require_equal(payload, "warning", "local-private-devnet-only", context)

    block = payload.get("block")
    if not isinstance(block, dict):
        raise SmokeError(f"{context}: expected block object")
    require_equal(block, "height", expected["current_height"], context)
    block_hash = require_hash(block.get("block_hash"), f"{context} block hash")
    require_equal(block, "transaction_count", expected["confirmed_transaction_count"], context)

    transactions = require_list(payload.get("confirmed_transactions"), context)
    if len(transactions) != expected["confirmed_transaction_count"]:
        raise SmokeError(f"{context}: expected one confirmed transaction")
    confirmed = transactions[0]
    if not isinstance(confirmed, dict):
        raise SmokeError(f"{context}: confirmed transaction must be object")
    require_equal(confirmed, "tx_hash", tx_hash, context)
    require_equal(confirmed, "status", "confirmed", context)
    require_equal(confirmed, "block_height", expected["current_height"], context)
    require_equal(confirmed, "transaction_index", 0, context)
    require_equal(confirmed, "block_hash", block_hash, context)

    pending_state = payload.get("pending_state")
    if not isinstance(pending_state, dict):
        raise SmokeError(f"{context}: expected pending_state object")
    require_equal(pending_state, "before_count", expected["pending_before_count"], context)
    require_equal(pending_state, "after_count", expected["pending_after_count"], context)
    require_equal(pending_state, "removed_tx_hashes", [tx_hash], context)
    require_equal(pending_state, "pending_file", str(pending_file), context)

    chain_state = payload.get("chain_state")
    if not isinstance(chain_state, dict):
        raise SmokeError(f"{context}: expected chain_state object")
    require_equal(chain_state, "previous_height", expected["previous_height"], context)
    require_equal(chain_state, "current_height", expected["current_height"], context)
    require_equal(chain_state, "chain_file", str(chain_file), context)

    require_equal(payload, "audit_scope", expected["audit_scope"], context)
    require_equal(payload, "audit_event_recorded", True, context)
    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise SmokeError(f"{context}: expected audit_event object")
    require_equal(
        audit_event,
        "event_id",
        f"block-production:{step['local_request_id']}",
        context,
    )
    require_equal(audit_event, "action", expected["audit_action"], context)
    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise SmokeError(f"{context}: expected audit metadata object")
    require_equal(metadata, "local_request_id", step["local_request_id"], context)
    require_equal(metadata, "explicit_flag", "--enable-local-block-production", context)
    require_equal(
        metadata,
        "confirmed_transaction_count",
        expected["confirmed_transaction_count"],
        context,
    )
    return block_hash


def validate_transaction_status(payload: dict[str, Any], *, tx_hash: str, height: int) -> None:
    context = "Phase 1.3 wallet transaction status"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "tx_hash", tx_hash, context)
    require_equal(payload, "status", "confirmed", context)
    require_equal(payload, "block_height", height, context)
    require_equal(payload, "transaction_index", 0, context)
    require_hash(payload.get("block_hash"), f"{context} block hash")


def validate_mempool(payload: dict[str, Any], *, expected_count: int) -> None:
    context = "Phase 1.3 mempool"
    require_equal(payload, "pending_count", expected_count, context)
    entries = require_list(payload.get("entries"), context)
    if len(entries) != expected_count:
        raise SmokeError(f"{context}: expected {expected_count} entries, got {len(entries)}")


def validate_network(payload: dict[str, Any], fixture: dict[str, Any]) -> None:
    expected = fixture["post_block_expectations"]["explorer"]
    context = "Phase 1.3 network"
    require_equal(payload, "current_height", expected["current_height"], context)
    require_hash(payload.get("latest_block_hash"), f"{context} latest block")
    require_hash(payload.get("state_root"), f"{context} state root")


def validate_explorer(payload: dict[str, Any], fixture: dict[str, Any]) -> None:
    expected = fixture["post_block_expectations"]["explorer"]
    context = "Phase 1.3 explorer overview"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    chain = payload.get("chain")
    totals = payload.get("totals")
    if not isinstance(chain, dict) or not isinstance(totals, dict):
        raise SmokeError(f"{context}: expected chain and totals objects")
    require_equal(chain, "current_height", expected["current_height"], context)
    require_equal(chain, "stored_blocks", expected["stored_blocks"], context)
    require_equal(chain, "pending_transactions", expected["pending_transactions"], context)
    require_equal(totals, "transactions", expected["confirmed_transactions"], context)


def validate_account(payload: dict[str, Any], *, account: dict[str, Any]) -> None:
    context = f"Phase 1.3 account {account['address']}"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "address", account["address"], context)
    require_equal(payload, "balance_base_units", account["balance_base_units"], context)
    require_equal(payload, "nonce", account["nonce"], context)


def validate_history(
    payload: dict[str, Any],
    *,
    address: str,
    tx_hash: str,
    min_rows: int,
    expected_direction: str,
) -> None:
    context = f"Phase 1.3 wallet history {address}"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "address", address, context)
    transactions = require_list(payload.get("transactions"), context)
    if len(transactions) < min_rows:
        raise SmokeError(f"{context}: expected at least {min_rows} rows")
    matching = [
        tx
        for tx in transactions
        if isinstance(tx, dict)
        and tx.get("tx_hash") == tx_hash
        and tx.get("direction") == expected_direction
    ]
    if not matching:
        raise SmokeError(
            f"{context}: missing {expected_direction} row for behavior tx {tx_hash}"
        )


def validate_admin_audit(payload: dict[str, Any], fixture: dict[str, Any]) -> None:
    context = "Phase 1.3 admin audit"
    require_equal(payload, "environment", "private-devnet", context)
    events = require_list(payload.get("audit_events"), context)
    local_events = require_list(payload.get("local_refusal_audit_events"), context)
    if not any(isinstance(event, dict) and event.get("action") == "index_block" for event in events):
        raise SmokeError(f"{context}: expected indexed block audit event")
    required_actions = set(
        fixture["post_block_expectations"]["admin"]["required_refusal_audit_actions"]
    )
    available_actions = {str(event.get("action")) for event in local_events if isinstance(event, dict)}
    missing = sorted(required_actions.difference(available_actions))
    if missing:
        raise SmokeError(f"{context}: missing required refusal audit actions {missing}")


def validate_refusal(payload: dict[str, Any], *, expected_code: str) -> None:
    context = f"Phase 1.3 refusal {expected_code}"
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "code", expected_code, context)
    require_equal(payload, "mutation", "none", context)


def validate_error(payload: dict[str, Any], *, expected_code: str) -> None:
    context = f"Phase 1.3 error {expected_code}"
    error = payload.get("error")
    if not isinstance(error, dict):
        raise SmokeError(f"{context}: expected error object")
    require_equal(error, "code", expected_code, context)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.3 CPU-only local/private wallet behavior smoke "
            "using the canonical fixture contract."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node and xriq-api debug binaries.",
    )
    return parser.parse_args(argv)


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    fixture = load_fixture()
    root = repo_root()
    xriq_dir = root / "xriq"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    api_dir = artifact_dir / "api"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    write_json(artifact_dir / "contract-fixture.json", fixture)

    completed: list[str] = ["validated Phase 1.3 behavior fixture"]
    if not args.skip_build:
        run_command(
            "build XRIQ Phase 1.3 behavior smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )
        completed.append("build xriq-node and xriq-api")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "phase1-3-wallet-behavior-chain.bin"
    pending_file = artifact_dir / "phase1-3-wallet-behavior-pending.tsv"
    preflight_pending_file = artifact_dir / "phase1-3-wallet-behavior-preflight-pending.tsv"

    base = fixture["base_chain_setup"]
    base_transfer = base["transfer"]
    base_response = run_json(
        "create Phase 1.3 base chain",
        [
            str(node_binary),
            "preflight-transfer",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(preflight_pending_file),
            "--alice-balance",
            base["sender_start_balance_base_units"],
            "--from",
            base_transfer["from_address"],
            "--to",
            base_transfer["to_address"],
            "--amount",
            base_transfer["amount_base_units"],
            "--fee",
            base_transfer["fee_base_units"],
            "--expires-at-height",
            str(base_transfer["expires_at_height"]),
            "--timestamp-ms",
            str(base_transfer["timestamp_ms"]),
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    base_tx_hash = validate_base_transfer(base_response, fixture)
    write_json(artifact_dir / "base-confirmed-transfer.json", base_response)
    pending_file.write_text("", encoding="utf-8")
    completed.append("created base confirmed transfer")

    send_step = fixture_step(fixture, "wallet_send_to_pending")
    send_target = (
        f"/api/v1/wallet/transfers/send?local_request_id={send_step['local_request_id']}"
        f"&{query_string(send_step['request'])}"
    )
    wallet_send = assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        send_target,
        int(send_step["expected"]["http_status"]),
        api_dir / "wallet-send-accepted-local.json",
        lambda payload: None,
        extra_args=["--enable-local-wallet-send", "true"],
    )
    wallet_send_tx_hash = validate_wallet_send(
        wallet_send,
        step=send_step,
        chain_file=chain_file,
        pending_file=pending_file,
    )
    write_json(api_dir / "wallet-send-accepted-local.json", wallet_send)
    if wallet_send_tx_hash not in pending_file.read_text(encoding="utf-8"):
        raise SmokeError("Phase 1.3 wallet send did not append the pending transaction")
    completed.append("wallet send accepted to pending")

    api_get(
        api_binary=api_binary,
        xriq_dir=xriq_dir,
        chain_file=chain_file,
        pending_file=pending_file,
        target=f"/api/v1/wallet/transactions/{wallet_send_tx_hash}/status",
        artifact_path=api_dir / "wallet-send-pending-status.json",
        validate=lambda payload: require_equal(
            payload,
            "status",
            send_step["expected"]["wallet_transaction_status"],
            "Phase 1.3 pending wallet status",
        ),
    )
    completed.append("wallet send pending status")

    block_step = fixture_step(fixture, "produce_one_block")
    block_target = (
        f"/api/v1/blocks/produce?local_request_id={block_step['local_request_id']}"
        f"&{query_string(block_step['request'])}"
    )
    produced_block = assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        block_target,
        int(block_step["expected"]["http_status"]),
        api_dir / "block-production-accepted-local.json",
        lambda payload: None,
        extra_args=["--enable-local-block-production", "true"],
    )
    block_hash = validate_block_production(
        produced_block,
        step=block_step,
        tx_hash=wallet_send_tx_hash,
        chain_file=chain_file,
        pending_file=pending_file,
    )
    write_json(api_dir / "block-production-accepted-local.json", produced_block)
    if pending_file.read_text(encoding="utf-8") != "":
        raise SmokeError("Phase 1.3 block production did not clear pending file")
    completed.append("produced one local block")

    final_height = int(block_step["expected"]["current_height"])
    api_get(
        api_binary=api_binary,
        xriq_dir=xriq_dir,
        chain_file=chain_file,
        pending_file=pending_file,
        target=f"/api/v1/wallet/transactions/{wallet_send_tx_hash}/status",
        artifact_path=api_dir / "wallet-send-confirmed-status.json",
        validate=lambda payload: validate_transaction_status(
            payload,
            tx_hash=wallet_send_tx_hash,
            height=final_height,
        ),
    )
    completed.append("wallet send confirmed status")

    api_get(
        api_binary=api_binary,
        xriq_dir=xriq_dir,
        chain_file=chain_file,
        pending_file=pending_file,
        target="/api/v1/mempool?limit=5",
        artifact_path=api_dir / "mempool-empty-after-production.json",
        validate=lambda payload: validate_mempool(
            payload,
            expected_count=int(block_step["expected"]["mempool_pending_count"]),
        ),
    )
    completed.append("mempool empty after production")

    api_get(
        api_binary=api_binary,
        xriq_dir=xriq_dir,
        chain_file=chain_file,
        pending_file=pending_file,
        target="/api/v1/network",
        artifact_path=api_dir / "network-after-production.json",
        validate=lambda payload: validate_network(payload, fixture),
    )
    completed.append("network height after production")

    api_get(
        api_binary=api_binary,
        xriq_dir=xriq_dir,
        chain_file=chain_file,
        pending_file=pending_file,
        target="/api/v1/explorer/overview",
        artifact_path=api_dir / "explorer-overview-after-production.json",
        validate=lambda payload: validate_explorer(payload, fixture),
    )
    completed.append("explorer overview after production")

    accounts = expected_accounts(fixture)
    for address, account in accounts.items():
        api_get(
            api_binary=api_binary,
            xriq_dir=xriq_dir,
            chain_file=chain_file,
            pending_file=pending_file,
            target=f"/api/v1/wallet/accounts/{address}/balance",
            artifact_path=api_dir / f"wallet-balance-{address}.json",
            validate=lambda payload, account=account: validate_account(payload, account=account),
        )
    completed.append("wallet account balances after production")

    history_expected = fixture["post_block_expectations"]["wallet_history"]
    sender = fixture["identities"]["sender"]
    recipient = fixture["identities"]["behavior_recipient"]
    api_get(
        api_binary=api_binary,
        xriq_dir=xriq_dir,
        chain_file=chain_file,
        pending_file=pending_file,
        target=f"/api/v1/wallet/accounts/{sender}/history?limit=5",
        artifact_path=api_dir / "wallet-history-sender.json",
        validate=lambda payload: validate_history(
            payload,
            address=sender,
            tx_hash=wallet_send_tx_hash,
            min_rows=int(history_expected["sender_min_confirmed_rows"]),
            expected_direction=history_expected["behavior_transaction_direction"],
        ),
    )
    api_get(
        api_binary=api_binary,
        xriq_dir=xriq_dir,
        chain_file=chain_file,
        pending_file=pending_file,
        target=f"/api/v1/wallet/accounts/{recipient}/history?limit=5",
        artifact_path=api_dir / "wallet-history-recipient.json",
        validate=lambda payload: validate_history(
            payload,
            address=recipient,
            tx_hash=wallet_send_tx_hash,
            min_rows=1,
            expected_direction=history_expected["recipient_transaction_direction"],
        ),
    )
    completed.append("wallet history after production")

    api_get(
        api_binary=api_binary,
        xriq_dir=xriq_dir,
        chain_file=chain_file,
        pending_file=pending_file,
        target="/api/v1/admin/audit-events?limit=10",
        artifact_path=api_dir / "admin-audit-events.json",
        validate=lambda payload: validate_admin_audit(payload, fixture),
    )
    completed.append("admin audit visibility")

    negative_dir = artifact_dir / "negative"
    negative_dir.mkdir(parents=True, exist_ok=True)
    for case in fixture["negative_matrix"]:
        if case["case"] == "default_wallet_send_disabled":
            assert_api_method_status(
                api_binary,
                xriq_dir,
                chain_file,
                pending_file,
                "POST",
                f"/api/v1/wallet/transfers/send?local_request_id=phase1-3-disabled-send&{query_string(send_step['request'])}",
                403,
                negative_dir / "default-wallet-send-disabled.json",
                lambda payload, case=case: validate_refusal(
                    payload,
                    expected_code=case["expected_code"],
                ),
            )
        elif case["case"] == "default_block_production_disabled":
            assert_api_method_status(
                api_binary,
                xriq_dir,
                chain_file,
                pending_file,
                "POST",
                f"/api/v1/blocks/produce?local_request_id=phase1-3-disabled-block&{query_string(block_step['request'])}",
                403,
                negative_dir / "default-block-production-disabled.json",
                lambda payload, case=case: validate_refusal(
                    payload,
                    expected_code=case["expected_code"],
                ),
            )
        elif case["case"] == "wallet_submit_ui_deferred":
            submit_request = {
                "local_request_id": "phase1-3-disabled-submit",
                "draft_id": "phase1-3-draft",
                **send_step["request"],
            }
            assert_api_method_status(
                api_binary,
                xriq_dir,
                chain_file,
                pending_file,
                "POST",
                f"/api/v1/wallet/transfers/submit?{query_string(submit_request)}",
                403,
                negative_dir / "wallet-submit-deferred.json",
                lambda payload, case=case: validate_refusal(
                    payload,
                    expected_code=case["expected_code"],
                ),
            )
        elif case["case"] == "no_pending_block_production":
            empty_pending_file = artifact_dir / "phase1-3-empty-pending.tsv"
            empty_pending_file.write_text("", encoding="utf-8")
            assert_api_method_status(
                api_binary,
                xriq_dir,
                chain_file,
                empty_pending_file,
                "POST",
                f"/api/v1/blocks/produce?local_request_id=phase1-3-no-pending&{query_string(block_step['request'])}",
                400,
                negative_dir / "no-pending-block-production.json",
                lambda payload, case=case: validate_error(
                    payload,
                    expected_code=case["expected_code"],
                ),
                extra_args=["--enable-local-block-production", "true"],
            )
            if empty_pending_file.read_text(encoding="utf-8") != "":
                raise SmokeError("Phase 1.3 no-pending negative mutated pending file")
        elif case["case"] == "invalid_wallet_send_request":
            invalid_request = {**send_step["request"], "amount_base_units": "0"}
            assert_api_method_status(
                api_binary,
                xriq_dir,
                chain_file,
                pending_file,
                "POST",
                f"/api/v1/wallet/transfers/send?local_request_id=phase1-3-invalid-send&{query_string(invalid_request)}",
                400,
                negative_dir / "invalid-wallet-send-request.json",
                lambda payload, case=case: validate_error(
                    payload,
                    expected_code=case["expected_code"],
                ),
                extra_args=["--enable-local-wallet-send", "true"],
            )
    completed.append("negative behavior matrix")

    summary = {
        "ok": "xriq-phase1-3-wallet-behavior-smoke",
        "artifact_dir": str(artifact_dir),
        "fixture": str(FIXTURE_PATH),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "base_confirmed_tx_hash": base_tx_hash,
        "wallet_send_tx_hash": wallet_send_tx_hash,
        "produced_block_hash": block_hash,
        "completed": completed,
        "guards": [
            "CPU-only request-mode smoke",
            "wallet send requires --enable-local-wallet-send true",
            "block production requires --enable-local-block-production true",
            "wallet submit UI remains deferred",
            "default mutation paths remain refused",
            "no Docker, browser, server, GCP, Vast, tag, public, DEX, or custody scope",
        ],
    }
    write_json(artifact_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return summary


def main(argv: list[str] | None = None) -> int:
    try:
        run_smoke(parse_args(argv))
    except SmokeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
