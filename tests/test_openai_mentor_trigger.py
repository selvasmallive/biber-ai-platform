from __future__ import annotations

import asyncio
from typing import Any

from biber_api.config import BiberSettings
from biber_api.llm import (
    BiberChatService,
    MENTOR_TRIGGER_PHRASE,
    ModelResult,
    OpenAIResponsesClient,
)
from biber_api.schemas import ChatMessage, ChatRequest


class FakeClient:
    def __init__(self, content: str) -> None:
        self.content = content
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
        return ModelResult(content=self.content, raw={"content": self.content})


def settings() -> BiberSettings:
    return BiberSettings(
        env="test",
        api_keys=("test-key",),
        priority_passcodes={},
        local_model_base_url="http://local-model/v1",
        local_model_name="biber-dev-core",
        local_model_timeout_seconds=1,
        mentor_enabled=True,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key="test-openai-key",
        openai_model="mentor-model",
        github_token=None,
        github_default_owner=None,
        github_default_repo=None,
        azure_storage_connection_string=None,
        azure_blob_container="biber-backups",
    )


def request(content: str, *, use_mentor: bool = True) -> ChatRequest:
    return ChatRequest(
        messages=[ChatMessage(role="user", content=content)],
        use_mentor=use_mentor,
    )


def service_with_fakes() -> tuple[BiberChatService, FakeClient, FakeClient]:
    service = BiberChatService(settings())
    local = FakeClient("local answer")
    mentor = FakeClient("mentor notes")
    service._local = local
    service._mentor = mentor
    return service, local, mentor


def test_mentor_not_called_without_trigger_phrase() -> None:
    service, local, mentor = service_with_fakes()

    content, mentor_notes, _ = asyncio.run(service.generate(request("Write a Rust module.")))

    assert content == "local answer"
    assert mentor_notes is None
    assert len(mentor.calls) == 0
    assert "Mentor guidance" not in local.calls[0]["messages"][0]["content"]


def test_mentor_called_when_prompt_contains_trigger_phrase() -> None:
    service, local, mentor = service_with_fakes()

    content, mentor_notes, _ = asyncio.run(
        service.generate(request(f"{MENTOR_TRIGGER_PHRASE}: review this wallet design."))
    )

    assert content == "local answer"
    assert mentor_notes == "mentor notes"
    assert len(mentor.calls) == 1
    assert "Mentor guidance to consider:\nmentor notes" in local.calls[0]["messages"][0]["content"]


def test_use_mentor_false_disables_trigger_phrase() -> None:
    service, _, mentor = service_with_fakes()

    _, mentor_notes, _ = asyncio.run(
        service.generate(
            request(f"{MENTOR_TRIGGER_PHRASE}: review this consensus change.", use_mentor=False)
        )
    )

    assert mentor_notes is None
    assert len(mentor.calls) == 0


def test_responses_client_extracts_output_text_shapes() -> None:
    assert OpenAIResponsesClient._extract_response_text({"output_text": "direct"}) == "direct"
    assert (
        OpenAIResponsesClient._extract_response_text(
            {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": "nested"},
                        ]
                    }
                ]
            }
        )
        == "nested"
    )
