# BIBER Azure DevOps Demo Runbook

Use this runbook for the conference-demo path only. It keeps BIBER private-first
and avoids broad automation until the dry-run artifacts are reviewed.

## Demo Goal

Show that BIBER can review Azure DevOps pull request or commit changes through a
private, OpenAI-compatible model-source API, with bounded context, secret
redaction, safe defaults, and optional pull request comments.

## Local Preflight

Run these from the BIBER-only checkout:

```bash
cd examples/azure_devops_extension
npm run validate
npm run validate:panel
npm run validate:pipeline
npm run demo:offline
npm run package
```

When Python is available locally, on CI, or on Vast, also run:

```bash
npm run validate:contract
npm run validate:wrapper
```

Expected local safety posture:

- `npm run validate` passes all publisher-readiness checks.
- `npm run validate:panel` confirms the browser-panel flow redacts secrets
  before fetch, keeps mentor disabled, handles unsafe URLs, and leaves API keys
  session-only.
- `npm run validate:pipeline` confirms the sample pipeline starts in dry-run
  mode, publishes artifacts, and reads the BIBER user key from a secret
  pipeline variable.
- `npm run demo:offline` creates a backup presentation bundle with fake
  redacted diff evidence and mock PR/commit review artifacts.
- The generated VSIX remains private-release configured.
- The task default remains `commentMode=dry-run`.
- The task reads `BIBER_API_KEY` only from the pipeline environment.
- The PR pipeline starts as artifact-only dry-run evidence.
- The commit pipeline publishes artifacts only and does not use
  `$(System.AccessToken)`.
- The installed-task pipeline invokes `BiberAiPrReview@1` after private
  extension install.
- The browser panel redacts secret-like pasted values before calling BIBER.
- No admin key, OpenAI key, or user key is embedded in package files.

## Azure DevOps Setup

Before publishing or sharing the private extension, follow
`docs/BIBER_AZURE_DEVOPS_PRIVATE_PUBLISH.md`. Use `tfx-cli` for Azure DevOps
extensions; reserve `vsce` for the separate VS Code extension.

For the first real pipeline run, follow
`docs/BIBER_AZURE_DEVOPS_LIVE_DRY_RUN.md` and keep the run artifact-only.

1. Upload the generated private VSIX:

   ```text
   examples/azure_devops_extension/flat-electronics-canada.biber-ai-azure-devops-0.1.0.vsix
   ```

2. Install/share it only with the test Azure DevOps organization.

3. Add a secret pipeline variable:

   ```text
   BIBER_API_KEY=<user-scoped BIBER API key>
   ```

4. Allow the pipeline to access the OAuth token only for the test repository if
   you plan to demonstrate PR comments.

5. Import or copy the sample pipeline:

   ```text
   examples/azure_devops_pipeline/biber-ai-pr-review.yml
   ```

For a push/commit-only demo, import or copy:

```text
examples/azure_devops_pipeline/biber-ai-commit-review.yml
```

This path reviews the latest pushed commit, publishes
`biber-ai-commit-review.md`, and intentionally does not request Azure PR
comment permissions.

After the private extension is installed, import or copy:

```text
examples/azure_devops_pipeline/biber-ai-extension-task-pr-review.yml
```

This path invokes the packaged `BiberAiPrReview@1` task, keeps
`commentMode=dry-run`, and publishes `biber-ai-review.md`.

## Dry-Run Demo Flow

1. Open a small test pull request with one deliberate correctness issue.

2. Include one fake secret-like value in the diff so redaction is visible. Use
   a clearly fake value, not a real credential.

3. Run the pipeline with:

   ```text
   commentMode=dry-run
   ```

4. Open the published `biber-ai-review.md` artifact.

5. Show these sections:

   - Summary
   - Risk level
   - Correctness risks
   - Security/privacy risks
   - Tests to run or add
   - Reviewer checklist
   - Merge recommendation

6. Show that the fake secret-like value is redacted.

7. Open the `BIBER AI Review` hub panel and explain that it is the UI direction
   for interactive review from inside Azure DevOps.
8. If the extension is installed, rerun the same scenario with
   `biber-ai-extension-task-pr-review.yml` to show the packaged task form.

## Commit Review Demo Flow

1. Push one small test commit to `main` or `master` in a demo repository.
2. Run the commit-review pipeline.
3. Open the published `biber-ai-commit-review.md` artifact.
4. Explain that this path is useful for post-commit inspection, audit trails,
   and teams that do not want PR comment permissions in the first rollout.

## Optional PR Comment Flow

Only after the dry-run artifact looks acceptable, rerun the test PR with:

```text
commentMode=post
```

Expected behavior:

- One Azure DevOps PR thread is created.
- The comment is based on the same Markdown artifact shape.
- The pipeline still sends bounded, redacted diff context.
- OpenAI mentor remains disabled unless a future explicit mentor-review
  workflow is enabled.

## Talking Points

- BIBER is not replacing human review; it reduces review toil.
- The first MVP is deliberately narrow: PR/commit review before autonomous file
  mutation.
- The model source is swappable behind the BIBER API contract.
- Local GPU inference can handle routine reviews.
- OpenAI/Codex mentor review can remain optional for high-risk planning and
  escalation.
- Full repository RAG, mature multi-agent orchestration, and safe multi-file
  edit loops are future BIBER phases, not claims for this demo.

## Do Not Claim Yet

- Do not claim production SOC2, HIPAA, ISO, or regulated-data readiness.
- Do not claim full repository understanding from the bounded-diff demo.
- Do not claim autonomous merge approval.
- Do not route the panel directly to raw vLLM or a GPU-local endpoint.
- Do not publish broadly until quotas, audit logs, abuse controls, and durable
  key storage are production-ready.

## Recovery Notes

If the pipeline cannot post a PR comment, keep the demo on the artifact path.
The artifact-only flow is still the safest and clearest conference story.

If the live BIBER API is unavailable, use the offline smoke outputs and explain
that the extension and task contract are validated without sending code outside
the test environment.

If Azure DevOps itself is unavailable during the talk, use the latest
`outputs/biber-azure-devops-offline-demo-*` bundle. Show `README.md`,
`sample-redacted.diff`, `biber-ai-review.md`, `biber-ai-commit-review.md`, and
`summary.json`, then explain that this bundle is generated by
`npm run demo:offline` without live API or cloud requests.
