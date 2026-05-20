from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_regression_review import main, run_regression_review


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def eval_prompt(
    *,
    prompt_id: str,
    prompt: str,
    language: str = "Python",
    task_type: str = "code_generation",
) -> dict[str, object]:
    return {
        "id": prompt_id,
        "prompt": prompt,
        "language": language,
        "task_type": task_type,
        "expect_contains": ["def"],
    }


def result_row(
    *,
    prompt_id: str,
    ok: bool = True,
    expectation_ok: bool = False,
    validation_ok: bool | None = None,
    missing_expectations: list[str] | None = None,
    validation_errors: list[str] | None = None,
    content: str = "I would explain the approach.",
) -> dict[str, object]:
    return {
        "id": prompt_id,
        "ok": ok,
        "expectation_ok": expectation_ok,
        "validation_ok": validation_ok,
        "validation_skipped": validation_ok is None,
        "model": "biber-dev-core",
        "latency_seconds": 0.1,
        "content": content,
        "matched_expectations": [],
        "missing_expectations": missing_expectations or ["def"],
        "validation_errors": validation_errors or [],
        "validation_details": [],
        "error": None,
    }


def test_regression_review_exports_human_review_only_candidates(tmp_path: Path) -> None:
    broad_prompts = tmp_path / "broad-prompts.jsonl"
    rust_prompts = tmp_path / "rust-prompts.jsonl"
    broad_results = tmp_path / "candidate-broad.jsonl"
    rust_results = tmp_path / "candidate-rust.jsonl"
    promotion_review = tmp_path / "promotion.json"
    review_output = tmp_path / "regression-review.json"
    candidates_output = tmp_path / "anti-regression-candidates.jsonl"

    write_jsonl(
        broad_prompts,
        [
            eval_prompt(
                prompt_id="python_add_function",
                prompt="Write a Python add function.",
                language="Python",
            )
        ],
    )
    write_jsonl(
        rust_prompts,
        [
            eval_prompt(
                prompt_id="rust_xriq_ledger",
                prompt="Write a Rust XRIQ ledger helper.",
                language="Rust",
                task_type="xriq_codegen",
            )
        ],
    )
    write_jsonl(broad_results, [result_row(prompt_id="python_add_function")])
    write_jsonl(
        rust_results,
        [
            result_row(
                prompt_id="rust_xriq_ledger",
                expectation_ok=True,
                validation_ok=False,
                missing_expectations=[],
                validation_errors=["rust:cargo_check failed"],
                content="pub fn apply() {}",
            )
        ],
    )
    promotion_review.write_text(
        json.dumps(
            {
                "candidate_adapter": "/workspace/adapters/candidate",
                "stable_adapter": "/workspace/adapters/stable",
                "hard_blockers": [
                    "broad_expectations_below_threshold",
                    "rust_validators_below_threshold",
                ],
            }
        ),
        encoding="utf-8",
    )

    review = run_regression_review(
        broad_results_path=broad_results,
        broad_prompts_path=broad_prompts,
        rust_results_path=rust_results,
        rust_prompts_path=rust_prompts,
        promotion_review_path=promotion_review,
        review_output=review_output,
        anti_regression_candidates_output=candidates_output,
        candidate_adapter=None,
        stable_adapter=None,
    )

    assert review["regression_rows"] == 2
    assert review["anti_regression_candidates"] == 2
    assert review["broad_regressions"] == 1
    assert review["rust_xriq_regressions"] == 1
    assert review["validator_regressions"] == 1
    assert review["training_allowed"] is False
    candidates = [
        json.loads(line)
        for line in candidates_output.read_text(encoding="utf-8").splitlines()
    ]
    assert candidates[0]["output"] == ""
    assert candidates[0]["quality"] == "needs_review"
    assert candidates[0]["metadata"]["source"] == "repo_adaptation_adapter_regression_review"
    assert candidates[0]["metadata"]["candidate_adapter"] == "/workspace/adapters/candidate"
    assert candidates[0]["training_allowed"] is False
    assert {candidate["instruction"] for candidate in candidates} == {
        "Write a Python add function.",
        "Write a Rust XRIQ ledger helper.",
    }


def test_regression_review_blocks_runtime_errors_from_candidate_export(
    tmp_path: Path,
) -> None:
    prompts = tmp_path / "prompts.jsonl"
    results = tmp_path / "results.jsonl"
    review_output = tmp_path / "review.json"
    candidates_output = tmp_path / "candidates.jsonl"
    write_jsonl(
        prompts,
        [eval_prompt(prompt_id="python_add_function", prompt="Write add.")],
    )
    write_jsonl(
        results,
        [
            result_row(
                prompt_id="python_add_function",
                ok=False,
                expectation_ok=False,
                content="",
            )
        ],
    )

    review = run_regression_review(
        broad_results_path=results,
        broad_prompts_path=prompts,
        rust_results_path=None,
        rust_prompts_path=None,
        promotion_review_path=None,
        review_output=review_output,
        anti_regression_candidates_output=candidates_output,
        candidate_adapter="/workspace/adapters/candidate",
        stable_adapter="/workspace/adapters/stable",
    )

    assert review["regression_rows"] == 1
    assert review["anti_regression_candidates"] == 0
    assert review["runtime_blocked_rows"] == 1
    assert candidates_output.read_text(encoding="utf-8") == ""


def test_main_writes_regression_review(tmp_path: Path) -> None:
    prompts = tmp_path / "prompts.jsonl"
    results = tmp_path / "results.jsonl"
    review_output = tmp_path / "review.json"
    write_jsonl(
        prompts,
        [eval_prompt(prompt_id="python_add_function", prompt="Write add.")],
    )
    write_jsonl(results, [result_row(prompt_id="python_add_function")])

    exit_code = main(
        [
            "--broad-results",
            str(results),
            "--broad-prompts",
            str(prompts),
            "--review-output",
            str(review_output),
        ]
    )

    assert exit_code == 0
    assert json.loads(review_output.read_text(encoding="utf-8"))["regression_rows"] == 1
