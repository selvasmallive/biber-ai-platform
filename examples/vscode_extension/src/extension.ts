import * as vscode from "vscode";

const API_KEY_SECRET = "biber.apiKey";
const CLIENT_NAME = "biber-vscode-extension-mvp";
const CLIENT_USER_AGENT = "BIBER-VSCode-Extension-MVP/0.3";
const OUTPUT_CHANNEL = "BIBER";
const CAPABILITIES_PATH = "/agent/capabilities";
const ORCHESTRATION_PATH = "/agent/orchestration/plan";
const DEFAULT_BASE_URL = "https://api.beaverapi.com/v1";
const LOCAL_BASE_URL = "http://127.0.0.1:8000/v1";
const DEFAULT_MODEL = "biber-dev-core-v1";

let inFlightRequest: Promise<void> | undefined;
const requestTimestamps: number[] = [];
let statusBar: vscode.StatusBarItem | undefined;
let chatViewProvider: BiberChatViewProvider | undefined;

interface BiberConfig {
  openaiBaseUrl: string;
  model: string;
  maxRequestsPerMinute: number;
  requestTimeoutMs: number;
  maxPromptChars: number;
  maxChangedPaths: number;
}

interface SetupOptions {
  offerNextAction?: boolean;
}

interface SetupEndpointPick extends vscode.QuickPickItem {
  value: "default" | "local" | "current" | "custom";
}

interface WebviewNotice {
  text: string;
  tone: "info" | "success" | "warning" | "error";
}

interface WebviewMessage {
  command?: string;
  baseUrl?: unknown;
  model?: unknown;
  apiKey?: unknown;
  instruction?: unknown;
}

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel(OUTPUT_CHANNEL);
  context.subscriptions.push(output);

  chatViewProvider = new BiberChatViewProvider(context, output);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      "biber.changeAgentView",
      chatViewProvider,
      { webviewOptions: { retainContextWhenHidden: true } }
    )
  );

  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.command = "biber.openChat";
  context.subscriptions.push(statusBar);

  context.subscriptions.push(
    vscode.commands.registerCommand("biber.openChat", () => openChatView()),
    vscode.commands.registerCommand("biber.openSetup", () => openSetup(context, output)),
    vscode.commands.registerCommand("biber.setApiKey", () => setApiKey(context, output)),
    vscode.commands.registerCommand("biber.clearApiKey", () => clearApiKey(context)),
    vscode.commands.registerCommand("biber.testConnection", () =>
      runSingleFlight(() => testConnection(context, output))
    ),
    vscode.commands.registerCommand("biber.orchestrationPlan", () =>
      runSingleFlight(() => orchestrationPlan(context, output))
    ),
    vscode.commands.registerCommand("biber.openOutput", () => output.show(true)),
    vscode.commands.registerCommand("biber.refreshSidebar", () => refreshUi(context)),
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("biber")) {
        void refreshUi(context);
      }
    }),
    vscode.window.onDidChangeActiveTextEditor(() => {
      void refreshUi(context);
    })
  );

  void refreshUi(context);
}

export function deactivate(): void {
  requestTimestamps.length = 0;
  statusBar?.dispose();
}

async function openChatView(): Promise<void> {
  await vscode.commands.executeCommand("biber.changeAgentView.focus");
}

