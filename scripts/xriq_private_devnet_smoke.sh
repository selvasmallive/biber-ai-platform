#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
XRIQ_DIR="${REPO_ROOT}/xriq"

SMOKE_ID="${XRIQ_SMOKE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
ARTIFACT_DIR="${XRIQ_SMOKE_ARTIFACT_DIR:-${XRIQ_DIR}/target/xriq-private-devnet-smoke-${SMOKE_ID}}"
DRAFT_FILE="${ARTIFACT_DIR}/wallet-transfer-draft.txt"
WALLET_JSON_FILE="${ARTIFACT_DIR}/wallet-transfer-submit.json"
CHAIN_FILE="${ARTIFACT_DIR}/chain.bin"
HTTP_JSON_CHAIN_FILE="${ARTIFACT_DIR}/http-json-chain.bin"
HTTP_PENDING_CHAIN_FILE="${ARTIFACT_DIR}/http-pending-chain.bin"
HTTP_PENDING_FILE="${ARTIFACT_DIR}/http-pending-mempool.tsv"
MEMPOOL_JSON_FILE="${ARTIFACT_DIR}/mempool-detail.json"
PENDING_TRANSACTION_JSON_FILE="${ARTIFACT_DIR}/pending-transaction-detail.json"
CONFIRMED_TRANSACTION_JSON_FILE="${ARTIFACT_DIR}/confirmed-transaction-detail.json"
OVERVIEW_JSON_FILE="${ARTIFACT_DIR}/explorer-overview.json"
ACCOUNT_JSON_FILE="${ARTIFACT_DIR}/account-detail.json"
STATUS_ERROR_JSON_FILE="${ARTIFACT_DIR}/status-error.json"
HTTP_JSON_SUBMIT_FILE="${ARTIFACT_DIR}/http-json-submit.json"
HTTP_JSON_TRANSACTION_FILE="${ARTIFACT_DIR}/http-json-transaction.json"
HTTP_JSON_ACCOUNT_FILE="${ARTIFACT_DIR}/http-json-account.json"
HTTP_PENDING_SUBMIT_FILE="${ARTIFACT_DIR}/http-pending-submit.json"
HTTP_PENDING_MEMPOOL_FILE="${ARTIFACT_DIR}/http-pending-mempool.json"
HTTP_PENDING_TRANSACTION_FILE="${ARTIFACT_DIR}/http-pending-transaction.json"

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

start_http_server() {
  local chain_file="$1"
  local port="$2"
  local log_file="$3"
  local pending_file="${4:-}"

  (
    cd "$XRIQ_DIR"
    if [ -n "$pending_file" ]; then
      cargo run -q -p xriq-node -- serve-private \
        --chain-file "$chain_file" \
        --pending-file "$pending_file" \
        --alice-balance 100 \
        --bind "127.0.0.1:${port}"
    else
      cargo run -q -p xriq-node -- serve-private \
        --chain-file "$chain_file" \
        --alice-balance 100 \
        --bind "127.0.0.1:${port}"
    fi
  ) > "$log_file" 2>&1 &
  HTTP_SERVER_PID=$!
}

stop_http_server() {
  if [ -n "${HTTP_SERVER_PID:-}" ]; then
    kill "$HTTP_SERVER_PID" >/dev/null 2>&1 || true
    wait "$HTTP_SERVER_PID" >/dev/null 2>&1 || true
    HTTP_SERVER_PID=""
  fi
}

wait_for_http_server() {
  local port="$1"

  for _ in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done

  echo "error=http server did not become ready on port ${port}" >&2
  exit 1
}

mkdir -p "$ARTIFACT_DIR"
trap stop_http_server EXIT

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

wallet_json_output="$(
  run_xriq -p xriq-wallet -- transfer \
    --chain-id xriq-devnet \
    --from xriqdev1alice00000000000 \
    --to xriqdev1bobbb00000000000 \
    --amount 25 \
    --fee 2 \
    --nonce 0 \
    --expires-at-height 100 \
    --format json
)"
printf '%s\n' "$wallet_json_output" > "$WALLET_JSON_FILE"
require_contains "wallet transfer json" "$wallet_json_output" '"format_version": "xriq-node-transfer-submit-v1"'
require_contains "wallet transfer json" "$wallet_json_output" '"warning": "private-devnet-test-identity-only"'
require_contains "wallet transfer json" "$wallet_json_output" '"chain_id": "xriq-devnet"'
require_contains "wallet transfer json" "$wallet_json_output" '"amount_base_units": "25"'
require_contains "wallet transfer json" "$wallet_json_output" '"fee_base_units": "2"'
require_contains "wallet transfer json" "$wallet_json_output" '"signature_bytes":'

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

mempool_json_output="$(
  run_xriq -p xriq-node -- mempool-detail \
    --chain-file "$CHAIN_FILE" \
    --draft-file "$DRAFT_FILE" \
    --alice-balance 100 \
    --format json
)"
printf '%s\n' "$mempool_json_output" > "$MEMPOOL_JSON_FILE"
require_contains "mempool-detail json" "$mempool_json_output" '"format_version": "xriq-node-json-v1"'
require_contains "mempool-detail json" "$mempool_json_output" '"command": "mempool-detail"'
require_contains "mempool-detail json" "$mempool_json_output" '"pending_count": 1'
require_contains "mempool-detail json" "$mempool_json_output" '"amount_base_units": "25"'
require_contains "mempool-detail json" "$mempool_json_output" '"fee_base_units": "2"'

