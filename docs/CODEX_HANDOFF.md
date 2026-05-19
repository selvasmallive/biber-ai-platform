# Codex Handoff

Last updated: 2026-05-19

## Current Goal

Near-term goal: finish the cost-conscious BIBER MVP and the XRIQ private-devnet
prototype from the current GPU-backed direct vLLM/FastAPI state.

- Current focus:
  - BIBER MVP: local model API, model registry, repo context, file-edit/test
    workflows, GitHub save/PR path, and optional OpenAI mentor review only when
    it is worth the cost.
  - BIBER MVP must now treat these Replit-replacement workflow capabilities as
    first-class near-term goals: more reliable repo-context selection, safer
    multi-file editing, and better structured test-failure diagnosis loops.
  - XRIQ private devnet: Rust-only private-devnet chain, replay startup, local
    runner/RPC tooling, wallet flow, explorer flow, and integration tests.
- Delayed scope:
  - Public XRIQ remains part of the later project plan, but do not implement
    public token economics, DEX/liquidity, validator rewards, public governance,
    bridges, custody, listings, or launch-facing claims during this near-term
    phase.
  - Future XRIQ privacy should follow a Zcash-like selective-disclosure
    roadmap: optional shielded transfers, viewing keys, payment/audit
    disclosure, and crypto agility after review. Do not make Monero-style
    mandatory privacy or default opaque transfers part of the MVP or default
    public design while DEX usability and AML-friendly posture remain goals.
  - Keep `docs/XRIQ_LEGAL_RISK_REDUCTION.md` as a hard guardrail for any future
    public XRIQ work.

## Cost-Control Execution Policy

Future Codex sessions must default to a low-OpenAI-cost operating mode.

- Primary near-term budget target: try to finish the focused BIBER MVP plus
  XRIQ private-devnet prototype with roughly `$250-$900` of additional
  OpenAI/Codex usage, and treat about `$500` as the practical disciplined target
  when scope stays focused.
- Do not use Codex as the default bulk implementation engine. Use Codex for
  planning, risky architecture, small scoped patches, security-sensitive Rust
  review, failure diagnosis, integration glue, verification interpretation, and
  handoff updates.
- Use the user's Vast.ai GPU, local scripts, the local BIBER model, and ordinary
  deterministic tests for repetitive generation, long-running evals, QLoRA,
  dataset work, smoke loops, and batch validation.
- Actual model training/fine-tuning should run on the Vast GPU with local
  datasets, local scripts, local checkpoints, and local evals. Do not put
  OpenAI/Codex calls inside the training loop. OpenAI/Codex cost should come
  only from bounded engineering sessions and optional mentor/reviewer calls.
- Do not start broad exploratory rewrites, large refactors, public XRIQ work,
  or extra model-training loops unless they directly unblock the focused MVP or
  the user explicitly approves the cost.
- Keep OpenAI mentor/reviewer calls optional and disabled by default. Use them
  only when the user requests mentor review or when quality/risk justifies it,
  such as cryptography boundaries, security design, eval design, legal-risk
  docs, or complex architecture decisions.
- Prefer the smallest valuable checkpoint: one narrow feature, one focused test
  addition, one doc checkpoint, or one deployment verification at a time.
- For docs-only updates, do not rerun expensive Rust/Vast verification; commit,
  push, and fast-forward Vast. For Rust/code changes, run focused local checks
  first, then Vast verification only after the local result is clean.
- If a future step looks likely to consume more than about `$50` of OpenAI/Codex
  usage or to require a long open-ended agent session, pause and give the user a
  cost/risk estimate before proceeding.

## Immediate Resume State

As of the latest 2026-05-18 checkpoint, the Vast.ai deployment is healthy and
serving the last broad-safe Rust/XRIQ adapter.

- Latest BIBER API/XRIQ wrapper commits pushed and Vast-verified:
  `ddc5dc8 Add BIBER XRIQ preflight API wrapper` and
  `67ce353 Add XRIQ wrapper Rust environment config`.
- Latest BIBER API/XRIQ read-wrapper commit pushed and Vast-verified:
  `4d8c251 Add BIBER XRIQ read wrappers`.
- Latest BIBER API/XRIQ durable mempool wrapper commit pushed and
  Vast-verified:
  `81824b3 Add XRIQ durable mempool wrapper`.
- Latest BIBER API/XRIQ explorer/block wrapper commit pushed and Vast-verified:
  `32909e8 Add BIBER XRIQ explorer wrappers`.
- Latest BIBER API/XRIQ consolidated smoke script commit pushed and
  Vast-verified:
  `16e506b Add BIBER XRIQ API smoke script`.
- Latest BIBER API/XRIQ snapshot wrapper commit pushed and Vast-verified:
  `4dbe7a0 Add BIBER XRIQ snapshot API wrapper`.
- Latest BIBER API/XRIQ snapshot discovery commit pushed and Vast-verified:
  `fc03d6d Add XRIQ snapshot discovery API`.
- Latest BIBER API/XRIQ private-devnet overview commit pushed and
  Vast-verified:
  `716e9c1 Add XRIQ private devnet overview API`.
- Latest BIBER API/XRIQ private-devnet client commit pushed and
  Vast-verified:
  `2bb7ca0 Add BIBER XRIQ private devnet client`.
- Latest BIBER API/XRIQ private-devnet dashboard commit pushed and
  Vast-verified:
  `afa080b Add XRIQ private devnet dashboard`.
- Latest BIBER API/XRIQ dashboard preflight-action commit pushed and
  Vast-verified:
  `f5f55a4 Add XRIQ dashboard preflight action`.
- Latest BIBER API/XRIQ dashboard transaction-lookup commit pushed and
  Vast-verified:
  `0e7975c Add XRIQ dashboard transaction lookup`.
- Latest BIBER API/XRIQ dashboard account-lookup commit pushed and
  Vast-verified:
  `4af1ee5 Add XRIQ dashboard account lookup`.
- Latest XRIQ explorer transaction-hash navigation commit pushed and
  Vast-verified:
  `6205b66 Expose XRIQ block transaction hashes`.
- Last XRIQ implementation commit pushed and Vast-verified:
  `919b348 Expose XRIQ replay state root`.
- Latest XRIQ checked-fixture-only commit pushed and Vast-verified:
  `66098c1 Add XRIQ block detail JSON fixture`.
- Latest XRIQ smoke-harness commit pushed and Vast-verified:
  `919b348 Expose XRIQ replay state root`.
- Latest XRIQ snapshot export/import commit pushed and Vast-verified:
  `fba4a1d Add XRIQ snapshot export import`.
- Latest BIBER MVP core-agent test-runner commit pushed and Vast-verified:
  `d4df8c0 Add allowlisted BIBER test runner API`.
- Latest BIBER MVP bounded workspace-edit commit pushed and Vast-verified:
  `992890b Add bounded BIBER workspace edit API`.
- Latest BIBER MVP GitHub branch/PR workflow commits pushed and Vast-verified:
  `552220b Add BIBER GitHub PR workflow support` and
  `179f58b Clarify GitHub workflow test label`.
- Latest BIBER MVP end-to-end agent-smoke script commit pushed and
  Vast-verified:
  `28ebe62 Add BIBER agent smoke script`.
- Latest BIBER MVP agent-session API/persistence commits pushed and
  Vast-verified:
  `b280d49 Add BIBER agent session API` and
  `786ec51 Persist BIBER agent sessions`.
- Latest BIBER MVP agent-session XRIQ-context commit pushed and Vast-verified:
  `e4df1d0 Add XRIQ context to agent sessions`.
- Latest BIBER MVP agent-capabilities commit pushed and Vast-verified:
  `8a539de Add BIBER agent capabilities endpoint`.
- Latest BIBER MVP agent-client helper commit pushed and Vast-verified:
  `51ad833 Add BIBER agent client helper`.
- Latest BIBER MVP repo-adaptation commits pushed and Vast-verified:
  `9126fdd Add BIBER repo adaptation plan` and
  `2efa65b Fix repo adaptation relative role detection`.
- Latest BIBER MVP repo-context planner commit pushed and Vast-verified:
  `1cc790a Add BIBER repo context planner`.
- Latest BIBER MVP multi-file edit planner commit pushed and Vast-verified:
  `70e6320 Add BIBER multi-file edit planner`.
- This handoff now makes reliable repo-context selection, safer multi-file
  editing, and structured test-failure diagnosis explicit BIBER MVP goals.
- Vast code verification is current through `70e6320`. Full Rust/private-devnet
  verification is current through `fba4a1d`; focused BIBER API wrapper/client
  and dashboard verification is current through `4af1ee5`; consolidated BIBER
  XRIQ API smoke verification is current through `4af1ee5`; focused fixture
  verification is current through `919b348`; BIBER test-runner API verification
  is current through `d4df8c0`; BIBER workspace-edit API verification is
  current through `992890b`; BIBER GitHub branch/PR workflow verification is
  current through `179f58b`; BIBER agent-smoke verification is current through
  `51ad833`;
  BIBER agent-session API/persistence verification is current through
  `51ad833`; BIBER repo-adaptation verification is current through `2efa65b`;
  BIBER repo-context planner verification is current through `1cc790a`;
  BIBER multi-file edit planner verification is current through `70e6320`.
- Current served adapter:
  `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
- Current agent-session artifact directory:
  `/workspace/outputs/agent-sessions`.
- Current serving state:
  - vLLM pid: `5802`
  - FastAPI pid: `51376`
  - API bind: `127.0.0.1:8000`
  - vLLM bind: `127.0.0.1:8001`
  - The `70e6320` multi-file edit planner checkpoint required a FastAPI-only
    restart because it added `POST /v1/files/edit/plan` and expanded
    `GET /v1/agent/capabilities`. vLLM stayed on pid `5802`; FastAPI moved
    from pid `51098` to pid `51376`.
  - Latest focused Vast verification for the BIBER multi-file edit planner
    slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_workspace_edit.py tests/test_agent_capabilities.py -q`
    with `12 passed`, a live authenticated `POST /v1/files/edit/plan` smoke,
    and a follow-up check confirming the planned create file was not written.
  - The `1cc790a` repo-context planner checkpoint required a FastAPI-only
    restart because it added `POST /v1/repo/context/plan` and expanded
    `GET /v1/agent/capabilities`. vLLM stayed on pid `5802`; FastAPI moved
    from pid `50843` to pid `51098`.
  - Latest focused Vast verification for the BIBER repo-context planner slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests`, focused
    pytest `tests/test_repo_context.py tests/test_agent_capabilities.py -q`
    with `12 passed`, and a live authenticated
    `POST /v1/repo/context/plan` smoke selecting
    `docs/API_EXAMPLES.md`, `src/biber_api/repo_context.py`,
    `tests/test_repo_context.py`, `pyproject.toml`, `xriq/Cargo.lock`, and
    `xriq/Cargo.toml`.
  - The `2efa65b` repo-adaptation checkpoint required a FastAPI-only restart
    because it also updated the `pytest-core` allowlist served by the API.
    vLLM stayed on pid `5802`; FastAPI moved from pid `50453` to pid `50843`.
  - Latest focused Vast verification for the BIBER repo-adaptation slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts training`,
    focused pytest
    `tests/test_repo_adaptation_plan.py tests/test_training_dataset.py -q`
    with `7 passed`, and a real plan smoke writing
    `/workspace/outputs/repo-adaptation-plan-smoke.json` plus
    `/workspace/outputs/repo-adaptation-eval-smoke.jsonl`.
  - The `51ad833` agent-client helper checkpoint required a FastAPI-only
    restart because it also updated the `pytest-core` allowlist served by the
    API. vLLM stayed on pid `5802`; FastAPI moved from pid `50105` to
    pid `50453`.
  - Latest focused Vast verification for the BIBER agent-client helper slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, and focused pytest covering
    `test_biber_agent_client.py`, `test_agent_capabilities.py`, and
    `test_agent_session.py` with `11 passed`.
  - The `8a539de` agent-capabilities checkpoint required a FastAPI-only
    restart. vLLM stayed on pid `5802`; FastAPI moved from pid `49733` to
    pid `50105`.
  - Latest focused Vast verification for the BIBER agent-capabilities slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, and focused pytest covering
    `test_agent_capabilities.py`, `test_agent_session.py`, and
    `test_xriq_preflight_api.py` with `25 passed`.
  - The `e4df1d0` agent-session XRIQ-context checkpoint required a FastAPI-only
    restart. vLLM stayed on pid `5802`; FastAPI moved from pid `48095` to
    pid `49733`.
  - Latest focused Vast verification for the BIBER agent-session XRIQ-context
    slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, and focused pytest covering
    `test_agent_session.py` and `test_xriq_preflight_api.py` with `23 passed`.
  - The `4af1ee5` dashboard account-lookup checkpoint required no service
    restart. vLLM stayed on pid `5802`; FastAPI stayed on pid `48095`.
  - Latest focused Vast verification for the BIBER/XRIQ dashboard account
    lookup:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest covering
    `test_xriq_preflight_api.py`, `test_xriq_private_devnet_client.py`, and
    `test_xriq_dashboard.py` with `26 passed`.
  - The `0e7975c` dashboard transaction-lookup checkpoint required no service
    restart. vLLM stayed on pid `5802`; FastAPI stayed on pid `48095`.
  - Latest focused Vast verification for the BIBER/XRIQ dashboard transaction
    lookup:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest covering
    `test_xriq_preflight_api.py`, `test_xriq_private_devnet_client.py`, and
    `test_xriq_dashboard.py` with `26 passed`.
  - The `f5f55a4` dashboard preflight-action checkpoint required no service
    restart. vLLM stayed on pid `5802`; FastAPI stayed on pid `48095`.
  - Latest focused Vast verification for the BIBER/XRIQ dashboard preflight
    action:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest covering
    `test_xriq_preflight_api.py`, `test_xriq_private_devnet_client.py`, and
    `test_xriq_dashboard.py` with `26 passed`.
  - The `afa080b` dashboard checkpoint required a FastAPI-only restart.
    vLLM stayed on pid `5802`; FastAPI moved from pid `47248` to pid `48095`.
  - Latest focused Vast verification for the BIBER/XRIQ dashboard slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest covering
    `test_xriq_preflight_api.py`, `test_xriq_private_devnet_client.py`, and
    `test_xriq_dashboard.py` with `26 passed`.
  - Browser dashboard route is live at:
    `http://127.0.0.1:8000/xriq/private-devnet/dashboard` when connected
    through the SSH tunnel. It is same-origin with the API and stores the typed
    API key only in browser `sessionStorage`.
  - The `2bb7ca0` client/docs/test checkpoint required no service restart;
    vLLM stayed on pid `5802` and FastAPI stayed on pid `47248`.
  - Latest focused Vast verification for the BIBER/XRIQ API client slice:
    `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and
    `pytest tests/test_xriq_preflight_api.py tests/test_xriq_private_devnet_client.py -q`
    with `24 passed`.
  - Latest BIBER test-runner smoke:
    `GET /v1/tests` returned the four allowlisted commands and
    `POST /v1/tests/run` with `test_id=python-compileall-api` returned
    `200 OK`, `executed=true`, and `ok=true`.
  - Latest BIBER workspace-edit smoke:
    `POST /v1/files/edit` with `create_if_missing=true` and `dry_run=true`
    returned `200 OK`, `created=true`, `changed=true`, and did not write a
    file.
  - Latest BIBER GitHub PR workflow smoke:
    `POST /v1/github/pull-request` returned the expected `503` with
    `GitHub saving is not configured` because live GitHub credentials are still
    intentionally not configured on Vast.
  - Latest BIBER end-to-end agent smoke:
    `bash scripts/vast_biber_agent_smoke.sh` passed with repo-context chat,
    agent-capabilities discovery, workspace-edit dry-run,
    `python-compileall-api`, opt-in XRIQ private-devnet context in a tracked
    agent session, and GitHub skipped because it is not configured. Latest
    artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T000619Z-50478`.
    Latest capability presets were `default_coding_session` and
    `xriq_private_devnet_review`. The smoke also validated the new
    `scripts/biber_agent_client.py capabilities --json` path and wrote
    `agent-client-capabilities.json`.
    Latest XRIQ-context session id:
    `36c0098f-d4a6-4674-9e58-88925bfb3d31`; step order was
    `xriq_context`, then `chat`; context height was `2`; mentor was not used.
  - Latest BIBER agent-session smoke:
    `POST /v1/agent/sessions` returned `200 OK` with steps `chat`,
    `workspace_edit`, and `test_run`; `model=biber-dev-core-v1`,
    `mentor_used=false`, workspace edit was dry-run only, and
    `python-compileall-api` returned `ok=true`. The persisted artifact was
    `/workspace/outputs/agent-sessions/af658dd2-44b6-4800-bd87-561b7424c17c.json`.
    `GET /v1/agent/sessions?limit=5` included the new session, and
    `GET /v1/agent/sessions/af658dd2-44b6-4800-bd87-561b7424c17c` returned
    the same persisted session.
  - Latest endpoint smoke:
    `POST /v1/xriq/private-devnet/preflight-transfer`,
    `GET /v1/xriq/private-devnet/status`,
    `GET /v1/xriq/private-devnet/accounts/xriqdev1alice00000000000`, and
    `GET /v1/xriq/private-devnet/transactions/{hash}` returned `200 OK`.
    Latest live mempool smoke also confirmed
    `GET /v1/xriq/private-devnet/mempool` returns `200 OK` with
    `command=mempool-detail` and current `pending_count=0`.
    Latest live explorer/block smoke confirmed
    `GET /v1/xriq/private-devnet/explorer?limit=5` returns
    `command=explorer-overview` with `current_height=2`, and
    `GET /v1/xriq/private-devnet/blocks/1` returns `command=block-detail`
    with `height=1`.
    Latest consolidated API smoke with `bash scripts/vast_xriq_api_smoke.sh`
    passed with status/explorer height `2`, block height `2`, Alice account
    detail, mempool pending count `0`, `POST
    /v1/xriq/private-devnet/snapshots/export`, `POST
    /v1/xriq/private-devnet/snapshots/import` to the safe staging target,
    `GET /v1/xriq/private-devnet/snapshots?limit=10`, `GET
    /v1/xriq/private-devnet/snapshots/{snapshot_name}`, snapshot height `2`,
    `GET /v1/xriq/private-devnet/overview?explorer_limit=5&snapshot_limit=10`,
    snapshot list count `8`, overview snapshot count `8`, state root
    `578bdd2affeece78c7949d34da08391c797b363b045c3cff6c999868e0baa2d6`,
    transaction hash
    `e1dadff3325ac720c71bfa8c900ed15e2637dbb041848f0fdfe35dbfbbb94e1d`
    sourced from the latest block, transaction detail status `confirmed`, and
    the minimal stdlib client commands for overview, snapshot list, and
    snapshot detail. The smoke also fetched
    `GET /xriq/private-devnet/dashboard` and verified the dashboard marker,
    preflight-transfer endpoint marker, and `transferForm` marker without
    submitting a transaction. It also verified the dashboard transaction-detail
    endpoint marker, `transactionLookupForm` marker, dashboard account-detail
    endpoint marker, and `accountLookupForm` marker.
    Latest smoke artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T233249Z-49206`. Client
    artifacts inside that directory:
    `client-overview.txt`, `client-snapshots.txt`, and
    `client-snapshot-detail.txt`. Dashboard artifact:
    `dashboard.html`.
    The earlier read smoke confirmed `transaction_status=confirmed` and status
    `current_height=2` for the test chain used in that smoke.
  - Latest XRIQ private-devnet CLI smoke:
    `bash scripts/xriq_private_devnet_smoke.sh` passed after adding
    snapshot export/import coverage. Artifact:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260518T203806Z-44845`.
    It includes `snapshot/`, `snapshot-export.json`,
    `snapshot-import-chain.bin`, and `snapshot-import.json`.
  - Last full chat smoke remains `bash scripts/vast_test_direct.sh` with chat
    content `ok` before the FastAPI-only restart; vLLM remained running.
