# API Examples

## List Models

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer dev-api-key-change-me"
```

The response includes stable/candidate model metadata. By default
`biber-dev-core-v1` is enabled and backed by the current local Qwen2.5-Coder
runtime, while `biber-dev-core-v2-candidate` is disabled until a Qwen3 or newer
candidate endpoint is configured and benchmarked.

## Runtime Status

```bash
curl http://localhost:8000/v1/runtime \
  -H "Authorization: Bearer dev-api-key-change-me"
```

## Generate Code With biber-dev-core

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "X-Biber-Passcode: BIBER_QUEUE_PRIORITY_DEMO" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "TypeScript",
    "model": "biber-dev-core-v1",
    "task_type": "code_generation",
    "repo_context_paths": ["src/components/SearchBox.tsx"],
    "messages": [
      {
        "role": "user",
        "content": "Create a React hook that debounces a search query."
      }
    ]
}'
```

`repo_context_paths` accepts selected workspace-relative files only. The server
applies file-count and byte limits and rejects `.env`, private-key-looking
files, cache directories, and paths outside the configured repo context root.

## Optional Runtime Profiles

Runtime profiles are narrow prompt contracts for known model gaps. They are
disabled unless the server sets `BIBER_RUNTIME_PROFILES_ENABLED=true`, and the
client must still request specific profile IDs with `runtime_profile_ids`.

Current profile IDs:

- `api-error-response`: stable JSON-style API error response shape.
- `rust-xriq-codegen`: Rust/XRIQ helper output shaped for rustfmt and
  borrow-checker safety.

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "Rust",
    "model": "biber-dev-core-v1",
    "task_type": "xriq_private_devnet_review",
    "runtime_profile_ids": ["rust-xriq-codegen"],
    "messages": [
      {
        "role": "user",
        "content": "Write a next_height(parent: &BlockHeader) helper."
      }
    ]
}'
```

`GET /v1/agent/capabilities` exposes whether runtime profiles are enabled and
which profile IDs the client can request. Keep these profiles opt-in until a
candidate adapter is explicitly approved for promotion against profiled evals.

## Plan Repo Context

Client tools can ask BIBER to select a safe starter context before creating a
chat or agent session. The planner is deterministic: it detects common stack
signals, keeps pinned and changed files first, adds related tests and project
manifests, and avoids secrets, dependency folders, build outputs, and binaries.

```bash
curl -X POST http://localhost:8000/v1/repo/context/plan \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Fix the WeatherController forecast route.",
    "changed_paths": ["src/Example.Api/Controllers/WeatherController.cs"],
    "pinned_paths": ["README.md"],
    "max_files": 8
  }'
```

Use the returned `selected_paths` as `repo_context_paths` for `/v1/chat` or
`/v1/agent/sessions`. The response also includes stack profiles for detected
`.NET` and Java projects, including preferred manifest/entrypoint patterns and
the matching allowlisted test IDs such as `dotnet-test`, `maven-test`,
`gradle-test`, and `gradle-wrapper-test`.

## Queue Chat Job Instead Of Immediate Inference

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a FastAPI endpoint for health check",
    "queue_only": true
}'
```

## Request OpenAI Mentor Review

Set `BIBER_MENTOR_ENABLED=true`, `OPENAI_API_KEY`, and `OPENAI_MODEL` on the
server first. BIBER calls OpenAI only when the prompt includes the explicit
trigger phrase `Review with OpenAI mentor`.

```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "Rust",
    "task_type": "security_review",
    "messages": [
      {
        "role": "user",
        "content": "Review with OpenAI mentor: Review this XRIQ transaction validation design."
      }
    ]
  }'
```

## Submit Code Task

```bash
curl http://localhost:8000/v1/code \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "X-Biber-Passcode: BIBER_QUEUE_PRIORITY_DEMO" \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "prompt": "Create a FastAPI endpoint for health check",
    "model": "biber-dev-core"
  }'
```

## Save Generated Code To GitHub

Set `GITHUB_TOKEN`, `GITHUB_DEFAULT_OWNER`, and `GITHUB_DEFAULT_REPO` in `.env`, then:

```bash
curl -X POST http://localhost:8000/v1/save/github \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "target": {
      "path": "generated/example.ts",
      "branch": "biber/generated-example",
      "base_branch": "main",
      "create_branch_if_missing": true,
      "commit_message": "Save generated BIBER example"
    },
    "content": "export const hello = () => \"biber\";\n"
}'
```

Then open a draft pull request for review:

```bash
curl -X POST http://localhost:8000/v1/github/pull-request \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "head": "biber/generated-example",
    "base": "main",
    "title": "Save generated BIBER example",
    "body": "Generated by BIBER and ready for review.",
    "draft": true
}'
```