async function openSetup(
  context: vscode.ExtensionContext,
  output: vscode.OutputChannel,
  options: SetupOptions = {}
): Promise<void> {
  const config = readConfig();
  const endpoint = await vscode.window.showQuickPick<SetupEndpointPick>(
    [
      {
        label: "Use Beaver API",
        description: DEFAULT_BASE_URL,
        detail: "Recommended for the public BIBER API gateway.",
        value: "default",
      },
      {
        label: "Use Local Vast Tunnel",
        description: LOCAL_BASE_URL,
        detail: "Use this when SSH forwards the BIBER API to localhost.",
        value: "local",
      },
      {
        label: "Keep Current Endpoint",
        description: config.openaiBaseUrl,
        detail: "Keep the currently configured BIBER API base URL.",
        value: "current",
      },
      {
        label: "Enter Custom Endpoint",
        description: "HTTPS remote URL or localhost HTTP URL",
        detail: "Use only the protected BIBER API gateway, not raw vLLM.",
        value: "custom",
      },
    ],
    {
      title: "BIBER API Setup",
      placeHolder: "Choose the BIBER API endpoint.",
      ignoreFocusOut: true,
    }
  );
  if (!endpoint) {
    return;
  }

  const selectedBaseUrl = await resolveBaseUrl(endpoint, config.openaiBaseUrl);
  if (!selectedBaseUrl) {
    return;
  }
  const normalizedBaseUrl = selectedBaseUrl.trim();
  try {
    assertAllowedBaseUrl(normalizedBaseUrl);
  } catch (error) {
    vscode.window.showErrorMessage(errorMessage(error));
    return;
  }

  const model = await vscode.window.showInputBox({
    title: "BIBER Model",
    prompt: "Enter the logical BIBER model id.",
    value: config.model || DEFAULT_MODEL,
    ignoreFocusOut: true,
    validateInput: (value) => (value.trim() ? undefined : "Model id is required."),
  });
  if (!model) {
    return;
  }

  await saveEndpointConfig(normalizedBaseUrl, model.trim());

  const existingKey = Boolean(await context.secrets.get(API_KEY_SECRET));
  if (existingKey) {
    const keyChoice = await vscode.window.showQuickPick(
      ["Keep existing API key", "Replace API key"],
      {
        title: "BIBER API Key",
        placeHolder: "Choose whether to keep or replace the stored key.",
        ignoreFocusOut: true,
      }
    );
    if (!keyChoice) {
      await refreshUi(context);
      return;
    }
    if (keyChoice === "Replace API key") {
      const stored = await promptAndStoreApiKey(context);
      if (!stored) {
        await refreshUi(context);
        return;
      }
    }
  } else {
    const stored = await promptAndStoreApiKey(context);
    if (!stored) {
      await refreshUi(context);
      return;
    }
  }

  chatViewProvider?.setNotice("BIBER setup saved.", "success");
  await refreshUi(context);
  if (options.offerNextAction === false) {
    return;
  }
  const action = await vscode.window.showInformationMessage(
    "BIBER API setup saved.",
    "Test Connection",
    "Plan Change"
  );
  if (action === "Test Connection") {
    await runSingleFlight(() => testConnection(context, output));
  } else if (action === "Plan Change") {
    await runSingleFlight(() => orchestrationPlan(context, output));
  }
}

async function resolveBaseUrl(
  endpoint: SetupEndpointPick,
  currentBaseUrl: string
): Promise<string | undefined> {
  if (endpoint.value === "default") {
    return DEFAULT_BASE_URL;
  }
  if (endpoint.value === "local") {
    return LOCAL_BASE_URL;
  }
  if (endpoint.value === "current") {
    return currentBaseUrl;
  }
  return vscode.window.showInputBox({
    title: "BIBER API Endpoint",
    prompt: "Enter the protected BIBER API base URL.",
    value: currentBaseUrl || DEFAULT_BASE_URL,
    placeHolder: DEFAULT_BASE_URL,
    ignoreFocusOut: true,
    validateInput: (value) => {
      try {
        assertAllowedBaseUrl(value.trim());
        return undefined;
      } catch (error) {
        return errorMessage(error);
      }
    },
  });
}

async function setApiKey(
  context: vscode.ExtensionContext,
  output?: vscode.OutputChannel
): Promise<void> {
  const stored = await promptAndStoreApiKey(context);
  await refreshUi(context);
  if (!stored) {
    return;
  }
  const action = await vscode.window.showInformationMessage(
    "BIBER API key saved in VS Code SecretStorage.",
    "Test Connection"
  );
  if (action === "Test Connection" && output) {
    await runSingleFlight(() => testConnection(context, output));
  }
}

async function promptAndStoreApiKey(context: vscode.ExtensionContext): Promise<boolean> {
  const apiKey = await vscode.window.showInputBox({
    title: "BIBER API Key",
    prompt: "Paste a per-user BIBER API key. It is stored only in VS Code SecretStorage.",
    password: true,
    ignoreFocusOut: true,
    validateInput: (value) =>
      value.trim().length < 16 ? "API key looks too short." : undefined,
  });
  if (!apiKey) {
    return false;
  }
  await context.secrets.store(API_KEY_SECRET, apiKey.trim());
  chatViewProvider?.setNotice("API key saved.", "success");
  return true;
}

