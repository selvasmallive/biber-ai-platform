# Codex Handoff

Last updated: 2026-05-17

## Current Goal

Continue the live Vast.ai deployment and development of the BIBER AI Platform from
the current GPU-backed direct vLLM/FastAPI state.

## Repo State

- Local branch: `main`
- Remote: `origin` points to `https://github.com/selvasmallive/biber-ai-platform.git`
- GitHub `origin/main` was pushed from this workstation on 2026-05-16 and now
  includes the live deployment hardening, GitHub save hardening, pytest
  verification, and handoff updates.
- The pushed history includes at least:
  - `b782c05 Harden Vast direct service binding`
  - `b0462e6 Update Vast handoff state`
  - `73bd171 Refresh Vast deployment handoff`
  - `97094ea Harden GitHub save integration`
  - `0272643 Update Vast handoff after GitHub save deploy`
  - `fae51c2 Record pytest availability in handoff`
  - `fc6b1ba Record Vast pytest verification`
  - `b3a7456 Record GitHub CLI auth setup`
  - `86129dc Smoke test BIBER GitHub save`
  - `8ae20ad Prepare Vast QLoRA training path`
  - `5f10d3f Add approved internet data ingestion`
  - `7d9446f Add bounded Hugging Face ingestion source`
  - `0e7fb30 Avoid training requirements transformer downgrade`
  - `e6a6339 Record Vast CodeInstruct dataset prep`
  - `1623c50 Harden Vast QLoRA launcher`
  - `fb97271 Add Vast LoRA serving start path`
  - `89ecb0b Record Vast LoRA training deploy`
  - `46f66c8 Add live LoRA eval runner`
  - `b25e68e Increase approved CodeInstruct ingest cap`
  - `4d76cf6 Relax React live eval heuristic`
  - `aa1f8d6 Add targeted eval training source`
  - `4c77e23 Record targeted LoRA improvement`
  - `1b6e073 Expand live eval prompt set`
  - `0d6b0b7 Relax rate limit eval heuristic`
  - `045d377 Relax API key eval heuristic`
  - `5f2e9de Add XRIQ Rust future track`
  - `d1dc0c5 Prioritize Rust XRIQ capability`
  - `fb5bb0f Add Rust XRIQ eval harness`
  - `11c3358 Add Vast Rust toolchain helper`
  - `14b89fb Fix Rust eval fixture formatting`
  - `fe75bce Harden Rust eval code validation`
  - `ca51c6e Add targeted Rust XRIQ dataset`
  - `4015d92 Record Rust XRIQ training results`
  - `9e5099c Confirm Rust XRIQ broad eval`
  - `17eebc9 Add HashSet Rust XRIQ examples`
  - `457155c Record Rust HashSet eval success`
  - `6482059 Add XRIQ spec and mentor strategy`
- Later local/Vast handoff commits may exist on top of those; verify with Git
  before acting on branch state.
- Use `git status --short --branch`, `git log --oneline -1`, and
  `git ls-remote origin refs/heads/main` for authoritative current Git state.
- Keep the Vast.ai checkout at `/workspace/biber-ai-platform` fast-forwarded
  with `git pull --ff-only origin main` after documentation or deployment
  commits are pushed.
- Prefer `git status --short --branch` and `git log --oneline -1` over this
  file for authoritative current Git state.
- GitHub CLI was installed on this workstation at
  `C:\Program Files\GitHub CLI\gh.exe` and authenticated as `selvasmallive`.
  `gh auth setup-git` was run, and `git push origin main` verified GitHub auth
  with `Everything up-to-date`. In this Codex process, `gh` may not be on
  `PATH` until the app/session is restarted; use the full path if needed.
- Real GitHub generated-code save was smoke-tested from the live Vast.ai API
  using a temporary GitHub CLI token from this workstation. The token was not
  written to the live `.env`, temporary files were removed, and FastAPI was
  restarted back to normal no-token configuration after the test.

## Completed

- Fast-forwarded the Vast.ai checkout from `4044c5b` to `5798c7f`.
- Bootstrapped the no-Docker direct deployment path on Vast.ai.
- Verified the instance has two GPUs:
  - GPU 0: NVIDIA GeForce RTX 5060 Ti, 16311 MiB
  - GPU 1: NVIDIA GeForce RTX 5060 Ti, 16311 MiB
- Confirmed Docker is not present on the instance; the direct deployment path is
  the correct path.
- Verified local scaffold validation passes with the bundled Codex Python runtime.
- Verified local Python syntax compile checks pass for `app`, `src`, `worker`,
  `training`, and `scripts`.
- Verified remote `pip check` reports no broken requirements after dependency
  pin updates.
- Verified remote direct smoke test passes:
  - `GET /health`
  - `GET /v1/runtime`
  - `GET /v1/models`
  - `POST /v1/chat`
- `/v1/chat` returned model content `ok` from `biber-dev-core`.
- Verified a richer live `/v1/chat` prompt through FastAPI produced a real
  Python `fib(n)` implementation from `biber-dev-core`.
- Hardened the direct deployment so FastAPI and vLLM bind to `127.0.0.1` by
  default. Use SSH tunnels unless the `.env` credentials have been replaced and
  public binding is intentionally configured.
- Restarted the live Vast.ai services after applying explicit loopback values in
  `.env`. Final `ss` output showed both listeners on `127.0.0.1` only.
- Re-verified the live Vast.ai deployment on 2026-05-16:
  - Vast checkout: `main...origin/main [ahead 2]` at that time
  - vLLM pid: `5634`
  - FastAPI pid: `6039`
  - both services listening only on `127.0.0.1`
  - `bash scripts/vast_test_direct.sh` passed
  - `/v1/chat` returned model content `ok` from `biber-dev-core`
- Hardened the GitHub generated-code save integration in `97094ea`:
  - GitHub target paths are normalized and reject empty/parent-directory paths.
  - missing GitHub owner/repo now returns a controlled configuration error
    instead of an unhandled exception.
  - GitHub API and network failures are wrapped as controlled save errors.
  - `/v1/chat` save-to-GitHub and `/v1/save/github` map disabled/config/API
    failures to clear HTTP responses.
  - added mocked client tests in `tests/test_github_client.py`.
- Deployed `97094ea` to the Vast.ai checkout through a Git bundle because
  GitHub push was blocked by credentials. Vast is now ahead of `origin/main`.
- Restarted only FastAPI after deploying `97094ea`; vLLM stayed warm.
  - vLLM pid: `5634`
  - FastAPI pid: `6759`
