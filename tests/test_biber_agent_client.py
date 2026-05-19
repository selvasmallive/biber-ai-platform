from __future__ import annotations

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
