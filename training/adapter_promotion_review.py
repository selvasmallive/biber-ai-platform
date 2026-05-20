from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DEFAULT_STABLE_ADAPTER = "/workspace/adapters/biber-dev-core-lora-rust-xriq-400"


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"JSON file not found: {path}"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, f"Expected a JSON object in {path}"
    return value, None


def int_value(summary: dict[str, Any] | None, key: str) -> int | None:
    if summary is None:
        return None
    value = summary.get(key)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def gate(
    *,
    name: str,
    ok: bool,
    blocker: str,
    actual: Any = None,
    required: Any = None,
    summary: Path | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "ok": ok,
        "blocker": None if ok else blocker,
    }
    if actual is not None:
        result["actual"] = actual
    if required is not None:
        result["required"] = required
    if summary is not None:
        result["summary"] = str(summary)
    if details:
        result["details"] = details
    return result


def threshold_gate(
    *,
    name: str,
    summary: dict[str, Any] | None,
    summary_path: Path,
    field: str,
    minimum: int,
    blocker: str,
) -> dict[str, Any]:
    actual = int_value(summary, field)
    return gate(
        name=name,
        ok=actual is not None and actual >= minimum,
        blocker=blocker,
        actual=actual,
        required={field: minimum},
        summary=summary_path,
    )


def zero_failed_gate(
    *,
    name: str,
    summary: dict[str, Any] | None,
    summary_path: Path,
    blocker: str,
) -> dict[str, Any]:
    failed = int_value(summary, "failed")
    return gate(
        name=name,
        ok=failed == 0,
        blocker=blocker,
        actual={"failed": failed},
        required={"failed": 0},
        summary=summary_path,
    )