The stdlib client wraps the same endpoints. It does not read GitHub tokens
directly; the server must already have GitHub configured in `.env`.
Use `--dry-run` first to build and inspect the payload locally without
resolving a BIBER API key or sending a GitHub request.

```bash
python scripts/biber_agent_client.py --json save-github \
  --dry-run \
  --path generated/example.ts \
  --content-file generated/example.ts \
  --branch biber/generated-example \
  --base-branch main \
  --create-branch-if-missing \
  --commit-message "Save generated BIBER example"
python scripts/biber_agent_client.py --json create-pr \
  --dry-run \
  --head biber/generated-example \
  --base main \
  --title "Save generated BIBER example" \
  --body "Generated by BIBER and ready for review."
python scripts/biber_agent_client.py save-github \
  --path generated/example.ts \
  --content-file generated/example.ts \
  --branch biber/generated-example \
  --base-branch main \
  --create-branch-if-missing \
  --commit-message "Save generated BIBER example"
python scripts/biber_agent_client.py create-pr \
  --head biber/generated-example \
  --base main \
  --title "Save generated BIBER example" \
  --body "Generated by BIBER and ready for review."
```

## Run Allowlisted Project Tests

BIBER exposes only fixed server-side test IDs. Clients cannot submit arbitrary
commands, directories, or file paths through this endpoint.

```bash
curl http://localhost:8000/v1/tests \
  -H "Authorization: Bearer dev-api-key-change-me"
```

```bash
curl -X POST http://localhost:8000/v1/tests/run \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "test_id": "python-compileall-api"
  }'
```

Use `dry_run: true` to inspect the selected command without executing it.

Current stack-oriented test IDs include:

- `dotnet-test`: runs `dotnet test --nologo`
- `maven-test`: runs `mvn test`
- `gradle-test`: runs `gradle test`
- `gradle-wrapper-test`: runs `./gradlew test`

## Diagnose Test Failure Output

This endpoint turns raw test output into a compact, structured diagnosis for a
client agent. It is deterministic and does not call a model. Use it after a
failed test run to classify the likely failure type and collect concise context
for BIBER.

```bash
curl -X POST http://localhost:8000/v1/tests/diagnose \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "test_id": "dotnet-test",
    "command": ["dotnet", "test"],
    "exit_code": 1,
    "stdout": "Example.cs(7,1): error CS1002: ; expected\n",
    "max_context_lines": 40
  }'
```

The first version detects common `.NET`, Java/Maven/Gradle, Rust/Cargo,
Python/pytest, and Node/Jest/Vitest failure signals.

## Apply A Bounded Workspace Edit

This endpoint performs one exact text replacement in a workspace-relative text
file, or creates a new text file only when `create_if_missing` is explicitly
set. It rejects path escapes, secret-looking paths, cache directories, common
binary file types, oversized files, and replacement-count mismatches.

```bash
curl -X POST http://localhost:8000/v1/files/edit \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "generated/example.ts",
    "old_text": "export const hello = () => \"old\";",
    "new_text": "export const hello = () => \"biber\";",
    "expected_replacements": 1
  }'
```

Use `dry_run: true` to validate the path and replacement count without writing
the file.

## Plan Multiple Workspace Edits

This endpoint validates a small batch of proposed file edits without writing
anything. Use it before asking a client tool to apply a multi-file patch. It
returns accepted edit previews, rejected edit reasons, hashes, byte counts, and
a simple risk marker. A clean plan also returns `plan_hash`; clients must send
that exact hash to the apply endpoint.

```bash
curl -X POST http://localhost:8000/v1/files/edit/plan \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "max_files": 4,
    "edits": [
      {
        "path": "src/example.py",
        "old_text": "return a + b",
        "new_text": "return int(a) + int(b)",
        "expected_replacements": 1
      },
      {
        "path": "generated/notes.md",
        "new_text": "planned note\n",
        "create_if_missing": true
      }
    ]
}'
```

## Apply A Planned Multi-File Edit

This endpoint writes a small multi-file edit only after BIBER recomputes the
plan and confirms the supplied `plan_hash` still matches the current workspace.
If the hash is stale or the plan has rejected edits, nothing is written. If a
write fails mid-apply, BIBER rolls back files it already touched.

```bash
curl -X POST http://localhost:8000/v1/files/edit/apply \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_hash": "<plan_hash from /v1/files/edit/plan>",
    "max_files": 4,
    "edits": [
      {
        "path": "src/example.py",
        "old_text": "return a + b",
        "new_text": "return int(a) + int(b)",
        "expected_replacements": 1
      },
      {
        "path": "generated/notes.md",
        "new_text": "planned note\n",
        "create_if_missing": true
      }
    ]
  }'
```

## Run The BIBER Agent Smoke

