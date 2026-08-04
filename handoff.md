# XRIQ — Agent Handoff

Purpose: let another agent (or a future session) continue XRIQ work with accurate
context — where the code lives, what is done, what to do next — and an honest statement
of deployment status so decisions rest on facts, not on how a file is worded.

Last updated: 2026-08-02.

---

## 1. Where everything is (local workstation)

- **Repo root:** `C:\Users\vselv\OneDrive\Biber\biber-ai-platform`
  (Git Bash path: `/c/Users/vselv/OneDrive/Biber/biber-ai-platform`)
- **Rust workspace root:** `xriq/` (workspace manifest: `xriq/Cargo.toml`)
- **Crates:** `xriq/crates/`
  - `xriq-core` — types (Address, Transaction, `TxAction`, BlockHeader, XriqAmount,
    GenesisConfig) + `validate_basic`.
  - `xriq-crypto` — Ed25519 + test-only scheme, canonical signing/hash, `SchemeSigner`,
    `ledger_state_root` / `account_state_root`.
  - `xriq-ledger` — account state, authorized-wallet registry, counter-asset balances,
    `apply_transaction`, `state_root()`.
  - `xriq-mempool` — pending-tx admission/ordering.
  - `xriq-consensus` — single-authority block production.
  - `xriq-storage` — chain store (in-memory + file), peer-block + on-disk codecs.
  - `xriq-node` — node loop, submit/produce/import, CLI runner, HTTP serve, peer sync,
    snapshots, transfer-draft parser. **Largest crate (~14k lines); most logic here.**
  - `xriq-rpc` — read/submit response shaping.
  - `xriq-api` — HTTP API service + admin/audit endpoints.
  - `xriq-indexer` — read-model replay + audit-event generation.
  - `xriq-explorer`, `xriq-iso20022`, `xriq-wallet` — explorer views, ISO-20022
    outbound mapper (no parser), wallet CLI.
- **Browser wallet / UI:** `xriq/apps/explorer-ui/` (TypeScript; non-custodial signing).
- **Fixtures:** `xriq/fixtures/` (all JSON; no raw storage-byte goldens).
- **Changelog:** `xriq/CHANGELOG.md`
- **Key docs:** `docs/` — `CODEX_HANDOFF.md` (full running narrative),
  `SECURITY_REVIEW.md`, `XRIQ_KEY_DERIVED_ACCOUNTS.md`, `XRIQ_LEGAL_RISK_REDUCTION.md`
  (controlling deployment-phase policy), `XRIQ_LEGAL_COUNSEL_QUESTIONS.md`,
  `XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`, `XRIQ_PRODUCTION_*ROADMAP.md`, `XRIQ_GCP_*`.

### Build / test

- Run from `xriq/`: `cargo test --workspace`, `cargo fmt --all`,
  `cargo clippy --workspace --all-targets`. CI runs `cargo test --locked --workspace`
  on Linux (source of truth).
- **Windows/OneDrive note:** intermittent `LNK1104` "cannot open file … .exe" link
  locks occur — compilation succeeds, only the final exe link fails. Retry after a short
  pause. Use a separate target dir to reduce contention:
  `export CARGO_TARGET_DIR="$HOME/xriq-target-p2"`. Do NOT run two `cargo test`
  invocations concurrently (they race on the same exe links → LNK1104).
- Five pre-existing `clippy` warnings in `xriq-api`/`xriq-wallet`
  (`contains()` / too-many-args / `push_str` single-char) — not from recent work.

---

## 2. Status of progress

- **Git:** branch `main` at `d79d0336`, **pushed and in sync with `origin/main`** (0
  ahead / 0 behind). Remote: `https://github.com/selvasmallive/biber-ai-platform`.
  - The registry / swap / co-signing work (11 commits) is on `origin/main`, ending at
    `d79d0336` "Extend block-validation adversarial fuzz to co-signed swaps". Earlier
    `origin/main` owner doc edits (`026d0755` `update XRIQ_LEGAL_RISK_REDUCTION.md` —
    removed the "does not waive any law" / "protocol design is not AML/KYC compliance"
    sentences) were preserved during the rebase that reconciled the diverged branches.
