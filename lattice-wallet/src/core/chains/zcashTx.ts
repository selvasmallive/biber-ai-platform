// Zcash v5 (NU5) transaction digest + transparent signing, per ZIP-244 / ZIP-225.
//
// The digest algorithm (txid + transparent SIGHASH_ALL, including the Sapling and Orchard
// sub-digests) is VERIFIED byte-for-byte against the official zcash-test-vectors
// (__tests__/fixtures/zip_0244.json) in __tests__/zec-sighash-vectors.ts — 10/10 txids and
// 6/6 transparent sighashes. The wallet only builds transparent-only transactions (empty
// Sapling/Orchard bundles), but the same verified digest code handles the general case.
import { blake2b } from '@noble/hashes/blake2b';
import { sha256 } from '@noble/hashes/sha256';
import { secp256k1 } from '@noble/curves/secp256k1';

// v5 / NU5 constants (mainnet).
export const V5_VERSION = 0x80000005; // fOverwintered | version 5
export const V5_VERSION_GROUP_ID = 0x26a7270a;
export const NU5_BRANCH_ID = 0xc2d6d0b4;
const SIGHASH_ALL = 0x01;

// ---------------------------------------------------------------------------
// Byte helpers.
// ---------------------------------------------------------------------------
const enc = new TextEncoder();
function P(s: string): Uint8Array {
  return enc.encode(s);
}
export function blake2b256(personal: string, msg?: Uint8Array): Uint8Array {
  return blake2b(msg ?? new Uint8Array(0), { dkLen: 32, personalization: P(personal) });
}
function cat(...parts: Uint8Array[]): Uint8Array {
  let n = 0;
  for (const p of parts) n += p.length;
  const out = new Uint8Array(n);
  let o = 0;
  for (const p of parts) {
    out.set(p, o);
    o += p.length;
  }
  return out;
}
function u32le(v: number): Uint8Array {
  return new Uint8Array([v & 0xff, (v >>> 8) & 0xff, (v >>> 16) & 0xff, (v >>> 24) & 0xff]);
}
function u64le(v: bigint): Uint8Array {
  const b = new Uint8Array(8);
  let x = BigInt.asUintN(64, v);
  for (let i = 0; i < 8; i++) {
    b[i] = Number(x & 0xffn);
    x >>= 8n;
  }
  return b;
}
export function compactSize(n: number): Uint8Array {
  if (n < 0xfd) return new Uint8Array([n]);
  if (n <= 0xffff) return new Uint8Array([0xfd, n & 0xff, (n >> 8) & 0xff]);
  return new Uint8Array([0xfe, n & 0xff, (n >> 8) & 0xff, (n >> 16) & 0xff, (n >>> 24) & 0xff]);
}

// ---------------------------------------------------------------------------
// Parsed transaction model (general v5, used for verification).
// ---------------------------------------------------------------------------
export interface ParsedInput {
  prevout: Uint8Array; // 36 bytes (txid || index LE)
  scriptSig: Uint8Array;
  sequence: Uint8Array; // 4 bytes
}
export interface ParsedOutput {
  value: Uint8Array; // 8 bytes LE
  script: Uint8Array;
}
export interface ParsedTx {
  header: Uint8Array; // 20 bytes
  consensusBranchId: Uint8Array; // 4 bytes LE
  vin: ParsedInput[];
  vout: ParsedOutput[];
  spends: { cv: Uint8Array; nullifier: Uint8Array; rk: Uint8Array }[];
  souts: { cv: Uint8Array; cmu: Uint8Array; eph: Uint8Array; enc: Uint8Array; out: Uint8Array }[];
  valueBalanceSapling: Uint8Array | null;
  anchorSapling: Uint8Array | null;
  actions: { cv: Uint8Array; nullifier: Uint8Array; rk: Uint8Array; cmx: Uint8Array; eph: Uint8Array; enc: Uint8Array; out: Uint8Array }[];
  flagsOrchard: Uint8Array | null;
  valueBalanceOrchard: Uint8Array | null;
  anchorOrchard: Uint8Array | null;
}

