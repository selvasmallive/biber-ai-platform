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
            "runtime_profiles": {
                "enabled": False,
                "available_profiles": [
                    {"id": "api-error-response"},
                    {"id": "rust-xriq-codegen"},
                ],
            },
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
                    "runtime_profile_ids": [],
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
                    "runtime_profile_ids": ["rust-xriq-codegen"],
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
    assert "runtime_profiles_enabled: False" in output
    assert "api-error-response" in output
    assert "rust-xriq-codegen" in output


def test_build_chat_payload_includes_runtime_profiles() -> None:
    payload = client.build_chat_payload(
        message="Return ok.",
        language="Rust",
        task_type="xriq_private_devnet_review",
        repo_context_paths=["README.md"],
        runtime_profile_ids=["rust-xriq-codegen"],
        max_tokens=32,
        temperature=0.1,
    )

    assert payload == {
        "messages": [{"role": "user", "content": "Return ok."}],
        "use_mentor": False,
        "language": "Rust",
        "task_type": "xriq_private_devnet_review",
        "repo_context_paths": ["README.md"],
        "runtime_profile_ids": ["rust-xriq-codegen"],
        "max_tokens": 32,
        "temperature": 0.1,
    }


def test_validate_runtime_profile_ids_rejects_unknown_ids() -> None:
    try:
        client.validate_runtime_profile_ids(
            capabilities=sample_capabilities(),
            runtime_profile_ids=["missing-profile"],
        )
    except client.BiberAgentClientError as exc:
        assert "Unknown runtime profile id" in str(exc)
    else:
        raise AssertionError("expected unknown runtime profile id to fail")


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
    assert payload["runtime_profile_ids"] == ["rust-xriq-codegen"]
    assert payload["test_id"] is None
    assert payload["max_tokens"] == 128


def test_build_session_payload_allows_overrides() -> None:
    payload = client.build_session_payload(
        capabilities=sample_capabilities(),
        preset_id="default_coding_session",
        instruction="Plan a TypeScript change.",
        language="TypeScript",
        task_type="frontend_review",
        runtime_profile_ids=["api-error-response"],
        test_id="pytest-core",
        include_xriq_context=True,
    )

    assert payload["language"] == "TypeScript"
    assert payload["task_type"] == "frontend_review"
    assert payload["runtime_profile_ids"] == ["api-error-response"]
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


def test_run_show_repair_attempt_summarizes_local_artifact_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("show-repair-attempt should not resolve an API key")

    artifact = tmp_path / "repair-attempt.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_attempt",
                "repair_status": "model_repair_proposed",
                "training_allowed": False,
                "auto_applied": False,
                "ready_for_edit_review": True,
                "source_artifact": "/workspace/outputs/failure-mvp-loop.json",
                "repair_request": {"repair_status": "ready_for_local_model"},
                "chat_request": {"runtime_profile_ids": ["rust-xriq-codegen"]},
                "model_response": {
                    "model": "biber-dev-core",
                    "mentor_used": False,
                },
                "repair_content": "Use the smallest safe edit.",
                "next_test_id": "cargo-test-workspace",
                "artifact_path": str(artifact),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(client.parse_args(["show-repair-attempt", str(artifact)]))

    assert "BIBER MVP loop repair attempt" in output
    assert "repair_status: model_repair_proposed" in output
    assert "training_allowed: False" in output
    assert "auto_applied: False" in output
    assert "model: biber-dev-core" in output
    assert "mentor_used: False" in output
    assert "runtime_profiles: rust-xriq-codegen" in output
    assert "repair_content_preview:" in output
    assert str(artifact) in output


def test_run_show_repair_attempt_json_returns_local_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "repair-attempt.json"
    payload = {
        "source": "biber_mvp_loop_repair_attempt",
        "repair_status": "model_repair_proposed",
        "training_allowed": False,
        "auto_applied": False,
        "model_response": {},
    }
    artifact.write_text(json.dumps({"body": payload}), encoding="utf-8")

    output = client.run(
        client.parse_args(["--json", "show-repair-attempt", str(artifact)])
    )

    assert json.loads(output) == payload


