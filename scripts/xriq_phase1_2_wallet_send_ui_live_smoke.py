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
    return root / "xriq" / "target" / f"xriq-phase1-2-wallet-send-ui-live-smoke-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the XRIQ Phase 1.2 feature-switched wallet-send UI live smoke "
            "against a temporary local/private serve-readonly API."
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


def run_npm_ui_live_check(
    *,
    ui_dir: Path,
    base_url: str,
    artifact_dir: Path,
    chain_file: Path,
    pending_file: Path,
    local_request_id: str,
) -> dict[str, Any]:
    previous_env = {
        "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI": os.environ.get(
            "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI"
        ),
        "VITE_XRIQ_API_BASE_URL": os.environ.get("VITE_XRIQ_API_BASE_URL"),
    }
    os.environ["VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI"] = "true"
    os.environ["VITE_XRIQ_API_BASE_URL"] = base_url
    try:
        run_command(
            "wallet-send UI live check",
            [
                npm_command(),
                "run",
                "check:wallet-send-ui-live",
                "--",
                "--base-url",
                base_url,
                "--artifact-dir",
                str(artifact_dir),
                "--local-request-id",
                local_request_id,
                "--expected-chain-file",
                str(chain_file),
                "--expected-pending-file",
                str(pending_file),
                "--expected-current-height",
                "1",
                "--expected-before-count",
                "0",
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
        raise SmokeError(f"wallet-send UI live summary missing: {summary_path}") from error
    except json.JSONDecodeError as error:
        raise SmokeError(f"wallet-send UI live summary is invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise SmokeError("wallet-send UI live summary must be a JSON object")
    return payload


def validate_mempool(payload: dict[str, Any], *, tx_hash: str, context: str) -> None:
    require_equal(payload, "pending_count", 1, context)
    entries = require_list(payload.get("entries"), f"{context} entries")
    if len(entries) != 1 or not isinstance(entries[0], dict):
        raise SmokeError(f"{context}: expected exactly one pending transaction")
    entry = entries[0]
    require_equal(entry, "tx_hash", tx_hash, context)
    require_equal(entry, "from_address", ALICE, context)
    require_equal(entry, "to_address", CAROL, context)
    require_equal(entry, "amount_base_units", "5", context)
    require_equal(entry, "fee_base_units", "2", context)
    require_equal(entry, "nonce", 1, context)
    require_equal(entry, "status", "pending", context)


def validate_disabled_response(
    payload: dict[str, Any],
    *,
    expected_code: str,
    expected_flag: str,
    context: str,
) -> None:
    require_equal(payload, "environment", "private-devnet", context)
    require_equal(payload, "network", "xriq-devnet", context)
    require_equal(payload, "enabled", False, context)
    require_equal(payload, "mutation", "none", context)
    require_equal(payload, "status", "disabled", context)
    require_equal(payload, "code", expected_code, context)
    required_enablement = payload.get("required_enablement")
    if not isinstance(required_enablement, dict):
        raise SmokeError(f"{context}: expected required_enablement object")
    require_equal(required_enablement, "mode", "local-private-devnet", context)
    require_equal(required_enablement, "explicit_flag", expected_flag, context)
    require_equal(required_enablement, "audit_event_required", True, context)
    require_equal(required_enablement, "test_identity_only", True, context)


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
            "build XRIQ wallet-send UI live smoke binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )
        completed.append("build xriq wallet-send UI live smoke binaries")

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    chain_file = artifact_dir / "wallet-send-ui-live-chain.bin"
    pending_file = artifact_dir / "wallet-send-ui-live-pending.tsv"
    preflight_pending_file = artifact_dir / "wallet-send-ui-live-preflight-pending.tsv"
    local_request_id = "wallet-send-ui-live-1"

    preflight = run_json(
        "create wallet-send UI live base chain",
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
        "wallet-send UI live base confirmed tx hash",
    )
    require_equal(preflight, "confirmed_block_height", 1, "wallet-send UI live base transfer")
    require_equal(preflight, "final_balance_base_units", "73", "wallet-send UI live base transfer")
    write_json(artifact_dir / "base-confirmed-transfer.json", preflight)
    pending_file.write_text("", encoding="utf-8")
    completed.append("base confirmed transfer")

    server_port = free_local_port()
    server_bind = f"127.0.0.1:{server_port}"
    server_base_url = f"http://{server_bind}"
    server_process = None
    tx_hash = ""
    try:
        server_process = start_api_readonly_server(
            api_binary,
            xriq_dir,
            artifact_dir,
            chain_file=chain_file,
            pending_file=pending_file,
            bind=server_bind,
            enable_local_wallet_send=True,
            stderr_log_name="api-wallet-send-ui-live-server.stderr.log",
        )
        wait_for_api_readonly_server(server_base_url, server_process)
        completed.append("serve-readonly wallet-send-only API started")

        ui_summary = run_npm_ui_live_check(
            ui_dir=ui_dir,
            base_url=server_base_url,
            artifact_dir=ui_artifact_dir,
            chain_file=chain_file,
            pending_file=pending_file,
            local_request_id=local_request_id,
        )
        accepted = ui_summary.get("accepted")
        if not isinstance(accepted, dict):
            raise SmokeError("wallet-send UI live summary missing accepted object")
        tx_hash = require_hash(accepted.get("tx_hash"), "wallet-send UI live tx hash")
        completed.append("wallet-send UI live accepted via shared client")

        if tx_hash not in pending_file.read_text(encoding="utf-8"):
            raise SmokeError("wallet-send UI live: pending file did not include accepted tx")

        mempool = http_json(server_base_url, "/api/v1/mempool?limit=5")
        validate_mempool(mempool, tx_hash=tx_hash, context="wallet-send UI live mempool")
        write_json(api_artifact_dir / "wallet-send-ui-live-mempool.json", mempool)
        completed.append("wallet-send UI live mempool has one pending tx")

        network = http_json(server_base_url, "/api/v1/network")
        require_equal(network, "current_height", 1, "wallet-send UI live network")
        write_json(api_artifact_dir / "wallet-send-ui-live-network.json", network)
        completed.append("wallet-send UI live chain height unchanged")

        wallet_submit_refusal = http_json(
            server_base_url,
            (
                "/api/v1/wallet/transfers/submit"
                "?local_request_id=wallet-send-ui-live-submit-refusal"
                "&draft_id=wallet-send-ui-live-draft"
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
            context="wallet-send UI live wallet-submit refusal",
        )
        write_json(api_artifact_dir / "wallet-send-ui-live-submit-refusal.json", wallet_submit_refusal)
        completed.append("wallet submit remains refused")

        block_refusal = http_json(
            server_base_url,
            (
                "/api/v1/blocks/produce"
                "?local_request_id=wallet-send-ui-live-block-refusal"
                "&producer=xriqdev1author00000000000&max_transactions=4&timestamp_ms=2000"
            ),
            expected_status=403,
            method="POST",
        )
        validate_disabled_response(
            block_refusal,
            expected_code="block_production_disabled",
            expected_flag="--enable-local-block-production",
            context="wallet-send UI live block-production refusal",
        )
        write_json(api_artifact_dir / "wallet-send-ui-live-block-refusal.json", block_refusal)
        completed.append("block production remains refused")
    finally:
        stop_process(server_process)

    if not tx_hash:
        raise SmokeError("wallet-send UI live: no accepted transaction hash recorded")

    summary = {
        "ok": "xriq-phase1-2-wallet-send-ui-live-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "base_confirmed_tx_hash": base_tx_hash,
        "wallet_send_tx_hash": tx_hash,
        "feature_switch": "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
        "serve_readonly_flags": {
            "enable_local_wallet_send": True,
            "enable_local_wallet_submit": False,
            "enable_local_block_production": False,
        },
        "artifacts": {
            "base_confirmed_transfer": str(artifact_dir / "base-confirmed-transfer.json"),
            "ui_summary": str(ui_artifact_dir / "summary.json"),
            "ui_accepted": str(ui_artifact_dir / "wallet-send-ui-live-accepted.json"),
            "mempool": str(api_artifact_dir / "wallet-send-ui-live-mempool.json"),
            "network": str(api_artifact_dir / "wallet-send-ui-live-network.json"),
            "wallet_submit_refusal": str(api_artifact_dir / "wallet-send-ui-live-submit-refusal.json"),
            "block_production_refusal": str(api_artifact_dir / "wallet-send-ui-live-block-refusal.json"),
        },
        "guards": [
            "wallet-send UI requires VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
            "wallet-send UI uses the shared API client helper",
            "wallet-send UI source has no direct fetch or wallet endpoint strings",
            "wallet send requires --enable-local-wallet-send",
            "wallet submit remains disabled without --enable-local-wallet-submit",
            "block production remains disabled without --enable-local-block-production",
            "accepted wallet-send mutation is pending_state_only",
            "chain height remains unchanged by wallet-send",
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
