#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ADMIN_API_KEY_VALUE="$(env_or_file BIBER_ADMIN_API_KEY)"
API_KEY_STORE_PATH="$(env_or_file BIBER_API_KEY_STORE_PATH)"
if [ -z "$API_KEY_STORE_PATH" ]; then
  API_KEY_STORE_PATH="/workspace/outputs/biber-api-keys.json"
fi

FASTAPI_RESTART=true
if [ "${BIBER_SKIP_API_RESTART:-0}" = "1" ]; then
  FASTAPI_RESTART=false
fi

cat <<EOF
BIBER admin API-key configuration plan
repo_root: ${ROOT_DIR}
api_url: http://127.0.0.1:${BIBER_API_PORT}
admin_key_configured: $([ -n "$ADMIN_API_KEY_VALUE" ] && echo true || echo false)
api_key_store_path: ${API_KEY_STORE_PATH}
persist_admin_key: ${BIBER_PERSIST_ADMIN_API_KEY:-0}
fastapi_restart: ${FASTAPI_RESTART}
approval_required: BIBER_CONFIGURE_ADMIN_API_KEY_APPROVED=1
EOF

[ -n "$ADMIN_API_KEY_VALUE" ] || die "BIBER_ADMIN_API_KEY is required in env or ${ROOT_DIR}/.env."

if [ "${BIBER_CONFIGURE_ADMIN_API_KEY_APPROVED:-0}" != "1" ]; then
  cat <<EOF

Dry run only. To configure admin API-key support and restart only FastAPI,
rerun with:

  BIBER_CONFIGURE_ADMIN_API_KEY_APPROVED=1 bash scripts/vast_configure_admin_api_key.sh

Set BIBER_PERSIST_ADMIN_API_KEY=1 only when you intentionally want the admin
key saved into ${ROOT_DIR}/.env on the Vast volume. The key is never printed.
EOF
  exit 0
fi

ensure_runtime_dirs
mkdir -p "$(dirname "$API_KEY_STORE_PATH")"

set_env_value BIBER_API_KEY_STORE_PATH "$API_KEY_STORE_PATH"
export BIBER_API_KEY_STORE_PATH="$API_KEY_STORE_PATH"
export BIBER_ADMIN_API_KEY="$ADMIN_API_KEY_VALUE"

if [ "${BIBER_PERSIST_ADMIN_API_KEY:-0}" = "1" ]; then
  set_env_value BIBER_ADMIN_API_KEY "$ADMIN_API_KEY_VALUE"
fi

if [ "$FASTAPI_RESTART" != true ]; then
  cat <<EOF

Configured BIBER admin API-key environment values. FastAPI restart was skipped;
restart BIBER FastAPI before using /v1/admin/api-keys.
EOF
  exit 0
fi

[ -x "${VENV_DIR}/bin/uvicorn" ] || die "uvicorn not found at ${VENV_DIR}/bin/uvicorn. Run scripts/vast_bootstrap_direct.sh first."

log "Restarting BIBER FastAPI only"
if pid_file_alive "$BIBER_API_PID_FILE"; then
  api_pid="$(tr -d '[:space:]' < "$BIBER_API_PID_FILE")"
  echo "Stopping API pid ${api_pid} ..."
  kill "$api_pid" 2>/dev/null || true
  for _ in $(seq 1 30); do
    if ! pid_alive "$api_pid"; then
      rm -f "$BIBER_API_PID_FILE"
      break
    fi
    sleep 1
  done
fi

remove_stale_pid_file "$BIBER_API_PID_FILE"
if port_listening "$BIBER_API_PORT"; then
  die "Port ${BIBER_API_PORT} is still listening; refusing to start a duplicate API."
fi

(
  cd "$ROOT_DIR"
  nohup env \
    HF_HOME="$HF_HOME" \
    PIP_CACHE_DIR="$PIP_CACHE_DIR" \
    BIBER_ADMIN_API_KEY="$BIBER_ADMIN_API_KEY" \
    BIBER_API_KEY_STORE_PATH="$BIBER_API_KEY_STORE_PATH" \
    "${VENV_DIR}/bin/uvicorn" app.main:app \
      --host "$BIBER_API_HOST" \
      --port "$BIBER_API_PORT" \
    > "$BIBER_API_LOG" 2>&1 < /dev/null &
  echo $! > "$BIBER_API_PID_FILE"
  disown "$(cat "$BIBER_API_PID_FILE")" 2>/dev/null || true
)

echo "API pid: $(cat "$BIBER_API_PID_FILE")"
echo "Waiting for API at http://127.0.0.1:${BIBER_API_PORT}/health ..."
if ! wait_for_http "http://127.0.0.1:${BIBER_API_PORT}/health" 120; then
  tail -n 120 "$BIBER_API_LOG" || true
  die "API did not become ready after admin API-key configuration."
fi

cat <<EOF

Configured BIBER admin API-key support and restarted FastAPI.
Admin key: configured but not printed
User key store: ${API_KEY_STORE_PATH}

Use the admin key only to issue/list/revoke user API keys. External clients
should receive per-user keys, not the admin key or bootstrap key.
EOF