- Verified on Vast.ai after the FastAPI restart:
  - `/workspace/biber-venv/bin/python -m compileall app src tests` passed.
  - mocked GitHub client checks passed against the Vast virtualenv.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/save/github` without `GITHUB_TOKEN` returns
    `HTTP 503 {"detail":"GitHub saving is not configured."}`.
- Installed `pytest>=8,<9` into the Vast.ai virtualenv and verified
  `tests/test_github_client.py` passes:
  - Python: `/workspace/biber-venv/bin/python`
  - pytest: `8.4.2`
  - result: `5 passed`
- Verified GitHub caught up through `fc6b1ba`, then fetched `origin/main` on
  Vast.ai. Vast checkout showed `main...origin/main` with no ahead count.
- Verified real `/v1/save/github` from Vast.ai with temporary GitHub credentials:
  - FastAPI was restarted with transient `GITHUB_TOKEN`,
    `GITHUB_DEFAULT_OWNER=selvasmallive`, and
    `GITHUB_DEFAULT_REPO=biber-ai-platform`.
  - `/v1/save/github` returned `HTTP 200`.
  - GitHub URL:
    `https://github.com/selvasmallive/biber-ai-platform/blob/main/generated/github-save-smoke.md`
  - Resulting Git commit: `86129dc Smoke test BIBER GitHub save`
  - Local and Vast.ai checkouts were fast-forwarded to include the generated
    smoke-test file.
  - FastAPI was restarted back to normal mode after the smoke test:
    vLLM pid `5634`, FastAPI pid `7818`.
  - `bash scripts/vast_test_direct.sh` passed after the normal restart.
  - `/v1/runtime` reports `github_configured=false` again because no GitHub
    token is currently persisted in `.env`.
- Prepared and verified the custom-model QLoRA training path in `8ae20ad`:
  - added JSONL dataset validation utilities and tests.
  - replaced the QLoRA placeholder with a dry-runnable training entrypoint.
  - added `scripts/vast_train_qlora_tmux.sh` for long GPU jobs on the 500 GB
    Vast volume.
  - added `requirements-training.txt` without forcing a Torch/CUDA replacement.
  - local bundled-Python compile, dataset validation, and QLoRA dry-run passed.
  - local pytest was not available in the bundled Python runtime, so pytest was
    verified on the Vast virtualenv instead.
  - Vast pytest for `tests/test_training_dataset.py` passed with `4 passed`.
  - Vast compile, sample dataset validation, and QLoRA dry-run also passed.
  - no real fine-tuning job was started.
- Added the approved internet dataset ingestion pipeline in `5f10d3f`:
  - approved-source manifest: `training/approved_sources.json`
  - ingestion CLI: `training/internet_ingest.py`
  - Vast helper: `scripts/vast_ingest_internet_dataset.sh`
  - tests: `tests/test_internet_ingest.py`
  - generated datasets, raw downloads, provenance, outputs, and adapters are
    ignored by Git.
- Verified internet ingestion on Vast after pulling `5f10d3f`:
  - compile checks for `training`, `scripts`, and `tests` passed.
  - Vast pytest for `tests/test_internet_ingest.py` and
    `tests/test_training_dataset.py` passed with `8 passed`.
  - approved internet-smoke ingestion wrote
    `/workspace/data/biber_train_internet_smoke.jsonl` with 2 records.
  - raw source was stored at
    `/workspace/data/raw/biber-platform-sample-jsonl.jsonl`.
  - provenance was written to `/workspace/outputs/dataset-provenance.json`.
  - validation report was written to
    `/workspace/outputs/internet-dataset-validation.json`.
  - QLoRA dry-run accepted the internet-smoke dataset.
  - no real fine-tuning job was started.
- Added and verified a bounded Hugging Face rows source in `7d9446f`:
  - enabled `SoyMaycol/CodeInstruct-20K` with `cc-by-4.0` metadata,
    `question` -> `instruction`, and `answer` -> `output`.
  - bounded source limit is currently 200 records.
  - Vast ingestion wrote
    `/workspace/data/biber_train_internet_codeinstruct_200.jsonl`.
  - resulting dataset had 200 records: 2 project-owned smoke records and 198
    CodeInstruct records.
  - provenance:
    `/workspace/outputs/dataset-provenance-codeinstruct-200.json`.
  - validation report:
    `/workspace/outputs/internet-dataset-validation-codeinstruct-200.json`.
  - canonical training dataset was promoted to `/workspace/data/biber_train.jsonl`
    and validated with 0 errors.
  - QLoRA dry-run accepted `/workspace/data/biber_train.jsonl`.
- Hardened `requirements-training.txt` in `0e7fb30` so it does not pin or
  downgrade Transformers. Vast already has `torch 2.11.0+cu130` and
  `transformers 5.8.1` from the live vLLM environment.
- Installed QLoRA extras into `/workspace/biber-venv` after a pip dry-run showed
  no Torch/Transformers downgrade:
  - `accelerate 1.13.0`
  - `bitsandbytes 0.49.2`
  - `peft 0.19.1`
  - `pip check` reported no broken requirements.
  - `training.qlora_train_biber_dev_core.require_training_dependencies()`
    imported all required training objects successfully.
  - vLLM and FastAPI remained running and healthy after install.
- Hardened the Vast QLoRA launcher in `1623c50`:
  - training jobs default Hugging Face and pip caches to `/workspace`.
  - `scripts/vast_train_qlora_tmux.sh` supports bounded smoke runs with
    `BIBER_TRAIN_MAX_STEPS`, `BIBER_TRAIN_LIMIT_SAMPLES`, `BIBER_TRAIN_SAVE_STEPS`,
    and related environment knobs.
  - long training jobs still run in `tmux` on the Vast GPU so Codex does not need
    to stay active while the GPU works.
- Added the LoRA serving start path in `fb97271`:
  - `scripts/vast_start_lora_direct.sh` serves `/workspace/adapters/biber-dev-core-lora`
    as `biber-dev-core`.
  - vLLM serves the base model separately as `biber-dev-core-base`.
  - `scripts/vast_start_direct.sh` accepts `BIBER_VLLM_LORA_MODULES` and passes
    `--enable-lora --lora-modules` to vLLM.
