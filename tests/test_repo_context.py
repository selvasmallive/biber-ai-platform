from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from biber_api.config import BiberSettings
from biber_api.llm import BiberChatService, ModelResult
from biber_api.repo_context import RepoContextError, build_repo_context_message
from biber_api.schemas import ChatMessage, ChatRequest


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int | None,
    ) -> ModelResult:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return ModelResult(content="local answer", raw={})


def settings(root: Path) -> BiberSettings:
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
        repo_context_root=str(root),
        repo_context_max_files=4,
        repo_context_max_bytes_per_file=80,
        repo_context_max_total_bytes=200,
    )


def test_build_repo_context_message_includes_selected_files(tmp_path: Path) -> None:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def hello() -> str:\n    return 'hello'\n", encoding="utf-8")

    context = build_repo_context_message(
        ["src/service.py"],
        root=str(tmp_path),
        max_files=4,
        max_bytes_per_file=200,
        max_total_bytes=500,
    )

    assert context is not None
    assert "Repository context from selected files" in context
    assert "--- FILE: src/service.py" in context
    assert "def hello" in context


def test_repo_context_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    with pytest.raises(RepoContextError, match="escapes"):
        build_repo_context_message(
            ["../secret.txt"],
            root=str(tmp_path),
            max_files=4,
            max_bytes_per_file=200,
            max_total_bytes=500,
        )


def test_repo_context_rejects_absolute_paths(tmp_path: Path) -> None:
    source = tmp_path / "src" / "service.py"
    source.parent.mkdir()
    source.write_text("def hello() -> str:\n    return 'hello'\n", encoding="utf-8")

    with pytest.raises(RepoContextError, match="workspace-relative"):
        build_repo_context_message(
            [str(source)],
            root=str(tmp_path),
            max_files=4,
            max_bytes_per_file=200,
            max_total_bytes=500,
        )


def test_repo_context_rejects_secret_like_paths(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("OPENAI_API_KEY=secret\n", encoding="utf-8")

    with pytest.raises(RepoContextError, match="not allowed"):
        build_repo_context_message(
            [".env"],
            root=str(tmp_path),
            max_files=4,
            max_bytes_per_file=200,
            max_total_bytes=500,
        )


def test_repo_context_rejects_denied_paths_case_insensitively(tmp_path: Path) -> None:
    source = tmp_path / "Node_Modules" / "package" / "index.js"
    source.parent.mkdir(parents=True)
    source.write_text("console.log('skip me')\n", encoding="utf-8")

    with pytest.raises(RepoContextError, match="not allowed"):
        build_repo_context_message(
            ["Node_Modules/package/index.js"],
            root=str(tmp_path),
            max_files=4,
            max_bytes_per_file=200,
            max_total_bytes=500,
        )


def test_repo_context_truncates_large_files(tmp_path: Path) -> None:
    source = tmp_path / "large.txt"
    source.write_text("abcdefghij" * 20, encoding="utf-8")

    context = build_repo_context_message(
        ["large.txt"],
        root=str(tmp_path),
        max_files=4,
        max_bytes_per_file=25,
        max_total_bytes=25,
    )

    assert context is not None
    assert "truncated" in context
    assert "abcdefghijabcdefghijabcde" in context


def test_chat_service_injects_repo_context_into_local_prompt(tmp_path: Path) -> None:
    source = tmp_path / "xriq" / "wallet.rs"
    source.parent.mkdir()
    source.write_text("pub fn sign() {}\n", encoding="utf-8")
    service = BiberChatService(settings(tmp_path))
    local = FakeClient()
    service._local = local

    content, mentor_notes, _, model_id = asyncio.run(
        service.generate(
            ChatRequest(
                messages=[ChatMessage(role="user", content="Explain this file.")],
                language="Rust",
                repo_context_paths=["xriq/wallet.rs"],
            )
        )
    )

    system_prompt = local.calls[0]["messages"][0]["content"]
    assert content == "local answer"
    assert mentor_notes is None
    assert model_id == "biber-dev-core-v1"
    assert "--- FILE: xriq/wallet.rs" in system_prompt
    assert "pub fn sign" in system_prompt
