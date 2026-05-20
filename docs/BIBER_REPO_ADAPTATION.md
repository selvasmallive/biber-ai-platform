# BIBER Repo Adaptation

Use this workflow when BIBER needs to become better for a specific GitHub repo.
The default path is deliberately conservative:

1. Use repo context first.
2. Run repo-specific eval prompts.
3. Collect repeated failures and reviewed fixes.
4. Fine-tune a candidate adapter on Vast only when the eval gap is repeatable.
5. Promote only if the candidate beats the current served adapter.

Do not blindly fine-tune on a whole repository. Private repos may contain
secrets, generated files, vendored dependencies, build artifacts, or code that is
not useful training signal.

## Build An Adaptation Plan

```bash
python training/repo_adaptation_plan.py \
  --repo-root /path/to/github/repo \
  --output /workspace/outputs/repo-adaptation-plan.json \
  --eval-prompts-output /workspace/outputs/repo-adaptation-eval-prompts.jsonl
```

The plan contains metadata only: selected file paths, hashes, language counts,
role counts, skip reasons, and suggested eval prompts. It does not copy source
code into the plan.

Use the default `basic` prompt mode for quick smoke checks. Use expanded mode
when collecting more repo-adaptation signal before any fine-tune:

```bash
python training/repo_adaptation_plan.py \
  --repo-root /path/to/github/repo \
  --output /workspace/outputs/repo-adaptation-plan-expanded.json \
  --eval-prompts-output /workspace/outputs/repo-adaptation-eval-prompts-expanded.jsonl \
  --prompt-mode expanded \
  --max-prompts 24
```

Expanded mode balances selected files by language/role group before repeating
variants, then emits implementation, context-selection, regression-test, and
risk/verification prompts. This keeps early eval batches from becoming
Python-only when Rust, docs, shell, SQL, and other supported files are present.

The scanner skips common unsafe or noisy paths, including `.git`, `.env`,
private-key-looking files, build outputs, `node_modules`, Rust `target`, binary
archives, and files whose contents look like secrets.

## Run The Repo-Specific Eval

After generating the prompt JSONL, run it against the currently served BIBER
model before considering fine-tuning:

```bash
python training/repo_adaptation_eval.py \
  --prompts /workspace/outputs/repo-adaptation-eval-prompts.jsonl \
  --base-url http://127.0.0.1:8000 \
  --env-file /workspace/biber-ai-platform/.env \
  --output /workspace/outputs/evals/repo-adaptation-results.jsonl \
  --summary /workspace/outputs/evals/repo-adaptation-summary.json \
  --failures-output /workspace/outputs/evals/repo-adaptation-failures.jsonl
```

On the direct Vast deployment, use the wrapper script:

```bash
cd /workspace/biber-ai-platform
bash scripts/vast_eval_repo_adaptation_direct.sh
```

The eval wrapper writes full results, a compact summary, and a failures JSONL.
Use the failures file as a review queue. Do not fine-tune from it directly; keep
only repeated, reviewed failures as curated training examples.

## Review Repeated Failures

Convert repeated eval failures into a compact human review queue before creating
training data. The helper groups matching failures by prompt and missing
expectations, marks runtime/API errors as blocked, and can write candidate JSONL
records that are intentionally marked `quality: needs_review`.

```bash
python training/repo_adaptation_failure_review.py \
  --failures /workspace/outputs/evals/repo-adaptation-failures.jsonl \
  --review-output /workspace/outputs/evals/repo-adaptation-failure-review.json \
  --training-candidates-output /workspace/outputs/evals/repo-adaptation-training-candidates.jsonl \
  --min-repeats 2
```

The candidate file is not a training dataset yet: `output` is left empty so the
dataset validator rejects it until a reviewer writes the verified answer or
patch and changes the quality to `reviewed` or `verified`.

Before promoting reviewed rows to any training dataset, check the candidate
queue explicitly:

```bash
python training/repo_adaptation_candidate_review.py \
  --candidates /workspace/outputs/evals/repo-adaptation-training-candidates.jsonl \
  --review-output /workspace/outputs/evals/repo-adaptation-candidate-review.json \
  --min-ready 1
```

This review only reports readiness for dataset validation. It does not start
training, mark a dataset as trainable, or promote an adapter.

When a reviewer approves a candidate, apply that decision through a separate
decision file so the output and reviewer metadata are auditable:

```bash
python training/repo_adaptation_candidate_decisions.py \
  --candidates /workspace/outputs/evals/repo-adaptation-training-candidates.jsonl \
  --decisions /workspace/outputs/evals/repo-adaptation-candidate-decisions.json \
  --output /workspace/outputs/evals/repo-adaptation-reviewed-candidates.jsonl \
  --review-output /workspace/outputs/evals/repo-adaptation-candidate-decisions.review.json
```

Then rerun `repo_adaptation_candidate_review.py` against the reviewed output.
Even a passing candidate review only means the rows are ready for dataset
validation; it is still not approval to start training.

