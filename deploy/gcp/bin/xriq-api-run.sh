#!/usr/bin/env bash
# Run the XRIQ staging-devnet API as a container. Invoked by the systemd unit.
# Reads configuration from /etc/xriq/xriq.env (written by vm-bootstrap.sh).
set -euo pipefail

ENV_FILE=/etc/xriq/xriq.env
# shellcheck source=/dev/null
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

: "${XRIQ_IMAGE:?XRIQ_IMAGE must be set in $ENV_FILE}"
: "${XRIQ_ALICE_BALANCE:=100000000}"
: "${XRIQ_ENVIRONMENT:=staging-devnet}"
: "${XRIQ_API_BIND:=0.0.0.0:8090}"
: "${XRIQ_API_MUTATION_FLAGS:=}"

# Host networking lets the container bind on the VPC and reach Cloud SQL. The
# API is file-backed; /data is the persistent chain/pending directory.
# XRIQ_API_MUTATION_FLAGS is intentionally unquoted so its flags word-split.
# shellcheck disable=SC2086
exec /usr/bin/docker run --rm --name xriq-api --network host \
  -v /var/lib/xriq:/data \
  "$XRIQ_IMAGE" \
  xriq-api serve-readonly \
  --chain-file /data/chain.bin \
  --pending-file /data/pending.tsv \
  --alice-balance "$XRIQ_ALICE_BALANCE" \
  --bind "$XRIQ_API_BIND" \
  --environment "$XRIQ_ENVIRONMENT" \
  $XRIQ_API_MUTATION_FLAGS
