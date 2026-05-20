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
from training.repo_adaptation_candidate_review import (
    READY_QUALITIES,
    is_repo_adaptation_candidate,
    load_candidate_jsonl,
)
from training.repo_adaptation_dataset_merge import reviewed_record_key


DEFAULT_REQUIRED_CATEGORIES = ("bash", "markdown", "python", "sql")


def issue_summary(issues: list[DatasetIssue]) -> list[dict[str, Any]]:
    return [
        {
            "line_number": issue.line_number,
            "level": issue.level,
            "message": issue.message,
        }
        for issue in issues
    ]


def summarize_bad_record(
    *,
    row: dict[str, Any],
    reason: str,
    validation_issues: list[DatasetIssue] | None = None,
) -> dict[str, Any]:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "jsonl_path": row.get("_source_file"),
        "jsonl_index": row.get("_source_line"),
        "reason": reason,
        "category": row.get("category"),
        "quality": row.get("quality"),
        "source": metadata.get("source"),
        "failure_key": metadata.get("failure_key"),
        "original_id": metadata.get("original_id"),
        "output_ready": bool(str(row.get("output") or "").strip()),
        "validation_issues": issue_summary(validation_issues or []),
    }


def review_repo_adaptation_dataset_readiness(
    *,
    dataset_path: Path,
    min_records: int,
    min_categories: int,
    required_categories: list[str],
) -> dict[str, Any]:
    if min_records < 1:
        raise ValueError("min_records must be at least 1.")
    if min_categories < 1:
        raise ValueError("min_categories must be at least 1.")

    generated_at = datetime.now(UTC).isoformat()
    rows: list[dict[str, Any]] = []
    load_error: str | None = None
    if not dataset_path.exists():
        load_error = f"Dataset not found: {dataset_path}"
    else:
        try:
            rows = load_candidate_jsonl(dataset_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            load_error = str(exc)

    categories: Counter[str] = Counter()
    qualities: Counter[str] = Counter()
    ready_records = 0
    validation_error_records: list[dict[str, Any]] = []
    unsupported_records: list[dict[str, Any]] = []
    not_ready_records: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = []
    seen_keys: dict[str, dict[str, Any]] = {}

    if load_error is None:
        for row in rows:
            category = str(row.get("category") or "uncategorized").strip() or "uncategorized"
            quality = str(row.get("quality") or "unspecified").strip() or "unspecified"
            categories[category] += 1
            qualities[quality] += 1

            validation_issues = validate_record(
                row,
                int(row.get("_source_line") or 0),
            )
            validation_errors = [
                issue for issue in validation_issues if issue.level == "error"
            ]
            if validation_errors:
                validation_error_records.append(
                    summarize_bad_record(
                        row=row,
                        reason="validation_error",
                        validation_issues=validation_issues,
                    )
                )

            if not is_repo_adaptation_candidate(row):
                unsupported_records.append(
                    summarize_bad_record(row=row, reason="unsupported_source")
                )

            output_ready = bool(str(row.get("output") or "").strip())
            quality_ready = quality in READY_QUALITIES
            if not output_ready or not quality_ready:
                not_ready_records.append(
                    summarize_bad_record(row=row, reason="output_or_quality_not_ready")
                )

            key = reviewed_record_key(row)
            if key in seen_keys:
                duplicate_records.append(
                    {
                        "key": key,
                        "first_jsonl_index": seen_keys[key].get("_source_line"),
                        "duplicate_jsonl_index": row.get("_source_line"),
                    }
                )
            else:
                seen_keys[key] = row

            if (
                not validation_errors
                and is_repo_adaptation_candidate(row)
                and output_ready
                and quality_ready
            ):
                ready_records += 1

    required_category_counts = {
        category: categories.get(category, 0) for category in required_categories
    }
    missing_required_categories = [
        category for category, count in required_category_counts.items() if count <= 0
    ]

    hard_blockers: list[str] = []
    if load_error is not None:
        hard_blockers.append("dataset_missing_or_unreadable")
    if not rows:
        hard_blockers.append("no_records")
    if validation_error_records:
        hard_blockers.append("dataset_validation_errors")
    if unsupported_records:
        hard_blockers.append("unsupported_source_records")
    if not_ready_records:
        hard_blockers.append("records_not_ready_for_training_review")
    if duplicate_records:
        hard_blockers.append("duplicate_records_present")
    if ready_records < min_records:
        hard_blockers.append("below_min_ready_records")
    if len(categories) < min_categories:
        hard_blockers.append("below_min_category_diversity")
    if missing_required_categories:
        hard_blockers.append("missing_required_categories")

    ready_for_manual_training_review = not hard_blockers
    review_status = (
        "manual_training_review_required"
        if ready_for_manual_training_review
        else "training_blocked"
    )

    return {
        "source": "biber_repo_adaptation_dataset_readiness_review",
        "command": "biber-repo-adaptation-dataset-readiness",
        "generated_at": generated_at,
        "dataset": str(dataset_path),
        "review_status": review_status,
        "training_gate_status": (
            "manual_review_required"
            if ready_for_manual_training_review
            else "blocked"
        ),
        "records": len(rows),
        "ready_records": ready_records,
        "min_records": min_records,
        "record_gap": max(0, min_records - ready_records),
        "categories": dict(categories),
        "category_count": len(categories),
        "min_categories": min_categories,
        "category_gap": max(0, min_categories - len(categories)),
        "required_categories": list(required_categories),
        "required_category_counts": required_category_counts,
        "missing_required_categories": missing_required_categories,
        "qualities": dict(qualities),
        "validation_error_records": len(validation_error_records),
        "unsupported_source_records": len(unsupported_records),
        "not_ready_records": len(not_ready_records),
        "duplicate_records": len(duplicate_records),
        "hard_blockers": hard_blockers,
        "load_error": load_error,
        "ready_for_manual_training_review": ready_for_manual_training_review,
        "required_manual_actions": [
            "collect_more_reviewed_repo_adaptation_examples",
            "manual_training_dataset_review",
            "explicit_user_approval_before_any_training_job",
            "separate_vast_gpu_training_run_outside_codex_loop",
        ],
        "training_dataset_ready": False,
        "training_allowed": False,
        "safe_to_train": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "details": {
            "validation_error_records": validation_error_records,
            "unsupported_records": unsupported_records,
            "not_ready_records": not_ready_records,
            "duplicate_records": duplicate_records,
        },
        "next_review_action": (
            "manual_training_dataset_review_required_before_training"
            if ready_for_manual_training_review
            else "collect_more_repo_adaptation_examples_before_training"
        ),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review cumulative repo-adaptation dataset readiness without "
            "approving or starting training."
        )
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--min-records", type=int, default=50)
    parser.add_argument("--min-categories", type=int, default=4)
    parser.add_argument(
        "--required-category",
        action="append",
        default=[],
        help=(
            "Category that must be present at least once. Can be passed "
            "multiple times. Defaults to bash, markdown, python, and sql."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    required_categories = args.required_category or list(DEFAULT_REQUIRED_CATEGORIES)
    review = review_repo_adaptation_dataset_readiness(
        dataset_path=args.dataset,
        min_records=args.min_records,
        min_categories=args.min_categories,
        required_categories=required_categories,
    )
    args.review_output.parent.mkdir(parents=True, exist_ok=True)
    args.review_output.write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Repo adaptation dataset readiness: "
        f"{review['review_status']}; "
        f"{review['ready_records']}/{review['min_records']} ready records."
    )
    print(f"Review: {args.review_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
