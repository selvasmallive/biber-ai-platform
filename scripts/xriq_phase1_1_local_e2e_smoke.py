#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ALICE = "xriqdev1alice00000000000"
BOB = "xriqdev1bobbb00000000000"
CAROL = "xriqdev1carol00000000000"


class SmokeError(RuntimeError):
    pass


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_artifact_dir(root: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return root / "xriq" / "target" / f"xriq-phase1-1-local-e2e-smoke-{timestamp}"


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


def run_command(
    name: str,
    command: list[str],
    *,
    cwd: Path,
    capture: bool = True,
    stdin_text: str | None = None,
) -> str:
    print(f"==> {name}", flush=True)
    print("$ " + " ".join(command), flush=True)
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=capture,
        input=stdin_text,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stdout = completed.stdout if capture else ""
        stderr = completed.stderr if capture else ""
        raise SmokeError(
            f"{name} failed with exit code {completed.returncode}\n"
            f"stdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return completed.stdout.strip() if capture else ""


def run_json(name: str, command: list[str], *, cwd: Path) -> dict[str, Any]:
    output = run_command(name, command, cwd=cwd)
    try:
        payload = json.loads(output)
    except json.JSONDecodeError as error:
        raise SmokeError(f"{name}: command did not return valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise SmokeError(f"{name}: expected JSON object output")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_equal(payload: dict[str, Any], key: str, expected: Any, context: str) -> None:
    actual = payload.get(key)
    if actual != expected:
        raise SmokeError(f"{context}: expected {key}={expected!r}, got {actual!r}")


def require_hash(value: Any, context: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise SmokeError(f"{context}: expected 64-character lowercase hex hash, got {value!r}")
    return value


def require_list(value: Any, context: str) -> list[Any]:
    if not isinstance(value, list):
        raise SmokeError(f"{context}: expected list, got {type(value).__name__}")
    return value


def parse_api_request_output(output: str, context: str) -> tuple[int, str, dict[str, Any]]:
    match = re.match(r"status_code=(\d+)\nreason=([^\n]*)\nbody=(.*)\Z", output, re.DOTALL)
    if not match:
        raise SmokeError(f"{context}: unexpected xriq-api request output:\n{output}")
    status_code = int(match.group(1))
    reason = match.group(2)
    body_text = match.group(3)
    try:
        body = json.loads(body_text)
    except json.JSONDecodeError as error:
        raise SmokeError(f"{context}: API body was not valid JSON: {error}") from error
    if not isinstance(body, dict):
        raise SmokeError(f"{context}: expected API JSON object body")
    return status_code, reason, body


def parse_key_value_output(output: str, context: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        if "=" not in line:
            raise SmokeError(f"{context}: expected key=value line, got {line!r}")
        key, value = line.split("=", 1)
        values[key] = value
    return values


def assert_api_ok(
    api_binary: Path,
    xriq_dir: Path,
    chain_file: Path,
    pending_file: Path,
    target: str,
    artifact_path: Path,
    validate: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    output = run_command(
        f"xriq-api {target}",
        [
            str(api_binary),
            "request",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(pending_file),
            "--alice-balance",
            "100",
            "--target",
            target,
        ],
        cwd=xriq_dir,
    )
    status_code, reason, payload = parse_api_request_output(output, target)
    if status_code != 200:
        raise SmokeError(f"{target}: expected HTTP 200, got {status_code} {reason}: {payload}")
    if "environment" in payload:
        require_equal(payload, "environment", "private-devnet", target)
    validate(payload)
    write_json(artifact_path, payload)
    return payload


def assert_api_status(
    api_binary: Path,
    xriq_dir: Path,
    chain_file: Path,
    pending_file: Path,
    target: str,
    expected_status: int,
    artifact_path: Path,
    validate: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    output = run_command(
        f"xriq-api {target}",
        [
            str(api_binary),
            "request",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(pending_file),
            "--alice-balance",
            "100",
            "--target",
            target,
        ],
        cwd=xriq_dir,
    )
    status_code, reason, payload = parse_api_request_output(output, target)
    if status_code != expected_status:
        raise SmokeError(
            f"{target}: expected HTTP {expected_status}, got {status_code} {reason}: {payload}"
        )
    if "environment" in payload:
        require_equal(payload, "environment", "private-devnet", target)
    validate(payload)
    write_json(artifact_path, payload)
    return payload


def npm_command() -> str:
    return "npm.cmd" if sys.platform.startswith("win") else "npm"


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def http_json(base_url: str, target: str, *, expected_status: int = 200) -> dict[str, Any]:
    request = Request(base_url + target, method="GET")
    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
            text = response.read().decode("utf-8")
    except HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8")
    except URLError as exc:
        raise SmokeError(f"GET {target} failed: {exc}") from exc

    if status != expected_status:
        raise SmokeError(f"GET {target}: expected HTTP {expected_status}, got {status}: {text}")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SmokeError(f"GET {target}: invalid JSON response: {exc}: {text}") from exc
    if not isinstance(payload, dict):
        raise SmokeError(f"GET {target}: expected JSON object response")
    return payload


def start_api_readonly_server(
    api_binary: Path,
    xriq_dir: Path,
    artifact_dir: Path,
    *,
    chain_file: Path,
    pending_file: Path,
    bind: str,
    postgres_container: str,
    postgres_database: str,
) -> subprocess.Popen[str]:
    stderr_log = artifact_dir / "api-postgres-read-model-server.stderr.log"
    stderr_handle = stderr_log.open("w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            [
                str(api_binary),
                "serve-readonly",
                "--chain-file",
                str(chain_file),
                "--pending-file",
                str(pending_file),
                "--alice-balance",
                "100",
                "--bind",
                bind,
                "--postgres-docker-container",
                postgres_container,
                "--postgres-database",
                postgres_database,
            ],
            cwd=xriq_dir,
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


def stop_process(process: subprocess.Popen[str] | None) -> None:
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


def wait_for_api_readonly_server(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 20
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stop_process(process)
            stderr_log = getattr(process, "stderr_log_path", None)
            stderr = (
                stderr_log.read_text(encoding="utf-8")
                if isinstance(stderr_log, Path) and stderr_log.exists()
                else ""
            )
            raise SmokeError(
                f"xriq-api serve-readonly exited early with {process.returncode}: {stderr}"
            )
        try:
            health = http_json(base_url, "/api/v1/health")
            require_equal(health, "ok", True, "serve-readonly health")
            return
        except Exception as exc:  # noqa: BLE001 - retry during startup.
            last_error = exc
            time.sleep(0.2)
    raise SmokeError(f"xriq-api serve-readonly did not become healthy: {last_error}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a local CPU-only XRIQ Phase 1.1 end-to-end smoke across "
            "contracts, product API routes, and React UI static guardrails."
        )
    )
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=None,
        help="Directory for smoke artifacts. Defaults under xriq/target/.",
    )
    parser.add_argument(
        "--skip-ui-check",
        action="store_true",
        help="Skip the React UI static guardrail check.",
    )
    parser.add_argument(
        "--skip-contract-check",
        action="store_true",
        help="Skip the Phase 1.1 contract/schema/fixture check.",
    )
    parser.add_argument(
        "--postgres-docker-live",
        action="store_true",
        help=(
            "Start/use the local Compose postgres service and validate the "
            "generated SQL against a dedicated smoke database. Defaults off."
        ),
    )
    parser.add_argument(
        "--postgres-docker-container",
        default="xriq-postgres",
        help="Postgres container name to use with --postgres-docker-live.",
    )
    parser.add_argument(
        "--postgres-docker-database",
        default="xriq_phase1_1_smoke",
        help=(
            "Dedicated database name to reset and use with "
            "--postgres-docker-live."
        ),
    )
    return parser.parse_args(argv)


def validate_postgres_identifier(value: str, context: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", value):
        raise SmokeError(
            f"{context}: expected PostgreSQL identifier with letters, digits, "
            f"and underscores only, got {value!r}"
        )
    return value


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def wait_for_docker_postgres(root: Path, container: str, timeout_seconds: int = 90) -> str:
    deadline = time.monotonic() + timeout_seconds
    last_status = "unknown"
    while time.monotonic() < deadline:
        completed = subprocess.run(
            [
                "docker",
                "inspect",
                "--format={{.State.Health.Status}}",
                container,
            ],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            last_status = completed.stdout.strip()
            if last_status == "healthy":
                return last_status
        else:
            last_status = completed.stderr.strip() or completed.stdout.strip()
        time.sleep(2)
    raise SmokeError(
        f"postgres docker container {container!r} did not become healthy "
        f"within {timeout_seconds}s; last status: {last_status}"
    )


def docker_psql(
    root: Path,
    container: str,
    database: str,
    sql: str,
    label: str,
    *,
    psql_args: list[str] | None = None,
) -> str:
    command = [
        "docker",
        "exec",
        "-i",
        container,
        "psql",
        "-U",
        "xriq",
        "-d",
        database,
        "-v",
        "ON_ERROR_STOP=1",
    ]
    command.extend(psql_args or [])
    return run_command(label, command, cwd=root, stdin_text=sql)


def run_postgres_docker_live(
    root: Path,
    xriq_dir: Path,
    indexer_sql: str,
    indexer_dir: Path,
    *,
    container: str,
    database: str,
) -> dict[str, Any]:
    validate_postgres_identifier(database, "postgres docker database")
    schema_sql = (xriq_dir / "db" / "schema.sql").read_text(encoding="utf-8")

    run_command(
        "start local XRIQ Postgres",
        ["docker", "compose", "up", "-d", "postgres"],
        cwd=root,
    )
    health = wait_for_docker_postgres(root, container)
    database_exists = docker_psql(
        root,
        container,
        "postgres",
        f"SELECT 1 FROM pg_database WHERE datname = {sql_literal(database)};\n",
        "check postgres smoke database",
        psql_args=["-t", "-A"],
    ).strip()
    if database_exists != "1":
        run_command(
            "create postgres smoke database",
            ["docker", "exec", container, "createdb", "-U", "xriq", database],
            cwd=root,
        )

    docker_psql(
        root,
        container,
        database,
        (
            "DROP SCHEMA IF EXISTS public CASCADE;\n"
            "CREATE SCHEMA public;\n"
            "GRANT ALL ON SCHEMA public TO xriq;\n"
        ),
        "reset postgres smoke schema",
    )
    docker_psql(root, container, database, schema_sql, "apply postgres schema")
    docker_psql(root, container, database, indexer_sql, "apply postgres indexer write plan")
    verify_output = docker_psql(
        root,
        container,
        database,
        postgres_verification_sql(),
        "verify postgres indexed counts",
        psql_args=["-t", "-A"],
    )
    counts = parse_key_value_output(verify_output, "postgres docker live verify")
    expected_counts = {
        "blocks": "1",
        "transactions": "1",
        "accounts": "3",
        "account_balances": "3",
        "account_transactions": "2",
        "audit_events": "1",
        "indexer_runs": "1",
        "latest_height": "1",
    }
    for key, expected in expected_counts.items():
        if counts.get(key) != expected:
            raise SmokeError(
                f"postgres docker live verify: expected {key}={expected!r}, "
                f"got {counts.get(key)!r}"
            )

    summary = {
        "mode": "docker-live",
        "container": container,
        "database": database,
        "health": health,
        "counts": counts,
        "warning": (
            "local-private-devnet-smoke-database-schema-reset-no-public-or-prod-data"
        ),
    }
    write_json(indexer_dir / "postgres-docker-live.json", summary)
    return summary


def postgres_verification_sql() -> str:
    return (
        "SELECT 'blocks=' || count(*) FROM xriq_blocks;\n"
        "SELECT 'transactions=' || count(*) FROM xriq_transactions;\n"
        "SELECT 'accounts=' || count(*) FROM xriq_accounts;\n"
        "SELECT 'account_balances=' || count(*) FROM xriq_account_balances;\n"
        "SELECT 'account_transactions=' || count(*) FROM xriq_account_transactions;\n"
        "SELECT 'audit_events=' || count(*) FROM xriq_audit_events;\n"
        "SELECT 'indexer_runs=' || count(*) FROM xriq_indexer_runs;\n"
        "SELECT 'latest_height=' || COALESCE(MAX(height)::text, 'none') FROM xriq_blocks;\n"
    )


def run_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = repo_root()
    xriq_dir = root / "xriq"
    ui_dir = xriq_dir / "apps" / "explorer-ui"
    artifact_dir = (args.artifact_dir or default_artifact_dir(root)).resolve()
    artifact_dir.mkdir(parents=True, exist_ok=False)
    api_artifact_dir = artifact_dir / "api"

    completed: list[str] = []
    skipped: list[str] = []
    routes_checked: list[str] = []
    failure_routes_checked: list[str] = []

    if args.skip_contract_check:
        skipped.append("phase1.1 contract check")
    else:
        run_command(
            "phase1.1 contract check",
            [sys.executable, str(root / "scripts" / "xriq_phase1_1_contract_check.py")],
            cwd=root,
        )
        completed.append("phase1.1 contract check")

    if args.skip_ui_check:
        skipped.append("explorer UI static guardrail")
    else:
        run_command("explorer UI static guardrail", [npm_command(), "run", "check"], cwd=ui_dir)
        completed.append("explorer UI static guardrail")

    run_command(
        "build xriq smoke binaries",
        [
            "cargo",
            "build",
            "-q",
            "-p",
            "xriq-node",
            "-p",
            "xriq-wallet",
            "-p",
            "xriq-api",
            "-p",
            "xriq-indexer",
        ],
        cwd=xriq_dir,
    )
    completed.append("build xriq smoke binaries")

    node_binary = executable_path(xriq_dir, "xriq-node")
    wallet_binary = executable_path(xriq_dir, "xriq-wallet")
    api_binary = executable_path(xriq_dir, "xriq-api")
    indexer_binary = executable_path(xriq_dir, "xriq-indexer")
    for binary in [node_binary, wallet_binary, api_binary, indexer_binary]:
        if not binary.exists():
            raise SmokeError(f"missing binary after build: {binary}")

    chain_file = artifact_dir / "chain.bin"
    preflight_pending_file = artifact_dir / "preflight-pending.tsv"
    pending_file = artifact_dir / "pending.tsv"
    transfer_file = artifact_dir / "pending-transfer.json"

    preflight = run_json(
        "create confirmed private-devnet transfer",
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
    confirmed_tx_hash = require_hash(
        preflight.get("transaction_hash") or preflight.get("tx_hash"),
        "confirmed transfer hash",
    )
    require_equal(preflight, "confirmed_block_height", 1, "confirmed transfer")
    require_equal(preflight, "final_balance_base_units", "73", "confirmed transfer")
    write_json(artifact_dir / "confirmed-transfer.json", preflight)
    completed.append("confirmed transfer")

    pending_transfer = run_json(
        "create pending wallet transfer draft",
        [
            str(wallet_binary),
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            ALICE,
            "--to",
            CAROL,
            "--amount",
            "5",
            "--fee",
            "2",
            "--nonce",
            "1",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    write_json(transfer_file, pending_transfer)

    pending_submit = run_json(
        "submit durable pending transfer",
        [
            str(wallet_binary),
            "submit",
            "--chain-file",
            str(chain_file),
            "--pending-file",
            str(pending_file),
            "--transfer-file",
            str(transfer_file),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    pending_tx_hash = require_hash(
        pending_submit.get("transaction_hash") or pending_submit.get("tx_hash"),
        "pending transfer hash",
    )
    require_equal(pending_submit, "status", "pending", "pending transfer")
    write_json(artifact_dir / "pending-submit.json", pending_submit)
    completed.append("pending transfer")

    indexer_dir = artifact_dir / "indexer"
    indexer_replay = run_json(
        "xriq-indexer replay json",
        [
            str(indexer_binary),
            "replay",
            "--chain-file",
            str(chain_file),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ],
        cwd=xriq_dir,
    )
    require_equal(indexer_replay, "format_version", "xriq-indexer-replay-json-v1", "indexer replay")
    require_equal(indexer_replay, "command", "replay", "indexer replay")
    require_equal(indexer_replay, "environment", "private-devnet", "indexer replay")
    require_equal(indexer_replay, "current_height", 1, "indexer replay")
    summary = indexer_replay.get("summary")
    if not isinstance(summary, dict):
        raise SmokeError("indexer replay: expected summary object")
    require_equal(summary, "blocks_indexed", 1, "indexer replay summary")
    require_equal(summary, "transactions_indexed", 1, "indexer replay summary")
    require_equal(summary, "audit_events_indexed", 1, "indexer replay summary")
    read_model_counts = indexer_replay.get("read_model_counts")
    if not isinstance(read_model_counts, dict):
        raise SmokeError("indexer replay: expected read_model_counts object")
    require_equal(read_model_counts, "accounts", 3, "indexer replay read_model_counts")
    write_json(indexer_dir / "replay.json", indexer_replay)

    indexer_sql = run_command(
        "xriq-indexer replay sql",
        [
            str(indexer_binary),
            "replay",
            "--chain-file",
            str(chain_file),
            "--alice-balance",
            "100",
            "--format",
            "sql",
        ],
        cwd=xriq_dir,
    )
    for marker in [
        "INSERT INTO xriq_indexer_runs",
        "INSERT INTO xriq_blocks",
        "INSERT INTO xriq_transactions",
        "ON CONFLICT",
        "COMMIT;",
    ]:
        if marker not in indexer_sql:
            raise SmokeError(f"indexer SQL write plan: missing {marker!r}")
    (indexer_dir / "write-plan.sql").write_text(indexer_sql + "\n", encoding="utf-8")

    apply_output = run_command(
        "xriq-indexer apply-postgres dry-run",
        [
            str(indexer_binary),
            "apply-postgres",
            "--chain-file",
            str(chain_file),
            "--alice-balance",
            "100",
            "--schema-file",
            "db/schema.sql",
            "--dry-run",
            "true",
        ],
        cwd=xriq_dir,
    )
    apply_summary = parse_key_value_output(apply_output, "indexer apply-postgres")
    expected_apply = {
        "environment": "private-devnet",
        "mode": "dry-run",
        "database_url_configured": "false",
        "current_height": "1",
        "blocks_indexed": "1",
        "transactions_indexed": "1",
        "schema_applied": "false",
        "write_plan_applied": "false",
    }
    for key, expected in expected_apply.items():
        if apply_summary.get(key) != expected:
            raise SmokeError(
                f"indexer apply-postgres: expected {key}={expected!r}, got {apply_summary.get(key)!r}"
            )
    (indexer_dir / "apply-postgres-dry-run.txt").write_text(
        apply_output + "\n", encoding="utf-8"
    )

    verify_output = run_command(
        "xriq-indexer verify-postgres dry-run",
        [str(indexer_binary), "verify-postgres", "--dry-run", "true"],
        cwd=xriq_dir,
    )
    verify_summary = parse_key_value_output(verify_output, "indexer verify-postgres")
    expected_verify = {
        "environment": "private-devnet",
        "mode": "dry-run",
        "database_url_configured": "false",
        "verification_query_available": "true",
        "verification_query_executed": "false",
        "verification_result": "not-run",
    }
    for key, expected in expected_verify.items():
        if verify_summary.get(key) != expected:
            raise SmokeError(
                f"indexer verify-postgres: expected {key}={expected!r}, got {verify_summary.get(key)!r}"
            )
    (indexer_dir / "verify-postgres-dry-run.txt").write_text(
        verify_output + "\n", encoding="utf-8"
    )
    completed.append("indexer replay and postgres dry-run")

    postgres_docker_live = None
    postgres_server_status = None
    postgres_api_overview = None
    postgres_server_overview = None
    postgres_api_blocks = None
    postgres_server_blocks = None
    postgres_ui_status = None
    if args.postgres_docker_live:
        postgres_docker_live = run_postgres_docker_live(
            root,
            xriq_dir,
            indexer_sql,
            indexer_dir,
            container=args.postgres_docker_container,
            database=args.postgres_docker_database,
        )
        completed.append("postgres docker live smoke")
        postgres_api_output = run_command(
            "xriq-api postgres read-model status",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/admin/postgres/read-model-status",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_status = parse_api_request_output(
            postgres_api_output,
            "xriq-api postgres read-model status",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres read-model status: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_status}"
            )
        require_equal(
            postgres_api_status,
            "source",
            "postgres-read-model",
            "xriq-api postgres read-model status",
        )
        require_equal(
            postgres_api_status,
            "read_only",
            True,
            "xriq-api postgres read-model status",
        )
        counts = postgres_api_status.get("counts")
        if not isinstance(counts, dict):
            raise SmokeError("xriq-api postgres read-model status: expected counts object")
        expected_counts = postgres_docker_live["counts"]
        for key, expected in expected_counts.items():
            if key == "latest_height":
                continue
            if counts.get(key) != int(expected):
                raise SmokeError(
                    "xriq-api postgres read-model status: expected "
                    f"{key}={expected!r}, got {counts.get(key)!r}"
                )
        require_equal(
            postgres_api_status,
            "latest_height",
            int(expected_counts["latest_height"]),
            "xriq-api postgres read-model status",
        )
        write_json(indexer_dir / "postgres-api-read-model-status.json", postgres_api_status)
        completed.append("postgres-backed api read-model status")

        def validate_postgres_overview(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            chain = payload.get("chain")
            indexer = payload.get("indexer")
            totals = payload.get("totals")
            if not isinstance(chain, dict):
                raise SmokeError(f"{context}: expected chain object")
            if not isinstance(indexer, dict):
                raise SmokeError(f"{context}: expected indexer object")
            if not isinstance(totals, dict):
                raise SmokeError(f"{context}: expected totals object")
            require_equal(chain, "current_height", int(expected_counts["latest_height"]), context)
            require_hash(chain.get("latest_block_hash"), f"{context} latest block hash")
            require_hash(chain.get("state_root"), f"{context} state root")
            require_equal(chain, "stored_blocks", int(expected_counts["blocks"]), context)
            require_equal(chain, "pending_transactions", 0, context)
            require_equal(indexer, "service", "xriq-indexer", context)
            require_equal(indexer, "status", "completed", context)
            require_equal(
                indexer,
                "latest_indexed_height",
                int(expected_counts["latest_height"]),
                context,
            )
            require_equal(totals, "blocks", int(expected_counts["blocks"]), context)
            require_equal(
                totals, "transactions", int(expected_counts["transactions"]), context
            )
            require_equal(
                totals, "accounts", int(expected_counts["account_balances"]), context
            )

        postgres_overview_output = run_command(
            "xriq-api postgres explorer overview",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/explorer/overview",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_overview = parse_api_request_output(
            postgres_overview_output,
            "xriq-api postgres explorer overview",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres explorer overview: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_overview}"
            )
        validate_postgres_overview(
            postgres_api_overview,
            "xriq-api postgres explorer overview",
        )
        write_json(indexer_dir / "postgres-api-explorer-overview.json", postgres_api_overview)
        completed.append("postgres-backed api explorer overview")

        def validate_postgres_blocks(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "limit", 5, context)
            require_equal(payload, "next_cursor", None, context)
            blocks = require_list(payload.get("blocks"), context)
            if len(blocks) != 1 or not isinstance(blocks[0], dict):
                raise SmokeError(f"{context}: expected exactly one block object")
            block = blocks[0]
            require_equal(block, "height", int(expected_counts["latest_height"]), context)
            require_hash(block.get("block_hash"), f"{context} block hash")
            require_hash(block.get("previous_block_hash"), f"{context} previous block hash")
            require_hash(block.get("state_root"), f"{context} state root")
            require_hash(block.get("transactions_root"), f"{context} transactions root")
            require_equal(block, "transaction_count", 1, context)
            timestamp = block.get("timestamp_utc")
            if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
                raise SmokeError(f"{context}: expected UTC timestamp, got {timestamp!r}")

        postgres_blocks_output = run_command(
            "xriq-api postgres blocks",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/blocks?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_blocks = parse_api_request_output(
            postgres_blocks_output,
            "xriq-api postgres blocks",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres blocks: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_blocks}"
            )
        validate_postgres_blocks(postgres_api_blocks, "xriq-api postgres blocks")
        write_json(indexer_dir / "postgres-api-blocks.json", postgres_api_blocks)
        completed.append("postgres-backed api blocks")

        server_port = free_local_port()
        server_bind = f"127.0.0.1:{server_port}"
        server_base_url = f"http://{server_bind}"
        server_process: subprocess.Popen[str] | None = None
        try:
            server_process = start_api_readonly_server(
                api_binary,
                xriq_dir,
                artifact_dir,
                chain_file=chain_file,
                pending_file=pending_file,
                bind=server_bind,
                postgres_container=args.postgres_docker_container,
                postgres_database=args.postgres_docker_database,
            )
            wait_for_api_readonly_server(server_base_url, server_process)
            postgres_server_status = http_json(
                server_base_url, "/api/v1/admin/postgres/read-model-status"
            )
            postgres_server_overview = http_json(server_base_url, "/api/v1/explorer/overview")
            postgres_server_blocks = http_json(server_base_url, "/api/v1/blocks?limit=5")
            postgres_ui_artifact = indexer_dir / "postgres-admin-ui-read-model-status.json"
            run_command(
                "xriq admin postgres UI status smoke",
                [
                    npm_command(),
                    "run",
                    "check:postgres-ui",
                    "--",
                    "--base-url",
                    server_base_url,
                    "--expect",
                    "available",
                    "--expected-database",
                    args.postgres_docker_database,
                    "--expected-blocks",
                    expected_counts["blocks"],
                    "--expected-transactions",
                    expected_counts["transactions"],
                    "--expected-accounts",
                    expected_counts["accounts"],
                    "--expected-account-history",
                    expected_counts["account_transactions"],
                    "--expected-audit-events",
                    expected_counts["audit_events"],
                    "--artifact",
                    str(postgres_ui_artifact),
                ],
                cwd=ui_dir,
            )
            postgres_ui_status = json.loads(postgres_ui_artifact.read_text(encoding="utf-8"))
        finally:
            stop_process(server_process)
        require_equal(
            postgres_server_status,
            "source",
            "postgres-read-model",
            "xriq-api serve-readonly postgres read-model status",
        )
        require_equal(
            postgres_server_status,
            "read_only",
            True,
            "xriq-api serve-readonly postgres read-model status",
        )
        server_counts = postgres_server_status.get("counts")
        if not isinstance(server_counts, dict):
            raise SmokeError(
                "xriq-api serve-readonly postgres read-model status: expected counts object"
            )
        for key, expected in expected_counts.items():
            if key == "latest_height":
                continue
            if server_counts.get(key) != int(expected):
                raise SmokeError(
                    "xriq-api serve-readonly postgres read-model status: expected "
                    f"{key}={expected!r}, got {server_counts.get(key)!r}"
                )
        require_equal(
            postgres_server_status,
            "latest_height",
            int(expected_counts["latest_height"]),
            "xriq-api serve-readonly postgres read-model status",
        )
        validate_postgres_overview(
            postgres_server_overview,
            "xriq-api serve-readonly postgres explorer overview",
        )
        validate_postgres_blocks(
            postgres_server_blocks,
            "xriq-api serve-readonly postgres blocks",
        )
        write_json(
            indexer_dir / "postgres-server-read-model-status.json", postgres_server_status
        )
        write_json(
            indexer_dir / "postgres-server-explorer-overview.json", postgres_server_overview
        )
        write_json(indexer_dir / "postgres-server-blocks.json", postgres_server_blocks)
        completed.append("postgres-backed server read-model status")
        completed.append("postgres-backed server explorer overview")
        completed.append("postgres-backed server blocks")
        completed.append("postgres-backed admin UI read-model status")
    else:
        skipped.append("postgres docker live smoke")

    def check(target: str, name: str, validate: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
        routes_checked.append(target)
        return assert_api_ok(
            api_binary,
            xriq_dir,
            chain_file,
            pending_file,
            target,
            api_artifact_dir / f"{name}.json",
            validate,
        )

    def check_status(
        target: str,
        name: str,
        expected_status: int,
        validate: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        failure_routes_checked.append(target)
        return assert_api_status(
            api_binary,
            xriq_dir,
            chain_file,
            pending_file,
            target,
            expected_status,
            api_artifact_dir / f"{name}.json",
            validate,
        )

    def validate_health(payload: dict[str, Any]) -> None:
        require_equal(payload, "ok", True, "health")
        require_equal(payload, "service", "xriq-api", "health")

    def validate_network(payload: dict[str, Any]) -> None:
        require_equal(payload, "current_height", 1, "network")
        require_hash(payload.get("latest_block_hash"), "network latest block hash")

    def validate_overview(payload: dict[str, Any]) -> None:
        chain = payload.get("chain")
        totals = payload.get("totals")
        if not isinstance(chain, dict) or not isinstance(totals, dict):
            raise SmokeError("overview: expected chain and totals objects")
        require_equal(chain, "current_height", 1, "overview chain")
        require_equal(chain, "pending_transactions", 1, "overview chain")
        require_equal(totals, "blocks", 1, "overview totals")
        require_equal(totals, "transactions", 1, "overview totals")

    def validate_blocks(payload: dict[str, Any]) -> None:
        blocks = require_list(payload.get("blocks"), "blocks")
        if len(blocks) != 1 or not isinstance(blocks[0], dict):
            raise SmokeError("blocks: expected exactly one block object")
        require_equal(blocks[0], "height", 1, "blocks")

    def validate_block(payload: dict[str, Any]) -> None:
        require_equal(payload, "height", 1, "block detail")
        transactions = require_list(payload.get("transactions"), "block transactions")
        if not transactions:
            raise SmokeError("block detail: expected transaction list")

    def validate_transactions(payload: dict[str, Any]) -> None:
        transactions = require_list(payload.get("transactions"), "transactions")
        if len(transactions) != 1 or not isinstance(transactions[0], dict):
            raise SmokeError("transactions: expected exactly one transaction object")
        require_equal(transactions[0], "tx_hash", confirmed_tx_hash, "transactions")

    def validate_transaction(payload: dict[str, Any]) -> None:
        require_equal(payload, "tx_hash", confirmed_tx_hash, "transaction detail")
        require_equal(payload, "status", "confirmed", "transaction detail")

    def validate_accounts(payload: dict[str, Any]) -> None:
        accounts = require_list(payload.get("accounts"), "accounts")
        addresses = {row.get("address") for row in accounts if isinstance(row, dict)}
        if ALICE not in addresses or BOB not in addresses:
            raise SmokeError("accounts: expected alice and bob")

    def validate_account(payload: dict[str, Any]) -> None:
        require_equal(payload, "address", ALICE, "account detail")
        require_equal(payload, "balance_base_units", "73", "account detail")

    def validate_account_history(payload: dict[str, Any]) -> None:
        history = require_list(payload.get("transactions"), "account history")
        if len(history) != 1 or not isinstance(history[0], dict):
            raise SmokeError("account history: expected one transaction")
        require_equal(history[0], "direction", "sent", "account history")

    def validate_mempool(payload: dict[str, Any]) -> None:
        require_equal(payload, "pending_count", 1, "mempool")
        require_equal(payload, "submit_status", "disabled", "mempool")
        require_equal(payload, "produce_block_status", "disabled", "mempool")
        entries = require_list(payload.get("entries"), "mempool entries")
        if len(entries) != 1 or not isinstance(entries[0], dict):
            raise SmokeError("mempool: expected one pending entry")
        require_equal(entries[0], "tx_hash", pending_tx_hash, "mempool entry")

    def validate_wallet_status(payload: dict[str, Any]) -> None:
        require_equal(payload, "pending_transactions", 1, "wallet status")
        capabilities = payload.get("capabilities")
        if not isinstance(capabilities, dict):
            raise SmokeError("wallet status: expected capabilities object")
        require_equal(capabilities, "draft", True, "wallet status capabilities")
        require_equal(capabilities, "submit", False, "wallet status capabilities")
        require_equal(capabilities, "send", False, "wallet status capabilities")

    def validate_wallet_accounts(payload: dict[str, Any]) -> None:
        require_list(payload.get("accounts"), "wallet accounts")
        if "private-devnet-preview-only-no-signing-no-submit" not in payload.get("warning", ""):
            raise SmokeError("wallet accounts: missing preview-only warning")

    def validate_wallet_balance(payload: dict[str, Any]) -> None:
        require_equal(payload, "address", ALICE, "wallet balance")
        require_equal(payload, "balance_base_units", "73", "wallet balance")

    def validate_confirmed_wallet_tx(payload: dict[str, Any]) -> None:
        require_equal(payload, "tx_hash", confirmed_tx_hash, "wallet confirmed tx")
        require_equal(payload, "status", "confirmed", "wallet confirmed tx")
        require_equal(payload, "block_height", 1, "wallet confirmed tx")

    def validate_pending_wallet_tx(payload: dict[str, Any]) -> None:
        require_equal(payload, "tx_hash", pending_tx_hash, "wallet pending tx")
        require_equal(payload, "status", "pending", "wallet pending tx")
        require_equal(payload, "block_height", None, "wallet pending tx")
        require_equal(payload, "transaction_index", None, "wallet pending tx")

    def validate_draft_preview(payload: dict[str, Any]) -> None:
        require_equal(payload, "mutation", "none", "draft preview")
        validation = payload.get("validation")
        balance = payload.get("balance")
        if not isinstance(validation, dict) or not isinstance(balance, dict):
            raise SmokeError("draft preview: expected validation and balance objects")
        require_equal(validation, "ok", True, "draft preview validation")
        require_equal(balance, "remaining_base_units", "66", "draft preview balance")

    def validate_draft_validation_failure(
        payload: dict[str, Any],
        context: str,
        expected_errors: list[str],
    ) -> None:
        require_equal(payload, "mutation", "none", context)
        validation = payload.get("validation")
        if not isinstance(validation, dict):
            raise SmokeError(f"{context}: expected validation object")
        require_equal(validation, "ok", False, context)
        errors = require_list(validation.get("errors"), context)
        joined_errors = "\n".join(str(error) for error in errors)
        for expected_error in expected_errors:
            if expected_error not in joined_errors:
                raise SmokeError(
                    f"{context}: missing expected error {expected_error!r} in {errors!r}"
                )

    def validate_combined_draft_failure(payload: dict[str, Any]) -> None:
        validate_draft_validation_failure(
            payload,
            "combined draft failure",
            [
                "sender and recipient must differ",
                "amount must be greater than zero",
                "fee must be at least 2 base units",
                "nonce must match sender nonce 1",
                "expiry must be greater than current height",
            ],
        )

    def validate_balance_draft_failure(payload: dict[str, Any]) -> None:
        validate_draft_validation_failure(
            payload,
            "balance draft failure",
            ["debit exceeds available balance"],
        )
        balance = payload.get("balance")
        if not isinstance(balance, dict):
            raise SmokeError("balance draft failure: expected balance object")
        require_equal(balance, "available_base_units", "73", "balance draft failure")
        require_equal(balance, "debit_base_units", "1002", "balance draft failure")
        require_equal(balance, "remaining_base_units", None, "balance draft failure")

    def validate_malformed_draft_request(payload: dict[str, Any]) -> None:
        error = payload.get("error")
        if not isinstance(error, dict):
            raise SmokeError("malformed draft request: expected error object")
        require_equal(error, "code", "bad_request", "malformed draft request")
        message = error.get("message")
        if not isinstance(message, str) or "invalid amount_base_units" not in message:
            raise SmokeError(
                "malformed draft request: expected invalid amount message, got "
                f"{message!r}"
            )

    def validate_node_status(payload: dict[str, Any]) -> None:
        require_equal(payload, "mode", "serve-readonly", "node status")
        require_equal(payload, "pending_transactions", 1, "node status")
        require_equal(payload, "wallet_submit_status", "disabled", "node status")
        require_equal(payload, "block_production_status", "disabled", "node status")

    def validate_indexer(payload: dict[str, Any]) -> None:
        require_equal(payload, "service", "xriq-indexer", "indexer status")
        require_equal(payload, "status", "current", "indexer status")
        require_equal(payload, "latest_indexed_height", 1, "indexer status")

    def validate_audit(payload: dict[str, Any]) -> None:
        events = require_list(payload.get("audit_events"), "audit events")
        if len(events) != 1 or not isinstance(events[0], dict):
            raise SmokeError("audit events: expected one event")
        require_equal(events[0], "actor", "xriq-indexer", "audit event")
        require_equal(events[0], "action", "index_block", "audit event")
        require_equal(events[0], "resource_type", "block", "audit event")

    def validate_snapshots(payload: dict[str, Any]) -> None:
        require_equal(
            payload,
            "warning",
            "private-devnet-read-only-snapshot-catalog-export-import-disabled",
            "snapshots",
        )
        snapshots = require_list(payload.get("snapshots"), "snapshots")
        if len(snapshots) != 1 or not isinstance(snapshots[0], dict):
            raise SmokeError("snapshots: expected one snapshot")
        require_equal(snapshots[0], "snapshot_name", "current-indexed-chain", "snapshots")
        require_equal(snapshots[0], "export_status", "disabled", "snapshots")
        require_equal(snapshots[0], "import_status", "disabled", "snapshots")

    def validate_snapshot_detail(payload: dict[str, Any]) -> None:
        require_equal(payload, "snapshot_name", "current-indexed-chain", "snapshot detail")
        require_equal(payload, "current_height", 1, "snapshot detail")
        require_equal(payload, "export_status", "disabled", "snapshot detail")
        require_equal(payload, "import_status", "disabled", "snapshot detail")

    def validate_iso_initiation(payload: dict[str, Any]) -> None:
        require_equal(payload, "not_certified", True, "iso initiation")
        require_equal(payload, "message_type", "payment_initiation_preview", "iso initiation")
        require_equal(payload, "source_tx_hash", confirmed_tx_hash, "iso initiation")

    def validate_iso_status(payload: dict[str, Any]) -> None:
        require_equal(payload, "not_certified", True, "iso status")
        require_equal(payload, "message_type", "payment_status_preview", "iso status")
        aligned = payload.get("iso20022_aligned")
        if not isinstance(aligned, dict):
            raise SmokeError("iso status: expected aligned object")
        require_equal(aligned, "transaction_status", "ACSC", "iso status")

    def validate_iso_statement(payload: dict[str, Any]) -> None:
        require_equal(payload, "not_certified", True, "iso statement")
        require_equal(payload, "message_type", "account_statement_preview", "iso statement")
        entries = require_list(payload.get("entries"), "iso statement entries")
        if len(entries) != 1 or not isinstance(entries[0], dict):
            raise SmokeError("iso statement: expected one statement entry")
        require_equal(entries[0], "direction", "debit", "iso statement")

    check("/api/v1/health", "health", validate_health)
    check("/api/v1/network", "network", validate_network)
    check("/api/v1/explorer/overview", "explorer-overview", validate_overview)
    check("/api/v1/blocks?limit=5", "blocks", validate_blocks)
    check("/api/v1/blocks/1", "block-detail", validate_block)
    check("/api/v1/transactions?limit=5", "transactions", validate_transactions)
    check(f"/api/v1/transactions/{confirmed_tx_hash}", "transaction-detail", validate_transaction)
    check("/api/v1/accounts?limit=5", "accounts", validate_accounts)
    check(f"/api/v1/accounts/{ALICE}", "account-detail", validate_account)
    check(
        f"/api/v1/accounts/{ALICE}/transactions?limit=5",
        "account-history",
        validate_account_history,
    )
    check("/api/v1/mempool?limit=5", "mempool", validate_mempool)
    check("/api/v1/wallet/status", "wallet-status", validate_wallet_status)
    check("/api/v1/wallet/accounts?limit=5", "wallet-accounts", validate_wallet_accounts)
    check(f"/api/v1/wallet/accounts/{ALICE}/balance", "wallet-balance", validate_wallet_balance)
    check(
        f"/api/v1/wallet/accounts/{ALICE}/history?limit=5",
        "wallet-history",
        validate_account_history,
    )
    check(
        f"/api/v1/wallet/transactions/{confirmed_tx_hash}/status",
        "wallet-confirmed-tx-status",
        validate_confirmed_wallet_tx,
    )
    check(
        f"/api/v1/wallet/transactions/{pending_tx_hash}/status",
        "wallet-pending-tx-status",
        validate_pending_wallet_tx,
    )
    check(
        f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}&to_address={CAROL}&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100",
        "wallet-draft-preview",
        validate_draft_preview,
    )
    check_status(
        f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}&to_address={ALICE}&amount_base_units=0&fee_base_units=1&nonce=0&expires_at_height=1",
        "wallet-draft-preview-combined-failure",
        200,
        validate_combined_draft_failure,
    )
    check_status(
        f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}&to_address={CAROL}&amount_base_units=1000&fee_base_units=2&nonce=1&expires_at_height=100",
        "wallet-draft-preview-balance-failure",
        200,
        validate_balance_draft_failure,
    )
    check_status(
        f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}&to_address={CAROL}&amount_base_units=abc&fee_base_units=2&nonce=1&expires_at_height=100",
        "wallet-draft-preview-malformed-request",
        400,
        validate_malformed_draft_request,
    )
    check("/api/v1/admin/node/status", "admin-node-status", validate_node_status)
    check("/api/v1/admin/indexer/status", "admin-indexer-status", validate_indexer)
    check("/api/v1/admin/audit-events?limit=5", "admin-audit-events", validate_audit)
    check("/api/v1/snapshots", "snapshots", validate_snapshots)
    check("/api/v1/snapshots/current-indexed-chain", "snapshot-detail", validate_snapshot_detail)
    check(
        f"/api/v1/iso20022/payment-initiation/preview?tx_hash={confirmed_tx_hash}",
        "iso-payment-initiation",
        validate_iso_initiation,
    )
    check(
        f"/api/v1/iso20022/transactions/{confirmed_tx_hash}/status",
        "iso-payment-status",
        validate_iso_status,
    )
    check(
        f"/api/v1/iso20022/accounts/{ALICE}/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z",
        "iso-account-statement",
        validate_iso_statement,
    )
    completed.append("product API route smoke")
    completed.append("wallet draft failure smoke")

    summary = {
        "ok": "xriq-phase1-1-local-e2e-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "indexer_artifacts": {
            "replay_json": str(indexer_dir / "replay.json"),
            "write_plan_sql": str(indexer_dir / "write-plan.sql"),
            "apply_postgres_dry_run": str(indexer_dir / "apply-postgres-dry-run.txt"),
            "verify_postgres_dry_run": str(indexer_dir / "verify-postgres-dry-run.txt"),
            "postgres_docker_live": (
                str(indexer_dir / "postgres-docker-live.json")
                if postgres_docker_live
                else None
            ),
            "postgres_api_read_model_status": (
                str(indexer_dir / "postgres-api-read-model-status.json")
                if postgres_docker_live
                else None
            ),
            "postgres_server_read_model_status": (
                str(indexer_dir / "postgres-server-read-model-status.json")
                if postgres_server_status
                else None
            ),
            "postgres_api_explorer_overview": (
                str(indexer_dir / "postgres-api-explorer-overview.json")
                if postgres_api_overview
                else None
            ),
            "postgres_server_explorer_overview": (
                str(indexer_dir / "postgres-server-explorer-overview.json")
                if postgres_server_overview
                else None
            ),
            "postgres_api_blocks": (
                str(indexer_dir / "postgres-api-blocks.json") if postgres_api_blocks else None
            ),
            "postgres_server_blocks": (
                str(indexer_dir / "postgres-server-blocks.json")
                if postgres_server_blocks
                else None
            ),
            "postgres_admin_ui_read_model_status": (
                str(indexer_dir / "postgres-admin-ui-read-model-status.json")
                if postgres_ui_status
                else None
            ),
        },
        "postgres_docker_live": postgres_docker_live,
        "confirmed_tx_hash": confirmed_tx_hash,
        "pending_tx_hash": pending_tx_hash,
        "routes_checked": routes_checked,
        "failure_routes_checked": failure_routes_checked,
        "completed": completed,
        "skipped": skipped,
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
