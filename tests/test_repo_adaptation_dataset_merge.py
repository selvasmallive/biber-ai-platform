from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_dataset_merge import (
    main,
    merge_reviewed_repo_adaptation_candidates,
)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def reviewed_record(
    *,
    failure_key: str = "failure-a",
    quality: str = "reviewed",
    output: str = "Use the existing repo conventions and add a focused test.",
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
            "failure_key": failure_key,
            "original_id": f"repo-{failure_key}",
            "review_required": False,
        },
    }


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_merge_reviewed_candidates_writes_curated_queue(tmp_path: Path) -> None:
    candidates_path = tmp_path / "reviewed.jsonl"
    output_path = tmp_path / "curated.jsonl"
    review_path = tmp_path / "merge-review.json"
    write_jsonl(candidates_path, [reviewed_record()])

    review = merge_reviewed_repo_adaptation_candidates(
        candidate_paths=[candidates_path],
        output_path=output_path,
        review_output=review_path,
        min_total_records=1,
    )
    rows = read_jsonl(output_path)

    assert review["added_records"] == 1
    assert review["total_records"] == 1
    assert review["hard_blockers"] == []
    assert review["training_allowed"] is False
    assert review["safe_to_train"] is False
    assert rows[0]["metadata"]["repo_adaptation_dataset_queue"][
        "source_candidate_file"
    ] == str(candidates_path)
    assert rows[0]["metadata"]["promotion_rule"].startswith("Keep in the curated")


def test_merge_reviewed_candidates_is_idempotent(tmp_path: Path) -> None:
    candidates_path = tmp_path / "reviewed.jsonl"
    output_path = tmp_path / "curated.jsonl"
    first_review_path = tmp_path / "merge-review-1.json"
    second_review_path = tmp_path / "merge-review-2.json"
    write_jsonl(candidates_path, [reviewed_record()])

    first = merge_reviewed_repo_adaptation_candidates(
        candidate_paths=[candidates_path],
        output_path=output_path,
        review_output=first_review_path,
        min_total_records=1,
    )
    second = merge_reviewed_repo_adaptation_candidates(
        candidate_paths=[candidates_path],
        output_path=output_path,
        review_output=second_review_path,
        min_total_records=1,
    )
    rows = read_jsonl(output_path)

    assert first["added_records"] == 1
    assert second["added_records"] == 0
    assert second["duplicate_records"] == 1
    assert second["hard_blockers"] == []
    assert len(rows) == 1


def test_merge_blocks_unreviewed_candidates(tmp_path: Path) -> None:
    candidates_path = tmp_path / "reviewed.jsonl"
    output_path = tmp_path / "curated.jsonl"
    review_path = tmp_path / "merge-review.json"
    write_jsonl(
        candidates_path,
        [reviewed_record(quality="needs_review", output="")],
    )

    review = merge_reviewed_repo_adaptation_candidates(
        candidate_paths=[candidates_path],
        output_path=output_path,
        review_output=review_path,
        min_total_records=1,
    )

    assert review["added_records"] == 0
    assert review["rejected_records"] == 1
    assert review["hard_blockers"] == [
        "candidate_records_not_ready_for_merge",
        "below_min_total_records",
    ]
    assert not output_path.exists()


def test_main_returns_nonzero_when_merge_is_blocked(tmp_path: Path) -> None:
    candidates_path = tmp_path / "reviewed.jsonl"
    output_path = tmp_path / "curated.jsonl"
    review_path = tmp_path / "merge-review.json"
    write_jsonl(
        candidates_path,
        [reviewed_record(source="unsupported", output="Still not mergeable.")],
    )

    exit_code = main(
        [
            "--candidates",
            str(candidates_path),
            "--output",
            str(output_path),
            "--review-output",
            str(review_path),
            "--min-total-records",
            "1",
        ]
    )

    assert exit_code == 1
    assert json.loads(review_path.read_text(encoding="utf-8"))[
        "rejected_records"
    ] == 1
