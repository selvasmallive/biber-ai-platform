#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from xriq_phase1_1_local_e2e_smoke import (
    ALICE,
    BOB,
    SmokeError,
    executable_path,
    free_local_port,
    http_json,
    npm_command,
    repo_root,
    require_equal,
    require_hash,
    run_command,
    run_json,
    start_api_readonly_server,
    stop_process,
    wait_for_api_readonly_server,
    write_json,
)


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-2-block-production-no-pending-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.2 block-production no-pending negative smoke "
            "against a temporary local/private serve-readonly API."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for no-pending smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node and xriq-api debug binaries.",
    )
    return parser.parse_args(argv)


def run_npm_no_pending_check(
    *,
    ui_dir: Path,
    base_url: str,
    artifact_dir: Path,
    block_local_request_id: str,
) -> dict[str, Any]:
    previous_env = {
        "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI": os.environ.get(
            "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI"
        ),
        "VITE_XRIQ_API_BASE_URL": os.environ.get("VITE_XRIQ_API_BASE_URL"),
    }
    os.environ["VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI"] = "true"
    os.environ["VITE_XRIQ_API_BASE_URL"] = base_url
    try:
        run_command(
            "block-production no-pending live check",
            [
                npm_command(),
                "run",
                "check:block-production-no-pending-live",
                "--",
                "--base-url",
                base_url,
                "--artifact-dir",
                str(artifact_dir),
                "--block-local-request-id",
                block_local_request_id,
            ],
            cwd=ui_dir,
        )
    finally:
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    summary_path = artifact_dir / "summary.json"
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SmokeError(f"block-production no-pending summary missing: {summary_path}") from error
    except json.JSONDecodeError as error:
        raise SmokeError(
            f"block-production no-pending summary is invalid JSON: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise SmokeError("block-production no-pending summary must be a JSON object")
    return payload


def validate_no_pending_error(payload: dict[str, Any], context: str) -> None:
    error = payload.get("error")
    if not isinstance(error, dict):
        raise SmokeError(f"{context}: expected error object")
    require_equal(error, "code", "no_pending_transactions", context)
    message = error.get("message")
    if not isinstance(message, str) or "at least one pending transaction" not in message:
        raise SmokeError(f"{context}: expected no-pending explanation")


def validate_no_pending_summary(payload: dict[str, Any]) -> None:
    require_equal(
        payload,
        "ok",
        "xriq-block-production-no-pending-live",
        "block-production no-pending",
    )
    require_equal(
        payload,
        "feature_switch",
        "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "block-production no-pending",
    )

    refusal = payload.get("no_pending_refusal")
    before = payload.get("admin_rows_before")
    after = payload.get("admin_rows_after")
    state = payload.get("state_unchanged")
    if not all(isinstance(value, dict) for value in [refusal, before, after, state]):
        raise SmokeError("block-production no-pending: expected summary objects")

    require_equal(refusal, "code", "no_pending_transactions", "block-production no-pending")
    require_equal(before, "network_height", 1, "block-production no-pending before")
    require_equal(before, "node_pending", 0, "block-production no-pending before")
    require_equal(before, "wallet_pending", 0, "block-production no-pending before")
    require_equal(before, "mempool_pending", 0, "block-production no-pending before")
    require_equal(before, "first_pending", "-", "block-production no-pending before")
    require_equal(before, "wallet_tx_status", "-", "block-production no-pending before")
    require_equal(after, "network_height", 1, "block-production no-pending after")
    require_equal(after, "node_pending", 0, "block-production no-pending after")
    require_equal(after, "wallet_pending", 0, "block-production no-pending after")
    require_equal(after, "mempool_pending", 0, "block-production no-pending after")
    require_equal(after, "first_pending", "-", "block-production no-pending after")
    require_equal(after, "wallet_tx_status", "-", "block-production no-pending after")
    require_equal(state, "height", 1, "block-production no-pending state")
    require_equal(state, "pending_count", 0, "block-production no-pending state")


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    ui_dir = xriq_dir / "apps" / "explorer-ui"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=False)
    ui_artifact_dir = artifact_dir / "ui"
    api_artifact_dir = artifact_dir / "api"

    completed: list[str] = []
    if not args.skip_build:
        run_command(
            "build XRIQ block-production no-pending smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )
        completed.append("build xriq block-production no-pending smoke binaries")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "block-production-no-pending-chain.bin"
    pending_file = artifact_dir / "block-production-no-pending-pending.tsv"
    preflight_pending_file = artifact_dir / "block-production-no-pending-preflight-pending.tsv"
    block_local_request_id = "block-production-no-pending-block-1"

    preflight = run_json(
        "create block-production no-pending base chain",
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
        "block-production no-pending base confirmed tx hash",
    )
    require_equal(preflight, "confirmed_block_height", 1, "block-production no-pending base transfer")
    require_equal(preflight, "final_balance_base_units", "73", "block-production no-pending base transfer")
    write_json(artifact_dir / "base-confirmed-transfer.json", preflight)
    pending_file.write_text("", encoding="utf-8")
    completed.append("base confirmed transfer with empty local pending file")

    server_port = free_local_port()
    server_bind = f"127.0.0.1:{server_port}"
    server_base_url = f"http://{server_bind}"
    server_process = None
    direct_refusal: dict[str, Any] | None = None
    try:
        server_process = start_api_readonly_server(
            api_binary,
            xriq_dir,
            artifact_dir,
            chain_file=chain_file,
            pending_file=pending_file,
            bind=server_bind,
            enable_local_block_production=True,
            stderr_log_name="api-block-production-no-pending-server.stderr.log",
        )
        wait_for_api_readonly_server(server_base_url, server_process)
        completed.append("serve-readonly block-production API started")

        ui_summary = run_npm_no_pending_check(
            ui_dir=ui_dir,
            base_url=server_base_url,
            artifact_dir=ui_artifact_dir,
            block_local_request_id=block_local_request_id,
        )
        validate_no_pending_summary(ui_summary)
        completed.append("Admin rows stayed unchanged after no-pending refusal")

        direct_refusal = http_json(
            server_base_url,
            (
                "/api/v1/blocks/produce"
                "?local_request_id=block-production-no-pending-direct"
                "&producer=xriqdev1author00000000000"
                "&max_transactions=4&timestamp_ms=2000"
            ),
            expected_status=400,
            method="POST",
        )
        validate_no_pending_error(direct_refusal, "direct block-production no-pending refusal")
        write_json(
            api_artifact_dir / "block-production-no-pending-direct-refusal.json",
            direct_refusal,
        )
        completed.append("direct API no-pending refusal remains stable")

        network = http_json(server_base_url, "/api/v1/network")
        require_equal(network, "current_height", 1, "block-production no-pending network")
        write_json(api_artifact_dir / "block-production-no-pending-network.json", network)
        completed.append("network height unchanged after no-pending refusal")

        mempool = http_json(server_base_url, "/api/v1/mempool?limit=5")
        require_equal(mempool, "pending_count", 0, "block-production no-pending mempool")
        write_json(api_artifact_dir / "block-production-no-pending-mempool-empty.json", mempool)
        completed.append("mempool remains empty after no-pending refusal")

        if pending_file.read_text(encoding="utf-8") != "":
            raise SmokeError("block-production no-pending: pending file was mutated")
        completed.append("pending file remains empty after no-pending refusal")
    finally:
        stop_process(server_process)

    if direct_refusal is None:
        raise SmokeError("block-production no-pending: no direct refusal recorded")

    summary = {
        "ok": "xriq-phase1-2-block-production-no-pending-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "base_confirmed_tx_hash": base_tx_hash,
        "feature_switch": "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "serve_readonly_flags": {
            "enable_local_wallet_send": False,
            "enable_local_wallet_submit": False,
            "enable_local_block_production": True,
        },
        "no_pending_refusal_code": direct_refusal["error"]["code"],
        "artifacts": {
            "base_confirmed_transfer": str(artifact_dir / "base-confirmed-transfer.json"),
            "ui_summary": str(ui_artifact_dir / "summary.json"),
            "ui_rows_before": str(ui_artifact_dir / "block-production-no-pending-rows-before.json"),
            "ui_refusal": str(ui_artifact_dir / "block-production-no-pending-refusal.json"),
            "ui_rows_after": str(ui_artifact_dir / "block-production-no-pending-rows-after.json"),
            "api_no_pending_refusal": str(
                api_artifact_dir / "block-production-no-pending-direct-refusal.json"
            ),
            "network": str(api_artifact_dir / "block-production-no-pending-network.json"),
            "mempool_empty": str(api_artifact_dir / "block-production-no-pending-mempool-empty.json"),
        },
        "guards": [
            "no-pending block production returns no_pending_transactions",
            "no-pending block production does not mutate chain state",
            "no-pending block production does not mutate pending state",
            "Admin rows stay at height 1 with zero pending transactions",
            "block production requires --enable-local-block-production",
            "feature-switched UI still disables Produce Local when pending_count is zero",
            "wallet send remains separate and disabled in this smoke",
            "wallet submit remains deferred",
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