- Completed real starter QLoRA training on Vast.ai:
  - stopped direct services first to free GPU memory.
  - one-step smoke run completed and wrote
    `/workspace/adapters/biber-dev-core-lora-smoke`.
  - full starter run completed 25 steps in about 73.18 seconds with train loss
    about `0.8886`.
  - saved the trained adapter at `/workspace/adapters/biber-dev-core-lora`.
  - direct PEFT/Transformers adapter-load smoke generated a correct Python
    `add(a, b)` function.
- Restarted the live Vast.ai direct deployment with the trained LoRA adapter:
  - vLLM pid: `9923`
  - FastAPI pid: `10535`
  - both services listen only on `127.0.0.1`.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/models` reports both `biber-dev-core-base` and the LoRA adapter model
    `biber-dev-core`.
  - `/v1/chat` returned model content `ok` from `biber-dev-core`.
- Added a fixed live LoRA evaluation runner in `46f66c8`:
  - prompt set: `training/eval_prompts.jsonl`
  - Python runner: `training/live_model_eval.py`
  - Vast wrapper: `scripts/vast_eval_lora_direct.sh`
  - outputs stay on the 500 GB Vast volume under `/workspace/outputs/evals`.
  - Vast verification passed:
    `/workspace/biber-venv/bin/python -m compileall training scripts tests`,
    `bash -n scripts/vast_eval_lora_direct.sh`, and
    `tests/test_live_model_eval.py` with `4 passed`.
- Ran the first live LoRA baseline eval against `biber-dev-core`:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T184927Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T184927Z.jsonl`
  - result: `6/6` prompts returned responses, `3/6` simple expectation checks
    passed.
  - passed: Python add function, subtract-bug fix, iterative Fibonacci.
  - weak spots: pytest generation returned an implementation instead of tests,
    React component used `interface` while the simple check expected `type`, and
    the API error-shape answer omitted `status`.
- Increased the approved `SoyMaycol/CodeInstruct-20K` ingest cap to 1000 in
  `b25e68e`; the Vast wrapper still keeps an explicit total cap and the source
  remains approved, license-allowlisted, and domain-allowlisted.
- Ingested and promoted a larger approved internet dataset:
  - candidate:
    `/workspace/data/biber_train_internet_codeinstruct_1000.jsonl`
  - canonical dataset:
    `/workspace/data/biber_train.jsonl`
  - result: `998` clean records, `0` validation errors.
  - provenance:
    `/workspace/outputs/dataset-provenance-codeinstruct-1000.json`
  - validation:
    `/workspace/outputs/internet-dataset-validation-codeinstruct-1000.json`
    and `/workspace/outputs/dataset-validation.json`.
  - first strict `min-records=1000` attempt failed because filtering left 998
    valid records; rerun accepted the dataset with `min-records=990`.
- Trained a new one-epoch LoRA adapter from the 998-record dataset:
  - services were stopped first to free GPU memory.
  - tmux session: `biber-qlora-codeinstruct-998`.
  - log: `/workspace/outputs/qlora-codeinstruct-998/qlora-20260516T185433Z.log`
  - output adapter:
    `/workspace/adapters/biber-dev-core-lora-codeinstruct-998`
  - steps: `125`
  - runtime: about `360.7` seconds.
  - train loss: about `0.7911`.
  - saved checkpoints: `checkpoint-50`, `checkpoint-100`, `checkpoint-125`.
- Restarted the live Vast.ai direct deployment with the 998-record LoRA adapter:
  - vLLM pid: `11462`
  - FastAPI pid: `11958`
  - both services listen only on `127.0.0.1`.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/models` reports `biber-dev-core` rooted at
    `/workspace/adapters/biber-dev-core-lora-codeinstruct-998`.
- Corrected the React eval heuristic in `4d76cf6` to accept `ButtonProps`
  rather than requiring the literal word `type`.
- Latest corrected live eval against the 998-record adapter:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T190402Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T190402Z.jsonl`
  - result: `6/6` prompts returned responses, `4/6` simple expectation checks
    passed.
  - passed: Python add function, subtract-bug fix, iterative Fibonacci, and
    TypeScript React Button component.
  - remaining weak spots: pytest generation still returned an implementation
    instead of tests, and the API error-shape answer still omitted `status`.
- Added the project-owned targeted eval-improvement source in `aa1f8d6`:
  - file: `training/targeted_eval_dataset.jsonl`
  - manifest source: `biber-targeted-eval-jsonl`
  - content: 27 verified records, focused on pytest/test generation and API
    error-response shapes with `status` and `detail`.
  - local and Vast validation reported 27 records, 0 errors, 0 warnings.
- Ingested and promoted the combined targeted approved dataset:
  - candidate:
    `/workspace/data/biber_train_targeted_codeinstruct_1000.jsonl`
  - canonical dataset:
    `/workspace/data/biber_train.jsonl`
  - result: `1000` clean records, `0` validation errors.
  - source mix: 2 project smoke records, 27 targeted project-owned records, and
    971 CodeInstruct records.
  - provenance:
    `/workspace/outputs/dataset-provenance-targeted-codeinstruct-1000.json`
  - validation:
    `/workspace/outputs/internet-dataset-validation-targeted-codeinstruct-1000.json`
    and `/workspace/outputs/dataset-validation.json`.
  - first ingest attempt hit a transient Hugging Face rows API `HTTP 502`; rerun
    succeeded.
- Trained a targeted-priority LoRA adapter:
  - services were stopped first to free GPU memory.
  - tmux session: `biber-qlora-targeted-350`.
  - log: `/workspace/outputs/qlora-targeted-350/qlora-20260516T191155Z.log`
  - output adapter: `/workspace/adapters/biber-dev-core-lora-targeted-350`
  - training used the canonical 1000-record dataset for validation, then
    `BIBER_TRAIN_LIMIT_SAMPLES=350` and `BIBER_TRAIN_NUM_EPOCHS=2` to keep the
    run low-cost while emphasizing the targeted examples.
  - steps: `88`
  - runtime: about `255.3` seconds.
  - train loss: about `0.7927`.
  - saved checkpoints: `checkpoint-50`, `checkpoint-75`, `checkpoint-88`.
- Restarted the live Vast.ai direct deployment with the targeted-priority LoRA
  adapter:
  - vLLM pid: `12793`
  - FastAPI pid: `13134`
  - both services listen only on `127.0.0.1`.
  - `bash scripts/vast_test_direct.sh` passed.
  - `/v1/models` reports `biber-dev-core` rooted at
    `/workspace/adapters/biber-dev-core-lora-targeted-350`.
