#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

API_KEY="${BIBER_TEST_API_KEY:-$(read_env_value BIBER_DEMO_API_KEY)}"
if [ -z "$API_KEY" ]; then
  API_KEY="dev-api-key-change-me"
fi

PYTHON_BIN="${BIBER_XRIQ_API_SMOKE_PYTHON:-${VENV_DIR}/bin/python}"
if [ ! -x "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    die "Python is required for JSON validation."
  fi
fi

SMOKE_ID="${BIBER_XRIQ_API_SMOKE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
ARTIFACT_DIR="${BIBER_XRIQ_API_SMOKE_ARTIFACT_DIR:-${BIBER_RUNTIME_ROOT}/outputs/xriq-api-smoke-${SMOKE_ID}}"
API_BASE_URL="${BIBER_XRIQ_API_SMOKE_URL:-http://127.0.0.1:${BIBER_API_PORT}}"
EXPLORER_LIMIT="${BIBER_XRIQ_API_SMOKE_LIMIT:-5}"
ALICE_ADDRESS="${BIBER_XRIQ_API_SMOKE_ACCOUNT:-xriqdev1alice00000000000}"
TX_HASH="${BIBER_XRIQ_API_SMOKE_TX_HASH:-}"

mkdir -p "$ARTIFACT_DIR"

export API_BASE_URL
export API_KEY
export ARTIFACT_DIR
export EXPLORER_LIMIT
export ALICE_ADDRESS
export TX_HASH

"$PYTHON_BIN" <<'PY'
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


api_base_url = os.environ["API_BASE_URL"].rstrip("/")
api_key = os.environ["API_KEY"]
artifact_dir = Path(os.environ["ARTIFACT_DIR"])
explorer_limit = int(os.environ["EXPLORER_LIMIT"])
alice_address = os.environ["ALICE_ADDRESS"]
tx_hash = os.environ["TX_HASH"].strip()


def fail(message: str) -> None:
    print(f"error={message}", file=sys.stderr)
    sys.exit(1)


def write_artifact(name: str, payload: object) -> None:
    (artifact_dir / name).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def request_json(path: str, artifact_name: str) -> dict[str, object]:
    request = urllib.request.Request(
        api_base_url + path,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        fail(f"{path} returned HTTP {exc.code}: {body[:500]}")
    except urllib.error.URLError as exc:
        fail(f"{path} request failed: {exc}")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        fail(f"{path} returned invalid JSON: {exc}")
    if not isinstance(payload, dict):
        fail(f"{path} returned non-object JSON")
    write_artifact(artifact_name, payload)
    return payload


def expect(payload: dict[str, object], key: str, value: object, label: str) -> None:
    if payload.get(key) != value:
        fail(f"{label} expected {key}={value!r}, got {payload.get(key)!r}")


health = request_json("/health", "health.json")
if health.get("status") != "ok":
    fail(f"health status was not ok: {health!r}")

status = request_json("/v1/xriq/private-devnet/status", "status.json")
expect(status, "command", "status", "status")

explorer_path = "/v1/xriq/private-devnet/explorer?" + urllib.parse.urlencode(
    {"limit": explorer_limit}
)
explorer = request_json(explorer_path, "explorer.json")
expect(explorer, "command", "explorer-overview", "explorer")

latest_blocks = explorer.get("latest_blocks")
block_height = None
block = None
if isinstance(latest_blocks, list) and latest_blocks:
    first_block = latest_blocks[0]
    if isinstance(first_block, dict) and isinstance(first_block.get("height"), int):
        block_height = first_block["height"]

if block_height is not None:
    block = request_json(f"/v1/xriq/private-devnet/blocks/{block_height}", "block.json")
    expect(block, "command", "block-detail", "block")
    expect(block, "height", block_height, "block")

account = request_json(
    f"/v1/xriq/private-devnet/accounts/{urllib.parse.quote(alice_address, safe='')}",
    "account.json",
)
expect(account, "command", "account-detail", "account")
expect(account, "address", alice_address, "account")

mempool = request_json("/v1/xriq/private-devnet/mempool", "mempool.json")
expect(mempool, "command", "mempool-detail", "mempool")

transaction_status = "skipped"
if tx_hash:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", tx_hash):
        fail("BIBER_XRIQ_API_SMOKE_TX_HASH must be 64 hex characters when set")
    transaction = request_json(
        f"/v1/xriq/private-devnet/transactions/{tx_hash}",
        "transaction.json",
    )
    expect(transaction, "command", "transaction-detail", "transaction")
    transaction_status = str(transaction.get("status"))

summary = {
    "ok": "biber-xriq-api-smoke",
    "artifacts": str(artifact_dir),
    "status_height": status.get("current_height"),
    "explorer_height": explorer.get("current_height"),
    "block_height": block_height,
    "account": account.get("address"),
    "mempool_pending": mempool.get("pending_count"),
    "transaction_status": transaction_status,
}
write_artifact("summary.json", summary)
print(json.dumps(summary, sort_keys=True))
PY
