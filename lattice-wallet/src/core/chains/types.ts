// Chain-adapter seam. Every supported cryptocurrency implements ChainAdapter; the
// wallet shell, keystore, biometrics, and UI are chain-agnostic and reuse a single
// recovery phrase across all chains (each chain derives its own account).
import type { HistoryEntry } from '../rpc';

export type ChainFamily = 'xriq' | 'evm' | 'utxo' | 'solana';

export interface ChainConfig {
  id: string; // 'xriq', 'ethereum', 'polygon', 'bitcoin', 'solana', 'zcash-t'
  name: string;
  symbol: string;
  decimals: number;
  coinType: number; // SLIP-44
  family: ChainFamily;
  rpcUrl: string;
  explorerUrl?: string;
  isTestnet: boolean;
  evmChainId?: number; // EVM only
  color?: string;
}

export interface DerivedAccount {
  chainId: string;
  address: string;
  publicKeyHex: string;
  path: string;
}

export interface TransferRequest {
  to: string;
  amountBaseUnits: bigint;
  /** Optional explicit fee (base units). Chains that compute fees may ignore this. */
  feeBaseUnits?: bigint;
  memo?: string;
}

export interface FeeEstimate {
  feeBaseUnits: bigint;
  detail?: string;
}

export interface BroadcastResult {
  hash: string;
  raw?: string;
}

export interface ChainAdapter {
  readonly config: ChainConfig;

  /** Derive this chain's account from the wallet's recovery phrase. */
  deriveAccount(mnemonic: string): DerivedAccount;

  /** True if `address` is a well-formed address on this chain. */
  validateAddress(address: string): boolean;

  /** Confirmed balance in base units. */
  getBalance(address: string): Promise<bigint>;

  /** Recent activity (best-effort; may be empty when no indexer is configured). */
  getHistory(address: string): Promise<HistoryEntry[]>;

  /** Estimate the network fee for a transfer. */
  estimateFee(from: string, req: TransferRequest): Promise<FeeEstimate>;

  /**
   * Build, sign (locally, from the mnemonic), and broadcast a transfer. The mnemonic
   * is used transiently and never stored or transmitted by the adapter.
   */
  send(mnemonic: string, req: TransferRequest): Promise<BroadcastResult>;
}
