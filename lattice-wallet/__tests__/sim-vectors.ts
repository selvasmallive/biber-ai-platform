// Transaction-simulation static decode conformance (offline).
// Run: npx tsx __tests__/sim-vectors.ts
import { decodeCalldata } from '../src/core/simulate';

let fail = 0;
function ok(name: string, cond: boolean, detail = '') {
  if (cond) console.log(`  ok   ${name}`);
  else { fail++; console.error(`  FAIL ${name} ${detail}`); }
}

const SPENDER = '00000000000000000000000000000000000000000000000000000000000000aa';
const MAX = 'f'.repeat(64);
const AMT = '0000000000000000000000000000000000000000000000000000000000000064'; // 100

console.log('decodeCalldata — approve');
const unlimited = decodeCalldata('0x095ea7b3' + SPENDER + MAX);
ok('approve unlimited flagged', unlimited.approvals[0]?.unlimited === true);
ok('approve warning mentions UNLIMITED', unlimited.warnings.some((w) => /UNLIMITED/.test(w)));
ok('approve kind erc20-allowance', unlimited.approvals[0]?.kind === 'erc20-allowance');

const limited = decodeCalldata('0x095ea7b3' + SPENDER + AMT);
ok('approve limited not unlimited', limited.approvals[0]?.unlimited === false);
ok('approve limited amount = 100', limited.approvals[0]?.amount === 100n);

console.log('decodeCalldata — setApprovalForAll');
const sa = decodeCalldata('0xa22cb465' + SPENDER + '0'.repeat(63) + '1');
ok('setApprovalForAll(true) => nft-operator approval', sa.approvals[0]?.kind === 'nft-operator');
ok('setApprovalForAll warns about ALL NFTs', sa.warnings.some((w) => /ALL your NFTs/.test(w)));

console.log('decodeCalldata — transfer & unknown & empty');
const tr = decodeCalldata('0xa9059cbb' + SPENDER + AMT);
ok('transfer decoded', tr.lines.some((l) => /Function: transfer/.test(l)));
ok('transfer has no approvals', tr.approvals.length === 0);

const unknown = decodeCalldata('0xdeadbeef' + SPENDER);
ok('unknown call warns', unknown.warnings.some((w) => /Unknown contract call/.test(w)));

const empty = decodeCalldata('0x');
ok('empty calldata => nothing', empty.lines.length === 0 && empty.warnings.length === 0);

console.log(`\n${fail === 0 ? 'ALL SIMULATION DECODE VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
