# BIBER Azure DevOps Conference Talk Source

This is the slide-ready source for a roughly 45-minute technical session about
the BIBER Azure DevOps review demo. It exists because `.pptx` export is blocked
until Codex has access to the presentation artifact runtime.

## Communication Job

By the end, software teams should understand that BIBER can review Azure DevOps
PR and commit changes through a private, swappable model API, giving teams a
lower-cost and more controllable AI review path before public-cloud mentor
review is introduced.

## Session Title

BIBER AI: Private Code Review for Azure DevOps with Swappable Local Models

## Abstract

This session demonstrates a practical AI engineering workflow that reviews
Azure DevOps pull request and commit changes using a private BIBER model
endpoint. Instead of starting with a complex multi-agent system, the demo
focuses on one valuable workflow: collect a bounded diff, redact secrets, call
an OpenAI-compatible local-model API, publish a review artifact, and optionally
post a pull request comment. The design keeps model providers swappable, keeps
OpenAI mentor review optional, and gives teams a realistic path from local GPU
inference to future enterprise governance.

## Slide Plan

1. Private AI review should start with one useful workflow
   - BIBER focuses first on PR/commit review because it has a clear input,
     output, and human approval loop.
   - Speaker note: Open with the practical need: teams want AI help without
     sending every repository detail directly to a public assistant.

2. The conference demo is deliberately narrow
   - Azure Pipeline collects a bounded diff.
   - BIBER reviews it through `/v1/chat/completions`.
   - The first PR run produces artifacts before posting comments.
   - The commit lane publishes artifacts only.
   - Speaker note: Emphasize that a narrow demo is easier to trust than a broad
     agent that can mutate code immediately.

3. The architecture separates review, model execution, and posting
   - Azure DevOps pipeline task: gathers change context.
   - BIBER API: routes to the selected local model.
   - PR thread posting: opt-in after artifact review.
   - Speaker note: This is the core architecture diagram slide.

4. BIBER speaks an OpenAI-compatible model-source API
   - Existing clients can call `/v1/models` and `/v1/chat/completions`.
   - The implementation can swap Qwen2.5, Qwen3, or later providers behind the
     same API contract.
   - Speaker note: This is the cost and model agility story.

5. The default review path avoids risky automation
   - OpenAI mentor is disabled.
   - Training is disabled.
   - Comment posting defaults to `dry-run`.
   - Speaker note: The goal is assistant review, not automatic merge approval.

6. The pipeline sends less code than a full repository upload
   - Only a bounded, redacted diff is sent.
   - Changed paths are included as metadata.
   - Secret-like values are redacted before model review.
   - Speaker note: Be honest that diff review is not full repo understanding;
     full repo RAG is a later capability.

7. Azure DevOps is a good first enterprise demo surface
   - Pull request review is a familiar workflow.
   - Pipeline artifacts are easy to inspect.
   - PR comments create visible value quickly.
   - The same flow can be shown as a repo-local script or installed extension
     task.
   - Speaker note: This is why Azure DevOps is better for the conference demo
     than starting with a custom app.

8. The extension panel proves the UI direction
   - A `BIBER AI Review` hub can call the same API from the browser.
   - CORS stays disabled until the public panel path is intentionally enabled.
   - API keys are not stored in the extension scaffold.
   - Speaker note: Position the panel as an MVP, not a complete product.

9. Server-side protections matter more than client-side promises
   - Keep BIBER API guards enabled.
   - Use Cloudflare/WAF or equivalent public-edge controls.
   - Add durable quotas and audit logs before broad release.
   - Speaker note: Client rate limits are useful UX, not a security boundary.

10. What the demo can show live
    - Run a PR build.
    - Review the `biber-ai-review.md` artifact.
    - Run a commit-review build if PR permissions are unavailable.
    - Use the offline demo bundle if the venue network or Azure DevOps is
      unavailable.
    - Switch to a test PR comment only after dry-run acceptance.
    - Speaker note: Have a prepared diff with one correctness issue and one
      redacted secret-like value.

