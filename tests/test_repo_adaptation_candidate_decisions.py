from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_candidate_decisions import (
    apply_repo_adaptation_candidate_decisions,
    main,
)
from training.repo_adaptation_candidate_review import (
    review_repo_adaptation_candidate_records,
)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def candidate_record(
    *,
    failure_key: str = "failure-a",
    original_id: str = "repo-rust-implementation",
) -> dict[str, object]:
    return {
        "instruction": "Explain the safest implementation step.",
        "input": "Repo adaptation failure requiring human review.",
        "output": "",
        "category": "rust",
        "stack": ["rust", "repo_adaptation", "repo_adaptation_eval"],
        "quality": "needs_review",
        "metadata": {
            "source": "repo_adaptation_failure_review",
            "failure_key": failure_key,
            "original_id": original_id,
            "review_required": True,
        },
    }


def write_decisions(path: Path, decisions: list[dict[str, object]]) -> None:
    path.write_text(
        json.dumps({"reviewer": "test-reviewer", "decisions": decisions}, indent=2),
        encoding="utf-8",
    )


def test_apply_candidate_decisions_writes_reviewed_output_and_passes_review(
    tmp_path: Path,
) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.json"
    reviewed_path = tmp_path / "reviewed.jsonl"
    review_path = tmp_path / "decision-review.json"
    write_jsonl(candidates_path, [candidate_record()])
    write_decisions(
        decisions_path,
        [
            {
                "failure_key": "failure-a",
                "decision": "approve",
                "quality": "reviewed",
                "output": "Use a small code change and add a focused regression test.",
                "notes": "Safe generic repo-adaptation response.",
            }
        ],
    )

    decision_review = apply_repo_adaptation_candidate_decisions(
        candidate_paths=[candidates_path],
        decision_path=decisions_path,
        output_path=reviewed_path,
        review_output=review_path,
    )
    candidate_review = review_repo_adaptation_candidate_records(
        candidate_paths=[reviewed_path],
        min_ready=1,
    )
    rows = [
        json.loads(line)
        for line in reviewed_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert decision_review["approved_records"] == 1
    assert decision_review["hard_blockers"] == []
    assert decision_review["training_allowed"] is False
    assert decision_review["safe_to_train"] is False
    assert rows[0]["quality"] == "reviewed"
    assert rows[0]["output"] == (
        "Use a small code change and add a focused regression test."
    )
    assert rows[0]["metadata"]["review_required"] is False
    assert rows[0]["metadata"]["candidate_review"]["reviewer"] == "test-reviewer"
    assert rows[0]["metadata"]["candidate_review"]["decision"] == "approve"
    assert candidate_review["ready_records"] == 1
    assert candidate_review["ready_for_dataset_validation"] is True
    assert candidate_review["training_allowed"] is False
    assert candidate_review["safe_to_train"] is False


def test_apply_candidate_decisions_blocks_missing_outputs(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.json"
    reviewed_path = tmp_path / "reviewed.jsonl"
    review_path = tmp_path / "decision-review.json"
    write_jsonl(candidates_path, [candidate_record()])
    write_decisions(
        decisions_path,
        [{"failure_key": "failure-a", "decision": "approve", "output": ""}],
    )

    review = apply_repo_adaptation_candidate_decisions(
        candidate_paths=[candidates_path],
        decision_path=decisions_path,
        output_path=reviewed_path,
        review_output=review_path,
    )

    assert review["approved_records"] == 0
    assert review["decision_errors"] == 1
    assert review["hard_blockers"] == ["candidate_decision_errors"]
    assert reviewed_path.read_text(encoding="utf-8") == ""


def test_apply_candidate_decisions_tracks_missing_decisions(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.json"
    reviewed_path = tmp_path / "reviewed.jsonl"
    review_path = tmp_path / "decision-review.json"
    write_jsonl(
        candidates_path,
        [
            candidate_record(failure_key="failure-a", original_id="repo-a"),
            candidate_record(failure_key="failure-b", original_id="repo-b"),
        ],
    )
    write_decisions(
        decisions_path,
        [
            {
                "failure_key": "failure-a",
                "decision": "defer",
                "notes": "Needs more review.",
            }
        ],
    )

    review = apply_repo_adaptation_candidate_decisions(
        candidate_paths=[candidates_path],
        decision_path=decisions_path,
        output_path=reviewed_path,
        review_output=review_path,
    )

    assert review["approved_records"] == 0
    assert review["decision_counts"]["defer"] == 1
    assert review["missing_decisions"] == 1
    assert review["hard_blockers"] == ["candidate_decisions_missing"]


def test_main_returns_nonzero_for_invalid_decisions(tmp_path: Path) -> None:
    candidates_path = tmp_path / "candidates.jsonl"
    decisions_path = tmp_path / "decisions.json"
    reviewed_path = tmp_path / "reviewed.jsonl"
    review_path = tmp_path / "decision-review.json"
    write_jsonl(candidates_path, [candidate_record()])
    write_decisions(
        decisions_path,
        [{"failure_key": "failure-a", "decision": "approve", "output": ""}],
    )

    exit_code = main(
        [
            "--candidates",
            str(candidates_path),
            "--decisions",
            str(decisions_path),
            "--output",
            str(reviewed_path),
            "--review-output",
            str(review_path),
        ]
    )

    assert exit_code == 1
    assert json.loads(review_path.read_text(encoding="utf-8"))["decision_errors"] == 1
