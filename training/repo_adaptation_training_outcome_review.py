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

from training.repo_adaptation_candidate_review import load_candidate_jsonl
from training.repo_adaptation_failure_review import as_string_list, trim_text


DEFAULT_MAX_CONTENT_CHARS = 1_200


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object.")
    return value


def load_result_jsonl(path: Path, *, eval_kind: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object.")
            row["_source_file"] = str(path)
            row["_source_line"] = line_number
            row["_eval_kind"] = eval_kind
            rows.append(row)
    return rows


def row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or "").strip()


def candidate_original_id(row: dict[str, Any]) -> str:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        return ""
    return str(metadata.get("original_id") or "").strip()


def validation_errors(row: dict[str, Any]) -> list[str]:
    value = row.get("validation_errors")
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def failure_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not bool(row.get("ok")):
        reasons.append("runtime_or_empty_response")
    if bool(row.get("ok")) and not bool(row.get("expectation_ok")):
        reasons.append("expectation_failed")
    if row.get("validation_ok") is False:
        reasons.append("validator_failed")
    return reasons


def is_failed_result(row: dict[str, Any]) -> bool:
    return bool(failure_reasons(row))


def summarize_failure(row: dict[str, Any], *, max_content_chars: int) -> dict[str, Any]:
    return {
        "id": row_id(row),
        "eval_kind": row.get("_eval_kind"),
        "reasons": failure_reasons(row),
        "ok": bool(row.get("ok")),
        "expectation_ok": bool(row.get("expectation_ok")),
        "validation_ok": row.get("validation_ok"),
        "missing_expectations": as_string_list(row.get("missing_expectations")),
        "validation_errors": validation_errors(row),
        "content_excerpt": trim_text(row.get("content"), max_content_chars),
        "source_location": {
            "file": row.get("_source_file"),
            "line": row.get("_source_line"),
        },
    }