def test_run_list_repair_attempts_summarizes_local_artifacts_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("list-repair-attempts should not resolve an API key")

    ready = tmp_path / "agent-client-repair-attempt.json"
    ready.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_attempt",
                "repair_status": "model_repair_proposed",
                "training_allowed": False,
                "auto_applied": False,
                "ready_for_edit_review": True,
                "chat_request": {"runtime_profile_ids": ["rust-xriq-codegen"]},
                "model_response": {
                    "model": "biber-dev-core",
                    "mentor_used": False,
                },
                "next_test_id": "cargo-test-workspace",
            }
        ),
        encoding="utf-8",
    )
    ignored = tmp_path / "other-repair-attempt.json"
    ignored.write_text(json.dumps({"source": "other"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-repair-attempts",
                str(tmp_path),
                "--ready-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER repair attempt artifacts (1)" in output
    assert str(ready) in output
    assert str(ignored) not in output
    assert "runtime_profiles=rust-xriq-codegen" in output
    assert "training_allowed: False" in output


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


def test_build_mvp_loop_repair_request_keeps_runtime_profiles(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "failure-mvp-loop.json"
    payload = {
        "ok": False,
        "instruction": "Fix an XRIQ Rust validator failure.",
        "runtime_profile_ids": ["rust-xriq-codegen", "rust-xriq-codegen"],
        "steps": {
            "test_run": {
                "ok": False,
                "test_id": "cargo-test",
                "command": ["cargo", "test"],
                "exit_code": 1,
                "timed_out": False,
                "stdout": "error[E0502]: cannot borrow ledger as mutable\n",
            },
            "test_diagnosis": {
                "primary_category": "compile_error",
                "detected_stack": "rust",
                "summary": "Detected Rust borrow-checker error.",
                "suggested_next_actions": ["Fix the borrow before rerunning tests."],
            },
        },
        "selected_context_paths": ["xriq/crates/xriq-ledger/src/lib.rs"],
        "test_ok": False,
    }

    repair = client.build_mvp_loop_repair_request(
        path=artifact,
        payload=payload,
        instruction=None,
        max_relevant_output_chars=120,
        max_context_paths=None,
    )

    assert repair["runtime_profile_ids"] == ["rust-xriq-codegen"]
    assert "runtime_profiles: rust-xriq-codegen" in (
        client.format_mvp_loop_repair_request_summary(repair)
    )


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


def test_run_attempt_repair_inherits_mvp_loop_runtime_profiles(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_fetch_capabilities(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["capabilities_base_url"] = base_url
        return sample_capabilities()

    def fake_chat_with_biber(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["payload"] = payload
        return {
            "id": "chat-1",
            "model": "biber-dev-core-v1",
            "content": "Use a scoped immutable borrow before mutating.",
            "mentor_used": False,
        }

    failure = tmp_path / "failure-mvp-loop.json"
    failure.write_text(
        json.dumps(
            {
                "ok": False,
                "instruction": "Fix an XRIQ Rust validator failure.",
                "runtime_profile_ids": ["rust-xriq-codegen"],
                "steps": {
                    "test_run": {
                        "ok": False,
                        "test_id": "cargo-test",
                        "command": ["cargo", "test"],
                        "exit_code": 1,
                        "timed_out": False,
                        "stdout": "error[E0502]: cannot borrow ledger as mutable\n",
                    },
                    "test_diagnosis": {
                        "primary_category": "compile_error",
                        "detected_stack": "rust",
                        "summary": "Detected Rust borrow-checker error.",
                        "suggested_next_actions": [
                            "Fix the borrow before rerunning tests."
                        ],
                    },
                },
                "selected_context_paths": ["xriq/crates/xriq-ledger/src/lib.rs"],
                "test_ok": False,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "fetch_capabilities", fake_fetch_capabilities)
    monkeypatch.setattr(client, "chat_with_biber", fake_chat_with_biber)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "attempt-repair",
                str(failure),
                "--max-tokens",
                "128",
            ]
        )
    )
    result = json.loads(output)

    assert captured["capabilities_base_url"] == "http://127.0.0.1:8000"
    assert captured["payload"]["runtime_profile_ids"] == ["rust-xriq-codegen"]
    assert result["repair_request"]["runtime_profile_ids"] == ["rust-xriq-codegen"]
    assert result["chat_request"]["runtime_profile_ids"] == ["rust-xriq-codegen"]


def test_run_attempt_repair_accepts_prepared_repair_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_fetch_capabilities(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["capabilities_base_url"] = base_url
        return sample_capabilities()

    def fake_chat_with_biber(
        *,
        base_url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["payload"] = payload
        return {
            "id": "chat-1",
            "model": "biber-dev-core-v1",
            "content": "Prepared repair proposal.",
            "mentor_used": False,
        }

    repair_request = {
        "source": "biber_mvp_loop_repair_request",
        "repair_loop_version": "mvp-v1",
        "repair_status": "ready_for_local_model",
        "training_allowed": False,
        "source_artifact": "/workspace/outputs/failure-mvp-loop.json",
        "repair_prompt": "Fix the prepared Rust repair.",
        "selected_context_paths": ["xriq/crates/xriq-ledger/src/lib.rs"],
        "failure": {"detected_stack": "rust", "test_id": "cargo-test"},
        "next_test_id": "cargo-test",
        "runtime_profile_ids": ["rust-xriq-codegen"],
    }
    repair_path = tmp_path / "prepared-repair.json"
    repair_path.write_text(json.dumps(repair_request), encoding="utf-8")

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "fetch_capabilities", fake_fetch_capabilities)
    monkeypatch.setattr(client, "chat_with_biber", fake_chat_with_biber)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "attempt-repair",
                str(repair_path),
                "--max-tokens",
                "128",
            ]
        )
    )
    result = json.loads(output)

    assert captured["payload"]["messages"][0]["content"] == (
        "Fix the prepared Rust repair."
    )
    assert captured["payload"]["language"] == "Rust"
    assert captured["payload"]["runtime_profile_ids"] == ["rust-xriq-codegen"]
    assert result["repair_request"]["source_artifact"] == (
        "/workspace/outputs/failure-mvp-loop.json"
    )
    assert result["repair_content"] == "Prepared repair proposal."


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


def test_run_show_repair_edit_extraction_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("show-repair-edit-extraction should not resolve an API key")

    artifact = tmp_path / "repair-edit-extraction.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_extraction",
                "source_artifact": "/workspace/outputs/repair-attempt.json",
                "extraction_status": "ready_for_plan_edit",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "apply_allowed": False,
                "review_status": "needs_review",
                "edits": [{"path": "src/App.cs", "new_text": "return a;"}],
                "rejected": [{"reason": "unsafe_path"}],
                "json_values_found": 2,
                "next_test_id": "dotnet-test",
                "artifact_path": str(artifact),
                "edits_output": str(tmp_path / "repair-edits.json"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(["show-repair-edit-extraction", str(artifact)])
    )

    assert "BIBER repair edit extraction" in output
    assert "extraction_status: ready_for_plan_edit" in output
    assert "training_allowed: False" in output
    assert "auto_applied: False" in output
    assert "apply_allowed: False" in output
    assert "edits: 1" in output
    assert "rejected: 1" in output
    assert "- src/App.cs" in output
    assert str(artifact) in output


def test_run_show_repair_edit_extraction_json_returns_local_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "repair-edit-extraction.json"
    payload = {
        "source": "biber_mvp_loop_repair_edit_extraction",
        "extraction_status": "ready_for_plan_edit",
        "ok": True,
        "edits": [],
        "rejected": [],
    }
    artifact.write_text(json.dumps({"body": payload}), encoding="utf-8")

    output = client.run(
        client.parse_args(["--json", "show-repair-edit-extraction", str(artifact)])
    )

    assert json.loads(output) == payload


def test_run_list_repair_edit_extractions_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("list-repair-edit-extractions should not resolve an API key")

    ready = tmp_path / "agent-client-repair-edit-extraction.json"
    ready.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_extraction",
                "extraction_status": "ready_for_plan_edit",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "apply_allowed": False,
                "review_status": "needs_review",
                "edits": [{"path": "src/App.cs", "new_text": "return a;"}],
                "rejected": [],
                "json_values_found": 1,
                "next_test_id": "dotnet-test",
            }
        ),
        encoding="utf-8",
    )
    ignored = tmp_path / "ignored-repair-edit-extraction.json"
    ignored.write_text(json.dumps({"source": "other"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-repair-edit-extractions",
                str(tmp_path),
                "--ready-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER repair edit extraction artifacts (1)" in output
    assert str(ready) in output
    assert str(ignored) not in output
    assert "ready_for_plan_edit: 1" in output
    assert "training_allowed: False" in output
    assert "apply_allowed: False" in output


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


def test_run_show_repair_edit_plan_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("show-repair-edit-plan should not resolve an API key")

    artifact = tmp_path / "repair-edit-plan.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_plan",
                "source_artifact": "/workspace/outputs/repair-edit-extraction.json",
                "plan_status": "planned",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "apply_allowed": False,
                "review_status": "needs_review",
                "plan_hash": "f" * 64,
                "next_test_id": "dotnet-test",
                "artifact_path": str(artifact),
                "plan_edit_payload": {
                    "edits": [{"path": "src/App.cs", "new_text": "return a;"}]
                },
                "edit_plan": {
                    "ok": True,
                    "plan_hash": "f" * 64,
                    "planned": [{"path": "src/App.cs", "operation": "edit"}],
                    "rejected": [{"path": "src/Bad.cs", "reason": "missing_old_text"}],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(client.parse_args(["show-repair-edit-plan", str(artifact)]))

    assert "BIBER repair edit plan" in output
    assert "plan_status: planned" in output
    assert "training_allowed: False" in output
    assert "auto_applied: False" in output
    assert "apply_allowed: False" in output
    assert f"plan_hash: {'f' * 64}" in output
    assert "planned: 1" in output
    assert "rejected: 1" in output
    assert "- src/App.cs" in output
    assert str(artifact) in output


def test_run_show_repair_edit_plan_json_returns_local_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "repair-edit-plan.json"
    payload = {
        "source": "biber_mvp_loop_repair_edit_plan",
        "plan_status": "planned",
        "ok": True,
        "edit_plan": {},
    }
    artifact.write_text(json.dumps({"body": payload}), encoding="utf-8")

    output = client.run(
        client.parse_args(["--json", "show-repair-edit-plan", str(artifact)])
    )

    assert json.loads(output) == payload


def test_run_list_repair_edit_plans_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("list-repair-edit-plans should not resolve an API key")

    planned = tmp_path / "agent-client-repair-edit-plan.json"
    planned.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_plan",
                "plan_status": "planned",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "apply_allowed": False,
                "review_status": "needs_review",
                "plan_hash": "a" * 64,
                "next_test_id": "dotnet-test",
                "edit_plan": {
                    "planned": [{"path": "src/App.cs", "operation": "edit"}],
                    "rejected": [],
                },
            }
        ),
        encoding="utf-8",
    )
    ignored = tmp_path / "ignored-repair-edit-plan.json"
    ignored.write_text(json.dumps({"source": "other"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-repair-edit-plans",
                str(tmp_path),
                "--planned-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER repair edit plan artifacts (1)" in output
    assert str(planned) in output
    assert str(ignored) not in output
    assert "planned: 1" in output
    assert "training_allowed: False" in output
    assert "apply_allowed: False" in output
    assert f"plan_hash={'a' * 64}" in output


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


def test_run_show_repair_edit_apply_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("show-repair-edit-apply should not resolve an API key")

    artifact = tmp_path / "repair-edit-apply.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_apply",
                "source_artifact": "/workspace/outputs/repair-edit-plan.json",
                "apply_status": "applied",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "approval_required": True,
                "approval_received": True,
                "apply_allowed": True,
                "review_status": "approved_apply_succeeded",
                "plan_hash": "f" * 64,
                "next_test_id": "dotnet-test",
                "artifact_path": str(artifact),
                "edit_apply": {
                    "ok": True,
                    "plan_hash": "f" * 64,
                    "applied": [{"path": "src/App.cs", "changed": True}],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(client.parse_args(["show-repair-edit-apply", str(artifact)]))

    assert "BIBER repair edit apply" in output
    assert "apply_status: applied" in output
    assert "training_allowed: False" in output
    assert "auto_applied: False" in output
    assert "approval_required: True" in output
    assert "approval_received: True" in output
    assert f"plan_hash: {'f' * 64}" in output
    assert "applied: 1" in output
    assert "- src/App.cs changed=True" in output
    assert str(artifact) in output


def test_run_show_repair_edit_apply_json_returns_local_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "repair-edit-apply.json"
    payload = {
        "source": "biber_mvp_loop_repair_edit_apply",
        "apply_status": "applied",
        "ok": True,
        "edit_apply": {},
    }
    artifact.write_text(json.dumps({"body": payload}), encoding="utf-8")

    output = client.run(
        client.parse_args(["--json", "show-repair-edit-apply", str(artifact)])
    )

    assert json.loads(output) == payload


def test_run_list_repair_edit_applies_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("list-repair-edit-applies should not resolve an API key")

    applied = tmp_path / "agent-client-repair-edit-apply.json"
    applied.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_edit_apply",
                "apply_status": "applied",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "approval_required": True,
                "approval_received": True,
                "apply_allowed": True,
                "review_status": "approved_apply_succeeded",
                "plan_hash": "a" * 64,
                "next_test_id": "dotnet-test",
                "edit_apply": {
                    "applied": [{"path": "src/App.cs", "changed": True}],
                },
            }
        ),
        encoding="utf-8",
    )
    ignored = tmp_path / "ignored-repair-edit-apply.json"
    ignored.write_text(json.dumps({"source": "other"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-repair-edit-applies",
                str(tmp_path),
                "--applied-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER repair edit apply artifacts (1)" in output
    assert str(applied) in output
    assert str(ignored) not in output
    assert "applied: 1" in output
    assert "training_allowed: False" in output
    assert "auto_applied: False" in output
    assert "approval_received=True" in output
    assert f"plan_hash={'a' * 64}" in output


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


def test_run_show_repair_test_verification_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-repair-test-verification should not resolve an API key"
        )

    artifact = tmp_path / "repair-test-verification.json"
    artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_test_verification",
                "source_artifact": "/workspace/outputs/repair-edit-apply.json",
                "verification_status": "passed",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "auto_saved": False,
                "plan_hash": "f" * 64,
                "test_id": "python-compileall-api",
                "artifact_path": str(artifact),
                "test_run": {
                    "executed": True,
                    "ok": True,
                    "exit_code": 0,
                    "command": ["python", "-m", "compileall", "src"],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(["show-repair-test-verification", str(artifact)])
    )

    assert "BIBER repair test verification" in output
    assert "verification_status: passed" in output
    assert "training_allowed: False" in output
    assert "auto_applied: False" in output
    assert "auto_saved: False" in output
    assert f"plan_hash: {'f' * 64}" in output
    assert "test_id: python-compileall-api" in output
    assert "test_executed: True" in output
    assert "test_ok: True" in output
    assert str(artifact) in output


def test_run_show_repair_test_verification_json_returns_local_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "repair-test-verification.json"
    payload = {
        "source": "biber_mvp_loop_repair_test_verification",
        "verification_status": "passed",
        "ok": True,
        "test_run": {"executed": True, "ok": True},
    }
    artifact.write_text(json.dumps({"body": payload}), encoding="utf-8")

    output = client.run(
        client.parse_args(["--json", "show-repair-test-verification", str(artifact)])
    )

    assert json.loads(output) == payload


def test_run_list_repair_test_verifications_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-repair-test-verifications should not resolve an API key"
        )

    passed = tmp_path / "agent-client-repair-test-verification.json"
    passed.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_test_verification",
                "source_artifact": "/workspace/outputs/repair-edit-apply.json",
                "verification_status": "passed",
                "ok": True,
                "training_allowed": False,
                "auto_applied": False,
                "auto_saved": False,
                "plan_hash": "a" * 64,
                "test_id": "python-compileall-api",
                "test_run": {"executed": True, "ok": True},
            }
        ),
        encoding="utf-8",
    )
    ignored = tmp_path / "ignored-repair-test-verification.json"
    ignored.write_text(json.dumps({"source": "other"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-repair-test-verifications",
                str(tmp_path),
                "--passed-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER repair test verification artifacts (1)" in output
    assert str(passed) in output
    assert str(ignored) not in output
    assert "passed: 1" in output
    assert "training_allowed: False" in output
    assert "auto_applied: False" in output
    assert "auto_saved: False" in output
    assert "status=passed" in output
    assert "test_id=python-compileall-api" in output
    assert f"plan_hash={'a' * 64}" in output


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


def test_run_show_verified_repair_review_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-verified-repair-review should not resolve an API key"
        )

    artifact = tmp_path / "verified-repair-review.json"
    payload = {
        "source": "biber_mvp_loop_verified_repair_review",
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": [str(tmp_path / "verified-repairs.jsonl")],
        "records": 1,
        "rejected_records": 0,
        "ready_for_human_review": 1,
        "min_repeat": 1,
        "artifact_path": str(artifact),
        "groups": [
            {
                "test_id": "python-compileall-api",
                "plan_hash": "a" * 64,
                "count": 1,
            }
        ],
    }
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(["show-verified-repair-review", str(artifact)])
    )

    assert "BIBER verified repair review" in output
    assert "records: 1" in output
    assert "ready_for_human_review: 1" in output
    assert "review_status: needs_human_review" in output
    assert "training_allowed: False" in output
    assert "eligible_for_training: False" in output
    assert "test_id=python-compileall-api" in output
    assert f"plan_hash={'a' * 64}" in output
    assert str(artifact) in output


def test_run_show_verified_repair_review_json_returns_local_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "verified-repair-review.json"
    payload = {
        "source": "biber_mvp_loop_verified_repair_review",
        "review_status": "needs_human_review",
        "records": 1,
        "ready_for_human_review": 1,
        "groups": [],
    }
    artifact.write_text(json.dumps({"body": payload}), encoding="utf-8")

    output = client.run(
        client.parse_args(["--json", "show-verified-repair-review", str(artifact)])
    )

    assert json.loads(output) == payload


def test_run_list_verified_repair_reviews_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-verified-repair-reviews should not resolve an API key"
        )

    ready = tmp_path / "agent-client-verified-repair-review.json"
    ready.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_verified_repair_review",
                "review_status": "needs_human_review",
                "training_allowed": False,
                "eligible_for_training": False,
                "auto_promoted": False,
                "records": 1,
                "rejected_records": 0,
                "ready_for_human_review": 1,
                "min_repeat": 1,
                "groups": [
                    {
                        "test_id": "python-compileall-api",
                        "plan_hash": "a" * 64,
                        "count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    not_ready = tmp_path / "not-ready-verified-repair-review.json"
    not_ready.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_verified_repair_review",
                "review_status": "needs_human_review",
                "training_allowed": False,
                "eligible_for_training": False,
                "records": 0,
                "ready_for_human_review": 0,
                "groups": [],
            }
        ),
        encoding="utf-8",
    )
    ignored = tmp_path / "ignored-verified-repair-review.json"
    ignored.write_text(json.dumps({"source": "other"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-verified-repair-reviews",
                str(tmp_path),
                "--ready-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER verified repair review artifacts (1)" in output
    assert str(ready) in output
    assert str(not_ready) not in output
    assert str(ignored) not in output
    assert "ready_artifacts: 1" in output
    assert "records: 1" in output
    assert "ready_for_human_review: 1" in output
    assert "training_allowed: False" in output
    assert "eligible_for_training: False" in output
    assert "status=needs_human_review" in output
    assert "groups=1" in output


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


def test_run_list_repair_chains_filters_ready_artifacts_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("list-repair-chains should not resolve an API key")

    ready_path = tmp_path / "ready-repair-chain.json"
    incomplete_path = tmp_path / "incomplete-repair-chain.json"
    output_path = tmp_path / "repair-chain-list.json"
    ready_payload = {
        "source": "biber_mvp_loop_repair_chain_summary",
        "chain_status": "ready_for_human_review",
        "ready_for_human_review": True,
        "chain_complete": True,
        "verification_passed": True,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "plan_hash": "c" * 64,
        "test_id": "python-compileall-api",
        "statuses": {"review_records": 2},
        "next_action": "human_review_before_github_or_training",
    }
    ready_path.write_text(
        json.dumps({"status": 0, "body": ready_payload}),
        encoding="utf-8",
    )
    incomplete_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_summary",
                "chain_status": "incomplete_or_needs_repair",
                "ready_for_human_review": False,
                "chain_complete": False,
                "verification_passed": False,
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "statuses": {"review_records": 0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "list-repair-chains",
                str(tmp_path),
                "--ready-only",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_list"
    assert result["scanned"] == 2
    assert result["matched"] == 1
    assert result["ready_for_human_review"] == 1
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["artifacts"][0]["path"] == str(ready_path)
    assert result["artifacts"][0]["chain_status"] == "ready_for_human_review"
    assert result["artifacts"][0]["review_records"] == 2


def test_run_export_ready_repair_chains_writes_review_jsonl_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("export-ready-repair-chains should not resolve an API key")

    ready_path = tmp_path / "ready-repair-chain.json"
    incomplete_path = tmp_path / "incomplete-repair-chain.json"
    output_path = tmp_path / "ready-repair-chains.jsonl"
    ready_payload = {
        "source": "biber_mvp_loop_repair_chain_summary",
        "repair_loop_version": "mvp-v1",
        "chain_status": "ready_for_human_review",
        "ready_for_human_review": True,
        "chain_complete": True,
        "verification_passed": True,
        "plan_hash_consistent": True,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "plan_hash": "d" * 64,
        "test_id": "python-compileall-api",
        "statuses": {"review_records": 1},
        "artifacts": {
            "verification": "repair-verification.json",
            "review_jsonl": ["verified-repairs.jsonl"],
        },
    }
    ready_path.write_text(
        json.dumps({"status": 0, "body": ready_payload}),
        encoding="utf-8",
    )
    incomplete_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_summary",
                "chain_status": "incomplete_or_needs_repair",
                "ready_for_human_review": False,
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "statuses": {"review_records": 0},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-ready-repair-chains",
                str(tmp_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_export"
    assert result["scanned"] == 2
    assert result["records"] == 1
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_review"
    assert rows[0]["review_status"] == "needs_human_review"
    assert rows[0]["training_allowed"] is False
    assert rows[0]["eligible_for_training"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["source_artifact"] == str(ready_path)
    assert rows[0]["plan_hash"] == "d" * 64
    assert rows[0]["test_id"] == "python-compileall-api"
    assert rows[0]["chain"]["review_records"] == 1
    assert rows[0]["artifacts"]["verification"] == "repair-verification.json"
    assert rows[0]["next_review_action"] == (
        "human_review_repair_chain_before_github_or_training"
    )


def test_run_review_ready_repair_chains_summarizes_jsonl_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError("review-ready-repair-chains should not resolve an API key")

    jsonl_path = tmp_path / "ready-repair-chains.jsonl"
    output_path = tmp_path / "ready-repair-chain-review.json"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_review",
            "review_status": "needs_human_review",
            "quality": "needs_review",
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "auto_promoted": False,
            "auto_saved": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "e" * 64,
            "test_id": "python-compileall-api",
            "chain": {
                "chain_status": "ready_for_human_review",
                "chain_complete": True,
                "verification_passed": True,
                "review_records": 1,
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
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-ready-repair-chains",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_ready_repair_chain_review"
    assert result["records"] == 1
    assert result["rejected_records"] == 1
    assert result["ready_for_human_review"] == 1
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["auto_promoted"] is False
    assert result["groups"] == [
        {
            "test_id": "python-compileall-api",
            "plan_hash": "e" * 64,
            "count": 1,
            "source_artifacts": ["repair-chain.json"],
            "review_statuses": ["needs_human_review"],
            "safe_to_train": False,
            "github_save_ready": False,
        }
    ]
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert result["next_review_action"] == (
        "human_review_repeated_repair_chains_before_github_or_training"
    )


def test_run_show_ready_repair_chain_review_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-review should not resolve an API key"
        )

    artifact = tmp_path / "ready-repair-chain-review.json"
    payload = {
        "source": "biber_mvp_loop_ready_repair_chain_review",
        "review_status": "needs_human_review",
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "auto_promoted": False,
        "jsonl_paths": [str(tmp_path / "ready-repair-chains.jsonl")],
        "records": 1,
        "rejected_records": 0,
        "ready_for_human_review": 1,
        "min_repeat": 1,
        "artifact_path": str(artifact),
        "groups": [
            {
                "test_id": "python-compileall-api",
                "plan_hash": "e" * 64,
                "count": 1,
            }
        ],
    }
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(["show-ready-repair-chain-review", str(artifact)])
    )

    assert "BIBER ready repair-chain review" in output
    assert "records: 1" in output
    assert "ready_for_human_review: 1" in output
    assert "review_status: needs_human_review" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "test_id=python-compileall-api" in output
    assert f"plan_hash={'e' * 64}" in output
    assert str(artifact) in output


def test_run_show_ready_repair_chain_review_json_returns_local_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "ready-repair-chain-review.json"
    payload = {
        "source": "biber_mvp_loop_ready_repair_chain_review",
        "review_status": "needs_human_review",
        "records": 1,
        "ready_for_human_review": 1,
        "groups": [],
    }
    artifact.write_text(json.dumps({"body": payload}), encoding="utf-8")

    output = client.run(
        client.parse_args(["--json", "show-ready-repair-chain-review", str(artifact)])
    )

    assert json.loads(output) == payload


def test_run_list_ready_repair_chain_reviews_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-ready-repair-chain-reviews should not resolve an API key"
        )

    ready = tmp_path / "agent-client-ready-repair-chain-review.json"
    ready.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_review",
                "review_status": "needs_human_review",
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "auto_promoted": False,
                "records": 1,
                "rejected_records": 0,
                "ready_for_human_review": 1,
                "min_repeat": 1,
                "groups": [
                    {
                        "test_id": "python-compileall-api",
                        "plan_hash": "e" * 64,
                        "count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    not_ready = tmp_path / "not-ready-repair-chain-review.json"
    not_ready.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_review",
                "review_status": "needs_human_review",
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "records": 0,
                "ready_for_human_review": 0,
                "groups": [],
            }
        ),
        encoding="utf-8",
    )
    ignored = tmp_path / "ignored-ready-repair-chain-review.json"
    ignored.write_text(json.dumps({"source": "other"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-ready-repair-chain-reviews",
                str(tmp_path),
                "--ready-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER ready repair-chain review artifacts (1)" in output
    assert str(ready) in output
    assert str(not_ready) not in output
    assert str(ignored) not in output
    assert "ready_artifacts: 1" in output
    assert "records: 1" in output
    assert "ready_for_human_review: 1" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "status=needs_human_review" in output
    assert "groups=1" in output


def test_run_record_ready_repair_chain_decision_writes_jsonl_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "record-ready-repair-chain-decision should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chains.jsonl"
    output_path = tmp_path / "ready-repair-chain-decisions.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_review",
            "review_status": "needs_human_review",
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "f" * 64,
            "test_id": "python-compileall-api",
            "chain": {
                "chain_status": "ready_for_human_review",
                "chain_complete": True,
                "verification_passed": True,
                "review_records": 1,
            },
            "artifacts": {"verification": "repair-verification.json"},
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
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "record-ready-repair-chain-decision",
                str(jsonl_path),
                "--decision",
                "defer",
                "--reviewer",
                "human-reviewer",
                "--notes",
                "Needs target repo confirmation.",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_decision_export"
    assert result["decision"] == "defer"
    assert result["reviewer"] == "human-reviewer"
    assert result["records"] == 1
    assert result["rejected_records"] == 1
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_decision"
    assert rows[0]["decision_status"] == "recorded"
    assert rows[0]["decision"] == "defer"
    assert rows[0]["review_status"] == "human_defer"
    assert rows[0]["reviewer"] == "human-reviewer"
    assert rows[0]["notes"] == "Needs target repo confirmation."
    assert rows[0]["training_allowed"] is False
    assert rows[0]["eligible_for_training"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["approved_for_eval"] is False
    assert rows[0]["approved_for_training"] is False
    assert rows[0]["source_artifact"] == "repair-chain.json"
    assert rows[0]["artifacts"]["verification"] == "repair-verification.json"
    assert rows[0]["next_review_action"] == (
        "continue_human_review_before_github_or_training"
    )
    assert result["rejected"][0]["reason"] == "unsupported_source"


def test_run_review_ready_repair_chain_decisions_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-ready-repair-chain-decisions should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-decisions.jsonl"
    output_path = tmp_path / "ready-repair-chain-decision-review.json"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_decision",
            "decision_status": "recorded",
            "decision": "approve_for_eval",
            "review_status": "human_approve_for_eval",
            "reviewer": "human-reviewer",
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_eval": True,
            "approved_for_training": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "a" * 64,
            "test_id": "python-compileall-api",
        },
        {
            "source": "biber_mvp_loop_repair_chain_decision",
            "decision_status": "recorded",
            "decision": "defer",
            "review_status": "human_defer",
            "reviewer": "second-reviewer",
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_eval": False,
            "approved_for_training": False,
            "source_artifact": "repair-chain-2.json",
            "plan_hash": "b" * 64,
            "test_id": "rust-check",
        },
        {
            "source": "other_source",
            "decision": "ignored",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-ready-repair-chain-decisions",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_decision_review"
    assert result["records"] == 2
    assert result["rejected_records"] == 1
    assert result["decision_counts"] == {"approve_for_eval": 1, "defer": 1}
    assert result["defer_records"] == 1
    assert result["reject_records"] == 0
    assert result["approved_for_eval_records"] == 1
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["groups"][0]["decision"] == "approve_for_eval"
    assert result["groups"][0]["approved_for_training"] is False
    assert result["groups"][0]["safe_to_train"] is False
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert saved == result


def test_run_show_ready_repair_chain_decision_review_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-decision-review should not resolve an API key"
        )

    artifact = tmp_path / "ready-repair-chain-decision-review.json"
    payload = {
        "source": "biber_mvp_loop_ready_repair_chain_decision_review",
        "review_status": "decision_summary_only",
        "records": 1,
        "rejected_records": 0,
        "decision_counts": {"defer": 1},
        "defer_records": 1,
        "reject_records": 0,
        "approved_for_eval_records": 0,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifact_path": str(artifact),
        "groups": [
            {
                "test_id": "python-compileall-api",
                "plan_hash": "f" * 64,
                "decision": "defer",
                "count": 1,
            }
        ],
    }
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(["show-ready-repair-chain-decision-review", str(artifact)])
    )

    assert "BIBER ready repair-chain decision review" in output
    assert "records: 1" in output
    assert "defer_records: 1" in output
    assert "approved_for_eval_records: 0" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "decision=defer" in output
    assert "test_id=python-compileall-api" in output
    assert str(artifact) in output


def test_run_show_ready_repair_chain_decision_review_json_returns_local_artifact(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "ready-repair-chain-decision-review.json"
    payload = {
        "source": "biber_mvp_loop_ready_repair_chain_decision_review",
        "review_status": "decision_summary_only",
        "records": 1,
        "decision_counts": {"defer": 1},
        "groups": [],
    }
    artifact.write_text(json.dumps({"body": payload}), encoding="utf-8")

    output = client.run(
        client.parse_args(
            ["--json", "show-ready-repair-chain-decision-review", str(artifact)]
        )
    )

    assert json.loads(output) == payload


def test_run_list_ready_repair_chain_decision_reviews_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-ready-repair-chain-decision-reviews should not resolve an API key"
        )

    defer_review = tmp_path / "agent-client-ready-repair-chain-decision-review.json"
    defer_review.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_decision_review",
                "review_status": "decision_summary_only",
                "records": 1,
                "rejected_records": 0,
                "decision_counts": {"defer": 1},
                "defer_records": 1,
                "reject_records": 0,
                "approved_for_eval_records": 0,
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "auto_promoted": False,
                "groups": [
                    {
                        "test_id": "python-compileall-api",
                        "plan_hash": "f" * 64,
                        "decision": "defer",
                        "count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    approve_review = tmp_path / "approve-ready-repair-chain-decision-review.json"
    approve_review.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_decision_review",
                "review_status": "decision_summary_only",
                "records": 1,
                "decision_counts": {"approve_for_eval": 1},
                "defer_records": 0,
                "approved_for_eval_records": 1,
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "groups": [],
            }
        ),
        encoding="utf-8",
    )
    ignored = tmp_path / "ignored-ready-repair-chain-decision-review.json"
    ignored.write_text(json.dumps({"source": "other"}), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-ready-repair-chain-decision-reviews",
                str(tmp_path),
                "--decision",
                "defer",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER ready repair-chain decision review artifacts (1)" in output
    assert str(defer_review) in output
    assert str(approve_review) not in output
    assert str(ignored) not in output
    assert "decision: defer" in output
    assert "records: 1" in output
    assert "defer_records: 1" in output
    assert "approved_for_eval_records: 0" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "status=decision_summary_only" in output
    assert "defer=1" in output


def test_run_export_ready_repair_chain_eval_candidates_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "export-ready-repair-chain-eval-candidates should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-decisions.jsonl"
    output_path = tmp_path / "ready-repair-chain-eval-candidates.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_decision",
            "decision_status": "recorded",
            "decision": "approve_for_eval",
            "review_status": "human_approve_for_eval",
            "reviewer": "human-reviewer",
            "notes": "Good eval candidate.",
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_eval": True,
            "approved_for_training": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "c" * 64,
            "test_id": "python-compileall-api",
            "chain": {"chain_status": "ready_for_human_review"},
            "artifacts": {"verification": "repair-verification.json"},
        },
        {
            "source": "biber_mvp_loop_repair_chain_decision",
            "decision_status": "recorded",
            "decision": "defer",
            "reviewer": "second-reviewer",
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_eval": False,
            "approved_for_training": False,
            "source_artifact": "repair-chain-2.json",
            "plan_hash": "d" * 64,
            "test_id": "rust-check",
        },
        {
            "source": "other_source",
            "decision": "approve_for_eval",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-ready-repair-chain-eval-candidates",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_eval_candidate_export"
    assert result["records"] == 1
    assert result["skipped_records"] == 1
    assert result["rejected_records"] == 1
    assert result["eval_candidates"] == 1
    assert result["eval_dataset_ready"] is False
    assert result["requires_dataset_review"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["skipped"][0]["reason"] == "not_approved_for_eval"
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_eval_candidate"
    assert rows[0]["eval_candidate"] is True
    assert rows[0]["eval_dataset_ready"] is False
    assert rows[0]["requires_dataset_review"] is True
    assert rows[0]["decision"] == "approve_for_eval"
    assert rows[0]["reviewer"] == "human-reviewer"
    assert rows[0]["training_allowed"] is False
    assert rows[0]["eligible_for_training"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["approved_for_training"] is False
    assert rows[0]["source_artifact"] == "repair-chain.json"
    assert rows[0]["artifacts"]["verification"] == "repair-verification.json"


def test_run_review_ready_repair_chain_eval_candidates_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-ready-repair-chain-eval-candidates should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-eval-candidates.jsonl"
    output_path = tmp_path / "ready-repair-chain-eval-candidate-review.json"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_eval_candidate",
            "eval_candidate": True,
            "eval_status": "candidate_needs_dataset_review",
            "requires_dataset_review": True,
            "eval_dataset_ready": False,
            "decision": "approve_for_eval",
            "reviewer": "human-reviewer",
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "e" * 64,
            "test_id": "python-compileall-api",
        },
        {
            "source": "other_source",
            "eval_candidate": True,
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-ready-repair-chain-eval-candidates",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_eval_candidate_review"
    assert result["records"] == 1
    assert result["rejected_records"] == 1
    assert result["ready_for_dataset_review"] == 1
    assert result["eval_dataset_ready_records"] == 0
    assert result["requires_dataset_review"] is True
    assert result["eval_dataset_ready"] is False
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["groups"][0]["test_id"] == "python-compileall-api"
    assert result["groups"][0]["requires_dataset_review"] is True
    assert result["groups"][0]["eval_dataset_ready"] is False
    assert result["groups"][0]["approved_for_training"] is False
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert saved == result


def test_run_show_ready_repair_chain_eval_candidate_review_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-eval-candidate-review should not resolve an API key"
        )

    artifact = tmp_path / "ready-repair-chain-eval-candidate-review.json"
    payload = {
        "source": "biber_mvp_loop_ready_repair_chain_eval_candidate_review",
        "review_status": "eval_candidates_need_dataset_review",
        "records": 1,
        "rejected_records": 0,
        "ready_for_dataset_review": 1,
        "eval_dataset_ready_records": 0,
        "eval_dataset_ready": False,
        "requires_dataset_review": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "min_repeat": 1,
        "artifact_path": str(artifact),
        "groups": [
            {
                "test_id": "python-compileall-api",
                "plan_hash": "f" * 64,
                "count": 1,
            }
        ],
    }
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "show-ready-repair-chain-eval-candidate-review",
                str(artifact),
            ]
        )
    )

    assert "BIBER ready repair-chain eval candidate review" in output
    assert "records: 1" in output
    assert "ready_for_dataset_review: 1" in output
    assert "review_status: eval_candidates_need_dataset_review" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "python-compileall-api" in output
    assert "f" * 64 in output
    assert str(artifact) in output


def test_run_show_ready_repair_chain_eval_candidate_review_json_wrapper_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-eval-candidate-review should not resolve an API key"
        )

    artifact = tmp_path / "agent-client-ready-repair-chain-eval-candidate-review.json"
    body = {
        "source": "biber_mvp_loop_ready_repair_chain_eval_candidate_review",
        "review_status": "eval_candidates_need_dataset_review",
        "records": 1,
        "ready_for_dataset_review": 1,
        "eval_dataset_ready": False,
        "requires_dataset_review": True,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "groups": [],
    }
    artifact.write_text(
        json.dumps({"status": 0, "body": body}, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "show-ready-repair-chain-eval-candidate-review",
                str(artifact),
            ]
        )
    )
    result = json.loads(output)

    assert result == body


def test_run_list_ready_repair_chain_eval_candidate_reviews_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-ready-repair-chain-eval-candidate-reviews should not resolve an API key"
        )

    ready_artifact = tmp_path / "ready-repair-chain-eval-candidate-review-1.json"
    not_ready_artifact = tmp_path / "ready-repair-chain-eval-candidate-review-2.json"
    ignored_artifact = tmp_path / "ready-repair-chain-eval-candidate-review-ignored.json"
    ready_artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_eval_candidate_review",
                "review_status": "eval_candidates_need_dataset_review",
                "records": 1,
                "ready_for_dataset_review": 1,
                "eval_dataset_ready": False,
                "requires_dataset_review": True,
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "min_repeat": 1,
                "groups": [{"test_id": "python-compileall-api", "count": 1}],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    not_ready_artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_eval_candidate_review",
                "review_status": "eval_candidates_need_dataset_review",
                "records": 0,
                "ready_for_dataset_review": 0,
                "eval_dataset_ready": False,
                "requires_dataset_review": True,
                "training_allowed": False,
                "groups": [],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    ignored_artifact.write_text(
        json.dumps({"source": "other_source"}, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-ready-repair-chain-eval-candidate-reviews",
                str(tmp_path),
                "--ready-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER ready repair-chain eval-candidate review artifacts (1)" in output
    assert str(ready_artifact) in output
    assert str(not_ready_artifact) not in output
    assert str(ignored_artifact) not in output
    assert "ready_for_dataset_review: 1" in output
    assert "eval_dataset_ready: False" in output
    assert "requires_dataset_review: True" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "status=eval_candidates_need_dataset_review" in output
    assert "groups=1" in output


def test_run_record_ready_repair_chain_eval_candidate_decision_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "record-ready-repair-chain-eval-candidate-decision should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-eval-candidates.jsonl"
    output_path = tmp_path / "ready-repair-chain-eval-dataset-decisions.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_eval_candidate",
            "eval_candidate": True,
            "eval_status": "candidate_needs_dataset_review",
            "requires_dataset_review": True,
            "eval_dataset_ready": False,
            "decision": "approve_for_eval",
            "reviewer": "human-reviewer",
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "f" * 64,
            "test_id": "python-compileall-api",
            "chain": {"chain_status": "ready_for_human_review"},
            "artifacts": {"verification": "repair-verification.json"},
        },
        {
            "source": "other_source",
            "eval_candidate": True,
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "record-ready-repair-chain-eval-candidate-decision",
                str(jsonl_path),
                "--decision",
                "approve_for_eval_dataset",
                "--reviewer",
                "dataset-reviewer",
                "--notes",
                "Approved for eval dataset only.",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_eval_candidate_decision_export"
    assert result["decision"] == "approve_for_eval_dataset"
    assert result["reviewer"] == "dataset-reviewer"
    assert result["records"] == 1
    assert result["rejected_records"] == 1
    assert result["approved_for_eval_dataset_records"] == 1
    assert result["eval_dataset_ready"] is True
    assert result["requires_dataset_review"] is False
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_eval_dataset_decision"
    assert rows[0]["decision_status"] == "recorded"
    assert rows[0]["decision"] == "approve_for_eval_dataset"
    assert rows[0]["review_status"] == "human_approve_for_eval_dataset"
    assert rows[0]["reviewer"] == "dataset-reviewer"
    assert rows[0]["notes"] == "Approved for eval dataset only."
    assert rows[0]["approved_for_eval_dataset"] is True
    assert rows[0]["eval_dataset_ready"] is True
    assert rows[0]["requires_dataset_review"] is False
    assert rows[0]["training_allowed"] is False
    assert rows[0]["eligible_for_training"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["approved_for_training"] is False
    assert rows[0]["source_artifact"] == "repair-chain.json"
    assert rows[0]["artifacts"]["verification"] == "repair-verification.json"


def test_run_review_ready_repair_chain_eval_dataset_decisions_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-ready-repair-chain-eval-dataset-decisions should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-eval-dataset-decisions.jsonl"
    output_path = tmp_path / "ready-repair-chain-eval-dataset-decision-review.json"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_eval_dataset_decision",
            "decision_status": "recorded",
            "decision": "approve_for_eval_dataset",
            "review_status": "human_approve_for_eval_dataset",
            "reviewer": "dataset-reviewer",
            "eval_candidate": True,
            "approved_for_eval_dataset": True,
            "eval_dataset_ready": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "a" * 64,
            "test_id": "python-compileall-api",
        },
        {
            "source": "biber_mvp_loop_repair_chain_eval_dataset_decision",
            "decision_status": "recorded",
            "decision": "defer",
            "review_status": "human_defer",
            "reviewer": "second-reviewer",
            "eval_candidate": True,
            "approved_for_eval_dataset": False,
            "eval_dataset_ready": False,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "source_artifact": "repair-chain-2.json",
            "plan_hash": "b" * 64,
            "test_id": "rust-check",
        },
        {
            "source": "other_source",
            "decision": "approve_for_eval_dataset",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-ready-repair-chain-eval-dataset-decisions",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review"
    assert result["records"] == 2
    assert result["rejected_records"] == 1
    assert result["decision_counts"] == {"approve_for_eval_dataset": 1, "defer": 1}
    assert result["defer_records"] == 1
    assert result["reject_records"] == 0
    assert result["approved_for_eval_dataset_records"] == 1
    assert result["eval_dataset_ready_records"] == 1
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["groups"][0]["decision"] == "approve_for_eval_dataset"
    assert result["groups"][0]["eval_dataset_ready"] is True
    assert result["groups"][0]["approved_for_training"] is False
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert saved == result


def test_run_show_ready_repair_chain_eval_dataset_decision_review_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-eval-dataset-decision-review should not resolve an API key"
        )

    artifact = tmp_path / "ready-repair-chain-eval-dataset-decision-review.json"
    payload = {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review",
        "review_status": "eval_dataset_decisions_need_final_dataset_export_review",
        "records": 1,
        "rejected_records": 0,
        "decision_counts": {"approve_for_eval_dataset": 1},
        "defer_records": 0,
        "reject_records": 0,
        "approved_for_eval_dataset_records": 1,
        "eval_dataset_ready_records": 1,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "min_repeat": 1,
        "artifact_path": str(artifact),
        "groups": [
            {
                "decision": "approve_for_eval_dataset",
                "test_id": "python-compileall-api",
                "plan_hash": "e" * 64,
                "count": 1,
                "eval_dataset_ready": True,
            }
        ],
    }
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "show-ready-repair-chain-eval-dataset-decision-review",
                str(artifact),
            ]
        )
    )

    assert "BIBER ready repair-chain eval dataset decision review" in output
    assert "records: 1" in output
    assert "approved_for_eval_dataset_records: 1" in output
    assert "eval_dataset_ready_records: 1" in output
    assert "review_status: eval_dataset_decisions_need_final_dataset_export_review" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "approve_for_eval_dataset" in output
    assert "python-compileall-api" in output
    assert "e" * 64 in output
    assert str(artifact) in output


