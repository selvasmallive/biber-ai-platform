from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.dataset_utils import validate_dataset, validate_record


DEFAULT_MAX_SOURCE_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_RECORD_CHARS = 20_000
MAX_SOURCE_MESSAGES = 50
USER_AGENT = "biber-ai-platform-ingest/0.1"


class IngestError(RuntimeError):
    pass


@dataclass
class SourceReport:
    name: str
    source_type: str
    license: str
    attribution: str
    status: str = "pending"
    records_seen: int = 0
    records_written: int = 0
    records_skipped: int = 0
    raw_path: str | None = None
    sha256: str | None = None
    messages: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.source_type,
            "license": self.license,
            "attribution": self.attribution,
            "status": self.status,
            "records_seen": self.records_seen,
            "records_written": self.records_written,
            "records_skipped": self.records_skipped,
            "raw_path": self.raw_path,
            "sha256": self.sha256,
            "messages": self.messages,
        }


@dataclass
class IngestReport:
    manifest: Path
    output: Path
    provenance: Path
    records_written: int = 0
    duplicate_records: int = 0
    sources: list[SourceReport] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "manifest": str(self.manifest),
            "output": str(self.output),
            "provenance": str(self.provenance),
            "records_written": self.records_written,
            "duplicate_records": self.duplicate_records,
            "sources": [source.as_dict() for source in self.sources],
        }


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise IngestError(f"Manifest must be a JSON object: {path}")
    return value


def normalize_license(value: Any) -> str:
    return str(value or "").strip().lower()


def require_source_allowed(
    source: dict[str, Any],
    *,
    allowed_licenses: set[str],
    allowed_domains: set[str],
    allow_local_sources: bool,
) -> None:
    name = str(source.get("name") or "").strip()
    if not name:
        raise IngestError("Every enabled source must have a non-empty name.")
    if source.get("approved") is not True:
        raise IngestError(f"Source {name!r} is enabled but not approved.")

    license_id = normalize_license(source.get("license"))
    if license_id not in allowed_licenses:
        raise IngestError(f"Source {name!r} has unapproved license {license_id!r}.")
    if not str(source.get("attribution") or "").strip():
        raise IngestError(f"Source {name!r} must include attribution text.")

    source_type = source.get("type")
    if source_type == "jsonl_url":
        url = str(source.get("url") or "")
        domain = urllib.parse.urlparse(url).netloc.lower()
        if domain not in allowed_domains:
            raise IngestError(f"Source {name!r} URL domain is not allowlisted: {domain}")
    elif source_type == "local_jsonl":
        if not allow_local_sources:
            raise IngestError(
                f"Source {name!r} is local_jsonl; pass --allow-local-sources for smoke tests."
            )
    else:
        raise IngestError(f"Source {name!r} has unsupported enabled type {source_type!r}.")


