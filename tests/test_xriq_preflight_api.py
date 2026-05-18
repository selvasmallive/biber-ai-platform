from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings
from biber_api.xriq_client import (
    XriqCommandError,
    XriqPreflightTransferRequest,
    run_private_devnet_account_detail,
    run_private_devnet_preflight_transfer,
    run_private_devnet_status,
    run_private_devnet_transaction_detail,
)


def make_settings(workspace: Path) -> BiberSettings:
    return BiberSettings(
        env="test",
        api_keys=("test-key",),
        priority_passcodes={},
        local_model_base_url="http://local-model/v1",
        local_model_name="biber-dev-core",
        local_model_timeout_seconds=1,
        mentor_enabled=False,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key=None,
        openai_model=None,
        github_token=None,
        github_default_owner=None,
        github_default_repo=None,
        azure_storage_connection_string=None,
        azure_blob_container="biber-backups",
        xriq_workspace_dir=str(workspace),
        xriq_node_command="xriq-node",
        xriq_chain_file="target/test-chain.bin",
        xriq_pending_file="target/test-pending.tsv",
        xriq_default_alice_balance_base_units="100",
        xriq_command_timeout_seconds=7,
    )


def preflight_request() -> XriqPreflightTransferRequest:
    return XriqPreflightTransferRequest.model_validate(
        {
            "from": "xriqdev1alice00000000000",
            "to": "xriqdev1bobbb00000000000",
            "amount_base_units": "25",
            "fee_base_units": "2",
            "expires_at_height": 100,
            "timestamp_ms": 1000,
        }
    )


def test_preflight_client_invokes_xriq_node_runner(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "format_version": "xriq-node-json-v1",
                    "command": "preflight-transfer",
                    "transaction_hash": "abc",
                }
            ),
            stderr="",
        )

    payload = run_private_devnet_preflight_transfer(
        preflight_request(),
        make_settings(tmp_path),
        runner=runner,
    )

    assert payload["command"] == "preflight-transfer"
    assert calls[0]["kwargs"]["cwd"] == str(tmp_path)
    assert calls[0]["kwargs"]["timeout"] == 7
    assert calls[0]["command"] == [
        "xriq-node",
        "preflight-transfer",
        "--chain-file",
        "target/test-chain.bin",
        "--pending-file",
        "target/test-pending.tsv",
        "--alice-balance",
        "100",
        "--from",
        "xriqdev1alice00000000000",
        "--to",
        "xriqdev1bobbb00000000000",
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
    ]


def test_preflight_client_surfaces_xriq_json_errors(tmp_path: Path) -> None:
    error_payload = {
        "format_version": "xriq-node-json-v1",
        "ok": False,
        "command": "preflight-transfer",
        "error": {"code": "node_error", "message": "insufficient funds"},
    }

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=json.dumps(error_payload))

    with pytest.raises(XriqCommandError) as exc_info:
        run_private_devnet_preflight_transfer(
            preflight_request(),
            make_settings(tmp_path),
            runner=runner,
        )

    assert str(exc_info.value) == "insufficient funds"
    assert exc_info.value.status_code == 400
    assert exc_info.value.payload == error_payload


def test_status_client_invokes_xriq_node_runner(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, "kwargs": kwargs})
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"format_version": "xriq-node-json-v1", "command": "status"}),
            stderr="",
        )

    payload = run_private_devnet_status(make_settings(tmp_path), runner=runner)

    assert payload["command"] == "status"
    assert calls[0]["command"] == [
        "xriq-node",
        "status",
        "--chain-file",
        "target/test-chain.bin",
        "--alice-balance",
        "100",
        "--format",
        "json",
    ]


def test_account_client_invokes_xriq_node_runner(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "format_version": "xriq-node-json-v1",
                    "command": "account-detail",
                    "address": "xriqdev1alice00000000000",
                }
            ),
            stderr="",
        )

    payload = run_private_devnet_account_detail(
        "xriqdev1alice00000000000",
        make_settings(tmp_path),
        runner=runner,
    )

    assert payload["command"] == "account-detail"
    assert calls[0] == [
        "xriq-node",
        "account-detail",
        "--chain-file",
        "target/test-chain.bin",
        "--alice-balance",
        "100",
        "--format",
        "json",
        "--address",
        "xriqdev1alice00000000000",
    ]


def test_transaction_client_invokes_xriq_node_runner(tmp_path: Path) -> None:
    calls: list[list[str]] = []
    tx_hash = "a" * 64

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "format_version": "xriq-node-json-v1",
                    "command": "transaction-detail",
                    "tx_hash": tx_hash,
                }
            ),
            stderr="",
        )

    payload = run_private_devnet_transaction_detail(
        tx_hash,
        make_settings(tmp_path),
        runner=runner,
    )

    assert payload["command"] == "transaction-detail"
    assert calls[0] == [
        "xriq-node",
        "transaction-detail",
        "--chain-file",
        "target/test-chain.bin",
        "--alice-balance",
        "100",
        "--format",
        "json",
        "--tx-hash",
        tx_hash,
    ]


def test_preflight_endpoint_returns_runner_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_preflight(
        request: XriqPreflightTransferRequest,
        settings: BiberSettings,
    ) -> dict[str, object]:
        assert request.from_address == "xriqdev1alice00000000000"
        assert settings.default_model == "biber-dev-core-v1"
        return {
            "format_version": "xriq-node-json-v1",
            "command": "preflight-transfer",
            "transaction_hash": "abc",
        }

    monkeypatch.setattr(
        main_module,
        "run_private_devnet_preflight_transfer",
        fake_preflight,
    )

    response = TestClient(main_module.app).post(
        "/v1/xriq/private-devnet/preflight-transfer",
        json={
            "from": "xriqdev1alice00000000000",
            "to": "xriqdev1bobbb00000000000",
            "amount_base_units": "25",
            "fee_base_units": "2",
        },
        headers={"x-api-key": "test-key"},
    )

    assert response.status_code == 200
    assert response.json()["command"] == "preflight-transfer"


def test_read_endpoints_return_runner_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main_module,
        "run_private_devnet_status",
        lambda settings: {"command": "status"},
    )
    monkeypatch.setattr(
        main_module,
        "run_private_devnet_account_detail",
        lambda address, settings: {"command": "account-detail", "address": address},
    )
    monkeypatch.setattr(
        main_module,
        "run_private_devnet_transaction_detail",
        lambda tx_hash, settings: {"command": "transaction-detail", "tx_hash": tx_hash},
    )

    client = TestClient(main_module.app)
    headers = {"x-api-key": "test-key"}

    status_response = client.get("/v1/xriq/private-devnet/status", headers=headers)
    account_response = client.get(
        "/v1/xriq/private-devnet/accounts/xriqdev1alice00000000000",
        headers=headers,
    )
    transaction_response = client.get(
        f"/v1/xriq/private-devnet/transactions/{'a' * 64}",
        headers=headers,
    )

    assert status_response.status_code == 200
    assert status_response.json()["command"] == "status"
    assert account_response.status_code == 200
    assert account_response.json()["address"] == "xriqdev1alice00000000000"
    assert transaction_response.status_code == 200
    assert transaction_response.json()["command"] == "transaction-detail"