export function parseV5(buf: Uint8Array): ParsedTx {
  let o = 0;
  const take = (n: number) => {
    const s = buf.subarray(o, o + n);
    o += n;
    return s;
  };
  const cs = () => {
    const f = buf[o++];
    if (f < 0xfd) return f;
    if (f === 0xfd) {
      const x = buf[o] | (buf[o + 1] << 8);
      o += 2;
      return x;
    }
    if (f === 0xfe) {
      const x = (buf[o] | (buf[o + 1] << 8) | (buf[o + 2] << 16) | (buf[o + 3] * 0x1000000)) >>> 0;
      o += 4;
      return x;
    }
    let x = 0n;
    for (let i = 0; i < 8; i++) x |= BigInt(buf[o + i]) << BigInt(8 * i);
    o += 8;
    return Number(x);
  };
  const header = buf.subarray(0, 20);
  const consensusBranchId = buf.subarray(8, 12);
  o = 20;
  const nin = cs();
  const vin: ParsedInput[] = [];
  for (let i = 0; i < nin; i++) {
    const prevout = take(36);
    const sl = cs();
    const scriptSig = take(sl);
    const sequence = take(4);
    vin.push({ prevout, scriptSig, sequence });
  }
  const nout = cs();
  const vout: ParsedOutput[] = [];
  for (let i = 0; i < nout; i++) {
    const value = take(8);
    const sl = cs();
    vout.push({ value, script: take(sl) });
  }
  const nsp = cs();
  const spends = [];
  for (let i = 0; i < nsp; i++) spends.push({ cv: take(32), nullifier: take(32), rk: take(32) });
  const nso = cs();
  const souts = [];
  for (let i = 0; i < nso; i++) souts.push({ cv: take(32), cmu: take(32), eph: take(32), enc: take(580), out: take(80) });
  let valueBalanceSapling: Uint8Array | null = null;
  let anchorSapling: Uint8Array | null = null;
  if (nsp + nso > 0) valueBalanceSapling = take(8);
  if (nsp > 0) anchorSapling = take(32);
  take(192 * nsp);
  take(64 * nsp);
  take(192 * nso);
  if (nsp + nso > 0) take(64);
  const nact = cs();
  const actions = [];
  for (let i = 0; i < nact; i++)
    actions.push({ cv: take(32), nullifier: take(32), rk: take(32), cmx: take(32), eph: take(32), enc: take(580), out: take(80) });
  let flagsOrchard: Uint8Array | null = null;
  let valueBalanceOrchard: Uint8Array | null = null;
  let anchorOrchard: Uint8Array | null = null;
  if (nact > 0) {
    flagsOrchard = take(1);
    valueBalanceOrchard = take(8);
    anchorOrchard = take(32);
    const sp = cs();
    take(sp);
    take(64 * nact);
    take(64);
  }
  return { header, consensusBranchId, vin, vout, spends, souts, valueBalanceSapling, anchorSapling, actions, flagsOrchard, valueBalanceOrchard, anchorOrchard };
}

