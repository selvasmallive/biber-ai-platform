#!/usr/bin/env bash
# Run an XRIQ testnet node (serve-readonly --network testnet) as a container.
# Invoked by the xriq-testnet-node systemd unit. Reads /etc/xriq/xriq.env.
# TEST-ONLY: the native unit has no monetary value; this runs the test-only
# signature scheme (production crypto is a separate migration).
set -euo pipefail

ENV_FILE=/etc/xriq/xriq.env
# shellcheck source=/dev/null
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

: "${XRIQ_IMAGE:?XRIQ_IMAGE must be set in $ENV_FILE}"
: "${XRIQ_TESTNET_CHAIN_FILE:=/data/testnet/chain.bin}"
: "${XRIQ_TESTNET_BIND:=0.0.0.0:8899}"
# Extra node flags, e.g. "--node-seed <seed> --peers-file /data/testnet/peers".
: "${XRIQ_TESTNET_NODE_FLAGS:=}"

mkdir -p /var/lib/xriq/testnet

# Host networking lets the node bind on the VPC. The file-backed testnet chain
# lives under /data (mounted from /var/lib/xriq). XRIQ_TESTNET_NODE_FLAGS is
# intentionally unquoted so its flags word-split.
# shellcheck disable=SC2086
exec /usr/bin/docker run --rm --name xriq-testnet-node --network host \
  -v /var/lib/xriq:/data \
  "$XRIQ_IMAGE" \
  xriq-node serve-readonly \
  --network testnet \
  --chain-file "$XRIQ_TESTNET_CHAIN_FILE" \
  --bind "$XRIQ_TESTNET_BIND" \
  $XRIQ_TESTNET_NODE_FLAGS
