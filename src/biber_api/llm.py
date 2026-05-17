from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import BiberSettings
from .model_registry import (
    ModelRegistryError,
    ModelSpec,
    build_model_registry,
    OPENAI_COMPATIBLE_CHAT,
)
from .schemas import ChatMessage, ChatRequest


BIBER_SYSTEM_PROMPT = """You are biber-dev-core, BIBER's private software development model.
Produce practical, secure, maintainable code. Prefer concise explanations, clear file names,
and tests when the task changes behavior. Do not claim production readiness without evidence."""

MENTOR_TRIGGER_PHRASE = "Review with OpenAI mentor"


@dataclass(frozen=True)
class ModelResult:
    content: str
    raw: dict[str, Any]


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 180,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int | None,
    ) -> ModelResult:
        headers: dict[str, str] = {"content-type": "application/json"}
        if self._api_key:
            headers["authorization"] = f"Bearer {self._api_key}"

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return ModelResult(content=content, raw=data)


class OpenAIResponsesClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: float = 90,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float,
        max_tokens: int | None,
    ) -> ModelResult:
        headers = {
            "authorization": f"Bearer {self._api_key}",
            "content-type": "application/json",
        }
        instructions, input_text = self._split_messages(messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "input": input_text,
            "store": False,
            "temperature": temperature,
        }
        if instructions:
            payload["instructions"] = instructions
        if max_tokens:
            payload["max_output_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/responses",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        return ModelResult(content=self._extract_response_text(data), raw=data)

    @staticmethod
    def _split_messages(messages: list[dict[str, str]]) -> tuple[str, str]:
        instructions: list[str] = []
        inputs: list[str] = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role in {"system", "developer"}:
                instructions.append(content)
            else:
                inputs.append(f"{role}: {content}")
        return "\n\n".join(instructions), "\n\n".join(inputs)

    @staticmethod
    def _extract_response_text(data: dict[str, Any]) -> str:
        output_text = data.get("output_text")
        if isinstance(output_text, str) and output_text:
            return output_text

        parts: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str):
                    parts.append(text)
        if parts:
            return "\n".join(parts)
        raise KeyError("OpenAI Responses API response did not include output text")


class BiberChatService:
    def __init__(self, settings: BiberSettings) -> None:
        self._settings = settings
        self._registry = build_model_registry(settings)
        self._providers = {
            model.id: self._build_provider(model)
            for model in self._registry.models
            if model.enabled
        }
        stable_model = self._registry.resolve(self._registry.stable_model)
        self._local = self._providers[stable_model.id]
        self._mentor = None
        if settings.mentor_enabled and settings.openai_api_key and settings.openai_model:
            self._mentor = OpenAIResponsesClient(
                base_url=settings.openai_base_url,
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                timeout_seconds=90,
            )

    @property
    def mentor_connected(self) -> bool:
        return self._mentor is not None

    async def generate(self, request: ChatRequest) -> tuple[str, str | None, dict[str, Any], str]:
        selected_model = self._registry.resolve(request.model)
        provider = self._provider_for(selected_model)
        mentor_notes = None
        messages = self._build_local_messages(request, mentor_notes=None)

        if request.use_mentor and self._mentor and self._has_mentor_trigger(request.messages):
            mentor_notes = await self._get_mentor_notes(request)
            messages = self._build_local_messages(request, mentor_notes=mentor_notes)

        result = await provider.chat(
            messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return result.content, mentor_notes, result.raw, selected_model.id

    def _build_provider(self, model: ModelSpec) -> OpenAICompatibleClient:
        if model.provider_type != OPENAI_COMPATIBLE_CHAT:
            raise ModelRegistryError(f"Unsupported provider type: {model.provider_type}")
        return OpenAICompatibleClient(
            base_url=model.base_url,
            model=model.provider_model,
            timeout_seconds=self._settings.local_model_timeout_seconds,
        )

    def _provider_for(self, model: ModelSpec) -> OpenAICompatibleClient:
        if model.id == self._registry.stable_model:
            return self._local
        return self._providers[model.id]

    async def _get_mentor_notes(self, request: ChatRequest) -> str:
        assert self._mentor is not None
        task = self._latest_user_message(request.messages)
        mentor_messages = [
            {
                "role": "system",
                "content": (
                    "You are the BIBER mentor layer. Give short engineering guidance for a "
                    "local coding model. Focus on architecture, edge cases, tests, and security."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Task type: {request.task_type}\n"
                    f"Language/platform: {request.language or 'unspecified'}\n\n"
                    f"Developer request:\n{task}"
                ),
            },
        ]
        result = await self._mentor.chat(mentor_messages, temperature=0.2, max_tokens=700)
        return result.content

    def _build_local_messages(
        self,
        request: ChatRequest,
        *,
        mentor_notes: str | None,
    ) -> list[dict[str, str]]:
        system_parts = [
            BIBER_SYSTEM_PROMPT,
            f"Task type: {request.task_type}.",
        ]
        if request.language:
            system_parts.append(f"Primary language/platform: {request.language}.")
        if mentor_notes:
            system_parts.append(f"Mentor guidance to consider:\n{mentor_notes}")

        return [
            {"role": "system", "content": "\n\n".join(system_parts)},
            *[self._message_to_dict(message) for message in request.messages],
        ]

    @staticmethod
    def _message_to_dict(message: ChatMessage) -> dict[str, str]:
        return {"role": message.role, "content": message.content}

    @staticmethod
    def _latest_user_message(messages: list[ChatMessage]) -> str:
        for message in reversed(messages):
            if message.role == "user":
                return message.content
        return messages[-1].content if messages else ""

    @staticmethod
    def _has_mentor_trigger(messages: list[ChatMessage]) -> bool:
        trigger = MENTOR_TRIGGER_PHRASE.casefold()
        return any(
            message.role == "user" and trigger in message.content.casefold()
            for message in messages
        )
