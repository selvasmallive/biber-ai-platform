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


def test_build_github_payloads_and_summaries() -> None:
    save_payload = client.build_github_save_payload(
        path="generated/example.ts",
        content="export const hello = () => 'biber';\n",
        owner="acme",
        repo="biber-generated",
        branch="biber/generated-example",
        base_branch="main",
        create_branch_if_missing=True,
        commit_message="Save generated BIBER example",
    )
    pr_payload = client.build_github_pull_request_payload(
        head="biber/generated-example",
        base="main",
        title="Save generated BIBER example",
        body="Generated by BIBER.",
        owner=None,
        repo=None,
        draft=True,
    )

    assert save_payload == {
        "target": {
            "path": "generated/example.ts",
            "owner": "acme",
            "repo": "biber-generated",
            "branch": "biber/generated-example",
            "base_branch": "main",
            "create_branch_if_missing": True,
            "commit_message": "Save generated BIBER example",
        },
        "content": "export const hello = () => 'biber';\n",
    }
    assert pr_payload == {
        "head": "biber/generated-example",
        "base": "main",
        "title": "Save generated BIBER example",
        "body": "Generated by BIBER.",
        "draft": True,
    }
    assert "https://github.com/acme/repo/blob/main/generated/example.ts" in (
        client.format_github_save_summary(
            {"url": "https://github.com/acme/repo/blob/main/generated/example.ts"}
        )
    )
    assert "number: 42" in client.format_github_pull_request_summary(
        {"url": "https://github.com/acme/repo/pull/42", "number": 42}
    )


def test_format_mvp_loop_summary_lists_steps_and_results() -> None:
    output = client.format_mvp_loop_summary(
        {
            "ok": False,
            "selected_context_paths": ["README.md"],
            "edit_plan_hash": "a" * 64,
            "test_ok": False,
            "diagnosis_summary": "Detected compile_error in dotnet output.",
            "github_url": "https://github.com/acme/repo/blob/main/generated/a.txt",
            "pull_request_url": "https://github.com/acme/repo/pull/42",
            "artifact_path": "/workspace/outputs/biber-mvp-loop.json",
            "steps": {
                "context_plan": {},
                "edit_plan": {},
                "test_run": {},
                "test_diagnosis": {},
                "github_save": {},
                "github_pull_request": {},
            },
        }
    )

    assert "BIBER MVP loop" in output
    assert "ok: False" in output
    assert "selected_context_paths: 1" in output
    assert "test_ok: False" in output
    assert "pull_request_url: https://github.com/acme/repo/pull/42" in output
    assert "artifact_path: /workspace/outputs/biber-mvp-loop.json" in output