async function clearApiKey(context: vscode.ExtensionContext): Promise<void> {
  await context.secrets.delete(API_KEY_SECRET);
  chatViewProvider?.setNotice("API key removed.", "info");
  await refreshUi(context);
  vscode.window.showInformationMessage("BIBER API key removed from VS Code SecretStorage.");
}

async function saveEndpointConfig(openaiBaseUrl: string, model: string): Promise<void> {
  await vscode.workspace
    .getConfiguration("biber")
    .update("openaiBaseUrl", openaiBaseUrl, vscode.ConfigurationTarget.Global);
  await vscode.workspace
    .getConfiguration("biber")
    .update("model", model, vscode.ConfigurationTarget.Global);
}

async function refreshUi(context: vscode.ExtensionContext): Promise<void> {
  const config = readConfig();
  const hasApiKey = Boolean(await context.secrets.get(API_KEY_SECRET));
  await chatViewProvider?.refresh();
  if (statusBar) {
    statusBar.text = hasApiKey ? "$(sparkle) BIBER AI" : "$(key) BIBER Setup";
    statusBar.tooltip = hasApiKey
      ? `Open BIBER AI Chat Agent for ${config.model} at ${config.openaiBaseUrl}.`
      : "Open BIBER AI setup.";
    statusBar.show();
  }
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
  let apiKey = await context.secrets.get(API_KEY_SECRET);
  if (!apiKey) {
    vscode.window.showWarningMessage("Set a BIBER API key before calling orchestration.");
    await openSetup(context, output, { offerNextAction: false });
    apiKey = await context.secrets.get(API_KEY_SECRET);
    if (!apiKey) {
      return;
    }
  }

  const config = readConfig();
  const activePath = activeWorkspacePath();
  const instruction = await vscode.window.showInputBox({
    title: "BIBER Change Agent",
    prompt: "Describe the change you want planned. The MVP sends path hints only, not file contents.",
    placeHolder: activePath
      ? `Plan a safe change related to ${activePath}`
      : "Plan a safe change for this repository.",
    ignoreFocusOut: true,
    validateInput: (value) => {
      if (!value.trim()) {
        return "Instruction is required.";
      }
      return value.length > config.maxPromptChars
        ? `Instruction is longer than ${config.maxPromptChars} characters.`
        : undefined;
    },
  });
  if (!instruction) {
    return;
  }

  await requestOrchestrationPlan(context, output, instruction);
}

async function requestOrchestrationPlan(
  context: vscode.ExtensionContext,
  output: vscode.OutputChannel,
  instruction: string
): Promise<void> {
  const config = readConfig();
  const apiKey = await context.secrets.get(API_KEY_SECRET);
  if (!apiKey) {
    chatViewProvider?.setNotice("Save a BIBER API key first.", "warning");
    vscode.window.showWarningMessage("Set a BIBER API key before calling orchestration.");
    await refreshUi(context);
    return;
  }

  const trimmedInstruction = instruction.trim();
  if (!trimmedInstruction) {
    chatViewProvider?.setNotice("Enter a change request first.", "warning");
    await refreshUi(context);
    return;
  }
  if (trimmedInstruction.length > config.maxPromptChars) {
    chatViewProvider?.setNotice(`Keep the request under ${config.maxPromptChars} characters.`, "warning");
    await refreshUi(context);
    return;
  }

  const changedPaths = collectChangedPaths(config.maxChangedPaths);
  const payload = {
    instruction: trimmedInstruction.slice(0, config.maxPromptChars),
    changed_paths: changedPaths,
    test_id: null,
    max_context_files: 8,
    max_rag_results: 8,
    max_scan_files: 2000,
    client: {
      name: CLIENT_NAME,
      model: config.model,
      sends_file_contents: false,
      openai_mentor: false,
    },
  };

  output.appendLine("Requesting BIBER change plan...");
  output.appendLine(`Endpoint: ${config.openaiBaseUrl}`);
  output.appendLine(`Model: ${config.model}`);
  output.appendLine(`Path hints: ${changedPaths.length ? changedPaths.join(", ") : "(none)"}`);
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
    chatViewProvider?.setNotice("Plan received. See BIBER output.", "success");
    await refreshUi(context);
  } catch (error) {
    output.appendLine(`BIBER request failed: ${errorMessage(error)}`);
    chatViewProvider?.setNotice("Plan request failed. See BIBER output.", "error");
    await refreshUi(context);
    vscode.window.showErrorMessage("BIBER change plan request failed. See output.");
  }
}

