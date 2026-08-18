from __future__ import annotations

from scripts.biber_admin_console_readiness import (
    console_checks,
    summarize_admin_api,
    summarize_admin_console_list_flow,
    summarize_public_admin_access,
)


def fake_response(
    *,
    status_code: int | None,
    body: str = "",
    headers: dict[str, str] | None = None,
    error: str | None = None,
) -> dict[str, object]:
    return {
        "status_code": status_code,
        "headers": headers or {},
        "body": body,
        "duration_ms": 1,
        "error": error,
    }


def served_console_response() -> dict[str, object]:
    return fake_response(
        status_code=200,
        body=(
            "BIBER Admin /v1/admin/api-keys Admin API key Issue Key Revoke"
        ),
        headers={
            "cache-control": "no-store",
            "content-security-policy": "frame-ancestors 'none'",
            "referrer-policy": "no-referrer",
            "x-content-type-options": "nosniff",
            "x-frame-options": "DENY",
        },
    )


def summarize_access(
    console_response: dict[str, object],
    alias_response: dict[str, object],
) -> dict[str, object]:
    console = console_checks(
        console_response,
        admin_key_value="admin-secret",
        require_console_served=False,
    )
    alias = console_checks(
        alias_response,
        admin_key_value="admin-secret",
        require_console_served=False,
    )
    admin_api = summarize_admin_api(
        fake_response(status_code=401),
        authenticated_response=None,
        require_authenticated_admin_list=False,
    )
    return summarize_public_admin_access(
        console_checks_payload=console,
        alias_checks_payload=alias,
        admin_api_summary=admin_api,
        require_console_served=False,
    )


def test_public_admin_access_reports_directly_served_console() -> None:
    summary = summarize_access(served_console_response(), served_console_response())

    assert summary["state"] == "admin_console_served_directly"
    assert summary["console_route_state"] == "served"
    assert summary["alias_route_state"] == "served"
    assert (
        summary["recommended_next_step"]
        == "protect_admin_routes_with_cloudflare_access_or_vpn_before_real_users"
    )


def test_public_admin_access_reports_edge_protected_console() -> None:
    summary = summarize_access(
        fake_response(status_code=403, body="Forbidden"),
        fake_response(status_code=403, body="Forbidden"),
    )

    assert summary["state"] == "admin_console_edge_protected"
    assert summary["cloudflare_access_candidate"] is True
    assert "/v1/admin/*" in summary["recommended_edge_protected_paths"]


def test_public_admin_access_reports_unreachable_console() -> None:
    summary = summarize_access(
        fake_response(status_code=None, error="name resolution failed"),
        fake_response(status_code=403, body="Forbidden"),
    )

    assert summary["state"] == "admin_console_unreachable"
    assert summary["console_route_state"] == "unreachable"


def test_admin_console_list_flow_ready_without_key_or_record_leakage() -> None:
    console = console_checks(
        served_console_response(),
        admin_key_value="admin-secret",
        require_console_served=True,
    )
    alias = console_checks(
        served_console_response(),
        admin_key_value="admin-secret",
        require_console_served=True,
    )
    admin_api = summarize_admin_api(
        fake_response(status_code=401),
        authenticated_response=fake_response(
            status_code=200,
            body='{"keys":[{"key_id":"secret-key-id","label":"IDE agent"}]}',
        ),
        require_authenticated_admin_list=True,
    )

    summary = summarize_admin_console_list_flow(
        console_checks_payload=console,
        alias_checks_payload=alias,
        admin_api_summary=admin_api,
        admin_api_key_configured=True,
    )

    assert summary["ready"] is True
    assert summary["authenticated_admin_key_count"] == 1
    assert summary["admin_api_key_included"] is False
    assert summary["raw_key_records_included"] is False
    assert "secret-key-id" not in str(summary)
    assert "IDE agent" not in str(summary)


def test_admin_console_list_flow_waits_for_authenticated_admin_list() -> None:
    console = console_checks(
        served_console_response(),
        admin_key_value=None,
        require_console_served=True,
    )
    admin_api = summarize_admin_api(
        fake_response(status_code=401),
        authenticated_response=None,
        require_authenticated_admin_list=False,
    )

    summary = summarize_admin_console_list_flow(
        console_checks_payload=console,
        alias_checks_payload=console,
        admin_api_summary=admin_api,
        admin_api_key_configured=False,
    )

    assert summary["ready"] is False
    assert summary["recommended_context"] == "direct_local_or_vast_check"
