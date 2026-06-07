import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createServer } from "vite";

const root = fileURLToPath(new URL("..", import.meta.url));
const args = parseArgs(process.argv.slice(2));

const baseUrl = trimTrailingSlash(args["--base-url"] ?? "http://127.0.0.1:8090");
const artifactDir = args["--artifact-dir"] ?? null;
const expectedChainFile = args["--expected-chain-file"] ?? null;
const expectedPendingFile = args["--expected-pending-file"] ?? null;
const fixturePath =
  args["--fixture"] ?? join(root, "../../fixtures/phase1_3/local-wallet-behavior-v1.json");

if (process.env.VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI !== "true") {
  throw new Error(
    "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true is required for this Phase 1.3 smoke",
  );
}
if (process.env.VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI !== "true") {
  throw new Error(
    "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true is required for this Phase 1.3 smoke",
  );
}

const fixture = JSON.parse(await readFile(fixturePath, "utf8"));
validateFixtureShape(fixture);
const identities = fixture.identities;
const walletStep = fixtureStep(fixture, "wallet_send_to_pending");
const blockStep = fixtureStep(fixture, "produce_one_block");
const walletRequest = walletStep.request;
const blockRequest = blockStep.request;
const postBlock = fixture.post_block_expectations;

const walletSource = await readFile(new URL("../src/wallet.tsx", import.meta.url), "utf8");
const adminSource = await readFile(new URL("../src/admin.tsx", import.meta.url), "utf8");
const apiSource = await readFile(new URL("../src/api.ts", import.meta.url), "utf8");

