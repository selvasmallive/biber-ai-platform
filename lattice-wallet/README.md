# Lattice

A non-custodial, **multi-chain** mobile wallet built with Expo / React Native so one
codebase ships to **both iOS and Android**. One recovery phrase derives an account on
every supported chain. Keys are generated and transactions are signed **on the device**;
only public keys and signatures ever reach a node.

The name nods to the lattice-based mathematics behind the post-quantum signature scheme
the wallet produces on XRIQ (ML-DSA / CRYSTALS-Dilithium).

## Supported chains

| Chain | Status | Signing | Address | Proven against |
| --- | --- | --- | --- | --- |
| **XRIQ** (devnet) | ✅ send/receive | Ed25519 | `xriqdev1…` | Rust chain golden vectors |
| **Ethereum + EVM** (Polygon, Base, Sepolia) | ✅ send/receive | secp256k1 | EIP-55 `0x…` | EIP-155 / EIP-55 golden vectors |
| **Bitcoin** | ✅ send/receive | secp256k1 (P2WPKH) | bech32 `bc1q…` | BIP84 golden addresses; `@scure/btc-signer` |
| **Solana** | ✅ send/receive | Ed25519 | base58 | derivation + tx bytes vs `@solana/web3.js` |
| **Zcash (transparent)** | ✅ send/receive | secp256k1 | `t1…` | ZIP-244 txid + sighash vs official zcash-test-vectors |
| Monero, shielded Zcash | ⛔ out of scope | ring sig / zk-SNARK | — | see below |

**Transparent Zcash spend** uses Zcash's own v5 (NU5) transaction digest — the full
ZIP-244 algorithm including the Sapling and Orchard sub-digests — implemented in
`src/core/chains/zcashTx.ts` and **verified byte-for-byte against the official
[zcash-test-vectors](https://github.com/zcash/zcash-test-vectors)** (10/10 txids, 6/6
transparent sighashes; see `__tests__/zec-sighash-vectors.ts`). Balance, history, and
broadcast use the public **Blockchair** Zcash API (`https://api.blockchair.com/zcash`) —
there is no public Esplora instance for Zcash; the free tier is rate-limited, so point
`rpcUrl` at a self-hosted node or keyed endpoint at scale. Only transparent (t-address)
funds are supported; shielded (z-address) is out of scope below.

Adding a chain is a `ChainAdapter` (`src/core/chains/`) plus one line in the registry —
the wallet shell, keystore, biometrics, PQ, and UI are chain-agnostic.

