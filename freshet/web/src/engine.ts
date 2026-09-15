//! Loading the tax engine into the page.
//!
//! The module is the same Rust that the desktop build runs — the same form
//! definitions, the same parameter packs, the same refusal to call a return
//! filable while a figure is unverified. That it happens to be compiled to
//! WebAssembly here does not make it a second implementation, which matters:
//! two implementations of a tax calculation would disagree eventually, and the
//! disagreement would be found by a customer.

import type { Capabilities, Computed, Period } from "./types";

type Wasm = {
  default: (init?: unknown) => Promise<unknown>;
  compute_t1: (year: number, province: string, facts: string) => string;
  compute_t2: (
    start: string,
    end: string,
    province: string,
    facts: string,
  ) => string;
  capabilities: () => string;
};

/// Served as a static file, not bundled. It is generated from the Rust crate
/// by `scripts/build-web.sh` and is not in the repository, so the specifier is
/// resolved at runtime rather than by the bundler or the type checker — hence
/// the variable. `Wasm` above is the hand-written record of its shape, and
/// `engine.test.ts` checks that record against the built module.
const MODULE_URL = "/engine/freshet_wasm.js";

let loading: Promise<Wasm> | null = null;

/// Load once, and share the load. Several components ask for the engine as
/// they mount; without this the browser fetches a megabyte more than once.
export function engine(): Promise<Wasm> {
  if (!loading) {
    loading = (async () => {
      const wasm = (await import(/* @vite-ignore */ MODULE_URL)) as unknown as Wasm;
      await wasm.default();
      return wasm;
    })();
  }
  return loading;
}

export type Facts = Record<string, string>;

/// Compute a corporate return for a fiscal period.
///
/// Errors come back as thrown strings from Rust — an impossible period, an
/// unsupported province. They are the user's to fix, so they are returned
/// rather than logged.
export async function computeT2(
  period: Period,
  province: string,
  facts: Facts,
): Promise<Computed> {
  const wasm = await engine();
  return JSON.parse(
    wasm.compute_t2(period.start, period.end, province, JSON.stringify(facts)),
  );
}

export async function computeT1(
  year: number,
  province: string,
  facts: Facts,
): Promise<Computed> {
  const wasm = await engine();
  return JSON.parse(wasm.compute_t1(year, province, JSON.stringify(facts)));
}

export async function capabilities(): Promise<Capabilities> {
  const wasm = await engine();
  return JSON.parse(wasm.capabilities());
}
