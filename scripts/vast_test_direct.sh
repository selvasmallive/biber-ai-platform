#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

API_KEY="${BIBER_TEST_API_KEY:-$(read_env_value BIBER_DEMO_API_KEY)}"
if [ -z "$API_KEY" ]; then
  API_KEY="dev-api-key-change-me"
fi

TMP_JSON="$(mktemp)"
trap 'rm -f "$TMP_JSON"' EXIT

cat > "$TMP_JSON" <<'JSON'
{
  "language": "Python",
  "max_tokens": 80,
  "messages": [
    {
      "role": "user",
      "content": "Return only: ok"
    }
  ]
}
JSON

echo "Health:"
curl -fsS "http://127.0.0.1:${BIBER_API_PORT}/health"
echo

echo "Runtime:"
curl -fsS -H "Authorization: Bearer ${API_KEY}" "http://127.0.0.1:${BIBER_API_PORT}/v1/runtime"
echo

echo "vLLM models:"
curl -fsS "http://127.0.0.1:${BIBER_VLLM_PORT}/v1/models"
echo

echo "Chat smoke test:"
curl -fsS \
  -X POST "http://127.0.0.1:${BIBER_API_PORT}/v1/chat" \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  --data-binary "@${TMP_JSON}"
echo