On Vast.ai, this script checks the live agent flow: repo-context chat,
workspace-edit dry-run, stdlib client capabilities and low-token
`create-session`, allowlisted test execution, and optional GitHub save/PR only
when explicitly enabled.

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_biber_agent_smoke.sh
```

To include GitHub save and draft-PR creation, configure GitHub credentials on
the server first, then run with `BIBER_AGENT_SMOKE_GITHUB=1`.

## Run The Stable Profile Baseline

On Vast.ai, this script verifies the current stable adapter with runtime
profiles enabled. It checks live status, runs the runtime-profile client smoke,
runs the broad API-error profile eval, and runs the Rust/XRIQ eval with cargo
validators. It does not train, reload a candidate adapter, or promote an
adapter.

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_profile_baseline_direct.sh
```

The combined summary is written under
`/workspace/outputs/profile-baseline-*/profile-baseline.summary.json`.

## Discover Agent Capabilities

Client tools can call this endpoint before creating sessions. It returns the
safe workflow surface, allowlisted test commands, and request templates for
common session presets such as XRIQ private-devnet review. It does not return
API keys or other secrets.

```bash
curl http://localhost:8000/v1/agent/capabilities \
  -H "Authorization: Bearer dev-api-key-change-me"
```

The stdlib client helper can consume the same endpoint and create sessions from
the advertised presets. It can also list and load persisted sessions for
client UIs that need a lightweight work history.

