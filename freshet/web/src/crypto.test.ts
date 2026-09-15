//! The encryption that stands between a saved return and whoever finds the
//! file.
//!
//! A lower iteration count is used nowhere here: these run the real 600,000,
//! which costs a few hundred milliseconds each and is worth paying in a test
//! that is checking the real thing.

import { describe, expect, it } from "vitest";

import { open, seal } from "./crypto";

const RETURN = JSON.stringify({
  province: "on",
  facts: { "gifi.8000": "750000", "t2.active_business_income": "270000" },
});

describe("a saved return", () => {
  it("comes back exactly as it went in", async () => {
    const sealed = await seal(RETURN, "correct horse battery staple");
    expect(await open(sealed, "correct horse battery staple")).toBe(RETURN);
  });

  it("does not contain the return in the clear", async () => {
    const sealed = await seal(RETURN, "correct horse battery staple");
    const whole = JSON.stringify(sealed);

    // The obvious failure is an envelope that carries the plaintext beside the
    // ciphertext, which no round-trip test would ever notice.
    expect(whole).not.toContain("750000");
    expect(whole).not.toContain("gifi.8000");
    expect(whole).not.toContain("correct horse battery staple");
  });

  it("will not open with the wrong passphrase, and says there is no recovery", async () => {
    const sealed = await seal(RETURN, "correct horse battery staple");

    await expect(open(sealed, "correct horse battery stapl")).rejects.toThrow(
      /no way to recover/,
    );
  });

  it("refuses ciphertext that has been altered", async () => {
    const sealed = await seal(RETURN, "correct horse battery staple");

    // Flip a byte in the middle. AES-GCM authenticates, so this must fail
    // rather than decrypt to something subtly different — a tax return that
    // decrypts to a *changed* amount would be far worse than one that fails.
    const bytes = atob(sealed.ciphertext).split("");
    const at = Math.floor(bytes.length / 2);
    bytes[at] = String.fromCharCode(bytes[at].charCodeAt(0) ^ 0x40);
    sealed.ciphertext = btoa(bytes.join(""));

    await expect(open(sealed, "correct horse battery staple")).rejects.toThrow();
  });

  it("uses a fresh salt and nonce every time", async () => {
    const a = await seal(RETURN, "correct horse battery staple");
    const b = await seal(RETURN, "correct horse battery staple");

    // Reusing a nonce under one key breaks AES-GCM outright, and reusing a
    // salt would make two files share a derived key. Identical plaintext under
    // an identical passphrase must still produce different bytes.
    expect(a.iv).not.toBe(b.iv);
    expect(a.salt).not.toBe(b.salt);
    expect(a.ciphertext).not.toBe(b.ciphertext);
  });

  it("carries the iteration count so it can be raised later", async () => {
    const sealed = await seal(RETURN, "correct horse battery staple");

    // Recorded rather than assumed, so a future increase does not strand every
    // return already saved at the old count.
    expect(sealed.iterations).toBeGreaterThanOrEqual(600_000);
    expect(sealed.kdf).toBe("pbkdf2-sha256");
  });
});
