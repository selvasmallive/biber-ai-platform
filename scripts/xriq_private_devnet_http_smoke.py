#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ALICE = "xriqdev1alice00000000000"
BOB = "xriqdev1bobbb00000000000"


class SmokeError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-private-devnet-http-smoke-{timestamp}"


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


def run_command(cwd: Path, *args: str) -> str:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise SmokeError(
            "command failed: "
            + " ".join(args)
            + "\nstdout:\n"
            + completed.stdout
            + "\nstderr:\n"
            + completed.stderr
        )
    return completed.stdout.strip()


def build_binaries(xriq_dir: Path) -> None:
    run_command(xriq_dir, "cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-wallet")


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def http_json(
    base_url: str,
    method: str,
    target: str,
    body: str | None = None,
    expected_status: int = 200,
) -> dict[str, Any]:
    data = None if body is None else body.encode("utf-8")
    request = Request(
        base_url + target,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=5) as response:
            status = response.status
            text = response.read().decode("utf-8")
    except HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8")
    except URLError as exc:
        raise SmokeError(f"{method} {target} failed: {exc}") from exc

    if status != expected_status:
        raise SmokeError(f"{method} {target}: expected HTTP {expected_status}, got {status}: {text}")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"{method} {target}: invalid JSON response: {exc}: {text}") from exc
    if not isinstance(parsed, dict):
        raise SmokeError(f"{method} {target}: expected JSON object response")
    return parsed


