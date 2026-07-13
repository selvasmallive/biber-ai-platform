#!/usr/bin/env python3
"""Check live OpenAI-compatible provider readiness without sending chat requests."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8001/v1"
DEFAULT_TIMEOUT_SECONDS = 10.0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_models_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    if clean.endswith("/models"):
        return clean
    if clean.endswith("/v1"):
        return f"{clean}/models"
    return f"{clean}/v1/models"


def is_local_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def request_models(
    *,
    base_url: str,
    api_key: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(
        normalize_models_url(base_url),
        headers=headers,
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("/v1/models response must be a JSON object.")
    return parsed


def extract_model_ids(payload: dict[str, Any]) -> list[str]:
    data = payload.get("data")
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            ids.append(item["id"])
    return sorted(dict.fromkeys(ids))


def readiness_summary(
    *,
    base_url: str,
    model: str | None,
    api_key_env: str,
    timeout_seconds: float,
    require_model: bool,
) -> dict[str, Any]:
    api_key = os.getenv(api_key_env)
    models_url = normalize_models_url(base_url)
    model_ids: list[str] = []
    error: str | None = None
    endpoint_reachable = False
    models_endpoint_ok = False
    try:
        models_payload = request_models(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        endpoint_reachable = True
        models_endpoint_ok = True
        model_ids = extract_model_ids(models_payload)
    except urllib.error.HTTPError as exc:
        endpoint_reachable = True
        body = exc.read().decode("utf-8", errors="replace")[:1000]
        error = f"HTTP {exc.code}: {body}"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        error = str(exc)

    requested_model = model or os.getenv("BIBER_LOCAL_OPENAI_MODEL") or os.getenv(
        "BIBER_LOCAL_MODEL_NAME"
    )
    model_available = (
        requested_model in model_ids if isinstance(requested_model, str) and requested_model else None
    )
    ok = endpoint_reachable and models_endpoint_ok
    if require_model:
        ok = ok and model_available is True
    return {
        "source": "biber_live_provider_readiness",
        "ok": ok,
        "base_url": base_url,
        "models_url": models_url,
        "endpoint_reachable": endpoint_reachable,
        "models_endpoint_ok": models_endpoint_ok,
        "requested_model": requested_model,
        "require_model": require_model,
        "model_available": model_available,
        "available_model_count": len(model_ids),
        "available_models_preview": model_ids[:20],
        "auth_env_name": api_key_env,
        "auth_configured": bool(api_key),
        "external_network_required": not is_local_url(models_url),
        "live_provider_required": True,
        "repair_request_sent": False,
        "chat_completion_sent": False,
        "mentor_used": False,
        "training_allowed": False,
        "api_required": False,
        "error": error,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check a live OpenAI-compatible provider via GET /v1/models only. "
            "No repair request, chat completion, OpenAI mentor, or training is used."
        )
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("BIBER_LOCAL_OPENAI_BASE_URL", DEFAULT_BASE_URL),
    )
    parser.add_argument("--model", help="Expected local provider model or adapter alias.")
    parser.add_argument(
        "--api-key-env",
        default="BIBER_LOCAL_OPENAI_API_KEY",
        help="Environment variable containing an optional bearer token.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--require-model",
        action="store_true",
        help="Require the requested model to appear in /v1/models.",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Exit nonzero when readiness is not ok.",
    )
    parser.add_argument("--output", help="Optional path for the readiness JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = readiness_summary(
        base_url=args.base_url,
        model=args.model,
        api_key_env=args.api_key_env,
        timeout_seconds=args.timeout_seconds,
        require_model=args.require_model,
    )
    if args.output:
        write_json(Path(args.output), summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.require_ready and not summary["ok"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
