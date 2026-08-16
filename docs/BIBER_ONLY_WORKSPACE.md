# BIBER-Only Workspace

Use this document when continuing BIBER MVP from the dedicated BIBER-only sparse checkout at:

```text
C:\Users\vselv\OneDrive\Biber\biber-mvp-only
```

This folder is intentionally filtered so BIBER work does not need to scan or
reason about the separate XRIS-Coin/XRIQ project.

## Scope

Continue BIBER MVP only:

- swappable model providers and model registry
- authenticated external-agent API compatibility through `/v1/chat/completions`
- repo-context selection
- safe workspace edit planning and apply
- test execution and diagnosis
- agent client MVP loop
- GitHub save/PR path
- optional OpenAI mentor, disabled by default
- GPU eval/training only when a concrete BIBER model gap requires it

Do not continue XRIS-Coin/XRIQ from this workspace unless the user explicitly
asks for it.

For external IDE/gateway/client setup, use
`docs/BIBER_EXTERNAL_AGENT_CLIENT_SETUP.md` together with
`docs/BIBER_EXTERNAL_AGENT_API.md`.

## Start Prompt

```text
Read docs/BIBER_ONLY_WORKSPACE.md, readme-resume-biber.md, and the BIBER
sections at the top of docs/CODEX_HANDOFF.md. Continue BIBER MVP only from the
current branch. Do not continue XRIS-Coin/XRIQ work. Keep providers swappable,
keep OpenAI mentor optional and disabled by default, and prefer CPU-local
workflow improvements before asking for GPU credentials.
```

When a live local-model provider is actually needed, read
`docs/BIBER_LIVE_PROVIDER_RUNBOOK.md` before asking the user for Vast/GPU
connection details.

## Local MVP Loop

Prefer the CPU-local agent-client path before using a live API:

```bash
python scripts/biber_agent_client.py --json mvp-loop \
  --instruction "Plan or validate a narrow code change." \
  --local-target-root /path/to/repo \
  --include-git-state \
  --changed-path src/example.py \
  --changed-paths-file /tmp/biber-changed-paths.txt \
  --test-id python-compileall-api \
  --test-dry-run \
  --output /tmp/biber-mvp-loop.json
```