After validation passes, merge reviewed rows into a cumulative curated queue
instead of training from a tiny one-off artifact:

```bash
python training/repo_adaptation_dataset_merge.py \
  --candidates /workspace/outputs/evals/repo-adaptation-reviewed-candidates.jsonl \
  --output /workspace/data/repo_adaptation/reviewed_candidates.jsonl \
  --review-output /workspace/outputs/evals/repo-adaptation-dataset-merge.review.json \
  --min-total-records 1
```

This merge is idempotent and keeps `training_allowed`, `safe_to_train`, and
`approved_for_training` false. Treat the curated queue as accumulation only;
start training later only after enough reviewed examples exist and the user
explicitly approves a training run.

Before asking for a training run, write a readiness report for the cumulative
queue:

```bash
python training/repo_adaptation_dataset_readiness.py \
  --dataset /workspace/data/repo_adaptation/reviewed_candidates.jsonl \
  --review-output /workspace/outputs/evals/repo-adaptation-dataset-readiness.review.json \
  --min-records 50 \
  --min-categories 4
```

The readiness report can say that manual training review is required after the
queue is large and diverse enough, but it still keeps `training_allowed`,
`safe_to_train`, and `approved_for_training` false. A separate explicit user
approval is required before any Vast training job.

After readiness reaches `manual_training_review_required`, create a manual
pre-training review artifact. This summarizes provenance, duplicates,
category balance, prompt variants, and the suggested training command, but it
still does not approve or start training:

```bash
python training/repo_adaptation_training_review.py \
  --dataset /workspace/data/repo_adaptation/reviewed_candidates.jsonl \
  --review-output /workspace/outputs/evals/repo-adaptation-manual-training-review.json \
  --min-records 50 \
  --min-categories 4 \
  --output-dir /workspace/adapters/biber-dev-core-repo-adapt-manual-review \
  --session-name biber-repo-adapt-review
```

Only after this artifact says `ready_for_user_training_approval` should a future
session ask the user for explicit approval to launch the separate Vast GPU
training job. Do not infer approval from a generic "continue" message. The
tmux training launcher refuses to start unless `BIBER_TRAIN_APPROVED=1` is set
in the same command after explicit user approval.

## Codex Mentor Role

Codex/OpenAI should be used for:

- reviewing the adaptation plan,
- deciding which failures are worth turning into training records,
- reviewing curated JSONL examples,
- improving eval prompts, and
- deciding whether a candidate adapter should be promoted.

Codex/OpenAI should not be used inside the training loop. Training, batch evals,
and adapter comparison should run on Vast.

## Promotion Rule

Keep serving the current stable adapter unless the candidate:

- passes the broad BIBER eval,
- improves the repo-specific held-out eval by at least the configured margin
  over the stable baseline; the default margin is `5` expectation checks,
- does not regress Rust/XRIQ prompts,
- loads cleanly through vLLM, and
- has its dataset/provenance recorded.
- is a different adapter path than the current stable adapter.

After a candidate training run and evals complete, write a promotion-review
artifact before leaving the candidate served:

```bash
BIBER_CANDIDATE_ADAPTER_DIR=/workspace/adapters/biber-dev-core-repo-adapt-candidate \
  bash scripts/vast_review_candidate_adapter_direct.sh
```

The wrapper refuses to run when the candidate path is the same as the stable
adapter path, unless `BIBER_ALLOW_STABLE_AS_CANDIDATE=1` is set for an explicit
smoke test. It restores the stable adapter by default. It runs the baseline
repo-held-out eval, candidate broad eval, candidate Rust/XRIQ validator eval,
candidate repo-held-out eval, and then writes the promotion-review artifact.
The wrapper stops and restarts the local services when switching between the
stable and candidate adapter so vLLM actually loads the intended LoRA.

You can also write the promotion review directly when the eval summaries
already exist:

```bash
python training/adapter_promotion_review.py \
  --candidate-adapter /workspace/adapters/biber-dev-core-repo-adapt-candidate \
  --training-review /workspace/outputs/evals/repo-adaptation-manual-training-review.json \
  --broad-summary /workspace/outputs/evals/candidate-broad.summary.json \
  --rust-summary /workspace/outputs/evals/candidate-rust-xriq.summary.json \
  --repo-summary /workspace/outputs/evals/candidate-repo-heldout.summary.json \
  --baseline-repo-summary /workspace/outputs/evals/stable-repo-heldout.summary.json \
  --review-output /workspace/outputs/evals/candidate-promotion-review.json
```

This helper is validation-only. It never restarts serving, never promotes an
adapter, and keeps `promotion_allowed`, `safe_to_promote`, and `auto_promoted`
false. If every gate passes, it only marks the candidate
`ready_for_user_promotion_approval`; a separate explicit user approval is still
required before keeping the candidate served.
