import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const root = fileURLToPath(new URL("..", import.meta.url));
const adminSource = readFileSync(join(root, "src/admin.tsx"), "utf8");
const apiSource = readFileSync(join(root, "src/api.ts"), "utf8");
const packageSource = readFileSync(join(root, "package.json"), "utf8");

for (const requiredText of [
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
  "LocalBlockProductionAcceptedResponse",
]) {
  if (!adminSource.includes(requiredText)) {
    throw new Error(`missing block-production UI marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "export async function produceLocalBlock",
  "LocalBlockProductionRequest",
  "LocalBlockProductionAcceptedResponse",
  "validateLocalBlockProductionAcceptedContract(data",
  "acceptedStatuses: [201]",
  "BLOCK_PRODUCTION_REFUSAL_PATH",
  "local_request_id",
  "max_transactions",
  "timestamp_ms",
]) {
  if (!apiSource.includes(requiredText)) {
    throw new Error(`missing block-production API marker: ${requiredText}`);
  }
}

for (const requiredText of [
  "check-block-production-ui-control.mjs",
  "check-wallet-send-ui-control.mjs",
]) {
  if (!packageSource.includes(requiredText)) {
    throw new Error(`missing package check marker: ${requiredText}`);
  }
}

for (const forbiddenText of [
  "fetch(",
  "/api/v1/blocks/produce",
  "private_key",
  "seed_phrase",
  "mnemonic",
  "signed_transaction",
  "localStorage",
  "sessionStorage",
  "indexedDB",
  "document.cookie",
]) {
  if (adminSource.toLowerCase().includes(forbiddenText.toLowerCase())) {
    throw new Error(`forbidden block-production UI behavior found: ${forbiddenText}`);
  }
}

if (
  !adminSource.includes(
    'const produceDisabled = !enabled || pendingCount <= 0 || state.status === "loading";',
  )
) {
  throw new Error("block production button must be feature-switch and pending-count gated");
}

const summary = {
  ok: "xriq-block-production-ui-control",
  feature_switch: "VITE_XRIQ_ENABLE_LOCAL_BLOCK_PRODUCTION_UI",
  default_enabled: false,
  wallet_submit_deferred: true,
  wallet_send_separate: true,
  shared_api_client: "produceLocalBlock",
  validator: "validateLocalBlockProductionAcceptedContract",
};

console.log(JSON.stringify(summary, null, 2));
