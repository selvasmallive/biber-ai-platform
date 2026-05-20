from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.dataset_utils import DatasetIssue, validate_record


READY_QUALITIES = {"reviewed", "verified"}


def load_candidate_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object.")
            value["_source_file"] = str(path)
            value["_source_line"] = line_number
            rows.append(value)
    return rows


def is_repo_adaptation_candidate(row: dict[str, Any]) -> bool:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata.get("source") == "repo_adaptation_failure_review"


def issue_summary(issues: list[DatasetIssue]) -> list[dict[str, Any]]:
    return [
        {
            "line_number": issue.line_number,
            "level": issue.level,
            "message": issue.message,
        }
        for issue in issues
    ]


def summarize_candidate(row: dict[str, Any], validation_issues: list[DatasetIssue]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    quality = str(row.get("quality") or "missing")
    output_ready = bool(str(row.get("output") or "").strip())
    quality_ready = quality in READY_QUALITIES
    validation_errors = [
        issue for issue in validation_issues if issue.level == "error"
    ]
    return {
        "jsonl_path": row.get("_source_file"),
        "jsonl_index": row.get("_source_line"),
        "original_id": metadata.get("original_id"),
        "failure_key": metadata.get("failure_key"),
        "category": row.get("category"),
        "quality": quality,
        "output_ready": output_ready,
        "quality_ready": quality_ready,
        "validation_ok": not validation_errors,
        "validation_issues": issue_summary(validation_issues),
    }


def review_repo_adaptation_candidate_records(
    *,
    candidate_paths: list[Path],
    min_ready: int,
) -> dict[str, Any]:
    if min_ready < 1:
        raise ValueError("min_ready must be at least 1.")

    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for path in candidate_paths:
        for row in load_candidate_jsonl(path):
            if is_repo_adaptation_candidate(row):
                rows.append(row)
            else:
                rejected.append(
                    {
                        "jsonl_path": str(path),
                        "jsonl_index": row.get("_source_line"),
                        "reason": "unsupported_source",
                        "metadata": row.get("metadata"),
                    }
                )

    ready_records: list[dict[str, Any]] = []
    pending_review: list[dict[str, Any]] = []
    quality_counts: Counter[str] = Counter()
    empty_output_records = 0
    unreviewed_quality_records = 0
    validation_error_records = 0
    for row in rows:
        quality = str(row.get("quality") or "missing")
        quality_counts[quality] += 1
        validation_issues = validate_record(row, int(row.get("_source_line") or 0))
        summary = summarize_candidate(row, validation_issues)
        if not summary["output_ready"]:
            empty_output_records += 1
        if not summary["quality_ready"]:
            unreviewed_quality_records += 1
        if not summary["validation_ok"]:
            validation_error_records += 1
        if (
            summary["output_ready"]
            and summary["quality_ready"]
            and summary["validation_ok"]
        ):
            ready_records.append(summary)
        else:
            pending_review.append(summary)

    hard_blockers: list[str] = []
    if not rows:
        hard_blockers.append("no_repo_adaptation_candidate_records")
    if rejected:
        hard_blockers.append("unsupported_candidate_records_present")
    if empty_output_records:
        hard_blockers.append("candidate_outputs_missing")
    if unreviewed_quality_records:
        hard_blockers.append("candidate_quality_not_reviewed")
    if validation_error_records:
        hard_blockers.append("candidate_validation_errors")
    if len(ready_records) < min_ready:
        hard_blockers.append("below_min_ready_records")

    ready_for_dataset_validation = not hard_blockers
    return {
        "command": "biber-repo-adaptation-candidate-review",
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate_files": [str(path) for path in candidate_paths],
        "records": len(rows),
        "rejected_records": len(rejected),
        "pending_review_records": len(pending_review),
        "ready_records": len(ready_records),
        "empty_output_records": empty_output_records,
        "unreviewed_quality_records": unreviewed_quality_records,
        "validation_error_records": validation_error_records,
        "quality_counts": dict(quality_counts),
        "min_ready": min_ready,
        "ready_for_dataset_validation": ready_for_dataset_validation,
        "training_dataset_ready": False,
        "training_allowed": False,
        "safe_to_train": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "hard_blockers": hard_blockers,
        "ready": ready_records,
        "pending_review": pending_review,
        "rejected": rejected,
        "next_review_action": (
            "validate_reviewed_repo_adaptation_dataset_before_training"
            if ready_for_dataset_validation
            else "fill_candidate_outputs_and_mark_quality_reviewed_or_verified"
        ),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Review repo-adaptation candidate JSONL before dataset validation."
    )
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--min-ready", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    review = review_repo_adaptation_candidate_records(
        candidate_paths=args.candidates,
        min_ready=args.min_ready,
    )
    args.review_output.parent.mkdir(parents=True, exist_ok=True)
    args.review_output.write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Repo adaptation candidate review complete: "
        f"{review['ready_records']}/{review['records']} ready, "
        f"{review['pending_review_records']} pending."
    )
    print(f"Review: {args.review_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
