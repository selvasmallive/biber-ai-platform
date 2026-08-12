// Supported-chain registry. One recovery phrase derives an account on each chain.
//
// Adding a chain = add a ChainConfig here and map it to an adapter in `makeAdapter`.
// EVM chains share one adapter, parameterized by evmChainId + rpcUrl.
import type { ChainAdapter, ChainConfig } from './types';
import { EvmAdapter } from './evm';
import { XriqAdapter } from './xriqAdapter';
import { BitcoinAdapter } from './bitcoin';
import { SolanaAdapter } from './solana';
import { ZcashTransparentAdapter } from './zcash';

export const CHAINS: ChainConfig[] = [
  {
    id: 'xriq',
    name: 'XRIQ Devnet',
    symbol: 'XRIQ',
    decimals: 0,
    coinType: 1,
    family: 'xriq',
    rpcUrl: 'http://127.0.0.1:8080',
    isTestnet: true,
    color: '#6E8BFF',
  },
  {
    id: 'ethereum',
    name: 'Ethereum',
    symbol: 'ETH',
    decimals: 18,
    coinType: 60,
    family: 'evm',
    evmChainId: 1,
    rpcUrl: 'https://ethereum-rpc.publicnode.com',
    explorerUrl: 'https://etherscan.io',
    isTestnet: false,
    color: '#627EEA',
  },
  {
    id: 'polygon',
    name: 'Polygon',
    symbol: 'POL',
    decimals: 18,
    coinType: 60,
    family: 'evm',
    evmChainId: 137,
    rpcUrl: 'https://polygon-bor-rpc.publicnode.com',
    explorerUrl: 'https://polygonscan.com',
    isTestnet: false,
    color: '#8247E5',
  },
  {
    id: 'base',
    name: 'Base',
    symbol: 'ETH',
    decimals: 18,
    coinType: 60,
    family: 'evm',
    evmChainId: 8453,
    rpcUrl: 'https://base-rpc.publicnode.com',
    explorerUrl: 'https://basescan.org',
    isTestnet: false,
    color: '#0052FF',
  },
  {
    id: 'sepolia',
    name: 'Ethereum Sepolia (testnet)',
    symbol: 'ETH',
    decimals: 18,
    coinType: 60,
    family: 'evm',
    evmChainId: 11155111,
    rpcUrl: 'https://ethereum-sepolia-rpc.publicnode.com',
    explorerUrl: 'https://sepolia.etherscan.io',
    isTestnet: true,
    color: '#627EEA',
  },
  {
    id: 'bitcoin',
    name: 'Bitcoin',
    symbol: 'BTC',
    decimals: 8,
    coinType: 0,
    family: 'bitcoin',
    rpcUrl: 'https://blockstream.info/api',
    explorerUrl: 'https://blockstream.info',
    isTestnet: false,
    color: '#F7931A',
  },
  {
    id: 'solana',
    name: 'Solana',
    symbol: 'SOL',
    decimals: 9,
    coinType: 501,
    family: 'solana',
    rpcUrl: 'https://api.mainnet-beta.solana.com',
    explorerUrl: 'https://explorer.solana.com',
    isTestnet: false,
    color: '#14F195',
  },
  {
    id: 'zcash-t',
    name: 'Zcash (transparent)',
    symbol: 'ZEC',
    decimals: 8,
    coinType: 133,
    family: 'zcash-t',
    rpcUrl: 'https://zec.explorer.example/api', // set to a Zcash Esplora-compatible endpoint
    explorerUrl: 'https://blockchair.com/zcash',
    isTestnet: false,
    color: '#ECB244',
  },
];

export function getChainConfig(id: string): ChainConfig {
  const c = CHAINS.find((x) => x.id === id);
  if (!c) throw new Error(`unknown chain: ${id}`);
  return c;
}

export function makeAdapter(config: ChainConfig): ChainAdapter {
  switch (config.family) {
    case 'xriq':
      return new XriqAdapter(config);
    case 'evm':
      return new EvmAdapter(config);
    case 'bitcoin':
      return new BitcoinAdapter(config);
    case 'solana':
      return new SolanaAdapter(config);
    case 'zcash-t':
      return new ZcashTransparentAdapter(config);
    default:
      throw new Error(`no adapter for family: ${config.family}`);
  }
}

export const DEFAULT_CHAIN_ID = 'xriq';
