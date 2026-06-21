import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

// Phase 2 wallet UI key-safety guard.
//
// Non-negotiable guardrail (see docs/XRIQ_LEGAL_RISK_REDUCTION.md and
// .github/copilot-instructions.md): the browser wallet/explorer UI must never
// generate, store, manage, or transmit private keys, seed phrases, mnemonics,
// raw signatures, or any custody material. All signing stays server-side /
// CLI-only in the private devnet. This check fails the build if any forbidden
// pattern appears in the UI source.

const root = fileURLToPath(new URL("..", import.meta.url));
const srcDir = join(root, "src");

const forbiddenPatterns = [
  { name: "private key", pattern: /private[_\s-]?key/i },
  { name: "secret key", pattern: /secret[_\s-]?key/i },
  { name: "seed phrase", pattern: /seed[_\s-]?phrase/i },
  { name: "mnemonic", pattern: /mnemonic/i },
  { name: "key pair", pattern: /\bkey\s?pair\b/i },
  { name: "keystore", pattern: /\bkeystore\b/i },
  { name: "web crypto subtle", pattern: /crypto\.subtle/i },
  { name: "generateKey", pattern: /generateKey/i },
  { name: "localStorage", pattern: /\blocalStorage\b/ },
  { name: "sessionStorage", pattern: /\bsessionStorage\b/ },
  { name: "indexedDB", pattern: /indexedDB/i },
  { name: "document.cookie", pattern: /document\.cookie/i },
  { name: "raw signature", pattern: /raw[_\s-]?signature/i },
  { name: "sign transaction", pattern: /sign[_]?transaction/i },
];

function collectSourceFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...collectSourceFiles(full));
    } else if (/\.(ts|tsx)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

const files = collectSourceFiles(srcDir);
if (files.length === 0) {
  throw new Error("wallet key-safety check found no UI source files");
}

const violations = [];
for (const file of files) {
  const lines = readFileSync(file, "utf8").split(/\r?\n/);
  lines.forEach((line, index) => {
    for (const { name, pattern } of forbiddenPatterns) {
      if (pattern.test(line)) {
        violations.push(`${file}:${index + 1}: forbidden "${name}": ${line.trim()}`);
      }
    }
  });
}

if (violations.length > 0) {
  throw new Error(
    "wallet UI key-safety violations (browser must not handle key material):\n" +
      violations.join("\n"),
  );
}

// Affirmative safety markers: the wallet UI must keep declaring its
// preview/local-only, no-signing posture so the guarantee stays explicit.
const walletSource = readFileSync(join(srcDir, "wallet.tsx"), "utf8");
for (const marker of [
  "private-devnet-preview-only-no-signing-no-submit",
  "No signing material",
  "No signing or submission",
]) {
  if (!walletSource.includes(marker)) {
    throw new Error(`wallet UI is missing required safety marker: ${marker}`);
  }
}

console.log(
  JSON.stringify(
    {
      ok: "xriq-wallet-ui-key-safety",
      files_scanned: files.length,
      forbidden_patterns: forbiddenPatterns.length,
      guarantee:
        "no browser-held private keys, seed phrases, mnemonics, raw signatures, or custody material",
    },
    null,
    2,
  ),
);
