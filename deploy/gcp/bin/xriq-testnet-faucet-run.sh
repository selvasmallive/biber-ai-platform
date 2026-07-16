#!/usr/bin/env bash
# Run the XRIQ testnet faucet + read API (xriq-api serve-readonly --network
# testnet --enable-local-testnet-faucet) as a container. Invoked by the systemd
# unit. Reads /etc/xriq/xriq.env. Now that build_service is testnet-aware the API
# replays the testnet genesis and restarts cleanly with testnet blocks present.
# TEST-ONLY: valueless test units, no monetary value.
set -euo pipefail

ENV_FILE=/etc/xriq/xriq.env
# shellcheck source=/dev/null
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

: "${XRIQ_IMAGE:?XRIQ_IMAGE must be set in $ENV_FILE}"
: "${XRIQ_TESTNET_CHAIN_FILE:=/data/testnet/chain.bin}"
: "${XRIQ_TESTNET_FAUCET_BIND:=0.0.0.0:8091}"
: "${XRIQ_TESTNET_FAUCET_MAX_PER_WINDOW:=5}"
: "${XRIQ_TESTNET_FAUCET_WINDOW_MS:=60000}"

mkdir -p /var/lib/xriq/testnet

exec /usr/bin/docker run --rm --name xriq-testnet-faucet --network host \
  -v /var/lib/xriq:/data \
  "$XRIQ_IMAGE" \
  xriq-api serve-readonly \
  --network testnet \
  --enable-local-testnet-faucet true \
  --faucet-max-per-window "$XRIQ_TESTNET_FAUCET_MAX_PER_WINDOW" \
  --faucet-window-ms "$XRIQ_TESTNET_FAUCET_WINDOW_MS" \
  --chain-file "$XRIQ_TESTNET_CHAIN_FILE" \
  --bind "$XRIQ_TESTNET_FAUCET_BIND"