With `--local-target-root`, context planning, safe edit plan/apply, test
execution, and diagnosis are local. GitHub save/PR remains server-backed.
For larger changes, pass newline-delimited path lists with
`--pinned-paths-file` and `--changed-paths-file`; blank lines and `#` comments
are ignored, and the file entries are appended after any repeated
`--pinned-path` or `--changed-path` flags.
Use `save-github --dry-run` and `create-pr --dry-run` to inspect the exact
GitHub payload locally before enabling server-backed credentials or sending any
GitHub request. Add `--output` when you want those standalone dry-runs saved as
JSON artifacts, then use `show-github-dry-run <artifact>` or
`list-github-dry-runs <directory>` to inspect them later. Use
`mvp-loop --github-dry-run` when you want the same payload inspection inside a
local MVP-loop artifact without resolving API credentials.
For external agent API users, admin API-key management is available through the
client after the server sets `BIBER_ADMIN_API_KEY`:
`admin-api-key-contract-smoke --output <artifact.json>`, `list-api-keys`,
`issue-api-key --user-id <id> --label <label>`, and
`revoke-api-key <key_id>`. These commands use the admin key only; normal
agent/chat commands continue to use `BIBER_API_KEY` or another user key. Prefer
`admin-api-key-contract-smoke` before list/issue/revoke when you only need a
non-secret proof that the admin endpoint is reachable. Add
`--allow-missing-admin-key` when the admin key is intentionally absent and you
need a redacted blocked artifact rather than a failed process.
Use `chat-completions --message <text> --model biber-dev-core-v1` to smoke-test
the OpenAI-compatible `/v1/chat/completions` model-source endpoint from the same
client; it sends `stream=false` and keeps OpenAI mentor off unless `--use-mentor`
is explicitly passed.
Use `models` to inspect `/v1/models` stable/candidate metadata from the same
client before configuring an external agent or gateway. Both `models` and
`chat-completions` accept `--output` to save JSON proof artifacts.
Use `runtime --output <artifact.json>` to save a non-secret health/provider
configuration proof from `/v1/runtime` before handing a base URL to another
agent or gateway.
Use `capabilities --output <artifact.json>` to save a non-secret feature and
workflow contract from `/v1/agent/capabilities`.
Use `external-agent-readiness --output <artifact.json>` when you want one
non-secret setup proof that includes connection, capabilities, runtime, and
model metadata for a generic OpenAI-compatible client.
Use `external-agent-connection --output <artifact.json>` when configuring an
IDE, gateway, or custom conversational agent: it bundles the OpenAI-compatible
base URL, `/v1/models`, `/v1/chat/completions`, the selected stable model, and
auth header names without writing the API key into the artifact.
Use `external-agent-bundle --output <artifact.json>` for a compact non-secret
handoff artifact containing env values, docs/examples paths, validation
commands, API-key management metadata, and an API-key placeholder for another
client or gateway.
Use `external-agent-bundle-health-check <artifact.json> --repo-root <repo>` to
verify the bundle is non-secret, internally consistent, and ready for handoff.
This check is offline and does not resolve API credentials.
Use `external-agent-client-contract-report <artifact.json> --repo-root <repo>`
to produce a compact non-secret setup report for a gateway/client with URL,
model, auth headers, endpoints, validation commands, and readiness status.
Use `external-agent-bundle-chat-smoke <artifact.json> --repo-root <repo>` to
prove a saved bundle can drive one live `/v1/chat/completions` request through
its `BIBER_OPENAI_BASE_URL` and `BIBER_MODEL`, with OpenAI mentor off.
Use `external-agent-handoff-package <artifact.json> --repo-root <repo>` to
create one non-secret index artifact linking the bundle, health report, client
contract report, optional chat-smoke proof, and API-key management metadata for
another gateway/client.
Use `show-external-agent-handoff-package <package.json>` to inspect the saved
handoff summary without opening JSON and without resolving API keys.
Use `external-client-readiness-bundle <package.json> --admin-smoke-artifact
<admin-smoke.json>` to combine the model-source handoff package and redacted
admin API-key smoke into one non-secret checklist for Copilot, Gemini Code
Assist, custom IDE agents, gateways, or conversational apps. A blocked
`admin-api-key-contract-smoke --allow-missing-admin-key` artifact is acceptable:
the bundle can still report `ready_for_external_client_configuration=true` while
keeping `admin_key_management_ready=false` until the server is deliberately
configured with `BIBER_ADMIN_API_KEY`.
Use `show-external-client-readiness-bundle <bundle.json>` to inspect that saved
checklist later without rebuilding it, resolving API keys, or opening JSON.
Use `external-client-quickstart-verify <bundle.json> --repo-root <repo>` before
handoff to confirm the saved readiness bundle, docs, examples, env names, and
setup command mentions still line up. It is offline and does not resolve API
keys or call BIBER.
Use `show-external-client-quickstart-verification <artifact.json>` to inspect a
saved quickstart verification summary without rerunning checks, resolving API
keys, or calling BIBER.
Use `external-agent-smoke --output <artifact.json>` when you want readiness plus
one short OpenAI-compatible chat-completions response in a single non-secret
artifact. This is the preferred MVP proof before handing BIBER to an external
agent client.
Use `examples/external_agent/` for minimal generic-client examples that require
only `BIBER_OPENAI_BASE_URL`, `BIBER_MODEL`, and `BIBER_API_KEY`. Run
`python scripts/biber_external_agent_examples_smoke.py` for an offline
fake-server validation before live GPU testing.
Add `--client-base-url <url>` when the saved profile should advertise an SSH
tunnel, reverse proxy, or HTTPS domain instead of the private probe URL.
Use `--include-git-state` for repo work so the artifact records the local
branch, short HEAD, dirty status, and `git status --short` before edits/tests.
Repo-context and safe-edit paths must stay workspace-relative; Windows
drive-relative paths are rejected, and repo-context scanning skips symlinked
entries so local context does not follow links outside the target repo.
Repo-context planning uses stack profile entrypoint patterns, so detected Rust,
React/TypeScript, Python, TensorFlow, Docker, GitHub Actions, Java, and .NET
projects can pull in their likely app/build/test entrypoints before falling
back to broad instruction-term matches.
Workspace edit plans include a deterministic `review` block with
`review_status`, `ready_for_apply`, risk/operation counts, warnings, blockers,
and required actions. Apply still requires the matching `plan_hash`; the review
is for safer human/agent inspection before that guarded apply step.
Workspace edits tolerate the common line-ending mismatch where a local model
returns LF `old_text` for a CRLF file, but only when the normalized match still
has the exact expected replacement count. The replacement preserves the target
file's line-ending style and still uses the normal plan-hash apply guard.
Each MVP-loop artifact includes `agent_report`, a compact machine-readable
status summary with repo state, selected context, edit counts, test result,
failure summary, and next actions for the following narrow step.
`show-mvp-loop` surfaces the context/test modes, selected context preview, and
edit review readiness so saved artifacts can be triaged without opening JSON.
The report's `edit` section carries workspace edit review metadata when the
plan provides it, including `review_status`, `ready_for_apply`, risk/operation
counts, warnings, and blockers.
When a local MVP-loop test fails, `agent_report.repair_hint` provides a compact
no-API repair packet: test id, command, exit/timing fields, failure category,
detected stack, relevant output preview, suggested next actions, and the
expected local repair workflow. Prefer this hint over re-parsing raw stdout
when preparing the next local-model repair step.
When the failed MVP-loop is saved with `--output`, the repair hint also includes
a `next_command` for the first no-API repair step:
`prepare-repair <mvp-loop-artifact> --output <prepared-repair.json>`.
When an MVP-loop artifact fails, run `prepare-repair` first. It preserves
`agent_report` in the repair request and includes the report in the bounded
local-model repair prompt, with OpenAI mentor still disabled unless explicitly
requested later through the separate repair-attempt path. The prompt includes
`agent_report.repair_hint` when available so the local model sees the same
failure category, stack, and no-API workflow guidance exposed by status output.
When the exact failed artifact path is not known, use
`prepare-latest-repair` and pass `--target-root` for real-repo work so fixture
failures are ignored:

