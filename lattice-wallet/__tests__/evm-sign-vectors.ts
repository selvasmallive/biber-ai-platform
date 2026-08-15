// EVM signing conformance — verifies EIP-191 (personal_sign) and EIP-712 v4 hashing
// against ethers (reference oracle), and that signatures recover to the signer.
// Run: npx tsx __tests__/evm-sign-vectors.ts
import { ethers } from 'ethers';
import { hashPersonalMessage, hashTypedDataV4, personalSign, signTypedDataV4, type TypedData } from '../src/core/chains/evmSign';
import { deriveEvmKey } from '../src/core/chains/evm';
import { hex } from '../src/core/xriq';

let fail = 0;
function eq(name: string, got: string, want: string) {
  if (got.toLowerCase() === want.toLowerCase()) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name}\n    got  ${got}\n    want ${want}`); }
}
function ok(name: string, cond: boolean) {
  if (cond) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name}`); }
}

const MNEMONIC = 'test test test test test test test test test test test junk';
const k = deriveEvmKey(MNEMONIC);
const wallet = new ethers.Wallet(hex.toHex(k.privateKey));

console.log('EIP-191 personal_sign hashing vs ethers');
for (const msg of ['Hello Lattice', 'sign in to dApp #42', '0xdeadbeef']) {
  eq(`hashMessage("${msg}")`, '0x' + hex.toHex(hashPersonalMessage(msg)), ethers.hashMessage(msg.startsWith('0x') ? ethers.getBytes(msg) : msg));
}

console.log('personal_sign signature recovers to signer (ethers)');
const sig = personalSign('Hello Lattice', k.privateKey);
eq('recovered address', ethers.verifyMessage('Hello Lattice', sig), wallet.address);

console.log('EIP-712 v4 typed-data hashing vs ethers (canonical Mail example)');
const typed: TypedData = {
  types: {
    EIP712Domain: [
      { name: 'name', type: 'string' },
      { name: 'version', type: 'string' },
      { name: 'chainId', type: 'uint256' },
      { name: 'verifyingContract', type: 'address' },
    ],
    Person: [
      { name: 'name', type: 'string' },
      { name: 'wallet', type: 'address' },
    ],
    Mail: [
      { name: 'from', type: 'Person' },
      { name: 'to', type: 'Person' },
      { name: 'contents', type: 'string' },
    ],
  },
  primaryType: 'Mail',
  domain: { name: 'Ether Mail', version: '1', chainId: 1, verifyingContract: '0xCcCCccccCCCCcCCCCCCcCcCccCcCCCcCcccccccC' },
  message: {
    from: { name: 'Cow', wallet: '0xCD2a3d9F938E13CD947Ec05AbC7FE734Df8DD826' },
    to: { name: 'Bob', wallet: '0xbBbBBBBbbBBBbbbBbbBbbbbBBbBbbbbBbBbbBBbB' },
    contents: 'Hello, Bob!',
  },
};
// ethers derives the domain separately; strip EIP712Domain from types for its API.
const { EIP712Domain, ...ethersTypes } = typed.types;
const ethersDigest = ethers.TypedDataEncoder.hash(typed.domain, ethersTypes, typed.message);
eq('hashTypedDataV4', '0x' + hex.toHex(hashTypedDataV4(typed)), ethersDigest);

const tdSig = signTypedDataV4(typed, k.privateKey);
eq('typed-data recovered address', ethers.verifyTypedData(typed.domain, ethersTypes, typed.message, tdSig), wallet.address);

console.log(`\n${fail === 0 ? 'ALL EVM SIGNING VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
