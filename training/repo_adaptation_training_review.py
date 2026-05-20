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


def row_metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def prompt_variant_from_original_id(original_id: str) -> str:
    for variant in (
        "risk-and-verification",
        "regression-test",
        "context-selection",
        "implementation-step",
    ):
        if variant in original_id:
            return variant.replace("-", "_")
    return "unknown"


def summarize_record(
    *,
    row: dict[str, Any],
    line_number: int,
    reason: str,
    validation_issues: list[DatasetIssue] | None = None,
) -> dict[str, Any]:
    metadata = row_metadata(row)
    return {
        "jsonl_index": line_number,
        "reason": reason,
        "category": row.get("category"),
        "quality": row.get("quality"),
        "source": metadata.get("source"),
        "failure_key": metadata.get("failure_key"),
        "original_id": metadata.get("original_id"),
        "validation_issues": issue_summary(validation_issues or []),
    }


def review_repo_adaptation_training_dataset(
    *,
    dataset_path: Path,
    review_output: Path,
    min_records: int,
    min_categories: int,
    required_categories: list[str],
    output_dir: str,
    session_name: str,
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
    sources: Counter[str] = Counter()
    prompt_variants: Counter[str] = Counter()
    stack_items: Counter[str] = Counter()
    validation_errors: list[dict[str, Any]] = []
    unsupported_records: list[dict[str, Any]] = []
    not_ready_records: list[dict[str, Any]] = []
    duplicate_records: list[dict[str, Any]] = []
    seen_keys: dict[str, int] = {}
    ready_records = 0

    if load_error is None:
        for line_number, row in enumerate(rows, start=1):
            category = str(row.get("category") or "uncategorized").strip() or "uncategorized"
            quality = str(row.get("quality") or "unspecified").strip() or "unspecified"
            metadata = row_metadata(row)
            source = str(metadata.get("source") or "unknown")
            original_id = str(metadata.get("original_id") or "")
            categories[category] += 1
            qualities[quality] += 1
            sources[source] += 1
            prompt_variants[prompt_variant_from_original_id(original_id)] += 1
            stack = row.get("stack")
            if isinstance(stack, list):
                for item in stack:
                    if isinstance(item, str) and item.strip():
                        stack_items[item.strip()] += 1

            validation_issues = validate_record(row, line_number)
            row_validation_errors = [
                issue for issue in validation_issues if issue.level == "error"
            ]
            if row_validation_errors:
                validation_errors.append(
                    summarize_record(
                        row=row,
                        line_number=line_number,
                        reason="validation_error",
                        validation_issues=validation_issues,
                    )
                )
            if not is_repo_adaptation_candidate(row):
                unsupported_records.append(
                    summarize_record(
                        row=row,
                        line_number=line_number,
                        reason="unsupported_source",
                    )
                )
            if not str(row.get("output") or "").strip() or quality not in READY_QUALITIES:
                not_ready_records.append(
                    summarize_record(
                        row=row,
                        line_number=line_number,
                        reason="output_or_quality_not_ready",
                    )
                )

            key = reviewed_record_key(row)
            if key in seen_keys:
                duplicate_records.append(
                    {
                        "key": key,
                        "first_jsonl_index": seen_keys[key],
                        "duplicate_jsonl_index": line_number,
                    }
                )
            else:
                seen_keys[key] = line_number

            if (
                not row_validation_errors
                and is_repo_adaptation_candidate(row)
                and str(row.get("output") or "").strip()
                and quality in READY_QUALITIES
            ):
                ready_records += 1

    required_category_counts = {
        category: categories.get(category, 0) for category in required_categories
    }
    missing_required_categories = [
        category for category, count in required_category_counts.items() if count <= 0
    ]

    blockers: list[str] = []
    if load_error is not None:
        blockers.append("dataset_missing_or_unreadable")
    if not rows:
        blockers.append("no_records")
    if validation_errors:
        blockers.append("dataset_validation_errors")
    if unsupported_records:
        blockers.append("unsupported_source_records")
    if not_ready_records:
        blockers.append("records_not_ready")
    if duplicate_records:
        blockers.append("duplicate_records_present")
    if ready_records < min_records:
        blockers.append("below_min_ready_records")
    if len(categories) < min_categories:
        blockers.append("below_min_category_diversity")
    if missing_required_categories:
        blockers.append("missing_required_categories")

    ready_for_user_training_approval = not blockers
    suggested_command = (
        "BIBER_TRAIN_DATASET={dataset} "
        "BIBER_TRAIN_OUTPUT_DIR={output_dir} "
        "BIBER_TRAIN_SESSION={session_name} "
        "BIBER_TRAIN_MIN_RECORDS={min_records} "
        "bash scripts/vast_train_qlora_tmux.sh {dataset}"
    ).format(
        dataset=dataset_path,
        output_dir=output_dir,
        session_name=session_name,
        min_records=min_records,
    )

    review = {
        "source": "biber_repo_adaptation_manual_training_review",
        "command": "biber-repo-adaptation-training-review",
        "generated_at": generated_at,
        "dataset": str(dataset_path),
        "review_output": str(review_output),
        "review_status": (
            "ready_for_user_training_approval"
            if ready_for_user_training_approval
            else "manual_training_review_blocked"
        ),
        "records": len(rows),
        "ready_records": ready_records,
        "min_records": min_records,
        "record_gap": max(0, min_records - ready_records),
        "categories": dict(categories),
        "category_count": len(categories),
        "min_categories": min_categories,
        "category_gap": max(0, min_categories - len(categories)),
        "required_categories": required_categories,
        "required_category_counts": required_category_counts,
        "missing_required_categories": missing_required_categories,
        "qualities": dict(qualities),
        "sources": dict(sources),
        "prompt_variants": dict(prompt_variants),
        "top_stack_items": dict(stack_items.most_common(20)),
        "hard_blockers": blockers,
        "load_error": load_error,
        "details": {
            "validation_error_records": validation_errors,
            "unsupported_records": unsupported_records,
            "not_ready_records": not_ready_records,
            "duplicate_records": duplicate_records,
        },
        "ready_for_user_training_approval": ready_for_user_training_approval,
        "requires_explicit_user_training_approval": True,
        "recommended_training": {
            "dataset": str(dataset_path),
            "output_dir": output_dir,
            "session_name": session_name,
            "command": suggested_command,
            "notes": [
                "Run only after explicit user approval.",
                "Run on Vast GPU in tmux, outside the Codex/OpenAI loop.",
                "Stop serving first if GPU memory is tight.",
                "Evaluate the adapter before promotion.",
            ],
        },
        "training_dataset_ready": False,
        "training_allowed": False,
        "safe_to_train": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "next_review_action": (
            "ask_user_for_explicit_training_approval"
            if ready_for_user_training_approval
            else "fix_manual_training_review_blockers"
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
            "Create a manual pre-training review for a repo-adaptation dataset "
            "without approving or starting training."
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
        help="Category that must be present at least once.",
    )
    parser.add_argument(
        "--output-dir",
        default="/workspace/adapters/biber-dev-core-repo-adapt-manual-review",
    )
    parser.add_argument("--session-name", default="biber-repo-adapt-review")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    required_categories = args.required_category or list(DEFAULT_REQUIRED_CATEGORIES)
    review = review_repo_adaptation_training_dataset(
        dataset_path=args.dataset,
        review_output=args.review_output,
        min_records=args.min_records,
        min_categories=args.min_categories,
        required_categories=required_categories,
        output_dir=args.output_dir,
        session_name=args.session_name,
    )
    print(
        "Repo adaptation manual training review: "
        f"{review['review_status']}; "
        f"{review['ready_records']}/{review['min_records']} ready records."
    )
    print(f"Review: {args.review_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
