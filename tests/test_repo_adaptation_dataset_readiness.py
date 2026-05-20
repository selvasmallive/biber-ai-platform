from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_dataset_readiness import (
    main,
    review_repo_adaptation_dataset_readiness,
)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def reviewed_record(
    *,
    failure_key: str,
    category: str,
    quality: str = "reviewed",
    output: str = "Use repo conventions and add a focused regression test.",
    source: str = "repo_adaptation_failure_review",
) -> dict[str, object]:
    return {
        "instruction": "Explain the safest implementation step.",
        "input": "Repo adaptation failure requiring human review.",
        "output": output,
        "category": category,
        "stack": [category, "repo_adaptation", "repo_adaptation_eval"],
        "quality": quality,
        "metadata": {
            "source": source,
            "failure_key": failure_key,
            "original_id": f"repo-{failure_key}",
            "review_required": False,
        },
    }


def test_readiness_blocks_small_curated_queue(tmp_path: Path) -> None:
    dataset = tmp_path / "curated.jsonl"
    write_jsonl(
        dataset,
        [
            reviewed_record(failure_key="bash-a", category="bash"),
            reviewed_record(failure_key="markdown-a", category="markdown"),
            reviewed_record(failure_key="python-a", category="python"),
            reviewed_record(failure_key="sql-a", category="sql"),
        ],
    )

    review = review_repo_adaptation_dataset_readiness(
        dataset_path=dataset,
        min_records=50,
        min_categories=4,
        required_categories=["bash", "markdown", "python", "sql"],
    )

    assert review["review_status"] == "training_blocked"
    assert review["ready_records"] == 4
    assert review["record_gap"] == 46
    assert review["category_gap"] == 0
    assert review["missing_required_categories"] == []
    assert review["hard_blockers"] == ["below_min_ready_records"]
    assert review["training_allowed"] is False
    assert review["safe_to_train"] is False


def test_readiness_marks_manual_review_required_when_thresholds_met(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "curated.jsonl"
    write_jsonl(
        dataset,
        [
            reviewed_record(failure_key="bash-a", category="bash"),
            reviewed_record(failure_key="markdown-a", category="markdown"),
            reviewed_record(failure_key="python-a", category="python"),
            reviewed_record(failure_key="sql-a", category="sql"),
        ],
    )

    review = review_repo_adaptation_dataset_readiness(
        dataset_path=dataset,
        min_records=4,
        min_categories=4,
        required_categories=["bash", "markdown", "python", "sql"],
    )

    assert review["review_status"] == "manual_training_review_required"
    assert review["training_gate_status"] == "manual_review_required"
    assert review["ready_for_manual_training_review"] is True
    assert review["hard_blockers"] == []
    assert review["training_dataset_ready"] is False
    assert review["approved_for_training"] is False


def test_readiness_blocks_invalid_duplicate_and_unsupported_records(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "curated.jsonl"
    write_jsonl(
        dataset,
        [
            reviewed_record(failure_key="dup", category="bash"),
            reviewed_record(failure_key="dup", category="bash"),
            reviewed_record(
                failure_key="unsupported",
                category="python",
                source="unsupported",
            ),
            reviewed_record(
                failure_key="needs-review",
                category="sql",
                quality="needs_review",
                output="",
            ),
        ],
    )

    review = review_repo_adaptation_dataset_readiness(
        dataset_path=dataset,
        min_records=4,
        min_categories=4,
        required_categories=["bash", "markdown", "python", "sql"],
    )

    assert review["review_status"] == "training_blocked"
    assert "unsupported_source_records" in review["hard_blockers"]
    assert "records_not_ready_for_training_review" in review["hard_blockers"]
    assert "duplicate_records_present" in review["hard_blockers"]
    assert "below_min_category_diversity" in review["hard_blockers"]
    assert "missing_required_categories" in review["hard_blockers"]
    assert review["duplicate_records"] == 1
    assert review["unsupported_source_records"] == 1
    assert review["not_ready_records"] == 1
    assert review["training_allowed"] is False


def test_main_writes_readiness_review_even_when_blocked(tmp_path: Path) -> None:
    dataset = tmp_path / "curated.jsonl"
    review_path = tmp_path / "readiness.json"
    write_jsonl(
        dataset,
        [reviewed_record(failure_key="bash-a", category="bash")],
    )

    exit_code = main(
        [
            "--dataset",
            str(dataset),
            "--review-output",
            str(review_path),
            "--min-records",
            "2",
            "--min-categories",
            "2",
            "--required-category",
            "bash",
            "--required-category",
            "python",
        ]
    )
    saved = json.loads(review_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert saved["review_status"] == "training_blocked"
    assert saved["record_gap"] == 1
    assert saved["missing_required_categories"] == ["python"]
