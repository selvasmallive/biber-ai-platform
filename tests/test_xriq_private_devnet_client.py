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


def test_format_status_summary_includes_chain_fields() -> None:
    payload = {
        "current_height": 3,
        "state_root": "e" * 64,
        "pending_transactions": 1,
        "stored_blocks": 3,
    }

    output = client.format_status_summary(payload)

    assert "BIBER XRIQ private-devnet status" in output
    assert "current_height: 3" in output
    assert "pending_transactions: 1" in output
    assert "stored_blocks: 3" in output


def test_format_account_summary_includes_balance_and_nonce() -> None:
    payload = {
        "address": "xriqdev1alice00000000000",
        "balance_base_units": "73",
        "nonce": 1,
    }

    output = client.format_account_summary(payload)

    assert "BIBER XRIQ private-devnet account" in output
    assert "address: xriqdev1alice00000000000" in output
    assert "balance_base_units: 73" in output
    assert "nonce: 1" in output


def test_format_block_summary_lists_transactions() -> None:
    payload = {
        "height": 1,
        "block_hash": "b" * 64,
        "state_root": "c" * 64,
        "transaction_count": 1,
        "timestamp_ms": 1000,
        "transactions": [
            {
                "tx_hash": "d" * 64,
                "from": "xriqdev1alice00000000000",
                "to": "xriqdev1bobbb00000000000",
                "amount_base_units": "25",
                "fee_base_units": "2",
            }
        ],
    }

    output = client.format_block_summary(payload)

    assert "BIBER XRIQ private-devnet block" in output
    assert "height: 1" in output
    assert "transaction_count: 1" in output
    assert "amount=25" in output
    assert "fee=2" in output


def test_format_mempool_summary_lists_pending_transactions() -> None:
    payload = {
        "pending_count": 1,
        "transactions": [
            {
                "tx_hash": "a" * 64,
                "from": "xriqdev1alice00000000000",
                "to": "xriqdev1bobbb00000000000",
                "amount_base_units": "25",
                "fee_base_units": "2",
            }
        ],
    }

    output = client.format_mempool_summary(payload)

    assert "BIBER XRIQ private-devnet mempool" in output
    assert "pending_count: 1" in output
    assert "amount=25" in output
    assert "fee=2" in output


def test_format_preflight_transfer_summary_includes_confirmation() -> None:
    payload = {
        "from": "xriqdev1alice00000000000",
        "to": "xriqdev1bobbb00000000000",
        "amount_base_units": "25",
        "fee_base_units": "2",
        "transaction_hash": "f" * 64,
        "confirmed_block_height": 1,
        "final_balance_base_units": "73",
        "final_nonce": 1,
    }

    output = client.format_preflight_transfer_summary(payload)

    assert "BIBER XRIQ private-devnet preflight transfer" in output
    assert "amount_base_units: 25" in output
    assert "confirmed_block_height: 1" in output
    assert "final_balance_base_units: 73" in output


def test_preflight_transfer_posts_expected_body(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(**kwargs):
        captured.update(kwargs)
        return {"command": "preflight-transfer"}

    monkeypatch.setattr(client, "request_json", fake_request_json)

    payload = client.preflight_transfer(
        base_url="http://127.0.0.1:8000",
        api_key="test-key",
        from_address="xriqdev1alice00000000000",
        to_address="xriqdev1bobbb00000000000",
        amount_base_units="25",
        fee_base_units="2",
        expires_at_height=100,
        timestamp_ms=1000,
        consensus_round=None,
        alice_balance_base_units=None,
        timeout_seconds=10,
    )

    assert payload == {"command": "preflight-transfer"}
    assert captured["path"] == "/v1/xriq/private-devnet/preflight-transfer"
    assert captured["method"] == "POST"
    assert captured["json_body"] == {
        "from": "xriqdev1alice00000000000",
        "to": "xriqdev1bobbb00000000000",
        "amount_base_units": "25",
        "fee_base_units": "2",
        "expires_at_height": 100,
        "timestamp_ms": 1000,
        "consensus_round": None,
        "alice_balance_base_units": None,
    }


def test_export_snapshot_posts_expected_body(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(**kwargs):
        captured.update(kwargs)
        return {"command": "snapshot-export", "snapshot_name": "api-smoke"}

    monkeypatch.setattr(client, "request_json", fake_request_json)

    payload = client.export_snapshot(
        base_url="http://127.0.0.1:8000",
        api_key="test-key",
        snapshot_name="api-smoke",
        include_pending_file=False,
        alice_balance_base_units="100",
        timeout_seconds=10,
    )

    assert payload == {"command": "snapshot-export", "snapshot_name": "api-smoke"}
    assert captured["path"] == "/v1/xriq/private-devnet/snapshots/export"
    assert captured["method"] == "POST"
    assert captured["json_body"] == {
        "snapshot_name": "api-smoke",
        "include_pending_file": False,
        "alice_balance_base_units": "100",
    }


def test_import_snapshot_posts_expected_body(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_request_json(**kwargs):
        captured.update(kwargs)
        return {"command": "snapshot-import", "snapshot_name": "api-smoke"}

    monkeypatch.setattr(client, "request_json", fake_request_json)

    payload = client.import_snapshot(
        base_url="http://127.0.0.1:8000",
        api_key="test-key",
        snapshot_name="api-smoke",
        target="staging",
        include_pending_file=True,
        alice_balance_base_units=None,
        timeout_seconds=10,
    )

    assert payload == {"command": "snapshot-import", "snapshot_name": "api-smoke"}
    assert captured["path"] == "/v1/xriq/private-devnet/snapshots/import"
    assert captured["method"] == "POST"
    assert captured["json_body"] == {
        "snapshot_name": "api-smoke",
        "target": "staging",
        "include_pending_file": True,
        "alice_balance_base_units": None,
    }


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
