from __future__ import annotations

import json
from pathlib import Path

from training.adapter_promotion_review import main, review_adapter_promotion


def write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def summary(
    *,
    prompts: int,
    ok: int,
    expectation_ok: int,
    validation_ok: int | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "prompts": prompts,
        "ok": ok,
        "failed": prompts - ok,
        "expectation_ok": expectation_ok,
        "expectation_failed": prompts - expectation_ok,
    }
    if validation_ok is not None:
        row["validation_prompts"] = prompts
        row["validation_ok"] = validation_ok
        row["validation_failed"] = prompts - validation_ok
    return row


def training_review() -> dict[str, object]:
    return {
        "review_status": "ready_for_user_training_approval",
        "ready_for_user_training_approval": True,
        "requires_explicit_user_training_approval": True,
    }


def make_adapter(path: Path) -> None:
    path.mkdir()
    (path / "adapter_config.json").write_text("{}", encoding="utf-8")


def test_adapter_promotion_review_marks_candidate_ready_without_promoting(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    make_adapter(candidate)
    stable = tmp_path / "stable"
    make_adapter(stable)
    training_review_path = tmp_path / "training-review.json"
    broad_summary = tmp_path / "broad.summary.json"
    rust_summary = tmp_path / "rust.summary.json"
    repo_summary = tmp_path / "repo-candidate.summary.json"
    baseline_repo_summary = tmp_path / "repo-baseline.summary.json"
    write_json(training_review_path, training_review())
    write_json(broad_summary, summary(prompts=18, ok=18, expectation_ok=18))
    write_json(
        rust_summary,
        summary(prompts=7, ok=7, expectation_ok=7, validation_ok=7),
    )
    write_json(repo_summary, summary(prompts=10, ok=10, expectation_ok=8))
    write_json(baseline_repo_summary, summary(prompts=10, ok=10, expectation_ok=7))

    review = review_adapter_promotion(
        candidate_adapter=candidate,
        stable_adapter=stable,
        training_review_path=training_review_path,
        broad_summary_path=broad_summary,
        rust_summary_path=rust_summary,
        repo_summary_path=repo_summary,
        baseline_repo_summary_path=baseline_repo_summary,
        min_broad_expectation_ok=18,
        min_rust_expectation_ok=7,
        min_rust_validation_ok=7,
        min_repo_expectation_ok=1,
        require_adapter_exists=True,
    )

    assert review["review_status"] == "ready_for_user_promotion_approval"
    assert review["hard_blockers"] == []
    assert review["ready_for_user_promotion_approval"] is True
    assert review["requires_explicit_user_promotion_approval"] is True
    assert review["promotion_allowed"] is False
    assert review["safe_to_promote"] is False
    assert review["auto_promoted"] is False
    assert review["serving_changed"] is False


def test_adapter_promotion_review_blocks_regressions_and_missing_repo_baseline(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "candidate"
    make_adapter(candidate)
    training_review_path = tmp_path / "training-review.json"
    broad_summary = tmp_path / "broad.summary.json"
    rust_summary = tmp_path / "rust.summary.json"
    repo_summary = tmp_path / "repo-candidate.summary.json"
    write_json(training_review_path, training_review())
    write_json(broad_summary, summary(prompts=18, ok=18, expectation_ok=17))
    write_json(
        rust_summary,
        summary(prompts=7, ok=7, expectation_ok=7, validation_ok=6),
    )
    write_json(repo_summary, summary(prompts=10, ok=10, expectation_ok=7))

    review = review_adapter_promotion(
        candidate_adapter=candidate,
        stable_adapter=tmp_path / "stable",
        training_review_path=training_review_path,
        broad_summary_path=broad_summary,
        rust_summary_path=rust_summary,
        repo_summary_path=repo_summary,
        baseline_repo_summary_path=None,
        min_broad_expectation_ok=18,
        min_rust_expectation_ok=7,
        min_rust_validation_ok=7,
        min_repo_expectation_ok=1,
        require_adapter_exists=True,
    )

    assert review["review_status"] == "promotion_blocked"
    assert "broad_expectations_below_threshold" in review["hard_blockers"]
    assert "rust_validators_below_threshold" in review["hard_blockers"]
    assert "baseline_repo_summary_missing_or_unreadable" in review["hard_blockers"]
    assert "repo_eval_did_not_improve_baseline" in review["hard_blockers"]
    assert review["auto_promoted"] is False


def test_adapter_promotion_review_blocks_same_candidate_and_stable_adapter(
    tmp_path: Path,
) -> None:
    candidate = tmp_path / "same-adapter"
    make_adapter(candidate)
    training_review_path = tmp_path / "training-review.json"
    broad_summary = tmp_path / "broad.summary.json"
    rust_summary = tmp_path / "rust.summary.json"
    repo_summary = tmp_path / "repo-candidate.summary.json"
    baseline_repo_summary = tmp_path / "repo-baseline.summary.json"
    write_json(training_review_path, training_review())
    write_json(broad_summary, summary(prompts=18, ok=18, expectation_ok=18))
    write_json(
        rust_summary,
        summary(prompts=7, ok=7, expectation_ok=7, validation_ok=7),
    )
    write_json(repo_summary, summary(prompts=10, ok=10, expectation_ok=8))
    write_json(baseline_repo_summary, summary(prompts=10, ok=10, expectation_ok=7))

    review = review_adapter_promotion(
        candidate_adapter=candidate,
        stable_adapter=candidate,
        training_review_path=training_review_path,
        broad_summary_path=broad_summary,
        rust_summary_path=rust_summary,
        repo_summary_path=repo_summary,
        baseline_repo_summary_path=baseline_repo_summary,
        min_broad_expectation_ok=18,
        min_rust_expectation_ok=7,
        min_rust_validation_ok=7,
        min_repo_expectation_ok=1,
        require_adapter_exists=True,
    )

    assert review["review_status"] == "promotion_blocked"
    assert "candidate_adapter_matches_stable" in review["hard_blockers"]
    assert review["promotion_allowed"] is False
    assert review["serving_changed"] is False


def test_main_writes_adapter_promotion_review(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    make_adapter(candidate)
    training_review_path = tmp_path / "training-review.json"
    broad_summary = tmp_path / "broad.summary.json"
    rust_summary = tmp_path / "rust.summary.json"
    repo_summary = tmp_path / "repo-candidate.summary.json"
    baseline_repo_summary = tmp_path / "repo-baseline.summary.json"
    output = tmp_path / "promotion-review.json"
    write_json(training_review_path, training_review())
    write_json(broad_summary, summary(prompts=18, ok=18, expectation_ok=18))
    write_json(
        rust_summary,
        summary(prompts=7, ok=7, expectation_ok=7, validation_ok=7),
    )
    write_json(repo_summary, summary(prompts=10, ok=10, expectation_ok=8))
    write_json(baseline_repo_summary, summary(prompts=10, ok=10, expectation_ok=7))

    exit_code = main(
        [
            "--candidate-adapter",
            str(candidate),
            "--training-review",
            str(training_review_path),
            "--broad-summary",
            str(broad_summary),
            "--rust-summary",
            str(rust_summary),
            "--repo-summary",
            str(repo_summary),
            "--baseline-repo-summary",
            str(baseline_repo_summary),
            "--review-output",
            str(output),
        ]
    )
    saved = json.loads(output.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert saved["review_status"] == "ready_for_user_promotion_approval"
