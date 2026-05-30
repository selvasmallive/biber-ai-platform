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
  "src/api.ts",
  "src/main.tsx",
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
  "/api/v1/accounts?limit=5",
  "/api/v1/accounts/",
  "/transactions?limit=5",
  "/api/v1/admin/indexer/status",
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
]) {
  if (!appSource.includes(requiredText)) {
    throw new Error(`missing UI marker: ${requiredText}`);
  }
}

const walletSource = readFileSync(join(root, "src/wallet.tsx"), "utf8");
for (const requiredText of [
  "Wallet Preview",
  "xriq-wallet-transfer-preview-v1",
  "private-devnet-preview-only-no-signing-no-submit",
  'mutation: "none"',
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
    walletSource.toLowerCase().includes(forbiddenText)
  ) {
    throw new Error(`forbidden public-market term found in UI: ${forbiddenText}`);
  }
}

console.log("xriq-explorer-ui static check passed");
