# BIBER Azure DevOps First-Run Quickstart

Use this for the first real Azure DevOps dry-run after the local checks pass. The goal is one disposable PR, one artifact-only BIBER review, and zero production side effects.

## Use Path A First

Start with the script-based pipeline because it does not require the private Azure DevOps extension to be installed yet:

```text
examples/azure_devops_pipeline/biber-ai-pr-review.yml
```

Keep the default:

```text
commentMode=dry-run
```

Do not enable `commentMode=post` on the first run.

## Required Live Inputs

- A disposable Azure DevOps test repository or PR URL.
- A user-scoped BIBER API key stored as a secret Azure Pipeline variable named exactly `BIBER_API_KEY`.

Do not add `BIBER_ADMIN_API_KEY`, OpenAI keys, Vast SSH keys, or training variables to Azure DevOps.

## Create The Demo PR

Use the checked-in fixture so the live demo and offline backup match each other.

```bash
git checkout -b biber-azdo-demo-review-fixture
git apply --unidiff-zero examples/azure_devops_demo_fixture/patches/demo-pr-reviewable-change.diff
PYTHONDONTWRITEBYTECODE=1 python examples/azure_devops_demo_fixture/tests/test_refund_policy.py
git add examples/azure_devops_demo_fixture/src/refund_policy.py
git commit -m "Create BIBER Azure DevOps review fixture change"
git push -u origin biber-azdo-demo-review-fixture
```

The unittest is expected to fail after the patch because zero-amount refunds are no longer rejected. That is intentional and gives BIBER a concrete correctness issue to review.

Open a PR from `biber-azdo-demo-review-fixture` into the imported BIBER MVP branch.

## Run The Pipeline

1. Create an Azure Pipeline from existing YAML.
2. Choose the BIBER repo branch and select `examples/azure_devops_pipeline/biber-ai-pr-review.yml`.
3. Add secret variable `BIBER_API_KEY`.
4. Run the pipeline against the demo PR.
5. Open or download the published `biber-ai-review` artifact.
6. Review `biber-ai-review.md` and `biber-ai-review.json`.
7. Validate the downloaded artifact locally before using it in the demo:

   ```bash
   cd examples/azure_devops_extension
   npm run validate:live-artifact -- --artifact-dir <downloaded-biber-ai-review-artifact-dir>
   ```

Expected posture:

- `OpenAI mentor: disabled`
- `training_allowed: false`
- `github_request_sent: false`
- `azure_comment_request_sent: false`
- fake token-like values are redacted as `[REDACTED_BIBER_SECRET]`

## Fallback

Before the live run exists, you can self-test the artifact checker without any network calls:

```bash
cd examples/azure_devops_extension
npm run validate:live-artifact
```

If Azure DevOps or the public BIBER API is unavailable, run the offline bundle locally:

```bash
cd examples/azure_devops_extension
npm run demo:offline -- --output-dir <writable-output-dir>
```

The offline bundle uses the same fixture patch and sends no Azure DevOps, BIBER API, GitHub, OpenAI, GPU, training, or paid API request.
