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
    CAROL,
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
from xriq_phase1_2_wallet_send_ui_live_smoke import validate_disabled_response


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-2-block-production-ui-live-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.2 feature-switched block-production UI live "
            "smoke against a temporary local/private serve-readonly API."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for live UI smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node and xriq-api debug binaries.",
    )
    return parser.parse_args(argv)


def run_npm_block_production_live_check(
    *,
    ui_dir: Path,
    base_url: str,
    artifact_dir: Path,
    chain_file: Path,
    pending_file: Path,
    wallet_local_request_id: str,
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
            "block-production UI live check",
            [
                npm_command(),
                "run",
                "check:block-production-ui-live",
                "--",
                "--base-url",
                base_url,
                "--artifact-dir",
                str(artifact_dir),
                "--wallet-local-request-id",
                wallet_local_request_id,
                "--block-local-request-id",
                block_local_request_id,
                "--expected-chain-file",
                str(chain_file),
                "--expected-pending-file",
                str(pending_file),
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
        raise SmokeError(f"block-production UI live summary missing: {summary_path}") from error
    except json.JSONDecodeError as error:
        raise SmokeError(f"block-production UI live summary is invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise SmokeError("block-production UI live summary must be a JSON object")
    return payload


def validate_block_summary(payload: dict[str, Any]) -> tuple[str, str]:
    require_equal(payload, "ok", "xriq-block-production-ui-live", "block-production UI live")
    require_equal(
        payload,
        "feature_switch",
        "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "block-production UI live",
    )
    require_equal(payload, "wallet_submit_deferred", True, "block-production UI live")
    require_equal(payload, "wallet_send_separate", True, "block-production UI live")
    require_equal(payload, "block_production_explicit", True, "block-production UI live")
    produced = payload.get("produced")
    if not isinstance(produced, dict):
        raise SmokeError("block-production UI live: expected produced object")
    require_equal(produced, "code", "block_production_accepted_local_only", "produced")
    require_equal(produced, "status", "confirmed", "produced")
    require_equal(produced, "mutation", "chain_and_pending_state_local_only", "produced")
    require_equal(produced, "pending_before_count", 1, "produced")
    require_equal(produced, "pending_after_count", 0, "produced")
    require_equal(produced, "chain_previous_height", 1, "produced")
    require_equal(produced, "chain_current_height", 2, "produced")
    tx_hash = require_hash(produced.get("tx_hash"), "block-production UI live tx hash")
    block_hash = require_hash(produced.get("block_hash"), "block-production UI live block hash")
    refresh = payload.get("refresh_after_production")
    if not isinstance(refresh, dict):
        raise SmokeError("block-production UI live: expected refresh_after_production object")
    require_equal(refresh, "current_height", 2, "refresh")
    require_equal(refresh, "mempool_pending_count", 0, "refresh")
    require_equal(refresh, "wallet_status_pending_transactions", 0, "refresh")
    require_equal(refresh, "transaction_status", "confirmed", "refresh")
    require_equal(refresh, "transaction_block_height", 2, "refresh")
    require_equal(refresh, "transaction_index", 0, "refresh")
    return tx_hash, block_hash


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
            "build XRIQ block-production UI live smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )
        completed.append("build xriq block-production UI live smoke binaries")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "block-production-ui-live-chain.bin"
    pending_file = artifact_dir / "block-production-ui-live-pending.tsv"
    preflight_pending_file = artifact_dir / "block-production-ui-live-preflight-pending.tsv"
    wallet_local_request_id = "block-production-ui-wallet-1"
    block_local_request_id = "block-production-ui-block-1"

    preflight = run_json(
        "create block-production UI live base chain",
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
        "block-production UI live base confirmed tx hash",
    )
    require_equal(preflight, "confirmed_block_height", 1, "block-production UI live base transfer")
    require_equal(preflight, "final_balance_base_units", "73", "block-production UI live base transfer")
    write_json(artifact_dir / "base-confirmed-transfer.json", preflight)
    pending_file.write_text("", encoding="utf-8")
    completed.append("base confirmed transfer")

    server_port = free_local_port()
    server_bind = f"127.0.0.1:{server_port}"
    server_base_url = f"http://{server_bind}"
    server_process = None
    tx_hash = ""
    block_hash = ""
    try:
        server_process = start_api_readonly_server(
            api_binary,
            xriq_dir,
            artifact_dir,
            chain_file=chain_file,
            pending_file=pending_file,
            bind=server_bind,
            enable_local_wallet_send=True,
            enable_local_block_production=True,
            stderr_log_name="api-block-production-ui-live-server.stderr.log",
        )
        wait_for_api_readonly_server(server_base_url, server_process)
        completed.append("serve-readonly wallet-send and block-production API started")

        ui_summary = run_npm_block_production_live_check(
            ui_dir=ui_dir,
            base_url=server_base_url,
            artifact_dir=ui_artifact_dir,
            chain_file=chain_file,
            pending_file=pending_file,
            wallet_local_request_id=wallet_local_request_id,
            block_local_request_id=block_local_request_id,
        )
        tx_hash, block_hash = validate_block_summary(ui_summary)
        completed.append("block-production UI live produced one local block")

        if pending_file.read_text(encoding="utf-8") != "":
            raise SmokeError("block-production UI live: pending file was not cleared")
        completed.append("pending file cleared after confirmed block production")

        wallet_submit_refusal = http_json(
            server_base_url,
            (
                "/api/v1/wallet/transfers/submit"
                "?local_request_id=block-production-ui-submit-refusal"
                "&draft_id=block-production-ui-draft"
                f"&from_address={ALICE}&to_address={CAROL}"
                "&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100"
            ),
            expected_status=403,
            method="POST",
        )
        validate_disabled_response(
            wallet_submit_refusal,
            expected_code="wallet_submit_disabled",
            expected_flag="--enable-local-wallet-submit",
            context="block-production UI live wallet-submit refusal",
        )
        write_json(api_artifact_dir / "block-production-ui-submit-refusal.json", wallet_submit_refusal)
        completed.append("wallet submit remains refused")

        network = http_json(server_base_url, "/api/v1/network")
        require_equal(network, "current_height", 2, "block-production UI live network")
        write_json(api_artifact_dir / "block-production-ui-network.json", network)
        completed.append("network height advanced exactly one block")

        mempool = http_json(server_base_url, "/api/v1/mempool?limit=5")
        require_equal(mempool, "pending_count", 0, "block-production UI live mempool")
        write_json(api_artifact_dir / "block-production-ui-mempool-empty.json", mempool)
        completed.append("mempool empty after local block production")
    finally:
        stop_process(server_process)

    if not tx_hash:
        raise SmokeError("block-production UI live: no transaction hash recorded")

    summary = {
        "ok": "xriq-phase1-2-block-production-ui-live-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "base_confirmed_tx_hash": base_tx_hash,
        "wallet_send_tx_hash": tx_hash,
        "produced_block_hash": block_hash,
        "feature_switch": "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "serve_readonly_flags": {
            "enable_local_wallet_send": True,
            "enable_local_wallet_submit": False,
            "enable_local_block_production": True,
        },
        "artifacts": {
            "base_confirmed_transfer": str(artifact_dir / "base-confirmed-transfer.json"),
            "ui_summary": str(ui_artifact_dir / "summary.json"),
            "ui_wallet_send": str(ui_artifact_dir / "block-production-ui-wallet-send.json"),
            "ui_produced_block": str(ui_artifact_dir / "block-production-ui-produced-block.json"),
            "ui_confirmed_status": str(
                ui_artifact_dir / "block-production-ui-confirmed-status.json"
            ),
            "ui_snapshot_after": str(ui_artifact_dir / "block-production-ui-snapshot-after.json"),
            "wallet_submit_refusal": str(api_artifact_dir / "block-production-ui-submit-refusal.json"),
            "network": str(api_artifact_dir / "block-production-ui-network.json"),
            "mempool_empty": str(api_artifact_dir / "block-production-ui-mempool-empty.json"),
        },
        "guards": [
            "block-production UI requires VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
            "block-production UI uses the shared API client helper",
            "block production requires --enable-local-block-production",
            "wallet send remains separate and explicit",
            "wallet submit remains disabled without --enable-local-wallet-submit",
            "accepted block-production mutation is chain_and_pending_state_local_only",
            "pending file removes confirmed transaction hashes",
            "chain height advances exactly one block",
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
