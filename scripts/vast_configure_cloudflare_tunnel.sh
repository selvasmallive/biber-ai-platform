#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

SERVICE_NAME="${BIBER_PUBLIC_TUNNEL_SERVICE_NAME:-biber_public_api_tunnel}"
PUBLIC_HOSTNAME="${BIBER_PUBLIC_API_HOSTNAME:-api.beaverapi.com}"
PUBLIC_BASE_URL="${BIBER_PUBLIC_API_BASE_URL:-https://${PUBLIC_HOSTNAME}/v1}"
CLOUDFLARED_BIN="${BIBER_CLOUDFLARED_BIN:-}"
WRAPPER_PATH="/opt/supervisor-scripts/${SERVICE_NAME}.sh"
SUPERVISOR_CONF="/etc/supervisor/conf.d/${SERVICE_NAME}.conf"

if [ -z "$CLOUDFLARED_BIN" ] && [ -x /opt/instance-tools/bin/cloudflared ]; then
  CLOUDFLARED_BIN="/opt/instance-tools/bin/cloudflared"
fi
if [ -z "$CLOUDFLARED_BIN" ] && command -v cloudflared >/dev/null 2>&1; then
  CLOUDFLARED_BIN="$(command -v cloudflared)"
fi

CF_TUNNEL_TOKEN_VALUE="$(env_or_file CF_TUNNEL_TOKEN)"

cat <<EOF
BIBER public API domain tunnel plan
service_name: ${SERVICE_NAME}
public_hostname: ${PUBLIC_HOSTNAME}
public_base_url: ${PUBLIC_BASE_URL}
local_service_url: http://127.0.0.1:${BIBER_API_PORT}
cloudflared_bin: ${CLOUDFLARED_BIN:-missing}
token_configured: $([ -n "$CF_TUNNEL_TOKEN_VALUE" ] && echo true || echo false)
approval_required: BIBER_CONFIGURE_PUBLIC_TUNNEL_APPROVED=1
EOF

[ -n "$CLOUDFLARED_BIN" ] || die "cloudflared not found on this Vast image."
[ -n "$CF_TUNNEL_TOKEN_VALUE" ] || die "CF_TUNNEL_TOKEN is required in env or ${ROOT_DIR}/.env."

wait_for_http "http://127.0.0.1:${BIBER_API_PORT}/health" 15 \
  || die "BIBER API is not healthy at http://127.0.0.1:${BIBER_API_PORT}/health."

if [ "${BIBER_CONFIGURE_PUBLIC_TUNNEL_APPROVED:-0}" != "1" ]; then
  cat <<EOF

Dry run only. To install/restart the supervisor-managed tunnel, rerun with:

  BIBER_CONFIGURE_PUBLIC_TUNNEL_APPROVED=1 bash scripts/vast_configure_cloudflare_tunnel.sh

EOF
  exit 0
fi

if [ "${BIBER_PERSIST_CF_TUNNEL_TOKEN:-0}" = "1" ]; then
  set_env_value CF_TUNNEL_TOKEN "$CF_TUNNEL_TOKEN_VALUE"
fi
set_env_value BIBER_PUBLIC_API_HOSTNAME "$PUBLIC_HOSTNAME"
set_env_value BIBER_PUBLIC_API_BASE_URL "$PUBLIC_BASE_URL"

run_as_root mkdir -p /opt/supervisor-scripts /etc/supervisor/conf.d

run_as_root tee "$WRAPPER_PATH" >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${BIBER_REPO_ROOT:-/workspace/biber-ai-platform}"
# shellcheck source=/workspace/biber-ai-platform/scripts/lib/vast_direct_common.sh
source "${REPO_ROOT}/scripts/lib/vast_direct_common.sh"

TOKEN="$(env_or_file CF_TUNNEL_TOKEN)"
[ -n "$TOKEN" ] || {
  echo "CF_TUNNEL_TOKEN is required in env or ${REPO_ROOT}/.env." >&2
  exit 1
}

exec "${BIBER_CLOUDFLARED_BIN:-/opt/instance-tools/bin/cloudflared}" \
  tunnel --no-autoupdate run --token "$TOKEN"
EOF
run_as_root chmod 0755 "$WRAPPER_PATH"

run_as_root tee "$SUPERVISOR_CONF" >/dev/null <<EOF
[program:${SERVICE_NAME}]
environment=PROC_NAME="%(program_name)s",BIBER_REPO_ROOT="${ROOT_DIR}",BIBER_CLOUDFLARED_BIN="${CLOUDFLARED_BIN}"
command=${WRAPPER_PATH}
autostart=true
autorestart=unexpected
stdout_logfile=/dev/stdout
redirect_stderr=true
stdout_logfile_maxbytes=0
EOF

run_as_root supervisorctl reread
run_as_root supervisorctl update
run_as_root supervisorctl restart "$SERVICE_NAME" || run_as_root supervisorctl start "$SERVICE_NAME"

sleep 2
run_as_root supervisorctl status "$SERVICE_NAME" || true

cat <<EOF

Configured BIBER public API tunnel supervisor service.
Expected public client base URL after DNS/tunnel route propagates:
  ${PUBLIC_BASE_URL}

The tunnel token was not printed. If BIBER_PERSIST_CF_TUNNEL_TOKEN=1 was not set,
the service requires CF_TUNNEL_TOKEN to remain available in the supervisor
environment or ${ROOT_DIR}/.env.
EOF
