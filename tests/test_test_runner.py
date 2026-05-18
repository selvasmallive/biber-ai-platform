from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings
from biber_api.test_runner import (
    UnknownTestCommandError,
    list_test_commands,
    run_test_command,
)


def make_settings(workspace: Path) -> BiberSettings:
    xriq_workspace = workspace / "xriq"
    xriq_workspace.mkdir(parents=True, exist_ok=True)
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
        repo_context_root=str(workspace),
        xriq_workspace_dir=str(xriq_workspace),
        test_runner_timeout_seconds=5,
        test_runner_max_output_bytes=8,
    )


def test_list_test_commands_exposes_fixed_allowlist(tmp_path: Path) -> None:
    commands = list_test_commands(make_settings(tmp_path))
    ids = {command["test_id"] for command in commands}

    assert ids == {
        "python-compileall-api",
        "pytest-core",
        "xriq-node-fixtures",
        "xriq-private-devnet-smoke",
    }
    assert all(isinstance(command["command"], list) for command in commands)
    assert all(command["cwd"] != "unavailable" for command in commands)


def test_dry_run_returns_command_without_executing(tmp_path: Path) -> None:
    def runner(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise AssertionError("dry_run must not call subprocess")

    result = run_test_command(
        "python-compileall-api",
        make_settings(tmp_path),
        dry_run=True,
        runner=runner,
    )

    assert result["executed"] is False
    assert result["ok"] is None
    assert result["exit_code"] is None
    assert result["cwd"] == str(tmp_path)
    assert result["command"][-3:] == ["compileall", "app", "src"]


def test_runner_executes_with_fixed_cwd_timeout_and_truncation(tmp_path: Path) -> None:
    calls: list[dict[str, Any]] = []

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, "kwargs": kwargs})
        return subprocess.CompletedProcess(command, 1, stdout="0123456789", stderr="err")

    result = run_test_command("pytest-core", make_settings(tmp_path), runner=runner)

    assert result["executed"] is True
    assert result["ok"] is False
    assert result["exit_code"] == 1
    assert result["stdout"] == "01234567\n...<truncated>"
    assert result["stdout_truncated"] is True
    assert result["stderr_truncated"] is False
    assert calls[0]["kwargs"]["cwd"] == str(tmp_path)
    assert calls[0]["kwargs"]["timeout"] == 180
    assert calls[0]["kwargs"]["capture_output"] is True
    assert calls[0]["kwargs"]["text"] is True
    assert calls[0]["kwargs"]["check"] is False


def test_xriq_test_command_uses_configured_rust_environment(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    settings = BiberSettings(
        **{
            **settings.__dict__,
            "xriq_rustup_home": "/opt/rustup",
            "xriq_cargo_home": "/opt/cargo",
            "xriq_path_prefix": "/opt/cargo/bin",
        }
    )
    calls: list[dict[str, Any]] = []

    def runner(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"command": command, "kwargs": kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    result = run_test_command("xriq-node-fixtures", settings, runner=runner)

    assert result["ok"] is True
    assert calls[0]["kwargs"]["cwd"] == str(Path(settings.xriq_workspace_dir))
    env = calls[0]["kwargs"]["env"]
    assert env["RUSTUP_HOME"] == "/opt/rustup"
    assert env["CARGO_HOME"] == "/opt/cargo"
    assert env["PATH"].startswith(f"/opt/cargo/bin{os.pathsep}")


def test_unknown_test_id_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(UnknownTestCommandError):
        run_test_command("shell-anything", make_settings(tmp_path))


def test_test_run_endpoint_invokes_allowlisted_runner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(tmp_path)
    calls: list[dict[str, Any]] = []

    def fake_runner(
        test_id: str,
        injected_settings: BiberSettings,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        calls.append(
            {
                "test_id": test_id,
                "settings": injected_settings,
                "dry_run": dry_run,
            }
        )
        return {
            "test_id": test_id,
            "label": "Core API pytest",
            "description": "Run focused API tests.",
            "cwd": str(tmp_path),
            "command": ["python", "-m", "pytest"],
            "timeout_seconds": 180,
            "executed": False,
            "ok": None,
            "exit_code": None,
            "timed_out": False,
            "duration_ms": 0,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }

    monkeypatch.setattr(main_module, "run_test_command", fake_runner)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/tests/run",
            json={"test_id": "pytest-core", "dry_run": True},
            headers={"x-api-key": "test-key"},
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["test_id"] == "pytest-core"
    assert calls == [
        {
            "test_id": "pytest-core",
            "settings": settings,
            "dry_run": True,
        }
    ]
