from __future__ import annotations

import argparse
import json
import sys
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


APPROVE_DECISIONS = {"approve", "approve_for_dataset_validation"}
DEFER_DECISIONS = {"defer", "reject"}


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def load_decision_payload(path: Path) -> tuple[str | None, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        reviewer = str(payload.get("reviewer") or "").strip() or None
        decisions = payload.get("decisions")
        if not isinstance(decisions, list):
            raise ValueError("Decision file object must contain a decisions list.")
    elif isinstance(payload, list):
        reviewer = None
        decisions = payload
    else:
        raise ValueError("Decision file must be a JSON object or array.")
    normalized: list[dict[str, Any]] = []
    for index, decision in enumerate(decisions, start=1):
        if not isinstance(decision, dict):
            raise ValueError(f"Decision {index} must be a JSON object.")
        normalized.append(decision)
    return reviewer, normalized


def decision_key(decision: dict[str, Any]) -> tuple[str, str]:
    failure_key = str(decision.get("failure_key") or "").strip()
    if failure_key:
        return ("failure_key", failure_key)
    original_id = str(decision.get("original_id") or "").strip()
    if original_id:
        return ("original_id", original_id)
    raise ValueError("Each decision must include failure_key or original_id.")


def candidate_keys(row: dict[str, Any]) -> list[tuple[str, str]]:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    keys: list[tuple[str, str]] = []
    failure_key = str(metadata.get("failure_key") or "").strip()
    if failure_key:
        keys.append(("failure_key", failure_key))
    original_id = str(metadata.get("original_id") or "").strip()
    if original_id:
        keys.append(("original_id", original_id))
    return keys


def build_decision_map(decisions: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    mapped: dict[tuple[str, str], dict[str, Any]] = {}
    for decision in decisions:
        key = decision_key(decision)
        if key in mapped:
            raise ValueError(f"Duplicate decision for {key[0]}={key[1]}.")
        mapped[key] = decision
    return mapped


def issue_summary(issues: list[DatasetIssue]) -> list[dict[str, Any]]:
    return [
        {
            "line_number": issue.line_number,
            "level": issue.level,
            "message": issue.message,
        }
        for issue in issues
    ]


def find_decision(
    row: dict[str, Any],
    decisions: dict[tuple[str, str], dict[str, Any]],
) -> tuple[tuple[str, str] | None, dict[str, Any] | None]:
    for key in candidate_keys(row):
        if key in decisions:
            return key, decisions[key]
    return None, None


def apply_approval_decision(
    *,
    row: dict[str, Any],
    decision: dict[str, Any],
    reviewer: str | None,
    reviewed_at: str,
) -> tuple[dict[str, Any] | None, list[DatasetIssue], str | None]:
    output = str(decision.get("output") or "").strip()
    if not output:
        return None, [], "approved_decision_missing_output"
    quality = str(decision.get("quality") or "reviewed").strip()
    if quality not in READY_QUALITIES:
        return None, [], "approved_decision_quality_not_ready"

    reviewed = {
        key: value
        for key, value in row.items()
        if not key.startswith("_source_")
    }
    metadata = reviewed.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata = dict(metadata)
    metadata["review_required"] = False
    metadata["candidate_review"] = {
        "decision": str(decision.get("decision") or "approve"),
        "reviewer": str(decision.get("reviewer") or reviewer or "unknown"),
        "reviewed_at": reviewed_at,
        "notes": str(decision.get("notes") or ""),
        "source_candidate_file": row.get("_source_file"),
        "source_candidate_line": row.get("_source_line"),
    }
    metadata["promotion_rule"] = (
        "Validate the reviewed dataset and obtain explicit user approval "
        "before starting any training job."
    )
    reviewed["metadata"] = metadata
    reviewed["output"] = output
    reviewed["quality"] = quality
    validation_issues = validate_record(reviewed, int(row.get("_source_line") or 0))
    validation_errors = [
        issue for issue in validation_issues if issue.level == "error"
    ]
    if validation_errors:
        return None, validation_issues, "approved_record_validation_error"
    return reviewed, validation_issues, None


def apply_repo_adaptation_candidate_decisions(
    *,
    candidate_paths: list[Path],
    decision_path: Path,
    output_path: Path,
    review_output: Path,
) -> dict[str, Any]:
    reviewer, decisions = load_decision_payload(decision_path)
    decision_map = build_decision_map(decisions)
    reviewed_at = datetime.now(UTC).isoformat()

    candidates = [
        row for path in candidate_paths for row in load_candidate_jsonl(path)
    ]
    approved_records: list[dict[str, Any]] = []
    rejected_candidates: list[dict[str, Any]] = []
    missing_decisions: list[dict[str, Any]] = []
    decision_errors: list[dict[str, Any]] = []
    matched_decision_keys: set[tuple[str, str]] = set()
    decision_counts = {"approve": 0, "defer": 0, "reject": 0}

    for row in candidates:
        if not is_repo_adaptation_candidate(row):
            rejected_candidates.append(
                {
                    "jsonl_path": row.get("_source_file"),
                    "jsonl_index": row.get("_source_line"),
                    "reason": "unsupported_source",
                    "metadata": row.get("metadata"),
                }
            )
            continue
        key, decision = find_decision(row, decision_map)
        if decision is None or key is None:
            missing_decisions.append(
                {
                    "jsonl_path": row.get("_source_file"),
                    "jsonl_index": row.get("_source_line"),
                    "keys": candidate_keys(row),
                }
            )
            continue
        matched_decision_keys.add(key)
        action = str(decision.get("decision") or "").strip()
        if action in APPROVE_DECISIONS:
            decision_counts["approve"] += 1
            approved, validation_issues, error = apply_approval_decision(
                row=row,
                decision=decision,
                reviewer=reviewer,
                reviewed_at=reviewed_at,
            )
            if approved is None:
                decision_errors.append(
                    {
                        "jsonl_path": row.get("_source_file"),
                        "jsonl_index": row.get("_source_line"),
                        "reason": error,
                        "validation_issues": issue_summary(validation_issues),
                    }
                )
            else:
                approved_records.append(approved)
            continue
        if action in DEFER_DECISIONS:
            decision_counts[action] += 1
            continue
        decision_errors.append(
            {
                "jsonl_path": row.get("_source_file"),
                "jsonl_index": row.get("_source_line"),
                "reason": "unsupported_decision",
                "decision": action,
            }
        )

    unmatched_decisions = [
        {"key_type": key[0], "key": key[1]}
        for key in sorted(decision_map)
        if key not in matched_decision_keys
    ]
    hard_blockers: list[str] = []
    if rejected_candidates:
        hard_blockers.append("unsupported_candidate_records_present")
    if missing_decisions:
        hard_blockers.append("candidate_decisions_missing")
    if decision_errors:
        hard_blockers.append("candidate_decision_errors")
    if unmatched_decisions:
        hard_blockers.append("unmatched_decisions_present")
    write_jsonl(output_path, approved_records)

    review = {
        "command": "biber-repo-adaptation-candidate-decisions",
        "generated_at": reviewed_at,
        "candidate_files": [str(path) for path in candidate_paths],
        "decision_file": str(decision_path),
        "output": str(output_path),
        "records": len(candidates),
        "approved_records": len(approved_records),
        "rejected_candidates": len(rejected_candidates),
        "missing_decisions": len(missing_decisions),
        "decision_errors": len(decision_errors),
        "unmatched_decisions": len(unmatched_decisions),
        "decision_counts": decision_counts,
        "hard_blockers": hard_blockers,
        "training_dataset_ready": False,
        "training_allowed": False,
        "safe_to_train": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "details": {
            "rejected_candidates": rejected_candidates,
            "missing_decisions": missing_decisions,
            "decision_errors": decision_errors,
            "unmatched_decisions": unmatched_decisions,
        },
        "next_review_action": (
            "run_repo_adaptation_candidate_review_on_reviewed_output"
            if not hard_blockers
            else "fix_candidate_decisions_before_dataset_validation"
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
        description="Apply human decisions to repo-adaptation candidate JSONL."
    )
    parser.add_argument("--candidates", type=Path, nargs="+", required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    review = apply_repo_adaptation_candidate_decisions(
        candidate_paths=args.candidates,
        decision_path=args.decisions,
        output_path=args.output,
        review_output=args.review_output,
    )
    print(
        "Repo adaptation candidate decisions complete: "
        f"{review['approved_records']}/{review['records']} approved."
    )
    print(f"Reviewed candidates: {args.output}")
    print(f"Review: {args.review_output}")
    return 0 if not review["hard_blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
