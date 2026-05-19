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

The scanner skips common unsafe or noisy paths, including `.git`, `.env`,
private-key-looking files, build outputs, `node_modules`, Rust `target`, binary
archives, and files whose contents look like secrets.

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
- improves the repo-specific held-out eval,
- does not regress Rust/XRIQ prompts,
- loads cleanly through vLLM, and
- has its dataset/provenance recorded.