def test_run_show_mvp_loop_summarizes_local_artifact_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("show-mvp-loop should not resolve an API key")

    artifact = tmp_path / "mvp-loop.json"
    artifact.write_text(
        json.dumps(
            {
                "ok": True,
                "artifact_path": str(artifact),
                "selected_context_paths": ["README.md", "pyproject.toml"],
                "steps": {
                    "context_plan": {"summary": "Selected repo context."},
                    "test_run": {
                        "ok": True,
                        "test_id": "python-compileall-api",
                        "summary": "Test passed.",
                    },
                },
                "test_ok": True,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(client.parse_args(["show-mvp-loop", str(artifact)]))

    assert "BIBER MVP loop" in output
    assert "ok: True" in output
    assert "selected_context_paths:" in output
    assert "- README.md" in output
    assert "step_summaries:" in output
    assert "- test_run ok=True summary=Test passed. test_id=python-compileall-api" in output


def test_run_show_mvp_loop_json_returns_local_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "mvp-loop.json"
    payload = {"ok": True, "steps": {"context_plan": {}}, "selected_context_paths": []}
    artifact.write_text(json.dumps(payload), encoding="utf-8")

    output = client.run(client.parse_args(["--json", "show-mvp-loop", str(artifact)]))

    assert json.loads(output) == payload


def test_run_list_mvp_loops_summarizes_local_artifacts_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("list-mvp-loops should not resolve an API key")

    direct = tmp_path / "biber-mvp-loop.json"
    direct.write_text(
        json.dumps(
            {
                "ok": True,
                "artifact_path": str(direct),
                "selected_context_paths": ["README.md"],
                "steps": {"context_plan": {}, "test_run": {"ok": True}},
                "test_ok": True,
            }
        ),
        encoding="utf-8",
    )
    wrapped = tmp_path / "nested" / "agent-client-mvp-loop.json"
    wrapped.parent.mkdir()
    wrapped.write_text(
        json.dumps(
            {
                "status": 0,
                "body": {
                    "ok": False,
                    "selected_context_paths": ["README.md", "pyproject.toml"],
                    "steps": {"context_plan": {}, "test_run": {"ok": False}},
                    "test_ok": False,
                },
            }
        ),
        encoding="utf-8",
    )
    noise = tmp_path / "agent-client-mvp-loop-report.json"
    noise.write_text(json.dumps({"status": 0, "body": "not a loop"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(client.parse_args(["list-mvp-loops", str(tmp_path)]))

    assert "BIBER MVP loop artifacts (2)" in output
    assert str(direct) in output
    assert str(wrapped) in output
    assert str(noise) not in output


def test_run_list_mvp_loops_json_returns_recent_artifacts(tmp_path: Path) -> None:
    direct = tmp_path / "biber-mvp-loop.json"
    direct.write_text(
        json.dumps({"ok": True, "steps": {"context_plan": {}}, "selected_context_paths": []}),
        encoding="utf-8",
    )

    output = client.run(
        client.parse_args(["--json", "list-mvp-loops", str(tmp_path), "--limit", "1"])
    )
    result = json.loads(output)

    assert result["directory"] == str(tmp_path)
    assert result["pattern"] == "*mvp-loop*.json"
    assert result["scanned"] == 1
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["path"] == str(direct)


def test_run_list_mvp_loops_failed_only_filters_successes(tmp_path: Path) -> None:
    success = tmp_path / "success-mvp-loop.json"
    success.write_text(
        json.dumps(
            {
                "ok": True,
                "steps": {"context_plan": {}, "test_run": {"ok": True}},
                "selected_context_paths": ["README.md"],
                "test_ok": True,
            }
        ),
        encoding="utf-8",
    )
    failure = tmp_path / "failure-mvp-loop.json"
    failure.write_text(
        json.dumps(
            {
                "ok": False,
                "steps": {"context_plan": {}, "test_run": {"ok": False}},
                "selected_context_paths": ["README.md"],
                "test_ok": False,
            }
        ),
        encoding="utf-8",
    )

    output = client.run(
        client.parse_args(["--json", "list-mvp-loops", str(tmp_path), "--failed-only"])
    )
    result = json.loads(output)

    assert result["failed_only"] is True
    assert result["scanned"] == 2
    assert [item["path"] for item in result["artifacts"]] == [str(failure)]


def test_run_export_mvp_failures_writes_review_jsonl_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("export-mvp-failures should not resolve an API key")

    success = tmp_path / "success-mvp-loop.json"
    success.write_text(
        json.dumps(
            {
                "ok": True,
                "steps": {"context_plan": {}, "test_run": {"ok": True}},
                "selected_context_paths": ["README.md"],
                "test_ok": True,
            }
        ),
        encoding="utf-8",
    )
    failure = tmp_path / "failure-mvp-loop.json"
    failure.write_text(
        json.dumps(
            {
                "ok": False,
                "diagnosis_summary": "Detected compile_error in dotnet output.",
                "steps": {
                    "context_plan": {},
                    "test_run": {
                        "ok": False,
                        "test_id": "dotnet-test",
                        "exit_code": 1,
                        "timed_out": False,
                        "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
                    },
                    "test_diagnosis": {
                        "primary_category": "compile_error",
                        "detected_stack": "dotnet",
                        "summary": "Detected compile_error in dotnet output.",
                    },
                },
                "selected_context_paths": ["README.md", "src/App.cs"],
                "test_ok": False,
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "mvp-loop-failures.jsonl"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-mvp-failures",
                str(tmp_path),
                "--output",
                str(output_path),
            ]
        )
    )
    summary = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert summary["records"] == 1
    assert summary["training_allowed"] is False
    assert rows[0]["source"] == "biber_mvp_loop_failure"
    assert rows[0]["review_status"] == "needs_review"
    assert rows[0]["training_allowed"] is False
    assert rows[0]["source_artifact"] == str(failure)
    assert rows[0]["failure"]["test_id"] == "dotnet-test"
    assert rows[0]["failure"]["primary_category"] == "compile_error"
    assert rows[0]["selected_context_paths"] == ["README.md", "src/App.cs"]


def test_build_mvp_loop_repair_request_extracts_failure_context(tmp_path: Path) -> None:
    artifact = tmp_path / "failure-mvp-loop.json"
    payload = {
        "ok": False,
        "instruction": "Fix the API compile error.",
        "diagnosis_summary": "Detected compile_error in dotnet output.",
        "steps": {
            "context_plan": {},
            "test_run": {
                "ok": False,
                "test_id": "dotnet-test",
                "command": ["dotnet", "test"],
                "exit_code": 1,
                "timed_out": False,
                "stdout": "before\nExample.cs(7,1): error CS1002: ; expected\n",
            },
            "test_diagnosis": {
                "primary_category": "compile_error",
                "detected_stack": "dotnet",
                "summary": "Detected compile_error in dotnet output.",
                "relevant_output": "Example.cs(7,1): error CS1002: ; expected\n",
                "suggested_next_actions": ["Fix compiler diagnostics first."],
            },
        },
        "selected_context_paths": ["README.md", "src/App.cs", "tests/AppTests.cs"],
        "test_ok": False,
    }

    repair = client.build_mvp_loop_repair_request(
        path=artifact,
        payload=payload,
        instruction=None,
        max_relevant_output_chars=80,
        max_context_paths=2,
    )

    assert repair["source"] == "biber_mvp_loop_repair_request"
    assert repair["repair_status"] == "ready_for_local_model"
    assert repair["training_allowed"] is False
    assert repair["selected_context_paths"] == ["README.md", "src/App.cs"]
    assert repair["selected_context_paths_truncated"] is True
    assert repair["failure"]["test_id"] == "dotnet-test"
    assert repair["failure"]["primary_category"] == "compile_error"
    assert repair["failure"]["relevant_output"].endswith("; expected\n")
    assert "Fix the API compile error." in repair["repair_prompt"]
    assert "Fix compiler diagnostics first." in repair["repair_prompt"]
    assert repair["next_test_id"] == "dotnet-test"


def test_build_repair_chat_payload_uses_local_model_without_mentor() -> None:
    payload = client.build_repair_chat_payload(
        repair_request={
            "repair_prompt": "Fix the compile error.",
            "selected_context_paths": ["README.md", "src/App.cs"],
            "failure": {"detected_stack": "dotnet"},
        },
        model="biber-dev-core-v1",
        max_tokens=256,
        temperature=0.1,
        use_mentor=False,
    )

    assert payload == {
        "messages": [{"role": "user", "content": "Fix the compile error."}],
        "task_type": "mvp_loop_repair",
        "temperature": 0.1,
        "use_mentor": False,
        "repo_context_paths": ["README.md", "src/App.cs"],
        "language": "C#/.NET",
        "model": "biber-dev-core-v1",
        "max_tokens": 256,
    }


def test_run_prepare_repair_writes_request_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("prepare-repair should not resolve an API key")

    failure = tmp_path / "failure-mvp-loop.json"
    failure.write_text(
        json.dumps(
            {
                "ok": False,
                "instruction": "Fix a .NET compile error.",
                "diagnosis_summary": "Detected compile_error in dotnet output.",
                "steps": {
                    "context_plan": {},
                    "test_run": {
                        "ok": False,
                        "test_id": "dotnet-test",
                        "command": ["dotnet", "test"],
                        "exit_code": 1,
                        "timed_out": False,
                        "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
                    },
                    "test_diagnosis": {
                        "primary_category": "compile_error",
                        "detected_stack": "dotnet",
                        "summary": "Detected compile_error in dotnet output.",
                        "suggested_next_actions": ["Fix compiler diagnostics first."],
                    },
                },
                "selected_context_paths": ["README.md", "src/App.cs"],
                "test_ok": False,
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "repair-request.json"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "prepare-repair",
                str(failure),
                "--instruction",
                "Repair with the smallest safe edit.",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["artifact_path"] == str(output_path)
    assert result["source_artifact"] == str(failure)
    assert result["instruction"] == "Repair with the smallest safe edit."
    assert result["failure"]["detected_stack"] == "dotnet"
    assert result["training_allowed"] is False


def test_run_attempt_repair_calls_local_model_and_writes_artifact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        assert cli_api_key is None
        return "test-key"

    def fake_chat_with_biber(
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
            "id": "chat-1",
            "created_at": "2026-05-19T13:30:00+00:00",
            "model": "biber-dev-core-v1",
            "content": "Change src/App.cs to add the missing semicolon.",
            "mentor_used": False,
            "priority": 3,
        }

    failure = tmp_path / "failure-mvp-loop.json"
    failure.write_text(
        json.dumps(
            {
                "ok": False,
                "instruction": "Fix a .NET compile error.",
                "diagnosis_summary": "Detected compile_error in dotnet output.",
                "steps": {
                    "context_plan": {},
                    "test_run": {
                        "ok": False,
                        "test_id": "dotnet-test",
                        "command": ["dotnet", "test"],
                        "exit_code": 1,
                        "timed_out": False,
                        "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
                    },
                    "test_diagnosis": {
                        "primary_category": "compile_error",
                        "detected_stack": "dotnet",
                        "summary": "Detected compile_error in dotnet output.",
                        "suggested_next_actions": ["Fix compiler diagnostics first."],
                    },
                },
                "selected_context_paths": ["README.md", "src/App.cs"],
                "test_ok": False,
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "repair-attempt.json"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "chat_with_biber", fake_chat_with_biber)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "attempt-repair",
                str(failure),
                "--model",
                "biber-dev-core-v1",
                "--max-tokens",
                "128",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert captured["api_key"] == "test-key"
    assert captured["payload"]["use_mentor"] is False
    assert captured["payload"]["max_tokens"] == 128
    assert captured["payload"]["repo_context_paths"] == ["README.md", "src/App.cs"]
    assert result["repair_status"] == "model_repair_proposed"
    assert result["auto_applied"] is False
    assert result["training_allowed"] is False
    assert result["model_response"]["mentor_used"] is False
    assert result["repair_content"].startswith("Change src/App.cs")


def test_extract_repair_edits_accepts_json_edit_candidates(tmp_path: Path) -> None:
    attempt = {
        "source": "biber_mvp_loop_repair_attempt",
        "repair_status": "model_repair_proposed",
        "training_allowed": False,
        "auto_applied": False,
        "next_test_id": "dotnet-test",
        "repair_content": (
            "Use this edit:\n"
            '{"path":"src/App.cs","old_text":"return a","new_text":"return a;","expected_replacements":1}'
        ),
    }

    extraction = client.extract_repair_edits(
        path=tmp_path / "repair-attempt.json",
        payload=attempt,
        max_edits=3,
        max_files=2,
    )

    assert extraction["ok"] is True
    assert extraction["extraction_status"] == "ready_for_plan_edit"
    assert extraction["training_allowed"] is False
    assert extraction["auto_applied"] is False
    assert extraction["apply_allowed"] is False
    assert extraction["review_status"] == "needs_review"
    assert extraction["edits"] == [
        {
            "path": "src/App.cs",
            "old_text": "return a",
            "new_text": "return a;",
            "expected_replacements": 1,
        }
    ]
    assert extraction["plan_edit_payload"] == {
        "edits": extraction["edits"],
        "max_files": 2,
    }
    assert extraction["next_test_id"] == "dotnet-test"


def test_extract_repair_edits_rejects_unsafe_candidates(tmp_path: Path) -> None:
    attempt = {
        "source": "biber_mvp_loop_repair_attempt",
        "repair_content": json.dumps(
            {
                "edits": [
                    {"path": "../secret.txt", "new_text": "bad\n"},
                    {"path": "src/App.cs", "new_text": "ok\n", "extra": True},
                ]
            }
        ),
    }

    extraction = client.extract_repair_edits(
        path=tmp_path / "repair-attempt.json",
        payload=attempt,
        max_edits=3,
        max_files=None,
    )

    assert extraction["ok"] is False
    assert extraction["edits"] == []
    assert [item["reason"] for item in extraction["rejected"]] == [
        "unsafe_path",
        "unknown_keys",
    ]
    assert extraction["plan_edit_payload"] == {"edits": []}


def test_run_extract_repair_edits_writes_review_and_edits_files_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("extract-repair-edits should not resolve an API key")

    artifact = tmp_path / "repair-attempt.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_attempt",
                "repair_status": "model_repair_proposed",
                "training_allowed": False,
                "auto_applied": False,
                "repair_content": json.dumps(
                    {
                        "edits": [
                            {
                                "path": "src/App.cs",
                                "old_text": "return a",
                                "new_text": "return a;",
                                "expected_replacements": 1,
                            }
                        ]
                    }
                ),
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "repair-edit-extraction.json"
    edits_path = tmp_path / "repair-edits.json"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "extract-repair-edits",
                str(artifact),
                "--max-files",
                "2",
                "--output",
                str(output_path),
                "--edits-output",
                str(edits_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    edits_payload = json.loads(edits_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["artifact_path"] == str(output_path)
    assert result["edits_output"] == str(edits_path)
    assert result["extraction_status"] == "ready_for_plan_edit"
    assert edits_payload == result["plan_edit_payload"]
    assert edits_payload["edits"][0]["path"] == "src/App.cs"


def test_build_plan_repair_edits_payload_rejects_empty_edits() -> None:
    try:
        client.build_plan_repair_edits_payload(
            {"plan_edit_payload": {"edits": []}},
            max_files=None,
        )
    except client.BiberAgentClientError as exc:
        assert "at least one edit" in str(exc)
    else:
        raise AssertionError("expected empty repair edits to be rejected")


def test_run_plan_repair_edits_calls_server_plan_without_apply(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
            "plan_hash": "e" * 64,
            "planned": [{"path": "src/App.cs", "operation": "edit"}],
            "rejected": [],
            "files_touched": 1,
            "total_new_bytes": 10,
            "summary": "Planned 1 edit.",
        }

    artifact = tmp_path / "repair-edit-extraction.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_extraction",
                "extraction_status": "ready_for_plan_edit",
                "training_allowed": False,
                "auto_applied": False,
                "apply_allowed": False,
                "next_test_id": "dotnet-test",
                "plan_edit_payload": {
                    "edits": [
                        {
                            "path": "src/App.cs",
                            "old_text": "return a",
                            "new_text": "return a;",
                            "expected_replacements": 1,
                        }
                    ],
                    "max_files": 2,
                },
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "repair-edit-plan.json"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "plan_workspace_edit", fake_plan_workspace_edit)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "plan-repair-edits",
                str(artifact),
                "--max-files",
                "1",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert captured["api_key"] == "test-key"
    assert captured["payload"]["max_files"] == 1
    assert captured["payload"]["edits"][0]["path"] == "src/App.cs"
    assert result["source"] == "biber_mvp_loop_repair_edit_plan"
    assert result["plan_status"] == "planned"
    assert result["plan_hash"] == "e" * 64
    assert result["training_allowed"] is False
    assert result["auto_applied"] is False
    assert result["apply_allowed"] is False
    assert result["review_status"] == "needs_review"
    assert result["next_test_id"] == "dotnet-test"


def test_build_apply_repair_edits_payload_rejects_unplanned_artifact() -> None:
    try:
        client.build_apply_repair_edits_payload(
            {
                "source": "biber_mvp_loop_repair_edit_plan",
                "plan_status": "rejected",
                "ok": False,
                "plan_hash": "f" * 64,
                "plan_edit_payload": {
                    "edits": [
                        {
                            "path": "src/App.cs",
                            "old_text": "return a",
                            "new_text": "return a;",
                        }
                    ]
                },
            }
        )
    except client.BiberAgentClientError as exc:
        assert "successful repair edit plan" in str(exc)
    else:
        raise AssertionError("expected rejected repair edit plan to be rejected")


def test_run_apply_repair_edits_requires_explicit_approval(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("apply-repair-edits without --approve must not need API auth")

    artifact = tmp_path / "repair-edit-plan.json"
    artifact.write_text(
        json.dumps({"source": "biber_mvp_loop_repair_edit_plan"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    try:
        client.run(client.parse_args(["apply-repair-edits", str(artifact)]))
    except client.BiberAgentClientError as exc:
        assert "requires --approve" in str(exc)
    else:
        raise AssertionError("expected apply-repair-edits to require approval")


def test_run_apply_repair_edits_calls_server_apply_after_approval(
    monkeypatch,
    tmp_path: Path,
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
            "plan_hash": "f" * 64,
            "applied": [{"path": "src/App.cs", "changed": True}],
            "files_touched": 1,
            "summary": "Applied 1 workspace edit.",
        }

    artifact = tmp_path / "repair-edit-plan.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_plan",
                "plan_status": "planned",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "apply_allowed": False,
                "review_status": "needs_review",
                "plan_hash": "f" * 64,
                "next_test_id": "dotnet-test",
                "plan_edit_payload": {
                    "edits": [
                        {
                            "path": "src/App.cs",
                            "old_text": "return a",
                            "new_text": "return a;",
                            "expected_replacements": 1,
                        }
                    ],
                    "max_files": 2,
                },
                "edit_plan": {
                    "ok": True,
                    "plan_hash": "f" * 64,
                    "planned": [{"path": "src/App.cs", "operation": "edit"}],
                    "rejected": [],
                },
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "repair-edit-apply.json"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "apply_workspace_edit_plan", fake_apply_workspace_edit_plan)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "apply-repair-edits",
                str(artifact),
                "--approve",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert captured["api_key"] == "test-key"
    assert captured["payload"] == {
        "edits": [
            {
                "path": "src/App.cs",
                "old_text": "return a",
                "new_text": "return a;",
                "expected_replacements": 1,
            }
        ],
        "max_files": 2,
        "plan_hash": "f" * 64,
    }
    assert result["source"] == "biber_mvp_loop_repair_edit_apply"
    assert result["apply_status"] == "applied"
    assert result["ok"] is True
    assert result["training_allowed"] is False
    assert result["auto_applied"] is False
    assert result["approval_required"] is True
    assert result["approval_received"] is True
    assert result["apply_allowed"] is True
    assert result["review_status"] == "approved_apply_succeeded"
    assert result["next_test_id"] == "dotnet-test"


def test_build_verify_repair_edits_payload_requires_applied_artifact() -> None:
    try:
        client.build_verify_repair_edits_payload(
            {
                "source": "biber_mvp_loop_repair_edit_apply",
                "apply_status": "failed",
                "ok": False,
                "next_test_id": "dotnet-test",
            },
            test_id=None,
            dry_run=False,
        )
    except client.BiberAgentClientError as exc:
        assert "successful repair edit apply" in str(exc)
    else:
        raise AssertionError("expected failed repair apply artifact to be rejected")


def test_run_verify_repair_edits_uses_next_test_id_without_saving_or_training(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
        captured.update(
            {
                "base_url": base_url,
                "api_key": api_key,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {
            "test_id": payload["test_id"],
            "label": "Python compileall API",
            "executed": True,
            "ok": True,
            "exit_code": 0,
            "timed_out": False,
            "duration_ms": 42,
            "cwd": ".",
            "command": ["python", "-m", "compileall", "src"],
            "stdout": "",
            "stderr": "",
        }

    artifact = tmp_path / "repair-edit-apply.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_apply",
                "apply_status": "applied",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "auto_saved": False,
                "approval_received": True,
                "plan_hash": "f" * 64,
                "next_test_id": "python-compileall-api",
                "edit_apply": {
                    "ok": True,
                    "applied": [{"path": "src/App.cs", "changed": True}],
                },
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "repair-test-verification.json"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "run_allowlisted_test", fake_run_allowlisted_test)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "verify-repair-edits",
                str(artifact),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert captured["api_key"] == "test-key"
    assert captured["payload"] == {"test_id": "python-compileall-api"}
    assert result["source"] == "biber_mvp_loop_repair_test_verification"
    assert result["verification_status"] == "passed"
    assert result["ok"] is True
    assert result["training_allowed"] is False
    assert result["auto_applied"] is False
    assert result["auto_saved"] is False
    assert result["plan_hash"] == "f" * 64
    assert result["test_id"] == "python-compileall-api"
    assert result["test_run"]["ok"] is True


def test_run_verify_repair_edits_can_override_test_id_and_diagnose_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
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
            "test_id": payload["test_id"],
            "label": "dotnet test",
            "executed": True,
            "ok": False,
            "exit_code": 1,
            "timed_out": False,
            "duration_ms": 42,
            "cwd": ".",
            "command": ["dotnet", "test", "--nologo"],
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

    artifact = tmp_path / "repair-edit-apply.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_apply",
                "apply_status": "applied",
                "ok": True,
                "plan_hash": "f" * 64,
                "next_test_id": "python-compileall-api",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "run_allowlisted_test", fake_run_allowlisted_test)
    monkeypatch.setattr(client, "diagnose_test_failure", fake_diagnose_test_failure)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "verify-repair-edits",
                str(artifact),
                "--test-id",
                "dotnet-test",
                "--diagnose-on-failure",
                "--max-context-lines",
                "30",
            ]
        )
    )
    result = json.loads(output)

    assert captured["run_payload"] == {"test_id": "dotnet-test"}
    assert captured["diagnosis_payload"]["test_id"] == "dotnet-test"
    assert captured["diagnosis_payload"]["max_context_lines"] == 30
    assert result["verification_status"] == "failed"
    assert result["ok"] is False
    assert result["test_run"]["diagnosis"]["primary_category"] == "compile_error"


def test_build_verified_repair_review_record_rejects_failed_verification(
    tmp_path: Path,
) -> None:
    try:
        client.build_verified_repair_review_record(
            tmp_path / "repair-test-verification.json",
            {
                "source": "biber_mvp_loop_repair_test_verification",
                "verification_status": "failed",
                "ok": False,
            },
        )
    except client.BiberAgentClientError as exc:
        assert "passed repair verification" in str(exc)
    else:
        raise AssertionError("expected failed repair verification to be rejected")


def test_run_export_verified_repair_writes_review_jsonl_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("export-verified-repair should not resolve an API key")

    artifact = tmp_path / "repair-test-verification.json"
    apply_artifact = tmp_path / "repair-edit-apply.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_test_verification",
                "repair_loop_version": "mvp-v1",
                "source_artifact": str(apply_artifact),
                "verification_status": "passed",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "auto_saved": False,
                "plan_hash": "a" * 64,
                "test_id": "python-compileall-api",
                "test_run": {
                    "test_id": "python-compileall-api",
                    "label": "Python compileall API",
                    "executed": True,
                    "ok": True,
                    "exit_code": 0,
                    "timed_out": False,
                    "duration_ms": 12,
                    "cwd": ".",
                    "command": ["python", "-m", "compileall", "src"],
                    "stdout": "",
                    "stderr": "",
                },
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "verified-repairs.jsonl"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-verified-repair",
                str(artifact),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_verified_repair_export"
    assert result["records"] == 1
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["source_artifact"] == str(artifact)
    assert rows[0]["source"] == "biber_mvp_loop_verified_repair"
    assert rows[0]["review_status"] == "needs_human_review"
    assert rows[0]["quality"] == "needs_review"
    assert rows[0]["training_allowed"] is False
    assert rows[0]["eligible_for_training"] is False
    assert rows[0]["auto_promoted"] is False
    assert rows[0]["auto_saved"] is False
    assert rows[0]["source_artifact"] == str(artifact)
    assert rows[0]["repair_apply_artifact"] == str(apply_artifact)
    assert rows[0]["plan_hash"] == "a" * 64
    assert rows[0]["test_id"] == "python-compileall-api"
    assert rows[0]["verification"]["verification_status"] == "passed"
    assert rows[0]["test"]["command"] == ["python", "-m", "compileall", "src"]
    assert rows[0]["next_review_action"] == "human_review_before_eval_or_training"


def test_run_review_verified_repairs_summarizes_jsonl_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("review-verified-repairs should not resolve an API key")

    jsonl_path = tmp_path / "verified-repairs.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_verified_repair",
            "review_status": "needs_human_review",
            "quality": "needs_review",
            "training_allowed": False,
            "eligible_for_training": False,
            "auto_promoted": False,
            "auto_saved": False,
            "source_artifact": "repair-test-verification.json",
            "repair_apply_artifact": "repair-edit-apply.json",
            "plan_hash": "a" * 64,
            "test_id": "python-compileall-api",
            "verification": {
                "verification_status": "passed",
                "ok": True,
                "test_ok": True,
            },
            "test": {
                "command": ["python", "-m", "compileall", "src"],
                "relevant_output": "",
            },
        },
        {
            "source": "other_source",
            "test_id": "ignored",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    output_path = tmp_path / "verified-repair-review.json"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-verified-repairs",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_verified_repair_review"
    assert result["records"] == 1
    assert result["rejected_records"] == 1
    assert result["ready_for_human_review"] == 1
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["auto_promoted"] is False
    assert result["groups"] == [
        {
            "test_id": "python-compileall-api",
            "plan_hash": "a" * 64,
            "count": 1,
            "source_artifacts": ["repair-test-verification.json"],
            "review_statuses": ["needs_human_review"],
            "eligible_for_training": False,
        }
    ]
    assert result["rejected"][0]["reason"] == "unsupported_source"


def test_run_show_repair_chain_summarizes_ready_chain_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("show-repair-chain should not resolve an API key")

    plan_hash = "b" * 64
    mvp_loop_path = tmp_path / "mvp-loop.json"
    repair_path = tmp_path / "repair-request.json"
    attempt_path = tmp_path / "repair-attempt.json"
    extraction_path = tmp_path / "repair-extraction.json"
    plan_path = tmp_path / "repair-plan.json"
    apply_path = tmp_path / "repair-apply.json"
    verification_path = tmp_path / "repair-verification.json"
    review_jsonl_path = tmp_path / "verified-repairs.jsonl"
    review_summary_path = tmp_path / "verified-repair-review.json"
    output_path = tmp_path / "repair-chain.json"
    mvp_loop_path.write_text(
        json.dumps({"ok": False, "test_ok": False, "steps": {}}),
        encoding="utf-8",
    )
    repair_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_request",
                "repair_status": "ready_for_local_model",
                "training_allowed": False,
                "next_test_id": "python-compileall-api",
            }
        ),
        encoding="utf-8",
    )
    attempt_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_attempt",
                "repair_status": "model_repair_proposed",
                "training_allowed": False,
                "auto_applied": False,
            }
        ),
        encoding="utf-8",
    )
    extraction_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_extraction",
                "extraction_status": "ready_for_plan_edit",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
            }
        ),
        encoding="utf-8",
    )
    plan_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_plan",
                "plan_status": "planned",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "plan_hash": plan_hash,
            }
        ),
        encoding="utf-8",
    )
    apply_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_apply",
                "apply_status": "applied",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "auto_saved": False,
                "approval_received": True,
                "plan_hash": plan_hash,
                "next_test_id": "python-compileall-api",
            }
        ),
        encoding="utf-8",
    )
    verification_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_test_verification",
                "verification_status": "passed",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "auto_saved": False,
                "plan_hash": plan_hash,
                "test_id": "python-compileall-api",
            }
        ),
        encoding="utf-8",
    )
    review_jsonl_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_verified_repair",
                "review_status": "needs_human_review",
                "training_allowed": False,
                "eligible_for_training": False,
                "auto_saved": False,
                "plan_hash": plan_hash,
                "test_id": "python-compileall-api",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    review_summary_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_verified_repair_review",
                "records": 1,
                "ready_for_human_review": 1,
                "rejected_records": 0,
                "training_allowed": False,
                "eligible_for_training": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "show-repair-chain",
                "--mvp-loop",
                str(mvp_loop_path),
                "--repair",
                str(repair_path),
                "--attempt",
                str(attempt_path),
                "--extraction",
                str(extraction_path),
                "--plan",
                str(plan_path),
                "--apply",
                str(apply_path),
                "--verification",
                str(verification_path),
                "--review-jsonl",
                str(review_jsonl_path),
                "--review-summary",
                str(review_summary_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_summary"
    assert result["chain_status"] == "ready_for_human_review"
    assert result["ready_for_human_review"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["auto_saved"] is False
    assert result["auto_applied"] is False
    assert result["plan_hash"] == plan_hash
    assert result["plan_hash_consistent"] is True
    assert result["test_id"] == "python-compileall-api"
    assert result["statuses"]["verification_status"] == "passed"
    assert result["statuses"]["review_records"] == 1
    assert result["missing_artifacts"] == []
    assert result["next_action"] == "human_review_before_github_or_training"


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


def test_run_save_github_json_uses_client_workflow(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    content_file = tmp_path / "generated.txt"
    content_file.write_text("BIBER generated content\n", encoding="utf-8")

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_save_to_github(
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
        return {"url": "https://github.com/acme/biber/generated/example.txt"}

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "save_to_github", fake_save_to_github)

    args = client.parse_args(
        [
            "--json",
            "save-github",
            "--path",
            "generated/example.txt",
            "--content-file",
            str(content_file),
            "--owner",
            "acme",
            "--repo",
            "biber",
            "--branch",
            "biber/generated-example",
            "--base-branch",
            "main",
            "--create-branch-if-missing",
            "--commit-message",
            "Save generated example",
        ]
    )

    output = client.run(args)

    assert captured["payload"] == {
        "target": {
            "path": "generated/example.txt",
            "owner": "acme",
            "repo": "biber",
            "branch": "biber/generated-example",
            "base_branch": "main",
            "create_branch_if_missing": True,
            "commit_message": "Save generated example",
        },
        "content": "BIBER generated content\n",
    }
    assert json.loads(output)["url"].endswith("/generated/example.txt")


def test_run_create_pr_json_uses_client_workflow(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    body_file = tmp_path / "body.md"
    body_file.write_text("Generated by BIBER and ready for review.\n", encoding="utf-8")

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_create_github_pull_request(
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
        return {"url": "https://github.com/acme/biber/pull/42", "number": 42}

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(
        client,
        "create_github_pull_request",
        fake_create_github_pull_request,
    )

    args = client.parse_args(
        [
            "--json",
            "create-pr",
            "--head",
            "biber/generated-example",
            "--base",
            "main",
            "--title",
            "Save generated BIBER example",
            "--body-file",
            str(body_file),
            "--owner",
            "acme",
            "--repo",
            "biber",
            "--ready",
        ]
    )

    output = client.run(args)

    assert captured["payload"] == {
        "head": "biber/generated-example",
        "base": "main",
        "title": "Save generated BIBER example",
        "body": "Generated by BIBER and ready for review.\n",
        "owner": "acme",
        "repo": "biber",
        "draft": False,
    }
    assert json.loads(output)["number"] == 42


def test_run_mvp_loop_json_chains_safe_workflow(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    save_file = tmp_path / "save.txt"
    save_file.write_text("BIBER saved output\n", encoding="utf-8")
    pr_body_file = tmp_path / "pr-body.md"
    pr_body_file.write_text("Ready for review.\n", encoding="utf-8")

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_plan_repo_context(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["context_payload"] = payload
        return {
            "selected_paths": ["README.md"],
            "detected_project_types": ["python"],
            "candidates": [],
            "skipped": [],
            "stack_profiles": [],
            "summary": "Detected python.",
        }

    def fake_plan_workspace_edit(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["edit_plan_payload"] = payload
        return {
            "ok": True,
            "plan_hash": "d" * 64,
            "planned": [{"path": "generated/a.txt"}],
            "rejected": [],
            "files_touched": 1,
            "summary": "Planned 1 edit.",
        }

    def fake_apply_workspace_edit_plan(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["edit_apply_payload"] = payload
        return {
            "ok": True,
            "plan_hash": "d" * 64,
            "applied": [{"path": "generated/a.txt", "changed": True}],
            "files_touched": 1,
            "summary": "Applied 1 edit.",
        }

    def fake_run_allowlisted_test(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["test_payload"] = payload
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

    def fake_save_to_github(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["github_save_payload"] = payload
        return {"url": "https://github.com/acme/biber/blob/biber/loop/generated/a.txt"}

    def fake_create_github_pull_request(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["github_pr_payload"] = payload
        return {"url": "https://github.com/acme/biber/pull/42", "number": 42}

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "plan_repo_context", fake_plan_repo_context)
    monkeypatch.setattr(client, "plan_workspace_edit", fake_plan_workspace_edit)
    monkeypatch.setattr(client, "apply_workspace_edit_plan", fake_apply_workspace_edit_plan)
    monkeypatch.setattr(client, "run_allowlisted_test", fake_run_allowlisted_test)
    monkeypatch.setattr(client, "diagnose_test_failure", fake_diagnose_test_failure)
    monkeypatch.setattr(client, "save_to_github", fake_save_to_github)
    monkeypatch.setattr(
        client,
        "create_github_pull_request",
        fake_create_github_pull_request,
    )

    edit_json = json.dumps(
        {"path": "generated/a.txt", "new_text": "hello\n", "create_if_missing": True}
    )
    output_path = tmp_path / "artifacts" / "mvp-loop.json"
    args = client.parse_args(
        [
            "--json",
            "mvp-loop",
            "--instruction",
            "Fix a .NET compile error.",
            "--pinned-path",
            "README.md",
            "--changed-path",
            "src/App.cs",
            "--max-context-files",
            "4",
            "--edit-json",
            edit_json,
            "--apply-edits",
            "--max-edit-files",
            "2",
            "--test-id",
            "dotnet-test",
            "--max-context-lines",
            "30",
            "--save-github-path",
            "generated/a.txt",
            "--save-content-file",
            str(save_file),
            "--github-owner",
            "acme",
            "--github-repo",
            "biber",
            "--github-branch",
            "biber/loop",
            "--github-base-branch",
            "main",
            "--create-branch-if-missing",
            "--commit-message",
            "Save MVP loop output",
            "--create-pr",
            "--pr-title",
            "Save MVP loop output",
            "--pr-body-file",
            str(pr_body_file),
            "--output",
            str(output_path),
        ]
    )

    output = client.run(args)
    result = json.loads(output)

    assert result["ok"] is False
    assert result["artifact_path"] == str(output_path)
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
    assert result["selected_context_paths"] == ["README.md"]
    assert set(result["steps"]) == {
        "context_plan",
        "edit_plan",
        "edit_apply",
        "test_run",
        "test_diagnosis",
        "github_save",
        "github_pull_request",
    }
    assert captured["context_payload"] == {
        "instruction": "Fix a .NET compile error.",
        "pinned_paths": ["README.md"],
        "changed_paths": ["src/App.cs"],
        "max_files": 4,
    }
    assert captured["edit_apply_payload"] == {
        "edits": [{"path": "generated/a.txt", "new_text": "hello\n", "create_if_missing": True}],
        "max_files": 2,
        "plan_hash": "d" * 64,
    }
    assert captured["test_payload"] == {"test_id": "dotnet-test"}
    assert captured["diagnosis_payload"]["max_context_lines"] == 30
    assert captured["github_save_payload"]["content"] == "BIBER saved output\n"
    assert captured["github_pr_payload"] == {
        "head": "biber/loop",
        "base": "main",
        "title": "Save MVP loop output",
        "body": "Ready for review.\n",
        "owner": "acme",
        "repo": "biber",
        "draft": True,
    }
