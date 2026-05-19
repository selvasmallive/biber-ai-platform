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
