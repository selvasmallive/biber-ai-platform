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
: "${XRIQ_POSTGRES_URL:=}"

# When a Cloud SQL URL is configured, serve the Postgres read model from it
# (the URL, with password, is passed only via the container environment).
if [ -n "$XRIQ_POSTGRES_URL" ]; then
  : "${XRIQ_API_POSTGRES_FLAGS:=--postgres-database-url-env XRIQ_POSTGRES_URL}"
else
  XRIQ_API_POSTGRES_FLAGS=""
fi

# Host networking lets the container bind on the VPC and reach Cloud SQL. The
# file-backed chain/pending state lives under /data.
# XRIQ_API_MUTATION_FLAGS and XRIQ_API_POSTGRES_FLAGS are intentionally unquoted
# so their flags word-split.
# shellcheck disable=SC2086
exec /usr/bin/docker run --rm --name xriq-api --network host \
  -v /var/lib/xriq:/data \
  -e XRIQ_POSTGRES_URL="$XRIQ_POSTGRES_URL" \
  "$XRIQ_IMAGE" \
  xriq-api serve-readonly \
  --chain-file /data/chain.bin \
  --pending-file /data/pending.tsv \
  --alice-balance "$XRIQ_ALICE_BALANCE" \
  --bind "$XRIQ_API_BIND" \
  --environment "$XRIQ_ENVIRONMENT" \
  $XRIQ_API_MUTATION_FLAGS \
  $XRIQ_API_POSTGRES_FLAGS
