#!/usr/bin/env python3
"""Bridge BIBER local model-command requests to an OpenAI-compatible endpoint."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8001/v1"
DEFAULT_TIMEOUT_SECONDS = 180.0
REQUEST_SOURCE = "biber_local_model_command_request"


class LocalProviderError(RuntimeError):
    pass


def read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise LocalProviderError("Expected BIBER local model-command JSON on stdin.")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LocalProviderError(f"stdin must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LocalProviderError("stdin JSON must be an object.")
    return parsed


def normalize_chat_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    if clean.endswith("/v1"):
        return f"{clean}/chat/completions"
    return f"{clean}/v1/chat/completions"


def require_request(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("source") != REQUEST_SOURCE:
        raise LocalProviderError(
            f"Expected request source {REQUEST_SOURCE}, got {payload.get('source')!r}."
        )
    chat_payload = payload.get("chat_payload")
    if not isinstance(chat_payload, dict):
        raise LocalProviderError("Request must include chat_payload object.")
    messages = chat_payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise LocalProviderError("chat_payload.messages must be a non-empty list.")
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise LocalProviderError(f"messages[{index}] must be an object.")
        if not isinstance(message.get("role"), str) or not isinstance(
            message.get("content"),
            str,
        ):
            raise LocalProviderError(
                f"messages[{index}] must include string role and content."
            )
    return dict(chat_payload)


def resolve_model(
    *,
    request: Mapping[str, Any],
    chat_payload: Mapping[str, Any],
    cli_model: str | None,
) -> str:
    model = (
        cli_model
        or os.getenv("BIBER_LOCAL_OPENAI_MODEL")
        or os.getenv("BIBER_LOCAL_MODEL_NAME")
        or chat_payload.get("model")
        or request.get("model")
    )
    if not isinstance(model, str) or not model.strip():
        raise LocalProviderError(
            "Model is required. Pass --model or set BIBER_LOCAL_OPENAI_MODEL."
        )
    return model.strip()


def build_chat_completions_payload(
    request: Mapping[str, Any],
    *,
    model: str | None,
    max_tokens: int | None,
    temperature: float | None,
) -> dict[str, Any]:
    chat_payload = require_request(request)
    resolved_model = resolve_model(
        request=request,
        chat_payload=chat_payload,
        cli_model=model,
    )
    resolved_temperature = (
        temperature
        if temperature is not None
        else float(chat_payload.get("temperature") or 0.0)
    )
    resolved_max_tokens = (
        max_tokens
        if max_tokens is not None
        else chat_payload.get("max_tokens")
    )
    provider_payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": chat_payload["messages"],
        "temperature": resolved_temperature,
        "stream": False,
    }
    if isinstance(resolved_max_tokens, int) and resolved_max_tokens > 0:
        provider_payload["max_tokens"] = resolved_max_tokens
    return provider_payload


def request_chat_completion(
    *,
    base_url: str,
    api_key: str | None,
    payload: Mapping[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        normalize_chat_url(base_url),
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        raise LocalProviderError(
            f"local OpenAI-compatible endpoint returned HTTP {exc.code}: {body}"
        ) from exc
    except urllib.error.URLError as exc:
        raise LocalProviderError(
            f"local OpenAI-compatible endpoint request failed: {exc}"
        ) from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LocalProviderError(f"endpoint returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LocalProviderError("endpoint response must be a JSON object.")
    return parsed


def extract_message_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LocalProviderError("endpoint response must include choices.")
    first = choices[0]
    if not isinstance(first, dict):
        raise LocalProviderError("endpoint response choices[0] must be an object.")
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        content = message["content"].strip()
        if content:
            return content
    if isinstance(first.get("text"), str) and first["text"].strip():
        return first["text"].strip()
    raise LocalProviderError(
        "endpoint response must include choices[0].message.content or choices[0].text."
    )


def build_command_output(
    *,
    content: str,
    response: Mapping[str, Any] | None,
    provider_payload: Mapping[str, Any],
    base_url: str,
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "content": content,
        "provider": "openai-compatible-local",
        "base_url": base_url,
        "model": provider_payload.get("model"),
        "mentor_used": False,
        "training_allowed": False,
        "api_required": False,
    }
    if response is not None:
        if response.get("model"):
            output["response_model"] = response.get("model")
        if isinstance(response.get("usage"), dict):
            output["usage"] = response.get("usage")
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read a BIBER local model-command request on stdin, call a local "
            "OpenAI-compatible chat/completions endpoint, and print JSON with a "
            "content field for local-repair-chain."
        )
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIBER_LOCAL_OPENAI_BASE_URL", DEFAULT_BASE_URL),
        help=(
            "OpenAI-compatible base URL. Defaults to BIBER_LOCAL_OPENAI_BASE_URL "
            f"or {DEFAULT_BASE_URL}."
        ),
    )
    parser.add_argument("--model", help="Provider model name or local served alias.")
    parser.add_argument(
        "--api-key-env",
        default="BIBER_LOCAL_OPENAI_API_KEY",
        help="Environment variable containing an optional bearer token.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the provider request payload without calling the endpoint.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        request = read_stdin_json()
        provider_payload = build_chat_completions_payload(
            request,
            model=args.model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        if args.dry_run:
            output = build_command_output(
                content=json.dumps(provider_payload, sort_keys=True),
                response=None,
                provider_payload=provider_payload,
                base_url=args.base_url,
            )
        else:
            response = request_chat_completion(
                base_url=args.base_url,
                api_key=os.getenv(args.api_key_env),
                payload=provider_payload,
                timeout_seconds=args.timeout_seconds,
            )
            output = build_command_output(
                content=extract_message_content(response),
                response=response,
                provider_payload=provider_payload,
                base_url=args.base_url,
            )
    except LocalProviderError as exc:
        print(f"biber_local_openai_provider: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
