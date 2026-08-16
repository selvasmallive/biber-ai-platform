// WalletConnect chain-management helpers. Run: npx tsx __tests__/wc-chains-vectors.ts
import { parseAddChainParams, hexToChainId, resolveEvmConfig } from '../src/core/chains/wcChains';
import { getChainConfig } from '../src/core/chains/registry';
import type { ChainConfig } from '../src/core/chains/types';

let fail = 0;
function ok(name: string, cond: boolean, detail = '') {
  if (cond) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name} ${detail}`); }
}

console.log('hexToChainId');
ok('0x89 -> 137', hexToChainId('0x89') === 137);
ok('0x1 -> 1', hexToChainId('0x1') === 1);
ok('decimal string rejected', hexToChainId('137') === null);
ok('non-string rejected', hexToChainId(137 as any) === null);

console.log('parseAddChainParams');
const good = parseAddChainParams({
  chainId: '0xa4b1',
  chainName: 'Arbitrum One',
  rpcUrls: ['http://insecure', 'https://arb1.example/rpc'],
  nativeCurrency: { symbol: 'ETH', decimals: 18 },
  blockExplorerUrls: ['https://arbiscan.io'],
});
ok('valid payload parses', !!good);
ok('picks the https RPC (not http)', good?.rpcUrl === 'https://arb1.example/rpc');
ok('chainId 42161', good?.evmChainId === 42161);
ok('family evm', good?.family === 'evm');
ok('explorer captured', good?.explorerUrl === 'https://arbiscan.io');

ok('no https RPC -> null', parseAddChainParams({ chainId: '0x64', rpcUrls: ['http://x'] }) === null);
ok('bad chainId -> null', parseAddChainParams({ chainId: 'nope', rpcUrls: ['https://x'] }) === null);
ok('missing -> null', parseAddChainParams(undefined) === null);

console.log('resolveEvmConfig');
const custom: ChainConfig[] = [good!];
ok('resolves built-in (ethereum=1)', resolveEvmConfig(1, [])?.id === getChainConfig('ethereum').id);
ok('resolves custom (42161)', resolveEvmConfig(42161, custom)?.evmChainId === 42161);
ok('unknown -> null', resolveEvmConfig(999999, custom) === null);

console.log(`\n${fail === 0 ? 'ALL WC-CHAIN VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
