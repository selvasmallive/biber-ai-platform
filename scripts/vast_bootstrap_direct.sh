#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

log "Preparing BIBER direct GPU deployment"
print_runtime_summary

log "Checking GPU"
require_cmd nvidia-smi
nvidia-smi

log "Installing system packages when apt is available"
if command -v apt-get >/dev/null 2>&1; then
  run_as_root apt-get update
  run_as_root apt-get install -y git curl jq python3 python3-venv python3-pip
else
  warn "apt-get not found; assuming git, curl, python3, venv, and pip are already available."
fi

require_cmd git
require_cmd curl
require_cmd python3

ensure_runtime_dirs

log "Creating or reusing Python virtual environment"
if [ ! -x "${VENV_DIR}/bin/python" ]; then
  python3 -m venv "$VENV_DIR"
fi

log "Installing API dependencies"
"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/pip" install -r "${ROOT_DIR}/requirements-api.txt"

if [ "${BIBER_SKIP_VLLM_INSTALL:-false}" = "true" ]; then
  warn "Skipping vLLM install because BIBER_SKIP_VLLM_INSTALL=true."
else
  log "Installing or verifying vLLM"
  if [ "${BIBER_FORCE_VLLM_INSTALL:-false}" = "true" ] \
    || ! "${VENV_DIR}/bin/python" -c 'import vllm' >/dev/null 2>&1; then
    "${VENV_DIR}/bin/pip" install vllm
  else
    "${VENV_DIR}/bin/python" - <<'PY'
import vllm
print(f"vLLM already installed: {vllm.__version__}")
PY
  fi
fi

log "Validating project scaffold"
"${VENV_DIR}/bin/python" "${ROOT_DIR}/scripts/validate_phase1.py"
"${VENV_DIR}/bin/python" -m compileall "${ROOT_DIR}/app" "${ROOT_DIR}/src" "${ROOT_DIR}/worker" "${ROOT_DIR}/scripts" "${ROOT_DIR}/training"

if [ ! -f "${ROOT_DIR}/.env" ]; then
  log "Creating .env from .env.example"
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
  warn "Starter credentials are active. Replace demo API keys before public exposure."
fi

set_env_value "BIBER_ENV" "gpu"
set_env_value "BIBER_CHAT_MODE" "infer"
set_env_value "BIBER_LOCAL_MODEL_BASE_URL" "http://127.0.0.1:${BIBER_VLLM_PORT}/v1"
set_env_value "BIBER_LOCAL_MODEL_NAME" "$BIBER_SERVED_MODEL_NAME"
set_env_value "BIBER_HF_MODEL" "$BIBER_MODEL"

if [ "${BIBER_START_AFTER_BOOTSTRAP:-true}" = "true" ]; then
  log "Starting BIBER services"
  exec "${SCRIPT_DIR}/vast_start_direct.sh"
fi

log "Bootstrap complete"
print_runtime_summary
