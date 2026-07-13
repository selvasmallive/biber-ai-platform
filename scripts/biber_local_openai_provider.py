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
STABLE_MODEL_ID = "biber-dev-core-v1"
CANDIDATE_MODEL_ID = "biber-dev-core-v2-candidate"
DEFAULT_PROVIDER_MODEL = "biber-dev-core"


class LocalProviderError(RuntimeError):
    pass


def clean_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def bool_env(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def csv_env(key: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    value = os.getenv(key)
    if not value:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


def registry_entries_from_env() -> list[dict[str, Any]]:
    raw_registry = os.getenv("BIBER_MODEL_REGISTRY_JSON")
    if raw_registry:
        try:
            parsed = json.loads(raw_registry)
        except json.JSONDecodeError as exc:
            raise LocalProviderError(
                f"BIBER_MODEL_REGISTRY_JSON is invalid JSON: {exc}"
            ) from exc
        models = parsed.get("models") if isinstance(parsed, dict) else None
        if not isinstance(models, list) or not models:
            raise LocalProviderError(
                "BIBER_MODEL_REGISTRY_JSON must include a non-empty models list."
            )
        entries: list[dict[str, Any]] = []
        for index, item in enumerate(models):
            if not isinstance(item, dict):
                raise LocalProviderError(
                    f"BIBER_MODEL_REGISTRY_JSON models[{index}] must be an object."
                )
            model_id = clean_string(item.get("id"))
            provider_model = clean_string(item.get("provider_model"))
            if not model_id or not provider_model:
                raise LocalProviderError(
                    "Each registry model must include string id and provider_model."
                )
            raw_aliases = item.get("aliases", ())
            if not isinstance(raw_aliases, (list, tuple)):
                raw_aliases = ()
            entries.append(
                {
                    "id": model_id,
                    "aliases": tuple(
                        alias
                        for alias in raw_aliases
                        if isinstance(alias, str) and alias.strip()
                    ),
                    "base_url": clean_string(item.get("base_url")),
                    "provider_id": clean_string(item.get("provider_id")),
                    "provider_model": provider_model,
                    "provider_type": clean_string(item.get("provider_type")),
                    "lifecycle": clean_string(item.get("lifecycle")),
                    "enabled": bool(item.get("enabled", True)),
                    "source": "env:BIBER_MODEL_REGISTRY_JSON",
                }
            )
        return entries

    stable_id = os.getenv("BIBER_STABLE_MODEL_ID", STABLE_MODEL_ID)
    stable_provider_model = os.getenv("BIBER_LOCAL_MODEL_NAME", DEFAULT_PROVIDER_MODEL)
    stable_aliases = csv_env(
        "BIBER_STABLE_MODEL_ALIASES",
        ("biber-dev-core", stable_provider_model),
    )
    candidate_id = os.getenv("BIBER_CANDIDATE_MODEL_ID", CANDIDATE_MODEL_ID)
    candidate_provider_model = (
        os.getenv("BIBER_CANDIDATE_PROVIDER_MODEL")
        or os.getenv("BIBER_CANDIDATE_MODEL_NAME")
        or candidate_id
    )
    return [
        {
            "id": stable_id,
            "aliases": tuple(dict.fromkeys(stable_aliases)),
            "base_url": None,
            "provider_id": os.getenv("BIBER_LOCAL_PROVIDER_ID", "local-openai"),
            "provider_model": stable_provider_model,
            "provider_type": "openai-compatible-chat",
            "lifecycle": "stable",
            "enabled": True,
            "source": "default:stable-model",
        },
        {
            "id": candidate_id,
            "aliases": csv_env("BIBER_CANDIDATE_MODEL_ALIASES", ()),
            "base_url": clean_string(os.getenv("BIBER_CANDIDATE_MODEL_BASE_URL")),
            "provider_id": os.getenv(
                "BIBER_CANDIDATE_PROVIDER_ID",
                "local-openai-candidate",
            ),
            "provider_model": candidate_provider_model,
            "provider_type": "openai-compatible-chat",
            "lifecycle": "candidate",
            "enabled": bool_env(
                os.getenv("BIBER_CANDIDATE_MODEL_ENABLED"),
                default=False,
            ),
            "source": "default:candidate-model",
        },
    ]


def find_registry_entry(model_id: str | None) -> dict[str, Any] | None:
    if not model_id:
        return None
    for entry in registry_entries_from_env():
        aliases = entry.get("aliases")
        if model_id == entry.get("id") or (
            isinstance(aliases, tuple) and model_id in aliases
        ):
            return entry
    return None


def requested_logical_model(
    request: Mapping[str, Any],
    chat_payload: Mapping[str, Any],
) -> str:
    return (
        clean_string(chat_payload.get("model"))
        or clean_string(request.get("model"))
        or clean_string(os.getenv("BIBER_DEFAULT_MODEL"))
        or STABLE_MODEL_ID
    )


def resolve_base_url(
    *,
    cli_base_url: str | None,
    registry_base_url: str | None,
) -> tuple[str, str]:
    cli_value = clean_string(cli_base_url)
    if cli_value:
        return cli_value, "cli:--base-url"
    env_value = clean_string(os.getenv("BIBER_LOCAL_OPENAI_BASE_URL"))
    if env_value:
        return env_value, "env:BIBER_LOCAL_OPENAI_BASE_URL"
    registry_value = clean_string(registry_base_url)
    if registry_value:
        return registry_value, "model-registry"
    return DEFAULT_BASE_URL, "default"


def resolve_provider_selection(
    *,
    request: Mapping[str, Any],
    chat_payload: Mapping[str, Any],
    cli_model: str | None,
    cli_base_url: str | None,
) -> dict[str, Any]:
    logical_model = requested_logical_model(request, chat_payload)
    explicit_model = clean_string(cli_model)
    if explicit_model:
        base_url, base_url_source = resolve_base_url(
            cli_base_url=cli_base_url,
            registry_base_url=None,
        )
        return {
            "logical_model": logical_model,
            "provider_model": explicit_model,
            "provider_id": None,
            "provider_type": "openai-compatible-chat",
            "lifecycle": None,
            "selection_source": "cli:--model",
            "base_url": base_url,
            "base_url_source": base_url_source,
        }

    env_openai_model = clean_string(os.getenv("BIBER_LOCAL_OPENAI_MODEL"))
    if env_openai_model:
        base_url, base_url_source = resolve_base_url(
            cli_base_url=cli_base_url,
            registry_base_url=None,
        )
        return {
            "logical_model": logical_model,
            "provider_model": env_openai_model,
            "provider_id": None,
            "provider_type": "openai-compatible-chat",
            "lifecycle": None,
            "selection_source": "env:BIBER_LOCAL_OPENAI_MODEL",
            "base_url": base_url,
            "base_url_source": base_url_source,
        }

    registry_entry = find_registry_entry(logical_model)
    if registry_entry:
        if registry_entry.get("enabled") is not True:
            raise LocalProviderError(
                f"Model is configured but disabled: {registry_entry.get('id')}"
            )
        base_url, base_url_source = resolve_base_url(
            cli_base_url=cli_base_url,
            registry_base_url=clean_string(registry_entry.get("base_url")),
        )
        return {
            "logical_model": registry_entry["id"],
            "provider_model": registry_entry["provider_model"],
            "provider_id": registry_entry.get("provider_id"),
            "provider_type": registry_entry.get("provider_type"),
            "lifecycle": registry_entry.get("lifecycle"),
            "selection_source": registry_entry.get("source"),
            "base_url": base_url,
            "base_url_source": base_url_source,
        }

    fallback_model = os.getenv("BIBER_LOCAL_MODEL_NAME") or logical_model
    base_url, base_url_source = resolve_base_url(
        cli_base_url=cli_base_url,
        registry_base_url=None,
    )
    return {
        "logical_model": logical_model,
        "provider_model": fallback_model,
        "provider_id": None,
        "provider_type": "openai-compatible-chat",
        "lifecycle": None,
        "selection_source": (
            "env:BIBER_LOCAL_MODEL_NAME"
            if os.getenv("BIBER_LOCAL_MODEL_NAME")
            else "request:model"
        ),
        "base_url": base_url,
        "base_url_source": base_url_source,
    }


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
    selection = resolve_provider_selection(
        request=request,
        chat_payload=chat_payload,
        cli_model=cli_model,
        cli_base_url=None,
    )
    model = selection.get("provider_model")
    if not isinstance(model, str) or not model.strip():
        raise LocalProviderError(
            "Model is required. Pass --model or set BIBER_LOCAL_OPENAI_MODEL."
        )
    return model.strip()


def build_chat_provider_request(
    request: Mapping[str, Any],
    *,
    model: str | None,
    base_url: str | None,
    max_tokens: int | None,
    temperature: float | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    chat_payload = require_request(request)
    selection = resolve_provider_selection(
        request=request,
        chat_payload=chat_payload,
        cli_model=model,
        cli_base_url=base_url,
    )
    resolved_model = selection["provider_model"]
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
    return provider_payload, selection


def build_chat_completions_payload(
    request: Mapping[str, Any],
    *,
    model: str | None,
    max_tokens: int | None,
    temperature: float | None,
) -> dict[str, Any]:
    provider_payload, _ = build_chat_provider_request(
        request,
        model=model,
        base_url=None,
        max_tokens=max_tokens,
        temperature=temperature,
    )
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
    provider_selection: Mapping[str, Any] | None = None,
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
    if provider_selection is not None:
        output["provider_selection"] = dict(provider_selection)
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
        help=(
            "OpenAI-compatible base URL. Overrides BIBER_LOCAL_OPENAI_BASE_URL, "
            "BIBER_MODEL_REGISTRY_JSON base_url, and the local default."
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
        provider_payload, provider_selection = build_chat_provider_request(
            request,
            model=args.model,
            base_url=args.base_url,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
        )
        base_url = str(provider_selection["base_url"])
        if args.dry_run:
            output = build_command_output(
                content=json.dumps(provider_payload, sort_keys=True),
                response=None,
                provider_payload=provider_payload,
                base_url=base_url,
                provider_selection=provider_selection,
            )
        else:
            response = request_chat_completion(
                base_url=base_url,
                api_key=os.getenv(args.api_key_env),
                payload=provider_payload,
                timeout_seconds=args.timeout_seconds,
            )
            output = build_command_output(
                content=extract_message_content(response),
                response=response,
                provider_payload=provider_payload,
                base_url=base_url,
                provider_selection=provider_selection,
            )
    except LocalProviderError as exc:
        print(f"biber_local_openai_provider: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