```bash
export BIBER_API_KEY=dev-api-key-change-me
python scripts/biber_agent_client.py capabilities
python scripts/biber_agent_client.py chat \
  --message "Return one concise Rust helper review note." \
  --language Rust \
  --task-type xriq_private_devnet_review \
  --repo-context README.md \
  --runtime-profile-id rust-xriq-codegen \
  --max-tokens 80
python scripts/biber_agent_client.py create-session \
  --preset xriq_private_devnet_review \
  --instruction "Review the next XRIQ private-devnet wallet/explorer step." \
  --runtime-profile-id rust-xriq-codegen \
  --no-test
python scripts/biber_agent_client.py list-sessions --limit 5
python scripts/biber_agent_client.py get-session <session-id>
python scripts/biber_agent_client.py plan-context \
  --instruction "Fix the WeatherController forecast route." \
  --pinned-path README.md \
  --changed-path src/Example.Api/Controllers/WeatherController.cs \
  --max-files 8
python scripts/biber_agent_client.py plan-edit \
  --edit-json '{"path":"generated/notes.md","new_text":"planned note\n","create_if_missing":true}' \
  --max-files 2
python scripts/biber_agent_client.py apply-edit \
  --edit-json '{"path":"generated/notes.md","new_text":"planned note\n","create_if_missing":true}' \
  --plan-hash <plan_hash-from-plan-edit> \
  --max-files 2
python scripts/biber_agent_client.py list-tests
python scripts/biber_agent_client.py run-test \
  --test-id python-compileall-api \
  --diagnose-on-failure
python scripts/biber_agent_client.py diagnose-test \
  --test-id dotnet-test \
  --command-json '["dotnet","test"]' \
  --exit-code 1 \
  --stdout "Example.cs(7,1): error CS1002: ; expected"
python scripts/biber_agent_client.py --json save-github \
  --dry-run \
  --path generated/notes.md \
  --content-file generated/notes.md \
  --branch biber/generated-notes \
  --base-branch main \
  --create-branch-if-missing \
  --commit-message "Save generated notes"
python scripts/biber_agent_client.py --json create-pr \
  --dry-run \
  --head biber/generated-notes \
  --base main \
  --title "Save generated notes" \
  --body "Generated by BIBER and ready for review."
python scripts/biber_agent_client.py save-github \
  --path generated/notes.md \
  --content-file generated/notes.md \
  --branch biber/generated-notes \
  --base-branch main \
  --create-branch-if-missing \
  --commit-message "Save generated notes"
python scripts/biber_agent_client.py create-pr \
  --head biber/generated-notes \
  --base main \
  --title "Save generated notes" \
  --body "Generated by BIBER and ready for review."
python scripts/biber_agent_client.py mvp-loop \
  --instruction "Fix the WeatherController forecast route." \
  --pinned-path README.md \
  --changed-path src/Example.Api/Controllers/WeatherController.cs \
  --max-context-files 8 \
  --runtime-profile-id rust-xriq-codegen \
  --edits-file /workspace/outputs/planned-edits.json \
  --apply-edits \
  --test-id dotnet-test \
  --save-github-path generated/notes.md \
  --save-content-file generated/notes.md \
  --github-branch biber/generated-notes \
  --github-base-branch main \
  --create-branch-if-missing \
  --commit-message "Save generated notes" \
  --create-pr \
  --pr-title "Save generated notes" \
  --pr-body "Generated by BIBER and ready for review." \
  --output /workspace/outputs/biber-mvp-loop.json
python scripts/biber_agent_client.py show-mvp-loop \
  /workspace/outputs/biber-mvp-loop.json
python scripts/biber_agent_client.py list-mvp-loops \
  /workspace/outputs \
  --limit 10
python scripts/biber_agent_client.py list-mvp-loops \
  /workspace/outputs \
  --failed-only \
  --limit 10
python scripts/biber_agent_client.py export-mvp-failures \
  /workspace/outputs \
  --output /workspace/outputs/biber-mvp-loop-failures.jsonl
python scripts/biber_agent_client.py prepare-repair \
  /workspace/outputs/biber-mvp-loop.json \
  --instruction "Repair the failed test with the smallest safe edit." \
  --output /workspace/outputs/biber-mvp-loop-repair.json
python scripts/biber_agent_client.py attempt-repair \
  /workspace/outputs/biber-mvp-loop-repair.json \
  --max-tokens 700 \
  --output /workspace/outputs/biber-mvp-loop-repair-attempt.json
python scripts/biber_agent_client.py show-repair-attempt \
  /workspace/outputs/biber-mvp-loop-repair-attempt.json
python scripts/biber_agent_client.py list-repair-attempts \
  /workspace/outputs \
  --ready-only \
  --limit 10
python scripts/biber_agent_client.py extract-repair-edits \
  /workspace/outputs/biber-mvp-loop-repair-attempt.json \
  --max-files 2 \
  --output /workspace/outputs/biber-mvp-loop-repair-edit-extraction.json \
  --edits-output /workspace/outputs/biber-mvp-loop-repair-edits.json
# Extraction accepts either "path" or the common model alias "file" for edit
# target paths; conflicting values are rejected before any plan/apply step.
python scripts/biber_agent_client.py show-repair-edit-extraction \
  /workspace/outputs/biber-mvp-loop-repair-edit-extraction.json
python scripts/biber_agent_client.py list-repair-edit-extractions \
  /workspace/outputs \
  --ready-only \
  --limit 10
python scripts/biber_agent_client.py plan-repair-edits \
  /workspace/outputs/biber-mvp-loop-repair-edit-extraction.json \
  --max-files 2 \
  --output /workspace/outputs/biber-mvp-loop-repair-edit-plan.json
python scripts/biber_agent_client.py show-repair-edit-plan \
  /workspace/outputs/biber-mvp-loop-repair-edit-plan.json
python scripts/biber_agent_client.py list-repair-edit-plans \
  /workspace/outputs \
  --planned-only \
  --limit 10
python scripts/biber_agent_client.py apply-repair-edits \
  /workspace/outputs/biber-mvp-loop-repair-edit-plan.json \
  --approve \
  --output /workspace/outputs/biber-mvp-loop-repair-edit-apply.json
python scripts/biber_agent_client.py show-repair-edit-apply \
  /workspace/outputs/biber-mvp-loop-repair-edit-apply.json
python scripts/biber_agent_client.py list-repair-edit-applies \
  /workspace/outputs \
  --applied-only \
  --limit 10
python scripts/biber_agent_client.py verify-repair-edits \
  /workspace/outputs/biber-mvp-loop-repair-edit-apply.json \
  --diagnose-on-failure \
  --output /workspace/outputs/biber-mvp-loop-repair-test-verification.json
python scripts/biber_agent_client.py show-repair-test-verification \
  /workspace/outputs/biber-mvp-loop-repair-test-verification.json
python scripts/biber_agent_client.py list-repair-test-verifications \
  /workspace/outputs \
  --passed-only \
  --limit 10
python scripts/biber_agent_client.py export-verified-repair \
  /workspace/outputs/biber-mvp-loop-repair-test-verification.json \
  --output /workspace/outputs/biber-mvp-loop-verified-repairs.jsonl
python scripts/biber_agent_client.py review-verified-repairs \
  /workspace/outputs/biber-mvp-loop-verified-repairs.jsonl \
  --output /workspace/outputs/biber-mvp-loop-verified-repair-review.json
python scripts/biber_agent_client.py show-verified-repair-review \
  /workspace/outputs/biber-mvp-loop-verified-repair-review.json
python scripts/biber_agent_client.py list-verified-repair-reviews \
  /workspace/outputs \
  --ready-only \
  --limit 10
python scripts/biber_agent_client.py show-repair-chain \
  --mvp-loop /workspace/outputs/biber-mvp-loop.json \
  --repair /workspace/outputs/biber-mvp-loop-repair.json \
  --attempt /workspace/outputs/biber-mvp-loop-repair-attempt.json \
  --extraction /workspace/outputs/biber-mvp-loop-repair-edit-extraction.json \
  --plan /workspace/outputs/biber-mvp-loop-repair-edit-plan.json \
  --apply /workspace/outputs/biber-mvp-loop-repair-edit-apply.json \
  --verification /workspace/outputs/biber-mvp-loop-repair-test-verification.json \
  --review-jsonl /workspace/outputs/biber-mvp-loop-verified-repairs.jsonl \
  --review-summary /workspace/outputs/biber-mvp-loop-verified-repair-review.json \
  --source-repo-root /workspace/biber-ai-platform \
  --output /workspace/outputs/biber-mvp-loop-repair-chain.json
# When --source-repo-root points at a Git checkout, show-repair-chain fills
# missing source repo URL, commit, and branch from git. Manual
# --source-repo-url/--source-repo-commit/--source-repo-branch values override
# derived values when supplied.
python scripts/biber_agent_client.py list-repair-chains \
  /workspace/outputs \
  --ready-only \
  --output /workspace/outputs/biber-mvp-loop-repair-chain-list.json
# The list output reports repo_provenance_ready/repo_provenance_missing, so
# reviewers can quickly tell whether ready chains have root-plus-commit evidence
# before attempting eval approval.
python scripts/biber_agent_client.py export-ready-repair-chains \
  /workspace/outputs \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chains.jsonl
python scripts/biber_agent_client.py review-ready-repair-chains \
  /workspace/outputs/biber-mvp-loop-ready-repair-chains.jsonl \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-review.json
# The review summary reports repo_provenance_ready/repo_provenance_missing.
# Only rows with source repo root plus commit should be considered for
# --decision approve_for_eval.
python scripts/biber_agent_client.py show-ready-repair-chain-review \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-review.json
python scripts/biber_agent_client.py list-ready-repair-chain-reviews \
  /workspace/outputs \
  --ready-only \
  --limit 10
python scripts/biber_agent_client.py record-ready-repair-chain-decision \
  /workspace/outputs/biber-mvp-loop-ready-repair-chains.jsonl \
  --decision defer \
  --reviewer human-reviewer \
  --notes "Needs one more review before eval curation." \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-decisions.jsonl
# To approve a real repo repair-chain for held-out eval curation, the reviewer
# must explicitly confirm provenance:
#   --decision approve_for_eval --evidence-source-type real_repo_candidate
# The decision export also reports repo_provenance_ready and
# rejected_repo_provenance_missing so missing root/commit evidence is visible
# immediately.
python scripts/biber_agent_client.py review-ready-repair-chain-decisions \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-decisions.jsonl \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-decision-review.json
python scripts/biber_agent_client.py show-ready-repair-chain-decision-review \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-decision-review.json
python scripts/biber_agent_client.py list-ready-repair-chain-decision-reviews \
  /workspace/outputs \
  --decision defer \
  --limit 10
# Only run the eval-candidate export for decision rows approved with
# --decision approve_for_eval. The export also blocks known fixture/smoke
# evidence, even if it was accidentally approved, so held-out evals come from
# real repo repair-chain evidence.
python scripts/biber_agent_client.py export-ready-repair-chain-eval-candidates \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-decisions.jsonl \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-candidates.jsonl
# Eval-candidate export/review also reports repo_provenance_ready and
# skipped_repo_provenance_missing so unconfirmed real-repo rows stay visible
# before dataset review.
python scripts/biber_agent_client.py review-ready-repair-chain-eval-candidates \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-candidates.jsonl \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-candidate-review.json
python scripts/biber_agent_client.py show-ready-repair-chain-eval-candidate-review \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-candidate-review.json
python scripts/biber_agent_client.py list-ready-repair-chain-eval-candidate-reviews \
  /workspace/outputs \
  --ready-only \
  --limit 10
# Only record eval-dataset readiness after manual dataset review.
python scripts/biber_agent_client.py record-ready-repair-chain-eval-candidate-decision \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-candidates.jsonl \
  --decision approve_for_eval_dataset \
  --reviewer human-dataset-reviewer \
  --notes "Approved for held-out eval dataset only; not training data." \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset-decisions.jsonl
python scripts/biber_agent_client.py review-ready-repair-chain-eval-dataset-decisions \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset-decisions.jsonl \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset-decision-review.json
python scripts/biber_agent_client.py show-ready-repair-chain-eval-dataset-decision-review \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset-decision-review.json
python scripts/biber_agent_client.py list-ready-repair-chain-eval-dataset-decision-reviews \
  /workspace/outputs \
  --decision approve_for_eval_dataset \
  --ready-only \
  --limit 10
python scripts/biber_agent_client.py export-ready-repair-chain-eval-dataset \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset-decisions.jsonl \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset.jsonl
python scripts/biber_agent_client.py validate-ready-repair-chain-eval-dataset \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset.jsonl \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset-validation.json
python scripts/biber_agent_client.py show-ready-repair-chain-eval-dataset-validation \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset-validation.json
python scripts/biber_agent_client.py list-ready-repair-chain-eval-dataset-validations \
  /workspace/outputs \
  --ok-only \
  --limit 10
python scripts/biber_agent_client.py export-ready-repair-chain-eval-prompts \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-dataset.jsonl \
  --output /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-prompts.jsonl
python scripts/biber_agent_client.py show-ready-repair-chain-eval-prompts \
  /workspace/outputs/biber-mvp-loop-ready-repair-chain-eval-prompts.jsonl
python scripts/biber_agent_client.py list-ready-repair-chain-eval-prompts \
  /workspace/outputs \
  --ready-only \
  --limit 10
python scripts/biber_agent_client.py review-repair-chain-heldout-eval-results \
  /workspace/outputs/evals/biber-repair-chain-heldout.jsonl \
  --summary /workspace/outputs/evals/biber-repair-chain-heldout.summary.json \
  --output /workspace/outputs/evals/biber-repair-chain-heldout-review.json
python scripts/biber_agent_client.py show-repair-chain-heldout-eval-review \
  /workspace/outputs/evals/biber-repair-chain-heldout-review.json
python scripts/biber_agent_client.py list-repair-chain-heldout-eval-reviews \
  /workspace/outputs/evals \
  --ok-only \
  --limit 10
# Only record held-out eval decisions after manual review.
python scripts/biber_agent_client.py record-repair-chain-heldout-eval-decision \
  /workspace/outputs/evals/biber-repair-chain-heldout-review.json \
  --decision defer \
  --reviewer human-heldout-reviewer \
  --notes "Deferred; not accepted as a training baseline." \
  --output /workspace/outputs/evals/biber-repair-chain-heldout-decisions.jsonl
python scripts/biber_agent_client.py review-repair-chain-heldout-eval-decisions \
  /workspace/outputs/evals/biber-repair-chain-heldout-decisions.jsonl \
  --output /workspace/outputs/evals/biber-repair-chain-heldout-decision-review.json
python scripts/biber_agent_client.py show-repair-chain-heldout-eval-decision-review \
  /workspace/outputs/evals/biber-repair-chain-heldout-decision-review.json
python scripts/biber_agent_client.py list-repair-chain-heldout-eval-decision-reviews \
  /workspace/outputs/evals \
  --decision defer \
  --limit 10
python scripts/biber_agent_client.py export-repair-chain-heldout-baseline-candidates \
  /workspace/outputs/evals/biber-repair-chain-heldout-decisions.jsonl \
  --output /workspace/outputs/evals/biber-repair-chain-heldout-baseline-candidates.jsonl
python scripts/biber_agent_client.py review-repair-chain-heldout-baseline-candidates \
  /workspace/outputs/evals/biber-repair-chain-heldout-baseline-candidates.jsonl \
  --output /workspace/outputs/evals/biber-repair-chain-heldout-baseline-candidate-review.json
python scripts/biber_agent_client.py show-repair-chain-heldout-baseline-candidate-review \
  /workspace/outputs/evals/biber-repair-chain-heldout-baseline-candidate-review.json
python scripts/biber_agent_client.py list-repair-chain-heldout-baseline-candidate-reviews \
  /workspace/outputs/evals \
  --limit 10
# Only record baseline decisions after manual baseline review.
python scripts/biber_agent_client.py record-repair-chain-heldout-baseline-candidate-decision \
  /workspace/outputs/evals/biber-repair-chain-heldout-baseline-candidates.jsonl \
  --decision approve_as_baseline \
  --reviewer human-baseline-reviewer \
  --notes "Approved as baseline evidence only; still not training data." \
  --output /workspace/outputs/evals/biber-repair-chain-heldout-baseline-decisions.jsonl
python scripts/biber_agent_client.py review-repair-chain-heldout-baseline-decisions \
  /workspace/outputs/evals/biber-repair-chain-heldout-baseline-decisions.jsonl \
  --output /workspace/outputs/evals/biber-repair-chain-heldout-baseline-decision-review.json
python scripts/biber_agent_client.py show-repair-chain-heldout-baseline-decision-review \
  /workspace/outputs/evals/biber-repair-chain-heldout-baseline-decision-review.json
python scripts/biber_agent_client.py list-repair-chain-heldout-baseline-decision-reviews \
  /workspace/outputs/evals \
  --limit 10
python scripts/biber_agent_client.py review-repair-chain-training-readiness \
  /workspace/outputs/evals/biber-repair-chain-heldout-baseline-decision-review.json \
  --output /workspace/outputs/evals/biber-repair-chain-training-readiness.json
python scripts/biber_agent_client.py show-repair-chain-training-readiness \
  /workspace/outputs/evals/biber-repair-chain-training-readiness.json
python scripts/biber_agent_client.py list-repair-chain-training-readiness \
  /workspace/outputs/evals \
  --limit 10
python scripts/biber_agent_client.py export-repair-chain-training-candidates \
  /workspace/outputs/evals/biber-repair-chain-training-readiness.json \
  --output /workspace/outputs/evals/biber-repair-chain-training-candidates.jsonl
python scripts/biber_agent_client.py review-repair-chain-training-candidates \
  /workspace/outputs/evals/biber-repair-chain-training-candidates.jsonl \
  --output /workspace/outputs/evals/biber-repair-chain-training-candidate-review.json
python scripts/biber_agent_client.py show-repair-chain-training-candidate-review \
  /workspace/outputs/evals/biber-repair-chain-training-candidate-review.json
python scripts/biber_agent_client.py list-repair-chain-training-candidate-reviews \
  /workspace/outputs/evals \
  --limit 10
python scripts/biber_agent_client.py review-repair-chain-training-pipeline \
  --artifact-dir /workspace/outputs/evals \
  --output /workspace/outputs/evals/biber-repair-chain-training-pipeline.json
python scripts/biber_agent_client.py show-repair-chain-training-pipeline \
  /workspace/outputs/evals/biber-repair-chain-training-pipeline.json
python scripts/biber_agent_client.py list-repair-chain-training-pipelines \
  /workspace/outputs/evals \
  --limit 10
```

