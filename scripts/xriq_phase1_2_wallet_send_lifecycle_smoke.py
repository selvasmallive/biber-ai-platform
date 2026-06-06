#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xriq_phase1_1_local_e2e_smoke import (
    ALICE,
    BOB,
    CAROL,
    SmokeError,
    assert_api_method_status,
    assert_api_status,
    executable_path,
    free_local_port,
    http_json,
    repo_root,
    require_equal,
    require_hash,
    require_list,
    run_command,
    run_json,
    start_api_readonly_server,
    stop_process,
    wait_for_api_readonly_server,
    write_json,
)


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-2-wallet-send-lifecycle-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.2 local wallet-send to confirmed-block "
            "lifecycle smoke on copied/private-devnet state."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for lifecycle smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node and xriq-api debug binaries.",
    )
    return parser.parse_args(argv)


def validate_wallet_send_accepted(
    payload: dict[str, Any],
    *,
    chain_file: Path,
    pending_file: Path,
    expected_local_request_id: str = "local-wallet-send-lifecycle-1",
    context: str = "wallet-send lifecycle accepted",
) -> str:
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "endpoint", "POST /api/v1/wallet/transfers/send", context)
    require_equal(payload, "code", "wallet_send_accepted_local_only", context)
    require_equal(payload, "status", "pending", context)
    require_equal(payload, "mutation", "pending_state_only", context)
    require_equal(payload, "warning", "local-private-devnet-only", context)

    transaction = payload.get("transaction")
    if not isinstance(transaction, dict):
        raise SmokeError(f"{context}: expected transaction object")
    tx_hash = require_hash(transaction.get("tx_hash"), f"{context} tx hash")
    require_equal(transaction, "status", "pending", context)
    require_equal(transaction, "from_address", ALICE, context)
    require_equal(transaction, "to_address", CAROL, context)
    require_equal(transaction, "amount_base_units", "5", context)
    require_equal(transaction, "fee_base_units", "2", context)
    require_equal(transaction, "nonce", 1, context)
    require_equal(transaction, "expires_at_height", 100, context)
    require_equal(transaction, "block_height", None, context)
    require_equal(transaction, "transaction_index", None, context)

    pending_state = payload.get("pending_state")
    if not isinstance(pending_state, dict):
        raise SmokeError(f"{context}: expected pending_state object")
    require_equal(pending_state, "before_count", 0, f"{context} pending")
    require_equal(pending_state, "after_count", 1, f"{context} pending")
    require_equal(pending_state, "added_tx_hash", tx_hash, f"{context} pending")
    require_equal(pending_state, "pending_file", str(pending_file), f"{context} pending")

    chain_state = payload.get("chain_state")
    if not isinstance(chain_state, dict):
        raise SmokeError(f"{context}: expected chain_state object")
    require_equal(chain_state, "current_height", 1, f"{context} chain")
    require_hash(chain_state.get("latest_block_hash"), f"{context} latest block")
    require_equal(chain_state, "chain_file", str(chain_file), f"{context} chain")
    require_equal(chain_state, "chain_unchanged", True, f"{context} chain")

    require_equal(payload, "audit_event_recorded", True, context)
    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise SmokeError(f"{context}: expected audit_event object")
    require_equal(
        audit_event,
        "event_id",
        f"wallet-transfer-send:{expected_local_request_id}",
        f"{context} audit",
    )
    require_equal(audit_event, "actor", "local-private-devnet-operator", f"{context} audit")
    require_equal(audit_event, "action", "wallet_transfer_send_attempt", f"{context} audit")
    require_equal(audit_event, "resource_type", "wallet_transfer", f"{context} audit")
    require_equal(audit_event, "resource_id", "local_request_id", f"{context} audit")
    require_equal(audit_event, "environment", "private-devnet", f"{context} audit")
    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise SmokeError(f"{context}: expected audit metadata object")
    require_equal(metadata, "outcome", "accepted", f"{context} metadata")
    require_equal(metadata, "status", "pending", f"{context} metadata")
    require_equal(metadata, "explicit_flag", "--enable-local-wallet-send", f"{context} metadata")
    require_equal(metadata, "local_request_id", expected_local_request_id, context)
    require_equal(metadata, "added_tx_hash", tx_hash, f"{context} metadata")
    metadata_policy = metadata.get("metadata_policy")
    if not isinstance(metadata_policy, str) or "no signing material" not in metadata_policy:
        raise SmokeError(f"{context}: expected metadata policy to forbid signing material")
    if "custody material" not in metadata_policy:
        raise SmokeError(f"{context}: expected metadata policy to forbid custody material")
    return tx_hash


