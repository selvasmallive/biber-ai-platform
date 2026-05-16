from __future__ import annotations

import json
from pathlib import Path

from training.live_model_eval import (
    build_chat_payload,
    load_eval_prompts,
    read_env_file_value,
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
            }
        ],
    )

    loaded = load_eval_prompts(prompts)

    assert loaded[0].id == "python_add"
    assert loaded[0].language == "Python"
    assert loaded[0].expect_contains == ("def add",)


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