def test_run_show_ready_repair_chain_eval_dataset_decision_review_json_wrapper_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-eval-dataset-decision-review should not resolve an API key"
        )

    artifact = tmp_path / "agent-client-ready-repair-chain-eval-dataset-decision-review.json"
    body = {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review",
        "review_status": "eval_dataset_decisions_need_final_dataset_export_review",
        "records": 1,
        "decision_counts": {"approve_for_eval_dataset": 1},
        "approved_for_eval_dataset_records": 1,
        "eval_dataset_ready_records": 1,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "groups": [],
    }
    artifact.write_text(
        json.dumps({"status": 0, "body": body}, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "show-ready-repair-chain-eval-dataset-decision-review",
                str(artifact),
            ]
        )
    )
    result = json.loads(output)

    assert result == body


def test_run_list_ready_repair_chain_eval_dataset_decision_reviews_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-ready-repair-chain-eval-dataset-decision-reviews should not resolve an API key"
        )

    ready_artifact = tmp_path / "ready-repair-chain-eval-dataset-decision-review-1.json"
    not_ready_artifact = tmp_path / "ready-repair-chain-eval-dataset-decision-review-2.json"
    ignored_artifact = tmp_path / "ready-repair-chain-eval-dataset-decision-review-ignored.json"
    ready_artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review",
                "review_status": "eval_dataset_decisions_need_final_dataset_export_review",
                "records": 1,
                "decision_counts": {"approve_for_eval_dataset": 1},
                "defer_records": 0,
                "reject_records": 0,
                "approved_for_eval_dataset_records": 1,
                "eval_dataset_ready_records": 1,
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "min_repeat": 1,
                "groups": [
                    {
                        "decision": "approve_for_eval_dataset",
                        "test_id": "python-compileall-api",
                        "count": 1,
                    }
                ],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    not_ready_artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_decision_review",
                "review_status": "eval_dataset_decisions_need_final_dataset_export_review",
                "records": 1,
                "decision_counts": {"defer": 1},
                "defer_records": 1,
                "reject_records": 0,
                "approved_for_eval_dataset_records": 0,
                "eval_dataset_ready_records": 0,
                "training_allowed": False,
                "groups": [],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    ignored_artifact.write_text(
        json.dumps({"source": "other_source"}, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-ready-repair-chain-eval-dataset-decision-reviews",
                str(tmp_path),
                "--decision",
                "approve_for_eval_dataset",
                "--ready-only",
                "--limit",
                "5",
            ]
        )
    )

    assert (
        "BIBER ready repair-chain eval-dataset decision review artifacts (1)"
        in output
    )
    assert str(ready_artifact) in output
    assert str(not_ready_artifact) not in output
    assert str(ignored_artifact) not in output
    assert "decision: approve_for_eval_dataset" in output
    assert "records: 1" in output
    assert "approved_for_eval_dataset_records: 1" in output
    assert "eval_dataset_ready_records: 1" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "status=eval_dataset_decisions_need_final_dataset_export_review" in output
    assert "groups=1" in output


