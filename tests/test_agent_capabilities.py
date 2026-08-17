from __future__ import annotations

import json
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
        agent_session_dir=str(workspace / ".biber-test-sessions"),
        repo_context_max_files=7,
        repo_context_max_total_bytes=12345,
        workspace_edit_max_file_bytes=1000,
        workspace_edit_max_new_text_bytes=500,
    )


def test_agent_capabilities_describes_client_workflows(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).get(
            "/v1/agent/capabilities",
            headers={"x-api-key": "test-key"},
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "biber-agent"
    assert body["version"] == "mvp-v1"
    assert body["default_model"] == "biber-dev-core-v1"
    assert body["endpoints"]["models"] == "GET /v1/models"
    assert body["endpoints"]["chat"] == "POST /v1/chat"
    assert body["endpoints"]["openai_chat_completions"] == "POST /v1/chat/completions"
    assert body["endpoints"]["agent_capabilities"] == "GET /v1/agent/capabilities"
    assert body["endpoints"]["create_session"] == "POST /v1/agent/sessions"
    assert body["endpoints"]["diagnose_test_failure"] == "POST /v1/tests/diagnose"
    assert body["endpoints"]["edit_plan"] == "POST /v1/files/edit/plan"
    assert body["endpoints"]["edit_apply"] == "POST /v1/files/edit/apply"
    external_api = body["features"]["external_agent_api"]
    assert external_api["enabled"] is True
    assert external_api["protocol"] == "openai-compatible-chat-completions"
    assert external_api["authentication"]["type"] == "bearer_api_key_or_x_api_key"
    assert "Authorization: Bearer <api-key>" in external_api["authentication"]["headers"]
    assert external_api["authentication"]["issued_key_store"] == "BIBER_API_KEY_STORE_PATH"
    assert external_api["authentication"]["admin_key_management_api"] == "mvp"
    assert external_api["authentication"]["admin_key_management_ui"] == "mvp"
    assert external_api["authentication"]["per_user_key_issuance"] == "mvp"
    assert external_api["endpoints"]["chat_completions"] == "POST /v1/chat/completions"
    assert external_api["endpoints"]["admin_api_keys"] == "GET/POST/DELETE /v1/admin/api-keys"
    assert external_api["endpoints"]["admin_api_keys_console"] == "GET /admin/api-keys"
    assert external_api["provider_swappable"] is True
    assert external_api["local_gpu_model_source"] is True
    assert external_api["openai_mentor_optional"] is True
    assert external_api["openai_mentor_disabled_by_default"] is True
    assert external_api["streaming_supported"] is False
    assert external_api["domain_required_for_local_mvp"] is False
    assert external_api["public_https_required_for_external_internet_clients"] is True
    assert external_api["admin_api_key_required"] is True
    assert "custom_conversational_agent" in external_api["intended_clients"]
    assert "github_copilot_extension_or_agent_gateway" in external_api["intended_clients"]
    assert body["features"]["repo_context"]["max_files"] == 7
    assert body["features"]["repo_context"]["planner_supported"] is True
    assert body["features"]["repo_context"]["plan_endpoint"] == "POST /v1/repo/context/plan"
    assert body["features"]["repo_context"]["stack_profiles_supported"] is True
    stack_profiles = {
        profile["id"]: profile
        for profile in body["features"]["repo_context"]["stack_profiles"]
    }
    assert stack_profiles["dotnet"]["recommended_test_ids"] == ["dotnet-test"]
    assert "maven-test" in stack_profiles["java"]["recommended_test_ids"]
    assert body["features"]["workspace_edit"]["dry_run_supported"] is True
    assert body["features"]["workspace_edit"]["multi_file_plan_supported"] is True
    assert body["features"]["workspace_edit"]["multi_file_apply_supported"] is True
    assert body["features"]["workspace_edit"]["plan_hash_required"] is True
    assert body["features"]["workspace_edit"]["plan_endpoint"] == "POST /v1/files/edit/plan"
    assert body["features"]["workspace_edit"]["apply_endpoint"] == "POST /v1/files/edit/apply"
    assert body["features"]["test_runner"]["failure_diagnosis_supported"] is True
    assert "dotnet" in body["features"]["test_runner"]["diagnosis_stacks"]
    assert body["features"]["openai_mentor"]["configured"] is False
    assert body["features"]["runtime_profiles"]["enabled"] is False
    profile_ids = {
        profile["id"]
        for profile in body["features"]["runtime_profiles"]["available_profiles"]
    }
    assert "api-error-response" in profile_ids
    assert "rust-xriq-codegen" in profile_ids
    assert body["features"]["xriq_private_devnet"]["context_supported"] is True
    test_ids = {
        command["test_id"]
        for command in body["features"]["test_runner"]["commands"]
    }
    assert "python-compileall-api" in test_ids
    assert "pytest-test-diagnosis" in test_ids
    assert "dotnet-test" in test_ids
    assert "maven-test" in test_ids
    assert "gradle-test" in test_ids
    assert "gradle-wrapper-test" in test_ids
    assert "xriq-private-devnet-smoke" in test_ids
    presets = {preset["id"]: preset for preset in body["presets"]}
    xriq_template = presets["xriq_private_devnet_review"]["request_template"]
    assert xriq_template["language"] == "Rust"
    assert xriq_template["runtime_profile_ids"] == ["rust-xriq-codegen"]
    assert xriq_template["include_xriq_context"] is True
    assert xriq_template["test_id"] == "python-compileall-api"
    assert body["safety"]["arbitrary_shell_commands"] is False
    assert body["safety"]["credentials_returned"] is False
    assert "test-key" not in json.dumps(body)


def test_agent_capabilities_requires_api_key(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).get("/v1/agent/capabilities")
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 401


def test_openai_chat_completions_accepts_bearer_key_and_disables_mentor_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = make_settings(tmp_path)

    class FakeBiberChatService:
        last_request: ChatRequest | None = None

        def __init__(self, service_settings: BiberSettings) -> None:
            self.service_settings = service_settings

        async def generate(
            self,
            request: ChatRequest,
        ) -> tuple[str, str | None, dict[str, Any], str]:
            self.__class__.last_request = request
            return (
                "local model answer",
                None,
                {"usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}},
                request.model or "biber-dev-core-v1",
            )

    monkeypatch.setattr(main_module, "BiberChatService", FakeBiberChatService)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-key"},
            json={
                "model": "biber-dev-core-v1",
                "messages": [
                    {
                        "role": "user",
                        "content": "Review with OpenAI mentor: answer locally.",
                    }
                ],
                "max_tokens": 64,
            },
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["model"] == "biber-dev-core-v1"
    assert body["choices"][0]["message"] == {
        "role": "assistant",
        "content": "local model answer",
    }
    assert body["usage"]["total_tokens"] == 7
    assert body["biber"]["mentor_used"] is False
    assert body["biber"]["openai_mentor_disabled_by_default"] is True
    assert FakeBiberChatService.last_request is not None
    assert FakeBiberChatService.last_request.use_mentor is False
    assert FakeBiberChatService.last_request.task_type == "external_agent_chat"
    assert "test-key" not in json.dumps(body)


def test_openai_chat_completions_rejects_streaming_for_mvp(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/chat/completions",
            headers={"x-api-key": "test-key"},
            json={
                "model": "biber-dev-core-v1",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Streaming chat completions are not supported" in response.json()["detail"]