def stream_download(url: str, raw_path: Path, max_bytes: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    hasher = hashlib.sha256()
    total = 0
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(request, timeout=60) as response:
        with raw_path.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise IngestError(f"Source exceeded max_bytes={max_bytes}: {url}")
                hasher.update(chunk)
                handle.write(chunk)
    return hasher.hexdigest()


def iter_jsonl(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError:
                yield line_number, None
                continue
            yield line_number, value


def normalize_record(source: dict[str, Any], value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    field_map = source.get("field_map")
    if field_map is None:
        field_map = {}
    if not isinstance(field_map, dict):
        raise IngestError(f"Source {source['name']!r} field_map must be an object.")

    instruction_key = str(field_map.get("instruction", "instruction"))
    input_key = str(field_map.get("input", "input"))
    output_key = str(field_map.get("output", "output"))

    instruction = value.get(instruction_key)
    output = value.get(output_key)
    if not instruction or not output:
        return None

    input_value = value.get(input_key, "")
    record = {
        "instruction": str(instruction).strip(),
        "input": str(input_value or "").strip(),
        "output": str(output).strip(),
        "category": str(value.get("category") or source.get("category") or "internet").strip(),
        "stack": value.get("stack") or source.get("stack") or [],
        "quality": str(value.get("quality") or source.get("quality") or "reviewed").strip(),
        "source": str(source["name"]),
        "source_license": normalize_license(source.get("license")),
        "source_attribution": str(source.get("attribution") or "").strip(),
    }
    if source.get("url"):
        record["source_url"] = str(source["url"])
    return record


def record_key(record: dict[str, Any]) -> str:
    text = "\n".join(
        " ".join(str(record.get(field_name, "")).split()).lower()
        for field_name in ("instruction", "input", "output")
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_char_count(record: dict[str, Any]) -> int:
    return sum(
        len(str(record.get(field_name, "")))
        for field_name in ("instruction", "input", "output")
    )


def add_source_message(source_report: SourceReport, message: str) -> None:
    if len(source_report.messages) < MAX_SOURCE_MESSAGES:
        source_report.messages.append(message)
    elif len(source_report.messages) == MAX_SOURCE_MESSAGES:
        source_report.messages.append("Further skipped-record messages omitted.")


def source_raw_path(raw_dir: Path, source_name: str) -> Path:
    safe_name = "".join(
        char if char.isalnum() or char in ("-", "_") else "_"
        for char in source_name
    )
    return raw_dir / f"{safe_name}.jsonl"


def ingest_source(
    source: dict[str, Any],
    *,
    raw_dir: Path,
    output_handle: Any,
    seen: set[str],
    total_limit: int | None,
    report: IngestReport,
) -> None:
    name = str(source["name"])
    source_type = str(source["type"])
    source_report = SourceReport(
        name=name,
        source_type=source_type,
        license=normalize_license(source.get("license")),
        attribution=str(source.get("attribution") or ""),
    )
    report.sources.append(source_report)

    if source_type == "jsonl_url":
        raw_path = source_raw_path(raw_dir, name)
        source_report.raw_path = str(raw_path)
        max_bytes = int(source.get("max_bytes") or DEFAULT_MAX_SOURCE_BYTES)
        source_report.sha256 = stream_download(str(source["url"]), raw_path, max_bytes)
        expected_sha = str(source.get("sha256") or "").strip().lower()
        if expected_sha and source_report.sha256 != expected_sha:
            raise IngestError(f"Source {name!r} SHA-256 mismatch.")
    else:
        raw_path = Path(str(source["path"]))
        source_report.raw_path = str(raw_path)

    source_limit = source.get("max_records")
    source_limit = int(source_limit) if source_limit is not None else None
    max_record_chars = int(source.get("max_record_chars") or DEFAULT_MAX_RECORD_CHARS)

    for line_number, value in iter_jsonl(raw_path):
        if total_limit is not None and report.records_written >= total_limit:
            break
        if source_limit is not None and source_report.records_written >= source_limit:
            break

        source_report.records_seen += 1
        record = normalize_record(source, value)
        if record is None:
            source_report.records_skipped += 1
            add_source_message(source_report, f"Skipped line {line_number}: unmappable record.")
            continue

        issues = validate_record(record, line_number)
        errors = [issue for issue in issues if issue.level == "error"]
        if errors:
            source_report.records_skipped += 1
            messages = "; ".join(issue.message for issue in errors)
            add_source_message(source_report, f"Skipped line {line_number}: {messages}")
            continue

        if record_char_count(record) > max_record_chars:
            source_report.records_skipped += 1
            add_source_message(source_report, f"Skipped line {line_number}: record too large.")
            continue

        key = record_key(record)
        if key in seen:
            source_report.records_skipped += 1
            report.duplicate_records += 1
            continue
        seen.add(key)

        output_handle.write(json.dumps(record, sort_keys=True) + "\n")
        source_report.records_written += 1
        report.records_written += 1

    source_report.status = "ok"


def ingest_manifest(
    manifest_path: Path,
    output_path: Path,
    raw_dir: Path,
    provenance_path: Path,
    *,
    max_records: int | None = None,
    min_records: int = 1,
    allow_local_sources: bool = False,
) -> IngestReport:
    manifest = load_json(manifest_path)
    allowed_licenses = {normalize_license(item) for item in manifest.get("allowed_licenses", [])}
    allowed_domains = {str(item).lower() for item in manifest.get("allowed_domains", [])}
    sources = manifest.get("sources", [])
    if not isinstance(sources, list):
        raise IngestError("Manifest field 'sources' must be a list.")

    enabled_sources = [
        source for source in sources if isinstance(source, dict) and source.get("enabled")
    ]
    if not enabled_sources:
        raise IngestError("No enabled sources in manifest.")

    for source in enabled_sources:
        require_source_allowed(
            source,
            allowed_licenses=allowed_licenses,
            allowed_domains=allowed_domains,
            allow_local_sources=allow_local_sources,
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    report = IngestReport(manifest=manifest_path, output=output_path, provenance=provenance_path)
    seen: set[str] = set()

    with output_path.open("w", encoding="utf-8") as output_handle:
        for source in enabled_sources:
            ingest_source(
                source,
                raw_dir=raw_dir,
                output_handle=output_handle,
                seen=seen,
                total_limit=max_records,
                report=report,
            )
            if max_records is not None and report.records_written >= max_records:
                break

    validation = validate_dataset(output_path, min_records=min_records)
    if not validation.ok:
        messages = "; ".join(issue.message for issue in validation.errors)
        raise IngestError(f"Ingested dataset failed validation: {messages}")

    provenance_path.write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")
    return report


def workspace_path(*parts: str) -> Path:
    root = Path("/workspace") if Path("/workspace").exists() else Path.cwd()
    return root.joinpath(*parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest approved internet data for BIBER training."
    )
    parser.add_argument("--manifest", type=Path, default=Path("training/approved_sources.json"))
    parser.add_argument("--output", type=Path, default=workspace_path("data", "biber_train.jsonl"))
    parser.add_argument("--raw-dir", type=Path, default=workspace_path("data", "raw"))
    parser.add_argument(
        "--provenance",
        type=Path,
        default=workspace_path("outputs", "dataset-provenance.json"),
    )
    parser.add_argument("--max-records", type=int, default=None)
    parser.add_argument("--min-records", type=int, default=1)
    parser.add_argument("--allow-local-sources", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = ingest_manifest(
            args.manifest,
            args.output,
            args.raw_dir,
            args.provenance,
            max_records=args.max_records,
            min_records=args.min_records,
            allow_local_sources=args.allow_local_sources,
        )
    except IngestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("BIBER internet dataset ingestion complete")
    print(f"Manifest:   {args.manifest}")
    print(f"Output:     {args.output}")
    print(f"Provenance: {args.provenance}")
    print(f"Records:    {report.records_written}")
    print(f"Duplicates: {report.duplicate_records}")
    for source in report.sources:
        print(
            f"- {source.name}: "
            f"{source.records_written} written, {source.records_skipped} skipped"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
