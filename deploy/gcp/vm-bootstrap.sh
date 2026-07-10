#!/usr/bin/env bash
# Bootstrap the XRIQ staging-devnet services on the Compute Engine node VM.
# Run as root (sudo) on the VM, from the deploy/gcp directory of the repo.
#
# It installs Docker, authenticates to Artifact Registry, pulls the image,
# fetches the DB password from Secret Manager into a root-only env file,
# initializes the chain (deterministic genesis), installs the run wrappers and
# systemd units, and starts the API service and indexer timer.
#
# No secret is printed. The env file it writes (with the DB URL) is mode 600 and
# must never be committed.
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
: "${REGION:=northamerica-northeast2}"
: "${IMAGE:?set IMAGE (region-docker.pkg.dev/PROJECT/REPO/xriq:TAG)}"
: "${DB_SECRET:=xriq-staging-devnet-db-password}"
: "${DB_HOST:=10.103.0.3}"
: "${DB_USER:=xriqpgadmin}"
: "${DB_NAME:=xriq}"
: "${ALICE_BALANCE:=100000000}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[1/8] Installing Docker if needed"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y --no-install-recommends docker.io
fi
systemctl enable --now docker

echo "[2/8] Authenticating Docker to Artifact Registry"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "[3/8] Pulling image"
docker pull "$IMAGE"

echo "[4/8] Creating data directory and config directory"
# The container runs as uid 10001; it must own the mounted data directory.
install -d -m 0750 /var/lib/xriq
chown 10001:10001 /var/lib/xriq
install -d -m 0755 /etc/xriq

echo "[5/8] Writing /etc/xriq/xriq.env (DB password from Secret Manager)"
DB_PASS="$(gcloud secrets versions access latest --secret="$DB_SECRET" --project="$PROJECT_ID")"
umask 077
cat > /etc/xriq/xriq.env <<EOF
XRIQ_IMAGE=$IMAGE
XRIQ_ENVIRONMENT=staging-devnet
XRIQ_ALICE_BALANCE=$ALICE_BALANCE
XRIQ_API_BIND=0.0.0.0:8090
XRIQ_API_MUTATION_FLAGS="--enable-local-wallet-send true --enable-local-wallet-submit-signed true --enable-local-block-production true"
XRIQ_POSTGRES_URL=postgresql://${DB_USER}:${DB_PASS}@${DB_HOST}:5432/${DB_NAME}
EOF
chmod 600 /etc/xriq/xriq.env
unset DB_PASS

echo "[6/8] Initializing chain file (deterministic genesis) if missing"
if [ ! -f /var/lib/xriq/chain.bin ]; then
  docker run --rm -u 10001:10001 -v /var/lib/xriq:/data "$IMAGE" \
    xriq-node status --chain-file /data/chain.bin --alice-balance "$ALICE_BALANCE" >/dev/null
fi

echo "[7/8] Installing run wrappers and systemd units"
install -m 0755 "$SCRIPT_DIR/bin/xriq-api-run.sh" /usr/local/bin/xriq-api-run.sh
install -m 0755 "$SCRIPT_DIR/bin/xriq-indexer-run.sh" /usr/local/bin/xriq-indexer-run.sh
install -m 0755 "$SCRIPT_DIR/bin/xriq-produce-run.sh" /usr/local/bin/xriq-produce-run.sh
install -m 0644 "$SCRIPT_DIR/systemd/xriq-api.service" /etc/systemd/system/xriq-api.service
install -m 0644 "$SCRIPT_DIR/systemd/xriq-indexer.service" /etc/systemd/system/xriq-indexer.service
install -m 0644 "$SCRIPT_DIR/systemd/xriq-indexer.timer" /etc/systemd/system/xriq-indexer.timer
# The block-producer timer is installed but left disabled (opt-in): enable with
# `systemctl enable --now xriq-producer.timer` to auto-produce blocks when the
# mempool is non-empty.
install -m 0644 "$SCRIPT_DIR/systemd/xriq-producer.service" /etc/systemd/system/xriq-producer.service
install -m 0644 "$SCRIPT_DIR/systemd/xriq-producer.timer" /etc/systemd/system/xriq-producer.timer
systemctl daemon-reload

echo "[8/8] Enabling and (re)starting services"
systemctl enable xriq-api.service xriq-indexer.timer
# restart picks up a new image or env on re-runs; it also starts if stopped.
systemctl restart xriq-api.service
systemctl restart xriq-indexer.timer

echo "Done. Check: systemctl status xriq-api; journalctl -u xriq-api -n 50"