If `mvp-loop` is started with `--runtime-profile-id`, failed-loop repair
requests and `attempt-repair` inherit those profile IDs unless you pass a
different `--runtime-profile-id` to `attempt-repair`. `attempt-repair` accepts
either the original failed `mvp-loop` artifact or the prepared
`prepare-repair` artifact.

## Prepare Repo-Specific BIBER Adaptation

Before fine-tuning BIBER for a GitHub repo, generate a safe adaptation plan and
starter eval prompts. Use repo context and evals first; fine-tune only after
repeatable failures are collected and reviewed.

```bash
python training/repo_adaptation_plan.py \
  --repo-root /path/to/github/repo \
  --output /workspace/outputs/repo-adaptation-plan.json \
  --eval-prompts-output /workspace/outputs/repo-adaptation-eval-prompts.jsonl
```

Run those eval prompts against the currently served BIBER model before deciding
whether fine-tuning is justified:

```bash
python training/repo_adaptation_eval.py \
  --prompts /workspace/outputs/repo-adaptation-eval-prompts.jsonl \
  --base-url http://127.0.0.1:8000 \
  --env-file /workspace/biber-ai-platform/.env \
  --output /workspace/outputs/evals/repo-adaptation-results.jsonl \
  --summary /workspace/outputs/evals/repo-adaptation-summary.json \
  --failures-output /workspace/outputs/evals/repo-adaptation-failures.jsonl
```

