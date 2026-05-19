from __future__ import annotations

import json
from pathlib import Path

from training.repo_adaptation_plan import build_plan, main, scan_repo


def test_scan_repo_skips_secrets_and_counts_languages(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "lib.rs").write_text(
        "pub fn add(a: u64, b: u64) -> u64 { a + b }\n",
        encoding="utf-8",
    )
    (repo / "README.md").write_text("# Example\n", encoding="utf-8")
    (repo / ".env").write_text("API_KEY=super-secret-value\n", encoding="utf-8")
    (repo / "src" / "config.rs").write_text(
        "let token = 'ghp_123456789012345678901234567890123456';\n",
        encoding="utf-8",
    )
    (repo / "target").mkdir()
    (repo / "target" / "ignored.rs").write_text("pub fn ignored() {}\n", encoding="utf-8")

    files, skipped, scanned = scan_repo(repo)

    paths = {file.path for file in files}
    assert "src/lib.rs" in paths
    assert "README.md" in paths
    assert ".env" not in paths
    assert "src/config.rs" not in paths
    assert "target/ignored.rs" not in paths
    assert skipped["denied_filename"] == 1
    assert skipped["possible_secret"] == 1
    assert skipped["denied_directory"] == 1
    assert scanned == 5


def test_build_plan_has_strategy_and_eval_prompts(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "wallet.rs").write_text(
        "pub struct Wallet;\n",
        encoding="utf-8",
    )

    plan = build_plan(repo, max_files=20, max_file_bytes=1000, max_prompts=5)

    assert plan["command"] == "biber-repo-adaptation-plan"
    assert plan["strategy"]["default"] == "repo_context_first"
    assert plan["strategy"]["codex_role"] == "mentor_reviewer_only"
    assert plan["languages"]["Rust"] == 1
    assert plan["roles"]["wallet"] == 1
    assert plan["suggested_eval_prompts"]
    prompt = plan["suggested_eval_prompts"][0]
    assert prompt["task_type"] == "repo_adaptation_eval"
    assert "src/wallet.rs" in prompt["prompt"]


def test_main_writes_plan_and_eval_jsonl(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("def handler():\n    return 'ok'\n", encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    prompts_path = tmp_path / "eval_prompts.jsonl"

    exit_code = main(
        [
            "--repo-root",
            str(repo),
            "--output",
            str(plan_path),
            "--eval-prompts-output",
            str(prompts_path),
        ]
    )

    assert exit_code == 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    prompts = [
        json.loads(line)
        for line in prompts_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert plan["included_files"] == 1
    assert prompts[0]["language"] == "Python"
