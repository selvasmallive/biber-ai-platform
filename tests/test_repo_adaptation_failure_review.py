from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_failure_review import (
    build_review,
    main,
    run_failure_review,
)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def failure_row(
    *,
    prompt_id: str = "repo-rust-implementation",
    prompt: str = "Explain the safest implementation step.",
    language: str = "Rust",
    content: str = "Use tests first.",
) -> dict[str, object]:
    return {
        "id": prompt_id,
        "prompt": prompt,
        "language": language,
        "task_type": "repo_adaptation_eval",
        "model": "biber-dev-core-v1",
        "ok": True,
        "expectation_ok": False,
        "matched_expectations": [],
        "missing_expectations": ["implementation"],
        "error": None,
        "content": content,
    }


def test_build_review_groups_repeated_failures_as_review_candidates() -> None:
    review = build_review(
        [failure_row(), failure_row(content="Prefer cargo test first.")],
        min_repeats=2,
    )

    assert review["failures_seen"] == 2
    assert review["groups"] == 1
    assert review["training_candidates"] == 1
    item = review["items"][0]
    assert item["repeat_count"] == 2
    assert item["eligible_for_training_candidate"] is True
    assert item["recommended_action"] == "write_reviewed_answer_then_promote_to_training_dataset"


def test_run_failure_review_writes_needs_review_candidates_with_empty_output(
    tmp_path: Path,
) -> None:
    failures_path = tmp_path / "failures.jsonl"
    review_path = tmp_path / "review.json"
    candidates_path = tmp_path / "candidates.jsonl"
    write_jsonl(
        failures_path,
        [failure_row(), failure_row(content="Mention implementation and tests.")],
    )

    review = run_failure_review(
        failure_paths=[failures_path],
        review_output=review_path,
        training_candidates_output=candidates_path,
        min_repeats=2,
    )

    assert review["training_candidates"] == 1
    assert json.loads(review_path.read_text(encoding="utf-8"))["groups"] == 1
    candidates = [json.loads(line) for line in candidates_path.read_text().splitlines()]
    assert len(candidates) == 1
    assert candidates[0]["instruction"] == "Explain the safest implementation step."
    assert candidates[0]["output"] == ""
    assert candidates[0]["quality"] == "needs_review"
    assert candidates[0]["category"] == "rust"
    assert candidates[0]["metadata"]["review_required"] is True


def test_run_failure_review_does_not_emit_candidates_below_threshold(
    tmp_path: Path,
) -> None:
    failures_path = tmp_path / "failures.jsonl"
    review_path = tmp_path / "review.json"
    candidates_path = tmp_path / "candidates.jsonl"
    write_jsonl(failures_path, [failure_row()])

    run_failure_review(
        failure_paths=[failures_path],
        review_output=review_path,
        training_candidates_output=candidates_path,
        min_repeats=2,
    )

    candidates = [line for line in candidates_path.read_text().splitlines() if line.strip()]
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert candidates == []
    assert review["items"][0]["blocked_reasons"] == ["below_min_repeats"]


def test_main_writes_review_file(tmp_path: Path) -> None:
    failures_path = tmp_path / "failures.jsonl"
    review_path = tmp_path / "review.json"
    write_jsonl(failures_path, [failure_row()])

    exit_code = main(
        [
            "--failures",
            str(failures_path),
            "--review-output",
            str(review_path),
            "--min-repeats",
            "1",
        ]
    )

    assert exit_code == 0
    assert json.loads(review_path.read_text(encoding="utf-8"))["training_candidates"] == 1
