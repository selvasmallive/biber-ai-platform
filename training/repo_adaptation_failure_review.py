from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.dataset_utils import validate_record


DEFAULT_MAX_CONTENT_CHARS = 4_000


def load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def normalize_language(value: Any) -> str:
    language = str(value or "").strip().lower()
    return language or "repo_adaptation"


def as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def trim_text(value: Any, max_chars: int) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 22].rstrip() + "\n...[truncated]"


def build_failure_key(row: dict[str, Any]) -> str:
    key_payload = {
        "id": str(row.get("id") or ""),
        "prompt": str(row.get("prompt") or ""),
        "language": str(row.get("language") or ""),
        "task_type": str(row.get("task_type") or ""),
        "missing_expectations": sorted(as_string_list(row.get("missing_expectations"))),
    }
    encoded = json.dumps(key_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def has_secret_like_text(record: dict[str, Any]) -> bool:
    probe = dict(record)
    if not str(probe.get("output") or "").strip():
        probe["output"] = "REVIEW_REQUIRED"
    return any(
        issue.level == "error" and "secret" in issue.message.lower()
        for issue in validate_record(probe, 1)
    )


def summarize_group(
    failure_key: str,
    rows: list[dict[str, Any]],
    *,
    min_repeats: int,
    max_content_chars: int,
) -> dict[str, Any]:
    first = rows[0]
    missing = sorted(
        {
            expectation
            for row in rows
            for expectation in as_string_list(row.get("missing_expectations"))
        }
    )
    latest = rows[-1]
    candidate_probe = build_training_candidate_probe(
        failure_key,
        first,
        missing_expectations=missing,
        latest_content=trim_text(latest.get("content"), max_content_chars),
        repeat_count=len(rows),
    )
    secret_blocked = has_secret_like_text(candidate_probe)
    runtime_blocked = any(not bool(row.get("ok")) for row in rows)
    eligible = len(rows) >= min_repeats and not secret_blocked and not runtime_blocked
    if runtime_blocked:
        recommended_action = "fix_runtime_or_api_error_before_training"
    elif secret_blocked:
        recommended_action = "redact_or_discard_secret_like_failure"
    elif eligible:
        recommended_action = "write_reviewed_answer_then_promote_to_training_dataset"
    else:
        recommended_action = "rerun_eval_until_failure_is_repeatable"

    return {
        "failure_key": failure_key,
        "id": str(first.get("id") or ""),
        "language": first.get("language"),
        "task_type": first.get("task_type") or "repo_adaptation_eval",
        "prompt": str(first.get("prompt") or ""),
        "repeat_count": len(rows),
        "response_ok_count": sum(1 for row in rows if bool(row.get("ok"))),
        "expectation_ok_count": sum(1 for row in rows if bool(row.get("expectation_ok"))),
        "missing_expectations": missing,
        "models": sorted({str(row.get("model") or "") for row in rows if row.get("model")}),
        "latest_content": trim_text(latest.get("content"), max_content_chars),
        "latest_error": latest.get("error"),
        "source_locations": [
            {
                "file": row.get("_source_file"),
                "line": row.get("_source_line"),
            }
            for row in rows
        ],
        "eligible_for_training_candidate": eligible,
        "blocked_reasons": [
            reason
            for reason, blocked in (
                ("below_min_repeats", len(rows) < min_repeats),
                ("runtime_or_api_error", runtime_blocked),
                ("secret_like_text", secret_blocked),
            )
            if blocked
        ],
        "recommended_action": recommended_action,
    }


def build_training_candidate_probe(
    failure_key: str,
    row: dict[str, Any],
    *,
    missing_expectations: list[str],
    latest_content: str,
    repeat_count: int,
) -> dict[str, Any]:
    category = normalize_language(row.get("language"))
    task_type = str(row.get("task_type") or "repo_adaptation_eval")
    stack = [category, "repo_adaptation"]
    if task_type not in stack:
        stack.append(task_type)
    return {
        "instruction": str(row.get("prompt") or "").strip(),
        "input": (
            "Repo adaptation failure requiring human review.\n"
            f"failure_key: {failure_key}\n"
            f"repeat_count: {repeat_count}\n"
            f"missing_expectations: {', '.join(missing_expectations) or 'none'}\n\n"
            "Latest model output:\n"
            f"{latest_content}"
        ),
        "output": "",
        "category": category,
        "stack": stack,
        "quality": "needs_review",
        "metadata": {
            "source": "repo_adaptation_failure_review",
            "failure_key": failure_key,
            "original_id": str(row.get("id") or ""),
            "review_required": True,
            "promotion_rule": "Fill output with a verified answer and change quality before training.",
        },
    }


def build_training_candidate(review_item: dict[str, Any]) -> dict[str, Any]:
    category = normalize_language(review_item.get("language"))
    task_type = str(review_item.get("task_type") or "repo_adaptation_eval")
    stack = [category, "repo_adaptation"]
    if task_type not in stack:
        stack.append(task_type)
    return {
        "instruction": str(review_item.get("prompt") or "").strip(),
        "input": (
            "Repo adaptation failure requiring human review.\n"
            f"failure_key: {review_item['failure_key']}\n"
            f"repeat_count: {review_item['repeat_count']}\n"
            "missing_expectations: "
            f"{', '.join(review_item.get('missing_expectations') or []) or 'none'}\n\n"
            "Latest model output:\n"
            f"{review_item.get('latest_content') or ''}"
        ),
        "output": "",
        "category": category,
        "stack": stack,
        "quality": "needs_review",
        "metadata": {
            "source": "repo_adaptation_failure_review",
            "failure_key": review_item["failure_key"],
            "original_id": str(review_item.get("id") or ""),
            "review_required": True,
            "promotion_rule": "Fill output with a verified answer and change quality before training.",
        },
    }


def build_review(
    failures: list[dict[str, Any]],
    *,
    min_repeats: int,
    max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in failures:
        groups[build_failure_key(row)].append(row)

    items = [
        summarize_group(
            failure_key,
            rows,
            min_repeats=min_repeats,
            max_content_chars=max_content_chars,
        )
        for failure_key, rows in groups.items()
    ]
    items.sort(key=lambda item: (-int(item["repeat_count"]), str(item["id"])))
    candidate_count = sum(1 for item in items if item["eligible_for_training_candidate"])
    return {
        "command": "biber-repo-adaptation-failure-review",
        "generated_at": datetime.now(UTC).isoformat(),
        "min_repeats": min_repeats,
        "failures_seen": len(failures),
        "groups": len(items),
        "training_candidates": candidate_count,
        "review_required": True,
        "items": items,
    }


def run_failure_review(
    *,
    failure_paths: list[Path],
    review_output: Path,
    training_candidates_output: Path | None,
    min_repeats: int,
    max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
) -> dict[str, Any]:
    if min_repeats < 1:
        raise ValueError("min_repeats must be at least 1.")
    failures = [row for path in failure_paths for row in load_jsonl(path)]
    review = build_review(
        failures,
        min_repeats=min_repeats,
        max_content_chars=max_content_chars,
    )
    if training_candidates_output is not None:
        candidates = [
            build_training_candidate(item)
            for item in review["items"]
            if item["eligible_for_training_candidate"]
        ]
        write_jsonl(training_candidates_output, candidates)
        review["training_candidates_output"] = str(training_candidates_output)
    else:
        review["training_candidates_output"] = None

    review_output.parent.mkdir(parents=True, exist_ok=True)
    review_output.write_text(json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return review


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize repo-adaptation eval failures for human review."
    )
    parser.add_argument("--failures", type=Path, nargs="+", required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--training-candidates-output", type=Path)
    parser.add_argument("--min-repeats", type=int, default=2)
    parser.add_argument("--max-content-chars", type=int, default=DEFAULT_MAX_CONTENT_CHARS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    review = run_failure_review(
        failure_paths=args.failures,
        review_output=args.review_output,
        training_candidates_output=args.training_candidates_output,
        min_repeats=args.min_repeats,
        max_content_chars=args.max_content_chars,
    )
    print(
        "Repo adaptation failure review complete: "
        f"{review['failures_seen']} failures, {review['groups']} groups, "
        f"{review['training_candidates']} training candidates need review."
    )
    print(f"Review: {args.review_output}")
    if args.training_candidates_output:
        print(f"Training candidates: {args.training_candidates_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