```bash
python scripts/biber_agent_client.py --json prepare-latest-repair \
  /workspace/outputs \
  --target-root /workspace/biber-ai-platform \
  --output /workspace/outputs/biber-prepared-latest-repair.json
```

`attempt-repair` artifacts include `repair_output_contract` and
`extraction_hint` so the next local step can call `extract-repair-edits` and
then `plan-repair-edits` without guessing the expected model-output shape.
For an offline/local-model response, use `local-repair-chain` with
`--model-response-file` and optional `--target-root`. It creates a combined
repair request, attempt, extraction, and local plan artifact without resolving
an API key and always stops before apply.
For a swappable local provider, `local-repair-chain` can also use
`--model-command`. The command receives a JSON repair request on stdin and may
print raw model text, strict JSON edits, or a JSON object with a string
`content` field. On Windows, prefer a JSON array command form:

```bash
python scripts/biber_agent_client.py --json local-repair-chain prepared-repair.json \
  --model-command "[\"python\",\"scripts/biber_local_openai_provider.py\"]" \
  --target-root /path/to/repo \
  --output /tmp/local-repair-chain.json
```

Before letting a live provider plan against a non-disposable repo, use the
plan-only real-repo smoke. It records bounded source snippets, asks the
swappable provider for JSON edits, reviews the hash-guarded plan, and stops
before any apply or GitHub save:

```bash
python scripts/biber_live_provider_real_repo_plan_smoke.py \
  --base-url http://127.0.0.1:8001/v1 \
  --model biber-dev-core \
  --target-root /workspace/biber-ai-platform \
  --changed-paths-file /workspace/outputs/biber-changed-paths.txt \
  --pinned-paths-file /workspace/outputs/biber-pinned-paths.txt \
  --output /workspace/outputs/biber-real-repo-plan-latest.json
```

Use `--mode mock --cleanup` for the no-GPU/no-network local check. A passing
result must report `target_is_disposable=false`, `mutation_performed=false`,
`plan_outcome=planned_for_review`, `chain_status=planned`,
`review_status=ready_for_explicit_apply_approval`, `apply_allowed=false`, and
`repo_status_unchanged=true`. If the live model returns a safe no-op or
unusable edit, inspect `plan_outcome`, `model_response_content_preview`,
`extraction_status`, and rejection fields before retrying. Do not apply any
real-repo plan without a separate explicit apply approval.
The smoke preflights the required edit target size before readiness or model
calls. By default it refuses files larger than `BIBER_WORKSPACE_EDIT_MAX_FILE_BYTES`
or 200000 bytes, matching the workspace edit apply guard; split oversized
targets or choose a smaller required path before using the live GPU provider.
The default smoke edit uses a single exact docs line so the live 3B provider is
not judged on preserving wrapped paragraph line breaks.
That docs-line profile can choose between the accepted `BIBER-only` and
`BIBER MVP-only` wording variants when no explicit `--required-*` text is
provided, so the smoke remains usable after an approved wording apply.
After that docs proof is synced, use the first real code profile to test a
small Python source edit plan:

```bash
python scripts/biber_live_provider_real_repo_plan_smoke.py \
  --base-url http://127.0.0.1:8001/v1 \
  --model biber-dev-core \
  --target-root /workspace/biber-ai-platform \
  --smoke-profile code-unused-timeout
```

This profile asks the local provider to plan removal of one unused assignment in
`app/model_registry.py`, still with `python-compileall-api` as the verify step
after any later approved apply. It defaults to one context file so the live 3B
endpoint with `BIBER_MAX_MODEL_LEN=4096` has room for the prompt. The prompt
includes a preferred exact JSON edit and must still report
`mutation_performed=false` and stop before apply. If the live 3B model returns
`{"edits":[]}` for the exact edit, the smoke can use `required_edit_fallback` to
produce a review-only hash-guarded plan only after confirming the target file
contains `old_text` exactly once; the summary keeps the model no-op attempt as
separate evidence.
For the next real task, pass `--required-path` plus either
`--required-old-text`/`--required-new-text` or the `*-file` variants. The
summary records `required_edit`, and the flow still stops before apply.
For less fragile shell quoting, write a guarded JSON spec first and pass it with
`--required-edit-spec`:

```bash
python scripts/biber_agent_client.py --json write-next-required-edit-spec \
  /workspace/outputs \
  --target-root /workspace/biber-ai-platform \
  --required-path docs/BIBER_ONLY_WORKSPACE.md \
  --old-text-file /workspace/outputs/biber-old.txt \
  --new-text-file /workspace/outputs/biber-new.txt \
  --changed-paths-file /workspace/outputs/biber-changed-paths.txt \
  --pinned-paths-file /workspace/outputs/biber-pinned-paths.txt \
  --output /workspace/outputs/biber-next-required-edit-write-latest.json
```