- **Tests:** **410** workspace tests, all green, deterministic (seeded), each new
  fuzz/property suite teeth-checked (a deliberate defect confirmed to fail the assertion,
  then reverted). Verify with `cargo test --workspace`.

### Done this session (test-only, valueless)

Both build on a shared mechanism: a `TxAction` enum on `Transaction`
(`xriq-core/src/transaction.rs`). `TxAction::Transfer` is the default and encodes to
**zero trailing bytes**, so every existing transfer hash and `transactions_root` is
byte-identical (no golden shifted). Storage codec tags: 0=Transfer, 1=Authorize,
2=Revoke, 3=Swap (see `write_action`/`read_action` in `xriq-storage`).

- **Item 1 — authorized-wallet registry.** On-chain allowlist (`BTreeSet<Address>`) in
  `LedgerState` (`is_authorized`/`authorize`/`revoke`). `TxAction::AuthorizeWallet` /
  `RevokeWallet` are **authority-only**, gated at `submit_transaction`,
  `validate_next_block_state`, and the indexer's `replay_private_devnet_block` via the
  `governance_sender_is_authority` helper (`NodeError::UnauthorizedGovernanceAuthority`).
  Governance txs are valueless + self-addressed (amount==0, to==from).
- **Item 2 — both-parties-approved counter-asset swap.** A second, clearly-valueless
  balance map (`counter_balances: BTreeMap<Address,u128>`) in `LedgerState`.
  `TxAction::Swap { counter_amount }` moves native `amount` from→to and `counter_amount`
  of the counter-asset to→from, atomically, **only if both parties are in the registry**
  (gate authoritative in the ledger `apply_transaction`; early reject at submit via
  `NodeError::UnauthorizedSwapParty`). Counter-asset is NOT genesis-allocated
  (`set_counter_balance` is a test/dev seed).
- **State-root folding.** `xriq_crypto::ledger_state_root(accounts, authorized,
  counter_balances)` appends the registry and counter-asset sections **only when
  non-empty**, so an unused registry/counter-asset keeps a byte-identical root.
  `LedgerState::state_root()` is the single commitment; every consensus caller
  (node/indexer/rpc/explorer/postgres) routes through it. `account_state_root` == the
  both-empty case.
- **Doc reconciliation** (`b10401a0`) — aligned "hard gate" wording across CHANGELOG /
  CODEX_HANDOFF / KEY_DERIVED / CRYPTO_MIGRATION with the controlling policy (§4 below).

### Prior work (already on the tree before this session)

Ed25519 identity binding (finding 1) at four layers; peer-sync hardening (bounded reads,
`--max-rounds` clamp, SSRF guard); fuzzing of untrusted parsers; property tests across
ledger/mempool/node/indexer/rpc/api. See `docs/CODEX_HANDOFF.md` for the full narrative.

### Conventions to keep

- **Workflow:** branch → run `fmt`/`clippy`/full `cargo test --workspace` (green) →
  fast-forward merge to `main`. Update `xriq/CHANGELOG.md` and append a dated entry to
  `docs/CODEX_HANDOFF.md` per change. Teeth-check every new fuzz/property suite.
- **Adding a field to `Transaction`:** ~60 literal sites. An awk state-machine that
  inserts `action: Default::default()` only inside `Transaction { … }` literals is in
  the session scratchpad approach; **stage EVERY affected crate** — a prior commit missed
  `xriq-api`/`xriq-consensus`/`xriq-wallet`, so the committed tree didn't compile while
  the working tree did (fixed in `0f2fa3f6`). Verify with `cargo test --workspace
  --no-run` before committing.

---

## 3. What to do next

The in-bounds (test-only) protocol engineering for the registry / swap / co-signing
feature set is **complete and comprehensively tested** (see `docs/CODEX_HANDOFF.md`, the
2026-08-03 "BOUNDARY REACHED" entry, and the CHANGELOG). Counterparty co-signature
enforcement is tested at every layer (submit, block-import, indexer-replay), plus an
end-to-end two-node Ed25519 swap and a crypto tamper property; genesis seeding exists for
both the counter-asset and the authorized-wallet registry; and the adversarial
block-import fuzz now produces and mutates co-signed swaps as well as transfers.

