import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = parseArgs(process.argv.slice(2));

const baseUrl = trimTrailingSlash(args["--base-url"] ?? "http://127.0.0.1:8090");
const artifactDir = args["--artifact-dir"] ?? null;
const blockLocalRequestId =
  args["--block-local-request-id"] ?? "block-production-no-pending-block-1";

const PRODUCER = "xriqdev1author00000000000";

if (process.env.VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI !== "true") {
  throw new Error(
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true is required for this no-pending smoke",
  );
}

const adminSource = await readFile(new URL("../src/admin.tsx", import.meta.url), "utf8");
const apiSource = await readFile(new URL("../src/api.ts", import.meta.url), "utf8");

requireMarkers(adminSource, [
  "export function adminSnapshotRows",
  "AdminSnapshotRows",
  "Local Block Production",
  "Produce Local",
  'const produceDisabled = !enabled || pendingCount <= 0 || state.status === "loading";',
]);
requireMarkers(apiSource, [
  "produceLocalBlockNoPendingRefusal",
  "validateLocalBlockProductionNoPendingContract",
  "LOCAL_BLOCK_PRODUCTION_NO_PENDING_CODE",
  "no_pending_transactions",
  "acceptedStatuses: [400]",
]);
requireAbsent(adminSource, [
  "fetch(",
  "/api/v1/blocks/produce",
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

let snapshotBefore;
let rowsBefore;
let refusal;
let snapshotAfter;
let rowsAfter;
try {
  const apiModule = await vite.ssrLoadModule("/src/api.ts");
  const adminModule = await vite.ssrLoadModule("/src/admin.tsx");

  snapshotBefore = await apiModule.loadExplorerSnapshot(baseUrl);
  rowsBefore = adminModule.adminSnapshotRows(snapshotBefore, null, "idle");
  refusal = await apiModule.produceLocalBlockNoPendingRefusal(baseUrl, {
    local_request_id: blockLocalRequestId,
    producer: PRODUCER,
    max_transactions: "4",
    timestamp_ms: "2000",
  });
  snapshotAfter = await apiModule.loadExplorerSnapshot(baseUrl);
  rowsAfter = adminModule.adminSnapshotRows(snapshotAfter, null, "idle");
} finally {
  await vite.close();
}

validateNoPendingRows(rowsBefore, "before");
validateNoPendingRows(rowsAfter, "after");
validateRefusal(refusal);
validateNoStateChange(snapshotBefore, snapshotAfter);

const sensitiveKeys = [
  ...findSensitiveKeys(snapshotBefore, "snapshotBefore"),
  ...findSensitiveKeys(rowsBefore, "rowsBefore"),
  ...findSensitiveKeys(refusal, "refusal"),
  ...findSensitiveKeys(snapshotAfter, "snapshotAfter"),
  ...findSensitiveKeys(rowsAfter, "rowsAfter"),
];
if (sensitiveKeys.length > 0) {
  throw new Error(`sensitive response keys found: ${sensitiveKeys.join(", ")}`);
}

const summary = {
  ok: "xriq-block-production-no-pending-live",
  base_url: baseUrl,
  feature_switch: "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
  block_local_request_id: blockLocalRequestId,
  no_pending_refusal: {
    code: refusal.error.code,
    message: refusal.error.message,
  },
  admin_rows_before: {
    network_height: rowValue(rowsBefore.network, "Height"),
    node_pending: rowValue(rowsBefore.node, "Pending"),
    wallet_pending: rowValue(rowsBefore.wallet, "Pending"),
    mempool_pending: rowValue(rowsBefore.mempool, "Pending"),
    first_pending: rowValue(rowsBefore.mempool, "First Pending"),
    wallet_tx_status: rowValue(rowsBefore.mempool, "Wallet Tx Status"),
    produce_block_status: rowValue(rowsBefore.mempool, "Produce Block"),
  },
  admin_rows_after: {
    network_height: rowValue(rowsAfter.network, "Height"),
    node_pending: rowValue(rowsAfter.node, "Pending"),
    wallet_pending: rowValue(rowsAfter.wallet, "Pending"),
    mempool_pending: rowValue(rowsAfter.mempool, "Pending"),
    first_pending: rowValue(rowsAfter.mempool, "First Pending"),
    wallet_tx_status: rowValue(rowsAfter.mempool, "Wallet Tx Status"),
    produce_block_status: rowValue(rowsAfter.mempool, "Produce Block"),
  },
  state_unchanged: {
    height: snapshotAfter.network.current_height,
    latest_block_hash: snapshotAfter.network.latest_block_hash,
    state_root: snapshotAfter.network.state_root,
    pending_count: snapshotAfter.mempool.pending_count,
  },
  artifacts: {
    rows_before: artifactDir
      ? join(artifactDir, "block-production-no-pending-rows-before.json")
      : null,
    refusal: artifactDir
      ? join(artifactDir, "block-production-no-pending-refusal.json")
      : null,
    rows_after: artifactDir
      ? join(artifactDir, "block-production-no-pending-rows-after.json")
      : null,
    snapshot_before: artifactDir
      ? join(artifactDir, "block-production-no-pending-snapshot-before.json")
      : null,
    snapshot_after: artifactDir
      ? join(artifactDir, "block-production-no-pending-snapshot-after.json")
      : null,
  },
};

if (artifactDir) {
  await mkdir(artifactDir, { recursive: true });
  await writeJson(
    join(artifactDir, "block-production-no-pending-rows-before.json"),
    rowsBefore,
  );
  await writeJson(
    join(artifactDir, "block-production-no-pending-refusal.json"),
    refusal,
  );
  await writeJson(
    join(artifactDir, "block-production-no-pending-rows-after.json"),
    rowsAfter,
  );
  await writeJson(
    join(artifactDir, "block-production-no-pending-snapshot-before.json"),
    snapshotBefore,
  );
  await writeJson(
    join(artifactDir, "block-production-no-pending-snapshot-after.json"),
    snapshotAfter,
  );
  await writeJson(join(artifactDir, "summary.json"), summary);
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

function rowValue(rows, label) {
  const row = rows.find(([candidate]) => candidate === label);
  if (!row) {
    throw new Error(`missing admin row: ${label}`);
  }
  return row[1];
}

function validateNoPendingRows(rows, context) {
  const errors = [];
  if (rowValue(rows.network, "Height") !== 1) {
    errors.push(`${context} network height must be 1`);
  }
  if (rowValue(rows.node, "Pending") !== 0) {
    errors.push(`${context} node pending must be 0`);
  }
  if (rowValue(rows.wallet, "Pending") !== 0) {
    errors.push(`${context} wallet pending must be 0`);
  }
  if (rowValue(rows.wallet, "Submit") !== "disabled") {
    errors.push(`${context} wallet submit must remain disabled`);
  }
  if (rowValue(rows.wallet, "Send") !== "disabled") {
    errors.push(`${context} wallet send must remain disabled`);
  }
  if (rowValue(rows.mempool, "Pending") !== 0) {
    errors.push(`${context} mempool pending must be 0`);
  }
  if (rowValue(rows.mempool, "Entries") !== 0) {
    errors.push(`${context} mempool entries must be 0`);
  }
  if (rowValue(rows.mempool, "First Pending") !== "-") {
    errors.push(`${context} first pending must be empty`);
  }
  if (rowValue(rows.mempool, "Wallet Tx Status") !== "-") {
    errors.push(`${context} wallet tx status row must be empty`);
  }
  if (rowValue(rows.mempool, "Produce Block") !== "disabled") {
    errors.push(`${context} produce block read-only status row must remain disabled`);
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateRefusal(data) {
  const errors = [];
  if (data.error.code !== "no_pending_transactions") {
    errors.push("refusal code must be no_pending_transactions");
  }
  if (!data.error.message.includes("at least one pending transaction")) {
    errors.push("refusal message must explain the pending transaction requirement");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateNoStateChange(before, after) {
  const errors = [];
  if (before.network.current_height !== 1 || after.network.current_height !== 1) {
    errors.push("network height must remain 1");
  }
  if (before.network.latest_block_hash !== after.network.latest_block_hash) {
    errors.push("latest block hash must not change");
  }
  if (before.network.state_root !== after.network.state_root) {
    errors.push("state root must not change");
  }
  if (before.overview.chain.current_height !== after.overview.chain.current_height) {
    errors.push("overview height must not change");
  }
  if (before.mempool.pending_count !== 0 || after.mempool.pending_count !== 0) {
    errors.push("mempool pending count must remain zero");
  }
  if (
    before.walletStatus.pending_transactions !== 0 ||
    after.walletStatus.pending_transactions !== 0
  ) {
    errors.push("wallet pending count must remain zero");
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

async function writeJson(path, payload) {
  await writeFile(path, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}