The helper refuses unsafe paths, refuses to overwrite an existing active spec
unless `--replace` is passed, and probes `--target-root` before writing when a
target root is provided. That target probe also refuses files larger than
`BIBER_WORKSPACE_EDIT_MAX_FILE_BYTES` or 200000 bytes by default, before the
spec is saved; override only with `--max-required-edit-target-bytes` when the
workspace edit apply guard has been intentionally raised too. It accepts
repeated `--changed-path`/`--pinned-path`
flags plus newline-delimited `--changed-paths-file`/`--pinned-paths-file`
inputs; blank lines and `#` comments are ignored, and file entries are appended
after repeated CLI path flags. Inspect the active spec before running the live
model:

```bash
python scripts/biber_agent_client.py show-next-required-edit-spec \
  /workspace/outputs \
  --target-root /workspace/biber-ai-platform
```

The manual JSON shape is:

```json
{
  "path": "docs/BIBER_ONLY_WORKSPACE.md",
  "old_text": "exact old text\n",
  "new_text": "exact new text\n",
  "changed_paths": ["docs/BIBER_ONLY_WORKSPACE.md"],
  "max_context_files": 1
}
```

The spec may also use `old_text_file` and `new_text_file`; relative file paths
are resolved from the spec file directory. Explicit CLI `--required-*`,
`--changed-path`, `--pinned-path`, and instruction flags still override the
spec.
When the next intended plan-only edit is ready, save the guarded exact-edit spec as
`/workspace/outputs/biber-next-required-edit.json` and refresh
`live-mvp-resume-status`. If the spec is complete, `next_ready_commands` will
include `inspect_next_required_edit_spec` plus
`run_next_required_edit_spec_plan`. The inspection command is read-only and
confirms the same target probe before the plan command runs
`biber_live_provider_real_repo_plan_smoke.py --required-edit-spec ...` against
the current target root. The plan command uses the local provider/GPU and still
stops before apply, GitHub save, OpenAI mentor, or training. After a verified
edit is saved/pushed, replace this spec before rerunning the command so
completed edits are not planned again.
When the plan-only result is ready, its `explicit_apply_approval` block gives
the exact apply and verify command arrays. Treat them as pending instructions:
do not run apply until the user explicitly approves the specific `plan_hash`,
then run verify immediately after apply.
To reopen or scan saved real-repo plan smoke summaries without rerunning the
local model:

```bash
python scripts/biber_agent_client.py show-real-repo-plan-smoke \
  /workspace/outputs/biber-real-repo-plan-latest.json
python scripts/biber_agent_client.py show-latest-real-repo-plan-smoke \
  /workspace/outputs \
  --pattern "*real-repo-plan*.json" \
  --target-root /workspace/biber-ai-platform
python scripts/biber_agent_client.py list-real-repo-plan-smokes \
  /workspace/outputs \
  --pattern "*real-repo-plan*.json" \
  --target-root /workspace/biber-ai-platform \
  --output /workspace/outputs/biber-real-repo-plan-smoke-list.json
```

To summarize the latest live MVP readiness, real-repo plan, and GitHub bridge
dry-run artifacts together without rerunning GPU/model work:

```bash
python scripts/biber_agent_client.py live-mvp-resume-status \
  /workspace/outputs \
  --target-root /workspace/biber-ai-platform \
  --python-command /workspace/biber-venv/bin/python \
  --live-base-url http://127.0.0.1:8001/v1 \
  --live-model biber-dev-core \
  --output /workspace/outputs/biber-live-mvp-resume-status-latest.json
```

