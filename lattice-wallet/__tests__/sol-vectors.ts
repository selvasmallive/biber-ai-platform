// Solana conformance — verifies the hand-rolled adapter against @solana/web3.js as a
// reference oracle: (1) key derivation and (2) transfer-message serialization must match
// byte-for-byte. Run: npx tsx __tests__/sol-vectors.ts
import { Keypair, PublicKey, SystemProgram, Transaction } from '@solana/web3.js';
import { derivePath } from 'ed25519-hd-key';
import { mnemonicToSeedSync } from '@scure/bip39';
import { base58 } from '@scure/base';
import { deriveSolanaKey, buildTransferMessage } from '../src/core/chains/solana';

let fail = 0;
function eq(name: string, got: string, want: string) {
  if (got === want) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name}\n    got  ${got}\n    want ${want}`); }
}

const MNEMONIC = 'test test test test test test test test test test test junk';

console.log('Derivation vs @solana/web3.js oracle (path m/44\'/501\'/0\'/0\')');
const seed = mnemonicToSeedSync(MNEMONIC);
const oracleKey = derivePath("m/44'/501'/0'/0'", Buffer.from(seed).toString('hex')).key;
const oracleAddr = Keypair.fromSeed(oracleKey).publicKey.toBase58();
eq('address matches web3.js', deriveSolanaKey(MNEMONIC).address, oracleAddr);

console.log('Transfer-message serialization vs web3.js oracle');
const mine = deriveSolanaKey(MNEMONIC);
const fromPk = new PublicKey(mine.publicKey);
const toBytes = new Uint8Array(32).fill(7);
const toPk = new PublicKey(toBytes);
const recentBlockhashBytes = new Uint8Array(32).fill(3);
const recentBlockhash = base58.encode(recentBlockhashBytes);
const lamports = 1_000_000n;

const oracleTx = new Transaction();
oracleTx.add(SystemProgram.transfer({ fromPubkey: fromPk, toPubkey: toPk, lamports: Number(lamports) }));
oracleTx.recentBlockhash = recentBlockhash;
oracleTx.feePayer = fromPk;
const oracleMsg = new Uint8Array(oracleTx.compileMessage().serialize());

const mineMsg = buildTransferMessage(mine.publicKey, toBytes, lamports, recentBlockhashBytes);

const toHex = (b: Uint8Array) => Array.from(b).map((x) => x.toString(16).padStart(2, '0')).join('');
eq('serialized message bytes', toHex(mineMsg), toHex(oracleMsg));

console.log(`\n${fail === 0 ? 'ALL SOLANA VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
