// Zcash transparent conformance — the address scheme is base58check with the Zcash
// t1 prefix. base58check itself is proven against the Bitcoin genesis address; the Zcash
// addresses are then checked for correct prefix/structure. Spending is gated (verified).
// Run: npx tsx __tests__/zec-vectors.ts
import { base58check } from '@scure/base';
import { sha256 } from '@noble/hashes/sha256';
import { secp256k1 } from '@noble/curves/secp256k1';
import {
  zcashTransparentAddress,
  deriveZcashKey,
  ZcashTransparentAdapter,
} from '../src/core/chains/zcash';
import { getChainConfig } from '../src/core/chains/registry';
import { hex } from '../src/core/xriq';

let fail = 0;
function eq(name: string, got: string, want: string) {
  if (got === want) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name}\n    got  ${got}\n    want ${want}`); }
}
function ok(name: string, cond: boolean, detail = '') {
  if (cond) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name} ${detail}`); }
}

console.log('base58check encoder (golden: Bitcoin genesis address)');
const b58c = base58check(sha256);
eq(
  'base58check(0x00 || genesis hash160)',
  b58c.encode(new Uint8Array([0x00, ...hex.fromHex('62e907b15cbf27d5425399ebf6f0fb50ebb88f18')])),
  '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
);

console.log('Zcash t-address structure');
const one = new Uint8Array(32); one[31] = 1;
const pub = secp256k1.getPublicKey(one, true); // compressed pubkey of privkey=1
const tAddr = zcashTransparentAddress(pub);
ok('starts with t1', tAddr.startsWith('t1'), tAddr);
ok('decodes to 22 bytes (2 prefix + 20 hash160)', b58c.decode(tAddr).length === 22);

const adapter = new ZcashTransparentAdapter(getChainConfig('zcash-t'));
ok('adapter validates its own address', adapter.validateAddress(tAddr));
ok('rejects a bitcoin address', !adapter.validateAddress('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'));

console.log('Derivation from mnemonic');
const derived = deriveZcashKey('test test test test test test test test test test test junk');
ok('derived t-address is valid', adapter.validateAddress(derived.address), derived.address);

console.log('Spend is honestly gated');
let gated = false;
adapter.send('x', { to: tAddr, amountBaseUnits: 1n }).catch((e) => {
  gated = /ZIP-243\/244|not yet enabled/.test((e as Error).message);
}).finally(() => {
  ok('send() refuses until ZIP-243/244 sighash is verified', gated);
  console.log(`\n${fail === 0 ? 'ALL ZCASH VECTORS MATCH ✓' : `${fail} FAILED`}`);
  if (fail > 0) process.exit(1);
});
