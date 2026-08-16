// Phase-3 risk-scan response mapping (offline, synthetic Blockaid payloads).
// Run: npx tsx __tests__/risk-vectors.ts
import { mapBlockaidResponse, blockaidChainName } from '../src/core/riskMap';

let fail = 0;
function ok(name: string, cond: boolean, detail = '') {
  if (cond) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name} ${detail}`); }
}

const ACCOUNT = '0x1111111111111111111111111111111111111111';

console.log('blockaidChainName');
ok('1 -> ethereum', blockaidChainName(1) === 'ethereum');
ok('137 -> polygon', blockaidChainName(137) === 'polygon');
ok('unknown -> null', blockaidChainName(999999) === null);
ok('undefined -> null', blockaidChainName(undefined) === null);

console.log('mapBlockaidResponse — malicious with features + asset diffs');
const malicious = mapBlockaidResponse({
  validation: {
    result_type: 'Malicious',
    description: 'Interaction with a known drainer',
    features: [
      { type: 'Malicious', description: 'Unlimited approval to a flagged address' },
      { type: 'Info', description: 'noise' },
    ],
  },
  simulation: {
    assets_diffs: {
      [ACCOUNT]: {
        out: [{ asset: { type: 'ERC20', symbol: 'USDC', decimals: 6, address: '0xusdc' }, raw_value: '100000000' }],
        in: [{ asset: { type: 'NATIVE', symbol: 'ETH', decimals: 18 }, raw_value: '30000000000000000' }],
      },
    },
  },
}, ACCOUNT);
ok('level malicious', malicious.level === 'malicious');
ok('summary present', /drainer/.test(malicious.summary ?? ''));
ok('issue included (Malicious feature)', malicious.issues.some((i) => /Unlimited approval/.test(i)));
ok('Info feature excluded', !malicious.issues.some((i) => /noise/.test(i)));
ok('asset out USDC 100,000,000', malicious.assetChanges?.some((c) => c.direction === 'out' && c.symbol === 'USDC' && c.amount === 100000000n) === true);
ok('asset in native 0.03 ETH', malicious.assetChanges?.some((c) => c.direction === 'in' && c.kind === 'native' && c.amount === 30000000000000000n) === true);

console.log('mapBlockaidResponse — benign, no diffs');
const benign = mapBlockaidResponse({ validation: { result_type: 'Benign', features: [] } }, ACCOUNT);
ok('level benign', benign.level === 'benign');
ok('no issues', benign.issues.length === 0);
ok('no assetChanges', benign.assetChanges === undefined);

console.log('mapBlockaidResponse — unknown result type', );
ok('unknown maps to unknown', mapBlockaidResponse({ validation: { result_type: 'Weird' } }, ACCOUNT).level === 'unknown');

console.log(`\n${fail === 0 ? 'ALL RISK VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
