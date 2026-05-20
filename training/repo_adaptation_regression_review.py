from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from training.live_model_eval import load_eval_prompts
from training.repo_adaptation_failure_review import (
    as_string_list,
    has_secret_like_text,
    normalize_language,
    trim_text,
    write_jsonl,
)


DEFAULT_MAX_CONTENT_CHARS = 4_000
DEFAULT_MAX_VALIDATION_DETAIL_CHARS = 2_000


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object.")
    return value


def load_prompt_metadata(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None:
        return {}
    prompts = load_eval_prompts(path)
    return {
        prompt.id: {
            "prompt": prompt.prompt,
            "language": prompt.language,
            "task_type": prompt.task_type,
        }
        for prompt in prompts
    }


def load_jsonl(
    path: Path,
    *,
    eval_kind: str,
    prompt_metadata: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected a JSON object.")
            metadata = prompt_metadata.get(str(value.get("id") or ""))
            if metadata:
                for key, metadata_value in metadata.items():
                    if value.get(key) in {None, ""}:
                        value[key] = metadata_value
            value["_source_file"] = str(path)
            value["_source_line"] = line_number
            value["_eval_kind"] = eval_kind
            rows.append(value)
    return rows


def validation_errors(row: dict[str, Any]) -> list[str]:
    errors = row.get("validation_errors")
    if isinstance(errors, list):
        return [str(error) for error in errors if str(error).strip()]
    return []


def validation_details(row: dict[str, Any], *, max_chars: int) -> str:
    details = row.get("validation_details")
    if not details:
        return ""
    return trim_text(json.dumps(details, sort_keys=True), max_chars)


def issue_types_for_row(row: dict[str, Any]) -> list[str]:
    issue_types: list[str] = []
    if not bool(row.get("ok")):
        issue_types.append("runtime_or_empty_response")
    if bool(row.get("ok")) and not bool(row.get("expectation_ok")):
        issue_types.append("expectation_regression")
    if row.get("validation_ok") is False:
        issue_types.append("validator_regression")
    return issue_types


def is_regression_row(row: dict[str, Any]) -> bool:
    return bool(issue_types_for_row(row))


def regression_key(row: dict[str, Any], issue_types: list[str]) -> str:
    key_payload = {
        "eval_kind": str(row.get("_eval_kind") or ""),
        "id": str(row.get("id") or ""),
        "language": str(row.get("language") or ""),
        "task_type": str(row.get("task_type") or ""),
        "issue_types": sorted(issue_types),
        "missing_expectations": sorted(as_string_list(row.get("missing_expectations"))),
        "validation_errors": sorted(validation_errors(row)),
    }
    encoded = json.dumps(key_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def summarize_regression(
    row: dict[str, Any],
    *,
    max_content_chars: int,
    max_validation_detail_chars: int,
) -> dict[str, Any]:
    issue_types = issue_types_for_row(row)
    key = regression_key(row, issue_types)
    missing = as_string_list(row.get("missing_expectations"))
    validator_errors = validation_errors(row)
    candidate_probe = build_anti_regression_candidate(
        {
            "regression_key": key,
            "row": row,
            "issue_types": issue_types,
            "missing_expectations": missing,
            "validation_errors": validator_errors,
            "validation_details": validation_details(
                row,
                max_chars=max_validation_detail_chars,
            ),
            "latest_content": trim_text(row.get("content"), max_content_chars),
        },
        candidate_adapter=None,
        stable_adapter=None,
        promotion_review=None,
    )
    runtime_blocked = "runtime_or_empty_response" in issue_types
    secret_blocked = has_secret_like_text(candidate_probe)
    eligible = not runtime_blocked and not secret_blocked
    if runtime_blocked:
        recommended_action = "fix_runtime_or_api_error_before_training"
    elif secret_blocked:
        recommended_action = "redact_or_discard_secret_like_regression"
    elif "validator_regression" in issue_types:
        recommended_action = "write_verified_compile_passing_answer_before_training"
    else:
        recommended_action = "write_verified_expected_answer_before_training"

    return {
        "regression_key": key,
        "eval_kind": row.get("_eval_kind"),
        "id": str(row.get("id") or ""),
        "language": row.get("language"),
        "task_type": row.get("task_type") or "code_generation",
        "prompt": str(row.get("prompt") or ""),
        "model": row.get("model"),
        "issue_types": issue_types,
        "ok": bool(row.get("ok")),
        "expectation_ok": bool(row.get("expectation_ok")),
        "validation_ok": row.get("validation_ok"),
        "missing_expectations": missing,
        "validation_errors": validator_errors,
        "validation_details": validation_details(
            row,
            max_chars=max_validation_detail_chars,
        ),
        "latest_content": trim_text(row.get("content"), max_content_chars),
        "latest_error": row.get("error"),
        "source_location": {
            "file": row.get("_source_file"),
            "line": row.get("_source_line"),
        },
        "eligible_for_anti_regression_candidate": eligible,
        "blocked_reasons": [
            reason
            for reason, blocked in (
                ("runtime_or_api_error", runtime_blocked),
                ("secret_like_text", secret_blocked),
            )
            if blocked
        ],
        "recommended_action": recommended_action,
        "row": row,
    }


def build_anti_regression_candidate(
    item: dict[str, Any],
    *,
    candidate_adapter: str | None,
    stable_adapter: str | None,
    promotion_review: str | None,
) -> dict[str, Any]:
    row = item["row"]
    category = normalize_language(row.get("language"))
    task_type = str(row.get("task_type") or "code_generation")
    stack = [category, "repo_adaptation", "anti_regression"]
    if task_type not in stack:
        stack.append(task_type)

    missing = item.get("missing_expectations") or []
    validator_errors = item.get("validation_errors") or []
    validation_detail_text = str(item.get("validation_details") or "")
    input_parts = [
        "Candidate adapter regression requiring human review.",
        f"regression_key: {item['regression_key']}",
        f"eval_kind: {item.get('eval_kind') or row.get('_eval_kind')}",
        f"issue_types: {', '.join(item.get('issue_types') or []) or 'none'}",
        f"missing_expectations: {', '.join(missing) or 'none'}",
        f"validation_errors: {', '.join(validator_errors) or 'none'}",
    ]
    if validation_detail_text:
        input_parts.extend(["", "Validator details:", validation_detail_text])
    input_parts.extend(["", "Candidate model output:", str(item.get("latest_content") or "")])

    metadata = {
        "source": "repo_adaptation_adapter_regression_review",
        "failure_key": item["regression_key"],
        "regression_key": item["regression_key"],
        "original_id": str(row.get("id") or ""),
        "eval_kind": item.get("eval_kind") or row.get("_eval_kind"),
        "issue_types": item.get("issue_types") or [],
        "candidate_adapter": candidate_adapter,
        "stable_adapter": stable_adapter,
        "promotion_review": promotion_review,
        "review_required": True,
        "approved_for_training": False,
        "training_allowed": False,
        "safe_to_train": False,
        "auto_promoted": False,
        "promotion_rule": (
            "Fill output with a verified non-regressing answer, change quality "
            "to reviewed or verified, validate the dataset, and require a "
            "separate explicit training approval before any new training run."
        ),
    }
    return {
        "instruction": str(row.get("prompt") or "").strip(),
        "input": "\n".join(input_parts),
        "output": "",
        "category": category,
        "stack": stack,
        "quality": "needs_review",
        "metadata": metadata,
        "approved_for_training": False,
        "training_allowed": False,
        "safe_to_train": False,
        "auto_promoted": False,
    }


def build_regression_review(
    *,
    broad_results_path: Path | None,
    broad_prompts_path: Path | None,
    rust_results_path: Path | None,
    rust_prompts_path: Path | None,
    promotion_review_path: Path | None,
    candidate_adapter: str | None,
    stable_adapter: str | None,
    max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    max_validation_detail_chars: int = DEFAULT_MAX_VALIDATION_DETAIL_CHARS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if broad_results_path is None and rust_results_path is None:
        raise ValueError("At least one results JSONL path is required.")

    promotion_review = load_json(promotion_review_path)
    resolved_candidate_adapter = candidate_adapter or promotion_review.get("candidate_adapter")
    resolved_stable_adapter = stable_adapter or promotion_review.get("stable_adapter")

    rows: list[dict[str, Any]] = []
    if broad_results_path is not None:
        rows.extend(
            load_jsonl(
                broad_results_path,
                eval_kind="broad",
                prompt_metadata=load_prompt_metadata(broad_prompts_path),
            )
        )
    if rust_results_path is not None:
        rows.extend(
            load_jsonl(
                rust_results_path,
                eval_kind="rust_xriq",
                prompt_metadata=load_prompt_metadata(rust_prompts_path),
            )
        )

    items = [
        summarize_regression(
            row,
            max_content_chars=max_content_chars,
            max_validation_detail_chars=max_validation_detail_chars,
        )
        for row in rows
        if is_regression_row(row)
    ]
    items.sort(key=lambda item: (str(item["eval_kind"]), str(item["id"])))

    candidates = [
        build_anti_regression_candidate(
            item,
            candidate_adapter=str(resolved_candidate_adapter) if resolved_candidate_adapter else None,
            stable_adapter=str(resolved_stable_adapter) if resolved_stable_adapter else None,
            promotion_review=str(promotion_review_path) if promotion_review_path else None,
        )
        for item in items
        if item["eligible_for_anti_regression_candidate"]
    ]

    serializable_items = [
        {key: value for key, value in item.items() if key != "row"} for item in items
    ]
    review = {
        "command": "biber-repo-adaptation-regression-review",
        "generated_at": datetime.now(UTC).isoformat(),
        "broad_results": str(broad_results_path) if broad_results_path else None,
        "rust_results": str(rust_results_path) if rust_results_path else None,
        "promotion_review": str(promotion_review_path) if promotion_review_path else None,
        "candidate_adapter": resolved_candidate_adapter,
        "stable_adapter": resolved_stable_adapter,
        "promotion_hard_blockers": promotion_review.get("hard_blockers", []),
        "results_seen": len(rows),
        "regression_rows": len(items),
        "anti_regression_candidates": len(candidates),
        "runtime_blocked_rows": sum(
            1 for item in items if "runtime_or_api_error" in item["blocked_reasons"]
        ),
        "secret_blocked_rows": sum(
            1 for item in items if "secret_like_text" in item["blocked_reasons"]
        ),
        "broad_regressions": sum(1 for item in items if item["eval_kind"] == "broad"),
        "rust_xriq_regressions": sum(
            1 for item in items if item["eval_kind"] == "rust_xriq"
        ),
        "validator_regressions": sum(
            1 for item in items if "validator_regression" in item["issue_types"]
        ),
        "training_dataset_ready": False,
        "training_allowed": False,
        "safe_to_train": False,
        "approved_for_training": False,
        "auto_promoted": False,
        "items": serializable_items,
        "next_review_action": (
            "fill_anti_regression_candidate_outputs_then_run_candidate_review"
            if candidates
            else "inspect_candidate_eval_failures_before_collecting_training_rows"
        ),
    }
    return review, candidates


def run_regression_review(
    *,
    broad_results_path: Path | None,
    broad_prompts_path: Path | None,
    rust_results_path: Path | None,
    rust_prompts_path: Path | None,
    promotion_review_path: Path | None,
    review_output: Path,
    anti_regression_candidates_output: Path | None,
    candidate_adapter: str | None,
    stable_adapter: str | None,
    max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    max_validation_detail_chars: int = DEFAULT_MAX_VALIDATION_DETAIL_CHARS,
) -> dict[str, Any]:
    review, candidates = build_regression_review(
        broad_results_path=broad_results_path,
        broad_prompts_path=broad_prompts_path,
        rust_results_path=rust_results_path,
        rust_prompts_path=rust_prompts_path,
        promotion_review_path=promotion_review_path,
        candidate_adapter=candidate_adapter,
        stable_adapter=stable_adapter,
        max_content_chars=max_content_chars,
        max_validation_detail_chars=max_validation_detail_chars,
    )
    if anti_regression_candidates_output is not None:
        write_jsonl(anti_regression_candidates_output, candidates)
        review["anti_regression_candidates_output"] = str(anti_regression_candidates_output)
    else:
        review["anti_regression_candidates_output"] = None

    review_output.parent.mkdir(parents=True, exist_ok=True)
    review_output.write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return review


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review candidate adapter broad/Rust regressions and export "
            "human-review-only anti-regression candidates."
        )
    )
    parser.add_argument("--broad-results", type=Path)
    parser.add_argument("--broad-prompts", type=Path, default=Path("training/eval_prompts.jsonl"))
    parser.add_argument("--rust-results", type=Path)
    parser.add_argument(
        "--rust-prompts",
        type=Path,
        default=Path("training/eval_prompts_rust_xriq.jsonl"),
    )
    parser.add_argument("--promotion-review", type=Path)
    parser.add_argument("--candidate-adapter")
    parser.add_argument("--stable-adapter")
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--anti-regression-candidates-output", type=Path)
    parser.add_argument("--max-content-chars", type=int, default=DEFAULT_MAX_CONTENT_CHARS)
    parser.add_argument(
        "--max-validation-detail-chars",
        type=int,
        default=DEFAULT_MAX_VALIDATION_DETAIL_CHARS,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    review = run_regression_review(
        broad_results_path=args.broad_results,
        broad_prompts_path=args.broad_prompts,
        rust_results_path=args.rust_results,
        rust_prompts_path=args.rust_prompts,
        promotion_review_path=args.promotion_review,
        review_output=args.review_output,
        anti_regression_candidates_output=args.anti_regression_candidates_output,
        candidate_adapter=args.candidate_adapter,
        stable_adapter=args.stable_adapter,
        max_content_chars=args.max_content_chars,
        max_validation_detail_chars=args.max_validation_detail_chars,
    )
    print(
        "Repo adaptation regression review complete: "
        f"{review['regression_rows']} regressions, "
        f"{review['anti_regression_candidates']} anti-regression candidates."
    )
    print(f"Review: {args.review_output}")
    if args.anti_regression_candidates_output:
        print(f"Anti-regression candidates: {args.anti_regression_candidates_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