def test_run_export_ready_repair_chain_eval_dataset_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "export-ready-repair-chain-eval-dataset should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-eval-dataset-decisions.jsonl"
    output_path = tmp_path / "ready-repair-chain-eval-dataset.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_eval_dataset_decision",
            "decision_status": "recorded",
            "decision": "approve_for_eval_dataset",
            "review_status": "human_approve_for_eval_dataset",
            "reviewer": "dataset-reviewer",
            "notes": "Approved for eval dataset only.",
            "eval_candidate": True,
            "approved_for_eval_dataset": True,
            "eval_dataset_ready": True,
            "requires_dataset_review": False,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "c" * 64,
            "test_id": "python-compileall-api",
            "chain": {"chain_status": "ready_for_human_review"},
            "artifacts": {"verification": "repair-verification.json"},
        },
        {
            "source": "biber_mvp_loop_repair_chain_eval_dataset_decision",
            "decision_status": "recorded",
            "decision": "defer",
            "review_status": "human_defer",
            "reviewer": "second-reviewer",
            "eval_candidate": True,
            "approved_for_eval_dataset": False,
            "eval_dataset_ready": False,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "source_artifact": "repair-chain-2.json",
            "plan_hash": "d" * 64,
            "test_id": "rust-check",
        },
        {
            "source": "other_source",
            "decision": "approve_for_eval_dataset",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-ready-repair-chain-eval-dataset",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_eval_dataset_export"
    assert result["records"] == 1
    assert result["skipped_records"] == 1
    assert result["rejected_records"] == 1
    assert result["eval_dataset_records"] == 1
    assert result["eval_dataset_ready"] is True
    assert result["requires_eval_dataset_validation"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["skipped"][0]["reason"] == "not_approved_for_eval_dataset"
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_eval_dataset_record"
    assert rows[0]["eval_dataset_record"] is True
    assert rows[0]["eval_dataset_status"] == "ready_for_eval_dataset_validation"
    assert rows[0]["review_status"] == "eval_dataset_reviewed"
    assert rows[0]["approved_for_eval_dataset"] is True
    assert rows[0]["eval_dataset_ready"] is True
    assert rows[0]["requires_eval_dataset_validation"] is True
    assert rows[0]["training_allowed"] is False
    assert rows[0]["eligible_for_training"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["approved_for_training"] is False
    assert rows[0]["source_artifact"] == "repair-chain.json"
    assert rows[0]["artifacts"]["verification"] == "repair-verification.json"


def test_run_validate_ready_repair_chain_eval_dataset_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "validate-ready-repair-chain-eval-dataset should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-eval-dataset.jsonl"
    output_path = tmp_path / "ready-repair-chain-eval-dataset-validation.json"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_eval_dataset_record",
            "eval_dataset_record": True,
            "eval_dataset_status": "ready_for_eval_dataset_validation",
            "review_status": "eval_dataset_reviewed",
            "quality": "eval_dataset_reviewed",
            "decision": "approve_for_eval_dataset",
            "approved_for_eval_dataset": True,
            "eval_dataset_ready": True,
            "requires_eval_dataset_validation": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "auto_saved": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "e" * 64,
            "test_id": "python-compileall-api",
            "chain": {"chain_status": "ready_for_human_review"},
            "artifacts": {"verification": "repair-verification.json"},
        },
        {
            "source": "biber_mvp_loop_repair_chain_eval_dataset_record",
            "eval_dataset_record": True,
            "eval_dataset_status": "ready_for_eval_dataset_validation",
            "approved_for_eval_dataset": True,
            "eval_dataset_ready": True,
            "requires_eval_dataset_validation": True,
            "training_allowed": True,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "auto_saved": False,
            "source_artifact": "",
            "plan_hash": "f" * 64,
            "test_id": "rust-check",
            "chain": {},
            "artifacts": {},
        },
        {
            "source": "other_source",
            "eval_dataset_record": True,
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "validate-ready-repair-chain-eval-dataset",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_ready_repair_chain_eval_dataset_validation"
    assert result["validation_status"] == "invalid_or_incomplete"
    assert result["ok"] is False
    assert result["records"] == 2
    assert result["valid_records"] == 1
    assert result["invalid_records"] == 1
    assert result["rejected_records"] == 1
    assert result["eval_dataset_ready"] is False
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["errors"][0]["reasons"] == [
        "training_allowed_must_be_false",
        "source_artifact_is_required",
    ]
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert result["groups"][0]["test_id"] == "python-compileall-api"
    assert result["groups"][0]["approved_for_training"] is False


def test_run_show_ready_repair_chain_eval_dataset_validation_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-eval-dataset-validation should not resolve an API key"
        )

    artifact = tmp_path / "ready-repair-chain-eval-dataset-validation.json"
    payload = {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_validation",
        "validation_status": "valid_eval_only",
        "ok": True,
        "records": 1,
        "valid_records": 1,
        "invalid_records": 0,
        "rejected_records": 0,
        "min_records": 1,
        "eval_dataset_ready": True,
        "requires_eval_dataset_validation": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "artifact_path": str(artifact),
        "groups": [
            {
                "test_id": "python-compileall-api",
                "plan_hash": "a" * 64,
                "count": 1,
            }
        ],
    }
    artifact.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "show-ready-repair-chain-eval-dataset-validation",
                str(artifact),
            ]
        )
    )

    assert "BIBER ready repair-chain eval dataset validation" in output
    assert "ok: True" in output
    assert "validation_status: valid_eval_only" in output
    assert "records: 1" in output
    assert "valid_records: 1" in output
    assert "invalid_records: 0" in output
    assert "eval_dataset_ready: True" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "python-compileall-api" in output
    assert "a" * 64 in output
    assert str(artifact) in output


def test_run_show_ready_repair_chain_eval_dataset_validation_json_wrapper_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-eval-dataset-validation should not resolve an API key"
        )

    artifact = tmp_path / "agent-client-ready-repair-chain-eval-dataset-validation.json"
    body = {
        "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_validation",
        "validation_status": "valid_eval_only",
        "ok": True,
        "records": 1,
        "valid_records": 1,
        "invalid_records": 0,
        "rejected_records": 0,
        "eval_dataset_ready": True,
        "requires_eval_dataset_validation": True,
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "groups": [],
    }
    artifact.write_text(
        json.dumps({"status": 0, "body": body}, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "show-ready-repair-chain-eval-dataset-validation",
                str(artifact),
            ]
        )
    )
    result = json.loads(output)

    assert result == body


