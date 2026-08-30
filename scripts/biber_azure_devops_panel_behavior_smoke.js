#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");
const PANEL_SCRIPT = path.join(ROOT, "examples", "azure_devops_extension", "static", "main.js");

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

class MockClassList {
  constructor() {
    this.values = new Set();
  }

  toggle(name, enabled) {
    if (enabled) {
      this.values.add(name);
    } else {
      this.values.delete(name);
    }
  }

  contains(name) {
    return this.values.has(name);
  }
}

class MockElement {
  constructor(id, value = "") {
    this.id = id;
    this.value = value;
    this.textContent = "";
    this.disabled = false;
    this.listeners = new Map();
    this.classList = new MockClassList();
  }

  addEventListener(eventName, handler) {
    const existing = this.listeners.get(eventName) || [];
    existing.push(handler);
    this.listeners.set(eventName, existing);
  }

  async dispatch(eventName) {
    const handlers = this.listeners.get(eventName) || [];
    for (const handler of handlers) {
      await handler({ target: this });
    }
  }

  async click() {
    await this.dispatch("click");
  }
}

function makeElements() {
  const elements = {
    baseUrl: new MockElement("baseUrl", "https://api.beaverapi.com/v1"),
    model: new MockElement("model", "biber-dev-core-v1"),
    apiKey: new MockElement("apiKey", "test-panel-user-key"),
    diffText: new MockElement(
      "diffText",
      [
        "diff --git a/src/example.ts b/src/example.ts",
        "--- a/src/example.ts",
        "+++ b/src/example.ts",
        "@@ -1,3 +1,5 @@",
        " export function approve(value: number) {",
        "+  const api_key = \"secret-value-for-panel-redaction\";",
        "+  if (value < 0) return true;",
        "   return value <= 100;",
        " }",
      ].join("\n"),
    ),
    diffCounter: new MockElement("diffCounter"),
    outputText: new MockElement("outputText"),
    statusText: new MockElement("statusText"),
    statusPill: new MockElement("statusPill"),
    connectionResult: new MockElement("connectionResult"),
    testConnectionButton: new MockElement("testConnectionButton"),
    reviewButton: new MockElement("reviewButton"),
    stopButton: new MockElement("stopButton"),
    sampleButton: new MockElement("sampleButton"),
    clearButton: new MockElement("clearButton"),
    copyButton: new MockElement("copyButton"),
  };
  elements.connectionResult.textContent = "Not tested";
  return elements;
}

