# BIBER Azure DevOps Private Publish Guide

Use this guide when publishing the BIBER Azure DevOps extension privately for a
demo or a limited team test.

## Scope

This guide is for the Azure DevOps extension in:

```text
examples/azure_devops_extension
```

It is not for the VS Code extension. VS Code uses `vsce`; Azure DevOps
Marketplace extensions use `tfx-cli`.

## Safe Defaults

- Keep the extension private while testing.
- Do not paste Marketplace PATs into source files, docs, terminal transcripts,
  screenshots, training data, eval artifacts, or chat logs.
- Keep `BIBER_API_KEY` as a secret pipeline variable.
- Keep `commentMode=dry-run` for the first PR demo.
- Use `examples/azure_devops_pipeline/biber-ai-commit-review.yml` when you want
  commit-review artifacts without Azure PR comment permissions.
- Publish/share only after `npm run validate`, `npm run validate:panel`,
  `npm run validate:pipeline`, and `npm run package` pass.

## Package

Run from the BIBER-only checkout:

```bash
cd examples/azure_devops_extension
npm ci
npm run validate
npm run validate:panel
npm run validate:pipeline
npm run package
```

Expected package:

```text
examples/azure_devops_extension/flat-electronics-canada.biber-ai-azure-devops-0.1.0.vsix
```

## Publish Through The Browser

1. Open the Visual Studio Marketplace publisher portal.
2. Select publisher `flat-electronics-canada`.
3. Choose `New extension` > `Azure DevOps`.
4. Upload the generated `.vsix`.
5. Leave the extension private for the first test.
6. Share the extension with the Azure DevOps organization that will install it.
7. Install it into that organization from the Marketplace listing.

Private extensions are visible only to the publisher and shared organizations.
Share with an organization before trying to install it there.

## Publish Through `tfx-cli`

Use this only from your own terminal. Let `tfx` prompt for the Marketplace token
or pass it through a secure secret mechanism outside Git.

```bash
cd examples/azure_devops_extension
npx tfx extension publish \
  --publisher flat-electronics-canada \
  --vsix flat-electronics-canada.biber-ai-azure-devops-0.1.0.vsix \
  --share-with <azure-devops-organization-name>
```

Use a Microsoft Entra token for mature automation. If using a PAT, Microsoft's
current docs call for a PAT with Marketplace publish scope.

## Pipeline Test After Install

Use `docs/BIBER_AZURE_DEVOPS_LIVE_DRY_RUN.md` as the first-run checklist.

For a PR artifact demo, copy:

```text
examples/azure_devops_pipeline/biber-ai-pr-review.yml
```

For a PR artifact demo that uses the installed extension task, copy:

```text
examples/azure_devops_pipeline/biber-ai-extension-task-pr-review.yml
```

For a commit artifact demo, copy:

```text
examples/azure_devops_pipeline/biber-ai-commit-review.yml
```

Add this as a secret pipeline variable:

```text
BIBER_API_KEY=<user-scoped BIBER API key>
```

The PR sample can use `$(System.AccessToken)` only for optional PR comment
posting. The commit sample does not need `$(System.AccessToken)`.

## Do Not Make Public Yet

Do not flip the Marketplace listing public until BIBER has durable production
key storage, quotas, audit logs, abuse detection, monitoring, incident
procedures, and a reviewed data-handling policy.

## References

- Azure DevOps package and publish guide:
  https://learn.microsoft.com/en-us/azure/devops/extend/publish/integration
- Azure DevOps command-line publish guide:
  https://learn.microsoft.com/en-us/azure/devops/extend/publish/command-line
- Azure DevOps extension manifest reference:
  https://learn.microsoft.com/en-us/azure/devops/extend/develop/manifest
