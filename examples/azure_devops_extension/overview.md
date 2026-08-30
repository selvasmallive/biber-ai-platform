# BIBER AI Review for Azure DevOps

BIBER AI Review brings private AI-assisted pull request review into Azure
DevOps. The MVP is designed for teams that want useful AI code review while
keeping the model source under their own control.

The fastest demo path is the included Azure Pipelines task. It reviews a
bounded and redacted git diff, sends it to the BIBER OpenAI-compatible API, and
can publish the review as a pull request comment after the pipeline has the
right Azure DevOps token permission.

The extension panel is the UI path. It gives reviewers a BIBER AI Review
surface for trying the same private review contract from inside Azure DevOps.

Security defaults:

- OpenAI mentor is disabled by default.
- API keys are entered by the user and must not be committed.
- The task redacts secret-like values before sending a diff to BIBER.
- The task uses a bounded diff budget.
- Comment posting is dry-run by default.
- The raw vLLM/GPU endpoint should stay private behind the BIBER API gateway.
