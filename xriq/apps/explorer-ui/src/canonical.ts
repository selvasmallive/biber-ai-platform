// Client-side reproduction of XRIQ's canonical `transaction_signing_hash`.
//
// This lets the non-custodial wallet verify that the signing hash returned by the
// server's prepare endpoint actually corresponds to the transaction fields the user
// entered — so the wallet signs what it verified, not server-dictated bytes. It must
// match `xriq-crypto::transaction_signing_hash` byte-for-byte; a golden cross-check
// (see scripts/check-canonical-signing-hash.mjs) verifies it against the Rust output.
//
// Only handles the transfer shape the wallet produces: no memo, an explicit
// expiry, and the ed25519 signer's public key folded into the signed body.
import { sha256 } from "@noble/hashes/sha2.js";

const DOMAIN_TRANSACTION_SIGNING = "xriq:v1:transaction:signing";

function utf8(value: string): Uint8Array {
  return new TextEncoder().encode(value);
}

function hexToBytes(hex: string): Uint8Array {
  if (hex.length % 2 !== 0) {
    throw new Error("hex string must have an even length");
  }
  const out = new Uint8Array(hex.length / 2);
  for (let index = 0; index < out.length; index += 1) {
    const byte = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16);
    if (Number.isNaN(byte)) {
      throw new Error("hex string contains a non-hex character");
    }
    out[index] = byte;
  }
  return out;
}

function bytesToHex(bytes: Uint8Array): string {
  let out = "";
  for (const byte of bytes) {
    out += byte.toString(16).padStart(2, "0");
  }
  return out;
}

// Little-endian encoding of an unsigned integer into `byteLength` bytes — matches
// Rust's `u16/u32/u64/u128::to_le_bytes`.
function intLe(value: bigint, byteLength: number): Uint8Array {
  if (value < 0n) {
    throw new Error("value must be non-negative");
  }
  const out = new Uint8Array(byteLength);
  let remaining = value;
  for (let index = 0; index < byteLength; index += 1) {
    out[index] = Number(remaining & 0xffn);
    remaining >>= 8n;
  }
  if (remaining !== 0n) {
    throw new Error("value does not fit in the given width");
  }
  return out;
}

// Length-prefixed bytes: u32 LE length followed by the bytes (Rust `encode_bytes`).
function encodeBytes(bytes: Uint8Array): Uint8Array {
  const length = intLe(BigInt(bytes.length), 4);
  const out = new Uint8Array(4 + bytes.length);
  out.set(length, 0);
  out.set(bytes, 4);
  return out;
}

function encodeString(value: string): Uint8Array {
  return encodeBytes(utf8(value));
}

function concat(parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

export interface CanonicalTransactionFields {
  version: string;
  chain_id: string;
  from_address: string;
  to_address: string;
  amount_base_units: string;
  fee_base_units: string;
  nonce: string;
  expires_at_height: string;
}

/**
 * Compute the canonical `transaction_signing_hash` (lowercase hex) for the given
 * transfer fields and the signer's public key. Mirrors
 * `xriq-crypto::encode_transaction_without_signature` preceded by the domain
 * preamble, then SHA-256.
 */
export function transactionSigningHashHex(
  fields: CanonicalTransactionFields,
  publicKeyHex: string,
): string {
  const message = concat([
    encodeBytes(utf8(DOMAIN_TRANSACTION_SIGNING)),
    intLe(BigInt(fields.version), 2),
    encodeString(fields.chain_id),
    encodeString(fields.from_address),
    encodeString(fields.to_address),
    intLe(BigInt(fields.amount_base_units), 16),
    intLe(BigInt(fields.fee_base_units), 16),
    intLe(BigInt(fields.nonce), 8),
    new Uint8Array([0]), // memo_hash: None
    new Uint8Array([1]), // expires_at_height: Some
    intLe(BigInt(fields.expires_at_height), 8),
    encodeBytes(hexToBytes(publicKeyHex)),
  ]);
  return bytesToHex(sha256(message));
}
