import * as vscode from "vscode";

const API_KEY_SECRET = "biber.apiKey";
const OUTPUT_CHANNEL = "BIBER";
const CAPABILITIES_PATH = "/agent/capabilities";
const ORCHESTRATION_PATH = "/agent/orchestration/plan";

let inFlightRequest: Promise<void> | undefined;
const requestTimestamps: number[] = [];

interface BiberConfig {
  openaiBaseUrl: string;
  model: string;
  maxRequestsPerMinute: number;
  requestTimeoutMs: number;
  maxPromptChars: number;
  maxChangedPaths: number;
}

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel(OUTPUT_CHANNEL);
  context.subscriptions.push(output);

  context.subscriptions.push(
    vscode.commands.registerCommand("biber.setApiKey", () => setApiKey(context)),
    vscode.commands.registerCommand("biber.clearApiKey", () => clearApiKey(context)),
    vscode.commands.registerCommand("biber.testConnection", () =>
      runSingleFlight(() => testConnection(context, output))
    ),
    vscode.commands.registerCommand("biber.orchestrationPlan", () =>
      runSingleFlight(() => orchestrationPlan(context, output))
    )
  );
}

export function deactivate(): void {
  requestTimestamps.length = 0;
}

async function setApiKey(context: vscode.ExtensionContext): Promise<void> {
  const apiKey = await vscode.window.showInputBox({
    title: "BIBER API Key",
    prompt: "Enter a per-user BIBER API key.",
    password: true,
    ignoreFocusOut: true,
    validateInput: (value) =>
      value.trim().length < 16 ? "API key looks too short." : undefined,
  });
  if (!apiKey) {
    return;
  }
  await context.secrets.store(API_KEY_SECRET, apiKey.trim());
  vscode.window.showInformationMessage("BIBER API key saved in VS Code SecretStorage.");
}

async function clearApiKey(context: vscode.ExtensionContext): Promise<void> {
  await context.secrets.delete(API_KEY_SECRET);
  vscode.window.showInformationMessage("BIBER API key removed from VS Code SecretStorage.");
}

async function runSingleFlight(operation: () => Promise<void>): Promise<void> {
  if (inFlightRequest) {
    vscode.window.showWarningMessage("A BIBER request is already running.");
    return;
  }
  inFlightRequest = operation().finally(() => {
    inFlightRequest = undefined;
  });
  await inFlightRequest;
}

async function orchestrationPlan(
  context: vscode.ExtensionContext,
  output: vscode.OutputChannel
): Promise<void> {
  const config = readConfig();
  const apiKey = await context.secrets.get(API_KEY_SECRET);
  if (!apiKey) {
    vscode.window.showWarningMessage("Set a BIBER API key before calling orchestration.");
    await vscode.commands.executeCommand("biber.setApiKey");
    return;
  }

  const instruction = await vscode.window.showInputBox({
    title: "BIBER Orchestration Plan",
    prompt: "Describe the coding task. The MVP sends path hints only, not file contents.",
    ignoreFocusOut: true,
    validateInput: (value) =>
      value.length > config.maxPromptChars
        ? `Instruction is longer than ${config.maxPromptChars} characters.`
        : undefined,
  });
  if (!instruction) {
    return;
  }

  const changedPaths = collectChangedPaths(config.maxChangedPaths);
  const payload = {
    instruction: instruction.slice(0, config.maxPromptChars),
    changed_paths: changedPaths,
    test_id: null,
    max_context_files: 8,
    max_rag_results: 8,
    max_scan_files: 2000,
    client: {
      name: "biber-vscode-extension-mvp",
      model: config.model,
      sends_file_contents: false,
      openai_mentor: false,
    },
  };

  output.appendLine("Requesting BIBER orchestration plan...");
  output.show(true);

  try {
    assertAllowedBaseUrl(config.openaiBaseUrl);
    checkRateLimit(config.maxRequestsPerMinute);
    const response = await postJson(
      config.openaiBaseUrl,
      ORCHESTRATION_PATH,
      apiKey,
      payload,
      config.requestTimeoutMs
    );
    output.appendLine(JSON.stringify(redactForOutput(response), null, 2));
  } catch (error) {
    output.appendLine(`BIBER request failed: ${errorMessage(error)}`);
    vscode.window.showErrorMessage("BIBER orchestration request failed. See output.");
  }
}

async function testConnection(
  context: vscode.ExtensionContext,
  output: vscode.OutputChannel
): Promise<void> {
  const config = readConfig();
  const apiKey = await context.secrets.get(API_KEY_SECRET);
  if (!apiKey) {
    vscode.window.showWarningMessage("Set a BIBER API key before testing the API.");
    await vscode.commands.executeCommand("biber.setApiKey");
    return;
  }

  output.appendLine("Testing BIBER API connection...");
  output.show(true);

  try {
    assertAllowedBaseUrl(config.openaiBaseUrl);
    checkRateLimit(config.maxRequestsPerMinute);
    const response = await getJson(
      config.openaiBaseUrl,
      CAPABILITIES_PATH,
      apiKey,
      config.requestTimeoutMs
    );
    const summary = summarizeCapabilities(response);
    output.appendLine(JSON.stringify(summary, null, 2));
    vscode.window.showInformationMessage("BIBER API connection is ready.");
  } catch (error) {
    output.appendLine(`BIBER connection test failed: ${errorMessage(error)}`);
    vscode.window.showErrorMessage("BIBER API connection test failed. See output.");
  }
}

