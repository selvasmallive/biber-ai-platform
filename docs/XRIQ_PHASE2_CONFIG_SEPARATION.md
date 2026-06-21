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

- This covers `xriq-core` (the profile type, fail-closed parsing, tests) and
  both binaries:
  - `xriq-api` accepts `--environment` on `request` and `serve-readonly`.
  - `xriq-node` accepts `--environment` on every subcommand and on
    `serve-readonly`/`serve-private`; the flag is parsed centrally and stripped
    before per-command parsing, defaulting to local and rejecting production-class
    values with `unsupported_environment`.
- The explorer-ui shows the active profile via an environment banner wired to a
  `VITE_XRIQ_ENVIRONMENT` build var (default local; `staging-devnet` is
  highlighted; any other value renders as "unsupported"). The UI feature
  switches are otherwise unchanged.
- The API response `environment` field (`"private-devnet"`) and the genesis
  `chain_id` (`"xriq-devnet"`) are deliberately unchanged to preserve existing
  response contracts and fixtures.

## Clean-Clone Staging Smokes

A clean clone can build and run the Phase 2 smokes, including the staging-devnet
profile, with a single command:

```bash
python scripts/xriq_phase2_staging_smokes.py
```

It builds the binaries once, runs the Phase 1.4 lifecycle smoke (local profile),
and runs the Phase 2 restart/recovery smoke under `--environment staging-devnet`,
exercising the fail-closed profile end-to-end across both binaries. The CI Rust
job runs this on every push (CI checks out a clean clone), which satisfies the
Phase 2 "clean clone can run local/staging smoke tests" exit criterion.

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