def test_run_list_ready_repair_chain_eval_dataset_validations_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-ready-repair-chain-eval-dataset-validations should not resolve an API key"
        )

    ok_artifact = tmp_path / "ready-repair-chain-eval-dataset-validation-1.json"
    invalid_artifact = tmp_path / "ready-repair-chain-eval-dataset-validation-2.json"
    ignored_artifact = tmp_path / "ready-repair-chain-eval-dataset-validation-ignored.json"
    ok_artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_validation",
                "validation_status": "valid_eval_only",
                "ok": True,
                "records": 1,
                "valid_records": 1,
                "invalid_records": 0,
                "rejected_records": 0,
                "eval_dataset_ready": True,
                "requires_eval_dataset_validation": True,
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "groups": [{"test_id": "python-compileall-api", "count": 1}],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    invalid_artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_ready_repair_chain_eval_dataset_validation",
                "validation_status": "invalid_or_incomplete",
                "ok": False,
                "records": 1,
                "valid_records": 0,
                "invalid_records": 1,
                "rejected_records": 0,
                "eval_dataset_ready": False,
                "requires_eval_dataset_validation": True,
                "training_allowed": False,
                "groups": [],
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    ignored_artifact.write_text(
        json.dumps({"source": "other_source"}, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-ready-repair-chain-eval-dataset-validations",
                str(tmp_path),
                "--ok-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER ready repair-chain eval-dataset validation artifacts (1)" in output
    assert str(ok_artifact) in output
    assert str(invalid_artifact) not in output
    assert str(ignored_artifact) not in output
    assert "ok_only: True" in output
    assert "ok_artifacts: 1" in output
    assert "records: 1" in output
    assert "valid_records: 1" in output
    assert "invalid_records: 0" in output
    assert "eval_dataset_ready: True" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "status=valid_eval_only" in output
    assert "ok=True" in output
    assert "groups=1" in output


def test_run_export_ready_repair_chain_eval_prompts_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "export-ready-repair-chain-eval-prompts should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-eval-dataset.jsonl"
    output_path = tmp_path / "ready-repair-chain-eval-prompts.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_eval_dataset_record",
            "eval_dataset_record": True,
            "eval_dataset_status": "ready_for_eval_dataset_validation",
            "review_status": "eval_dataset_reviewed",
            "quality": "eval_dataset_reviewed",
            "decision": "approve_for_eval_dataset",
            "approved_for_eval_dataset": True,
            "eval_dataset_ready": True,
            "requires_eval_dataset_validation": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "auto_saved": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "a" * 64,
            "test_id": "python-compileall-api",
            "chain": {
                "chain_status": "ready_for_human_review",
                "chain_complete": True,
                "verification_passed": True,
                "plan_hash_consistent": True,
            },
            "artifacts": {
                "repair": "repair-request.json",
                "verification": "repair-verification.json",
            },
        },
        {
            "source": "biber_mvp_loop_repair_chain_eval_dataset_record",
            "eval_dataset_record": True,
            "eval_dataset_status": "ready_for_eval_dataset_validation",
            "approved_for_eval_dataset": True,
            "eval_dataset_ready": True,
            "requires_eval_dataset_validation": True,
            "training_allowed": True,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "auto_saved": False,
            "source_artifact": "repair-chain-2.json",
            "plan_hash": "b" * 64,
            "test_id": "rust-check",
            "chain": {},
            "artifacts": {},
        },
        {
            "source": "other_source",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-ready-repair-chain-eval-prompts",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_eval_prompt_export"
    assert result["records"] == 1
    assert result["skipped_records"] == 1
    assert result["rejected_records"] == 1
    assert result["eval_prompts"] == 1
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["skipped"][0]["reason"] == "invalid_eval_dataset_record"
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_eval_prompt"
    assert rows[0]["id"].startswith("repair_chain_python_compileall_api_")
    assert rows[0]["language"] == "Python"
    assert rows[0]["task_type"] == "mvp_loop_repair_eval"
    assert rows[0]["expect_contains"] == ["Repair", "Test", "Risk"]
    assert rows[0]["eval_prompt_ready"] is True
    assert rows[0]["eval_only"] is True
    assert rows[0]["training_allowed"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["approved_for_training"] is False
    assert "test_id: python-compileall-api" in rows[0]["prompt"]
    assert "Repair, Test, Risk" in rows[0]["prompt"]


def test_run_show_ready_repair_chain_eval_prompts_summarizes_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-eval-prompts should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-eval-prompts.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_eval_prompt",
            "id": "repair_chain_python_compileall_api_abc123",
            "language": "Python",
            "task_type": "mvp_loop_repair_eval",
            "prompt": "Repair:\nTest:\nRisk:",
            "expect_contains": ["Repair", "Test", "Risk"],
            "eval_prompt_ready": True,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "source_artifact": "repair-chain.json",
            "plan_hash": "c" * 64,
            "test_id": "python-compileall-api",
        },
        {
            "source": "biber_mvp_loop_repair_chain_eval_prompt",
            "id": "repair_chain_rust_check_def456",
            "language": "Rust",
            "task_type": "mvp_loop_repair_eval",
            "prompt": "",
            "expect_contains": [],
            "eval_prompt_ready": True,
            "eval_only": True,
            "training_allowed": True,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "source_artifact": "repair-chain-2.json",
            "plan_hash": "d" * 64,
            "test_id": "rust-check",
        },
        {
            "source": "other_source",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "show-ready-repair-chain-eval-prompts",
                str(jsonl_path),
            ]
        )
    )

    assert "BIBER ready repair-chain eval prompts" in output
    assert "ok: False" in output
    assert "inspection_status: eval_prompts_need_review" in output
    assert "records: 2" in output
    assert "valid_records: 1" in output
    assert "invalid_records: 1" in output
    assert "rejected_records: 1" in output
    assert "eval_prompts: 2" in output
    assert "eval_prompt_ready_records: 2" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "python-compileall-api" in output
    assert "c" * 64 in output
    assert str(jsonl_path) in output


def test_run_show_ready_repair_chain_eval_prompts_json_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-ready-repair-chain-eval-prompts should not resolve an API key"
        )

    jsonl_path = tmp_path / "ready-repair-chain-eval-prompts.jsonl"
    record = {
        "source": "biber_mvp_loop_repair_chain_eval_prompt",
        "id": "repair_chain_python_compileall_api_abc123",
        "language": "Python",
        "task_type": "mvp_loop_repair_eval",
        "prompt": "Repair:\nTest:\nRisk:",
        "expect_contains": ["Repair", "Test", "Risk"],
        "eval_prompt_ready": True,
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "source_artifact": "repair-chain.json",
        "plan_hash": "e" * 64,
        "test_id": "python-compileall-api",
    }
    jsonl_path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "show-ready-repair-chain-eval-prompts",
                str(jsonl_path),
            ]
        )
    )
    result = json.loads(output)

    assert result["source"] == "biber_mvp_loop_ready_repair_chain_eval_prompt_inspection"
    assert result["inspection_status"] == "eval_prompts_ready"
    assert result["ok"] is True
    assert result["records"] == 1
    assert result["valid_records"] == 1
    assert result["invalid_records"] == 0
    assert result["rejected_records"] == 0
    assert result["eval_prompts"] == 1
    assert result["eval_prompt_ready_records"] == 1
    assert result["language_counts"] == {"Python": 1}
    assert result["task_type_counts"] == {"mvp_loop_repair_eval": 1}
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False


def test_run_list_ready_repair_chain_eval_prompts_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-ready-repair-chain-eval-prompts should not resolve an API key"
        )

    ready_artifact = tmp_path / "ready-repair-chain-eval-prompts-1.jsonl"
    invalid_artifact = tmp_path / "ready-repair-chain-eval-prompts-2.jsonl"
    ready_artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_eval_prompt",
                "id": "repair_chain_python_compileall_api_abc123",
                "language": "Python",
                "task_type": "mvp_loop_repair_eval",
                "prompt": "Repair:\nTest:\nRisk:",
                "expect_contains": ["Repair", "Test", "Risk"],
                "eval_prompt_ready": True,
                "eval_only": True,
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "auto_promoted": False,
                "source_artifact": "repair-chain.json",
                "plan_hash": "f" * 64,
                "test_id": "python-compileall-api",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    invalid_artifact.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_eval_prompt",
                "id": "repair_chain_rust_check_def456",
                "task_type": "mvp_loop_repair_eval",
                "prompt": "",
                "expect_contains": [],
                "eval_prompt_ready": True,
                "eval_only": True,
                "training_allowed": True,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "list-ready-repair-chain-eval-prompts",
                str(tmp_path),
                "--ready-only",
                "--limit",
                "5",
            ]
        )
    )

    assert "BIBER ready repair-chain eval prompt artifacts (1)" in output
    assert str(ready_artifact) in output
    assert str(invalid_artifact) not in output
    assert "ready_only: True" in output
    assert "ok_artifacts: 1" in output
    assert "records: 1" in output
    assert "valid_records: 1" in output
    assert "invalid_records: 0" in output
    assert "eval_prompts: 1" in output
    assert "eval_prompt_ready_records: 1" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert "status=eval_prompts_ready" in output
    assert "ok=True" in output
    assert "groups=1" in output


def test_run_review_repair_chain_heldout_eval_results_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-heldout-eval-results should not resolve an API key"
        )

    jsonl_path = tmp_path / "heldout-results.jsonl"
    summary_path = tmp_path / "heldout-summary.json"
    output_path = tmp_path / "heldout-review.json"
    records = [
        {
            "id": "repair_chain_python_compileall_api_abc123",
            "ok": True,
            "expectation_ok": True,
            "validation_ok": None,
            "validation_skipped": False,
            "model": "biber-dev-core-v1",
            "latency_seconds": 1.25,
            "content": "Repair:\nsmall fix\nTest:\npython-compileall-api\nRisk:\nlow",
            "matched_expectations": ["Repair", "Test", "Risk"],
            "missing_expectations": [],
            "error": None,
        },
        {
            "id": "repair_chain_python_compileall_api_def456",
            "ok": True,
            "expectation_ok": False,
            "validation_ok": None,
            "validation_skipped": False,
            "model": "biber-dev-core-v1",
            "latency_seconds": 1.1,
            "content": "Repair:\nsmall fix\nTest:\npython-compileall-api",
            "matched_expectations": ["Repair", "Test"],
            "missing_expectations": ["Risk"],
            "error": None,
        },
        {
            "id": "python_add_function",
            "ok": True,
            "expectation_ok": True,
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(
            {
                "prompts": 2,
                "ok": 2,
                "failed": 0,
                "expectation_ok": 1,
                "expectation_failed": 1,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-heldout-eval-results",
                str(jsonl_path),
                "--summary",
                str(summary_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_heldout_eval_review"
    assert result["review_status"] == "heldout_eval_needs_review"
    assert result["ok"] is False
    assert result["records"] == 2
    assert result["passed_records"] == 1
    assert result["failed_records"] == 1
    assert result["expectation_failed_records"] == 1
    assert result["validation_failed_records"] == 0
    assert result["error_records"] == 0
    assert result["rejected_records"] == 1
    assert result["model_counts"] == {"biber-dev-core-v1": 2}
    assert result["summary_prompts"] == 2
    assert result["summary_expectation_failed"] == 1
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["results"][0]["id"] == "repair_chain_python_compileall_api_def456"
    assert result["results"][0]["passed"] is False
    assert result["results"][0]["missing_expectations"] == ["Risk"]
    assert result["rejected"][0]["reason"] == "unsupported_eval_result_id"


def test_run_show_repair_chain_heldout_eval_review_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-repair-chain-heldout-eval-review should not resolve an API key"
        )

    review_path = tmp_path / "repair-chain-heldout-eval-review.json"
    review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_heldout_eval_review",
                "review_status": "heldout_eval_passed",
                "ok": True,
                "records": 1,
                "passed_records": 1,
                "failed_records": 0,
                "expectation_failed_records": 0,
                "validation_failed_records": 0,
                "error_records": 0,
                "rejected_records": 0,
                "min_passes": 1,
                "model_counts": {"biber-dev-core-v1": 1},
                "summary_path": "heldout.summary.json",
                "eval_only": True,
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "auto_promoted": False,
                "jsonl_paths": ["heldout.jsonl"],
                "results": [
                    {
                        "id": "repair_chain_python_compileall_api_abc123",
                        "passed": True,
                        "expectation_ok": True,
                        "model": "biber-dev-core-v1",
                    }
                ],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "show-repair-chain-heldout-eval-review",
                str(review_path),
            ]
        )
    )

    assert "BIBER repair-chain held-out eval review" in output
    assert "ok: True" in output
    assert "review_status: heldout_eval_passed" in output
    assert "records: 1" in output
    assert "passed_records: 1" in output
    assert "failed_records: 0" in output
    assert "model_counts: {'biber-dev-core-v1': 1}" in output
    assert "eval_only: True" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert f"artifact_path: {review_path}" in output
    assert "repair_chain_python_compileall_api_abc123" in output


def test_run_list_repair_chain_heldout_eval_reviews_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-repair-chain-heldout-eval-reviews should not resolve an API key"
        )

    ok_artifact = tmp_path / "repair-chain-heldout-eval-review-ok.json"
    failed_artifact = tmp_path / "repair-chain-heldout-eval-review-failed.json"
    wrapped_artifact = tmp_path / "agent-client-mvp-loop-repair-chain-heldout-eval-review-result.json"
    ok_review = {
        "source": "biber_mvp_loop_repair_chain_heldout_eval_review",
        "review_status": "heldout_eval_passed",
        "ok": True,
        "records": 1,
        "passed_records": 1,
        "failed_records": 0,
        "expectation_failed_records": 0,
        "validation_failed_records": 0,
        "error_records": 0,
        "rejected_records": 0,
        "min_passes": 1,
        "model_counts": {"biber-dev-core-v1": 1},
        "summary_path": "heldout.summary.json",
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": ["heldout.jsonl"],
        "results": [
            {
                "id": "repair_chain_python_compileall_api_abc123",
                "passed": True,
            }
        ],
    }
    failed_review = {
        **ok_review,
        "review_status": "heldout_eval_needs_review",
        "ok": False,
        "passed_records": 0,
        "failed_records": 1,
        "expectation_failed_records": 1,
    }
    wrapped_artifact.write_text(
        json.dumps(
            {
                "status": 0,
                "body": ok_review,
                "output": str(ok_artifact),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    failed_artifact.write_text(
        json.dumps(failed_review, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "list-repair-chain-heldout-eval-reviews",
                str(tmp_path),
                "--ok-only",
                "--limit",
                "5",
            ]
        )
    )
    result = json.loads(output)

    assert result["source"] == "biber_mvp_loop_repair_chain_heldout_eval_review_list"
    assert result["ok_only"] is True
    assert result["matched"] == 1
    assert result["ok_artifacts"] == 1
    assert result["records"] == 1
    assert result["passed_records"] == 1
    assert result["failed_records"] == 0
    assert result["expectation_failed_records"] == 0
    assert result["model_counts"] == {"biber-dev-core-v1": 1}
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["path"] == str(wrapped_artifact)
    assert result["artifacts"][0]["artifact_path"] == str(ok_artifact)
    assert result["artifacts"][0]["review_status"] == "heldout_eval_passed"
    assert result["artifacts"][0]["ok"] is True


def test_run_record_repair_chain_heldout_eval_decision_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "record-repair-chain-heldout-eval-decision should not resolve an API key"
        )

    review_path = tmp_path / "heldout-review.json"
    unsupported_path = tmp_path / "unsupported-review.json"
    output_path = tmp_path / "heldout-decisions.jsonl"
    review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_heldout_eval_review",
                "review_status": "heldout_eval_passed",
                "ok": True,
                "records": 1,
                "passed_records": 1,
                "failed_records": 0,
                "expectation_failed_records": 0,
                "rejected_records": 0,
                "model_counts": {"biber-dev-core-v1": 1},
                "summary_path": "heldout.summary.json",
                "jsonl_paths": ["heldout.jsonl"],
                "results": [
                    {
                        "id": "repair_chain_python_compileall_api_abc123",
                        "passed": True,
                    }
                ],
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    unsupported_path.write_text(
        json.dumps({"source": "other_source"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "record-repair-chain-heldout-eval-decision",
                str(review_path),
                str(unsupported_path),
                "--decision",
                "accept_for_baseline",
                "--reviewer",
                "biber-test",
                "--notes",
                "Test accept without training promotion.",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_repair_chain_heldout_eval_decision_export"
    assert result["decision"] == "accept_for_baseline"
    assert result["reviewer"] == "biber-test"
    assert result["records"] == 1
    assert result["rejected_records"] == 1
    assert result["accepted_for_baseline_records"] == 1
    assert result["baseline_candidate_ready"] is True
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_heldout_eval_decision"
    assert rows[0]["decision"] == "accept_for_baseline"
    assert rows[0]["reviewer"] == "biber-test"
    assert rows[0]["accepted_for_baseline"] is True
    assert rows[0]["baseline_candidate_ready"] is True
    assert rows[0]["requires_follow_up"] is False
    assert rows[0]["eval_only"] is True
    assert rows[0]["training_allowed"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["approved_for_training"] is False
    assert rows[0]["heldout_eval_review_artifact"] == str(review_path)
    assert rows[0]["heldout_eval_result_ids"] == [
        "repair_chain_python_compileall_api_abc123"
    ]


def test_run_review_repair_chain_heldout_eval_decisions_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-heldout-eval-decisions should not resolve an API key"
        )

    jsonl_path = tmp_path / "heldout-decisions.jsonl"
    output_path = tmp_path / "heldout-decision-review.json"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_heldout_eval_decision",
            "decision": "accept_for_baseline",
            "review_status": "human_accept_for_baseline",
            "reviewer": "biber-test",
            "accepted_for_baseline": True,
            "baseline_candidate_ready": True,
            "requires_follow_up": False,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "heldout_eval_review_artifact": "heldout-review.json",
            "heldout_eval_result_ids": [
                "repair_chain_python_compileall_api_abc123"
            ],
        },
        {
            "source": "biber_mvp_loop_repair_chain_heldout_eval_decision",
            "decision": "defer",
            "review_status": "human_defer",
            "reviewer": "biber-test",
            "accepted_for_baseline": False,
            "baseline_candidate_ready": False,
            "requires_follow_up": True,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "heldout_eval_review_artifact": "heldout-review-2.json",
            "heldout_eval_result_ids": [
                "repair_chain_python_compileall_api_def456"
            ],
        },
        {
            "source": "other_source",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-heldout-eval-decisions",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_heldout_eval_decision_review"
    assert result["review_status"] == "heldout_eval_decision_summary_only"
    assert result["records"] == 2
    assert result["rejected_records"] == 1
    assert result["decision_counts"] == {
        "accept_for_baseline": 1,
        "defer": 1,
    }
    assert result["defer_records"] == 1
    assert result["reject_records"] == 0
    assert result["accepted_for_baseline_records"] == 1
    assert result["baseline_candidate_ready_records"] == 1
    assert result["follow_up_records"] == 1
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["groups"][0]["decision"] == "accept_for_baseline"
    assert result["groups"][0]["baseline_candidate_ready"] is True
    assert result["groups"][1]["decision"] == "defer"
    assert result["groups"][1]["requires_follow_up"] is True
    assert result["rejected"][0]["reason"] == "unsupported_source"


def test_run_show_repair_chain_heldout_eval_decision_review_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-repair-chain-heldout-eval-decision-review should not resolve an API key"
        )

    review_path = tmp_path / "heldout-eval-decision-review.json"
    review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_heldout_eval_decision_review",
                "review_status": "heldout_eval_decision_summary_only",
                "records": 1,
                "rejected_records": 0,
                "decision_counts": {"defer": 1},
                "defer_records": 1,
                "reject_records": 0,
                "accepted_for_baseline_records": 0,
                "baseline_candidate_ready_records": 0,
                "follow_up_records": 1,
                "min_repeat": 1,
                "groups": [
                    {
                        "decision": "defer",
                        "count": 1,
                        "baseline_candidate_ready": False,
                        "requires_follow_up": True,
                    }
                ],
                "eval_only": True,
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "auto_promoted": False,
                "jsonl_paths": ["heldout-decisions.jsonl"],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "show-repair-chain-heldout-eval-decision-review",
                str(review_path),
            ]
        )
    )

    assert "BIBER repair-chain held-out eval decision review" in output
    assert "records: 1" in output
    assert "defer_records: 1" in output
    assert "accepted_for_baseline_records: 0" in output
    assert "baseline_candidate_ready_records: 0" in output
    assert "follow_up_records: 1" in output
    assert "decision_counts: {'defer': 1}" in output
    assert "eval_only: True" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert f"artifact_path: {review_path}" in output