async function runPanel() {
  const requests = [];
  let copiedText = "";
  const elements = makeElements();
  const document = {
    getElementById(id) {
      if (!elements[id]) {
        throw new Error(`Unexpected document element requested: ${id}`);
      }
      return elements[id];
    },
  };
  const window = {
    setTimeout,
    clearTimeout,
  };
  const navigator = {
    clipboard: {
      async writeText(value) {
        copiedText = value;
      },
    },
  };
  async function fetch(url, options) {
    requests.push({
      url,
      method: options && options.method,
      headers: options && options.headers,
      body: options && options.body ? JSON.parse(options.body) : null,
    });
    if (String(url).endsWith("/models")) {
      return {
        ok: true,
        status: 200,
        async json() {
          return {
            data: [
              { id: "biber-dev-core-v1", object: "model" },
              { id: "biber-dev-core-v2-candidate", object: "model" },
            ],
          };
        },
        async text() {
          return "";
        },
      };
    }
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          choices: [
            {
              message: {
                content: "### Summary\nPanel behavior smoke review completed.",
              },
            },
          ],
        };
      },
      async text() {
        return "";
      },
    };
  }

  const context = {
    AbortController,
    Date,
    Error,
    JSON,
    TextEncoder,
    URL,
    console,
    document,
    fetch,
    navigator,
    window,
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(PANEL_SCRIPT, "utf8"), context, {
    filename: PANEL_SCRIPT,
  });

  const checks = [];
  checks.push(check(elements.diffCounter.textContent.includes("60000"), "initial_diff_counter"));
  checks.push(check(elements.stopButton.disabled === true, "stop_initially_disabled"));
  checks.push(check(elements.connectionResult.textContent === "Not tested", "connection_initial_status"));

  elements.diffText.value = "x".repeat(60001);
  await elements.diffText.dispatch("input");
  checks.push(check(elements.diffCounter.textContent === "60000 / 60000 bytes", "diff_counter_caps_display"));
  checks.push(check(elements.diffCounter.classList.contains("warn"), "diff_counter_warns_over_budget"));

  elements.diffText.value = makeElements().diffText.value;
  await elements.diffText.dispatch("input");
  await elements.testConnectionButton.click();

  checks.push(check(requests.length === 1, "models_fetch_called_once"));
  checks.push(check(requests[0].url === "https://api.beaverapi.com/v1/models", "models_fetch_url"));
  checks.push(check(requests[0].method === "GET", "models_fetch_method_get"));
  checks.push(check(requests[0].headers && requests[0].headers.Authorization === "Bearer test-panel-user-key", "models_fetch_uses_bearer_key"));
  checks.push(check(!requests[0].body, "models_fetch_no_body"));
  checks.push(check(elements.connectionResult.textContent.includes("Connected"), "connection_success_status"));
  checks.push(check(elements.statusText.textContent.includes("connection looks ready"), "connection_ready_status"));
  checks.push(check(elements.testConnectionButton.disabled === false, "connection_button_reenabled"));

  await elements.reviewButton.click();

  checks.push(check(requests.length === 2, "review_fetch_called_after_models"));
  const request = requests[1] || {};
  const body = request.body || {};
  const prompt = body.messages && body.messages[0] ? body.messages[0].content : "";
  checks.push(check(request.url === "https://api.beaverapi.com/v1/chat/completions", "fetch_url"));
  checks.push(check(request.method === "POST", "fetch_method_post"));
  checks.push(check(request.headers && request.headers.Authorization === "Bearer test-panel-user-key", "fetch_uses_bearer_key"));
  checks.push(check(request.headers && request.headers["X-BIBER-Client"] === "biber-azure-devops-extension-panel-mvp", "fetch_client_header"));
  checks.push(check(body.model === "biber-dev-core-v1", "body_model"));
  checks.push(check(body.stream === false, "body_stream_false"));
  checks.push(check(body.use_mentor === false, "body_mentor_disabled"));
  checks.push(check(body.task_type === "azure_devops_panel_review", "body_task_type"));
  checks.push(check(prompt.includes("[REDACTED]"), "prompt_secret_redacted"));
  checks.push(check(!prompt.includes("secret-value-for-panel-redaction"), "prompt_secret_value_absent"));
  checks.push(check(elements.outputText.textContent.includes("Panel behavior smoke review completed"), "output_rendered"));
  checks.push(check(elements.statusText.textContent.includes("Review complete"), "status_completed"));
  checks.push(check(elements.statusText.textContent.includes("Redacted 1 value"), "status_redaction_count"));
  checks.push(check(elements.reviewButton.disabled === false, "review_button_reenabled"));
  checks.push(check(elements.stopButton.disabled === true, "stop_disabled_after_completion"));
  checks.push(check(elements.statusPill.textContent === "Session only", "status_pill_reset"));

  await elements.copyButton.click();
  checks.push(check(copiedText.includes("Panel behavior smoke review completed"), "copy_output"));

  elements.diffText.value = "changed";
  await elements.sampleButton.click();
  checks.push(check(elements.diffText.value.includes("secret-value-for-panel-redaction"), "sample_diff_restored"));

  await elements.clearButton.click();
  checks.push(check(elements.outputText.textContent === "No review generated yet.", "clear_output"));
  checks.push(check(elements.statusText.textContent === "Ready for a dry review.", "clear_status"));

  elements.baseUrl.value = "http://example.com/v1";
  await elements.reviewButton.click();
  checks.push(check(requests.length === 2, "insecure_url_no_fetch"));
  checks.push(check(elements.outputText.textContent.includes("Use HTTPS"), "insecure_url_error"));

  return { checks, requests };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const checks = [check(fs.existsSync(PANEL_SCRIPT), "panel_script_exists")];
  let requests = [];
  try {
    const run = await runPanel();
    checks.push(...run.checks);
    requests = run.requests;
  } catch (error) {
    checks.push(check(false, "panel_execution", error && error.stack ? error.stack : String(error)));
  }

  const failed = checks.filter((item) => !item.ok);
  const result = {
    source: "biber_azure_devops_panel_behavior_smoke",
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
    panel_script: PANEL_SCRIPT,
    simulated_fetch_count: requests.length,
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

main().catch((error) => {
  process.stderr.write(`${error && error.stack ? error.stack : String(error)}\n`);
  process.exit(1);
});
