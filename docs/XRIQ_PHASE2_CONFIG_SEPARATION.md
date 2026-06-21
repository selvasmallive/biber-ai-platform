# XRIQ Phase 2 Environment / Config Separation

Status: active Phase 2 hardening. Local/private only. No production behavior.

This document describes the first slice of the Phase 2 "staging configuration
clearly separated from production" exit criterion from
`docs/XRIQ_PRODUCTION_ROADMAP.md`: an explicit, fail-closed deployment
environment profile.

## Problem

Before this change there was no notion of a deployment environment in the XRIQ
runtime. The accepted-mutation flags (`--enable-local-wallet-submit`,
`--enable-local-wallet-send`, `--enable-local-wallet-submit-signed`,
`--enable-local-block-production`) were independent booleans with nothing tying
them to a profile that could be distinguished from production. Nothing prevented
a build from being described or run as "production".

## Environment Profile

A single source of truth now lives in `xriq-core`
(`xriq/crates/xriq-core/src/environment.rs`):

- `Environment::Local` — developer machine; the default profile.
- `Environment::StagingDevnet` — hardened private/staging devnet:
  production-like topology, but no public network exposure and no public
  financial claims.

There is intentionally **no `Production` or `Mainnet` variant**. Parsing is
**fail-closed**: `local` and `staging-devnet` are the only accepted values;
`production`, `mainnet`, `public-testnet`, `production-candidate`, and any
unknown or differently-cased value are rejected with a clear error. This makes
it impossible to run, or accidentally configure, this build as production.

`CANONICAL_NETWORK = "xriq-devnet"` is also centralized in the same module.

## Runtime Flag

The `xriq-api` binary accepts an optional `--environment` flag on both the
`request` and `serve-readonly` commands:

```bash
# default (local) — unchanged behavior
xriq-api request --chain-file <path> --target /api/v1/health

# staging-devnet
xriq-api request --chain-file <path> --target /api/v1/health --environment staging-devnet

# rejected, exits non-zero
xriq-api request --chain-file <path> --target /api/v1/health --environment production
# error=unsupported environment "production": only "local" and "staging-devnet" are allowed; ...
```

- The default is `local`, so every existing command, test, and smoke behaves
  exactly as before (no contract or fixture change).
- The active profile is logged to stderr (`environment=<profile>`), so operators
  can see which profile a process is running under.
- Accepted local mutation flags remain usable under `local` and `staging-devnet`
  and can never be paired with a production profile, because the profile cannot
  parse to production at all.

## Scope And Follow-Ups

- This slice covers `xriq-core` (the profile type, fail-closed parsing, tests)
  and the `xriq-api` binary (the `--environment` flag and validation).
- The `xriq-node` CLI and the explorer-ui environment banner are follow-ups; the
  node remains local/private and the UI feature switches are unchanged.
- The API response `environment` field (`"private-devnet"`) and the genesis
  `chain_id` (`"xriq-devnet"`) are deliberately unchanged to preserve existing
  response contracts and fixtures.

## Verification

```bash
cd xriq
cargo test -p xriq-core -j 1
cargo test -p xriq-api -j 1
```

The `xriq-core` tests cover fail-closed parsing (supported profiles accepted;
production/mainnet/public-testnet/unknown rejected). The `xriq-api` test
`environment_flag_is_fail_closed_for_request_and_serve` covers the `request` and
`serve-readonly` flag parsing, including rejection of production-class values and
that accepted mutation flags still work under `staging-devnet`. The Phase 1.4
lifecycle smoke and the Phase 2 restart/recovery smoke continue to pass under the
default `local` profile.
