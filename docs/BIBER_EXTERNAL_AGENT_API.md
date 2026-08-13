# BIBER External Agent API

This is the MVP contract for using BIBER as a model source from an IDE agent,
custom conversational agent, internal app, or a future GitHub Copilot extension
or agent gateway.

## MVP Contract

BIBER exposes an authenticated OpenAI-compatible chat-completions surface:

```text
GET  /v1/models
POST /v1/chat/completions
GET  /v1/agent/capabilities
```

Authentication accepts either header form:

```text
Authorization: Bearer <api-key>
x-api-key: <api-key>
```

The current MVP key source is `BIBER_API_KEYS`. Put comma-separated keys in the
server environment or `.env` file. Do not commit `.env` or paste keys into chat.

`POST /v1/chat/completions` defaults to the configured swappable BIBER model
registry. The raw GPU runtime remains behind BIBER; external clients should talk
to the BIBER API, not directly to vLLM. OpenAI mentor is optional and disabled
by default for this endpoint. Streaming is intentionally not part of this MVP
contract yet.

Example:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "biber-dev-core-v1",
    "messages": [
      {"role": "user", "content": "Write one concise Rust review note."}
    ],
    "max_tokens": 120
  }'
```

## Client Compatibility

Any client that supports an OpenAI-compatible base URL and API key can point at
the BIBER API base URL and use `/v1/models` plus `/v1/chat/completions`.

GitHub Copilot itself may require a Copilot extension, approved integration, or
agent gateway rather than direct arbitrary model endpoint configuration. Keep
the BIBER side generic: OpenAI-compatible HTTP, bearer API key, stable model
metadata, and no provider-specific assumptions.

## Domain And Public HTTPS

A `.com` domain is not required for local MVP or private GPU testing. Use a
domain only when BIBER needs to be reachable by external clients over the
internet.

When public access is needed:

1. Buy a domain in Namecheap, for example `your-biber-domain.com`.
2. Choose the production host/API edge first: GCP, AWS, Azure, Cloudflare, or a
   reverse proxy VM/load balancer.
3. In Namecheap DNS, create either an `A` record to the public IP or a `CNAME`
   to the cloud load balancer/proxy hostname.
4. Enable HTTPS on the cloud edge or reverse proxy before allowing real users.
5. Route only BIBER API paths such as `/v1/*` to the BIBER API service.
6. Keep the GPU/vLLM port private where possible; expose BIBER API as the
   controlled gateway.
7. Configure API keys through environment/secret storage. Never place keys in
   GitHub.

## Planned Admin Portal

The MVP does not need a website admin portal before proving the API contract.
The planned production portal should add:

- Admin login with secure password or SSO.
- Registered users.
- Per-user API key issuance.
- Hashed API key storage, not plaintext key storage.
- Key revoke/disable/rotate controls.
- Usage audit events.
- Rate limits and monthly quotas.
- Optional passcode or policy-based GPU priority scheduling.

Build this only after the model-source API is stable and useful from at least
one real client.
