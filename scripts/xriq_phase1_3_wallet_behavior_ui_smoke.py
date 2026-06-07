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
from xriq_phase1_3_behavior_contract_check import FIXTURE_PATH
from xriq_phase1_3_wallet_behavior_smoke import (
    fixture_step,
    load_fixture,
    validate_base_transfer,
)


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-3-wallet-behavior-ui-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.3 UI-backed local/private wallet behavior "
            "smoke against a temporary serve-readonly API."
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


def run_npm_phase1_3_ui_check(
    *,
    ui_dir: Path,
    base_url: str,
    artifact_dir: Path,
    chain_file: Path,
    pending_file: Path,
) -> dict[str, Any]:
    previous_env = {
        "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI": os.environ.get(
            "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI"
        ),
        "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI": os.environ.get(
            "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI"
        ),
        "VITE_XRIQ_API_BASE_URL": os.environ.get("VITE_XRIQ_API_BASE_URL"),
    }
    os.environ["VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI"] = "true"
    os.environ["VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI"] = "true"
    os.environ["VITE_XRIQ_API_BASE_URL"] = base_url
    try:
        run_command(
            "Phase 1.3 wallet behavior UI live check",
            [
                npm_command(),
                "run",
                "check:phase1-3-wallet-behavior-live",
                "--",
                "--base-url",
                base_url,
                "--artifact-dir",
                str(artifact_dir),
                "--expected-chain-file",
                str(chain_file),
                "--expected-pending-file",
                str(pending_file),
                "--fixture",
                str(FIXTURE_PATH),
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
        raise SmokeError(f"Phase 1.3 UI behavior summary missing: {summary_path}") from error
    except json.JSONDecodeError as error:
        raise SmokeError(f"Phase 1.3 UI behavior summary is invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise SmokeError("Phase 1.3 UI behavior summary must be a JSON object")
    return payload


def validate_ui_summary(payload: dict[str, Any], fixture: dict[str, Any]) -> tuple[str, str]:
    context = "Phase 1.3 UI behavior"
    require_equal(payload, "ok", "xriq-phase1-3-wallet-behavior-ui-live", context)
    require_equal(payload, "wallet_submit_deferred", True, context)
    require_equal(payload, "default_controls_disabled_by_source", True, context)
    require_equal(payload, "shared_client_flow", True, context)
    send_step = fixture_step(fixture, "wallet_send_to_pending")
    block_step = fixture_step(fixture, "produce_one_block")
    require_equal(payload, "wallet_local_request_id", send_step["local_request_id"], context)
    require_equal(payload, "block_local_request_id", block_step["local_request_id"], context)

    tx_hash = require_hash(payload.get("wallet_send_tx_hash"), f"{context} tx hash")
    block_hash = require_hash(payload.get("produced_block_hash"), f"{context} block hash")

    before = payload.get("refresh_before_block")
    if not isinstance(before, dict):
        raise SmokeError(f"{context}: expected refresh_before_block object")
    require_equal(before, "current_height", 1, context)
    require_equal(before, "mempool_pending_count", 1, context)
    require_equal(before, "wallet_pending_transactions", 1, context)
    require_equal(before, "transaction_status", "pending", context)

    after = payload.get("refresh_after_block")
    if not isinstance(after, dict):
        raise SmokeError(f"{context}: expected refresh_after_block object")
    expected_explorer = fixture["post_block_expectations"]["explorer"]
    require_equal(after, "current_height", expected_explorer["current_height"], context)
    require_equal(after, "stored_blocks", expected_explorer["stored_blocks"], context)
    require_equal(after, "confirmed_transactions", expected_explorer["confirmed_transactions"], context)
    require_equal(after, "mempool_pending_count", expected_explorer["pending_transactions"], context)
    require_equal(after, "wallet_pending_transactions", 0, context)
    require_equal(after, "transaction_status", "confirmed", context)
    require_equal(after, "transaction_block_height", expected_explorer["current_height"], context)
    require_equal(after, "transaction_index", 0, context)

    refusal = payload.get("no_pending_refusal")
    if not isinstance(refusal, dict):
        raise SmokeError(f"{context}: expected no_pending_refusal object")
    require_equal(refusal, "code", "no_pending_transactions", context)
    require_equal(refusal, "state_unchanged", True, context)

    balances = payload.get("balances")
    if not isinstance(balances, dict):
        raise SmokeError(f"{context}: expected balances object")
    for account in fixture["post_block_expectations"]["accounts"]:
        balance = balances.get(account["address"])
        if not isinstance(balance, dict):
            raise SmokeError(f"{context}: missing balance for {account['address']}")
        require_equal(balance, "balance_base_units", account["balance_base_units"], context)
        require_equal(balance, "nonce", account["nonce"], context)

    return tx_hash, block_hash


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    fixture = load_fixture()
    root = repo_root()
    xriq_dir = root / "xriq"
    ui_dir = xriq_dir / "apps" / "explorer-ui"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    ui_artifact_dir = artifact_dir / "ui"
    api_artifact_dir = artifact_dir / "api"
    artifact_dir.mkdir(parents=True, exist_ok=False)
    write_json(artifact_dir / "contract-fixture.json", fixture)

    completed: list[str] = ["validated Phase 1.3 behavior fixture"]
    if not args.skip_build:
        run_command(
            "build XRIQ Phase 1.3 UI behavior smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )
        completed.append("build xriq-node and xriq-api")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "phase1-3-wallet-behavior-ui-chain.bin"
    pending_file = artifact_dir / "phase1-3-wallet-behavior-ui-pending.tsv"
    preflight_pending_file = artifact_dir / "phase1-3-wallet-behavior-ui-preflight-pending.tsv"

    base = fixture["base_chain_setup"]
    base_transfer = base["transfer"]
    base_response = run_json(
        "create Phase 1.3 UI behavior base chain",
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
            stderr_log_name="api-phase1-3-wallet-behavior-ui-server.stderr.log",
        )
        wait_for_api_readonly_server(server_base_url, server_process)
        completed.append("serve-readonly wallet-send and block-production API started")

        ui_summary = run_npm_phase1_3_ui_check(
            ui_dir=ui_dir,
            base_url=server_base_url,
            artifact_dir=ui_artifact_dir,
            chain_file=chain_file,
            pending_file=pending_file,
        )
        tx_hash, block_hash = validate_ui_summary(ui_summary, fixture)
        completed.append("UI shared-client behavior smoke passed")

        if pending_file.read_text(encoding="utf-8") != "":
            raise SmokeError("Phase 1.3 UI behavior smoke did not clear pending file")
        completed.append("pending file cleared after produced block")

        network = http_json(server_base_url, "/api/v1/network")
        require_equal(
            network,
            "current_height",
            fixture["post_block_expectations"]["explorer"]["current_height"],
            "Phase 1.3 UI behavior network",
        )
        write_json(api_artifact_dir / "network-after-ui-behavior.json", network)

        mempool = http_json(server_base_url, "/api/v1/mempool?limit=5")
        require_equal(mempool, "pending_count", 0, "Phase 1.3 UI behavior mempool")
        write_json(api_artifact_dir / "mempool-empty-after-ui-behavior.json", mempool)
        completed.append("API network and mempool remain consistent after UI smoke")
    finally:
        stop_process(server_process)

    if not tx_hash or not block_hash:
        raise SmokeError("Phase 1.3 UI behavior smoke did not record tx/block hashes")

    summary = {
        "ok": "xriq-phase1-3-wallet-behavior-ui-smoke",
        "artifact_dir": str(artifact_dir),
        "fixture": str(FIXTURE_PATH),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "base_confirmed_tx_hash": base_tx_hash,
        "wallet_send_tx_hash": tx_hash,
        "produced_block_hash": block_hash,
        "feature_switches": {
            "wallet_send_ui": "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
            "block_production_ui": "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        },
        "serve_readonly_flags": {
            "enable_local_wallet_send": True,
            "enable_local_wallet_submit": False,
            "enable_local_block_production": True,
        },
        "artifacts": {
            "contract_fixture": str(artifact_dir / "contract-fixture.json"),
            "base_confirmed_transfer": str(artifact_dir / "base-confirmed-transfer.json"),
            "ui_summary": str(ui_artifact_dir / "summary.json"),
            "ui_wallet_send": str(ui_artifact_dir / "phase1-3-wallet-send.json"),
            "ui_produced_block": str(ui_artifact_dir / "phase1-3-produced-block.json"),
            "ui_confirmed_status": str(ui_artifact_dir / "phase1-3-confirmed-status.json"),
            "ui_balances": str(ui_artifact_dir / "phase1-3-balances.json"),
            "ui_histories": str(ui_artifact_dir / "phase1-3-histories.json"),
            "ui_no_pending_refusal": str(
                ui_artifact_dir / "phase1-3-no-pending-refusal.json"
            ),
            "network_after_ui_behavior": str(api_artifact_dir / "network-after-ui-behavior.json"),
            "mempool_empty_after_ui_behavior": str(
                api_artifact_dir / "mempool-empty-after-ui-behavior.json"
            ),
        },
        "guards": [
            "UI behavior smoke requires both Phase 1.3 Vite feature switches",
            "temporary API enables only local wallet-send and block-production flags",
            "wallet submit remains disabled and deferred",
            "UI source uses shared TypeScript API client helpers",
            "wallet and Admin UI source have no direct mutation fetch calls",
            "wallet rows show pending before the block and confirmed after the block",
            "Admin rows show pending count moving from one to zero",
            "no-pending block-production refusal leaves state unchanged",
            "no signing material or custody material is accepted",
            "no Docker, browser, GCP, Vast, public, DEX, or custody scope",
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
