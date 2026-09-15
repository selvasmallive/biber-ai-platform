//! Encrypting a return before it is stored.
//!
//! The server holds saved work so a user can come back to it from another
//! machine. It does not hold the work in a form it can read: the browser
//! encrypts with a key derived from a passphrase the server never sees, and
//! uploads ciphertext.
//!
//! This mirrors the desktop vault, including the part people dislike: **there
//! is no recovery**. A forgotten passphrase is a lost return, and saying so
//! before the user commits is the only honest option. Escrowing a key would
//! quietly undo the whole arrangement, because then the server could read
//! everything after all.
//!
//! WebCrypto, not a library. PBKDF2 rather than Argon2 because it is what the
//! platform actually provides — Argon2 would mean shipping another WebAssembly
//! module to every visitor, and a high iteration count on PBKDF2-SHA-256 is a
//! reasonable trade for a passphrase that is also protecting a network round
//! trip rather than an offline file.

/// OWASP's floor for PBKDF2-HMAC-SHA-256 at the time of writing. Raising it
/// later is safe: the count is stored with the ciphertext, so old records keep
/// decrypting with the count they were written at.
const ITERATIONS = 600_000;

export interface Sealed {
  /// The format, so a future change is a decision rather than a corruption.
  v: 1;
  kdf: "pbkdf2-sha256";
  iterations: number;
  salt: string;
  iv: string;
  ciphertext: string;
}

const b64 = (bytes: Uint8Array): string =>
  btoa(String.fromCharCode(...bytes));

// Annotated as backed by a plain ArrayBuffer rather than the wider
// ArrayBufferLike. WebCrypto will not accept a view onto a SharedArrayBuffer,
// and TypeScript is right to insist: passing one would fail at runtime.
const unb64 = (s: string): Uint8Array<ArrayBuffer> => {
  const raw = atob(s);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
};

async function derive(
  passphrase: string,
  salt: Uint8Array<ArrayBuffer>,
  iterations: number,
): Promise<CryptoKey> {
  const material = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(passphrase),
    "PBKDF2",
    false,
    ["deriveKey"],
  );

  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    material,
    { name: "AES-GCM", length: 256 },
    // Not extractable. The key exists for the life of the call and cannot be
    // read back out into JavaScript, which limits what a script injected into
    // the page could take with it.
    false,
    ["encrypt", "decrypt"],
  );
}

export async function seal(
  plaintext: string,
  passphrase: string,
): Promise<Sealed> {
  const salt = crypto.getRandomValues(new Uint8Array(new ArrayBuffer(16)));
  const iv = crypto.getRandomValues(new Uint8Array(new ArrayBuffer(12)));
  const key = await derive(passphrase, salt, ITERATIONS);

  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: "AES-GCM", iv },
      key,
      new TextEncoder().encode(plaintext),
    ),
  );

  return {
    v: 1,
    kdf: "pbkdf2-sha256",
    iterations: ITERATIONS,
    salt: b64(salt),
    iv: b64(iv),
    ciphertext: b64(ciphertext),
  };
}

export async function open(
  sealed: Sealed,
  passphrase: string,
): Promise<string> {
  if (sealed.v !== 1 || sealed.kdf !== "pbkdf2-sha256") {
    throw new Error(
      "This return was saved by a newer version of Freshet than this one.",
    );
  }

  const key = await derive(passphrase, unb64(sealed.salt), sealed.iterations);

  try {
    const plaintext = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: unb64(sealed.iv) },
      key,
      unb64(sealed.ciphertext),
    );
    return new TextDecoder().decode(plaintext);
  } catch {
    // AES-GCM fails authentication identically for a wrong passphrase and for
    // tampered ciphertext, and the browser cannot tell them apart. Say the
    // likely thing without claiming to know which.
    throw new Error(
      "That passphrase did not open this return. There is no way to recover it.",
    );
  }
}
