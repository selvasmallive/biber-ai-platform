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

async function esploraGet(base: string, path: string): Promise<any> {
  const res = await fetch(`${base}${path}`);
  if (!res.ok) throw new Error(`explorer ${path}: HTTP ${res.status}`);
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
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
    // Esplora-compatible shape; returns 0 if no endpoint is configured/reachable.
    try {
      const info = await esploraGet(this.base, `/address/${address}`);
      const c = info.chain_stats ?? {};
      return BigInt(c.funded_txo_sum ?? 0) - BigInt(c.spent_txo_sum ?? 0);
    } catch {
      return 0n;
    }
  }

  async getHistory(address: string): Promise<HistoryEntry[]> {
    try {
      const txs: any[] = await esploraGet(this.base, `/address/${address}/txs`);
      return (txs ?? []).slice(0, 50).map((t) => ({
        hash: t.txid,
        direction: 'unknown' as const,
        height: t.status?.block_height ? BigInt(t.status.block_height) : undefined,
      }));
    } catch {
      return [];
    }
  }

  async estimateFee(from: string, _req: TransferRequest): Promise<FeeEstimate> {
    // ZIP-317 conventional fee: 5000 zats × max(2, #inputs + #outputs).
    let nIn = 1;
    try {
      const utxos = await esploraGet(this.base, `/address/${from}/utxo`);
      nIn = Math.max(1, (utxos ?? []).length);
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
    const [utxosRaw, tipHeight] = await Promise.all([
      esploraGet(this.base, `/address/${k.address}/utxo`),
      esploraGet(this.base, '/blocks/tip/height').catch(() => 0),
    ]);
    const utxos = (utxosRaw ?? [])
      .map((u: any) => ({ txid: u.txid as string, vout: u.vout as number, value: BigInt(u.value) }))
      .sort((a: any, b: any) => (b.value > a.value ? 1 : -1));
    if (utxos.length === 0) throw new Error('No spendable Zcash UTXOs');

    const target = req.amountBaseUnits;
    const fee = BigInt(5000 * Math.max(2, utxos.length + 2));
    const selected: any[] = [];
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

    const expiryHeight = typeof tipHeight === 'number' && tipHeight > 0 ? tipHeight + 40 : Number(tipHeight) + 40 || 0;
    const signed = buildAndSignTransparent(inputs, outputs, 0, Number.isFinite(expiryHeight) ? expiryHeight : 0);

    const res = await fetch(`${this.base}/tx`, { method: 'POST', body: signed.rawHex });
    const body = await res.text();
    if (!res.ok) throw new Error(`broadcast failed: ${body}`);
    return { hash: body.trim() || signed.txid, raw: signed.rawHex };
  }
}
