#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const EXTENSION_ROOT = path.join(ROOT, "examples", "azure_devops_extension");
const OFFLINE_DEMO_SCRIPT = path.join(ROOT, "scripts", "biber_azure_devops_offline_demo_bundle_smoke.js");
const REQUIRED_FILES = [
  "vss-extension.json",
  "overview.md",
  "README.md",
  "images/icon.png",
  "static/index.html",
  "static/main.js",
  "static/styles.css",
  "tasks/biber-ai-pr-review/v1/task.json",
  "tasks/biber-ai-pr-review/v1/biber-ai-pr-review.js",
  "tasks/biber-ai-pr-review/v1/icon.png",
];

function check(condition, name, detail = "") {
  return { name, ok: Boolean(condition), detail };
}

function readText(relativePath) {
  return fs.readFileSync(path.join(EXTENSION_ROOT, relativePath), "utf8");
}

function readJson(relativePath) {
  return JSON.parse(readText(relativePath));
}

function exists(relativePath) {
  return fs.existsSync(path.join(EXTENSION_ROOT, relativePath));
}

function isPng(relativePath) {
  const fullPath = path.join(EXTENSION_ROOT, relativePath);
  if (!fs.existsSync(fullPath)) {
    return false;
  }
  const header = fs.readFileSync(fullPath).subarray(0, 8);
  return header.equals(Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]));
}

function walkTextFiles(dir, output = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (["node_modules", "dist", ".git"].includes(entry.name)) {
      continue;
    }
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkTextFiles(fullPath, output);
      continue;
    }
    if (/\.(json|md|html|js|css|yml|yaml)$/i.test(entry.name)) {
      output.push(fullPath);
    }
  }
  return output;
}