11. What the demo should not claim yet
    - It is not a production SOC2-ready gateway.
    - It is not full repository RAG yet.
    - It is not autonomous multi-file editing in Azure DevOps yet.
    - Speaker note: The credibility comes from saying what is not done.

12. The roadmap grows from review into orchestration
    - Better repo-context selection.
    - Safer multi-file edit planning.
    - Test failure diagnosis loops.
    - Optional mentor review for high-risk changes.
    - Speaker note: Tie this back to the BIBER MVP roadmap.

13. Why swappable models are central
    - Qwen2.5 can run now.
    - Qwen3 or stronger models can be evaluated later.
    - The client and pipeline should not depend on one model family.
    - Speaker note: Model upgrades should improve capability without breaking
      the agent workflow contract.

14. Cost control is an architectural feature
    - Use local GPU inference for routine review.
    - Use Codex/OpenAI mentor only for planning, review, or difficult failures.
    - Keep training separate from normal development loops.
    - Speaker note: This is the long-term savings story.

15. The MVP validation contract is already testable
    - Azure DevOps review smoke checks extension files, CORS config, redaction,
      dry-run behavior, and no mentor/training calls.
    - The broader BIBER confidence smoke now includes the Azure DevOps path.
    - Speaker note: Mention that demos fail less when the demo itself has
      regression tests.

16. The next release should stay practical
    - Package the extension privately.
    - Share the private Azure DevOps extension only with the demo organization.
    - Run a private Azure Pipeline dry-run.
    - Add a push/commit artifact demo for audit-style review.
    - Add one controlled PR comment demo.
    - Speaker note: Close with the idea that a useful platform is built from
      small trusted workflows.

## Live Demo Script

Use `docs/BIBER_AZURE_DEVOPS_DEMO_RUNBOOK.md` as the operator checklist.

1. Open an Azure DevOps pull request with a small intentional bug.
2. Run `npm run validate` and `npm run validate:panel` locally to show the
   extension/package and browser-panel behavior gates.
3. Run the sample pipeline with `commentMode=dry-run`.
4. Open the published Markdown artifact and point out the summary, risk level,
   tests, and merge recommendation.
5. Optionally run the commit-review pipeline and open
   `biber-ai-commit-review.md` as an audit-style artifact.
6. Show that secret-like values were redacted.
7. Open the `BIBER AI Review` extension panel and run the same bounded diff
   manually.
8. Optionally rerun the test PR with `commentMode=post` to create one PR
   thread.
9. If the live path is unavailable, open the latest
   `outputs/biber-azure-devops-offline-demo-*` bundle and show the same artifact
   shape with no live API request.
10. After private extension install, show the
    `biber-ai-extension-task-pr-review.yml` pipeline invoking
    `BiberAiPrReview@1`.

## Speaker Notes For Hard Questions

- Full repository RAG is not done yet. The current demo is intentionally a
  bounded-diff review path.
- The local model can be replaced because the API contract is OpenAI-compatible
  and model metadata is served separately.
- The first public API deployment still needs production-grade key storage,
  quotas, audit logging, abuse detection, and operational monitoring.
- OpenAI mentor review remains optional and disabled by default to control
  cost and preserve the private-first story.

## Source Notes

- Azure DevOps extension manifests use `vss-extension.json` to declare package
  identity, targets, files, and contributions:
  https://learn.microsoft.com/en-us/azure/devops/extend/develop/manifest
- Azure DevOps custom build tasks use `task.json` to describe inputs and
  execution scripts:
  https://learn.microsoft.com/en-us/azure/devops/extend/develop/integrate-build-task
- Azure DevOps PR comments can be added by creating a pull request thread:
  https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-threads/create
- The Azure Pipelines task schema currently includes `Node20_1` as a supported
  execution handler:
  https://github.com/microsoft/azure-pipelines-task-lib/blob/master/tasks.schema.json

## PPTX Status

Actual PowerPoint generation is blocked until Codex can access the presentation
artifact runtime paths normally supplied by `load_workspace_dependencies`:
`RUNTIME_NODE`, `RUNTIME_NODE_MODULES`, and `RUNTIME_BIN_DIR`. Do not create the
deck with `python-pptx`; the required presentation workflow uses
`@oai/artifact-tool`.
