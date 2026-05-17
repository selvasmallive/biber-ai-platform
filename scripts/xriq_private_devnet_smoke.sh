#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
XRIQ_DIR="${REPO_ROOT}/xriq"

SMOKE_ID="${XRIQ_SMOKE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
ARTIFACT_DIR="${XRIQ_SMOKE_ARTIFACT_DIR:-${XRIQ_DIR}/target/xriq-private-devnet-smoke-${SMOKE_ID}}"
DRAFT_FILE="${ARTIFACT_DIR}/wallet-transfer-draft.txt"
CHAIN_FILE="${ARTIFACT_DIR}/chain.bin"

require_contains() {
  local label="$1"
  local haystack="$2"
  local needle="$3"

  if ! printf '%s\n' "$haystack" | grep -Fq -- "$needle"; then
    echo "error=${label} missing expected text: ${needle}" >&2
    echo "--- ${label} output ---" >&2
    printf '%s\n' "$haystack" >&2
    exit 1
  fi
}

run_xriq() {
  (cd "$XRIQ_DIR" && cargo run -q "$@")
}

mkdir -p "$ARTIFACT_DIR"

echo "XRIQ private-devnet smoke"
echo "artifacts=${ARTIFACT_DIR}"

wallet_output="$(
  run_xriq -p xriq-wallet -- transfer \
    --chain-id xriq-devnet \
    --from xriqdev1alice00000000000 \
    --to xriqdev1bobbb00000000000 \
    --amount 25 \
    --fee 2 \
    --nonce 0 \
    --expires-at-height 100
)"
printf '%s\n' "$wallet_output" > "$DRAFT_FILE"
require_contains "wallet draft" "$wallet_output" "warning=private-devnet-test-identity-only"
require_contains "wallet draft" "$wallet_output" "chain_id=xriq-devnet"
require_contains "wallet draft" "$wallet_output" "signature_bytes="

mempool_output="$(
  run_xriq -p xriq-node -- mempool-detail \
    --chain-file "$CHAIN_FILE" \
    --draft-file "$DRAFT_FILE" \
    --alice-balance 100
)"
require_contains "mempool-detail" "$mempool_output" "mempool pending: 1"
require_contains "mempool-detail" "$mempool_output" "xriqdev1alice00000000000 -> xriqdev1bobbb00000000000"
require_contains "mempool-detail" "$mempool_output" "amount=25"
require_contains "mempool-detail" "$mempool_output" "fee=2"

produce_output="$(
  run_xriq -p xriq-node -- produce-draft-block \
    --chain-file "$CHAIN_FILE" \
    --draft-file "$DRAFT_FILE" \
    --alice-balance 100 \
    --timestamp-ms 1000
)"
require_contains "produce-draft-block" "$produce_output" "warning=private-devnet-only-no-public-token"
require_contains "produce-draft-block" "$produce_output" "current_height=1"
require_contains "produce-draft-block" "$produce_output" "stored_blocks=1"

overview_output="$(
  run_xriq -p xriq-node -- explorer-overview \
    --chain-file "$CHAIN_FILE" \
    --alice-balance 100 \
    --limit 5
)"
require_contains "explorer-overview" "$overview_output" "XRIQ Private Devnet Explorer"
require_contains "explorer-overview" "$overview_output" "current height: 1"
require_contains "explorer-overview" "$overview_output" "stored blocks: 1, pending transactions: 0"

block_output="$(
  run_xriq -p xriq-node -- block-detail \
    --chain-file "$CHAIN_FILE" \
    --alice-balance 100 \
    --height 1
)"
require_contains "block-detail" "$block_output" "block 1"
require_contains "block-detail" "$block_output" "transactions: 1"
require_contains "block-detail" "$block_output" "xriqdev1alice00000000000 -> xriqdev1bobbb00000000000"
require_contains "block-detail" "$block_output" "amount=25"
require_contains "block-detail" "$block_output" "fee=2"

account_output="$(
  run_xriq -p xriq-node -- account-detail \
    --chain-file "$CHAIN_FILE" \
    --alice-balance 100 \
    --address xriqdev1alice00000000000
)"
require_contains "account-detail" "$account_output" "account xriqdev1alice00000000000"
require_contains "account-detail" "$account_output" "balance: 73"
require_contains "account-detail" "$account_output" "nonce: 1"

echo "ok=xriq-private-devnet-smoke"
echo "draft=${DRAFT_FILE}"
echo "chain=${CHAIN_FILE}"
