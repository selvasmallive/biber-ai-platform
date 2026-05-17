#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/vast_direct_common.sh
source "${SCRIPT_DIR}/lib/vast_direct_common.sh"

ensure_runtime_dirs

export CARGO_HOME="${CARGO_HOME:-${BIBER_RUNTIME_ROOT}/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-${BIBER_RUNTIME_ROOT}/.rustup}"
export PATH="${CARGO_HOME}/bin:${PATH}"

mkdir -p "$CARGO_HOME" "$RUSTUP_HOME"

if command -v cargo >/dev/null 2>&1 && command -v rustfmt >/dev/null 2>&1; then
  log "Rust toolchain already available"
  cargo --version
  rustc --version
  rustfmt --version
  if ! cargo clippy --version >/dev/null 2>&1; then
    log "Installing Rust clippy component"
    rustup component add clippy
  fi
  cargo clippy --version
  exit 0
fi

command -v curl >/dev/null 2>&1 || die "curl is required to install rustup"

RUST_TOOLCHAIN="${BIBER_RUST_TOOLCHAIN:-stable}"
RUSTUP_INIT="${BIBER_RUNTIME_ROOT}/rustup-init.sh"
trap 'rm -f "$RUSTUP_INIT"' EXIT

log "Installing Rust toolchain '${RUST_TOOLCHAIN}' under ${BIBER_RUNTIME_ROOT}"
curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs -o "$RUSTUP_INIT"
sh "$RUSTUP_INIT" -y --profile minimal --default-toolchain "$RUST_TOOLCHAIN" --component rustfmt --component clippy

log "Rust toolchain installed"
cargo --version
rustc --version
rustfmt --version
cargo clippy --version
