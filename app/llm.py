from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings
from app.model_registry import (
    ModelRegistryError,
    ModelSpec,
    build_model_registry,
    OPENAI_COMPATIBLE_CHAT,
)


BIBER_SYSTEM_PROMPT = """You are biber-dev-core, BIBER's private software development model.
Produce practical, secure, maintainable code. Prefer clear file names, concise explanations,
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
    def __init__(self) -> None:
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

    async def generate(
        self,
        *,
        messages: list[dict[str, str]],
        language: str | None,
        task_type: str,
        use_mentor: bool,
        model: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> tuple[str, str | None, dict[str, Any], str]:
        selected_model = self._registry.resolve(model)
        provider = self._provider_for(selected_model)
        mentor_notes = None
        local_messages = self._build_local_messages(
            messages=messages,
            language=language,
            task_type=task_type,
            mentor_notes=None,
        )

        if use_mentor and self._mentor and self._has_mentor_trigger(messages):
            mentor_notes = await self._get_mentor_notes(messages, language, task_type)
            local_messages = self._build_local_messages(
                messages=messages,
                language=language,
                task_type=task_type,
                mentor_notes=mentor_notes,
            )

        result = await provider.chat(
            local_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result.content, mentor_notes, result.raw, selected_model.id

    def _build_provider(self, model: ModelSpec) -> OpenAICompatibleClient:
        if model.provider_type != OPENAI_COMPATIBLE_CHAT:
            raise ModelRegistryError(f"Unsupported provider type: {model.provider_type}")
        return OpenAICompatibleClient(
            base_url=model.base_url,
            model=model.provider_model,
            timeout_seconds=settings.local_model_timeout_seconds,
        )

    def _provider_for(self, model: ModelSpec) -> OpenAICompatibleClient:
        if model.id == self._registry.stable_model:
            return self._local
        return self._providers[model.id]

    async def _get_mentor_notes(
        self,
        messages: list[dict[str, str]],
        language: str | None,
        task_type: str,
    ) -> str:
        assert self._mentor is not None
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
                    f"Task type: {task_type}\n"
                    f"Language/platform: {language or 'unspecified'}\n\n"
                    f"Developer request:\n{self._latest_user_message(messages)}"
                ),
            },
        ]
        result = await self._mentor.chat(mentor_messages, temperature=0.2, max_tokens=700)
        return result.content

    def _build_local_messages(
        self,
        *,
        messages: list[dict[str, str]],
        language: str | None,
        task_type: str,
        mentor_notes: str | None,
    ) -> list[dict[str, str]]:
        system_parts = [
            BIBER_SYSTEM_PROMPT,
            f"Task type: {task_type}.",
        ]
        if language:
            system_parts.append(f"Primary language/platform: {language}.")
        if mentor_notes:
            system_parts.append(f"Mentor guidance to consider:\n{mentor_notes}")

        return [
            {"role": "system", "content": "\n\n".join(system_parts)},
            *messages,
        ]

    @staticmethod
    def _latest_user_message(messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content", "")
        return messages[-1].get("content", "") if messages else ""

    @staticmethod
    def _has_mentor_trigger(messages: list[dict[str, str]]) -> bool:
        trigger = MENTOR_TRIGGER_PHRASE.casefold()
        return any(
            message.get("role") == "user" and trigger in message.get("content", "").casefold()
            for message in messages
        )
