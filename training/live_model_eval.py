from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EvalPrompt:
    id: str
    prompt: str
    language: str | None = None
    task_type: str = "code_generation"
    temperature: float = 0.0
    max_tokens: int = 256
    expect_contains: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalResult:
    id: str
    ok: bool
    expectation_ok: bool
    model: str | None
    latency_seconds: float
    content: str
    matched_expectations: tuple[str, ...]
    missing_expectations: tuple[str, ...]
    error: str | None = None


def read_env_file_value(env_file: Path, key: str) -> str | None:
    if not env_file.exists():
        return None

    prefix = f"{key}="
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return None


def load_eval_prompts(path: Path) -> list[EvalPrompt]:
    prompts: list[EvalPrompt] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc

            prompt_id = str(record.get("id", "")).strip()
            prompt = str(record.get("prompt", "")).strip()
            if not prompt_id:
                raise ValueError(f"{path}:{line_number}: missing id")
            if not prompt:
                raise ValueError(f"{path}:{line_number}: missing prompt")

            expectations = record.get("expect_contains", [])
            if not isinstance(expectations, list) or not all(
                isinstance(item, str) for item in expectations
            ):
                raise ValueError(f"{path}:{line_number}: expect_contains must be a string list")

            prompts.append(
                EvalPrompt(
                    id=prompt_id,
                    prompt=prompt,
                    language=record.get("language"),
                    task_type=str(record.get("task_type", "code_generation")),
                    temperature=float(record.get("temperature", 0.0)),
                    max_tokens=int(record.get("max_tokens", 256)),
                    expect_contains=tuple(expectations),
                )
            )

    if not prompts:
        raise ValueError(f"{path}: no evaluation prompts found")
    return prompts


def score_expectations(content: str, expectations: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    lowered = content.lower()
    matched = tuple(item for item in expectations if item.lower() in lowered)
    missing = tuple(item for item in expectations if item.lower() not in lowered)
    return matched, missing


def build_chat_payload(prompt: EvalPrompt) -> dict[str, Any]:
    return {
        "language": prompt.language,
        "task_type": prompt.task_type,
        "temperature": prompt.temperature,
        "max_tokens": prompt.max_tokens,
        "use_mentor": False,
        "messages": [{"role": "user", "content": prompt.prompt}],
    }


def post_chat(base_url: str, api_key: str, prompt: EvalPrompt, timeout_seconds: float) -> EvalResult:
    url = f"{base_url.rstrip('/')}/v1/chat"
    body = json.dumps(build_chat_payload(prompt)).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        latency = time.perf_counter() - started
        detail = exc.read().decode("utf-8", errors="replace")
        return EvalResult(
            id=prompt.id,
            ok=False,
            expectation_ok=False,
            model=None,
            latency_seconds=latency,
            content="",
            matched_expectations=(),
            missing_expectations=prompt.expect_contains,
            error=f"HTTP {exc.code}: {detail}",
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        latency = time.perf_counter() - started
        return EvalResult(
            id=prompt.id,
            ok=False,
            expectation_ok=False,
            model=None,
            latency_seconds=latency,
            content="",
            matched_expectations=(),
            missing_expectations=prompt.expect_contains,
            error=str(exc),
        )

    latency = time.perf_counter() - started
    content = str(payload.get("content", "")).strip()
    matched, missing = score_expectations(content, prompt.expect_contains)
    return EvalResult(
        id=prompt.id,
        ok=bool(content),
        expectation_ok=bool(content) and not missing,
        model=payload.get("model"),
        latency_seconds=latency,
        content=content,
        matched_expectations=matched,
        missing_expectations=missing,
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_api_key(args: argparse.Namespace) -> str:
    if args.api_key:
        return args.api_key
    if os.getenv("BIBER_TEST_API_KEY"):
        return os.environ["BIBER_TEST_API_KEY"]
    if os.getenv("BIBER_DEMO_API_KEY"):
        return os.environ["BIBER_DEMO_API_KEY"]
    env_file_value = read_env_file_value(args.env_file, "BIBER_DEMO_API_KEY")
    return env_file_value or "dev-api-key-change-me"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a small fixed eval against the live BIBER API.")
    parser.add_argument("--prompts", type=Path, default=Path("training/eval_prompts.jsonl"))
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--fail-on-failed-expectations", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    prompts = load_eval_prompts(args.prompts)
    if args.limit is not None:
        prompts = prompts[: args.limit]

    api_key = resolve_api_key(args)
    started_at = datetime.now(UTC).isoformat()
    results = [post_chat(args.base_url, api_key, prompt, args.timeout_seconds) for prompt in prompts]

    rows = [asdict(result) for result in results]
    write_jsonl(args.output, rows)

    ok_count = sum(1 for result in results if result.ok)
    expectation_ok_count = sum(1 for result in results if result.expectation_ok)
    summary = {
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "prompts": len(results),
        "ok": ok_count,
        "failed": len(results) - ok_count,
        "expectation_ok": expectation_ok_count,
        "expectation_failed": len(results) - expectation_ok_count,
        "output": str(args.output),
        "summary": str(args.summary),
    }
    write_summary(args.summary, summary)

    print(
        "Eval complete: "
        f"{ok_count}/{len(results)} responses, "
        f"{expectation_ok_count}/{len(results)} expectation checks passed."
    )
    print(f"Results: {args.output}")
    print(f"Summary: {args.summary}")

    if any(not result.ok for result in results):
        return 1
    if args.fail_on_failed_expectations and expectation_ok_count != len(results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
