#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

[ -x "${VENV_DIR}/bin/python" ] || die "Virtualenv not found at ${VENV_DIR}. Run scripts/vast_bootstrap_direct.sh first."
[ -x "${VENV_DIR}/bin/vllm" ] || die "vLLM executable not found in ${VENV_DIR}. Run scripts/vast_bootstrap_direct.sh first."

if [ ! -f "${ROOT_DIR}/.env" ]; then
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
  warn "Created .env from .env.example. Replace demo API keys before public exposure."
fi

set_env_value "BIBER_ENV" "gpu"
set_env_value "BIBER_CHAT_MODE" "infer"
set_env_value "BIBER_LOCAL_MODEL_BASE_URL" "http://127.0.0.1:${BIBER_VLLM_PORT}/v1"
set_env_value "BIBER_LOCAL_MODEL_NAME" "$BIBER_SERVED_MODEL_NAME"
set_env_value "BIBER_HF_MODEL" "$BIBER_MODEL"
set_env_value "BIBER_VLLM_SERVED_MODEL_NAME" "$BIBER_VLLM_SERVED_MODEL_NAME"
if [ -n "$BIBER_VLLM_LORA_MODULES" ]; then
  set_env_value "BIBER_VLLM_LORA_MODULES" "$BIBER_VLLM_LORA_MODULES"
fi

remove_stale_pid_file "$BIBER_VLLM_PID_FILE"
remove_stale_pid_file "$BIBER_API_PID_FILE"

VLLM_TP="${BIBER_VLLM_TENSOR_PARALLEL_SIZE:-$(default_tensor_parallel_size)}"
CUDA_DEVICES="$(default_cuda_visible_devices)"
MAX_MODEL_LEN="$(default_max_model_len)"
GPU_MEMORY_UTILIZATION="${BIBER_GPU_MEMORY_UTILIZATION:-0.85}"
START_TIMEOUT_SECONDS="${BIBER_START_TIMEOUT_SECONDS:-900}"
VLLM_LORA_ARGS=()
if [ -n "$BIBER_VLLM_LORA_MODULES" ]; then
  # shellcheck disable=SC2206
  VLLM_LORA_MODULE_ARRAY=($BIBER_VLLM_LORA_MODULES)
  VLLM_LORA_ARGS=(--enable-lora --lora-modules "${VLLM_LORA_MODULE_ARRAY[@]}")
fi

log "Starting biber-dev-core through vLLM"
if pid_file_alive "$BIBER_VLLM_PID_FILE"; then
  echo "vLLM already running with pid $(cat "$BIBER_VLLM_PID_FILE")."
elif port_listening "$BIBER_VLLM_PORT"; then
  die "Port ${BIBER_VLLM_PORT} is already listening, but ${BIBER_VLLM_PID_FILE} is not active."
else
  (
    cd "$ROOT_DIR"
    nohup env \
      HF_HOME="$HF_HOME" \
      HF_TOKEN="$BIBER_HF_TOKEN" \
      PIP_CACHE_DIR="$PIP_CACHE_DIR" \
      VLLM_USAGE_SOURCE=production \
      CUDA_VISIBLE_DEVICES="$CUDA_DEVICES" \
      "${VENV_DIR}/bin/vllm" serve "$BIBER_MODEL" \
        --served-model-name "$BIBER_VLLM_SERVED_MODEL_NAME" \
        --host "$BIBER_VLLM_HOST" \
        --port "$BIBER_VLLM_PORT" \
        --tensor-parallel-size "$VLLM_TP" \
        --max-model-len "$MAX_MODEL_LEN" \
        --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION" \
        --disable-custom-all-reduce \
        --generation-config vllm \
        "${VLLM_LORA_ARGS[@]}" \
        ${BIBER_VLLM_EXTRA_ARGS:-} \
      > "$BIBER_VLLM_LOG" 2>&1 < /dev/null &
    echo $! > "$BIBER_VLLM_PID_FILE"
    disown "$(cat "$BIBER_VLLM_PID_FILE")" 2>/dev/null || true
  )
  echo "vLLM pid: $(cat "$BIBER_VLLM_PID_FILE")"
fi

echo "Waiting for vLLM at http://127.0.0.1:${BIBER_VLLM_PORT}/v1/models ..."
if ! wait_for_http "http://127.0.0.1:${BIBER_VLLM_PORT}/v1/models" "$START_TIMEOUT_SECONDS"; then
  tail -n 120 "$BIBER_VLLM_LOG" || true
  die "vLLM did not become ready within ${START_TIMEOUT_SECONDS}s."
fi

log "Starting BIBER FastAPI"
if pid_file_alive "$BIBER_API_PID_FILE"; then
  echo "API already running with pid $(cat "$BIBER_API_PID_FILE")."
elif port_listening "$BIBER_API_PORT"; then
  die "Port ${BIBER_API_PORT} is already listening, but ${BIBER_API_PID_FILE} is not active."
else
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
fi

echo "Waiting for API at http://127.0.0.1:${BIBER_API_PORT}/health ..."
if ! wait_for_http "http://127.0.0.1:${BIBER_API_PORT}/health" 120; then
  tail -n 120 "$BIBER_API_LOG" || true
  die "API did not become ready."
fi

log "BIBER direct GPU deployment is running"
print_runtime_summary
cat <<EOF

Useful commands:
  bash scripts/vast_status_direct.sh
  bash scripts/vast_test_direct.sh
  bash scripts/vast_stop_direct.sh

Log files:
  ${BIBER_VLLM_LOG}
  ${BIBER_API_LOG}
EOF
