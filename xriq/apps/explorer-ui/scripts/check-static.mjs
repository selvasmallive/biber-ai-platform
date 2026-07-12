import { readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const requiredFiles = [
  "index.html",
  "package.json",
  "scripts/check-block-production-admin-refresh-live.mjs",
  "scripts/check-block-production-no-pending-live.mjs",
  "scripts/check-block-production-ui-control.mjs",
  "scripts/check-block-production-ui-live.mjs",
  "scripts/check-postgres-ui-state.mjs",
  "scripts/check-wallet-key-safety.mjs",
  "scripts/check-wallet-send-accepted-contract.mjs",
  "scripts/check-wallet-submit-accepted-contract.mjs",
  "tsconfig.json",
  "vite.config.ts",
  "public/xriq-topology.svg",
  "src/App.tsx",
  "src/admin.tsx",
  "src/api.ts",
  "src/audit.tsx",
  "src/iso.tsx",
  "src/main.tsx",
  "src/mempool.tsx",
  "src/snapshots.tsx",
  "src/styles.css",
  "src/wallet.tsx",
  "src/faucet.tsx",
  "src/vite-env.d.ts",
];

for (const file of requiredFiles) {
  statSync(join(root, file));
}

const packageJson = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
for (const dependency of ["react", "react-dom", "typescript", "vite"]) {
  if (!packageJson.dependencies?.[dependency] && !packageJson.devDependencies?.[dependency]) {
    throw new Error(`missing dependency: ${dependency}`);
  }
}

const apiSource = readFileSync(join(root, "src/api.ts"), "utf8");
for (const route of [
  "/api/v1/health",
  "/api/v1/network",
  "/api/v1/explorer/overview",
  "/api/v1/blocks?limit=5",
  "/api/v1/blocks/",
  "/api/v1/transactions?limit=5",
  "/api/v1/transactions/",
  "/api/v1/mempool?limit=5",
  "/api/v1/accounts?limit=5",
  "/api/v1/accounts/",
  "/transactions?limit=5",
  "/api/v1/wallet/status",
  "/api/v1/wallet/accounts/",
  "/api/v1/wallet/transactions/",
  "/api/v1/wallet/transfers/draft-preview",
  "/api/v1/wallet/transfers/submit",
  "/api/v1/wallet/transfers/send",
  "/api/v1/blocks/produce",
  "/api/v1/admin/node/status",
  "/api/v1/admin/indexer/status",
  "/api/v1/admin/postgres/read-model-status",
  "/api/v1/admin/audit-events?limit=5",
  "/api/v1/snapshots",
  "/api/v1/iso20022/payment-initiation/preview",
  "/api/v1/iso20022/transactions/",
  "/api/v1/iso20022/accounts/",
  "/api/v1/faucet?",
]) {
  if (!apiSource.includes(route)) {
    throw new Error(`missing API route in client: ${route}`);
  }
}

for (const requiredText of [
  "TestnetFaucetResponse",
  "requestTestnetFaucet",
  "faucet-dispense",
  "recipient_balance_base_units",
  'acceptedStatuses: [200, 201]',
]) {
  if (!apiSource.includes(requiredText)) {
    throw new Error(`missing testnet faucet API marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "LocalWalletSubmitAcceptedResponse",
  "LocalWalletSubmitPendingTransaction",
  "LocalWalletSubmitAcceptedExpectations",
  "validateLocalWalletSubmitAcceptedContract",
  "WALLET_SUBMIT_REFUSAL_ENDPOINT",
  "LOCAL_WALLET_SUBMIT_ACCEPTED_CODE",
  "LOCAL_WALLET_SUBMIT_ACCEPTED_MUTATION",
  "wallet_submit_accepted_local_only",
  "pending_state_only",
  "wallet_transfer_submit_attempt",
  "added_tx_hash",
  "chain_unchanged",
]) {
  if (!apiSource.includes(requiredText)) {
    throw new Error(`missing accepted wallet-submit API marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "LocalWalletSendAcceptedResponse",
  "LocalWalletSendPendingTransaction",
  "LocalWalletSendAcceptedExpectations",
  "validateLocalWalletSendAcceptedContract",
  "audit resource_id must use the local_request_id marker",
  "WALLET_SEND_REFUSAL_ENDPOINT",
  "LOCAL_WALLET_SEND_ACCEPTED_CODE",
  "LOCAL_WALLET_SEND_ACCEPTED_MUTATION",
  "wallet_send_accepted_local_only",
  "pending_state_only",
  "wallet_transfer_send_attempt",
  "added_tx_hash",
  "chain_unchanged",
]) {
  if (!apiSource.includes(requiredText)) {
    throw new Error(`missing accepted wallet-send API marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "LocalBlockProductionAcceptedResponse",
  "LocalBlockProductionConfirmedTransaction",
  "LocalBlockProductionAcceptedExpectations",
  "validateLocalBlockProductionAcceptedContract",
  "LOCAL_BLOCK_PRODUCTION_ACCEPTED_CODE",
  "LOCAL_BLOCK_PRODUCTION_ACCEPTED_AUDIT_SCOPE",
  "LOCAL_BLOCK_PRODUCTION_ACCEPTED_MUTATION",
  "block_production_accepted_local_only",
  "chain_and_pending_state_local_only",
  "api-local-accepted",
  "confirmed_transactions",
  "pending_state",
  "chain_state",
  "metadata_policy",
  "LocalBlockProductionRequest",
  "produceLocalBlock",
  "acceptedStatuses: [201]",
  "LocalBlockProductionNoPendingResponse",
  "validateLocalBlockProductionNoPendingContract",
  "LOCAL_BLOCK_PRODUCTION_NO_PENDING_CODE",
  "produceLocalBlockNoPendingRefusal",
  "no_pending_transactions",
  "acceptedStatuses: [400]",
]) {
  if (!apiSource.includes(requiredText)) {
    throw new Error(`missing accepted block-production API marker: ${requiredText}`);
  }
}

const appSource = readFileSync(join(root, "src/App.tsx"), "utf8");
for (const requiredText of [
  "XRIQ Private Devnet",
  "XRIQ Explorer",
  "private-devnet",
  "xriq-topology.svg",
  "Block Detail",
  "Transaction Detail",
  "Account Detail",
  "WalletShell",
  "TestnetFaucetPanel",
  "AuditEventsPanel",
  "PendingTransactionsPanel",
  "SnapshotCatalogPanel",
  "IsoPreviewPanel",
  "AdminStatusPanel",
  "VITE_XRIQ_ENVIRONMENT",
  "resolveEnvironment",
  "staging-devnet",
  "envPill",
  "unsupported",
]) {
  if (!appSource.includes(requiredText)) {
    throw new Error(`missing UI marker: ${requiredText}`);
  }
}

const faucetSource = readFileSync(join(root, "src/faucet.tsx"), "utf8");
for (const requiredText of [
  "Testnet Faucet",
  "Valueless test units",
  "TEST-ONLY",
  "this page never handles wallet secrets",
  "requestTestnetFaucet",
  "xriq-testnet",
  "Recipient address",
  "Request test units",
]) {
  if (!faucetSource.includes(requiredText)) {
    throw new Error(`missing testnet faucet UI marker: ${requiredText}`);
  }
}
for (const forbiddenText of [
  "private_key",
  "seed_phrase",
  "mainnet",
  "custody",
  "liquidity",
  "swap",
]) {
  if (faucetSource.toLowerCase().includes(forbiddenText)) {
    throw new Error(`forbidden faucet UI behavior found: ${forbiddenText}`);
  }
}

const walletSource = readFileSync(join(root, "src/wallet.tsx"), "utf8");
const adminSource = readFileSync(join(root, "src/admin.tsx"), "utf8");
const auditSource = readFileSync(join(root, "src/audit.tsx"), "utf8");
const isoSource = readFileSync(join(root, "src/iso.tsx"), "utf8");
const mempoolSource = readFileSync(join(root, "src/mempool.tsx"), "utf8");
const snapshotsSource = readFileSync(join(root, "src/snapshots.tsx"), "utf8");
const postgresUiSmokeSource = readFileSync(
  join(root, "scripts/check-postgres-ui-state.mjs"),
  "utf8",
);
for (const requiredText of [
  "Wallet Preview",
  "xriq-wallet-transfer-preview-v1",
  "private-devnet-preview-only-no-signing-no-submit",
  'mutation: "none"',
  "loadWalletDraftPreview",
  "Check Preview",
  "Sender and recipient must differ.",
  "Amount must be a positive integer.",
  "Fee must be at least 2 base units.",
  "Nonce must be a non-negative integer.",
  "Expiry must be empty or a non-negative integer.",
  "Debit exceeds available balance.",
  "Wallet Activity",
  "Selected Wallet Activity",
  "read-only confirmed and pending",
  "No wallet activity",
  "Pending Block",
  "walletActivityRows",
  "Wallet API Transaction Status",
  "api-backed status",
  "Loading wallet activity status",
  "API Block Height",
  "loadWalletTransactionStatus",
  "Wallet API History",
  "api-backed confirmed history",
  "No API wallet history",
  "loadWalletHistory",
  "Wallet Action Guards",
  "disabled submit/send",
  "Submit Draft",
  "Send Transfer",
  "Check Guards",
  "WalletMutationRefusalResponse",
  "loadWalletMutationRefusal",
  "wallet_submit_disabled",
  "wallet_send_disabled",
  "--enable-local-wallet-submit",
  "--enable-local-wallet-send",
  "local-private-devnet-preflight-only",
  "validateActionRefusalContract",
]) {
  if (!walletSource.includes(requiredText)) {
    throw new Error(`missing wallet preview marker: ${requiredText}`);
  }
}

for (const forbiddenText of [
  "fetch(",
  "/transfers/submit",
  "/transfers/send",
  "private_key",
  "seed_phrase",
]) {
  if (walletSource.toLowerCase().includes(forbiddenText)) {
    throw new Error(`forbidden wallet preview behavior found: ${forbiddenText}`);
  }
}

for (const forbiddenText of ["mainnet", "liquidity", "custody", "swap"]) {
  if (
    appSource.toLowerCase().includes(forbiddenText) ||
    walletSource.toLowerCase().includes(forbiddenText) ||
    adminSource.toLowerCase().includes(forbiddenText) ||
    auditSource.toLowerCase().includes(forbiddenText) ||
    mempoolSource.toLowerCase().includes(forbiddenText) ||
    snapshotsSource.toLowerCase().includes(forbiddenText) ||
    isoSource.toLowerCase().includes(forbiddenText)
  ) {
    throw new Error(`forbidden public-market term found in UI: ${forbiddenText}`);
  }
}

for (const requiredText of [
  "ISO 20022 Preview",
  "Payment Initiation",
  "Payment Status",
  "Account Statement",
  "not_certified",
  "unsupported_fields",
  "loadIsoPaymentInitiationPreview",
  "loadIsoPaymentStatusPreview",
  "loadIsoAccountStatementPreview",
  "Read only",
]) {
  if (!isoSource.includes(requiredText)) {
    throw new Error(`missing ISO preview marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "Pending Transactions",
  "Selected Pending Status",
  "loadWalletTransactionStatus",
  "No pending transactions",
  "block_height",
  "transaction_index",
  "mempoolPanel",
]) {
  if (!mempoolSource.includes(requiredText)) {
    throw new Error(`missing mempool panel marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "Audit Events",
  "Selected Audit Event",
  "Read only indexed audit log",
  "No audit events",
  "resource_type",
  "resource_id",
  "auditPanel",
]) {
  if (!auditSource.includes(requiredText)) {
    throw new Error(`missing audit panel marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "Snapshot Catalog",
  "Selected Snapshot Detail",
  "Export and import controls disabled",
  "loadSnapshotDetail",
  "snapshot_dir",
  "export_status",
  "import_status",
  "snapshotPanel",
]) {
  if (!snapshotsSource.includes(requiredText)) {
    throw new Error(`missing snapshot panel marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "Admin Status",
  "Node",
  "nodeStatus",
  "wallet_submit_status",
  "block_production_status",
  "Mempool",
  "mempool",
  "First Pending",
  "Wallet Tx Status",
  "Wallet Tx Block",
  "Wallet Tx Index",
  "loadWalletTransactionStatus",
  "Postgres Read Model",
  "loadPostgresReadModelStatus",
  "PostgresReadModelStatusResponse",
  "postgresReadModelRows",
  "PostgresStatusState",
  "account_transactions",
  "HTTP 404",
  "transaction_index",
  "amount_base_units",
  "submit_status",
  "produce_block_status",
  "walletStatus",
  "auditEvents",
  "snapshots",
  "capabilities.submit",
  "capabilities.send",
  "Snapshot Catalog",
  "Audit Events",
  "export_status",
  "import_status",
  "Admin Action Guards",
  "Block Production Guard",
  "Produce Block",
  "Check Guard",
  "LocalMutationRefusalResponse",
  "loadBlockProductionRefusal",
  "BLOCK_PRODUCTION_REFUSAL_ENDPOINT",
  "block_production_disabled",
  "--enable-local-block-production",
  "local-private-devnet-preflight-only",
  "validateBlockProductionRefusalContract",
  "local_refusal_audit_count",
  "local_refusal_audit_events",
  "block_production",
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
  "adminSnapshotRows",
  "AdminSnapshotRows",
  'const produceDisabled = !enabled || pendingCount <= 0 || state.status === "loading";',
]) {
  if (!adminSource.includes(requiredText)) {
    throw new Error(`missing admin status marker: ${requiredText}`);
  }
}

for (const forbiddenText of ["fetch(", "/api/v1/blocks/produce"]) {
  if (adminSource.includes(forbiddenText)) {
    throw new Error(`forbidden admin guard behavior found: ${forbiddenText}`);
  }
}

for (const requiredText of [
  "/api/v1/admin/postgres/read-model-status",
  "postgresReadModelRows",
  "--expected-blocks",
  "--expected-account-history",
  "xriq-admin-postgres-ui-state",
]) {
  if (!postgresUiSmokeSource.includes(requiredText)) {
    throw new Error(`missing postgres UI smoke marker: ${requiredText}`);
  }
}

console.log("xriq-explorer-ui static check passed");
