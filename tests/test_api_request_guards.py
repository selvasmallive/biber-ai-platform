from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings
from biber_api.security import clear_api_request_guard_state


def make_settings(
    workspace: Path,
    *,
    max_request_bytes: int = 1048576,
    rate_limit_requests_per_minute: int = 120,
) -> BiberSettings:
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
        api_guard_enabled=True,
        api_max_request_bytes=max_request_bytes,
        api_rate_limit_requests_per_minute=rate_limit_requests_per_minute,
    )


def test_api_guard_rejects_oversized_v1_payload_before_route_parsing(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path, max_request_bytes=32)
    clear_api_request_guard_state()
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/tests/diagnose",
            headers={
                "x-api-key": "test-key",
                "content-type": "application/json",
            },
            content='{"stdout":"' + ("x" * 80) + '"}',
        )
    finally:
        main_module.app.dependency_overrides.clear()
        clear_api_request_guard_state()

    assert response.status_code == 413
    assert response.json()["detail"] == "BIBER API request body is too large."
    assert response.headers["x-biber-max-request-bytes"] == "32"
    assert "test-key" not in response.text


def test_api_guard_rate_limits_by_api_key_hash(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, rate_limit_requests_per_minute=2)
    clear_api_request_guard_state()
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        client = TestClient(main_module.app)
        headers = {"Authorization": "Bearer test-key"}
        first = client.get("/v1/agent/capabilities", headers=headers)
        second = client.get("/v1/agent/capabilities", headers=headers)
        third = client.get("/v1/agent/capabilities", headers=headers)
    finally:
        main_module.app.dependency_overrides.clear()
        clear_api_request_guard_state()

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["detail"] == "BIBER API request rate limit exceeded."
    assert third.headers["x-biber-ratelimit-limit"] == "2"
    assert int(third.headers["retry-after"]) >= 1
    assert "test-key" not in third.text


def test_api_guard_does_not_block_health_probe(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, rate_limit_requests_per_minute=1)
    clear_api_request_guard_state()
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        client = TestClient(main_module.app)
        responses = [client.get("/health") for _ in range(3)]
    finally:
        main_module.app.dependency_overrides.clear()
        clear_api_request_guard_state()

    assert [response.status_code for response in responses] == [200, 200, 200]