This command is offline and read-only. It should report any pending
`plan_hash` that needs a separate explicit apply decision, and it must not call
GitHub, OpenAI mentor, training, external APIs, or apply files.
If the latest verified GitHub dry-run bridge has the same `plan_hash` as the
latest real-repo plan, the status command treats that plan as already
applied/verified historically and will not ask for duplicate apply approval.
It also checks whether the linked apply artifact's `new_sha256` values still
match the current target files. With a clean target git checkout, `next_action`
should become `start_next_narrow_biber_step`; with a dirty target checkout, it
should become `save_verified_change_to_github_if_requested`.
The JSON output includes `next_commands`, a small list of safe command hints
for the reported `next_action`. Use `--python-command` to make those hints
match the current runtime, for example `/workspace/biber-venv/bin/python` on
Vast. Use `--live-base-url` and `--live-model` to keep the hints aligned with
the currently served local provider or candidate model. Treat commands with
`ready_to_run=false` as templates that need exact task inputs first. These hints
do not override the normal gates: real-repo apply, training, OpenAI mentor, and
real GitHub save/PR still need separate explicit approval.
When top-level canonical files such as
`/workspace/outputs/biber-live-provider-confidence-latest.json`,
`/workspace/outputs/biber-real-repo-plan-latest.json`,
`/workspace/outputs/biber-live-verified-github-dry-run-latest.json`, or
`/workspace/outputs/biber-live-mvp-resume-status-latest.json` exist, latest
artifact discovery prefers those files over newer nested disposable smoke
artifacts. This keeps throwaway validation directories from accidentally
becoming the real resume state.
Automation should prefer `next_ready_commands` when it wants only fully
specified safe commands; this filtered subset excludes templates and any command
that would mutate the repo, send GitHub requests, use OpenAI mentor, or allow
training.
If `apply_decision_status` is
`already_verified_history_stale_file_hashes`, the saved apply history still
matches the plan hash, but the target file has moved since that verified apply.
Treat it as historical evidence, not a fresh apply candidate; if the target Git
status is clean, continue with the next narrow BIBER step.
When no active `biber-next-required-edit.json` exists, `next_commands` includes
a non-ready `write_next_required_edit_spec_template` to show the exact helper
shape for the next spec; fill in the path and text files before running it.
When a target-root-matching failed saved `mvp-loop` artifact exists and the
current verified plan is already handled, `live-mvp-resume-status` may include a
safe ready command labeled `prepare_latest_repair`. That command runs
`prepare-latest-repair` against the outputs directory, builds a local repair
request from the latest failed artifact for the same target root, and does not
call a model, GitHub, OpenAI mentor, training, or external APIs.
To print one saved ready command without parsing JSON manually:

```bash
python scripts/biber_agent_client.py show-live-mvp-ready-command \
  /workspace/outputs/biber-live-mvp-resume-status-latest.json \
  --label rerun_live_provider_confidence_gate \
  --command-only
```

To list every saved ready command in a compact read-only view:

```bash
python scripts/biber_agent_client.py list-live-mvp-ready-commands \
  /workspace/outputs/biber-live-mvp-resume-status-latest.json
```

When the exact status JSON path is not known, use the latest-artifact variants:

```bash
python scripts/biber_agent_client.py show-latest-live-mvp-ready-command \
  /workspace/outputs \
  --label refresh_resume_status

python scripts/biber_agent_client.py list-latest-live-mvp-ready-commands \
  /workspace/outputs
```

To run one saved ready command through the built-in guard instead of copying the
command by hand:

```bash
python scripts/biber_agent_client.py run-live-mvp-ready-command \
  /workspace/outputs/biber-live-mvp-resume-status-latest.json \
  --label refresh_resume_status \
  --cwd /workspace/biber-ai-platform
```

If the exact resume-status JSON path is not known, let the client discover the
newest valid saved status artifact under the outputs directory and then run the
same guarded command:

```bash
python scripts/biber_agent_client.py run-latest-live-mvp-ready-command \
  /workspace/outputs \
  --label refresh_resume_status \
  --cwd /workspace/biber-ai-platform
```

The runner executes only commands already present in `next_ready_commands` and
still rejects repo mutation, GitHub requests, OpenAI mentor use, training,
external-network requirements, and API-required commands. GPU/live-provider
commands require explicit `--allow-gpu --allow-live-provider`; use `--dry-run`
when you only want to verify the selected command and safety guard.

This keeps Qwen2.5, Qwen3, llama.cpp, vLLM wrappers, and future local runners
swappable without enabling OpenAI mentor, API auth, GPU training, or file apply.
`scripts/biber_local_openai_provider.py` is the stdlib OpenAI-compatible
wrapper. Set `BIBER_LOCAL_OPENAI_BASE_URL` to the local endpoint base URL
(default `http://127.0.0.1:8001/v1`) and optionally
`BIBER_LOCAL_OPENAI_MODEL` to the served model or LoRA alias. If the endpoint
requires a token, put it in `BIBER_LOCAL_OPENAI_API_KEY`; do not paste it into
chat or commit it. Without an explicit `--model` or
`BIBER_LOCAL_OPENAI_MODEL`, the wrapper resolves logical BIBER IDs such as
`biber-dev-core-v1` and `biber-dev-core-v2-candidate` through the local model
registry/env defaults before sending the provider request, so the live endpoint
receives the served alias (for example `biber-dev-core`) instead of the logical
API model ID.
To check whether a live OpenAI-compatible provider is reachable without
sending a repair request or chat completion, run:

```bash
python scripts/biber_live_provider_readiness.py --model biber-dev-core-v1
```

Add `--require-ready --require-model` when you want the command to exit nonzero
unless `/v1/models` is reachable and the requested model/adapter alias is
listed.
To run the proven disposable live repair path as one command on Vast:

```bash
python scripts/biber_live_provider_repair_smoke.py \
  --base-url http://127.0.0.1:8001/v1 \
  --model biber-dev-core
```

The script creates a disposable target repo, runs the local repair loop through
the live provider wrapper, applies only to that disposable target after the
normal review/hash gate is ready, verifies with `python-compileall-api`, and
does not use OpenAI mentor, training, or GitHub save. Use `--mode mock` for
local no-GPU validation of the script itself.
To verify the wrapper without a GPU or live model endpoint, run:

