# XRIQ Phase 1.3 Demo Runbook

Status: local/private browser demo only. This is not public mainnet, a hosted
wallet, custody, DEX/liquidity, smart-contract, validator, bridge, production
infrastructure, exchange-listing, or legal/compliance readiness.

## What This Demo Shows

The Phase 1.3 demo shows one transparent local/private wallet journey:

1. start from a deterministic private-devnet chain,
2. open the local React + TypeScript UI,
3. send a local/private wallet transfer from Alice to Carol,
4. see the transfer enter pending state,
5. produce one local block,
6. refresh the UI,
7. see the transfer confirmed with updated wallet/Admin/mempool state.

The demo uses only test identities and local files under `xriq/target/`. It does
not use private keys, seed phrases, signing, custody, public networking, GCP,
Vast, Docker, or production services.

## Prerequisites

From the repo root:

```powershell
cd C:\Users\vselv\OneDrive\Biber\biber-ai-platform
```

If local debug binaries already exist, use `--skip-build`. If they do not, omit
`--skip-build` and the launcher will build `xriq-node` and `xriq-api`.

## Quick Scripted Proof

To verify the behavior without a browser:

```powershell
python scripts\xriq_phase1_3_wallet_behavior_ui_smoke.py --skip-build
python scripts\xriq_phase1_3_readiness_summary.py --cpu-smoke-summary xriq\target\xriq-phase1-3-wallet-behavior-smoke-20260607T131636Z\summary.json
```

## Browser Demo

Launch the local API and UI:

```powershell
python scripts\xriq_phase1_3_demo_launcher.py --skip-build --launch --auto-port
```

The launcher prints the API URL, UI URL, artifact directory, and click path.
Open the printed UI URL in a browser. Keep the launcher terminal open while
testing; press `Ctrl+C` in that terminal to stop both local servers.

Expected click path:

1. Confirm the app header status is `Healthy`.
2. In `Wallet`, confirm `Local Wallet Send` says `feature switch on`.
3. Keep the default demo values: Alice to Carol, amount `5`, fee `2`, nonce
   `1`, expiry `100`.
4. Click `Send Local`.
5. Confirm the local send result is `pending` and `pending_state_only`.
6. Confirm `Wallet Activity` shows the transaction as pending.
7. In `Admin Status`, confirm `Local Block Production` says `feature switch on`
   and `Pending` is `1`.
8. Click `Produce Local`.
9. Confirm block height is `2`, pending after is `0`, and the confirmed count is
   `1`.
10. Click the header refresh button.
11. Confirm wallet/Admin/mempool state now shows the transaction confirmed and
    pending count `0`.

## Prepare-Only Mode

To create deterministic demo files and command snippets without starting
servers:

```powershell
python scripts\xriq_phase1_3_demo_launcher.py --skip-build --prepare-only
```

The artifact directory contains:

- `demo-context.json`
- `summary.json`
- `demo-commands.ps1`
- `demo-commands.sh`
- `base-confirmed-transfer.json`
- local demo chain and pending files

## Local Smoke For The Launcher

To start the API/UI, verify both respond, and stop automatically:

```powershell
python scripts\xriq_phase1_3_demo_launcher.py --skip-build --smoke-only --auto-port
```

## Expected Final State

After a successful browser demo:

- chain height is `2`,
- mempool pending count is `0`,
- wallet pending count is `0`,
- Alice balance is `66` with nonce `2`,
- Bob balance is `25`,
- Carol balance is `5`,
- fee sink balance is `4`,
- the behavior transaction is confirmed at block height `2`, transaction index
  `0`.

## Boundaries

Do not use this demo to claim public launch, exchange listing readiness,
custody, smart-contract readiness, DEX support, privacy guarantees, ISO 20022
certification, or production infrastructure readiness.

Do not create, move, delete, recreate, or push any RC tag from this demo. A
future Phase 1.3 RC tag would require a separate exact approval for
`phase1-3-xriq-local-private-behavior-rc1`.