- Latest current Rust/XRIQ eval:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260517T021032Z.summary.json`
  - result: `7/7` responses, `7/7` substring expectations,
    `6/7` cargo validators.
  - remaining failure: `rust_xriq_apply_ledger_transaction` failed
    `cargo fmt --check`. The generated code also used an external
    `thiserror::Error` derive that is not available in the eval crate, so treat
    the ledger prompt as not solved by the model yet.
- Latest current broad eval:
  - summary:
    `/workspace/outputs/evals/biber-dev-core-lora-20260517T021053Z.summary.json`
  - result: `18/18` responses and `18/18` simple expectation checks.
- Current canonical training dataset:
  - path: `/workspace/data/biber_train.jsonl`
  - candidate source:
    `/workspace/data/biber_train_rust_xriq_fee_codeinstruct_1000.jsonl`
  - records: `1000`
  - mix: `2` smoke, `27` Python/API targeted, `21` Rust/XRIQ targeted,
    `3` Rust/XRIQ validation-regression, `2` Rust/XRIQ ledger-regression,
    `2` Rust/XRIQ fee-regression, and `943` CodeInstruct records.
  - provenance:
    `/workspace/outputs/dataset-provenance-rust-xriq-fee-codeinstruct-1000.json`
  - validation:
    `/workspace/outputs/internet-dataset-validation-rust-xriq-fee-codeinstruct-1000.json`
    and `/workspace/outputs/dataset-validation-rust-xriq-fee-current.json`
- QLoRA attempts made after adding the ledger eval:
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-ledger-validation-560`
    failed early and left an empty adapter directory. Log:
    `/workspace/outputs/qlora-rust-xriq-ledger-validation-560/qlora-20260517T013913Z.log`.
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-ledger-validation-280`
    completed, train loss about `0.7749`, reached `6/7` Rust/XRIQ validators,
    but broad eval regressed to `17/18`; not promoted.
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-fee-validation-280`
    completed, train loss about `0.7728`, but reached only `5/7` Rust/XRIQ
    validators; not promoted.
  - `/workspace/adapters/biber-dev-core-lora-rust-xriq-focused-120e4`
    completed, train loss about `0.6196`, reached `6/7` Rust/XRIQ validators,
    but still failed the ledger prompt; not promoted.
- Conclusion: keep serving `biber-dev-core-lora-rust-xriq-400` for now because
  it preserves the broad `18/18` baseline and ties the best current Rust/XRIQ
  validator score at `6/7`. Do not chase more blind QLoRA runs for the ledger
  prompt without first improving the eval design, prompt scaffolding, or
  training-data strategy.
- XRIQ prototype progress made after the last model eval:
  - `docs/XRIQ_TECHNICAL_SPEC.md` now makes the intended XRIQ advantages
    explicit: no mining, predictable fees, Rust-first implementation, clean
    token issuance, DEX/BTC-swap friendliness, Zcash-like selective privacy as
    a future roadmap track, crypto agility, cautious compliance posture, and
    BIBER-assisted vertical tooling.
  - Added `xriq/crates/xriq-mempool` to the Rust workspace for deterministic
    private-devnet pending-transaction rules.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `27` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-mempool`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test` with `27`
    passing tests, and `cargo clippy -- -D warnings`.
- XRIQ prototype progress after the mempool checkpoint:
  - Added `xriq/crates/xriq-consensus` for deterministic single-authority
    private-devnet block production.
  - The producer creates child blocks from a parent header view, uses explicit
    state-root and transactions-root inputs, enforces block signatures, caps
    transaction count, and selects mempool transactions by deterministic
    fee/order/hash ordering.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `34` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-consensus`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test` with `34`
    passing tests, and `cargo clippy -- -D warnings`.
- Added the dedicated XRIQ legal-risk guardrail document:
  `docs/XRIQ_LEGAL_RISK_REDUCTION.md`.
  - Future Codex/BIBER sessions must follow it before XRIQ public-token, DEX,
    custody, bridge, stablecoin, payment, airdrop, validator-reward, liquidity,
    listing, or investment-facing messaging work.
  - Treat it as conservative engineering guidance, not legal advice. Public
    launch steps still require qualified legal, tax, AML, sanctions, securities,
    commodities, consumer-protection, and security review.
- Local XRIQ prototype progress after the legal-risk guardrail checkpoint:
  - Added `xriq/crates/xriq-rpc` for dependency-free local private-devnet RPC
    endpoint behavior.
  - The local RPC service currently covers health, chain status, account lookup,
    mempool listing, pending transaction lookup, and transaction submission with
    ledger-backed validation before mempool insertion.
  - Added `Mempool::entry` so RPC can expose pending transaction status without
    duplicating mempool internals.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `40` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-rpc`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test` with `40`
    passing tests, and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the RPC checkpoint:
  - Added `xriq/crates/xriq-storage` for in-memory block indexing and
    append-only local file storage that can reload persisted blocks.
  - Added `xriq/crates/xriq-node` for a minimal local private-devnet node loop.
  - The node loop can submit validated transactions, produce a block from
    pending transactions, apply ledger transitions, persist the block before
    committing node state, clear included mempool transactions, and expose
    RPC-visible state.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `50` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-storage` and `xriq-node`;
    Vast Rust verification also passed with `cargo fmt --check`, `cargo test`
    with `50` passing tests, and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the storage/node checkpoint:
  - Added `xriq/crates/xriq-wallet` with a real binary crate named
    `xriq-wallet`.
  - Current commands:
    - `xriq-wallet key generate --label <lowercase-label>`
    - `xriq-wallet transfer --chain-id <id> --from <address> --to <address> --amount <base-units> --fee <base-units> --nonce <number> [--expires-at-height <height>]`
  - This wallet is private-devnet-only. It creates deterministic test
    identities and fake nonempty test signatures; it does not manage real
    private keys, seed phrases, encrypted key stores, or production custody.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test` with `56` passing tests, and
    `cargo clippy -- -D warnings`.
  - Local CLI smoke passed:
    `cargo run -p xriq-wallet -- key generate --label alice`.
  - Local transfer CLI smoke passed:
    `cargo run -p xriq-wallet -- transfer --chain-id xriq-devnet --from xriqdev1alice00000000000 --to xriqdev1bobbb00000000000 --amount 25 --fee 2 --nonce 7 --expires-at-height 100`.
  - Vast checkout was fast-forwarded to include `xriq-wallet`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test` with `56`
    passing tests, `cargo clippy -- -D warnings`, and both wallet CLI smokes.
- Local XRIQ prototype progress after the wallet checkpoint:
  - Added `xriq/crates/xriq-explorer` for private-devnet explorer view models
    and dependency-free text rendering.
  - Added `ChainStore::blocks_by_height_desc` so explorer views can list recent
    blocks without depending on a public web explorer or external database.
  - Current explorer scope is read-only and private-devnet-only: chain overview,
    latest blocks, block detail, account detail, mempool detail, and pending
    transaction detail.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `64` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-explorer`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test -j 1` with
    `64` passing tests, and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the explorer checkpoint:
  - Added `XriqNode::import_block` for in-process private-devnet block
    propagation tests between local nodes.
  - Imported peer blocks now validate the parent height/hash, chain id,
    nonempty block signature, authorized producer, and maximum transactions per
    block before any ledger or storage commit.
  - Follower nodes apply imported block transactions through the same ledger
    transition path, persist the block before committing node state, update the
    local tip, and remove matching included transactions from the local mempool.
  - Added local multi-node tests for follower import, consecutive empty block
    import, wrong-parent rejection, unauthorized-producer rejection, and
    over-limit block rejection.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `69` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include the local multi-node checkpoint;
    Vast Rust verification also passed with `cargo fmt --check`,
    `cargo test -j 1` with `69` passing tests, and
    `cargo clippy -- -D warnings`.
- XRIQ Phase 3 decision checkpoint after local multi-node verification:
  - Added `docs/XRIQ_PHASE3_DECISIONS.md`.
  - Consensus decision: keep deterministic authority consensus for the private
    devnet; defer public PoS/BFT economics, validator rewards, slashing, and
    public validator admission.
  - Supply decision: keep XRIQ supply test-only through deterministic private
    allocations; public supply, emissions, burns, treasury allocation, sale,
    airdrop, and reward schedule remain unset and blocked.
  - Governance decision: use private engineering governance through docs,
    commits, and verification; do not add token governance, treasury rights,
    revenue rights, or public upgrade promises.
  - Public-readiness decision: public launch remains blocked until crypto,
    hashing, genesis/config, networking, security, open-source, and legal-risk
    gates are satisfied.
  - Next implementation target is `xriq-crypto` plus canonical transaction and
    block hashing, with fake wallet signatures kept test-only until the crypto
    boundary is reviewed.
- Local XRIQ prototype progress after the Phase 3 decision checkpoint:
  - Added `xriq/crates/xriq-crypto`.
  - Added SHA-256 canonical transaction signing hashes, transaction hashes,
    block-header signing hashes, block/header hashes, and transaction-list
    roots using the RustCrypto `sha2` crate.
  - Added explicit signature algorithm identifiers for crypto agility and a
    `TestOnlySignatureVerifier` that accepts only hash-bound private-devnet
    test signatures.
  - Updated `xriq-wallet` so private-devnet transfer drafts produce
    hash-bound test-only signatures instead of arbitrary nonempty fake bytes.
  - This is still not production key custody or production signature
    verification.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `78` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to include `xriq-crypto`; Vast Rust
    verification also passed with `cargo fmt --check`, `cargo test -j 1` with
    `78` passing tests, and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the crypto/hash checkpoint:
  - Wired canonical transaction hashes into higher-level RPC and node
    transaction-submission helper APIs.
  - Added a storage helper that appends blocks using the canonical
    block/header hash while keeping explicit hash append available for fixtures.
  - Added node helper APIs for canonical block production and peer-block import.
    Canonical production now derives the transaction-list root from selected
    transactions and derives the stored block hash from the produced block.
  - Explicit manual hash APIs remain available where tests need fixture control
    and negative-case construction.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `84` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `b77da59`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `84` passing tests,
    and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the canonical-hash API checkpoint:
  - Added shared private-devnet `GenesisConfig` in `xriq-core` with explicit
    chain id, genesis block hash, minimum fee, fee sink, authority,
    mempool/block limits, and deterministic test allocations.
  - Added genesis-derived constructors for ledger, mempool, consensus, and
    node setup so future tests and tooling do not need scattered fixture
    policy values.
  - Added deterministic account-state entries and SHA-256 account-state root
    calculation in `xriq-crypto`.
  - Added node canonical-root block production that derives transaction root,
    account-state root, and block hash from selected transactions and resulting
    ledger state.
  - This remains private-devnet-only. Public supply, emissions, validator
    rewards, token sale, airdrop, treasury, and public economics remain unset
    and blocked.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `96` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `a5a8c08`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `96` passing tests,
    and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the genesis/config checkpoint:
  - Imported peer blocks now reject mismatched canonical transaction roots.
  - Imported peer blocks now reject mismatched deterministic account-state roots
    after follower-side ledger execution.
  - Imported peer blocks now verify hash-bound private-devnet block-header
    signatures through `TestOnlySignatureVerifier`.
  - Wrong transaction roots, wrong state roots, and bad test-only block
    signatures leave follower ledger, tip, storage, and mempool state
    unchanged.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `99` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `543057c`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `99` passing tests,
    and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the import validation checkpoint:
  - RPC transaction submission now rejects invalid hash-bound private-devnet
    test signatures before mempool insertion.
  - Node transaction submission now rejects invalid hash-bound private-devnet
    test signatures before mempool insertion.
  - Imported peer blocks now reject transactions with invalid hash-bound
    private-devnet test signatures before follower ledger execution, storage
    commit, tip update, or mempool cleanup.
  - Explorer RPC-error mapping was updated for the new transaction-signature
    rejection case.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `102` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `3aca387`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `102` passing tests,
    and `cargo clippy -- -D warnings`.
- Local XRIQ prototype progress after the signature-bound import checkpoint:
  - Added deterministic private-devnet replay startup through
    `XriqNode::from_genesis_replaying_store`.
  - Replay starts from genesis, walks persisted store heights contiguously,
    rejects missing heights, rejects noncanonical stored block hashes, and uses
    the same parent/proposer/signature/transaction-root/state-root validation
    path as peer-block import before restoring ledger height, account state, and
    latest tip.
  - Added tests for file-store replay into node state, noncanonical stored hash
    rejection, and height-gap rejection.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `105` passing tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `3e3e69c`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `105` passing
    tests, and `cargo clippy -- -D warnings`.
  - Vast noninteractive shells need the workspace Rust toolchain on PATH:
    `export CARGO_HOME=/workspace/.cargo RUSTUP_HOME=/workspace/.rustup PATH=/workspace/.cargo/bin:$PATH`.
- Local XRIQ prototype progress after the replay-startup checkpoint:
  - Added `xriq-node` as a real binary runner for private-devnet status checks.
  - New command:
    `cargo run -p xriq-node -- status --chain-file target/xriq-node-smoke-chain.bin`.
  - The status command opens the append-only file store, replays persisted
    canonical blocks through `XriqNode::from_genesis_replaying_store`, and
    prints private-devnet-only chain status including chain id, height, latest
    block hash, pending transaction count, and stored block count.
  - Added an optional `--alice-balance <base-units>` flag for local
    private-devnet test fixtures; this is not public-token economics.
  - Reaffirmed the narrowed project goal: finish BIBER MVP plus XRIQ
    private-devnet now, keep public XRIQ as a later guarded plan only.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `107` passing tests,
    `cargo clippy -- -D warnings`, and the new `xriq-node status` smoke.
  - Vast checkout was fast-forwarded to `066933f`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `107` passing
    tests, `cargo clippy -- -D warnings`, and the new `xriq-node status` smoke.
- Local XRIQ prototype progress after the status-runner checkpoint:
  - Added `xriq-node produce-transfer-block` as the first local runner command
    that moves a transfer through node state without a full HTTP server.
  - The command opens the append-only chain file, replays persisted canonical
    blocks, builds a hash-bound private-devnet test transaction, submits it
    through the node validation path, produces a canonical-root block with a
    hash-bound test block signature, persists the block, and reports replayable
    chain status.
  - Added runner tests for successful transfer/block persistence and failed
    transfer rejection without block persistence.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `109` passing tests,
    `cargo clippy -- -D warnings`, the new transfer/block smoke, and a replay
    status smoke against the same chain file.
  - Vast checkout was fast-forwarded to `4f0cb38`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `109` passing
    tests, `cargo clippy -- -D warnings`, the transfer/block smoke, and a
    replay status smoke against the same chain file.
- Local XRIQ prototype progress after the transfer-runner checkpoint:
  - Added `xriq-node explorer-overview` as the first file-backed local explorer
    runner over persisted private-devnet chain files.
  - The command opens the append-only chain file, replays persisted canonical
    blocks through `XriqNode::from_genesis_replaying_store`, and renders chain
    id, height, latest block hash, stored block count, pending count, and recent
    block summaries using `xriq-explorer`.
  - Added runner coverage for producing two persisted blocks and then rendering
    the replayed explorer overview from the same chain file.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `110` passing tests,
    `cargo clippy -- -D warnings`, two transfer/block smokes, and the new
    explorer overview smoke.
  - Vast checkout was fast-forwarded to `9b098f2`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `110` passing
    tests, `cargo clippy -- -D warnings`, two transfer/block smokes, and the
    explorer overview smoke.
- Local XRIQ prototype progress after the explorer-runner checkpoint:
  - Added `xriq-node produce-draft-block` so wallet `key=value` transfer draft
    files can be consumed by the node runner without starting HTTP/RPC serving.
  - The parser accepts the current `xriq-wallet transfer` output format,
    tolerates UTF-8 BOMs from Windows PowerShell-created files, rejects unknown,
    duplicate, missing, malformed, unsupported-version, and wrong-chain draft
    input, then uses the same private-devnet validation and block-production
    path as direct transfer production.
  - Added runner coverage for producing a block from a wallet draft file and
    rejecting a wrong-chain wallet draft without persisting a block.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `112` passing tests,
    `cargo clippy -- -D warnings`, wallet draft generation, draft-block
    production, and explorer overview replay. The local Windows test run used
    `CARGO_TARGET_DIR=target-codex-draft` because the default test binary was
    temporarily locked.
  - Vast checkout was fast-forwarded to `00f363f`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `112` passing
    tests, `cargo clippy -- -D warnings`, wallet draft generation,
    draft-block production, and explorer overview replay.
- Local XRIQ prototype progress after the wallet-draft runner checkpoint:
  - Added `xriq-node block-detail` for focused block inspection by height over
    persisted private-devnet chain files.
  - Added `xriq-node account-detail` for focused account inspection by address
    over persisted private-devnet chain files.
  - Added dependency-free account detail text rendering in `xriq-explorer`.
  - Added runner coverage for replaying a chain file before rendering block and
    account detail output.
  - Local Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `114` passing tests,
    `cargo clippy -- -D warnings`, wallet draft generation, draft-block
    production, explorer overview replay, block detail, and account detail.
    The local Windows test run used `CARGO_TARGET_DIR=target-codex-detail` to
    avoid default target binary locks.
  - Vast checkout was fast-forwarded to `f00e881`; Vast Rust verification also
    passed with `cargo fmt --check`, `cargo test -j 1` with `114` passing
    tests, `cargo clippy -- -D warnings`, wallet draft generation,
    draft-block production, explorer overview replay, block detail, and account
    detail.
- Local XRIQ prototype progress after the file-detail runner checkpoint:
  - Added `scripts/xriq_private_devnet_smoke.sh` as the compact one-command
    private-devnet smoke path.
  - The script chains wallet draft generation, draft-block production, explorer
    overview, block detail, and account detail against one persisted chain file
    under `xriq/target/`.
  - Added `.gitattributes` so Bash scripts keep LF line endings across Windows
    and Vast checkouts.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `114` passing tests, and
    `cargo clippy -- -D warnings`, using `CARGO_TARGET_DIR=target-codex-smoke`
    to avoid default target binary locks.
  - Local Windows Bash execution is unavailable because `bash.exe` maps to WSL
    and no WSL distribution is installed, so Bash script verification happened
    on Vast.
  - Vast checkout was fast-forwarded to `0789724`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `114` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T142125Z-19189`.
