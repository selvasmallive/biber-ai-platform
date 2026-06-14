# Gemini Code Assist Prompt: BIBER MVP

Use this prompt in Gemini Code Assist Enterprise for BIBER MVP work.

```text
GitHub repo:
https://github.com/selvasmallive/biber-ai-platform

Project:
BIBER MVP as a cost-saving local coding assistant platform.

Base branch:
main

Backup branch that preserves the pre-Gemini handoff state:
backup/biber-pre-gemini-20260614

First, read these files before proposing or changing code:
- docs/CODEX_HANDOFF.md
- readme-resume-biber.md
- docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md
- docs/BIBER_REPO_ADAPTATION.md
- docs/BIBER_CAPABILITY_ROADMAP.md
- docs/API_EXAMPLES.md
- README.md
- src/biber_api/model_registry.py
- src/biber_api/repo_context.py
- src/biber_api/workspace_edit.py
- src/biber_api/test_runner.py
- src/biber_api/test_diagnosis.py
- scripts/biber_agent_client.py

Current state:
BIBER MVP has partial provider/model registry, agent session, repo context,
workspace edit, test runner, diagnosis, GitHub, runtime profile, and optional
OpenAI mentor plumbing. The old Vast GPU was terminated, so do not assume
/workspace, vLLM, FastAPI on Vast, or live GPU access exists until a new GPU is
provisioned and the user provides connection details.

Goal:
Resume BIBER MVP toward a usable Copilot/Codex-like local coding assistant
while keeping development cost low.

Cost-saving strategy:
- Start CPU/local-first with mocks, unit tests, and deterministic scripts.
- Keep local/open-source model providers swappable.
- Do not require a Vast GPU for orchestration-layer work.
- Do not start QLoRA, long evals, or training without explicit user approval.
- Keep OpenAI mentor optional, disabled by default, and only triggered by an
  explicit request such as "Review with OpenAI mentor".
- Codex should be used only as an occasional monitor/reviewer between
  milestones, not as the bulk implementation engine.

Target BIBER phases:
1. Resume audit and local test baseline.
2. Provider abstraction and model registry hardening.
3. Repo context selection and task planning.
4. Safe patch generation/application and test loop.
5. GitHub branch/commit/PR workflow.
6. Reliability hardening for multi-file edits and test-failure diagnosis.
7. Optional local model eval/training loop after GPU is available.

When BIBER becomes usable:
- After Phase 3: limited read-only/repo-planning assistant.
- After Phase 4: basic local coding-agent MVP.
- After Phase 5: usable practical alternative for selected Copilot/Codex-style
  repo tasks.
- After Phase 6: more reliable daily-development helper.

Recommended first PR:
Create a narrow BIBER MVP resume/checkpoint PR that:
1. Adds or updates a BIBER MVP phase plan and status matrix.
2. Verifies current local tests for model registry, runtime profiles, repo
   context, workspace edits, test runner, diagnosis, and agent client.
3. Adds a cheap validation guard script for the BIBER MVP resume plan.
4. Keeps all providers swappable and does not hard-code Gemini, OpenAI, Qwen, or
   Vertex AI as the only provider.
5. Does not provision cloud resources, change secrets, rotate credentials, or
   start training.
6. Updates docs/CODEX_HANDOFF.md with the new BIBER resume checkpoint.

Verification for the first PR:
Run the narrowest local tests relevant to any changed files. Prefer tests like:
- pytest tests/test_model_registry.py
- pytest tests/test_runtime_profiles.py
- pytest tests/test_agent_session.py
- pytest tests/test_agent_capabilities.py
- pytest tests/test_biber_agent_client.py
- pytest tests/test_workspace_edit.py tests/test_test_runner.py tests/test_test_diagnosis.py
- the new BIBER MVP resume guard script

If Python dependencies are missing, document the exact blocker and do not hide
the failure.

PR summary must include:
- what changed
- whether GPU/Vast was required: no, unless explicitly approved
- cloud resources touched: none
- secrets/credentials touched: none
- training/eval jobs started: none
- tests/checks run
- current BIBER MVP phase completion estimate
- recommended next PR

Codex monitor checkpoint:
After each meaningful Gemini PR, ask Codex to review the PR for architecture
drift, provider lock-in, cost drift, unsafe edits, missing tests, credential
risk, and whether Gemini is moving BIBER toward a usable local coding assistant
instead of overbuilding.
```
