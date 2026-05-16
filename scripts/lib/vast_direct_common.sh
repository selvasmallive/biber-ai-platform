#!/usr/bin/env bash
set -euo pipefail

biber_direct_repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

ROOT_DIR="${BIBER_ROOT_DIR:-$(biber_direct_repo_root)}"

read_env_file_value() {
  local key="$1"
  local env_file="${2:-${ROOT_DIR}/.env}"
  [ -f "$env_file" ] || return 0
  awk -v key="$key" '
    BEGIN { prefix = key "=" }
    index($0, prefix) == 1 { value = substr($0, length(prefix) + 1) }
    END { print value }
  ' "$env_file"
}

env_or_file() {
  local key="$1"
  local default_value="${2:-}"
  local env_value="${!key-}"
  local file_value

  if [ -n "$env_value" ]; then
    echo "$env_value"
    return
  fi

  file_value="$(read_env_file_value "$key")"
  if [ -n "$file_value" ]; then
    echo "$file_value"
  else
    echo "$default_value"
  fi
}

if [ -d /workspace ] && [ -w /workspace ]; then
  DEFAULT_RUNTIME_ROOT="/workspace"
else
  DEFAULT_RUNTIME_ROOT="${ROOT_DIR}/.biber-runtime"
fi

BIBER_RUNTIME_ROOT="${BIBER_RUNTIME_ROOT:-${BIBER_WORKSPACE_DIR:-$DEFAULT_RUNTIME_ROOT}}"
VENV_DIR="${BIBER_VENV_DIR:-${BIBER_RUNTIME_ROOT}/biber-venv}"
LOG_DIR="${BIBER_LOG_DIR:-${BIBER_RUNTIME_ROOT}/biber-logs}"
PID_DIR="${BIBER_PID_DIR:-${BIBER_RUNTIME_ROOT}/biber-pids}"
HF_HOME="$(env_or_file HF_HOME "${BIBER_RUNTIME_ROOT}/.hf_home")"
PIP_CACHE_DIR="$(env_or_file PIP_CACHE_DIR "${BIBER_RUNTIME_ROOT}/pip-cache")"

BIBER_MODEL="$(env_or_file BIBER_HF_MODEL Qwen/Qwen2.5-Coder-7B-Instruct)"
BIBER_SERVED_MODEL_NAME="$(env_or_file BIBER_LOCAL_MODEL_NAME biber-dev-core)"
BIBER_VLLM_SERVED_MODEL_NAME="$(
  env_or_file BIBER_VLLM_SERVED_MODEL_NAME "$BIBER_SERVED_MODEL_NAME"
)"
BIBER_VLLM_LORA_MODULES="$(env_or_file BIBER_VLLM_LORA_MODULES)"
BIBER_API_HOST="$(env_or_file BIBER_API_HOST 127.0.0.1)"
BIBER_API_PORT="$(env_or_file BIBER_API_PORT 8000)"
BIBER_VLLM_HOST="$(env_or_file BIBER_VLLM_HOST 127.0.0.1)"
BIBER_VLLM_PORT="$(env_or_file BIBER_VLLM_PORT 8001)"
BIBER_HF_TOKEN="$(env_or_file HF_TOKEN)"
BIBER_API_LOG="${BIBER_API_LOG:-${LOG_DIR}/api.log}"
BIBER_VLLM_LOG="${BIBER_VLLM_LOG:-${LOG_DIR}/vllm.log}"
BIBER_API_PID_FILE="${BIBER_API_PID_FILE:-${PID_DIR}/api.pid}"
BIBER_VLLM_PID_FILE="${BIBER_VLLM_PID_FILE:-${PID_DIR}/vllm.pid}"

export HF_HOME
export PIP_CACHE_DIR

log() {
  printf '\n==> %s\n' "$*"
}

warn() {
  printf 'WARNING: %s\n' "$*" >&2
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    die "Need root privileges to run: $*"
  fi
}

ensure_runtime_dirs() {
  mkdir -p "$BIBER_RUNTIME_ROOT" "$VENV_DIR" "$LOG_DIR" "$PID_DIR" "$HF_HOME" "$PIP_CACHE_DIR"
}

pid_alive() {
  local pid="${1:-}"
  [ -n "$pid" ] && kill -0 "$pid" >/dev/null 2>&1
}