def review_adapter_promotion(
    *,
    candidate_adapter: Path,
    stable_adapter: Path,
    training_review_path: Path,
    broad_summary_path: Path,
    rust_summary_path: Path,
    repo_summary_path: Path | None,
    baseline_repo_summary_path: Path | None,
    min_broad_expectation_ok: int,
    min_rust_expectation_ok: int,
    min_rust_validation_ok: int,
    min_repo_expectation_ok: int,
    min_repo_improvement_delta: int,
    require_adapter_exists: bool,
) -> dict[str, Any]:
    if min_repo_improvement_delta < 1:
        raise ValueError("min_repo_improvement_delta must be at least 1.")

    generated_at = datetime.now(UTC).isoformat()
    training_review, training_review_error = load_json(training_review_path)
    broad_summary, broad_error = load_json(broad_summary_path)
    rust_summary, rust_error = load_json(rust_summary_path)
    repo_summary, repo_error = (
        load_json(repo_summary_path) if repo_summary_path is not None else (None, "missing repo summary")
    )
    baseline_repo_summary, baseline_repo_error = (
        load_json(baseline_repo_summary_path)
        if baseline_repo_summary_path is not None
        else (None, "missing baseline repo summary")
    )

    gates: list[dict[str, Any]] = []

    candidate_resolved = candidate_adapter.resolve(strict=False)
    stable_resolved = stable_adapter.resolve(strict=False)
    gates.append(
        gate(
            name="candidate_differs_from_stable",
            ok=candidate_resolved != stable_resolved,
            blocker="candidate_adapter_matches_stable",
            actual={
                "candidate_adapter": str(candidate_resolved),
                "stable_adapter": str(stable_resolved),
            },
            required={"candidate_adapter": "different_from_stable_adapter"},
        )
    )

    adapter_exists = candidate_adapter.is_dir()
    adapter_config_exists = (candidate_adapter / "adapter_config.json").is_file()
    gates.append(
        gate(
            name="candidate_adapter_artifact",
            ok=(not require_adapter_exists) or (adapter_exists and adapter_config_exists),
            blocker="candidate_adapter_missing_or_incomplete",
            actual={
                "exists": adapter_exists,
                "adapter_config_exists": adapter_config_exists,
            },
            required=(
                {"exists": True, "adapter_config_exists": True}
                if require_adapter_exists
                else {"exists": "not_required"}
            ),
        )
    )

    training_review_ready = (
        training_review is not None
        and training_review.get("review_status") == "ready_for_user_training_approval"
        and training_review.get("ready_for_user_training_approval") is True
        and training_review.get("requires_explicit_user_training_approval") is True
    )
    gates.append(
        gate(
            name="training_review_provenance",
            ok=training_review_ready,
            blocker="training_review_not_ready",
            actual={
                "load_error": training_review_error,
                "review_status": training_review.get("review_status") if training_review else None,
                "ready_for_user_training_approval": (
                    training_review.get("ready_for_user_training_approval")
                    if training_review
                    else None
                ),
            },
            required={
                "review_status": "ready_for_user_training_approval",
                "ready_for_user_training_approval": True,
                "requires_explicit_user_training_approval": True,
            },
            summary=training_review_path,
        )
    )

    gates.append(
        gate(
            name="broad_summary_load",
            ok=broad_error is None,
            blocker="broad_summary_missing_or_unreadable",
            actual={"load_error": broad_error},
            summary=broad_summary_path,
        )
    )
    gates.append(
        gate(
            name="rust_summary_load",
            ok=rust_error is None,
            blocker="rust_summary_missing_or_unreadable",
            actual={"load_error": rust_error},
            summary=rust_summary_path,
        )
    )
    gates.append(
        gate(
            name="repo_summary_load",
            ok=repo_error is None,
            blocker="repo_summary_missing_or_unreadable",
            actual={"load_error": repo_error},
            summary=repo_summary_path,
        )
    )
    gates.append(
        gate(
            name="baseline_repo_summary_load",
            ok=baseline_repo_error is None,
            blocker="baseline_repo_summary_missing_or_unreadable",
            actual={"load_error": baseline_repo_error},
            summary=baseline_repo_summary_path,
        )
    )

    gates.append(
        zero_failed_gate(
            name="broad_runtime_success",
            summary=broad_summary,
            summary_path=broad_summary_path,
            blocker="broad_eval_runtime_failures",
        )
    )
    gates.append(
        threshold_gate(
            name="broad_expectations",
            summary=broad_summary,
            summary_path=broad_summary_path,
            field="expectation_ok",
            minimum=min_broad_expectation_ok,
            blocker="broad_expectations_below_threshold",
        )
    )
    gates.append(
        zero_failed_gate(
            name="rust_runtime_success",
            summary=rust_summary,
            summary_path=rust_summary_path,
            blocker="rust_eval_runtime_failures",
        )
    )
    gates.append(
        threshold_gate(
            name="rust_expectations",
            summary=rust_summary,
            summary_path=rust_summary_path,
            field="expectation_ok",
            minimum=min_rust_expectation_ok,
            blocker="rust_expectations_below_threshold",
        )
    )
    gates.append(
        threshold_gate(
            name="rust_validators",
            summary=rust_summary,
            summary_path=rust_summary_path,
            field="validation_ok",
            minimum=min_rust_validation_ok,
            blocker="rust_validators_below_threshold",
        )
    )
    if repo_summary_path is not None:
        gates.append(
            zero_failed_gate(
                name="repo_runtime_success",
                summary=repo_summary,
                summary_path=repo_summary_path,
                blocker="repo_eval_runtime_failures",
            )
        )
        gates.append(
            threshold_gate(
                name="repo_expectations",
                summary=repo_summary,
                summary_path=repo_summary_path,
                field="expectation_ok",
                minimum=min_repo_expectation_ok,
                blocker="repo_expectations_below_threshold",
            )
        )

    candidate_repo_score = int_value(repo_summary, "expectation_ok")
    baseline_repo_score = int_value(baseline_repo_summary, "expectation_ok")
    required_repo_score = (
        baseline_repo_score + min_repo_improvement_delta
        if baseline_repo_score is not None
        else None
    )
    gates.append(
        gate(
            name="repo_baseline_improvement",
            ok=(
                candidate_repo_score is not None
                and required_repo_score is not None
                and candidate_repo_score >= required_repo_score
            ),
            blocker="repo_eval_improvement_below_margin",
            actual={
                "candidate_expectation_ok": candidate_repo_score,
                "baseline_expectation_ok": baseline_repo_score,
                "delta": (
                    candidate_repo_score - baseline_repo_score
                    if candidate_repo_score is not None and baseline_repo_score is not None
                    else None
                ),
            },
            required={
                "candidate_expectation_ok": "baseline_plus_min_delta",
                "min_repo_improvement_delta": min_repo_improvement_delta,
                "required_candidate_expectation_ok": required_repo_score,
            },
            summary=repo_summary_path,
        )
    )

    hard_blockers = [
        str(item["blocker"]) for item in gates if item.get("blocker")
    ]
    ready = not hard_blockers
    return {
        "source": "biber_adapter_promotion_review",
        "command": "biber-adapter-promotion-review",
        "generated_at": generated_at,
        "review_status": (
            "ready_for_user_promotion_approval" if ready else "promotion_blocked"
        ),
        "candidate_adapter": str(candidate_adapter),
        "stable_adapter": str(stable_adapter),
        "training_review": str(training_review_path),
        "broad_summary": str(broad_summary_path),
        "rust_summary": str(rust_summary_path),
        "repo_summary": str(repo_summary_path) if repo_summary_path else None,
        "baseline_repo_summary": (
            str(baseline_repo_summary_path) if baseline_repo_summary_path else None
        ),
        "gates": gates,
        "hard_blockers": hard_blockers,
        "ready_for_user_promotion_approval": ready,
        "requires_explicit_user_promotion_approval": True,
        "promotion_allowed": False,
        "safe_to_promote": False,
        "auto_promoted": False,
        "serving_changed": False,
        "suggested_commands": {
            "promote_after_explicit_approval": (
                f"BIBER_LORA_ADAPTER_DIR={candidate_adapter} "
                "bash scripts/vast_start_lora_direct.sh"
            ),
            "restore_stable_adapter": (
                f"BIBER_LORA_ADAPTER_DIR={stable_adapter} "
                "bash scripts/vast_start_lora_direct.sh"
            ),
            "verify_serving": "bash scripts/vast_test_direct.sh",
        },
        "next_review_action": (
            "ask_user_for_explicit_promotion_approval"
            if ready
            else "fix_blockers_or_restore_stable_adapter"
        ),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review a candidate BIBER adapter against promotion gates without "
            "changing serving."
        )
    )
    parser.add_argument("--candidate-adapter", type=Path, required=True)
    parser.add_argument(
        "--stable-adapter",
        type=Path,
        default=Path(DEFAULT_STABLE_ADAPTER),
    )
    parser.add_argument("--training-review", type=Path, required=True)
    parser.add_argument("--broad-summary", type=Path, required=True)
    parser.add_argument("--rust-summary", type=Path, required=True)
    parser.add_argument("--repo-summary", type=Path)
    parser.add_argument("--baseline-repo-summary", type=Path)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--min-broad-expectation-ok", type=int, default=18)
    parser.add_argument("--min-rust-expectation-ok", type=int, default=7)
    parser.add_argument("--min-rust-validation-ok", type=int, default=7)
    parser.add_argument("--min-repo-expectation-ok", type=int, default=1)
    parser.add_argument("--min-repo-improvement-delta", type=int, default=5)
    parser.add_argument(
        "--skip-adapter-exists-check",
        action="store_true",
        help="Use only for tests or preflight planning before the adapter exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    review = review_adapter_promotion(
        candidate_adapter=args.candidate_adapter,
        stable_adapter=args.stable_adapter,
        training_review_path=args.training_review,
        broad_summary_path=args.broad_summary,
        rust_summary_path=args.rust_summary,
        repo_summary_path=args.repo_summary,
        baseline_repo_summary_path=args.baseline_repo_summary,
        min_broad_expectation_ok=args.min_broad_expectation_ok,
        min_rust_expectation_ok=args.min_rust_expectation_ok,
        min_rust_validation_ok=args.min_rust_validation_ok,
        min_repo_expectation_ok=args.min_repo_expectation_ok,
        min_repo_improvement_delta=args.min_repo_improvement_delta,
        require_adapter_exists=not args.skip_adapter_exists_check,
    )
    args.review_output.parent.mkdir(parents=True, exist_ok=True)
    args.review_output.write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "Adapter promotion review: "
        f"{review['review_status']}; blockers={len(review['hard_blockers'])}."
    )
    print(f"Review: {args.review_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
