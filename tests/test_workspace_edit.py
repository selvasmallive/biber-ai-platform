from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import biber_api.main as main_module
from biber_api.config import BiberSettings
from biber_api.workspace_edit import (
    WorkspaceEditError,
    apply_workspace_edit_plan,
    apply_workspace_edit,
    plan_workspace_edits,
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
        repo_context_root=str(workspace),
        workspace_edit_max_file_bytes=1000,
        workspace_edit_max_new_text_bytes=500,
    )


def test_workspace_edit_replaces_exact_text(tmp_path: Path) -> None:
    target = tmp_path / "src" / "example.py"
    target.parent.mkdir()
    target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    result = apply_workspace_edit(
        path="src/example.py",
        old_text="return a + b",
        new_text="return int(a) + int(b)",
        expected_replacements=1,
        create_if_missing=False,
        dry_run=False,
        settings=make_settings(tmp_path),
    )

    assert result["path"] == "src/example.py"
    assert result["changed"] is True
    assert result["replacements"] == 1
    assert target.read_text(encoding="utf-8") == "def add(a, b):\n    return int(a) + int(b)\n"


def test_workspace_edit_dry_run_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("old value\n", encoding="utf-8")

    result = apply_workspace_edit(
        path="README.md",
        old_text="old value",
        new_text="new value",
        expected_replacements=1,
        create_if_missing=False,
        dry_run=True,
        settings=make_settings(tmp_path),
    )

    assert result["dry_run"] is True
    assert result["changed"] is True
    assert target.read_text(encoding="utf-8") == "old value\n"


def test_workspace_edit_creates_file_when_explicitly_enabled(tmp_path: Path) -> None:
    result = apply_workspace_edit(
        path="generated/example.txt",
        old_text=None,
        new_text="created by BIBER\n",
        expected_replacements=1,
        create_if_missing=True,
        dry_run=False,
        settings=make_settings(tmp_path),
    )

    assert result["created"] is True
    assert result["replacements"] == 0
    assert (tmp_path / "generated" / "example.txt").read_text(encoding="utf-8") == (
        "created by BIBER\n"
    )


def test_workspace_edit_rejects_path_escape(tmp_path: Path) -> None:
    try:
        apply_workspace_edit(
            path="../outside.txt",
            old_text="old",
            new_text="new",
            expected_replacements=1,
            create_if_missing=False,
            dry_run=False,
            settings=make_settings(tmp_path),
        )
    except WorkspaceEditError as exc:
        assert "escapes the workspace" in str(exc)
    else:
        raise AssertionError("Expected path escape to be rejected")


def test_workspace_edit_rejects_secret_path(tmp_path: Path) -> None:
    try:
        apply_workspace_edit(
            path=".env",
            old_text=None,
            new_text="SECRET=value\n",
            expected_replacements=1,
            create_if_missing=True,
            dry_run=False,
            settings=make_settings(tmp_path),
        )
    except WorkspaceEditError as exc:
        assert "not allowed" in str(exc)
    else:
        raise AssertionError("Expected secret path to be rejected")


def test_workspace_edit_rejects_replacement_count_mismatch(tmp_path: Path) -> None:
    target = tmp_path / "notes.md"
    target.write_text("same same\n", encoding="utf-8")

    try:
        apply_workspace_edit(
            path="notes.md",
            old_text="same",
            new_text="changed",
            expected_replacements=1,
            create_if_missing=False,
            dry_run=False,
            settings=make_settings(tmp_path),
        )
    except WorkspaceEditError as exc:
        assert "replacement count mismatch" in str(exc)
    else:
        raise AssertionError("Expected replacement count mismatch to be rejected")


def test_workspace_edit_plan_validates_multiple_files_without_writing(
    tmp_path: Path,
) -> None:
    target = tmp_path / "src" / "example.py"
    target.parent.mkdir()
    target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    plan = plan_workspace_edits(
        edits=[
            {
                "path": "src/example.py",
                "old_text": "return a + b",
                "new_text": "return int(a) + int(b)",
                "expected_replacements": 1,
            },
            {
                "path": "generated/notes.md",
                "new_text": "planned note\n",
                "create_if_missing": True,
            },
        ],
        settings=make_settings(tmp_path),
        max_files=4,
    )

    assert plan["ok"] is True
    assert len(plan["plan_hash"]) == 64
    assert plan["files_touched"] == 2
    assert plan["rejected"] == []
    assert [item["path"] for item in plan["planned"]] == [
        "src/example.py",
        "generated/notes.md",
    ]
    assert plan["planned"][0]["operation"] == "replace"
    assert plan["planned"][1]["operation"] == "create"
    assert plan["planned"][1]["risk_level"] == "medium"
    assert target.read_text(encoding="utf-8") == "def add(a, b):\n    return a + b\n"
    assert not (tmp_path / "generated" / "notes.md").exists()


