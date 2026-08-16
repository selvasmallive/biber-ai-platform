// Transaction simulation — Phase 3 (OPT-IN, third-party risk API).
//
// PRIVACY: OFF by default. When enabled, the pending transaction and your address are sent
// to a third-party service (Blockaid) to check for known scams / malicious contracts and to
// get an asset-change preview without a trace-capable RPC. The user must explicitly enable it
// and supply THEIR OWN API key. This crosses the privacy line the rest of the wallet avoids.
//
// NOTE: unlike Phases 1–2, this adapter is coded to Blockaid's documented v0 EVM
// transaction-scan API but is NOT live-verified here (no key available). The response mapping
// is pure (riskMap.ts) and unit-tested against a synthetic payload; verify field names against
// the current Blockaid API before relying on it.
import * as SecureStore from 'expo-secure-store';
import { loadJson, saveJson } from './storage';
import { blockaidChainName, mapBlockaidResponse, type RiskResult } from './riskMap';
import type { ChainConfig } from './chains/types';

export type { RiskLevel, RiskResult } from './riskMap';
export { blockaidChainName } from './riskMap';

export interface RiskConfig {
  enabled: boolean;
  provider: 'blockaid';
}

const CONFIG_KEY = 'lattice.risk-config.v1';
const API_KEY_STORE = 'lattice.risk.apiKey.v1';
const KEY_OPTS = { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY };

export async function loadRiskConfig(): Promise<RiskConfig> {
  return loadJson<RiskConfig>(CONFIG_KEY, { enabled: false, provider: 'blockaid' });
}
export async function setRiskConfig(c: RiskConfig): Promise<void> {
  await saveJson(CONFIG_KEY, c);
}
export async function getRiskApiKey(): Promise<string | null> {
  return SecureStore.getItemAsync(API_KEY_STORE, KEY_OPTS);
}
export async function setRiskApiKey(key: string): Promise<void> {
  if (key.trim()) await SecureStore.setItemAsync(API_KEY_STORE, key.trim(), KEY_OPTS);
  else await SecureStore.deleteItemAsync(API_KEY_STORE, KEY_OPTS);
}
export async function hasRiskApiKey(): Promise<boolean> {
  return (await getRiskApiKey()) !== null;
}

async function scanBlockaid(apiKey: string, chain: string, account: string, tx: any): Promise<RiskResult> {
  const res = await fetch('https://api.blockaid.io/v0/evm/transaction/scan', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'X-API-KEY': apiKey },
    body: JSON.stringify({
      chain,
      account_address: account,
      metadata: { domain: 'https://lattice.app' },
      data: { from: tx.from, to: tx.to, value: tx.value ?? '0x0', data: tx.data ?? '0x' },
      options: ['validation', 'simulation'],
    }),
  });
  if (!res.ok) throw new Error(`Blockaid HTTP ${res.status}`);
  return mapBlockaidResponse(await res.json(), account);
}

/**
 * Run a risk scan if enabled + configured + supported. Returns null when off/unable (callers
 * skip it). Never throws — failures degrade to an 'unknown' result.
 */
export async function runRiskScan(
  config: RiskConfig,
  apiKey: string | null,
  chain: ChainConfig,
  tx: { from?: string; to?: string; value?: string; data?: string },
): Promise<RiskResult | null> {
  if (!config.enabled || !apiKey || chain.family !== 'evm' || !tx.from) return null;
  const chainName = blockaidChainName(chain.evmChainId);
  if (!chainName) return null;
  try {
    return await scanBlockaid(apiKey, chainName, tx.from, tx);
  } catch {
    return { level: 'unknown', issues: [], provider: 'blockaid', summary: 'Risk scan unavailable' };
  }
}