requireMarkers(walletSource, [
  "LOCAL_WALLET_SEND_UI_ENABLED",
  "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI",
  "Local Wallet Send",
  "wallet submit deferred",
  "export function walletActivityRows",
  "source: \"pending\"",
]);
requireMarkers(adminSource, [
  "LOCAL_BLOCK_PRODUCTION_UI_ENABLED",
  "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI",
  "Local Block Production",
  "wallet send remains separate",
  "wallet submit deferred",
  "export function adminSnapshotRows",
  'const produceDisabled = !enabled || pendingCount <= 0 || state.status === "loading";',
]);
requireMarkers(apiSource, [
  "sendLocalWalletTransfer",
  "produceLocalBlock",
  "produceLocalBlockNoPendingRefusal",
  "loadWalletMutationRefusal",
  "loadWalletBalance",
  "loadWalletHistory",
  "validateLocalWalletSendAcceptedContract",
  "validateLocalBlockProductionAcceptedContract",
  "validateLocalBlockProductionNoPendingContract",
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

let apiModule;
let walletModule;
let adminModule;
let walletSend;
let walletSubmitRefusal;
let snapshotBefore;
let pendingStatus;
let walletRowsBefore;
let adminRowsBefore;
let producedBlock;
let confirmedStatus;
let snapshotAfter;
let walletRowsAfter;
let adminRowsAfter;
let balances;
let histories;
let noPendingRefusal;
let snapshotAfterNoPendingRefusal;
let adminRowsAfterNoPendingRefusal;

try {
  apiModule = await vite.ssrLoadModule("/src/api.ts");
  walletModule = await vite.ssrLoadModule("/src/wallet.tsx");
  adminModule = await vite.ssrLoadModule("/src/admin.tsx");

  walletSubmitRefusal = await apiModule.loadWalletMutationRefusal(baseUrl, "submit");
  walletSend = await apiModule.sendLocalWalletTransfer(baseUrl, {
    local_request_id: walletStep.local_request_id,
    from_address: walletRequest.from_address,
    to_address: walletRequest.to_address,
    amount_base_units: walletRequest.amount_base_units,
    fee_base_units: walletRequest.fee_base_units,
    nonce: String(walletRequest.nonce),
    expires_at_height: String(walletRequest.expires_at_height),
  });
  validateContractErrors(
    apiModule.validateLocalWalletSendAcceptedContract(walletSend, {
      localRequestId: walletStep.local_request_id,
      pendingFile: expectedPendingFile ?? undefined,
      chainFile: expectedChainFile ?? undefined,
      fromAddress: walletRequest.from_address,
      toAddress: walletRequest.to_address,
    }),
    "wallet-send accepted contract",
  );

  snapshotBefore = await apiModule.loadExplorerSnapshot(baseUrl);
  pendingStatus = await apiModule.loadWalletTransactionStatus(
    baseUrl,
    walletSend.transaction.tx_hash,
  );
  walletRowsBefore = {
    sender: walletModule.walletActivityRows(snapshotBefore, identities.sender),
    recipient: walletModule.walletActivityRows(snapshotBefore, identities.behavior_recipient),
  };
  adminRowsBefore = adminModule.adminSnapshotRows(snapshotBefore, pendingStatus, "ready");

  producedBlock = await apiModule.produceLocalBlock(baseUrl, {
    local_request_id: blockStep.local_request_id,
    producer: blockRequest.producer,
    max_transactions: String(blockRequest.max_transactions),
    timestamp_ms: String(blockRequest.timestamp_ms),
  });
  validateContractErrors(
    apiModule.validateLocalBlockProductionAcceptedContract(producedBlock, {
      localRequestId: blockStep.local_request_id,
      pendingFile: expectedPendingFile ?? undefined,
      chainFile: expectedChainFile ?? undefined,
      producer: blockRequest.producer,
      maxTransactions: Number(blockRequest.max_transactions),
    }),
    "block-production accepted contract",
  );

  confirmedStatus = await apiModule.loadWalletTransactionStatus(
    baseUrl,
    walletSend.transaction.tx_hash,
  );
  snapshotAfter = await apiModule.loadExplorerSnapshot(baseUrl);
  walletRowsAfter = {
    sender: walletModule.walletActivityRows(snapshotAfter, identities.sender),
    recipient: walletModule.walletActivityRows(snapshotAfter, identities.behavior_recipient),
  };
  adminRowsAfter = adminModule.adminSnapshotRows(snapshotAfter, confirmedStatus, "ready");

  balances = {};
  for (const account of postBlock.accounts) {
    balances[account.address] = await apiModule.loadWalletBalance(baseUrl, account.address);
  }
  histories = {
    sender: await apiModule.loadWalletHistory(baseUrl, identities.sender),
    recipient: await apiModule.loadWalletHistory(baseUrl, identities.behavior_recipient),
  };

  noPendingRefusal = await apiModule.produceLocalBlockNoPendingRefusal(baseUrl, {
    local_request_id: "phase1-3-ui-no-pending",
    producer: blockRequest.producer,
    max_transactions: String(blockRequest.max_transactions),
    timestamp_ms: String(Number(blockRequest.timestamp_ms) + 1),
  });
  snapshotAfterNoPendingRefusal = await apiModule.loadExplorerSnapshot(baseUrl);
  adminRowsAfterNoPendingRefusal = adminModule.adminSnapshotRows(
    snapshotAfterNoPendingRefusal,
    confirmedStatus,
    "idle",
  );
} finally {
  await vite.close();
}

const txHash = walletSend.transaction.tx_hash;
const blockHash = producedBlock.block.block_hash;

validateWalletSubmitRefusal(walletSubmitRefusal);
validateWalletSend(walletSend, walletStep, txHash);
validatePendingRefresh(snapshotBefore, pendingStatus, walletRowsBefore, adminRowsBefore, walletStep, txHash);
validateProducedBlock(producedBlock, blockStep, txHash);
validateConfirmedRefresh(
  snapshotAfter,
  confirmedStatus,
  walletRowsAfter,
  adminRowsAfter,
  blockStep,
  txHash,
);
validateBalances(balances, postBlock.accounts);
validateHistories(histories, fixture, txHash);
validateNoPendingRefusal(noPendingRefusal, snapshotAfter, snapshotAfterNoPendingRefusal);
validateAdminRowsAfterNoPending(adminRowsAfterNoPendingRefusal);

const sensitiveKeys = [
  ...findSensitiveKeys(walletSubmitRefusal, "walletSubmitRefusal"),
  ...findSensitiveKeys(walletSend, "walletSend"),
  ...findSensitiveKeys(snapshotBefore, "snapshotBefore"),
  ...findSensitiveKeys(pendingStatus, "pendingStatus"),
  ...findSensitiveKeys(walletRowsBefore, "walletRowsBefore"),
  ...findSensitiveKeys(adminRowsBefore, "adminRowsBefore"),
  ...findSensitiveKeys(producedBlock, "producedBlock"),
  ...findSensitiveKeys(confirmedStatus, "confirmedStatus"),
  ...findSensitiveKeys(snapshotAfter, "snapshotAfter"),
  ...findSensitiveKeys(walletRowsAfter, "walletRowsAfter"),
  ...findSensitiveKeys(adminRowsAfter, "adminRowsAfter"),
  ...findSensitiveKeys(balances, "balances"),
  ...findSensitiveKeys(histories, "histories"),
  ...findSensitiveKeys(noPendingRefusal, "noPendingRefusal"),
];
if (sensitiveKeys.length > 0) {
  throw new Error(`sensitive response keys found: ${sensitiveKeys.join(", ")}`);
}

const summary = {
  ok: "xriq-phase1-3-wallet-behavior-ui-live",
  base_url: baseUrl,
  fixture: fixturePath,
  feature_switches: {
    wallet_send_ui: "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI=true",
    block_production_ui: "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI=true",
  },
  wallet_submit_deferred: true,
  default_controls_disabled_by_source: true,
  shared_client_flow: true,
  wallet_local_request_id: walletStep.local_request_id,
  block_local_request_id: blockStep.local_request_id,
  wallet_send_tx_hash: txHash,
  produced_block_hash: blockHash,
  refresh_before_block: {
    current_height: snapshotBefore.network.current_height,
    mempool_pending_count: snapshotBefore.mempool.pending_count,
    wallet_pending_transactions: snapshotBefore.walletStatus.pending_transactions,
    transaction_status: pendingStatus.status,
    sender_activity_source: findActivityRow(
      walletRowsBefore.sender,
      txHash,
      "pending",
      postBlock.wallet_history.behavior_transaction_direction,
    ).source,
    recipient_activity_source: findActivityRow(
      walletRowsBefore.recipient,
      txHash,
      "pending",
      postBlock.wallet_history.recipient_transaction_direction,
    ).source,
    admin_wallet_tx_status: rowValue(adminRowsBefore.mempool, "Wallet Tx Status"),
  },
  refresh_after_block: {
    current_height: snapshotAfter.network.current_height,
    stored_blocks: snapshotAfter.overview.chain.stored_blocks,
    confirmed_transactions: snapshotAfter.overview.totals.transactions,
    mempool_pending_count: snapshotAfter.mempool.pending_count,
    wallet_pending_transactions: snapshotAfter.walletStatus.pending_transactions,
    transaction_status: confirmedStatus.status,
    transaction_block_height: confirmedStatus.block_height,
    transaction_index: confirmedStatus.transaction_index,
    sender_activity_source: findActivityRow(
      walletRowsAfter.sender,
      txHash,
      "confirmed",
      postBlock.wallet_history.behavior_transaction_direction,
    ).source,
    recipient_activity_source: findActivityRow(
      walletRowsAfter.recipient,
      txHash,
      "confirmed",
      postBlock.wallet_history.recipient_transaction_direction,
    ).source,
    admin_mempool_pending: rowValue(adminRowsAfter.mempool, "Pending"),
  },
  balances: Object.fromEntries(
    Object.entries(balances).map(([address, balance]) => [
      address,
      {
        balance_base_units: balance.balance_base_units,
        nonce: balance.nonce,
        height: balance.height,
      },
    ]),
  ),
  no_pending_refusal: {
    code: noPendingRefusal.error.code,
    state_unchanged: true,
  },
  source_guards: {
    shared_api_client: true,
    direct_wallet_fetch: false,
    direct_admin_fetch: false,
    browser_persistence: false,
    sensitive_signing_fields: false,
  },
  artifacts: {
    wallet_submit_refusal: artifactDir
      ? join(artifactDir, "phase1-3-wallet-submit-refusal.json")
      : null,
    wallet_send: artifactDir ? join(artifactDir, "phase1-3-wallet-send.json") : null,
    snapshot_before: artifactDir ? join(artifactDir, "phase1-3-snapshot-before.json") : null,
    pending_status: artifactDir ? join(artifactDir, "phase1-3-pending-status.json") : null,
    wallet_rows_before: artifactDir ? join(artifactDir, "phase1-3-wallet-rows-before.json") : null,
    admin_rows_before: artifactDir ? join(artifactDir, "phase1-3-admin-rows-before.json") : null,
    produced_block: artifactDir ? join(artifactDir, "phase1-3-produced-block.json") : null,
    confirmed_status: artifactDir ? join(artifactDir, "phase1-3-confirmed-status.json") : null,
    snapshot_after: artifactDir ? join(artifactDir, "phase1-3-snapshot-after.json") : null,
    wallet_rows_after: artifactDir ? join(artifactDir, "phase1-3-wallet-rows-after.json") : null,
    admin_rows_after: artifactDir ? join(artifactDir, "phase1-3-admin-rows-after.json") : null,
    balances: artifactDir ? join(artifactDir, "phase1-3-balances.json") : null,
    histories: artifactDir ? join(artifactDir, "phase1-3-histories.json") : null,
    no_pending_refusal: artifactDir
      ? join(artifactDir, "phase1-3-no-pending-refusal.json")
      : null,
    snapshot_after_no_pending_refusal: artifactDir
      ? join(artifactDir, "phase1-3-snapshot-after-no-pending-refusal.json")
      : null,
  },
};

if (artifactDir) {
  await mkdir(artifactDir, { recursive: true });
  await writeJson(join(artifactDir, "phase1-3-wallet-submit-refusal.json"), walletSubmitRefusal);
  await writeJson(join(artifactDir, "phase1-3-wallet-send.json"), walletSend);
  await writeJson(join(artifactDir, "phase1-3-snapshot-before.json"), snapshotBefore);
  await writeJson(join(artifactDir, "phase1-3-pending-status.json"), pendingStatus);
  await writeJson(join(artifactDir, "phase1-3-wallet-rows-before.json"), walletRowsBefore);
  await writeJson(join(artifactDir, "phase1-3-admin-rows-before.json"), adminRowsBefore);
  await writeJson(join(artifactDir, "phase1-3-produced-block.json"), producedBlock);
  await writeJson(join(artifactDir, "phase1-3-confirmed-status.json"), confirmedStatus);
  await writeJson(join(artifactDir, "phase1-3-snapshot-after.json"), snapshotAfter);
  await writeJson(join(artifactDir, "phase1-3-wallet-rows-after.json"), walletRowsAfter);
  await writeJson(join(artifactDir, "phase1-3-admin-rows-after.json"), adminRowsAfter);
  await writeJson(join(artifactDir, "phase1-3-balances.json"), balances);
  await writeJson(join(artifactDir, "phase1-3-histories.json"), histories);
  await writeJson(join(artifactDir, "phase1-3-no-pending-refusal.json"), noPendingRefusal);
  await writeJson(
    join(artifactDir, "phase1-3-snapshot-after-no-pending-refusal.json"),
    snapshotAfterNoPendingRefusal,
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

function fixtureStep(value, stepName) {
  const step = value.behavior_flow.find((candidate) => candidate.step === stepName);
  if (!step) {
    throw new Error(`fixture missing behavior step: ${stepName}`);
  }
  return step;
}

function validateFixtureShape(value) {
  if (!value || typeof value !== "object") {
    throw new Error("fixture must be an object");
  }
  if (value.environment !== "private-devnet" || value.network !== "xriq-devnet") {
    throw new Error("fixture must target the private-devnet xriq-devnet scope");
  }
  if (!Array.isArray(value.behavior_flow) || value.behavior_flow.length < 2) {
    throw new Error("fixture behavior_flow must include wallet send and block production");
  }
  if (!value.identities || !value.post_block_expectations) {
    throw new Error("fixture must include identities and post_block_expectations");
  }
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

function validateContractErrors(errors, context) {
  if (errors.length > 0) {
    throw new Error(`${context}: ${errors.join("; ")}`);
  }
}

function validateWalletSubmitRefusal(data) {
  const errors = [];
  if (data.code !== "wallet_submit_disabled") {
    errors.push("wallet submit refusal code must be wallet_submit_disabled");
  }
  if (data.mutation !== "none") {
    errors.push("wallet submit refusal mutation must be none");
  }
  if (data.required_enablement?.explicit_flag !== "--enable-local-wallet-submit") {
    errors.push("wallet submit refusal must point at the submit enablement flag");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateWalletSend(data, step, txHash) {
  const expected = step.expected;
  const request = step.request;
  const errors = [];
  if (data.code !== expected.code) {
    errors.push(`wallet send code must be ${expected.code}`);
  }
  if (data.status !== expected.status) {
    errors.push(`wallet send status must be ${expected.status}`);
  }
  if (data.mutation !== expected.mutation) {
    errors.push(`wallet send mutation must be ${expected.mutation}`);
  }
  if (data.pending_state.before_count !== expected.pending_before_count) {
    errors.push("wallet send pending before_count mismatch");
  }
  if (data.pending_state.after_count !== expected.pending_after_count) {
    errors.push("wallet send pending after_count mismatch");
  }
  if (data.chain_state.chain_unchanged !== expected.chain_unchanged) {
    errors.push("wallet send must leave chain unchanged");
  }
  if (data.transaction.tx_hash !== txHash || data.pending_state.added_tx_hash !== txHash) {
    errors.push("wallet send tx hash must match pending added hash");
  }
  if (data.transaction.from_address !== request.from_address) {
    errors.push("wallet send sender mismatch");
  }
  if (data.transaction.to_address !== request.to_address) {
    errors.push("wallet send recipient mismatch");
  }
  if (data.transaction.amount_base_units !== request.amount_base_units) {
    errors.push("wallet send amount mismatch");
  }
  if (data.transaction.fee_base_units !== request.fee_base_units) {
    errors.push("wallet send fee mismatch");
  }
  if (data.transaction.nonce !== request.nonce) {
    errors.push("wallet send nonce mismatch");
  }
  if (data.audit_event.action !== expected.audit_action) {
    errors.push("wallet send audit action mismatch");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validatePendingRefresh(snapshot, status, walletRows, adminRows, step, txHash) {
  const expected = step.expected;
  const request = step.request;
  const errors = [];
  if (snapshot.network.current_height !== 1) {
    errors.push("pending snapshot height must remain 1");
  }
  if (snapshot.mempool.pending_count !== expected.pending_after_count) {
    errors.push("pending snapshot mempool count mismatch");
  }
  if (snapshot.walletStatus.pending_transactions !== expected.pending_after_count) {
    errors.push("pending wallet status count mismatch");
  }
  if (status.tx_hash !== txHash || status.status !== expected.wallet_transaction_status) {
    errors.push("wallet transaction status must be pending before block production");
  }
  if (status.block_height !== null || status.transaction_index !== null) {
    errors.push("pending wallet transaction must not have block position");
  }
  const entry = snapshot.mempool.entries.find((candidate) => candidate.tx_hash === txHash);
  if (!entry) {
    errors.push("pending snapshot missing accepted tx hash");
  } else {
    if (entry.from_address !== request.from_address || entry.to_address !== request.to_address) {
      errors.push("pending mempool sender/recipient mismatch");
    }
    if (entry.amount_base_units !== request.amount_base_units) {
      errors.push("pending mempool amount mismatch");
    }
  }
  validateActivityRow(findActivityRow(walletRows.sender, txHash, "pending", "sent"), {
    context: "sender pending activity",
    step,
    counterparty: request.to_address,
  });
  validateActivityRow(findActivityRow(walletRows.recipient, txHash, "pending", "received"), {
    context: "recipient pending activity",
    step,
    counterparty: request.from_address,
  });
  if (rowValue(adminRows.network, "Height") !== 1) {
    errors.push("admin rows before block must show height 1");
  }
  if (rowValue(adminRows.mempool, "First Pending") !== txHash) {
    errors.push("admin rows before block must show first pending tx");
  }
  if (rowValue(adminRows.mempool, "Wallet Tx Status") !== "pending") {
    errors.push("admin rows before block must show pending wallet tx status");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateProducedBlock(data, step, txHash) {
  const expected = step.expected;
  const errors = [];
  if (data.code !== expected.code) {
    errors.push(`block production code must be ${expected.code}`);
  }
  if (data.status !== expected.status) {
    errors.push(`block production status must be ${expected.status}`);
  }
  if (data.mutation !== expected.mutation) {
    errors.push(`block production mutation must be ${expected.mutation}`);
  }
  if (data.chain_state.previous_height !== expected.previous_height) {
    errors.push("block production previous height mismatch");
  }
  if (data.chain_state.current_height !== expected.current_height) {
    errors.push("block production current height mismatch");
  }
  if (data.pending_state.before_count !== expected.pending_before_count) {
    errors.push("block production pending before_count mismatch");
  }
  if (data.pending_state.after_count !== expected.pending_after_count) {
    errors.push("block production pending after_count mismatch");
  }
  if (data.confirmed_transactions.length !== expected.confirmed_transaction_count) {
    errors.push("block production confirmed transaction count mismatch");
  }
  if (data.confirmed_transactions[0]?.tx_hash !== txHash) {
    errors.push("block production confirmed tx hash mismatch");
  }
  if (data.audit_event.action !== expected.audit_action) {
    errors.push("block production audit action mismatch");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateConfirmedRefresh(snapshot, status, walletRows, adminRows, step, txHash) {
  const expected = step.expected;
  const explorer = postBlock.explorer;
  const errors = [];
  if (snapshot.network.current_height !== explorer.current_height) {
    errors.push("confirmed snapshot network height mismatch");
  }
  if (snapshot.overview.chain.stored_blocks !== explorer.stored_blocks) {
    errors.push("confirmed snapshot stored block count mismatch");
  }
  if (snapshot.overview.totals.transactions !== explorer.confirmed_transactions) {
    errors.push("confirmed snapshot transaction total mismatch");
  }
  if (snapshot.mempool.pending_count !== expected.mempool_pending_count) {
    errors.push("confirmed snapshot mempool must be empty");
  }
  if (snapshot.walletStatus.pending_transactions !== expected.pending_after_count) {
    errors.push("confirmed wallet pending count must be zero");
  }
  if (status.tx_hash !== txHash || status.status !== expected.wallet_transaction_status) {
    errors.push("wallet transaction status must be confirmed after block production");
  }
  if (status.block_height !== expected.current_height || status.transaction_index !== 0) {
    errors.push("confirmed wallet transaction block position mismatch");
  }
  validateActivityRow(findActivityRow(walletRows.sender, txHash, "confirmed", "sent"), {
    context: "sender confirmed activity",
    step: walletStep,
    counterparty: walletStep.request.to_address,
  });
  validateActivityRow(findActivityRow(walletRows.recipient, txHash, "confirmed", "received"), {
    context: "recipient confirmed activity",
    step: walletStep,
    counterparty: walletStep.request.from_address,
  });
  if (rowValue(adminRows.network, "Height") !== expected.current_height) {
    errors.push("admin rows after block must show height 2");
  }
  if (rowValue(adminRows.node, "Pending") !== postBlock.admin.node_pending) {
    errors.push("admin node pending mismatch after block");
  }
  if (rowValue(adminRows.wallet, "Pending") !== postBlock.admin.wallet_pending) {
    errors.push("admin wallet pending mismatch after block");
  }
  if (rowValue(adminRows.mempool, "Pending") !== postBlock.admin.mempool_pending) {
    errors.push("admin mempool pending mismatch after block");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateBalances(actual, expectedAccounts) {
  const errors = [];
  for (const expected of expectedAccounts) {
    const balance = actual[expected.address];
    if (!balance) {
      errors.push(`missing balance for ${expected.address}`);
      continue;
    }
    if (balance.balance_base_units !== expected.balance_base_units) {
      errors.push(`balance mismatch for ${expected.address}`);
    }
    if (balance.nonce !== expected.nonce) {
      errors.push(`nonce mismatch for ${expected.address}`);
    }
    if (balance.height !== postBlock.explorer.current_height) {
      errors.push(`height mismatch for ${expected.address}`);
    }
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateHistories(actual, fixtureValue, txHash) {
  const expected = fixtureValue.post_block_expectations.wallet_history;
  const errors = [];
  if (actual.sender.transactions.length < expected.sender_min_confirmed_rows) {
    errors.push("sender wallet history has too few confirmed rows");
  }
  if (!historyHas(actual.sender, txHash, expected.behavior_transaction_direction)) {
    errors.push("sender wallet history missing behavior transaction");
  }
  if (!historyHas(actual.recipient, txHash, expected.recipient_transaction_direction)) {
    errors.push("recipient wallet history missing behavior transaction");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateNoPendingRefusal(refusal, before, after) {
  const errors = [];
  if (refusal.error.code !== "no_pending_transactions") {
    errors.push("no-pending refusal code mismatch");
  }
  if (!refusal.error.message.includes("at least one pending transaction")) {
    errors.push("no-pending refusal message must explain pending transaction requirement");
  }
  if (after.network.current_height !== before.network.current_height) {
    errors.push("no-pending refusal must not change height");
  }
  if (after.network.latest_block_hash !== before.network.latest_block_hash) {
    errors.push("no-pending refusal must not change tip hash");
  }
  if (after.network.state_root !== before.network.state_root) {
    errors.push("no-pending refusal must not change state root");
  }
  if (after.mempool.pending_count !== before.mempool.pending_count) {
    errors.push("no-pending refusal must not change mempool count");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function validateAdminRowsAfterNoPending(rows) {
  const errors = [];
  if (rowValue(rows.network, "Height") !== postBlock.explorer.current_height) {
    errors.push("no-pending admin rows height mismatch");
  }
  if (rowValue(rows.mempool, "Pending") !== 0) {
    errors.push("no-pending admin rows must keep pending count at zero");
  }
  if (rowValue(rows.mempool, "First Pending") !== "-") {
    errors.push("no-pending admin rows must not show a first pending transaction");
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function rowValue(rows, label) {
  const row = rows.find(([candidate]) => candidate === label);
  if (!row) {
    throw new Error(`missing row: ${label}`);
  }
  return row[1];
}

function findActivityRow(rows, txHash, source, direction) {
  const row = rows.find(
    (candidate) =>
      candidate.txHash === txHash &&
      candidate.source === source &&
      candidate.direction === direction,
  );
  if (!row) {
    throw new Error(`missing ${source}/${direction} wallet activity row for ${txHash}`);
  }
  return row;
}

function validateActivityRow(row, { context, step, counterparty }) {
  const request = step.request;
  const errors = [];
  if (row.amount !== request.amount_base_units) {
    errors.push(`${context}: amount mismatch`);
  }
  if (row.fee !== request.fee_base_units) {
    errors.push(`${context}: fee mismatch`);
  }
  if (row.nonce !== request.nonce) {
    errors.push(`${context}: nonce mismatch`);
  }
  if (row.counterparty !== counterparty) {
    errors.push(`${context}: counterparty mismatch`);
  }
  if (row.source === "pending") {
    if (row.block !== "pending" || row.transactionIndex !== "pending") {
      errors.push(`${context}: pending row position mismatch`);
    }
  }
  if (row.source === "confirmed") {
    if (row.block !== String(blockStep.expected.current_height) || row.transactionIndex !== "0") {
      errors.push(`${context}: confirmed row position mismatch`);
    }
  }
  if (errors.length > 0) {
    throw new Error(errors.join("; "));
  }
}

function historyHas(history, txHash, direction) {
  return history.transactions.some(
    (transaction) => transaction.tx_hash === txHash && transaction.direction === direction,
  );
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
      if (/(private[_-]?key|seed[_-]?phrase|mnemonic|signed[_-]?transaction)/i.test(key)) {
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
