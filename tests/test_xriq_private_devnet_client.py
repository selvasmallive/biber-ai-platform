from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import biber_xriq_private_devnet_client as client  # noqa: E402


def test_build_url_encodes_query_and_omits_none_values() -> None:
    url = client.build_url(
        "http://127.0.0.1:8000/",
        "/v1/xriq/private-devnet/snapshots",
        {"limit": 10, "name": "api smoke", "skip": None},
    )

    assert url == (
        "http://127.0.0.1:8000/v1/xriq/private-devnet/snapshots"
        "?limit=10&name=api+smoke"
    )


def test_resolve_api_key_prefers_cli_value(monkeypatch) -> None:
    monkeypatch.setenv("BIBER_API_KEY", "env-key")

    assert client.resolve_api_key("cli-key") == "cli-key"


def test_format_overview_summary_includes_dashboard_fields() -> None:
    payload = {
        "summary": {
            "current_height": 2,
            "state_root": "b" * 64,
            "pending_count": 0,
            "snapshot_count": 3,
            "latest_snapshot_name": "api-smoke",
        },
        "explorer": {
            "latest_blocks": [
                {
                    "height": 2,
                    "block_hash": "a" * 64,
                }
            ]
        },
    }

    lines = client.format_overview_summary(payload).splitlines()

    assert lines[0] == "BIBER XRIQ private-devnet overview"
    assert "current_height: 2" in lines
    assert "pending_count: 0" in lines
    assert "snapshot_count: 3" in lines
    assert "latest_snapshot: api-smoke" in lines
    assert "latest_block_height: 2" in lines


def test_format_snapshot_list_summary_includes_each_snapshot() -> None:
    payload = {
        "count": 1,
        "total_available": 2,
        "snapshots": [
            {
                "snapshot_name": "api-smoke",
                "current_height": 2,
                "pending_transactions": 0,
                "state_root": "c" * 64,
            }
        ],
    }

    output = client.format_snapshot_list_summary(payload)

    assert "BIBER XRIQ private-devnet snapshots" in output
    assert "count: 1" in output
    assert "total_available: 2" in output
    assert "- api-smoke height=2 pending=0 state_root=cccccccccccccccc..." in output


def test_format_snapshot_detail_summary_uses_manifest_and_file_flags() -> None:
    payload = {
        "snapshot_name": "api-smoke",
        "status": "ok",
        "manifest": {
            "current_height": 2,
            "state_root": "d" * 64,
            "pending_transactions": 0,
        },
        "files": {
            "chain": True,
            "pending": False,
        },
    }

    output = client.format_snapshot_detail_summary(payload)

    assert "BIBER XRIQ private-devnet snapshot" in output
    assert "snapshot_name: api-smoke" in output
    assert "status: ok" in output
    assert "current_height: 2" in output
    assert "chain_file: True" in output
    assert "pending_file: False" in output
