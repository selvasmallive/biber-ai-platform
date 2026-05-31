import { readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const requiredFiles = [
  "index.html",
  "package.json",
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
  "/api/v1/admin/node/status",
  "/api/v1/admin/indexer/status",
  "/api/v1/admin/postgres/read-model-status",
  "/api/v1/admin/audit-events?limit=5",
  "/api/v1/snapshots",
  "/api/v1/iso20022/payment-initiation/preview",
  "/api/v1/iso20022/transactions/",
  "/api/v1/iso20022/accounts/",
]) {
  if (!apiSource.includes(route)) {
    throw new Error(`missing API route in client: ${route}`);
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
  "AuditEventsPanel",
  "PendingTransactionsPanel",
  "SnapshotCatalogPanel",
  "IsoPreviewPanel",
  "AdminStatusPanel",
]) {
  if (!appSource.includes(requiredText)) {
    throw new Error(`missing UI marker: ${requiredText}`);
  }
}

const walletSource = readFileSync(join(root, "src/wallet.tsx"), "utf8");
const adminSource = readFileSync(join(root, "src/admin.tsx"), "utf8");
const auditSource = readFileSync(join(root, "src/audit.tsx"), "utf8");
const isoSource = readFileSync(join(root, "src/iso.tsx"), "utf8");
const mempoolSource = readFileSync(join(root, "src/mempool.tsx"), "utf8");
const snapshotsSource = readFileSync(join(root, "src/snapshots.tsx"), "utf8");
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
]) {
  if (!adminSource.includes(requiredText)) {
    throw new Error(`missing admin status marker: ${requiredText}`);
  }
}

console.log("xriq-explorer-ui static check passed");
