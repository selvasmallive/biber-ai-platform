import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = parseArgs(process.argv.slice(2));

const baseUrl = trimTrailingSlash(args["--base-url"] ?? "http://127.0.0.1:8090");
const artifactDir = args["--artifact-dir"] ?? null;
const localRequestId = args["--local-request-id"] ?? "wallet-send-refresh-live-1";
const expectedChainFile = args["--expected-chain-file"] ?? null;
const expectedPendingFile = args["--expected-pending-file"] ?? null;

const ALICE = "xriqdev1alice00000000000";
const CAROL = "xriqdev1carol00000000000";

if (process.env.VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI !== "true") {
  throw new Error("VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true is required for this refresh smoke");
}

const walletSource = await readFile(new URL("../src/wallet.tsx", import.meta.url), "utf8");
requireMarkers(walletSource, [
  "export function walletActivityRows",
  "Wallet Activity",
  "read-only confirmed and pending",
  "source: \"pending\"",
  "block: \"pending\"",
  "transactionIndex: \"pending\"",
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

let accepted;
let snapshot;
let transactionStatus;
let aliceRows;
let carolRows;
try {
  const apiModule = await vite.ssrLoadModule("/src/api.ts");
  const walletModule = await vite.ssrLoadModule("/src/wallet.tsx");

  accepted = await apiModule.sendLocalWalletTransfer(baseUrl, {
    local_request_id: localRequestId,
    from_address: ALICE,
    to_address: CAROL,
    amount_base_units: "5",
    fee_base_units: "2",
    nonce: "1",
    expires_at_height: "100",
  });
  snapshot = await apiModule.loadExplorerSnapshot(baseUrl);
  transactionStatus = await apiModule.loadWalletTransactionStatus(
    baseUrl,
    accepted.transaction.tx_hash,
  );
  aliceRows = walletModule.walletActivityRows(snapshot, ALICE);
  carolRows = walletModule.walletActivityRows(snapshot, CAROL);
} finally {
  await vite.close();
}

const txHash = accepted.transaction.tx_hash;
const alicePendingRow = findPendingRow(aliceRows, txHash);
const carolPendingRow = findPendingRow(carolRows, txHash);

validateAccepted(accepted);
validateSnapshot(snapshot, txHash);
validateTransactionStatus(transactionStatus, txHash);
validateActivityRow(alicePendingRow, {
  context: "sender wallet activity",
  direction: "sent",
  counterparty: CAROL,
});
validateActivityRow(carolPendingRow, {
  context: "recipient wallet activity",
  direction: "received",
  counterparty: ALICE,
});

const sensitiveKeys = [
  ...findSensitiveKeys(accepted, "accepted"),
  ...findSensitiveKeys(snapshot, "snapshot"),
  ...findSensitiveKeys(transactionStatus, "transactionStatus"),
  ...findSensitiveKeys(aliceRows, "aliceRows"),
  ...findSensitiveKeys(carolRows, "carolRows"),
];
if (sensitiveKeys.length > 0) {
  throw new Error(`sensitive response keys found: ${sensitiveKeys.join(", ")}`);
}

const summary = {
  ok: "xriq-wallet-send-refresh-live",
  base_url: baseUrl,
  feature_switch: "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
  local_request_id: localRequestId,
  wallet_submit_deferred: true,
  block_production_separate: true,
  wallet_send_tx_hash: txHash,
  refresh: {
    snapshot_loaded: true,
    current_height: snapshot.network.current_height,
    overview_pending_transactions: snapshot.overview.chain.pending_transactions,
    mempool_pending_count: snapshot.mempool.pending_count,
    wallet_status_pending_transactions: snapshot.walletStatus.pending_transactions,
    wallet_status_send_capability: snapshot.walletStatus.capabilities.send,
    node_status_pending_transactions: snapshot.nodeStatus.pending_transactions,
    transaction_status: transactionStatus.status,
    sender_activity_source: alicePendingRow.source,
    sender_activity_direction: alicePendingRow.direction,
    recipient_activity_source: carolPendingRow.source,
    recipient_activity_direction: carolPendingRow.direction,
  },
  artifacts: {
    accepted: artifactDir ? join(artifactDir, "wallet-send-refresh-accepted.json") : null,
    snapshot: artifactDir ? join(artifactDir, "wallet-send-refresh-snapshot.json") : null,
    transaction_status: artifactDir
      ? join(artifactDir, "wallet-send-refresh-transaction-status.json")
      : null,
    activity_rows: artifactDir ? join(artifactDir, "wallet-send-refresh-activity-rows.json") : null,
  },
};

if (artifactDir) {
  await mkdir(artifactDir, { recursive: true });
  await writeJson(join(artifactDir, "wallet-send-refresh-accepted.json"), accepted);
  await writeJson(join(artifactDir, "wallet-send-refresh-snapshot.json"), snapshot);
  await writeJson(join(artifactDir, "wallet-send-refresh-transaction-status.json"), transactionStatus);
  await writeJson(join(artifactDir, "wallet-send-refresh-activity-rows.json"), {
    alice: aliceRows,
    carol: carolRows,
  });
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
    throw new Error(`forbidden wallet source markers found: ${found.join(", ")}`);
  }
}

function findPendingRow(rows, txHash) {
  const row = rows.find((candidate) => candidate.txHash === txHash && candidate.source === "pending");
  if (!row) {
    throw new Error(`pending wallet activity row not found for ${txHash}`);
  }
  return row;
}

function validateAccepted(data) {
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
    errors.push("accepted tx_hash must match pending_state added_tx_hash");
  }
  if (expectedPendingFile && data.pending_state.pending_file !== expectedPendingFile) {
    errors.push("accepted pending_file mismatch");
  }
  if (expectedChainFile && data.chain_state.chain_file !== expectedChainFile) {
    errors.push("accepted chain_file mismatch");
  }
  if (data.chain_state.chain_unchanged !== true) {
    errors.push("accepted wallet-send must leave chain unchanged");
  }
  if (data.audit_event.event_id !== `wallet-transfer-send:${localRequestId}`) {
    errors.push("accepted audit event id mismatch");
  }
  if (data.audit_event.metadata.local_request_id !== localRequestId) {
    errors.push("accepted audit metadata local_request_id mismatch");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateSnapshot(data, txHash) {
  const errors = [];
  const entry = data.mempool.entries.find((candidate) => candidate.tx_hash === txHash);
  if (!entry) {
    errors.push("snapshot mempool does not contain accepted tx_hash");
  }
  if (data.network.current_height !== 1) {
    errors.push("snapshot network height must remain 1 after wallet send");
  }
  if (data.overview.chain.current_height !== 1) {
    errors.push("snapshot overview height must remain 1 after wallet send");
  }
  if (data.mempool.current_height !== 1) {
    errors.push("snapshot mempool height must remain 1 after wallet send");
  }
  if (data.mempool.pending_count !== 1) {
    errors.push("snapshot mempool pending_count must be 1");
  }
  if (data.overview.chain.pending_transactions !== 1) {
    errors.push("snapshot overview pending_transactions must be 1");
  }
  if (data.walletStatus.pending_transactions !== 1) {
    errors.push("wallet status pending_transactions must be 1");
  }
  if (data.nodeStatus.pending_transactions !== 1) {
    errors.push("node status pending_transactions must be 1");
  }
  if (data.walletStatus.capabilities.submit !== false) {
    errors.push("wallet submit capability must remain false");
  }
  if (data.nodeStatus.block_production_status !== "disabled") {
    errors.push("node block_production_status must remain disabled");
  }
  if (entry) {
    if (entry.from_address !== ALICE) {
      errors.push("snapshot mempool sender mismatch");
    }
    if (entry.to_address !== CAROL) {
      errors.push("snapshot mempool recipient mismatch");
    }
    if (entry.amount_base_units !== "5") {
      errors.push("snapshot mempool amount mismatch");
    }
    if (entry.fee_base_units !== "2") {
      errors.push("snapshot mempool fee mismatch");
    }
    if (entry.nonce !== 1) {
      errors.push("snapshot mempool nonce mismatch");
    }
    if (entry.status !== "pending") {
      errors.push("snapshot mempool status must be pending");
    }
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateTransactionStatus(data, txHash) {
  const errors = [];
  if (data.tx_hash !== txHash) {
    errors.push("wallet transaction status tx_hash mismatch");
  }
  if (data.status !== "pending") {
    errors.push("wallet transaction status must remain pending");
  }
  if (data.block_height !== null) {
    errors.push("pending wallet transaction block_height must be null");
  }
  if (data.block_hash !== null) {
    errors.push("pending wallet transaction block_hash must be null");
  }
  if (data.transaction_index !== null) {
    errors.push("pending wallet transaction transaction_index must be null");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateActivityRow(row, { context, direction, counterparty }) {
  const errors = [];
  if (row.source !== "pending") {
    errors.push(`${context}: source must be pending`);
  }
  if (row.status !== "pending") {
    errors.push(`${context}: status must be pending`);
  }
  if (row.direction !== direction) {
    errors.push(`${context}: direction mismatch`);
  }
  if (row.amount !== "5") {
    errors.push(`${context}: amount mismatch`);
  }
  if (row.fee !== "2") {
    errors.push(`${context}: fee mismatch`);
  }
  if (row.nonce !== 1) {
    errors.push(`${context}: nonce mismatch`);
  }
  if (row.block !== "pending") {
    errors.push(`${context}: block must render as pending`);
  }
  if (row.transactionIndex !== "pending") {
    errors.push(`${context}: transaction index must render as pending`);
  }
  if (row.counterparty !== counterparty) {
    errors.push(`${context}: counterparty mismatch`);
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
