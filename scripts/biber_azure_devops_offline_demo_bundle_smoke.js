#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const SOURCE = "biber_azure_devops_offline_demo_bundle_smoke";
const ROOT = path.resolve(__dirname, "..");
const DEFAULT_OUTPUT_ROOT = path.join(ROOT, "outputs");
const DEFAULT_MODEL = "biber-dev-core-v1";
const DEFAULT_BASE_URL = "https://api.beaverapi.com/v1";

const SECRET_PATTERNS = [
  /(?<label>api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*['"]?[^'"\s]+/gi,
  /authorization:\s*bearer\s+[A-Za-z0-9._~+/=-]+/gi,
  /-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----/g,
  /\b[A-Za-z0-9+/]{40,}={0,2}\b/g,
];

const SAMPLE_DIFF = `diff --git a/src/payments.ts b/src/payments.ts
--- a/src/payments.ts
+++ b/src/payments.ts
@@ -1,7 +1,13 @@
 export function approveTransfer(amount: number, userRole: string): boolean {
+  const apiKey = "fake-secret-for-redaction-demo";
+  if (userRole === "admin") return true;
+  if (amount < 0) return true;
   return amount > 0 && amount < 1000;
 }

 export function formatReceipt(id: string): string {
-  return "receipt:" + id;
+  return "receipt:" + id.trim();
 }
`;

const SAMPLE_REVIEW = `### Summary
The transfer approval change introduces broad approval paths and a small receipt formatting improvement.

### Risk level
High risk because negative amounts and all admin requests are approved without policy checks.

### Correctness risks
- Negative transfer amounts should never be approved.
- Admin bypass logic should be explicit, audited, and tested.
- Receipt trimming is probably fine, but callers that depend on exact IDs should be checked.

### Security/privacy risks
- Secret-like values were present in the diff and must stay redacted.
- Authorization bypass behavior should not ship without a separate security review.

### Tests to run or add
- Add boundary tests for negative, zero, allowed, and over-limit amounts.
- Add role-based tests proving admin behavior is intentional.
- Add a regression test for receipt formatting.

### Reviewer checklist
- Confirm no real secrets are present in the commit.
- Confirm the approval policy is documented.
- Confirm CI tests cover the changed branches.

### Merge recommendation
Do not merge until the negative amount path and admin bypass are fixed or explicitly approved.`;

function parseArgs(argv) {
  const timestamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const parsed = {
    outputDir: path.join(DEFAULT_OUTPUT_ROOT, `biber-azure-devops-offline-demo-${timestamp}`),
    baseUrl: DEFAULT_BASE_URL,
    model: DEFAULT_MODEL,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--output-dir" && argv[index + 1]) {
      parsed.outputDir = argv[index + 1];
      index += 1;
    } else if (arg === "--base-url" && argv[index + 1]) {
      parsed.baseUrl = argv[index + 1];
      index += 1;
    } else if (arg === "--model" && argv[index + 1]) {
      parsed.model = argv[index + 1];
      index += 1;
    }
  }
  return parsed;
}

function redactSecrets(text) {
  let redacted = text;
  let count = 0;
  for (const pattern of SECRET_PATTERNS) {
    redacted = redacted.replace(pattern, () => {
      count += 1;
      return "[REDACTED_BIBER_SECRET]";
    });
  }
  return { text: redacted, count };
}

function changedPathsFromDiff(diffText) {
  const paths = [];
  const seen = new Set();
  for (const line of diffText.split(/\r?\n/)) {
    let candidate = "";
    if (line.startsWith("+++ b/") || line.startsWith("--- a/")) {
      candidate = line.slice(6).trim();
    } else if (line.startsWith("diff --git ")) {
      const parts = line.split(/\s+/);
      candidate = parts[3] && parts[3].startsWith("b/") ? parts[3].slice(2) : "";
    }
    if (!candidate || candidate === "/dev/null") {
      continue;
    }
    const key = candidate.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    paths.push(candidate);
  }
  return paths;
}

function formatReviewArtifact({
  artifactKind,
  model,
  reviewMarkdown,
  changedPaths,
  redactionCount,
}) {
  const pathPreview = changedPaths.map((item) => `- \`${item}\``).join("\n") || "- none detected";
  return `## BIBER AI Review

**Artifact kind:** \`${artifactKind}\`
**Model:** \`${model}\`
**Risk:** \`high\`
**OpenAI mentor:** \`disabled\`
**Diff truncated:** \`no\`
**Secret-like values redacted:** \`${redactionCount}\`

${reviewMarkdown}

### Changed paths reviewed
${pathPreview}

_BIBER reviewed a bounded, redacted demo diff. This offline artifact is for presentation backup only and is not an automatic merge approval._
`;
}

function writeText(filePath, text) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, text, "utf8");
}

