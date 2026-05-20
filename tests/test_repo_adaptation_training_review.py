from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_training_review import (
    main,
    review_repo_adaptation_training_dataset,
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
    original_id: str,
    quality: str = "reviewed",
    output: str = "Use repo conventions and run the focused verification command.",
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
            "original_id": original_id,
            "review_required": False,
        },
    }


def test_training_review_marks_ready_for_user_approval_without_enabling_training(
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "reviewed.jsonl"
    review_output = tmp_path / "training-review.json"
    write_jsonl(
        dataset,
        [
            reviewed_record(
                failure_key="bash-a",
                category="bash",
                original_id="repo-bash-implementation-step-aaaa",
            ),
            reviewed_record(
                failure_key="markdown-a",
                category="markdown",
                original_id="repo-markdown-context-selection-bbbb",
            ),
            reviewed_record(
                failure_key="python-a",
                category="python",
                original_id="repo-python-regression-test-cccc",
            ),
            reviewed_record(
                failure_key="sql-a",
                category="sql",
                original_id="repo-sql-risk-and-verification-dddd",
            ),
        ],
    )

    review = review_repo_adaptation_training_dataset(
        dataset_path=dataset,
        review_output=review_output,
        min_records=4,
        min_categories=4,
        required_categories=["bash", "markdown", "python", "sql"],
        output_dir="/workspace/adapters/biber-test",
        session_name="biber-test",
    )

    assert review["review_status"] == "ready_for_user_training_approval"
    assert review["ready_for_user_training_approval"] is True
    assert review["requires_explicit_user_training_approval"] is True
    assert review["hard_blockers"] == []
    assert review["prompt_variants"]["implementation_step"] == 1
    assert review["prompt_variants"]["context_selection"] == 1
    assert review["prompt_variants"]["regression_test"] == 1
    assert review["prompt_variants"]["risk_and_verification"] == 1
    assert "scripts/vast_train_qlora_tmux.sh" in review["recommended_training"]["command"]
    assert review["training_dataset_ready"] is False
    assert review["training_allowed"] is False
    assert review["safe_to_train"] is False
    assert review["approved_for_training"] is False
    assert review_output.exists()


def test_training_review_blocks_duplicates_and_unready_rows(tmp_path: Path) -> None:
    dataset = tmp_path / "reviewed.jsonl"
    review_output = tmp_path / "training-review.json"
    write_jsonl(
        dataset,
        [
            reviewed_record(
                failure_key="dup",
                category="bash",
                original_id="repo-bash-implementation-step-aaaa",
            ),
            reviewed_record(
                failure_key="dup",
                category="bash",
                original_id="repo-bash-implementation-step-aaaa",
            ),
            reviewed_record(
                failure_key="needs-review",
                category="python",
                original_id="repo-python-regression-test-bbbb",
                quality="needs_review",
                output="",
            ),
        ],
    )

    review = review_repo_adaptation_training_dataset(
        dataset_path=dataset,
        review_output=review_output,
        min_records=4,
        min_categories=4,
        required_categories=["bash", "markdown", "python", "sql"],
        output_dir="/workspace/adapters/biber-test",
        session_name="biber-test",
    )

    assert review["review_status"] == "manual_training_review_blocked"
    assert review["ready_for_user_training_approval"] is False
    assert "duplicate_records_present" in review["hard_blockers"]
    assert "records_not_ready" in review["hard_blockers"]
    assert "below_min_ready_records" in review["hard_blockers"]
    assert review["training_allowed"] is False


def test_main_writes_manual_training_review(tmp_path: Path) -> None:
    dataset = tmp_path / "reviewed.jsonl"
    review_output = tmp_path / "training-review.json"
    write_jsonl(
        dataset,
        [
            reviewed_record(
                failure_key="bash-a",
                category="bash",
                original_id="repo-bash-implementation-step-aaaa",
            )
        ],
    )

    exit_code = main(
        [
            "--dataset",
            str(dataset),
            "--review-output",
            str(review_output),
            "--min-records",
            "1",
            "--min-categories",
            "1",
            "--required-category",
            "bash",
            "--output-dir",
            "/workspace/adapters/biber-test",
            "--session-name",
            "biber-test",
        ]
    )
    saved = json.loads(review_output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert saved["review_status"] == "ready_for_user_training_approval"
    assert saved["recommended_training"]["session_name"] == "biber-test"
