# BIBER VS Code Extension MVP

This is the minimal VS Code extension shape for testing BIBER as a
Copilot-style local/remote coding assistant without overbuilding the editor
client.

The first command surface is intentionally small:

- `BIBER: Set API Key` stores the user API key in VS Code SecretStorage.
- `BIBER: Clear API Key` removes the stored key.
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
- Keep OpenAI mentor disabled by default and do not expose admin APIs.

These client-side controls are not a substitute for server-side protections.
The BIBER API must still enforce authentication, per-key quotas, server-side
rate limits, payload size limits, logging redaction, and abuse monitoring.

## MVP Limitation

The current orchestration call is a planning contract test. It is useful for
editor integration because it verifies API keys, URL configuration, path hints,
repo planning output, and user-facing workflow. It does not yet implement a
full autonomous editor agent, streaming chat, background indexing, or direct
multi-file apply in VS Code.

## Local Development

Install dependencies only when you are actively developing the extension:

```bash
npm install
npm run compile
```

Then open this folder in VS Code and run the extension host. Keep the first live
tests against a private tunnel or a low-quota per-user API key.
