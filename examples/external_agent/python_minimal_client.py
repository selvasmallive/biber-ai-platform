#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping


DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_MODEL = "biber-dev-core-v1"
DEFAULT_MESSAGE = "Reply with one concise sentence confirming BIBER access."


def chat_completions_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/chat/completions"):
        return clean
    if clean.endswith("/v1"):
        return f"{clean}/chat/completions"
    return f"{clean}/v1/chat/completions"


def extract_content(payload: Mapping[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return ""
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            return content
    return ""


def post_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    message: str,
    max_tokens: int,
    temperature: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
        "use_mentor": False,
    }
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        chat_completions_url(base_url),
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"BIBER request failed with HTTP {exc.code}: {error_body}") from exc
    parsed = json.loads(response_body)
    if not isinstance(parsed, dict):
        raise RuntimeError("BIBER response was not a JSON object.")
    return parsed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal OpenAI-compatible BIBER chat-completions client."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIBER_OPENAI_BASE_URL", DEFAULT_BASE_URL),
        help="OpenAI-compatible BIBER base URL, usually ending in /v1.",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("BIBER_MODEL", DEFAULT_MODEL),
        help="BIBER model id from /v1/models.",
    )
    parser.add_argument(
        "--api-key-env",
        default="BIBER_API_KEY",
        help="Environment variable containing the BIBER user API key.",
    )
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--max-tokens", type=int, default=120)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--output", help="Optional JSON artifact path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    api_key = os.getenv(args.api_key_env, "").strip()
    if not api_key:
        print(f"Missing API key environment variable: {args.api_key_env}", file=sys.stderr)
        return 2
    response = post_chat_completion(
        base_url=args.base_url,
        api_key=api_key,
        model=args.model,
        message=args.message,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
    )
    if args.output:
        Path(args.output).write_text(
            json.dumps(response, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(extract_content(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
