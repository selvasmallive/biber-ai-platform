#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

print_runtime_summary

echo
echo "GPU:"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv
else
  echo "nvidia-smi not found"
fi

echo
echo "Processes:"
if pid_file_alive "$BIBER_VLLM_PID_FILE"; then
  echo "vLLM: running pid $(cat "$BIBER_VLLM_PID_FILE")"
else
  echo "vLLM: not running from pid file"
fi
if pid_file_alive "$BIBER_API_PID_FILE"; then
  echo "API:  running pid $(cat "$BIBER_API_PID_FILE")"
else
  echo "API:  not running from pid file"
fi

echo
echo "HTTP:"
curl -fsS --max-time 5 "http://127.0.0.1:${BIBER_API_PORT}/health" || true
echo
curl -fsS --max-time 5 "http://127.0.0.1:${BIBER_VLLM_PORT}/v1/models" || true
echo

echo
echo "Ports:"
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | grep -E ":(${BIBER_API_PORT}|${BIBER_VLLM_PORT})\\b" || true
else
  echo "ss not found"
fi

echo
echo "Recent API log:"
tail -n 20 "$BIBER_API_LOG" 2>/dev/null || true

echo
echo "Recent vLLM log:"
tail -n 20 "$BIBER_VLLM_LOG" 2>/dev/null || true