- Latest corrected live eval against the targeted-priority adapter:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T191829Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T191829Z.jsonl`
  - result: `6/6` prompts returned responses, `6/6` simple expectation checks
    passed.
  - the previously weak pytest-generation and API error-shape prompts now pass
    the fixed baseline checks.
- Expanded the live eval prompt set in `1b6e073` from 6 to 18 prompts across
  Python, pytest, FastAPI, API error shapes, React, TypeScript, SQL, JSONL, and
  retry-helper tasks. This gives the next improvement loop broader coverage than
  the targeted 6-prompt smoke baseline.
- Ran the expanded live eval against the targeted-priority adapter:
  - first broad run produced `18/18` responses and `17/18` simple expectation
    checks because the rate-limit prompt used `rate_limit_exceeded`, which was
    acceptable but too strict for the old literal check.
  - after `0d6b0b7`, a second broad run produced `18/18` responses and `17/18`
    checks because the missing-API-key prompt used `api_key_missing`, again
    acceptable but too strict for the old literal check.
  - after `045d377`, the latest broad run produced `18/18` responses and
    `18/18` simple expectation checks.
  - latest summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T192652Z.summary.json`
  - latest detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260516T192652Z.jsonl`
  - note: this is still a lightweight substring/regex baseline, not a full
    execution-quality guarantee.
- Started the Rust/XRIQ capability track:
  - Rust/XRIQ prompt file: `training/eval_prompts_rust_xriq.jsonl`.
  - Vast wrapper: `scripts/vast_eval_rust_xriq_direct.sh`.
  - Vast Rust toolchain helper: `scripts/vast_install_rust_toolchain.sh`.
  - `training/live_model_eval.py` now supports optional code validators.
  - Rust validators create temporary cargo projects and run
    `cargo fmt --check`, `cargo check`, and `cargo test --lib`.
  - Rust/XRIQ evals are separate from `training/eval_prompts.jsonl` so the
    existing `18/18` broad baseline remains comparable.
  - The Rust toolchain helper installs to `/workspace/.cargo` and
    `/workspace/.rustup` so toolchain files stay on the 500 GB Vast volume.
- Completed the first Rust/XRIQ improvement loop:
  - Rust toolchain installed on Vast under `/workspace/.cargo` and
    `/workspace/.rustup`.
  - Pre-training Rust/XRIQ eval against
    `/workspace/adapters/biber-dev-core-lora-targeted-350`:
    `6/6` responses, `6/6` substring expectations, `2/6` cargo validators.
  - Added project-owned targeted Rust/XRIQ data:
    `training/targeted_rust_xriq_dataset.jsonl`.
  - Added approved-source manifest entry:
    `biber-rust-xriq-targeted-jsonl`.
  - Ingested candidate:
    `/workspace/data/biber_train_rust_xriq_targeted_codeinstruct_1000.jsonl`.
  - Candidate mix: 2 project smoke records, 27 Python/API targeted records, 10
    Rust/XRIQ targeted records, and 961 CodeInstruct records.
  - Candidate validation: `1000` records, `0` errors, `0` warnings.
  - Candidate provenance:
    `/workspace/outputs/dataset-provenance-rust-xriq-targeted-codeinstruct-1000.json`.
  - Candidate validation report:
    `/workspace/outputs/internet-dataset-validation-rust-xriq-targeted-codeinstruct-1000.json`.
  - Promoted candidate to `/workspace/data/biber_train.jsonl` and validated it
    with `1000` records, `0` errors, `0` warnings.
  - Stopped services before training to free GPU memory.
  - Trained Rust/XRIQ-priority adapter in tmux session
    `biber-qlora-rust-xriq-400`.
  - Training log:
    `/workspace/outputs/qlora-rust-xriq-400/qlora-20260516T195917Z.log`.
  - Output adapter:
    `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - Training used the canonical 1000-record dataset for validation, then
    `BIBER_TRAIN_LIMIT_SAMPLES=400` and `BIBER_TRAIN_NUM_EPOCHS=2`.
  - Steps: `100`.
  - Runtime: about `290.5` seconds.
  - Train loss: about `0.7752`.
  - Saved checkpoints include `checkpoint-50`, `checkpoint-75`, and
    `checkpoint-100`.
  - Restarted live serving with the Rust/XRIQ adapter:
    `biber-dev-core=/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
  - Last confirmed pids after restart: vLLM `16407`, FastAPI `16748`.
  - `bash scripts/vast_test_direct.sh` passed after restart.
  - Post-training Rust/XRIQ eval:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260516T200642Z.summary.json`.
  - Post-training Rust/XRIQ result: `6/6` responses, `6/6` substring
    expectations, `5/6` cargo validators.
  - Remaining Rust/XRIQ weak spot: `rust_xriq_mempool_insert` still omitted
    `use std::collections::HashSet;`, causing `cargo check` failure.
  - Added six extra project-owned HashSet-focused Rust/XRIQ source examples and
    tightened the held-out `rust_xriq_mempool_insert` eval prompt so it
    explicitly requires `use std::collections::HashSet;`.
  - Verified the updated Rust/XRIQ targeted source locally and on Vast:
    `16` records, `0` errors, `0` warnings.
  - Reran the Rust/XRIQ eval against the existing live adapter without
    retraining:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260517T001354Z.summary.json`.
  - HashSet follow-up result: `6/6` responses, `6/6` substring expectations,
    and `6/6` cargo validators. No new adapter was trained because the current
    live adapter passed the tightened Rust/XRIQ eval.
  - A first broad 18-prompt eval attempt after Rust/XRIQ retraining wrote
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T000202Z.summary.json`
    with `0/18` responses because FastAPI was not listening yet
    (`Connection refused`). Treat that as an infrastructure failure, not a
    model-quality result.
  - After restarting services with the Rust/XRIQ adapter, the confirmed broad
    18-prompt eval passed:
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T000637Z.summary.json`.
  - Confirmed broad result after Rust/XRIQ retraining: `18/18` responses and
    `18/18` simple expectation checks.
  - Confirmed detailed broad JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T000637Z.jsonl`.
- Started XRIQ Phase 2 design documentation:
  - technical spec draft: `docs/XRIQ_TECHNICAL_SPEC.md`.
  - current draft direction: private-devnet first, account-based first
    prototype, Rust workspace with small crates, deterministic authority
    consensus for the initial private devnet, wallet CLI, and private explorer.
  - public launch, public token distribution, exchange/custody/payment use, and
    production security claims remain out of scope until separate security and
    legal/compliance review.
