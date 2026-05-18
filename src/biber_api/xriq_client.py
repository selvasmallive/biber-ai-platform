from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field

from .config import BiberSettings


class XriqPreflightTransferRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_address: str = Field(alias="from", min_length=1)
    to_address: str = Field(alias="to", min_length=1)
    amount_base_units: str = Field(min_length=1, pattern=r"^[0-9]+$")
    fee_base_units: str = Field(min_length=1, pattern=r"^[0-9]+$")
    expires_at_height: int | None = Field(default=None, ge=0)
    timestamp_ms: int | None = Field(default=None, ge=0)
    consensus_round: int | None = Field(default=None, ge=0)
    alice_balance_base_units: str | None = Field(default=None, pattern=r"^[0-9]+$")


class XriqConfigurationError(RuntimeError):
    pass


class XriqCommandTimeout(RuntimeError):
    pass


class XriqCommandError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        payload: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


Runner = Callable[..., subprocess.CompletedProcess[str]]


def run_private_devnet_preflight_transfer(
    request: XriqPreflightTransferRequest,
    settings: BiberSettings,
    *,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    return _run_xriq_node_json(
        _preflight_command(request, settings),
        settings,
        runner=runner,
        operation="XRIQ preflight transfer",
    )


def run_private_devnet_status(
    settings: BiberSettings,
    *,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    return _run_xriq_node_json(
        _read_command("status", settings),
        settings,
        runner=runner,
        operation="XRIQ status",
    )


def run_private_devnet_account_detail(
    address: str,
    settings: BiberSettings,
    *,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    command = _read_command("account-detail", settings)
    command.extend(["--address", address])
    return _run_xriq_node_json(
        command,
        settings,
        runner=runner,
        operation="XRIQ account detail",
    )


def run_private_devnet_transaction_detail(
    tx_hash: str,
    settings: BiberSettings,
    *,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    command = _read_command("transaction-detail", settings)
    command.extend(["--tx-hash", tx_hash])
    return _run_xriq_node_json(
        command,
        settings,
        runner=runner,
        operation="XRIQ transaction detail",
    )


def _run_xriq_node_json(
    command: list[str],
    settings: BiberSettings,
    *,
    runner: Runner,
    operation: str,
) -> dict[str, Any]:
    workspace = Path(settings.xriq_workspace_dir)
    if not workspace.exists() or not workspace.is_dir():
        raise XriqConfigurationError(f"XRIQ workspace does not exist: {workspace}")

    try:
        completed = runner(
            command,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=settings.xriq_command_timeout_seconds,
            check=False,
            env=_subprocess_env(settings),
        )
    except FileNotFoundError as exc:
        raise XriqConfigurationError(f"XRIQ node command not found: {command[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise XriqCommandTimeout(
            f"{operation} timed out after {settings.xriq_command_timeout_seconds}s"
        ) from exc

    if completed.returncode != 0:
        payload = _parse_json_or_none(completed.stderr) or _parse_json_or_none(completed.stdout)
        message = _error_message(payload) if payload else _trim_output(completed.stderr)
        if not message:
            message = f"{operation} failed with exit code {completed.returncode}"
        raise XriqCommandError(
            message,
            status_code=400 if payload else 502,
            payload=payload,
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise XriqCommandError(
            f"{operation} returned invalid JSON.",
            status_code=502,
        ) from exc
    if not isinstance(payload, dict):
        raise XriqCommandError(
            f"{operation} returned a non-object JSON response.",
            status_code=502,
        )
    return payload


def _preflight_command(
    request: XriqPreflightTransferRequest,
    settings: BiberSettings,
) -> list[str]:
    command = _base_command(settings)
    command.extend(
        [
            "preflight-transfer",
            "--chain-file",
            settings.xriq_chain_file,
            "--pending-file",
            settings.xriq_pending_file,
            "--alice-balance",
            request.alice_balance_base_units
            or settings.xriq_default_alice_balance_base_units,
            "--from",
            request.from_address,
            "--to",
            request.to_address,
            "--amount",
            request.amount_base_units,
            "--fee",
            request.fee_base_units,
        ]
    )
    if request.expires_at_height is not None:
        command.extend(["--expires-at-height", str(request.expires_at_height)])
    if request.timestamp_ms is not None:
        command.extend(["--timestamp-ms", str(request.timestamp_ms)])
    if request.consensus_round is not None:
        command.extend(["--consensus-round", str(request.consensus_round)])
    command.extend(["--format", "json"])
    return command


def _read_command(command_name: str, settings: BiberSettings) -> list[str]:
    command = _base_command(settings)
    command.extend(
        [
            command_name,
            "--chain-file",
            settings.xriq_chain_file,
            "--alice-balance",
            settings.xriq_default_alice_balance_base_units,
            "--format",
            "json",
        ]
    )
    return command


def _base_command(settings: BiberSettings) -> list[str]:
    command = shlex.split(settings.xriq_node_command)
    if not command:
        raise XriqConfigurationError("BIBER_XRIQ_NODE_COMMAND must not be empty.")
    return command


def _subprocess_env(settings: BiberSettings) -> dict[str, str]:
    env = os.environ.copy()
    if settings.xriq_rustup_home:
        env["RUSTUP_HOME"] = settings.xriq_rustup_home
    if settings.xriq_cargo_home:
        env["CARGO_HOME"] = settings.xriq_cargo_home
    if settings.xriq_path_prefix:
        current_path = env.get("PATH", "")
        env["PATH"] = settings.xriq_path_prefix + os.pathsep + current_path
    return env


def _parse_json_or_none(value: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _error_message(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    return str(payload)


def _trim_output(value: str) -> str:
    return value.strip()[:1000]