On the direct Vast deployment, the convenience wrapper is:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_eval_repo_adaptation_direct.sh
```

Group repeated failures into a human review queue before turning any of them
into training records:

```bash
python training/repo_adaptation_failure_review.py \
  --failures /workspace/outputs/evals/repo-adaptation-failures.jsonl \
  --review-output /workspace/outputs/evals/repo-adaptation-failure-review.json \
  --training-candidates-output /workspace/outputs/evals/repo-adaptation-training-candidates.jsonl \
  --min-repeats 2
```

The helper writes candidate rows with `quality: needs_review` and an empty
`output`; fill in a verified answer or patch before adding any row to the real
training dataset.

See `docs/BIBER_REPO_ADAPTATION.md` for the promotion rules.

## Run A Tracked Agent Session

This endpoint wraps the existing MVP primitives into one tracked workflow:
repo-context chat, optional bounded workspace edit, optional allowlisted test,
optional XRIQ private-devnet context, and optional GitHub save/PR only when
explicitly supplied. Each completed session is persisted as a local JSON
artifact under `BIBER_AGENT_SESSION_DIR`, or `/workspace/outputs/agent-sessions`
on Vast.ai when the setting is omitted.

When the allowlisted test step fails or times out, the persisted `test_run`
step now includes a deterministic `diagnosis` object with the detected stack,
failure category, concise relevant output, and suggested next actions.

```bash
curl -X POST http://localhost:8000/v1/agent/sessions \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "instruction": "Use README.md context and draft a concise implementation note.",
    "repo_context_paths": ["README.md"],
    "include_xriq_context": true,
    "xriq_explorer_limit": 3,
    "xriq_snapshot_limit": 3,
    "workspace_edit": {
      "path": "generated/agent-session-note.txt",
      "new_text": "BIBER agent session note\n",
      "create_if_missing": true,
      "dry_run": true
    },
    "test_id": "python-compileall-api"
  }'
