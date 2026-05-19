from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import biber_agent_client as client  # noqa: E402


def sample_capabilities() -> dict[str, object]:
    return {
        "service": "biber-agent",
        "version": "mvp-v1",
        "default_model": "biber-dev-core-v1",
        "features": {
            "openai_mentor": {"configured": False},
            "xriq_private_devnet": {"context_supported": True},
            "test_runner": {
                "commands": [
                    {"test_id": "python-compileall-api"},
                    {"test_id": "xriq-private-devnet-smoke"},
                ]
            },
        },
        "presets": [
            {
                "id": "default_coding_session",
                "request_template": {
                    "model": "biber-dev-core-v1",
                    "task_type": "agent_session",
                    "use_mentor": False,
                    "include_xriq_context": False,
                    "test_id": "python-compileall-api",
                },
            },
            {
                "id": "xriq_private_devnet_review",
                "request_template": {
                    "model": "biber-dev-core-v1",
                    "language": "Rust",
                    "task_type": "xriq_private_devnet_review",
                    "use_mentor": False,
                    "include_xriq_context": True,
                    "test_id": "python-compileall-api",
                },
            },
        ],
    }


def test_build_url_encodes_query_values() -> None:
    url = client.build_url(
        "http://127.0.0.1:8000/",
        "/v1/agent/capabilities",
        {"preset": "xriq review", "skip": None},
    )

    assert url == "http://127.0.0.1:8000/v1/agent/capabilities?preset=xriq+review"


def test_format_capabilities_summary_includes_presets_and_tests() -> None:
    output = client.format_capabilities_summary(sample_capabilities())

    assert "BIBER agent capabilities" in output
    assert "default_model: biber-dev-core-v1" in output
    assert "default_coding_session" in output
    assert "xriq_private_devnet_review" in output
    assert "python-compileall-api" in output
    assert "xriq_context: True" in output
    assert "mentor_configured: False" in output


def test_build_session_payload_uses_discovered_preset() -> None:
    payload = client.build_session_payload(
        capabilities=sample_capabilities(),
        preset_id="xriq_private_devnet_review",
        instruction="Review the next XRIQ wallet step.",
        repo_context_paths=["README.md"],
        no_test=True,
        max_tokens=128,
    )

    assert payload["instruction"] == "Review the next XRIQ wallet step."
    assert payload["language"] == "Rust"
    assert payload["task_type"] == "xriq_private_devnet_review"
    assert payload["include_xriq_context"] is True
    assert payload["repo_context_paths"] == ["README.md"]
    assert payload["test_id"] is None
    assert payload["max_tokens"] == 128


def test_build_session_payload_allows_overrides() -> None:
    payload = client.build_session_payload(
        capabilities=sample_capabilities(),
        preset_id="default_coding_session",
        instruction="Plan a TypeScript change.",
        language="TypeScript",
        task_type="frontend_review",
        test_id="pytest-core",
        include_xriq_context=True,
    )

    assert payload["language"] == "TypeScript"
    assert payload["task_type"] == "frontend_review"
    assert payload["test_id"] == "pytest-core"
    assert payload["include_xriq_context"] is True


def test_format_session_summary_lists_steps() -> None:
    output = client.format_session_summary(
        {
            "id": "session-1",
            "model": "biber-dev-core-v1",
            "mentor_used": False,
            "artifact_path": "/workspace/outputs/agent-sessions/session-1.json",
            "steps": [{"name": "xriq_context"}, {"name": "chat"}],
        }
    )

    assert "BIBER agent session" in output
    assert "id: session-1" in output
    assert "steps: xriq_context, chat" in output


def test_format_session_list_summary_lists_recent_sessions() -> None:
    output = client.format_session_list_summary(
        {
            "sessions": [
                {
                    "id": "session-1",
                    "model": "biber-dev-core-v1",
                    "steps": ["chat"],
                    "artifact_path": "/workspace/outputs/agent-sessions/session-1.json",
                }
            ]
        }
    )

    assert "BIBER agent sessions (1)" in output
    assert "id=session-1" in output
    assert "steps=chat" in output


def test_build_repo_context_payload_omits_unset_values() -> None:
    payload = client.build_repo_context_payload(
        instruction="Fix API docs.",
        pinned_paths=["README.md"],
        changed_paths=None,
        max_files=4,
        max_scan_files=None,
    )

    assert payload == {
        "instruction": "Fix API docs.",
        "pinned_paths": ["README.md"],
        "max_files": 4,
    }


