from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_candidate_review import (
    main,
    review_repo_adaptation_candidate_records,
)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def candidate_record(
    *,
    output: str = "",
    quality: str = "needs_review",
    source: str = "repo_adaptation_failure_review",
) -> dict[str, object]:
    return {
        "instruction": "Explain the safest implementation step.",
        "input": "Repo adaptation failure requiring human review.",
        "output": output,
        "category": "rust",
        "stack": ["rust", "repo_adaptation", "repo_adaptation_eval"],
        "quality": quality,
        "metadata": {
            "source": source,
            "failure_key": "failure-a",
            "original_id": "repo-rust-implementation",
            "review_required": True,
        },
    }


def test_review_blocks_needs_review_candidates_with_empty_output(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    write_jsonl(candidates_path, [candidate_record()])

    review = review_repo_adaptation_candidate_records(
        candidate_paths=[candidates_path],
        min_ready=1,
    )

    assert review["command"] == "biber-repo-adaptation-candidate-review"
    assert review["records"] == 1
    assert review["ready_records"] == 0
    assert review["pending_review_records"] == 1
    assert review["empty_output_records"] == 1
    assert review["unreviewed_quality_records"] == 1
    assert review["validation_error_records"] == 1
    assert review["ready_for_dataset_validation"] is False
    assert review["training_dataset_ready"] is False
    assert review["training_allowed"] is False
    assert review["safe_to_train"] is False
    assert review["approved_for_training"] is False
    assert review["hard_blockers"] == [
        "candidate_outputs_missing",
        "candidate_quality_not_reviewed",
        "candidate_validation_errors",
        "below_min_ready_records",
    ]
    assert review["pending_review"][0]["output_ready"] is False
    assert review["pending_review"][0]["quality_ready"] is False
    assert review["pending_review"][0]["validation_ok"] is False


def test_review_marks_reviewed_output_ready_for_dataset_validation(
    tmp_path: Path,
) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    write_jsonl(
        candidates_path,
        [
            candidate_record(
                output="Use a small code change and add a focused regression test.",
                quality="verified",
            )
        ],
    )

    review = review_repo_adaptation_candidate_records(
        candidate_paths=[candidates_path],
        min_ready=1,
    )

    assert review["records"] == 1
    assert review["ready_records"] == 1
    assert review["pending_review_records"] == 0
    assert review["validation_error_records"] == 0
    assert review["ready_for_dataset_validation"] is True
    assert review["training_dataset_ready"] is False
    assert review["training_allowed"] is False
    assert review["safe_to_train"] is False
    assert review["approved_for_training"] is False
    assert review["hard_blockers"] == []
    assert review["ready"][0]["quality"] == "verified"
    assert review["ready"][0]["output_ready"] is True
    assert review["ready"][0]["quality_ready"] is True
    assert review["ready"][0]["validation_ok"] is True


def test_review_rejects_unsupported_candidate_sources(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    write_jsonl(candidates_path, [candidate_record(source="other_source")])

    review = review_repo_adaptation_candidate_records(
        candidate_paths=[candidates_path],
        min_ready=1,
    )

    assert review["records"] == 0
    assert review["rejected_records"] == 1
    assert "unsupported_candidate_records_present" in review["hard_blockers"]
    assert "no_repo_adaptation_candidate_records" in review["hard_blockers"]
    assert review["ready_for_dataset_validation"] is False


def test_main_writes_candidate_review(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    review_path = tmp_path / "review.json"
    write_jsonl(candidates_path, [candidate_record()])

    exit_code = main(
        [
            "--candidates",
            str(candidates_path),
            "--review-output",
            str(review_path),
        ]
    )

    assert exit_code == 0
    review = json.loads(review_path.read_text(encoding="utf-8"))
    assert review["records"] == 1
    assert review["ready_for_dataset_validation"] is False
