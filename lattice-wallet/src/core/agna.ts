// AGNA DEX integration — pluggable interface.
//
// AGNA is a decentralized exchange for cryptocurrencies, still under development and
// not yet present in this repo. Rather than fake swaps, Lattice codes against a clean
// interface: when the AGNA API ships, implement `AgnaClient` against it and the Swap
// screen goes live unchanged. Until then `provider` is null and the UI shows a
// "coming online" state — no trade is ever fabricated.
//
// Per the wallet's safety posture, executing real trades/transfers is out of scope for
// automated flows; swaps are prepared and require explicit on-device user confirmation.
import type { XriqRpc } from './rpc';

export interface TokenRef {
  symbol: string;
  assetId: string; // chain/asset identifier
  decimals: number;
}

export interface Quote {
  pair: string;
  inAmountBaseUnits: bigint;
  outAmountBaseUnits: bigint;
  priceImpactBps: number;
  feeBaseUnits: bigint;
  expiresAtMs: number;
  route: string[];
}

export interface SwapIntent {
  from: TokenRef;
  to: TokenRef;
  amountBaseUnits: bigint;
  ownerAddress: string;
  maxSlippageBps: number;
}

/** The contract a real AGNA backend must satisfy. */
export interface AgnaClient {
  listTokens(): Promise<TokenRef[]>;
  quote(intent: SwapIntent): Promise<Quote>;
  /**
   * Build the unsigned on-chain transaction(s) for a swap. The wallet signs locally
   * and submits — AGNA never receives keys. Returns a chain-native payload the XRIQ
   * signer can process once the swap tx shape is defined on-chain.
   */
  buildSwapTransaction(intent: SwapIntent, quote: Quote): Promise<unknown>;
}

export interface AgnaStatus {
  available: boolean;
  message: string;
}

/**
 * Resolve the active AGNA client. Returns null until a backend is configured.
 * Wire a concrete implementation here (or via Settings) when AGNA is available.
 */
export function resolveAgnaClient(_rpc: XriqRpc): AgnaClient | null {
  return null;
}

export function agnaStatus(client: AgnaClient | null): AgnaStatus {
  if (client) return { available: true, message: 'AGNA connected' };
  return {
    available: false,
    message: 'AGNA DEX is not yet available. Swap goes live when the exchange API ships.',
  };
}
