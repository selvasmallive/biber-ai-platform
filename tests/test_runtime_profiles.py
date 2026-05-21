from __future__ import annotations

import asyncio
from typing import Any

from biber_api.config import BiberSettings
from biber_api.llm import BiberChatService, ModelResult
from biber_api.runtime_profiles import (
    API_ERROR_RESPONSE_PROFILE_ID,
    RUST_XRIQ_CODEGEN_PROFILE_ID,
    build_runtime_profiles_prompt,
)
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


def settings(*, runtime_profiles_enabled: bool) -> BiberSettings:
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
        runtime_profiles_enabled=runtime_profiles_enabled,
    )


def test_runtime_profiles_are_injected_when_enabled() -> None:
    service = BiberChatService(settings(runtime_profiles_enabled=True))
    local = FakeClient()
    service._local = local

    content, mentor_notes, _, model_id = asyncio.run(
        service.generate(
            ChatRequest(
                messages=[ChatMessage(role="user", content="Show a missing API key error.")],
                runtime_profile_ids=[
                    API_ERROR_RESPONSE_PROFILE_ID,
                    RUST_XRIQ_CODEGEN_PROFILE_ID,
                ],
            )
        )
    )

    system_prompt = local.calls[0]["messages"][0]["content"]
    assert content == "local answer"
    assert mentor_notes is None
    assert model_id == "biber-dev-core-v1"
    assert "top-level numeric `status` field" in system_prompt
    assert "Return only Rust code." in system_prompt


def test_runtime_profiles_are_ignored_when_disabled() -> None:
    service = BiberChatService(settings(runtime_profiles_enabled=False))
    local = FakeClient()
    service._local = local

    asyncio.run(
        service.generate(
            ChatRequest(
                messages=[ChatMessage(role="user", content="Show a rate limit error.")],
                runtime_profile_ids=[API_ERROR_RESPONSE_PROFILE_ID],
            )
        )
    )

    system_prompt = local.calls[0]["messages"][0]["content"]
    assert "top-level numeric `status` field" not in system_prompt


def test_runtime_profile_prompt_deduplicates_and_ignores_unknown_ids() -> None:
    prompt = build_runtime_profiles_prompt(
        [
            API_ERROR_RESPONSE_PROFILE_ID,
            "unknown-profile",
            API_ERROR_RESPONSE_PROFILE_ID,
        ]
    )

    assert prompt is not None
    assert prompt.count("[api-error-response]") == 1
    assert "unknown-profile" not in prompt
