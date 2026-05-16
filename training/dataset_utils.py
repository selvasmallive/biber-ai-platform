from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ("instruction", "output")
OPTIONAL_FIELDS = ("input", "category", "stack", "quality")
KNOWN_QUALITIES = {"verified", "reviewed", "synthetic", "draft"}
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[^'\"\s]{12,}"),
)


@dataclass(frozen=True)
class DatasetIssue:
    line_number: int
    level: str
    message: str


@dataclass
class DatasetValidationResult:
    path: Path
    records: int = 0
    errors: list[DatasetIssue] = field(default_factory=list)
    warnings: list[DatasetIssue] = field(default_factory=list)
    categories: Counter[str] = field(default_factory=Counter)
    qualities: Counter[str] = field(default_factory=Counter)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_issue(self, issue: DatasetIssue) -> None:
        if issue.level == "error":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "records": self.records,
            "ok": self.ok,
            "errors": [issue.__dict__ for issue in self.errors],
            "warnings": [issue.__dict__ for issue in self.warnings],
            "categories": dict(self.categories),
            "qualities": dict(self.qualities),
        }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"Line {line_number}: expected a JSON object.")
            records.append(value)
    return records


def validate_dataset(
    path: Path,
    *,
    min_records: int = 1,
    max_records: int | None = None,
) -> DatasetValidationResult:
    result = DatasetValidationResult(path=path)
    if not path.exists():
        result.add_issue(DatasetIssue(0, "error", f"Dataset not found: {path}"))
        return result

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            if max_records is not None and result.records >= max_records:
                break
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                result.add_issue(DatasetIssue(line_number, "error", f"Invalid JSON: {exc}"))
                continue
            result.records += 1
            if not isinstance(record, dict):
                result.add_issue(
                    DatasetIssue(line_number, "error", "Record must be a JSON object.")
                )
                continue
            for issue in validate_record(record, line_number):
                result.add_issue(issue)
            category = str(record.get("category") or "uncategorized").strip() or "uncategorized"
            quality = str(record.get("quality") or "unspecified").strip() or "unspecified"
            result.categories[category] += 1
            result.qualities[quality] += 1

    if result.records < min_records:
        result.add_issue(
            DatasetIssue(
                0,
                "error",
                f"Dataset has {result.records} records; expected at least {min_records}.",
            )
        )
    return result


def validate_record(record: dict[str, Any], line_number: int) -> list[DatasetIssue]:
    issues: list[DatasetIssue] = []
    for field_name in REQUIRED_FIELDS:
        value = record.get(field_name)
        if not isinstance(value, str) or not value.strip():
            issues.append(DatasetIssue(line_number, "error", f"Missing non-empty {field_name!r}."))

    input_value = record.get("input", "")
    if input_value is not None and not isinstance(input_value, str):
        issues.append(DatasetIssue(line_number, "error", "'input' must be a string when provided."))

    stack = record.get("stack", [])
    if stack is not None and (
        not isinstance(stack, list) or any(not isinstance(item, str) for item in stack)
    ):
        issues.append(DatasetIssue(line_number, "error", "'stack' must be a list of strings."))

    quality = record.get("quality")
    if quality is not None and quality not in KNOWN_QUALITIES:
        issues.append(
            DatasetIssue(
                line_number,
                "warning",
                f"Unknown quality {quality!r}; expected one of {sorted(KNOWN_QUALITIES)}.",
            )
        )

    text = "\n".join(
        str(record.get(field_name, "")) for field_name in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS)
    )
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            issues.append(DatasetIssue(line_number, "error", "Possible secret detected."))
            break

    return issues


def format_training_text(record: dict[str, Any], eos_token: str | None = None) -> str:
    instruction = str(record.get("instruction", "")).strip()
    input_text = str(record.get("input", "") or "").strip()
    output = str(record.get("output", "")).strip()
    sections = [f"### Instruction:\n{instruction}"]
    if input_text:
        sections.append(f"### Input:\n{input_text}")
    sections.append(f"### Response:\n{output}")
    text = "\n\n".join(sections)
    if eos_token:
        text += eos_token
    return text
