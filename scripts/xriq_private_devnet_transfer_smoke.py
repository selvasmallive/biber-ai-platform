#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ALICE = "xriqdev1alice00000000000"
BOB = "xriqdev1bobbb00000000000"
FEE_SINK = "xriqdev1fees000000000000"


class SmokeError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-private-devnet-transfer-smoke-{timestamp}"


def run_xriq(xriq_dir: Path, *args: str) -> str:
    command = ["cargo", "run", "-q", *args]
    completed = subprocess.run(
        command,
        cwd=xriq_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SmokeError(
            "command failed: "
            + " ".join(command)
            + "\nstdout:\n"
            + completed.stdout
            + "\nstderr:\n"
            + completed.stderr
        )
    return completed.stdout.strip()


def run_node_json(xriq_dir: Path, *args: str) -> dict[str, Any]:
    output = run_xriq(xriq_dir, "-p", "xriq-node", "--", *args, "--format", "json")
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"xriq-node returned invalid JSON for {args}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SmokeError(f"xriq-node returned non-object JSON for {args}")
    return parsed


def run_wallet_json(xriq_dir: Path, *args: str) -> dict[str, Any]:
    output = run_xriq(xriq_dir, "-p", "xriq-wallet", "--", *args, "--format", "json")
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"xriq-wallet returned invalid JSON for {args}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise SmokeError(f"xriq-wallet returned non-object JSON for {args}")
    return parsed


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(payload: dict[str, Any], key: str, expected: Any, label: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise SmokeError(f"{label}: expected {key}={expected!r}, got {actual!r}")


def require_transaction_hash(payload: dict[str, Any], label: str) -> str:
    tx_hash = payload.get("transaction_hash") or payload.get("tx_hash")
    if not isinstance(tx_hash, str) or len(tx_hash) != 64:
        raise SmokeError(f"{label}: expected 64-character transaction hash, got {tx_hash!r}")
    return tx_hash


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run an isolated XRIQ private-devnet transfer, replay, account, "
            "and snapshot smoke without GPU or BIBER API."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument("--alice-balance", default="100")
    parser.add_argument("--amount", default="25")
    parser.add_argument("--fee", default="2")
    parser.add_argument("--expires-at-height", default="100")
    parser.add_argument("--timestamp-ms", default="1000")
    return parser.parse_args(argv)


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    artifact_dir = args.artifact_dir or default_artifact_dir(root)
    artifact_dir.mkdir(parents=True, exist_ok=False)

    chain_file = artifact_dir / "chain.bin"
    pending_file = artifact_dir / "pending.tsv"
    wallet_submit_pending_file = artifact_dir / "wallet-submit-pending.tsv"
    snapshot_dir = artifact_dir / "snapshot"
    imported_chain_file = artifact_dir / "imported-chain.bin"
    imported_pending_file = artifact_dir / "imported-pending.tsv"
    wallet_flow_chain_file = artifact_dir / "wallet-flow-chain.bin"
    wallet_flow_pending_file = artifact_dir / "wallet-flow-pending.tsv"

    wallet = run_wallet_json(
        xriq_dir,
        "transfer",
        "--chain-id",
        "xriq-devnet",
        "--from",
        ALICE,
        "--to",
        BOB,
        "--amount",
        args.amount,
        "--fee",
        args.fee,
        "--nonce",
        "0",
        "--expires-at-height",
        args.expires_at_height,
    )
    write_json(artifact_dir / "wallet-transfer-submit.json", wallet)
    require_equal(wallet, "format_version", "xriq-node-transfer-submit-v1", "wallet")
    require_equal(wallet, "from", ALICE, "wallet")
    require_equal(wallet, "to", BOB, "wallet")

    initial_status = run_node_json(
        xriq_dir,
        "status",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "initial-status.json", initial_status)
    require_equal(initial_status, "current_height", 0, "initial status")
    require_equal(initial_status, "stored_blocks", 0, "initial status")

    wallet_initial_status = run_wallet_json(
        xriq_dir,
        "status",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-status-initial.json", wallet_initial_status)
    require_equal(wallet_initial_status, "command", "status", "wallet initial status")
    require_equal(wallet_initial_status, "current_height", 0, "wallet initial status")
    require_equal(wallet_initial_status, "pending_transactions", 0, "wallet initial status")
    require_equal(wallet_initial_status, "stored_blocks", 0, "wallet initial status")

    wallet_initial_check = run_wallet_json(
        xriq_dir,
        "check",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-check-initial.json", wallet_initial_check)
    require_equal(wallet_initial_check, "command", "check", "wallet initial check")
    require_equal(wallet_initial_check, "verified", True, "wallet initial check")
    require_equal(wallet_initial_check, "current_height", 0, "wallet initial check")
    require_equal(wallet_initial_check, "pending_transactions", 0, "wallet initial check")
    require_equal(wallet_initial_check, "stored_blocks", 0, "wallet initial check")

    preflight = run_node_json(
        xriq_dir,
        "preflight-transfer",
        "--chain-file",
        str(chain_file),
        "--pending-file",
        str(pending_file),
        "--alice-balance",
        args.alice_balance,
        "--from",
        ALICE,
        "--to",
        BOB,
        "--amount",
        args.amount,
        "--fee",
        args.fee,
        "--expires-at-height",
        args.expires_at_height,
        "--timestamp-ms",
        args.timestamp_ms,
    )
    write_json(artifact_dir / "preflight-transfer.json", preflight)
    require_equal(preflight, "command", "preflight-transfer", "preflight")
    require_equal(preflight, "confirmed_block_height", 1, "preflight")
    require_equal(preflight, "confirmed_transaction_index", 0, "preflight")
    require_equal(preflight, "final_balance_base_units", "73", "preflight")
    require_equal(preflight, "final_nonce", 1, "preflight")
    require_equal(preflight, "pending_transactions", 0, "preflight")
    tx_hash = require_transaction_hash(preflight, "preflight")

    if pending_file.exists() and pending_file.stat().st_size != 0:
        raise SmokeError(f"pending file was not compacted: {pending_file}")

    transaction = run_node_json(
        xriq_dir,
        "transaction-detail",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--tx-hash",
        tx_hash,
    )
    write_json(artifact_dir / "transaction-detail.json", transaction)
    require_equal(transaction, "status", "confirmed", "transaction")
    require_equal(transaction, "block_height", 1, "transaction")
    require_equal(transaction, "amount_base_units", args.amount, "transaction")

    wallet_tx_status = run_wallet_json(
        xriq_dir,
        "tx",
        "status",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--tx-hash",
        tx_hash,
    )
    write_json(artifact_dir / "wallet-tx-status.json", wallet_tx_status)
    require_equal(wallet_tx_status, "command", "tx-status", "wallet tx status")
    require_equal(wallet_tx_status, "status", "confirmed", "wallet tx status")
    require_equal(wallet_tx_status, "tx_hash", tx_hash, "wallet tx status")
    require_equal(wallet_tx_status, "block_height", 1, "wallet tx status")
    require_equal(wallet_tx_status, "amount_base_units", args.amount, "wallet tx status")

    wallet_auto_nonce_transfer = run_wallet_json(
        xriq_dir,
        "transfer",
        "--chain-id",
        "xriq-devnet",
        "--from",
        ALICE,
        "--to",
        BOB,
        "--amount",
        "5",
        "--fee",
        args.fee,
        "--nonce",
        "auto",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--expires-at-height",
        args.expires_at_height,
    )
    write_json(artifact_dir / "wallet-transfer-auto-nonce.json", wallet_auto_nonce_transfer)
    require_equal(
        wallet_auto_nonce_transfer,
        "format_version",
        "xriq-node-transfer-submit-v1",
        "wallet auto nonce transfer",
    )
    require_equal(wallet_auto_nonce_transfer, "nonce", 1, "wallet auto nonce transfer")
    require_equal(wallet_auto_nonce_transfer, "from", ALICE, "wallet auto nonce transfer")
    require_equal(wallet_auto_nonce_transfer, "to", BOB, "wallet auto nonce transfer")

    wallet_submit_pending = run_wallet_json(
        xriq_dir,
        "submit",
        "--chain-file",
        str(chain_file),
        "--pending-file",
        str(wallet_submit_pending_file),
        "--transfer-file",
        str(artifact_dir / "wallet-transfer-auto-nonce.json"),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-submit-pending.json", wallet_submit_pending)
    require_equal(wallet_submit_pending, "command", "submit-pending", "wallet submit pending")
    require_equal(wallet_submit_pending, "status", "pending", "wallet submit pending")
    require_equal(wallet_submit_pending, "nonce", 1, "wallet submit pending")
    require_equal(wallet_submit_pending, "amount_base_units", "5", "wallet submit pending")
    wallet_submit_tx_hash = require_transaction_hash(wallet_submit_pending, "wallet submit pending")

    wallet_submit_status = run_wallet_json(
        xriq_dir,
        "tx",
        "status",
        "--chain-file",
        str(chain_file),
        "--pending-file",
        str(wallet_submit_pending_file),
        "--alice-balance",
        args.alice_balance,
        "--tx-hash",
        wallet_submit_tx_hash,
    )
    write_json(artifact_dir / "wallet-submit-pending-status.json", wallet_submit_status)
    require_equal(wallet_submit_status, "command", "tx-status", "wallet submit pending status")
    require_equal(wallet_submit_status, "status", "pending", "wallet submit pending status")
    require_equal(
        wallet_submit_status,
        "tx_hash",
        wallet_submit_tx_hash,
        "wallet submit pending status",
    )
    require_equal(wallet_submit_status, "nonce", 1, "wallet submit pending status")
    require_equal(wallet_submit_status, "amount_base_units", "5", "wallet submit pending status")

    wallet_pending = run_wallet_json(
        xriq_dir,
        "pending",
        "--chain-file",
        str(chain_file),
        "--pending-file",
        str(wallet_submit_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-pending.json", wallet_pending)
    require_equal(wallet_pending, "command", "pending", "wallet pending")
    require_equal(wallet_pending, "pending_count", 1, "wallet pending")
    wallet_pending_transactions = wallet_pending.get("transactions")
    if not isinstance(wallet_pending_transactions, list) or len(wallet_pending_transactions) != 1:
        raise SmokeError("wallet pending: expected one pending transaction")
    wallet_pending_transaction = wallet_pending_transactions[0]
    if not isinstance(wallet_pending_transaction, dict):
        raise SmokeError("wallet pending: expected transaction object")
    require_equal(wallet_pending_transaction, "tx_hash", wallet_submit_tx_hash, "wallet pending")
    require_equal(wallet_pending_transaction, "received_order", 0, "wallet pending")
    require_equal(wallet_pending_transaction, "nonce", 1, "wallet pending")
    require_equal(wallet_pending_transaction, "amount_base_units", "5", "wallet pending")

    block = run_node_json(
        xriq_dir,
        "block-detail",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--height",
        "1",
    )
    write_json(artifact_dir / "block-detail.json", block)
    require_equal(block, "command", "block-detail", "block")
    require_equal(block, "height", 1, "block")
    require_equal(block, "transaction_count", 1, "block")
    transactions = block.get("transactions")
    if not isinstance(transactions, list) or not transactions:
        raise SmokeError("block: expected at least one transaction")
    first_transaction = transactions[0]
    if not isinstance(first_transaction, dict) or first_transaction.get("tx_hash") != tx_hash:
        raise SmokeError("block: first transaction did not match preflight transaction hash")

    alice = run_node_json(
        xriq_dir,
        "account-detail",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--address",
        ALICE,
    )
    write_json(artifact_dir / "account-alice.json", alice)
    require_equal(alice, "balance_base_units", "73", "alice account")
    require_equal(alice, "nonce", 1, "alice account")

    wallet_alice_balance = run_wallet_json(
        xriq_dir,
        "balance",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--address",
        ALICE,
    )
    write_json(artifact_dir / "wallet-balance-alice.json", wallet_alice_balance)
    require_equal(wallet_alice_balance, "command", "balance", "wallet alice balance")
    require_equal(wallet_alice_balance, "address", ALICE, "wallet alice balance")
    require_equal(
        wallet_alice_balance,
        "balance_base_units",
        alice["balance_base_units"],
        "wallet alice balance",
    )
    require_equal(wallet_alice_balance, "nonce", alice["nonce"], "wallet alice balance")

    wallet_accounts = run_wallet_json(
        xriq_dir,
        "accounts",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--limit",
        "10",
    )
    write_json(artifact_dir / "wallet-accounts.json", wallet_accounts)
    require_equal(wallet_accounts, "command", "accounts", "wallet accounts")
    require_equal(wallet_accounts, "account_count", 3, "wallet accounts")
    wallet_account_rows = wallet_accounts.get("accounts")
    if not isinstance(wallet_account_rows, list):
        raise SmokeError("wallet accounts: expected accounts array")
    accounts_by_address = {
        account.get("address"): account
        for account in wallet_account_rows
        if isinstance(account, dict)
    }
    require_equal(
        accounts_by_address.get(ALICE) or {},
        "balance_base_units",
        alice["balance_base_units"],
        "wallet accounts alice",
    )
    require_equal(
        accounts_by_address.get(BOB) or {},
        "balance_base_units",
        args.amount,
        "wallet accounts bob",
    )
    require_equal(
        accounts_by_address.get(FEE_SINK) or {},
        "balance_base_units",
        args.fee,
        "wallet accounts fee sink",
    )

    wallet_alice_history = run_wallet_json(
        xriq_dir,
        "history",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--address",
        ALICE,
        "--limit",
        "5",
    )
    write_json(artifact_dir / "wallet-history-alice.json", wallet_alice_history)
    require_equal(wallet_alice_history, "command", "history", "wallet alice history")
    require_equal(wallet_alice_history, "address", ALICE, "wallet alice history")
    require_equal(wallet_alice_history, "transaction_count", 1, "wallet alice history")
    wallet_transactions = wallet_alice_history.get("transactions")
    if not isinstance(wallet_transactions, list) or len(wallet_transactions) != 1:
        raise SmokeError("wallet alice history: expected one transaction")
    wallet_history_transaction = wallet_transactions[0]
    if not isinstance(wallet_history_transaction, dict):
        raise SmokeError("wallet alice history: expected transaction object")
    require_equal(wallet_history_transaction, "tx_hash", tx_hash, "wallet alice history")
    require_equal(wallet_history_transaction, "direction", "sent", "wallet alice history")
    require_equal(
        wallet_history_transaction,
        "amount_base_units",
        args.amount,
        "wallet alice history",
    )

    bob = run_node_json(
        xriq_dir,
        "account-detail",
        "--chain-file",
        str(chain_file),
        "--alice-balance",
        args.alice_balance,
        "--address",
        BOB,
    )
    write_json(artifact_dir / "account-bob.json", bob)
    require_equal(bob, "balance_base_units", args.amount, "bob account")
    require_equal(bob, "nonce", 0, "bob account")

    mempool = run_node_json(
        xriq_dir,
        "mempool-detail",
        "--chain-file",
        str(chain_file),
        "--pending-file",
        str(pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "mempool-detail.json", mempool)
    require_equal(mempool, "pending_count", 0, "mempool")

    snapshot_export = run_node_json(
        xriq_dir,
        "snapshot-export",
        "--chain-file",
        str(chain_file),
        "--pending-file",
        str(pending_file),
        "--snapshot-dir",
        str(snapshot_dir),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "snapshot-export.json", snapshot_export)
    require_equal(snapshot_export, "command", "snapshot-export", "snapshot export")
    require_equal(snapshot_export, "current_height", 1, "snapshot export")

    snapshot_list = run_node_json(
        xriq_dir,
        "snapshot-list",
        "--snapshot-root",
        str(artifact_dir),
        "--limit",
        "5",
    )
    write_json(artifact_dir / "snapshot-list.json", snapshot_list)
    require_equal(snapshot_list, "command", "snapshot-list", "snapshot list")
    require_equal(snapshot_list, "snapshot_count", 1, "snapshot list")
    snapshots = snapshot_list.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise SmokeError("snapshot list: expected one snapshot entry")
    first_snapshot = snapshots[0]
    if not isinstance(first_snapshot, dict):
        raise SmokeError("snapshot list: expected snapshot object")
    require_equal(first_snapshot, "snapshot_name", "snapshot", "snapshot list")
    require_equal(first_snapshot, "current_height", 1, "snapshot list")

    snapshot_latest = run_node_json(
        xriq_dir,
        "snapshot-latest",
        "--snapshot-root",
        str(artifact_dir),
    )
    write_json(artifact_dir / "snapshot-latest.json", snapshot_latest)
    require_equal(snapshot_latest, "command", "snapshot-latest", "snapshot latest")
    require_equal(snapshot_latest, "snapshot_name", "snapshot", "snapshot latest")
    require_equal(snapshot_latest, "current_height", 1, "snapshot latest")
    require_equal(
        snapshot_latest,
        "state_root",
        snapshot_export["state_root"],
        "snapshot latest",
    )

    snapshot_latest_check = run_node_json(
        xriq_dir,
        "snapshot-latest-check",
        "--snapshot-root",
        str(artifact_dir),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "snapshot-latest-check.json", snapshot_latest_check)
    require_equal(
        snapshot_latest_check,
        "command",
        "snapshot-latest-check",
        "snapshot latest check",
    )
    require_equal(snapshot_latest_check, "verified", True, "snapshot latest check")
    latest_mismatches = snapshot_latest_check.get("mismatches")
    if latest_mismatches != []:
        raise SmokeError(
            f"snapshot latest check: expected no mismatches, got {latest_mismatches!r}"
        )

    snapshot_detail = run_node_json(
        xriq_dir,
        "snapshot-detail",
        "--snapshot-dir",
        str(snapshot_dir),
    )
    write_json(artifact_dir / "snapshot-detail.json", snapshot_detail)
    require_equal(snapshot_detail, "command", "snapshot-detail", "snapshot detail")
    require_equal(snapshot_detail, "snapshot_name", "snapshot", "snapshot detail")
    require_equal(snapshot_detail, "current_height", 1, "snapshot detail")
    require_equal(snapshot_detail, "state_root", snapshot_export["state_root"], "snapshot detail")

    snapshot_check = run_node_json(
        xriq_dir,
        "snapshot-check",
        "--snapshot-dir",
        str(snapshot_dir),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "snapshot-check.json", snapshot_check)
    require_equal(snapshot_check, "command", "snapshot-check", "snapshot check")
    require_equal(snapshot_check, "verified", True, "snapshot check")
    mismatches = snapshot_check.get("mismatches")
    if mismatches != []:
        raise SmokeError(f"snapshot check: expected no mismatches, got {mismatches!r}")

    snapshot_import = run_node_json(
        xriq_dir,
        "snapshot-import",
        "--snapshot-dir",
        str(snapshot_dir),
        "--chain-file",
        str(imported_chain_file),
        "--pending-file",
        str(imported_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "snapshot-import.json", snapshot_import)
    require_equal(snapshot_import, "command", "snapshot-import", "snapshot import")
    require_equal(
        snapshot_import,
        "current_height",
        snapshot_export["current_height"],
        "snapshot import",
    )
    require_equal(snapshot_import, "state_root", snapshot_export["state_root"], "snapshot import")

    imported_chain_check = run_node_json(
        xriq_dir,
        "chain-check",
        "--chain-file",
        str(imported_chain_file),
        "--pending-file",
        str(imported_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "imported-chain-check.json", imported_chain_check)
    require_equal(imported_chain_check, "command", "chain-check", "imported chain check")
    require_equal(imported_chain_check, "verified", True, "imported chain check")
    require_equal(
        imported_chain_check,
        "current_height",
        snapshot_export["current_height"],
        "imported chain check",
    )
    require_equal(
        imported_chain_check,
        "state_root",
        snapshot_export["state_root"],
        "imported chain check",
    )
    require_equal(
        imported_chain_check,
        "pending_transactions",
        snapshot_export["pending_transactions"],
        "imported chain check",
    )

    imported_transaction = run_node_json(
        xriq_dir,
        "transaction-detail",
        "--chain-file",
        str(imported_chain_file),
        "--alice-balance",
        args.alice_balance,
        "--tx-hash",
        tx_hash,
    )
    write_json(artifact_dir / "imported-transaction-detail.json", imported_transaction)
    require_equal(imported_transaction, "status", "confirmed", "imported transaction")
    require_equal(imported_transaction, "block_height", 1, "imported transaction")

    wallet_flow_send = run_wallet_json(
        xriq_dir,
        "send",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--pending-file",
        str(wallet_flow_pending_file),
        "--chain-id",
        "xriq-devnet",
        "--from",
        ALICE,
        "--to",
        BOB,
        "--amount",
        args.amount,
        "--fee",
        args.fee,
        "--nonce",
        "auto",
        "--alice-balance",
        args.alice_balance,
        "--expires-at-height",
        args.expires_at_height,
    )
    write_json(artifact_dir / "wallet-flow-send-pending.json", wallet_flow_send)
    require_equal(wallet_flow_send, "command", "send-pending", "wallet flow send")
    require_equal(wallet_flow_send, "status", "pending", "wallet flow send")
    require_equal(wallet_flow_send, "nonce", 0, "wallet flow send")
    require_equal(wallet_flow_send, "amount_base_units", args.amount, "wallet flow send")
    wallet_flow_tx_hash = require_transaction_hash(wallet_flow_send, "wallet flow send")

    wallet_flow_pending_before = run_wallet_json(
        xriq_dir,
        "pending",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--pending-file",
        str(wallet_flow_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-flow-pending-before-block.json", wallet_flow_pending_before)
    require_equal(wallet_flow_pending_before, "pending_count", 1, "wallet flow pending before")
    wallet_flow_pending_transactions = wallet_flow_pending_before.get("transactions")
    if (
        not isinstance(wallet_flow_pending_transactions, list)
        or len(wallet_flow_pending_transactions) != 1
    ):
        raise SmokeError("wallet flow pending before: expected one pending transaction")
    wallet_flow_pending_transaction = wallet_flow_pending_transactions[0]
    if not isinstance(wallet_flow_pending_transaction, dict):
        raise SmokeError("wallet flow pending before: expected transaction object")
    require_equal(
        wallet_flow_pending_transaction,
        "tx_hash",
        wallet_flow_tx_hash,
        "wallet flow pending before",
    )

    wallet_flow_status_before = run_wallet_json(
        xriq_dir,
        "status",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--pending-file",
        str(wallet_flow_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-flow-status-before-block.json", wallet_flow_status_before)
    require_equal(wallet_flow_status_before, "current_height", 0, "wallet flow status before")
    require_equal(
        wallet_flow_status_before,
        "pending_transactions",
        1,
        "wallet flow status before",
    )
    require_equal(wallet_flow_status_before, "stored_blocks", 0, "wallet flow status before")

    wallet_flow_check_before = run_wallet_json(
        xriq_dir,
        "check",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--pending-file",
        str(wallet_flow_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-flow-check-before-block.json", wallet_flow_check_before)
    require_equal(wallet_flow_check_before, "command", "check", "wallet flow check before")
    require_equal(wallet_flow_check_before, "verified", True, "wallet flow check before")
    require_equal(wallet_flow_check_before, "current_height", 0, "wallet flow check before")
    require_equal(
        wallet_flow_check_before,
        "pending_transactions",
        1,
        "wallet flow check before",
    )

    wallet_flow_produced = run_node_json(
        xriq_dir,
        "produce-pending-block",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--pending-file",
        str(wallet_flow_pending_file),
        "--alice-balance",
        args.alice_balance,
        "--timestamp-ms",
        args.timestamp_ms,
    )
    write_json(artifact_dir / "wallet-flow-produced-pending-block.json", wallet_flow_produced)
    require_equal(
        wallet_flow_produced,
        "command",
        "produce-pending-block",
        "wallet flow produce",
    )
    require_equal(wallet_flow_produced, "current_height", 1, "wallet flow produce")
    require_equal(wallet_flow_produced, "applied_transactions", 1, "wallet flow produce")
    require_equal(wallet_flow_produced, "pending_transactions", 0, "wallet flow produce")
    included_hashes = wallet_flow_produced.get("included_transaction_hashes")
    if included_hashes != [wallet_flow_tx_hash]:
        raise SmokeError(
            "wallet flow produce: expected included transaction hash "
            f"{wallet_flow_tx_hash!r}, got {included_hashes!r}"
        )
    if wallet_flow_pending_file.exists() and wallet_flow_pending_file.stat().st_size != 0:
        raise SmokeError(f"wallet flow pending file was not compacted: {wallet_flow_pending_file}")

    wallet_flow_pending_after = run_wallet_json(
        xriq_dir,
        "pending",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--pending-file",
        str(wallet_flow_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-flow-pending-after-block.json", wallet_flow_pending_after)
    require_equal(wallet_flow_pending_after, "pending_count", 0, "wallet flow pending after")

    wallet_flow_status_after = run_wallet_json(
        xriq_dir,
        "status",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--pending-file",
        str(wallet_flow_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-flow-status-after-block.json", wallet_flow_status_after)
    require_equal(wallet_flow_status_after, "current_height", 1, "wallet flow status after")
    require_equal(
        wallet_flow_status_after,
        "pending_transactions",
        0,
        "wallet flow status after",
    )
    require_equal(wallet_flow_status_after, "stored_blocks", 1, "wallet flow status after")

    wallet_flow_check_after = run_wallet_json(
        xriq_dir,
        "check",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--pending-file",
        str(wallet_flow_pending_file),
        "--alice-balance",
        args.alice_balance,
    )
    write_json(artifact_dir / "wallet-flow-check-after-block.json", wallet_flow_check_after)
    require_equal(wallet_flow_check_after, "command", "check", "wallet flow check after")
    require_equal(wallet_flow_check_after, "verified", True, "wallet flow check after")
    require_equal(wallet_flow_check_after, "current_height", 1, "wallet flow check after")
    require_equal(
        wallet_flow_check_after,
        "pending_transactions",
        0,
        "wallet flow check after",
    )

    wallet_flow_confirmed = run_wallet_json(
        xriq_dir,
        "tx",
        "status",
        "--chain-file",
        str(wallet_flow_chain_file),
        "--alice-balance",
        args.alice_balance,
        "--tx-hash",
        wallet_flow_tx_hash,
    )
    write_json(artifact_dir / "wallet-flow-tx-status-confirmed.json", wallet_flow_confirmed)
    require_equal(wallet_flow_confirmed, "status", "confirmed", "wallet flow confirmed")
    require_equal(wallet_flow_confirmed, "tx_hash", wallet_flow_tx_hash, "wallet flow confirmed")
    require_equal(wallet_flow_confirmed, "block_height", 1, "wallet flow confirmed")
    require_equal(wallet_flow_confirmed, "amount_base_units", args.amount, "wallet flow confirmed")

    summary = {
        "ok": "xriq-private-devnet-transfer-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "snapshot_dir": str(snapshot_dir),
        "imported_chain_file": str(imported_chain_file),
        "wallet_flow_chain_file": str(wallet_flow_chain_file),
        "transaction_hash": tx_hash,
        "wallet_flow_transaction_hash": wallet_flow_tx_hash,
        "block_height": 1,
        "alice_balance_base_units": alice["balance_base_units"],
        "bob_balance_base_units": bob["balance_base_units"],
        "state_root": snapshot_export["state_root"],
    }
    write_json(artifact_dir / "summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    try:
        summary = run_smoke(parse_args(argv))
    except SmokeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
