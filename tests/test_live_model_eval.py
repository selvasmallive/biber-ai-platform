from __future__ import annotations

import json
from pathlib import Path

from training.live_model_eval import (
    EvalPrompt,
    apply_prompt_prefix,
    build_rust_eval_project,
    build_chat_payload,
    extract_code_for_language,
    load_prompt_prefix,
    load_eval_prompts,
    read_env_file_value,
    run_code_validators,
    score_expectations,
)


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def test_load_eval_prompts_accepts_valid_records(tmp_path: Path) -> None:
    prompts = tmp_path / "eval.jsonl"
    write_jsonl(
        prompts,
        [
            {
                "id": "python_add",
                "prompt": "Write add(a, b).",
                "language": "Python",
                "expect_contains": ["def add"],
                "validators": ["rust:cargo_check"],
                "rust_tests": "#[cfg(test)] mod tests {}",
            }
        ],
    )

    loaded = load_eval_prompts(prompts)

    assert loaded[0].id == "python_add"
    assert loaded[0].language == "Python"
    assert loaded[0].expect_contains == ("def add",)
    assert loaded[0].validators == ("rust:cargo_check",)
    assert loaded[0].rust_tests == "#[cfg(test)] mod tests {}"


def test_score_expectations_is_case_insensitive() -> None:
    matched, missing = score_expectations("DEF add(a, b):\n    return a + b", ("def add", "pytest"))

    assert matched == ("def add",)
    assert missing == ("pytest",)


def test_build_chat_payload_disables_mentor() -> None:
    prompt = load_eval_prompts(Path("training/eval_prompts.jsonl"))[0]

    payload = build_chat_payload(prompt)

    assert payload["use_mentor"] is False
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == prompt.prompt


def test_apply_prompt_prefix_prepends_profile_to_prompt() -> None:
    prompt = EvalPrompt(id="rust_eval", prompt="Return only Rust code.")

    updated = apply_prompt_prefix(prompt, "Use rustfmt-clean output.")

    assert updated.id == prompt.id
    assert updated.prompt == "Use rustfmt-clean output.\n\nTask:\nReturn only Rust code."


def test_load_prompt_prefix_reads_trimmed_text(tmp_path: Path) -> None:
    prefix = tmp_path / "prefix.txt"
    prefix.write_text("  Use cargo fmt clean output.  \n", encoding="utf-8")

    assert load_prompt_prefix(prefix) == "Use cargo fmt clean output."


def test_main_applies_prompt_prefix_only_to_selected_ids(
    monkeypatch,
    tmp_path: Path,
) -> None:
    prompts = tmp_path / "prompts.jsonl"
    output = tmp_path / "results.jsonl"
    summary = tmp_path / "summary.json"
    prefix = tmp_path / "prefix.txt"
    prefix.write_text("Use rustfmt-clean output.", encoding="utf-8")
    write_jsonl(
        prompts,
        [
            {"id": "plain", "prompt": "Plain prompt."},
            {"id": "ledger", "prompt": "Ledger prompt."},
        ],
    )
    captured_prompts: list[str] = []

    def fake_post_chat(*args, **kwargs):
        prompt = args[2]
        captured_prompts.append(prompt.prompt)
        return EvalPrompt(
            id=prompt.id,
            prompt=prompt.prompt,
        )

    from training import live_model_eval

    def fake_post_chat_result(
        base_url,
        api_key,
        prompt,
        timeout_seconds,
        run_validators,
        validator_work_dir,
        validator_timeout_seconds,
    ):
        captured_prompts.append(prompt.prompt)
        return live_model_eval.EvalResult(
            id=prompt.id,
            ok=True,
            expectation_ok=True,
            validation_ok=None,
            validation_skipped=False,
            model="test",
            latency_seconds=0.0,
            content="ok",
            matched_expectations=(),
            missing_expectations=(),
        )

    monkeypatch.setattr(live_model_eval, "post_chat", fake_post_chat_result)

    assert live_model_eval.main(
        [
            "--prompts",
            str(prompts),
            "--output",
            str(output),
            "--summary",
            str(summary),
            "--prompt-prefix-file",
            str(prefix),
            "--prompt-prefix-id",
            "ledger",
        ]
    ) == 0

    assert captured_prompts == [
        "Plain prompt.",
        "Use rustfmt-clean output.\n\nTask:\nLedger prompt.",
    ]


def test_read_env_file_value_handles_quoted_values(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('BIBER_DEMO_API_KEY="quoted-key"\nOTHER=value\n', encoding="utf-8")

    assert read_env_file_value(env_file, "BIBER_DEMO_API_KEY") == "quoted-key"


def test_extract_code_for_language_prefers_matching_fence() -> None:
    content = """Here is code:

```python
print("wrong")
```

```rust
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
```
"""

    extracted = extract_code_for_language(content, "Rust")

    assert "pub fn add" in extracted
    assert "print" not in extracted


def test_extract_code_for_language_ignores_doc_comment_fences() -> None:
    content = """/// Example:
/// ```
/// let value = 1;
/// ```
pub fn value() -> u64 {
    1
}
"""

    extracted = extract_code_for_language(content, "Rust")

    assert "pub fn value" in extracted
    assert "let value = 1" in extracted


def test_build_rust_eval_project_writes_cargo_project(tmp_path: Path) -> None:
    prompt = EvalPrompt(
        id="rust_add",
        prompt="Write add.",
        language="Rust",
        rust_tests="#[cfg(test)] mod biber_eval_tests {}",
    )

    build_rust_eval_project(
        tmp_path,
        prompt,
        "pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}",
    )

    assert "[package]" in (tmp_path / "Cargo.toml").read_text(encoding="utf-8")
    lib_rs = (tmp_path / "src" / "lib.rs").read_text(encoding="utf-8")
    assert "pub fn add" in lib_rs
    assert "biber_eval_tests" in lib_rs


def test_run_code_validators_rejects_unknown_validator() -> None:
    prompt = EvalPrompt(
        id="rust_add",
        prompt="Write add.",
        language="Rust",
        validators=("rust:unknown",),
    )

    outcome = run_code_validators("pub fn add() {}", prompt, work_dir=None, timeout_seconds=1)

    assert outcome.ok is False
    assert outcome.skipped is False
    assert outcome.errors == ("Unsupported validator: rust:unknown",)
