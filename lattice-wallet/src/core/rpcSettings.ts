// User-overridable RPC endpoints — self-sovereignty and privacy: point any chain at your
// own node so no third party sees your queries. Overrides are stored on-device and
// merged over the registry defaults.
import { loadJson, saveJson } from './storage';
import { getChainConfig } from './chains/registry';
import type { ChainConfig } from './chains/types';

const KEY = 'lattice.rpc-overrides.v1';

export type RpcOverrides = Record<string, string>;

export async function loadRpcOverrides(): Promise<RpcOverrides> {
  return loadJson<RpcOverrides>(KEY, {});
}

export async function setRpcOverride(chainId: string, rpcUrl: string): Promise<RpcOverrides> {
  const cur = await loadRpcOverrides();
  const next = { ...cur };
  if (rpcUrl.trim()) next[chainId] = rpcUrl.trim();
  else delete next[chainId];
  await saveJson(KEY, next);
  return next;
}

/** Registry config with any user RPC override applied. */
export function effectiveConfig(chainId: string, overrides: RpcOverrides): ChainConfig {
  const base = getChainConfig(chainId);
  const rpcUrl = overrides[chainId];
  return rpcUrl ? { ...base, rpcUrl } : base;
}