async function testConnection(
  context: vscode.ExtensionContext,
  output: vscode.OutputChannel,
  options: SetupOptions = {}
): Promise<void> {
  let apiKey = await context.secrets.get(API_KEY_SECRET);
  if (!apiKey) {
    if (options.offerNextAction === false) {
      chatViewProvider?.setNotice("Save a BIBER API key first.", "warning");
      await refreshUi(context);
      return;
    }
    vscode.window.showWarningMessage("Set a BIBER API key before testing the API.");
    await openSetup(context, output, { offerNextAction: false });
    apiKey = await context.secrets.get(API_KEY_SECRET);
    if (!apiKey) {
      return;
    }
  }

  const config = readConfig();
  output.appendLine("Testing BIBER API connection...");
  output.appendLine(`Endpoint: ${config.openaiBaseUrl}`);
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
    chatViewProvider?.setNotice("Connection ready.", "success");
    await refreshUi(context);
    vscode.window.showInformationMessage("BIBER API connection is ready.");
  } catch (error) {
    output.appendLine(`BIBER connection test failed: ${errorMessage(error)}`);
    chatViewProvider?.setNotice("Connection test failed. See BIBER output.", "error");
    await refreshUi(context);
    vscode.window.showErrorMessage("BIBER API connection test failed. See output.");
  }
}

