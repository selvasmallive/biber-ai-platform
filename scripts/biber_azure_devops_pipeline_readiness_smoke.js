#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const PIPELINE_PATH = path.join(
  ROOT,
  "examples",
  "azure_devops_pipeline",
  "biber-ai-pr-review.yml",
);

function check(condition, name, detail = "") {
  return { name, ok: Boolean(condition), detail };
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

function countMatches(text, pattern) {
  const matches = text.match(pattern);
  return matches ? matches.length : 0;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const checks = [check(fs.existsSync(PIPELINE_PATH), "pipeline_exists")];
  const pipelineText = fs.existsSync(PIPELINE_PATH)
    ? fs.readFileSync(PIPELINE_PATH, "utf8")
    : "";

  checks.push(check(/^trigger:\s*none\s*$/m.test(pipelineText), "trigger_disabled"));
  checks.push(check(/^pr:\s*$/m.test(pipelineText), "pr_trigger_present"));
  checks.push(check(/-\s*main\b/.test(pipelineText), "pr_includes_main"));
  checks.push(check(/-\s*master\b/.test(pipelineText), "pr_includes_master"));
  checks.push(check(/vmImage:\s*ubuntu-latest/.test(pipelineText), "uses_ubuntu_hosted_agent"));
  checks.push(check(/BIBER_OPENAI_BASE_URL:\s*https:\/\/api\.beaverapi\.com\/v1/.test(pipelineText), "base_url_default"));
  checks.push(check(/BIBER_MODEL:\s*biber-dev-core-v1/.test(pipelineText), "model_default"));
  checks.push(check(/-\s*checkout:\s*self/.test(pipelineText), "checkout_self"));
  checks.push(check(/fetchDepth:\s*0/.test(pipelineText), "checkout_full_history"));
  checks.push(check(/persistCredentials:\s*true/.test(pipelineText), "checkout_persist_credentials_for_pr_context"));
  checks.push(check(/UsePythonVersion@0/.test(pipelineText), "python_version_task"));
  checks.push(check(/versionSpec:\s*["']3\.11["']/.test(pipelineText), "python_311"));
  checks.push(check(/python scripts\/biber_azure_devops_pr_review\.py/.test(pipelineText), "review_script_invoked"));
  checks.push(check(/--repo-root\s+"\$\(Build\.SourcesDirectory\)"/.test(pipelineText), "repo_root_from_build_sources"));
  checks.push(check(/--base-url\s+"\$\(BIBER_OPENAI_BASE_URL\)"/.test(pipelineText), "base_url_from_variable"));
  checks.push(check(/--model\s+"\$\(BIBER_MODEL\)"/.test(pipelineText), "model_from_variable"));
  checks.push(check(/--comment-mode\s+dry-run/.test(pipelineText), "comment_mode_dry_run"));
  checks.push(check(!/--comment-mode\s+post/.test(pipelineText), "comment_mode_post_not_enabled"));
  checks.push(check(/--output-json\s+"\$\(Build\.ArtifactStagingDirectory\)\/biber-ai-review\.json"/.test(pipelineText), "json_artifact_path"));
  checks.push(check(/--output-md\s+"\$\(Build\.ArtifactStagingDirectory\)\/biber-ai-review\.md"/.test(pipelineText), "markdown_artifact_path"));
  checks.push(check(/BIBER_API_KEY:\s*\$\(BIBER_API_KEY\)/.test(pipelineText), "biber_key_from_secret_variable"));
  checks.push(check(/SYSTEM_ACCESSTOKEN:\s*\$\(System\.AccessToken\)/.test(pipelineText), "system_access_token_env"));
  checks.push(check(/-\s*publish:\s+"\$\(Build\.ArtifactStagingDirectory\)"/.test(pipelineText), "publishes_artifacts"));
  checks.push(check(/artifact:\s*biber-ai-review/.test(pipelineText), "artifact_name"));
  checks.push(check(countMatches(pipelineText, /BIBER_API_KEY/g) === 3, "no_extra_biber_key_mentions"));
  checks.push(check(!/BIBER_API_KEY\s*:\s*["'][^"']{12,}["']/.test(pipelineText), "no_embedded_biber_key"));
  checks.push(check(!/OPENAI_API_KEY\s*:/.test(pipelineText), "no_openai_key"));
  checks.push(check(!/BIBER_ADMIN_API_KEY\s*:/.test(pipelineText), "no_admin_key"));
  checks.push(check(!/Review with OpenAI mentor/i.test(pipelineText), "mentor_not_requested"));
  checks.push(check(!/BIBER_TRAIN_APPROVED/.test(pipelineText), "training_not_enabled"));

  const failed = checks.filter((item) => !item.ok);
  const result = {
    source: "biber_azure_devops_pipeline_readiness_smoke",
    ok: failed.length === 0,
    status: failed.length === 0 ? "passed" : "failed",
    api_required: false,
    external_network_required: false,
    azure_devops_request_sent: false,
    github_request_sent: false,
    gpu_required: false,
    mentor_used: false,
    training_allowed: false,
    pipeline_path: PIPELINE_PATH,
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