def summarize_reviewed_candidate(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    return {
        "original_id": str(metadata.get("original_id") or ""),
        "failure_key": str(metadata.get("failure_key") or ""),
        "source": metadata.get("source"),
        "quality": row.get("quality"),
        "category": row.get("category"),
    }


def gate_summary(promotion_review: dict[str, Any]) -> list[dict[str, Any]]:
    gates = promotion_review.get("gates")
    if not isinstance(gates, list):
        return []
    summaries: list[dict[str, Any]] = []
    for gate in gates:
        if not isinstance(gate, dict):
            continue
        summaries.append(
            {
                "name": gate.get("name"),
                "ok": gate.get("ok"),
                "blocker": gate.get("blocker"),
                "actual": gate.get("actual"),
                "required": gate.get("required"),
            }
        )
    return summaries


def previous_regression_ids(previous_review: dict[str, Any]) -> set[str]:
    items = previous_review.get("items")
    if not isinstance(items, list):
        return set()
    ids: set[str] = set()
    for item in items:
        if isinstance(item, dict) and str(item.get("id") or "").strip():
            ids.add(str(item.get("id")).strip())
    return ids


def review_repo_adaptation_training_outcome(
    *,
    current_broad_results: Path,
    current_rust_results: Path,
    reviewed_candidates_path: Path,
    promotion_review_path: Path,
    previous_regression_review_path: Path | None,
    max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
) -> dict[str, Any]:
    promotion_review = load_json(promotion_review_path)
    previous_review = load_json(previous_regression_review_path)
    reviewed_rows = load_candidate_jsonl(reviewed_candidates_path)
    result_rows = [
        *load_result_jsonl(current_broad_results, eval_kind="broad"),
        *load_result_jsonl(current_rust_results, eval_kind="rust_xriq"),
    ]

    reviewed_by_id = {
        candidate_original_id(row): row
        for row in reviewed_rows
        if candidate_original_id(row)
    }
    failures = [row for row in result_rows if is_failed_result(row)]
    failures_by_id = {row_id(row): row for row in failures if row_id(row)}
    prior_ids = previous_regression_ids(previous_review)

    persistent_trained = [
        {
            "reviewed_candidate": summarize_reviewed_candidate(reviewed_by_id[row_id(row)]),
            "current_failure": summarize_failure(
                row,
                max_content_chars=max_content_chars,
            ),
        }
        for row in failures
        if row_id(row) in reviewed_by_id
    ]
    learned_ids = sorted(
        original_id
        for original_id in reviewed_by_id
        if original_id and original_id not in failures_by_id
    )
    untrained_failures = [
        summarize_failure(row, max_content_chars=max_content_chars)
        for row in failures
        if row_id(row) not in reviewed_by_id
    ]
    persisted_from_previous = sorted(
        row_id(row) for row in failures if row_id(row) in prior_ids
    )

    reason_counts: Counter[str] = Counter()
    eval_kind_counts: Counter[str] = Counter()
    for failure in failures:
        eval_kind_counts[str(failure.get("_eval_kind") or "unknown")] += 1
        reason_counts.update(failure_reasons(failure))

    promotion_blocked = promotion_review.get("review_status") == "promotion_blocked"
    persistent_trained_count = len(persistent_trained)
    if promotion_blocked and persistent_trained_count:
        review_status = "training_strategy_blocked"
        next_action = "change_prompt_or_dataset_strategy_before_more_training"
    elif promotion_blocked:
        review_status = "candidate_promotion_blocked"
        next_action = "inspect_untrained_failures_before_more_training"
    else:
        review_status = "candidate_review_not_blocked"
        next_action = "follow_promotion_review_gate"

    return {
        "source": "biber_repo_adaptation_training_outcome_review",
        "command": "biber-repo-adaptation-training-outcome-review",
        "generated_at": datetime.now(UTC).isoformat(),
        "review_status": review_status,
        "current_broad_results": str(current_broad_results),
        "current_rust_results": str(current_rust_results),
        "reviewed_candidates": str(reviewed_candidates_path),
        "promotion_review": str(promotion_review_path),
        "previous_regression_review": (
            str(previous_regression_review_path)
            if previous_regression_review_path
            else None
        ),
        "promotion_review_status": promotion_review.get("review_status"),
        "promotion_hard_blockers": promotion_review.get("hard_blockers", []),
        "promotion_gates": gate_summary(promotion_review),
        "reviewed_candidate_records": len(reviewed_rows),
        "current_result_rows": len(result_rows),
        "current_failed_rows": len(failures),
        "current_failure_counts_by_eval": dict(eval_kind_counts),
        "current_failure_counts_by_reason": dict(reason_counts),
        "persistent_trained_failures": persistent_trained_count,
        "persisted_from_previous_regression_ids": persisted_from_previous,
        "learned_reviewed_candidate_ids": learned_ids,
        "untrained_current_failures": len(untrained_failures),
        "persistent_trained_failure_details": persistent_trained,
        "untrained_current_failure_details": untrained_failures,
        "training_allowed": False,
        "safe_to_train": False,
        "approved_for_training": False,
        "promotion_allowed": False,
        "auto_promoted": False,
        "recommended_actions": [
            "do_not_start_another_training_run_from_this_artifact",
            next_action,
            "prefer_prompt_profile_or_eval_contract_changes_before_more_qlora",
            "keep_stable_adapter_served_until_broad_and_rust_gates_pass",
        ],
        "next_review_action": next_action,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review whether a repo-adaptation training run fixed the specific "
            "anti-regression rows it was trained on."
        )
    )
    parser.add_argument("--current-broad-results", type=Path, required=True)
    parser.add_argument("--current-rust-results", type=Path, required=True)
    parser.add_argument("--reviewed-candidates", type=Path, required=True)
    parser.add_argument("--promotion-review", type=Path, required=True)
    parser.add_argument("--previous-regression-review", type=Path)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--max-content-chars", type=int, default=DEFAULT_MAX_CONTENT_CHARS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    review = review_repo_adaptation_training_outcome(
        current_broad_results=args.current_broad_results,
        current_rust_results=args.current_rust_results,
        reviewed_candidates_path=args.reviewed_candidates,
        promotion_review_path=args.promotion_review,
        previous_regression_review_path=args.previous_regression_review,
        max_content_chars=args.max_content_chars,
    )
    args.review_output.parent.mkdir(parents=True, exist_ok=True)
    args.review_output.write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Repo adaptation training outcome review: "
        f"{review['review_status']}; "
        f"{review['persistent_trained_failures']} trained failures persisted."
    )
    print(f"Review: {args.review_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
