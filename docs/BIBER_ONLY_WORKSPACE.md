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

## Vast GPU

Do not ask for Vast credentials for ordinary source work. Ask only when a step
requires live model serving, batch evals, adapter restore, or QLoRA/training.
