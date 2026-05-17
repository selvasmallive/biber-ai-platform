from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from biber_api.config import BiberSettings
from biber_api.llm import BiberChatService, ModelResult
from biber_api.main import app
from biber_api.model_registry import (
    DisabledModelError,
    build_model_registry,
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
        mentor_enabled=False,
        openai_base_url="https://api.openai.com/v1",
        openai_api_key=None,
        openai_model=None,
        github_token=None,
        github_default_owner=None,
        github_default_repo=None,
        azure_storage_connection_string=None,
        azure_blob_container="biber-backups",
    )


def chat_request(model: str | None = None) -> ChatRequest:
    return ChatRequest(
        messages=[ChatMessage(role="user", content="Write a tiny Rust helper.")],
        model=model,
    )


def test_default_registry_exposes_stable_and_disabled_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIBER_MODEL_REGISTRY_JSON", raising=False)
    monkeypatch.delenv("BIBER_CANDIDATE_MODEL_ENABLED", raising=False)

    registry = build_model_registry(settings())
    response = registry.as_response()

    assert response["default_model"] == "biber-dev-core-v1"
    assert response["stable_model"] == "biber-dev-core-v1"
    assert response["candidate_model"] == "biber-dev-core-v2-candidate"
    assert registry.resolve("biber-dev-core").id == "biber-dev-core-v1"
    assert registry.resolve("biber-dev-core-v1").provider_model == "biber-dev-core"
    with pytest.raises(DisabledModelError):
        registry.resolve("biber-dev-core-v2-candidate")


def test_candidate_model_can_be_enabled_for_eval_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BIBER_CANDIDATE_MODEL_ENABLED", "true")
    monkeypatch.setenv("BIBER_CANDIDATE_MODEL_BASE_URL", "http://candidate-model/v1")
    monkeypatch.setenv("BIBER_CANDIDATE_PROVIDER_MODEL", "qwen3-coder-next")

    registry = build_model_registry(settings())

    candidate = registry.resolve("biber-dev-core-v2-candidate")
    assert candidate.base_url == "http://candidate-model/v1"
    assert candidate.provider_model == "qwen3-coder-next"
    assert candidate.lifecycle == "candidate"


def test_chat_service_routes_requested_candidate_to_candidate_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BIBER_CANDIDATE_MODEL_ENABLED", "true")
    monkeypatch.setenv("BIBER_CANDIDATE_PROVIDER_MODEL", "qwen3-coder-next")
    service = BiberChatService(settings())
    stable = FakeClient("stable")
    candidate = FakeClient("candidate")
    service._local = stable
    service._providers["biber-dev-core-v2-candidate"] = candidate

    content, _, _, model_id = asyncio.run(
        service.generate(chat_request("biber-dev-core-v2-candidate"))
    )

    assert content == "candidate"
    assert model_id == "biber-dev-core-v2-candidate"
    assert len(stable.calls) == 0
    assert len(candidate.calls) == 1


def test_models_endpoint_returns_registry_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIBER_MODEL_REGISTRY_JSON", raising=False)
    monkeypatch.delenv("BIBER_CANDIDATE_MODEL_ENABLED", raising=False)

    response = TestClient(app).get("/v1/models")

    assert response.status_code == 200
    body = response.json()
    assert body["default_model"] == "biber-dev-core-v1"
    assert body["candidate_model"] == "biber-dev-core-v2-candidate"
    assert body["models"][0]["provider_type"] == "openai-compatible-chat"