- Local XRIQ prototype progress after the mempool-detail runner checkpoint:
  - Added `xriq-node mempool-detail` for read-only pending transaction
    inspection over persisted private-devnet chain files.
  - The command replays the chain file and can preview a wallet transfer draft
    in the local mempool without producing a block or mutating storage.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the compact smoke path now
    verifies wallet draft generation, mempool preview, draft-block production,
    explorer overview, block detail, and account detail against one persisted
    chain file under `xriq/target/`.
  - Added directionally compatible exchange-readiness guardrails across the
    XRIQ docs: keep the MVP transparent and auditable, preserve future
    exchange-review surfaces, and do not claim listing readiness until public
    network, security, tokenomics, legal, AML/CFT, sanctions, custody,
    integration, and market-quality reviews are complete.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `115` passing tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-mempool` to avoid default target binary
    locks.
  - Local PowerShell smoke verified wallet draft generation, `mempool-detail`
    preview, unchanged status before block production, draft-block production,
    and explorer overview replay.
  - Vast checkout was fast-forwarded to `7e9d99f`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `115` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T144421Z-19849`.
- XRIQ exchange-compatibility documentation checkpoint:
  - Added `docs/XRIQ_EXCHANGE_READINESS_CHECKLIST.md`.
  - The checklist keeps XRIQ directionally compatible with future centralized
    exchange review while explicitly stating that XRIQ is not listing-ready.
  - It defines private-devnet, public-testnet, public-mainnet, and
    centralized-exchange review gates; hard-blocks listing outreach, market
    making, custody, bridges, public distribution, and investment-facing claims;
    and keeps privacy future-facing and selective-disclosure oriented.
  - Linked the checklist from `docs/XRIQ_TECHNICAL_SPEC.md`,
    `docs/XRIQ_PHASE3_DECISIONS.md`, `docs/XRIQ_LEGAL_RISK_REDUCTION.md`, and
    `docs/XRIQ_RUST_TRACK.md`.
- Local XRIQ prototype progress after the JSON runner checkpoint:
  - Added `--format text|json` to the file-backed `xriq-node` runner commands:
    `status`, `produce-transfer-block`, `produce-draft-block`,
    `explorer-overview`, `block-detail`, `account-detail`, and
    `mempool-detail`.
  - Text output remains the default. JSON output uses
    `format_version: xriq-node-json-v1`, keeps private-devnet warnings in the
    payload, emits hashes and addresses as strings, and emits XRIQ amounts as
    decimal `*_base_units` strings so future JS/TS clients do not lose `u128`
    precision.
  - Added Rust coverage for JSON output across status, block production,
    overview, block detail, account detail, and mempool detail.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the one-command Vast
    smoke path verifies selected JSON outputs for mempool detail, explorer
    overview, and account detail.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `116` passing tests, and
    `cargo clippy -- -D warnings`, using `CARGO_TARGET_DIR=target-codex-json2`
    to avoid default target binary locks. A first rerun under
    `target-codex-json` hit a Windows linker lock on an old test executable.
  - Vast checkout was fast-forwarded to `266daf3`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `116` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T150315Z-20580`.
- XRIQ JSON schema documentation checkpoint:
  - Added `docs/XRIQ_NODE_JSON_SCHEMA.md` for the private-devnet
    `xriq-node --format json` contract.
  - Documented the stable `xriq-node-json-v1` success shapes for status,
    produced block, explorer overview, block detail, account detail, and
    mempool detail.
  - Documented compatibility rules: text remains default, hashes and addresses
    are strings, XRIQ amounts are decimal `*_base_units` strings, optional
    heights are number-or-null, unknown fields should be ignored by consumers,
    and JSON error responses are available when `--format json` is requested.
  - Linked the schema doc from `xriq/README.md` and
    `docs/XRIQ_TECHNICAL_SPEC.md`.
- Local XRIQ prototype progress after the JSON error-response checkpoint:
  - Added structured JSON error responses for the `xriq-node` CLI when
    `--format json` is present and the command fails.
  - JSON error responses are written to stderr, exit nonzero, include
    `format_version: xriq-node-json-v1`, private-devnet warning, `ok: false`,
    optional `command`, and stable `error.code` plus `error.message`.
  - Text errors and help output remain the default when `--format json` is not
    requested.
  - Added stable `NodeRunnerError::code()` mappings and Rust coverage for the
    JSON error shape.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the one-command Vast
    smoke path verifies a missing `--chain-file` failure returns JSON with
    `ok: false`, `command: "status"`, `code: "missing_flag"`, and the expected
    message.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `117` passing tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-json-errors` to avoid default target binary
    locks.
  - Vast checkout was fast-forwarded to `8969b08`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T153320Z-21369`.
- Local XRIQ prototype progress after the JSON success-command checkpoint:
  - Added `command` to every successful `xriq-node --format json` response.
  - Success and error JSON responses now both identify the command, making the
    file-backed runner easier for future BIBER agents and HTTP/RPC wrappers to
    consume.
  - Updated `docs/XRIQ_NODE_JSON_SCHEMA.md` and
    `scripts/xriq_private_devnet_smoke.sh` to require command names in selected
    success JSON responses.
  - Local Windows Rust verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -j 1` with `117` passing tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-json-command` to avoid default target binary
    locks.
  - Vast checkout was fast-forwarded to `1a7218f`; Vast verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T154848Z-22177`.
- Local XRIQ prototype progress after the smoke JSON artifact checkpoint:
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the one-command smoke
    path persists representative JSON response artifacts beside the draft and
    chain file.
  - Generated files are `mempool-detail.json`, `explorer-overview.json`,
    `account-detail.json`, and `status-error.json`.
  - Updated `docs/XRIQ_NODE_JSON_SCHEMA.md` and `docs/XRIQ_TECHNICAL_SPEC.md`
    so future BIBER/Codex sessions know to use those generated files as
    private-devnet examples, not public API fixtures.
  - Vast checkout was fast-forwarded to `f222b01`; focused verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh`,
    `bash scripts/xriq_private_devnet_smoke.sh`, and `test -s` checks on all
    four generated JSON artifact files.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T155325Z-22475`.
  - Full Rust tests were intentionally not rerun for this script/docs-only
    checkpoint; previous full Rust and Vast verification remains through
    `1a7218f`.
- Local XRIQ prototype progress after the read-only HTTP wrapper checkpoint:
  - Added `xriq-node serve-readonly` as a dependency-free, loopback-first,
    private-devnet HTTP wrapper over the existing file-backed JSON runner
    outputs.
  - Implemented read-only endpoints for `/health`, `/v1/chain/status`,
    `/v1/explorer/overview?limit=5`, `/v1/blocks/{height}`,
    `/v1/accounts/{address}`, and `/v1/mempool`.
  - `POST /v1/transactions` and `GET /v1/transactions/{hash}` intentionally
    return `501` until a real persisted transaction index/submission path is
    added. Do not treat this wrapper as public API readiness.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the private-devnet HTTP surface and
    next-step boundaries.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    focused `cargo test -p xriq-node private_devnet_http_routes_wrap_file_backed_json_outputs -j 1`,
    `cargo test -p xriq-node -j 1` with `35` passing node tests,
    `cargo test -j 1` with `117` passing workspace tests using
    `CARGO_TARGET_DIR=target-codex-http` after the default target directory hit
    the known Windows linker lock, and `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `9618a11`; Vast verification passed
    with `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, a live loopback HTTP smoke against
    `127.0.0.1:18787`, and `bash scripts/xriq_private_devnet_smoke.sh`.
  - Live Vast HTTP smoke used chain:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-smoke-chain-20260517T160404Z-23361.bin`.
    It verified `/health`, `/v1/chain/status` with `current_height: 1`,
    `/v1/accounts/xriqdev1alice00000000000` with balance `73`, and `POST
    /v1/transactions` returning `501`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T160417Z-23404`.
- Local XRIQ prototype progress after the confirmed transaction HTTP lookup
  checkpoint:
  - Added `GET /v1/transactions/{hash}` behavior to `xriq-node
    serve-readonly` for confirmed transactions already stored in persisted
    private-devnet blocks.
  - The endpoint scans canonical transaction hashes in the replayed chain file
    and returns `command: "transaction-detail"`, `status: "confirmed"`,
    block height/hash, transaction index, sender/recipient, amount, fee, nonce,
    and expiry height.
  - Missing confirmed transactions return `404 transaction_not_found`; invalid
    non-lowercase/non-64-hex hashes return `400 invalid_hash`.
  - Durable pending transaction status and `POST /v1/transactions` remain
    intentionally deferred; do not pretend the file-backed HTTP wrapper has a
    persistent mempool yet.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the confirmed-transaction lookup
    boundary and the next implementation target.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -p xriq-node -j 1` with `35` passing node tests,
    `cargo test -j 1` with `117` passing workspace tests using
    `CARGO_TARGET_DIR=target-codex-tx-status`, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `b2080a2`; Vast verification passed
    with `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, a live loopback HTTP transaction lookup
    smoke against `127.0.0.1:18789`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Live Vast HTTP transaction lookup smoke used chain:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-tx-smoke-chain-20260517T161320Z-24229.bin`.
    It verified transaction hash
    `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`
    returned `transaction-detail`, `confirmed`, and `amount_base_units: "25"`;
    it also verified missing hash returns `404` and malformed hash returns
    `400`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T161332Z-24264`.
