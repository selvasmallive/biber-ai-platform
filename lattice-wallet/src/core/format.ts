import { NATIVE_DECIMALS, NATIVE_SYMBOL } from './config';

/** Format integer base units as a human amount using the native decimals. */
export function formatUnits(baseUnits: bigint, decimals = NATIVE_DECIMALS): string {
  if (decimals === 0) return groupDigits(baseUnits.toString());
  const neg = baseUnits < 0n;
  const abs = neg ? -baseUnits : baseUnits;
  const s = abs.toString().padStart(decimals + 1, '0');
  const whole = s.slice(0, s.length - decimals);
  const frac = s.slice(s.length - decimals).replace(/0+$/, '');
  const out = frac ? `${groupDigits(whole)}.${frac}` : groupDigits(whole);
  return neg ? `-${out}` : out;
}

export function formatAmount(baseUnits: bigint): string {
  return `${formatUnits(baseUnits)} ${NATIVE_SYMBOL}`;
}

/** Parse a human amount string into integer base units. Throws on malformed input. */
export function parseUnits(input: string, decimals = NATIVE_DECIMALS): bigint {
  const trimmed = input.trim();
  if (!trimmed) throw new Error('Enter an amount');
  if (decimals === 0) {
    if (!/^\d+$/.test(trimmed)) throw new Error('Amount must be a whole number');
    return BigInt(trimmed);
  }
  if (!/^\d+(\.\d+)?$/.test(trimmed)) throw new Error('Invalid amount');
  const [whole, frac = ''] = trimmed.split('.');
  if (frac.length > decimals) throw new Error(`Max ${decimals} decimal places`);
  return BigInt(whole + frac.padEnd(decimals, '0'));
}

function groupDigits(s: string): string {
  return s.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}
