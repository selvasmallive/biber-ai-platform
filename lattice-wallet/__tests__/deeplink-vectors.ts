// Deep-link WalletConnect URI extraction. Run: npx tsx __tests__/deeplink-vectors.ts
import { extractWcUri } from '../src/core/deeplink';

let fail = 0;
function eq(name: string, got: string | null, want: string | null) {
  if (got === want) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name}\n    got  ${got}\n    want ${want}`); }
}

const WC = 'wc:7f6e...@2?relay-protocol=irn&symKey=abc';

eq('raw wc: uri', extractWcUri(WC), WC);
eq('lattice://wc?uri= (encoded)', extractWcUri(`lattice://wc?uri=${encodeURIComponent(WC)}`), WC);
eq('lattice://wc?uri= with extra params', extractWcUri(`lattice://wc?foo=1&uri=${encodeURIComponent(WC)}&bar=2`), WC);
eq('https universal link', extractWcUri(`https://lattice.app/wc?uri=${encodeURIComponent(WC)}`), WC);
eq('non-wc link returns null', extractWcUri('https://example.com/page?x=1'), null);
eq('empty returns null', extractWcUri(''), null);
eq('whitespace-trimmed raw uri', extractWcUri(`  ${WC}  `), WC);

console.log(`\n${fail === 0 ? 'ALL DEEP-LINK VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
