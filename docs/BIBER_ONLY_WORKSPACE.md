# BIBER-Only Workspace

Use this document when continuing BIBER MVP from the sparse checkout at:

```text
C:\Users\vselv\OneDrive\Biber\biber-mvp-only
```

This folder is intentionally filtered so BIBER work does not need to scan or
reason about the separate XRIS-Coin/XRIQ project.

## Scope

Continue BIBER MVP only:

- swappable model providers and model registry
- repo-context selection
- safe workspace edit planning and apply
- test execution and diagnosis
- agent client MVP loop
- GitHub save/PR path
- optional OpenAI mentor, disabled by default
- GPU eval/training only when a concrete BIBER model gap requires it

Do not continue XRIS-Coin/XRIQ from this workspace unless the user explicitly
asks for it.

## Start Prompt

```text
Read docs/BIBER_ONLY_WORKSPACE.md, readme-resume-biber.md, and the BIBER
sections at the top of docs/CODEX_HANDOFF.md. Continue BIBER MVP only from the
current branch. Do not continue XRIS-Coin/XRIQ work. Keep providers swappable,
keep OpenAI mentor optional and disabled by default, and prefer CPU-local
workflow improvements before asking for GPU credentials.
```

## Local MVP Loop

Prefer the CPU-local agent-client path before using a live API:

```bash
python scripts/biber_agent_client.py --json mvp-loop \
  --instruction "Plan or validate a narrow code change." \
  --local-target-root /path/to/repo \
  --include-git-state \
  --changed-path src/example.py \
  --test-id python-compileall-api \
  --test-dry-run \
  --output /tmp/biber-mvp-loop.json
```

With `--local-target-root`, context planning, safe edit plan/apply, test
execution, and diagnosis are local. GitHub save/PR remains server-backed.
Use `--include-git-state` for repo work so the artifact records the local
branch, short HEAD, dirty status, and `git status --short` before edits/tests.
Each MVP-loop artifact includes `agent_report`, a compact machine-readable
status summary with repo state, selected context, edit counts, test result,
failure summary, and next actions for the following narrow step.
When an MVP-loop artifact fails, run `prepare-repair` first. It preserves
`agent_report` in the repair request and includes the report in the bounded
local-model repair prompt, with OpenAI mentor still disabled unless explicitly
requested later through the separate repair-attempt path.
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

This keeps Qwen2.5, Qwen3, llama.cpp, vLLM wrappers, and future local runners
swappable without enabling OpenAI mentor, API auth, GPU training, or file apply.
`scripts/biber_local_openai_provider.py` is the stdlib OpenAI-compatible
wrapper. Set `BIBER_LOCAL_OPENAI_BASE_URL` to the local endpoint base URL
(default `http://127.0.0.1:8001/v1`) and optionally
`BIBER_LOCAL_OPENAI_MODEL` to the served model or LoRA alias. If the endpoint
requires a token, put it in `BIBER_LOCAL_OPENAI_API_KEY`; do not paste it into
chat or commit it.
To verify the wrapper without a GPU or live model endpoint, run:

```bash
python scripts/biber_local_openai_provider_smoke.py
```

The smoke starts a temporary localhost `/v1/chat/completions` mock, confirms
the wrapper sends the expected OpenAI-compatible payload and optional bearer
token, and verifies the returned `content` JSON can carry repair edits.
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
For a quick end-to-end local confidence check after changing this workflow, run:

```bash
python scripts/biber_local_confidence_smoke.py
```

This combined smoke runs the mocked local OpenAI-compatible provider HTTP smoke
and the local repair-loop smoke together. It is the preferred pre-live-provider
gate before asking for Vast GPU credentials or pointing BIBER at a real local
Qwen/vLLM endpoint.

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
