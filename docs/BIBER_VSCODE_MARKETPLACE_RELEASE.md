# BIBER VS Code Marketplace Release

This runbook is for packaging, install-testing, and publishing the BIBER AI
Assistant extension under the existing Visual Studio Marketplace publisher:

```text
flat-electronics-canada
```

The extension ID is:

```text
flat-electronics-canada.biber-ai-assistant
```

## Current Release Scope

Version `0.1.0` is intentionally a planning-first extension:

- Stores API keys in VS Code SecretStorage.
- Tests `/v1/agent/capabilities` before orchestration.
- Calls `/v1/agent/orchestration/plan` by explicit user command.
- Sends bounded instructions and bounded workspace-relative path hints.
- Sends no file contents in this release.
- Does not call model inference directly from the extension.
- Does not expose admin APIs, training APIs, credential rotation, or raw vLLM.
- Does not mutate files from VS Code yet.

The next publishable feature can add guarded multi-file edit support only after
the UX requires human review of `/v1/files/edit/plan`, matching `plan_hash`, and
explicit apply confirmation.

## Security Posture

Do not rely on the VS Code extension to protect BIBER by itself. Client-side
single-flight, timeout, prompt/path limits, and per-minute limits are only UX
guards. Real protection belongs in the BIBER API and edge layer:

- API-key authentication.
- Per-key quotas and server-side rate limits.
- Request payload size caps.
- Cloudflare/WAF protections for public domains.
- Logging redaction.
- Admin API isolation.
- No direct public access to vLLM.
- No public training/fine-tuning endpoint.

The model should remain inference-only for extension users. User prompts and
repository paths must never update training data automatically. Any future
fine-tuning must stay in the curated, reviewed, offline training pipeline with
explicit owner approval.

An MCP server is not required for the Marketplace `0.1.0` release. The BIBER
API gateway already abstracts and protects the model. MCP may be useful later
as a local tool bridge for filesystem, datasource, or workflow integrations,
but it should not be treated as the security boundary for the model.

## Package And Install Test

From the extension root:

```bash
cd examples/vscode_extension
npm ci
npm run compile
npm run package
```

From the repository root, the repeatable smoke is:

```bash
python scripts/biber_vscode_extension_package_smoke.py
```

On Windows/OneDrive workspaces, `npm ci` can occasionally fail while deleting
generated `node_modules` files that are locked by the OS, editor, sync client,
or antivirus. If dependencies are already installed and `npm install` reports
zero vulnerabilities, use the explicit local fallback:

```bash
python scripts/biber_vscode_extension_compile_smoke.py --skip-npm-ci
python scripts/biber_vscode_extension_package_smoke.py --skip-npm-ci
```

This fallback still runs TypeScript compile, creates the VSIX, and install-tests
the VSIX; it only skips the dependency delete/recreate step.

Install-test into an isolated temporary VS Code profile before publishing:

```bash
code --extensions-dir <temp-extensions-dir> \
  --user-data-dir <temp-user-data-dir> \
  --install-extension biber-ai-assistant-0.1.0.vsix \
  --force

code --extensions-dir <temp-extensions-dir> \
  --user-data-dir <temp-user-data-dir> \
  --list-extensions --show-versions
```

The installed extension should appear as:

```text
flat-electronics-canada.biber-ai-assistant@0.1.0
```

## Publish

Publishing requires a Marketplace/Azure DevOps token for the
`flat-electronics-canada` publisher with Marketplace Manage permission. Do not
commit or paste the token into docs or chat logs.

Recommended publish flow:

```bash
cd examples/vscode_extension
npx vsce login flat-electronics-canada
npm run publish
```

If publishing from CI later, store the token as a secret and use `vsce publish`
with the secret injected by the CI provider.

## Pre-Publish Checklist

- `package.json.publisher` is `flat-electronics-canada`.
- `package.json.name` is `biber-ai-assistant`.
- `npm ci` passes.
- `npm run compile` passes.
- `npm run package` creates `biber-ai-assistant-0.1.0.vsix`.
- Isolated VS Code install-test passes.
- `scripts/biber_vscode_extension_contract_smoke.py` passes.
- `scripts/biber_vscode_extension_compile_smoke.py` passes.
- `scripts/biber_vscode_extension_package_smoke.py` passes.
- `scripts/biber_vscode_extension_connection_smoke.py` passes against the
  intended BIBER API with a low-quota user key.
- `scripts/biber_vscode_extension_orchestration_smoke.py` passes against the
  intended BIBER API with a low-quota user key.
- Handoff is updated with the VSIX path, install-test result, and whether
  publishing was completed or deliberately deferred.
