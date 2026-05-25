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
    method: str = "GET",
    json_body: Mapping[str, object | None] | None = None,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    url = build_url(base_url, path, query)
    body_bytes: bytes | None = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    if json_body is not None:
        headers["Content-Type"] = "application/json"
        body_bytes = json.dumps(
            {key: value for key, value in json_body.items() if value is not None}
        ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body_bytes,
        headers=headers,
        method=method,
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


def format_status_summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "BIBER XRIQ private-devnet status",
        f"current_height: {short_value(payload.get('current_height'))}",
        f"state_root: {short_value(payload.get('state_root'), max_chars=24)}",
        f"pending_transactions: {short_value(payload.get('pending_transactions'))}",
        f"stored_blocks: {short_value(payload.get('stored_blocks'))}",
    ]
    return "\n".join(lines)


def format_account_summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "BIBER XRIQ private-devnet account",
        f"address: {short_value(payload.get('address'), max_chars=48)}",
        f"balance_base_units: {short_value(payload.get('balance_base_units'))}",
        f"nonce: {short_value(payload.get('nonce'))}",
    ]
    return "\n".join(lines)


def format_mempool_summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "BIBER XRIQ private-devnet mempool",
        f"pending_count: {short_value(payload.get('pending_count'))}",
    ]
    transactions = payload.get("transactions")
    if isinstance(transactions, list):
        for tx in transactions[:5]:
            if not isinstance(tx, dict):
                continue
            lines.append(
                "- "
                f"{short_value(tx.get('tx_hash'), max_chars=16)} "
                f"{short_value(tx.get('from'), max_chars=24)} -> "
                f"{short_value(tx.get('to'), max_chars=24)} "
                f"amount={short_value(tx.get('amount_base_units'))} "
                f"fee={short_value(tx.get('fee_base_units'))}"
            )
    return "\n".join(lines)


def format_transaction_summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "BIBER XRIQ private-devnet transaction",
        f"tx_hash: {short_value(payload.get('tx_hash'), max_chars=24)}",
        f"status: {short_value(payload.get('status'))}",
        f"block_height: {short_value(payload.get('block_height'))}",
        f"from: {short_value(payload.get('from'), max_chars=48)}",
        f"to: {short_value(payload.get('to'), max_chars=48)}",
        f"amount_base_units: {short_value(payload.get('amount_base_units'))}",
        f"fee_base_units: {short_value(payload.get('fee_base_units'))}",
    ]
    return "\n".join(lines)


def format_preflight_transfer_summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "BIBER XRIQ private-devnet preflight transfer",
        f"from: {short_value(payload.get('from'), max_chars=48)}",
        f"to: {short_value(payload.get('to'), max_chars=48)}",
        f"amount_base_units: {short_value(payload.get('amount_base_units'))}",
        f"fee_base_units: {short_value(payload.get('fee_base_units'))}",
        f"transaction_hash: {short_value(payload.get('transaction_hash'), max_chars=24)}",
        f"confirmed_block_height: {short_value(payload.get('confirmed_block_height'))}",
        f"final_balance_base_units: {short_value(payload.get('final_balance_base_units'))}",
        f"final_nonce: {short_value(payload.get('final_nonce'))}",
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


def fetch_status(
    *,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/xriq/private-devnet/status",
        timeout_seconds=timeout_seconds,
    )


def fetch_account(
    *,
    base_url: str,
    api_key: str,
    address: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path=f"/v1/xriq/private-devnet/accounts/{urllib.parse.quote(address, safe='')}",
        timeout_seconds=timeout_seconds,
    )


def fetch_mempool(
    *,
    base_url: str,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/xriq/private-devnet/mempool",
        timeout_seconds=timeout_seconds,
    )


def fetch_transaction(
    *,
    base_url: str,
    api_key: str,
    tx_hash: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path=f"/v1/xriq/private-devnet/transactions/{urllib.parse.quote(tx_hash, safe='')}",
        timeout_seconds=timeout_seconds,
    )


def preflight_transfer(
    *,
    base_url: str,
    api_key: str,
    from_address: str,
    to_address: str,
    amount_base_units: str,
    fee_base_units: str,
    expires_at_height: int | None,
    timestamp_ms: int | None,
    consensus_round: int | None,
    alice_balance_base_units: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    return request_json(
        base_url=base_url,
        api_key=api_key,
        path="/v1/xriq/private-devnet/preflight-transfer",
        method="POST",
        json_body={
            "from": from_address,
            "to": to_address,
            "amount_base_units": amount_base_units,
            "fee_base_units": fee_base_units,
            "expires_at_height": expires_at_height,
            "timestamp_ms": timestamp_ms,
            "consensus_round": consensus_round,
            "alice_balance_base_units": alice_balance_base_units,
        },
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

    subparsers.add_parser("status", help="Fetch private-devnet chain status.")

    account = subparsers.add_parser("account", help="Fetch one account detail.")
    account.add_argument("address")

    subparsers.add_parser("mempool", help="Fetch durable mempool detail.")

    transaction = subparsers.add_parser("transaction", help="Fetch one transaction detail.")
    transaction.add_argument("tx_hash")

    preflight = subparsers.add_parser(
        "preflight-transfer",
        help="Submit a deterministic private-devnet transfer through the BIBER API.",
    )
    preflight.add_argument("--from", dest="from_address", required=True)
    preflight.add_argument("--to", dest="to_address", required=True)
    preflight.add_argument("--amount", dest="amount_base_units", required=True)
    preflight.add_argument("--fee", dest="fee_base_units", required=True)
    preflight.add_argument("--expires-at-height", type=int, default=None)
    preflight.add_argument("--timestamp-ms", type=int, default=None)
    preflight.add_argument("--consensus-round", type=int, default=None)
    preflight.add_argument("--alice-balance", dest="alice_balance_base_units", default=None)

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

    if args.command == "status":
        payload = fetch_status(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.print_json
            else format_status_summary(payload)
        )

    if args.command == "account":
        payload = fetch_account(
            base_url=base_url,
            api_key=api_key,
            address=args.address,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.print_json
            else format_account_summary(payload)
        )

    if args.command == "mempool":
        payload = fetch_mempool(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.print_json
            else format_mempool_summary(payload)
        )

    if args.command == "transaction":
        payload = fetch_transaction(
            base_url=base_url,
            api_key=api_key,
            tx_hash=args.tx_hash,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.print_json
            else format_transaction_summary(payload)
        )

    if args.command == "preflight-transfer":
        payload = preflight_transfer(
            base_url=base_url,
            api_key=api_key,
            from_address=args.from_address,
            to_address=args.to_address,
            amount_base_units=args.amount_base_units,
            fee_base_units=args.fee_base_units,
            expires_at_height=args.expires_at_height,
            timestamp_ms=args.timestamp_ms,
            consensus_round=args.consensus_round,
            alice_balance_base_units=args.alice_balance_base_units,
            timeout_seconds=args.timeout_seconds,
        )
        return (
            json.dumps(payload, indent=2, sort_keys=True)
            if args.print_json
            else format_preflight_transfer_summary(payload)
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
