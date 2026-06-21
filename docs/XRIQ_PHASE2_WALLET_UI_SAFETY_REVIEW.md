# XRIQ Phase 2 Wallet UI Safety Review

Status: complete for the current explorer-ui. Local/private only.

This review covers the Phase 2 exit criterion that "no unsafe key material enters
browser or server custody paths" and the non-negotiable guardrail in
`docs/XRIQ_LEGAL_RISK_REDUCTION.md` and `.github/copilot-instructions.md`: the
wallet/explorer UI must never generate, store, manage, or transmit private keys,
seed phrases, mnemonics, raw signatures, or any custody material.

## Scope

The React/TypeScript explorer-ui at `xriq/apps/explorer-ui/src/` (App, wallet,
admin, audit, iso, mempool, snapshots, api, main).

## Findings

The UI is safe by design:

- The wallet panel (`src/wallet.tsx`) only collects and transmits transfer
  fields: from/to address, amount, fee, nonce, and expiry height. It never
  asks for, derives, or holds a private key, seed phrase, or mnemonic.
- The default wallet flow is preview-only. The constant
  `private-devnet-preview-only-no-signing-no-submit` and the UI copy
  "Preview only. No signing or submission." / "No signing material." make the
  no-signing posture explicit.
- The optional local send path (behind the `VITE_XRIQ_ENABLE_LOCAL_WALLET_SEND_UI`
  feature switch) posts the same plain transfer fields to the local API, which
  performs test-only signing server-side. The browser performs no signing.
- No browser storage of key-like material: no `localStorage`, `sessionStorage`,
  `indexedDB`, or `document.cookie` usage anywhere in the UI source.
- No Web Crypto key generation (`crypto.subtle`, `generateKey`) and no
  client-side transaction signing.
- The accepted-mutation UI controls remain gated behind explicit Vite feature
  switches and matching local API flags; audit metadata policy requires
  "no signing material".

A source scan for key-material patterns returns zero matches; the only
`signing`/`signature` strings are negative assertions of absence.

## Enforcement

This is enforced automatically, not just reviewed once. A new guard,
`xriq/apps/explorer-ui/scripts/check-wallet-key-safety.mjs`, scans every UI
`.ts`/`.tsx` source file and fails the build if any forbidden pattern appears
(private/secret key, seed phrase, mnemonic, key pair, keystore, `crypto.subtle`,
`generateKey`, `localStorage`, `sessionStorage`, `indexedDB`, `document.cookie`,
raw signature, sign transaction). It also asserts the affirmative no-signing
safety markers remain present.

The guard runs as part of `npm run check` (and therefore the CI Explorer UI
job). Run it directly with:

```bash
cd xriq/apps/explorer-ui
npm run check:wallet-key-safety
```

## Follow-Ups

- If a future signed-transfer UI is ever proposed, it must keep signing
  server-side / CLI-only or go through a separate security and legal review
  before any browser-side key handling; this guard must be revisited at that
  time rather than relaxed silently.
