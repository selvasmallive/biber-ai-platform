// Bitcoin adapter — BIP84 native SegWit (P2WPKH, bc1q…). Signing uses the audited
// @scure/btc-signer (correct BIP143 sighash); UTXOs/balance/history/broadcast come from
// an Esplora HTTP API (blockstream.info / mempool.space compatible).
import { HDKey } from '@scure/bip32';
import { mnemonicToSeedSync } from '@scure/bip39';
import * as btc from '@scure/btc-signer';
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

interface Utxo {
  txid: string;
  vout: number;
  value: bigint;
}

const DUST = 546n;

export function deriveBtcKey(mnemonic: string, accountIndex = 0): { privateKey: Uint8Array; publicKey: Uint8Array; address: string; path: string } {
  const seed = mnemonicToSeedSync(mnemonic.trim());
  const path = `m/84'/0'/0'/0/${accountIndex}`;
  const child = HDKey.fromMasterSeed(seed).derive(path);
  if (!child.privateKey || !child.publicKey) throw new Error('failed to derive BTC key');
  const address = btc.p2wpkh(child.publicKey, btc.NETWORK).address!;
  return { privateKey: child.privateKey, publicKey: child.publicKey, address, path };
}

async function esploraGet(base: string, path: string): Promise<any> {
  const res = await fetch(`${base}${path}`);
  if (!res.ok) throw new Error(`esplora ${path}: HTTP ${res.status}`);
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export class BitcoinAdapter implements ChainAdapter {
  constructor(readonly config: ChainConfig) {}

  private get base() {
    return this.config.rpcUrl.replace(/\/$/, '');
  }

  deriveAccount(mnemonic: string): DerivedAccount {
    const k = deriveBtcKey(mnemonic);
    return { chainId: this.config.id, address: k.address, publicKeyHex: hex.toHex(k.publicKey), path: k.path };
  }

  validateAddress(address: string): boolean {
    try {
      const decoded = btc.Address(btc.NETWORK).decode(address.trim());
      return decoded.type === 'wpkh' || decoded.type === 'pkh' || decoded.type === 'wsh' || decoded.type === 'tr' || decoded.type === 'sh';
    } catch {
      return false;
    }
  }

  async getBalance(address: string): Promise<bigint> {
    const info = await esploraGet(this.base, `/address/${address}`);
    const c = info.chain_stats ?? {};
    const m = info.mempool_stats ?? {};
    const funded = BigInt(c.funded_txo_sum ?? 0) + BigInt(m.funded_txo_sum ?? 0);
    const spent = BigInt(c.spent_txo_sum ?? 0) + BigInt(m.spent_txo_sum ?? 0);
    return funded - spent;
  }

  async getHistory(address: string): Promise<HistoryEntry[]> {
    const txs: any[] = await esploraGet(this.base, `/address/${address}/txs`);
    return (txs ?? []).slice(0, 50).map((t) => {
      const outToAddr = (t.vout ?? []).some((o: any) => o.scriptpubkey_address === address);
      const inFromAddr = (t.vin ?? []).some((i: any) => i.prevout?.scriptpubkey_address === address);
      const direction: HistoryEntry['direction'] = inFromAddr ? 'out' : outToAddr ? 'in' : 'unknown';
      const received = (t.vout ?? [])
        .filter((o: any) => o.scriptpubkey_address === address)
        .reduce((s: bigint, o: any) => s + BigInt(o.value ?? 0), 0n);
      return {
        hash: t.txid,
        direction,
        amountBaseUnits: received,
        height: t.status?.block_height ? BigInt(t.status.block_height) : undefined,
      };
    });
  }

  private async feeRate(): Promise<number> {
    try {
      const est = await esploraGet(this.base, '/fee-estimates');
      return Math.max(1, Math.ceil(est['6'] ?? est['3'] ?? est['1'] ?? 2));
    } catch {
      return 5; // sat/vByte fallback
    }
  }

  async estimateFee(from: string, _req: TransferRequest): Promise<FeeEstimate> {
    const rate = await this.feeRate();
    // Rough: 1 input + 2 outputs P2WPKH ≈ 141 vBytes.
    return { feeBaseUnits: BigInt(Math.ceil(141 * rate)), detail: `${rate} sat/vB` };
  }

  async send(mnemonic: string, req: TransferRequest): Promise<BroadcastResult> {
    const k = deriveBtcKey(mnemonic);
    const spend = btc.p2wpkh(k.publicKey, btc.NETWORK);
    const [utxosRaw, rate] = await Promise.all([
      esploraGet(this.base, `/address/${k.address}/utxo`),
      this.feeRate(),
    ]);
    const utxos: Utxo[] = (utxosRaw ?? [])
      .map((u: any) => ({ txid: u.txid, vout: u.vout, value: BigInt(u.value) }))
      .sort((a: Utxo, b: Utxo) => (b.value > a.value ? 1 : -1));

    const target = req.amountBaseUnits;
    const selected: Utxo[] = [];
    let inputSum = 0n;
    // Largest-first selection covering amount + a running fee estimate.
    for (const u of utxos) {
      selected.push(u);
      inputSum += u.value;
      const vbytes = BigInt(selected.length) * 68n + 62n + 11n; // inputs + 2 outputs + overhead
      const fee = vbytes * BigInt(rate);
      if (inputSum >= target + fee) break;
    }
    if (selected.length === 0) throw new Error('No spendable UTXOs');

    const vbytes = BigInt(selected.length) * 68n + 62n + 11n;
    const fee = vbytes * BigInt(rate);
    if (inputSum < target + fee) throw new Error('Insufficient balance for amount + fee');

    const tx = new btc.Transaction();
    for (const u of selected) {
      tx.addInput({
        txid: hex.fromHex(u.txid),
        index: u.vout,
        witnessUtxo: { script: spend.script, amount: u.value },
      });
    }
    tx.addOutputAddress(req.to.trim(), target, btc.NETWORK);
    const change = inputSum - target - fee;
    if (change >= DUST) tx.addOutputAddress(k.address, change, btc.NETWORK);
    tx.sign(k.privateKey);
    tx.finalize();

    const rawHex = tx.hex;
    const res = await fetch(`${this.base}/tx`, { method: 'POST', body: rawHex });
    const body = await res.text();
    if (!res.ok) throw new Error(`broadcast failed: ${body}`);
    return { hash: body.trim() || tx.id, raw: rawHex };
  }
}
