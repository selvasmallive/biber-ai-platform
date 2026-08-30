# BIBER Azure DevOps Extension MVP

This is the conference-demo path for showing BIBER as a private AI code review
assistant inside Azure DevOps.

## What It Does Now

- Collects a bounded local git diff in an Azure Pipeline.
- Redacts secret-like values before sending context to BIBER.
- Calls the BIBER OpenAI-compatible `/v1/chat/completions` endpoint.
- Keeps OpenAI mentor disabled by default with `use_mentor=false`.
- Produces a Markdown PR review artifact.
- Can post one Azure DevOps PR thread only when `commentMode=post` and the
  pipeline has `$(System.AccessToken)` access.
- Provides a separate commit-review pipeline that publishes artifacts only and
  does not require Azure DevOps PR comment credentials.
- Provides a first `BIBER AI Review` extension panel scaffold.

## Demo Order

1. Run the PR sample pipeline with `commentMode=dry-run`.
2. Inspect the published `biber-ai-review.md` artifact.
3. Run the commit sample pipeline to review the latest pushed commit without
   any Azure PR comment permission.
4. Show the Azure DevOps extension panel and paste a small diff manually.
5. Explain that the same BIBER API can run behind `api.beaverapi.com`, a
   private tunnel, or a future enterprise gateway.
6. Only after a dry-run artifact is accepted, switch `commentMode=post` in a
   test PR so the script posts one top-level PR thread.

## Files

```text
scripts/biber_azure_devops_pr_review.py
scripts/biber_azure_devops_review_smoke.py
examples/azure_devops_pipeline/biber-ai-pr-review.yml
examples/azure_devops_pipeline/biber-ai-commit-review.yml
examples/azure_devops_extension/vss-extension.json
examples/azure_devops_extension/static/index.html
examples/azure_devops_extension/tasks/biber-ai-pr-review/v1/task.json
```

## Pipeline Setup

1. Add the sample YAML from
   `examples/azure_devops_pipeline/biber-ai-pr-review.yml`.
2. Add `BIBER_API_KEY` as a secret pipeline variable.
3. Keep `commentMode` as `dry-run` for the first demo.
4. After the artifact looks good, enable pull request comment posting by
   setting `commentMode` to `post` and allowing scripts to access
   `$(System.AccessToken)`.

For a push/commit-only demo, use
`examples/azure_devops_pipeline/biber-ai-commit-review.yml`. It triggers on
`main` and `master`, checks out the last two commits, reviews the latest commit
diff through the same BIBER script, publishes `biber-ai-commit-review.md`, and
does not pass `$(System.AccessToken)` or post PR comments.

## Extension Setup

The Azure DevOps extension scaffold is intentionally thin. It should package
the pipeline task plus a `BIBER AI Review` hub panel.

For live browser-panel calls to `https://api.beaverapi.com/v1`, configure CORS
on the public BIBER API edge for Azure DevOps origins. The pipeline task does
not need CORS because it calls BIBER from the build agent.

Recommended public-panel CORS environment:

```text
BIBER_CORS_ALLOWED_ORIGINS=https://dev.azure.com
BIBER_CORS_ALLOWED_ORIGIN_REGEX=https://.*\.visualstudio\.com
```

Leave these unset for private pipeline-only demos.

Packaging and Marketplace publish are intentionally a later dependency step.
When ready, install/package with `tfx-cli` from this folder and keep the first
release private:

```bash
cd examples/azure_devops_extension
npm install
npm run validate
npm run validate:panel
npm run validate:pipeline
npm run package
```

Do not enter Marketplace tokens into source files, docs, terminal transcripts,
or training/eval artifacts.

`npm run validate` is a Node-only Marketplace/demo readiness preflight. It
checks the manifest, task metadata, icons, safe defaults, browser-panel storage
rules, client-side redaction, diff budget UI, mock wrapper hooks, and obvious
embedded-secret mistakes without calling BIBER, Azure DevOps, GitHub, OpenAI,
GPU, or external network services.

`npm run validate:panel` is a Node-only browser-panel behavior smoke. It
simulates the panel without Azure DevOps or BIBER, verifies client-side
redaction happens before `fetch`, checks `use_mentor=false`, confirms unsafe
public HTTP URLs do not send requests, and exercises cancel/sample/copy/clear
controls.

`npm run validate:pipeline` is a Node-only readiness preflight for both sample
Azure Pipelines. It checks the PR pipeline uses `commentMode=dry-run`, checks
the commit pipeline uses `commentMode=none`, verifies both publish review
artifacts, confirms `BIBER_API_KEY` is read from the pipeline environment, and
confirms neither path requests mentor review or training.

The repo-level packaging smoke is:

```bash
python scripts/biber_azure_devops_extension_package_smoke.py
```

It may download npm packages the first time. It still sends no BIBER, Azure
DevOps, GitHub, OpenAI mentor, GPU, or training request.

The validated local package path is:

```text
examples/azure_devops_extension/flat-electronics-canada.biber-ai-azure-devops-0.1.0.vsix
```

`npm ci` currently reports audit findings in the dev-only `tfx-cli` dependency
tree. The generated VSIX excludes `node_modules`, but package public releases
from a clean environment and reassess the packaging toolchain before a broad
Marketplace launch.

To test the actual task wrapper entrypoint without Azure DevOps credentials or
a live BIBER API, run:

```bash
npm run validate:wrapper
```

That smoke feeds mock diff/model files through the same Node task wrapper that
the packaged task uses, then verifies the generated review JSON and Markdown.

## Security Contract

- Do not store BIBER user API keys in source control.
- Do not send the raw repository unless a future explicit repo-RAG upload flow
  is reviewed and approved.
- Keep the raw vLLM endpoint private.
- Keep BIBER server-side guards enabled.
- Treat BIBER output as assistant review, not automatic approval.
- Keep comment posting opt-in.

## Local Validation

```bash
npm run validate:contract
```

This smoke uses mock diff/model data. It sends no BIBER request, no Azure
comment request, no GitHub request, no OpenAI mentor request, and no training
request.

## Source Notes

- Azure DevOps extensions are described by a root `vss-extension.json`
  manifest with required fields such as `manifestVersion`, `id`, `version`,
  `publisher`, `targets`, and contributions:
  https://learn.microsoft.com/en-us/azure/devops/extend/develop/manifest
- Custom build tasks are included through `task.json` files that describe
  configuration inputs and the scripts Azure Pipelines executes:
  https://learn.microsoft.com/en-us/azure/devops/extend/develop/integrate-build-task
- PR comments are posted by creating a pull request thread through the Azure
  DevOps Git REST API:
  https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-threads/create
- The current Azure Pipelines task schema includes `Node20_1` execution
  entries:
  https://github.com/microsoft/azure-pipelines-task-lib/blob/master/tasks.schema.json