```bash
python scripts/biber_local_openai_provider_smoke.py
```

The smoke starts a temporary localhost `/v1/chat/completions` mock, confirms
the wrapper sends the expected OpenAI-compatible payload and optional bearer
token, and verifies the returned `content` JSON can carry repair edits.
The wrapper also prepends a strict repair system prompt before calling the
local OpenAI-compatible endpoint. Local models must return one JSON object
only, must not use Markdown fences/prose, must copy `old_text` exactly from the
prepared repair source snippets, and must return `{"edits":[]}` instead of
inventing file contents or paths. Source snippets are bounded and skip
secret-like files, dependency/cache folders, and symlinks.

For client tools that want to consume BIBER itself as a model source, use the
BIBER API gateway endpoint `POST /v1/chat/completions` with
`Authorization: Bearer <api-key>` or `x-api-key: <api-key>`. This endpoint is
OpenAI-compatible, uses the same swappable model registry, and keeps OpenAI
mentor disabled by default. A `.com` domain is not needed for local/private MVP
testing; public internet clients need a later HTTPS domain/reverse-proxy layer
and admin key-management portal. The backend key-management MVP is
`GET/POST/DELETE /v1/admin/api-keys`, protected by `BIBER_ADMIN_API_KEY`, with
issued user keys stored as hashes under `BIBER_API_KEY_STORE_PATH`. Use
`admin-api-key-contract-smoke` for a list-only redacted endpoint proof before
building an admin UI or gateway; use `--allow-missing-admin-key` for non-secret
blocked evidence before credentials are configured. See
`docs/BIBER_EXTERNAL_AGENT_API.md`.
Then run `review-local-repair-chain` on that combined artifact before asking
for explicit apply approval. The review is deterministic, no-API, and reports
blockers, warnings, plan hash, target root, and the next test id.
If apply is explicitly approved, pass the accepted review artifact to
`apply-repair-edits --approve --review-artifact ...`. The apply command checks
that the review is ready and that its plan hash matches the repair plan before
it changes files.
After apply, run `local-verify-chain` on the apply artifact. It reruns the
recorded next test against the local target root, optionally diagnoses failures
locally, and emits a compact `verified` / `still_failing` / `not_executed`
artifact for the next loop without resolving API credentials.
If the result is `still_failing`, run `prepare-local-verify-repair` on the
local verification chain artifact. It creates the next local-model repair
request, carries the failed edit paths as context, records forbidden exact
edits when the linked apply artifact is available, and still does not resolve
API credentials.
When resuming from an artifact directory, run `local-repair-loop-status` first.
It scans local JSON artifacts, identifies the newest known BIBER repair-loop
state, and prints the next exact no-API command to run.
For MVP-loop artifact directories, `list-mvp-loops` shows compact
`agent_report_status`, context/test modes, and edit review status per artifact
so you can quickly choose which saved loop to inspect or repair.
For failed MVP-loop artifacts, the list JSON also carries repair-hint status,
category, stack, first repair step, and the exact next command when available.
For failed MVP-loop and prepared repair artifacts, the status output surfaces
the repair-hint status, primary failure category, detected stack, and first
local repair workflow steps so future sessions can resume without scraping raw
test output.
For a quick end-to-end local confidence check after changing this workflow, run:

```bash
python scripts/biber_local_confidence_smoke.py
```

To save the confidence result and summarize it later without rerunning the full
gate:

```bash
python scripts/biber_local_confidence_smoke.py \
  --output /workspace/outputs/biber-local-confidence-smoke.json
python scripts/biber_agent_client.py show-confidence-smoke \
  /workspace/outputs/biber-local-confidence-smoke.json
python scripts/biber_agent_client.py list-confidence-smokes \
  /workspace/outputs \
  --pattern "*confidence-smoke*.json" \
  --output /workspace/outputs/biber-local-confidence-smoke-list.json
python scripts/biber_agent_client.py list-mvp-loops \
  /workspace/outputs \
  --failed-only \
  --output /workspace/outputs/biber-mvp-loop-list.json
python scripts/biber_agent_client.py show-mvp-loop-list \
  /workspace/outputs/biber-mvp-loop-list.json
```

