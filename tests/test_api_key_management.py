from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings


def make_settings(tmp_path: Path) -> BiberSettings:
    return BiberSettings(
        env="test",
        api_keys=("bootstrap-key",),
        admin_api_key="admin-key",
        api_key_store_path=str(tmp_path / "api-keys.json"),
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
        repo_context_root=str(tmp_path),
    )


def test_admin_can_issue_list_revoke_file_backed_api_key(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        client = TestClient(main_module.app)
        issued = client.post(
            "/v1/admin/api-keys",
            headers={"Authorization": "Bearer admin-key"},
            json={"user_id": "user-1", "label": "IDE agent"},
        )
        assert issued.status_code == 200
        issued_body = issued.json()
        api_key = issued_body["api_key"]
        key_id = issued_body["record"]["key_id"]
        assert api_key.startswith("biber_")
        assert issued_body["record"]["user_id"] == "user-1"
        assert issued_body["record"]["label"] == "IDE agent"
        assert issued_body["record"]["active"] is True

        store_text = Path(settings.api_key_store_path).read_text(encoding="utf-8")
        assert api_key not in store_text
        assert "key_hash" in store_text

        capabilities = client.get(
            "/v1/agent/capabilities",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert capabilities.status_code == 200

        listed = client.get(
            "/v1/admin/api-keys",
            headers={"Authorization": "Bearer admin-key"},
        )
        assert listed.status_code == 200
        listed_text = json.dumps(listed.json())
        assert key_id in listed_text
        assert api_key not in listed_text
        assert "key_hash" not in listed_text

        revoked = client.delete(
            f"/v1/admin/api-keys/{key_id}",
            headers={"Authorization": "Bearer admin-key"},
        )
        assert revoked.status_code == 200
        assert revoked.json()["record"]["active"] is False

        rejected = client.get(
            "/v1/agent/capabilities",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        assert rejected.status_code == 401
    finally:
        main_module.app.dependency_overrides.clear()


def test_admin_key_management_requires_admin_key(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        client = TestClient(main_module.app)
        missing = client.get("/v1/admin/api-keys")
        assert missing.status_code == 401

        normal_user = client.get(
            "/v1/admin/api-keys",
            headers={"Authorization": "Bearer bootstrap-key"},
        )
        assert normal_user.status_code == 401
    finally:
        main_module.app.dependency_overrides.clear()
