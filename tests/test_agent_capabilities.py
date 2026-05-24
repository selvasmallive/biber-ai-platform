from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings


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
    assert body["endpoints"]["create_session"] == "POST /v1/agent/sessions"
    assert body["endpoints"]["diagnose_test_failure"] == "POST /v1/tests/diagnose"
    assert body["endpoints"]["edit_plan"] == "POST /v1/files/edit/plan"
    assert body["endpoints"]["edit_apply"] == "POST /v1/files/edit/apply"
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
