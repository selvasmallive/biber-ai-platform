from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.dataset_utils import DatasetIssue, validate_record
from training.repo_adaptation_candidate_review import (
    READY_QUALITIES,
    is_repo_adaptation_candidate,
    load_candidate_jsonl,
)


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def issue_summary(issues: list[DatasetIssue]) -> list[dict[str, Any]]:
    return [
        {
            "line_number": issue.line_number,
            "level": issue.level,
            "message": issue.message,
        }
        for issue in issues
    ]


def reviewed_record_key(record: dict[str, Any]) -> str:
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        failure_key = str(metadata.get("failure_key") or "").strip()
        if failure_key:
            return f"failure_key:{failure_key}"
        original_id = str(metadata.get("original_id") or "").strip()
        if original_id:
            return f"original_id:{original_id}"
    identity = {
        "instruction": str(record.get("instruction") or "").strip(),
        "input": str(record.get("input") or "").strip(),
        "output": str(record.get("output") or "").strip(),
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def strip_source_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if not key.startswith("_source_")
    }


def is_ready_reviewed_candidate(record: dict[str, Any]) -> bool:
    output = str(record.get("output") or "").strip()
    quality = str(record.get("quality") or "").strip()
    return (
        is_repo_adaptation_candidate(record)
        and bool(output)
        and quality in READY_QUALITIES
    )


def with_merge_metadata(
    *,
    record: dict[str, Any],
    merged_at: str,
) -> dict[str, Any]:
    cleaned = strip_source_fields(record)
    metadata = cleaned.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)
    metadata["repo_adaptation_dataset_queue"] = {
        "merged_at": merged_at,
        "source_candidate_file": record.get("_source_file"),
        "source_candidate_line": record.get("_source_line"),
    }
    metadata["promotion_rule"] = (
        "Keep in the curated repo-adaptation queue until the dataset is large "
        "enough, validated, and explicitly approved for training."
    )
    cleaned["metadata"] = metadata
    return cleaned


def load_existing_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [strip_source_fields(row) for row in load_candidate_jsonl(path)]


def merge_reviewed_repo_adaptation_candidates(
    *,
    candidate_paths: list[Path],
    output_path: Path,
    review_output: Path,
    min_total_records: int,
) -> dict[str, Any]:
    if min_total_records < 1:
        raise ValueError("min_total_records must be at least 1.")

    merged_at = datetime.now(UTC).isoformat()
    existing_records = load_existing_records(output_path)
    merged_records = list(existing_records)
    existing_keys = {reviewed_record_key(record) for record in existing_records}

    rejected: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    added_records: list[dict[str, Any]] = []
    input_records = 0

    for path in candidate_paths:
        for row in load_candidate_jsonl(path):
            input_records += 1
            validation_issues = validate_record(row, int(row.get("_source_line") or 0))
            validation_errors = [
                issue for issue in validation_issues if issue.level == "error"
            ]
            if not is_ready_reviewed_candidate(row) or validation_errors:
                rejected.append(
                    {
                        "jsonl_path": row.get("_source_file"),
                        "jsonl_index": row.get("_source_line"),
                        "reason": "candidate_not_ready_for_merge",
                        "source": row.get("metadata", {}).get("source")
                        if isinstance(row.get("metadata"), dict)
                        else None,
                        "quality": row.get("quality"),
                        "output_ready": bool(str(row.get("output") or "").strip()),
                        "validation_issues": issue_summary(validation_issues),
                    }
                )
                continue

            key = reviewed_record_key(row)
            if key in existing_keys:
                duplicates.append(
                    {
                        "jsonl_path": row.get("_source_file"),
                        "jsonl_index": row.get("_source_line"),
                        "key": key,
                    }
                )
                continue

            merged = with_merge_metadata(record=row, merged_at=merged_at)
            merged_records.append(merged)
            added_records.append(merged)
            existing_keys.add(key)

    merged_validation_errors: list[dict[str, Any]] = []
    categories: Counter[str] = Counter()
    qualities: Counter[str] = Counter()
    for index, record in enumerate(merged_records, start=1):
        categories[str(record.get("category") or "uncategorized")] += 1
        qualities[str(record.get("quality") or "unspecified")] += 1
        validation_issues = validate_record(record, index)
        validation_errors = [
            issue for issue in validation_issues if issue.level == "error"
        ]
        if validation_errors:
            merged_validation_errors.append(
                {
                    "jsonl_index": index,
                    "validation_issues": issue_summary(validation_issues),
                }
            )

    hard_blockers: list[str] = []
    if rejected:
        hard_blockers.append("candidate_records_not_ready_for_merge")
    if merged_validation_errors:
        hard_blockers.append("merged_dataset_validation_errors")
    if len(merged_records) < min_total_records:
        hard_blockers.append("below_min_total_records")

    if not hard_blockers:
        write_jsonl(output_path, merged_records)

    review = {
        "command": "biber-repo-adaptation-dataset-merge",
        "generated_at": merged_at,
        "candidate_files": [str(path) for path in candidate_paths],
        "output": str(output_path),
        "input_records": input_records,
        "existing_records": len(existing_records),
        "added_records": len(added_records),
        "duplicate_records": len(duplicates),
        "rejected_records": len(rejected),
        "total_records": len(merged_records),
        "min_total_records": min_total_records,
        "categories": dict(categories),
        "qualities": dict(qualities),
        "hard_blockers": hard_blockers,
        "training_dataset_ready": False,
        "training_allowed": False,
        "safe_to_train": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "details": {
            "duplicates": duplicates,
            "rejected": rejected,
            "merged_validation_errors": merged_validation_errors,
        },
        "next_review_action": (
            "collect_more_repo_adaptation_examples_before_training"
            if not hard_blockers
            else "fix_reviewed_candidates_before_merge"
        ),
    }
    review_output.parent.mkdir(parents=True, exist_ok=True)
    review_output.write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return review


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Merge validated reviewed repo-adaptation candidates into a "
            "cumulative curated queue without approving training."
        )
    )
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--min-total-records", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    review = merge_reviewed_repo_adaptation_candidates(
        candidate_paths=args.candidates,
        output_path=args.output,
        review_output=args.review_output,
        min_total_records=args.min_total_records,
    )
    print(
        "Repo adaptation dataset merge complete: "
        f"{review['added_records']} added, "
        f"{review['duplicate_records']} duplicates, "
        f"{review['total_records']} total."
    )
    print(f"Curated queue: {args.output}")
    print(f"Review: {args.review_output}")
    return 0 if not review["hard_blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
