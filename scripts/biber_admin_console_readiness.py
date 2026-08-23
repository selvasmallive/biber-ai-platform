from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


SOURCE = "biber_admin_console_readiness"
PROTECTED_ADMIN_STATUSES = {401, 403, 503}
EDGE_PROTECTED_CONSOLE_STATUSES = {401, 403}


def normalize_base_url(value: str) -> str:
    base_url = value.strip().rstrip("/")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3].rstrip("/")
    return base_url


def default_base_url() -> str:
    for name in (
        "BIBER_ADMIN_CONSOLE_BASE_URL",
        "BIBER_PUBLIC_API_BASE_URL",
        "BIBER_OPENAI_BASE_URL",
    ):
        value = os.getenv(name)
        if value:
            return normalize_base_url(value)
    return "http://127.0.0.1:8000"


def build_url(base_url: str, path: str) -> str:
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def read_dotenv_value(path: str, name: str) -> str | None:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    prefix = f"{name}="
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value
    return None


def request_url(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            return {
                "status_code": response.status,
                "headers": dict(response.headers.items()),
                "body": body.decode("utf-8", errors="replace"),
                "duration_ms": int((time.monotonic() - started) * 1000),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read()
        return {
            "status_code": exc.code,
            "headers": dict(exc.headers.items()),
            "body": body.decode("utf-8", errors="replace"),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error": None,
        }
    except urllib.error.URLError as exc:
        return {
            "status_code": None,
            "headers": {},
            "body": "",
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error": str(exc),
        }


def header_value(response: dict[str, Any], name: str) -> str:
    wanted = name.lower()
    headers = response.get("headers")
    if not isinstance(headers, dict):
        return ""
    for key, value in headers.items():
        if str(key).lower() == wanted:
            return str(value)
    return ""


def response_public_summary(response: dict[str, Any]) -> dict[str, Any]:
    body = str(response.get("body") or "")
    return {
        "status_code": response.get("status_code"),
        "duration_ms": response.get("duration_ms"),
        "error": response.get("error"),
        "content_length": len(body.encode("utf-8")),
    }


def console_checks(
    response: dict[str, Any],
    *,
    admin_key_value: str | None,
    require_console_served: bool,
) -> dict[str, Any]:
    body = str(response.get("body") or "")
    cache_control = header_value(response, "cache-control")
    csp = header_value(response, "content-security-policy")
    referrer_policy = header_value(response, "referrer-policy")
    x_content_type_options = header_value(response, "x-content-type-options")
    x_frame_options = header_value(response, "x-frame-options")
    required_markers = [
        "BIBER Admin",
        "/v1/admin/api-keys",
        "Admin API key",
        "Issue Key",
        "Revoke",
        "Connection Checks",
        "External Agent Quickstart",
        "BIBER_OPENAI_BASE_URL",
    ]
    markers_missing = [marker for marker in required_markers if marker not in body]
    admin_key_leaked = bool(admin_key_value and admin_key_value in body)
    served_ok = (
        response.get("status_code") == 200
        and not markers_missing
        and "no-store" in cache_control.lower()
        and "frame-ancestors 'none'" in csp
        and referrer_policy.lower() == "no-referrer"
        and x_content_type_options.lower() == "nosniff"
        and x_frame_options.lower() == "deny"
        and not admin_key_leaked
    )
    edge_protected = (
        response.get("status_code") in EDGE_PROTECTED_CONSOLE_STATUSES
        and "BIBER Admin" not in body
        and not admin_key_leaked
    )
    checks = {
        "status_code": response.get("status_code"),
        "request_error": response.get("error"),
        "status_ok": response.get("status_code") == 200,
        "served_ok": served_ok,
        "edge_protected": edge_protected,
        "require_console_served": require_console_served,
        "required_markers_ok": not markers_missing,
        "markers_missing": markers_missing,
        "cache_control_no_store": "no-store" in cache_control.lower(),
        "content_security_policy_frame_ancestors_none": "frame-ancestors 'none'" in csp,
        "referrer_policy_no_referrer": referrer_policy.lower() == "no-referrer",
        "x_content_type_options_nosniff": x_content_type_options.lower() == "nosniff",
        "x_frame_options_deny": x_frame_options.lower() == "deny",
        "admin_key_value_found_in_console_html": admin_key_leaked,
    }
    checks["ok"] = served_ok or (edge_protected and not require_console_served)
    checks["headers"] = {
        "cache_control": cache_control,
        "content_security_policy_present": bool(csp),
        "referrer_policy": referrer_policy,
        "x_content_type_options": x_content_type_options,
        "x_frame_options": x_frame_options,
    }
    return checks


def console_route_state(checks: dict[str, Any]) -> str:
    if checks.get("served_ok") is True:
        return "served"
    if checks.get("edge_protected") is True:
        return "edge_protected"
    if checks.get("status_code") is None or checks.get("request_error"):
        return "unreachable"
    return "needs_review"


def summarize_public_admin_access(
    *,
    console_checks_payload: dict[str, Any],
    alias_checks_payload: dict[str, Any],
    admin_api_summary: dict[str, Any],
    require_console_served: bool,
) -> dict[str, Any]:
    console_state = console_route_state(console_checks_payload)
    alias_state = console_route_state(alias_checks_payload)
    admin_api_protected = admin_api_summary.get("anonymous_protected") is True
    both_console_routes_served = console_state == "served" and alias_state == "served"
    both_console_routes_edge_protected = (
        console_state == "edge_protected" and alias_state == "edge_protected"
    )

    if both_console_routes_served and admin_api_protected:
        state = "admin_console_served_directly"
        recommendation = "protect_admin_routes_with_cloudflare_access_or_vpn_before_real_users"
    elif both_console_routes_edge_protected and admin_api_protected:
        state = "admin_console_edge_protected"
        recommendation = "verify_admin_email_access_in_browser_then_keep_chat_api_user_key_auth"
    elif "unreachable" in {console_state, alias_state}:
        state = "admin_console_unreachable"
        recommendation = "check_dns_tunnel_or_cloudflare_route_before_using_admin_console"
    else:
        state = "admin_console_needs_review"
        recommendation = "inspect_route_statuses_and_cloudflare_access_policy"

    return {
        "state": state,
        "console_route_state": console_state,
        "alias_route_state": alias_state,
        "anonymous_admin_api_protected": admin_api_protected,
        "require_console_served": require_console_served,
        "cloudflare_access_candidate": both_console_routes_edge_protected,
        "recommended_next_step": recommendation,
        "recommended_edge_protected_paths": [
            "/admin",
            "/admin/*",
            "/v1/admin/*",
        ],
        "public_chat_routes_should_remain_user_api_key_protected": True,
    }


def summarize_admin_console_list_flow(
    *,
    console_checks_payload: dict[str, Any],
    alias_checks_payload: dict[str, Any],
    admin_api_summary: dict[str, Any],
    admin_api_key_configured: bool,
) -> dict[str, Any]:
    console_served = console_checks_payload.get("served_ok") is True
    alias_served = alias_checks_payload.get("served_ok") is True
    authenticated_list_ok = admin_api_summary.get("authenticated_ok") is True
    ready = console_served and alias_served and admin_api_key_configured and authenticated_list_ok
    return {
        "ready": ready,
        "console_html_served": console_served,
        "alias_html_served": alias_served,
        "admin_api_key_configured": admin_api_key_configured,
        "authenticated_admin_list_ok": authenticated_list_ok,
        "authenticated_admin_key_count": admin_api_summary.get("authenticated_key_count"),
        "admin_api_key_included": False,
        "raw_key_records_included": False,
        "mutation_performed": False,
        "recommended_context": "direct_local_or_vast_check",
        "recommended_next_step": (
            "open_admin_console_with_cloudflare_access_in_browser"
            if ready
            else "run_direct_check_with_admin_api_key_env_when_admin_console_access_is_needed"
        ),
    }


def parse_json_body(response: dict[str, Any]) -> dict[str, Any] | None:
    try:
        body = json.loads(str(response.get("body") or ""))
    except json.JSONDecodeError:
        return None
    return body if isinstance(body, dict) else None


def summarize_admin_api(
    anonymous_response: dict[str, Any],
    authenticated_response: dict[str, Any] | None,
    *,
    require_authenticated_admin_list: bool,
) -> dict[str, Any]:
    anonymous_status = anonymous_response.get("status_code")
    anonymous_protected = anonymous_status in PROTECTED_ADMIN_STATUSES
    summary: dict[str, Any] = {
        "anonymous_status_code": anonymous_status,
        "anonymous_error": anonymous_response.get("error"),
        "anonymous_protected": anonymous_protected,
        "authenticated_request_sent": authenticated_response is not None,
        "authenticated_status_code": None,
        "authenticated_ok": None,
        "authenticated_key_count": None,
        "raw_key_records_included": False,
    }
    if authenticated_response is not None:
        summary["authenticated_status_code"] = authenticated_response.get("status_code")
        parsed = parse_json_body(authenticated_response)
        keys = parsed.get("keys") if isinstance(parsed, dict) else None
        key_count = len(keys) if isinstance(keys, list) else None
        summary["authenticated_key_count"] = key_count
        summary["authenticated_ok"] = authenticated_response.get("status_code") == 200

    summary["ok"] = anonymous_protected and (
        not require_authenticated_admin_list or summary["authenticated_ok"] is True
    )
    return summary


def write_json(path: str | None, payload: dict[str, Any]) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> dict[str, Any]:
    base_url = normalize_base_url(args.base_url or default_base_url())
    admin_key_value = None
    admin_key_source = None
    if args.admin_api_key_env:
        admin_key_value = os.getenv(args.admin_api_key_env) or None
        admin_key_source = "environment" if admin_key_value else None
        if not admin_key_value and args.admin_api_key_dotenv:
            admin_key_value = read_dotenv_value(args.admin_api_key_dotenv, args.admin_api_key_env)
            admin_key_source = "dotenv_file" if admin_key_value else None

    console_url = build_url(base_url, "/admin")
    alias_url = build_url(base_url, "/admin/api-keys")
    admin_api_url = build_url(base_url, "/v1/admin/api-keys")

    console_response = request_url(console_url, timeout_seconds=args.timeout_seconds)
    alias_response = request_url(alias_url, timeout_seconds=args.timeout_seconds)
    anonymous_admin_response = request_url(admin_api_url, timeout_seconds=args.timeout_seconds)
    authenticated_admin_response = None
    if admin_key_value:
        authenticated_admin_response = request_url(
            admin_api_url,
            headers={"Authorization": f"Bearer {admin_key_value}"},
            timeout_seconds=args.timeout_seconds,
        )

    console = {
        **response_public_summary(console_response),
        "url": console_url,
        "checks": console_checks(
            console_response,
            admin_key_value=admin_key_value,
            require_console_served=args.require_console_served,
        ),
    }
    alias = {
        **response_public_summary(alias_response),
        "url": alias_url,
        "checks": console_checks(
            alias_response,
            admin_key_value=admin_key_value,
            require_console_served=args.require_console_served,
        ),
    }
    admin_api = summarize_admin_api(
        anonymous_admin_response,
        authenticated_admin_response,
        require_authenticated_admin_list=args.require_authenticated_admin_list,
    )
    public_admin_access = summarize_public_admin_access(
        console_checks_payload=console["checks"],
        alias_checks_payload=alias["checks"],
        admin_api_summary=admin_api,
        require_console_served=args.require_console_served,
    )
    admin_console_list_flow = summarize_admin_console_list_flow(
        console_checks_payload=console["checks"],
        alias_checks_payload=alias["checks"],
        admin_api_summary=admin_api,
        admin_api_key_configured=bool(admin_key_value),
    )

    warnings: list[str] = []
    if args.admin_api_key_env and not admin_key_value:
        warnings.append(f"{args.admin_api_key_env} was not set; authenticated admin list skipped")
    if args.admin_api_key_dotenv and not args.admin_api_key_env:
        warnings.append("--admin-api-key-dotenv ignored because --admin-api-key-env was not set")

    summary = {
        "source": SOURCE,
        "base_url": base_url,
        "console_url": console_url,
        "alias_url": alias_url,
        "admin_api_url": admin_api_url,
        "external_network_required": not base_url.startswith(("http://127.0.0.1", "http://localhost")),
        "api_required": False,
        "mentor_used": False,
        "training_allowed": False,
        "admin_api_key_env": args.admin_api_key_env or None,
        "admin_api_key_configured": bool(admin_key_value),
        "admin_api_key_source": admin_key_source,
        "admin_api_key_included": False,
        "raw_key_records_included": False,
        "console": console,
        "alias": alias,
        "admin_api": admin_api,
        "public_admin_access": public_admin_access,
        "admin_console_list_flow": admin_console_list_flow,
        "warnings": warnings,
    }
    summary["ok"] = bool(console["checks"]["ok"] and alias["checks"]["ok"] and admin_api["ok"])
    if args.require_admin_console_list_flow and not admin_console_list_flow["ready"]:
        summary["ok"] = False
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a no-secret BIBER admin console readiness smoke."
    )
    parser.add_argument(
        "--base-url",
        help=(
            "BIBER API root such as https://api.beaverapi.com or http://127.0.0.1:8000. "
            "A trailing /v1 is accepted and stripped."
        ),
    )
    parser.add_argument(
        "--admin-api-key-env",
        default="",
        help=(
            "Optional environment variable containing BIBER_ADMIN_API_KEY. If set and present, "
            "the script verifies authenticated admin listing without writing key values."
        ),
    )
    parser.add_argument(
        "--admin-api-key-dotenv",
        default="",
        help=(
            "Optional dotenv file used only to read the variable named by --admin-api-key-env "
            "when it is absent from the process environment. The key value is never printed "
            "or written to the readiness artifact."
        ),
    )
    parser.add_argument(
        "--require-authenticated-admin-list",
        action="store_true",
        help="Fail unless the optional authenticated admin API list check returns HTTP 200.",
    )
    parser.add_argument(
        "--require-admin-console-list-flow",
        action="store_true",
        help=(
            "Fail unless the console HTML is served directly and the optional authenticated "
            "admin list check returns HTTP 200. Use only for direct local/Vast checks."
        ),
    )
    parser.add_argument(
        "--require-console-served",
        action="store_true",
        help=(
            "Fail if /admin and /admin/api-keys are protected at the edge instead of "
            "returning the BIBER Admin HTML. Use this for local/Vast direct checks."
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--output", help="Optional path for the redacted readiness artifact JSON.")
    args = parser.parse_args(argv)

    summary = run(args)
    write_json(args.output, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
