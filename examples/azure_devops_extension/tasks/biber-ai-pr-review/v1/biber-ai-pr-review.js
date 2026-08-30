#!/usr/bin/env node
"use strict";

const childProcess = require("child_process");
const path = require("path");

function input(name, fallback) {
  const envName = `INPUT_${name.replace(/ /g, "_").toUpperCase()}`;
  return process.env[envName] || fallback || "";
}

function findRepoRoot() {
  return process.env.BUILD_SOURCESDIRECTORY || process.cwd();
}

function main() {
  const taskDir = __dirname;
  const repoRoot = findRepoRoot();
  const scriptPath = path.join(repoRoot, "scripts", "biber_azure_devops_pr_review.py");
  const artifactDir = process.env.BUILD_ARTIFACTSTAGINGDIRECTORY || repoRoot;
  const outputJson = path.join(artifactDir, "biber-ai-review.json");
  const outputMd = path.join(artifactDir, "biber-ai-review.md");
  const python = process.env.PYTHON || process.env.PYTHON3 || "python";
  const args = [
    scriptPath,
    "--repo-root",
    repoRoot,
    "--base-url",
    input("biberApiBaseUrl", "https://api.beaverapi.com/v1"),
    "--model",
    input("biberModel", "biber-dev-core-v1"),
    "--comment-mode",
    input("commentMode", "dry-run"),
    "--max-diff-bytes",
    input("maxDiffBytes", "60000"),
    "--output-json",
    outputJson,
    "--output-md",
    outputMd,
  ];

  const biberKey = process.env.BIBER_API_KEY || "";
  const env = Object.assign({}, process.env, {
    BIBER_API_KEY: biberKey,
    BIBER_AZURE_DEVOPS_TASK_DIR: taskDir,
  });
  const result = childProcess.spawnSync(python, args, {
    cwd: repoRoot,
    env,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.stdout) {
    process.stdout.write(result.stdout);
  }
  if (result.stderr) {
    process.stderr.write(result.stderr);
  }
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

main();
