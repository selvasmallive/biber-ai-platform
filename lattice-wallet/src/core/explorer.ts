// Block-explorer deep links — the privacy-first way to view full history: the user opens
// the explorer themselves in a browser, so the wallet never queries an indexer with the
// user's address behind their back.
import type { ChainConfig } from './chains/types';

export function explorerTxUrl(chain: ChainConfig, txid: string): string | null {
  if (!chain.explorerUrl) return null;
  const base = chain.explorerUrl.replace(/\/$/, '');
  switch (chain.family) {
    case 'evm':
      return `${base}/tx/0x${txid.replace(/^0x/, '')}`;
    case 'bitcoin':
      return `${base}/tx/${txid}`;
    case 'solana':
      return `${base}/tx/${txid}`;
    case 'zcash-t':
      return `${base}/transaction/${txid}`;
    case 'xriq':
      return `${base}/tx/${txid}`;
    default:
      return `${base}/tx/${txid}`;
  }
}

export function explorerAddressUrl(chain: ChainConfig, address: string): string | null {
  if (!chain.explorerUrl) return null;
  const base = chain.explorerUrl.replace(/\/$/, '');
  switch (chain.family) {
    case 'evm':
      return `${base}/address/${address}`;
    case 'zcash-t':
      return `${base}/address/${address}`;
    case 'solana':
      return `${base}/address/${address}`;
    default:
      return `${base}/address/${address}`;
  }
}
