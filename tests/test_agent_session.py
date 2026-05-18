from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings
from biber_api.schemas import ChatRequest


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
        repo_context_root=str(workspace),
        workspace_edit_max_file_bytes=1000,
        workspace_edit_max_new_text_bytes=500,
    )


def test_agent_session_runs_chat_edit_and_test(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: dict[str, Any] = {}
    settings = make_settings(tmp_path)

    class FakeChatService:
        def __init__(self, injected_settings: BiberSettings) -> None:
            calls["chat_settings"] = injected_settings

        async def generate(
            self,
            request: ChatRequest,
        ) -> tuple[str, str | None, dict[str, Any], str]:
            calls["chat_request"] = request
            return "BIBER agent plan", None, {"raw": True}, "biber-dev-core-v1"

    def fake_edit(**kwargs: Any) -> dict[str, Any]:
        calls["edit"] = kwargs
        return {
            "path": kwargs["path"],
            "created": True,
            "dry_run": True,
            "changed": True,
            "replacements": 0,
            "old_sha256": None,
            "new_sha256": "abc",
            "old_bytes": 0,
            "new_bytes": 5,
        }

    def fake_test_command(
        test_id: str,
        injected_settings: BiberSettings,
        *,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        calls["test"] = {
            "test_id": test_id,
            "settings": injected_settings,
            "dry_run": dry_run,
        }
        return {
            "test_id": test_id,
            "label": "Python API compileall",
            "description": "Compile-check app/ and src/ Python modules.",
            "cwd": str(tmp_path),
            "command": ["python", "-m", "compileall", "app", "src"],
            "timeout_seconds": 120,
            "executed": True,
            "ok": True,
            "exit_code": 0,
            "timed_out": False,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }

    monkeypatch.setattr(main_module, "BiberChatService", FakeChatService)
    monkeypatch.setattr(main_module, "apply_workspace_edit", fake_edit)
    monkeypatch.setattr(main_module, "run_test_command", fake_test_command)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/agent/sessions",
            json={
                "instruction": "Plan a tiny change.",
                "language": "Python",
                "repo_context_paths": ["README.md"],
                "workspace_edit": {
                    "path": "generated/session.txt",
                    "new_text": "hello",
                    "create_if_missing": True,
                    "dry_run": True,
                },
                "test_id": "python-compileall-api",
            },
            headers={"x-api-key": "test-key"},
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "biber-dev-core-v1"
    assert body["content"] == "BIBER agent plan"
    assert body["mentor_used"] is False
    assert [step["name"] for step in body["steps"]] == [
        "chat",
        "workspace_edit",
        "test_run",
    ]
    assert body["steps"][2]["output"]["ok"] is True
    assert calls["chat_request"].messages[0].content == "Plan a tiny change."
    assert calls["chat_request"].repo_context_paths == ["README.md"]
    assert calls["edit"]["path"] == "generated/session.txt"
    assert calls["edit"]["dry_run"] is True
    assert calls["test"]["test_id"] == "python-compileall-api"


def test_agent_session_can_skip_test_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class FakeChatService:
        def __init__(self, injected_settings: BiberSettings) -> None:
            pass

        async def generate(
            self,
            request: ChatRequest,
        ) -> tuple[str, str | None, dict[str, Any], str]:
            return "Only chat", None, {}, "biber-dev-core-v1"

    def unexpected_test(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("test run should be skipped")

    monkeypatch.setattr(main_module, "BiberChatService", FakeChatService)
    monkeypatch.setattr(main_module, "run_test_command", unexpected_test)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: make_settings(
        tmp_path
    )
    try:
        response = TestClient(main_module.app).post(
            "/v1/agent/sessions",
            json={"instruction": "Only plan.", "test_id": None},
            headers={"x-api-key": "test-key"},
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [step["name"] for step in response.json()["steps"]] == ["chat"]