This combined smoke runs the mocked local OpenAI-compatible provider HTTP smoke,
the mocked live-provider readiness smoke, the local MVP-loop edit-review smoke,
the local MVP-loop failure/repair-hint smoke, the real-checkout MVP-loop
repo-probe dry run, the mock real-repo plan smoke, the full local MVP-loop
repair smoke, the verified-repair GitHub dry-run handoff smoke, the standalone
GitHub dry-run artifact smoke, the live verified-repair GitHub dry-run bridge
in fixture mode, and the local repair-loop smoke together. It is the preferred
pre-live-provider gate before asking for Vast GPU credentials or pointing BIBER
at a real local Qwen/vLLM endpoint.
The real-checkout repo-probe also verifies that `mvp-loop` accepts
`--pinned-paths-file` and `--changed-paths-file` in the local path.
`show-confidence-smoke` and `list-confidence-smokes` surface this path-list
evidence plus the live verified-repair GitHub dry-run bridge status from saved
confidence artifacts.
`list-mvp-loops --output` can save the discovered loop artifacts and repair
next-step metadata for later resume, and `show-mvp-loop-list` summarizes that
saved list without rerunning the scan.
After a local repair attempt exists, `list-repair-attempts --output` saves the
ready-for-edit-review queue and `show-repair-attempt-list` reopens that queue
without rerunning the directory scan.
After repair edits are extracted, `list-repair-edit-extractions --output` saves
the ready-for-plan queue and `show-repair-edit-extraction-list` reopens that
queue without rerunning the directory scan.
After repair edit plans exist, `list-repair-edit-plans --output` saves the
planned queue and `show-repair-edit-plan-list` reopens that queue without
rerunning the directory scan.
After guarded repair edits are applied, `list-repair-edit-applies --output`
saves the applied queue and `show-repair-edit-apply-list` reopens that queue
without rerunning the directory scan.
After repaired tests are verified, `list-repair-test-verifications --output`
saves the passed-verification queue and `show-repair-test-verification-list`
reopens that queue without rerunning the directory scan.
After verified repairs are reviewed, `list-verified-repair-reviews --output`
saves the human-review queue and `show-verified-repair-review-list` reopens
that queue without rerunning the directory scan.
After repair-chain summaries exist, `list-repair-chains --output` saves the
ready-chain queue and `show-repair-chain-list` reopens that queue without
rerunning the directory scan.
After ready repair-chain reviews exist, `list-ready-repair-chain-reviews --output`
saves the review queue and `show-ready-repair-chain-review-list` reopens that
queue without rerunning the directory scan.
After ready repair-chain decisions are reviewed,
`list-ready-repair-chain-decision-reviews --output` saves the decision-review
queue and `show-ready-repair-chain-decision-review-list` reopens that queue
without rerunning the directory scan.
After ready repair-chain eval candidates are reviewed,
`list-ready-repair-chain-eval-candidate-reviews --output` saves the
eval-candidate review queue and
`show-ready-repair-chain-eval-candidate-review-list` reopens that queue without
rerunning the directory scan.
After eval-dataset decisions are reviewed,
`list-ready-repair-chain-eval-dataset-decision-reviews --output` saves the
eval-dataset decision review queue and
`show-ready-repair-chain-eval-dataset-decision-review-list` reopens that queue
without rerunning the directory scan.
After eval datasets are validated,
`list-ready-repair-chain-eval-dataset-validations --output` saves the validation
queue and `show-ready-repair-chain-eval-dataset-validation-list` reopens that
queue without rerunning the directory scan.
After eval prompts are exported, `list-ready-repair-chain-eval-prompts --output`
saves the held-out eval prompt queue and `show-ready-repair-chain-eval-prompt-list`
reopens that queue without rerunning the directory scan.
It also includes the full local MVP-loop repair smoke, which starts from a real
failed local `mvp-loop` artifact and walks through local-model repair, review,
guarded apply, verification, and status without API credentials.

To run only the local MVP-loop edit-review smoke:

```bash
python scripts/biber_local_mvp_loop_smoke.py
```

The smoke creates a temporary target repo, runs `mvp-loop --local-target-root`
with two guarded local edits, applies them through the hash-guarded local path,
and verifies that `agent_report.edit` exposes the deterministic workspace edit
review metadata. It does not require BIBER API, OpenAI, Vast GPU, or training
credentials.

To run only the local MVP-loop failure/repair-hint smoke:

```bash
python scripts/biber_local_mvp_loop_failure_smoke.py
```

The smoke creates a temporary target repo with a Python syntax failure, runs
`mvp-loop --local-target-root`, verifies `agent_report.repair_hint`, and runs
`prepare-repair` to prove the hint is preserved for the next local-model repair
step and included in the bounded repair prompt. It also verifies
`list-mvp-loops --failed-only` exposes the repair-hint status and next repair
step from the saved failed artifact, then verifies `show-mvp-loop-list` can
read the saved list artifact back. It does not require BIBER API, OpenAI, Vast
GPU, or training credentials.

To run only the real-checkout MVP-loop repo-probe smoke:

```bash
python scripts/biber_local_mvp_loop_repo_probe_smoke.py
```

The smoke points `mvp-loop --local-target-root` at this BIBER checkout with
`--include-git-state`, changed-path hints, and `--test-dry-run`. It verifies
real repo context selection, git-state capture, dry-run test reporting, and
that the repo status is unchanged by the probe. It does not require BIBER API,
OpenAI, Vast GPU, or training credentials.

To run only the full local MVP-loop repair smoke:

```bash
python scripts/biber_local_mvp_loop_full_repair_smoke.py
```

The smoke creates a temporary target repo with a Python syntax failure and runs
the full local coding-assistant path:
`mvp-loop -> prepare-repair -> local-repair-chain --model-command ->
review-local-repair-chain -> apply-repair-edits --approve --review-artifact ->
local-verify-chain -> local-repair-loop-status`. It uses a fixture
model-command provider and does not require BIBER API, OpenAI, Vast GPU, or
training credentials.

