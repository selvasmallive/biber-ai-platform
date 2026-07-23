// Golden cross-check: the browser's client-side canonical signing-hash encoder
// (src/canonical.ts) must match `xriq-crypto::transaction_signing_hash` byte-for-byte,
// otherwise the wallet's "verify what I sign" check would reject valid transactions
// (or, worse, accept a mismatched server hash). The goldens below were produced by
// the Rust implementation for the fixed transfer fields. Run under Node's type
// stripping so the .ts encoder is exercised directly (no drift from a re-implementation).
import { transactionSigningHashHex } from "../src/canonical.ts";

const fields = {
  version: "1",
  chain_id: "xriq-devnet",
  from_address: "xriqdev1alice00000000000",
  to_address: "xriqdev1carol00000000000",
  amount_base_units: "5",
  fee_base_units: "2",
  nonce: "1",
  expires_at_height: "100",
};

const cases = [
  {
    name: "test-only (empty public key)",
    publicKeyHex: "",
    expected: "dabb964e58a91b7cea297abc60ea5d5c68ce0dd061e2496aec0c85273a63250f",
  },
  {
    name: "ed25519 (32-byte public key)",
    publicKeyHex: "ca93ac1705187071d67b83c7ff0efe8108e8ec4530575d7726879333dbdabe7c",
    expected: "610466b391644367cd5f0b6701e0d5dffba9c8a7ef8f23b423e80cb2172f12ce",
  },
];

const failures = [];
for (const testCase of cases) {
  const actual = transactionSigningHashHex(fields, testCase.publicKeyHex);
  if (actual !== testCase.expected) {
    failures.push(`${testCase.name}: expected ${testCase.expected}, got ${actual}`);
  }
}

if (failures.length > 0) {
  throw new Error(
    "canonical signing-hash mismatch vs the Rust golden (src/canonical.ts drifted from xriq-crypto):\n" +
      failures.join("\n"),
  );
}

console.log(
  JSON.stringify(
    {
      ok: "xriq-canonical-signing-hash",
      cases: cases.length,
      note: "browser encoder matches xriq-crypto::transaction_signing_hash",
    },
    null,
    2,
  ),
);