def validate_block_production_accepted(
    payload: dict[str, Any],
    *,
    tx_hash: str,
    chain_file: Path,
    pending_file: Path,
    expected_local_request_id: str = "local-wallet-send-lifecycle-2",
    context: str = "wallet-send lifecycle block production",
) -> None:
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "endpoint", "POST /api/v1/blocks/produce", context)
    require_equal(payload, "code", "block_production_accepted_local_only", context)
    require_equal(payload, "status", "confirmed", context)
    require_equal(payload, "mutation", "chain_and_pending_state_local_only", context)
    require_equal(payload, "warning", "local-private-devnet-only", context)

    block = payload.get("block")
    if not isinstance(block, dict):
        raise SmokeError(f"{context}: expected block object")
    require_equal(block, "height", 2, f"{context} block")
    require_hash(block.get("block_hash"), f"{context} block hash")
    require_equal(block, "transaction_count", 1, f"{context} block")
    require_equal(block, "timestamp_utc", "1970-01-01T00:00:02Z", f"{context} block")

    confirmed_transactions = require_list(
        payload.get("confirmed_transactions"),
        f"{context} confirmed transactions",
    )
    if len(confirmed_transactions) != 1 or not isinstance(confirmed_transactions[0], dict):
        raise SmokeError(f"{context}: expected exactly one confirmed transaction")
    confirmed = confirmed_transactions[0]
    require_equal(confirmed, "tx_hash", tx_hash, f"{context} tx")
    require_equal(confirmed, "status", "confirmed", f"{context} tx")
    require_equal(confirmed, "block_height", 2, f"{context} tx")
    require_equal(confirmed, "transaction_index", 0, f"{context} tx")
    require_hash(confirmed.get("block_hash"), f"{context} tx block hash")

    pending_state = payload.get("pending_state")
    if not isinstance(pending_state, dict):
        raise SmokeError(f"{context}: expected pending_state object")
    require_equal(pending_state, "before_count", 1, f"{context} pending")
    require_equal(pending_state, "after_count", 0, f"{context} pending")
    if pending_state.get("removed_tx_hashes") != [tx_hash]:
        raise SmokeError(
            f"{context}: expected removed_tx_hashes={[tx_hash]!r}, "
            f"got {pending_state.get('removed_tx_hashes')!r}"
        )
    require_equal(pending_state, "pending_file", str(pending_file), f"{context} pending")

    chain_state = payload.get("chain_state")
    if not isinstance(chain_state, dict):
        raise SmokeError(f"{context}: expected chain_state object")
    require_equal(chain_state, "previous_height", 1, f"{context} chain")
    require_equal(chain_state, "current_height", 2, f"{context} chain")
    require_equal(chain_state, "chain_file", str(chain_file), f"{context} chain")

    require_equal(payload, "audit_scope", "api-local-accepted", context)
    require_equal(payload, "audit_event_recorded", True, context)
    audit_event = payload.get("audit_event")
    if not isinstance(audit_event, dict):
        raise SmokeError(f"{context}: expected audit_event object")
    require_equal(
        audit_event,
        "event_id",
        f"block-production:{expected_local_request_id}",
        f"{context} audit",
    )
    require_equal(audit_event, "actor", "local-private-devnet-operator", f"{context} audit")
    require_equal(audit_event, "action", "block_production_attempt", f"{context} audit")
    require_equal(audit_event, "resource_type", "block_production", f"{context} audit")
    require_equal(
        audit_event,
        "resource_id",
        expected_local_request_id,
        f"{context} audit",
    )
    metadata = audit_event.get("metadata")
    if not isinstance(metadata, dict):
        raise SmokeError(f"{context}: expected audit metadata object")
    require_equal(metadata, "outcome", "accepted", f"{context} metadata")
    require_equal(metadata, "status", "confirmed", f"{context} metadata")
    require_equal(
        metadata,
        "explicit_flag",
        "--enable-local-block-production",
        f"{context} metadata",
    )
    require_equal(metadata, "local_request_id", expected_local_request_id, context)
    require_equal(metadata, "producer", "xriqdev1author00000000000", f"{context} metadata")
    require_equal(metadata, "confirmed_transaction_count", 1, f"{context} metadata")


