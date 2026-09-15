#!/usr/bin/env bash
#
# Build the browser engine.
#
# The tax calculation runs in the page, so the engine has to become a
# WebAssembly module plus the JavaScript that loads it. Both halves are
# generated; neither is edited by hand, and `web/public/engine` is ignored by
# git for that reason.
#
# `wasm-bindgen` couples the CLI to the crate version exactly — the macro emits
# a schema the CLI parses, and a mismatch fails with a message that does not
# say "version". Both are pinned, here and in the crate manifest, and they must
# be changed together.
set -euo pipefail

VERSION="0.2.100"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRATE="$ROOT/crates/freshet-wasm"
OUT="$ROOT/web/public/engine"

if ! command -v wasm-bindgen >/dev/null 2>&1 \
  || [ "$(wasm-bindgen --version | awk '{print $2}')" != "$VERSION" ]; then
  echo "installing wasm-bindgen-cli $VERSION"
  cargo install wasm-bindgen-cli --version "$VERSION" --force
fi

rustup target add wasm32-unknown-unknown >/dev/null

echo "building the engine for the browser"
cargo build --release --target wasm32-unknown-unknown --manifest-path "$CRATE/Cargo.toml"

wasm-bindgen --target web --no-typescript --out-dir "$OUT" \
  "$CRATE/target/wasm32-unknown-unknown/release/freshet_wasm.wasm"

SIZE=$(wc -c < "$OUT/freshet_wasm_bg.wasm")
GZIP=$(gzip -9 -c "$OUT/freshet_wasm_bg.wasm" | wc -c)
echo "engine: $((SIZE / 1024)) KB, $((GZIP / 1024)) KB compressed"

# A first visit pays this. It is worth noticing if it doubles.
if [ "$GZIP" -gt 400000 ]; then
  echo "the compressed engine has grown past 400 KB; check what was added" >&2
  exit 1
fi
