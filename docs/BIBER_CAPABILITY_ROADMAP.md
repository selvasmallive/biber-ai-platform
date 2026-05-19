# BIBER Capability Roadmap

This roadmap defines the order in which BIBER AI should improve inference
capability across languages, frameworks, infrastructure, and security domains.
The goal is to use the user's Vast.ai GPU for long-running evaluation and
fine-tuning work while using Codex only as needed for planning, scripts, code
changes, review, and handoff updates.

## Cost-Saving Operating Model

- Use BIBER AI through inference first.
- Treat `docs/BIBER_AGENT_API_AND_MENTOR_STRATEGY.md` as the source of truth
  for the future BIBER API-key agent-client path and OpenAI/Codex mentor usage.
- Add eval prompts and executable validators before adding new training data.
- Use the Vast.ai GPU for batch evals, QLoRA fine-tuning, and adapter serving.
- Run long jobs in `tmux` under `/workspace` so Codex does not need to stay
  active while the GPU works.
- Use Codex for quality-maintaining work: eval design, script changes, failure
  diagnosis, result interpretation, docs, and small targeted patches.
- Keep datasets, raw downloads, toolchains, checkpoints, adapters, logs, and
  eval outputs under `/workspace` on the 500 GB Vast volume.
- Do not overwrite known-good adapters. Save each trained adapter under a
  versioned path and promote only after eval comparison.
- Fine-tune only when evals show repeatable gaps or the user explicitly chooses
  a domain as the next product priority.

## Cross-Cutting MVP Workflow Priorities

Before broad language expansion, improve the reusable agent workflows that make
BIBER a practical lower-cost Replit alternative:

1. Reliable repo-context selection across stacks.
2. Safe multi-file edit planning and patch application.
3. Structured test-failure diagnosis and targeted retry loops.

These workflow capabilities should serve every language below. Add stack
specific details gradually, starting with the user's highest-value development
paths and the existing Rust/XRIQ work.

## Priority Order

1. Rust/XRIQ cryptocurrency blockchain development.
2. PostgreSQL.
3. React.
4. TypeScript.
5. JavaScript.
6. jQuery.
7. CSS.
8. HTML.
9. Docker.
10. GitHub Actions for CI/CD.
11. WebAssembly/WASM.
12. Bash scripts.
13. Security engineering.
14. Cryptography concepts.
15. Kubernetes.
16. Distributed systems optimization.
17. Other lower-priority languages and config formats, including generic SQL,
    YAML, .NET, Spring Boot Java, Python expansion, and additional stacks as
    requested later.

## Capability Loop For Each Priority

For each stack or domain, use the same controlled loop:

1. Add held-out eval prompts for the target capability.
2. Add executable validators when practical.
3. Run inference-only evals against the current live adapter.
4. Review failures and classify them as model gaps, prompt/eval issues, or
   project-design issues.
5. Add approved, provenance-tracked targeted data only for repeatable model
   gaps.
6. Run bounded QLoRA training on Vast.ai in `tmux`.
7. Serve the new adapter under a versioned path.
8. Compare against the target eval and the broad regression baseline.
9. Promote only if the new adapter improves the target without unacceptable
   regression.

## Current Resource Fit

The current Vast.ai setup is suitable for this roadmap when used as a staged
LoRA/QLoRA and inference platform:

- serving the current 7B coding model with a LoRA adapter
- running focused eval batches
- building multiple small targeted datasets
- training versioned LoRA/QLoRA adapters
- storing several adapters, datasets, toolchains, logs, and eval outputs under
  `/workspace`

The current setup is not intended for:

- training a full foundation model from scratch
- large multi-user production serving
- very large raw datasets without pruning
- many large checkpoints kept forever
- much larger models that require substantially more GPU memory

As of the last confirmed check, `/workspace` was a 499 GB volume with about
470 GB available after installing the Rust toolchain and training the first
Rust/XRIQ adapter. That is enough for many targeted capability loops, as long as
old failed checkpoints and unnecessary raw artifacts are cleaned up deliberately.
