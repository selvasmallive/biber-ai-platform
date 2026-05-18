#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from typing import Any


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
API_KEY_ENV_NAMES = ("BIBER_API_KEY", "BIBER_TEST_API_KEY", "BIBER_DEMO_API_KEY")


class BiberClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body_snippet: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body_snippet = body_snippet


def build_url(
    base_url: str,
    path: str,
    query: Mapping[str, object | None] | None = None,
) -> str:
    clean_base_url = base_url.rstrip("/")
    clean_path = path if path.startswith("/") else f"/{path}"
    query_items = {
        key: value
        for key, value in (query or {}).items()
        if value is not None
    }
    if not query_items:
        return f"{clean_base_url}{clean_path}"
    return f"{clean_base_url}{clean_path}?{urllib.parse.urlencode(query_items)}"


def resolve_api_key(cli_api_key: str | None = None) -> str:
    if cli_api_key:
        return cli_api_key
    for env_name in API_KEY_ENV_NAMES:
        api_key = os.environ.get(env_name)
        if api_key:
            return api_key
    raise BiberClientError(
        "API key required. Set BIBER_API_KEY or pass --api-key."
    )


def request_json(
    *,
    base_url: str,
    api_key: str,
    path: str,
    query: Mapping[str, object | None] | None = None,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    url = build_url(base_url, path, query)
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        snippet = body[:500]
        raise BiberClientError(
            f"{path} returned HTTP {exc.code}: {snippet}",
            status_code=int(exc.code),
            body_snippet=snippet,
        ) from exc
    except urllib.error.URLError as exc:
        raise BiberClientError(f"{path} request failed: {exc}") from exc

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BiberClientError(f"{path} returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise BiberClientError(f"{path} returned non-object JSON")
    return payload


def short_value(value: object, *, max_chars: int = 20) -> str:
    if value is None or value == "":
        return "-"
    text = str(value)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}..."


def require_mapping(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def format_overview_summary(payload: Mapping[str, Any]) -> str:
    summary = require_mapping(payload.get("summary"))
    explorer = require_mapping(payload.get("explorer"))
    latest_blocks = explorer.get("latest_blocks")
    latest_block_height = "-"
    latest_block_hash = "-"
    if isinstance(latest_blocks, list) and latest_blocks:
        first_block = latest_blocks[0]
        if isinstance(first_block, dict):
            latest_block_height = short_value(first_block.get("height"))
            latest_block_hash = short_value(first_block.get("block_hash"))

    lines = [
        "BIBER XRIQ private-devnet overview",
        f"current_height: {short_value(summary.get('current_height'))}",
        f"state_root: {short_value(summary.get('state_root'), max_chars=24)}",
        f"pending_count: {short_value(summary.get('pending_count'))}",
        f"snapshot_count: {short_value(summary.get('snapshot_count'))}",
        f"latest_snapshot: {short_value(summary.get('latest_snapshot_name'))}",
        f"latest_block_height: {latest_block_height}",
        f"latest_block_hash: {latest_block_hash}",
    ]
    return "\n".join(lines)


def format_snapshot_list_summary(payload: Mapping[str, Any]) -> str:
    snapshots = payload.get("snapshots")
    lines = [
        "BIBER XRIQ private-devnet snapshots",
        f"count: {short_value(payload.get('count'))}",
        f"total_available: {short_value(payload.get('total_available'))}",
    ]
    if isinstance(snapshots, list):
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            lines.append(
                "- "
                f"{short_value(snapshot.get('snapshot_name'), max_chars=48)} "
                f"height={short_value(snapshot.get('current_height'))} "
                f"pending={short_value(snapshot.get('pending_transactions'))} "
                f"state_root={short_value(snapshot.get('state_root'), max_chars=16)}"
            )
    return "\n".join(lines)


def format_snapshot_detail_summary(payload: Mapping[str, Any]) -> str:
    manifest = require_mapping(payload.get("manifest"))
    files = require_mapping(payload.get("files"))
    lines = [
        "BIBER XRIQ private-devnet snapshot",
        f"snapshot_name: {short_value(payload.get('snapshot_name'), max_chars=48)}",
        f"status: {short_value(payload.get('status'))}",
        f"current_height: {short_value(manifest.get('current_height'))}",
        f"state_root: {short_value(manifest.get('state_root'), max_chars=24)}",
        f"pending_transactions: {short_value(manifest.get('pending_transactions'))}",
        f"chain_file: {short_value(files.get('chain'))}",
        f"pending_file: {short_value(files.get('pending'))}",
    ]
    return "\n".join(lines)


def fetch_overview(
    *,
    base_url: str,
    api_key: str,
    explorer_limit: int,
    snapshot_limit: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/xriq/private-devnet/overview",
        query={"explorer_limit": explorer_limit, "snapshot_limit": snapshot_limit},
        timeout_seconds=timeout_seconds,
    )


def fetch_snapshots(
    *,
    base_url: str,
    api_key: str,
    limit: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/xriq/private-devnet/snapshots",
        query={"limit": limit},
        timeout_seconds=timeout_seconds,
    )


def fetch_snapshot(
    *,
    base_url: str,
    api_key: str,
    snapshot_name: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    encoded_name = urllib.parse.quote(snapshot_name, safe="")
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path=f"/v1/xriq/private-devnet/snapshots/{encoded_name}",
        timeout_seconds=timeout_seconds,
    )


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=os.environ.get("BIBER_API_BASE_URL", DEFAULT_BASE_URL),
        help="BIBER API base URL. Defaults to BIBER_API_BASE_URL or localhost.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="BIBER API key. Prefer BIBER_API_KEY so it is not visible in shell history.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="print_json",
        help="Print the full JSON response instead of a concise summary.",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal stdlib client for BIBER XRIQ private-devnet API endpoints."
    )
    add_common_args(parser)
    subparsers = parser.add_subparsers(dest="command")

    overview = subparsers.add_parser("overview", help="Fetch the compact dashboard payload.")
    overview.add_argument("--explorer-limit", type=int, default=5)
    overview.add_argument("--snapshot-limit", type=int, default=5)

    snapshots = subparsers.add_parser("snapshots", help="List private-devnet snapshots.")
    snapshots.add_argument("--limit", type=int, default=10)

    snapshot = subparsers.add_parser("snapshot", help="Inspect one private-devnet snapshot.")
    snapshot.add_argument("snapshot_name_arg", nargs="?")
    snapshot.add_argument("--snapshot-name", dest="snapshot_name_flag")

    args = parser.parse_args(argv)
    if args.command is None:
        args.command = "overview"
        args.explorer_limit = 5
        args.snapshot_limit = 5
    return args


def run(args: argparse.Namespace) -> str:
    api_key = resolve_api_key(args.api_key)
    base_url = args.base_url.rstrip("/")

    if args.command == "overview":
        payload = fetch_overview(
            base_url=base_url,
            api_key=api_key,
            explorer_limit=args.explorer_limit,
            snapshot_limit=args.snapshot_limit,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.print_json
            else format_overview_summary(payload)
        )

    if args.command == "snapshots":
        payload = fetch_snapshots(
            base_url=base_url,
            api_key=api_key,
            limit=args.limit,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.print_json
            else format_snapshot_list_summary(payload)
        )

    if args.command == "snapshot":
        snapshot_name = args.snapshot_name_flag or args.snapshot_name_arg
        if not snapshot_name:
            raise BiberClientError("snapshot requires a snapshot name.")
        payload = fetch_snapshot(
            base_url=base_url,
            api_key=api_key,
            snapshot_name=snapshot_name,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.print_json
            else format_snapshot_detail_summary(payload)
        )

    raise BiberClientError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    try:
        output = run(parse_args(argv))
    except BiberClientError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