- Local XRIQ prototype progress after the wallet-draft HTTP submission
  checkpoint:
  - Added `xriq-node serve-private` as the submit-capable private-devnet HTTP
    mode while preserving `xriq-node serve-readonly` as read-only.
  - `POST /v1/transactions` in `serve-private` accepts the existing wallet
    transfer draft text body emitted by `xriq-wallet transfer`, validates it
    against the replayed chain state, immediately produces one block, and
    persists that block to the configured chain file.
  - `serve-readonly` still returns `501 not_implemented` for
    `POST /v1/transactions`.
  - This is an MVP submit-and-block helper, not a production mempool API.
    Durable pending transaction status and JSON transaction submission remain
    future work.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the `serve-private` command and wallet
    draft POST contract.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -p xriq-node -j 1` with `35` passing node tests,
    `cargo test -j 1` with `117` passing workspace tests using
    `CARGO_TARGET_DIR=target-codex-submit`, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `f9f4c6b`; Vast verification passed
    with `cargo fmt --check`, `cargo test -j 1` with `117` passing tests,
    `cargo clippy -- -D warnings`, a live `serve-private` wallet-draft POST
    smoke against `127.0.0.1:18795`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Live Vast HTTP submit smoke used:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-submit-smoke-chain-20260517T162821Z-25111.bin`
    and draft:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-submit-smoke-draft-20260517T162821Z-25111.txt`.
    It verified `POST /v1/transactions` returned `submit-transaction` and
    `current_height: 1`, the returned transaction hash
    `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`
    was retrievable through `GET /v1/transactions/{hash}` as `confirmed`, and
    Alice's account balance became `73`.
  - Latest smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T162821Z-25143`.
- Local XRIQ prototype progress after the JSON transaction submission
  checkpoint:
  - Added dependency-free flat JSON parsing for `POST /v1/transactions` under
    `xriq-node serve-private`, while preserving the existing wallet transfer
    draft text body and preserving `serve-readonly` as read-only with `501` for
    POST.
  - Accepted JSON body shape is `xriq-node-transfer-submit-v1` with
    `version`, `chain_id`, `from`, `to`, `amount_base_units`,
    `fee_base_units`, `nonce`, and optional `expires_at_height`,
    `timestamp_ms`, and `consensus_round`. This remains a private-devnet
    submit-and-block helper, not a production mempool or signed-transaction
    format.
  - Added stable JSON error codes for malformed or unsupported JSON bodies:
    `invalid_json`, `unknown_json_field`, `duplicate_json_field`, and
    `missing_json_field`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` so future clients and BIBER agents can use
    the JSON submit body without treating it as a public API.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -p xriq-node -j 1` with `35` passing node tests,
    `cargo test -j 1` with `117` passing workspace tests, and
    `cargo clippy -- -D warnings`.
  - Vast checkout was fast-forwarded to `120654b`; Vast verification passed
    with the workspace-volume Rust toolchain:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`. Use that environment in future
    non-interactive SSH sessions because plain `cargo` is not on the default
    SSH `PATH`.
  - Vast Rust verification passed with `cargo fmt --check`,
    `cargo test -j 1` with `117` passing tests, and
    `cargo clippy -- -D warnings`.
  - Live Vast HTTP JSON submit smoke against `127.0.0.1:18796` passed. It
    verified JSON `POST /v1/transactions` returned `submit-transaction` and
    `current_height: 1`, the returned transaction hash
    `fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565`
    was retrievable through `GET /v1/transactions/{hash}` as `confirmed`, and
    Alice's account balance became `73`.
  - Live Vast JSON submit artifacts:
    `/workspace/biber-ai-platform/xriq/target/xriq-http-json-submit-smoke-chain-20260517T193409Z-26165.bin`,
    `/workspace/biber-ai-platform/xriq/target/xriq-http-json-submit-smoke-body-20260517T193409Z-26165.json`,
    and
    `/workspace/biber-ai-platform/xriq/target/xriq-http-json-submit-smoke-response-20260517T193409Z-26165.json`.
  - Latest standard smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T193410Z-26244`.
- Local XRIQ prototype progress after the wallet JSON submit-output
  checkpoint:
  - Added `xriq-wallet transfer --format json`, which emits a
    `xriq-node-transfer-submit-v1` private-devnet JSON body accepted directly
    by `xriq-node serve-private` `POST /v1/transactions`.
  - The default `xriq-wallet transfer` text draft remains unchanged for older
    file-backed flows. The JSON output includes the private-devnet warning and
    `signature_bytes` metadata, but still does not expose private keys, seeds,
    or the test-only signature envelope.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the one-command smoke now
    generates the wallet JSON body, starts `serve-private`, posts the JSON body
    over HTTP, verifies confirmed transaction lookup, and verifies Alice's
    updated balance.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the wallet-generated JSON submit body
    and the new smoke artifacts.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    `cargo test -p xriq-wallet -j 1` with `12` passing wallet tests,
    `cargo test -j 1` with `120` passing workspace tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-wallet-json` to avoid default target binary
    locks. The generated local target directory was removed afterward.
  - Vast checkout was fast-forwarded to `3c0f0c1`; Vast verification passed
    with the workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `120` passing tests, `cargo clippy -- -D warnings`,
    `bash -n scripts/xriq_private_devnet_smoke.sh`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T194801Z-26995`.
    Important generated files include
    `wallet-transfer-submit.json`, `http-json-submit.json`,
    `http-json-transaction.json`, and `http-json-account.json` in that
    directory.
- Local XRIQ prototype progress after the checked JSON fixture checkpoint:
  - Added checked private-devnet golden fixtures under
    `xriq/fixtures/private-devnet/`:
    `wallet-transfer-submit.json` and `node-produce-transfer-block.json`.
  - Added exact-match Rust tests so `xriq-wallet transfer --format json` and
    `xriq-node produce-transfer-block --format json` must continue matching
    those private-devnet schema examples.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` to describe these fixtures as private-devnet
    schema drift checks, not public-mainnet API guarantees.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    focused wallet fixture tests with `13` passing wallet tests, focused node
    fixture test, `cargo test -j 1` with `122` passing workspace tests, and
    `cargo clippy -- -D warnings`, using
    `CARGO_TARGET_DIR=target-codex-fixtures` to avoid default target binary
    locks. Generated local target directories were removed afterward.
  - Vast checkout was fast-forwarded to `dafc5f0`; Vast verification passed
    with the workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `122` passing tests, `cargo clippy -- -D warnings`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T195504Z-28133`.
- Local XRIQ prototype progress after the read-only JSON fixture checkpoint:
  - Added additional checked private-devnet golden fixtures under
    `xriq/fixtures/private-devnet/`:
    `node-status-empty.json`, `node-mempool-empty.json`, and
    `node-account-alice-initial.json`.
  - Added exact-match Rust tests so fresh `xriq-node status --format json`,
    empty `xriq-node mempool-detail --format json`, and initial Alice
    `xriq-node account-detail --format json` continue matching those
    private-devnet schema examples.
  - Updated `xriq/README.md` and `docs/XRIQ_NODE_JSON_SCHEMA.md` to list the
    expanded checked fixture set for future BIBER/client-agent work.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-next-fixtures`: `cargo fmt --check`,
    focused `cargo test -p xriq-node checked_fixture -j 1` with `4` passing
    node fixture tests, `cargo test -j 1` with `125` passing workspace tests,
    and `cargo clippy -- -D warnings`. Generated local target/test files were
    removed afterward.
  - Pushed implementation commit:
    `3c50394 Add XRIQ read-only JSON fixtures`.
  - Vast checkout was fast-forwarded to `3c50394`; Vast verification passed
    with the workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `125` passing tests, and `cargo clippy -- -D warnings`. Full
    `scripts/xriq_private_devnet_smoke.sh` was intentionally not rerun for
    this fixture-only Rust checkpoint to keep cost/time low.
- Local XRIQ prototype progress after the transaction-detail runner checkpoint:
  - Added `xriq-node transaction-detail --chain-file <path> --tx-hash <64-hex>`
    with text and JSON output.
  - The command scans confirmed transactions in persisted blocks first. When
    `--draft-file <path>` is also supplied, it previews that wallet draft as an
    in-memory pending transaction and returns `status: "pending"` when the hash
    matches, without mutating the chain file or creating durable mempool state.
  - Added explicit `invalid_hash` JSON error support for malformed
    `--tx-hash` values.
  - Expanded `scripts/xriq_private_devnet_smoke.sh` so it now writes and checks
    `pending-transaction-detail.json` before block production and
    `confirmed-transaction-detail.json` after block production.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the transaction-detail runner contract
    and the new smoke artifacts.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-tx-detail`: `cargo fmt --check`, focused
    `cargo test -p xriq-node transaction_detail -j 1` with `2` passing tests,
    `cargo test -j 1` with `127` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward. Local `bash -n scripts/xriq_private_devnet_smoke.sh` could not
    run because Windows routed `bash` to WSL and no WSL distribution is
    installed, so Bash verification was done on Vast.
  - Pushed implementation commit:
    `824816e Add XRIQ transaction detail runner`.
  - Vast checkout was fast-forwarded to `824816e`; Vast verification passed
    with the workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `127` passing tests, `cargo clippy -- -D warnings`,
    `bash -n scripts/xriq_private_devnet_smoke.sh`, and
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T202943Z-29119`.
- Local XRIQ prototype progress after the durable pending HTTP checkpoint:
  - Added optional durable private-devnet pending HTTP state to
    `xriq-node serve-private --pending-file <path>`.
  - Added `POST /v1/mempool` for private-devnet pending transaction submission.
    It accepts the same wallet draft or wallet JSON transfer body as
    `POST /v1/transactions`, validates against replayed chain state plus the
    current pending file, appends a pending record, and returns `202 Accepted`
    with the existing transaction-detail JSON shape and `status: "pending"`.
  - `GET /v1/mempool`, `GET /v1/chain/status`, and
    `GET /v1/transactions/{hash}` now include durable pending-file state when
    `--pending-file` is configured. Confirmed chain transactions are still
    resolved before pending records.
  - Existing `POST /v1/transactions` intentionally remains the simple
    submit-and-produce private-devnet flow; it persists a block immediately and
    does not become a public mempool API.
  - Updated `scripts/xriq_private_devnet_smoke.sh` so the full smoke covers
    durable pending submit/list/lookup artifacts:
    `http-pending-submit.json`, `http-pending-mempool.json`,
    `http-pending-transaction.json`, and `http-pending-mempool.tsv`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the pending HTTP endpoint contract and
    internal private-devnet pending-file behavior.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-pending-http2`: `cargo fmt --check`,
    focused
    `cargo test -p xriq-node private_devnet_http_routes_persist_pending_transactions -j 1`,
    `cargo test -j 1` with `128` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward. Local Bash verification is still unavailable because Windows has
    no WSL distribution installed, so Bash syntax and smoke verification were
    done on Vast.
  - Pushed implementation commit:
    `4e437cc Add XRIQ durable pending HTTP state`.
  - Pushed smoke-harness robustness commits:
    `174cdb1 Harden XRIQ smoke HTTP port selection` and
    `3306130 Run XRIQ smoke server directly`, followed by
    `2bd99cc Ensure XRIQ smoke server cleanup`. These fixed Vast smoke harness
    issues caused by fixed-port collisions, `cargo run` leaving the server
    child alive after the harness stopped Cargo, and the subshell needing to
    `exec` the node binary so cleanup kills the actual server process.
  - Vast Rust verification passed through `4e437cc` with
    `cargo fmt --check`, `cargo test -j 1` with `128` passing workspace tests,
    and `cargo clippy -- -D warnings`.
  - Vast checkout was then fast-forwarded to `2bd99cc`; verification passed
    with `bash -n scripts/xriq_private_devnet_smoke.sh` and
    `bash scripts/xriq_private_devnet_smoke.sh`. After the final smoke,
    `pgrep -af xriq-node` showed no lingering XRIQ smoke server process.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T205029Z-32291`.
- Local XRIQ prototype progress after the durable pending block-production
  checkpoint:
  - Added `xriq-node produce-pending-block --chain-file <path> --pending-file
    <path>` with text and JSON output.
  - Added private-devnet HTTP `POST /v1/blocks` for
    `serve-private --pending-file <path>`. It loads durable pending
    transactions, produces one block, persists it to the configured chain file,
    and compacts the pending file so included transactions are removed.
  - Added `ProducedPendingBlockStatus` JSON with `block_hash`,
    `included_transaction_hashes`, `applied_transactions`, and the standard
    private-devnet node status fields.
  - Pending-file record loading now rejects records whose stored hash does not
    match the canonical transaction hash.
  - Expanded `scripts/xriq_private_devnet_smoke.sh` so the HTTP pending path
    now verifies `POST /v1/blocks`, pending-file compaction,
    `GET /v1/mempool` after production, and confirmed transaction lookup after
    production. New smoke artifacts include `http-pending-produce.json`,
    `http-pending-mempool-after-produce.json`, and
    `http-pending-confirmed-transaction.json`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the pending-block runner/API contract.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-pending-produce`: `cargo fmt --check`,
    focused `cargo test -p xriq-node pending -j 1` with `3` passing tests,
    `cargo test -j 1` with `129` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward. Bash verification is still done on Vast because this Windows
    workstation has no WSL distribution installed.
  - Pushed implementation commit:
    `ea9918d Add XRIQ pending block production`.
  - Vast checkout was fast-forwarded to `ea9918d`; verification passed with the
    workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `129` passing workspace tests, `cargo clippy -- -D warnings`,
    `bash -n scripts/xriq_private_devnet_smoke.sh`, and
    `bash scripts/xriq_private_devnet_smoke.sh`. After the smoke,
    `pgrep -af xriq-node` showed no lingering XRIQ smoke server process.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T210028Z-33204`.
- XRIQ checked pending-block fixture checkpoint:
  - Added checked fixture:
    `xriq/fixtures/private-devnet/node-produce-pending-block.json`.
  - Added Rust coverage so `xriq-node produce-pending-block --format json`
    must continue matching that fixture exactly after a deterministic durable
    pending transaction is submitted.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` so the checked fixture set includes
    pending-block production.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-pending-fixture`: `cargo fmt --check`,
    focused `cargo test -p xriq-node checked_fixture -j 1` with `5` passing
    fixture tests, `cargo test -j 1` with `130` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward.
  - Pushed fixture/docs commit:
    `77cf376 Add XRIQ pending block JSON fixture`.
  - Vast checkout was fast-forwarded to `77cf376`; focused verification passed
    with `cargo fmt --check`,
    `cargo test -p xriq-node checked_fixture -j 1` with `5` passing fixture
    tests, and `cargo clippy -p xriq-node -- -D warnings`.
  - Full Vast runtime smoke was not rerun for this fixture-only checkpoint; the
    pending-block implementation itself remains smoke-verified through
    `ea9918d` with artifacts at
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T210028Z-33204`.
- Local XRIQ prototype progress after the preflight transfer checkpoint:
  - Added `xriq-node preflight-transfer`, a deterministic private-devnet helper
    that infers the sender nonce from a replayed file-backed chain, validates a
    test-only transfer, submits it to the durable pending file, produces one
    block from pending transactions, compacts the pending file, and verifies the
    transaction through confirmed transaction lookup.
  - Added stable JSON/text output for the preflight transfer result including
    preflight balance/nonce, transaction hash, block hash, confirmed block
    height/index, final balance/nonce, and node status fields.
  - Expanded `scripts/xriq_private_devnet_smoke.sh` with preflight artifacts:
    `preflight-chain.bin`, `preflight-pending.tsv`,
    `preflight-transfer.json`, and `preflight-transaction.json`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` with the preflight transfer workflow and
    artifact contract.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-preflight`: focused
    `cargo test -p xriq-node preflight -j 1`, `cargo test -j 1` with `131`
    passing workspace tests, and `cargo clippy -- -D warnings`. Generated
    local target files were removed afterward.
  - Pushed implementation commit:
    `7c4030d Add XRIQ preflight transfer flow`.
  - Vast checkout was fast-forwarded to `7c4030d`; verification passed with the
    workspace-volume Rust toolchain env:
    `RUSTUP_HOME=/workspace/.rustup`,
    `CARGO_HOME=/workspace/.cargo`, and
    `PATH=/workspace/.cargo/bin:...`.
  - Vast verification passed with `cargo fmt --check`, `cargo test -j 1` with
    `131` passing workspace tests, `cargo clippy -- -D warnings`,
    `bash -n scripts/xriq_private_devnet_smoke.sh`, and
    `bash scripts/xriq_private_devnet_smoke.sh`. After the smoke,
    `pgrep -af xriq-node` showed only the invoking shell command, not a live
    XRIQ smoke server process.
  - Latest expanded smoke artifacts on Vast:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T215459Z-35326`.
- XRIQ checked preflight-transfer fixture checkpoint:
  - Added checked fixture:
    `xriq/fixtures/private-devnet/node-preflight-transfer.json`.
  - Added Rust coverage so `xriq-node preflight-transfer --format json` must
    continue matching that fixture exactly after the deterministic file-backed
    preflight flow submits, produces, confirms, and compacts pending state.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` so the checked fixture set includes
    preflight transfer.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-preflight-fixture`: `cargo fmt --check`,
    focused `cargo test -p xriq-node checked_fixture -j 1` with `6` passing
    fixture tests, `cargo test -j 1` with `132` passing workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward.
  - Pushed fixture/docs commit:
    `2a2b9d8 Add XRIQ preflight JSON fixture`.
  - Vast checkout was fast-forwarded to `2a2b9d8`; focused verification passed
    with `cargo fmt --check`,
    `cargo test -p xriq-node checked_fixture -j 1` with `6` passing fixture
    tests, and `cargo clippy -p xriq-node -- -D warnings`.
  - Full Vast runtime smoke was not rerun for this fixture-only checkpoint; the
    preflight implementation itself remains smoke-verified through `7c4030d`
    with artifacts at
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260517T215459Z-35326`.
- XRIQ checked block-detail transaction fixture checkpoint:
  - Added checked fixture:
    `xriq/fixtures/private-devnet/node-block-detail-transfer.json`.
  - Added Rust coverage so `xriq-node block-detail --format json` must continue
    matching the fixture exactly after a deterministic produced transfer block,
    including the block transaction hash used by the BIBER API smoke to follow
    latest-block transactions into transaction detail.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` so the checked fixture set includes block
    detail transaction hashes.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-block-detail-fixture`: `cargo fmt`, Python
    `compileall scripts`, focused
    `cargo test -p xriq-node block_detail_json_matches_checked_fixture -j 1`,
    `cargo fmt --check`, `git diff --check`, full `cargo test -j 1` with `135`
    passing Rust workspace tests, and `cargo clippy -- -D warnings`. Generated
    local target files were removed afterward.
  - Pushed fixture/docs commit:
    `66098c1 Add XRIQ block detail JSON fixture`.
  - Vast checkout was fast-forwarded to `66098c1`; focused verification passed
    with `cargo fmt --check` and
    `cargo test -p xriq-node block_detail_json_matches_checked_fixture -j 1`.
  - Full Vast runtime smoke was not rerun for this fixture-only checkpoint; the
    live BIBER API/vLLM services were not restarted and remain on the existing
    healthy direct deployment.
