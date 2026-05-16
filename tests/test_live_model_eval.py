from __future__ import annotations

import json
from pathlib import Path

from training.live_model_eval import (
    EvalPrompt,
    build_rust_eval_project,
    build_chat_payload,
    extract_code_for_language,
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