**Why Monero and shielded Zcash are out of scope:** their privacy cryptography (Monero's
ring signatures + RingCT + on-device output scanning; Zcash's zk-SNARK proving) has no
safe, practical pure-JavaScript implementation for React Native today — real support means
embedding large C++/WASM proving libraries. A subtly-wrong privacy-coin wallet loses funds
irreversibly, so these are deferred to a dedicated effort rather than shipped half-built.

> ## ⚠️ Status: testnet · unaudited
> XRIQ has **not** completed an independent third-party security audit or legal review.
> This wallet targets the XRIQ **test network**. Do not store real value in it. The audit
> and legal-review status is surfaced honestly inside the app (Settings → Audit status)
> and cannot be marked complete from a code change — only from a real external report.
> The **AGNA** decentralized exchange is still under development; the in-app Swap screen is
> wired to a pluggable interface and shows a "coming online" state rather than simulating
> trades.

---

## What works today

- **Non-custodial key management** — BIP39 recovery phrase (24 words), SLIP-0010 Ed25519
  HD derivation, hardware-backed storage (iOS Keychain / Android Keystore via
  `expo-secure-store`), biometric / passcode gate on every reveal and signature
  (`expo-local-authentication`).
- **Byte-exact XRIQ protocol** — address derivation, canonical transaction encoding,
  signing hash, and Ed25519 signatures reproduce the Rust chain **exactly** (see
  Conformance below).
- **Send / Receive / History** — build, review, biometric-sign, and submit transfers via
  the node's non-custodial `POST /api/v1/wallet/transfers/submit-signed` endpoint; QR
  receive; on-chain activity list; testnet faucet.
- **Real post-quantum signing** — ML-DSA-65 (FIPS 204) keys derived from the same
  mnemonic, producing a hybrid (Ed25519 + ML-DSA) signature tagged to XRIQ's reserved
  on-chain algorithm id **250**. Toggle in Settings. Enabling it never lowers present
  security: the chain still verifies the classical leg today, and the PQ leg is carried
  forward for when XRIQ wires id-250 verification.

## Privacy-first wallet features

Everything here is designed so the wallet reveals as little as possible about you:

- **Privacy-first history (default).** Lattice keeps a **local, on-device activity log** of
  transactions you send, and offers **"view full history on explorer"** deep links — it
  never sends your address to a history indexer by default. Full indexer history is an
  explicit opt-in (Settings → Privacy). Rationale: every indexer lookup leaks your address
  to that provider.
- **ERC-20 tokens, added by contract address.** No third-party token-discovery service —
  you paste a contract, metadata is read from *your* RPC, and balances/transfers use your
  RPC too. Sends show a human-readable "you are sending X TOKEN to …" preview before signing.
- **ENS resolution** — `name.eth` resolves fully on-chain via your own RPC (no name service),
  verified against the EIP-137 namehash vectors.
- **Local address book** — contacts stored only on-device; send by name to defend against
  clipboard/paste address-swap attacks.
- **Custom RPC per chain** — point any chain at your own node so no third party sees your
  queries (Settings → Privacy).

## Architecture

```
src/core/        protocol + security (unit-testable, no UI)
  chains/        multi-chain seam
    types.ts     ChainAdapter interface (derive/validate/balance/history/send)
    registry.ts  supported chains + adapter factory
    xriqAdapter.ts  XRIQ over the Rust-conformant core
    evm.ts       Ethereum + EVM (secp256k1, keccak, RLP, EIP-1559 + EIP-155)
    bitcoin.ts   Bitcoin BIP84 P2WPKH (@scure/btc-signer, Esplora backend)
    solana.ts    Solana Ed25519 + hand-rolled transfer message (web3.js-verified)
    zcash.ts     Zcash transparent t-addr adapter (derive/balance/history/send)
    zcashTx.ts   Zcash v5/NU5 ZIP-244 digest + transparent signer (vector-verified)
  xriq.ts        canonical encoding, address derivation, tx signing, submit envelope
  pq.ts          ML-DSA-65 hybrid post-quantum signing (algorithm id 250)
  keystore.ts    hardware-backed secret storage + biometric gate (the only secret sink)
  rpc.ts         XRIQ HTTP API client (accounts, history, faucet, submit-signed)
  agna.ts        AGNA DEX interface (pluggable; null until the exchange API ships)
  config.ts      symbols, honest security status
  format.ts      base-unit <-> human amount
src/state/       WalletProvider — coordinates keystore + rpc + signing
src/screens/     Onboarding, Backup, Import, Home, Send, Receive, History, Swap, Settings
src/components/  shared UI primitives
__tests__/       conformance harness + cross-language Rust golden vectors
```

Design rule: **all secret material flows through `keystore.ts`**. Private keys and the
mnemonic are derived on demand, never logged, never sent over the network.

## Conformance — proven against the real chain

The wallet's crypto core is cross-checked against goldens generated by the actual Rust
code (`xriq/crates/xriq-core` + `xriq-crypto`) for a fixed seed and transaction:

| Value          | Source of truth                    | Result |
| -------------- | ---------------------------------- | ------ |
| Address (zero key) | `xriq-crypto` `ED25519_ADDRESS_GOLDEN` | ✅ match |
| Public key, address | Rust `ed25519_address` | ✅ match |
| Transaction signing hash | Rust `transaction_signing_hash` | ✅ match |
| Ed25519 signature | Rust `SchemeSigner::sign_transaction` | ✅ match |
| Transaction hash | Rust `transaction_hash` | ✅ match |

Run the checks (Node only, no device needed):

```bash
npm install
npm run test:core
```

## Run the app

Prerequisites: Node 18+, the [Expo](https://docs.expo.dev/) tooling, and the **Expo Go**
app on your phone (or an iOS Simulator / Android Emulator).

```bash
npm install
npm start
```

Scan the QR code with Expo Go (Android) or the Camera app (iOS). Point the wallet at a
running XRIQ node by editing `rpcUrl` in `src/core/config.ts` or switching networks in
Settings. Start a local node from the `xriq/` workspace and use the **XRIQ Devnet (local)**
network (default `http://127.0.0.1:8080`).

## Build store binaries

Signed iOS/Android builds are produced with EAS (requires an Expo account and, for iOS,
Apple Developer enrollment):

```bash
npm install -g eas-cli
eas build --platform android
eas build --platform ios
```

Note: publishing to the App Store / Google Play requires passing each store's crypto-wallet
review policy, and — before this should be represented as anything beyond testnet software —
the XRIQ security audit and legal review noted above.

## Security posture

- Non-custodial: keys never leave the device; the server is send-only for signed payloads.
- Hardware-backed secret storage, biometric gate on reveal and signing.
- Audited primitives: `@noble/curves` (Ed25519), `@noble/hashes` (SHA-256/512, HKDF, HMAC),
  `@noble/post-quantum` (ML-DSA-65), `@scure/bip39`.
- Deterministic derivation; nonce is read from chain state immediately before signing.
- **Not** a substitute for an independent audit. See the status banner above.

## Roadmap — deferred, with reasons

Kept out of this build deliberately. Some need *your* accounts/keys; some conflict with the
privacy-first stance; some can't be done safely in a pure-JS/React-Native app.

- **WalletConnect v2 (dApp connect)** — needs a WalletConnect Cloud project id (your account).
- **Fiat on-ramp & in-app swaps** — third-party KYC / order-flow that leaks data; not
  privacy-first. (AGNA swap remains wired but pending its API.)
- **Push notifications / price alerts** — a server would have to watch your addresses, which
  is exactly the privacy leak the history design avoids.
- **Ledger hardware wallet** — large native BLE/HID integration.
- **Multiple accounts per chain** — a focused cross-adapter derivation-index change; safe to
  add on its own.
- **SPL token sends & NFTs** — SPL needs associated-token-account logic; NFT discovery needs
  an indexer (privacy leak).
- **Shielded Zcash (z-address)** — requires zk-SNARK proving (`librustzcash`); there is no
  pure-JS prover and Hermes has no WASM. The correct path is a native Zcash light-client SDK
  module, which is a separate project. Transparent ZEC is fully supported.