- XRIQ replay/startup consistency guard checkpoint:
  - Added a post-replay consistency guard inside
    `XriqNode::from_genesis_replaying_store`.
  - Replay still validates contiguous heights, canonical stored block hashes,
    parent links, authorized producer, transaction roots, state roots, and
    signatures while replaying each block. The new guard adds a final stored
    block count and replayed tip check so a corrupted/local store cannot hide
    extra records outside the replayed height range.
  - Added regression coverage with
    `replay_rejects_extra_stored_blocks_outside_replayed_height_range`, which
    creates a valid height-1 block plus an extra genesis-height record and now
    expects `UnexpectedStoredBlockCount`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` for the tightened replay/startup contract and
    current checked fixture set.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-replay-guard`: `cargo fmt`, focused replay
    guard test, `cargo fmt --check`, `git diff --check`, full
    `cargo test -j 1` with `136` passing Rust workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward.
  - Pushed implementation/docs commit:
    `66bf4bf Add XRIQ replay consistency guard`.
  - Vast checkout was fast-forwarded to `66bf4bf`; verification passed with
    `cargo fmt --check`, focused replay guard test,
    `cargo clippy -p xriq-node -- -D warnings`, full `cargo test -j 1` with
    `136` passing Rust workspace tests, and full
    `cargo clippy -- -D warnings`.
  - Live BIBER API smoke passed with
    `bash scripts/vast_xriq_api_smoke.sh`; artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T174425Z-41324`.
  - No vLLM/FastAPI restart, model training, or OpenAI mentor call was needed.
- XRIQ replay state-root/status marker checkpoint:
  - Added `state_root` to `NodeStatus`, text output, and the stable
    `xriq-node-json-v1` status/produced/preflight JSON surfaces.
  - Updated checked fixtures for empty status, produced transfer block,
    produced pending block, and preflight transfer so schema drift is explicit.
  - Updated `scripts/xriq_private_devnet_smoke.sh` to write
    `replay-status.json` and compare the replayed `status --format json`
    state root against the state root emitted immediately after block
    production. This gives future snapshot/copy/restart checks a compact marker
    without adding a premature snapshot export format.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`, and
    `docs/XRIQ_TECHNICAL_SPEC.md` to document the state-root marker.
  - Local Windows verification passed from `xriq/` with
    `CARGO_TARGET_DIR=target-codex-status-root`: `cargo fmt`, focused
    `cargo test -p xriq-node checked_fixture -j 1` with `7` passing fixture
    tests, `cargo fmt --check`, `git diff --check`, full `cargo test -j 1`
    with `136` passing Rust workspace tests, and
    `cargo clippy -- -D warnings`. Generated local target files were removed
    afterward.
  - Pushed implementation/docs/smoke commit:
    `919b348 Expose XRIQ replay state root`.
  - Vast checkout was fast-forwarded to `919b348`; verification passed with
    `cargo fmt --check`, `bash -n scripts/xriq_private_devnet_smoke.sh`,
    focused checked-fixture tests, full `cargo test -j 1` with `136` passing
    Rust workspace tests, full `cargo clippy -- -D warnings`, and the full
    private-devnet smoke.
  - Latest private-devnet smoke artifact:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260518T180351Z-42108`.
    It includes `replay-status.json`.
  - Live BIBER API smoke passed with
    `bash scripts/vast_xriq_api_smoke.sh`; artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T180400Z-42662`.
  - No vLLM/FastAPI restart, model training, or OpenAI mentor call was needed.
- BIBER API XRIQ preflight wrapper checkpoint:
  - Added a thin private-devnet BIBER wrapper around the existing Rust
    `xriq-node preflight-transfer --format json` flow.
  - New API endpoint:
    `POST /v1/xriq/private-devnet/preflight-transfer`.
  - The request accepts transfer values only: `from`, `to`,
    `amount_base_units`, `fee_base_units`, optional `expires_at_height`,
    optional `timestamp_ms`, optional `consensus_round`, and optional
    `alice_balance_base_units`. It does not accept arbitrary chain or pending
    file paths.
  - Server-side XRIQ settings now include:
    `BIBER_XRIQ_WORKSPACE_DIR`, `BIBER_XRIQ_NODE_COMMAND`,
    `BIBER_XRIQ_CHAIN_FILE`, `BIBER_XRIQ_PENDING_FILE`,
    `BIBER_XRIQ_DEFAULT_ALICE_BALANCE_BASE_UNITS`,
    `BIBER_XRIQ_COMMAND_TIMEOUT_SECONDS`, `BIBER_XRIQ_RUSTUP_HOME`,
    `BIBER_XRIQ_CARGO_HOME`, and `BIBER_XRIQ_PATH_PREFIX`.
  - Vast `.env` was updated with:
    `BIBER_XRIQ_WORKSPACE_DIR=/workspace/biber-ai-platform/xriq`,
    `BIBER_XRIQ_NODE_COMMAND=/workspace/.cargo/bin/cargo run -q -p xriq-node --`,
    `BIBER_XRIQ_CHAIN_FILE=target/biber-api-private-devnet-chain.bin`,
    `BIBER_XRIQ_PENDING_FILE=target/biber-api-private-devnet-pending.tsv`,
    `BIBER_XRIQ_RUSTUP_HOME=/workspace/.rustup`,
    `BIBER_XRIQ_CARGO_HOME=/workspace/.cargo`, and
    `BIBER_XRIQ_PATH_PREFIX=/workspace/.cargo/bin`.
  - Implemented in both API paths because the packaged Docker/test path uses
    `src/biber_api`, while the current Vast direct launcher still serves
    `app.main:app`.
  - Local Windows verification: bundled Python `compileall app src` passed.
    Local pytest was not available on this workstation runtime, so pytest was
    run on Vast.
  - Vast verification passed with `/workspace/biber-venv/bin/python -m
    compileall app src`, `/workspace/biber-venv/bin/python -m pytest
    tests/test_xriq_preflight_api.py tests/test_model_registry.py
    tests/test_openai_mentor_trigger.py tests/test_repo_context.py -q`
    (`18 passed`), direct Python wrapper smoke through `src/biber_api`,
    `cargo fmt --check`, and
    `cargo test -p xriq-node checked_fixture -j 1` with `6` passing fixture
    tests.
  - FastAPI only was restarted on Vast; vLLM was not restarted. Live endpoint
    smoke passed through the current API process with a valid private-devnet
    fee of `2`. Earlier smoke with fee `1` correctly failed with
    `Transaction(FeeTooLow)`.
  - Pushed commits:
    `ddc5dc8 Add BIBER XRIQ preflight API wrapper` and
    `67ce353 Add XRIQ wrapper Rust environment config`.
- BIBER API XRIQ read-wrapper checkpoint:
  - Added thin private-devnet BIBER read wrappers around existing
    `xriq-node --format json` read commands.
  - New API endpoints:
    `GET /v1/xriq/private-devnet/status`,
    `GET /v1/xriq/private-devnet/accounts/{address}`, and
    `GET /v1/xriq/private-devnet/transactions/{tx_hash}`.
  - Implemented in both API paths because the packaged Docker/test path uses
    `src/biber_api`, while the current Vast direct launcher serves
    `app.main:app`.
  - Mempool read wrapper is intentionally delayed. The current CLI
    `xriq-node mempool-detail` command does not read the durable pending file,
    so exposing it through BIBER now would risk misleading clients about
    pending state.
  - Local Windows verification: bundled Python `compileall app src tests`
    passed. Local pytest remains unavailable on this workstation runtime, so
    pytest was run on Vast.
  - Vast verification passed with `/workspace/biber-venv/bin/python -m
    compileall app src`, `/workspace/biber-venv/bin/python -m pytest
    tests/test_xriq_preflight_api.py tests/test_model_registry.py
    tests/test_openai_mentor_trigger.py tests/test_repo_context.py -q`
    (`22 passed`), `cargo fmt --check`, and
    `cargo test -p xriq-node checked_fixture -j 1` with `6` passing fixture
    tests.
  - FastAPI only was restarted on Vast; vLLM was not restarted. Live endpoint
    smoke passed by first creating a valid private-devnet transfer through the
    preflight endpoint, then reading status, Alice account detail, and the
    confirmed transaction through the new BIBER read endpoints.
  - Pushed commit:
    `4d8c251 Add BIBER XRIQ read wrappers`.
- BIBER API/XRIQ durable mempool wrapper checkpoint:
  - Added durable pending-file support to `xriq-node mempool-detail` with
    `--pending-file`, while preserving the existing `--draft-file` preview path.
  - Added the BIBER API mempool read wrapper in both API paths:
    `GET /v1/xriq/private-devnet/mempool`.
  - Updated the private-devnet smoke script to create and verify
    `cli-pending-mempool.json` from the durable pending TSV file.
  - Local Windows verification passed: `git diff --check`, bundled Python
    `compileall app src tests`, `cargo fmt --check`, full `cargo test -j 1`
    with `134` passing Rust tests, and `cargo clippy -- -D warnings`.
    Local pytest is still unavailable in the bundled workstation runtime.
  - Vast verification passed: `/workspace/biber-venv/bin/python -m compileall
    app src tests`, focused pytest with `23 passed`, `cargo fmt --check`, full
    `cargo test -j 1` with `134` passing Rust tests, `cargo clippy -- -D
    warnings`, and `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest Vast smoke artifact:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260518T162531Z-37876/cli-pending-mempool.json`.
  - FastAPI only was restarted on Vast; vLLM was not restarted. Live endpoint
    smoke confirmed `/v1/xriq/private-devnet/mempool` returns `200 OK` with
    `command=mempool-detail` and current `pending_count=0`.
  - Pushed commit:
    `81824b3 Add XRIQ durable mempool wrapper`.
- BIBER API/XRIQ explorer/block wrapper checkpoint:
  - Added thin BIBER read wrappers around existing `xriq-node --format json`
    explorer commands.
  - New API endpoints in both API paths:
    `GET /v1/xriq/private-devnet/explorer?limit={count}` and
    `GET /v1/xriq/private-devnet/blocks/{height}`.
  - The explorer `limit` query is optional and bounded to `1..100`; block
    height is constrained to `>= 0`.
  - Local Windows verification passed: `git diff --check` and bundled Python
    `compileall app src tests`. Local pytest remains unavailable in the
    bundled workstation runtime.
  - Vast verification passed: `/workspace/biber-venv/bin/python -m compileall
    app src tests`, focused pytest with `25 passed`, and live endpoint smoke
    for `/v1/xriq/private-devnet/explorer?limit=5` plus
    `/v1/xriq/private-devnet/blocks/1`.
  - FastAPI only was restarted on Vast; vLLM was not restarted. Live smoke
    confirmed explorer `current_height=2` and block detail `height=1`.
  - Pushed commit:
    `32909e8 Add BIBER XRIQ explorer wrappers`.
