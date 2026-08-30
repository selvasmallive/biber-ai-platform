import * as vscode from "vscode";

const API_KEY_SECRET = "biber.apiKey";
const CLIENT_NAME = "biber-vscode-extension-mvp";
const CLIENT_USER_AGENT = "BIBER-VSCode-Extension-MVP/0.2";
const OUTPUT_CHANNEL = "BIBER";
const CAPABILITIES_PATH = "/agent/capabilities";
const ORCHESTRATION_PATH = "/agent/orchestration/plan";
const DEFAULT_BASE_URL = "https://api.beaverapi.com/v1";
const LOCAL_BASE_URL = "http://127.0.0.1:8000/v1";
const DEFAULT_MODEL = "biber-dev-core-v1";

let inFlightRequest: Promise<void> | undefined;
const requestTimestamps: number[] = [];
let statusBar: vscode.StatusBarItem | undefined;
let treeProvider: BiberTreeProvider | undefined;

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

type TreeAction = {
  label: string;
  description?: string;
  tooltip?: string;
  icon: string;
  command?: vscode.Command;
};

export function activate(context: vscode.ExtensionContext): void {
  const output = vscode.window.createOutputChannel(OUTPUT_CHANNEL);
  context.subscriptions.push(output);

  treeProvider = new BiberTreeProvider(context);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("biber.changeAgentView", treeProvider)
  );

  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.command = "biber.openSetup";
  context.subscriptions.push(statusBar);

  context.subscriptions.push(
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
    })
  );

  void refreshUi(context);
}

export function deactivate(): void {
  requestTimestamps.length = 0;
  statusBar?.dispose();
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

  await vscode.workspace
    .getConfiguration("biber")
    .update("openaiBaseUrl", normalizedBaseUrl, vscode.ConfigurationTarget.Global);
  await vscode.workspace
    .getConfiguration("biber")
    .update("model", model.trim(), vscode.ConfigurationTarget.Global);

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
  return true;
}

async function clearApiKey(context: vscode.ExtensionContext): Promise<void> {
  await context.secrets.delete(API_KEY_SECRET);
  await refreshUi(context);
  vscode.window.showInformationMessage("BIBER API key removed from VS Code SecretStorage.");
}

async function refreshUi(context: vscode.ExtensionContext): Promise<void> {
  const config = readConfig();
  const hasApiKey = Boolean(await context.secrets.get(API_KEY_SECRET));
  treeProvider?.refresh();
  if (statusBar) {
    statusBar.text = hasApiKey ? "$(sparkle) BIBER Ready" : "$(key) BIBER Setup";
    statusBar.tooltip = hasApiKey
      ? `BIBER is configured for ${config.model} at ${config.openaiBaseUrl}. Click to edit setup.`
      : "Set up your BIBER API endpoint and API key.";
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
  const config = readConfig();
  let apiKey = await context.secrets.get(API_KEY_SECRET);
  if (!apiKey) {
    vscode.window.showWarningMessage("Set a BIBER API key before calling orchestration.");
    await openSetup(context, output, { offerNextAction: false });
    apiKey = await context.secrets.get(API_KEY_SECRET);
    if (!apiKey) {
      return;
    }
  }

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

  const changedPaths = collectChangedPaths(config.maxChangedPaths);
  const payload = {
    instruction: instruction.slice(0, config.maxPromptChars),
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
  } catch (error) {
    output.appendLine(`BIBER request failed: ${errorMessage(error)}`);
    vscode.window.showErrorMessage("BIBER change plan request failed. See output.");
  }
}

async function testConnection(
  context: vscode.ExtensionContext,
  output: vscode.OutputChannel
): Promise<void> {
  const config = readConfig();
  let apiKey = await context.secrets.get(API_KEY_SECRET);
  if (!apiKey) {
    vscode.window.showWarningMessage("Set a BIBER API key before testing the API.");
    await openSetup(context, output, { offerNextAction: false });
    apiKey = await context.secrets.get(API_KEY_SECRET);
    if (!apiKey) {
      return;
    }
  }

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
    await refreshUi(context);
    vscode.window.showInformationMessage("BIBER API connection is ready.");
  } catch (error) {
    output.appendLine(`BIBER connection test failed: ${errorMessage(error)}`);
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

class BiberTreeProvider implements vscode.TreeDataProvider<BiberTreeItem> {
  private readonly emitter = new vscode.EventEmitter<BiberTreeItem | undefined>();
  readonly onDidChangeTreeData = this.emitter.event;

  constructor(private readonly context: vscode.ExtensionContext) {}

  refresh(): void {
    this.emitter.fire(undefined);
  }

  getTreeItem(element: BiberTreeItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: BiberTreeItem): Promise<BiberTreeItem[]> {
    if (element) {
      return [];
    }
    const config = readConfig();
    const hasApiKey = Boolean(await this.context.secrets.get(API_KEY_SECRET));
    const activePath = activeWorkspacePath();
    const actions: TreeAction[] = [
      {
        label: hasApiKey ? "API Key Configured" : "Setup API Connection",
        description: hasApiKey ? "SecretStorage" : "required",
        tooltip: hasApiKey
          ? "A BIBER API key is stored securely in VS Code SecretStorage."
          : "Open the guided setup flow to enter your API endpoint, model, and API key.",
        icon: hasApiKey ? "shield" : "key",
        command: {
          command: "biber.openSetup",
          title: "BIBER: Setup API Connection",
        },
      },
      {
        label: "Test API Connection",
        description: config.model,
        tooltip: config.openaiBaseUrl,
        icon: "plug",
        command: {
          command: "biber.testConnection",
          title: "BIBER: Test API Connection",
        },
      },
      {
        label: "Plan Change",
        description: activePath ? "uses active file path hint" : "planning-only",
        tooltip: "Ask BIBER for a safe repo-aware plan. This MVP sends path hints only.",
        icon: "sparkle",
        command: {
          command: "biber.orchestrationPlan",
          title: "BIBER: Plan Change",
        },
      },
      {
        label: "Show Output",
        description: "redacted logs",
        tooltip: "Open the BIBER output channel.",
        icon: "output",
        command: {
          command: "biber.openOutput",
          title: "BIBER: Show Output",
        },
      },
      {
        label: "Endpoint",
        description: config.openaiBaseUrl,
        tooltip: "Configured BIBER API base URL.",
        icon: "globe",
      },
      {
        label: "Workspace Context",
        description: activePath || "no active file",
        tooltip: "The MVP sends bounded path hints, not file contents.",
        icon: "folder",
      },
    ];
    return actions.map((action) => new BiberTreeItem(action));
  }
}

class BiberTreeItem extends vscode.TreeItem {
  constructor(action: TreeAction) {
    super(action.label, vscode.TreeItemCollapsibleState.None);
    this.description = action.description;
    this.tooltip = action.tooltip || action.description;
    this.iconPath = new vscode.ThemeIcon(action.icon);
    this.command = action.command;
  }
}