To run only the verified-repair GitHub dry-run handoff smoke:

```bash
python scripts/biber_local_verified_repair_github_dry_run_smoke.py
```

The smoke runs the full local MVP-loop repair smoke, points
`save-github --dry-run` at the verified repaired file, then runs
`create-pr --dry-run` for the review branch. It verifies no GitHub request was
sent. It also verifies the integrated `mvp-loop --github-dry-run` save/PR
handoff fields. It does not require BIBER API, GitHub credentials, OpenAI, Vast
GPU, or training credentials.

To run only the standalone GitHub dry-run artifact smoke:

```bash
python scripts/biber_local_github_dry_run_artifacts_smoke.py
```

The smoke creates `save-github --dry-run` and `create-pr --dry-run` artifacts,
runs `show-github-dry-run` on each, and runs `list-github-dry-runs` over the
artifact directory. It verifies no GitHub request was sent and does not require
BIBER API, GitHub credentials, OpenAI, Vast GPU, or training credentials.

To create GitHub save/PR dry-runs from a verified live-provider repair:

```bash
python scripts/biber_live_verified_repair_github_dry_run_smoke.py \
  --verification-artifact /workspace/outputs/.../artifacts/real-repo-local-verify-chain.json \
  --target-root /workspace/biber-ai-platform \
  --branch biber/live-verified-repair
```

This post-verification bridge reads the verified `local-verify-chain` artifact,
confirms the linked `apply-repair-edits` artifact was applied and verified, then
writes `save-github --dry-run`, `create-pr --dry-run`, and
`list-github-dry-runs` artifacts. It sends no GitHub request, uses no OpenAI
mentor, runs no model inference, and starts no training. Review the dry-run
artifacts before any real GitHub save or PR. The combined confidence gate runs
the same bridge in `--mode fixture` so this handoff path is checked locally even
when no live Vast artifact is available.
To reopen saved bridge summaries without rerunning the smoke:

```bash
python scripts/biber_agent_client.py show-live-verified-github-dry-run \
  /workspace/outputs/biber-live-verified-github-dry-run-latest.json
python scripts/biber_agent_client.py show-latest-live-verified-github-dry-run \
  /workspace/outputs \
  --pattern "*live-verified-github-dry-run*.json" \
  --target-root /workspace/biber-ai-platform
python scripts/biber_agent_client.py list-live-verified-github-dry-runs \
  /workspace/outputs \
  --pattern "*live-verified-github-dry-run*.json" \
  --target-root /workspace/biber-ai-platform \
  --output /workspace/outputs/biber-live-verified-github-dry-run-list.json
```

To run a quick live local-model plan-only check on Vast without touching the
active repo:

```bash
python scripts/biber_live_provider_fixture_plan_smoke.py \
  --base-url http://127.0.0.1:8001/v1 \
  --model biber-dev-core
```

This creates a disposable target under `/workspace/outputs`, routes it through
the same real-repo plan-only path, and stops before apply/save. It is the
preferred quick GPU-backed validation when the Vast runtime is already running.
It sends no GitHub request, uses no OpenAI mentor, and starts no training.

To run the preferred one-command live local-model confidence check on Vast:

```bash
python scripts/biber_live_provider_confidence_smoke.py \
  --base-url http://127.0.0.1:8001/v1 \
  --model biber-dev-core \
  --output /workspace/outputs/biber-live-provider-confidence-latest.json
```

This combines live-provider readiness, disposable fixture plan-only validation,
and disposable live repair validation. It is GPU-backed in `--mode live` and can
also run locally with `--mode mock`. It sends no GitHub request, uses no OpenAI
mentor, starts no training, and only applies edits inside a disposable target
created under the smoke work directory.
To reopen or scan saved live-provider confidence artifacts without rerunning the
GPU checks:

```bash
python scripts/biber_agent_client.py show-live-provider-confidence \
  /workspace/outputs/biber-live-provider-confidence-latest.json
python scripts/biber_agent_client.py show-latest-live-provider-confidence \
  /workspace/outputs \
  --pattern "*live-provider-confidence*.json"
python scripts/biber_agent_client.py list-live-provider-confidence \
  /workspace/outputs \
  --pattern "*live-provider-confidence*.json" \
  --output /workspace/outputs/biber-live-provider-confidence-list.json
```

To run only the repair-loop smoke:

```bash
python scripts/biber_local_repair_loop_smoke.py
```

The smoke creates a temporary target repo, runs prepare/local-chain/review/
guarded-apply/verify/status with a temporary local model-command provider
fixture, and does not require BIBER API, OpenAI, Vast GPU, or training
credentials.

## Vast GPU

Do not ask for Vast credentials for ordinary source work. Ask only when a step
requires live model serving, batch evals, adapter restore, or QLoRA/training.
Use `docs/BIBER_LIVE_PROVIDER_RUNBOOK.md` for the exact questions and readiness
commands when that point arrives.