function readConfig(): BiberConfig {
  const config = vscode.workspace.getConfiguration("biber");
  return {
    openaiBaseUrl: String(config.get("openaiBaseUrl") || DEFAULT_BASE_URL),
    model: String(config.get("model") || DEFAULT_MODEL),
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

function activeWorkspacePath(): string | undefined {
  const editor = vscode.window.activeTextEditor;
  if (editor?.document.uri.scheme !== "file") {
    return undefined;
  }
  return vscode.workspace.asRelativePath(editor.document.uri, false);
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
    "Accept": "application/json",
    "Authorization": `Bearer ${apiKey}`,
    "User-Agent": CLIENT_USER_AGENT,
    "X-BIBER-Client": CLIENT_NAME,
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

function asTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function getNonce(): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let nonce = "";
  for (let index = 0; index < 32; index += 1) {
    nonce += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return nonce;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

class BiberChatViewProvider implements vscode.WebviewViewProvider {
  private view: vscode.WebviewView | undefined;
  private notice: WebviewNotice | undefined;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly output: vscode.OutputChannel
  ) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext<unknown>,
    _token: vscode.CancellationToken
  ): void {
    this.view = webviewView;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.onDidReceiveMessage(
      (message: WebviewMessage) => {
        void this.handleMessage(message);
      },
      undefined,
      this.context.subscriptions
    );
    void this.refresh();
  }

  async refresh(): Promise<void> {
    if (!this.view) {
      return;
    }
    const config = readConfig();
    const hasApiKey = Boolean(await this.context.secrets.get(API_KEY_SECRET));
    const activePath = activeWorkspacePath();
    const nonce = getNonce();
    this.view.title = "Chat Agent";
    this.view.description = hasApiKey ? "ready" : "setup";
    this.view.webview.html = this.renderHtml(
      this.view.webview,
      config,
      hasApiKey,
      activePath,
      nonce
    );
  }

  setNotice(
    text: string | undefined,
    tone: WebviewNotice["tone"] = "info"
  ): void {
    this.notice = text ? { text, tone } : undefined;
    void this.refresh();
  }

  private async handleMessage(message: WebviewMessage): Promise<void> {
    switch (message.command) {
      case "saveSetup":
        await this.saveSetupFromView(message);
        return;
      case "clearApiKey":
        await clearApiKey(this.context);
        return;
      case "testConnection":
        if (!(await this.hasApiKeyForView())) {
          return;
        }
        this.setNotice("Testing connection...", "info");
        await runSingleFlight(() =>
          testConnection(this.context, this.output, { offerNextAction: false })
        );
        return;
      case "planChange":
        if (!(await this.hasApiKeyForView())) {
          return;
        }
        this.setNotice("Requesting plan...", "info");
        await runSingleFlight(() =>
          requestOrchestrationPlan(
            this.context,
            this.output,
            asTrimmedString(message.instruction)
          )
        );
        return;
      case "openOutput":
        this.output.show(true);
        return;
      case "openSetup":
        await openSetup(this.context, this.output);
        return;
      default:
        return;
    }
  }

  private async saveSetupFromView(message: WebviewMessage): Promise<void> {
    const baseUrl = asTrimmedString(message.baseUrl);
    const model = asTrimmedString(message.model);
    const apiKey = asTrimmedString(message.apiKey);
    if (!baseUrl) {
      this.setNotice("Endpoint is required.", "warning");
      return;
    }
    if (!model) {
      this.setNotice("Model id is required.", "warning");
      return;
    }
    try {
      assertAllowedBaseUrl(baseUrl);
    } catch (error) {
      this.setNotice(errorMessage(error), "error");
      return;
    }

    await saveEndpointConfig(baseUrl, model);
    if (apiKey) {
      if (apiKey.length < 16) {
        this.setNotice("API key looks too short.", "warning");
        await refreshUi(this.context);
        return;
      }
      await this.context.secrets.store(API_KEY_SECRET, apiKey);
      this.setNotice("Setup saved. API key stored securely.", "success");
    } else if (await this.context.secrets.get(API_KEY_SECRET)) {
      this.setNotice("Setup saved. Existing API key kept.", "success");
    } else {
      this.setNotice("Endpoint and model saved. Add an API key to continue.", "warning");
    }
    await refreshUi(this.context);
  }

  private async hasApiKeyForView(): Promise<boolean> {
    if (await this.context.secrets.get(API_KEY_SECRET)) {
      return true;
    }
    this.setNotice("Paste your API key, then click Save Setup.", "warning");
    await refreshUi(this.context);
    return false;
  }

  private renderHtml(
    webview: vscode.Webview,
    config: BiberConfig,
    hasApiKey: boolean,
    activePath: string | undefined,
    nonce: string
  ): string {
    const notice = this.notice
      ? `<div class="notice ${escapeHtml(this.notice.tone)}">${escapeHtml(this.notice.text)}</div>`
      : "";
    const keyStatus = hasApiKey ? "Ready" : "Setup needed";
    const keyDetail = hasApiKey ? "API key stored" : "API key required";
    const contextPath = activePath || "No active file";
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta
    http-equiv="Content-Security-Policy"
    content="default-src 'none'; style-src ${webview.cspSource} 'nonce-${nonce}'; script-src 'nonce-${nonce}';">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style nonce="${nonce}">
    :root {
      color-scheme: light dark;
    }
    * {
      box-sizing: border-box;
    }
    body {
      margin: 0;
      padding: 0;
      color: var(--vscode-foreground);
      background: var(--vscode-sideBar-background);
      font-family: var(--vscode-font-family);
      font-size: var(--vscode-font-size);
    }
    .shell {
      display: flex;
      flex-direction: column;
      gap: 12px;
      padding: 14px;
    }
    .hero {
      display: grid;
      grid-template-columns: 42px minmax(0, 1fr);
      align-items: center;
      gap: 10px;
    }
    .mark {
      width: 42px;
      height: 42px;
      border: 1px solid var(--vscode-button-background);
      border-radius: 6px;
      display: grid;
      place-items: center;
      color: var(--vscode-button-foreground);
      background: var(--vscode-button-background);
      font-weight: 700;
      font-size: 20px;
    }
    h1 {
      margin: 0;
      font-size: 16px;
      font-weight: 700;
      line-height: 1.2;
    }
    .subtle {
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
      margin-top: 2px;
      overflow-wrap: anywhere;
    }
    .status-row {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 8px;
      align-items: center;
    }
    .pill {
      border: 1px solid var(--vscode-editorWidget-border);
      border-radius: 999px;
      padding: 3px 8px;
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
      white-space: nowrap;
    }
    .panel {
      border: 1px solid var(--vscode-editorWidget-border);
      border-radius: 6px;
      padding: 10px;
      background: var(--vscode-editorWidget-background);
    }
    .panel-title {
      margin: 0 0 8px;
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      color: var(--vscode-descriptionForeground);
    }
    label {
      display: block;
      margin-bottom: 8px;
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
    }
    input,
    textarea {
      width: 100%;
      min-width: 0;
      margin-top: 4px;
      color: var(--vscode-input-foreground);
      background: var(--vscode-input-background);
      border: 1px solid var(--vscode-input-border, var(--vscode-editorWidget-border));
      border-radius: 4px;
      padding: 7px;
      font: inherit;
      outline: none;
    }
    textarea {
      min-height: 108px;
      resize: vertical;
      line-height: 1.35;
    }
    input:focus,
    textarea:focus {
      border-color: var(--vscode-focusBorder);
    }
    .buttons {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    button {
      min-height: 30px;
      border: 0;
      border-radius: 4px;
      padding: 6px 8px;
      color: var(--vscode-button-foreground);
      background: var(--vscode-button-background);
      font: inherit;
      cursor: pointer;
    }
    button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    button.secondary {
      color: var(--vscode-button-secondaryForeground);
      background: var(--vscode-button-secondaryBackground);
    }
    button.secondary:hover {
      background: var(--vscode-button-secondaryHoverBackground);
    }
    .notice {
      border-radius: 4px;
      padding: 8px;
      border: 1px solid var(--vscode-editorWidget-border);
      overflow-wrap: anywhere;
    }
    .notice.success {
      border-color: var(--vscode-testing-iconPassed);
    }
    .notice.warning {
      border-color: var(--vscode-testing-iconQueued);
    }
    .notice.error {
      border-color: var(--vscode-testing-iconFailed);
    }
    .kv {
      display: grid;
      gap: 6px;
      color: var(--vscode-descriptionForeground);
      font-size: 12px;
    }
    .kv div {
      overflow-wrap: anywhere;
    }
  </style>
  <title>BIBER AI</title>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="mark" aria-hidden="true">B</div>
      <div>
        <h1>BIBER AI</h1>
        <div class="subtle">Chat Agent</div>
      </div>
    </section>

    <div class="status-row">
      <div>
        <strong>${escapeHtml(keyStatus)}</strong>
        <div class="subtle">${escapeHtml(keyDetail)}</div>
      </div>
      <div class="pill">${escapeHtml(config.model)}</div>
    </div>

    ${notice}

    <section class="panel">
      <p class="panel-title">Setup</p>
      <label>
        Endpoint
        <input id="endpoint" type="url" value="${escapeHtml(config.openaiBaseUrl)}" autocomplete="off">
      </label>
      <label>
        Model
        <input id="model" type="text" value="${escapeHtml(config.model)}" autocomplete="off">
      </label>
      <label>
        API Key
        <input id="apiKey" type="password" placeholder="${hasApiKey ? "Leave blank to keep current key" : "Paste API key"}" autocomplete="off">
      </label>
      <div class="buttons">
        <button id="saveSetup" type="button">Save Setup</button>
        <button id="testConnection" class="secondary" type="button">Test API</button>
      </div>
    </section>

    <section class="panel">
      <p class="panel-title">Plan Change</p>
      <textarea id="instruction" maxlength="${config.maxPromptChars}" placeholder="Ask BIBER to plan a safe repository change."></textarea>
      <div class="buttons">
        <button id="planChange" type="button">Ask BIBER</button>
        <button id="openOutput" class="secondary" type="button">Output</button>
      </div>
    </section>

    <section class="panel">
      <p class="panel-title">Context</p>
      <div class="kv">
        <div>${escapeHtml(contextPath)}</div>
        <div>${escapeHtml(config.openaiBaseUrl)}</div>
      </div>
    </section>
  </main>

  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const byId = (id) => document.getElementById(id);
    byId("saveSetup").addEventListener("click", () => {
      const apiKey = byId("apiKey").value;
      vscode.postMessage({
        command: "saveSetup",
        baseUrl: byId("endpoint").value,
        model: byId("model").value,
        apiKey
      });
      byId("apiKey").value = "";
    });
    byId("testConnection").addEventListener("click", () => {
      vscode.postMessage({ command: "testConnection" });
    });
    byId("planChange").addEventListener("click", () => {
      vscode.postMessage({
        command: "planChange",
        instruction: byId("instruction").value
      });
    });
    byId("openOutput").addEventListener("click", () => {
      vscode.postMessage({ command: "openOutput" });
    });
  </script>
</body>
</html>`;
  }
}
