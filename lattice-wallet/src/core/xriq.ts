// XRIQ protocol client — canonical encoding, address derivation, and transaction
// signing that reproduce the Rust chain BYTE-FOR-BYTE.
//
// Conformance is pinned to goldens taken directly from `xriq/crates/xriq-crypto`:
//   - ed25519_address([0u8;32]) == "xriqdev1397e043c1939ff954726c0f3657a7a5093b33b89"
//   - all integers are little-endian; encode_bytes(x) = u32_le(len) || x
//   - a Transfer action contributes ZERO trailing bytes (see TxAction docs).
//
// The wallet is NON-CUSTODIAL: keys are generated and transactions signed on-device;
// only the public key + signature + tx fields are ever sent to a node.

import { sha256 } from '@noble/hashes/sha256';
import { hmac } from '@noble/hashes/hmac';
import { sha512 } from '@noble/hashes/sha512';
import { ed25519 } from '@noble/curves/ed25519';
import { mnemonicToSeedSync, generateMnemonic, validateMnemonic } from '@scure/bip39';
import { wordlist } from '@scure/bip39/wordlists/english';

// ---------------------------------------------------------------------------
// Domain tags — must match xriq-crypto exactly.
// ---------------------------------------------------------------------------
const DOMAIN_ED25519_ADDRESS = utf8('xriq:v1:ed25519-address');
const DOMAIN_TRANSACTION_SIGNING = utf8('xriq:v1:transaction:signing');
const DOMAIN_TRANSACTION_HASH = utf8('xriq:v1:transaction:hash');

const ADDRESS_PREFIX = 'xriqdev1';
const ADDRESS_PAYLOAD_BYTES = 20;

/** XRIQ signature algorithm ids (xriq-crypto `SignatureAlgorithm::id`). */
export const SignatureAlgorithmId = {
  TestOnly: 0,
  Ed25519: 1,
  Secp256k1: 2,
  /** Reserved on-chain for the hybrid post-quantum scheme (not yet chain-verified). */
  HybridPostQuantumReserved: 250,
} as const;

export const SUPPORTED_TX_VERSION = 1;

// ---------------------------------------------------------------------------
// Canonical byte encoders (little-endian, length-prefixed) — mirror of
// xriq-crypto's private encode_* helpers.
// ---------------------------------------------------------------------------
// Dependency-free UTF-8 encoder — avoids relying on a global TextEncoder, which is
// not guaranteed in the React Native / Hermes runtime.
function utf8(s: string): Uint8Array {
  const out: number[] = [];
  for (let i = 0; i < s.length; i++) {
    let code = s.charCodeAt(i);
    if (code >= 0xd800 && code <= 0xdbff && i + 1 < s.length) {
      const next = s.charCodeAt(i + 1);
      if (next >= 0xdc00 && next <= 0xdfff) {
        code = 0x10000 + ((code - 0xd800) << 10) + (next - 0xdc00);
        i++;
      }
    }
    if (code < 0x80) out.push(code);
    else if (code < 0x800) out.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f));
    else if (code < 0x10000)
      out.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f));
    else
      out.push(
        0xf0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3f),
        0x80 | ((code >> 6) & 0x3f),
        0x80 | (code & 0x3f),
      );
  }
  return new Uint8Array(out);
}

function concat(...parts: Uint8Array[]): Uint8Array {
  const total = parts.reduce((n, p) => n + p.length, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}

function u16le(v: number): Uint8Array {
  const b = new Uint8Array(2);
  new DataView(b.buffer).setUint16(0, v, true);
  return b;
}

function u32le(v: number): Uint8Array {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, v >>> 0, true);
  return b;
}

function u64le(v: bigint): Uint8Array {
  const b = new Uint8Array(8);
  new DataView(b.buffer).setBigUint64(0, BigInt.asUintN(64, v), true);
  return b;
}

function u128le(v: bigint): Uint8Array {
  const b = new Uint8Array(16);
  let x = BigInt.asUintN(128, v);
  for (let i = 0; i < 16; i++) {
    b[i] = Number(x & 0xffn);
    x >>= 8n;
  }
  return b;
}

/** encode_bytes: u32_le(len) || bytes. */
function encodeBytes(bytes: Uint8Array): Uint8Array {
  return concat(u32le(bytes.length), bytes);
}

/** encode_string: encode_bytes(utf8(s)). */
function encodeString(s: string): Uint8Array {
  return encodeBytes(utf8(s));
}

/** canonical_preamble(domain): encode_bytes(domain). */
function preamble(domain: Uint8Array): Uint8Array {
  return encodeBytes(domain);
}

