// XRIQ HTTP RPC client — talks to the xriq-api service.
// Endpoints used (see xriq/crates/xriq-api/src/lib.rs):
//   GET  /api/v1/health
//   GET  /api/v1/network
//   GET  /api/v1/accounts/{address}
//   GET  /api/v1/wallet/transactions/{address}
//   POST /api/v1/faucet
//   POST /api/v1/wallet/transfers/submit-signed
import type { NetworkConfig } from './config';
import type { XriqTransaction, SignedTransfer } from './xriq';
import { buildSignedSubmitEnvelope } from './xriq';

export interface AccountInfo {
  address: string;
  balanceBaseUnits: bigint;
  nonce: bigint;
  exists: boolean;
}

export interface NetworkInfo {
  network: string;
  currentHeight: bigint;
  latestBlockHash: string;
  stateRoot: string;
}

export interface HistoryEntry {
  hash: string;
  from?: string;
  to?: string;
  amountBaseUnits?: bigint;
  feeBaseUnits?: bigint;
  nonce?: bigint;
  height?: bigint;
  direction: 'in' | 'out' | 'self' | 'unknown';
}

export class RpcError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly body?: unknown,
  ) {
    super(message);
    this.name = 'RpcError';
  }
}

const TIMEOUT_MS = 15000;

async function request<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(`${base}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { 'content-type': 'application/json', accept: 'application/json', ...(init?.headers ?? {}) },
    });
    const text = await res.text();
    let json: unknown = undefined;
    try {
      json = text ? JSON.parse(text) : undefined;
    } catch {
      /* non-JSON body */
    }
    if (!res.ok) {
      throw new RpcError(`HTTP ${res.status} for ${path}`, res.status, json ?? text);
    }
    return json as T;
  } catch (e) {
    if (e instanceof RpcError) throw e;
    if ((e as Error).name === 'AbortError') throw new RpcError(`Request timed out: ${path}`);
    throw new RpcError(`Network error for ${path}: ${(e as Error).message}`);
  } finally {
    clearTimeout(timer);
  }
}

function toBig(v: unknown): bigint | undefined {
  if (v === null || v === undefined) return undefined;
  if (typeof v === 'bigint') return v;
  if (typeof v === 'number') return BigInt(Math.trunc(v));
  if (typeof v === 'string' && /^-?\d+$/.test(v.trim())) return BigInt(v.trim());
  return undefined;
}

export class XriqRpc {
  constructor(private net: NetworkConfig) {}

  get network() {
    return this.net;
  }

  async health(): Promise<boolean> {
    try {
      const h = await request<{ ok?: boolean }>(this.net.rpcUrl, '/api/v1/health');
      return h?.ok !== false;
    } catch {
      return false;
    }
  }

  async getNetwork(): Promise<NetworkInfo> {
    const n = await request<any>(this.net.rpcUrl, '/api/v1/network');
    return {
      network: n.network ?? n.chain_id ?? this.net.chainId,
      currentHeight: toBig(n.current_height) ?? 0n,
      latestBlockHash: n.latest_block_hash ?? '',
      stateRoot: n.state_root ?? '',
    };
  }

  async getAccount(address: string): Promise<AccountInfo> {
    try {
      const a = await request<any>(this.net.rpcUrl, `/api/v1/accounts/${encodeURIComponent(address)}`);
      const balance = toBig(a.balance_base_units ?? a.balance ?? a.balance_base_units_str);
      const nonce = toBig(a.nonce);
      return {
        address,
        balanceBaseUnits: balance ?? 0n,
        nonce: nonce ?? 0n,
        exists: balance !== undefined || nonce !== undefined,
      };
    } catch (e) {
      // A never-seen account (404) is a valid zero-balance, nonce-0 account.
      if (e instanceof RpcError && e.status === 404) {
        return { address, balanceBaseUnits: 0n, nonce: 0n, exists: false };
      }
      throw e;
    }
  }

  async getHistory(address: string, limit = 50): Promise<HistoryEntry[]> {
    const r = await request<any>(
      this.net.rpcUrl,
      `/api/v1/wallet/transactions/${encodeURIComponent(address)}?limit=${limit}`,
    );
    const list: any[] = Array.isArray(r) ? r : (r.transactions ?? r.items ?? r.entries ?? []);
    return list.map((t) => {
      const from = t.from ?? t.sender;
      const to = t.to ?? t.recipient;
      let direction: HistoryEntry['direction'] = 'unknown';
      if (from === address && to === address) direction = 'self';
      else if (from === address) direction = 'out';
      else if (to === address) direction = 'in';
      return {
        hash: t.transaction_hash ?? t.hash ?? '',
        from,
        to,
        amountBaseUnits: toBig(t.amount_base_units ?? t.amount),
        feeBaseUnits: toBig(t.fee_base_units ?? t.fee),
        nonce: toBig(t.nonce),
        height: toBig(t.height ?? t.block_height),
        direction,
      };
    });
  }

  async faucet(address: string): Promise<unknown> {
    if (!this.net.faucetEnabled) throw new RpcError('Faucet disabled for this network');
    return request(this.net.rpcUrl, '/api/v1/faucet', {
      method: 'POST',
      body: JSON.stringify({ to_address: address }),
    });
  }

  /** Submit a locally-signed transfer. Keys never leave the device. */
  async submitSigned(tx: XriqTransaction, signed: SignedTransfer): Promise<any> {
    const envelope = buildSignedSubmitEnvelope(tx, signed);
    return request(this.net.rpcUrl, '/api/v1/wallet/transfers/submit-signed', {
      method: 'POST',
      body: JSON.stringify(envelope),
    });
  }
}
