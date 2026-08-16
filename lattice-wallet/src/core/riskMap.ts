// Pure Phase-3 risk-scan types + response mapping (no native/secure-store deps, so this is
// unit-testable). The network + secure-storage side lives in risk.ts.
import type { AssetDelta } from './simulate';

export type RiskLevel = 'benign' | 'warning' | 'malicious' | 'error' | 'unknown';

export interface RiskResult {
  level: RiskLevel;
  summary?: string;
  issues: string[];
  assetChanges?: AssetDelta[];
  provider: string;
}

// eip155 chain id -> Blockaid chain name.
const BLOCKAID_CHAINS: Record<number, string> = {
  1: 'ethereum',
  137: 'polygon',
  8453: 'base',
  42161: 'arbitrum',
  10: 'optimism',
  56: 'bsc',
  43114: 'avalanche',
};

export function blockaidChainName(evmChainId?: number): string | null {
  return evmChainId != null ? BLOCKAID_CHAINS[evmChainId] ?? null : null;
}

function levelFromResultType(rt: unknown): RiskLevel {
  switch (String(rt).toLowerCase()) {
    case 'benign': return 'benign';
    case 'warning': return 'warning';
    case 'malicious': return 'malicious';
    case 'error': return 'error';
    default: return 'unknown';
  }
}

function toBig(v: unknown): bigint | undefined {
  if (v == null) return undefined;
  const s = String(v).trim();
  if (/^-?\d+$/.test(s)) return BigInt(s);
  if (/^0x[0-9a-fA-F]+$/.test(s)) return BigInt(s);
  return undefined;
}

function mapDiffSide(list: any[], direction: 'in' | 'out'): AssetDelta[] {
  return (list ?? []).map((d: any) => {
    const asset = d.asset ?? {};
    const std = String(asset.type ?? asset.standard ?? 'ERC20').toUpperCase();
    const amount = toBig(d.raw_value ?? d.raw_amount ?? d.value) ?? 0n;
    return {
      kind: std.includes('721') || std.includes('1155') ? 'erc721' : std.includes('NATIVE') ? 'native' : 'erc20',
      token: asset.address ?? asset.contract_address,
      symbol: asset.symbol,
      decimals: typeof asset.decimals === 'number' ? asset.decimals : 18,
      direction,
      amount,
    } as AssetDelta;
  });
}

/** Pure: map a Blockaid scan response into a RiskResult. */
export function mapBlockaidResponse(json: any, account: string): RiskResult {
  const validation = json?.validation ?? {};
  const level = levelFromResultType(validation.result_type);
  const issues = (validation.features ?? [])
    .filter((f: any) => ['malicious', 'warning'].includes(String(f?.type).toLowerCase()))
    .map((f: any) => String(f?.description ?? f?.feature_id ?? '').trim())
    .filter(Boolean);

  let assetChanges: AssetDelta[] | undefined;
  const diffs = json?.simulation?.assets_diffs ?? json?.simulation?.account_summary?.assets_diffs;
  if (diffs) {
    const perAccount = diffs[account?.toLowerCase()] ?? diffs[account] ?? Object.values(diffs)[0] ?? {};
    assetChanges = [...mapDiffSide((perAccount as any).out, 'out'), ...mapDiffSide((perAccount as any).in, 'in')];
  }

  return { level, summary: validation.description ?? validation.reason, issues, assetChanges, provider: 'blockaid' };
}
