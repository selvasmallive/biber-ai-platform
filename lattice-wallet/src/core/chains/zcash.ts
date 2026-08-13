// Zcash TRANSPARENT adapter — t-addresses (t1…), which are Bitcoin-style P2PKH over
// secp256k1 with the Zcash mainnet version prefix 0x1CB8.
//
// Derivation, address validation, balance, history, receive, and SEND are implemented.
// The spend uses Zcash's own v5 (NU5) transaction digest / SIGHASH_ALL from `zcashTx.ts`,
// which is verified byte-for-byte against the official ZIP-244 test vectors
// (__tests__/zec-sighash-vectors.ts). Broadcasting requires `rpcUrl` to point at an
// Esplora-compatible Zcash endpoint that accepts POST /tx.
import { HDKey } from '@scure/bip32';
import { mnemonicToSeedSync } from '@scure/bip39';
import { secp256k1 } from '@noble/curves/secp256k1';
import { sha256 } from '@noble/hashes/sha256';
import { ripemd160 } from '@noble/hashes/ripemd160';
import { base58check } from '@scure/base';
import { hex } from '../xriq';
import {
  buildAndSignTransparent,
  p2pkhScript,
  type SpendInput,
  type SpendOutput,
} from './zcashTx';
import type { HistoryEntry } from '../rpc';
import type {
  ChainAdapter,
  ChainConfig,
  DerivedAccount,
  FeeEstimate,
  TransferRequest,
  BroadcastResult,
} from './types';

const b58c = base58check(sha256);
// Zcash mainnet transparent P2PKH address prefix.
const ZCASH_T1_PREFIX = new Uint8Array([0x1c, 0xb8]);

function hash160(data: Uint8Array): Uint8Array {
  return ripemd160(sha256(data));
}

export function zcashTransparentAddress(publicKeyCompressed: Uint8Array): string {
  return b58c.encode(new Uint8Array([...ZCASH_T1_PREFIX, ...hash160(publicKeyCompressed)]));
}

export function deriveZcashKey(mnemonic: string, accountIndex = 0): { privateKey: Uint8Array; publicKey: Uint8Array; address: string; path: string } {
  const seed = mnemonicToSeedSync(mnemonic.trim());
  const path = `m/44'/133'/0'/0/${accountIndex}`;
  const child = HDKey.fromMasterSeed(seed).derive(path);
  if (!child.privateKey || !child.publicKey) throw new Error('failed to derive ZEC key');
  const publicKey = secp256k1.getPublicKey(child.privateKey, true); // compressed
  return { privateKey: child.privateKey, publicKey, address: zcashTransparentAddress(publicKey), path };
}

// ---------------------------------------------------------------------------
// Data backend: Blockchair Zcash API (public). No public Esplora instance exists for
// Zcash; Blockchair is the verified default. Override `rpcUrl` for a self-hosted node.
//   balance/utxo/history: GET /dashboards/address/{addr}
//   tip height:           GET /stats
//   broadcast:            POST /push/transaction  (form: data=<rawhex>)
// ---------------------------------------------------------------------------
interface ZcashUtxo {
  txid: string; // display order
  vout: number;
  value: bigint;
}

async function bcGet(base: string, path: string): Promise<any> {
  const res = await fetch(`${base}${path}`, { headers: { accept: 'application/json' } });
  const json = await res.json().catch(() => null);
  if (!res.ok || !json) throw new Error(`blockchair ${path}: HTTP ${res.status}`);
  return json;
}

async function bcAddress(
  base: string,
  addr: string,
): Promise<{ balance: bigint; utxo: ZcashUtxo[]; txids: string[] }> {
  const json = await bcGet(base, `/dashboards/address/${encodeURIComponent(addr)}?limit=50`);
  const a = json?.data?.[addr];
  if (!a) return { balance: 0n, utxo: [], txids: [] };
  return {
    balance: BigInt(a.address?.balance ?? 0),
    utxo: (a.utxo ?? []).map((u: any) => ({ txid: u.transaction_hash, vout: u.index, value: BigInt(u.value) })),
    txids: (a.transactions ?? []) as string[],
  };
}

async function bcTipHeight(base: string): Promise<number> {
  try {
    const json = await bcGet(base, '/stats');
    return Number(json?.data?.best_block_height ?? 0);
  } catch {
    return 0;
  }
}

