#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


ALICE = "xriqdev1alice00000000000"
BOB = "xriqdev1bobbb00000000000"
CAROL = "xriqdev1carol00000000000"


class SmokeError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-1-local-e2e-smoke-{timestamp}"


def executable_path(xriq_dir: Path, name: str) -> Path:
    suffix = ".exe" if sys.platform.startswith("win") else ""
    target_dir = os.environ.get("CARGO_TARGET_DIR")
    if target_dir:
        target_path = Path(target_dir)
        if not target_path.is_absolute():
            target_path = xriq_dir / target_path
    else:
        target_path = xriq_dir / "target"
    return target_path / "debug" / f"{name}{suffix}"


def run_command(
    name: str,
    command: list[str],
    *,
    cwd: Path,
    capture: bool = True,
) -> str:
    print(f"==> {name}", flush=True)
    print("$ " + " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stdout = completed.stdout if capture else ""
        stderr = completed.stderr if capture else ""
        raise SmokeError(
            f"{name} failed with exit code {completed.returncode}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return completed.stdout.strip() if capture else ""


def run_json(name: str, command: list[str], *, cwd: Path) -> dict[str, Any]:
    output = run_command(name, command, cwd=cwd)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise SmokeError(f"{name}: command did not return valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise SmokeError(f"{name}: expected JSON object output")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise SmokeError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_hash(value: Any, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SmokeError(f"{context}: expected 64-character lowercase hex hash, got {value!r}")
    return value


def require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise SmokeError(f"{context}: expected list, got {type(value).__name__}")
    return value


def parse_api_request_output(output: str, context: str) -> tuple[int, str, dict[str, Any]]:
    match = re.match(r"status_code=(\d+)\nreason=([^\n]*)\nbody=(.*)\Z", output, re.DOTALL)
    if not match:
        raise SmokeError(f"{context}: unexpected xriq-api request output:\n{output}")
    status_code = int(match.group(1))
    reason = match.group(2)
    body_text = match.group(3)
    try:
        body = json.loads(body_text)
    except json.JSONDecodeError as error:
        raise SmokeError(f"{context}: API body was not valid JSON: {error}") from error
    if not isinstance(body, dict):
        raise SmokeError(f"{context}: expected API JSON object body")
    return status_code, reason, body


def assert_api_ok(
    api_binary: Path,
    xriq_dir: Path,
    chain_file: Path,
    pending_file: Path,
    target: str,
    artifact_path: Path,
    validate: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    output = run_command(
        f"xriq-api {target}",
        [
            str(api_binary),
            "request",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(pending_file),
            "--alice-balance",
            "100",
            "--target",
            target,
        ],
        cwd=xriq_dir,
    )
    status_code, reason, payload = parse_api_request_output(output, target)
    if status_code != 200:
        raise SmokeError(f"{target}: expected HTTP 200, got {status_code} {reason}: {payload}")
    if "environment" in payload:
        require_equal(payload, "environment", "private-devnet", target)
    validate(payload)
    write_json(artifact_path, payload)
    return payload


def assert_api_status(
    api_binary: Path,
    xriq_dir: Path,
    chain_file: Path,
    pending_file: Path,
    target: str,
    expected_status: int,
    artifact_path: Path,
    validate: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    output = run_command(
        f"xriq-api {target}",
        [
            str(api_binary),
            "request",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(pending_file),
            "--alice-balance",
            "100",
            "--target",
            target,
        ],
        cwd=xriq_dir,
    )
    status_code, reason, payload = parse_api_request_output(output, target)
    if status_code != expected_status:
        raise SmokeError(
            f"{target}: expected HTTP {expected_status}, got {status_code} {reason}: {payload}"
        )
    if "environment" in payload:
        require_equal(payload, "environment", "private-devnet", target)
    validate(payload)
    write_json(artifact_path, payload)
    return payload


def npm_command() -> str:
    return "npm.cmd" if sys.platform.startswith("win") else "npm"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local CPU-only XRIQ Phase 1.1 end-to-end smoke across "
            "contracts, product API routes, and React UI static guardrails."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-ui-check",
        action="store_true",
        help="Skip the React UI static guardrail check.",
    )
    parser.add_argument(
        "--skip-contract-check",
        action="store_true",
        help="Skip the Phase 1.1 contract/schema/fixture check.",
    )
    return parser.parse_args(argv)


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    ui_dir = xriq_dir / "apps" / "explorer-ui"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=False)
    api_artifact_dir = artifact_dir / "api"

    completed: list[str] = []
    skipped: list[str] = []
    routes_checked: list[str] = []
    failure_routes_checked: list[str] = []

    if args.skip_contract_check:
        skipped.append("phase1.1 contract check")
    else:
        run_command(
            "phase1.1 contract check",
            [sys.executable, str(root / "scripts" / "xriq_phase1_1_contract_check.py")],
            cwd=root,
        )
        completed.append("phase1.1 contract check")

    if args.skip_ui_check:
        skipped.append("explorer UI static guardrail")
    else:
        run_command("explorer UI static guardrail", [npm_command(), "run", "check"], cwd=ui_dir)
        completed.append("explorer UI static guardrail")

    run_command(
        "build xriq smoke binaries",
        ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-wallet", "-p", "xriq-api"],
        cwd=xriq_dir,
    )
    completed.append("build xriq smoke binaries")

    node_binary = executable_path(xriq_dir, "xriq-node")
    wallet_binary = executable_path(xriq_dir, "xriq-wallet")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, wallet_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary after build: {binary}")

    chain_file = artifact_dir / "chain.bin"
    preflight_pending_file = artifact_dir / "preflight-pending.tsv"
    pending_file = artifact_dir / "pending.tsv"
    transfer_file = artifact_dir / "pending-transfer.json"

    preflight = run_json(
        "create confirmed private-devnet transfer",
        [
            str(node_binary),
            "preflight-transfer",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(preflight_pending_file),
            "--alice-balance",
            "100",
            "--from",
            ALICE,
            "--to",
            BOB,
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    confirmed_tx_hash = require_hash(
        preflight.get("transaction_hash") or preflight.get("tx_hash"),
        "confirmed transfer hash",
    )
    require_equal(preflight, "confirmed_block_height", 1, "confirmed transfer")
    require_equal(preflight, "final_balance_base_units", "73", "confirmed transfer")
    write_json(artifact_dir / "confirmed-transfer.json", preflight)
    completed.append("confirmed transfer")

    pending_transfer = run_json(
        "create pending wallet transfer draft",
        [
            str(wallet_binary),
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            ALICE,
            "--to",
            CAROL,
            "--amount",
            "5",
            "--fee",
            "2",
            "--nonce",
            "1",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    write_json(transfer_file, pending_transfer)

    pending_submit = run_json(
        "submit durable pending transfer",
        [
            str(wallet_binary),
            "submit",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(pending_file),
            "--transfer-file",
            str(transfer_file),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    pending_tx_hash = require_hash(
        pending_submit.get("transaction_hash") or pending_submit.get("tx_hash"),
        "pending transfer hash",
    )
    require_equal(pending_submit, "status", "pending", "pending transfer")
    write_json(artifact_dir / "pending-submit.json", pending_submit)
    completed.append("pending transfer")

    def check(target: str, name: str, validate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        routes_checked.append(target)
        return assert_api_ok(
            api_binary,
            xriq_dir,
            chain_file,
            pending_file,
            target,
            api_artifact_dir / f"{name}.json",
            validate,
        )

    def check_status(
        target: str,
        name: str,
        expected_status: int,
        validate: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        failure_routes_checked.append(target)
        return assert_api_status(
            api_binary,
            xriq_dir,
            chain_file,
            pending_file,
            target,
            expected_status,
            api_artifact_dir / f"{name}.json",
            validate,
        )

    def validate_health(payload: dict[str, Any]) -> None:
        require_equal(payload, "ok", True, "health")
        require_equal(payload, "service", "xriq-api", "health")

    def validate_network(payload: dict[str, Any]) -> None:
        require_equal(payload, "current_height", 1, "network")
        require_hash(payload.get("latest_block_hash"), "network latest block hash")

    def validate_overview(payload: dict[str, Any]) -> None:
        chain = payload.get("chain")
        totals = payload.get("totals")
        if not isinstance(chain, dict) or not isinstance(totals, dict):
            raise SmokeError("overview: expected chain and totals objects")
        require_equal(chain, "current_height", 1, "overview chain")
        require_equal(chain, "pending_transactions", 1, "overview chain")
        require_equal(totals, "blocks", 1, "overview totals")
        require_equal(totals, "transactions", 1, "overview totals")

    def validate_blocks(payload: dict[str, Any]) -> None:
        blocks = require_list(payload.get("blocks"), "blocks")
        if len(blocks) != 1 or not isinstance(blocks[0], dict):
            raise SmokeError("blocks: expected exactly one block object")
        require_equal(blocks[0], "height", 1, "blocks")

    def validate_block(payload: dict[str, Any]) -> None:
        require_equal(payload, "height", 1, "block detail")
        transactions = require_list(payload.get("transactions"), "block transactions")
        if not transactions:
            raise SmokeError("block detail: expected transaction list")

    def validate_transactions(payload: dict[str, Any]) -> None:
        transactions = require_list(payload.get("transactions"), "transactions")
        if len(transactions) != 1 or not isinstance(transactions[0], dict):
            raise SmokeError("transactions: expected exactly one transaction object")
        require_equal(transactions[0], "tx_hash", confirmed_tx_hash, "transactions")

    def validate_transaction(payload: dict[str, Any]) -> None:
        require_equal(payload, "tx_hash", confirmed_tx_hash, "transaction detail")
        require_equal(payload, "status", "confirmed", "transaction detail")

    def validate_accounts(payload: dict[str, Any]) -> None:
        accounts = require_list(payload.get("accounts"), "accounts")
        addresses = {row.get("address") for row in accounts if isinstance(row, dict)}
        if ALICE not in addresses or BOB not in addresses:
            raise SmokeError("accounts: expected alice and bob")

    def validate_account(payload: dict[str, Any]) -> None:
        require_equal(payload, "address", ALICE, "account detail")
        require_equal(payload, "balance_base_units", "73", "account detail")

    def validate_account_history(payload: dict[str, Any]) -> None:
        history = require_list(payload.get("transactions"), "account history")
        if len(history) != 1 or not isinstance(history[0], dict):
            raise SmokeError("account history: expected one transaction")
        require_equal(history[0], "direction", "sent", "account history")

    def validate_mempool(payload: dict[str, Any]) -> None:
        require_equal(payload, "pending_count", 1, "mempool")
        require_equal(payload, "submit_status", "disabled", "mempool")
        require_equal(payload, "produce_block_status", "disabled", "mempool")
        entries = require_list(payload.get("entries"), "mempool entries")
        if len(entries) != 1 or not isinstance(entries[0], dict):
            raise SmokeError("mempool: expected one pending entry")
        require_equal(entries[0], "tx_hash", pending_tx_hash, "mempool entry")

    def validate_wallet_status(payload: dict[str, Any]) -> None:
        require_equal(payload, "pending_transactions", 1, "wallet status")
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, dict):
            raise SmokeError("wallet status: expected capabilities object")
        require_equal(capabilities, "draft", True, "wallet status capabilities")
        require_equal(capabilities, "submit", False, "wallet status capabilities")
        require_equal(capabilities, "send", False, "wallet status capabilities")

    def validate_wallet_accounts(payload: dict[str, Any]) -> None:
        require_list(payload.get("accounts"), "wallet accounts")
        if "private-devnet-preview-only-no-signing-no-submit" not in payload.get("warning", ""):
            raise SmokeError("wallet accounts: missing preview-only warning")

    def validate_wallet_balance(payload: dict[str, Any]) -> None:
        require_equal(payload, "address", ALICE, "wallet balance")
        require_equal(payload, "balance_base_units", "73", "wallet balance")

    def validate_confirmed_wallet_tx(payload: dict[str, Any]) -> None:
        require_equal(payload, "tx_hash", confirmed_tx_hash, "wallet confirmed tx")
        require_equal(payload, "status", "confirmed", "wallet confirmed tx")
        require_equal(payload, "block_height", 1, "wallet confirmed tx")

    def validate_pending_wallet_tx(payload: dict[str, Any]) -> None:
        require_equal(payload, "tx_hash", pending_tx_hash, "wallet pending tx")
        require_equal(payload, "status", "pending", "wallet pending tx")
        require_equal(payload, "block_height", None, "wallet pending tx")
        require_equal(payload, "transaction_index", None, "wallet pending tx")

    def validate_draft_preview(payload: dict[str, Any]) -> None:
        require_equal(payload, "mutation", "none", "draft preview")
        validation = payload.get("validation")
        balance = payload.get("balance")
        if not isinstance(validation, dict) or not isinstance(balance, dict):
            raise SmokeError("draft preview: expected validation and balance objects")
        require_equal(validation, "ok", True, "draft preview validation")
        require_equal(balance, "remaining_base_units", "66", "draft preview balance")

    def validate_draft_validation_failure(
        payload: dict[str, Any],
        context: str,
        expected_errors: list[str],
    ) -> None:
        require_equal(payload, "mutation", "none", context)
        validation = payload.get("validation")
        if not isinstance(validation, dict):
            raise SmokeError(f"{context}: expected validation object")
        require_equal(validation, "ok", False, context)
        errors = require_list(validation.get("errors"), context)
        joined_errors = "\n".join(str(error) for error in errors)
        for expected_error in expected_errors:
            if expected_error not in joined_errors:
                raise SmokeError(
                    f"{context}: missing expected error {expected_error!r} in {errors!r}"
                )

    def validate_combined_draft_failure(payload: dict[str, Any]) -> None:
        validate_draft_validation_failure(
            payload,
            "combined draft failure",
            [
                "sender and recipient must differ",
                "amount must be greater than zero",
                "fee must be at least 2 base units",
                "nonce must match sender nonce 1",
                "expiry must be greater than current height",
            ],
        )

    def validate_balance_draft_failure(payload: dict[str, Any]) -> None:
        validate_draft_validation_failure(
            payload,
            "balance draft failure",
            ["debit exceeds available balance"],
        )
        balance = payload.get("balance")
        if not isinstance(balance, dict):
            raise SmokeError("balance draft failure: expected balance object")
        require_equal(balance, "available_base_units", "73", "balance draft failure")
        require_equal(balance, "debit_base_units", "1002", "balance draft failure")
        require_equal(balance, "remaining_base_units", None, "balance draft failure")

    def validate_malformed_draft_request(payload: dict[str, Any]) -> None:
        error = payload.get("error")
        if not isinstance(error, dict):
            raise SmokeError("malformed draft request: expected error object")
        require_equal(error, "code", "bad_request", "malformed draft request")
        message = error.get("message")
        if not isinstance(message, str) or "invalid amount_base_units" not in message:
            raise SmokeError(
                "malformed draft request: expected invalid amount message, got "
                f"{message!r}"
            )

    def validate_node_status(payload: dict[str, Any]) -> None:
        require_equal(payload, "mode", "serve-readonly", "node status")
        require_equal(payload, "pending_transactions", 1, "node status")
        require_equal(payload, "wallet_submit_status", "disabled", "node status")
        require_equal(payload, "block_production_status", "disabled", "node status")

    def validate_indexer(payload: dict[str, Any]) -> None:
        require_equal(payload, "service", "xriq-indexer", "indexer status")
        require_equal(payload, "status", "current", "indexer status")
        require_equal(payload, "latest_indexed_height", 1, "indexer status")

    def validate_audit(payload: dict[str, Any]) -> None:
        events = require_list(payload.get("audit_events"), "audit events")
        if len(events) != 1 or not isinstance(events[0], dict):
            raise SmokeError("audit events: expected one event")
        require_equal(events[0], "actor", "xriq-indexer", "audit event")
        require_equal(events[0], "action", "index_block", "audit event")
        require_equal(events[0], "resource_type", "block", "audit event")

    def validate_snapshots(payload: dict[str, Any]) -> None:
        require_equal(
            payload,
            "warning",
            "private-devnet-read-only-snapshot-catalog-export-import-disabled",
            "snapshots",
        )
        snapshots = require_list(payload.get("snapshots"), "snapshots")
        if len(snapshots) != 1 or not isinstance(snapshots[0], dict):
            raise SmokeError("snapshots: expected one snapshot")
        require_equal(snapshots[0], "snapshot_name", "current-indexed-chain", "snapshots")
        require_equal(snapshots[0], "export_status", "disabled", "snapshots")
        require_equal(snapshots[0], "import_status", "disabled", "snapshots")

    def validate_snapshot_detail(payload: dict[str, Any]) -> None:
        require_equal(payload, "snapshot_name", "current-indexed-chain", "snapshot detail")
        require_equal(payload, "current_height", 1, "snapshot detail")
        require_equal(payload, "export_status", "disabled", "snapshot detail")
        require_equal(payload, "import_status", "disabled", "snapshot detail")

    def validate_iso_initiation(payload: dict[str, Any]) -> None:
        require_equal(payload, "not_certified", True, "iso initiation")
        require_equal(payload, "message_type", "payment_initiation_preview", "iso initiation")
        require_equal(payload, "source_tx_hash", confirmed_tx_hash, "iso initiation")

    def validate_iso_status(payload: dict[str, Any]) -> None:
        require_equal(payload, "not_certified", True, "iso status")
        require_equal(payload, "message_type", "payment_status_preview", "iso status")
        aligned = payload.get("iso20022_aligned")
        if not isinstance(aligned, dict):
            raise SmokeError("iso status: expected aligned object")
        require_equal(aligned, "transaction_status", "ACSC", "iso status")

    def validate_iso_statement(payload: dict[str, Any]) -> None:
        require_equal(payload, "not_certified", True, "iso statement")
        require_equal(payload, "message_type", "account_statement_preview", "iso statement")
        entries = require_list(payload.get("entries"), "iso statement entries")
        if len(entries) != 1 or not isinstance(entries[0], dict):
            raise SmokeError("iso statement: expected one statement entry")
        require_equal(entries[0], "direction", "debit", "iso statement")

    check("/api/v1/health", "health", validate_health)
    check("/api/v1/network", "network", validate_network)
    check("/api/v1/explorer/overview", "explorer-overview", validate_overview)
    check("/api/v1/blocks?limit=5", "blocks", validate_blocks)
    check("/api/v1/blocks/1", "block-detail", validate_block)
    check("/api/v1/transactions?limit=5", "transactions", validate_transactions)
    check(f"/api/v1/transactions/{confirmed_tx_hash}", "transaction-detail", validate_transaction)
    check("/api/v1/accounts?limit=5", "accounts", validate_accounts)
    check(f"/api/v1/accounts/{ALICE}", "account-detail", validate_account)
    check(
        f"/api/v1/accounts/{ALICE}/transactions?limit=5",
        "account-history",
        validate_account_history,
    )
    check("/api/v1/mempool?limit=5", "mempool", validate_mempool)
    check("/api/v1/wallet/status", "wallet-status", validate_wallet_status)
    check("/api/v1/wallet/accounts?limit=5", "wallet-accounts", validate_wallet_accounts)
    check(f"/api/v1/wallet/accounts/{ALICE}/balance", "wallet-balance", validate_wallet_balance)
    check(
        f"/api/v1/wallet/transactions/{confirmed_tx_hash}/status",
        "wallet-confirmed-tx-status",
        validate_confirmed_wallet_tx,
    )
    check(
        f"/api/v1/wallet/transactions/{pending_tx_hash}/status",
        "wallet-pending-tx-status",
        validate_pending_wallet_tx,
    )
    check(
        f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}&to_address={CAROL}&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100",
        "wallet-draft-preview",
        validate_draft_preview,
    )
    check_status(
        f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}&to_address={ALICE}&amount_base_units=0&fee_base_units=1&nonce=0&expires_at_height=1",
        "wallet-draft-preview-combined-failure",
        200,
        validate_combined_draft_failure,
    )
    check_status(
        f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}&to_address={CAROL}&amount_base_units=1000&fee_base_units=2&nonce=1&expires_at_height=100",
        "wallet-draft-preview-balance-failure",
        200,
        validate_balance_draft_failure,
    )
    check_status(
        f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}&to_address={CAROL}&amount_base_units=abc&fee_base_units=2&nonce=1&expires_at_height=100",
        "wallet-draft-preview-malformed-request",
        400,
        validate_malformed_draft_request,
    )
    check("/api/v1/admin/node/status", "admin-node-status", validate_node_status)
    check("/api/v1/admin/indexer/status", "admin-indexer-status", validate_indexer)
    check("/api/v1/admin/audit-events?limit=5", "admin-audit-events", validate_audit)
    check("/api/v1/snapshots", "snapshots", validate_snapshots)
    check("/api/v1/snapshots/current-indexed-chain", "snapshot-detail", validate_snapshot_detail)
    check(
        f"/api/v1/iso20022/payment-initiation/preview?tx_hash={confirmed_tx_hash}",
        "iso-payment-initiation",
        validate_iso_initiation,
    )
    check(
        f"/api/v1/iso20022/transactions/{confirmed_tx_hash}/status",
        "iso-payment-status",
        validate_iso_status,
    )
    check(
        f"/api/v1/iso20022/accounts/{ALICE}/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z",
        "iso-account-statement",
        validate_iso_statement,
    )
    completed.append("product API route smoke")
    completed.append("wallet draft failure smoke")

    summary = {
        "ok": "xriq-phase1-1-local-e2e-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "confirmed_tx_hash": confirmed_tx_hash,
        "pending_tx_hash": pending_tx_hash,
        "routes_checked": routes_checked,
        "failure_routes_checked": failure_routes_checked,
        "completed": completed,
        "skipped": skipped,
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
