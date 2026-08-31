# BIBER Azure DevOps Demo Fixture

This disposable fixture gives the first live Azure DevOps dry-run a predictable PR diff. It is intentionally small, fake, and safe to discard after the demo.

## What It Contains

- `src/refund_policy.py`: clean base code with deterministic behavior.
- `tests/test_refund_policy.py`: local unittest coverage for the base behavior.
- `patches/demo-pr-reviewable-change.diff`: a deliberately risky demo change that logs a token-like value and weakens zero-amount refund validation.

The token-like value in the patch is fake. Do not replace it with a real secret.

## Use It For Path A Dry-Run

Use this when the BIBER repo branch is imported into Azure DevOps and you want one small PR that the script-based pipeline can review.

1. Keep the Azure pipeline on the safe default:

   ```text
   commentMode=dry-run
   ```

2. Create a temporary branch from the BIBER MVP branch:

   ```bash
   git checkout -b biber-azdo-demo-review-fixture
   ```

3. Apply the fixture patch:

   ```bash
   git apply --unidiff-zero examples/azure_devops_demo_fixture/patches/demo-pr-reviewable-change.diff
   ```

4. Run the local fixture test if Python is available:

   ```bash
   PYTHONDONTWRITEBYTECODE=1 python examples/azure_devops_demo_fixture/tests/test_refund_policy.py
   ```

   The demo patch is expected to make this test fail because zero-amount refunds are no longer rejected. That gives BIBER a concrete correctness issue to discuss.

5. Commit the temporary branch and open a PR into the imported BIBER MVP branch.

6. Run `examples/azure_devops_pipeline/biber-ai-pr-review.yml` with secret variable `BIBER_API_KEY` configured.

7. Open the published `biber-ai-review.md` artifact and verify it calls out the correctness and security/privacy concerns. Treat the artifact as review assistance, not merge approval.

## Cleanup

Close the demo PR without merging, then delete the temporary branch. Keep this fixture in the BIBER repo so future conference or customer demos can recreate the same dry-run quickly.