export class ZcashTransparentAdapter implements ChainAdapter {
  constructor(readonly config: ChainConfig) {}

  private get base() {
    return this.config.rpcUrl.replace(/\/$/, '');
  }

  deriveAccount(mnemonic: string): DerivedAccount {
    const k = deriveZcashKey(mnemonic);
    return { chainId: this.config.id, address: k.address, publicKeyHex: hex.toHex(k.publicKey), path: k.path };
  }

  validateAddress(address: string): boolean {
    const a = address.trim();
    if (!a.startsWith('t1') && !a.startsWith('t3')) return false;
    try {
      const decoded = b58c.decode(a);
      return decoded.length === 22; // 2-byte prefix + 20-byte hash160
    } catch {
      return false;
    }
  }

  async getBalance(address: string): Promise<bigint> {
    try {
      return (await bcAddress(this.base, address)).balance;
    } catch {
      return 0n;
    }
  }

  async getHistory(address: string): Promise<HistoryEntry[]> {
    try {
      const { txids } = await bcAddress(this.base, address);
      return txids.slice(0, 50).map((hash) => ({ hash, direction: 'unknown' as const }));
    } catch {
      return [];
    }
  }

  async estimateFee(from: string, _req: TransferRequest): Promise<FeeEstimate> {
    // ZIP-317 conventional fee: 5000 zats × max(2, #inputs + #outputs).
    let nIn = 1;
    try {
      nIn = Math.max(1, (await bcAddress(this.base, from)).utxo.length);
    } catch {
      /* keep default */
    }
    const logical = Math.max(2, nIn + 2);
    return { feeBaseUnits: BigInt(5000 * logical), detail: 'ZIP-317 conventional fee' };
  }

  private hash160FromAddress(address: string): Uint8Array {
    const decoded = b58c.decode(address.trim());
    if (decoded.length !== 22) throw new Error('invalid Zcash transparent address');
    return decoded.subarray(2); // strip 2-byte t1 prefix
  }

  async send(mnemonic: string, req: TransferRequest): Promise<BroadcastResult> {
    const k = deriveZcashKey(mnemonic);
    if (!this.validateAddress(req.to)) throw new Error('Recipient is not a transparent Zcash (t1) address');

    const myScript = p2pkhScript(hash160(k.publicKey));
    const [{ utxo }, tipHeight] = await Promise.all([
      bcAddress(this.base, k.address),
      bcTipHeight(this.base),
    ]);
    const utxos = [...utxo].sort((a, b) => (b.value > a.value ? 1 : -1));
    if (utxos.length === 0) throw new Error('No spendable Zcash UTXOs');

    const target = req.amountBaseUnits;
    const fee = BigInt(5000 * Math.max(2, utxos.length + 2));
    const selected: ZcashUtxo[] = [];
    let sum = 0n;
    for (const u of utxos) {
      selected.push(u);
      sum += u.value;
      if (sum >= target + fee) break;
    }
    if (sum < target + fee) throw new Error('Insufficient balance for amount + fee');

    const inputs: SpendInput[] = selected.map((u) => ({
      txidLE: Uint8Array.from(hex.fromHex(u.txid)).reverse(), // display -> internal order
      vout: u.vout,
      value: u.value,
      scriptPubKey: myScript,
      privateKey: k.privateKey,
      publicKey: k.publicKey,
    }));
    const outputs: SpendOutput[] = [{ value: target, scriptPubKey: p2pkhScript(this.hash160FromAddress(req.to)) }];
    const change = sum - target - fee;
    if (change >= 1000n) outputs.push({ value: change, scriptPubKey: myScript });

    const expiryHeight = tipHeight > 0 ? tipHeight + 40 : 0;
    const signed = buildAndSignTransparent(inputs, outputs, 0, expiryHeight);

    // Broadcast via Blockchair push endpoint (form-encoded raw hex).
    const res = await fetch(`${this.base}/push/transaction`, {
      method: 'POST',
      headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: `data=${signed.rawHex}`,
    });
    const json = await res.json().catch(() => null);
    const broadcastHash = json?.data?.transaction_hash;
    if (!res.ok || !broadcastHash) {
      throw new Error(`broadcast failed: ${JSON.stringify(json)?.slice(0, 200) ?? res.status}`);
    }
    return { hash: broadcastHash, raw: signed.rawHex };
  }
}
