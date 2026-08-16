// On-device store of custom EVM chains added via WalletConnect (wallet_addEthereumChain)
// or, later, manually. These extend the built-in registry for EVM send/switch/sign over
// WalletConnect. Stored locally only.
import { loadJson, saveJson } from './storage';
import type { ChainConfig } from './chains/types';

const KEY = 'lattice.custom-evm-chains.v1';

export async function loadCustomChains(): Promise<ChainConfig[]> {
  return loadJson<ChainConfig[]>(KEY, []);
}

export async function addCustomChain(chain: ChainConfig): Promise<ChainConfig[]> {
  const list = await loadCustomChains();
  const next = [chain, ...list.filter((c) => c.evmChainId !== chain.evmChainId)];
  await saveJson(KEY, next);
  return next;
}

export async function removeCustomChain(evmChainId: number): Promise<ChainConfig[]> {
  const list = await loadCustomChains();
  const next = list.filter((c) => c.evmChainId !== evmChainId);
  await saveJson(KEY, next);
  return next;
}
