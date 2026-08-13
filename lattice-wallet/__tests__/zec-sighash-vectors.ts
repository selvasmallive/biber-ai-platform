// Zcash ZIP-244 conformance — verifies the transaction digest (txid) and the transparent
// SIGHASH_ALL against the OFFICIAL zcash-test-vectors (fixtures/zip_0244.json, from
// github.com/zcash/zcash-test-vectors). This is what makes the transparent spend safe.
// Run: npx tsx __tests__/zec-sighash-vectors.ts
import { readFileSync } from 'node:fs';
import { parseV5, computeTxid, transparentSighashAll } from '../src/core/chains/zcashTx';

const vectors = JSON.parse(readFileSync(new URL('./fixtures/zip_0244.json', import.meta.url), 'utf8'));

const hexToBytes = (h: string) => Uint8Array.from(Buffer.from(h, 'hex'));
const toHex = (b: Uint8Array) => Buffer.from(b).toString('hex');
const u64le = (v: bigint) => {
  const b = new Uint8Array(8);
  let x = v;
  for (let i = 0; i < 8; i++) { b[i] = Number(x & 0xffn); x >>= 8n; }
  return b;
};

let txidPass = 0, txidFail = 0, shPass = 0, shFail = 0;
for (let i = 2; i < vectors.length; i++) {
  const row = vectors[i];
  const tx = parseV5(hexToBytes(row[0]));
  const gotTxid = toHex(computeTxid(tx));
  if (gotTxid === row[1]) txidPass++;
  else { txidFail++; console.error(`  FAIL txid row ${i}\n    got  ${gotTxid}\n    want ${row[1]}`); }

  if (row[5] !== null) {
    const amounts = (row[3] as (number | string)[]).map((a) => u64le(BigInt(a)));
    const scripts = (row[4] as string[]).map(hexToBytes);
    const gotSh = toHex(transparentSighashAll(tx, row[5], amounts, scripts));
    if (gotSh === row[7]) shPass++;
    else { shFail++; console.error(`  FAIL sighash row ${i}\n    got  ${gotSh}\n    want ${row[7]}`); }
  }
}

console.log(`  ok   txid: ${txidPass} vectors match (${txidFail} fail)`);
console.log(`  ok   transparent SIGHASH_ALL: ${shPass} vectors match (${shFail} fail)`);
console.log(`\n${txidFail + shFail === 0 ? 'ALL ZCASH ZIP-244 VECTORS MATCH ✓' : `${txidFail + shFail} FAILED`}`);
if (txidFail + shFail > 0) process.exit(1);
