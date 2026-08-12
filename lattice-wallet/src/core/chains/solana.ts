// Solana adapter — Ed25519 keys (SLIP-0010, Phantom-compatible path m/44'/501'/0'/0'),
// base58 addresses, hand-rolled legacy transaction assembly for a native SOL transfer.
// The message serialization is verified byte-for-byte against @solana/web3.js in
// __tests__/sol-vectors.ts, and the derivation against the same reference oracle.
import { base58 } from '@scure/base';
import { ed25519 } from '@noble/curves/ed25519';
import { seedFromMnemonic } from '../xriq';
import type { HistoryEntry } from '../rpc';
import type {
  ChainAdapter,
  ChainConfig,
  DerivedAccount,
  FeeEstimate,
  TransferRequest,
  BroadcastResult,
} from './types';

const HARDENED = 0x80000000;
export const SOLANA_PATH = [44 + HARDENED, 501 + HARDENED, 0 + HARDENED, 0 + HARDENED];
const SYSTEM_PROGRAM_ID = new Uint8Array(32); // all zeros = "111…111"
const LAMPORTS_PER_SIGNATURE = 5000n;

export function deriveSolanaKey(mnemonic: string): { privateSeed: Uint8Array; publicKey: Uint8Array; address: string } {
  const privateSeed = seedFromMnemonic(mnemonic, SOLANA_PATH);
  const publicKey = ed25519.getPublicKey(privateSeed);
  return { privateSeed, publicKey, address: base58.encode(publicKey) };
}

// compact-u16 (shortvec) length prefix.
function encodeLength(len: number): number[] {
  const out: number[] = [];
  let rem = len;
  for (;;) {
    let elem = rem & 0x7f;
    rem >>= 7;
    if (rem === 0) {
      out.push(elem);
      break;
    }
    elem |= 0x80;
    out.push(elem);
  }
  return out;
}

function u32le(v: number): number[] {
  return [v & 0xff, (v >> 8) & 0xff, (v >> 16) & 0xff, (v >> 24) & 0xff];
}

function u64le(v: bigint): number[] {
  const out: number[] = [];
  let x = v;
  for (let i = 0; i < 8; i++) {
    out.push(Number(x & 0xffn));
    x >>= 8n;
  }
  return out;
}

/**
 * Serialize a legacy transfer message.
 * accounts = [from(signer,writable), to(writable), systemProgram(readonly)].
 * SystemProgram Transfer data = u32(2) || u64(lamports).
 */
export function buildTransferMessage(
  fromPubkey: Uint8Array,
  toPubkey: Uint8Array,
  lamports: bigint,
  recentBlockhash: Uint8Array,
): Uint8Array {
  const accounts = [fromPubkey, toPubkey, SYSTEM_PROGRAM_ID];
  const header = [1, 0, 1]; // 1 required sig, 0 readonly-signed, 1 readonly-unsigned
  const data = [...u32le(2), ...u64le(lamports)];
  const instruction = [
    2, // programIdIndex (systemProgram)
    ...encodeLength(2),
    0,
    1, // account indexes: from, to
    ...encodeLength(data.length),
    ...data,
  ];
  const bytes: number[] = [
    ...header,
    ...encodeLength(accounts.length),
    ...accounts.flatMap((a) => Array.from(a)),
    ...Array.from(recentBlockhash),
    ...encodeLength(1),
    ...instruction,
  ];
  return new Uint8Array(bytes);
}

function b64encode(bytes: Uint8Array): string {
  // React Native has global btoa; fall back to a manual encoder if absent.
  const g: any = globalThis as any;
  let binary = '';
  for (const b of bytes) binary += String.fromCharCode(b);
  if (typeof g.btoa === 'function') return g.btoa(binary);
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  let out = '';
  for (let i = 0; i < bytes.length; i += 3) {
    const a = bytes[i], b = bytes[i + 1], c = bytes[i + 2];
    out += chars[a >> 2];
    out += chars[((a & 3) << 4) | (b >> 4 || 0)];
    out += i + 1 < bytes.length ? chars[((b & 15) << 2) | (c >> 6 || 0)] : '=';
    out += i + 2 < bytes.length ? chars[c & 63] : '=';
  }
  return out;
}

async function rpc<T>(url: string, method: string, params: unknown[]): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  });
  const json: any = await res.json();
  if (json.error) throw new Error(`${method}: ${json.error.message ?? JSON.stringify(json.error)}`);
  return json.result as T;
}

export class SolanaAdapter implements ChainAdapter {
  constructor(readonly config: ChainConfig) {}

  deriveAccount(mnemonic: string): DerivedAccount {
    const k = deriveSolanaKey(mnemonic);
    return { chainId: this.config.id, address: k.address, publicKeyHex: Array.from(k.publicKey).map((b) => b.toString(16).padStart(2, '0')).join(''), path: "m/44'/501'/0'/0'" };
  }

  validateAddress(address: string): boolean {
    try {
      const decoded = base58.decode(address.trim());
      return decoded.length === 32;
    } catch {
      return false;
    }
  }

  async getBalance(address: string): Promise<bigint> {
    const r = await rpc<{ value: number }>(this.config.rpcUrl, 'getBalance', [address]);
    return BigInt(r.value ?? 0);
  }

  async getHistory(address: string): Promise<HistoryEntry[]> {
    const sigs = await rpc<any[]>(this.config.rpcUrl, 'getSignaturesForAddress', [address, { limit: 25 }]);
    return (sigs ?? []).map((s) => ({
      hash: s.signature,
      direction: 'unknown' as const,
      height: s.slot ? BigInt(s.slot) : undefined,
    }));
  }

  async estimateFee(): Promise<FeeEstimate> {
    return { feeBaseUnits: LAMPORTS_PER_SIGNATURE, detail: 'base fee per signature' };
  }

  async send(mnemonic: string, req: TransferRequest): Promise<BroadcastResult> {
    const k = deriveSolanaKey(mnemonic);
    const to = base58.decode(req.to.trim());
    if (to.length !== 32) throw new Error('invalid Solana recipient');
    const { value } = await rpc<{ value: { blockhash: string } }>(
      this.config.rpcUrl,
      'getLatestBlockhash',
      [{ commitment: 'finalized' }],
    );
    const recentBlockhash = base58.decode(value.blockhash);
    const message = buildTransferMessage(k.publicKey, to, req.amountBaseUnits, recentBlockhash);
    const signature = ed25519.sign(message, k.privateSeed);
    const wire = new Uint8Array([...encodeLength(1), ...signature, ...message]);
    const sig = await rpc<string>(this.config.rpcUrl, 'sendTransaction', [
      b64encode(wire),
      { encoding: 'base64', preflightCommitment: 'finalized' },
    ]);
    return { hash: sig };
  }
}
