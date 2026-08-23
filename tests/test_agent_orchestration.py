from __future__ import annotations

from pathlib import Path

from biber_api.config import BiberSettings
from biber_api.orchestration import plan_agent_orchestration


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


def test_agent_orchestration_plans_rag_context_edit_test_and_gates(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text(
        "def add(a, b):\n"
        "    return a - b\n",
        encoding="utf-8",
    )
    test = tmp_path / "tests" / "test_service.py"
    test.parent.mkdir()
    test.write_text("def test_add():\n    assert True\n", encoding="utf-8")

    plan = plan_agent_orchestration(
        settings=make_settings(tmp_path),
        instruction="Fix add service behavior and run tests",
        changed_paths=["src/service.py"],
        proposed_edits=[
            {
                "path": "src/service.py",
                "old_text": "return a - b",
                "new_text": "return a + b",
                "expected_replacements": 1,
            }
        ],
        test_id="python-compileall-api",
        max_context_files=6,
        max_rag_results=6,
    )

    assert plan["ok"] is True
    assert plan["safe_to_apply"] is False
    assert plan["repo_rag"]["selected_paths"][0] == "src/service.py"
    assert "tests/test_service.py" in plan["repo_context"]["selected_paths"]
    assert plan["edit_plan"]["ok"] is True
    assert len(plan["edit_plan"]["plan_hash"]) == 64
    assert plan["test_plan"]["test_id"] == "python-compileall-api"
    assert "human_review_edit_plan" in plan["required_gates"]
    assert "matching_plan_hash_before_apply" in plan["required_gates"]
    assert "openai_mentor_optional_and_disabled_by_default" in plan["required_gates"]
    assert [step["name"] for step in plan["workflow_steps"]] == [
        "repo_rag_search",
        "repo_context_plan",
        "model_edit_proposal",
        "workspace_edit_plan",
        "test_and_diagnose",
    ]


def test_agent_orchestration_blocks_rejected_edits(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("before\n", encoding="utf-8")

    plan = plan_agent_orchestration(
        settings=make_settings(tmp_path),
        instruction="Try to write a secret file",
        proposed_edits=[
            {
                "path": ".env",
                "new_text": "SECRET=value\n",
                "create_if_missing": True,
            }
        ],
        test_id=None,
    )

    assert plan["ok"] is False
    assert plan["hard_blockers"] == ["edit_plan_blocked"]
    assert plan["edit_plan"]["ok"] is False
    assert "not allowed" in plan["edit_plan"]["rejected"][0]["error"]
    assert "Fix rejected edits before calling apply." in plan["next_actions"]
