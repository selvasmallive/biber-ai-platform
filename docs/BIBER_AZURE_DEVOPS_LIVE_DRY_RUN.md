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

## Local Live-Run Preflight

Before touching Azure DevOps, run the offline preflight from the BIBER-only
checkout:

```bash
cd examples/azure_devops_extension
npm run validate:live-dry-run
```

Default mode sends no Azure DevOps request, no BIBER API request, no GitHub
request, no mentor request, no training request, and no GPU work. It reports
whether the local demo pack is ready and lists any live inputs still needed:

- `BIBER_API_KEY` as a user-scoped secret pipeline variable.
- `BIBER_AZURE_DEVOPS_TEST_REPO_URL` for the disposable test repository or PR.
- `BIBER_AZURE_DEVOPS_PRIVATE_EXTENSION_INSTALLED=yes` only after the private
  VSIX is uploaded/shared/installed.
- `BIBER_AZURE_DEVOPS_OAUTH_TOKEN_ALLOWED=yes` only later, if testing
  `commentMode=post` in a disposable test PR.

Only when you deliberately want to test the public BIBER endpoint, run the
script directly with `--probe-api`. That mode calls `GET /v1/models` and should
use a user-scoped key, not an admin key.

After the first Azure DevOps dry-run publishes `biber-ai-review`, validate the downloaded artifact locally before using it in the demo:

```bash
cd examples/azure_devops_extension
npm run validate:live-artifact -- --artifact-dir <downloaded-biber-ai-review-artifact-dir>
```

Without a downloaded artifact, `npm run validate:live-artifact` runs a local mock self-test against the checked-in disposable fixture.


## Disposable Demo Fixture

For the first real dry-run, use the checked-in fixture instead of inventing a PR during the demo:

```text
examples/azure_devops_demo_fixture
```

The fixture contains clean base code, a unittest file, and a patch that deliberately introduces two safe-to-discuss risks: token-like logging and weakened zero-amount refund validation. The token-like value is fake and must not be replaced with a real secret.

Recommended first live path:

1. Import or mirror the BIBER MVP branch into a disposable Azure DevOps test repo.
2. Create a temporary branch named `biber-azdo-demo-review-fixture`.
3. Apply `examples/azure_devops_demo_fixture/patches/demo-pr-reviewable-change.diff` with `git apply --unidiff-zero`.
4. Open a PR back to the imported BIBER MVP branch.
5. Run Path A with `commentMode=dry-run` and secret variable `BIBER_API_KEY` configured.
6. Review only the published artifact first; do not enable comment posting on the first run.

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
3. Download or open the published artifact.
4. Run the acceptance checker from the BIBER-only checkout:

   ```bash
   cd examples/azure_devops_extension
   npm run validate:live-artifact -- --artifact-dir <downloaded-biber-ai-review-artifact-dir>
   ```

5. Confirm the artifact says:

   ```text
   OpenAI mentor: disabled
   ```

6. Confirm the JSON summary reports no training and no GitHub request.
7. Confirm fake secret-like values are replaced with:

   ```text
   [REDACTED_BIBER_SECRET]
   ```

8. Treat the output as human-review assistance, not merge approval.

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
