// Bitcoin conformance — BIP84 golden addresses from the BIP84 spec, plus a structural
// build/sign/finalize check of the send path (network-independent).
// Run: npx tsx __tests__/btc-vectors.ts
import * as btc from '@scure/btc-signer';
import { HDKey } from '@scure/bip32';
import { mnemonicToSeedSync } from '@scure/bip39';
import { deriveBtcKey, BitcoinAdapter } from '../src/core/chains/bitcoin';
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

const BIP84_MNEMONIC =
  'abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about';

console.log('BIP84 native SegWit addresses (golden vectors from BIP84)');
eq('receive #0', deriveBtcKey(BIP84_MNEMONIC, 0).address, 'bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu');
eq('receive #1', deriveBtcKey(BIP84_MNEMONIC, 1).address, 'bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g');

console.log('Address validation');
const adapter = new BitcoinAdapter(getChainConfig('bitcoin'));
ok('accepts bech32 P2WPKH', adapter.validateAddress('bc1qcr8te4kr609gcawutmrza0j4xv80jy8z306fyu'));
ok('accepts legacy P2PKH', adapter.validateAddress('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'));
ok('rejects junk', !adapter.validateAddress('not-an-address'));
ok('rejects empty', !adapter.validateAddress(''));

console.log('Send path — build, sign, finalize a P2WPKH tx (no network)');
const k = deriveBtcKey(BIP84_MNEMONIC, 0);
const spend = btc.p2wpkh(k.publicKey, btc.NETWORK);
const tx = new btc.Transaction();
tx.addInput({
  txid: hex.fromHex('a'.repeat(64)),
  index: 0,
  witnessUtxo: { script: spend.script, amount: 100_000n },
});
tx.addOutputAddress('bc1qnjg0jd8228aq7egyzacy8cys3knf9xvrerkf9g', 60_000n, btc.NETWORK);
tx.addOutputAddress(k.address, 39_000n, btc.NETWORK); // change (fee 1000)
tx.sign(k.privateKey);
tx.finalize();
ok('produces a txid', /^[0-9a-f]{64}$/.test(tx.id), tx.id);
const decoded = btc.RawTx.decode(hex.fromHex(tx.hex));
ok('decodes to 1 input', decoded.inputs.length === 1);
ok('decodes to 2 outputs', decoded.outputs.length === 2);
ok('input carries a witness (signed)', !!decoded.witnesses && decoded.witnesses[0].length === 2);

console.log(`\n${fail === 0 ? 'ALL BITCOIN VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