pending_tx_hash="$(printf '%s\n' "$mempool_json_output" | grep -m1 '"tx_hash"' | cut -d '"' -f4)"
pending_transaction_output="$(
  run_xriq -p xriq-node -- transaction-detail \
    --chain-file "$CHAIN_FILE" \
    --draft-file "$DRAFT_FILE" \
    --alice-balance 100 \
    --tx-hash "$pending_tx_hash" \
    --format json
)"
printf '%s\n' "$pending_transaction_output" > "$PENDING_TRANSACTION_JSON_FILE"
require_contains "pending transaction detail" "$pending_transaction_output" '"command": "transaction-detail"'
require_contains "pending transaction detail" "$pending_transaction_output" '"status": "pending"'
require_contains "pending transaction detail" "$pending_transaction_output" '"received_order": 0'
require_contains "pending transaction detail" "$pending_transaction_output" '"amount_base_units": "25"'

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

confirmed_transaction_output="$(
  run_xriq -p xriq-node -- transaction-detail \
    --chain-file "$CHAIN_FILE" \
    --alice-balance 100 \
    --tx-hash "$pending_tx_hash" \
    --format json
)"
printf '%s\n' "$confirmed_transaction_output" > "$CONFIRMED_TRANSACTION_JSON_FILE"
require_contains "confirmed transaction detail" "$confirmed_transaction_output" '"command": "transaction-detail"'
require_contains "confirmed transaction detail" "$confirmed_transaction_output" '"status": "confirmed"'
require_contains "confirmed transaction detail" "$confirmed_transaction_output" '"block_height": 1'
require_contains "confirmed transaction detail" "$confirmed_transaction_output" '"amount_base_units": "25"'

overview_output="$(
  run_xriq -p xriq-node -- explorer-overview \
    --chain-file "$CHAIN_FILE" \
    --alice-balance 100 \
    --limit 5
)"
require_contains "explorer-overview" "$overview_output" "XRIQ Private Devnet Explorer"
require_contains "explorer-overview" "$overview_output" "current height: 1"
require_contains "explorer-overview" "$overview_output" "stored blocks: 1, pending transactions: 0"

overview_json_output="$(
  run_xriq -p xriq-node -- explorer-overview \
    --chain-file "$CHAIN_FILE" \
    --alice-balance 100 \
    --limit 5 \
    --format json
)"
printf '%s\n' "$overview_json_output" > "$OVERVIEW_JSON_FILE"
require_contains "explorer-overview json" "$overview_json_output" '"command": "explorer-overview"'
require_contains "explorer-overview json" "$overview_json_output" '"latest_blocks": ['
require_contains "explorer-overview json" "$overview_json_output" '"height": 1'
require_contains "explorer-overview json" "$overview_json_output" '"transaction_count": 1'

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

account_json_output="$(
  run_xriq -p xriq-node -- account-detail \
    --chain-file "$CHAIN_FILE" \
    --alice-balance 100 \
    --address xriqdev1alice00000000000 \
    --format json
)"
printf '%s\n' "$account_json_output" > "$ACCOUNT_JSON_FILE"
require_contains "account-detail json" "$account_json_output" '"command": "account-detail"'
require_contains "account-detail json" "$account_json_output" '"address": "xriqdev1alice00000000000"'
require_contains "account-detail json" "$account_json_output" '"balance_base_units": "73"'
require_contains "account-detail json" "$account_json_output" '"nonce": 1'

set +e
json_error_output="$(run_xriq -p xriq-node -- status --format json 2>&1)"
json_error_status=$?
set -e
printf '%s\n' "$json_error_output" > "$STATUS_ERROR_JSON_FILE"
if [ "$json_error_status" -eq 0 ]; then
  echo "error=status json error unexpectedly succeeded" >&2
  printf '%s\n' "$json_error_output" >&2
  exit 1
fi
require_contains "status json error" "$json_error_output" '"ok": false'
require_contains "status json error" "$json_error_output" '"command": "status"'
require_contains "status json error" "$json_error_output" '"code": "missing_flag"'
require_contains "status json error" "$json_error_output" '"message": "missing required flag: --chain-file"'

HTTP_PORT="${XRIQ_SMOKE_HTTP_PORT:-18797}"
HTTP_LOG_FILE="${ARTIFACT_DIR}/http-json-server.log"
start_http_server "$HTTP_JSON_CHAIN_FILE" "$HTTP_PORT" "$HTTP_LOG_FILE"
wait_for_http_server "$HTTP_PORT"

