# XRIQ Rust Development Track

This is a future-phase track for using BIBER AI to help build XRIQ, a Rust-based
blockchain and cryptocurrency platform. Treat this as a staged engineering
program: first make BIBER reliable for Rust work, then build a private testnet,
then add wallet/explorer tools, and only later consider any public network or
token launch.

## Guiding Principles

- Rust/XRIQ is the near-term top language/domain priority for BIBER AI because
  the first major inference use case is building the XRIQ cryptocurrency
  blockchain. Prioritize Rust capability before the broader stack roadmap in
  `docs/BIBER_CAPABILITY_ROADMAP.md` unless the user explicitly redirects the
  roadmap.
- Use Rust as the primary language for XRIQ node, consensus, networking,
  storage, cryptography, wallet, and CLI work.
- Keep BIBER AI as a coding assistant and evaluator first. Do not assume the
  current model is strong enough for production Rust blockchain code until Rust
  evals pass consistently.
- Keep the cost-saving strategy: Codex prepares docs, evals, scripts, and
  diagnosis; long model runs and batch evals run on the user's Vast.ai GPU.
- Build XRIQ privately before any public launch. Start with a local devnet and
  private testnet.
- Do not market, sell, list, or distribute a cryptocurrency/token without
  separate legal, tax, AML, securities, and consumer-protection review.
- Security comes before launch: cryptography, key handling, consensus, wallet
  signing, networking, and upgrade paths need independent review.

## Phase 1: Rust Capability Baseline

Goal: verify whether current `biber-dev-core` can help write correct Rust.

- Treat this as the first capability milestone before spending effort on other
  new language tracks.
- Rust/XRIQ eval prompts are kept separate from the existing Python/API broad
  baseline so the current `18/18` broad baseline remains comparable.
- Current Rust/XRIQ eval prompt file:
  `training/eval_prompts_rust_xriq.jsonl`.
- Current Vast Rust/XRIQ eval wrapper:
  `scripts/vast_eval_rust_xriq_direct.sh`.
- The live eval runner supports cargo-backed validators that can run generated
  Rust through:
  - `cargo fmt --check`
  - `cargo check`
  - `cargo test --lib`
  - focused unit tests for serialization, transaction validation, and error
    handling.
- Add held-out Rust prompts covering:
  - structs/enums and ownership
  - error handling with `Result`
  - async networking shape
  - serde serialization
  - CLI parsing
  - unit and property-style tests
  - simple cryptographic API usage without inventing custom crypto.
- Only fine-tune on Rust data if the eval baseline shows repeatable gaps.
- Defer post-Rust capability tracks until the Rust/XRIQ baseline is useful
  enough for private XRIQ development. After Rust/XRIQ, follow the order in
  `docs/BIBER_CAPABILITY_ROADMAP.md`.

Run the Rust/XRIQ eval on Vast with:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_install_rust_toolchain.sh
bash scripts/vast_eval_rust_xriq_direct.sh
```

The Rust/XRIQ wrapper writes artifacts under `/workspace/outputs/evals` and
uses `/workspace/outputs/evals/validator-work` for temporary cargo projects.
The Rust toolchain helper installs Rust under `/workspace/.cargo` and
`/workspace/.rustup` so toolchain files stay on the 500 GB Vast volume.

Current baseline as of 2026-05-17:

- Pre-Rust/XRIQ training adapter:
  `/workspace/adapters/biber-dev-core-lora-targeted-350`.
- Pre-training Rust/XRIQ eval: `6/6` responses, `6/6` substring expectations,
  `2/6` cargo validators.
- Rust/XRIQ-priority adapter:
  `/workspace/adapters/biber-dev-core-lora-rust-xriq-400`.
- Post-training Rust/XRIQ eval:
  `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260516T200642Z.summary.json`.
- Post-training Rust/XRIQ result: `6/6` responses, `6/6` substring
  expectations, `5/6` cargo validators.
- HashSet follow-up source update:
  `training/targeted_rust_xriq_dataset.jsonl` now has `16` validated
  project-owned Rust/XRIQ records, including six extra HashSet-focused examples.
- HashSet follow-up eval:
  `/workspace/outputs/evals/biber-dev-core-rust-xriq-20260517T001354Z.summary.json`.
- HashSet follow-up result: `6/6` responses, `6/6` substring expectations,
  `6/6` cargo validators.
- The prior `rust_xriq_mempool_insert` missing-import failure is resolved for
  the current held-out eval without another training run. Keep the same live
  adapter unless future evals reveal repeatable Rust gaps.
- Broad 18-prompt eval after Rust/XRIQ retraining:
  `/workspace/outputs/evals/biber-dev-core-lora-20260517T000637Z.summary.json`.
- Broad post-training result: `18/18` responses and `18/18` simple expectation
  checks.
- The Rust/XRIQ adapter is the current confirmed live candidate because adapter
  training improved the Rust/XRIQ cargo baseline from `2/6` to `5/6`, the
  HashSet follow-up reaches `6/6` without changing weights, and the broad
  `18/18` regression baseline remains intact.

## Phase 2: XRIQ Technical Specification

Goal: define what XRIQ is before generating serious code.

- Write an XRIQ technical spec covering:
  - chain purpose and non-goals
  - account or UTXO model
  - transaction format
  - block format
  - mempool rules
  - fees
  - token supply and issuance schedule
  - validator/miner model
  - consensus mechanism
  - finality assumptions
  - networking protocol
  - storage layout
  - wallet/key model
  - RPC API
  - governance and upgrade process.
- Keep this phase design-only until the user approves the first prototype
  scope.

## Phase 3: Rust Private Devnet Prototype

Goal: build a local-only XRIQ node prototype.

- Create a Rust workspace for the XRIQ prototype.
- Build minimal crates for:
  - core types
  - transaction validation
  - block validation
  - chain storage
  - mempool
  - node networking or local simulation
  - RPC API
  - CLI.
- Start with deterministic local tests before any networked behavior.
- Keep generated code in Git, but keep chain data, node databases, and testnet
  artifacts out of Git.

## Phase 4: Wallet, Explorer, And Developer Tools

Goal: make the private chain usable without pretending it is production-ready.

- Add a wallet CLI for key generation, signing, balance checks, and transfers.
- Add an explorer API/UI for blocks, transactions, addresses, and chain status.
- Add faucet/devnet tooling for test coins only.
- Add integration tests that run multiple local nodes and verify transfers.

## Phase 5: Security, Compliance, And Launch Readiness

Goal: decide whether XRIQ should move beyond private testing.

- Require security review before public exposure.
- Require legal/compliance review before any token sale, exchange listing,
  public distribution, custody, exchange, payment, or investment-related use.
- Add monitoring, incident response, backup/restore, release signing, and
  upgrade procedures.
- Keep public launch as an explicit separate decision, not a default next step.

## BIBER Model Improvement Loop For XRIQ

Use this loop only when XRIQ/Rust evals show real gaps:

1. Add failing Rust/XRIQ prompt to a held-out eval set.
2. Add approved, provenance-tracked Rust training examples.
3. Validate data before training.
4. Run QLoRA on Vast.ai in `tmux`.
5. Serve the new adapter under a versioned path.
6. Compare Rust/XRIQ evals against the prior adapter.
7. Promote only if the new adapter improves without regressing the broad
   baseline.

Do not run new GPU fine-tuning for other language tracks before this Rust/XRIQ
loop is established, unless the user changes the product priority. After this
track is stable, use the ordered roadmap in `docs/BIBER_CAPABILITY_ROADMAP.md`.
