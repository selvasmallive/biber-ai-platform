#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from xriq_phase1_1_local_e2e_smoke import (
    SmokeError,
    executable_path,
    free_local_port,
    http_json,
    npm_command,
    repo_root,
    run_command,
    run_json,
    start_api_readonly_server,
    stop_process,
    wait_for_api_readonly_server,
    write_json,
)
from xriq_phase1_3_behavior_contract_check import FIXTURE_PATH
from xriq_phase1_3_wallet_behavior_smoke import load_fixture, validate_base_transfer


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-3-demo-{timestamp}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare or launch the XRIQ Phase 1.3 local/private browser demo. "
            "Default mode prepares deterministic demo state and command files."
        )
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--prepare-only",
        action="store_true",
        help="Prepare demo files and commands without starting servers. This is the default.",
    )
    mode.add_argument(
        "--smoke-only",
        action="store_true",
        help="Start the local API/UI, verify both respond, write a summary, then stop.",
    )
    mode.add_argument(
        "--launch",
        action="store_true",
        help="Start the local API/UI and keep them running until Ctrl+C.",
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for demo artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse existing xriq-node and xriq-api debug binaries.",
    )
    parser.add_argument(
        "--api-port",
        type=int,
        default=8090,
        help="API port for launch/smoke modes, unless --auto-port is used.",
    )
    parser.add_argument(
        "--ui-port",
        type=int,
        default=5173,
        help="Vite UI port for launch/smoke modes, unless --auto-port is used.",
    )
    parser.add_argument(
        "--auto-port",
        action="store_true",
        help="Use currently free local ports instead of the requested fixed ports.",
    )
    return parser.parse_args(argv)


def selected_mode(args: argparse.Namespace) -> str:
    if args.launch:
        return "launch"
    if args.smoke_only:
        return "smoke-only"
    return "prepare-only"


def choose_port(requested: int, auto: bool) -> int:
    return free_local_port() if auto else requested


def quote_ps(value: Path | str) -> str:
    text = str(value).replace("`", "``").replace('"', '`"')
    return f'"{text}"'


def quote_sh(value: Path | str) -> str:
    text = str(value).replace("'", "'\"'\"'")
    return f"'{text}'"


def demo_steps() -> list[str]:
    return [
        "Open the printed UI URL.",
        "Confirm the header status is Healthy.",
        "In the Wallet panel, confirm Local Wallet Send says feature switch on.",
        "Use the default demo values: Alice to Carol, amount 5, fee 2, nonce 1, expiry 100.",
        "Click Send Local and confirm the result status is pending with mutation pending_state_only.",
        "Confirm Wallet Activity shows the transaction as pending for Alice/Carol.",
        "In the Admin Status panel, confirm Local Block Production says feature switch on and Pending is 1.",
        "Click Produce Local and confirm Block Height is 2 and Pending After is 0.",
        "Click the refresh button in the app header.",
        "Confirm Wallet Activity/History shows the transaction as confirmed and Admin/Mempool pending is 0.",
    ]


