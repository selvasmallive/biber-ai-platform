#!/usr/bin/env bash
# Live-chain smoke for the deployed XRIQ staging-devnet. Runs ON the node VM
# against the local API (127.0.0.1:8090): send a local transfer (server-side
# test signing), produce a block, and report the new height. Re-runnable: it
# reads the sender's current nonce each time.
#
# It prints only public chain data (addresses, amounts, heights, hashes); no
# secrets. Requires the API to have --enable-local-wallet-send and
# --enable-local-block-production (the staging defaults).
set -euo pipefail

API="${XRIQ_API:-http://127.0.0.1:8090}"
ALICE="${XRIQ_FROM:-xriqdev1alice00000000000}"
BOB="${XRIQ_TO:-xriqdev1bobbb00000000000}"
PRODUCER="${XRIQ_PRODUCER:-xriqdev1author00000000000}"
AMOUNT="${XRIQ_AMOUNT:-5}"
FEE="${XRIQ_FEE:-2}"
RID="live-smoke-$(date -u +%Y%m%dT%H%M%SZ)"

json_int() { grep -o "\"$1\":[0-9]*" | head -1 | grep -o '[0-9]*'; }

HEIGHT="$(curl -fsS "$API/api/v1/network" | json_int current_height)"
NONCE="$(curl -fsS "$API/api/v1/wallet/accounts/$ALICE/balance" | json_int nonce)"
EXPIRES=$((HEIGHT + 100))
echo "before: height=$HEIGHT sender_nonce=$NONCE"

echo "1) send $AMOUNT from alice to bob (server-side test signing -> pending)"
curl -fsS -X POST \
  "$API/api/v1/wallet/transfers/send?local_request_id=${RID}-send&from_address=${ALICE}&to_address=${BOB}&amount_base_units=${AMOUNT}&fee_base_units=${FEE}&nonce=${NONCE}&expires_at_height=${EXPIRES}"
echo

echo "2) produce a block"
curl -fsS -X POST \
  "$API/api/v1/blocks/produce?local_request_id=${RID}-block&producer=${PRODUCER}&max_transactions=4&timestamp_ms=$(date -u +%s)000"
echo

NEW_HEIGHT="$(curl -fsS "$API/api/v1/network" | json_int current_height)"
echo "after: height=$NEW_HEIGHT"
if [ "$NEW_HEIGHT" -le "$HEIGHT" ]; then
  echo "ERROR: height did not advance" >&2
  exit 1
fi
echo "OK: chain advanced from $HEIGHT to $NEW_HEIGHT"