// ---------------------------------------------------------------------------
// ZIP-244 digests.
// ---------------------------------------------------------------------------
export function headerDigest(tx: ParsedTx): Uint8Array {
  return blake2b256('ZTxIdHeadersHash', tx.header);
}
function prevoutsDigest(tx: ParsedTx) {
  return blake2b256('ZTxIdPrevoutHash', cat(...tx.vin.map((i) => i.prevout)));
}
function sequenceDigest(tx: ParsedTx) {
  return blake2b256('ZTxIdSequencHash', cat(...tx.vin.map((i) => i.sequence)));
}
function outputsDigest(tx: ParsedTx) {
  return blake2b256('ZTxIdOutputsHash', cat(...tx.vout.map((o) => cat(o.value, compactSize(o.script.length), o.script))));
}
export function transparentDigest(tx: ParsedTx): Uint8Array {
  if (tx.vin.length === 0 && tx.vout.length === 0) return blake2b256('ZTxIdTranspaHash');
  return blake2b256('ZTxIdTranspaHash', cat(prevoutsDigest(tx), sequenceDigest(tx), outputsDigest(tx)));
}
export function saplingDigest(tx: ParsedTx): Uint8Array {
  if (tx.spends.length === 0 && tx.souts.length === 0) return blake2b256('ZTxIdSaplingHash');
  const spendsD =
    tx.spends.length === 0
      ? blake2b256('ZTxIdSSpendsHash')
      : blake2b256(
          'ZTxIdSSpendsHash',
          cat(
            blake2b256('ZTxIdSSpendCHash', cat(...tx.spends.map((s) => s.nullifier))),
            blake2b256('ZTxIdSSpendNHash', cat(...tx.spends.map((s) => cat(s.cv, tx.anchorSapling!, s.rk)))),
          ),
        );
  const outsD =
    tx.souts.length === 0
      ? blake2b256('ZTxIdSOutputHash')
      : blake2b256(
          'ZTxIdSOutputHash',
          cat(
            blake2b256('ZTxIdSOutC__Hash', cat(...tx.souts.map((o) => cat(o.cmu, o.eph, o.enc.subarray(0, 52))))),
            blake2b256('ZTxIdSOutM__Hash', cat(...tx.souts.map((o) => o.enc.subarray(52, 564)))),
            blake2b256('ZTxIdSOutN__Hash', cat(...tx.souts.map((o) => cat(o.cv, o.enc.subarray(564), o.out)))),
          ),
        );
  return blake2b256('ZTxIdSaplingHash', cat(spendsD, outsD, tx.valueBalanceSapling!));
}
export function orchardDigest(tx: ParsedTx): Uint8Array {
  if (tx.actions.length === 0) return blake2b256('ZTxIdOrchardHash');
  return blake2b256(
    'ZTxIdOrchardHash',
    cat(
      blake2b256('ZTxIdOrcActCHash', cat(...tx.actions.map((a) => cat(a.nullifier, a.cmx, a.eph, a.enc.subarray(0, 52))))),
      blake2b256('ZTxIdOrcActMHash', cat(...tx.actions.map((a) => a.enc.subarray(52, 564)))),
      blake2b256('ZTxIdOrcActNHash', cat(...tx.actions.map((a) => cat(a.cv, a.rk, a.enc.subarray(564), a.out)))),
      tx.flagsOrchard!,
      tx.valueBalanceOrchard!,
      tx.anchorOrchard!,
    ),
  );
}
// blake2b with a raw 16-byte personalization (the branch-id personal isn't valid UTF-8).
function blakeRaw(personal16: Uint8Array, msg: Uint8Array): Uint8Array {
  return blake2b(msg, { dkLen: 32, personalization: personal16 });
}
function txidRootPersonal(cbid: Uint8Array): Uint8Array {
  return cat(P('ZcashTxHash_'), cbid);
}

export function computeTxid(tx: ParsedTx): Uint8Array {
  return blakeRaw(txidRootPersonal(tx.consensusBranchId), cat(headerDigest(tx), transparentDigest(tx), saplingDigest(tx), orchardDigest(tx)));
}

/**
 * Transparent SIGHASH_ALL for input `index`. `spentAmounts` (8-byte LE) and
 * `spentScripts` (raw pk_script) are the coins being spent (from the UTXOs).
 */
export function transparentSighashAll(
  tx: ParsedTx,
  index: number,
  spentAmounts: Uint8Array[],
  spentScripts: Uint8Array[],
): Uint8Array {
  const amountsD = blake2b256('ZTxTrAmountsHash', cat(...spentAmounts));
  const scriptsD = blake2b256('ZTxTrScriptsHash', cat(...spentScripts.map((s) => cat(compactSize(s.length), s))));
  const inp = tx.vin[index];
  const txinD = blake2b256(
    'Zcash___TxInHash',
    cat(inp.prevout, spentAmounts[index], compactSize(spentScripts[index].length), spentScripts[index], inp.sequence),
  );
  const transparentSig = blake2b256(
    'ZTxIdTranspaHash',
    cat(new Uint8Array([SIGHASH_ALL]), prevoutsDigest(tx), amountsD, scriptsD, sequenceDigest(tx), outputsDigest(tx), txinD),
  );
  return blakeRaw(txidRootPersonal(tx.consensusBranchId), cat(headerDigest(tx), transparentSig, saplingDigest(tx), orchardDigest(tx)));
}