def test_run_list_repair_chain_heldout_eval_decision_reviews_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-repair-chain-heldout-eval-decision-reviews should not resolve an API key"
        )

    accepted_artifact = tmp_path / "heldout-eval-decision-review-accepted.json"
    defer_artifact = tmp_path / "heldout-eval-decision-review-defer.json"
    wrapped_artifact = (
        tmp_path / "agent-client-mvp-loop-repair-chain-heldout-eval-decision-review-result.json"
    )
    accepted_review = {
        "source": "biber_mvp_loop_repair_chain_heldout_eval_decision_review",
        "review_status": "heldout_eval_decision_summary_only",
        "records": 1,
        "rejected_records": 0,
        "decision_counts": {"accept_for_baseline": 1},
        "defer_records": 0,
        "reject_records": 0,
        "accepted_for_baseline_records": 1,
        "baseline_candidate_ready_records": 1,
        "follow_up_records": 0,
        "min_repeat": 1,
        "groups": [
            {
                "decision": "accept_for_baseline",
                "count": 1,
                "baseline_candidate_ready": True,
                "requires_follow_up": False,
            }
        ],
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": ["heldout-decisions.jsonl"],
    }
    defer_review = {
        **accepted_review,
        "decision_counts": {"defer": 1},
        "defer_records": 1,
        "accepted_for_baseline_records": 0,
        "baseline_candidate_ready_records": 0,
        "follow_up_records": 1,
        "groups": [
            {
                "decision": "defer",
                "count": 1,
                "baseline_candidate_ready": False,
                "requires_follow_up": True,
            }
        ],
    }
    wrapped_artifact.write_text(
        json.dumps(
            {
                "status": 0,
                "body": accepted_review,
                "output": str(accepted_artifact),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    defer_artifact.write_text(
        json.dumps(defer_review, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "list-repair-chain-heldout-eval-decision-reviews",
                str(tmp_path),
                "--decision",
                "accept_for_baseline",
                "--baseline-ready-only",
                "--limit",
                "5",
            ]
        )
    )
    result = json.loads(output)

    assert (
        result["source"]
        == "biber_mvp_loop_repair_chain_heldout_eval_decision_review_list"
    )
    assert result["decision"] == "accept_for_baseline"
    assert result["baseline_ready_only"] is True
    assert result["matched"] == 1
    assert result["records"] == 1
    assert result["defer_records"] == 0
    assert result["accepted_for_baseline_records"] == 1
    assert result["baseline_candidate_ready_records"] == 1
    assert result["follow_up_records"] == 0
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["path"] == str(wrapped_artifact)
    assert result["artifacts"][0]["artifact_path"] == str(accepted_artifact)
    assert result["artifacts"][0]["decision_counts"] == {"accept_for_baseline": 1}
    assert result["artifacts"][0]["baseline_candidate_ready_records"] == 1


def test_run_export_repair_chain_heldout_baseline_candidates_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "export-repair-chain-heldout-baseline-candidates should not resolve an API key"
        )

    jsonl_path = tmp_path / "heldout-decisions.jsonl"
    output_path = tmp_path / "heldout-baseline-candidates.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_heldout_eval_decision",
            "decision_status": "recorded",
            "decision": "accept_for_baseline",
            "review_status": "human_accept_for_baseline",
            "reviewer": "baseline-reviewer",
            "notes": "Candidate only.",
            "accepted_for_baseline": True,
            "baseline_candidate_ready": True,
            "requires_follow_up": False,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "heldout_eval_review_artifact": "heldout-review.json",
            "heldout_eval_review_status": "heldout_eval_passed",
            "heldout_eval_review_ok": True,
            "heldout_eval_records": 1,
            "heldout_eval_passed_records": 1,
            "heldout_eval_failed_records": 0,
            "heldout_eval_expectation_failed_records": 0,
            "heldout_eval_rejected_records": 0,
            "heldout_eval_model_counts": {"biber-dev-core-v1": 1},
            "heldout_eval_summary_path": "heldout.summary.json",
            "heldout_eval_result_jsonl_paths": ["heldout.jsonl"],
            "heldout_eval_result_ids": [
                "repair_chain_python_compileall_api_abc123"
            ],
        },
        {
            "source": "biber_mvp_loop_repair_chain_heldout_eval_decision",
            "decision_status": "recorded",
            "decision": "defer",
            "review_status": "human_defer",
            "reviewer": "second-reviewer",
            "accepted_for_baseline": False,
            "baseline_candidate_ready": False,
            "requires_follow_up": True,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "heldout_eval_review_artifact": "heldout-review-2.json",
            "heldout_eval_result_ids": [
                "repair_chain_rust_check_def456"
            ],
        },
        {
            "source": "other_source",
            "decision": "accept_for_baseline",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-repair-chain-heldout-baseline-candidates",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_repair_chain_heldout_baseline_candidate_export"
    assert result["records"] == 1
    assert result["skipped_records"] == 1
    assert result["rejected_records"] == 1
    assert result["baseline_candidates"] == 1
    assert result["accepted_for_baseline_records"] == 1
    assert result["baseline_candidate_ready"] is True
    assert result["baseline_ready"] is False
    assert result["requires_baseline_review"] is True
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["skipped"][0]["reason"] == "not_accepted_for_baseline"
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_heldout_baseline_candidate"
    assert rows[0]["heldout_baseline_candidate"] is True
    assert rows[0]["baseline_candidate_status"] == "candidate_needs_manual_baseline_review"
    assert rows[0]["decision"] == "accept_for_baseline"
    assert rows[0]["reviewer"] == "baseline-reviewer"
    assert rows[0]["accepted_for_baseline"] is True
    assert rows[0]["baseline_candidate_ready"] is True
    assert rows[0]["baseline_ready"] is False
    assert rows[0]["requires_baseline_review"] is True
    assert rows[0]["eval_only"] is True
    assert rows[0]["training_allowed"] is False
    assert rows[0]["eligible_for_training"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["approved_for_training"] is False
    assert rows[0]["heldout_eval_review_artifact"] == "heldout-review.json"
    assert rows[0]["heldout_eval_result_ids"] == [
        "repair_chain_python_compileall_api_abc123"
    ]


def test_run_review_repair_chain_heldout_baseline_candidates_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-heldout-baseline-candidates should not resolve an API key"
        )

    jsonl_path = tmp_path / "heldout-baseline-candidates.jsonl"
    output_path = tmp_path / "heldout-baseline-candidate-review.json"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_heldout_baseline_candidate",
            "heldout_baseline_candidate": True,
            "baseline_candidate_status": "candidate_needs_manual_baseline_review",
            "decision": "accept_for_baseline",
            "decision_status": "recorded",
            "review_status": "human_accept_for_baseline",
            "reviewer": "baseline-reviewer",
            "accepted_for_baseline": True,
            "baseline_candidate_ready": True,
            "baseline_ready": False,
            "requires_baseline_review": True,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "heldout_eval_review_artifact": "heldout-review.json",
            "heldout_eval_result_ids": [
                "repair_chain_python_compileall_api_abc123"
            ],
        },
        {
            "source": "other_source",
            "decision": "accept_for_baseline",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-heldout-baseline-candidates",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_heldout_baseline_candidate_review"
    assert result["review_status"] == "heldout_baseline_candidate_summary_only"
    assert result["records"] == 1
    assert result["rejected_records"] == 1
    assert result["baseline_candidates"] == 1
    assert result["decision_counts"] == {"accept_for_baseline": 1}
    assert result["accepted_for_baseline_records"] == 1
    assert result["baseline_candidate_ready_records"] == 1
    assert result["baseline_ready_records"] == 0
    assert result["requires_baseline_review_records"] == 1
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["groups"][0]["decision"] == "accept_for_baseline"
    assert result["groups"][0]["baseline_candidate_ready"] is True
    assert result["groups"][0]["baseline_ready"] is False
    assert result["groups"][0]["requires_baseline_review"] is True
    assert result["groups"][0]["approved_for_training"] is False
    assert result["rejected"][0]["reason"] == "unsupported_source"


def test_run_show_repair_chain_heldout_baseline_candidate_review_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-repair-chain-heldout-baseline-candidate-review should not resolve an API key"
        )

    review_path = tmp_path / "heldout-baseline-candidate-review.json"
    review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_heldout_baseline_candidate_review",
                "review_status": "heldout_baseline_candidate_summary_only",
                "records": 1,
                "rejected_records": 0,
                "baseline_candidates": 1,
                "decision_counts": {"accept_for_baseline": 1},
                "accepted_for_baseline_records": 1,
                "baseline_candidate_ready_records": 1,
                "baseline_ready_records": 0,
                "requires_baseline_review_records": 1,
                "min_repeat": 1,
                "groups": [
                    {
                        "decision": "accept_for_baseline",
                        "count": 1,
                        "baseline_candidate_ready": True,
                        "baseline_ready": False,
                        "requires_baseline_review": True,
                    }
                ],
                "eval_only": True,
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "auto_promoted": False,
                "jsonl_paths": ["heldout-baseline-candidates.jsonl"],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "show-repair-chain-heldout-baseline-candidate-review",
                str(review_path),
            ]
        )
    )

    assert "BIBER repair-chain held-out baseline candidate review" in output
    assert "records: 1" in output
    assert "baseline_candidates: 1" in output
    assert "accepted_for_baseline_records: 1" in output
    assert "baseline_candidate_ready_records: 1" in output
    assert "baseline_ready_records: 0" in output
    assert "requires_baseline_review_records: 1" in output
    assert "decision_counts: {'accept_for_baseline': 1}" in output
    assert "eval_only: True" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert f"artifact_path: {review_path}" in output