function toHex(bytes: Uint8Array): string {
  let s = '';
  for (const b of bytes) s += b.toString(16).padStart(2, '0');
  return s;
}

function fromHex(hex: string): Uint8Array {
  const clean = hex.startsWith('0x') ? hex.slice(2) : hex;
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(clean.substr(i * 2, 2), 16);
  return out;
}

export const hex = { toHex, fromHex };

// ---------------------------------------------------------------------------
// Address derivation — pure function of the Ed25519 public key.
//   address = "xriqdev1" + hex(sha256("xriq:v1:ed25519-address" || pubkey)[0..20])
// ---------------------------------------------------------------------------
export function ed25519Address(publicKey: Uint8Array): string {
  if (publicKey.length !== 32) throw new Error('public key must be 32 bytes');
  const digest = sha256(concat(DOMAIN_ED25519_ADDRESS, publicKey));
  return ADDRESS_PREFIX + toHex(digest.subarray(0, ADDRESS_PAYLOAD_BYTES));
}

const ADDRESS_RE = /^xriqdev1[0-9a-f]{40}$/;
export function isValidAddress(addr: string): boolean {
  // The chain accepts a broader payload (16..96 lowercase alnum), but every
  // key-derived address is exactly xriqdev1 + 40 hex chars. We validate the
  // canonical shape and defer looser forms to the node.
  const trimmed = addr.trim();
  if (ADDRESS_RE.test(trimmed)) return true;
  // Fall back to the chain's general rule so pasted non-derived addresses pass.
  if (!trimmed.startsWith(ADDRESS_PREFIX)) return false;
  const payload = trimmed.slice(ADDRESS_PREFIX.length);
  return payload.length >= 16 && payload.length <= 96 && /^[0-9a-z]+$/.test(payload);
}

// ---------------------------------------------------------------------------
// HD key derivation — SLIP-0010 for Ed25519 (hardened-only), from a BIP39 seed.
// The chain treats the 32-byte private scalar seed as the signing key
// (`SigningKey::from_bytes`), so we derive that 32-byte seed deterministically.
// Testnet coin type (SLIP-0044 index 1') reflects the wallet's testnet scope.
// ---------------------------------------------------------------------------
const HARDENED = 0x80000000;
export const DEFAULT_PATH = [44 + HARDENED, 1 + HARDENED, 0 + HARDENED, 0 + HARDENED, 0 + HARDENED];

interface Slip10Node {
  key: Uint8Array; // 32-byte private
  chainCode: Uint8Array; // 32-byte
}

function slip10Master(seed: Uint8Array): Slip10Node {
  const I = hmac(sha512, utf8('ed25519 seed'), seed);
  return { key: I.slice(0, 32), chainCode: I.slice(32, 64) };
}

function slip10Derive(node: Slip10Node, index: number): Slip10Node {
  if (index < HARDENED) throw new Error('SLIP-0010 ed25519 supports hardened derivation only');
  const data = concat(new Uint8Array([0]), node.key, u32be(index));
  const I = hmac(sha512, node.chainCode, data);
  return { key: I.slice(0, 32), chainCode: I.slice(32, 64) };
}

function u32be(v: number): Uint8Array {
  const b = new Uint8Array(4);
  new DataView(b.buffer).setUint32(0, v >>> 0, false);
  return b;
}

/** Derive the 32-byte Ed25519 seed for a mnemonic at the given path. */
export function seedFromMnemonic(mnemonic: string, path: number[] = DEFAULT_PATH, passphrase = ''): Uint8Array {
  const bip39seed = mnemonicToSeedSync(mnemonic.trim(), passphrase);
  let node = slip10Master(bip39seed);
  for (const index of path) node = slip10Derive(node, index);
  return node.key;
}

export interface Keypair {
  privateSeed: Uint8Array; // 32-byte ed25519 seed (secret — never leaves device)
  publicKey: Uint8Array; // 32-byte
  address: string;
}

export function keypairFromSeed(privateSeed: Uint8Array): Keypair {
  if (privateSeed.length !== 32) throw new Error('seed must be 32 bytes');
  const publicKey = ed25519.getPublicKey(privateSeed);
  return { privateSeed, publicKey, address: ed25519Address(publicKey) };
}

export function keypairFromMnemonic(mnemonic: string, path: number[] = DEFAULT_PATH): Keypair {
  return keypairFromSeed(seedFromMnemonic(mnemonic, path));
}