// ---------------------------------------------------------------------------
// Build + sign a transparent-only v5 transaction (P2PKH inputs and outputs).
// ---------------------------------------------------------------------------
export interface SpendInput {
  txidLE: Uint8Array; // 32 bytes, internal (little-endian) order as used in the tx
  vout: number;
  value: bigint;
  scriptPubKey: Uint8Array; // the coin's pk_script (P2PKH)
  privateKey: Uint8Array;
  publicKey: Uint8Array; // compressed
}
export interface SpendOutput {
  value: bigint;
  scriptPubKey: Uint8Array;
}

export function p2pkhScript(hash160: Uint8Array): Uint8Array {
  return cat(new Uint8Array([0x76, 0xa9, 0x14]), hash160, new Uint8Array([0x88, 0xac]));
}

function buildHeader(lockTime: number, expiryHeight: number): Uint8Array {
  return cat(u32le(V5_VERSION), u32le(V5_VERSION_GROUP_ID), u32le(NU5_BRANCH_ID), u32le(lockTime), u32le(expiryHeight));
}

/** Serialize a transparent-only v5 transaction (empty Sapling/Orchard bundles). */
function serializeV5(header: Uint8Array, vin: ParsedInput[], vout: ParsedOutput[]): Uint8Array {
  const inBytes = cat(
    compactSize(vin.length),
    ...vin.map((i) => cat(i.prevout, compactSize(i.scriptSig.length), i.scriptSig, i.sequence)),
  );
  const outBytes = cat(
    compactSize(vout.length),
    ...vout.map((o) => cat(o.value, compactSize(o.script.length), o.script)),
  );
  // sapling: 0 spends, 0 outputs; orchard: 0 actions.
  return cat(header, inBytes, outBytes, new Uint8Array([0x00, 0x00, 0x00]));
}

export interface SignedZcashTx {
  rawHex: string;
  txid: string; // display order (reversed)
}

export function buildAndSignTransparent(
  inputs: SpendInput[],
  outputs: SpendOutput[],
  lockTime: number,
  expiryHeight: number,
): SignedZcashTx {
  const header = buildHeader(lockTime, expiryHeight);
  const sequence = new Uint8Array([0xff, 0xff, 0xff, 0xff]);
  const vin: ParsedInput[] = inputs.map((i) => ({
    prevout: cat(i.txidLE, u32le(i.vout)),
    scriptSig: new Uint8Array(0),
    sequence,
  }));
  const vout: ParsedOutput[] = outputs.map((o) => ({ value: u64le(o.value), script: o.scriptPubKey }));
  const spentAmounts = inputs.map((i) => u64le(i.value));
  const spentScripts = inputs.map((i) => i.scriptPubKey);

  const parsed: ParsedTx = {
    header,
    consensusBranchId: header.subarray(8, 12),
    vin,
    vout,
    spends: [],
    souts: [],
    valueBalanceSapling: null,
    anchorSapling: null,
    actions: [],
    flagsOrchard: null,
    valueBalanceOrchard: null,
    anchorOrchard: null,
  };

  // Sign each input, filling its scriptSig.
  inputs.forEach((inp, i) => {
    const sighash = transparentSighashAll(parsed, i, spentAmounts, spentScripts);
    const sig = secp256k1.sign(sighash, inp.privateKey); // low-S by default
    const der = sig.toDERRawBytes();
    const sigWithType = cat(der, new Uint8Array([SIGHASH_ALL]));
    // P2PKH scriptSig: PUSH(sig+type) PUSH(pubkey)
    vin[i].scriptSig = cat(
      new Uint8Array([sigWithType.length]),
      sigWithType,
      new Uint8Array([inp.publicKey.length]),
      inp.publicKey,
    );
  });

  const raw = serializeV5(header, vin, vout);
  const idLE = computeTxid(parsed); // txid is over the unsigned/effecting digest
  const idDisplay = Uint8Array.from(idLE).reverse();
  return {
    rawHex: bytesToHex(raw),
    txid: bytesToHex(idDisplay),
  };
}

function bytesToHex(b: Uint8Array): string {
  let s = '';
  for (const x of b) s += x.toString(16).padStart(2, '0');
  return s;
}

export { sha256 };
