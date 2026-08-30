# BIBER Azure DevOps Conference Submission

Use this as paste-ready source for Sessionize or similar CFP forms. Keep claims
aligned with the current MVP: private AI-assisted Azure DevOps review with
bounded diffs, safe defaults, and a swappable BIBER model API.

## Session Title

BIBER AI: Private Code Review for Azure DevOps with Swappable Local Models

## Short Abstract

BIBER AI demonstrates a practical way to bring private AI-assisted code review
into Azure DevOps without starting with a giant autonomous agent platform. The
demo reviews pull request and commit diffs through a BIBER OpenAI-compatible
API, keeps model providers swappable, redacts secret-like values, publishes
review artifacts, and enables PR comments only after a dry-run review is
accepted.

## Long Abstract

Many teams want AI help during code review, but they also want stronger control
over cost, model choice, and how much repository context leaves their
environment. This session walks through the BIBER AI Azure DevOps MVP: a narrow
review workflow that gathers a bounded git diff, redacts secret-like values,
calls a private BIBER model-source API, publishes Markdown/JSON review
artifacts, and optionally posts one Azure DevOps PR thread after a dry-run gate.

The talk focuses on practical engineering decisions rather than theoretical
multi-agent architecture. Attendees will see how the same review contract can
work as an Azure Pipeline script, a packaged Azure DevOps task, and a browser
panel inside Azure DevOps. The design keeps OpenAI mentor review optional and
disabled by default, keeps training separate from normal review traffic, and
lets BIBER swap local model providers behind `/v1/models` and
`/v1/chat/completions`.

The goal is not to claim production readiness on day one. The goal is to show a
credible path from one trusted workflow to a private AI engineering platform:
bounded context first, human review gates first, then future repository RAG,
safer multi-file edit loops, and orchestration.

## Speaker Bio

Selva Vadivel is a software builder and founder at Flat Electronics Canada
Limited, focused on practical AI tools for software engineering, secure
application delivery, and developer productivity. Selva is building BIBER AI as
a private, swappable-model assistant that can support engineering workflows
without forcing every step through a public AI service.

## Audience

This session is for software engineers, DevOps engineers, engineering managers,
and AI builders who use Azure DevOps or want a private-first pattern for AI
code review.

## Attendee Takeaways

- How to design a narrow AI review workflow before building a broad agent
  system.
- How BIBER uses an OpenAI-compatible API while keeping model providers
  swappable.
- How to keep early AI review safer with bounded diffs, redaction, dry-run
  artifacts, and human approval gates.
- How an Azure DevOps extension can combine a browser panel and pipeline task.
- What still belongs in later phases: full repository RAG, durable quotas,
  audit logs, multi-agent orchestration, and production governance.

## Demo Outline

1. Show the BIBER Azure DevOps review architecture.
2. Run the local validation gates.
3. Open the Azure Pipeline PR review sample in dry-run mode.
4. Review the generated Markdown artifact.
5. Show the commit-review artifact path for post-commit inspection.
6. Open the Azure DevOps extension panel.
7. Paste a user-scoped API key and click `Test Connection`.
8. Generate a BIBER review from a small bounded diff.
9. Explain when `commentMode=post` can be enabled for a test PR.
10. Close with the roadmap from review to repo RAG and orchestration.

## Demo Safety Notes

- Use fake secret-like values only.
- Keep `commentMode=dry-run` for the first pipeline run.
- Do not use admin keys in pipeline variables.
- Do not enable OpenAI mentor review during the default demo.
- Do not claim full repository understanding from a bounded-diff review.
- Keep public production claims out of the talk until quotas, audit logs,
  abuse controls, monitoring, and incident procedures exist.

## Supporting Repo Files

```text
docs/BIBER_AZURE_DEVOPS_CONFERENCE_TALK.md
docs/BIBER_AZURE_DEVOPS_DEMO_RUNBOOK.md
docs/BIBER_AZURE_DEVOPS_LIVE_DRY_RUN.md
docs/BIBER_AZURE_DEVOPS_PRIVATE_PUBLISH.md
examples/azure_devops_pipeline/biber-ai-pr-review.yml
examples/azure_devops_pipeline/biber-ai-commit-review.yml
examples/azure_devops_pipeline/biber-ai-extension-task-pr-review.yml
examples/azure_devops_extension/
```
