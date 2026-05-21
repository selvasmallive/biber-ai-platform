from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_training_outcome_review import (
    main,
    review_repo_adaptation_training_outcome,
)


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def candidate(original_id: str, *, category: str = "rust") -> dict[str, object]:
    return {
        "instruction": f"Fix {original_id}.",
        "input": "Candidate adapter regression requiring human review.",
        "output": "Verified answer.",
        "category": category,
        "stack": [category, "repo_adaptation", "anti_regression"],
        "quality": "verified",
        "metadata": {
            "source": "repo_adaptation_adapter_regression_review",
            "failure_key": f"key-{original_id}",
            "original_id": original_id,
            "review_required": False,
        },
    }


def result(
    prompt_id: str,
    *,
    expectation_ok: bool = True,
    validation_ok: bool | None = None,
    content: str = "ok",
) -> dict[str, object]:
    return {
        "id": prompt_id,
        "ok": True,
        "expectation_ok": expectation_ok,
        "validation_ok": validation_ok,
        "validation_skipped": validation_ok is None,
        "model": "biber-dev-core",
        "latency_seconds": 0.1,
        "content": content,
        "matched_expectations": [],
        "missing_expectations": [] if expectation_ok else ["status"],
        "validation_errors": [] if validation_ok is not False else ["rust:cargo_check failed"],
        "validation_details": [],
        "error": None,
    }


def promotion_review(*, blocked: bool = True) -> dict[str, object]:
    return {
        "review_status": "promotion_blocked" if blocked else "ready_for_user_promotion_approval",
        "hard_blockers": ["broad_expectations_below_threshold"] if blocked else [],
        "gates": [
            {
                "name": "broad_expectations",
                "ok": not blocked,
                "blocker": "broad_expectations_below_threshold" if blocked else None,
                "actual": 15 if blocked else 18,
                "required": {"expectation_ok": 18},
            }
        ],
        "promotion_allowed": False,
    }


def test_outcome_review_flags_persistent_trained_failures(tmp_path: Path) -> None:
    candidates_path = tmp_path / "reviewed.jsonl"
    broad_results = tmp_path / "broad.jsonl"
    rust_results = tmp_path / "rust.jsonl"
    promotion_path = tmp_path / "promotion.json"
    previous_path = tmp_path / "previous.json"

    write_jsonl(
        candidates_path,
        [candidate("api_error_shape", category="python"), candidate("rust_fee")],
    )
    write_jsonl(broad_results, [result("api_error_shape", expectation_ok=False)])
    write_jsonl(rust_results, [result("rust_fee", validation_ok=False)])
    write_json(promotion_path, promotion_review(blocked=True))
    write_json(
        previous_path,
        {
            "items": [
                {"id": "api_error_shape"},
                {"id": "rust_fee"},
            ]
        },
    )

    review = review_repo_adaptation_training_outcome(
        current_broad_results=broad_results,
        current_rust_results=rust_results,
        reviewed_candidates_path=candidates_path,
        promotion_review_path=promotion_path,
        previous_regression_review_path=previous_path,
    )

    assert review["review_status"] == "training_strategy_blocked"
    assert review["persistent_trained_failures"] == 2
    assert review["learned_reviewed_candidate_ids"] == []
    assert review["persisted_from_previous_regression_ids"] == [
        "api_error_shape",
        "rust_fee",
    ]
    assert review["training_allowed"] is False
    assert review["promotion_allowed"] is False
    assert (
        "prefer_prompt_profile_or_eval_contract_changes_before_more_qlora"
        in review["recommended_actions"]
    )


def test_outcome_review_tracks_learned_and_new_failures(tmp_path: Path) -> None:
    candidates_path = tmp_path / "reviewed.jsonl"
    broad_results = tmp_path / "broad.jsonl"
    rust_results = tmp_path / "rust.jsonl"
    promotion_path = tmp_path / "promotion.json"

    write_jsonl(candidates_path, [candidate("api_error_shape", category="python")])
    write_jsonl(
        broad_results,
        [
            result("api_error_shape", expectation_ok=True),
            result("api_rate_limit_error_shape", expectation_ok=False),
        ],
    )
    write_jsonl(rust_results, [])
    write_json(promotion_path, promotion_review(blocked=True))

    review = review_repo_adaptation_training_outcome(
        current_broad_results=broad_results,
        current_rust_results=rust_results,
        reviewed_candidates_path=candidates_path,
        promotion_review_path=promotion_path,
        previous_regression_review_path=None,
    )

    assert review["review_status"] == "candidate_promotion_blocked"
    assert review["persistent_trained_failures"] == 0
    assert review["learned_reviewed_candidate_ids"] == ["api_error_shape"]
    assert review["untrained_current_failures"] == 1
    assert review["next_review_action"] == "inspect_untrained_failures_before_more_training"


def test_main_writes_outcome_review(tmp_path: Path) -> None:
    candidates_path = tmp_path / "reviewed.jsonl"
    broad_results = tmp_path / "broad.jsonl"
    rust_results = tmp_path / "rust.jsonl"
    promotion_path = tmp_path / "promotion.json"
    review_output = tmp_path / "review.json"

    write_jsonl(candidates_path, [candidate("api_error_shape", category="python")])
    write_jsonl(broad_results, [result("api_error_shape", expectation_ok=False)])
    write_jsonl(rust_results, [])
    write_json(promotion_path, promotion_review(blocked=True))

    exit_code = main(
        [
            "--current-broad-results",
            str(broad_results),
            "--current-rust-results",
            str(rust_results),
            "--reviewed-candidates",
            str(candidates_path),
            "--promotion-review",
            str(promotion_path),
            "--review-output",
            str(review_output),
        ]
    )

    assert exit_code == 0
    assert json.loads(review_output.read_text(encoding="utf-8"))[
        "persistent_trained_failures"
    ] == 1
