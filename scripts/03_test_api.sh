#!/usr/bin/env bash
set -e

API_KEY="${BIBER_DEMO_API_KEY:-dev-api-key-change-me}"

echo "Testing health..."
curl -s http://localhost:8000/health | jq . || true

echo
echo "Testing models..."
curl -s http://localhost:8000/v1/models \
  -H "Authorization: Bearer ${API_KEY}" | jq . || true

echo
echo "Submitting code job..."
curl -s http://localhost:8000/v1/code \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "X-Biber-Passcode: BIBER_QUEUE_PRIORITY_DEMO" \
  -H "Content-Type: application/json" \
  -d '{"language":"python","prompt":"Create a FastAPI health endpoint","model":"biber-dev-core"}' | jq . || true
