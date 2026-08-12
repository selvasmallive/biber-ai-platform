// Post-quantum signing (wallet side) — REAL ML-DSA-65 (FIPS 204 / CRYSTALS-Dilithium)
// keys and signatures, packaged as a HYBRID envelope tagged to XRIQ's reserved
// on-chain algorithm id 250 (`SignatureAlgorithm::HybridPostQuantumReserved`).
//
// STATUS: the wallet produces genuine PQ signatures today. End-to-end PQ security
// finalizes when the chain's verifier for id 250 is wired (XRIQ production-crypto
// migration). Until then this is forward-compatible: a hybrid signature is only as
// weak as its strongest-still-standing leg, and the classical Ed25519 leg is what
// the chain checks now — so enabling PQ never reduces present security.

import { ml_dsa65 } from '@noble/post-quantum/ml-dsa';
import { hkdf } from '@noble/hashes/hkdf';
import { sha256 } from '@noble/hashes/sha256';
import { ed25519 } from '@noble/curves/ed25519';
import { seedFromMnemonic, DEFAULT_PATH, hex } from './xriq';
import { SignatureAlgorithmId } from './xriq';

// Domain-separate the PQ key material from the classical account key so the two
// legs are independent secrets derived from the same mnemonic.
const PQ_HKDF_INFO = new TextEncoder().encode('lattice:v1:ml-dsa-65:account-seed');
const PQ_SEED_LEN = 32;

export interface PqKeypair {
  seed: Uint8Array; // 32-byte ML-DSA seed (secret)
  publicKey: Uint8Array; // ML-DSA-65 public key
  secretKey: Uint8Array; // ML-DSA-65 secret key
}

/** Deterministically derive an ML-DSA-65 keypair from the wallet mnemonic. */
export function pqKeypairFromMnemonic(mnemonic: string, path: number[] = DEFAULT_PATH): PqKeypair {
  const classicalSeed = seedFromMnemonic(mnemonic, path);
  const seed = hkdf(sha256, classicalSeed, undefined, PQ_HKDF_INFO, PQ_SEED_LEN);
  const { publicKey, secretKey } = ml_dsa65.keygen(seed);
  return { seed, publicKey, secretKey };
}

export interface HybridSignature {
  algorithmId: number; // 250
  classical: { publicKey: string; signature: string }; // ed25519, hex
  pq: { scheme: 'ml-dsa-65'; publicKey: string; signature: string }; // hex
}

/**
 * Produce a hybrid signature over an XRIQ 32-byte signing hash: the classical
 * Ed25519 signature the chain checks today PLUS a real ML-DSA-65 signature over
 * the same hash, both bound into one id-250 envelope.
 */
export function hybridSign(
  signingHash: Uint8Array,
  classicalSeed: Uint8Array,
  pq: PqKeypair,
): HybridSignature {
  const classicalPub = ed25519.getPublicKey(classicalSeed);
  const classicalSig = ed25519.sign(signingHash, classicalSeed);
  const pqSig = ml_dsa65.sign(pq.secretKey, signingHash);
  return {
    algorithmId: SignatureAlgorithmId.HybridPostQuantumReserved,
    classical: { publicKey: hex.toHex(classicalPub), signature: hex.toHex(classicalSig) },
    pq: { scheme: 'ml-dsa-65', publicKey: hex.toHex(pq.publicKey), signature: hex.toHex(pqSig) },
  };
}

/** Verify both legs of a hybrid signature (offline self-check / test helper). */
export function hybridVerify(signingHash: Uint8Array, sig: HybridSignature): boolean {
  const classicalOk = ed25519.verify(
    hex.fromHex(sig.classical.signature),
    signingHash,
    hex.fromHex(sig.classical.publicKey),
  );
  const pqOk = ml_dsa65.verify(
    hex.fromHex(sig.pq.publicKey),
    signingHash,
    hex.fromHex(sig.pq.signature),
  );
  return classicalOk && pqOk;
}
