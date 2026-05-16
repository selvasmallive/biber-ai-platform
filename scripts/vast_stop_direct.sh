#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    echo "${name}: no pid file"
    return
  fi

  local pid
  pid="$(tr -d '[:space:]' < "$pid_file")"
  if ! pid_alive "$pid"; then
    echo "${name}: stale pid ${pid}"
    rm -f "$pid_file"
    return
  fi

  echo "Stopping ${name} pid ${pid} ..."
  kill "$pid" 2>/dev/null || true

  for _ in $(seq 1 30); do
    if ! pid_alive "$pid"; then
      rm -f "$pid_file"
      echo "${name}: stopped"
      return
    fi
    sleep 1
  done

  echo "${name}: forcing stop"
  kill -9 "$pid" 2>/dev/null || true
  rm -f "$pid_file"
}

stop_pid_file "API" "$BIBER_API_PID_FILE"
stop_pid_file "vLLM" "$BIBER_VLLM_PID_FILE"

echo
echo "Remaining matching processes:"
ps -eo pid,stat,cmd | grep -E '[v]llm serve|[u]vicorn app.main' || true
