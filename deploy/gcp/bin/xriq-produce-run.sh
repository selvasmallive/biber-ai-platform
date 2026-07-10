#!/usr/bin/env bash
# Produce a block on the deployed XRIQ staging-devnet API, but only when there
# are pending transactions. Invoked by the (opt-in) xriq-producer systemd timer.
# Producing empty blocks is intentionally avoided.
#
# Prints only public chain data; no secrets. Requires the API to have
# --enable-local-block-production (the staging default).
set -euo pipefail

API="${XRIQ_API:-http://127.0.0.1:8090}"
PRODUCER="${XRIQ_PRODUCER:-xriqdev1author00000000000}"
MAX_TX="${XRIQ_MAX_TRANSACTIONS:-64}"
RID="cadence-$(date -u +%Y%m%dT%H%M%SZ)"

json_int() { grep -o "\"$1\"[[:space:]]*:[[:space:]]*[0-9]*" | head -1 | grep -o '[0-9]*$'; }

PENDING="$(curl -fsS "$API/api/v1/mempool?limit=1" | json_int pending_count || true)"
if [ "${PENDING:-0}" -eq 0 ] 2>/dev/null; then
  echo "no pending transactions; skipping block production"
  exit 0
fi

echo "producing a block for ${PENDING} pending transaction(s)"
curl -fsS -X POST \
  "$API/api/v1/blocks/produce?local_request_id=${RID}&producer=${PRODUCER}&max_transactions=${MAX_TX}&timestamp_ms=$(date -u +%s)000"
echo
