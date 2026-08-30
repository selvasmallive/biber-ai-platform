# BIBER Azure DevOps Live Dry-Run Checklist

Use this checklist for the first real Azure DevOps demo against a test
repository. Keep the first run artifact-only.

## Choose One Path

### Path A: Script-Based PR Review

Use this when the BIBER repo files are present in the checked-out repository
and you have not installed the Azure DevOps extension yet.

```text
examples/azure_devops_pipeline/biber-ai-pr-review.yml
```

Default behavior:

- PR trigger only.
- `commentMode=dry-run`.
- Full checkout for target-branch diff.
- Publishes `biber-ai-review.json` and `biber-ai-review.md`.
- Wires `$(System.AccessToken)` only so future `commentMode=post` can work.

### Path B: Installed Extension Task PR Review

Use this after the private BIBER Azure DevOps extension has been uploaded,
shared, and installed in the Azure DevOps organization.

```text
examples/azure_devops_pipeline/biber-ai-extension-task-pr-review.yml
```

Default behavior:

- PR trigger only.
- Invokes `BiberAiPrReview@1`.
- `commentMode=dry-run`.
- Publishes `biber-ai-review.json` and `biber-ai-review.md`.

### Path C: Commit Review

Use this when you want push/commit review artifacts without PR comment
permissions.

```text
examples/azure_devops_pipeline/biber-ai-commit-review.yml
```

Default behavior:

- Push trigger on `main` and `master`.
- Checks out the latest two commits.
- `commentMode=none`.
- Does not wire `$(System.AccessToken)`.
- Publishes `biber-ai-commit-review.json` and
  `biber-ai-commit-review.md`.

## Before Running

1. Confirm `https://api.beaverapi.com/v1/models` resolves from a normal
   browser or shell.
2. Create or choose a user-scoped BIBER API key.
3. Add the key as a secret pipeline variable named:

   ```text
   BIBER_API_KEY
   ```

4. Do not add `BIBER_ADMIN_API_KEY`, OpenAI keys, Vast SSH keys, or model
   training variables to the pipeline.
5. Use a test repository or small test branch with a deliberately simple change.
6. Include only fake secret-like values if you want to demonstrate redaction.

For the browser-panel path, paste only a user-scoped key, click
`Test Connection`, and confirm `/models` lists the selected model before
running `Generate Review`.

## First Run

1. Import or copy exactly one sample YAML into the Azure DevOps test repo.
2. Run the pipeline with the default settings.
3. Open the published artifact.
4. Confirm the artifact says:

   ```text
   OpenAI mentor: disabled
   ```

5. Confirm the JSON summary reports no training and no GitHub request.
6. Confirm fake secret-like values are replaced with:

   ```text
   [REDACTED_BIBER_SECRET]
   ```

7. Treat the output as human-review assistance, not merge approval.

## Only After Dry-Run Acceptance

For PR pipelines only, you may test comment posting by changing the task or
script input to:

```text
commentMode=post
```

Do this only in a test PR after confirming the pipeline has permission to use
`$(System.AccessToken)` and the project build service can comment on PRs.

## Fallback

If Azure DevOps or the live BIBER API is unavailable, run:

```bash
cd examples/azure_devops_extension
npm run demo:offline
```

Then present the latest:

```text
outputs/biber-azure-devops-offline-demo-*
```

That bundle is fake, non-secret, and generated without live API or cloud
requests.
