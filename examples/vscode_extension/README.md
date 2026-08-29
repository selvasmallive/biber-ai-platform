# BIBER AI Assistant

BIBER AI Assistant is a secure VS Code client for testing BIBER as a
Copilot-style local/remote coding assistant. The Marketplace icon is packaged
from `media/icon.png`. Version `0.1.1` focuses on API
readiness and orchestration planning before direct file mutation is enabled.

The first command surface is intentionally small:

- `BIBER: Set API Key` stores the user API key in VS Code SecretStorage.
- `BIBER: Clear API Key` removes the stored key.
- `BIBER: Test API Connection` calls `/v1/agent/capabilities` without sending
  repository data and prints a redacted readiness summary.
- `BIBER: Plan With BIBER Orchestration` calls the planning-only
  `/v1/agent/orchestration/plan` endpoint.

The extension targets the OpenAI-compatible BIBER API base URL configured in
`biber.openaiBaseUrl`, defaulting to:

```text
https://api.beaverapi.com/v1
```

For a private Vast SSH tunnel during development, set:

```text
http://127.0.0.1:8000/v1
```

Do not point the extension at the raw vLLM provider URL.

## Security Contract

The extension must protect the BIBER API and the user's code workspace:

- Store API keys only in VS Code SecretStorage.
- Never write API keys to settings, files, terminal output, or the output panel.
- Require HTTPS for remote API URLs; allow HTTP only for localhost/127.0.0.1.
- Use explicit user commands only; do not run background repository scans.
- Send no file contents in the first MVP orchestration command.
- Send only bounded workspace-relative path hints and a bounded instruction.
- Enforce a local per-minute request limit before calling BIBER.
- Enforce single-flight requests so repeated clicks do not fan out.
- Enforce request timeouts with `AbortController`.
- Avoid automatic retry storms; failed calls should stop and show one error.
- Validate the API connection with capabilities before using orchestration.
- Keep OpenAI mentor disabled by default and do not expose admin APIs.

These client-side controls are not a substitute for server-side protections.
The BIBER API must still enforce authentication, per-key quotas, server-side
rate limits, payload size limits, logging redaction, and abuse monitoring.

## Current Limitation

The current orchestration call is a planning contract test. It is useful for
editor integration because it verifies API keys, URL configuration, path hints,
repo planning output, and user-facing workflow. It does not yet implement a
full autonomous editor agent, streaming chat, background indexing, or direct
multi-file apply in VS Code.

Use `BIBER: Test API Connection` first after installing or changing the API
URL/key. It should show the BIBER service/version/model plus server-side guard
metadata such as payload caps and rate limits. If that check fails, do not run
orchestration from the extension until the API URL, key, or server is fixed.

## Local Development

Install dependencies only when you are actively developing the extension:

```bash
npm ci
npm run compile
```

Then open this folder in VS Code and run the extension host. Keep the first live
tests against a private tunnel or a low-quota per-user API key.

From the repository root, the same build can be checked with:

```bash
python scripts/biber_vscode_extension_compile_smoke.py
```

Package and install-test the VSIX into an isolated temporary VS Code profile
with:

```bash
python scripts/biber_vscode_extension_package_smoke.py
```

To test the same API readiness flow without launching VS Code, run:

```bash
python scripts/biber_vscode_extension_connection_smoke.py \
  --base-url http://127.0.0.1:8000/v1
```

Set `BIBER_API_KEY` first. The smoke calls only `/v1/agent/capabilities`, sends
no repository data, sends the same BIBER client identity headers as the
extension, and redacts secret-like fields from its artifact.

To test the same orchestration planning flow without launching VS Code, run:

```bash
python scripts/biber_vscode_extension_orchestration_smoke.py \
  --base-url http://127.0.0.1:8000/v1 \
  --changed-path docs/BIBER_ONLY_WORKSPACE.md
```

That smoke calls only `/v1/agent/orchestration/plan`, sends bounded path hints
and a bounded instruction, sends no file contents, and verifies that the
response remains planning-only with no model request, GitHub save, training, or
OpenAI mentor call.

## Marketplace

The Marketplace extension ID is:

```text
flat-electronics-canada.biber-ai-assistant
```

See the repository release checklist for packaging and publishing steps:
https://github.com/selvasmallive/biber-ai-platform/blob/biber/mvp-resume-20260712/docs/BIBER_VSCODE_MARKETPLACE_RELEASE.md
