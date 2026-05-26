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
    snapshot_dir = artifact_dir / "snapshot"
    imported_chain_file = artifact_dir / "imported-chain.bin"
    imported_pending_file = artifact_dir / "imported-pending.tsv"

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

    summary = {
        "ok": "xriq-private-devnet-transfer-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "snapshot_dir": str(snapshot_dir),
        "imported_chain_file": str(imported_chain_file),
        "transaction_hash": tx_hash,
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
