#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

[ -x "${VENV_DIR}/bin/uvicorn" ] || die "uvicorn not found in ${VENV_DIR}. Run scripts/vast_bootstrap_direct.sh first."

stop_api() {
  remove_stale_pid_file "$BIBER_API_PID_FILE"

  if [ ! -f "$BIBER_API_PID_FILE" ]; then
    echo "API: no active pid file"
    return
  fi

  local pid
  pid="$(tr -d '[:space:]' < "$BIBER_API_PID_FILE")"
  echo "Stopping API pid ${pid} ..."
  kill "$pid" 2>/dev/null || true

  for _ in $(seq 1 30); do
    if ! pid_alive "$pid"; then
      rm -f "$BIBER_API_PID_FILE"
      echo "API: stopped"
      return
    fi
    sleep 1
  done

  echo "API: forcing stop"
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$BIBER_API_PID_FILE"
}

start_api() {
  remove_stale_pid_file "$BIBER_API_PID_FILE"

  if pid_file_alive "$BIBER_API_PID_FILE"; then
    echo "API already running with pid $(cat "$BIBER_API_PID_FILE")."
    return
  fi
  if port_listening "$BIBER_API_PORT"; then
    die "Port ${BIBER_API_PORT} is already listening, but ${BIBER_API_PID_FILE} is not active."
  fi

  (
    cd "$ROOT_DIR"
    nohup env \
      HF_HOME="$HF_HOME" \
      PIP_CACHE_DIR="$PIP_CACHE_DIR" \
      "${VENV_DIR}/bin/uvicorn" app.main:app \
        --host "$BIBER_API_HOST" \
        --port "$BIBER_API_PORT" \
      > "$BIBER_API_LOG" 2>&1 < /dev/null &
    echo $! > "$BIBER_API_PID_FILE"
    disown "$(cat "$BIBER_API_PID_FILE")" 2>/dev/null || true
  )
  echo "API pid: $(cat "$BIBER_API_PID_FILE")"
}

stop_api
start_api

echo "Waiting for API at http://127.0.0.1:${BIBER_API_PORT}/health ..."
if ! wait_for_http "http://127.0.0.1:${BIBER_API_PORT}/health" 120; then
  tail -n 120 "$BIBER_API_LOG" || true
  die "API did not become ready."
fi

print_runtime_summary
