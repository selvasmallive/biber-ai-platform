#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
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
    return xriq_dir / "target" / "debug" / f"{name}{suffix}"


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
            args.alice_balance,
        )
        wait_for_health(base_url, process)

        initial_status = http_json(base_url, "GET", "/v1/chain/status")
        write_json(artifact_dir / "initial-status.json", initial_status)
        require_equal(initial_status, "current_height", 0, "initial status")
        require_equal(initial_status, "pending_transactions", 0, "initial status")

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

        confirmed_transaction = http_json(base_url, "GET", f"/v1/transactions/{tx_hash}")
        write_json(artifact_dir / "confirmed-transaction.json", confirmed_transaction)
        require_equal(confirmed_transaction, "status", "confirmed", "confirmed transaction")
        require_equal(confirmed_transaction, "block_height", 1, "confirmed transaction")

        block = http_json(base_url, "GET", "/v1/blocks/1")
        write_json(artifact_dir / "block-detail.json", block)
        require_equal(block, "transaction_count", 1, "block")

        alice = http_json(base_url, "GET", f"/v1/accounts/{ALICE}")
        write_json(artifact_dir / "account-alice.json", alice)
        require_equal(alice, "balance_base_units", "73", "alice account")
        require_equal(alice, "nonce", 1, "alice account")

        bob = http_json(base_url, "GET", f"/v1/accounts/{BOB}")
        write_json(artifact_dir / "account-bob.json", bob)
        require_equal(bob, "balance_base_units", args.amount, "bob account")

        final_mempool = http_json(base_url, "GET", "/v1/mempool")
        write_json(artifact_dir / "final-mempool.json", final_mempool)
        require_equal(final_mempool, "pending_count", 0, "final mempool")

        overview = http_json(base_url, "GET", "/v1/explorer/overview?limit=5")
        write_json(artifact_dir / "overview.json", overview)
        require_equal(overview, "current_height", 1, "overview")

        summary = {
            "ok": "xriq-private-devnet-http-smoke",
            "artifact_dir": str(artifact_dir),
            "base_url": base_url,
            "chain_file": str(chain_file),
            "pending_file": str(pending_file),
            "transaction_hash": tx_hash,
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