function parseArgs(argv) {
  const parsed = { output: "" };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--output" && argv[index + 1]) {
      parsed.output = argv[index + 1];
      index += 1;
    }
  }
  return parsed;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const checks = [];

  for (const relativePath of REQUIRED_FILES) {
    checks.push(check(exists(relativePath), `exists:${relativePath}`));
  }

  const manifest = exists("vss-extension.json") ? readJson("vss-extension.json") : {};
  const task = exists("tasks/biber-ai-pr-review/v1/task.json")
    ? readJson("tasks/biber-ai-pr-review/v1/task.json")
    : {};
  const packageJson = exists("package.json") ? readJson("package.json") : {};
  const taskScript = exists("tasks/biber-ai-pr-review/v1/biber-ai-pr-review.js")
    ? readText("tasks/biber-ai-pr-review/v1/biber-ai-pr-review.js")
    : "";
  const panelText = ["static/index.html", "static/main.js", "static/styles.css"]
    .filter(exists)
    .map(readText)
    .join("\n");
  const readmeText = exists("README.md") ? readText("README.md") : "";
  const overviewText = exists("overview.md") ? readText("overview.md") : "";
  const allText = walkTextFiles(EXTENSION_ROOT)
    .map((filePath) => fs.readFileSync(filePath, "utf8"))
    .join("\n");

  const contributionIds = new Set(
    Array.isArray(manifest.contributions)
      ? manifest.contributions.map((item) => item && item.id).filter(Boolean)
      : [],
  );
  const taskInputNames = new Set(
    Array.isArray(task.inputs) ? task.inputs.map((item) => item && item.name).filter(Boolean) : [],
  );
  const commentModeInput = Array.isArray(task.inputs)
    ? task.inputs.find((item) => item && item.name === "commentMode")
    : null;
  const maxDiffInput = Array.isArray(task.inputs)
    ? task.inputs.find((item) => item && item.name === "maxDiffBytes")
    : null;
  const scopeSet = new Set(Array.isArray(manifest.scopes) ? manifest.scopes : []);
  const unexpectedScopes = [...scopeSet].filter((scope) => scope !== "vso.code");

  checks.push(check(packageJson.name === "biber-ai-azure-devops", "package:name"));
  checks.push(check(packageJson.private === true, "package:private"));
  checks.push(check(packageJson.scripts && packageJson.scripts.validate && packageJson.scripts.validate.startsWith("node "), "package:node_validate"));
  checks.push(check(packageJson.scripts && packageJson.scripts["validate:panel"], "package:panel_smoke_available"));
  checks.push(check(packageJson.scripts && packageJson.scripts["validate:pipeline"], "package:pipeline_smoke_available"));
  checks.push(check(packageJson.scripts && packageJson.scripts["validate:contract"], "package:contract_smoke_available"));
  checks.push(check(packageJson.scripts && packageJson.scripts["validate:wrapper"], "package:wrapper_smoke_available"));
  checks.push(check(packageJson.scripts && packageJson.scripts["demo:offline"], "package:offline_demo_available"));
  checks.push(check(fs.existsSync(OFFLINE_DEMO_SCRIPT), "demo:offline_script_exists"));
  checks.push(check(/^0\.1\.0$/.test(packageJson.version || ""), "package:demo_version"));

  checks.push(check(manifest.manifestVersion === 1, "manifest:version"));
  checks.push(check(manifest.id === "biber-ai-azure-devops", "manifest:id"));
  checks.push(check(manifest.name === "BIBER AI Review for Azure DevOps", "manifest:name"));
  checks.push(check(manifest.publisher === "flat-electronics-canada", "manifest:publisher"));
  checks.push(check(manifest.public === false, "manifest:private_release_default"));
  checks.push(check(Array.isArray(manifest.categories) && manifest.categories.includes("Azure Repos"), "manifest:azure_repos_category"));
  checks.push(check(Array.isArray(manifest.categories) && manifest.categories.includes("Azure Pipelines"), "manifest:azure_pipelines_category"));
  checks.push(check(scopeSet.has("vso.code"), "manifest:vso_code_scope"));
  checks.push(check(unexpectedScopes.length === 0, "manifest:no_unexpected_scopes", unexpectedScopes.join(",")));
  checks.push(check(contributionIds.has("biber-ai-review-hub"), "manifest:hub_contribution"));
  checks.push(check(contributionIds.has("biber-ai-pr-review-task"), "manifest:task_contribution"));
  checks.push(check(JSON.stringify(manifest).includes("ms.vss-code-web.code-hub-group"), "manifest:repos_hub_target"));
  checks.push(check(JSON.stringify(manifest).includes("ms.vss-distributed-task.tasks"), "manifest:pipeline_task_target"));
  checks.push(check(isPng("images/icon.png"), "assets:marketplace_icon_png"));
  checks.push(check(isPng("tasks/biber-ai-pr-review/v1/icon.png"), "assets:task_icon_png"));

  checks.push(check(task.name === "BiberAiPrReview", "task:name"));
  checks.push(check(Boolean(task.execution && task.execution.Node20_1 && task.execution.Node20_1.target), "task:node20_1_handler"));
  checks.push(check(taskInputNames.has("biberApiBaseUrl"), "task:base_url_input"));
  checks.push(check(taskInputNames.has("biberModel"), "task:model_input"));
  checks.push(check(taskInputNames.has("commentMode"), "task:comment_mode_input"));
  checks.push(check(taskInputNames.has("maxDiffBytes"), "task:max_diff_input"));
  checks.push(check(!taskInputNames.has("biberApiKey"), "task:no_api_key_input"));
  checks.push(check(commentModeInput && commentModeInput.defaultValue === "dry-run", "task:dry_run_default"));
  checks.push(check(maxDiffInput && String(maxDiffInput.defaultValue) === "60000", "task:bounded_diff_default"));

  checks.push(check(taskScript.includes("process.env.BIBER_API_KEY"), "wrapper:api_key_from_env"));
  checks.push(check(taskScript.includes("BIBER_AZURE_DEVOPS_MOCK_DIFF_FILE"), "wrapper:mock_diff_hook"));
  checks.push(check(taskScript.includes("BIBER_AZURE_DEVOPS_MOCK_RESPONSE_FILE"), "wrapper:mock_response_hook"));
  checks.push(check(taskScript.includes("--comment-mode"), "wrapper:comment_mode_passed"));
  checks.push(check(taskScript.includes("--max-diff-bytes"), "wrapper:max_diff_passed"));
  checks.push(check(!taskScript.includes("BIBER_ADMIN_API_KEY"), "wrapper:no_admin_key"));

  checks.push(check(panelText.includes("BIBER AI Review"), "panel:title"));
  checks.push(check(panelText.includes("apiKey"), "panel:api_key_field"));
  checks.push(check(panelText.includes("redactSecrets"), "panel:client_redaction"));
  checks.push(check(panelText.includes("TextEncoder"), "panel:diff_budget_counter"));
  checks.push(check(panelText.includes("AbortController"), "panel:request_cancel"));
  checks.push(check(panelText.includes("navigator.clipboard"), "panel:copy_output"));
  checks.push(check(!panelText.includes("localStorage"), "panel:no_local_storage"));
  checks.push(check(!panelText.includes("sessionStorage"), "panel:no_session_storage"));
  checks.push(check(!panelText.includes("document.cookie"), "panel:no_cookie_storage"));
  checks.push(check(readmeText.includes("Do not point"), "docs:no_raw_vllm_warning"));
  checks.push(check(readmeText.includes("CORS"), "docs:cors_called_out"));
  checks.push(check(overviewText.includes("dry-run by default"), "overview:dry_run_default"));

  checks.push(check(!/OPENAI_API_KEY\s*=/.test(allText), "secrets:no_openai_key_assignment"));
  checks.push(check(!/BIBER_ADMIN_API_KEY\s*=/.test(allText), "secrets:no_admin_key_assignment"));
  checks.push(check(!/BIBER_API_KEY\s*=\s*['\"][^'\"]{12,}/.test(allText), "secrets:no_embedded_biber_key"));

  const failed = checks.filter((item) => !item.ok);
  const result = {
    source: "biber_azure_devops_publisher_readiness_smoke",
    ok: failed.length === 0,
    status: failed.length === 0 ? "passed" : "failed",
    api_required: false,
    external_network_required: false,
    github_request_sent: false,
    gpu_required: false,
    mentor_used: false,
    training_allowed: false,
    extension_root: EXTENSION_ROOT,
    checks,
    failed,
  };

  const body = `${JSON.stringify(result, null, 2)}\n`;
  if (args.output) {
    const outputPath = path.resolve(args.output);
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, body, "utf8");
  }
  process.stdout.write(body);
  process.exit(result.ok ? 0 : 1);
}

main();
