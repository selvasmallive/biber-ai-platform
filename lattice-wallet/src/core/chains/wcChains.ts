// Pure helpers for WalletConnect chain-management (wallet_switchEthereumChain /
// wallet_addEthereumChain). Kept free of the WalletConnect SDK so they are unit-testable.
import type { ChainConfig } from './types';
import { evmConfigByChainId } from './registry';

/** Resolve an EVM chain id to a config: built-in registry first, then user/dApp customs. */
export function resolveEvmConfig(evmChainId: number, custom: ChainConfig[]): ChainConfig | null {
  return evmConfigByChainId(evmChainId) ?? custom.find((c) => c.evmChainId === evmChainId) ?? null;
}

export function hexToChainId(hex: unknown): number | null {
  if (typeof hex !== 'string' || !/^0x[0-9a-fA-F]+$/.test(hex)) return null;
  try {
    const n = Number(BigInt(hex));
    return Number.isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

export interface AddChainParams {
  chainId?: string;
  chainName?: string;
  rpcUrls?: string[];
  nativeCurrency?: { name?: string; symbol?: string; decimals?: number };
  blockExplorerUrls?: string[];
}

/**
 * Validate and normalize an EIP-3085 wallet_addEthereumChain payload into a ChainConfig.
 * Returns null if the payload is malformed or has no https RPC (we refuse plaintext RPCs).
 */
export function parseAddChainParams(p: AddChainParams | undefined): ChainConfig | null {
  if (!p) return null;
  const evmChainId = hexToChainId(p.chainId);
  if (evmChainId === null) return null;
  const rpcUrl = (p.rpcUrls ?? []).map((u) => String(u).trim()).find((u) => /^https:\/\//i.test(u));
  if (!rpcUrl) return null;
  const decimals = Number(p.nativeCurrency?.decimals);
  const explorer = (p.blockExplorerUrls ?? []).find((u) => /^https:\/\//i.test(String(u)));
  return {
    id: `evm-${evmChainId}`,
    name: (p.chainName && String(p.chainName).slice(0, 40)) || `Chain ${evmChainId}`,
    symbol: (p.nativeCurrency?.symbol && String(p.nativeCurrency.symbol).slice(0, 12)) || 'ETH',
    decimals: Number.isInteger(decimals) && decimals >= 0 && decimals <= 36 ? decimals : 18,
    coinType: 60,
    family: 'evm',
    evmChainId,
    rpcUrl,
    explorerUrl: explorer,
    isTestnet: false,
    color: '#627EEA',
  };
}
