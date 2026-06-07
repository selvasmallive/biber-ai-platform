import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = parseArgs(process.argv.slice(2));

const baseUrl = trimTrailingSlash(args["--base-url"] ?? "http://127.0.0.1:8090");
const artifactDir = args["--artifact-dir"] ?? null;
const walletLocalRequestId =
  args["--wallet-local-request-id"] ?? "block-production-admin-refresh-wallet-1";
const blockLocalRequestId =
  args["--block-local-request-id"] ?? "block-production-admin-refresh-block-1";

const ALICE = "xriqdev1alice00000000000";
const CAROL = "xriqdev1carol00000000000";
const PRODUCER = "xriqdev1author00000000000";

if (process.env.VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI !== "true") {
  throw new Error(
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true is required for this admin refresh smoke",
  );
}

const adminSource = await readFile(new URL("../src/admin.tsx", import.meta.url), "utf8");
requireMarkers(adminSource, [
  "export function adminSnapshotRows",
  "AdminSnapshotRows",
  "Local Block Production",
  "Produce Local",
  "chain_and_pending_state_local_only",
  "wallet send remains separate",
  "wallet submit deferred",
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

let walletSend;
let snapshotBefore;
let statusBefore;
let rowsBefore;
let producedBlock;
let statusAfter;
let snapshotAfter;
let rowsAfter;
try {
  const apiModule = await vite.ssrLoadModule("/src/api.ts");
  const adminModule = await vite.ssrLoadModule("/src/admin.tsx");

  walletSend = await apiModule.sendLocalWalletTransfer(baseUrl, {
    local_request_id: walletLocalRequestId,
    from_address: ALICE,
    to_address: CAROL,
    amount_base_units: "5",
    fee_base_units: "2",
    nonce: "1",
    expires_at_height: "100",
  });
  snapshotBefore = await apiModule.loadExplorerSnapshot(baseUrl);
  statusBefore = await apiModule.loadWalletTransactionStatus(
    baseUrl,
    walletSend.transaction.tx_hash,
  );
  rowsBefore = adminModule.adminSnapshotRows(snapshotBefore, statusBefore, "ready");

  producedBlock = await apiModule.produceLocalBlock(baseUrl, {
    local_request_id: blockLocalRequestId,
    producer: PRODUCER,
    max_transactions: "4",
    timestamp_ms: "2000",
  });

  statusAfter = await apiModule.loadWalletTransactionStatus(
    baseUrl,
    walletSend.transaction.tx_hash,
  );
  snapshotAfter = await apiModule.loadExplorerSnapshot(baseUrl);
  rowsAfter = adminModule.adminSnapshotRows(snapshotAfter, statusAfter, "ready");
} finally {
  await vite.close();
}

const txHash = walletSend.transaction.tx_hash;
validateRowsBefore(rowsBefore, txHash);
validateRowsAfter(rowsAfter);
validateStatusAndBlock(statusAfter, producedBlock, txHash);

const sensitiveKeys = [
  ...findSensitiveKeys(rowsBefore, "rowsBefore"),
  ...findSensitiveKeys(rowsAfter, "rowsAfter"),
  ...findSensitiveKeys(statusAfter, "statusAfter"),
  ...findSensitiveKeys(producedBlock, "producedBlock"),
];
if (sensitiveKeys.length > 0) {
  throw new Error(`sensitive response keys found: ${sensitiveKeys.join(", ")}`);
}

const summary = {
  ok: "xriq-block-production-admin-refresh-live",
  base_url: baseUrl,
  feature_switch: "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
  wallet_local_request_id: walletLocalRequestId,
  block_local_request_id: blockLocalRequestId,
  wallet_send_tx_hash: txHash,
  produced_block_hash: producedBlock.block.block_hash,
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
  confirmed_status: {
    status: statusAfter.status,
    block_height: statusAfter.block_height,
    transaction_index: statusAfter.transaction_index,
  },
  artifacts: {
    rows_before: artifactDir
      ? join(artifactDir, "block-production-admin-rows-before.json")
      : null,
    rows_after: artifactDir
      ? join(artifactDir, "block-production-admin-rows-after.json")
      : null,
    produced_block: artifactDir
      ? join(artifactDir, "block-production-admin-produced-block.json")
      : null,
    confirmed_status: artifactDir
      ? join(artifactDir, "block-production-admin-confirmed-status.json")
      : null,
  },
};

if (artifactDir) {
  await mkdir(artifactDir, { recursive: true });
  await writeJson(join(artifactDir, "block-production-admin-rows-before.json"), rowsBefore);
  await writeJson(join(artifactDir, "block-production-admin-rows-after.json"), rowsAfter);
  await writeJson(join(artifactDir, "block-production-admin-produced-block.json"), producedBlock);
  await writeJson(
    join(artifactDir, "block-production-admin-confirmed-status.json"),
    statusAfter,
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

function validateRowsBefore(rows, txHash) {
  const errors = [];
  if (rowValue(rows.network, "Height") !== 1) {
    errors.push("before network height must be 1");
  }
  if (rowValue(rows.node, "Pending") !== 1) {
    errors.push("before node pending must be 1");
  }
  if (rowValue(rows.wallet, "Pending") !== 1) {
    errors.push("before wallet pending must be 1");
  }
  if (rowValue(rows.wallet, "Submit") !== "disabled") {
    errors.push("before wallet submit must remain disabled");
  }
  if (rowValue(rows.wallet, "Send") !== "disabled") {
    errors.push("before wallet send read-only status row must remain disabled");
  }
  if (rowValue(rows.mempool, "Pending") !== 1) {
    errors.push("before mempool pending must be 1");
  }
  if (rowValue(rows.mempool, "First Pending") !== txHash) {
    errors.push("before first pending hash mismatch");
  }
  if (rowValue(rows.mempool, "Wallet Tx Status") !== "pending") {
    errors.push("before wallet tx status must be pending");
  }
  if (rowValue(rows.mempool, "Wallet Tx Block") !== "null") {
    errors.push("before wallet tx block must render null");
  }
  if (rowValue(rows.mempool, "Wallet Tx Index") !== "null") {
    errors.push("before wallet tx index must render null");
  }
  if (rowValue(rows.mempool, "Produce Block") !== "disabled") {
    errors.push("before produce block read-only status row must remain disabled");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateRowsAfter(rows) {
  const errors = [];
  if (rowValue(rows.network, "Height") !== 2) {
    errors.push("after network height must be 2");
  }
  if (rowValue(rows.node, "Pending") !== 0) {
    errors.push("after node pending must be 0");
  }
  if (rowValue(rows.wallet, "Pending") !== 0) {
    errors.push("after wallet pending must be 0");
  }
  if (rowValue(rows.wallet, "Submit") !== "disabled") {
    errors.push("after wallet submit must remain disabled");
  }
  if (rowValue(rows.wallet, "Send") !== "disabled") {
    errors.push("after wallet send read-only status row must remain disabled");
  }
  if (rowValue(rows.mempool, "Pending") !== 0) {
    errors.push("after mempool pending must be 0");
  }
  if (rowValue(rows.mempool, "Entries") !== 0) {
    errors.push("after mempool entries must be 0");
  }
  if (rowValue(rows.mempool, "First Pending") !== "-") {
    errors.push("after first pending must be empty");
  }
  if (rowValue(rows.mempool, "Wallet Tx Status") !== "-") {
    errors.push("after wallet tx status row must be empty without pending tx");
  }
  if (rowValue(rows.mempool, "Produce Block") !== "disabled") {
    errors.push("after produce block read-only status row must remain disabled");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateStatusAndBlock(status, block, txHash) {
  const errors = [];
  if (status.tx_hash !== txHash) {
    errors.push("confirmed status tx_hash mismatch");
  }
  if (status.status !== "confirmed") {
    errors.push("confirmed status must be confirmed");
  }
  if (status.block_height !== 2) {
    errors.push("confirmed status block_height must be 2");
  }
  if (status.transaction_index !== 0) {
    errors.push("confirmed status transaction_index must be 0");
  }
  if (block.confirmed_transactions.length !== 1) {
    errors.push("produced block must confirm exactly one transaction");
  }
  if (block.confirmed_transactions[0]?.tx_hash !== txHash) {
    errors.push("produced block confirmed tx hash mismatch");
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