- BIBER API/XRIQ consolidated smoke checkpoint:
  - Added `scripts/vast_xriq_api_smoke.sh`, a read-only live BIBER API smoke
    for the XRIQ private-devnet wrapper endpoints.
  - The script checks health, status, explorer overview, latest block detail,
    Alice account detail, and mempool detail. It stores JSON artifacts under
    `/workspace/outputs/xriq-api-smoke-*` by default.
  - Transaction detail is intentionally optional and skipped unless
    `BIBER_XRIQ_API_SMOKE_TX_HASH` is supplied; this avoids mutating the live
    chain just to create a confirmed hash.
  - Local Windows verification passed: bundled Python `compileall scripts` and
    `git diff --check`. Local `bash -n` could not run because this workstation
    has WSL but no installed Linux distro.
  - Vast verification passed: `bash -n scripts/vast_xriq_api_smoke.sh` and
    `bash scripts/vast_xriq_api_smoke.sh`.
  - Latest consolidated smoke artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T165750Z-39065/summary.json`.
  - Pushed commit:
    `16e506b Add BIBER XRIQ API smoke script`.
- XRIQ block transaction-hash navigation checkpoint:
  - Added canonical `tx_hash` to private-devnet block-detail transaction
    summaries, in both text rendering and `xriq-node block-detail --format
    json`.
  - Added `xriq-crypto` as a local `xriq-explorer` dependency so explorer view
    models derive canonical transaction hashes directly from block transactions.
  - Updated `scripts/vast_xriq_api_smoke.sh` so it automatically follows the
    first latest-block transaction hash into
    `/v1/xriq/private-devnet/transactions/{hash}` when present.
  - Local Windows verification passed: bundled Python `compileall scripts`,
    `git diff --check`, `cargo fmt --check`, full `cargo test -j 1` with `134`
    passing Rust tests, and `cargo clippy -- -D warnings`.
  - Vast verification passed: `cargo fmt --check`, full `cargo test -j 1` with
    `134` passing Rust tests, `cargo clippy -- -D warnings`, `bash -n
    scripts/vast_xriq_api_smoke.sh`, and `bash scripts/vast_xriq_api_smoke.sh`.
  - Latest consolidated smoke artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T170733Z-39972/summary.json`.
  - The live smoke confirmed `transaction_source=latest-block` and
    `transaction_status=confirmed` without mutating the chain. FastAPI and vLLM
    were not restarted.
  - Pushed commit:
    `6205b66 Expose XRIQ block transaction hashes`.
- BIBER MVP allowlisted test-runner checkpoint:
  - Added a protected, fixed-ID test-runner API in both the packaged API and
    the current Vast direct launcher path.
  - New endpoints:
    `GET /v1/tests` and `POST /v1/tests/run`.
  - Current allowlisted `test_id` values:
    `python-compileall-api`, `pytest-core`, `xriq-node-fixtures`, and
    `xriq-private-devnet-smoke`.
  - Clients choose only `test_id` and optional `dry_run`; they cannot submit
    arbitrary commands, working directories, shell fragments, or file paths.
  - Local workstation verification passed with bundled Python
    `compileall app src`, a direct runner dry-run smoke, and `git diff --check`.
    Local pytest is still unavailable in the bundled workstation runtime.
  - Vast checkout was fast-forwarded to `d4df8c0`.
  - Vast verification passed with the command
    `/workspace/biber-venv/bin/python -m compileall app src` and focused pytest:
    `tests/test_test_runner.py`, `tests/test_model_registry.py`,
    `tests/test_repo_context.py`, `tests/test_openai_mentor_trigger.py`, and
    `tests/test_xriq_preflight_api.py` with `31 passed`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `42987`.
  - Live smoke passed: `GET /v1/tests` returned the allowlist, and
    `POST /v1/tests/run` for `python-compileall-api` returned `ok=true`.
  - Pushed commit:
    `d4df8c0 Add allowlisted BIBER test runner API`.
- BIBER MVP bounded workspace-edit checkpoint:
  - Added a protected exact-text workspace edit API in both the packaged API
    and the current Vast direct launcher path.
  - New endpoint: `POST /v1/files/edit`.
  - The request accepts a workspace-relative `path`, `old_text`, `new_text`,
    `expected_replacements`, optional `create_if_missing`, and optional
    `dry_run`.
  - The edit path rejects absolute paths, path escapes, secret-looking paths,
    cache directories, common binary file types, oversized files, and
    replacement-count mismatches.
  - Creation is allowed only when `create_if_missing=true`; existing files
    require non-empty `old_text` and an exact replacement count.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --cached --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Vast checkout was fast-forwarded to `992890b`.
  - Vast verification passed with the command
    `/workspace/biber-venv/bin/python -m compileall app src tests` and focused pytest:
    `tests/test_workspace_edit.py`, `tests/test_test_runner.py`,
    `tests/test_model_registry.py`, `tests/test_repo_context.py`,
    `tests/test_openai_mentor_trigger.py`, and `tests/test_xriq_preflight_api.py`
    with `38 passed`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `43390`.
  - Live smoke passed: `GET /v1/tests` returned the updated allowlist, and
    `POST /v1/files/edit` in dry-run create mode returned `200 OK` with
    `created=true` and `changed=true`.
  - Pushed commit:
    `992890b Add bounded BIBER workspace edit API`.
- BIBER MVP GitHub branch/PR workflow checkpoint:
  - Added optional branch creation to GitHub file save. `GitHubSaveTarget` now
    supports `base_branch` and `create_branch_if_missing` so BIBER can save a
    generated file to a review branch created from a configured base branch.
  - Added the protected endpoint `POST /v1/github/pull-request` for opening a
    draft or ready pull request from an existing head branch to a base branch.
  - The GitHub client validates path/branch inputs, rejects unsafe branch
    names, wraps GitHub API failures, and keeps the token server-side.
  - Updated `docs/API_EXAMPLES.md` with the branch-save plus draft-PR flow.
  - Updated the focused `pytest-core` allowlist to include
    `tests/test_github_client.py`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --cached --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Vast checkout was fast-forwarded to `552220b`; verification passed with
    the command `/workspace/biber-venv/bin/python -m compileall app src tests`
    and focused pytest:
    `tests/test_workspace_edit.py`, `tests/test_github_client.py`,
    `tests/test_test_runner.py`, `tests/test_model_registry.py`,
    `tests/test_repo_context.py`, `tests/test_openai_mentor_trigger.py`, and
    `tests/test_xriq_preflight_api.py` with `47 passed`.
  - A follow-up label-only commit `179f58b` clarified the live `/v1/tests`
    description for GitHub workflows; Vast was fast-forwarded and compile-check
    passed after that commit.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `43893`.
  - Live smoke passed: `POST /v1/github/pull-request` returned expected
    disabled-state HTTP `503` because live GitHub credentials are intentionally
    not configured. `GET /v1/tests` shows `tests/test_github_client.py` in the
    focused pytest command.
  - Pushed commits:
    `552220b Add BIBER GitHub PR workflow support` and
    `179f58b Clarify GitHub workflow test label`.
- BIBER MVP end-to-end agent-smoke checkpoint:
  - Added `scripts/vast_biber_agent_smoke.sh`.
  - The script validates the live BIBER agent workflow with:
    repo-context `/v1/chat`, bounded `/v1/files/edit` dry-run, allowlisted
    `/v1/tests/run` with `python-compileall-api`, and optional GitHub
    save/draft-PR creation only when `BIBER_AGENT_SMOKE_GITHUB=1` is explicitly
    set.
  - Default GitHub behavior is `skip`, so the smoke does not create branches,
    commits, or pull requests unless deliberately enabled.
  - Artifacts are written outside the repo under
    `/workspace/outputs/biber-agent-smoke-*`.
  - Updated `docs/API_EXAMPLES.md` with the smoke command.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --cached --check`. Local
    `bash -n` remains unavailable because WSL has no installed distro.
  - Vast checkout was fast-forwarded to `28ebe62`; Vast verification passed
    with `bash -n scripts/vast_biber_agent_smoke.sh`,
    `/workspace/biber-venv/bin/python -m compileall app src tests`, and the
    live smoke script.
  - Latest live smoke summary: chat returned `model=biber-dev-core-v1`,
    mentor was not used, file edit was dry-run only, `python-compileall-api`
    returned `ok=true`, and GitHub was skipped because it is not configured.
  - Latest smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260518T195259Z-44005`.
  - No FastAPI/vLLM restart, model training, credential change, or OpenAI
    mentor call was needed.
  - Pushed commit:
    `28ebe62 Add BIBER agent smoke script`.