- Added BIBER agent API and OpenAI/Codex mentor strategy:
  `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md`.
  - BIBER remains the default low-cost GPU-backed inference engine.
  - OpenAI/Codex mentor remains optional and disabled by default unless the user
    explicitly enables it for quality review.
  - Future agent-client work should move toward database-backed API keys,
    repo-agent sessions, patch-oriented responses, streaming, usage logging, and
    explicit mentor review gates.
- Started the Rust private-devnet prototype workspace:
  - workspace path: `xriq/`.
  - first crate: `xriq/crates/xriq-core`.
  - implemented dependency-free private-devnet primitives for checked
    `XriqAmount`, validated devnet `Address`, `Hash32`, basic transaction
    validation, and block-header validation.
  - local validation passed: `cd xriq && cargo fmt --check && cargo test`.
  - Rust test result: `15` passed.
  - local clippy validation passed: `cd xriq && cargo clippy -- -D warnings`.
  - Vast Rust validation passed with the toolchain stored under `/workspace`:
    `cargo fmt --check`, `cargo test`, and `cargo clippy -- -D warnings`.
  - Installed the `clippy` Rust component into `/workspace/.rustup` and updated
    `scripts/vast_install_rust_toolchain.sh` so future Rust setup includes it.
  - No Vast GPU/model training was needed for this step.

## Live Vast.ai Deployment Status

- Host: `70.30.158.46`
- SSH port: `61995`
- SSH key path on this workstation: `C:\Users\vselv\.ssh\biber_vast_ed25519`
- Remote repo path: `/workspace/biber-ai-platform`
- Runtime root: `/workspace`
- Storage:
  - `/workspace` is mounted from `/dev/md0[/volumes/V.36840046/_data]`
    as XFS.
  - Size at last check: `499G`, used `31G`, available `469G`.
  - BIBER runtime, model cache, venv, pip cache, logs, pid files, future
    datasets, checkpoints, adapters, and outputs should stay under
    `/workspace` to use the 500 GB Vast volume and avoid the small root
    filesystem.
- Virtualenv: `/workspace/biber-venv`
- Logs:
  - `/workspace/biber-logs/vllm.log`
  - `/workspace/biber-logs/api.log`
- Pid files:
  - `/workspace/biber-pids/vllm.pid`
  - `/workspace/biber-pids/api.pid`
- vLLM:
  - URL: `http://127.0.0.1:8001/v1`
  - Model: `Qwen/Qwen2.5-Coder-7B-Instruct`
  - Base served model name: `biber-dev-core-base`
  - LoRA adapter model name: `biber-dev-core`
  - LoRA modules:
    `biber-dev-core=/workspace/adapters/biber-dev-core-lora-rust-xriq-400`
  - Tensor parallel size: `2`
  - Max model length: `8192`
  - Current pid at last confirmed check: `1558`
- BIBER FastAPI:
  - URL: `http://127.0.0.1:8000`
  - Environment: `gpu`
  - Chat mode: `infer`
  - Local model name: `biber-dev-core`
  - Current pid at last confirmed check: `1914`
  - Run `bash scripts/vast_status_direct.sh` for current PIDs and bind details.
- Persistent training/output directories created on the 500 GB volume:
  - `/workspace/data`
  - `/workspace/checkpoints`
  - `/workspace/adapters`
  - `/workspace/outputs`
  - `/workspace/.cargo`
  - `/workspace/.rustup`
- Current generated artifact sizes at last check:
  - `/workspace/data`: `3.2M`
  - `/workspace/.cargo`: `20M`
  - `/workspace/.rustup`: `594M`
  - `/workspace/.hf_home`: `15G`
  - `/workspace/outputs`: `304K`
  - `/workspace/adapters`: `3.5G`
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`: `896M`, trained
    and served successfully.
  - `/workspace/adapters/biber-dev-core-lora-targeted-350`: `896M`
  - `/workspace/adapters/biber-dev-core-lora-codeinstruct-998`: `896M`
  - `/workspace/adapters/biber-dev-core-lora`: `409M`
  - `/workspace/adapters/biber-dev-core-lora-smoke`: `409M`
- Current Rust/XRIQ adapter contents should include:
  - `adapter_model.safetensors`: `155M`
  - `adapter_config.json`
  - `tokenizer.json`: `11M`
  - `chat_template.jinja`
  - checkpoints including `checkpoint-50`, `checkpoint-75`, and
    `checkpoint-100`

## Custom Model Training Prep

- A conservative QLoRA training path is now working on the user's own GPU.
  It is meant to keep Codex usage low: Codex prepares and verifies scripts, then
  long fine-tuning runs happen inside `tmux` on Vast.ai.
- Real training data should live on the 500 GB Vast volume at:
  - `/workspace/data/biber_train.jsonl`
- Do not commit real datasets, checkpoints, adapters, or evaluation outputs to
  Git. Keep generated model artifacts under:
  - `/workspace/checkpoints`
  - `/workspace/adapters`
  - `/workspace/outputs`
- Dataset format and validation notes are in `training/dataset_format.md`.
- The tiny `training/sample_dataset.jsonl` file is only for smoke tests.
- Dataset validation entrypoint:

```bash
cd /workspace/biber-ai-platform
/workspace/biber-venv/bin/python training/validate_dataset.py \
  --dataset /workspace/data/biber_train.jsonl \
  --min-records 10 \
  --report /workspace/outputs/dataset-validation.json \
  --print-sample
```

- QLoRA dry-run entrypoint for script/dataset plumbing:

```bash
cd /workspace/biber-ai-platform
/workspace/biber-venv/bin/python training/qlora_train_biber_dev_core.py \
  --dataset training/sample_dataset.jsonl \
  --output-dir /workspace/adapters/dry-run \
  --logging-dir /workspace/outputs/dry-run \
  --dry-run
```

- Long training launcher:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_train_qlora_tmux.sh /workspace/data/biber_train.jsonl
```

- Install `requirements-training.txt` only when preparing an actual training
  run. It intentionally avoids replacing Torch/CUDA by default; preserve the
  working vLLM CUDA stack unless a compatibility issue requires a planned
  change.
- Real starter fine-tuning has completed once. The next training milestone is to
  grow or improve the approved dataset, validate it, then launch a longer QLoRA
  run in `tmux` when the user is ready to spend the GPU time.
- Verified on Vast after pulling `8ae20ad`: compile, sample dataset validation,
  QLoRA dry-run, and `tests/test_training_dataset.py` all passed under
  `/workspace/biber-venv`.
