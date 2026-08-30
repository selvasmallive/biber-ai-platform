# BIBER AI Azure DevOps Extension MVP

This folder contains the first Azure DevOps MVP for the conference demo:

- A pipeline task contribution scaffold in `vss-extension.json`.
- A browser panel at `static/index.html` for the "BIBER AI Review" UI path.
- A task manifest at `tasks/biber-ai-pr-review/v1/task.json`.
- A repo-level pipeline example at
  `examples/azure_devops_pipeline/biber-ai-pr-review.yml`.

## Recommended Demo Order

1. Run the sample pipeline in dry-run mode and publish the generated Markdown
   review artifact.
2. Enable `commentMode: post` only after the pipeline has access to
   `$(System.AccessToken)` and the project allows the build service to comment
   on pull requests.
3. Open the extension panel to show how the same BIBER review contract can be
   surfaced inside Azure DevOps.

## BIBER API Configuration

Use the controlled BIBER API gateway:

```text
BIBER_OPENAI_BASE_URL=https://api.beaverapi.com/v1
BIBER_MODEL=biber-dev-core-v1
BIBER_API_KEY=<user-api-key-secret>
```

Do not point the extension or task at the raw vLLM endpoint. The raw model
runtime should stay private behind BIBER's authentication, request guard,
Cloudflare edge controls, and future quota store.

The browser panel can call BIBER directly only when the public API allows the
Azure DevOps origin through CORS. For the pipeline task, CORS is not needed
because the call is server-side inside the build agent.

For a live public browser-panel demo, configure the BIBER API process with:

```text
BIBER_CORS_ALLOWED_ORIGINS=https://dev.azure.com
BIBER_CORS_ALLOWED_ORIGIN_REGEX=https://.*\.visualstudio\.com
```

Leave those values unset for pipeline-only or private tunnel demos.

The packaged pipeline task reads the BIBER user key from the `BIBER_API_KEY`
environment variable. Pass it from a secret pipeline variable; do not expose it
as a normal task input.

## Package Later

When the extension is ready for Marketplace packaging, install the package
tooling locally and run:

```bash
npm ci
npm run package
```

Or use the repo-level smoke, which validates the manifest/task contract, runs
the local extension validation, packages the VSIX, and checks the archive
contents:

```bash
python scripts/biber_azure_devops_extension_package_smoke.py
```

The generated package is ignored by Git and currently lands at:

```text
flat-electronics-canada.biber-ai-azure-devops-0.1.0.vsix
```

`tfx-cli` is a dev-only packaging dependency. If `npm ci` reports audit
findings, do not treat them as BIBER runtime dependencies; still revisit the
packaging toolchain before a broad public Marketplace release.

To test the task wrapper entrypoint without Azure DevOps credentials or a live
BIBER API:

```bash
python ../../scripts/biber_azure_devops_task_wrapper_smoke.py
```

For now, validate the contract without Azure credentials or network calls:

```bash
python scripts/biber_azure_devops_review_smoke.py
```