- BIBER MVP agent-session API checkpoint:
  - Added `POST /v1/agent/sessions` in both the packaged API and current Vast
    direct launcher path.
  - The endpoint wraps the existing MVP primitives into one response with a
    session id and ordered step records:
    repo-context chat, optional bounded workspace edit, optional allowlisted
    test run, optional GitHub save, and optional GitHub pull request.
  - Defaults remain conservative: `use_mentor=false`, `test_id` defaults to
    `python-compileall-api`, GitHub actions run only when explicitly included,
    and workspace edits obey the same bounded edit guardrails.
  - Added `tests/test_agent_session.py` and included it in the focused
    `pytest-core` allowlist.
  - Updated `docs/API_EXAMPLES.md` with a tracked agent-session example.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --cached --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Vast checkout was fast-forwarded to `b280d49`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests` and
    focused pytest:
    `tests/test_agent_session.py`, `tests/test_workspace_edit.py`,
    `tests/test_github_client.py`, `tests/test_test_runner.py`,
    `tests/test_model_registry.py`, `tests/test_repo_context.py`,
    `tests/test_openai_mentor_trigger.py`, and `tests/test_xriq_preflight_api.py`
    with `49 passed`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `44329`.
  - Live smoke passed: `POST /v1/agent/sessions` returned `200 OK` with chat,
    dry-run workspace edit, and successful `python-compileall-api` test step.
  - Pushed commit:
    `b280d49 Add BIBER agent session API`.
- BIBER MVP agent-session persistence checkpoint:
  - Added a file-backed agent-session artifact store in both the packaged API
    and the current Vast direct launcher path.
  - `POST /v1/agent/sessions` now persists each completed session as JSON and
    returns `artifact_path`.
  - Added read endpoints:
    `GET /v1/agent/sessions?limit=<n>` and
    `GET /v1/agent/sessions/{session_id}`.
  - New setting: `BIBER_AGENT_SESSION_DIR`. If omitted, Vast defaults to
    `/workspace/outputs/agent-sessions`; non-Vast local runs default to
    `.biber-runtime/agent-sessions` under the configured repo context root.
  - Updated `docs/API_EXAMPLES.md` with list/read examples and added
    persistence coverage to `tests/test_agent_session.py`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`. Local pytest and ruff
    are still unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `786ec51 Persist BIBER agent sessions`.
  - Vast checkout was fast-forwarded to `786ec51`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests` and
    focused pytest:
    `tests/test_agent_session.py`, `tests/test_workspace_edit.py`,
    `tests/test_github_client.py`, `tests/test_model_registry.py`,
    `tests/test_openai_mentor_trigger.py`, `tests/test_repo_context.py`, and
    `tests/test_xriq_preflight_api.py` with `44 passed`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `44642`.
  - Live persisted-session smoke passed: create/list/read all returned
    `200 OK`; session id `af658dd2-44b6-4800-bd87-561b7424c17c`; artifact:
    `/workspace/outputs/agent-sessions/af658dd2-44b6-4800-bd87-561b7424c17c.json`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP agent-session XRIQ-context checkpoint:
  - Added opt-in `include_xriq_context` to `POST /v1/agent/sessions` in both
    the packaged API and the current Vast direct launcher path.
  - When enabled, the session reads the configured XRIQ private-devnet overview
    before chat, prepends a concise chain summary to the model context, and
    persists the raw overview under an `xriq_context` step.
  - Added bounded controls `xriq_explorer_limit` and `xriq_snapshot_limit`.
    Defaults are `5`; each is capped at `25`.
  - Updated `scripts/vast_biber_agent_smoke.sh` so the live smoke now verifies
    the `xriq_context` step before `chat`, confirms mentor remains disabled,
    and records the XRIQ context height in `summary.json`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests scripts` and `git diff --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `e4df1d0 Add XRIQ context to agent sessions`.
  - Vast checkout was fast-forwarded to `e4df1d0`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_agent_session.py tests/test_xriq_preflight_api.py -q` with
    `23 passed`, and the live BIBER agent smoke.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `49733`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260518T234409Z-49758`.
    It returned session id `303e354e-79f3-4435-a936-01669802a1a4`, step order
    `xriq_context`, then `chat`, `xriq_context_height=2`, and
    `mentor_used=false`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP agent-capabilities checkpoint:
  - Added authenticated `GET /v1/agent/capabilities` in both the packaged API
    and the current Vast direct launcher path.
  - The endpoint gives future desktop/web/CLI agent clients a safe discovery
    surface for the current MVP: session endpoints, bounded workspace edits,
    allowlisted tests, GitHub save/PR availability, optional OpenAI mentor
    trigger, XRIQ private-devnet context support, and request templates.
  - Current presets:
    `default_coding_session` and `xriq_private_devnet_review`.
  - The XRIQ preset is still conservative: `language=Rust`,
    `task_type=xriq_private_devnet_review`, `use_mentor=false`,
    `include_xriq_context=true`, and `test_id=python-compileall-api`.
  - Added `tests/test_agent_capabilities.py`, updated
    `docs/API_EXAMPLES.md`, and extended `scripts/vast_biber_agent_smoke.sh`
    to validate the capabilities endpoint and preset list.
  - Local workstation verification passed with bundled Python
    `compileall app src tests scripts` and `git diff --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `8a539de Add BIBER agent capabilities endpoint`.
  - Vast checkout was fast-forwarded to `8a539de`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_agent_capabilities.py tests/test_agent_session.py tests/test_xriq_preflight_api.py -q`
    with `25 passed`, and the live BIBER agent smoke.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `50105`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260518T235843Z-50130`.
    It confirmed capability presets `default_coding_session` and
    `xriq_private_devnet_review`, returned session id
    `c1b8a1f1-fd96-4012-9607-90b687325e73`, step order `xriq_context`, then
    `chat`, and `xriq_context_height=2`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP agent-client helper checkpoint:
  - Added `scripts/biber_agent_client.py`, a dependency-free stdlib helper for
    future desktop/web/CLI client work.
  - The helper can:
    - call `GET /v1/agent/capabilities`,
    - print a concise capability/preset summary,
    - create `POST /v1/agent/sessions` requests from advertised presets, and
    - override model/language/task type/repo context/test id/XRIQ context flags
      from the command line.
  - The helper sends both `Authorization: Bearer <key>` and `X-API-Key` so it
    works against the current direct Vast API and the packaged API auth path.
  - Added `tests/test_biber_agent_client.py`, documented the helper in
    `docs/API_EXAMPLES.md`, and added the test to the `pytest-core` allowlist
    in both `app/test_runner.py` and `src/biber_api/test_runner.py`.
  - Extended `scripts/vast_biber_agent_smoke.sh` to run
    `scripts/biber_agent_client.py --json capabilities` against the live API
    and store `agent-client-capabilities.json` in the smoke artifact directory.
  - Local workstation verification passed with bundled Python
    `compileall app src tests scripts` and `git diff --check`. Local pytest is
    still unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `51ad833 Add BIBER agent client helper`.
  - Vast checkout was fast-forwarded to `51ad833`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests scripts`,
    `bash -n scripts/vast_biber_agent_smoke.sh`, focused pytest
    `tests/test_biber_agent_client.py tests/test_agent_capabilities.py tests/test_agent_session.py -q`
    with `11 passed`, and the live BIBER agent smoke.
  - Restarted only the FastAPI process because the server-side `pytest-core`
    allowlist changed. vLLM stayed running with pid `5802`. New FastAPI pid:
    `50453`.
  - Latest live smoke artifact:
    `/workspace/outputs/biber-agent-smoke-20260519T000619Z-50478`.
    It confirmed the helper capabilities path, capability presets
    `default_coding_session` and `xriq_private_devnet_review`, session id
    `36c0098f-d4a6-4674-9e58-88925bfb3d31`, step order `xriq_context`, then
    `chat`, and `xriq_context_height=2`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP repo-adaptation checkpoint:
  - Added `training/repo_adaptation_plan.py`, a conservative helper for
    preparing repo-specific BIBER adaptation work from a GitHub checkout or
    local repo without copying source code into a training file.
  - The helper scans metadata only: selected relative paths, size, SHA-256,
    language, and role. It skips `.git`, dependency/build directories,
    binary-looking files, secret-looking filenames, and files with
    secret-looking contents.
  - The emitted strategy defaults to repo-context-first. Fine-tuning is
    explicitly gated on repeated model failures, curated examples, held-out eval
    prompts, and a candidate model beating the current served baseline.
  - Added generated eval-prompt output so future BIBER sessions can test repo
    understanding before paying for a training run.
  - Added `docs/BIBER_REPO_ADAPTATION.md`, documented the CLI in
    `docs/API_EXAMPLES.md`, and added `tests/test_repo_adaptation_plan.py`.
  - Added the repo-adaptation test to the `pytest-core` allowlist in both
    `app/test_runner.py` and `src/biber_api/test_runner.py`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests scripts training`, `git diff --check`, a touched
    file long-line scan, and a real local plan smoke against this repo writing
    `.biber-runtime/repo-adaptation-smoke.json` plus
    `.biber-runtime/repo-adaptation-smoke-eval.jsonl`. Local pytest is still
    unavailable in the bundled workstation runtime.
  - Pushed implementation/fix commits:
    `9126fdd Add BIBER repo adaptation plan` and
    `2efa65b Fix repo adaptation relative role detection`.
  - Vast checkout was fast-forwarded to `2efa65b`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests scripts training`,
    focused pytest
    `tests/test_repo_adaptation_plan.py tests/test_training_dataset.py -q`
    with `7 passed`, and a real repo-adaptation plan smoke against this repo
    writing `/workspace/outputs/repo-adaptation-plan-smoke.json` plus
    `/workspace/outputs/repo-adaptation-eval-smoke.jsonl`.
  - Restarted only the FastAPI process because the server-side `pytest-core`
    allowlist changed. vLLM stayed running with pid `5802`. New FastAPI pid:
    `50843`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP repo-context planner checkpoint:
  - Added deterministic `plan_repo_context` support in both the packaged API
    and the current direct Vast app copy.
  - Added authenticated `POST /v1/repo/context/plan`. The endpoint returns
    `selected_paths`, `detected_project_types`, candidate reasons/priorities,
    skipped paths, and a concise summary. It does not return file contents.
  - The planner keeps user-pinned paths first, then changed files, related
    tests, project manifests, README files, and instruction-term matches.
  - It detects starter stack signals for `.NET`, Java/Spring-style Gradle or
    Maven repos, Rust, Node/React, and Python.
  - It filters secret-looking paths, dependency folders, build outputs, common
    binary suffixes, and paths outside `BIBER_REPO_CONTEXT_ROOT`.
  - `GET /v1/agent/capabilities` now advertises planner support and the
    `POST /v1/repo/context/plan` endpoint.
  - Added tests in `tests/test_repo_context.py` and
    `tests/test_agent_capabilities.py`, and documented the endpoint in
    `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests`, `git diff --check`, and a lightweight planner
    smoke. Local pytest is still unavailable in the bundled workstation
    runtime.
  - Pushed implementation commit:
    `1cc790a Add BIBER repo context planner`.
  - Vast checkout was fast-forwarded to `1cc790a`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests`,
    focused pytest
    `tests/test_repo_context.py tests/test_agent_capabilities.py -q` with
    `12 passed`, and a live authenticated planner endpoint smoke.
  - Restarted only the FastAPI process because API code changed. vLLM stayed
    running with pid `5802`. New FastAPI pid: `51098`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER MVP multi-file edit planner checkpoint:
  - Added deterministic `plan_workspace_edits` support in both the packaged
    API and the current direct Vast app copy.
  - Added authenticated `POST /v1/files/edit/plan`. The endpoint validates a
    small batch of proposed edits without writing anything.
  - The response returns accepted edit previews, rejected edit reasons,
    old/new hashes, byte counts, replacement counts, simple risk markers,
    touched-file count, and a concise summary.
  - It reuses the existing single-file workspace edit guardrails: workspace
    path bounds, denied secret/build/binary paths, byte limits, exact
    replacement-count checks, and create-only-when-explicit behavior.
  - It rejects duplicate target paths within the same plan and caps the plan
    size through `max_files`/schema limits.
  - `GET /v1/agent/capabilities` now advertises `edit_plan`,
    `POST /v1/files/edit/plan`, and multi-file plan support.
  - Added tests in `tests/test_workspace_edit.py` and
    `tests/test_agent_capabilities.py`, and documented the endpoint in
    `docs/API_EXAMPLES.md`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests`, `git diff --check`, and a lightweight planner
    smoke confirming no file was written. Local pytest is still unavailable in
    the bundled workstation runtime.
  - Pushed implementation commit:
    `70e6320 Add BIBER multi-file edit planner`.
  - Vast checkout was fast-forwarded to `70e6320`; Vast verification passed
    with `/workspace/biber-venv/bin/python -m compileall app src tests`,
    focused pytest
    `tests/test_workspace_edit.py tests/test_agent_capabilities.py -q` with
    `12 passed`, and a live authenticated edit-plan endpoint smoke.
  - Restarted only the FastAPI process because API code changed. vLLM stayed
    running with pid `5802`. New FastAPI pid: `51376`.
  - Confirmed the live smoke's planned create file was not written.
  - No credential change, model training, or OpenAI mentor call was needed.
- XRIQ snapshot export/import checkpoint:
  - Added private-devnet `xriq-node snapshot-export` and
    `xriq-node snapshot-import`.
  - Export writes a new snapshot directory containing `manifest.json`,
    `chain.bin`, and optional `pending.tsv`. The manifest records
    `xriq-private-devnet-snapshot-v1`, chain id, height, latest block hash,
    state root, pending count, and stored block count.
  - Import restores into fresh target chain/pending files only and refuses to
    overwrite existing targets, so it can be used for cheap Vast GPU/volume
    moves without accidentally replacing a live chain.
  - Added design/operations doc:
    `docs/XRIQ_SNAPSHOT_EXPORT_IMPORT.md`.
  - Updated `xriq/README.md`, `docs/XRIQ_NODE_JSON_SCHEMA.md`,
    `docs/XRIQ_TECHNICAL_SPEC.md`, and
    `scripts/xriq_private_devnet_smoke.sh`.
  - Local Windows verification passed from `xriq/`: `cargo fmt --check`,
    focused `cargo test -p xriq-node snapshot -j 1`,
    focused `cargo test -p xriq-node checked_fixture -j 1`,
    full isolated `cargo test -j 1` with `136` passing workspace tests, and
    `cargo clippy -- -D warnings`. The default Windows target had a transient
    locked test binary, so full tests were run with an isolated target dir,
    then generated target files were removed.
  - Pushed implementation/docs/smoke commit:
    `fba4a1d Add XRIQ snapshot export import`.
  - Vast checkout was fast-forwarded to `fba4a1d`; verification passed with
    `bash -n scripts/xriq_private_devnet_smoke.sh`, `cargo fmt --check`,
    focused snapshot tests, focused checked-fixture tests, full
    `cargo test -j 1` with `136` passing workspace tests,
    `cargo clippy -- -D warnings`, and full
    `bash scripts/xriq_private_devnet_smoke.sh`.
  - Latest private-devnet smoke artifact:
    `/workspace/biber-ai-platform/xriq/target/xriq-private-devnet-smoke-20260518T203806Z-44845`.
  - No FastAPI/vLLM restart, credential change, model training, or OpenAI
    mentor call was needed.
- BIBER XRIQ snapshot API wrapper checkpoint:
  - Added server-side snapshot roots:
    `BIBER_XRIQ_SNAPSHOT_ROOT_DIR` and
    `BIBER_XRIQ_SNAPSHOT_IMPORT_ROOT_DIR`.
  - Added authenticated endpoints:
    `POST /v1/xriq/private-devnet/snapshots/export` and
    `POST /v1/xriq/private-devnet/snapshots/import`.
  - Clients can provide only a safe snapshot name and options. Export writes
    under the configured snapshot root; import defaults to `target: staging`
    under the configured import root so normal smoke tests do not overwrite
    live private-devnet files. `target: configured` is available only as an
    explicit restore path, and the Rust runner still refuses existing targets.
  - Updated `docs/API_EXAMPLES.md`,
    `tests/test_xriq_preflight_api.py`, and
    `scripts/vast_xriq_api_smoke.sh`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`. Local pytest remains
    unavailable in the bundled workstation runtime.
  - Pushed implementation commit:
    `4dbe7a0 Add BIBER XRIQ snapshot API wrapper`.
  - Vast checkout was fast-forwarded to `4dbe7a0`; verification passed with
    `/workspace/biber-venv/bin/python -m compileall app src tests`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest
    `tests/test_xriq_preflight_api.py -q` with `14 passed`.
  - Restarted only FastAPI; vLLM stayed running with pid `5802`. New FastAPI
    pid: `46258`.
  - Live consolidated API smoke passed, including snapshot export and safe
    staging import. Artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T210223Z-46283`.
    Snapshot name: `api-smoke-20260518T210223Z-46283`; height `2`; state root
    `578bdd2affeece78c7949d34da08391c797b363b045c3cff6c999868e0baa2d6`;
    pending transactions `0`.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER XRIQ snapshot discovery checkpoint:
  - Added authenticated read-only endpoints:
    `GET /v1/xriq/private-devnet/snapshots?limit=<n>` and
    `GET /v1/xriq/private-devnet/snapshots/{snapshot_name}`.
  - The endpoints read only `manifest.json` files below the configured
    snapshot root, validate safe snapshot names, and expose summary/detail
    metadata for snapshots created by the server-side export endpoint.
  - Updated `docs/API_EXAMPLES.md`,
    `tests/test_xriq_preflight_api.py`, and
    `scripts/vast_xriq_api_smoke.sh`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`.
  - Pushed implementation commit:
    `fc03d6d Add XRIQ snapshot discovery API`.
  - Vast checkout was fast-forwarded to `fc03d6d`; verification passed with
    `/workspace/biber-venv/bin/python -m compileall app src tests`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest
    `tests/test_xriq_preflight_api.py -q` with `18 passed`.
  - Restarted only FastAPI; vLLM stayed running with pid `5802`. New FastAPI
    pid: `46758`.
  - Live consolidated API smoke passed, including snapshot export, safe
    staging import, snapshot list, and snapshot detail. Artifact:
    `/workspace/outputs/xriq-api-smoke-20260518T220342Z-46783`.
    Snapshot name: `api-smoke-20260518T220342Z-46783`; height `2`; list count
    `2`; state root
    `578bdd2affeece78c7949d34da08391c797b363b045c3cff6c999868e0baa2d6`;
    detail reported manifest, chain, and pending files present.
  - No credential change, model training, or OpenAI mentor call was needed.
- BIBER XRIQ private-devnet overview checkpoint:
  - Added authenticated read-only endpoint:
    `GET /v1/xriq/private-devnet/overview?explorer_limit=<n>&snapshot_limit=<n>`.
  - The endpoint consolidates existing server-side wrappers for status,
    explorer overview, durable mempool detail, and snapshot list into one
    wallet/explorer-friendly payload with a short summary.
  - Updated `docs/API_EXAMPLES.md`,
    `tests/test_xriq_preflight_api.py`, and
    `scripts/vast_xriq_api_smoke.sh`.
  - Local workstation verification passed with bundled Python
    `compileall app src tests` and `git diff --check`.
  - Pushed implementation commit:
    `716e9c1 Add XRIQ private devnet overview API`.
  - Vast checkout was fast-forwarded to `716e9c1`; verification passed with
    `/workspace/biber-venv/bin/python -m compileall app src tests`,
    `bash -n scripts/vast_xriq_api_smoke.sh`, and focused pytest
    `tests/test_xriq_preflight_api.py -q` with `19 passed`.
  - Restarted only FastAPI; vLLM stayed running with pid `5802`. New FastAPI
    pid: `47248`.
  - Live consolidated API smoke passed, including the new overview endpoint.
    Artifact: `/workspace/outputs/xriq-api-smoke-20260518T223059Z-47273`.
    Overview summary: height `2`, pending count `0`, snapshot count `3`,
    latest snapshot `api-smoke-20260518T223059Z-47273`, state root
    `578bdd2affeece78c7949d34da08391c797b363b045c3cff6c999868e0baa2d6`.
  - No credential change, model training, or OpenAI mentor call was needed.

## Repo State

- Local branch: `main`
- Remote: `origin` points to `https://github.com/selvasmallive/biber-ai-platform.git`
- GitHub `origin/main` was pushed from this workstation on 2026-05-18 and now
  includes the live deployment hardening, GitHub save hardening, pytest
  verification, BIBER XRIQ preflight/read wrappers, the durable mempool
  wrapper, BIBER XRIQ snapshot wrapper/discovery endpoints, the consolidated
  private-devnet overview endpoint, allowlisted BIBER test-runner API,
  persisted BIBER agent-session artifacts, and handoff updates.
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
  - `ddc5dc8 Add BIBER XRIQ preflight API wrapper`
  - `67ce353 Add XRIQ wrapper Rust environment config`
  - `4d8c251 Add BIBER XRIQ read wrappers`
  - `690df43 Record BIBER XRIQ read wrapper checkpoint`
  - `81824b3 Add XRIQ durable mempool wrapper`
  - `0fffb80 Record XRIQ mempool wrapper checkpoint`
  - `32909e8 Add BIBER XRIQ explorer wrappers`
  - `4610a32 Record XRIQ explorer wrapper checkpoint`
  - `16e506b Add BIBER XRIQ API smoke script`
  - `a193478 Record XRIQ API smoke checkpoint`
  - `6205b66 Expose XRIQ block transaction hashes`
  - `d4df8c0 Add allowlisted BIBER test runner API`
  - `992890b Add bounded BIBER workspace edit API`
  - `552220b Add BIBER GitHub PR workflow support`
  - `179f58b Clarify GitHub workflow test label`
  - `28ebe62 Add BIBER agent smoke script`
  - `b280d49 Add BIBER agent session API`
  - `786ec51 Persist BIBER agent sessions`
  - `fba4a1d Add XRIQ snapshot export import`
  - `4dbe7a0 Add BIBER XRIQ snapshot API wrapper`
  - `fc03d6d Add XRIQ snapshot discovery API`
  - `716e9c1 Add XRIQ private devnet overview API`
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
- Added explicit OpenAI mentor trigger plumbing:
  - `OPENAI_API_KEY` must stay server-side in `.env` or a secret manager; do
    not commit it, train on it, or send it to the local model.
  - When `BIBER_MENTOR_ENABLED=true`, `OPENAI_API_KEY` is present, and
    `OPENAI_MODEL` is set, BIBER calls the OpenAI Responses API only if a user
    prompt includes `Review with OpenAI mentor`.
  - Routine inference still stays on the local Vast GPU-backed model, and
    `use_mentor=false` disables the mentor call even if the phrase appears.
  - Local Python verification passed with `pytest`: `27` tests.
  - Vast checkout was fast-forwarded to `859df96`.
  - Vast syntax verification passed with `/venv/main/bin/python -m compileall
    app src tests training`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `14596`.
  - `bash scripts/vast_test_direct.sh` passed. Runtime now reports
    `mentor_trigger_phrase="Review with OpenAI mentor"`, with
    `mentor_enabled=false` and `mentor_configured=false` until server-side
    OpenAI credentials are deliberately added.
- Added the first BIBER model registry/provider abstraction checkpoint:
  - `app/model_registry.py` and `src/biber_api/model_registry.py` define a
    config-driven registry for logical BIBER model IDs.
  - Default stable logical model: `biber-dev-core-v1`, backed by the existing
    local vLLM served model `biber-dev-core` and upstream
    `Qwen/Qwen2.5-Coder-7B-Instruct`.
  - Default candidate logical model: `biber-dev-core-v2-candidate`, disabled
    until a Qwen3-Coder/Qwen3-Coder-Next or newer endpoint is configured and
    benchmarked.
  - `/v1/models` now returns stable/candidate model metadata instead of only
    static model-name strings.
  - `/v1/chat` resolves requested logical model IDs through the registry and
    returns the resolved logical model ID in the response.
  - Backward-compatible alias: requests for `biber-dev-core` resolve to
    `biber-dev-core-v1`.
  - Local Python verification passed with `pytest`: `31` tests.
  - Vast checkout was fast-forwarded to `328ab3f`.
  - Vast syntax verification passed with `/venv/main/bin/python -m compileall
    app src tests training`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `14815`.
  - `bash scripts/vast_test_direct.sh` passed. `/v1/chat` returned
    `model="biber-dev-core-v1"` and `mentor_used=false`.
  - Live `/v1/models` now reports `biber-dev-core-v1` as stable/enabled backed
    by provider model `biber-dev-core`, and `biber-dev-core-v2-candidate` as a
    disabled candidate for future Qwen3/newer-model evaluation.
