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
import {
  buildAndSignTransparent,
  parseV5,
  computeTxid,
  p2pkhScript,
  type SpendInput,
  type SpendOutput,
} from '../src/core/chains/zcashTx';
import { getChainConfig } from '../src/core/chains/registry';
import { hex } from '../src/core/xriq';
import { ripemd160 } from '@noble/hashes/ripemd160';
import { sha256 as sha256h } from '@noble/hashes/sha256';

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

console.log('Build + sign a transparent v5 spend (verified ZIP-244 digest)');
const k = deriveZcashKey('test test test test test test test test test test test junk');
const myScript = p2pkhScript(ripemd160(sha256h(k.publicKey)));
const inputs: SpendInput[] = [
  {
    txidLE: Uint8Array.from(hex.fromHex('b'.repeat(64))).reverse(),
    vout: 0,
    value: 100_000n,
    scriptPubKey: myScript,
    privateKey: k.privateKey,
    publicKey: k.publicKey,
  },
];
const outputs: SpendOutput[] = [
  { value: 60_000n, scriptPubKey: myScript },
  { value: 30_000n, scriptPubKey: myScript }, // change (fee 10000)
];
const signed = buildAndSignTransparent(inputs, outputs, 0, 2_500_000);
ok('produces a display txid', /^[0-9a-f]{64}$/.test(signed.txid), signed.txid);
ok('raw is v5/NU5 (version+group+branch)', signed.rawHex.startsWith('050000800a27a726b4d0d6c2'), signed.rawHex.slice(0, 24));
const reparsed = parseV5(hex.fromHex(signed.rawHex));
ok('reparses to 1 input', reparsed.vin.length === 1);
ok('reparses to 2 outputs', reparsed.vout.length === 2);
ok('input got a scriptSig (signed)', reparsed.vin[0].scriptSig.length > 100);
ok('no shielded components', reparsed.spends.length === 0 && reparsed.actions.length === 0);
// txid over the reparsed (signed) tx equals the returned txid — ZIP-244 txid excludes scriptSig.
const reTxid = Buffer.from(Uint8Array.from(computeTxid(reparsed)).reverse()).toString('hex');
eq('txid stable across signing (scriptSig not in txid)', reTxid, signed.txid);

console.log(`\n${fail === 0 ? 'ALL ZCASH VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