function writeJson(filePath, payload) {
  writeText(filePath, `${JSON.stringify(payload, null, 2)}\n`);
}

function check(condition, name, detail = "") {
  return { name, ok: Boolean(condition), detail };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const outputDir = path.resolve(args.outputDir);
  const redacted = redactSecrets(SAMPLE_DIFF);
  const changedPaths = changedPathsFromDiff(redacted.text);
  const prMarkdown = formatReviewArtifact({
    artifactKind: "azure_devops_pr_dry_run",
    model: args.model,
    reviewMarkdown: SAMPLE_REVIEW,
    changedPaths,
    redactionCount: redacted.count,
  });
  const commitMarkdown = formatReviewArtifact({
    artifactKind: "azure_devops_commit_artifact_only",
    model: args.model,
    reviewMarkdown: SAMPLE_REVIEW,
    changedPaths,
    redactionCount: redacted.count,
  });
  const mockResponse = {
    choices: [
      {
        message: {
          role: "assistant",
          content: SAMPLE_REVIEW,
        },
      },
    ],
    usage: {
      prompt_tokens: 80,
      completion_tokens: 220,
      total_tokens: 300,
    },
  };

  const files = {
    readme: path.join(outputDir, "README.md"),
    sampleDiff: path.join(outputDir, "sample-redacted.diff"),
    mockResponse: path.join(outputDir, "mock-biber-response.json"),
    prMarkdown: path.join(outputDir, "biber-ai-review.md"),
    commitMarkdown: path.join(outputDir, "biber-ai-commit-review.md"),
    summary: path.join(outputDir, "summary.json"),
  };

  writeText(files.sampleDiff, redacted.text);
  writeJson(files.mockResponse, mockResponse);
  writeText(files.prMarkdown, prMarkdown);
  writeText(files.commitMarkdown, commitMarkdown);
  writeText(
    files.readme,
    `# BIBER Azure DevOps Offline Demo Bundle

This bundle is a presentation backup for the Azure DevOps PR/commit review demo.
It is generated without contacting BIBER, Azure DevOps, GitHub, OpenAI, GPU, or
any external network service.

## Files

- \`sample-redacted.diff\`: fake demo diff after client-side-style redaction.
- \`mock-biber-response.json\`: mock OpenAI-compatible response shape.
- \`biber-ai-review.md\`: PR dry-run review artifact.
- \`biber-ai-commit-review.md\`: commit-review artifact-only output.
- \`summary.json\`: non-secret proof that the bundle is offline-only.

Use this bundle only when the live demo path is unavailable.
`,
  );

  const checks = [
    check(fs.existsSync(files.readme), "readme_written"),
    check(fs.existsSync(files.sampleDiff), "sample_diff_written"),
    check(fs.existsSync(files.mockResponse), "mock_response_written"),
    check(fs.existsSync(files.prMarkdown), "pr_markdown_written"),
    check(fs.existsSync(files.commitMarkdown), "commit_markdown_written"),
    check(redacted.count >= 1, "secret_like_value_redacted"),
    check(!fs.readFileSync(files.sampleDiff, "utf8").includes("fake-secret-for-redaction-demo"), "sample_diff_no_raw_secret"),
    check(prMarkdown.includes("OpenAI mentor:** `disabled`"), "pr_mentor_disabled"),
    check(commitMarkdown.includes("Artifact kind:** `azure_devops_commit_artifact_only`"), "commit_artifact_kind"),
    check(changedPaths.includes("src/payments.ts"), "changed_path_detected"),
  ];
  const failed = checks.filter((item) => !item.ok);
  const summary = {
    source: SOURCE,
    ok: failed.length === 0,
    status: failed.length === 0 ? "passed" : "failed",
    api_required: false,
    external_network_required: false,
    azure_devops_request_sent: false,
    biber_request_sent: false,
    github_request_sent: false,
    gpu_required: false,
    mentor_used: false,
    training_allowed: false,
    base_url: args.baseUrl,
    model: args.model,
    changed_paths: changedPaths,
    secret_like_values_redacted: redacted.count,
    output_dir: outputDir,
    files,
    checks,
    failed,
  };

  writeJson(files.summary, summary);
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);
  process.exit(summary.ok ? 0 : 1);
}

main();