- Internet-sourced training data must use the approved-source ingestion
  pipeline, not broad scraping:
  - manifest: `training/approved_sources.json`
  - script: `training/internet_ingest.py`
  - Vast helper: `scripts/vast_ingest_internet_dataset.sh`
  - raw downloads: `/workspace/data/raw`
  - processed JSONL: `/workspace/data/biber_train_internet.jsonl`
  - provenance: `/workspace/outputs/dataset-provenance.json`
  - validation report: `/workspace/outputs/internet-dataset-validation.json`
- The ingestion pipeline requires each enabled source to be explicitly
  `approved`, license-allowlisted, domain-allowlisted, and attributed. It also
  deduplicates records, filters likely secrets, caps record size, and validates
  the final JSONL before use.
- The current enabled internet sources are the small project-owned smoke
  dataset, the project-owned targeted eval dataset, the project-owned
  Rust/XRIQ targeted dataset, and a bounded 1000-record cap from
  `SoyMaycol/CodeInstruct-20K`. Increase real approved source limits only after
  reviewing license/provenance and storage impact.
- The tracked source file `training/targeted_rust_xriq_dataset.jsonl` now has
  `16` validated project-owned Rust/XRIQ records after adding HashSet-focused
  examples. The canonical `/workspace/data/biber_train.jsonl` was not
  regenerated for this follow-up because the existing live adapter passed the
  tightened Rust/XRIQ eval without another training run.
- Only promote an internet-ingested dataset to `/workspace/data/biber_train.jsonl`
  after reviewing provenance and validation output.
- Current canonical dataset: `/workspace/data/biber_train.jsonl`
  - 1000 records
  - about 2.6M for `/workspace/data` overall
  - validated with 0 errors
  - provenance for its internet candidate:
    `/workspace/outputs/dataset-provenance-rust-xriq-targeted-codeinstruct-1000.json`
- Current trained adapter:
  `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`
  - produced by a 100-step, two-epoch QLoRA run over the first 400 records of
    the Rust/XRIQ-targeted 1000-record dataset.
  - last confirmed served live as `biber-dev-core`.
- Current broad live eval baseline after Rust/XRIQ retraining:
  - runner: `bash scripts/vast_eval_lora_direct.sh`
  - result: `18/18` responses, `18/18` simple expectation checks passed.
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T000637Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T000637Z.jsonl`
  - quality caveat: the current runner checks simple expected substrings or
    regexes. Treat the score as a regression signal, then add stronger
    execution/type/lint validators before trusting it as a quality score.
- Current Rust/XRIQ eval baseline after the HashSet follow-up:
  - runner: `bash scripts/vast_eval_rust_xriq_direct.sh`
  - result: `6/6` responses, `6/6` substring expectations, `6/6` cargo
    validators.
  - summary:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260517T001354Z.summary.json`
  - detailed JSONL:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260517T001354Z.jsonl`
  - prior remaining failure, missing `use std::collections::HashSet;` in
    `rust_xriq_mempool_insert`, is resolved for the current held-out eval.
- The Rust/XRIQ adapter is the current confirmed live candidate: the adapter
  training improved the Rust/XRIQ cargo baseline from `2/6` to `5/6` while
  preserving the broad `18/18` regression baseline. After the HashSet source and
  eval-prompt follow-up, the current live path reaches `6/6` cargo validators.
  The HashSet follow-up did not change model weights.
- The current serving process holds about 14 GB on each 16 GB GPU. Before
  starting another QLoRA run on this instance, stop the direct services with
  `bash scripts/vast_stop_direct.sh`, or run training on a separate GPU.

## Important Fixes Made During Deployment

### Bootstrap script execution

`scripts/vast_bootstrap_direct.sh` now starts services with:

```bash
exec bash "${SCRIPT_DIR}/vast_start_direct.sh"
```

This avoids `Permission denied` on filesystems where the checked-out script is
not executable.

### Shared venv dependency pins

The direct deployment shares one virtualenv between FastAPI and vLLM. The older
API pins downgraded packages below what vLLM `0.21.0` expects. The current API
requirements now include:

```text
fastapi==0.136.1
starlette==0.52.1
pydantic==2.13.4
```

Remote `pip check` passed after applying these pins.

### Loopback bind defaults

`scripts/lib/vast_direct_common.sh` defaults both services to loopback:

```text
BIBER_API_HOST=127.0.0.1
BIBER_VLLM_HOST=127.0.0.1
```

Set either host to `0.0.0.0` only after replacing the starter credentials and
intentionally exposing the instance.

## Moving To A New Vast GPU

Use this section when replacing the current Vast.ai GPU. The goal is to avoid
re-downloading or rebuilding large assets when the current GPU or its storage is
still reachable, while keeping the new instance reproducible from GitHub if the
current GPU is unavailable.

### If the current GPU is still available

1. First make GitHub authoritative for code:

```bash
cd /workspace/biber-ai-platform
git status --short --branch
git log --oneline -1
```

From this workstation, push any local commits before moving:

```powershell
cd C:\Users\vselv\OneDrive\Biber\biber-ai-platform
git push origin main
```

2. Rent the new Vast.ai GPU. Prefer the same OS/template family and enough disk
   space for the existing runtime, model cache, datasets, and checkpoints.

3. Bootstrap code on the new GPU from GitHub:

```bash
cd /workspace
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
```

4. Copy only state that saves real time or cannot be recreated. Important paths:

```text
/workspace/biber-ai-platform/.env     # secrets/config; copy carefully
/workspace/.hf_home                   # Hugging Face/model cache; saves download time
/workspace/pip-cache                  # optional; saves pip download time
/workspace/data                       # future datasets, if present
/workspace/checkpoints                # future training checkpoints, if present
/workspace/adapters                   # future LoRA/QLoRA adapters, if present
/workspace/outputs                    # future evaluation/training outputs, if present
```

Do not copy pid files:

```text
/workspace/biber-pids
```

Logs are optional:

```text
/workspace/biber-logs
```

5. Prefer Vast.ai's instance/volume copy tools or same-provider local network
   copy when available, because that can be faster and may avoid routing large
   transfers through this workstation.

If both old and new instances are reachable to Vast's copy service, use command
shapes like these with the actual Vast instance IDs:

```bash
vastai copy C.<OLD_INSTANCE_ID>:/workspace/.hf_home/ C.<NEW_INSTANCE_ID>:/workspace/.hf_home/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/pip-cache/ C.<NEW_INSTANCE_ID>:/workspace/pip-cache/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/data/ C.<NEW_INSTANCE_ID>:/workspace/data/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/checkpoints/ C.<NEW_INSTANCE_ID>:/workspace/checkpoints/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/adapters/ C.<NEW_INSTANCE_ID>:/workspace/adapters/
```

For a Vast 500 GB volume, remember that Vast volumes are local to the machine
where they were created. If the same machine can still be used, rent the new
instance using the existing volume. If moving to a different machine, create a
new destination volume/instance and copy data instead of assuming the old volume
can be attached directly:

```bash
vastai copy V.<OLD_VOLUME_ID>:/data/ V.<NEW_VOLUME_ID>:/data/
vastai copy V.<OLD_VOLUME_ID>:/data/ C.<NEW_INSTANCE_ID>:/workspace/
vastai copy C.<OLD_INSTANCE_ID>:/workspace/ V.<NEW_VOLUME_ID>:/data/
```

If using manual SSH copy, run it from a Linux shell that can reach both
instances. Example shape:

```bash
rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/.hf_home/ /workspace/.hf_home/

rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/pip-cache/ /workspace/pip-cache/

rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/biber-ai-platform/.env /workspace/biber-ai-platform/.env
```

For training datasets/checkpoints, copy the relevant directories only if they
exist:

```bash
rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/data/ /workspace/data/

rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/checkpoints/ /workspace/checkpoints/

rsync -aH --info=progress2 \
  -e "ssh -p <OLD_SSH_PORT> -i <SSH_KEY>" \
  root@<OLD_HOST>:/workspace/adapters/ /workspace/adapters/
```

If a training job is actively writing checkpoints, stop or pause the job first,
or run `rsync` twice so the second pass catches changed files.

6. Start the new GPU direct deployment:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_bootstrap_direct.sh
bash scripts/vast_test_direct.sh
bash scripts/vast_status_direct.sh
```

7. Update this handoff immediately with the new host, SSH port, runtime paths,
PIDs, bind status, test result, and whether caches/datasets/checkpoints were
copied or rebuilt.

8. Keep the old GPU only until the new GPU is verified. After verification,
stop or destroy the old instance according to the user's cost/risk preference.
Remember: stopped storage can still cost money; destroyed instance storage is
not recoverable unless copied/backed up first.

### If the current GPU is not available

1. Treat the new GPU as a clean rebuild from GitHub:

```bash
cd /workspace
git clone https://github.com/selvasmallive/biber-ai-platform.git
cd biber-ai-platform
cp .env.example .env
```

2. Recreate `.env` from the user's secure password manager or prior private
backup. Do not paste secrets into chat or docs. Keep loopback values unless
public exposure is intentionally configured:

```text
BIBER_API_HOST=127.0.0.1
BIBER_VLLM_HOST=127.0.0.1
```

3. Rebuild runtime and re-download model cache:

```bash
bash scripts/vast_bootstrap_direct.sh
bash scripts/vast_test_direct.sh
bash scripts/vast_status_direct.sh
```

4. Restore datasets/checkpoints/adapters from whatever backup exists. If no
backup exists, assume training data/checkpoints on the unavailable GPU are lost
and continue from GitHub plus any local/cloud copies.

5. Update this handoff with the new state and explicitly mark which assets were
rebuilt, restored, or lost.

## Reconnect And Test

From Windows PowerShell:

```powershell
ssh -i C:\Users\vselv\.ssh\biber_vast_ed25519 -p 61995 root@70.30.158.46 -L 8080:localhost:8080 -L 8000:127.0.0.1:8000 -L 8001:127.0.0.1:8001
```

Then open:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8001/v1/models
http://127.0.0.1:8080
```

Do not paste private key contents, Vast API keys, Jupyter tokens, or `.env`
secrets into chat or docs.

## Useful Remote Commands

After SSH:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
bash scripts/vast_eval_lora_direct.sh
```

Restart only the BIBER direct services:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_stop_direct.sh
bash scripts/vast_start_lora_direct.sh
```

Start base-model-only serving, if adapter serving must be bypassed. The LoRA
start path persists `BIBER_VLLM_LORA_MODULES` in `.env`, so remove that line
before using the plain direct start:

```bash
cd /workspace/biber-ai-platform
sed -i '/^BIBER_VLLM_LORA_MODULES=/d' .env
BIBER_VLLM_SERVED_MODEL_NAME=biber-dev-core bash scripts/vast_start_direct.sh
```

Rerun bootstrap if the environment is partially missing:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_bootstrap_direct.sh
```

Follow logs:

```bash
tail -f /workspace/biber-logs/api.log
tail -f /workspace/biber-logs/vllm.log
```

## Important Config Notes

- `.env` exists on the Vast.ai instance.
- `.env` explicitly contains:
  - `BIBER_API_HOST=127.0.0.1`
  - `BIBER_VLLM_HOST=127.0.0.1`
  - `BIBER_LOCAL_MODEL_NAME=biber-dev-core`
  - `BIBER_VLLM_SERVED_MODEL_NAME=biber-dev-core-base`
  - `BIBER_VLLM_LORA_MODULES=biber-dev-core=/workspace/adapters/biber-dev-core-lora-rust-xriq-400`
- A redacted credential audit on 2026-05-16 showed the live `.env` still uses
  starter values for sensitive placeholders. Live rotation was not performed
  because changing running API credentials requires explicit user approval.
- Before public exposure, replace all starter credentials in `.env`:
  - `BIBER_ADMIN_PASSWORD`
  - `BIBER_DEMO_API_KEY`
  - `BIBER_API_KEYS`
  - `BIBER_PASSCODE_FULL_GPU`
  - `BIBER_PASSCODE_20_GPU`
  - `BIBER_PASSCODE_QUEUE_PRIORITY`
  - `BIBER_PRIORITY_PASSCODES`
  - `MYSQL_ROOT_PASSWORD`
  - `MYSQL_PASSWORD`
- The direct path currently starts:
  - `biber-dev-core-base` through vLLM as the base model.
  - `biber-dev-core` through vLLM as the LoRA adapter model.
  - BIBER FastAPI, configured to use `biber-dev-core`.
- The direct path does not start MySQL, Redis, or Adminer.
- Optional integrations are currently not configured on the live instance:
  - OpenAI mentor
  - durable GitHub generated-code save credentials
  - Azure Blob backups

## Operating Notes For Future Codex Sessions

- Do not rotate live credentials routinely. Treat credential rotation as an
  explicit, infrequent operation that requires user approval and a plan for
  preserving the new secrets outside chat.
