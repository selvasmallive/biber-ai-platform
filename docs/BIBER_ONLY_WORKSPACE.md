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
Use `--include-git-state` for repo work so the artifact records the local
branch, short HEAD, dirty status, and `git status --short` before edits/tests.
Repo-context and safe-edit paths must stay workspace-relative; Windows
drive-relative paths are rejected, and repo-context scanning skips symlinked
entries so local context does not follow links outside the target repo.
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
repo-probe dry run, the verified-repair GitHub dry-run handoff smoke, the
standalone GitHub dry-run artifact smoke, and the local repair-loop smoke
together. It is the preferred pre-live-provider gate before asking for Vast GPU
credentials or pointing BIBER at a real local Qwen/vLLM endpoint.
The real-checkout repo-probe also verifies that `mvp-loop` accepts
`--pinned-paths-file` and `--changed-paths-file` in the local path.
`show-confidence-smoke` and `list-confidence-smokes` surface this path-list
evidence from saved confidence artifacts.
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
