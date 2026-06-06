#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
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
FEES = "xriqdev1fees000000000000"
FORBIDDEN_WALLET_MUTATION_KEYS = {
    "tx_hash",
    "transaction_hash",
    "private_key",
    "seed_phrase",
    "mnemonic",
    "signature",
    "signed_transaction",
}


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


def find_forbidden_wallet_keys(payload: Any) -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_WALLET_MUTATION_KEYS:
                found.append(key)
            found.extend(find_forbidden_wallet_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(find_forbidden_wallet_keys(item))
    return found


def validate_local_refusal_audit_events(payload: dict[str, Any], context: str) -> None:
    require_equal(payload, "local_refusal_audit_count", 3, context)
    events = require_list(payload.get("local_refusal_audit_events"), context)
    if len(events) != 3 or not all(isinstance(event, dict) for event in events):
        raise SmokeError(f"{context}: expected three local refusal audit events")
    by_id = {str(event.get("event_id")): event for event in events}
    expected_events = {
        "wallet-transfer-submit:local_request_id": {
            "action": "wallet_transfer_submit_attempt",
            "resource_type": "wallet_transfer",
            "resource_id": "draft_id_or_local_request_id",
            "endpoint": "POST /api/v1/wallet/transfers/submit",
            "refusal_code": "wallet_submit_disabled",
            "explicit_flag": "--enable-local-wallet-submit",
        },
        "wallet-transfer-send:local_request_id": {
            "action": "wallet_transfer_send_attempt",
            "resource_type": "wallet_transfer",
            "resource_id": "local_request_id",
            "endpoint": "POST /api/v1/wallet/transfers/send",
            "refusal_code": "wallet_send_disabled",
            "explicit_flag": "--enable-local-wallet-send",
        },
        "block-production:local_request_id": {
            "action": "block_production_attempt",
            "resource_type": "block_production",
            "resource_id": "local_request_id",
            "endpoint": "POST /api/v1/blocks/produce",
            "refusal_code": "block_production_disabled",
            "explicit_flag": "--enable-local-block-production",
        },
    }
    for event_id, expected in expected_events.items():
        event = by_id.get(event_id)
        if not isinstance(event, dict):
            raise SmokeError(f"{context}: missing local refusal audit event {event_id}")
        require_equal(event, "actor", "local-private-devnet-operator", context)
        require_equal(event, "action", expected["action"], context)
        require_equal(event, "resource_type", expected["resource_type"], context)
        require_equal(event, "resource_id", expected["resource_id"], context)
        require_equal(event, "environment", "private-devnet", context)
        require_equal(event, "audit_scope", "api-local-refusal", context)
        require_equal(event, "recording", "api-local-response", context)
        require_equal(event, "outcome", "refused", context)
        require_equal(event, "status", "disabled", context)
        require_equal(event, "mutation", "none", context)
        metadata = event.get("metadata")
        if not isinstance(metadata, dict):
            raise SmokeError(f"{context}: expected metadata for {event_id}")
        require_equal(metadata, "endpoint", expected["endpoint"], context)
        require_equal(metadata, "refusal_code", expected["refusal_code"], context)
        require_equal(metadata, "explicit_flag", expected["explicit_flag"], context)
        require_equal(metadata, "local_request_id", "local_request_id", context)
        require_equal(metadata, "resource_id_policy", expected["resource_id"], context)
        metadata_policy = metadata.get("metadata_policy")
        if not isinstance(metadata_policy, str) or "request fields only" not in metadata_policy:
            raise SmokeError(f"{context}: expected request-fields-only local audit metadata")
    forbidden_keys = find_forbidden_wallet_keys(events)
    if forbidden_keys:
        raise SmokeError(f"{context}: forbidden local audit response keys {forbidden_keys}")


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


def assert_api_method_status(
    api_binary: Path,
    xriq_dir: Path,
    chain_file: Path,
    pending_file: Path,
    method: str,
    target: str,
    expected_status: int,
    artifact_path: Path,
    validate: Callable[[dict[str, Any]], None],
    *,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    command = [
        str(api_binary),
        "request",
        "--chain-file",
        str(chain_file),
        "--pending-file",
        str(pending_file),
        "--alice-balance",
        "100",
        "--method",
        method,
    ]
    if extra_args:
        command.extend(extra_args)
    command.extend(["--target", target])
    output = run_command(f"xriq-api {method} {target}", command, cwd=xriq_dir)
    status_code, reason, payload = parse_api_request_output(output, f"{method} {target}")
    if status_code != expected_status:
        raise SmokeError(
            f"{method} {target}: expected HTTP {expected_status}, got "
            f"{status_code} {reason}: {payload}"
        )
    if "environment" in payload:
        require_equal(payload, "environment", "private-devnet", f"{method} {target}")
    validate(payload)
    write_json(artifact_path, payload)
    return payload


def npm_command() -> str:
    return "npm.cmd" if sys.platform.startswith("win") else "npm"


def free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def http_json(
    base_url: str,
    target: str,
    *,
    expected_status: int = 200,
    method: str = "GET",
) -> dict[str, Any]:
    request_body = b"" if method == "POST" else None
    request = Request(base_url + target, data=request_body, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            status = response.status
            text = response.read().decode("utf-8")
    except HTTPError as exc:
        status = exc.code
        text = exc.read().decode("utf-8")
    except URLError as exc:
        raise SmokeError(f"{method} {target} failed: {exc}") from exc

    if status != expected_status:
        raise SmokeError(
            f"{method} {target}: expected HTTP {expected_status}, got {status}: {text}"
        )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SmokeError(
            f"{method} {target}: invalid JSON response: {exc}: {text}"
        ) from exc
    if not isinstance(payload, dict):
        raise SmokeError(f"{method} {target}: expected JSON object response")
    return payload


def start_api_readonly_server(
    api_binary: Path,
    xriq_dir: Path,
    artifact_dir: Path,
    *,
    chain_file: Path,
    pending_file: Path,
    bind: str,
    postgres_container: str | None = None,
    postgres_database: str | None = None,
    enable_local_wallet_submit: bool = False,
    enable_local_wallet_send: bool = False,
    enable_local_block_production: bool = False,
    stderr_log_name: str = "api-postgres-read-model-server.stderr.log",
) -> subprocess.Popen[str]:
    stderr_log = artifact_dir / stderr_log_name
    stderr_handle = stderr_log.open("w", encoding="utf-8")
    command = [
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
    ]
    if postgres_container is not None and postgres_database is not None:
        command.extend(
            [
                "--postgres-docker-container",
                postgres_container,
                "--postgres-database",
                postgres_database,
            ]
        )
    if enable_local_wallet_submit:
        command.extend(["--enable-local-wallet-submit", "true"])
    if enable_local_wallet_send:
        command.extend(["--enable-local-wallet-send", "true"])
    if enable_local_block_production:
        command.extend(["--enable-local-block-production", "true"])
    try:
        process = subprocess.Popen(
            command,
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


def require_pending_address(value: str, context: str) -> str:
    if not re.fullmatch(r"xriqdev1[a-z0-9]{16}", value):
        raise SmokeError(f"{context}: expected local devnet address, got {value!r}")
    return value


def require_decimal(value: str, context: str) -> str:
    if not re.fullmatch(r"[0-9]+", value):
        raise SmokeError(f"{context}: expected base-unit integer, got {value!r}")
    return value


def pending_mempool_sql_from_tsv(pending_file: Path) -> str:
    lines = [
        line.strip()
        for line in pending_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        return "DELETE FROM xriq_mempool_entries;\n"

    rows: list[str] = []
    for index, line in enumerate(lines, start=1):
        fields = line.split("\t")
        if len(fields) != 11:
            raise SmokeError(
                f"postgres pending mempool import line {index}: expected 11 TSV fields, "
                f"got {len(fields)}"
            )
        if fields[0] != "xriq-pending-transaction-v1":
            raise SmokeError(
                f"postgres pending mempool import line {index}: unsupported record version"
            )
        tx_hash = require_hash(fields[1], f"postgres pending mempool import line {index} tx_hash")
        require_decimal(fields[2], f"postgres pending mempool import line {index} version")
        if fields[3] != "xriq-devnet":
            raise SmokeError(
                f"postgres pending mempool import line {index}: expected chain xriq-devnet, "
                f"got {fields[3]!r}"
            )
        from_address = require_pending_address(
            fields[4], f"postgres pending mempool import line {index} from_address"
        )
        to_address = require_pending_address(
            fields[5], f"postgres pending mempool import line {index} to_address"
        )
        amount = require_decimal(
            fields[6], f"postgres pending mempool import line {index} amount_base_units"
        )
        fee = require_decimal(
            fields[7], f"postgres pending mempool import line {index} fee_base_units"
        )
        nonce = require_decimal(fields[8], f"postgres pending mempool import line {index} nonce")
        seen_at = f"1970-01-01T00:00:{min(index, 59):02d}Z"
        rows.append(
            "("
            f"{sql_literal(tx_hash)}, "
            f"{sql_literal(from_address)}, "
            f"{sql_literal(to_address)}, "
            f"{amount}, "
            f"{fee}, "
            f"{nonce}, "
            f"{sql_literal('pending')}, "
            f"{sql_literal(seen_at)}::timestamptz, "
            f"{sql_literal(seen_at)}::timestamptz"
            ")"
        )

    return (
        "DELETE FROM xriq_mempool_entries;\n"
        "INSERT INTO xriq_mempool_entries (\n"
        "    tx_hash, from_address, to_address, amount_base_units, fee_base_units,\n"
        "    nonce, status, first_seen_at, last_seen_at\n"
        ")\nVALUES\n"
        + ",\n".join(rows)
        + "\nON CONFLICT (tx_hash) DO UPDATE SET\n"
        "    from_address = EXCLUDED.from_address,\n"
        "    to_address = EXCLUDED.to_address,\n"
        "    amount_base_units = EXCLUDED.amount_base_units,\n"
        "    fee_base_units = EXCLUDED.fee_base_units,\n"
        "    nonce = EXCLUDED.nonce,\n"
        "    status = EXCLUDED.status,\n"
        "    first_seen_at = EXCLUDED.first_seen_at,\n"
        "    last_seen_at = EXCLUDED.last_seen_at;\n"
    )


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
    pending_file: Path,
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
    docker_psql(
        root,
        container,
        database,
        pending_mempool_sql_from_tsv(pending_file),
        "apply postgres pending mempool rows",
    )
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
        "mempool_entries": "1",
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
        "SELECT 'mempool_entries=' || count(*) FROM xriq_mempool_entries;\n"
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
        "INSERT INTO xriq_snapshots",
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
    postgres_api_node_status = None
    postgres_server_node_status = None
    postgres_api_indexer_status = None
    postgres_server_indexer_status = None
    postgres_api_overview = None
    postgres_server_overview = None
    postgres_api_blocks = None
    postgres_server_blocks = None
    postgres_api_block_detail = None
    postgres_server_block_detail = None
    postgres_api_transactions = None
    postgres_server_transactions = None
    postgres_api_mempool = None
    postgres_server_mempool = None
    postgres_api_wallet_status = None
    postgres_server_wallet_status = None
    postgres_api_wallet_draft_preview = None
    postgres_server_wallet_draft_preview = None
    postgres_api_transaction_detail = None
    postgres_server_transaction_detail = None
    postgres_api_wallet_transaction_status = None
    postgres_server_wallet_transaction_status = None
    postgres_api_iso_transaction_status = None
    postgres_server_iso_transaction_status = None
    postgres_api_iso_payment_initiation = None
    postgres_server_iso_payment_initiation = None
    postgres_api_iso_account_statement = None
    postgres_server_iso_account_statement = None
    postgres_api_wallet_pending_transaction_status = None
    postgres_server_wallet_pending_transaction_status = None
    postgres_api_accounts = None
    postgres_server_accounts = None
    postgres_api_wallet_accounts = None
    postgres_server_wallet_accounts = None
    postgres_api_account_detail = None
    postgres_server_account_detail = None
    postgres_api_wallet_balance = None
    postgres_server_wallet_balance = None
    postgres_api_account_history = None
    postgres_server_account_history = None
    postgres_api_wallet_account_history = None
    postgres_server_wallet_account_history = None
    postgres_api_audit_events = None
    postgres_server_audit_events = None
    postgres_api_snapshots = None
    postgres_server_snapshots = None
    postgres_api_snapshot_detail = None
    postgres_server_snapshot_detail = None
    postgres_ui_status = None
    if args.postgres_docker_live:
        postgres_docker_live = run_postgres_docker_live(
            root,
            xriq_dir,
            indexer_sql,
            indexer_dir,
            pending_file,
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

        def validate_postgres_node_status(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "environment", "private-devnet", context)
            require_equal(payload, "service", "xriq-api", context)
            require_equal(payload, "status", "healthy", context)
            require_equal(payload, "mode", "serve-readonly", context)
            require_equal(payload, "network", "xriq-devnet", context)
            require_equal(payload, "current_height", int(expected_counts["latest_height"]), context)
            require_hash(payload.get("latest_block_hash"), f"{context} latest block hash")
            require_hash(payload.get("state_root"), f"{context} state root")
            require_equal(payload, "stored_blocks", int(expected_counts["blocks"]), context)
            require_equal(
                payload,
                "pending_transactions",
                int(expected_counts["mempool_entries"]),
                context,
            )
            require_equal(payload, "wallet_submit_status", "disabled", context)
            require_equal(payload, "block_production_status", "disabled", context)

        postgres_node_status_output = run_command(
            "xriq-api postgres node status",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/admin/node/status",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_node_status = parse_api_request_output(
            postgres_node_status_output,
            "xriq-api postgres node status",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres node status: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_node_status}"
            )
        validate_postgres_node_status(
            postgres_api_node_status,
            "xriq-api postgres node status",
        )
        write_json(
            indexer_dir / "postgres-api-node-status.json",
            postgres_api_node_status,
        )
        completed.append("postgres-backed api node status")

        def validate_postgres_indexer_status(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "environment", "private-devnet", context)
            require_equal(payload, "service", "xriq-indexer", context)
            require_equal(payload, "status", "current", context)
            require_equal(
                payload,
                "latest_indexed_height",
                int(expected_counts["latest_height"]),
                context,
            )
            require_hash(payload.get("latest_indexed_block_hash"), f"{context} latest block hash")
            require_equal(payload, "lag_blocks", 0, context)
            last_run = payload.get("last_run")
            if not isinstance(last_run, dict):
                raise SmokeError(f"{context}: expected last_run object")
            run_id = last_run.get("run_id")
            if not isinstance(run_id, str) or not run_id.startswith("private-devnet-replay-"):
                raise SmokeError(f"{context}: expected replay run id, got {run_id!r}")
            require_equal(last_run, "status", "completed", context)
            require_equal(last_run, "from_height", int(expected_counts["latest_height"]), context)
            require_equal(last_run, "to_height", int(expected_counts["latest_height"]), context)
            require_equal(last_run, "blocks_indexed", int(expected_counts["blocks"]), context)
            require_equal(
                last_run,
                "transactions_indexed",
                int(expected_counts["transactions"]),
                context,
            )

        postgres_indexer_status_output = run_command(
            "xriq-api postgres indexer status",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/admin/indexer/status",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_indexer_status = parse_api_request_output(
            postgres_indexer_status_output,
            "xriq-api postgres indexer status",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres indexer status: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_indexer_status}"
            )
        validate_postgres_indexer_status(
            postgres_api_indexer_status,
            "xriq-api postgres indexer status",
        )
        write_json(
            indexer_dir / "postgres-api-indexer-status.json",
            postgres_api_indexer_status,
        )
        completed.append("postgres-backed api indexer status")

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
            require_equal(
                chain,
                "pending_transactions",
                int(expected_counts["mempool_entries"]),
                context,
            )
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

        def validate_postgres_block_detail(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "height", int(expected_counts["latest_height"]), context)
            require_hash(payload.get("block_hash"), f"{context} block hash")
            require_hash(payload.get("previous_block_hash"), f"{context} previous block hash")
            require_hash(payload.get("state_root"), f"{context} state root")
            require_hash(payload.get("transactions_root"), f"{context} transactions root")
            require_equal(payload, "transaction_count", 1, context)
            timestamp = payload.get("timestamp_utc")
            if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
                raise SmokeError(f"{context}: expected UTC timestamp, got {timestamp!r}")
            transactions = require_list(payload.get("transactions"), context)
            if len(transactions) != 1 or not isinstance(transactions[0], dict):
                raise SmokeError(f"{context}: expected exactly one transaction object")
            validate_postgres_transaction_fields(transactions[0], context)

        def validate_postgres_transaction_fields(
            transaction: dict[str, Any], context: str
        ) -> None:
            require_equal(transaction, "tx_hash", confirmed_tx_hash, context)
            require_equal(
                transaction,
                "block_height",
                int(expected_counts["latest_height"]),
                context,
            )
            require_hash(transaction.get("block_hash"), f"{context} block hash")
            require_equal(transaction, "transaction_index", 0, context)
            require_equal(transaction, "status", "confirmed", context)
            require_equal(transaction, "from_address", ALICE, context)
            require_equal(transaction, "to_address", BOB, context)
            require_equal(transaction, "amount_base_units", "25", context)
            require_equal(transaction, "fee_base_units", "2", context)
            require_equal(transaction, "nonce", 0, context)

        def validate_postgres_transactions(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "limit", 5, context)
            require_equal(payload, "next_cursor", None, context)
            transactions = require_list(payload.get("transactions"), context)
            if len(transactions) != 1 or not isinstance(transactions[0], dict):
                raise SmokeError(f"{context}: expected exactly one transaction object")
            validate_postgres_transaction_fields(transactions[0], context)

        def validate_postgres_mempool(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(
                payload,
                "warning",
                "private-devnet-read-only-mempool-status-submit-disabled",
                context,
            )
            require_equal(
                payload,
                "read_model_warning",
                "local-private-devnet-postgres-read-only-preview-no-mutation",
                context,
            )
            require_equal(payload, "current_height", int(expected_counts["latest_height"]), context)
            require_equal(payload, "pending_count", int(expected_counts["mempool_entries"]), context)
            require_equal(payload, "limit", 5, context)
            require_equal(payload, "next_cursor", None, context)
            require_equal(payload, "inspect_status", "enabled", context)
            require_equal(payload, "submit_status", "disabled", context)
            require_equal(payload, "produce_block_status", "disabled", context)
            entries = require_list(payload.get("entries"), context)
            if len(entries) != 1 or not isinstance(entries[0], dict):
                raise SmokeError(f"{context}: expected exactly one pending mempool entry")
            entry = entries[0]
            require_equal(entry, "tx_hash", pending_tx_hash, context)
            require_equal(entry, "from_address", ALICE, context)
            require_equal(entry, "to_address", CAROL, context)
            require_equal(entry, "amount_base_units", "5", context)
            require_equal(entry, "fee_base_units", "2", context)
            require_equal(entry, "nonce", 1, context)
            require_equal(entry, "status", "pending", context)
            for field in ("first_seen_at_utc", "last_seen_at_utc"):
                timestamp = entry.get(field)
                if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
                    raise SmokeError(f"{context}: expected UTC {field}, got {timestamp!r}")

        def validate_postgres_wallet_status(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "environment", "private-devnet", context)
            require_equal(payload, "network", "xriq-devnet", context)
            require_equal(
                payload,
                "warning",
                "private-devnet-preview-only-no-signing-no-submit",
                context,
            )
            require_equal(
                payload,
                "read_model_warning",
                "local-private-devnet-postgres-read-only-preview-no-mutation",
                context,
            )
            require_equal(payload, "current_height", int(expected_counts["latest_height"]), context)
            require_hash(payload.get("latest_block_hash"), f"{context} latest block hash")
            require_hash(payload.get("state_root"), f"{context} state root")
            require_equal(payload, "account_count", int(expected_counts["account_balances"]), context)
            require_equal(
                payload,
                "pending_transactions",
                int(expected_counts["mempool_entries"]),
                context,
            )
            capabilities = payload.get("capabilities")
            if not isinstance(capabilities, dict):
                raise SmokeError(f"{context}: expected capabilities object")
            require_equal(capabilities, "draft", True, context)
            require_equal(capabilities, "submit", False, context)
            require_equal(capabilities, "send", False, context)

        def validate_postgres_wallet_draft_preview(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "environment", "private-devnet", context)
            require_equal(payload, "network", "xriq-devnet", context)
            require_equal(
                payload,
                "warning",
                "private-devnet-preview-only-no-signing-no-submit",
                context,
            )
            require_equal(
                payload,
                "read_model_warning",
                "local-private-devnet-postgres-read-only-preview-no-mutation",
                context,
            )
            require_equal(payload, "mutation", "none", context)
            validation = payload.get("validation")
            if not isinstance(validation, dict):
                raise SmokeError(f"{context}: expected validation object")
            require_equal(validation, "ok", True, context)
            errors = require_list(validation.get("errors"), context)
            if errors:
                raise SmokeError(f"{context}: expected no validation errors, got {errors!r}")
            draft = payload.get("draft")
            if not isinstance(draft, dict):
                raise SmokeError(f"{context}: expected draft object")
            require_equal(draft, "chain_id", "xriq-devnet", context)
            require_equal(draft, "from_address", ALICE, context)
            require_equal(draft, "to_address", CAROL, context)
            require_equal(draft, "amount_base_units", "5", context)
            require_equal(draft, "fee_base_units", "2", context)
            require_equal(draft, "nonce", 1, context)
            require_equal(draft, "expires_at_height", 100, context)
            balance = payload.get("balance")
            if not isinstance(balance, dict):
                raise SmokeError(f"{context}: expected balance object")
            require_equal(balance, "available_base_units", "73", context)
            require_equal(balance, "debit_base_units", "7", context)
            require_equal(balance, "remaining_base_units", "66", context)

        def validate_postgres_transaction_detail(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            validate_postgres_transaction_fields(payload, context)

        def validate_postgres_wallet_transaction_status(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "tx_hash", confirmed_tx_hash, context)
            require_equal(payload, "status", "confirmed", context)
            require_equal(payload, "block_height", int(expected_counts["latest_height"]), context)
            require_hash(payload.get("block_hash"), f"{context} block hash")
            require_equal(payload, "transaction_index", 0, context)
            for field in (
                "from_address",
                "to_address",
                "amount_base_units",
                "fee_base_units",
                "nonce",
            ):
                if field in payload:
                    raise SmokeError(f"{context}: wallet transaction status must not expose {field}")

        def validate_postgres_iso_transaction_status(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "environment", "private-devnet", context)
            require_equal(payload, "not_certified", True, context)
            require_equal(payload, "mapping_version", "xriq-iso20022-preview-v1", context)
            require_equal(payload, "message_type", "payment_status_preview", context)
            message_id = payload.get("message_id")
            if not isinstance(message_id, str) or not message_id.startswith("iso-status-"):
                raise SmokeError(f"{context}: expected iso status message_id, got {message_id!r}")
            require_equal(payload, "source_tx_hash", confirmed_tx_hash, context)
            require_equal(payload, "xriq_status", "confirmed", context)
            require_equal(
                payload,
                "read_model_warning",
                "local-private-devnet-postgres-read-only-preview-no-mutation",
                context,
            )
            aligned = payload.get("iso20022_aligned")
            if not isinstance(aligned, dict):
                raise SmokeError(f"{context}: expected iso20022_aligned object")
            require_equal(aligned, "original_end_to_end_id", confirmed_tx_hash, context)
            require_equal(aligned, "transaction_status", "ACSC", context)
            require_equal(
                aligned,
                "status_reason",
                "accepted_settlement_completed_on_private_devnet",
                context,
            )
            require_equal(
                aligned,
                "confirmed_block_height",
                int(expected_counts["latest_height"]),
                context,
            )
            unsupported = require_list(payload.get("unsupported_fields"), context)
            for field in ("interbank_settlement_date", "clearing_system_reference"):
                if field not in unsupported:
                    raise SmokeError(f"{context}: missing unsupported field {field!r}")

        def validate_postgres_iso_payment_initiation(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "environment", "private-devnet", context)
            require_equal(payload, "not_certified", True, context)
            require_equal(payload, "mapping_version", "xriq-iso20022-preview-v1", context)
            require_equal(payload, "message_type", "payment_initiation_preview", context)
            message_id = payload.get("message_id")
            if not isinstance(message_id, str) or not message_id.startswith("iso-preview-"):
                raise SmokeError(f"{context}: expected iso preview message_id, got {message_id!r}")
            require_equal(payload, "source_tx_hash", confirmed_tx_hash, context)
            require_equal(
                payload,
                "read_model_warning",
                "local-private-devnet-postgres-read-only-preview-no-mutation",
                context,
            )
            xriq = payload.get("xriq")
            if not isinstance(xriq, dict):
                raise SmokeError(f"{context}: expected xriq transfer object")
            require_equal(xriq, "from_address", ALICE, context)
            require_equal(xriq, "to_address", BOB, context)
            require_equal(xriq, "amount_base_units", "25", context)
            require_equal(xriq, "fee_base_units", "2", context)
            require_equal(xriq, "nonce", 0, context)
            aligned = payload.get("iso20022_aligned")
            if not isinstance(aligned, dict):
                raise SmokeError(f"{context}: expected iso20022_aligned object")
            require_equal(aligned, "creditor_account", BOB, context)
            require_equal(aligned, "debtor_account", ALICE, context)
            require_equal(aligned, "instructed_amount", "25", context)
            require_equal(aligned, "currency", "XRIQ-DEV", context)
            require_equal(aligned, "end_to_end_id", confirmed_tx_hash, context)
            unsupported = require_list(payload.get("unsupported_fields"), context)
            for field in (
                "bank_bic",
                "iban",
                "clearing_system_member_id",
                "legal_entity_identifier",
            ):
                if field not in unsupported:
                    raise SmokeError(f"{context}: missing unsupported field {field!r}")

        def validate_postgres_iso_account_statement(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "environment", "private-devnet", context)
            require_equal(payload, "not_certified", True, context)
            require_equal(payload, "mapping_version", "xriq-iso20022-preview-v1", context)
            require_equal(payload, "message_type", "account_statement_preview", context)
            require_equal(payload, "message_id", "iso-statement-alice-0001", context)
            require_equal(payload, "account_address", ALICE, context)
            require_equal(payload, "from", "1970-01-01T00:00:00Z", context)
            require_equal(payload, "to", "1970-01-01T00:00:02Z", context)
            require_equal(payload, "opening_balance_base_units", "100", context)
            require_equal(payload, "closing_balance_base_units", "73", context)
            require_equal(
                payload,
                "read_model_warning",
                "local-private-devnet-postgres-read-only-preview-no-mutation",
                context,
            )
            entries = require_list(payload.get("entries"), context)
            if len(entries) != 1 or not isinstance(entries[0], dict):
                raise SmokeError(f"{context}: expected one statement entry")
            require_equal(entries[0], "tx_hash", confirmed_tx_hash, context)
            require_equal(entries[0], "direction", "debit", context)
            require_equal(entries[0], "amount_base_units", "25", context)
            require_equal(entries[0], "fee_base_units", "2", context)
            require_equal(entries[0], "status", "confirmed", context)
            require_equal(entries[0], "block_height", int(expected_counts["latest_height"]), context)
            unsupported = require_list(payload.get("unsupported_fields"), context)
            for field in ("bank_account_servicer", "booking_date_from_bank", "fiat_currency"):
                if field not in unsupported:
                    raise SmokeError(f"{context}: missing unsupported field {field!r}")

        def validate_postgres_pending_wallet_transaction_status(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "tx_hash", pending_tx_hash, context)
            require_equal(payload, "status", "pending", context)
            require_equal(payload, "block_height", None, context)
            require_equal(payload, "block_hash", None, context)
            require_equal(payload, "transaction_index", None, context)
            for field in (
                "from_address",
                "to_address",
                "amount_base_units",
                "fee_base_units",
                "nonce",
            ):
                if field in payload:
                    raise SmokeError(f"{context}: wallet transaction status must not expose {field}")

        def validate_postgres_accounts(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "limit", 5, context)
            require_equal(payload, "next_cursor", None, context)
            accounts = require_list(payload.get("accounts"), context)
            if len(accounts) != int(expected_counts["account_balances"]):
                raise SmokeError(
                    f"{context}: expected {expected_counts['account_balances']} accounts, "
                    f"got {len(accounts)}"
                )
            by_address = {row.get("address"): row for row in accounts if isinstance(row, dict)}
            expected_balances = {
                ALICE: "73",
                BOB: "25",
                FEES: "2",
            }
            for address, balance in expected_balances.items():
                account = by_address.get(address)
                if not isinstance(account, dict):
                    raise SmokeError(f"{context}: missing account {address}")
                require_equal(account, "balance_base_units", balance, context)
                require_equal(account, "height", int(expected_counts["latest_height"]), context)
                require_hash(account.get("state_root"), f"{context} {address} state root")
                first_seen = account.get("first_seen_height")
                last_seen = account.get("last_seen_height")
                if not (
                    isinstance(first_seen, int) or first_seen is None
                ) or not (isinstance(last_seen, int) or last_seen is None):
                    raise SmokeError(
                        f"{context}: expected integer or null first/last seen heights for {address}"
                    )

        def validate_postgres_account_detail(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "address", ALICE, context)
            require_equal(payload, "balance_base_units", "73", context)
            require_equal(payload, "nonce", 1, context)
            require_equal(payload, "height", int(expected_counts["latest_height"]), context)
            require_hash(payload.get("state_root"), f"{context} state root")
            first_seen = payload.get("first_seen_height")
            last_seen = payload.get("last_seen_height")
            if not isinstance(first_seen, int) or not isinstance(last_seen, int):
                raise SmokeError(
                    f"{context}: expected integer first/last seen heights for {ALICE}"
                )

        def validate_postgres_wallet_balance(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "address", ALICE, context)
            require_equal(payload, "balance_base_units", "73", context)
            require_equal(payload, "nonce", 1, context)
            require_equal(payload, "height", int(expected_counts["latest_height"]), context)
            require_hash(payload.get("state_root"), f"{context} state root")
            if "first_seen_height" in payload or "last_seen_height" in payload:
                raise SmokeError(f"{context}: wallet balance must not expose first/last seen fields")

        def validate_postgres_account_history(
            payload: dict[str, Any], context: str
        ) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "address", ALICE, context)
            require_equal(payload, "limit", 5, context)
            require_equal(payload, "next_cursor", None, context)
            transactions = require_list(payload.get("transactions"), context)
            if len(transactions) != 1 or not isinstance(transactions[0], dict):
                raise SmokeError(f"{context}: expected exactly one account transaction")
            transaction = transactions[0]
            require_equal(transaction, "address", ALICE, context)
            require_equal(transaction, "tx_hash", confirmed_tx_hash, context)
            require_equal(transaction, "direction", "sent", context)
            require_equal(transaction, "block_height", int(expected_counts["latest_height"]), context)
            require_equal(transaction, "transaction_index", 0, context)
            require_equal(transaction, "amount_base_units", "25", context)
            require_equal(transaction, "fee_base_units", "2", context)

        def validate_postgres_audit_events(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(payload, "limit", 5, context)
            require_equal(payload, "next_cursor", None, context)
            events = require_list(payload.get("audit_events"), context)
            if len(events) != 1 or not isinstance(events[0], dict):
                raise SmokeError(f"{context}: expected exactly one audit event")
            event = events[0]
            event_id = event.get("event_id")
            if not isinstance(event_id, str) or not event_id.startswith("index-block:1:"):
                raise SmokeError(f"{context}: expected index-block audit id, got {event_id!r}")
            require_equal(event, "actor", "xriq-indexer", context)
            require_equal(event, "action", "index_block", context)
            require_equal(event, "resource_type", "block", context)
            require_hash(event.get("resource_id"), f"{context} resource id")
            require_equal(event, "environment", "private-devnet", context)
            validate_local_refusal_audit_events(payload, context)

        def validate_postgres_snapshot_fields(
            snapshot: dict[str, Any], context: str
        ) -> None:
            require_equal(snapshot, "snapshot_name", "current-indexed-chain", context)
            require_equal(
                snapshot,
                "snapshot_dir",
                "read-model://current-indexed-chain",
                context,
            )
            require_equal(
                snapshot,
                "current_height",
                int(expected_counts["latest_height"]),
                context,
            )
            require_hash(snapshot.get("latest_block_hash"), f"{context} latest block hash")
            require_hash(snapshot.get("state_root"), f"{context} state root")
            require_equal(snapshot, "block_count", int(expected_counts["blocks"]), context)
            require_equal(
                snapshot,
                "transaction_count",
                int(expected_counts["transactions"]),
                context,
            )
            require_equal(
                snapshot,
                "audit_event_count",
                int(expected_counts["audit_events"]),
                context,
            )
            require_equal(snapshot, "export_status", "disabled", context)
            require_equal(snapshot, "import_status", "disabled", context)

        def validate_postgres_snapshot_metadata(payload: dict[str, Any], context: str) -> None:
            require_equal(payload, "source", "postgres-read-model", context)
            require_equal(payload, "read_only", True, context)
            require_equal(
                payload,
                "warning",
                "private-devnet-read-only-snapshot-catalog-export-import-disabled",
                context,
            )
            require_equal(
                payload,
                "read_model_warning",
                "local-private-devnet-postgres-read-only-preview-no-mutation",
                context,
            )

        def validate_postgres_snapshots(payload: dict[str, Any], context: str) -> None:
            validate_postgres_snapshot_metadata(payload, context)
            require_equal(payload, "limit", 5, context)
            require_equal(payload, "next_cursor", None, context)
            snapshots = require_list(payload.get("snapshots"), context)
            if len(snapshots) != 1 or not isinstance(snapshots[0], dict):
                raise SmokeError(f"{context}: expected exactly one snapshot")
            validate_postgres_snapshot_fields(snapshots[0], context)

        def validate_postgres_snapshot_detail(payload: dict[str, Any], context: str) -> None:
            validate_postgres_snapshot_metadata(payload, context)
            validate_postgres_snapshot_fields(payload, context)

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

        postgres_block_detail_output = run_command(
            "xriq-api postgres block detail",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/blocks/1",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_block_detail = parse_api_request_output(
            postgres_block_detail_output,
            "xriq-api postgres block detail",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres block detail: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_block_detail}"
            )
        validate_postgres_block_detail(
            postgres_api_block_detail,
            "xriq-api postgres block detail",
        )
        write_json(
            indexer_dir / "postgres-api-block-detail.json",
            postgres_api_block_detail,
        )
        completed.append("postgres-backed api block detail")

        postgres_transactions_output = run_command(
            "xriq-api postgres transactions",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/transactions?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_transactions = parse_api_request_output(
            postgres_transactions_output,
            "xriq-api postgres transactions",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres transactions: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_transactions}"
            )
        validate_postgres_transactions(
            postgres_api_transactions,
            "xriq-api postgres transactions",
        )
        write_json(
            indexer_dir / "postgres-api-transactions.json",
            postgres_api_transactions,
        )
        completed.append("postgres-backed api transactions")

        postgres_mempool_output = run_command(
            "xriq-api postgres mempool",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/mempool?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_mempool = parse_api_request_output(
            postgres_mempool_output,
            "xriq-api postgres mempool",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres mempool: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_mempool}"
            )
        validate_postgres_mempool(
            postgres_api_mempool,
            "xriq-api postgres mempool",
        )
        write_json(
            indexer_dir / "postgres-api-mempool.json",
            postgres_api_mempool,
        )
        completed.append("postgres-backed api mempool")

        postgres_wallet_status_output = run_command(
            "xriq-api postgres wallet status",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/wallet/status",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_wallet_status = parse_api_request_output(
            postgres_wallet_status_output,
            "xriq-api postgres wallet status",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres wallet status: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_wallet_status}"
            )
        validate_postgres_wallet_status(
            postgres_api_wallet_status,
            "xriq-api postgres wallet status",
        )
        write_json(
            indexer_dir / "postgres-api-wallet-status.json",
            postgres_api_wallet_status,
        )
        completed.append("postgres-backed api wallet status")

        wallet_draft_preview_target = (
            f"/api/v1/wallet/transfers/draft-preview?from_address={ALICE}"
            f"&to_address={CAROL}&amount_base_units=5&fee_base_units=2"
            "&nonce=1&expires_at_height=100"
        )
        postgres_wallet_draft_preview_output = run_command(
            "xriq-api postgres wallet draft preview",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                wallet_draft_preview_target,
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_wallet_draft_preview = parse_api_request_output(
            postgres_wallet_draft_preview_output,
            "xriq-api postgres wallet draft preview",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres wallet draft preview: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_wallet_draft_preview}"
            )
        validate_postgres_wallet_draft_preview(
            postgres_api_wallet_draft_preview,
            "xriq-api postgres wallet draft preview",
        )
        write_json(
            indexer_dir / "postgres-api-wallet-draft-preview.json",
            postgres_api_wallet_draft_preview,
        )
        completed.append("postgres-backed api wallet draft preview")

        postgres_transaction_detail_output = run_command(
            "xriq-api postgres transaction detail",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/transactions/{confirmed_tx_hash}",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_transaction_detail = parse_api_request_output(
            postgres_transaction_detail_output,
            "xriq-api postgres transaction detail",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres transaction detail: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_transaction_detail}"
            )
        validate_postgres_transaction_detail(
            postgres_api_transaction_detail,
            "xriq-api postgres transaction detail",
        )
        write_json(
            indexer_dir / "postgres-api-transaction-detail.json",
            postgres_api_transaction_detail,
        )
        completed.append("postgres-backed api transaction detail")

        postgres_wallet_transaction_status_output = run_command(
            "xriq-api postgres wallet transaction status",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/wallet/transactions/{confirmed_tx_hash}/status",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_wallet_transaction_status = parse_api_request_output(
            postgres_wallet_transaction_status_output,
            "xriq-api postgres wallet transaction status",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres wallet transaction status: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_wallet_transaction_status}"
            )
        validate_postgres_wallet_transaction_status(
            postgres_api_wallet_transaction_status,
            "xriq-api postgres wallet transaction status",
        )
        write_json(
            indexer_dir / "postgres-api-wallet-transaction-status.json",
            postgres_api_wallet_transaction_status,
        )
        completed.append("postgres-backed api wallet transaction status")

        postgres_iso_transaction_status_output = run_command(
            "xriq-api postgres iso20022 transaction status",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/iso20022/transactions/{confirmed_tx_hash}/status",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_iso_transaction_status = parse_api_request_output(
            postgres_iso_transaction_status_output,
            "xriq-api postgres iso20022 transaction status",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres iso20022 transaction status: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_iso_transaction_status}"
            )
        validate_postgres_iso_transaction_status(
            postgres_api_iso_transaction_status,
            "xriq-api postgres iso20022 transaction status",
        )
        write_json(
            indexer_dir / "postgres-api-iso-transaction-status.json",
            postgres_api_iso_transaction_status,
        )
        completed.append("postgres-backed api iso20022 transaction status")

        postgres_iso_payment_initiation_output = run_command(
            "xriq-api postgres iso20022 payment initiation",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/iso20022/payment-initiation/preview?tx_hash={confirmed_tx_hash}",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_iso_payment_initiation = parse_api_request_output(
            postgres_iso_payment_initiation_output,
            "xriq-api postgres iso20022 payment initiation",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres iso20022 payment initiation: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_iso_payment_initiation}"
            )
        validate_postgres_iso_payment_initiation(
            postgres_api_iso_payment_initiation,
            "xriq-api postgres iso20022 payment initiation",
        )
        write_json(
            indexer_dir / "postgres-api-iso-payment-initiation.json",
            postgres_api_iso_payment_initiation,
        )
        completed.append("postgres-backed api iso20022 payment initiation")

        postgres_iso_account_statement_output = run_command(
            "xriq-api postgres iso20022 account statement",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/iso20022/accounts/{ALICE}/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_iso_account_statement = parse_api_request_output(
            postgres_iso_account_statement_output,
            "xriq-api postgres iso20022 account statement",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres iso20022 account statement: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_iso_account_statement}"
            )
        validate_postgres_iso_account_statement(
            postgres_api_iso_account_statement,
            "xriq-api postgres iso20022 account statement",
        )
        write_json(
            indexer_dir / "postgres-api-iso-account-statement.json",
            postgres_api_iso_account_statement,
        )
        completed.append("postgres-backed api iso20022 account statement")

        postgres_wallet_pending_transaction_status_output = run_command(
            "xriq-api postgres pending wallet transaction status",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/wallet/transactions/{pending_tx_hash}/status",
            ],
            cwd=xriq_dir,
        )
        (
            status_code,
            reason,
            postgres_api_wallet_pending_transaction_status,
        ) = parse_api_request_output(
            postgres_wallet_pending_transaction_status_output,
            "xriq-api postgres pending wallet transaction status",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres pending wallet transaction status: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_wallet_pending_transaction_status}"
            )
        validate_postgres_pending_wallet_transaction_status(
            postgres_api_wallet_pending_transaction_status,
            "xriq-api postgres pending wallet transaction status",
        )
        write_json(
            indexer_dir / "postgres-api-wallet-pending-transaction-status.json",
            postgres_api_wallet_pending_transaction_status,
        )
        completed.append("postgres-backed api pending wallet transaction status")

        postgres_accounts_output = run_command(
            "xriq-api postgres accounts",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/accounts?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_accounts = parse_api_request_output(
            postgres_accounts_output,
            "xriq-api postgres accounts",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres accounts: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_accounts}"
            )
        validate_postgres_accounts(
            postgres_api_accounts,
            "xriq-api postgres accounts",
        )
        write_json(indexer_dir / "postgres-api-accounts.json", postgres_api_accounts)
        completed.append("postgres-backed api accounts")

        postgres_wallet_accounts_output = run_command(
            "xriq-api postgres wallet accounts",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/wallet/accounts?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_wallet_accounts = parse_api_request_output(
            postgres_wallet_accounts_output,
            "xriq-api postgres wallet accounts",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres wallet accounts: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_wallet_accounts}"
            )
        validate_postgres_accounts(
            postgres_api_wallet_accounts,
            "xriq-api postgres wallet accounts",
        )
        write_json(
            indexer_dir / "postgres-api-wallet-accounts.json",
            postgres_api_wallet_accounts,
        )
        completed.append("postgres-backed api wallet accounts")

        postgres_account_detail_output = run_command(
            "xriq-api postgres account detail",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/accounts/{ALICE}",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_account_detail = parse_api_request_output(
            postgres_account_detail_output,
            "xriq-api postgres account detail",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres account detail: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_account_detail}"
            )
        validate_postgres_account_detail(
            postgres_api_account_detail,
            "xriq-api postgres account detail",
        )
        write_json(
            indexer_dir / "postgres-api-account-detail.json",
            postgres_api_account_detail,
        )
        completed.append("postgres-backed api account detail")

        postgres_wallet_balance_output = run_command(
            "xriq-api postgres wallet balance",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/wallet/accounts/{ALICE}/balance",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_wallet_balance = parse_api_request_output(
            postgres_wallet_balance_output,
            "xriq-api postgres wallet balance",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres wallet balance: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_wallet_balance}"
            )
        validate_postgres_wallet_balance(
            postgres_api_wallet_balance,
            "xriq-api postgres wallet balance",
        )
        write_json(
            indexer_dir / "postgres-api-wallet-balance.json",
            postgres_api_wallet_balance,
        )
        completed.append("postgres-backed api wallet balance")

        postgres_account_history_output = run_command(
            "xriq-api postgres account history",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/accounts/{ALICE}/transactions?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_account_history = parse_api_request_output(
            postgres_account_history_output,
            "xriq-api postgres account history",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres account history: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_account_history}"
            )
        validate_postgres_account_history(
            postgres_api_account_history,
            "xriq-api postgres account history",
        )
        write_json(
            indexer_dir / "postgres-api-account-history.json",
            postgres_api_account_history,
        )
        completed.append("postgres-backed api account history")

        postgres_wallet_account_history_output = run_command(
            "xriq-api postgres wallet account history",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                f"/api/v1/wallet/accounts/{ALICE}/history?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_wallet_account_history = parse_api_request_output(
            postgres_wallet_account_history_output,
            "xriq-api postgres wallet account history",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres wallet account history: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_wallet_account_history}"
            )
        validate_postgres_account_history(
            postgres_api_wallet_account_history,
            "xriq-api postgres wallet account history",
        )
        write_json(
            indexer_dir / "postgres-api-wallet-account-history.json",
            postgres_api_wallet_account_history,
        )
        completed.append("postgres-backed api wallet account history")

        postgres_audit_events_output = run_command(
            "xriq-api postgres audit events",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/admin/audit-events?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_audit_events = parse_api_request_output(
            postgres_audit_events_output,
            "xriq-api postgres audit events",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres audit events: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_audit_events}"
            )
        validate_postgres_audit_events(
            postgres_api_audit_events,
            "xriq-api postgres audit events",
        )
        write_json(
            indexer_dir / "postgres-api-audit-events.json",
            postgres_api_audit_events,
        )
        completed.append("postgres-backed api audit events")

        postgres_snapshots_output = run_command(
            "xriq-api postgres snapshots",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/snapshots?limit=5",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_snapshots = parse_api_request_output(
            postgres_snapshots_output,
            "xriq-api postgres snapshots",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres snapshots: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_snapshots}"
            )
        validate_postgres_snapshots(
            postgres_api_snapshots,
            "xriq-api postgres snapshots",
        )
        write_json(
            indexer_dir / "postgres-api-snapshots.json",
            postgres_api_snapshots,
        )
        completed.append("postgres-backed api snapshots")

        postgres_snapshot_detail_output = run_command(
            "xriq-api postgres snapshot detail",
            [
                str(api_binary),
                "request-postgres",
                "--docker-container",
                args.postgres_docker_container,
                "--database",
                args.postgres_docker_database,
                "--target",
                "/api/v1/snapshots/current-indexed-chain",
            ],
            cwd=xriq_dir,
        )
        status_code, reason, postgres_api_snapshot_detail = parse_api_request_output(
            postgres_snapshot_detail_output,
            "xriq-api postgres snapshot detail",
        )
        if status_code != 200:
            raise SmokeError(
                "xriq-api postgres snapshot detail: expected HTTP 200, "
                f"got {status_code} {reason}: {postgres_api_snapshot_detail}"
            )
        validate_postgres_snapshot_detail(
            postgres_api_snapshot_detail,
            "xriq-api postgres snapshot detail",
        )
        write_json(
            indexer_dir / "postgres-api-snapshot-detail.json",
            postgres_api_snapshot_detail,
        )
        completed.append("postgres-backed api snapshot detail")

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
            postgres_server_node_status = http_json(
                server_base_url, "/api/v1/admin/node/status"
            )
            postgres_server_indexer_status = http_json(
                server_base_url, "/api/v1/admin/indexer/status"
            )
            postgres_server_overview = http_json(server_base_url, "/api/v1/explorer/overview")
            postgres_server_blocks = http_json(server_base_url, "/api/v1/blocks?limit=5")
            postgres_server_block_detail = http_json(server_base_url, "/api/v1/blocks/1")
            postgres_server_transactions = http_json(
                server_base_url, "/api/v1/transactions?limit=5"
            )
            postgres_server_mempool = http_json(server_base_url, "/api/v1/mempool?limit=5")
            postgres_server_wallet_status = http_json(server_base_url, "/api/v1/wallet/status")
            postgres_server_wallet_draft_preview = http_json(
                server_base_url, wallet_draft_preview_target
            )
            postgres_server_transaction_detail = http_json(
                server_base_url, f"/api/v1/transactions/{confirmed_tx_hash}"
            )
            postgres_server_wallet_transaction_status = http_json(
                server_base_url, f"/api/v1/wallet/transactions/{confirmed_tx_hash}/status"
            )
            postgres_server_iso_transaction_status = http_json(
                server_base_url, f"/api/v1/iso20022/transactions/{confirmed_tx_hash}/status"
            )
            postgres_server_iso_payment_initiation = http_json(
                server_base_url,
                f"/api/v1/iso20022/payment-initiation/preview?tx_hash={confirmed_tx_hash}",
            )
            postgres_server_iso_account_statement = http_json(
                server_base_url,
                f"/api/v1/iso20022/accounts/{ALICE}/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z",
            )
            postgres_server_wallet_pending_transaction_status = http_json(
                server_base_url, f"/api/v1/wallet/transactions/{pending_tx_hash}/status"
            )
            postgres_server_accounts = http_json(server_base_url, "/api/v1/accounts?limit=5")
            postgres_server_wallet_accounts = http_json(
                server_base_url, "/api/v1/wallet/accounts?limit=5"
            )
            postgres_server_account_detail = http_json(server_base_url, f"/api/v1/accounts/{ALICE}")
            postgres_server_wallet_balance = http_json(
                server_base_url, f"/api/v1/wallet/accounts/{ALICE}/balance"
            )
            postgres_server_account_history = http_json(
                server_base_url, f"/api/v1/accounts/{ALICE}/transactions?limit=5"
            )
            postgres_server_wallet_account_history = http_json(
                server_base_url, f"/api/v1/wallet/accounts/{ALICE}/history?limit=5"
            )
            postgres_server_audit_events = http_json(
                server_base_url, "/api/v1/admin/audit-events?limit=5"
            )
            postgres_server_snapshots = http_json(server_base_url, "/api/v1/snapshots?limit=5")
            postgres_server_snapshot_detail = http_json(
                server_base_url, "/api/v1/snapshots/current-indexed-chain"
            )
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
        validate_postgres_node_status(
            postgres_server_node_status,
            "xriq-api serve-readonly postgres node status",
        )
        validate_postgres_indexer_status(
            postgres_server_indexer_status,
            "xriq-api serve-readonly postgres indexer status",
        )
        validate_postgres_blocks(
            postgres_server_blocks,
            "xriq-api serve-readonly postgres blocks",
        )
        validate_postgres_block_detail(
            postgres_server_block_detail,
            "xriq-api serve-readonly postgres block detail",
        )
        validate_postgres_transactions(
            postgres_server_transactions,
            "xriq-api serve-readonly postgres transactions",
        )
        validate_postgres_mempool(
            postgres_server_mempool,
            "xriq-api serve-readonly postgres mempool",
        )
        validate_postgres_wallet_status(
            postgres_server_wallet_status,
            "xriq-api serve-readonly postgres wallet status",
        )
        validate_postgres_wallet_draft_preview(
            postgres_server_wallet_draft_preview,
            "xriq-api serve-readonly postgres wallet draft preview",
        )
        validate_postgres_transaction_detail(
            postgres_server_transaction_detail,
            "xriq-api serve-readonly postgres transaction detail",
        )
        validate_postgres_wallet_transaction_status(
            postgres_server_wallet_transaction_status,
            "xriq-api serve-readonly postgres wallet transaction status",
        )
        validate_postgres_iso_transaction_status(
            postgres_server_iso_transaction_status,
            "xriq-api serve-readonly postgres iso20022 transaction status",
        )
        validate_postgres_iso_payment_initiation(
            postgres_server_iso_payment_initiation,
            "xriq-api serve-readonly postgres iso20022 payment initiation",
        )
        validate_postgres_iso_account_statement(
            postgres_server_iso_account_statement,
            "xriq-api serve-readonly postgres iso20022 account statement",
        )
        validate_postgres_pending_wallet_transaction_status(
            postgres_server_wallet_pending_transaction_status,
            "xriq-api serve-readonly postgres pending wallet transaction status",
        )
        validate_postgres_accounts(
            postgres_server_accounts,
            "xriq-api serve-readonly postgres accounts",
        )
        validate_postgres_accounts(
            postgres_server_wallet_accounts,
            "xriq-api serve-readonly postgres wallet accounts",
        )
        validate_postgres_account_detail(
            postgres_server_account_detail,
            "xriq-api serve-readonly postgres account detail",
        )
        validate_postgres_wallet_balance(
            postgres_server_wallet_balance,
            "xriq-api serve-readonly postgres wallet balance",
        )
        validate_postgres_account_history(
            postgres_server_account_history,
            "xriq-api serve-readonly postgres account history",
        )
        validate_postgres_account_history(
            postgres_server_wallet_account_history,
            "xriq-api serve-readonly postgres wallet account history",
        )
        validate_postgres_audit_events(
            postgres_server_audit_events,
            "xriq-api serve-readonly postgres audit events",
        )
        validate_postgres_snapshots(
            postgres_server_snapshots,
            "xriq-api serve-readonly postgres snapshots",
        )
        validate_postgres_snapshot_detail(
            postgres_server_snapshot_detail,
            "xriq-api serve-readonly postgres snapshot detail",
        )
        write_json(
            indexer_dir / "postgres-server-read-model-status.json", postgres_server_status
        )
        write_json(
            indexer_dir / "postgres-server-node-status.json",
            postgres_server_node_status,
        )
        write_json(
            indexer_dir / "postgres-server-indexer-status.json",
            postgres_server_indexer_status,
        )
        write_json(
            indexer_dir / "postgres-server-explorer-overview.json", postgres_server_overview
        )
        write_json(indexer_dir / "postgres-server-blocks.json", postgres_server_blocks)
        write_json(
            indexer_dir / "postgres-server-block-detail.json",
            postgres_server_block_detail,
        )
        write_json(
            indexer_dir / "postgres-server-transactions.json",
            postgres_server_transactions,
        )
        write_json(indexer_dir / "postgres-server-mempool.json", postgres_server_mempool)
        write_json(
            indexer_dir / "postgres-server-wallet-status.json",
            postgres_server_wallet_status,
        )
        write_json(
            indexer_dir / "postgres-server-wallet-draft-preview.json",
            postgres_server_wallet_draft_preview,
        )
        write_json(
            indexer_dir / "postgres-server-transaction-detail.json",
            postgres_server_transaction_detail,
        )
        write_json(
            indexer_dir / "postgres-server-wallet-transaction-status.json",
            postgres_server_wallet_transaction_status,
        )
        write_json(
            indexer_dir / "postgres-server-iso-transaction-status.json",
            postgres_server_iso_transaction_status,
        )
        write_json(
            indexer_dir / "postgres-server-iso-payment-initiation.json",
            postgres_server_iso_payment_initiation,
        )
        write_json(
            indexer_dir / "postgres-server-iso-account-statement.json",
            postgres_server_iso_account_statement,
        )
        write_json(
            indexer_dir / "postgres-server-wallet-pending-transaction-status.json",
            postgres_server_wallet_pending_transaction_status,
        )
        write_json(indexer_dir / "postgres-server-accounts.json", postgres_server_accounts)
        write_json(
            indexer_dir / "postgres-server-wallet-accounts.json",
            postgres_server_wallet_accounts,
        )
        write_json(
            indexer_dir / "postgres-server-account-detail.json",
            postgres_server_account_detail,
        )
        write_json(
            indexer_dir / "postgres-server-wallet-balance.json",
            postgres_server_wallet_balance,
        )
        write_json(
            indexer_dir / "postgres-server-account-history.json",
            postgres_server_account_history,
        )
        write_json(
            indexer_dir / "postgres-server-wallet-account-history.json",
            postgres_server_wallet_account_history,
        )
        write_json(
            indexer_dir / "postgres-server-audit-events.json",
            postgres_server_audit_events,
        )
        write_json(
            indexer_dir / "postgres-server-snapshots.json",
            postgres_server_snapshots,
        )
        write_json(
            indexer_dir / "postgres-server-snapshot-detail.json",
            postgres_server_snapshot_detail,
        )
        completed.append("postgres-backed server read-model status")
        completed.append("postgres-backed server node status")
        completed.append("postgres-backed server indexer status")
        completed.append("postgres-backed server explorer overview")
        completed.append("postgres-backed server blocks")
        completed.append("postgres-backed server block detail")
        completed.append("postgres-backed server transactions")
        completed.append("postgres-backed server mempool")
        completed.append("postgres-backed server wallet status")
        completed.append("postgres-backed server wallet draft preview")
        completed.append("postgres-backed server transaction detail")
        completed.append("postgres-backed server wallet transaction status")
        completed.append("postgres-backed server iso20022 transaction status")
        completed.append("postgres-backed server iso20022 payment initiation")
        completed.append("postgres-backed server iso20022 account statement")
        completed.append("postgres-backed server pending wallet transaction status")
        completed.append("postgres-backed server accounts")
        completed.append("postgres-backed server wallet accounts")
        completed.append("postgres-backed server account detail")
        completed.append("postgres-backed server wallet balance")
        completed.append("postgres-backed server account history")
        completed.append("postgres-backed server wallet account history")
        completed.append("postgres-backed server audit events")
        completed.append("postgres-backed server snapshots")
        completed.append("postgres-backed server snapshot detail")
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

    def check_method_status(
        method: str,
        target: str,
        name: str,
        expected_status: int,
        validate: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        failure_routes_checked.append(f"{method} {target}")
        return assert_api_method_status(
            api_binary,
            xriq_dir,
            chain_file,
            pending_file,
            method,
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

    def validate_disabled_local_mutation(
        payload: dict[str, Any],
        context: str,
        expected_endpoint: str,
        expected_code: str,
        expected_flag: str,
        expected_action: str,
        expected_event_id: str,
        expected_resource_type: str,
        expected_resource_id: str,
        expected_request_fields: list[str],
        expected_guards: list[str],
    ) -> None:
        require_equal(payload, "network", "xriq-devnet", context)
        require_equal(payload, "endpoint", expected_endpoint, context)
        require_equal(payload, "enabled", False, context)
        require_equal(payload, "mutation", "none", context)
        require_equal(payload, "status", "disabled", context)
        require_equal(payload, "code", expected_code, context)
        require_equal(payload, "warning", "local-private-devnet-preflight-only", context)
        enablement = payload.get("required_enablement")
        if not isinstance(enablement, dict):
            raise SmokeError(f"{context}: expected required_enablement object")
        require_equal(enablement, "mode", "local-private-devnet", context)
        require_equal(enablement, "explicit_flag", expected_flag, context)
        require_equal(enablement, "audit_event_required", True, context)
        require_equal(enablement, "test_identity_only", True, context)
        require_equal(payload, "audit_scope", "api-local-refusal", context)
        require_equal(payload, "audit_event_recorded", True, context)
        audit_event = payload.get("audit_event")
        if not isinstance(audit_event, dict):
            raise SmokeError(f"{context}: expected audit_event object")
        require_equal(audit_event, "event_id", expected_event_id, context)
        require_equal(audit_event, "actor", "local-private-devnet-operator", context)
        require_equal(audit_event, "action", expected_action, context)
        require_equal(audit_event, "resource_type", expected_resource_type, context)
        require_equal(audit_event, "resource_id", expected_resource_id, context)
        require_equal(audit_event, "environment", "private-devnet", context)
        metadata = audit_event.get("metadata")
        if not isinstance(metadata, dict):
            raise SmokeError(f"{context}: expected audit_event.metadata object")
        require_equal(metadata, "endpoint", expected_endpoint, context)
        require_equal(metadata, "outcome", "refused", context)
        require_equal(metadata, "status", "disabled", context)
        require_equal(metadata, "refusal_code", expected_code, context)
        require_equal(metadata, "explicit_flag", expected_flag, context)
        require_equal(metadata, "local_request_id", "local_request_id", context)
        require_equal(metadata, "resource_id_policy", expected_resource_id, context)
        require_equal(metadata, "mutation", "none", context)
        metadata_policy = metadata.get("metadata_policy")
        if not isinstance(metadata_policy, str) or "request fields only" not in metadata_policy:
            raise SmokeError(f"{context}: expected request-fields-only audit metadata policy")
        request_fields = require_list(payload.get("request_fields"), context)
        for required_field in expected_request_fields:
            if required_field not in request_fields:
                raise SmokeError(f"{context}: missing request field {required_field}")
        refusal_guards = require_list(payload.get("refusal_guards"), context)
        guard_text = "\n".join(str(guard) for guard in refusal_guards)
        for required_guard in expected_guards:
            if required_guard not in guard_text:
                raise SmokeError(f"{context}: missing refusal guard {required_guard!r}")
        forbidden_keys = find_forbidden_wallet_keys(payload)
        if forbidden_keys:
            raise SmokeError(f"{context}: forbidden response keys {forbidden_keys}")

    def validate_wallet_submit_disabled(payload: dict[str, Any]) -> None:
        validate_disabled_local_mutation(
            payload,
            "wallet submit disabled",
            "POST /api/v1/wallet/transfers/submit",
            "wallet_submit_disabled",
            "--enable-local-wallet-submit",
            "wallet_transfer_submit_attempt",
            "wallet-transfer-submit:local_request_id",
            "wallet_transfer",
            "draft_id_or_local_request_id",
            [
                "draft_id",
                "from_address",
                "to_address",
                "amount_base_units",
                "fee_base_units",
                "nonce",
                "expires_at_height",
            ],
            [
                "default mode refuses mutation",
                "signing material is not accepted",
                "custody is not supported",
                "audit event is required before any future accepted mutation",
            ],
        )

    def validate_wallet_send_disabled(payload: dict[str, Any]) -> None:
        validate_disabled_local_mutation(
            payload,
            "wallet send disabled",
            "POST /api/v1/wallet/transfers/send",
            "wallet_send_disabled",
            "--enable-local-wallet-send",
            "wallet_transfer_send_attempt",
            "wallet-transfer-send:local_request_id",
            "wallet_transfer",
            "local_request_id",
            [
                "draft_id",
                "from_address",
                "to_address",
                "amount_base_units",
                "fee_base_units",
                "nonce",
                "expires_at_height",
            ],
            [
                "default mode refuses mutation",
                "signing material is not accepted",
                "custody is not supported",
                "pending state is not changed",
            ],
        )

    def validate_block_production_disabled(payload: dict[str, Any]) -> None:
        validate_disabled_local_mutation(
            payload,
            "block production disabled",
            "POST /api/v1/blocks/produce",
            "block_production_disabled",
            "--enable-local-block-production",
            "block_production_attempt",
            "block-production:local_request_id",
            "block_production",
            "local_request_id",
            [
                "pending_file",
                "chain_file",
                "producer",
                "max_transactions",
                "timestamp_ms",
            ],
            [
                "default mode refuses mutation",
                "pending state is not changed",
                "chain state is not changed",
                "audit event is required before any future accepted mutation",
            ],
        )

    def validate_wallet_submit_accepted(payload: dict[str, Any]) -> None:
        context = "local wallet submit"
        require_equal(payload, "environment", "private-devnet", context)
        require_equal(payload, "network", "xriq-devnet", context)
        require_equal(payload, "endpoint", "POST /api/v1/wallet/transfers/submit", context)
        require_equal(payload, "code", "wallet_submit_accepted_local_only", context)
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
        require_equal(
            pending_state,
            "pending_file",
            str(local_wallet_submit_pending_file),
            f"{context} pending",
        )
        chain_state = payload.get("chain_state")
        if not isinstance(chain_state, dict):
            raise SmokeError(f"{context}: expected chain_state object")
        require_equal(chain_state, "current_height", 1, f"{context} chain")
        require_hash(chain_state.get("latest_block_hash"), f"{context} latest block")
        require_equal(
            chain_state,
            "chain_file",
            str(local_wallet_submit_chain_file),
            f"{context} chain",
        )
        require_equal(chain_state, "chain_unchanged", True, f"{context} chain")
        require_equal(payload, "audit_event_recorded", True, context)
        audit_event = payload.get("audit_event")
        if not isinstance(audit_event, dict):
            raise SmokeError(f"{context}: expected audit_event object")
        require_equal(
            audit_event,
            "event_id",
            "wallet-transfer-submit:local-wallet-smoke-1",
            f"{context} audit",
        )
        require_equal(
            audit_event,
            "actor",
            "local-private-devnet-operator",
            f"{context} audit",
        )
        require_equal(
            audit_event,
            "action",
            "wallet_transfer_submit_attempt",
            f"{context} audit",
        )
        require_equal(audit_event, "resource_type", "wallet_transfer", f"{context} audit")
        require_equal(
            audit_event,
            "resource_id",
            "draft_id_or_local_request_id",
            f"{context} audit",
        )
        metadata = audit_event.get("metadata")
        if not isinstance(metadata, dict):
            raise SmokeError(f"{context}: expected audit metadata object")
        require_equal(metadata, "outcome", "accepted", f"{context} audit metadata")
        require_equal(metadata, "status", "pending", f"{context} audit metadata")
        require_equal(
            metadata,
            "explicit_flag",
            "--enable-local-wallet-submit",
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "local_request_id",
            "local-wallet-smoke-1",
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "draft_id",
            "draft-wallet-smoke-1",
            f"{context} audit metadata",
        )
        require_equal(metadata, "added_tx_hash", tx_hash, f"{context} audit metadata")
        require_equal(metadata, "pending_before_count", 0, f"{context} audit metadata")
        require_equal(metadata, "pending_after_count", 1, f"{context} audit metadata")
        metadata_policy = metadata.get("metadata_policy")
        if not isinstance(metadata_policy, str) or "no signing material" not in metadata_policy:
            raise SmokeError(f"{context}: expected audit metadata to forbid signing material")

    def validate_wallet_send_accepted(payload: dict[str, Any]) -> None:
        context = "local wallet send"
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
        require_equal(
            pending_state,
            "pending_file",
            str(local_wallet_send_pending_file),
            f"{context} pending",
        )
        chain_state = payload.get("chain_state")
        if not isinstance(chain_state, dict):
            raise SmokeError(f"{context}: expected chain_state object")
        require_equal(chain_state, "current_height", 1, f"{context} chain")
        require_hash(chain_state.get("latest_block_hash"), f"{context} latest block")
        require_equal(
            chain_state,
            "chain_file",
            str(local_wallet_send_chain_file),
            f"{context} chain",
        )
        require_equal(chain_state, "chain_unchanged", True, f"{context} chain")
        require_equal(payload, "audit_event_recorded", True, context)
        audit_event = payload.get("audit_event")
        if not isinstance(audit_event, dict):
            raise SmokeError(f"{context}: expected audit_event object")
        require_equal(
            audit_event,
            "event_id",
            "wallet-transfer-send:local-wallet-send-smoke-1",
            f"{context} audit",
        )
        require_equal(
            audit_event,
            "actor",
            "local-private-devnet-operator",
            f"{context} audit",
        )
        require_equal(
            audit_event,
            "action",
            "wallet_transfer_send_attempt",
            f"{context} audit",
        )
        require_equal(audit_event, "resource_type", "wallet_transfer", f"{context} audit")
        require_equal(audit_event, "resource_id", "local_request_id", f"{context} audit")
        metadata = audit_event.get("metadata")
        if not isinstance(metadata, dict):
            raise SmokeError(f"{context}: expected audit metadata object")
        require_equal(metadata, "outcome", "accepted", f"{context} audit metadata")
        require_equal(metadata, "status", "pending", f"{context} audit metadata")
        require_equal(
            metadata,
            "explicit_flag",
            "--enable-local-wallet-send",
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "local_request_id",
            "local-wallet-send-smoke-1",
            f"{context} audit metadata",
        )
        require_equal(metadata, "added_tx_hash", tx_hash, f"{context} audit metadata")
        require_equal(metadata, "pending_before_count", 0, f"{context} audit metadata")
        require_equal(metadata, "pending_after_count", 1, f"{context} audit metadata")
        metadata_policy = metadata.get("metadata_policy")
        if not isinstance(metadata_policy, str) or "no signing material" not in metadata_policy:
            raise SmokeError(f"{context}: expected audit metadata to forbid signing material")

    def validate_block_production_accepted_payload(
        payload: dict[str, Any],
        *,
        context: str,
        expected_local_request_id: str,
        expected_chain_file: Path,
        expected_pending_file: Path,
    ) -> None:
        require_equal(payload, "environment", "private-devnet", context)
        require_equal(payload, "network", "xriq-devnet", context)
        require_equal(payload, "endpoint", "POST /api/v1/blocks/produce", context)
        require_equal(
            payload,
            "code",
            "block_production_accepted_local_only",
            context,
        )
        require_equal(payload, "status", "confirmed", context)
        require_equal(
            payload,
            "mutation",
            "chain_and_pending_state_local_only",
            context,
        )
        require_equal(payload, "warning", "local-private-devnet-only", context)
        block = payload.get("block")
        if not isinstance(block, dict):
            raise SmokeError(f"{context}: expected block object")
        require_equal(block, "height", 2, f"{context} block")
        require_hash(block.get("block_hash"), f"{context} block hash")
        require_hash(block.get("previous_block_hash"), f"{context} previous hash")
        require_hash(block.get("state_root"), f"{context} state root")
        require_hash(block.get("transactions_root"), f"{context} transactions root")
        require_equal(block, "transaction_count", 1, f"{context} block")
        require_equal(block, "timestamp_utc", "1970-01-01T00:00:02Z", context)
        confirmed_transactions = require_list(
            payload.get("confirmed_transactions"),
            f"{context} confirmed transactions",
        )
        if len(confirmed_transactions) != 1 or not isinstance(confirmed_transactions[0], dict):
            raise SmokeError(f"{context}: expected one confirmed transaction")
        confirmed = confirmed_transactions[0]
        require_equal(confirmed, "tx_hash", pending_tx_hash, f"{context} tx")
        require_equal(confirmed, "status", "confirmed", f"{context} tx")
        require_equal(confirmed, "block_height", 2, f"{context} tx")
        require_equal(confirmed, "transaction_index", 0, f"{context} tx")
        require_hash(confirmed.get("block_hash"), f"{context} tx block hash")
        pending_state = payload.get("pending_state")
        if not isinstance(pending_state, dict):
            raise SmokeError(f"{context}: expected pending_state object")
        require_equal(pending_state, "before_count", 1, f"{context} pending")
        require_equal(pending_state, "after_count", 0, f"{context} pending")
        removed = require_list(
            pending_state.get("removed_tx_hashes"),
            f"{context} removed tx hashes",
        )
        if removed != [pending_tx_hash]:
            raise SmokeError(
                f"{context}: expected removed pending hash "
                f"{pending_tx_hash}, got {removed!r}"
            )
        require_equal(
            pending_state,
            "pending_file",
            str(expected_pending_file),
            f"{context} pending",
        )
        chain_state = payload.get("chain_state")
        if not isinstance(chain_state, dict):
            raise SmokeError(f"{context}: expected chain_state object")
        require_equal(chain_state, "previous_height", 1, f"{context} chain")
        require_equal(chain_state, "current_height", 2, f"{context} chain")
        require_equal(
            chain_state,
            "chain_file",
            str(expected_chain_file),
            f"{context} chain",
        )
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
        require_equal(
            audit_event,
            "actor",
            "local-private-devnet-operator",
            f"{context} audit",
        )
        require_equal(
            audit_event,
            "action",
            "block_production_attempt",
            f"{context} audit",
        )
        require_equal(
            audit_event,
            "resource_type",
            "block_production",
            f"{context} audit",
        )
        require_equal(
            audit_event,
            "resource_id",
            expected_local_request_id,
            f"{context} audit",
        )
        metadata = audit_event.get("metadata")
        if not isinstance(metadata, dict):
            raise SmokeError(f"{context}: expected audit metadata object")
        require_equal(metadata, "outcome", "accepted", f"{context} audit metadata")
        require_equal(metadata, "status", "confirmed", f"{context} audit metadata")
        require_equal(
            metadata,
            "explicit_flag",
            "--enable-local-block-production",
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "local_request_id",
            expected_local_request_id,
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "producer",
            "xriqdev1author00000000000",
            f"{context} audit metadata",
        )
        require_equal(metadata, "max_transactions", 4, f"{context} audit metadata")
        require_equal(metadata, "timestamp_ms", 2000, f"{context} audit metadata")
        require_equal(
            metadata,
            "pending_before_count",
            1,
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "pending_after_count",
            0,
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "confirmed_transaction_count",
            1,
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "chain_previous_height",
            1,
            f"{context} audit metadata",
        )
        require_equal(
            metadata,
            "chain_current_height",
            2,
            f"{context} audit metadata",
        )

    def validate_block_production_accepted(payload: dict[str, Any]) -> None:
        validate_block_production_accepted_payload(
            payload,
            context="local block production",
            expected_local_request_id="local-smoke-1",
            expected_chain_file=local_production_chain_file,
            expected_pending_file=local_production_pending_file,
        )

    def validate_server_block_production_accepted(payload: dict[str, Any]) -> None:
        validate_block_production_accepted_payload(
            payload,
            context="serve-readonly local block production",
            expected_local_request_id="local-smoke-server-1",
            expected_chain_file=local_server_production_chain_file,
            expected_pending_file=local_server_production_pending_file,
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
        validate_local_refusal_audit_events(payload, "audit events")

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
    check_method_status(
        "POST",
        "/api/v1/wallet/transfers/submit",
        "wallet-submit-disabled",
        403,
        validate_wallet_submit_disabled,
    )
    check_method_status(
        "POST",
        "/api/v1/wallet/transfers/send",
        "wallet-send-disabled",
        403,
        validate_wallet_send_disabled,
    )
    check_method_status(
        "POST",
        "/api/v1/blocks/produce",
        "block-production-disabled",
        403,
        validate_block_production_disabled,
    )
    local_wallet_submit_chain_file = artifact_dir / "local-wallet-submit-chain.bin"
    local_wallet_submit_pending_file = artifact_dir / "local-wallet-submit-pending.tsv"
    shutil.copyfile(chain_file, local_wallet_submit_chain_file)
    local_wallet_submit_pending_file.write_text("", encoding="utf-8")
    local_wallet_submit_target = (
        f"/api/v1/wallet/transfers/submit?local_request_id=local-wallet-smoke-1"
        f"&draft_id=draft-wallet-smoke-1&from_address={ALICE}&to_address={CAROL}"
        "&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100"
    )
    local_wallet_submit = assert_api_method_status(
        api_binary,
        xriq_dir,
        local_wallet_submit_chain_file,
        local_wallet_submit_pending_file,
        "POST",
        local_wallet_submit_target,
        201,
        api_artifact_dir / "wallet-submit-accepted-local.json",
        validate_wallet_submit_accepted,
        extra_args=["--enable-local-wallet-submit", "true"],
    )
    local_wallet_submit_tx_hash = require_hash(
        local_wallet_submit.get("transaction", {}).get("tx_hash"),
        "local wallet submit accepted tx hash",
    )
    local_wallet_submit_pending_text = local_wallet_submit_pending_file.read_text(
        encoding="utf-8"
    )
    if local_wallet_submit_tx_hash not in local_wallet_submit_pending_text:
        raise SmokeError("local wallet submit: copied pending file did not include accepted tx")
    if pending_tx_hash not in pending_file.read_text(encoding="utf-8"):
        raise SmokeError("local wallet submit: original pending file was unexpectedly changed")
    completed.append("local wallet submit accepted smoke")
    local_wallet_send_chain_file = artifact_dir / "local-wallet-send-chain.bin"
    local_wallet_send_pending_file = artifact_dir / "local-wallet-send-pending.tsv"
    shutil.copyfile(chain_file, local_wallet_send_chain_file)
    local_wallet_send_pending_file.write_text("", encoding="utf-8")
    local_wallet_send_target = (
        f"/api/v1/wallet/transfers/send?local_request_id=local-wallet-send-smoke-1"
        f"&from_address={ALICE}&to_address={CAROL}"
        "&amount_base_units=5&fee_base_units=2&nonce=1&expires_at_height=100"
    )
    local_wallet_send = assert_api_method_status(
        api_binary,
        xriq_dir,
        local_wallet_send_chain_file,
        local_wallet_send_pending_file,
        "POST",
        local_wallet_send_target,
        201,
        api_artifact_dir / "wallet-send-accepted-local.json",
        validate_wallet_send_accepted,
        extra_args=["--enable-local-wallet-send", "true"],
    )
    local_wallet_send_tx_hash = require_hash(
        local_wallet_send.get("transaction", {}).get("tx_hash"),
        "local wallet send accepted tx hash",
    )
    local_wallet_send_pending_text = local_wallet_send_pending_file.read_text(encoding="utf-8")
    if local_wallet_send_tx_hash not in local_wallet_send_pending_text:
        raise SmokeError("local wallet send: copied pending file did not include accepted tx")
    if pending_tx_hash not in pending_file.read_text(encoding="utf-8"):
        raise SmokeError("local wallet send: original pending file was unexpectedly changed")
    completed.append("local wallet send accepted smoke")
    local_production_chain_file = artifact_dir / "local-block-production-chain.bin"
    local_production_pending_file = artifact_dir / "local-block-production-pending.tsv"
    shutil.copyfile(chain_file, local_production_chain_file)
    shutil.copyfile(pending_file, local_production_pending_file)
    local_block_production_target = (
        "/api/v1/blocks/produce?local_request_id=local-smoke-1"
        "&producer=xriqdev1author00000000000&max_transactions=4&timestamp_ms=2000"
    )
    assert_api_method_status(
        api_binary,
        xriq_dir,
        local_production_chain_file,
        local_production_pending_file,
        "POST",
        local_block_production_target,
        201,
        api_artifact_dir / "block-production-accepted-local.json",
        validate_block_production_accepted,
        extra_args=["--enable-local-block-production", "true"],
    )
    if local_production_pending_file.read_text(encoding="utf-8") != "":
        raise SmokeError("local block production: copied pending file was not cleared")
    if pending_tx_hash not in pending_file.read_text(encoding="utf-8"):
        raise SmokeError("local block production: original pending file was unexpectedly changed")
    completed.append("local block production accepted smoke")
    local_server_production_chain_file = artifact_dir / "local-block-production-server-chain.bin"
    local_server_production_pending_file = artifact_dir / "local-block-production-server-pending.tsv"
    shutil.copyfile(chain_file, local_server_production_chain_file)
    shutil.copyfile(pending_file, local_server_production_pending_file)
    local_server_block_production_target = (
        "/api/v1/blocks/produce?local_request_id=local-smoke-server-1"
        "&producer=xriqdev1author00000000000&max_transactions=4&timestamp_ms=2000"
    )
    local_server_port = free_local_port()
    local_server_bind = f"127.0.0.1:{local_server_port}"
    local_server_base_url = f"http://{local_server_bind}"
    local_server_process: subprocess.Popen[str] | None = None
    try:
        local_server_process = start_api_readonly_server(
            api_binary,
            xriq_dir,
            artifact_dir,
            chain_file=local_server_production_chain_file,
            pending_file=local_server_production_pending_file,
            bind=local_server_bind,
            enable_local_block_production=True,
            stderr_log_name="api-local-block-production-server.stderr.log",
        )
        wait_for_api_readonly_server(local_server_base_url, local_server_process)
        local_server_block_production = http_json(
            local_server_base_url,
            local_server_block_production_target,
            expected_status=201,
            method="POST",
        )
        validate_server_block_production_accepted(local_server_block_production)
        write_json(
            api_artifact_dir / "block-production-accepted-local-server.json",
            local_server_block_production,
        )
        local_server_network = http_json(local_server_base_url, "/api/v1/network")
        require_equal(local_server_network, "current_height", 2, "serve-readonly network")
        write_json(api_artifact_dir / "block-production-server-network.json", local_server_network)
        local_server_mempool = http_json(local_server_base_url, "/api/v1/mempool?limit=5")
        require_equal(local_server_mempool, "pending_count", 0, "serve-readonly mempool")
        write_json(api_artifact_dir / "block-production-server-mempool.json", local_server_mempool)
    finally:
        stop_process(local_server_process)
    if local_server_production_pending_file.read_text(encoding="utf-8") != "":
        raise SmokeError("serve-readonly local block production: copied pending file was not cleared")
    if pending_tx_hash not in pending_file.read_text(encoding="utf-8"):
        raise SmokeError(
            "serve-readonly local block production: original pending file was unexpectedly changed"
        )
    completed.append("serve-readonly local block production accepted smoke")
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
    completed.append("wallet mutation refusal smoke")
    completed.append("block production refusal smoke")

    summary = {
        "ok": "xriq-phase1-1-local-e2e-smoke",
        "artifact_dir": str(artifact_dir),
        "chain_file": str(chain_file),
        "pending_file": str(pending_file),
        "local_block_production": {
            "chain_file": str(local_production_chain_file),
            "pending_file": str(local_production_pending_file),
            "accepted_response": str(api_artifact_dir / "block-production-accepted-local.json"),
            "serve_readonly_chain_file": str(local_server_production_chain_file),
            "serve_readonly_pending_file": str(local_server_production_pending_file),
            "serve_readonly_accepted_response": str(
                api_artifact_dir / "block-production-accepted-local-server.json"
            ),
            "serve_readonly_network": str(
                api_artifact_dir / "block-production-server-network.json"
            ),
            "serve_readonly_mempool": str(
                api_artifact_dir / "block-production-server-mempool.json"
            ),
        },
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
            "postgres_api_node_status": (
                str(indexer_dir / "postgres-api-node-status.json")
                if postgres_api_node_status
                else None
            ),
            "postgres_server_node_status": (
                str(indexer_dir / "postgres-server-node-status.json")
                if postgres_server_node_status
                else None
            ),
            "postgres_api_indexer_status": (
                str(indexer_dir / "postgres-api-indexer-status.json")
                if postgres_api_indexer_status
                else None
            ),
            "postgres_server_indexer_status": (
                str(indexer_dir / "postgres-server-indexer-status.json")
                if postgres_server_indexer_status
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
            "postgres_api_block_detail": (
                str(indexer_dir / "postgres-api-block-detail.json")
                if postgres_api_block_detail
                else None
            ),
            "postgres_server_block_detail": (
                str(indexer_dir / "postgres-server-block-detail.json")
                if postgres_server_block_detail
                else None
            ),
            "postgres_api_transactions": (
                str(indexer_dir / "postgres-api-transactions.json")
                if postgres_api_transactions
                else None
            ),
            "postgres_server_transactions": (
                str(indexer_dir / "postgres-server-transactions.json")
                if postgres_server_transactions
                else None
            ),
            "postgres_api_mempool": (
                str(indexer_dir / "postgres-api-mempool.json") if postgres_api_mempool else None
            ),
            "postgres_server_mempool": (
                str(indexer_dir / "postgres-server-mempool.json")
                if postgres_server_mempool
                else None
            ),
            "postgres_api_wallet_status": (
                str(indexer_dir / "postgres-api-wallet-status.json")
                if postgres_api_wallet_status
                else None
            ),
            "postgres_server_wallet_status": (
                str(indexer_dir / "postgres-server-wallet-status.json")
                if postgres_server_wallet_status
                else None
            ),
            "postgres_api_wallet_draft_preview": (
                str(indexer_dir / "postgres-api-wallet-draft-preview.json")
                if postgres_api_wallet_draft_preview
                else None
            ),
            "postgres_server_wallet_draft_preview": (
                str(indexer_dir / "postgres-server-wallet-draft-preview.json")
                if postgres_server_wallet_draft_preview
                else None
            ),
            "postgres_api_transaction_detail": (
                str(indexer_dir / "postgres-api-transaction-detail.json")
                if postgres_api_transaction_detail
                else None
            ),
            "postgres_server_transaction_detail": (
                str(indexer_dir / "postgres-server-transaction-detail.json")
                if postgres_server_transaction_detail
                else None
            ),
            "postgres_api_wallet_transaction_status": (
                str(indexer_dir / "postgres-api-wallet-transaction-status.json")
                if postgres_api_wallet_transaction_status
                else None
            ),
            "postgres_server_wallet_transaction_status": (
                str(indexer_dir / "postgres-server-wallet-transaction-status.json")
                if postgres_server_wallet_transaction_status
                else None
            ),
            "postgres_api_iso_transaction_status": (
                str(indexer_dir / "postgres-api-iso-transaction-status.json")
                if postgres_api_iso_transaction_status
                else None
            ),
            "postgres_server_iso_transaction_status": (
                str(indexer_dir / "postgres-server-iso-transaction-status.json")
                if postgres_server_iso_transaction_status
                else None
            ),
            "postgres_api_iso_payment_initiation": (
                str(indexer_dir / "postgres-api-iso-payment-initiation.json")
                if postgres_api_iso_payment_initiation
                else None
            ),
            "postgres_server_iso_payment_initiation": (
                str(indexer_dir / "postgres-server-iso-payment-initiation.json")
                if postgres_server_iso_payment_initiation
                else None
            ),
            "postgres_api_iso_account_statement": (
                str(indexer_dir / "postgres-api-iso-account-statement.json")
                if postgres_api_iso_account_statement
                else None
            ),
            "postgres_server_iso_account_statement": (
                str(indexer_dir / "postgres-server-iso-account-statement.json")
                if postgres_server_iso_account_statement
                else None
            ),
            "postgres_api_wallet_pending_transaction_status": (
                str(indexer_dir / "postgres-api-wallet-pending-transaction-status.json")
                if postgres_api_wallet_pending_transaction_status
                else None
            ),
            "postgres_server_wallet_pending_transaction_status": (
                str(indexer_dir / "postgres-server-wallet-pending-transaction-status.json")
                if postgres_server_wallet_pending_transaction_status
                else None
            ),
            "postgres_api_accounts": (
                str(indexer_dir / "postgres-api-accounts.json")
                if postgres_api_accounts
                else None
            ),
            "postgres_server_accounts": (
                str(indexer_dir / "postgres-server-accounts.json")
                if postgres_server_accounts
                else None
            ),
            "postgres_api_wallet_accounts": (
                str(indexer_dir / "postgres-api-wallet-accounts.json")
                if postgres_api_wallet_accounts
                else None
            ),
            "postgres_server_wallet_accounts": (
                str(indexer_dir / "postgres-server-wallet-accounts.json")
                if postgres_server_wallet_accounts
                else None
            ),
            "postgres_api_account_detail": (
                str(indexer_dir / "postgres-api-account-detail.json")
                if postgres_api_account_detail
                else None
            ),
            "postgres_server_account_detail": (
                str(indexer_dir / "postgres-server-account-detail.json")
                if postgres_server_account_detail
                else None
            ),
            "postgres_api_wallet_balance": (
                str(indexer_dir / "postgres-api-wallet-balance.json")
                if postgres_api_wallet_balance
                else None
            ),
            "postgres_server_wallet_balance": (
                str(indexer_dir / "postgres-server-wallet-balance.json")
                if postgres_server_wallet_balance
                else None
            ),
            "postgres_api_account_history": (
                str(indexer_dir / "postgres-api-account-history.json")
                if postgres_api_account_history
                else None
            ),
            "postgres_server_account_history": (
                str(indexer_dir / "postgres-server-account-history.json")
                if postgres_server_account_history
                else None
            ),
            "postgres_api_wallet_account_history": (
                str(indexer_dir / "postgres-api-wallet-account-history.json")
                if postgres_api_wallet_account_history
                else None
            ),
            "postgres_server_wallet_account_history": (
                str(indexer_dir / "postgres-server-wallet-account-history.json")
                if postgres_server_wallet_account_history
                else None
            ),
            "postgres_api_audit_events": (
                str(indexer_dir / "postgres-api-audit-events.json")
                if postgres_api_audit_events
                else None
            ),
            "postgres_server_audit_events": (
                str(indexer_dir / "postgres-server-audit-events.json")
                if postgres_server_audit_events
                else None
            ),
            "postgres_api_snapshots": (
                str(indexer_dir / "postgres-api-snapshots.json")
                if postgres_api_snapshots
                else None
            ),
            "postgres_server_snapshots": (
                str(indexer_dir / "postgres-server-snapshots.json")
                if postgres_server_snapshots
                else None
            ),
            "postgres_api_snapshot_detail": (
                str(indexer_dir / "postgres-api-snapshot-detail.json")
                if postgres_api_snapshot_detail
                else None
            ),
            "postgres_server_snapshot_detail": (
                str(indexer_dir / "postgres-server-snapshot-detail.json")
                if postgres_server_snapshot_detail
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