def require_equal(payload: dict[str, Any], key: str, expected: Any, label: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise SmokeError(f"{label}: expected {key}={expected!r}, got {actual!r}")


def require_transaction_hash(payload: dict[str, Any], label: str) -> str:
    tx_hash = payload.get("transaction_hash") or payload.get("tx_hash")
    if not isinstance(tx_hash, str) or len(tx_hash) != 64:
        raise SmokeError(f"{label}: expected 64-character transaction hash, got {tx_hash!r}")
    return tx_hash


def wait_for_health(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stderr = process.stderr.read() if process.stderr is not None else ""
            raise SmokeError(f"xriq-node server exited early with {process.returncode}: {stderr}")
        try:
            health = http_json(base_url, "GET", "/health")
            require_equal(health, "status", "ok", "health")
            return
        except Exception as exc:  # noqa: BLE001 - keep retrying during startup.
            last_error = exc
            time.sleep(0.2)
    raise SmokeError(f"xriq-node server did not become healthy: {last_error}")


def start_server(
    node_binary: Path,
    artifact_dir: Path,
    bind: str,
    chain_file: Path,
    pending_file: Path,
    snapshot_root: Path,
    alice_balance: str,
) -> subprocess.Popen[str]:
    stderr_log = artifact_dir / f"server-{datetime.now(UTC).strftime('%H%M%S%f')}.stderr.log"
    stderr_handle = stderr_log.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [
                str(node_binary),
                "serve-private",
                "--chain-file",
                str(chain_file),
                "--pending-file",
                str(pending_file),
                "--snapshot-root",
                str(snapshot_root),
                "--alice-balance",
                alice_balance,
                "--bind",
                bind,
            ],
            stdout=subprocess.DEVNULL,
            stderr=stderr_handle,
            text=True,
        )
    except Exception:
        stderr_handle.close()
        raise
    process.stderr_log_path = stderr_log  # type: ignore[attr-defined]
    process.stderr_handle = stderr_handle  # type: ignore[attr-defined]
    return process


def stop_server(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    stderr_handle = getattr(process, "stderr_handle", None)
    if stderr_handle is not None:
        stderr_handle.close()


def wallet_transfer_json(
    wallet_binary: Path,
    xriq_dir: Path,
    amount: str,
    fee: str,
    nonce: str,
    expires_at_height: str,
) -> str:
    return run_command(
        xriq_dir,
        str(wallet_binary),
        "transfer",
        "--chain-id",
        "xriq-devnet",
        "--from",
        ALICE,
        "--to",
        BOB,
        "--amount",
        amount,
        "--fee",
        fee,
        "--nonce",
        nonce,
        "--expires-at-height",
        expires_at_height,
        "--format",
        "json",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local XRIQ serve-private HTTP smoke against a real xriq-node "
            "process without Vast, BIBER API, or GPU."
        )
    )
    parser.add_argument("--artifact-dir", type=Path, default=None)
    parser.add_argument("--alice-balance", default="100")
    parser.add_argument("--amount", default="25")
    parser.add_argument("--fee", default="2")
    parser.add_argument("--expires-at-height", default="100")
    return parser.parse_args(argv)


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    artifact_dir = args.artifact_dir or default_artifact_dir(root)
    artifact_dir.mkdir(parents=True, exist_ok=False)

    build_binaries(xriq_dir)
    node_binary = executable_path(xriq_dir, "xriq-node")
    wallet_binary = executable_path(xriq_dir, "xriq-wallet")
    if not node_binary.exists():
        raise SmokeError(f"missing node binary after build: {node_binary}")
    if not wallet_binary.exists():
        raise SmokeError(f"missing wallet binary after build: {wallet_binary}")

    chain_file = artifact_dir / "chain.bin"
    pending_file = artifact_dir / "pending.tsv"
    snapshot_dir = artifact_dir / "http-snapshot"
    imported_chain_file = artifact_dir / "imported-chain.bin"
    imported_pending_file = artifact_dir / "imported-pending.tsv"
    port = free_local_port()
    bind = f"127.0.0.1:{port}"
    base_url = f"http://{bind}"
    process: subprocess.Popen[str] | None = None
    try:
        process = start_server(
            node_binary,
            artifact_dir,
            bind,
            chain_file,
            pending_file,
            artifact_dir,
            args.alice_balance,
        )
        wait_for_health(base_url, process)

        initial_status = http_json(base_url, "GET", "/v1/chain/status")
        write_json(artifact_dir / "initial-status.json", initial_status)
        require_equal(initial_status, "current_height", 0, "initial status")
        require_equal(initial_status, "pending_transactions", 0, "initial status")
        initial_chain_check = http_json(base_url, "GET", "/v1/chain/check")
        write_json(artifact_dir / "initial-chain-check.json", initial_chain_check)
        require_equal(initial_chain_check, "verified", True, "initial chain check")
        require_equal(initial_chain_check, "current_height", 0, "initial chain check")

        transfer_body = wallet_transfer_json(
            wallet_binary,
            xriq_dir,
            args.amount,
            args.fee,
            "0",
            args.expires_at_height,
        )
        (artifact_dir / "wallet-transfer-submit.json").write_text(
            transfer_body + "\n",
            encoding="utf-8",
        )
        try:
            wallet_payload = json.loads(transfer_body)
        except json.JSONDecodeError as exc:
            raise SmokeError(f"wallet transfer JSON was invalid: {exc}") from exc
        if not isinstance(wallet_payload, dict):
            raise SmokeError("wallet transfer JSON was not an object")
        wallet_tx_hash = require_transaction_hash(wallet_payload, "wallet transfer")
        pending_submit = http_json(
            base_url,
            "POST",
            "/v1/mempool",
            body=transfer_body,
            expected_status=202,
        )
        write_json(artifact_dir / "pending-submit.json", pending_submit)
        require_equal(pending_submit, "status", "pending", "pending submit")
        tx_hash = require_transaction_hash(pending_submit, "pending submit")
        if tx_hash != wallet_tx_hash:
            raise SmokeError(
                "pending submit: wallet transaction_hash did not match node tx_hash "
                f"({wallet_tx_hash} != {tx_hash})"
            )

        pending_mempool = http_json(base_url, "GET", "/v1/mempool")
        write_json(artifact_dir / "pending-mempool.json", pending_mempool)
        require_equal(pending_mempool, "pending_count", 1, "pending mempool")

        stop_server(process)
        process = start_server(
            node_binary,
            artifact_dir,
            bind,
            chain_file,
            pending_file,
            artifact_dir,
            args.alice_balance,
        )
        wait_for_health(base_url, process)

        reloaded_transaction = http_json(base_url, "GET", f"/v1/transactions/{tx_hash}")
        write_json(artifact_dir / "reloaded-pending-transaction.json", reloaded_transaction)
        require_equal(reloaded_transaction, "status", "pending", "reloaded transaction")

        produced = http_json(
            base_url,
            "POST",
            "/v1/blocks?timestamp_ms=1000&consensus_round=0",
            expected_status=201,
        )
        write_json(artifact_dir / "produced-block.json", produced)
        require_equal(produced, "current_height", 1, "produced block")
        require_equal(produced, "applied_transactions", 1, "produced block")
        block_hash = produced.get("block_hash")
        if not isinstance(block_hash, str) or len(block_hash) != 64:
            raise SmokeError(f"produced block: expected 64-character block_hash, got {block_hash!r}")

        chain_check = http_json(base_url, "GET", "/v1/chain/check")
        write_json(artifact_dir / "chain-check.json", chain_check)
        require_equal(chain_check, "verified", True, "chain check")
        require_equal(chain_check, "current_height", 1, "chain check")
        require_equal(chain_check, "state_root", produced.get("state_root"), "chain check")

        confirmed_transaction = http_json(base_url, "GET", f"/v1/transactions/{tx_hash}")
        write_json(artifact_dir / "confirmed-transaction.json", confirmed_transaction)
        require_equal(confirmed_transaction, "status", "confirmed", "confirmed transaction")
        require_equal(confirmed_transaction, "block_height", 1, "confirmed transaction")

        block = http_json(base_url, "GET", "/v1/blocks/1")
        write_json(artifact_dir / "block-detail.json", block)
        require_equal(block, "transaction_count", 1, "block")

        block_by_hash = http_json(base_url, "GET", f"/v1/blocks/{block_hash}")
        write_json(artifact_dir / "block-detail-by-hash.json", block_by_hash)
        require_equal(block_by_hash, "height", 1, "block by hash")
        require_equal(block_by_hash, "block_hash", block_hash, "block by hash")

        latest_block = http_json(base_url, "GET", "/v1/blocks/latest")
        write_json(artifact_dir / "block-detail-latest.json", latest_block)
        require_equal(latest_block, "height", 1, "latest block")
        require_equal(latest_block, "block_hash", block_hash, "latest block")

        block_list = http_json(base_url, "GET", "/v1/blocks?limit=5")
        write_json(artifact_dir / "block-list.json", block_list)
        require_equal(block_list, "block_count", 1, "block list")
        blocks = block_list.get("blocks")
        if not isinstance(blocks, list) or not blocks:
            raise SmokeError("block list: expected one block entry")
        first_block = blocks[0]
        if not isinstance(first_block, dict):
            raise SmokeError("block list: expected block object")
        require_equal(first_block, "height", 1, "block list")
        require_equal(first_block, "block_hash", block_hash, "block list")

        alice = http_json(base_url, "GET", f"/v1/accounts/{ALICE}")
        write_json(artifact_dir / "account-alice.json", alice)
        require_equal(alice, "balance_base_units", "73", "alice account")
        require_equal(alice, "nonce", 1, "alice account")

        bob = http_json(base_url, "GET", f"/v1/accounts/{BOB}")
        write_json(artifact_dir / "account-bob.json", bob)
        require_equal(bob, "balance_base_units", args.amount, "bob account")

        accounts = http_json(base_url, "GET", "/v1/accounts?limit=5")
        write_json(artifact_dir / "accounts.json", accounts)
        require_equal(accounts, "account_count", 3, "accounts")
        account_entries = accounts.get("accounts")
        if not isinstance(account_entries, list) or len(account_entries) < 2:
            raise SmokeError("accounts: expected at least alice and bob account entries")
        account_addresses = {
            entry.get("address")
            for entry in account_entries
            if isinstance(entry, dict)
        }
        if ALICE not in account_addresses or BOB not in account_addresses:
            raise SmokeError("accounts: expected alice and bob addresses")

        alice_transactions = http_json(
            base_url,
            "GET",
            f"/v1/accounts/{ALICE}/transactions?limit=5",
        )
        write_json(artifact_dir / "account-alice-transactions.json", alice_transactions)
        require_equal(
            alice_transactions,
            "transaction_count",
            1,
            "alice account transactions",
        )
        transactions = alice_transactions.get("transactions")
        if not isinstance(transactions, list) or not transactions:
            raise SmokeError("alice account transactions: expected one transaction")
        first_account_transaction = transactions[0]
        if not isinstance(first_account_transaction, dict):
            raise SmokeError("alice account transactions: expected transaction object")
        require_equal(first_account_transaction, "tx_hash", tx_hash, "alice account transaction")
        require_equal(first_account_transaction, "direction", "sent", "alice account transaction")

        latest_transactions = http_json(base_url, "GET", "/v1/transactions?limit=5")
        write_json(artifact_dir / "latest-transactions.json", latest_transactions)
        require_equal(latest_transactions, "transaction_count", 1, "latest transactions")
        transactions = latest_transactions.get("transactions")
        if not isinstance(transactions, list) or not transactions:
            raise SmokeError("latest transactions: expected one transaction")
        first_latest_transaction = transactions[0]
        if not isinstance(first_latest_transaction, dict):
            raise SmokeError("latest transactions: expected transaction object")
        require_equal(first_latest_transaction, "tx_hash", tx_hash, "latest transaction")
        require_equal(first_latest_transaction, "block_height", 1, "latest transaction")

        final_mempool = http_json(base_url, "GET", "/v1/mempool")
        write_json(artifact_dir / "final-mempool.json", final_mempool)
        require_equal(final_mempool, "pending_count", 0, "final mempool")

        overview = http_json(base_url, "GET", "/v1/explorer/overview?limit=5")
        write_json(artifact_dir / "overview.json", overview)
        require_equal(overview, "current_height", 1, "overview")
        require_equal(overview, "state_root", produced.get("state_root"), "overview")

        snapshot_query = urlencode({"snapshot_dir": str(snapshot_dir)})
        snapshot_export = http_json(
            base_url,
            "POST",
            f"/v1/snapshots/export?{snapshot_query}",
            expected_status=201,
        )
        write_json(artifact_dir / "snapshot-export.json", snapshot_export)
        require_equal(snapshot_export, "command", "snapshot-export", "snapshot export")
        require_equal(snapshot_export, "current_height", 1, "snapshot export")
        if not (snapshot_dir / "chain.bin").exists():
            raise SmokeError(
                f"snapshot chain file was not created: {snapshot_dir / 'chain.bin'}"
            )
        if not (snapshot_dir / "manifest.json").exists():
            raise SmokeError(
                f"snapshot manifest was not created: {snapshot_dir / 'manifest.json'}"
            )

        snapshot_list = http_json(base_url, "GET", "/v1/snapshots?limit=5")
        write_json(artifact_dir / "http-snapshot-list.json", snapshot_list)
        require_equal(snapshot_list, "command", "snapshot-list", "snapshot list")
        require_equal(snapshot_list, "snapshot_count", 1, "snapshot list")
        snapshots = snapshot_list.get("snapshots")
        if not isinstance(snapshots, list) or not snapshots:
            raise SmokeError("snapshot list: expected one snapshot entry")
        first_snapshot = snapshots[0]
        if not isinstance(first_snapshot, dict):
            raise SmokeError("snapshot list: expected snapshot object")
        require_equal(first_snapshot, "snapshot_name", "http-snapshot", "snapshot list")
        require_equal(first_snapshot, "current_height", 1, "snapshot list")

        snapshot_detail = http_json(base_url, "GET", "/v1/snapshots/http-snapshot")
        write_json(artifact_dir / "http-snapshot-detail.json", snapshot_detail)
        require_equal(snapshot_detail, "command", "snapshot-detail", "snapshot detail")
        require_equal(snapshot_detail, "snapshot_name", "http-snapshot", "snapshot detail")
        require_equal(
            snapshot_detail,
            "state_root",
            snapshot_export["state_root"],
            "snapshot detail",
        )

        stop_server(process)
        process = start_server(
            node_binary,
            artifact_dir,
            bind,
            imported_chain_file,
            imported_pending_file,
            artifact_dir,
            args.alice_balance,
        )
        wait_for_health(base_url, process)

        snapshot_import = http_json(
            base_url,
            "POST",
            f"/v1/snapshots/import?{snapshot_query}",
            expected_status=201,
        )
        write_json(artifact_dir / "snapshot-import.json", snapshot_import)
        require_equal(snapshot_import, "command", "snapshot-import", "snapshot import")
        require_equal(snapshot_import, "current_height", 1, "snapshot import")
        require_equal(
            snapshot_import,
            "state_root",
            snapshot_export["state_root"],
            "snapshot import",
        )

        imported_transaction = http_json(base_url, "GET", f"/v1/transactions/{tx_hash}")
        write_json(artifact_dir / "imported-transaction.json", imported_transaction)
        require_equal(imported_transaction, "status", "confirmed", "imported transaction")
        require_equal(imported_transaction, "block_height", 1, "imported transaction")

        summary = {
            "ok": "xriq-private-devnet-http-smoke",
            "artifact_dir": str(artifact_dir),
            "base_url": base_url,
            "chain_file": str(chain_file),
            "imported_chain_file": str(imported_chain_file),
            "imported_pending_file": str(imported_pending_file),
            "pending_file": str(pending_file),
            "snapshot_dir": str(snapshot_dir),
            "transaction_hash": tx_hash,
            "block_hash": block_hash,
            "block_height": 1,
            "alice_balance_base_units": alice["balance_base_units"],
            "bob_balance_base_units": bob["balance_base_units"],
        }
        write_json(artifact_dir / "summary.json", summary)
        return summary
    finally:
        stop_server(process)


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