def test_workspace_edit_apply_requires_matching_plan_hash(tmp_path: Path) -> None:
    target = tmp_path / "src" / "example.py"
    target.parent.mkdir()
    target.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    edits = [
        {
            "path": "src/example.py",
            "old_text": "return a + b",
            "new_text": "return int(a) + int(b)",
            "expected_replacements": 1,
        },
        {
            "path": "generated/notes.md",
            "new_text": "applied note\n",
            "create_if_missing": True,
        },
    ]
    settings = make_settings(tmp_path)
    plan = plan_workspace_edits(edits=edits, settings=settings, max_files=4)

    result = apply_workspace_edit_plan(
        edits=edits,
        expected_plan_hash=plan["plan_hash"],
        settings=settings,
        max_files=4,
    )

    assert result["ok"] is True
    assert result["plan_hash"] == plan["plan_hash"]
    assert result["files_touched"] == 2
    assert target.read_text(encoding="utf-8") == (
        "def add(a, b):\n    return int(a) + int(b)\n"
    )
    assert (tmp_path / "generated" / "notes.md").read_text(encoding="utf-8") == (
        "applied note\n"
    )


def test_workspace_edit_apply_rejects_stale_plan_hash(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("before\n", encoding="utf-8")
    settings = make_settings(tmp_path)
    edits = [
        {
            "path": "README.md",
            "old_text": "before",
            "new_text": "after",
            "expected_replacements": 1,
        }
    ]
    plan = plan_workspace_edits(edits=edits, settings=settings, max_files=4)
    target.write_text("changed by user\n", encoding="utf-8")

    try:
        apply_workspace_edit_plan(
            edits=edits,
            expected_plan_hash=plan["plan_hash"],
            settings=settings,
            max_files=4,
        )
    except WorkspaceEditError as exc:
        assert "plan hash mismatch" in str(exc)
    else:
        raise AssertionError("Expected stale plan hash to be rejected")

    assert target.read_text(encoding="utf-8") == "changed by user\n"


def test_workspace_edit_plan_reports_rejected_edits(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("same same\n", encoding="utf-8")

    plan = plan_workspace_edits(
        edits=[
            {
                "path": "README.md",
                "old_text": "same",
                "new_text": "changed",
                "expected_replacements": 1,
            },
            {
                "path": ".env",
                "new_text": "SECRET=value\n",
                "create_if_missing": True,
            },
        ],
        settings=make_settings(tmp_path),
        max_files=4,
    )

    assert plan["ok"] is False
    assert plan["planned"] == []
    assert len(plan["rejected"]) == 2
    assert "replacement count mismatch" in plan["rejected"][0]["error"]
    assert "not allowed" in plan["rejected"][1]["error"]


def test_workspace_edit_endpoint_applies_change(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "note.md"
    target.parent.mkdir()
    target.write_text("before\n", encoding="utf-8")
    settings = make_settings(tmp_path)

    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/files/edit",
            json={
                "path": "docs/note.md",
                "old_text": "before",
                "new_text": "after",
                "expected_replacements": 1,
            },
            headers={"x-api-key": "test-key"},
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["changed"] is True
    assert target.read_text(encoding="utf-8") == "after\n"


def test_workspace_edit_plan_endpoint_returns_preview(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "note.md"
    target.parent.mkdir()
    target.write_text("before\n", encoding="utf-8")
    settings = make_settings(tmp_path)

    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/files/edit/plan",
            json={
                "edits": [
                    {
                        "path": "docs/note.md",
                        "old_text": "before",
                        "new_text": "after",
                        "expected_replacements": 1,
                    }
                ]
            },
            headers={"x-api-key": "test-key"},
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert len(body["plan_hash"]) == 64
    assert body["planned"][0]["path"] == "docs/note.md"
    assert target.read_text(encoding="utf-8") == "before\n"


def test_workspace_edit_apply_endpoint_writes_matching_plan(tmp_path: Path) -> None:
    target = tmp_path / "docs" / "note.md"
    target.parent.mkdir()
    target.write_text("before\n", encoding="utf-8")
    settings = make_settings(tmp_path)
    edits = [
        {
            "path": "docs/note.md",
            "old_text": "before",
            "new_text": "after",
            "expected_replacements": 1,
        }
    ]
    plan = plan_workspace_edits(edits=edits, settings=settings, max_files=4)

    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/files/edit/apply",
            json={"edits": edits, "plan_hash": plan["plan_hash"], "max_files": 4},
            headers={"x-api-key": "test-key"},
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["plan_hash"] == plan["plan_hash"]
    assert body["applied"][0]["path"] == "docs/note.md"
    assert target.read_text(encoding="utf-8") == "after\n"


def test_workspace_edit_apply_endpoint_rejects_mismatched_hash(
    tmp_path: Path,
) -> None:
    target = tmp_path / "docs" / "note.md"
    target.parent.mkdir()
    target.write_text("before\n", encoding="utf-8")
    settings = make_settings(tmp_path)

    main_module.app.dependency_overrides[main_module.get_settings] = lambda: settings
    try:
        response = TestClient(main_module.app).post(
            "/v1/files/edit/apply",
            json={
                "edits": [
                    {
                        "path": "docs/note.md",
                        "old_text": "before",
                        "new_text": "after",
                        "expected_replacements": 1,
                    }
                ],
                "plan_hash": "0" * 64,
                "max_files": 4,
            },
            headers={"x-api-key": "test-key"},
        )
    finally:
        main_module.app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "plan hash mismatch" in response.json()["detail"]
    assert target.read_text(encoding="utf-8") == "before\n"
