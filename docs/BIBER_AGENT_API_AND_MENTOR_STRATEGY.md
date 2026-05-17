# BIBER Agent API And Mentor Strategy

Status: planning document for future BIBER platform phases.

## Goal

BIBER should become a private coding-model API that can power custom developer
agents, including tools similar in shape to Codex, Replit Agent, or repo-aware
internal assistants.

The cost-saving principle is:

- BIBER is the default inference engine on the user's GPU.
- OpenAI/Codex is an optional mentor/reviewer layer.
- Vast.ai runs long inference, eval, and training jobs.
- Codex is used only when it protects quality, resolves blockers, or updates
  the project.

## Current State

The current platform already has the beginnings of this architecture:

- FastAPI service for BIBER.
- Protected endpoints using bearer API keys from `BIBER_API_KEYS`.
- `/v1/chat` for BIBER code generation and reasoning.
- `/v1/models` and `/v1/runtime` for model/runtime discovery.
- vLLM serving `biber-dev-core` through an OpenAI-compatible local runtime.
- Optional mentor plumbing controlled by `BIBER_MENTOR_ENABLED`,
  `OPENAI_API_KEY`, and `OPENAI_MODEL`.
- Mentor is currently disabled on the live Vast instance to save cost.

Current limitation:

- API keys are config-driven starter credentials, not durable user-owned
  database records.
- The API is private over SSH tunnel while starter credentials remain in place.
- There is no first-class repo-agent protocol yet.

## Target API Shape

BIBER should support two API layers:

1. Compatibility layer for simple model clients.
2. Agent layer for repo-aware development tools.

Compatibility layer:

```text
GET  /health
GET  /v1/runtime
GET  /v1/models
POST /v1/chat
```

Future OpenAI-compatible layer:

```text
POST /v1/chat/completions
POST /v1/responses
```

Agent layer:

```text
POST /v1/agent/sessions
POST /v1/agent/sessions/{session_id}/messages
POST /v1/agent/sessions/{session_id}/context
POST /v1/agent/sessions/{session_id}/patches
POST /v1/agent/sessions/{session_id}/runs
GET  /v1/agent/sessions/{session_id}
GET  /v1/agent/sessions/{session_id}/events
```

The future agent client should be able to:

- authenticate with an API key
- send task instructions
- send selected repo files or summaries
- request code patches
- run tests locally or in a controlled worker
- stream model events
- ask for mentor review only when enabled
- save approved generated code to GitHub when configured

## API Key Model

Near-term:

- keep `BIBER_API_KEYS` for private development
- do not expose the service publicly while starter keys remain in use
- do not rotate credentials routinely unless the user approves it

Production target:

- database-backed API keys
- hashed key storage
- key prefixes for lookup
- per-key owner, scopes, rate limits, and quotas
- key creation and revocation audit logs
- usage metering by model, endpoint, and token count
- optional project-level or organization-level keys

Suggested key scopes:

```text
chat:read
chat:write
agent:read
agent:write
repo:save
admin:read
admin:write
mentor:use
```

Mentor use should require an explicit `mentor:use` capability or admin setting
because mentor calls may create external API cost.

## Agent Client Workflow

Recommended end-user agent flow:

1. User authenticates a local or web agent client with a BIBER API key.
2. Client creates an agent session.
3. Client sends a task and selected workspace context.
4. BIBER proposes a plan or patch.
5. Client applies patches locally or in a controlled workspace.
6. Client runs tests and sends results back to BIBER.
7. BIBER iterates until tests pass or asks for human decision.
8. Optional mentor review is requested only for high-value checkpoints.
9. Approved changes can be saved to GitHub if GitHub integration is configured.

The client should prefer sending focused file context over whole repositories.
This controls token use and reduces accidental secret exposure.

## OpenAI/Codex Mentor Strategy

OpenAI/Codex should remain available as BIBER's mentor layer, not as the default
engine.

Use mentor calls for:

- architecture review
- security-sensitive Rust or cryptography review
- XRIQ consensus and wallet design review
- eval design
- diagnosing repeatable BIBER failures
- reviewing training examples before a fine-tune
- comparing candidate answers during quality gates

Avoid mentor calls for:

- routine code generation that BIBER can handle
- long batch jobs
- repeated low-value retries
- private secrets, keys, seed phrases, or unredacted credentials
- public-launch legal/compliance decisions

Mentor should be disabled by default in `.env`:

```text
BIBER_MENTOR_ENABLED=false
```

Enable it only when the user explicitly chooses the extra quality/cost tradeoff.

## Training Improvement Loop

Use mentor output to improve BIBER only through controlled artifacts:

1. BIBER produces an answer.
2. Eval, tests, or mentor review identifies a concrete issue.
3. A human or future approved process decides whether the issue is real.
4. Add a held-out eval prompt if it is a repeatable capability gap.
5. Add approved/provenance-tracked training examples only when needed.
6. Validate the dataset.
7. Run QLoRA on Vast.ai in `tmux`.
8. Compare the new adapter against target evals and broad regression evals.
9. Promote only if it improves the target without unacceptable regression.

Do not train directly on unreviewed mentor transcripts. Curate examples and
remove secrets, credentials, private keys, and irrelevant conversation text.

## XRIQ Agent Use Case

For XRIQ, the agent client should eventually support:

- spec drafting
- Rust crate scaffolding
- transaction and block validation implementation
- unit and property-style test generation
- wallet CLI implementation
- explorer frontend implementation
- Docker and CI/CD setup
- security review checklists
- local private-devnet runbooks

The first XRIQ agent target should be private-devnet development, not public
mainnet operation.

## Implementation Milestones

1. Keep `/v1/chat`, `/v1/models`, and `/v1/runtime` stable.
2. Add persistent database-backed API keys.
3. Add request/response usage logging without storing secrets.
4. Add optional streaming responses.
5. Add a repo-agent session model.
6. Add patch-oriented responses.
7. Add local test-result feedback messages.
8. Add optional mentor review gates.
9. Add GitHub save integration with durable credentials.
10. Add admin UI for keys, usage, mentor toggles, and model selection.

## Safety Requirements

- Never send private keys, seed phrases, API keys, `.env` files, or raw
  credentials to BIBER or mentor prompts.
- Redact secrets before storing request logs.
- Keep public binding disabled until real credentials, auth, TLS, rate limits,
  and monitoring are in place.
- Keep XRIQ public-launch decisions outside automated agent control.