pid_file_alive() {
  local pid_file="$1"
  [ -f "$pid_file" ] || return 1
  local pid
  pid="$(tr -d '[:space:]' < "$pid_file")"
  pid_alive "$pid"
}

remove_stale_pid_file() {
  local pid_file="$1"
  if [ -f "$pid_file" ] && ! pid_file_alive "$pid_file"; then
    rm -f "$pid_file"
  fi
}

gpu_count() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo 0
    return
  fi
  nvidia-smi -L 2>/dev/null | grep -c '^GPU ' || true
}

count_csv_items() {
  local value="$1"
  if [ -z "$value" ]; then
    echo 0
  else
    awk -F',' '{ print NF }' <<< "$value"
  fi
}

gpu_index_list() {
  local count="$1"
  if [ "$count" -le 0 ]; then
    echo ""
    return
  fi
  seq -s, 0 "$((count - 1))"
}

min_gpu_memory_mb() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo 0
    return
  fi
  nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null \
    | awk 'NR == 1 || $1 < min { min = $1 } END { print min + 0 }'
}

default_tensor_parallel_size() {
  local cuda_devices="${BIBER_CUDA_VISIBLE_DEVICES:-${CUDA_VISIBLE_DEVICES:-}}"
  if [ -n "$cuda_devices" ]; then
    count_csv_items "$cuda_devices"
    return
  fi

  local count
  count="$(gpu_count)"
  if [ "$count" -le 0 ]; then
    die "No GPUs found through nvidia-smi."
  fi
  echo "$count"
}

default_cuda_visible_devices() {
  local cuda_devices="${BIBER_CUDA_VISIBLE_DEVICES:-${CUDA_VISIBLE_DEVICES:-}}"
  if [ -n "$cuda_devices" ]; then
    echo "$cuda_devices"
    return
  fi

  gpu_index_list "$(default_tensor_parallel_size)"
}

default_max_model_len() {
  if [ -n "${BIBER_MAX_MODEL_LEN:-}" ]; then
    echo "$BIBER_MAX_MODEL_LEN"
    return
  fi

  local tp min_mb
  tp="$(default_tensor_parallel_size)"
  min_mb="$(min_gpu_memory_mb)"
  if [ "$tp" -ge 2 ]; then
    echo 8192
  elif [ "$min_mb" -gt 0 ] && [ "$min_mb" -lt 20000 ]; then
    echo 4096
  else
    echo 8192
  fi
}

read_env_value() {
  local key="$1"
  local env_file="${2:-${ROOT_DIR}/.env}"
  read_env_file_value "$key" "$env_file"
}

set_env_value() {
  local key="$1"
  local value="$2"
  local env_file="${3:-${ROOT_DIR}/.env}"

  if [ ! -f "$env_file" ]; then
    touch "$env_file"
  fi

  if grep -q "^${key}=" "$env_file"; then
    local escaped
    escaped="$(printf '%s' "$value" | sed 's/[&|]/\\&/g')"
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$env_file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

wait_for_http() {
  local url="$1"
  local timeout_seconds="${2:-120}"
  local started
  started="$(date +%s)"

  while true; do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      return 0
    fi

    if [ "$(( $(date +%s) - started ))" -ge "$timeout_seconds" ]; then
      return 1
    fi

    sleep 2
  done
}

port_listening() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn 2>/dev/null | awk '{ print $4 }' | grep -Eq "[:.]${port}$"
    return
  fi
  return 1
}

print_runtime_summary() {
  cat <<EOF
Runtime root: ${BIBER_RUNTIME_ROOT}
Repo root:    ${ROOT_DIR}
Venv:         ${VENV_DIR}
Logs:         ${LOG_DIR}
HF cache:     ${HF_HOME}
API URL:      http://127.0.0.1:${BIBER_API_PORT}
vLLM URL:     http://127.0.0.1:${BIBER_VLLM_PORT}/v1
API bind:     ${BIBER_API_HOST}:${BIBER_API_PORT}
vLLM bind:    ${BIBER_VLLM_HOST}:${BIBER_VLLM_PORT}
Model:        ${BIBER_MODEL}
Served name:  ${BIBER_SERVED_MODEL_NAME}
vLLM base served name: ${BIBER_VLLM_SERVED_MODEL_NAME}
vLLM LoRA modules: ${BIBER_VLLM_LORA_MODULES:-none}
EOF
}