def test_run_list_repair_chain_heldout_baseline_candidate_reviews_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-repair-chain-heldout-baseline-candidate-reviews should not resolve an API key"
        )

    candidate_artifact = tmp_path / "heldout-baseline-candidate-review-ready.json"
    empty_artifact = tmp_path / "heldout-baseline-candidate-review-empty.json"
    wrapped_artifact = (
        tmp_path
        / "agent-client-mvp-loop-repair-chain-heldout-baseline-candidate-review-result.json"
    )
    candidate_review = {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_candidate_review",
        "review_status": "heldout_baseline_candidate_summary_only",
        "records": 1,
        "rejected_records": 0,
        "baseline_candidates": 1,
        "decision_counts": {"accept_for_baseline": 1},
        "accepted_for_baseline_records": 1,
        "baseline_candidate_ready_records": 1,
        "baseline_ready_records": 0,
        "requires_baseline_review_records": 1,
        "min_repeat": 1,
        "groups": [
            {
                "decision": "accept_for_baseline",
                "count": 1,
                "baseline_candidate_ready": True,
                "baseline_ready": False,
                "requires_baseline_review": True,
            }
        ],
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": ["heldout-baseline-candidates.jsonl"],
    }
    empty_review = {
        **candidate_review,
        "records": 0,
        "baseline_candidates": 0,
        "decision_counts": {},
        "accepted_for_baseline_records": 0,
        "baseline_candidate_ready_records": 0,
        "baseline_ready_records": 0,
        "requires_baseline_review_records": 0,
        "groups": [],
    }
    wrapped_artifact.write_text(
        json.dumps(
            {
                "status": 0,
                "body": candidate_review,
                "output": str(candidate_artifact),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    empty_artifact.write_text(
        json.dumps(empty_review, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "list-repair-chain-heldout-baseline-candidate-reviews",
                str(tmp_path),
                "--candidate-ready-only",
                "--limit",
                "5",
            ]
        )
    )
    result = json.loads(output)

    assert (
        result["source"]
        == "biber_mvp_loop_repair_chain_heldout_baseline_candidate_review_list"
    )
    assert result["candidate_ready_only"] is True
    assert result["matched"] == 1
    assert result["records"] == 1
    assert result["rejected_records"] == 0
    assert result["baseline_candidates"] == 1
    assert result["accepted_for_baseline_records"] == 1
    assert result["baseline_candidate_ready_records"] == 1
    assert result["baseline_ready_records"] == 0
    assert result["requires_baseline_review_records"] == 1
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["path"] == str(wrapped_artifact)
    assert result["artifacts"][0]["artifact_path"] == str(candidate_artifact)
    assert result["artifacts"][0]["decision_counts"] == {"accept_for_baseline": 1}
    assert result["artifacts"][0]["baseline_candidate_ready_records"] == 1


def test_run_record_repair_chain_heldout_baseline_candidate_decision_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "record-repair-chain-heldout-baseline-candidate-decision should not resolve an API key"
        )

    jsonl_path = tmp_path / "heldout-baseline-candidates.jsonl"
    output_path = tmp_path / "heldout-baseline-decisions.jsonl"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_heldout_baseline_candidate",
            "heldout_baseline_candidate": True,
            "baseline_candidate_status": "candidate_needs_manual_baseline_review",
            "decision": "accept_for_baseline",
            "decision_status": "recorded",
            "review_status": "human_accept_for_baseline",
            "reviewer": "baseline-reviewer",
            "notes": "Candidate only.",
            "accepted_for_baseline": True,
            "baseline_candidate_ready": True,
            "baseline_ready": False,
            "requires_baseline_review": True,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "heldout_eval_decision_jsonl_path": "heldout-decisions.jsonl",
            "heldout_eval_decision_jsonl_index": 1,
            "heldout_eval_review_artifact": "heldout-review.json",
            "heldout_eval_review_status": "heldout_eval_passed",
            "heldout_eval_review_ok": True,
            "heldout_eval_records": 1,
            "heldout_eval_passed_records": 1,
            "heldout_eval_failed_records": 0,
            "heldout_eval_expectation_failed_records": 0,
            "heldout_eval_rejected_records": 0,
            "heldout_eval_model_counts": {"biber-dev-core-v1": 1},
            "heldout_eval_summary_path": "heldout.summary.json",
            "heldout_eval_result_jsonl_paths": ["heldout.jsonl"],
            "heldout_eval_result_ids": [
                "repair_chain_python_compileall_api_abc123"
            ],
        },
        {
            "source": "other_source",
            "decision": "accept_for_baseline",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "record-repair-chain-heldout-baseline-candidate-decision",
                str(jsonl_path),
                "--decision",
                "approve_as_baseline",
                "--reviewer",
                "baseline-decision-reviewer",
                "--notes",
                "Approved as baseline evidence only.",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]

    assert result["source"] == "biber_mvp_loop_repair_chain_heldout_baseline_decision_export"
    assert result["decision"] == "approve_as_baseline"
    assert result["reviewer"] == "baseline-decision-reviewer"
    assert result["records"] == 1
    assert result["rejected_records"] == 1
    assert result["approved_as_baseline_records"] == 1
    assert result["baseline_ready"] is True
    assert result["requires_baseline_review"] is False
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["rejected"][0]["reason"] == "unsupported_source"
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_heldout_baseline_decision"
    assert rows[0]["decision_status"] == "recorded"
    assert rows[0]["decision"] == "approve_as_baseline"
    assert rows[0]["review_status"] == "human_approve_as_baseline"
    assert rows[0]["reviewer"] == "baseline-decision-reviewer"
    assert rows[0]["notes"] == "Approved as baseline evidence only."
    assert rows[0]["heldout_baseline_candidate"] is True
    assert rows[0]["approved_as_baseline"] is True
    assert rows[0]["baseline_candidate_ready"] is True
    assert rows[0]["baseline_ready"] is True
    assert rows[0]["requires_baseline_review"] is False
    assert rows[0]["eval_only"] is True
    assert rows[0]["training_allowed"] is False
    assert rows[0]["eligible_for_training"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["github_save_ready"] is False
    assert rows[0]["approved_for_training"] is False
    assert rows[0]["heldout_eval_review_artifact"] == "heldout-review.json"
    assert rows[0]["heldout_eval_result_ids"] == [
        "repair_chain_python_compileall_api_abc123"
    ]


def test_run_review_repair_chain_heldout_baseline_decisions_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-heldout-baseline-decisions should not resolve an API key"
        )

    jsonl_path = tmp_path / "heldout-baseline-decisions.jsonl"
    output_path = tmp_path / "heldout-baseline-decision-review.json"
    records = [
        {
            "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision",
            "decision_status": "recorded",
            "decision": "approve_as_baseline",
            "review_status": "human_approve_as_baseline",
            "reviewer": "baseline-reviewer",
            "notes": "Approved as baseline evidence only.",
            "heldout_baseline_candidate": True,
            "approved_as_baseline": True,
            "baseline_candidate_ready": True,
            "baseline_ready": True,
            "requires_baseline_review": False,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "heldout_eval_review_artifact": "heldout-review.json",
            "heldout_eval_result_ids": [
                "repair_chain_python_compileall_api_abc123"
            ],
        },
        {
            "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision",
            "decision_status": "recorded",
            "decision": "defer",
            "review_status": "human_defer",
            "reviewer": "second-reviewer",
            "heldout_baseline_candidate": True,
            "approved_as_baseline": False,
            "baseline_candidate_ready": True,
            "baseline_ready": False,
            "requires_baseline_review": True,
            "eval_only": True,
            "training_allowed": False,
            "eligible_for_training": False,
            "safe_to_train": False,
            "github_save_ready": False,
            "approved_for_training": False,
            "auto_promoted": False,
            "heldout_eval_review_artifact": "heldout-review-2.json",
            "heldout_eval_result_ids": [
                "repair_chain_rust_check_def456"
            ],
        },
        {
            "source": "other_source",
            "decision": "approve_as_baseline",
        },
    ]
    jsonl_path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-heldout-baseline-decisions",
                str(jsonl_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_heldout_baseline_decision_review"
    assert result["review_status"] == "heldout_baseline_decision_summary_only"
    assert result["records"] == 2
    assert result["rejected_records"] == 1
    assert result["decision_counts"] == {
        "approve_as_baseline": 1,
        "defer": 1,
    }
    assert result["defer_records"] == 1
    assert result["reject_records"] == 0
    assert result["approved_as_baseline_records"] == 1
    assert result["baseline_candidate_ready_records"] == 2
    assert result["baseline_ready_records"] == 1
    assert result["requires_baseline_review_records"] == 1
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["groups"][0]["decision"] == "approve_as_baseline"
    assert result["groups"][0]["approved_as_baseline"] is True
    assert result["groups"][0]["baseline_ready"] is True
    assert result["groups"][0]["approved_for_training"] is False
    assert result["groups"][1]["decision"] == "defer"
    assert result["groups"][1]["requires_baseline_review"] is True
    assert result["rejected"][0]["reason"] == "unsupported_source"


def test_run_show_repair_chain_heldout_baseline_decision_review_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "show-repair-chain-heldout-baseline-decision-review should not resolve an API key"
        )

    review_path = tmp_path / "heldout-baseline-decision-review.json"
    review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision_review",
                "review_status": "heldout_baseline_decision_summary_only",
                "records": 2,
                "rejected_records": 0,
                "decision_counts": {"approve_as_baseline": 2},
                "defer_records": 0,
                "reject_records": 0,
                "approved_as_baseline_records": 2,
                "baseline_candidate_ready_records": 2,
                "baseline_ready_records": 2,
                "requires_baseline_review_records": 0,
                "min_repeat": 1,
                "groups": [
                    {
                        "decision": "approve_as_baseline",
                        "count": 2,
                        "approved_as_baseline": True,
                        "baseline_candidate_ready": True,
                        "baseline_ready": True,
                        "requires_baseline_review": False,
                    }
                ],
                "eval_only": True,
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "auto_promoted": False,
                "jsonl_paths": ["heldout-baseline-decisions.jsonl"],
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "show-repair-chain-heldout-baseline-decision-review",
                str(review_path),
            ]
        )
    )

    assert "BIBER repair-chain held-out baseline decision review" in output
    assert "records: 2" in output
    assert "approved_as_baseline_records: 2" in output
    assert "baseline_candidate_ready_records: 2" in output
    assert "baseline_ready_records: 2" in output
    assert "requires_baseline_review_records: 0" in output
    assert "decision_counts: {'approve_as_baseline': 2}" in output
    assert "eval_only: True" in output
    assert "training_allowed: False" in output
    assert "safe_to_train: False" in output
    assert "github_save_ready: False" in output
    assert "approved_for_training: False" in output
    assert f"artifact_path: {review_path}" in output


