from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from training.live_model_eval import (
    EvalPrompt,
    EvalResult,
    load_eval_prompts,
    post_chat,
    read_env_file_value,
    write_jsonl,
    write_summary,
)


ChatRunner = Callable[[str, str, EvalPrompt, float, bool, Path | None, float], EvalResult]


def resolve_api_key(*, api_key: str | None, env_file: Path) -> str:
    if api_key:
        return api_key
    env_value = read_env_file_value(env_file, "BIBER_TEST_API_KEY")
    if env_value:
        return env_value
    env_value = read_env_file_value(env_file, "BIBER_DEMO_API_KEY")
    return env_value or "dev-api-key-change-me"


def build_failure_rows(
    prompts: list[EvalPrompt],
    results: list[EvalResult],
) -> list[dict[str, object]]:
    prompt_by_id = {prompt.id: prompt for prompt in prompts}
    rows: list[dict[str, object]] = []
    for result in results:
        if result.ok and result.expectation_ok:
            continue
        prompt = prompt_by_id.get(result.id)
        rows.append(
            {
                "id": result.id,
                "prompt": prompt.prompt if prompt else "",
                "language": prompt.language if prompt else None,
                "task_type": prompt.task_type if prompt else "repo_adaptation_eval",
                "model": result.model,
                "ok": result.ok,
                "expectation_ok": result.expectation_ok,
                "matched_expectations": list(result.matched_expectations),
                "missing_expectations": list(result.missing_expectations),
                "error": result.error,
                "content": result.content,
            }
        )
    return rows


def run_repo_adaptation_eval(
    *,
    prompts_path: Path,
    output_path: Path,
    summary_path: Path,
    failures_path: Path | None,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
    limit: int | None,
    chat_runner: ChatRunner = post_chat,
) -> dict[str, object]:
    prompts = load_eval_prompts(prompts_path)
    if limit is not None:
        prompts = prompts[:limit]

    started_at = datetime.now(UTC).isoformat()
    results = [
        chat_runner(
            base_url,
            api_key,
            prompt,
            timeout_seconds,
            False,
            None,
            0.0,
        )
        for prompt in prompts
    ]
    rows = [asdict(result) for result in results]
    write_jsonl(output_path, rows)

    failures = build_failure_rows(prompts, results)
    if failures_path is not None:
        write_jsonl(failures_path, failures)

    ok_count = sum(1 for result in results if result.ok)
    expectation_ok_count = sum(1 for result in results if result.expectation_ok)
    summary = {
        "command": "biber-repo-adaptation-eval",
        "started_at": started_at,
        "completed_at": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "prompts_path": str(prompts_path),
        "prompts": len(results),
        "ok": ok_count,
        "failed": len(results) - ok_count,
        "expectation_ok": expectation_ok_count,
        "expectation_failed": len(results) - expectation_ok_count,
        "failures": len(failures),
        "output": str(output_path),
        "summary": str(summary_path),
        "failures_output": str(failures_path) if failures_path is not None else None,
    }
    write_summary(summary_path, summary)
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run generated repo-adaptation eval prompts against BIBER."
    )
    parser.add_argument("--prompts", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--failures-output", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--fail-on-failed-expectations", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    api_key = resolve_api_key(api_key=args.api_key, env_file=args.env_file)
    summary = run_repo_adaptation_eval(
        prompts_path=args.prompts,
        output_path=args.output,
        summary_path=args.summary,
        failures_path=args.failures_output,
        base_url=args.base_url,
        api_key=api_key,
        timeout_seconds=args.timeout_seconds,
        limit=args.limit,
    )

    print(
        "Repo adaptation eval complete: "
        f"{summary['ok']}/{summary['prompts']} responses, "
        f"{summary['expectation_ok']}/{summary['prompts']} expectation checks passed."
    )
    print(f"Results: {summary['output']}")
    print(f"Summary: {summary['summary']}")
    if summary["failures_output"]:
        print(f"Failures: {summary['failures_output']}")

    if summary["failed"]:
        return 1
    if args.fail_on_failed_expectations and summary["expectation_failed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