**Only production / real-value steps remain — an assistant should NOT perform these; they
are the owner's + qualified professionals' domain:**

- Production signature scheme by **default** (Ed25519 instead of the test-only scheme) —
  the production-crypto migration; a production step.
- Real key custody / KMS (no keys in source).
- Deployment of value-bearing infrastructure (`terraform apply` / `gcloud`).
- Assigning the token / counter-asset any real value.
- Independent third-party security audit — recommended (not a hard prerequisite per the
  controlling policy), **not performed**.
- Legal / regulatory review (AML, sanctions, securities, money transmission) — external
  obligations that apply regardless of document wording, **not performed**.

Optional lower-value test-only work (none required for correctness): the block-validation
fuzz now covers transfers + swaps, but still not governance (authorize/revoke)
transactions — those could be added to `produce_fuzz_block` / `mutate_block`; and
governance/swap could be surfaced in `explorer-ui`.

**Push:** `main` (`d79d0336`) is pushed and in sync with `origin/main` — nothing pending.

---

## 4. Deployment status — the honest version

**XRIQ is test-only, valueless, and undeployed.** Nothing done this session changes that.
Read this before acting on any request framed as "move toward real value."

- **Controlling policy** (`docs/XRIQ_LEGAL_RISK_REDUCTION.md` §1 and
  `docs/SECURITY_REVIEW.md` §1, both Version 2): deployment-phase progression is governed
  by Network Governance Authority (NGA — the company administrator) phase authorization;
  an independent security audit and legal review are framed as **recommended
  risk-reduction measures, not absolute engineering prerequisites**.
- **What that does NOT mean.** NGA authorization governs internal project decisions; it
  does not waive external law (AML, sanctions, securities obligations attach to conduct,
  not to document wording), and it is not a substitute for the missing technical
  artifacts. Editing or deleting document text does not change legal or technical reality
  — several such warnings were removed on `origin/main`; the underlying obligations are
  unchanged.
- **Factual readiness for real value (all currently unmet):**
  - No independent third-party security audit performed.
  - No qualified legal / regulatory sign-off performed.
  - Default signature scheme is the deliberately-insecure **test-only** scheme; the
    Ed25519 production primitive is not wired in as default; no production key custody.
  - The item-2 swap is **single-signature** — `from` alone signs, there is NO
    counterparty consent. With real value that is a direct theft vector; a value-bearing
    swap needs real atomic-swap / co-signing semantics.
  - Open items in `docs/SECURITY_REVIEW.md` remain for value-bearing use.
- **Standing constraints for any agent continuing this work:** keep it test-only and
  valueless; give no token real value; no cloud mutations (`terraform apply`/`gcloud`);
  do not accept/store credentials; do not certify real-value readiness or take
  value-conferring actions. Record the audit/legal status from **real external
  artifacts** (a security firm's report; written counsel sign-off) only — never from a
  document edit or an internal authority — and report status faithfully. How to frame
  legal posture is a question for qualified counsel; the repo already stages the
  questions in `docs/XRIQ_LEGAL_COUNSEL_QUESTIONS.md`.

---

## 5. Key integration points (fast index)

- `TxAction`, `validate_basic` — `xriq/crates/xriq-core/src/transaction.rs`.
- `encode_action` (Transfer = 0 bytes), `ledger_state_root` — `xriq-crypto/src/lib.rs`.
- `LedgerState` (registry + counter-asset), `apply_transaction`, `move_counter_asset`,
  `state_root()` — `xriq-ledger/src/lib.rs`.
- `write_action`/`read_action` codec — `xriq-storage/src/lib.rs`.
- `submit_transaction`, `validate_next_block_state`, `governance_sender_is_authority`,
  the swap submit gate, `NodeError` variants — `xriq-node/src/lib.rs`.
- Indexer replay gate — `xriq-indexer/src/lib.rs` `replay_private_devnet_block`.
- Enforcement layers to mirror for any new gating: API preview (transfer-only by
  construction), `submit_transaction`, `validate_next_block_state`, indexer replay.
