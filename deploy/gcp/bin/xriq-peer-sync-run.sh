#!/usr/bin/env bash
# Pull validated blocks from the testnet seed into this follower's chain file.
# Invoked by the xriq-peer-sync systemd timer (one-shot per tick). Reads
# /etc/xriq/xriq.env. Each imported block is fully re-validated by the node;
# a peer on a different network (e.g. devnet) is rejected by the handshake.
# TEST-ONLY: the native unit has no monetary value.
set -euo pipefail

ENV_FILE=/etc/xriq/xriq.env
# shellcheck source=/dev/null
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

: "${XRIQ_IMAGE:?XRIQ_IMAGE must be set in $ENV_FILE}"
: "${XRIQ_TESTNET_CHAIN_FILE:=/data/testnet/chain.bin}"
: "${XRIQ_TESTNET_SEED_URL:?XRIQ_TESTNET_SEED_URL must be set (e.g. http://SEED_IP:8899)}"
: "${XRIQ_TESTNET_SYNC_MAX_ROUNDS:=64}"

mkdir -p /var/lib/xriq/testnet

exec /usr/bin/docker run --rm --name xriq-peer-sync --network host \
  -v /var/lib/xriq:/data \
  "$XRIQ_IMAGE" \
  xriq-node peer-sync \
  --network testnet \
  --chain-file "$XRIQ_TESTNET_CHAIN_FILE" \
  --peer "$XRIQ_TESTNET_SEED_URL" \
  --max-rounds "$XRIQ_TESTNET_SYNC_MAX_ROUNDS" \
  --format json
