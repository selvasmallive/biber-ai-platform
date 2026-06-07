import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = parseArgs(process.argv.slice(2));

const baseUrl = trimTrailingSlash(args["--base-url"] ?? "http://127.0.0.1:8090");
const artifactDir = args["--artifact-dir"] ?? null;
const walletLocalRequestId =
  args["--wallet-local-request-id"] ?? "block-production-ui-wallet-1";
const blockLocalRequestId =
  args["--block-local-request-id"] ?? "block-production-ui-block-1";
const expectedChainFile = args["--expected-chain-file"] ?? null;
const expectedPendingFile = args["--expected-pending-file"] ?? null;

const ALICE = "xriqdev1alice00000000000";
const CAROL = "xriqdev1carol00000000000";
const PRODUCER = "xriqdev1author00000000000";

if (process.env.VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI !== "true") {
  throw new Error(
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true is required for this live smoke",
  );
}

const adminSource = await readFile(new URL("../src/admin.tsx", import.meta.url), "utf8");
const apiSource = await readFile(new URL("../src/api.ts", import.meta.url), "utf8");

requireMarkers(adminSource, [
  "LOCAL_BLOCK_PRODUCTION_UI_ENABLED",
  "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI",
  "Local Block Production",
  "block-production local-only guard",
  "Produce Local",
  "chain_and_pending_state_local_only",
  "wallet send remains separate",
  "wallet submit deferred",
  "explicit local action",
  "produceLocalBlock",
  "validateLocalBlockProductionAcceptedContract",
  'const produceDisabled = !enabled || pendingCount <= 0 || state.status === "loading";',
]);
requireMarkers(apiSource, [
  "produceLocalBlock",
  "LocalBlockProductionRequest",
  "validateLocalBlockProductionAcceptedContract",
  "acceptedStatuses: [201]",
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
let pendingStatus;
let producedBlock;
let confirmedStatus;
let snapshotAfter;
try {
  const apiModule = await vite.ssrLoadModule("/src/api.ts");

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
  pendingStatus = await apiModule.loadWalletTransactionStatus(
    baseUrl,
    walletSend.transaction.tx_hash,
  );
  producedBlock = await apiModule.produceLocalBlock(baseUrl, {
    local_request_id: blockLocalRequestId,
    producer: PRODUCER,
    max_transactions: "4",
    timestamp_ms: "2000",
  });
  const contractErrors = apiModule.validateLocalBlockProductionAcceptedContract(producedBlock, {
    localRequestId: blockLocalRequestId,
    pendingFile: expectedPendingFile ?? undefined,
    chainFile: expectedChainFile ?? undefined,
    producer: PRODUCER,
    maxTransactions: 4,
  });
  if (contractErrors.length > 0) {
    throw new Error(contractErrors.join("; "));
  }
  confirmedStatus = await apiModule.loadWalletTransactionStatus(
    baseUrl,
    walletSend.transaction.tx_hash,
  );
  snapshotAfter = await apiModule.loadExplorerSnapshot(baseUrl);
} finally {
  await vite.close();
}

const txHash = walletSend.transaction.tx_hash;
validatePendingSetup(walletSend, snapshotBefore, pendingStatus, txHash);
validateProducedBlock(producedBlock, txHash);
validateConfirmedSnapshot(snapshotAfter, confirmedStatus, txHash);

const sensitiveKeys = [
  ...findSensitiveKeys(walletSend, "walletSend"),
  ...findSensitiveKeys(snapshotBefore, "snapshotBefore"),
  ...findSensitiveKeys(pendingStatus, "pendingStatus"),
  ...findSensitiveKeys(producedBlock, "producedBlock"),
  ...findSensitiveKeys(confirmedStatus, "confirmedStatus"),
  ...findSensitiveKeys(snapshotAfter, "snapshotAfter"),
];
if (sensitiveKeys.length > 0) {
  throw new Error(`sensitive response keys found: ${sensitiveKeys.join(", ")}`);
}

const summary = {
  ok: "xriq-block-production-ui-live",
  base_url: baseUrl,
  feature_switch: "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
  wallet_local_request_id: walletLocalRequestId,
  block_local_request_id: blockLocalRequestId,
  wallet_submit_deferred: true,
  wallet_send_separate: true,
  block_production_explicit: true,
  source_guards: {
    shared_api_client: true,
    direct_admin_fetch: false,
    direct_block_endpoint_string: false,
    browser_persistence: false,
    sensitive_signing_fields: false,
  },
  produced: {
    code: producedBlock.code,
    status: producedBlock.status,
    mutation: producedBlock.mutation,
    tx_hash: txHash,
    block_height: producedBlock.block.height,
    block_hash: producedBlock.block.block_hash,
    audit_event_id: producedBlock.audit_event.event_id,
    pending_file: producedBlock.pending_state.pending_file,
    chain_file: producedBlock.chain_state.chain_file,
    pending_before_count: producedBlock.pending_state.before_count,
    pending_after_count: producedBlock.pending_state.after_count,
    chain_previous_height: producedBlock.chain_state.previous_height,
    chain_current_height: producedBlock.chain_state.current_height,
  },
  refresh_after_production: {
    current_height: snapshotAfter.network.current_height,
    mempool_pending_count: snapshotAfter.mempool.pending_count,
    wallet_status_pending_transactions: snapshotAfter.walletStatus.pending_transactions,
    transaction_status: confirmedStatus.status,
    transaction_block_height: confirmedStatus.block_height,
    transaction_index: confirmedStatus.transaction_index,
  },
  artifacts: {
    wallet_send: artifactDir ? join(artifactDir, "block-production-ui-wallet-send.json") : null,
    snapshot_before: artifactDir
      ? join(artifactDir, "block-production-ui-snapshot-before.json")
      : null,
    pending_status: artifactDir
      ? join(artifactDir, "block-production-ui-pending-status.json")
      : null,
    produced_block: artifactDir
      ? join(artifactDir, "block-production-ui-produced-block.json")
      : null,
    confirmed_status: artifactDir
      ? join(artifactDir, "block-production-ui-confirmed-status.json")
      : null,
    snapshot_after: artifactDir
      ? join(artifactDir, "block-production-ui-snapshot-after.json")
      : null,
  },
};

if (artifactDir) {
  await mkdir(artifactDir, { recursive: true });
  await writeJson(join(artifactDir, "block-production-ui-wallet-send.json"), walletSend);
  await writeJson(join(artifactDir, "block-production-ui-snapshot-before.json"), snapshotBefore);
  await writeJson(join(artifactDir, "block-production-ui-pending-status.json"), pendingStatus);
  await writeJson(join(artifactDir, "block-production-ui-produced-block.json"), producedBlock);
  await writeJson(join(artifactDir, "block-production-ui-confirmed-status.json"), confirmedStatus);
  await writeJson(join(artifactDir, "block-production-ui-snapshot-after.json"), snapshotAfter);
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

function validatePendingSetup(send, snapshot, status, txHash) {
  const errors = [];
  if (send.code !== "wallet_send_accepted_local_only") {
    errors.push("wallet setup code must be wallet_send_accepted_local_only");
  }
  if (send.status !== "pending") {
    errors.push("wallet setup status must be pending");
  }
  if (send.mutation !== "pending_state_only") {
    errors.push("wallet setup mutation must be pending_state_only");
  }
  if (send.transaction.tx_hash !== txHash) {
    errors.push("wallet setup tx hash mismatch");
  }
  if (send.pending_state.after_count !== 1) {
    errors.push("wallet setup pending after_count must be 1");
  }
  if (snapshot.network.current_height !== 1) {
    errors.push("snapshot before block production must remain at height 1");
  }
  if (snapshot.mempool.pending_count !== 1) {
    errors.push("snapshot before block production must have one pending transaction");
  }
  if (status.status !== "pending") {
    errors.push("wallet transaction status before production must be pending");
  }
  if (status.block_height !== null || status.transaction_index !== null) {
    errors.push("wallet transaction status before production must not have block position");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateProducedBlock(data, txHash) {
  const errors = [];
  if (data.code !== "block_production_accepted_local_only") {
    errors.push("block production code must be block_production_accepted_local_only");
  }
  if (data.status !== "confirmed") {
    errors.push("block production status must be confirmed");
  }
  if (data.mutation !== "chain_and_pending_state_local_only") {
    errors.push("block production mutation must be chain_and_pending_state_local_only");
  }
  if (data.pending_state.before_count !== 1) {
    errors.push("block production pending before_count must be 1");
  }
  if (data.pending_state.after_count !== 0) {
    errors.push("block production pending after_count must be 0");
  }
  if (data.chain_state.previous_height !== 1 || data.chain_state.current_height !== 2) {
    errors.push("block production must advance from height 1 to height 2");
  }
  if (data.block.height !== 2) {
    errors.push("produced block height must be 2");
  }
  if (data.confirmed_transactions.length !== 1) {
    errors.push("block production must confirm exactly one transaction");
  }
  const confirmed = data.confirmed_transactions[0];
  if (!confirmed || confirmed.tx_hash !== txHash) {
    errors.push("confirmed transaction hash mismatch");
  }
  if (confirmed?.status !== "confirmed") {
    errors.push("confirmed transaction status mismatch");
  }
  if (confirmed?.block_height !== data.block.height) {
    errors.push("confirmed transaction block_height mismatch");
  }
  if (data.pending_state.removed_tx_hashes.join(",") !== txHash) {
    errors.push("removed pending hash mismatch");
  }
  if (data.audit_event.event_id !== `block-production:${blockLocalRequestId}`) {
    errors.push("block production audit event id mismatch");
  }
  if (data.audit_event.metadata.local_request_id !== blockLocalRequestId) {
    errors.push("block production audit local_request_id mismatch");
  }
  if (data.audit_event.metadata.explicit_flag !== "--enable-local-block-production") {
    errors.push("block production audit explicit flag mismatch");
  }
  if (!data.audit_event.metadata.metadata_policy.includes("no signing material")) {
    errors.push("block production audit policy must forbid signing material");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateConfirmedSnapshot(snapshot, status, txHash) {
  const errors = [];
  if (snapshot.network.current_height !== 2) {
    errors.push("snapshot after block production must be height 2");
  }
  if (snapshot.overview.chain.current_height !== 2) {
    errors.push("overview after block production must be height 2");
  }
  if (snapshot.mempool.pending_count !== 0) {
    errors.push("mempool after block production must be empty");
  }
  if (snapshot.walletStatus.pending_transactions !== 0) {
    errors.push("wallet status after block production must have zero pending transactions");
  }
  if (status.tx_hash !== txHash) {
    errors.push("confirmed wallet status tx_hash mismatch");
  }
  if (status.status !== "confirmed") {
    errors.push("wallet transaction status after production must be confirmed");
  }
  if (status.block_height !== 2) {
    errors.push("wallet transaction status block height must be 2");
  }
  if (status.transaction_index !== 0) {
    errors.push("wallet transaction status transaction index must be 0");
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