http_submit_output="$(
  curl -fsS \
    -X POST \
    -H 'Content-Type: application/json' \
    --data-binary "@${WALLET_JSON_FILE}" \
    "http://127.0.0.1:${HTTP_PORT}/v1/transactions"
)"
printf '%s\n' "$http_submit_output" > "$HTTP_JSON_SUBMIT_FILE"
require_contains "http json submit" "$http_submit_output" '"command": "submit-transaction"'
require_contains "http json submit" "$http_submit_output" '"current_height": 1'
require_contains "http json submit" "$http_submit_output" '"applied_transactions": 1'

http_tx_hash="$(printf '%s\n' "$http_submit_output" | grep -m1 '"transaction_hash"' | cut -d '"' -f4)"
http_transaction_output="$(
  curl -fsS "http://127.0.0.1:${HTTP_PORT}/v1/transactions/${http_tx_hash}"
)"
printf '%s\n' "$http_transaction_output" > "$HTTP_JSON_TRANSACTION_FILE"
require_contains "http json transaction detail" "$http_transaction_output" '"command": "transaction-detail"'
require_contains "http json transaction detail" "$http_transaction_output" '"status": "confirmed"'
require_contains "http json transaction detail" "$http_transaction_output" '"amount_base_units": "25"'

http_account_output="$(
  curl -fsS "http://127.0.0.1:${HTTP_PORT}/v1/accounts/xriqdev1alice00000000000"
)"
printf '%s\n' "$http_account_output" > "$HTTP_JSON_ACCOUNT_FILE"
require_contains "http json account detail" "$http_account_output" '"command": "account-detail"'
require_contains "http json account detail" "$http_account_output" '"balance_base_units": "73"'

stop_http_server

HTTP_PENDING_LOG_FILE="${ARTIFACT_DIR}/http-pending-server.log"
start_http_server "$HTTP_PENDING_CHAIN_FILE" "$HTTP_PORT" "$HTTP_PENDING_LOG_FILE" "$HTTP_PENDING_FILE"
wait_for_http_server "$HTTP_PORT"

http_pending_submit_output="$(
  curl -fsS \
    -X POST \
    -H 'Content-Type: application/json' \
    --data-binary "@${WALLET_JSON_FILE}" \
    "http://127.0.0.1:${HTTP_PORT}/v1/mempool"
)"
printf '%s\n' "$http_pending_submit_output" > "$HTTP_PENDING_SUBMIT_FILE"
require_contains "http pending submit" "$http_pending_submit_output" '"command": "transaction-detail"'
require_contains "http pending submit" "$http_pending_submit_output" '"status": "pending"'
require_contains "http pending submit" "$http_pending_submit_output" '"amount_base_units": "25"'

http_pending_hash="$(printf '%s\n' "$http_pending_submit_output" | grep -m1 '"tx_hash"' | cut -d '"' -f4)"
http_pending_mempool_output="$(
  curl -fsS "http://127.0.0.1:${HTTP_PORT}/v1/mempool"
)"
printf '%s\n' "$http_pending_mempool_output" > "$HTTP_PENDING_MEMPOOL_FILE"
require_contains "http pending mempool" "$http_pending_mempool_output" '"command": "mempool-detail"'
require_contains "http pending mempool" "$http_pending_mempool_output" '"pending_count": 1'
require_contains "http pending mempool" "$http_pending_mempool_output" '"amount_base_units": "25"'

http_pending_transaction_output="$(
  curl -fsS "http://127.0.0.1:${HTTP_PORT}/v1/transactions/${http_pending_hash}"
)"
printf '%s\n' "$http_pending_transaction_output" > "$HTTP_PENDING_TRANSACTION_FILE"
require_contains "http pending transaction" "$http_pending_transaction_output" '"command": "transaction-detail"'
require_contains "http pending transaction" "$http_pending_transaction_output" '"status": "pending"'
require_contains "http pending transaction" "$http_pending_transaction_output" '"amount_base_units": "25"'

stop_http_server

echo "ok=xriq-private-devnet-smoke"
echo "draft=${DRAFT_FILE}"
echo "wallet_json=${WALLET_JSON_FILE}"
echo "chain=${CHAIN_FILE}"
echo "mempool_json=${MEMPOOL_JSON_FILE}"
echo "pending_transaction_json=${PENDING_TRANSACTION_JSON_FILE}"
echo "confirmed_transaction_json=${CONFIRMED_TRANSACTION_JSON_FILE}"
echo "overview_json=${OVERVIEW_JSON_FILE}"
echo "account_json=${ACCOUNT_JSON_FILE}"
echo "status_error_json=${STATUS_ERROR_JSON_FILE}"
echo "http_json_chain=${HTTP_JSON_CHAIN_FILE}"
echo "http_json_submit=${HTTP_JSON_SUBMIT_FILE}"
echo "http_json_transaction=${HTTP_JSON_TRANSACTION_FILE}"
echo "http_json_account=${HTTP_JSON_ACCOUNT_FILE}"
echo "http_pending_chain=${HTTP_PENDING_CHAIN_FILE}"
echo "http_pending_store=${HTTP_PENDING_FILE}"
echo "http_pending_submit=${HTTP_PENDING_SUBMIT_FILE}"
echo "http_pending_mempool=${HTTP_PENDING_MEMPOOL_FILE}"
echo "http_pending_transaction=${HTTP_PENDING_TRANSACTION_FILE}"
