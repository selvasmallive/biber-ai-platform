// ERC-20 ABI + ENS namehash conformance. Run: npx tsx __tests__/erc20-vectors.ts
import { selector, ERC20_SELECTORS, encodeTransfer, encodeBalanceOf, decodeUint, decodeString } from '../src/core/evmAbi';
import { namehash } from '../src/core/ens';
import { hex } from '../src/core/xriq';

let fail = 0;
function eq(name: string, got: string, want: string) {
  if (got === want) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name}\n    got  ${got}\n    want ${want}`); }
}

console.log('ERC-20 function selectors (first 4 bytes of keccak256(sig))');
eq('transfer(address,uint256)', selector('transfer(address,uint256)'), ERC20_SELECTORS.transfer);
eq('balanceOf(address)', selector('balanceOf(address)'), ERC20_SELECTORS.balanceOf);
eq('decimals()', selector('decimals()'), ERC20_SELECTORS.decimals);
eq('symbol()', selector('symbol()'), ERC20_SELECTORS.symbol);

console.log('ERC-20 call encoding');
// transfer 1.0 token (1e18) to 0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed
eq(
  'encodeTransfer',
  encodeTransfer('0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed', 1_000_000_000_000_000_000n),
  '0xa9059cbb0000000000000000000000005aaeb6053f3e94c9b9a09f33669435e7ef1beaed0000000000000000000000000000000000000000000000000de0b6b3a7640000',
);
eq(
  'encodeBalanceOf',
  encodeBalanceOf('0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed'),
  '0x70a082310000000000000000000000005aaeb6053f3e94c9b9a09f33669435e7ef1beaed',
);

console.log('ERC-20 return decoding');
eq('decodeUint (12345)', decodeUint('0x0000000000000000000000000000000000000000000000000000000000003039').toString(), '12345');
// dynamic string "USDC": offset 0x20, length 4, data "USDC"
eq(
  'decodeString (dynamic)',
  decodeString('0x00000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000004555344430000000000000000000000000000000000000000000000000000000000'),
  'USDC',
);
// legacy bytes32 "DAI"
eq('decodeString (bytes32)', decodeString('0x4441490000000000000000000000000000000000000000000000000000000000'), 'DAI');

console.log('ENS namehash (EIP-137 golden vectors)');
eq('namehash("")', hex.toHex(namehash('')), '0000000000000000000000000000000000000000000000000000000000000000');
eq('namehash("eth")', hex.toHex(namehash('eth')), '93cdeb708b7545dc668eb9280176169d1c33cfd8ed6f04690a0bcc88a93fc4ae');
eq('namehash("foo.eth")', hex.toHex(namehash('foo.eth')), 'de9b09fd7c5f901e23a3f19fecc54828e9c848539801e86591bd9801b019f84f');

console.log(`\n${fail === 0 ? 'ALL ERC-20 / ENS VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
