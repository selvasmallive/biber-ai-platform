from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import BiberSettings
from .schemas import ChatMessage, ChatRequest


BIBER_SYSTEM_PROMPT = """You are biber-dev-core, BIBER's private software development model.
Produce practical, secure, maintainable code. Prefer concise explanations, clear file names,
and tests when the task changes behavior. Do not claim production readiness without evidence."""


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


class BiberChatService:
    def __init__(self, settings: BiberSettings) -> None:
        self._settings = settings
        self._local = OpenAICompatibleClient(
            base_url=settings.local_model_base_url,
            model=settings.local_model_name,
            timeout_seconds=settings.local_model_timeout_seconds,
        )
        self._mentor = None
        if settings.mentor_enabled and settings.openai_api_key and settings.openai_model:
            self._mentor = OpenAICompatibleClient(
                base_url=settings.openai_base_url,
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                timeout_seconds=90,
            )

    @property
    def mentor_connected(self) -> bool:
        return self._mentor is not None

    async def generate(self, request: ChatRequest) -> tuple[str, str | None, dict[str, Any]]:
        mentor_notes = None
        messages = self._build_local_messages(request, mentor_notes=None)

        if request.use_mentor and self._mentor:
            mentor_notes = await self._get_mentor_notes(request)
            messages = self._build_local_messages(request, mentor_notes=mentor_notes)

        result = await self._local.chat(
            messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        return result.content, mentor_notes, result.raw

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