// ---------------------------------------------------------------------------
// Mnemonic helpers (BIP39, English).
// ---------------------------------------------------------------------------
export function newMnemonic(strength: 128 | 256 = 256): string {
  return generateMnemonic(wordlist, strength);
}

export function isValidMnemonic(mnemonic: string): boolean {
  return validateMnemonic(mnemonic.trim(), wordlist);
}

// ---------------------------------------------------------------------------
// Transaction model + canonical signing.
// ---------------------------------------------------------------------------
export interface XriqTransaction {
  version: number;
  chainId: string;
  from: string;
  to: string;
  amountBaseUnits: bigint;
  feeBaseUnits: bigint;
  nonce: bigint;
  memoHash: Uint8Array | null; // 32 bytes or null
  expiresAtHeight: bigint | null;
  publicKey: Uint8Array; // 32-byte signer key, part of the signed body
}

/** encode_transaction_without_signature — Transfer action => zero trailing bytes. */
function encodeTxBody(tx: XriqTransaction): Uint8Array {
  const parts: Uint8Array[] = [
    u16le(tx.version),
    encodeString(tx.chainId),
    encodeString(tx.from),
    encodeString(tx.to),
    u128le(tx.amountBaseUnits),
    u128le(tx.feeBaseUnits),
    u64le(tx.nonce),
  ];
  // encode_option_hash(memo_hash)
  if (tx.memoHash) {
    if (tx.memoHash.length !== 32) throw new Error('memo hash must be 32 bytes');
    parts.push(new Uint8Array([1]), tx.memoHash);
  } else {
    parts.push(new Uint8Array([0]));
  }
  // encode_option_u64(expires_at_height)
  if (tx.expiresAtHeight !== null) {
    parts.push(new Uint8Array([1]), u64le(tx.expiresAtHeight));
  } else {
    parts.push(new Uint8Array([0]));
  }
  // encode_bytes(public_key)
  parts.push(encodeBytes(tx.publicKey));
  // encode_action(Transfer) => nothing.
  return concat(...parts);
}

export function transactionSigningBytes(tx: XriqTransaction): Uint8Array {
  return concat(preamble(DOMAIN_TRANSACTION_SIGNING), encodeTxBody(tx));
}

export function transactionSigningHash(tx: XriqTransaction): Uint8Array {
  return sha256(transactionSigningBytes(tx));
}

export function transactionBytes(tx: XriqTransaction, signature: Uint8Array): Uint8Array {
  return concat(preamble(DOMAIN_TRANSACTION_HASH), encodeTxBody(tx), encodeBytes(signature));
}

export function transactionHash(tx: XriqTransaction, signature: Uint8Array): Uint8Array {
  return sha256(transactionBytes(tx, signature));
}

export interface SignedTransfer {
  signingHash: Uint8Array;
  signature: Uint8Array; // 64-byte ed25519
  transactionHash: Uint8Array;
}

/**
 * Sign a transfer with the account's private seed. The chain verifies with
 * `verify_strict(signing_hash_bytes, signature)`, so we sign the 32-byte hash
 * directly (plain Ed25519 over the hash as message).
 */
export function signTransfer(tx: XriqTransaction, privateSeed: Uint8Array): SignedTransfer {
  const signingHash = transactionSigningHash(tx);
  const signature = ed25519.sign(signingHash, privateSeed);
  return { signingHash, signature, transactionHash: transactionHash(tx, signature) };
}

/**
 * Build the exact JSON body the node's non-custodial endpoint expects:
 * POST /api/v1/wallet/transfers/submit-signed (format version below).
 */
export const SIGNED_SUBMIT_FORMAT_VERSION = 'xriq-local-signed-transfer-envelope-v1';

export function buildSignedSubmitEnvelope(tx: XriqTransaction, signed: SignedTransfer) {
  return {
    format_version: SIGNED_SUBMIT_FORMAT_VERSION,
    transaction: {
      version: tx.version,
      chain_id: tx.chainId,
      from: tx.from,
      to: tx.to,
      amount_base_units: tx.amountBaseUnits.toString(),
      fee_base_units: tx.feeBaseUnits.toString(),
      nonce: Number(tx.nonce),
      expires_at_height: tx.expiresAtHeight === null ? null : Number(tx.expiresAtHeight),
    },
    hashes: {
      transaction_signing_hash: toHex(signed.signingHash),
      transaction_hash: toHex(signed.transactionHash),
    },
    signature_envelope: {
      algorithm: 'ed25519',
      signature_encoding: 'ed25519-hex',
      public_key: toHex(tx.publicKey),
      signature: toHex(signed.signature),
    },
  };
}
