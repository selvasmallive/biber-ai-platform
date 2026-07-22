import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

// Wallet UI key-safety guard — NON-CUSTODIAL edition.
//
// Guardrail (see docs/XRIQ_LEGAL_RISK_REDUCTION.md and
// docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md Phase 5c): the browser wallet may sign
// transactions locally with a vetted Ed25519 library, but ONLY non-custodially —
// the private key is generated in memory, used once, and never persisted or
// transmitted. This check fails the build if any *custody* anti-pattern appears in
// the UI source: persistence of key material (localStorage/sessionStorage/
// indexedDB/cookies), mnemonic/seed-phrase/keystore material, or raw WebCrypto key
// export. Ephemeral in-memory signing is allowed; custody is not.

const root = fileURLToPath(new URL("..", import.meta.url));
const srcDir = join(root, "src");

const forbiddenPatterns = [
  // Persisting key material in the browser = custody. Forbidden.
  { name: "localStorage", pattern: /\blocalStorage\b/ },
  { name: "sessionStorage", pattern: /\bsessionStorage\b/ },
  { name: "indexedDB", pattern: /indexedDB/i },
  { name: "document.cookie", pattern: /document\.cookie/i },
  // HD / persisted custody material. The ephemeral signer is a fresh random key,
  // never a mnemonic-derived or stored keystore key.
  { name: "seed phrase", pattern: /seed[_\s-]?phrase/i },
  { name: "mnemonic", pattern: /mnemonic/i },
  { name: "keystore", pattern: /\bkeystore\b/i },
  { name: "secret key", pattern: /secret[_\s-]?key/i },
  // Raw WebCrypto key handling is not used (we use a vetted Ed25519 library that
  // keeps the key an ephemeral Uint8Array); forbid it to avoid extractable-key
  // footguns and keep the signing surface small.
  { name: "web crypto subtle", pattern: /crypto\.subtle/i },
  { name: "web crypto exportKey", pattern: /exportKey/i },
];

// Only the isolated signing module may reference the ephemeral private key. The
// rest of the UI handles only public keys and signatures (defense against
// accidental custody).
const KEY_MATERIAL_ALLOWLIST = new Set(["signing.ts"]);
const privateKeyPattern = /private[_\s-]?key/i;

function baseNameOf(file) {
  const slash = Math.max(file.lastIndexOf("/"), file.lastIndexOf("\\"));
  return file.slice(slash + 1);
}

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
  const baseName = baseNameOf(file);
  const lines = readFileSync(file, "utf8").split(/\r?\n/);
  lines.forEach((line, index) => {
    for (const { name, pattern } of forbiddenPatterns) {
      if (pattern.test(line)) {
        violations.push(`${file}:${index + 1}: forbidden "${name}": ${line.trim()}`);
      }
    }
    if (!KEY_MATERIAL_ALLOWLIST.has(baseName) && privateKeyPattern.test(line)) {
      violations.push(
        `${file}:${index + 1}: private key material outside the isolated signing module: ${line.trim()}`,
      );
    }
  });
}

if (violations.length > 0) {
  throw new Error(
    "wallet UI key-safety violations (browser signing must stay non-custodial):\n" +
      violations.join("\n"),
  );
}

// Affirmative safety markers: the wallet UI must keep declaring its non-custodial,
// ephemeral-key posture so the guarantee stays explicit.
const walletSource = readFileSync(join(srcDir, "wallet.tsx"), "utf8");
for (const marker of ["non-custodial", "ephemeral", "never persisted or transmitted"]) {
  if (!walletSource.includes(marker)) {
    throw new Error(`wallet UI is missing required non-custodial safety marker: ${marker}`);
  }
}

console.log(
  JSON.stringify(
    {
      ok: "xriq-wallet-ui-key-safety",
      mode: "non-custodial",
      files_scanned: files.length,
      forbidden_patterns: forbiddenPatterns.length,
      guarantee:
        "ephemeral in-memory Ed25519 key, isolated to the signing module, never persisted or transmitted; only public key + signature leave the wallet",
    },
    null,
    2,
  ),
);