def validate_wallet_confirmed_status(
    payload: dict[str, Any],
    *,
    tx_hash: str,
    context: str = "wallet-send lifecycle confirmed status",
) -> None:
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    warning = payload.get("warning")
    if not isinstance(warning, str) or "no-signing-no-submit" not in warning:
        raise SmokeError(f"{context}: expected preview-only wallet warning")
    require_equal(payload, "tx_hash", tx_hash, context)
    require_equal(payload, "status", "confirmed", context)
    require_equal(payload, "block_height", 2, context)
    require_hash(payload.get("block_hash"), f"{context} block hash")
    require_equal(payload, "transaction_index", 0, context)


def validate_mempool_empty(
    payload: dict[str, Any],
    *,
    context: str = "wallet-send lifecycle mempool",
) -> None:
    require_equal(payload, "pending_count", 0, context)
    entries = require_list(payload.get("entries"), f"{context} entries")
    if entries:
        raise SmokeError(f"{context}: expected no pending entries after block production")


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=False)
    api_artifact_dir = artifact_dir / "api"

    completed: list[str] = []
    if not args.skip_build:
        run_command(
            "build XRIQ lifecycle smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )
        completed.append("build xriq lifecycle smoke binaries")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "wallet-send-lifecycle-chain.bin"
    pending_file = artifact_dir / "wallet-send-lifecycle-pending.tsv"
    preflight_pending_file = artifact_dir / "wallet-send-lifecycle-preflight-pending.tsv"

    preflight = run_json(
        "create lifecycle base chain",
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
    base_tx_hash = require_hash(
        preflight.get("transaction_hash") or preflight.get("tx_hash"),
        "lifecycle base confirmed tx hash",
    )
    require_equal(preflight, "confirmed_block_height", 1, "lifecycle base transfer")
    require_equal(preflight, "final_balance_base_units", "73", "lifecycle base transfer")
    write_json(artifact_dir / "base-confirmed-transfer.json", preflight)
    completed.append("base confirmed transfer")

    pending_file.write_text("", encoding="utf-8")
    send_target = (
        f"/api/v1/wallet/transfers/send?local_request_id=local-wallet-send-lifecycle-1"
        f"&from_address={ALICE}&to_address={CAROL}"
        "&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100"
    )
    wallet_send_response = assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        send_target,
        201,
        api_artifact_dir / "wallet-send-accepted-local.json",
        lambda payload: validate_wallet_send_accepted(
            payload,
            chain_file=chain_file,
            pending_file=pending_file,
        ),
        extra_args=["--enable-local-wallet-send", "true"],
    )
    tx_hash = require_hash(
        wallet_send_response.get("transaction", {}).get("tx_hash"),
        "lifecycle wallet-send tx hash",
    )
    if tx_hash not in pending_file.read_text(encoding="utf-8"):
        raise SmokeError("wallet-send lifecycle: pending file did not include accepted tx")
    completed.append("wallet-send accepted")

    block_target = (
        "/api/v1/blocks/produce?local_request_id=local-wallet-send-lifecycle-2"
        "&producer=xriqdev1author00000000000&max_transactions=4&timestamp_ms=2000"
    )
    assert_api_method_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "POST",
        block_target,
        201,
        api_artifact_dir / "wallet-send-produced-block-local.json",
        lambda payload: validate_block_production_accepted(
            payload,
            tx_hash=tx_hash,
            chain_file=chain_file,
            pending_file=pending_file,
        ),
        extra_args=["--enable-local-block-production", "true"],
    )
    if pending_file.read_text(encoding="utf-8") != "":
        raise SmokeError("wallet-send lifecycle: pending file was not cleared")
    completed.append("wallet-send produced into local block")

    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        f"/api/v1/wallet/transactions/{tx_hash}/status",
        200,
        api_artifact_dir / "wallet-send-confirmed-status-local.json",
        lambda payload: validate_wallet_confirmed_status(payload, tx_hash=tx_hash),
    )
    completed.append("wallet-send confirmed wallet status")

    assert_api_status(
        api_binary,
        xriq_dir,
        chain_file,
        pending_file,
        "/api/v1/mempool?limit=5",
        200,
        api_artifact_dir / "wallet-send-lifecycle-mempool-empty.json",
        lambda payload: validate_mempool_empty(payload),
    )
    completed.append("wallet-send lifecycle mempool empty")

    server_chain_file = artifact_dir / "wallet-send-lifecycle-server-chain.bin"
    server_pending_file = artifact_dir / "wallet-send-lifecycle-server-pending.tsv"
    server_preflight_pending_file = (
        artifact_dir / "wallet-send-lifecycle-server-preflight-pending.tsv"
    )
    server_preflight = run_json(
        "create serve-readonly lifecycle base chain",
        [
            str(node_binary),
            "preflight-transfer",
            "--chain-file",
            str(server_chain_file),
            "--pending-file",
            str(server_preflight_pending_file),
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
    server_base_tx_hash = require_hash(
        server_preflight.get("transaction_hash") or server_preflight.get("tx_hash"),
        "serve-readonly lifecycle base confirmed tx hash",
    )
    require_equal(server_preflight, "confirmed_block_height", 1, "server base transfer")
    require_equal(server_preflight, "final_balance_base_units", "73", "server base transfer")
    write_json(artifact_dir / "server-base-confirmed-transfer.json", server_preflight)
    server_pending_file.write_text("", encoding="utf-8")

    server_port = free_local_port()
    server_bind = f"127.0.0.1:{server_port}"
    server_base_url = f"http://{server_bind}"
    server_process = None
    server_tx_hash = ""
    try:
        server_process = start_api_readonly_server(
            api_binary,
            xriq_dir,
            artifact_dir,
            chain_file=server_chain_file,
            pending_file=server_pending_file,
            bind=server_bind,
            enable_local_wallet_send=True,
            enable_local_block_production=True,
            stderr_log_name="api-wallet-send-lifecycle-server.stderr.log",
        )
        wait_for_api_readonly_server(server_base_url, server_process)

        server_send_target = (
            "/api/v1/wallet/transfers/send"
            "?local_request_id=local-wallet-send-lifecycle-server-1"
            f"&from_address={ALICE}&to_address={CAROL}"
            "&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100"
        )
        server_wallet_send = http_json(
            server_base_url,
            server_send_target,
            expected_status=201,
            method="POST",
        )
        server_tx_hash = validate_wallet_send_accepted(
            server_wallet_send,
            chain_file=server_chain_file,
            pending_file=server_pending_file,
            expected_local_request_id="local-wallet-send-lifecycle-server-1",
            context="serve-readonly wallet-send lifecycle accepted",
        )
        write_json(
            api_artifact_dir / "wallet-send-accepted-local-server.json",
            server_wallet_send,
        )
        if server_tx_hash not in server_pending_file.read_text(encoding="utf-8"):
            raise SmokeError(
                "serve-readonly wallet-send lifecycle: pending file did not include accepted tx"
            )
        completed.append("serve-readonly wallet-send accepted")

        server_block_target = (
            "/api/v1/blocks/produce?local_request_id=local-wallet-send-lifecycle-server-2"
            "&producer=xriqdev1author00000000000&max_transactions=4&timestamp_ms=2000"
        )
        server_block = http_json(
            server_base_url,
            server_block_target,
            expected_status=201,
            method="POST",
        )
        validate_block_production_accepted(
            server_block,
            tx_hash=server_tx_hash,
            chain_file=server_chain_file,
            pending_file=server_pending_file,
            expected_local_request_id="local-wallet-send-lifecycle-server-2",
            context="serve-readonly wallet-send lifecycle block production",
        )
        write_json(
            api_artifact_dir / "wallet-send-produced-block-local-server.json",
            server_block,
        )
        completed.append("serve-readonly wallet-send produced into local block")

        server_confirmed_status = http_json(
            server_base_url,
            f"/api/v1/wallet/transactions/{server_tx_hash}/status",
        )
        validate_wallet_confirmed_status(
            server_confirmed_status,
            tx_hash=server_tx_hash,
            context="serve-readonly wallet-send lifecycle confirmed status",
        )
        write_json(
            api_artifact_dir / "wallet-send-confirmed-status-local-server.json",
            server_confirmed_status,
        )
        completed.append("serve-readonly wallet-send confirmed wallet status")

        server_mempool = http_json(server_base_url, "/api/v1/mempool?limit=5")
        validate_mempool_empty(
            server_mempool,
            context="serve-readonly wallet-send lifecycle mempool",
        )
        write_json(
            api_artifact_dir / "wallet-send-lifecycle-mempool-empty-server.json",
            server_mempool,
        )
        completed.append("serve-readonly wallet-send lifecycle mempool empty")

        server_network = http_json(server_base_url, "/api/v1/network")
        require_equal(server_network, "current_height", 2, "serve-readonly lifecycle network")
        write_json(api_artifact_dir / "wallet-send-lifecycle-network-server.json", server_network)
        completed.append("serve-readonly wallet-send lifecycle network height")
    finally:
        stop_process(server_process)

    if server_pending_file.read_text(encoding="utf-8") != "":
        raise SmokeError("serve-readonly wallet-send lifecycle: pending file was not cleared")

    summary = {
        "ok": "xriq-phase1-2-wallet-send-lifecycle-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "serve_readonly_chain_file": str(server_chain_file),
        "serve_readonly_pending_file": str(server_pending_file),
        "base_confirmed_tx_hash": base_tx_hash,
        "serve_readonly_base_confirmed_tx_hash": server_base_tx_hash,
        "wallet_send_tx_hash": tx_hash,
        "serve_readonly_wallet_send_tx_hash": server_tx_hash,
        "artifacts": {
            "base_confirmed_transfer": str(artifact_dir / "base-confirmed-transfer.json"),
            "wallet_send_accepted": str(api_artifact_dir / "wallet-send-accepted-local.json"),
            "wallet_send_produced_block": str(
                api_artifact_dir / "wallet-send-produced-block-local.json"
            ),
            "wallet_send_confirmed_status": str(
                api_artifact_dir / "wallet-send-confirmed-status-local.json"
            ),
            "mempool_empty": str(api_artifact_dir / "wallet-send-lifecycle-mempool-empty.json"),
            "serve_readonly_base_confirmed_transfer": str(
                artifact_dir / "server-base-confirmed-transfer.json"
            ),
            "serve_readonly_wallet_send_accepted": str(
                api_artifact_dir / "wallet-send-accepted-local-server.json"
            ),
            "serve_readonly_wallet_send_produced_block": str(
                api_artifact_dir / "wallet-send-produced-block-local-server.json"
            ),
            "serve_readonly_wallet_send_confirmed_status": str(
                api_artifact_dir / "wallet-send-confirmed-status-local-server.json"
            ),
            "serve_readonly_mempool_empty": str(
                api_artifact_dir / "wallet-send-lifecycle-mempool-empty-server.json"
            ),
            "serve_readonly_network": str(
                api_artifact_dir / "wallet-send-lifecycle-network-server.json"
            ),
        },
        "guards": [
            "wallet send requires --enable-local-wallet-send",
            "block production requires --enable-local-block-production",
            "serve-readonly uses explicit local wallet-send and block-production flags",
            "pending state is copied local/private-devnet state",
            "wallet send appends exactly one pending transaction",
            "block production confirms the same wallet-send transaction",
            "pending file is empty after confirmation",
            "no UI mutation control is enabled",
            "no signing material or custody material is accepted",
        ],
        "completed": completed,
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