def test_run_list_repair_chain_heldout_baseline_decision_reviews_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-repair-chain-heldout-baseline-decision-reviews should not resolve an API key"
        )

    ready_artifact = tmp_path / "heldout-baseline-decision-review-ready.json"
    defer_artifact = tmp_path / "heldout-baseline-decision-review-defer.json"
    wrapped_artifact = (
        tmp_path
        / "agent-client-mvp-loop-repair-chain-heldout-baseline-decision-review-result.json"
    )
    ready_review = {
        "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision_review",
        "review_status": "heldout_baseline_decision_summary_only",
        "records": 2,
        "rejected_records": 0,
        "decision_counts": {"approve_as_baseline": 2},
        "defer_records": 0,
        "reject_records": 0,
        "approved_as_baseline_records": 2,
        "baseline_candidate_ready_records": 2,
        "baseline_ready_records": 2,
        "requires_baseline_review_records": 0,
        "min_repeat": 1,
        "groups": [
            {
                "decision": "approve_as_baseline",
                "count": 2,
                "approved_as_baseline": True,
                "baseline_candidate_ready": True,
                "baseline_ready": True,
                "requires_baseline_review": False,
            }
        ],
        "eval_only": True,
        "training_allowed": False,
        "eligible_for_training": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "jsonl_paths": ["heldout-baseline-decisions.jsonl"],
    }
    defer_review = {
        **ready_review,
        "records": 1,
        "decision_counts": {"defer": 1},
        "defer_records": 1,
        "approved_as_baseline_records": 0,
        "baseline_candidate_ready_records": 1,
        "baseline_ready_records": 0,
        "requires_baseline_review_records": 1,
        "groups": [
            {
                "decision": "defer",
                "count": 1,
                "approved_as_baseline": False,
                "baseline_candidate_ready": True,
                "baseline_ready": False,
                "requires_baseline_review": True,
            }
        ],
    }
    wrapped_artifact.write_text(
        json.dumps(
            {
                "status": 0,
                "body": ready_review,
                "output": str(ready_artifact),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    defer_artifact.write_text(
        json.dumps(defer_review, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "list-repair-chain-heldout-baseline-decision-reviews",
                str(tmp_path),
                "--decision",
                "approve_as_baseline",
                "--baseline-ready-only",
                "--limit",
                "5",
            ]
        )
    )
    result = json.loads(output)

    assert (
        result["source"]
        == "biber_mvp_loop_repair_chain_heldout_baseline_decision_review_list"
    )
    assert result["decision"] == "approve_as_baseline"
    assert result["baseline_ready_only"] is True
    assert result["matched"] == 1
    assert result["records"] == 2
    assert result["rejected_records"] == 0
    assert result["defer_records"] == 0
    assert result["approved_as_baseline_records"] == 2
    assert result["baseline_candidate_ready_records"] == 2
    assert result["baseline_ready_records"] == 2
    assert result["requires_baseline_review_records"] == 0
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert len(result["artifacts"]) == 1
    assert result["artifacts"][0]["path"] == str(wrapped_artifact)
    assert result["artifacts"][0]["artifact_path"] == str(ready_artifact)
    assert result["artifacts"][0]["decision_counts"] == {
        "approve_as_baseline": 2
    }
    assert result["artifacts"][0]["baseline_ready_records"] == 2


def test_run_review_repair_chain_training_readiness_blocks_empty_baseline(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-training-readiness should not resolve an API key"
        )

    review_path = tmp_path / "heldout-baseline-decision-review.json"
    output_path = tmp_path / "training-readiness-review.json"
    review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision_review",
                "review_status": "heldout_baseline_decision_summary_only",
                "records": 0,
                "approved_as_baseline_records": 0,
                "baseline_candidate_ready_records": 0,
                "baseline_ready_records": 0,
                "requires_baseline_review_records": 0,
                "decision_counts": {},
                "groups": [],
                "eval_only": True,
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "auto_promoted": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-training-readiness",
                str(review_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_training_readiness_review"
    assert result["review_status"] == "training_blocked"
    assert result["training_gate_status"] == "blocked"
    assert result["supported_review_artifacts"] == 1
    assert result["rejected_artifacts"] == 0
    assert result["baseline_ready_records"] == 0
    assert result["ready_for_manual_training_dataset_review"] is False
    assert result["hard_blockers"] == ["no_baseline_ready_records"]
    assert result["eval_only"] is True
    assert result["training_allowed"] is False
    assert result["eligible_for_training"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["auto_promoted"] is False


def test_run_review_repair_chain_training_readiness_marks_manual_review_ready(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-training-readiness should not resolve an API key"
        )

    review_path = tmp_path / "heldout-baseline-decision-review.json"
    review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision_review",
                "review_status": "heldout_baseline_decision_summary_only",
                "records": 2,
                "approved_as_baseline_records": 2,
                "baseline_candidate_ready_records": 2,
                "baseline_ready_records": 2,
                "requires_baseline_review_records": 0,
                "decision_counts": {"approve_as_baseline": 2},
                "groups": [
                    {
                        "decision": "approve_as_baseline",
                        "count": 2,
                        "baseline_ready": True,
                        "heldout_eval_result_ids": ["result-a", "result-b"],
                        "reviewers": ["baseline-reviewer"],
                    }
                ],
                "eval_only": True,
                "training_allowed": False,
                "eligible_for_training": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
                "auto_promoted": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-training-readiness",
                str(review_path),
                "--min-baseline-ready",
                "2",
            ]
        )
    )
    result = json.loads(output)

    assert result["review_status"] == "baseline_ready_manual_training_review_required"
    assert result["training_gate_status"] == "manual_review_required"
    assert result["baseline_ready_records"] == 2
    assert result["ready_for_manual_training_dataset_review"] is True
    assert result["hard_blockers"] == []
    assert result["baseline_ready_groups"][0]["decision"] == "approve_as_baseline"
    assert result["baseline_ready_groups"][0]["count"] == 2
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["approved_for_training"] is False


def test_run_export_repair_chain_training_candidates_blocks_unready_gate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "export-repair-chain-training-candidates should not resolve an API key"
        )

    readiness_path = tmp_path / "training-readiness.json"
    output_path = tmp_path / "training-candidates.jsonl"
    readiness_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_training_readiness_review",
                "review_status": "training_blocked",
                "training_gate_status": "blocked",
                "baseline_ready_records": 0,
                "ready_for_manual_training_dataset_review": False,
                "hard_blockers": ["no_baseline_ready_records"],
                "baseline_ready_groups": [],
                "training_allowed": False,
                "safe_to_train": False,
                "approved_for_training": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-repair-chain-training-candidates",
                str(readiness_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)

    assert output_path.read_text(encoding="utf-8") == ""
    assert result["source"] == "biber_mvp_loop_repair_chain_training_candidate_export"
    assert result["export_status"] == "training_candidates_blocked"
    assert result["records"] == 0
    assert result["training_candidate_records"] == 0
    assert result["supported_review_artifacts"] == 1
    assert result["skipped_artifacts"] == 1
    assert result["rejected_artifacts"] == 0
    assert result["hard_blockers"] == ["no_baseline_ready_records"]
    assert result["training_dataset_ready"] is False
    assert result["requires_human_training_dataset_review"] is False
    assert result["review_queue_only"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["approved_for_training"] is False


def test_run_export_repair_chain_training_candidates_writes_review_queue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "export-repair-chain-training-candidates should not resolve an API key"
        )

    readiness_path = tmp_path / "training-readiness.json"
    output_path = tmp_path / "training-candidates.jsonl"
    readiness_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_training_readiness_review",
                "review_status": "baseline_ready_manual_training_review_required",
                "training_gate_status": "manual_review_required",
                "baseline_ready_records": 1,
                "ready_for_manual_training_dataset_review": True,
                "hard_blockers": [],
                "baseline_ready_groups": [
                    {
                        "decision": "approve_as_baseline",
                        "count": 2,
                        "heldout_eval_result_ids": ["result-a"],
                        "reviewers": ["baseline-reviewer"],
                    }
                ],
                "training_allowed": False,
                "safe_to_train": False,
                "approved_for_training": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "export-repair-chain-training-candidates",
                str(readiness_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert result["export_status"] == "training_candidates_need_human_review"
    assert result["records"] == 1
    assert result["training_candidate_records"] == 1
    assert result["hard_blockers"] == []
    assert result["training_dataset_ready"] is False
    assert result["requires_human_training_dataset_review"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["approved_for_training"] is False
    assert len(rows) == 1
    assert rows[0]["source"] == "biber_mvp_loop_repair_chain_training_candidate"
    assert rows[0]["quality"] == "needs_review"
    assert rows[0]["output"] == ""
    assert rows[0]["training_candidate_status"] == (
        "needs_human_training_dataset_review"
    )
    assert rows[0]["training_allowed"] is False
    assert rows[0]["safe_to_train"] is False
    assert rows[0]["approved_for_training"] is False
    assert rows[0]["metadata"]["readiness_artifact"] == str(readiness_path)
    assert rows[0]["metadata"]["heldout_eval_result_ids"] == ["result-a"]


def test_run_review_repair_chain_training_candidates_blocks_empty_queue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-training-candidates should not resolve an API key"
        )

    candidates_path = tmp_path / "training-candidates.jsonl"
    review_path = tmp_path / "training-candidate-review.json"
    candidates_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-training-candidates",
                str(candidates_path),
                "--output",
                str(review_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(review_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_training_candidate_review"
    assert result["review_status"] == "training_candidates_need_review"
    assert result["records"] == 0
    assert result["reviewed_records"] == 0
    assert result["pending_review_records"] == 0
    assert result["ready_for_dataset_validation"] is False
    assert result["training_dataset_ready"] is False
    assert result["hard_blockers"] == [
        "no_training_candidate_records",
        "below_min_ready_records",
    ]
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["approved_for_training"] is False


def test_run_review_repair_chain_training_candidates_ready_for_dataset_validation(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-training-candidates should not resolve an API key"
        )

    candidates_path = tmp_path / "training-candidates.jsonl"
    record = {
        "source": "biber_mvp_loop_repair_chain_training_candidate",
        "instruction": "Fix the repeated repo bug.",
        "input": "Repeated failure evidence.",
        "output": "Verified answer.",
        "category": "repo_adaptation",
        "stack": ["repo_adaptation", "biber_repair_chain"],
        "quality": "verified",
        "review_required": False,
        "training_allowed": False,
        "safe_to_train": False,
        "approved_for_training": False,
        "metadata": {
            "readiness_artifact": "training-readiness.json",
            "heldout_eval_result_ids": ["result-a"],
        },
    }
    candidates_path.write_text(
        json.dumps(record, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-training-candidates",
                str(candidates_path),
            ]
        )
    )
    result = json.loads(output)

    assert result["review_status"] == "training_candidates_ready_for_dataset_validation"
    assert result["records"] == 1
    assert result["reviewed_records"] == 1
    assert result["pending_review_records"] == 0
    assert result["empty_output_records"] == 0
    assert result["unreviewed_quality_records"] == 0
    assert result["quality_counts"] == {"verified": 1}
    assert result["ready_for_dataset_validation"] is True
    assert result["training_dataset_ready"] is False
    assert result["hard_blockers"] == []
    assert result["ready_records"][0]["quality"] == "verified"
    assert result["ready_records"][0]["output_ready"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["approved_for_training"] is False


def test_run_review_repair_chain_training_pipeline_blocks_missing_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-training-pipeline should not resolve an API key"
        )

    output_path = tmp_path / "training-pipeline.json"
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-training-pipeline",
                "--artifact-dir",
                str(tmp_path),
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == (
        "biber_mvp_loop_repair_chain_training_pipeline_status"
    )
    assert result["training_pipeline_status"] == "blocked"
    assert result["missing_or_blocked_step"] == "heldout_baseline_decision_review"
    assert result["baseline_ready_records"] == 0
    assert result["training_candidate_records"] == 0
    assert result["ready_for_dataset_validation"] is False
    assert "missing_or_invalid_baseline_decision_review" in result["hard_blockers"]
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["approved_for_training"] is False


def test_run_review_repair_chain_training_pipeline_summarizes_blocked_gate(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "review-repair-chain-training-pipeline should not resolve an API key"
        )

    baseline_review_path = (
        tmp_path
        / "agent-client-mvp-loop-repair-chain-heldout-baseline-decision-review.json"
    )
    readiness_path = (
        tmp_path
        / "agent-client-mvp-loop-repair-chain-training-readiness.json"
    )
    candidates_path = (
        tmp_path
        / "agent-client-mvp-loop-repair-chain-training-candidates.jsonl"
    )
    candidate_review_path = (
        tmp_path
        / "agent-client-mvp-loop-repair-chain-training-candidate-review.json"
    )
    pipeline_path = tmp_path / "training-pipeline.json"
    baseline_review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_heldout_baseline_decision_review",
                "review_status": "heldout_baseline_decision_summary_only",
                "records": 0,
                "baseline_ready_records": 0,
                "groups": [],
                "training_allowed": False,
                "safe_to_train": False,
                "approved_for_training": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    readiness_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_training_readiness_review",
                "review_status": "training_blocked",
                "training_gate_status": "blocked",
                "baseline_ready_records": 0,
                "ready_for_manual_training_dataset_review": False,
                "hard_blockers": ["no_baseline_ready_records"],
                "training_allowed": False,
                "safe_to_train": False,
                "approved_for_training": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    candidates_path.write_text("", encoding="utf-8")
    candidate_review_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_training_candidate_review",
                "review_status": "training_candidates_need_review",
                "records": 0,
                "ready_for_dataset_validation": False,
                "hard_blockers": [
                    "no_training_candidate_records",
                    "below_min_ready_records",
                ],
                "training_allowed": False,
                "safe_to_train": False,
                "approved_for_training": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "review-repair-chain-training-pipeline",
                "--artifact-dir",
                str(tmp_path),
                "--output",
                str(pipeline_path),
            ]
        )
    )
    result = json.loads(output)

    assert json.loads(pipeline_path.read_text(encoding="utf-8")) == result
    assert result["training_pipeline_status"] == "blocked"
    assert result["missing_or_blocked_step"] == "baseline_ready_records"
    assert result["baseline_ready_records"] == 0
    assert result["training_gate_status"] == "blocked"
    assert result["training_candidate_records"] == 0
    assert result["training_candidate_review_records"] == 0
    assert result["ready_for_dataset_validation"] is False
    assert "no_baseline_ready_records" in result["hard_blockers"]
    assert "no_training_candidate_records" in result["hard_blockers"]
    assert result["checks"][0]["ok"] is True
    assert result["checks"][1]["ok"] is True
    assert result["checks"][2]["ok"] is True
    assert result["checks"][3]["ok"] is True
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False


def test_run_list_repair_chain_training_pipelines_filters_ready_artifacts_without_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        raise AssertionError(
            "list-repair-chain-training-pipelines should not resolve an API key"
        )

    blocked_dir = tmp_path / "blocked-smoke"
    ready_dir = tmp_path / "ready-smoke"
    blocked_dir.mkdir()
    ready_dir.mkdir()
    blocked_path = (
        blocked_dir
        / "agent-client-mvp-loop-repair-chain-training-pipeline.json"
    )
    ready_path = (
        ready_dir
        / "agent-client-mvp-loop-repair-chain-training-pipeline.json"
    )
    output_path = tmp_path / "training-pipeline-list.json"
    blocked_path.write_text(
        json.dumps(
            {
                "source": "biber_mvp_loop_repair_chain_training_pipeline_status",
                "training_pipeline_status": "blocked",
                "missing_or_blocked_step": "baseline_ready_records",
                "artifact_dir": str(blocked_dir),
                "baseline_ready_records": 0,
                "training_candidate_records": 0,
                "training_candidate_review_records": 0,
                "ready_for_dataset_validation": False,
                "hard_blockers": ["baseline_ready_records"],
                "training_allowed": False,
                "safe_to_train": False,
                "github_save_ready": False,
                "approved_for_training": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    ready_payload = {
        "source": "biber_mvp_loop_repair_chain_training_pipeline_status",
        "training_pipeline_status": "ready_for_dataset_validation",
        "missing_or_blocked_step": None,
        "artifact_dir": str(ready_dir),
        "baseline_ready_records": 2,
        "training_candidate_records": 2,
        "training_candidate_review_records": 2,
        "ready_for_dataset_validation": True,
        "hard_blockers": [],
        "training_allowed": False,
        "safe_to_train": False,
        "github_save_ready": False,
        "approved_for_training": False,
    }
    ready_path.write_text(
        json.dumps({"status": 0, "body": ready_payload}, sort_keys=True),
        encoding="utf-8",
    )
    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)

    output = client.run(
        client.parse_args(
            [
                "--json",
                "list-repair-chain-training-pipelines",
                str(tmp_path),
                "--ready-only",
                "--output",
                str(output_path),
            ]
        )
    )
    result = json.loads(output)
    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == result
    assert result["source"] == "biber_mvp_loop_repair_chain_training_pipeline_list"
    assert result["scanned"] == 2
    assert result["matched"] == 1
    assert result["ready_for_dataset_validation"] == 1
    assert result["blocked"] == 0
    assert result["training_allowed"] is False
    assert result["safe_to_train"] is False
    assert result["github_save_ready"] is False
    assert result["approved_for_training"] is False
    assert result["artifacts"][0]["path"] == str(ready_path)
    assert result["artifacts"][0]["training_pipeline_status"] == (
        "ready_for_dataset_validation"
    )
    assert result["artifacts"][0]["baseline_ready_records"] == 2
    assert result["artifacts"][0]["training_candidate_records"] == 2
    assert result["artifacts"][0]["ready_for_dataset_validation"] is True
    assert result["artifacts"][0]["training_allowed"] is False
    assert result["artifacts"][0]["safe_to_train"] is False
    assert result["artifacts"][0]["approved_for_training"] is False


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
            "--runtime-profile-id",
            "rust-xriq-codegen",
            "--runtime-profile-id",
            "rust-xriq-codegen",
            "--no-test",
            "--max-tokens",
            "24",
        ]
    )

    output = client.run(args)

    assert captured_payload["instruction"] == "Say ok."
    assert captured_payload["repo_context_paths"] == ["README.md"]
    assert captured_payload["runtime_profile_ids"] == ["rust-xriq-codegen"]
    assert captured_payload["test_id"] is None
    assert captured_payload["max_tokens"] == 24
    assert json.loads(output)["id"] == "session-1"


def test_run_chat_json_sends_runtime_profile_ids(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_resolve_api_key(cli_api_key: str | None = None) -> str:
        return "test-key"

    def fake_fetch_capabilities(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["capabilities_base_url"] = base_url
        return sample_capabilities()

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
            "model": "biber-dev-core-v1",
            "content": "ok",
            "mentor_used": False,
            "priority": 3,
        }

    monkeypatch.setattr(client, "resolve_api_key", fake_resolve_api_key)
    monkeypatch.setattr(client, "fetch_capabilities", fake_fetch_capabilities)
    monkeypatch.setattr(client, "chat_with_biber", fake_chat_with_biber)

    args = client.parse_args(
        [
            "--json",
            "chat",
            "--message",
            "Return ok.",
            "--language",
            "Rust",
            "--task-type",
            "xriq_private_devnet_review",
            "--repo-context",
            "README.md",
            "--runtime-profile-id",
            "rust-xriq-codegen",
            "--max-tokens",
            "24",
        ]
    )

    output = client.run(args)

    assert captured["capabilities_base_url"] == "http://127.0.0.1:8000"
    assert captured["api_key"] == "test-key"
    assert captured["payload"] == {
        "messages": [{"role": "user", "content": "Return ok."}],
        "use_mentor": False,
        "language": "Rust",
        "task_type": "xriq_private_devnet_review",
        "repo_context_paths": ["README.md"],
        "runtime_profile_ids": ["rust-xriq-codegen"],
        "max_tokens": 24,
        "temperature": 0.2,
    }
    assert json.loads(output)["id"] == "chat-1"


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

    def fake_fetch_capabilities(
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
    ) -> dict[str, object]:
        captured["capabilities_base_url"] = base_url
        return sample_capabilities()

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
    monkeypatch.setattr(client, "fetch_capabilities", fake_fetch_capabilities)
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
            "--runtime-profile-id",
            "rust-xriq-codegen",
            "--runtime-profile-id",
            "rust-xriq-codegen",
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
    assert result["runtime_profile_ids"] == ["rust-xriq-codegen"]
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