def test_format_repo_context_summary_lists_selected_paths_and_profiles() -> None:
    output = client.format_repo_context_summary(
        {
            "summary": "Detected python.",
            "selected_paths": ["README.md", "app/main.py"],
            "detected_project_types": ["python"],
            "stack_profiles": [{"id": "dotnet"}, {"id": "java"}],
        }
    )

    assert "BIBER repo context plan" in output
    assert "detected_project_types: python" in output
    assert "stack_profiles: dotnet, java" in output
    assert "- README.md" in output


def test_load_workspace_edits_accepts_json_values_and_file(tmp_path: Path) -> None:
    edits_file = tmp_path / "edits.json"
    edits_file.write_text(
        json.dumps(
            {
                "edits": [
                    {
                        "path": "docs/a.md",
                        "new_text": "a\n",
                        "create_if_missing": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    edits = client.load_workspace_edits(
        edit_json_values=[
            json.dumps(
                {
                    "path": "docs/b.md",
                    "new_text": "b\n",
                    "create_if_missing": True,
                }
            )
        ],
        edits_file=str(edits_file),
    )

    assert [edit["path"] for edit in edits] == ["docs/a.md", "docs/b.md"]


def test_build_workspace_edit_payload_includes_plan_hash_for_apply() -> None:
    payload = client.build_workspace_edit_payload(
        edits=[{"path": "docs/a.md", "new_text": "a\n", "create_if_missing": True}],
        max_files=2,
        plan_hash="a" * 64,
    )

    assert payload["max_files"] == 2
    assert payload["plan_hash"] == "a" * 64
    assert payload["edits"][0]["path"] == "docs/a.md"


def test_format_workspace_edit_plan_and_apply_summaries() -> None:
    plan_output = client.format_workspace_edit_plan_summary(
        {
            "ok": True,
            "plan_hash": "a" * 64,
            "summary": "Planned 1 edit.",
            "planned": [
                {
                    "path": "docs/a.md",
                    "operation": "create",
                    "risk_level": "medium",
                    "changed": True,
                }
            ],
            "rejected": [],
        }
    )
    apply_output = client.format_workspace_edit_apply_summary(
        {
            "ok": True,
            "plan_hash": "a" * 64,
            "summary": "Applied 1 workspace edit.",
            "applied": [{"path": "docs/a.md", "changed": True}],
        }
    )

    assert "BIBER workspace edit plan" in plan_output
    assert "docs/a.md operation=create" in plan_output
    assert "BIBER workspace edit apply" in apply_output
    assert "docs/a.md changed=True" in apply_output


def test_build_test_diagnosis_payload_accepts_command_json_and_files(tmp_path: Path) -> None:
    stdout_file = tmp_path / "stdout.txt"
    stdout_file.write_text("Example.cs(7,1): error CS1002: ; expected\n", encoding="utf-8")

    stdout = client.load_text_argument(
        value=None,
        file_path=str(stdout_file),
        label="--stdout",
    )
    payload = client.build_test_diagnosis_payload(
        test_id="dotnet-test",
        command_json=json.dumps(["dotnet", "test"]),
        command_parts=None,
        exit_code=1,
        timed_out=False,
        stdout=stdout,
        stderr="",
        max_context_lines=40,
    )

    assert payload == {
        "test_id": "dotnet-test",
        "command": ["dotnet", "test"],
        "exit_code": 1,
        "timed_out": False,
        "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
        "stderr": "",
        "max_context_lines": 40,
    }


def test_format_test_helpers_summarize_commands_runs_and_diagnosis() -> None:
    test_list = client.format_test_list_summary(
        {
            "commands": [
                {
                    "test_id": "python-compileall-api",
                    "label": "Python API compileall",
                    "cwd": "/workspace/biber-ai-platform",
                    "command": ["python", "-m", "compileall", "app", "src"],
                }
            ]
        }
    )
    run_output = client.format_test_run_summary(
        {
            "test_id": "python-compileall-api",
            "label": "Python API compileall",
            "executed": True,
            "ok": True,
            "exit_code": 0,
            "timed_out": False,
            "duration_ms": 42,
            "cwd": "/workspace/biber-ai-platform",
            "command": ["python", "-m", "compileall", "app", "src"],
        }
    )
    diagnosis_output = client.format_test_diagnosis_summary(
        {
            "has_failure": True,
            "primary_category": "compile_error",
            "detected_stack": "dotnet",
            "summary": "Detected compile_error in dotnet output with 1 signal.",
            "signals": [
                {
                    "category": "compile_error",
                    "stack": "dotnet",
                    "line_number": 1,
                    "evidence": "error CS1002",
                }
            ],
            "suggested_next_actions": ["Fix the reported compile error."],
        }
    )

    assert "BIBER allowlisted tests (1)" in test_list
    assert "python-compileall-api" in test_list
    assert "BIBER test run" in run_output
    assert "ok: True" in run_output
    assert "BIBER test failure diagnosis" in diagnosis_output
    assert "primary_category: compile_error" in diagnosis_output


def test_run_create_session_json_uses_client_workflow(monkeypatch) -> None:
    captured_payload: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        assert cli_api_key is None
        return "test-key"

    def fake_fetch_capabilities(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        assert base_url == "http://127.0.0.1:8000"
        assert api_key == "test-key"
        assert timeout_seconds == 180.0
        return sample_capabilities()

    def fake_create_agent_session(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        assert base_url == "http://127.0.0.1:8000"
        assert api_key == "test-key"
        assert timeout_seconds == 180.0
        captured_payload.update(payload)
        return {
            "id": "session-1",
            "model": payload["model"],
            "mentor_used": False,
            "steps": [{"name": "chat"}],
            "artifact_path": "/workspace/outputs/agent-sessions/session-1.json",
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "fetch_capabilities", fake_fetch_capabilities)
    monkeypatch.setattr(client, "create_agent_session", fake_create_agent_session)

    args = client.parse_args(
        [
            "--json",
            "create-session",
            "--preset",
            "default_coding_session",
            "--instruction",
            "Say ok.",
            "--repo-context",
            "README.md",
            "--no-test",
            "--max-tokens",
            "24",
        ]
    )

    output = client.run(args)

    assert captured_payload["instruction"] == "Say ok."
    assert captured_payload["repo_context_paths"] == ["README.md"]
    assert captured_payload["test_id"] is None
    assert captured_payload["max_tokens"] == 24
    assert json.loads(output)["id"] == "session-1"


def test_run_list_sessions_json_uses_client_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_fetch_capabilities(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        return sample_capabilities()

    def fake_list_agent_sessions(
        *,
        base_url: str,
        api_key: str,
        limit: int | None,
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "limit": limit,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "sessions": [
                {
                    "id": "session-1",
                    "model": "biber-dev-core-v1",
                    "steps": ["chat"],
                }
            ]
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "fetch_capabilities", fake_fetch_capabilities)
    monkeypatch.setattr(client, "list_agent_sessions", fake_list_agent_sessions)

    args = client.parse_args(["--json", "list-sessions", "--limit", "3"])

    output = client.run(args)

    assert captured["base_url"] == "http://127.0.0.1:8000"
    assert captured["api_key"] == "test-key"
    assert captured["limit"] == 3
    assert json.loads(output)["sessions"][0]["id"] == "session-1"


def test_run_get_session_json_uses_client_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_fetch_capabilities(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        return sample_capabilities()

    def fake_get_agent_session(
        *,
        base_url: str,
        api_key: str,
        session_id: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "session_id": session_id,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "id": session_id,
            "model": "biber-dev-core-v1",
            "mentor_used": False,
            "steps": [{"name": "chat"}],
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "fetch_capabilities", fake_fetch_capabilities)
    monkeypatch.setattr(client, "get_agent_session", fake_get_agent_session)

    args = client.parse_args(["--json", "get-session", "session-1"])

    output = client.run(args)

    assert captured["session_id"] == "session-1"
    assert json.loads(output)["id"] == "session-1"


def test_run_plan_context_json_uses_client_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_fetch_capabilities(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        raise AssertionError("plan-context should not fetch capabilities")

    def fake_plan_repo_context(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "selected_paths": ["README.md"],
            "detected_project_types": ["python"],
            "candidates": [],
            "skipped": [],
            "stack_profiles": [],
            "summary": "Detected python.",
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "fetch_capabilities", fake_fetch_capabilities)
    monkeypatch.setattr(client, "plan_repo_context", fake_plan_repo_context)

    args = client.parse_args(
        [
            "--json",
            "plan-context",
            "--instruction",
            "Plan docs update.",
            "--pinned-path",
            "README.md",
            "--changed-path",
            "docs/API_EXAMPLES.md",
            "--max-files",
            "4",
        ]
    )

    output = client.run(args)

    assert captured["base_url"] == "http://127.0.0.1:8000"
    assert captured["api_key"] == "test-key"
    assert captured["payload"] == {
        "instruction": "Plan docs update.",
        "pinned_paths": ["README.md"],
        "changed_paths": ["docs/API_EXAMPLES.md"],
        "max_files": 4,
    }
    assert json.loads(output)["selected_paths"] == ["README.md"]


def test_run_plan_edit_json_uses_client_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_plan_workspace_edit(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "ok": True,
            "plan_hash": "b" * 64,
            "planned": [{"path": "docs/a.md"}],
            "rejected": [],
            "files_touched": 1,
            "summary": "Planned 1 edit.",
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "plan_workspace_edit", fake_plan_workspace_edit)

    edit_json = json.dumps(
        {"path": "docs/a.md", "new_text": "a\n", "create_if_missing": True}
    )
    args = client.parse_args(["--json", "plan-edit", "--edit-json", edit_json])

    output = client.run(args)

    assert captured["payload"] == {
        "edits": [{"path": "docs/a.md", "new_text": "a\n", "create_if_missing": True}]
    }
    assert json.loads(output)["plan_hash"] == "b" * 64


def test_run_apply_edit_json_requires_plan_hash_and_uses_client_workflow(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_apply_workspace_edit_plan(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "ok": True,
            "plan_hash": "c" * 64,
            "applied": [{"path": "docs/a.md", "changed": True}],
            "files_touched": 1,
            "summary": "Applied 1 workspace edit.",
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "apply_workspace_edit_plan", fake_apply_workspace_edit_plan)

    edit_json = json.dumps(
        {"path": "docs/a.md", "new_text": "a\n", "create_if_missing": True}
    )
    args = client.parse_args(
        [
            "--json",
            "apply-edit",
            "--edit-json",
            edit_json,
            "--plan-hash",
            "c" * 64,
            "--max-files",
            "2",
        ]
    )

    output = client.run(args)

    assert captured["payload"] == {
        "edits": [{"path": "docs/a.md", "new_text": "a\n", "create_if_missing": True}],
        "max_files": 2,
        "plan_hash": "c" * 64,
    }
    assert json.loads(output)["applied"][0]["path"] == "docs/a.md"


def test_run_list_tests_json_uses_client_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_list_test_commands(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"commands": [{"test_id": "python-compileall-api"}]}

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "list_test_commands", fake_list_test_commands)

    args = client.parse_args(["--json", "list-tests"])

    output = client.run(args)

    assert captured["base_url"] == "http://127.0.0.1:8000"
    assert json.loads(output)["commands"][0]["test_id"] == "python-compileall-api"


def test_run_test_json_can_attach_diagnosis_on_failure(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_run_allowlisted_test(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["run_payload"] = payload
        return {
            "test_id": "dotnet-test",
            "label": ".NET test",
            "description": "Run dotnet test.",
            "cwd": "/workspace/repo",
            "command": ["dotnet", "test", "--nologo"],
            "timeout_seconds": 300,
            "executed": True,
            "ok": False,
            "exit_code": 1,
            "timed_out": False,
            "duration_ms": 10,
            "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
            "stderr": "",
            "stdout_truncated": False,
            "stderr_truncated": False,
        }

    def fake_diagnose_test_failure(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["diagnosis_payload"] = payload
        return {
            "has_failure": True,
            "primary_category": "compile_error",
            "detected_stack": "dotnet",
            "signals": [],
            "relevant_output": "Example.cs(7,1): error CS1002: ; expected",
            "suggested_next_actions": [],
            "summary": "Detected compile_error in dotnet output with 1 signal.",
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "run_allowlisted_test", fake_run_allowlisted_test)
    monkeypatch.setattr(client, "diagnose_test_failure", fake_diagnose_test_failure)

    args = client.parse_args(
        [
            "--json",
            "run-test",
            "--test-id",
            "dotnet-test",
            "--diagnose-on-failure",
            "--max-context-lines",
            "30",
        ]
    )

    output = client.run(args)

    assert captured["run_payload"] == {"test_id": "dotnet-test"}
    assert captured["diagnosis_payload"] == {
        "test_id": "dotnet-test",
        "command": ["dotnet", "test", "--nologo"],
        "exit_code": 1,
        "timed_out": False,
        "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
        "stderr": "",
        "max_context_lines": 30,
    }
    assert json.loads(output)["diagnosis"]["primary_category"] == "compile_error"


def test_run_diagnose_test_json_uses_client_workflow(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_diagnose_test_failure(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "has_failure": True,
            "primary_category": "compile_error",
            "detected_stack": "dotnet",
            "signals": [],
            "relevant_output": "Example.cs(7,1): error CS1002: ; expected",
            "suggested_next_actions": [],
            "summary": "Detected compile_error in dotnet output with 1 signal.",
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "diagnose_test_failure", fake_diagnose_test_failure)

    args = client.parse_args(
        [
            "--json",
            "diagnose-test",
            "--test-id",
            "dotnet-test",
            "--command-part",
            "dotnet",
            "--command-part",
            "test",
            "--exit-code",
            "1",
            "--stdout",
            "Example.cs(7,1): error CS1002: ; expected\n",
        ]
    )

    output = client.run(args)

    assert captured["payload"] == {
        "test_id": "dotnet-test",
        "command": ["dotnet", "test"],
        "exit_code": 1,
        "timed_out": False,
        "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
        "stderr": "",
    }
    assert json.loads(output)["detected_stack"] == "dotnet"
