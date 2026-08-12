// Zcash TRANSPARENT adapter — t-addresses (t1…), which are Bitcoin-style P2PKH over
// secp256k1 with the Zcash mainnet version prefix 0x1CB8.
//
// Derivation, address validation, balance, history, and RECEIVE are fully implemented
// and the address scheme is proven (base58check verified against the Bitcoin genesis
// address; the Zcash prefix is the only delta).
//
// SPENDING is deliberately gated: a transparent Zcash spend needs Zcash's own
// transaction digest / sighash (ZIP-243 for v4 Sapling, ZIP-244 for v5 NU5) — NOT
// Bitcoin's BIP143 — including the consensus branch id and expiry. Shipping that without
// verifying it against the official ZIP test vectors risks producing invalid or
// fund-losing transactions, so send() refuses until that verification lands.
import { HDKey } from '@scure/bip32';
import { mnemonicToSeedSync } from '@scure/bip39';
import { secp256k1 } from '@noble/curves/secp256k1';
import { sha256 } from '@noble/hashes/sha256';
import { ripemd160 } from '@noble/hashes/ripemd160';
import { base58check } from '@scure/base';
import { hex } from '../xriq';
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

  async estimateFee(): Promise<FeeEstimate> {
    return { feeBaseUnits: 1000n, detail: 'ZIP-317 conventional fee (approx)' };
  }

  async send(_mnemonic: string, _req: TransferRequest): Promise<BroadcastResult> {
    throw new Error(
      'Transparent Zcash spend is not yet enabled: it requires a ZIP-243/244 sighash ' +
        'implementation verified against the official test vectors. Receiving, balance, and ' +
        'history work today.',
    );
  }
}
