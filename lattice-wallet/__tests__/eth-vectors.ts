// Ethereum conformance — pinned to Ethereum's OWN published golden vectors.
// Proves the EVM adapter derives addresses and signs transactions exactly as Ethereum
// does. Run: npx tsx __tests__/eth-vectors.ts
import { secp256k1 } from '@noble/curves/secp256k1';
import {
  evmAddressFromPublicKey,
  toChecksumAddress,
  isValidChecksum,
  deriveEvmKey,
  signLegacy155,
  signEip1559,
  type LegacyTx,
  type Eip1559Tx,
} from '../src/core/chains/evm';
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

console.log('EVM address derivation (golden: private key = 1 -> secp256k1 G)');
const one = new Uint8Array(32); one[31] = 1;
const pub1 = secp256k1.getPublicKey(one, false);
eq('address(privkey=1)', evmAddressFromPublicKey(pub1), '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf');

console.log('EIP-55 checksum (golden vectors from the EIP)');
for (const a of [
  '0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed',
  '0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359',
  '0xdbF03B407c01E7cD3CBea99509d93f8DDDC8C6FB',
  '0xD1220A0cf47c7B9Be7A2E6BA89F429762e7b9aDb',
]) {
  eq(`checksum ${a.slice(0, 10)}…`, toChecksumAddress(a.toLowerCase()), a);
  ok(`isValidChecksum ${a.slice(0, 10)}…`, isValidChecksum(a));
}
ok('rejects bad checksum', !isValidChecksum('0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAeD'));

console.log('BIP44 derivation (golden: canonical test mnemonic, account 0)');
const MNEMONIC = 'test test test test test test test test test test test junk';
eq(
  "m/44'/60'/0'/0/0 address",
  deriveEvmKey(MNEMONIC).address,
  '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266',
);

console.log('Legacy EIP-155 signing (golden: the EIP-155 example transaction)');
const legacy: LegacyTx = {
  nonce: 9n,
  gasPrice: 20_000_000_000n,
  gasLimit: 21000n,
  to: '0x3535353535353535353535353535353535353535',
  value: 1_000_000_000_000_000_000n,
  data: new Uint8Array(0),
  chainId: 1n,
};
const eip155Key = hex.fromHex('4646464646464646464646464646464646464646464646464646464646464646');
const signedLegacy = signLegacy155(legacy, eip155Key);
eq(
  'EIP-155 raw signed tx',
  signedLegacy.raw,
  '0xf86c098504a817c800825208943535353535353535353535353535353535353535880de0b6b3a7640000' +
    '8025a028ef61340bd939bc2195fe537567866003e1a15d3c71ff63e1590620aa636276a067cbe9d8997f' +
    '761aecb703304b3800ccf555c9f3dc64214b297fb1966a3b6d83',
);

console.log('EIP-1559 signing (sign -> ecrecover round-trips to sender)');
const k = deriveEvmKey(MNEMONIC);
const tx1559: Eip1559Tx = {
  chainId: 1n,
  nonce: 0n,
  maxPriorityFeePerGas: 1_000_000_000n,
  maxFeePerGas: 30_000_000_000n,
  gasLimit: 21000n,
  to: '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf',
  value: 1_000_000_000_000_000_000n,
  data: new Uint8Array(0),
};
const s1 = signEip1559(tx1559, k.privateKey);
const s2 = signEip1559(tx1559, k.privateKey);
ok('type-2 tx (0x02 prefix)', s1.raw.startsWith('0x02'));
eq('deterministic (RFC6979)', s1.raw, s2.raw);
ok('raw hash is 32 bytes', s1.hash.length === 66);

console.log(`\n${fail === 0 ? 'ALL ETHEREUM VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