function readConfig(): BiberConfig {
  const config = vscode.workspace.getConfiguration("biber");
  return {
    openaiBaseUrl: String(config.get("openaiBaseUrl") || "https://api.beaverapi.com/v1"),
    model: String(config.get("model") || "biber-dev-core-v1"),
    maxRequestsPerMinute: clampNumber(config.get("maxRequestsPerMinute"), 1, 60, 12),
    requestTimeoutMs: clampNumber(config.get("requestTimeoutMs"), 5000, 120000, 30000),
    maxPromptChars: clampNumber(config.get("maxPromptChars"), 200, 20000, 4000),
    maxChangedPaths: clampNumber(config.get("maxChangedPaths"), 1, 100, 20),
  };
}

function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, Math.floor(parsed)));
}

function checkRateLimit(maxRequestsPerMinute: number): void {
  const now = Date.now();
  const windowStart = now - 60_000;
  while (requestTimestamps.length > 0 && requestTimestamps[0] < windowStart) {
    requestTimestamps.shift();
  }
  if (requestTimestamps.length >= maxRequestsPerMinute) {
    throw new Error("Local BIBER request limit reached. Wait before trying again.");
  }
  requestTimestamps.push(now);
}

function assertAllowedBaseUrl(openaiBaseUrl: string): void {
  let parsed: URL;
  try {
    parsed = new URL(openaiBaseUrl);
  } catch {
    throw new Error("BIBER API base URL is not a valid URL.");
  }
  const host = parsed.hostname.toLowerCase();
  const localhost = host === "localhost" || host === "127.0.0.1" || host === "::1";
  if (parsed.protocol === "https:" || (parsed.protocol === "http:" && localhost)) {
    return;
  }
  throw new Error("BIBER API URL must use HTTPS, except localhost development tunnels.");
}

function collectChangedPaths(maxChangedPaths: number): string[] {
  const paths = new Set<string>();
  const editor = vscode.window.activeTextEditor;
  if (editor?.document.uri.scheme === "file") {
    paths.add(vscode.workspace.asRelativePath(editor.document.uri, false));
  }
  return Array.from(paths).slice(0, maxChangedPaths);
}

async function postJson(
  openaiBaseUrl: string,
  path: string,
  apiKey: string,
  payload: unknown,
  timeoutMs: number
): Promise<unknown> {
  return requestJson(openaiBaseUrl, path, apiKey, timeoutMs, "POST", payload);
}

async function getJson(
  openaiBaseUrl: string,
  path: string,
  apiKey: string,
  timeoutMs: number
): Promise<unknown> {
  return requestJson(openaiBaseUrl, path, apiKey, timeoutMs, "GET");
}

async function requestJson(
  openaiBaseUrl: string,
  path: string,
  apiKey: string,
  timeoutMs: number,
  method: "GET" | "POST",
  payload?: unknown
): Promise<unknown> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const headers: Record<string, string> = {
    "Authorization": `Bearer ${apiKey}`,
  };
  const body = payload === undefined ? undefined : JSON.stringify(payload);
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  try {
    const response = await fetch(`${openaiBaseUrl.replace(/\/+$/, "")}${path}`, {
      method,
      headers,
      body,
      signal: controller.signal,
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${text.slice(0, 400)}`);
    }
    return text ? JSON.parse(text) : {};
  } finally {
    clearTimeout(timeout);
  }
}

function summarizeCapabilities(value: unknown): unknown {
  if (!value || typeof value !== "object") {
    return { service: "unknown", server_side_protections: "missing" };
  }
  const payload = value as Record<string, unknown>;
  const features = objectValue(payload.features);
  const externalAgentApi = objectValue(features.external_agent_api);
  const protections = objectValue(externalAgentApi.server_side_protections);
  return redactForOutput({
    service: payload.service,
    version: payload.version,
    default_model: payload.default_model,
    server_side_protections: {
      api_guard_enabled: protections.api_guard_enabled,
      scope: protections.scope,
      identity: protections.identity,
      max_request_bytes: protections.max_request_bytes,
      rate_limit_requests_per_minute: protections.rate_limit_requests_per_minute,
      client_side_guards_are_not_trusted: protections.client_side_guards_are_not_trusted,
    },
  });
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function redactForOutput(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => redactForOutput(item));
  }
  if (value && typeof value === "object") {
    const redacted: Record<string, unknown> = {};
    for (const [key, nested] of Object.entries(value)) {
      if (/api[_-]?key|authorization|token|secret/i.test(key)) {
        redacted[key] = "<redacted>";
      } else {
        redacted[key] = redactForOutput(nested);
      }
    }
    return redacted;
  }
  return value;
}

function errorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
