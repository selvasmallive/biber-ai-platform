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
    return root / "xriq" / "target" / f"xriq-phase1-2-block-production-admin-refresh-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.2 Admin read-only refresh smoke after one "
            "feature-switched local block-production request."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for Admin refresh artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node and xriq-api debug binaries.",
    )
    return parser.parse_args(argv)


def run_npm_admin_refresh_check(
    *,
    ui_dir: Path,
    base_url: str,
    artifact_dir: Path,
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
            "block-production Admin refresh live check",
            [
                npm_command(),
                "run",
                "check:block-production-admin-refresh-live",
                "--",
                "--base-url",
                base_url,
                "--artifact-dir",
                str(artifact_dir),
                "--wallet-local-request-id",
                wallet_local_request_id,
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
        raise SmokeError(f"block-production Admin refresh summary missing: {summary_path}") from error
    except json.JSONDecodeError as error:
        raise SmokeError(
            f"block-production Admin refresh summary is invalid JSON: {error}"
        ) from error
    if not isinstance(payload, dict):
        raise SmokeError("block-production Admin refresh summary must be a JSON object")
    return payload


def validate_admin_refresh_summary(payload: dict[str, Any]) -> tuple[str, str]:
    require_equal(
        payload,
        "ok",
        "xriq-block-production-admin-refresh-live",
        "Admin refresh",
    )
    require_equal(
        payload,
        "feature_switch",
        "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        "Admin refresh",
    )
    before = payload.get("admin_rows_before")
    after = payload.get("admin_rows_after")
    status = payload.get("confirmed_status")
    if not isinstance(before, dict) or not isinstance(after, dict) or not isinstance(status, dict):
        raise SmokeError("Admin refresh: expected before/after/status objects")
    require_equal(before, "network_height", 1, "Admin refresh before")
    require_equal(before, "node_pending", 1, "Admin refresh before")
    require_equal(before, "wallet_pending", 1, "Admin refresh before")
    require_equal(before, "mempool_pending", 1, "Admin refresh before")
    require_equal(before, "wallet_tx_status", "pending", "Admin refresh before")
    require_equal(after, "network_height", 2, "Admin refresh after")
    require_equal(after, "node_pending", 0, "Admin refresh after")
    require_equal(after, "wallet_pending", 0, "Admin refresh after")
    require_equal(after, "mempool_pending", 0, "Admin refresh after")
    require_equal(after, "first_pending", "-", "Admin refresh after")
    require_equal(after, "wallet_tx_status", "-", "Admin refresh after")
    require_equal(status, "status", "confirmed", "Admin refresh status")
    require_equal(status, "block_height", 2, "Admin refresh status")
    require_equal(status, "transaction_index", 0, "Admin refresh status")
    tx_hash = require_hash(payload.get("wallet_send_tx_hash"), "Admin refresh tx hash")
    block_hash = require_hash(payload.get("produced_block_hash"), "Admin refresh block hash")
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
            "build XRIQ block-production Admin refresh smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )
        completed.append("build xriq block-production Admin refresh smoke binaries")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "block-production-admin-refresh-chain.bin"
    pending_file = artifact_dir / "block-production-admin-refresh-pending.tsv"
    preflight_pending_file = artifact_dir / "block-production-admin-refresh-preflight-pending.tsv"
    wallet_local_request_id = "block-production-admin-refresh-wallet-1"
    block_local_request_id = "block-production-admin-refresh-block-1"

    preflight = run_json(
        "create block-production Admin refresh base chain",
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
        "block-production Admin refresh base confirmed tx hash",
    )
    require_equal(preflight, "confirmed_block_height", 1, "block-production Admin refresh base transfer")
    require_equal(preflight, "final_balance_base_units", "73", "block-production Admin refresh base transfer")
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
            stderr_log_name="api-block-production-admin-refresh-server.stderr.log",
        )
        wait_for_api_readonly_server(server_base_url, server_process)
        completed.append("serve-readonly wallet-send and block-production API started")

        ui_summary = run_npm_admin_refresh_check(
            ui_dir=ui_dir,
            base_url=server_base_url,
            artifact_dir=ui_artifact_dir,
            wallet_local_request_id=wallet_local_request_id,
            block_local_request_id=block_local_request_id,
        )
        tx_hash, block_hash = validate_admin_refresh_summary(ui_summary)
        completed.append("Admin rows refresh from pending to confirmed state")

        if pending_file.read_text(encoding="utf-8") != "":
            raise SmokeError("block-production Admin refresh: pending file was not cleared")
        completed.append("pending file cleared after Admin refresh block production")

        wallet_submit_refusal = http_json(
            server_base_url,
            (
                "/api/v1/wallet/transfers/submit"
                "?local_request_id=block-production-admin-refresh-submit-refusal"
                "&draft_id=block-production-admin-refresh-draft"
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
            context="block-production Admin refresh wallet-submit refusal",
        )
        write_json(
            api_artifact_dir / "block-production-admin-refresh-submit-refusal.json",
            wallet_submit_refusal,
        )
        completed.append("wallet submit remains refused")
    finally:
        stop_process(server_process)

    if not tx_hash:
        raise SmokeError("block-production Admin refresh: no transaction hash recorded")

    summary = {
        "ok": "xriq-phase1-2-block-production-admin-refresh-smoke",
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
            "ui_rows_before": str(ui_artifact_dir / "block-production-admin-rows-before.json"),
            "ui_rows_after": str(ui_artifact_dir / "block-production-admin-rows-after.json"),
            "ui_produced_block": str(ui_artifact_dir / "block-production-admin-produced-block.json"),
            "ui_confirmed_status": str(
                ui_artifact_dir / "block-production-admin-confirmed-status.json"
            ),
            "wallet_submit_refusal": str(
                api_artifact_dir / "block-production-admin-refresh-submit-refusal.json"
            ),
        },
        "guards": [
            "Admin refresh uses the same adminSnapshotRows helper as the UI",
            "block-production Admin refresh requires VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
            "block production requires --enable-local-block-production",
            "wallet send remains separate and explicit",
            "wallet submit remains disabled without --enable-local-wallet-submit",
            "Admin rows show pending before block production",
            "Admin rows show height 2 and zero pending after block production",
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
