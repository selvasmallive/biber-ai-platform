// Conformance harness — proves the wallet's crypto core matches the XRIQ chain.
// Run: npx tsx __tests__/conformance.ts
import { ed25519 } from '@noble/curves/ed25519';
import {
  ed25519Address,
  keypairFromMnemonic,
  keypairFromSeed,
  seedFromMnemonic,
  signTransfer,
  transactionSigningHash,
  transactionSigningBytes,
  buildSignedSubmitEnvelope,
  isValidAddress,
  hex,
  type XriqTransaction,
} from '../src/core/xriq';
import { pqKeypairFromMnemonic, hybridSign, hybridVerify } from '../src/core/pq';

let pass = 0;
let fail = 0;
function check(name: string, cond: boolean, detail = '') {
  if (cond) {
    pass++;
    console.log(`  ok   ${name}`);
  } else {
    fail++;
    console.error(`  FAIL ${name} ${detail}`);
  }
}

console.log('XRIQ address derivation (golden vs Rust xriq-crypto)');
// Rust: ed25519_address([0u8;32]) == ED25519_ADDRESS_GOLDEN
const GOLDEN_ZERO = 'xriqdev1397e043c1939ff954726c0f3657a7a5093b33b89';
check('zero-key address matches Rust golden', ed25519Address(new Uint8Array(32)) === GOLDEN_ZERO, ed25519Address(new Uint8Array(32)));
check('derived address passes validator', isValidAddress(GOLDEN_ZERO));
check('address is xriqdev1 + 40 hex', /^xriqdev1[0-9a-f]{40}$/.test(GOLDEN_ZERO));

console.log('HD derivation + keypair determinism');
const MNEMONIC = 'test test test test test test test test test test test junk'; // well-known test vector
const kp1 = keypairFromMnemonic(MNEMONIC);
const kp2 = keypairFromMnemonic(MNEMONIC);
check('same mnemonic -> same address', kp1.address === kp2.address, kp1.address);
check('address well-formed', isValidAddress(kp1.address), kp1.address);
check('public key is 32 bytes', kp1.publicKey.length === 32);
const seed = seedFromMnemonic(MNEMONIC);
check('seed is 32 bytes', seed.length === 32);
check('keypairFromSeed matches keypairFromMnemonic', keypairFromSeed(seed).address === kp1.address);

console.log('Transaction signing round-trip (Ed25519 verify_strict semantics)');
const tx: XriqTransaction = {
  version: 1,
  chainId: 'xriq-devnet',
  from: kp1.address,
  to: GOLDEN_ZERO,
  amountBaseUnits: 25n,
  feeBaseUnits: 2n,
  nonce: 7n,
  memoHash: null,
  expiresAtHeight: null,
  publicKey: kp1.publicKey,
};
const signingHash = transactionSigningHash(tx);
check('signing hash is 32 bytes', signingHash.length === 32);
const signed = signTransfer(tx, kp1.privateSeed);
check('signature is 64 bytes', signed.signature.length === 64);
// The chain verifies with verify_strict(signing_hash_bytes, sig, pubkey).
check(
  'ed25519 verify_strict accepts our signature over the signing hash',
  ed25519.verify(signed.signature, signingHash, kp1.publicKey),
);
// A tampered amount must break verification (teeth check).
const txTampered = { ...tx, amountBaseUnits: 26n };
check(
  'tampering with amount changes the signing hash',
  hex.toHex(transactionSigningHash(txTampered)) !== hex.toHex(signingHash),
);

console.log('Signing preimage regression pin (transfer => zero action bytes)');
// Preimage = encode_bytes("xriq:v1:transaction:signing") || body.
// Pin the exact length so any accidental encoding drift is caught.
const preimage = transactionSigningBytes(tx);
// 4 (u32 len) + 27 (domain) = 31 preamble.
// body: 2(ver) + [4+11 chain_id "xriq-devnet"] + [4+48 from] + [4+48 to]
//   + 16(amount) + 16(fee) + 8(nonce) + 1(memo none) + 1(expires none) + [4+32 pubkey]
const expectedLen =
  4 + 27 + // preamble
  2 +
  (4 + 'xriq-devnet'.length) +
  (4 + kp1.address.length) +
  (4 + GOLDEN_ZERO.length) +
  16 + 16 + 8 + 1 + 1 +
  (4 + 32);
check('signing preimage byte length is exactly as specified', preimage.length === expectedLen, `${preimage.length} != ${expectedLen}`);

console.log('Signed-submit envelope shape (POST /wallet/transfers/submit-signed)');
const env = buildSignedSubmitEnvelope(tx, signed);
check('format_version correct', env.format_version === 'xriq-local-signed-transfer-envelope-v1');
check('amount encoded as decimal string base-units', env.transaction.amount_base_units === '25');
check('algorithm is ed25519', env.signature_envelope.algorithm === 'ed25519');
check('public_key hex is 64 chars (32 bytes)', env.signature_envelope.public_key.length === 64);
check('signature hex is 128 chars (64 bytes)', env.signature_envelope.signature.length === 128);
check('signing hash hex present', env.hashes.transaction_signing_hash.length === 64);

console.log('Post-quantum hybrid signing (ML-DSA-65, algorithm id 250)');
const pq = pqKeypairFromMnemonic(MNEMONIC);
const pq2 = pqKeypairFromMnemonic(MNEMONIC);
check('PQ keypair deterministic from mnemonic', hex.toHex(pq.publicKey) === hex.toHex(pq2.publicKey));
const hybrid = hybridSign(signingHash, kp1.privateSeed, pq);
check('hybrid tagged to reserved id 250', hybrid.algorithmId === 250);
check('hybrid scheme is ml-dsa-65', hybrid.pq.scheme === 'ml-dsa-65');
check('hybrid signature verifies (both legs)', hybridVerify(signingHash, hybrid));
// Teeth check: a wrong hash must fail PQ verification.
const wrongHash = new Uint8Array(32).fill(9);
check('hybrid verify rejects wrong hash', hybridVerify(wrongHash, hybrid) === false);

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
