from __future__ import annotations

import json
from pathlib import Path

from training.live_model_eval import EvalPrompt, EvalResult
from training.repo_adaptation_eval import (
    build_failure_rows,
    main,
    resolve_api_key,
    run_repo_adaptation_eval,
)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def test_resolve_api_key_reads_env_file_without_exposing_secret(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('BIBER_DEMO_API_KEY="demo-key"\n', encoding="utf-8")

    assert resolve_api_key(api_key=None, env_file=env_file) == "demo-key"


def test_build_failure_rows_keeps_prompt_context_for_failed_expectations() -> None:
    prompts = [
        EvalPrompt(
            id="repo-python-implementation",
            prompt="Explain implementation step.",
            language="Python",
            task_type="repo_adaptation_eval",
            expect_contains=("implementation",),
        )
    ]
    results = [
        EvalResult(
            id="repo-python-implementation",
            ok=True,
            expectation_ok=False,
            validation_ok=None,
            validation_skipped=False,
            model="biber-dev-core-v1",
            latency_seconds=0.1,
            content="Use tests first.",
            matched_expectations=(),
            missing_expectations=("implementation",),
        )
    ]

    rows = build_failure_rows(prompts, results)

    assert rows == [
        {
            "id": "repo-python-implementation",
            "prompt": "Explain implementation step.",
            "language": "Python",
            "task_type": "repo_adaptation_eval",
            "model": "biber-dev-core-v1",
            "ok": True,
            "expectation_ok": False,
            "matched_expectations": [],
            "missing_expectations": ["implementation"],
            "error": None,
            "content": "Use tests first.",
        }
    ]


def test_run_repo_adaptation_eval_writes_results_summary_and_failures(
    tmp_path: Path,
) -> None:
    prompts_path = tmp_path / "prompts.jsonl"
    output_path = tmp_path / "results.jsonl"
    summary_path = tmp_path / "summary.json"
    failures_path = tmp_path / "failures.jsonl"
    write_jsonl(
        prompts_path,
        [
            {
                "id": "repo-python-implementation",
                "prompt": "Explain implementation step.",
                "language": "Python",
                "task_type": "repo_adaptation_eval",
                "expect_contains": ["implementation"],
            },
            {
                "id": "repo-java-test",
                "prompt": "Explain test step.",
                "language": "Java",
                "task_type": "repo_adaptation_eval",
                "expect_contains": ["test"],
            },
        ],
    )

    def fake_chat_runner(
        base_url: str,
        api_key: str,
        prompt: EvalPrompt,
        timeout_seconds: float,
        run_validators: bool,
        validator_work_dir: Path | None,
        validator_timeout_seconds: float,
    ) -> EvalResult:
        content = "implementation plan" if "implementation" in prompt.id else "no match"
        matched = ("implementation",) if "implementation" in content else ()
        missing = tuple(item for item in prompt.expect_contains if item not in matched)
        return EvalResult(
            id=prompt.id,
            ok=True,
            expectation_ok=not missing,
            validation_ok=None,
            validation_skipped=False,
            model="biber-dev-core-v1",
            latency_seconds=0.01,
            content=content,
            matched_expectations=matched,
            missing_expectations=missing,
        )

    summary = run_repo_adaptation_eval(
        prompts_path=prompts_path,
        output_path=output_path,
        summary_path=summary_path,
        failures_path=failures_path,
        base_url="http://127.0.0.1:8000",
        api_key="test-key",
        timeout_seconds=1.0,
        limit=None,
        chat_runner=fake_chat_runner,
    )

    assert summary["command"] == "biber-repo-adaptation-eval"
    assert summary["prompts"] == 2
    assert summary["expectation_ok"] == 1
    assert summary["failures"] == 1
    assert output_path.exists()
    assert summary_path.exists()
    failure_rows = [json.loads(line) for line in failures_path.read_text().splitlines()]
    assert failure_rows[0]["id"] == "repo-java-test"


def test_main_returns_failure_when_response_missing(tmp_path: Path) -> None:
    prompts_path = tmp_path / "prompts.jsonl"
    output_path = tmp_path / "results.jsonl"
    summary_path = tmp_path / "summary.json"
    write_jsonl(
        prompts_path,
        [
            {
                "id": "repo-python-implementation",
                "prompt": "Explain implementation step.",
                "language": "Python",
                "task_type": "repo_adaptation_eval",
                "expect_contains": ["implementation"],
            }
        ],
    )

    exit_code = main(
        [
            "--prompts",
            str(prompts_path),
            "--base-url",
            "http://127.0.0.1:1",
            "--api-key",
            "test-key",
            "--output",
            str(output_path),
            "--summary",
            str(summary_path),
            "--timeout-seconds",
            "0.01",
        ]
    )

    assert exit_code == 1
    assert json.loads(summary_path.read_text(encoding="utf-8"))["failed"] == 1
