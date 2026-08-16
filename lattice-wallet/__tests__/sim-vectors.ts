// Transaction-simulation conformance (offline): static calldata decode (Phase 1) and
// trace asset-delta parsing (Phase 2). Run: npx tsx __tests__/sim-vectors.ts
import { decodeCalldata, parseTraceAssetDeltas, TRANSFER_TOPIC } from '../src/core/simulate';
import { keccak_256 } from '@noble/hashes/sha3';
import { hex } from '../src/core/xriq';

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

console.log('Phase 2 — parseTraceAssetDeltas (native + ERC-20 + ERC-721)');
ok('TRANSFER_TOPIC = keccak(Transfer(address,address,uint256))',
  TRANSFER_TOPIC === '0x' + hex.toHex(keccak_256(new TextEncoder().encode('Transfer(address,address,uint256)'))));

const USER = '0x1111111111111111111111111111111111111111';
const ROUTER = '0x2222222222222222222222222222222222222222';
const USDC = '0x3333333333333333333333333333333333333333';
const NFT = '0x4444444444444444444444444444444444444444';
const topicAddr = (a: string) => '0x' + '0'.repeat(24) + a.slice(2);
const word = (n: bigint) => '0x' + n.toString(16).padStart(64, '0');

const trace = {
  from: USER, to: ROUTER, value: word(1000000000000000000n), // 1 ETH in
  calls: [
    { from: ROUTER, to: USER, value: word(500000000000000000n), calls: [], logs: [] }, // 0.5 ETH back
  ],
  logs: [
    { address: USDC, topics: [TRANSFER_TOPIC, topicAddr(ROUTER), topicAddr(USER)], data: word(100000000n) }, // +100 USDC (6dp)
    { address: NFT, topics: [TRANSFER_TOPIC, topicAddr(ROUTER), topicAddr(USER), word(7n)] }, // NFT #7 in
    { address: USDC, topics: [TRANSFER_TOPIC, topicAddr(USER), topicAddr(ROUTER)], data: word(4000000n) }, // -4 USDC out
  ],
};
const d = parseTraceAssetDeltas(trace, USER);
ok('native net = -0.5 ETH (out)', d.native === -500000000000000000n, String(d.native));
ok('USDC net = +96,000,000 (in)', d.tokens[USDC.toLowerCase()] === 96000000n, String(d.tokens[USDC.toLowerCase()]));
ok('NFT #7 received', d.nfts.length === 1 && d.nfts[0].id === 7n && d.nfts[0].dir === 'in');
// From the router's perspective the diffs invert: native +0.5 ETH, USDC -96,000,000.
const dr = parseTraceAssetDeltas(trace, ROUTER);
ok('router native = +0.5 ETH', dr.native === 500000000000000000n, String(dr.native));
ok('router USDC = -96,000,000', dr.tokens[USDC.toLowerCase()] === -96000000n, String(dr.tokens[USDC.toLowerCase()]));

console.log(`\n${fail === 0 ? 'ALL SIMULATION VECTORS MATCH ✓' : `${fail} FAILED`}`);
if (fail > 0) process.exit(1);
