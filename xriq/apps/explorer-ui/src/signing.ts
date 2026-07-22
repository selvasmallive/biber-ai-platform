// Non-custodial ephemeral Ed25519 signer for the local test wallet.
//
// This is the ONLY module that touches private key material. The private key is a
// fresh random Uint8Array held solely inside the closure returned by
// createEphemeralSigner; it is never returned, never written to any browser
// storage, and never transmitted. Only the public key (hex) and per-transaction
// signatures leave this module. See scripts/check-wallet-key-safety.mjs and
// docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md.
import * as ed from "@noble/ed25519";

function toHex(bytes: Uint8Array): string {
  let out = "";
  for (const byte of bytes) {
    out += byte.toString(16).padStart(2, "0");
  }
  return out;
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

export interface EphemeralSigner {
  /** The 32-byte Ed25519 public key as lowercase hex — safe to share. */
  readonly publicKeyHex: string;
  /**
   * Sign a 32-byte canonical signing hash (lowercase hex) and return the 64-byte
   * Ed25519 signature as lowercase hex. The private key never leaves this closure.
   */
  signHashHex(signingHashHex: string): Promise<string>;
}

/**
 * Create a fresh, ephemeral, in-memory Ed25519 signer. The key exists only for the
 * lifetime of the returned object and is discarded when it is dropped — nothing is
 * persisted or transmitted.
 */
export async function createEphemeralSigner(): Promise<EphemeralSigner> {
  // Fresh random key from the platform CSPRNG (crypto.getRandomValues under the
  // hood). Held only in this closure; never returned or stored.
  const signingSeed = ed.utils.randomPrivateKey();
  const publicKeyHex = toHex(await ed.getPublicKeyAsync(signingSeed));
  return {
    publicKeyHex,
    async signHashHex(signingHashHex: string): Promise<string> {
      const signature = await ed.signAsync(hexToBytes(signingHashHex), signingSeed);
      return toHex(signature);
    },
  };
}