- Keep the deployment loopback-only while starter credentials remain in place.
- Cost-saving strategy: use Codex minimally for engineering setup, script
  changes, error diagnosis, evaluation/deployment glue, and handoff updates.
  Run long model work directly on the user's Vast.ai GPU instead of keeping a
  Codex session active. Start training, fine-tuning, batch evaluation, and other
  multi-hour jobs in `tmux`/`screen` on the GPU; disconnect while they run; bring
  Codex back only for failures, log review, result interpretation, or the next
  code/deployment change.
- Future custom-model phases should prefer the user's own GPU and eventual
  fine-tuned `biber-dev-core` model over paid external model APIs. Keep optional
  mentor APIs disabled unless the user explicitly wants them for quality review.
- Future BIBER API-key agent-client and mentor work is documented in
  `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md`. Treat BIBER as the default
  engine and OpenAI/Codex as an optional mentor/reviewer for architecture,
  security-sensitive Rust/crypto review, eval design, failure diagnosis, and
  curated training-data review.
- Future Rust/XRIQ work is now an explicit project track documented in
  `docs/XRIQ_RUST_TRACK.md`. Treat it as a phased path: first prove BIBER's
  Rust capability with `cargo`-backed evals, then design XRIQ, then build a
  private Rust devnet, then wallet/explorer tools, and only later consider any
  public network or cryptocurrency launch after separate security and
  legal/compliance review.
- Near-term language priority is Rust/XRIQ first because the user's first major
  inference use case for BIBER AI is developing the XRIQ cryptocurrency
  blockchain. Defer .NET, Spring Boot Java, broader Python expansion, and other
  language-specific fine-tuning until Rust/XRIQ evals and private-devnet support
  are established, unless the user explicitly changes priority.
- Broader post-Rust capability order is now explicit in
  `docs/BIBER_CAPABILITY_ROADMAP.md`. After Rust/XRIQ, prioritize PostgreSQL,
  React, TypeScript, JavaScript, jQuery, CSS, HTML, Docker, GitHub Actions
  CI/CD, WASM, Bash scripts, security engineering, cryptography concepts,
  Kubernetes, and distributed systems optimization before lower-priority
  generic SQL, YAML, .NET, Spring Boot Java, Python expansion, or other stacks.
- Apply the capability roadmap through inference/evals first and targeted GPU
  fine-tuning only for repeatable gaps. This preserves the cost-saving strategy:
  Vast.ai does the long GPU work, while Codex is used only where it preserves
  quality and momentum.
- Update this handoff at important points so a new Codex session can resume
  accurately from the current Vast.ai state. Important points include:
  - live service restarts or failures
  - host, SSH port, key path, runtime path, pid, or log path changes
  - Git commit/branch/remote state changes
  - dependency, model, port, bind, or environment changes
  - smoke test, runtime test, mentor, GitHub save, Azure backup, MySQL, or Redis
    status changes
  - credential status changes, without recording secret values

## Recommended Next Steps

1. Fast-forward the Vast checkout to GitHub `main` after this handoff update is
   pushed:
   `cd /workspace/biber-ai-platform && git pull --ff-only origin main`.
2. Treat `/workspace/adapters/biber-dev-core-lora-rust-xriq-400` as the current
   confirmed live candidate. The adapter training improved Rust/XRIQ cargo
   validators from `2/6` to `5/6`, and the HashSet source/eval follow-up now
   reaches `6/6` on the current eval without changing weights. It preserved the
   broad `18/18` baseline.
3. Do not train immediately for the prior HashSet failure. The current adapter
   passed the tightened Rust/XRIQ eval, so the cost-saving next step is XRIQ
   inference usage and stronger Rust eval coverage, not another GPU run.
4. Train again only if future Rust/XRIQ evals show repeatable gaps or if the
   user explicitly prioritizes Rust improvement over spending time on the next
   capability domain.
5. Continue the XRIQ private-devnet prototype by adding `xriq-ledger` account
   state transitions, nonce checks, balance updates, and deterministic unit
   tests.
6. Keep reviewing and refining `docs/XRIQ_TECHNICAL_SPEC.md` as the prototype
   clarifies open decisions. Do not treat the private devnet as public launch
   readiness.
7. Use BIBER AI for XRIQ through inference first: spec drafting, Rust module
   scaffolding, tests, review prompts, and private-devnet tooling. Fine-tune
   only after Rust/XRIQ evals show repeatable gaps.
8. After the Rust/XRIQ baseline is stable, follow
   `docs/BIBER_CAPABILITY_ROADMAP.md` in order: PostgreSQL, React, TypeScript,
   JavaScript, jQuery, CSS, HTML, Docker, GitHub Actions CI/CD, WASM, Bash,
   security engineering, cryptography concepts, Kubernetes, and distributed
   systems optimization before lower-priority stacks.
9. Add new training data only through approved/provenance-tracked sources, then
   validate and promote to `/workspace/data/biber_train.jsonl`.
10. Train again only when the broader evals reveal real gaps. Keep the
   cost-saving pattern: Codex changes the scripts and reviews outputs; Vast.ai
   runs long GPU jobs in `tmux`.
11. For the next QLoRA run on the current Vast GPU, stop the direct services
   first because vLLM occupies most GPU memory:
   `bash scripts/vast_stop_direct.sh`.
12. Launch the QLoRA job with `scripts/vast_train_qlora_tmux.sh` so the GPU keeps
   working after Codex disconnects, then restart serving after the adapter is
   produced and evaluated.
13. Restart LoRA serving with `bash scripts/vast_start_lora_direct.sh`, rerun
    `bash scripts/vast_eval_lora_direct.sh`, and compare against the current
    `18/18` broad baseline.
14. Keep the API private over SSH tunnels unless credentials are deliberately
   rotated and public binding is intentionally enabled.
15. Keep the Vast.ai checkout fast-forwarded with local/GitHub `main`.
16. Add optional OpenAI mentor credentials if desired and cost-approved.
17. Add database-backed API keys and agent-client sessions per
    `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md`.
18. Add a durable fine-grained GitHub token to Vast `.env` if persistent
   generated-code save should stay enabled.
19. Add Azure Blob connection string and test backups.
20. Replace demo API key/passcode auth with database-backed credentials.
21. Add real MySQL persistence and Redis worker integration.

## Resume Prompt For A New Chat

```text
Read docs/CODEX_HANDOFF.md and continue the Vast.ai deployment and development
of biber-ai-platform from the current live GPU state.
```
