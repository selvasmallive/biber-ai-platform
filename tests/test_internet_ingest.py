from __future__ import annotations

import json
from pathlib import Path

import pytest

from training.internet_ingest import IngestError, ingest_manifest


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(record) for record in records) + "\n",
        encoding="utf-8",
    )


def manifest_for(source: dict[str, object]) -> dict[str, object]:
    return {
        "version": 1,
        "allowed_licenses": ["mit", "project-owned"],
        "allowed_domains": ["example.com"],
        "sources": [source],
    }


def run_ingest(tmp_path: Path, manifest: dict[str, object]) -> list[dict[str, object]]:
    manifest_path = tmp_path / "manifest.json"
    output_path = tmp_path / "train.jsonl"
    provenance_path = tmp_path / "provenance.json"
    write_json(manifest_path, manifest)

    ingest_manifest(
        manifest_path,
        output_path,
        tmp_path / "raw",
        provenance_path,
        allow_local_sources=True,
    )

    return [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]


def test_ingest_local_approved_source(tmp_path: Path) -> None:
    source_path = tmp_path / "source.jsonl"
    write_jsonl(
        source_path,
        [
            {
                "instruction": "Fix this function.",
                "input": "def add(a, b): return a - b",
                "output": "def add(a, b): return a + b",
            }
        ],
    )

    records = run_ingest(
        tmp_path,
        manifest_for(
            {
                "name": "local-smoke",
                "enabled": True,
                "approved": True,
                "type": "local_jsonl",
                "path": str(source_path),
                "license": "project-owned",
                "attribution": "Unit test fixture.",
                "category": "python",
                "stack": ["python"],
                "quality": "verified",
            }
        ),
    )

    assert len(records) == 1
    assert records[0]["source"] == "local-smoke"
    assert records[0]["source_license"] == "project-owned"


def test_ingest_rejects_unapproved_enabled_source(tmp_path: Path) -> None:
    source_path = tmp_path / "source.jsonl"
    write_jsonl(source_path, [{"instruction": "Do it.", "output": "Done."}])
    manifest_path = tmp_path / "manifest.json"
    write_json(
        manifest_path,
        manifest_for(
            {
                "name": "not-approved",
                "enabled": True,
                "approved": False,
                "type": "local_jsonl",
                "path": str(source_path),
                "license": "project-owned",
                "attribution": "Unit test fixture.",
            }
        ),
    )

    with pytest.raises(IngestError, match="not approved"):
        ingest_manifest(
            manifest_path,
            tmp_path / "train.jsonl",
            tmp_path / "raw",
            tmp_path / "provenance.json",
            allow_local_sources=True,
        )


def test_ingest_rejects_unapproved_license(tmp_path: Path) -> None:
    source_path = tmp_path / "source.jsonl"
    write_jsonl(source_path, [{"instruction": "Do it.", "output": "Done."}])
    manifest_path = tmp_path / "manifest.json"
    write_json(
        manifest_path,
        manifest_for(
            {
                "name": "bad-license",
                "enabled": True,
                "approved": True,
                "type": "local_jsonl",
                "path": str(source_path),
                "license": "unknown",
                "attribution": "Unit test fixture.",
            }
        ),
    )

    with pytest.raises(IngestError, match="unapproved license"):
        ingest_manifest(
            manifest_path,
            tmp_path / "train.jsonl",
            tmp_path / "raw",
            tmp_path / "provenance.json",
            allow_local_sources=True,
        )


def test_ingest_filters_duplicates_and_secrets(tmp_path: Path) -> None:
    source_path = tmp_path / "source.jsonl"
    good_record = {"instruction": "Say hi.", "output": "hi"}
    write_jsonl(
        source_path,
        [
            good_record,
            good_record,
            {
                "instruction": "Use this token.",
                "output": "token = 'ghp_123456789012345678901234567890123456'",
            },
        ],
    )

    records = run_ingest(
        tmp_path,
        manifest_for(
            {
                "name": "filter-smoke",
                "enabled": True,
                "approved": True,
                "type": "local_jsonl",
                "path": str(source_path),
                "license": "mit",
                "attribution": "Unit test fixture.",
                "quality": "reviewed",
            }
        ),
    )

    assert len(records) == 1
    assert records[0]["instruction"] == "Say hi."
