import { existsSync, readdirSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { createServer } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const repoRoot = fileURLToPath(new URL("../../../..", import.meta.url));
const args = parseArgs(process.argv.slice(2));

const fixturePath =
  args["--fixture"] ??
  join(repoRoot, "xriq/fixtures/phase1_2/wallet-transfer-send-to-pending-contract.json");
const artifactPath = args["--artifact"] ?? latestWalletSendArtifact();

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

let api;
try {
  api = await vite.ssrLoadModule("/src/api.ts");
} finally {
  await vite.close();
}

const fixture = readJson(fixturePath);
requireEqual(fixture, "status", "guarded-local-api-implemented", "fixture");
requireEqual(
  fixture,
  "implementation_status",
  "request-and-serve-explicit-local-flag",
  "fixture",
);

const fixtureErrors = validateAcceptedResponse(
  api,
  fixture.example_accepted_response,
  "fixture example",
  {
    localRequestId: "local_request_id",
    pendingFile: "target/xriq-devnet-pending.tsv",
    chainFile: "target/xriq-devnet.bin",
    fromAddress: "xriqdev1alice00000000000",
    toAddress: "xriqdev1carol00000000000",
  },
);

let artifact = null;
let artifactErrors = [];
if (artifactPath) {
  artifact = readJson(artifactPath);
  const metadata = artifact.audit_event?.metadata ?? {};
  artifactErrors = validateAcceptedResponse(api, artifact, "local smoke artifact", {
    localRequestId: metadata.local_request_id,
    pendingFile: artifact.pending_state?.pending_file,
    chainFile: artifact.chain_state?.chain_file,
    fromAddress: artifact.transaction?.from_address,
    toAddress: artifact.transaction?.to_address,
  });
}

const errors = [...fixtureErrors, ...artifactErrors];
if (errors.length > 0) {
  throw new Error(errors.join("\n"));
}

const summary = {
  ok: "xriq-wallet-send-accepted-client-contract",
  fixture: fixturePath,
  fixture_checked: true,
  artifact: artifactPath,
  artifact_checked: Boolean(artifactPath),
  validator: "validateLocalWalletSendAcceptedContract",
};

console.log(JSON.stringify(summary, null, 2));

function validateAcceptedResponse(apiModule, payload, label, expectations) {
  const errors = [];
  if (!payload || typeof payload !== "object") {
    return [`${label}: accepted response must be an object`];
  }
  const validatorErrors = apiModule.validateLocalWalletSendAcceptedContract(
    payload,
    expectations,
  );
  for (const error of validatorErrors) {
    errors.push(`${label}: ${error}`);
  }
  for (const field of findSensitiveFields(payload)) {
    errors.push(`${label}: sensitive field is forbidden: ${field}`);
  }
  return errors;
}

function findSensitiveFields(value, path = "") {
  const matches = [];
  if (!value || typeof value !== "object") {
    return matches;
  }
  for (const [key, child] of Object.entries(value)) {
    const childPath = path ? `${path}.${key}` : key;
    if (/(private[_-]?key|seed[_-]?phrase|mnemonic|signature|signed[_-]?transaction)/i.test(key)) {
      matches.push(childPath);
    }
    matches.push(...findSensitiveFields(child, childPath));
  }
  return matches;
}

function latestWalletSendArtifact() {
  const targetDir = join(repoRoot, "xriq/target");
  if (!existsSync(targetDir)) {
    return null;
  }
  const candidateDirs = readdirSync(targetDir)
    .filter((name) => name.startsWith("xriq-phase1-2-wallet-send-smoke-"))
    .sort()
    .reverse();
  for (const dir of candidateDirs) {
    const artifact = join(targetDir, dir, "api/wallet-send-accepted-local.json");
    if (existsSync(artifact)) {
      return artifact;
    }
  }
  return null;
}

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

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function requireEqual(payload, key, expected, label) {
  if (payload?.[key] !== expected) {
    throw new Error(`${label}: expected ${key}=${JSON.stringify(expected)}`);
  }
}
