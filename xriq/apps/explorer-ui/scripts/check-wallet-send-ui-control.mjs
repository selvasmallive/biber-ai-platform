import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const walletSource = readFileSync(join(root, "src/wallet.tsx"), "utf8");
const apiSource = readFileSync(join(root, "src/api.ts"), "utf8");
const packageSource = readFileSync(join(root, "package.json"), "utf8");

for (const requiredText of [
  "LOCAL_WALLET_SEND_UI_ENABLED",
  "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI",
  "Local Wallet Send",
  "Wallet send local-only guard",
  "wallet-send only",
  "wallet submit deferred",
  "pending_state_only",
  "no implicit block production",
  "Send Local",
  "sendLocalWalletTransfer",
  "LocalWalletSendAcceptedResponse",
  "LocalWalletSendRequest",
]) {
  if (!walletSource.includes(requiredText)) {
    throw new Error(`missing wallet-send UI marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "export async function sendLocalWalletTransfer",
  "LocalWalletSendRequest",
  "LocalWalletSendAcceptedResponse",
  "validateLocalWalletSendAcceptedContract(data",
  "acceptedStatuses: [201]",
  "WALLET_SEND_REFUSAL_PATH",
  "local_request_id",
]) {
  if (!apiSource.includes(requiredText)) {
    throw new Error(`missing wallet-send API marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "check-wallet-send-ui-control.mjs",
  "check-wallet-send-accepted-contract.mjs",
]) {
  if (!packageSource.includes(requiredText)) {
    throw new Error(`missing package check marker: ${requiredText}`);
  }
}

for (const forbiddenText of [
  "fetch(",
  "/api/v1/wallet/transfers/send",
  "/transfers/send",
  "/transfers/submit",
  "private_key",
  "seed_phrase",
  "mnemonic",
  "signed_transaction",
  "localStorage",
  "sessionStorage",
  "indexedDB",
  "document.cookie",
]) {
  if (walletSource.toLowerCase().includes(forbiddenText.toLowerCase())) {
    throw new Error(`forbidden wallet-send UI behavior found: ${forbiddenText}`);
  }
}

if (!walletSource.includes('type="button" disabled')) {
  throw new Error("wallet submit guard button must remain disabled");
}

if (
  !walletSource.includes(
    'const sendDisabled = !enabled || errors.length > 0 || state.status === "loading";',
  )
) {
  throw new Error("wallet send button must be disabled unless the feature switch is on");
}

const summary = {
  ok: "xriq-wallet-send-ui-control",
  feature_switch: "VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI",
  default_enabled: false,
  wallet_submit_deferred: true,
  shared_api_client: "sendLocalWalletTransfer",
  validator: "validateLocalWalletSendAcceptedContract",
};

console.log(JSON.stringify(summary, null, 2));
