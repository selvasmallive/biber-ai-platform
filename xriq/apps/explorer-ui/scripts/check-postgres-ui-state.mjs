import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = parseArgs(process.argv.slice(2));

const baseUrl = trimTrailingSlash(args["--base-url"] ?? "http://127.0.0.1:8090");
const expect = args["--expect"] ?? "available";
const artifact = args["--artifact"] ?? null;

if (!["available", "disabled"].includes(expect)) {
  throw new Error(`--expect must be available or disabled, got ${expect}`);
}

const response = await fetch(`${baseUrl}/api/v1/admin/postgres/read-model-status`, {
  headers: { Accept: "application/json" },
});

let statusState;
let payload = null;
if (response.status === 404) {
  if (expect !== "disabled") {
    throw new Error("expected available Postgres read model, got HTTP 404 disabled route");
  }
  statusState = { status: "disabled", data: null, error: null };
} else if (response.ok) {
  payload = await response.json();
  if (expect !== "available") {
    throw new Error(`expected disabled Postgres read model, got HTTP ${response.status}`);
  }
  statusState = { status: "ready", data: payload, error: null };
} else {
  throw new Error(
    `unexpected Postgres read-model HTTP status ${response.status}: ${await response.text()}`,
  );
}

const vite = await createServer({
  root,
  configFile: false,
  logLevel: "error",
  appType: "custom",
  optimizeDeps: {
    entries: [],
    noDiscovery: true,
  },
  server: {
    middlewareMode: true,
  },
});

let rows;
try {
  const adminModule = await vite.ssrLoadModule("/src/admin.tsx");
  rows = Object.fromEntries(adminModule.postgresReadModelRows(statusState));
} finally {
  await vite.close();
}

if (expect === "disabled") {
  requireRow(rows, "Status", "disabled");
  requireRow(rows, "Blocks", "-");
  requireRow(rows, "Read Only", "-");
} else {
  requireRow(rows, "Status", "available");
  requireRow(rows, "Source", "postgres-read-model");
  requireRow(rows, "Read Only", "true");
  requireExpectedRow(rows, "Database", "--expected-database");
  requireExpectedRow(rows, "Blocks", "--expected-blocks");
  requireExpectedRow(rows, "Transactions", "--expected-transactions");
  requireExpectedRow(rows, "Accounts", "--expected-accounts");
  requireExpectedRow(rows, "Account History", "--expected-account-history");
  requireExpectedRow(rows, "Audit Events", "--expected-audit-events");
}

const summary = {
  ok: "xriq-admin-postgres-ui-state",
  base_url: baseUrl,
  expected: expect,
  http_status: response.status,
  rows,
  payload,
};

if (artifact) {
  await writeFile(artifact, `${JSON.stringify(summary, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify(summary, null, 2));

function parseArgs(values) {
  const parsed = {};
  for (let index = 0; index < values.length; index += 2) {
    const flag = values[index];
    const value = values[index + 1];
    if (!flag?.startsWith("--")) {
      throw new Error(`unexpected argument: ${flag}`);
    }
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`missing value for ${flag}`);
    }
    if (parsed[flag] !== undefined) {
      throw new Error(`duplicate argument: ${flag}`);
    }
    parsed[flag] = value;
  }
  return parsed;
}

function trimTrailingSlash(value) {
  return value.replace(/\/+$/, "");
}

function requireExpectedRow(rows, label, flag) {
  const expected = args[flag];
  if (expected === undefined) {
    return;
  }
  requireRow(rows, label, parseExpectedValue(expected));
}

function requireRow(rows, label, expected) {
  const actual = rows[label];
  if (actual !== expected) {
    throw new Error(`expected ${label}=${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

function parseExpectedValue(value) {
  return /^[0-9]+$/.test(value) ? Number(value) : value;
}
