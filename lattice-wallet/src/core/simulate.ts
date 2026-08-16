// Transaction simulation — Phase 1 (privacy-first, default, no third parties).
//
// 1) Static calldata decode: recognise common drain vectors (approve / setApprovalForAll /
//    transfer) and flag unlimited allowances.
// 2) Dry-run via eth_call against the USER'S OWN RPC: catch transactions that will REVERT
//    before the user spends gas, and decode the revert reason.
//
// Everything here uses the configured RPC only — nothing is sent to a third party. Richer
// asset-change simulation (Phase 2, needs a trace-capable RPC) and third-party risk APIs
// (Phase 3, opt-in) build on this same interface.
import { hex } from './xriq';

export interface ApprovalChange {
  spender: string;
  amount: bigint;
  unlimited: boolean;
  kind: 'erc20-allowance' | 'nft-operator';
}

export interface CalldataDecode {
  lines: string[];
  approvals: ApprovalChange[];
  warnings: string[];
}

export interface EvmTxParams {
  from?: string;
  to?: string;
  value?: string;
  data?: string;
}

export type SimStatus = 'ok' | 'revert' | 'unknown';

export interface SimulationResult {
  status: SimStatus;
  revertReason?: string;
  approvals: ApprovalChange[];
  warnings: string[];
  source: string;
}

const UNLIMITED = 1n << 255n;
const SELECTORS: Record<string, string> = {
  '0xa9059cbb': 'transfer',
  '0x095ea7b3': 'approve',
  '0x23b872dd': 'transferFrom',
  '0xa22cb465': 'setApprovalForAll',
  '0x39509351': 'increaseAllowance',
};

function word(data: string, i: number): string {
  return data.slice(10 + i * 64, 10 + (i + 1) * 64);
}
function addrFromWord(w: string): string {
  return '0x' + w.slice(24);
}
function short(a: string): string {
  return a.length > 12 ? `${a.slice(0, 8)}…${a.slice(-4)}` : a;
}

/** Static decode of EVM calldata for the known high-risk functions. */
export function decodeCalldata(data?: string): CalldataDecode {
  const lines: string[] = [];
  const approvals: ApprovalChange[] = [];
  const warnings: string[] = [];
  if (!data || data === '0x') return { lines, approvals, warnings };
  try {
    const sel = data.slice(0, 10).toLowerCase();
    const name = SELECTORS[sel];
    lines.push(`Selector: ${sel}`);
    if (name === 'approve' || name === 'increaseAllowance') {
      const spender = addrFromWord(word(data, 0));
      const amount = BigInt('0x' + word(data, 1));
      const unlimited = amount >= UNLIMITED;
      lines.push(`Function: ${name}`, `Spender: ${short(spender)}`, `Amount: ${unlimited ? 'UNLIMITED' : amount.toString()}`);
      approvals.push({ spender, amount, unlimited, kind: 'erc20-allowance' });
      warnings.push(unlimited
        ? `Grants UNLIMITED token allowance to ${short(spender)}. A common drain pattern — only approve if you trust it.`
        : `Grants a token spending allowance to ${short(spender)}.`);
    } else if (name === 'setApprovalForAll') {
      const operator = addrFromWord(word(data, 0));
      const approved = BigInt('0x' + word(data, 1)) !== 0n;
      lines.push('Function: setApprovalForAll', `Operator: ${short(operator)}`, `Approved: ${approved}`);
      if (approved) {
        approvals.push({ spender: operator, amount: UNLIMITED, unlimited: true, kind: 'nft-operator' });
        warnings.push(`Grants control of ALL your NFTs in this collection to ${short(operator)}.`);
      }
    } else if (name === 'transfer') {
      lines.push('Function: transfer', `To: ${short(addrFromWord(word(data, 0)))}`, `Amount: ${BigInt('0x' + word(data, 1)).toString()} (token units)`);
    } else if (name) {
      lines.push(`Function: ${name}`);
    } else {
      warnings.push("Unknown contract call — Lattice can't decode it. Only approve if you trust this dApp.");
    }
  } catch {
    warnings.push('Malformed calldata — do not approve unless you trust this dApp.');
  }
  return { lines, approvals, warnings };
}

// Solidity revert selectors.
const ERROR_STRING = '08c379a0'; // Error(string)
const PANIC = '4e487b71'; // Panic(uint256)

function decodeRevert(raw: any): string | undefined {
  let data = raw;
  if (data && typeof data === 'object') data = typeof data.data === 'string' ? data.data : undefined;
  if (typeof data !== 'string') return undefined;
  const d = data.replace(/^0x/, '');
  if (d.startsWith(ERROR_STRING)) {
    try {
      const len = Number(BigInt('0x' + d.slice(8 + 64, 8 + 128)));
      return new TextDecoder().decode(hex.fromHex(d.slice(8 + 128, 8 + 128 + len * 2)));
    } catch {
      return undefined;
    }
  }
  if (d.startsWith(PANIC)) {
    try {
      return `Panic(0x${BigInt('0x' + d.slice(8, 8 + 64)).toString(16)})`;
    } catch {
      return undefined;
    }
  }
  return undefined;
}

/** Dry-run a transaction with eth_call; detect reverts and extract the reason. */
export async function dryRunEvm(rpcUrl: string, tx: EvmTxParams): Promise<{ status: SimStatus; revertReason?: string }> {
  try {
    const res = await fetch(rpcUrl, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'eth_call',
        params: [{ from: tx.from, to: tx.to, value: tx.value ?? '0x0', data: tx.data ?? '0x' }, 'latest'],
      }),
    });
    const json: any = await res.json();
    if (json.error) {
      const cleaned = String(json.error.message ?? 'reverted').replace(/^execution reverted:?\s*/i, '').trim();
      const reason = decodeRevert(json.error.data) ?? (cleaned || 'reverted');
      return { status: 'revert', revertReason: reason };
    }
    return { status: 'ok' };
  } catch {
    // Network/RPC problem — don't block signing, just can't simulate.
    return { status: 'unknown' };
  }
}

/** Full Phase-1 simulation: static decode + dry-run. */
export async function simulateEvm(rpcUrl: string, tx: EvmTxParams): Promise<SimulationResult> {
  const decoded = decodeCalldata(tx.data);
  const run = await dryRunEvm(rpcUrl, tx);
  const warnings = [...decoded.warnings];
  if (run.status === 'revert') warnings.unshift(`Expected to FAIL${run.revertReason ? `: ${run.revertReason}` : ''}.`);
  return { status: run.status, revertReason: run.revertReason, approvals: decoded.approvals, warnings, source: 'rpc-call' };
}
