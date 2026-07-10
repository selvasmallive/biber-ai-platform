#!/usr/bin/env bash
# Index the local chain into Cloud SQL. Invoked by the systemd indexer service
# (run periodically by its timer). The DB URL (with password) is passed only via
# the environment, never on the command line, so it does not appear in `ps`.
set -euo pipefail

ENV_FILE=/etc/xriq/xriq.env
# shellcheck source=/dev/null
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

: "${XRIQ_IMAGE:?XRIQ_IMAGE must be set in $ENV_FILE}"
: "${XRIQ_ALICE_BALANCE:=100000000}"
: "${XRIQ_POSTGRES_URL:?XRIQ_POSTGRES_URL must be set in $ENV_FILE}"

exec /usr/bin/docker run --rm --name xriq-indexer --network host \
  -v /var/lib/xriq:/data \
  -e XRIQ_POSTGRES_URL="$XRIQ_POSTGRES_URL" \
  "$XRIQ_IMAGE" \
  xriq-indexer apply-postgres \
  --chain-file /data/chain.bin \
  --alice-balance "$XRIQ_ALICE_BALANCE" \
  --database-url-env XRIQ_POSTGRES_URL \
  --dry-run false
