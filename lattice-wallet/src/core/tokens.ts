// ERC-20 token registry — PRIVACY-FIRST: tokens are added by the user by contract
// address (optionally auto-filling metadata from the chain), never discovered by a
// third-party token-tracking service. Balances are read from the user's own RPC.
import { loadJson, saveJson } from './storage';

export interface Token {
  chainId: string;
  address: string; // contract address (lowercased)
  symbol: string;
  name: string;
  decimals: number;
}

const KEY = 'lattice.tokens.v1';

export async function loadTokens(): Promise<Token[]> {
  return loadJson<Token[]>(KEY, []);
}

export async function tokensForChain(chainId: string): Promise<Token[]> {
  return (await loadTokens()).filter((t) => t.chainId === chainId);
}

export async function addToken(t: Token): Promise<Token[]> {
  const list = await loadTokens();
  const addr = t.address.toLowerCase();
  const next = [{ ...t, address: addr }, ...list.filter((x) => !(x.chainId === t.chainId && x.address.toLowerCase() === addr))];
  await saveJson(KEY, next);
  return next;
}

export async function removeToken(chainId: string, address: string): Promise<Token[]> {
  const list = await loadTokens();
  const next = list.filter((t) => !(t.chainId === chainId && t.address.toLowerCase() === address.toLowerCase()));
  await saveJson(KEY, next);
  return next;
}
