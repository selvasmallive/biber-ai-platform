import { mkdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = parseArgs(process.argv.slice(2));

const baseUrl = trimTrailingSlash(args["--base-url"] ?? "http://127.0.0.1:8090");
const artifactDir = args["--artifact-dir"] ?? null;
const localRequestId = args["--local-request-id"] ?? "wallet-send-ui-live-1";
const expectedChainFile = args["--expected-chain-file"] ?? null;
const expectedPendingFile = args["--expected-pending-file"] ?? null;
const expectedCurrentHeight = parseExpectedInteger(args["--expected-current-height"] ?? "1");
const expectedBeforeCount = parseExpectedInteger(args["--expected-before-count"] ?? "0");

if (process.env.VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI !== "true") {
  throw new Error("VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true is required for this live smoke");
}

const walletSource = await readFile(new URL("../src/wallet.tsx", import.meta.url), "utf8");
const apiSource = await readFile(new URL("../src/api.ts", import.meta.url), "utf8");

requireMarkers(walletSource, [
  "LOCAL_WALLET_SEND_UI_ENABLED",
  "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI",
  "Local Wallet Send",
  "Wallet send local-only guard",
  "Send Local",
  "wallet submit deferred",
  "pending_state_only",
  "no implicit block production",
  'const sendDisabled = !enabled || errors.length > 0 || state.status === "loading";',
]);
requireMarkers(apiSource, [
  "sendLocalWalletTransfer",
  "validateLocalWalletSendAcceptedContract",
  "acceptedStatuses: [201]",
]);
requireAbsent(walletSource, [
  "fetch(",
  "/transfers/submit",
  "/transfers/send",
  "localStorage",
  "sessionStorage",
  "indexedDB",
  "document.cookie",
  "private_key",
  "seed_phrase",
  "mnemonic",
  "signed_transaction",
]);

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

let data;
try {
  const apiModule = await vite.ssrLoadModule("/src/api.ts");
  data = await apiModule.sendLocalWalletTransfer(baseUrl, {
    local_request_id: localRequestId,
    from_address: "xriqdev1alice00000000000",
    to_address: "xriqdev1carol00000000000",
    amount_base_units: "5",
    fee_base_units: "2",
    nonce: "1",
    expires_at_height: "100",
  });
} finally {
  await vite.close();
}

validateAcceptedResponse(data);

const summary = {
  ok: "xriq-wallet-send-ui-live",
  base_url: baseUrl,
  feature_switch: "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
  local_request_id: localRequestId,
  wallet_submit_deferred: true,
  block_production_separate: true,
  source_guards: {
    shared_api_client: true,
    direct_wallet_fetch: false,
    direct_wallet_endpoint_strings: false,
    browser_persistence: false,
    sensitive_signing_fields: false,
  },
  accepted: {
    code: data.code,
    status: data.status,
    mutation: data.mutation,
    tx_hash: data.transaction.tx_hash,
    audit_event_id: data.audit_event.event_id,
    pending_file: data.pending_state.pending_file,
    chain_file: data.chain_state.chain_file,
    pending_before_count: data.pending_state.before_count,
    pending_after_count: data.pending_state.after_count,
    chain_current_height: data.chain_state.current_height,
    chain_unchanged: data.chain_state.chain_unchanged,
  },
};

if (artifactDir) {
  await mkdir(artifactDir, { recursive: true });
  await writeFile(
    `${artifactDir}/wallet-send-ui-live-accepted.json`,
    `${JSON.stringify(data, null, 2)}\n`,
    "utf8",
  );
  await writeFile(
    `${artifactDir}/summary.json`,
    `${JSON.stringify(summary, null, 2)}\n`,
    "utf8",
  );
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

function parseExpectedInteger(value) {
  if (!/^\d+$/.test(value)) {
    throw new Error(`expected integer value, got ${value}`);
  }
  return Number(value);
}

function requireMarkers(text, markers) {
  const missing = markers.filter((marker) => !text.includes(marker));
  if (missing.length > 0) {
    throw new Error(`missing source markers: ${missing.join(", ")}`);
  }
}

function requireAbsent(text, markers) {
  const found = markers.filter((marker) => text.toLowerCase().includes(marker.toLowerCase()));
  if (found.length > 0) {
    throw new Error(`forbidden source markers found: ${found.join(", ")}`);
  }
}

function validateAcceptedResponse(data) {
  const errors = [];
  if (data.code !== "wallet_send_accepted_local_only") {
    errors.push("accepted code must be wallet_send_accepted_local_only");
  }
  if (data.status !== "pending") {
    errors.push("accepted status must be pending");
  }
  if (data.mutation !== "pending_state_only") {
    errors.push("accepted mutation must be pending_state_only");
  }
  if (data.transaction.tx_hash !== data.pending_state.added_tx_hash) {
    errors.push("transaction hash must match pending_state added_tx_hash");
  }
  if (!/^[0-9a-f]{64}$/.test(data.transaction.tx_hash)) {
    errors.push("transaction hash must be 64 lowercase hex characters");
  }
  if (data.transaction.from_address !== "xriqdev1alice00000000000") {
    errors.push("transaction sender mismatch");
  }
  if (data.transaction.to_address !== "xriqdev1carol00000000000") {
    errors.push("transaction recipient mismatch");
  }
  if (data.transaction.amount_base_units !== "5") {
    errors.push("transaction amount mismatch");
  }
  if (data.transaction.fee_base_units !== "2") {
    errors.push("transaction fee mismatch");
  }
  if (data.transaction.nonce !== 1) {
    errors.push("transaction nonce mismatch");
  }
  if (data.transaction.expires_at_height !== 100) {
    errors.push("transaction expiry mismatch");
  }
  if (data.transaction.block_height !== null || data.transaction.transaction_index !== null) {
    errors.push("accepted wallet-send transaction must remain pending");
  }
  if (data.pending_state.before_count !== expectedBeforeCount) {
    errors.push("pending before_count mismatch");
  }
  if (data.pending_state.after_count !== expectedBeforeCount + 1) {
    errors.push("pending after_count must add exactly one transaction");
  }
  if (expectedPendingFile && data.pending_state.pending_file !== expectedPendingFile) {
    errors.push("pending_file mismatch");
  }
  if (expectedChainFile && data.chain_state.chain_file !== expectedChainFile) {
    errors.push("chain_file mismatch");
  }
  if (data.chain_state.current_height !== expectedCurrentHeight) {
    errors.push("chain current_height mismatch");
  }
  if (data.chain_state.chain_unchanged !== true) {
    errors.push("chain_unchanged must be true");
  }
  if (data.audit_event.event_id !== `wallet-transfer-send:${localRequestId}`) {
    errors.push("audit event id mismatch");
  }
  if (data.audit_event.resource_id !== "local_request_id") {
    errors.push("audit resource_id must stay as local_request_id marker");
  }
  if (data.audit_event.metadata.local_request_id !== localRequestId) {
    errors.push("audit metadata local_request_id mismatch");
  }
  if (data.audit_event.metadata.explicit_flag !== "--enable-local-wallet-send") {
    errors.push("audit metadata explicit flag mismatch");
  }
  if (!data.audit_event.metadata.metadata_policy.includes("no signing material")) {
    errors.push("audit metadata policy must forbid signing material");
  }
  if (!data.audit_event.metadata.metadata_policy.includes("custody material")) {
    errors.push("audit metadata policy must forbid custody material");
  }
  const sensitiveKeys = findSensitiveKeys(data);
  if (sensitiveKeys.length > 0) {
    errors.push(`sensitive response keys found: ${sensitiveKeys.join(", ")}`);
  }

  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function findSensitiveKeys(value, path = "") {
  const found = [];
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      found.push(...findSensitiveKeys(item, `${path}[${index}]`));
    });
    return found;
  }
  if (value && typeof value === "object") {
    for (const [key, child] of Object.entries(value)) {
      const childPath = path ? `${path}.${key}` : key;
      if (/(private[_-]?key|seed[_-]?phrase|mnemonic|signature|signed[_-]?transaction)/i.test(key)) {
        found.push(childPath);
      }
      found.push(...findSensitiveKeys(child, childPath));
    }
  }
  return found;
}
