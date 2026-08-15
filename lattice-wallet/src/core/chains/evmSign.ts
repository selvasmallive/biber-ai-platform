// EVM message + typed-data signing for WalletConnect requests (personal_sign, eth_sign,
// eth_signTypedData_v4). EIP-191 and EIP-712 hashing are verified against ethers in
// __tests__/evm-sign-vectors.ts. Signing itself is standard secp256k1 (low-S), on-device.
import { keccak_256 } from '@noble/hashes/sha3';
import { secp256k1 } from '@noble/curves/secp256k1';
import { hex } from '../xriq';

const enc = new TextEncoder();

function concatBytes(...parts: Uint8Array[]): Uint8Array {
  let n = 0;
  for (const p of parts) n += p.length;
  const out = new Uint8Array(n);
  let o = 0;
  for (const p of parts) { out.set(p, o); o += p.length; }
  return out;
}

function pad32(value: bigint): Uint8Array {
  const out = new Uint8Array(32);
  let x = BigInt.asUintN(256, value);
  for (let i = 31; i >= 0; i--) { out[i] = Number(x & 0xffn); x >>= 8n; }
  return out;
}

function bytesFromMessage(message: string | Uint8Array): Uint8Array {
  if (typeof message !== 'string') return message;
  // A 0x-hex string is treated as raw bytes (how dApps send personal_sign payloads).
  if (/^0x[0-9a-fA-F]*$/.test(message)) return hex.fromHex(message.slice(2));
  return enc.encode(message);
}

/** EIP-191 personal-message digest: keccak256("\x19Ethereum Signed Message:\n"+len+msg). */
export function hashPersonalMessage(message: string | Uint8Array): Uint8Array {
  const msg = bytesFromMessage(message);
  const prefix = enc.encode(`\x19Ethereum Signed Message:\n${msg.length}`);
  return keccak_256(concatBytes(prefix, msg));
}

/** Sign a 32-byte digest; returns 65-byte r||s||v hex with v in {27,28}. */
export function signDigest(digest: Uint8Array, privateKey: Uint8Array): string {
  const sig = secp256k1.sign(digest, privateKey); // low-S by default
  const v = 27 + sig.recovery;
  return '0x' + hex.toHex(concatBytes(pad32(sig.r), pad32(sig.s), new Uint8Array([v])));
}

export function personalSign(message: string | Uint8Array, privateKey: Uint8Array): string {
  return signDigest(hashPersonalMessage(message), privateKey);
}

// ---------------------------------------------------------------------------
// EIP-712 typed data (v4).
// ---------------------------------------------------------------------------
export interface TypedField {
  name: string;
  type: string;
}
export interface TypedData {
  types: Record<string, TypedField[]>;
  primaryType: string;
  domain: Record<string, any>;
  message: Record<string, any>;
}

function dependencies(primaryType: string, types: Record<string, TypedField[]>, found: Set<string> = new Set()): string[] {
  if (found.has(primaryType) || !types[primaryType]) return [];
  found.add(primaryType);
  let deps: string[] = [primaryType];
  for (const field of types[primaryType]) {
    const base = field.type.replace(/\[.*\]$/, '');
    if (types[base]) deps = deps.concat(dependencies(base, types, found));
  }
  return deps;
}

function encodeType(primaryType: string, types: Record<string, TypedField[]>): string {
  const deps = dependencies(primaryType, types).filter((d) => d !== primaryType).sort();
  const ordered = [primaryType, ...deps];
  return ordered.map((t) => `${t}(${types[t].map((f) => `${f.type} ${f.name}`).join(',')})`).join('');
}

function typeHash(primaryType: string, types: Record<string, TypedField[]>): Uint8Array {
  return keccak_256(enc.encode(encodeType(primaryType, types)));
}

function encodeField(type: string, value: any, types: Record<string, TypedField[]>): Uint8Array {
  if (types[type]) return keccak_256(encodeData(type, value, types)); // struct
  const arrayMatch = type.match(/^(.*)\[(\d*)\]$/);
  if (arrayMatch) {
    const base = arrayMatch[1];
    const items = (value as any[]).map((v) => encodeField(base, v, types));
    return keccak_256(concatBytes(...items));
  }
  if (type === 'string') return keccak_256(enc.encode(String(value)));
  if (type === 'bytes') return keccak_256(hex.fromHex(String(value).replace(/^0x/, '')));
  if (type === 'bool') return pad32(value ? 1n : 0n);
  if (type === 'address') return pad32(BigInt(value));
  if (/^bytes([0-9]+)$/.test(type)) {
    const raw = hex.fromHex(String(value).replace(/^0x/, ''));
    const out = new Uint8Array(32);
    out.set(raw.subarray(0, 32), 0); // right-padded
    return out;
  }
  if (/^(u?int)([0-9]*)$/.test(type)) return pad32(BigInt(value));
  throw new Error(`unsupported EIP-712 type: ${type}`);
}

function encodeData(primaryType: string, data: Record<string, any>, types: Record<string, TypedField[]>): Uint8Array {
  const parts: Uint8Array[] = [typeHash(primaryType, types)];
  for (const field of types[primaryType]) parts.push(encodeField(field.type, data[field.name], types));
  return concatBytes(...parts);
}

export function hashStruct(primaryType: string, data: Record<string, any>, types: Record<string, TypedField[]>): Uint8Array {
  return keccak_256(encodeData(primaryType, data, types));
}

/** EIP-712 v4 signing digest: keccak256(0x1901 || domainSeparator || hashStruct(message)). */
export function hashTypedDataV4(typed: TypedData): Uint8Array {
  const domainSeparator = hashStruct('EIP712Domain', typed.domain, typed.types);
  const messageHash = hashStruct(typed.primaryType, typed.message, typed.types);
  return keccak_256(concatBytes(new Uint8Array([0x19, 0x01]), domainSeparator, messageHash));
}

export function signTypedDataV4(typed: TypedData, privateKey: Uint8Array): string {
  return signDigest(hashTypedDataV4(typed), privateKey);
}
