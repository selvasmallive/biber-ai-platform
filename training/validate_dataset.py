from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.dataset_utils import format_training_text, load_jsonl, validate_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a BIBER JSONL training dataset.")
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--min-records", type=int, default=1)
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--print-sample", action="store_true")
    args = parser.parse_args()

    result = validate_dataset(
        args.dataset,
        min_records=args.min_records,
        max_records=args.max_records,
    )

    print(f"Dataset: {result.path}")
    print(f"Records: {result.records}")
    print(f"Errors:  {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")
    if result.categories:
        print(f"Categories: {dict(result.categories)}")
    if result.qualities:
        print(f"Qualities:  {dict(result.qualities)}")

    for issue in [*result.errors, *result.warnings]:
        print(f"{issue.level.upper()} line {issue.line_number}: {issue.message}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result.as_dict(), indent=2), encoding="utf-8")
        print(f"Report: {args.report}")

    if args.print_sample and result.ok and result.records:
        sample = load_jsonl(args.dataset)[0]
        print()
        print("Formatted sample:")
        print(format_training_text(sample))

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