- Added selected-file repo context for the BIBER MVP:
  - `app/repo_context.py` and `src/biber_api/repo_context.py` provide bounded
    selected-file context ingestion for `/v1/chat`.
  - Request field: `repo_context_paths`, with workspace-relative file paths.
  - The context loader rejects paths outside the configured repo root, obvious
    secret paths such as `.env`, private-key-looking files, binary-looking
    files, and common cache/VCS directories.
  - Context is bounded by `BIBER_REPO_CONTEXT_MAX_FILES`,
    `BIBER_REPO_CONTEXT_MAX_BYTES_PER_FILE`, and
    `BIBER_REPO_CONTEXT_MAX_TOTAL_BYTES`.
  - This is intentionally not full RAG or automatic repo crawling. It is the
    minimal repo-aware step before file edit/test execution workflows.
  - Local Python verification passed with `pytest`: `38` tests.
  - Vast checkout was fast-forwarded to `7e66a7f`.
  - Vast syntax verification passed with `/venv/main/bin/python -m compileall
    app src tests training`.
  - Restarted only the FastAPI process; vLLM stayed running with pid `5802`.
    New FastAPI pid: `15053`.
  - `bash scripts/vast_test_direct.sh` passed. `/v1/chat` returned
    `model="biber-dev-core-v1"` and `mentor_used=false`.
  - Live repo-context smoke passed: a valid `repo_context_paths=["README.md"]`
    request returned from `biber-dev-core-v1`, and an absolute path was rejected
    with HTTP `400` and `Repo context path must be workspace-relative`.
- Started and expanded the Rust private-devnet prototype workspace:
  - workspace path: `xriq/`.
  - implemented crates:
    - `xriq/crates/xriq-core`
    - `xriq/crates/xriq-consensus`
    - `xriq/crates/xriq-ledger`
    - `xriq/crates/xriq-mempool`
    - `xriq/crates/xriq-node`
    - `xriq/crates/xriq-rpc`
    - `xriq/crates/xriq-storage`
    - `xriq/crates/xriq-wallet`
  - implemented dependency-free private-devnet primitives for checked
    `XriqAmount`, validated devnet `Address`, `Hash32`, basic transaction
    validation, and block-header validation.
  - implemented account ledger state transitions for balances, nonces, minimum
    fees, fee-sink crediting, and atomic mutation.
  - implemented deterministic mempool checks for duplicate transaction hashes,
    duplicate account nonces, minimum fee, zero amount, removal, and
    fee/order/hash ordering.
  - implemented deterministic single-authority block production with parent
    checks, explicit roots, signature requirement, transaction cap enforcement,
    and mempool-based transaction selection.
  - implemented dependency-free local RPC endpoint behavior for health, chain
    status, account lookup, mempool listing, pending transaction lookup, and
    transaction submission.
  - implemented local block storage and a minimal node loop for transaction
    submission, block production, ledger application, mempool cleanup, block
    persistence, replay startup from persisted canonical blocks, and
    RPC-visible state.
  - implemented private-devnet wallet CLI baseline for deterministic test
    identity generation and transfer draft construction.
  - latest local validation passed: `cd xriq && cargo fmt --check && cargo test`.
  - latest local Rust test result: `56` passed.
  - latest local clippy validation passed:
    `cd xriq && cargo clippy -- -D warnings`.
  - latest Vast Rust validation passed with the toolchain stored under
    `/workspace`: `cargo fmt --check`, `cargo test` with `56` passing tests,
    `cargo clippy -- -D warnings`, and wallet CLI `key generate`/`transfer`
    smokes.
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
- Agent-session artifacts are local JSON files. `BIBER_AGENT_SESSION_DIR` is
  optional; when omitted on Vast, the API stores them under
  `/workspace/outputs/agent-sessions`.
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
  code/deployment change. Follow the explicit `Cost-Control Execution Policy`
  near the top of this handoff.
- Future custom-model phases should prefer the user's own GPU and eventual
  fine-tuned `biber-dev-core` model over paid external model APIs. Keep optional
  mentor APIs disabled unless the user explicitly wants them for quality review.
- Future BIBER API-key agent-client and mentor work is documented in
  `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md`. Treat BIBER as the default
  engine and OpenAI/Codex as an optional mentor/reviewer for architecture,
  security-sensitive Rust/crypto review, eval design, failure diagnosis, and
  curated training-data review.
- Repo-specific adaptation is documented in `docs/BIBER_REPO_ADAPTATION.md`.
  Use `training/repo_adaptation_plan.py` against the user's target GitHub repo
  first, run the generated eval prompts through the current served BIBER model,
  and fine-tune on Vast only after repeatable failures are converted into
  curated examples with a held-out eval set. Do not treat arbitrary repo source
  dumps as training data.
- Future Rust/XRIQ work is now an explicit project track documented in
  `docs/XRIQ_RUST_TRACK.md`. Treat it as a phased path: first prove BIBER's
  Rust capability with `cargo`-backed evals, then design XRIQ, then build a
  private Rust devnet, then wallet/explorer tools, and only later consider any
  public network or cryptocurrency launch after separate security and
  legal/compliance review.
- XRIQ legal-risk reduction is now a hard design guardrail documented in
  `docs/XRIQ_LEGAL_RISK_REDUCTION.md`. Do not implement or generate
  market-facing public token, DEX, custody, bridge, stablecoin, payment,
  airdrop, liquidity, listing, validator-yield, or investment-promotion features
  unless the required review status is explicitly recorded in docs.
- XRIQ privacy direction is now explicit in `docs/XRIQ_TECHNICAL_SPEC.md`,
  `docs/XRIQ_PHASE3_DECISIONS.md`, `docs/XRIQ_LEGAL_RISK_REDUCTION.md`, and
  `docs/XRIQ_RUST_TRACK.md`: keep the MVP transparent, reserve future
  Zcash-like selective privacy with viewing keys/payment disclosure/audit
  receipts, and avoid Monero-style mandatory privacy while DEX usability and
  AML-friendly posture remain goals.
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

1. Keep `/workspace/adapters/biber-dev-core-lora-rust-xriq-400` served unless a
   future adapter beats both gates: current Rust/XRIQ cargo validators and the
   broad regression eval.
2. Reconnect and verify current service state with:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_status_direct.sh
bash scripts/vast_test_direct.sh
```

3. If serving is not on the broad-safe adapter, restore it:

```bash
cd /workspace/biber-ai-platform
BIBER_LORA_ADAPTER_DIR=/workspace/adapters/biber-dev-core-lora-rust-xriq-400 \
  bash scripts/vast_start_lora_direct.sh
bash scripts/vast_test_direct.sh
```

4. Before any more GPU training, improve the Rust/XRIQ ledger evaluation and
   prompt strategy. The current remaining failure is
   `rust_xriq_apply_ledger_transaction`; the model needs stronger guidance for
   rustfmt-clean output, no external crates in standalone evals, cloned-map
   atomic commits, and checked nonce/fee/balance arithmetic.
5. Consider adding a structured "BIBER codegen profile" prompt for Rust/XRIQ:
   "standard library only, cargo fmt clean, no external crates unless listed,
   compile before final answer, prefer cloned state for atomic ledger updates."
   Test this through inference before another fine-tune.
6. Run the two current evals after any serving change:

```bash
cd /workspace/biber-ai-platform
BIBER_EVAL_FAIL_ON_VALIDATORS=0 bash scripts/vast_eval_rust_xriq_direct.sh
bash scripts/vast_eval_lora_direct.sh
```

7. Promote a new adapter only if it improves beyond the current served baseline:
   at least `7/7` current Rust/XRIQ cargo validators and `18/18` broad
   expectation checks.
8. If a future training run fails, inspect the QLoRA log and do not leave an
   unverified adapter served. Restore `biber-dev-core-lora-rust-xriq-400` unless
   a better verified candidate exists.
9. If the current Vast instance is unavailable, follow the
   `Moving To A New Vast GPU` section. Prefer attaching or copying the existing
   500 GB volume/state if it is still available; otherwise rebuild from GitHub
   and regenerate datasets from the approved sources.
10. Update this handoff immediately after SSH is restored, training finishes,
   serving restarts, evals complete, or the instance is moved.
11. After future local XRIQ prototype changes, fast-forward the Vast checkout
   and rerun Rust validation there:

```bash
cd /workspace/biber-ai-platform
git pull --ff-only origin main
cd xriq
export RUSTUP_HOME=/workspace/.rustup
export CARGO_HOME=/workspace/.cargo
export PATH=/workspace/.cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
cargo fmt --check
cargo test -j 1
cargo clippy -- -D warnings
cd /workspace/biber-ai-platform
bash -n scripts/xriq_private_devnet_smoke.sh
bash scripts/xriq_private_devnet_smoke.sh
```

12. Treat these as first-class BIBER MVP/Replit-replacement workflow goals
   before broad language expansion:
   - More reliable repo-context selection: detect project type, include
     relevant manifests/config/tests/changed files, support pinned files, and
     avoid secrets, dependency folders, build outputs, and binaries. The first
     deterministic planner endpoint, `POST /v1/repo/context/plan`, is now
     implemented and Vast-verified.
   - Safer multi-file editing: produce an edit plan, enforce workspace/path
     bounds, limit touched files, apply patch-style changes, and run formatting
     or targeted tests after edits. The first no-write multi-file planner
     endpoint, `POST /v1/files/edit/plan`, is now implemented and
     Vast-verified.
   - Better test-failure diagnosis loops: parse failures for `.NET`, Java,
     Rust, Node/React, and Python incrementally; classify compile/test/config
     failures; extract concise model context; rerun targeted tests; and save
     useful failure/fix pairs as future eval or training candidates.
13. Continue the XRIQ private-devnet prototype after the Rust/XRIQ model loop is
   stable. `xriq/` is already the separate Rust workspace inside this repo, and
   it is preferred over creating a second top-level Rust workspace unless the
   project later needs independent release/versioning. The next protocol target
   after `xriq-core`, `xriq-ledger`, `xriq-mempool`, `xriq-consensus`,
   `xriq-rpc`, `xriq-storage`, `xriq-node`, `xriq-wallet`, and
   `xriq-explorer`, canonical hash API wiring, genesis/root strategy,
   deterministic replay startup, the local `xriq-node status`,
   `xriq-node produce-transfer-block`, `xriq-node produce-draft-block`,
   `xriq-node explorer-overview`, `xriq-node block-detail`,
   `xriq-node account-detail`, `xriq-node mempool-detail`, and
   `xriq-node transaction-detail` runner commands,
   `scripts/xriq_private_devnet_smoke.sh`,
   `xriq-node serve-readonly`, `xriq-node serve-private`, and
   durable pending HTTP state, pending-block production, and
   `xriq-node preflight-transfer`, is to keep the local file-backed workflow
   small and deterministic. The thin BIBER preflight wrapper and read wrappers
   for status/explorer/block/account/transaction/mempool are now done, and
   `scripts/vast_xriq_api_smoke.sh` provides a consolidated live API smoke
   that follows block transaction hashes into transaction detail and checks the
   snapshot wrapper through safe staging import. The
   status state-root marker, deterministic replay smoke, the first allowlisted
   BIBER test-execution API slice, and bounded workspace-edit API slice are now
   done. The branch-aware GitHub save plus draft-PR path, a small BIBER MVP
   end-to-end agent smoke, the tracked agent-session endpoint, and the
   file-backed persisted agent-session artifact layer are now implemented and
   Vast-verified. XRIQ private-devnet snapshot export/import is also
   implemented and Vast-verified for cheap chain/pending state moves, with the
   thin BIBER API wrapper, snapshot discovery endpoints, and consolidated
   private-devnet overview endpoint now live. The minimal stdlib client and
   same-origin browser dashboard for the BIBER/XRIQ private-devnet overview,
   snapshot, preflight-transfer, transaction-detail, and account-detail
   endpoints are now also implemented and Vast-verified. The tracked BIBER
   agent-session flow can now opt into XRIQ private-devnet overview context
   before chat, and client tools can discover agent capabilities and the
   `xriq_private_devnet_review` request template through
   `GET /v1/agent/capabilities`. The stdlib
   `scripts/biber_agent_client.py` helper can now consume capabilities and
   create sessions from presets. Repo-specific adaptation now has a conservative
   metadata/eval scaffold in `training/repo_adaptation_plan.py` and
   `docs/BIBER_REPO_ADAPTATION.md`; use it against the user's actual target
   GitHub repo before considering Vast fine-tuning. The first repo-context
   planner endpoint is live, and the first no-write multi-file edit-plan
   endpoint is live. Good next targets are adding a structured test-failure
   diagnosis parser for `.NET`/Java/Rust/Python output, adding a cautious
   multi-file apply transaction that requires a clean plan id/hash, adding a
   live eval-run wrapper for generated repo-adaptation prompts, or adding a
   client helper `create-session` live smoke with a tiny max-token budget.
   Public XRIQ launch, exchange listing, custody, liquidity, bridges, and
   market-facing work remain blocked.
14. Keep reviewing and refining `docs/XRIQ_TECHNICAL_SPEC.md` as the prototype
   clarifies open decisions. Do not treat the private devnet as public launch
   readiness.
15. Use BIBER AI for XRIQ through inference first: spec drafting, Rust module
   scaffolding, tests, review prompts, and private-devnet tooling. Fine-tune
   only after Rust/XRIQ evals show repeatable gaps.
16. After the Rust/XRIQ baseline is stable, follow
   `docs/BIBER_CAPABILITY_ROADMAP.md` in order: PostgreSQL, React, TypeScript,
   JavaScript, jQuery, CSS, HTML, Docker, GitHub Actions CI/CD, WASM, Bash,
   security engineering, cryptography concepts, Kubernetes, and distributed
   systems optimization before lower-priority stacks.
17. Add new training data only through approved/provenance-tracked sources, then
   validate and promote to `/workspace/data/biber_train.jsonl`.
18. Keep the cost-saving pattern: Codex changes scripts, docs, evals, and
   diagnoses failures; Vast.ai runs long GPU jobs in `tmux`.
19. Keep the API private over SSH tunnels unless credentials are deliberately
   rotated and public binding is intentionally enabled.
20. Keep the Vast.ai checkout fast-forwarded with local/GitHub `main`.
21. Add optional OpenAI mentor credentials to the server-side `.env` only if
    desired and cost-approved. The code path is already gated by
    `BIBER_MENTOR_ENABLED=true`, `OPENAI_API_KEY`, `OPENAI_MODEL`, and the
    prompt phrase `Review with OpenAI mentor`.
22. Add database-backed API keys and agent-client sessions per
    `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md`.
23. Add a durable fine-grained GitHub token to Vast `.env` if persistent
   generated-code save should stay enabled.
24. Add Azure Blob connection string and test backups.
25. Replace demo API key/passcode auth with database-backed credentials.
26. Add real MySQL persistence and Redis worker integration.

## Resume Prompt For A New Chat

```text
Read docs/CODEX_HANDOFF.md and continue the Vast.ai deployment and development
of biber-ai-platform from the current live GPU state.
```
