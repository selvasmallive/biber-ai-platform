// Minimal ABI encoding/decoding for ERC-20 — enough to read balances/metadata and build
// transfers, without a heavy ABI library. Function selectors are the first 4 bytes of
// keccak256(signature); they're pinned here and verified against keccak in
// __tests__/erc20-vectors.ts.
import { keccak_256 } from '@noble/hashes/sha3';
import { hex } from './xriq';

export const ERC20_SELECTORS = {
  balanceOf: '70a08231', // balanceOf(address)
  transfer: 'a9059cbb', // transfer(address,uint256)
  decimals: '313ce567', // decimals()
  symbol: '95d89b41', // symbol()
  name: '06fdde03', // name()
} as const;

/** The 4-byte selector for a Solidity function signature. */
export function selector(signature: string): string {
  return hex.toHex(keccak_256(new TextEncoder().encode(signature)).subarray(0, 4));
}

function padAddress(addr: string): string {
  const a = (addr.startsWith('0x') ? addr.slice(2) : addr).toLowerCase();
  if (a.length !== 40) throw new Error('bad address');
  return '0'.repeat(24) + a; // left-pad to 32 bytes
}

function padUint(value: bigint): string {
  if (value < 0n) throw new Error('negative');
  const h = value.toString(16);
  return '0'.repeat(64 - h.length) + h;
}

export function encodeBalanceOf(owner: string): string {
  return '0x' + ERC20_SELECTORS.balanceOf + padAddress(owner);
}

export function encodeTransfer(to: string, amount: bigint): string {
  return '0x' + ERC20_SELECTORS.transfer + padAddress(to) + padUint(amount);
}

export function encodeCall(sel: string): string {
  return '0x' + sel;
}

/** Decode a uint256 return value (hex, with or without 0x). */
export function decodeUint(data: string): bigint {
  const d = (data.startsWith('0x') ? data.slice(2) : data).trim();
  if (!d) return 0n;
  return BigInt('0x' + d.slice(0, 64));
}

/**
 * Decode a string return value. Handles both the ABI dynamic-string encoding
 * (offset || length || bytes) and legacy bytes32 tokens (fixed 32-byte, zero-padded).
 */
export function decodeString(data: string): string {
  const d = (data.startsWith('0x') ? data.slice(2) : data).trim();
  if (!d) return '';
  if (d.length === 64) {
    // Could be bytes32 (legacy) — strip trailing zeros and decode as ASCII.
    const bytes = hex.fromHex(d).filter((b) => b !== 0);
    return new TextDecoder().decode(bytes);
  }
  // Dynamic string: [0]=offset(32), then [offset]=length(32), then data.
  try {
    const len = Number(BigInt('0x' + d.slice(64, 128)));
    const strHex = d.slice(128, 128 + len * 2);
    return new TextDecoder().decode(hex.fromHex(strHex));
  } catch {
    return '';
  }
}