```

When `include_xriq_context` is `true`, the session first reads the configured
XRIQ private-devnet overview, adds a concise chain summary to the model context,
and persists the raw overview under an `xriq_context` session step.

List recent persisted sessions:

```bash
curl 'http://localhost:8000/v1/agent/sessions?limit=10' \
  -H "Authorization: Bearer dev-api-key-change-me"
```

Load one persisted session by the `id` returned from the create call:

```bash
curl http://localhost:8000/v1/agent/sessions/<session-id> \
  -H "Authorization: Bearer dev-api-key-change-me"
```

## XRIQ Private-Devnet Preflight Transfer

This endpoint is a thin wrapper around the local Rust
`xriq-node preflight-transfer --format json` command. The chain file, pending
file, Rust workspace, and runner command are configured on the server with
`BIBER_XRIQ_*` settings. The request does not accept arbitrary file paths.

```bash
curl -X POST http://localhost:8000/v1/xriq/private-devnet/preflight-transfer \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "xriqdev1alice00000000000",
    "to": "xriqdev1bobbb00000000000",
    "amount_base_units": "25",
    "fee_base_units": "2",
    "expires_at_height": 100,
    "timestamp_ms": 1000
  }'
```

## XRIQ Private-Devnet Read Helpers

These endpoints are thin wrappers around the existing `xriq-node --format json`
read commands. Mempool detail reads the server-configured durable pending file.

Use the overview endpoint when a client needs one compact private-devnet status
payload for a wallet/explorer dashboard:

```bash
curl 'http://localhost:8000/v1/xriq/private-devnet/overview?explorer_limit=5&snapshot_limit=5' \
  -H "Authorization: Bearer dev-api-key-change-me"