def write_demo_commands(
    *,
    artifact_dir: Path,
    xriq_dir: Path,
    ui_dir: Path,
    api_binary: Path,
    chain_file: Path,
    pending_file: Path,
    api_port: int,
    ui_port: int,
) -> dict[str, str]:
    api_base_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"
    powershell = artifact_dir / "demo-commands.ps1"
    bash = artifact_dir / "demo-commands.sh"

    powershell.write_text(
        "\n".join(
            [
                "# XRIQ Phase 1.3 local/private browser demo commands.",
                "# Terminal 1: API",
                f"Set-Location {quote_ps(xriq_dir)}",
                (
                    f"& {quote_ps(api_binary)} serve-readonly "
                    f"--chain-file {quote_ps(chain_file)} "
                    f"--pending-file {quote_ps(pending_file)} "
                    "--alice-balance 100 "
                    f"--bind 127.0.0.1:{api_port} "
                    "--enable-local-wallet-send true "
                    "--enable-local-block-production true"
                ),
                "",
                "# Terminal 2: UI",
                f"Set-Location {quote_ps(ui_dir)}",
                f"$env:VITE_XRIQ_API_BASE_URL = {quote_ps(api_base_url)}",
                '$env:VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI = "true"',
                '$env:VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI = "true"',
                f"{npm_command()} run dev -- --port {ui_port}",
                "",
                f"# Open {ui_url}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    bash.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "# Terminal 1: API",
                f"cd {quote_sh(xriq_dir)}",
                (
                    f"{quote_sh(api_binary)} serve-readonly "
                    f"--chain-file {quote_sh(chain_file)} "
                    f"--pending-file {quote_sh(pending_file)} "
                    "--alice-balance 100 "
                    f"--bind 127.0.0.1:{api_port} "
                    "--enable-local-wallet-send true "
                    "--enable-local-block-production true"
                ),
                "",
                "# Terminal 2: UI",
                f"cd {quote_sh(ui_dir)}",
                f"export VITE_XRIQ_API_BASE_URL={quote_sh(api_base_url)}",
                "export VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
                "export VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
                f"npm run dev -- --port {ui_port}",
                "",
                f"# Open {ui_url}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "powershell": str(powershell),
        "bash": str(bash),
    }


def prepare_demo_state(
    *,
    args: argparse.Namespace,
    mode: str,
) -> dict[str, Any]:
    fixture = load_fixture()
    root = repo_root()
    xriq_dir = root / "xriq"
    ui_dir = xriq_dir / "apps" / "explorer-ui"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=False)
    write_json(artifact_dir / "contract-fixture.json", fixture)

    if not args.skip_build:
        run_command(
            "build XRIQ Phase 1.3 demo binaries",
            ["cargo", "build", "-q", "-p", "xriq-node", "-p", "xriq-api"],
            cwd=xriq_dir,
        )

    node_binary = executable_path(xriq_dir, "xriq-node")
    api_binary = executable_path(xriq_dir, "xriq-api")
    for binary in [node_binary, api_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary: {binary}")

    api_port = choose_port(args.api_port, args.auto_port)
    ui_port = choose_port(args.ui_port, args.auto_port)
    if api_port == ui_port:
        ui_port = free_local_port()
    api_base_url = f"http://127.0.0.1:{api_port}"
    ui_url = f"http://127.0.0.1:{ui_port}"

    chain_file = artifact_dir / "phase1-3-demo-chain.bin"
    pending_file = artifact_dir / "phase1-3-demo-pending.tsv"
    preflight_pending_file = artifact_dir / "phase1-3-demo-preflight-pending.tsv"

    base = fixture["base_chain_setup"]
    base_transfer = base["transfer"]
    base_response = run_json(
        "create Phase 1.3 demo base chain",
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

    command_files = write_demo_commands(
        artifact_dir=artifact_dir,
        xriq_dir=xriq_dir,
        ui_dir=ui_dir,
        api_binary=api_binary,
        chain_file=chain_file,
        pending_file=pending_file,
        api_port=api_port,
        ui_port=ui_port,
    )

    context = {
        "ok": "xriq-phase1-3-demo-context",
        "mode": mode,
        "artifact_dir": str(artifact_dir),
        "fixture": str(FIXTURE_PATH),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "base_confirmed_tx_hash": base_tx_hash,
        "api_base_url": api_base_url,
        "ui_url": ui_url,
        "api_command_file": command_files["powershell"],
        "bash_command_file": command_files["bash"],
        "demo_inputs": {
            "from_address": fixture["identities"]["sender"],
            "to_address": fixture["identities"]["behavior_recipient"],
            "amount_base_units": "5",
            "fee_base_units": "2",
            "nonce": 1,
            "expires_at_height": 100,
            "producer": fixture["identities"]["producer"],
            "max_transactions": 4,
        },
        "feature_switches": {
            "wallet_send_ui": "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
            "block_production_ui": "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
        },
        "api_flags": {
            "enable_local_wallet_send": True,
            "enable_local_wallet_submit": False,
            "enable_local_block_production": True,
        },
        "manual_demo_steps": demo_steps(),
        "scope_boundaries": [
            "local/private demo only",
            "wallet submit UI remains deferred",
            "test identities only",
            "no private keys, seed phrases, signing, custody, public mainnet, DEX, or production infrastructure",
        ],
    }
    write_json(artifact_dir / "demo-context.json", context)
    return {
        "root": root,
        "xriq_dir": xriq_dir,
        "ui_dir": ui_dir,
        "artifact_dir": artifact_dir,
        "chain_file": chain_file,
        "pending_file": pending_file,
        "api_base_url": api_base_url,
        "ui_url": ui_url,
        "context": context,
        "api_binary": api_binary,
    }


def start_ui_dev_server(
    *,
    ui_dir: Path,
    artifact_dir: Path,
    api_base_url: str,
    ui_port: int,
) -> subprocess.Popen[str]:
    log_path = artifact_dir / "vite-ui-demo.log"
    log_handle = log_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env["VITE_XRIQ_API_BASE_URL"] = api_base_url
    env["VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI"] = "true"
    env["VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI"] = "true"
    command = [npm_command(), "run", "dev", "--", "--port", str(ui_port)]
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform.startswith("win") else 0
    try:
        process = subprocess.Popen(
            command,
            cwd=ui_dir,
            stdout=log_handle,
            stderr=log_handle,
            text=True,
            env=env,
            creationflags=creationflags,
        )
    except Exception:
        log_handle.close()
        raise
    process.log_path = log_path  # type: ignore[attr-defined]
    process.log_handle = log_handle  # type: ignore[attr-defined]
    return process


def stop_ui_dev_server(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    if process.poll() is None:
        if sys.platform.startswith("win"):
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    log_handle = getattr(process, "log_handle", None)
    if log_handle is not None:
        log_handle.close()


def wait_for_ui_dev_server(ui_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            log_path = getattr(process, "log_path", None)
            stderr = (
                log_path.read_text(encoding="utf-8")
                if isinstance(log_path, Path) and log_path.exists()
                else ""
            )
            raise SmokeError(f"Vite dev server exited early with {process.returncode}: {stderr}")
        try:
            with urlopen(ui_url, timeout=2) as response:
                if response.status == 200:
                    return
        except (HTTPError, URLError, TimeoutError) as error:
            last_error = error
        time.sleep(0.3)
    raise SmokeError(f"Vite dev server did not become ready at {ui_url}: {last_error}")


def launch_or_smoke(args: argparse.Namespace, mode: str) -> dict[str, Any]:
    state = prepare_demo_state(args=args, mode=mode)
    artifact_dir = state["artifact_dir"]
    api_process = None
    ui_process = None
    ui_port = int(state["ui_url"].rsplit(":", 1)[1])
    try:
        api_process = start_api_readonly_server(
            state["api_binary"],
            state["xriq_dir"],
            artifact_dir,
            chain_file=state["chain_file"],
            pending_file=state["pending_file"],
            bind=f"127.0.0.1:{state['api_base_url'].rsplit(':', 1)[1]}",
            enable_local_wallet_send=True,
            enable_local_block_production=True,
            stderr_log_name="api-demo-server.stderr.log",
        )
        wait_for_api_readonly_server(state["api_base_url"], api_process)
        health = http_json(state["api_base_url"], "/api/v1/health")
        ui_process = start_ui_dev_server(
            ui_dir=state["ui_dir"],
            artifact_dir=artifact_dir,
            api_base_url=state["api_base_url"],
            ui_port=ui_port,
        )
        wait_for_ui_dev_server(state["ui_url"], ui_process)

        summary = {
            **state["context"],
            "ok": "xriq-phase1-3-demo-launcher",
            "api_health": health,
            "api_log": str(artifact_dir / "api-demo-server.stderr.log"),
            "ui_log": str(artifact_dir / "vite-ui-demo.log"),
            "servers_ready": True,
        }
        write_json(artifact_dir / "summary.json", summary)

        if mode == "launch":
            print_demo_banner(summary)
            while True:
                time.sleep(1)

        return summary
    except KeyboardInterrupt:
        print("\nStopping XRIQ Phase 1.3 demo servers...", flush=True)
        return state["context"]
    finally:
        stop_ui_dev_server(ui_process)
        stop_process(api_process)


def print_demo_banner(summary: dict[str, Any]) -> None:
    print("\nXRIQ Phase 1.3 local/private demo is running.", flush=True)
    print(f"UI:  {summary['ui_url']}", flush=True)
    print(f"API: {summary['api_base_url']}", flush=True)
    print(f"Artifacts: {summary['artifact_dir']}", flush=True)
    print("\nManual demo steps:", flush=True)
    for index, step in enumerate(summary["manual_demo_steps"], start=1):
        print(f"{index}. {step}", flush=True)
    print("\nPress Ctrl+C in this terminal to stop both local servers.", flush=True)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = selected_mode(args)
    try:
        if mode == "prepare-only":
            state = prepare_demo_state(args=args, mode=mode)
            summary = state["context"]
            write_json(state["artifact_dir"] / "summary.json", summary)
        else:
            summary = launch_or_smoke(args, mode)
    except SmokeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
