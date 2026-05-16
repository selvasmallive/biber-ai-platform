from __future__ import annotations

import json
from pathlib import Path

from training.dataset_utils import format_training_text, validate_dataset


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def test_validate_dataset_accepts_valid_records(tmp_path: Path) -> None:
    dataset = tmp_path / "train.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "instruction": "Fix this bug.",
                "input": "def add(a, b): return a - b",
                "output": "def add(a, b): return a + b",
                "category": "python",
                "stack": ["python"],
                "quality": "verified",
            }
        ],
    )

    result = validate_dataset(dataset)

    assert result.ok
    assert result.records == 1
    assert result.categories["python"] == 1


def test_validate_dataset_rejects_missing_required_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "train.jsonl"
    write_jsonl(dataset, [{"instruction": "No output"}])

    result = validate_dataset(dataset)

    assert not result.ok
    assert "output" in result.errors[0].message


def test_validate_dataset_rejects_possible_secrets(tmp_path: Path) -> None:
    dataset = tmp_path / "train.jsonl"
    write_jsonl(
        dataset,
        [
            {
                "instruction": "Use this token.",
                "output": "token = 'ghp_123456789012345678901234567890123456'",
            }
        ],
    )

    result = validate_dataset(dataset)

    assert not result.ok
    assert "secret" in result.errors[0].message.lower()


def test_format_training_text_omits_empty_input() -> None:
    text = format_training_text({"instruction": "Say hi.", "output": "hi"})

    assert "### Instruction:" in text
    assert "### Input:" not in text
    assert "### Response:" in text