```

For a dependency-free Python client that future wallet/explorer work can reuse:

```bash
BIBER_API_BASE_URL=http://127.0.0.1:8000 \
BIBER_API_KEY=dev-api-key-change-me \
python scripts/biber_xriq_private_devnet_client.py overview
```

```bash
BIBER_API_BASE_URL=http://127.0.0.1:8000 \
BIBER_API_KEY=dev-api-key-change-me \
python scripts/biber_xriq_private_devnet_client.py snapshots --limit 10
```

```bash
BIBER_API_BASE_URL=http://127.0.0.1:8000 \
BIBER_API_KEY=dev-api-key-change-me \
python scripts/biber_xriq_private_devnet_client.py snapshot manual-smoke
```

For a same-origin browser dashboard over an SSH tunnel:

```text
http://127.0.0.1:8000/xriq/private-devnet/dashboard
```

The dashboard reads the overview/snapshot endpoints, can submit a
private-devnet preflight transfer through the existing safe wrapper, and can
look up transaction hashes and accounts through the read-only wrappers. It does
not embed an API key; enter the key in the browser session after opening it.

```bash
curl http://localhost:8000/v1/xriq/private-devnet/status \
  -H "Authorization: Bearer dev-api-key-change-me"

curl 'http://localhost:8000/v1/xriq/private-devnet/explorer?limit=5' \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/blocks/1 \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/accounts/xriqdev1alice00000000000 \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/transactions/<transaction-hash> \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/mempool \
  -H "Authorization: Bearer dev-api-key-change-me"
```

## XRIQ Private-Devnet Snapshots

These endpoints wrap `xriq-node snapshot-export` and `xriq-node
snapshot-import`. Clients provide only a safe snapshot name and options; the
server controls the snapshot, chain, and pending-file roots through
`BIBER_XRIQ_*` settings.

```bash
curl -X POST http://localhost:8000/v1/xriq/private-devnet/snapshots/export \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_name": "manual-smoke",
    "include_pending_file": true
  }'
```

Import defaults to a staging target so the restored chain can be checked
without overwriting the live configured private-devnet files:

```bash
curl -X POST http://localhost:8000/v1/xriq/private-devnet/snapshots/import \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_name": "manual-smoke",
    "target": "staging",
    "include_pending_file": true
  }'
```

Use `"target": "configured"` only for an intentional restore onto a clean or
operator-prepared private-devnet file path. The Rust command refuses to
overwrite existing target files.

List snapshots and inspect one snapshot manifest:

```bash
curl 'http://localhost:8000/v1/xriq/private-devnet/snapshots?limit=10' \
  -H "Authorization: Bearer dev-api-key-change-me"

curl http://localhost:8000/v1/xriq/private-devnet/snapshots/manual-smoke \
  -H "Authorization: Bearer dev-api-key-change-me"
```

## Submit Proctoring Analysis

```bash
curl http://localhost:8000/v1/proctor/session/analyze \
  -H "Authorization: Bearer dev-api-key-change-me" \
  -H "X-Biber-Passcode: BIBER_20_GPU_DEMO" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session_001",
    "prompt": "Analyze for face missing, multiple faces, and speech events",
    "model": "biber-proctor-core"
  }'
```
