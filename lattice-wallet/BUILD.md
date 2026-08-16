# Building Lattice store binaries (EAS)

Lattice builds for iOS and Android through **EAS Build** (Expo's cloud build service).
The project is already build-ready — verified below — but the cloud build must be run
**from your own accounts**: EAS uploads the project to Expo's servers, signs it, and bills
your build quota, and iOS additionally requires your Apple Developer account. Those steps
need credentials that only you should enter.

## What's already done (verified in this repo)

- ✅ Production JS bundle compiles for **both** platforms (Hermes): `npm run bundle:check`
  (Android + iOS bundle to ~3.5 MB each, all crypto libs included, no missing polyfills).
- ✅ `npx expo-doctor` — 18/18 checks pass; dependency versions aligned to the Expo SDK.
- ✅ `eas.json` build profiles (development / preview / production) are committed.
- ✅ `app.json` has iOS `bundleIdentifier` and Android `package` (`app.lattice.wallet`),
  the biometric usage strings, icons, and splash.
- ✅ Full typecheck clean; 7 golden-vector test suites green (`npm run test:core`).

## Prerequisites (you provide)

1. A free **Expo account** — https://expo.dev.
2. **EAS CLI**: `npm i -g eas-cli` (or use `npx eas-cli`).
3. **Android**: nothing extra — EAS generates and stores the upload keystore for you.
4. **iOS**: an **Apple Developer Program** membership ($99/yr). EAS can create the
   signing certificate and provisioning profile for you during the build (it will prompt
   for your Apple ID), or you can supply them.

## One-time setup

```bash
cd lattice-wallet
npm install
eas login            # your Expo credentials — run this yourself
eas init             # links the project, writes extra.eas.projectId to app.json
```

## Dev build (WalletConnect, camera, and the handshake self-test)

WalletConnect (WalletKit) and the QR camera use native modules, so they **don't run in Expo
Go** — you need a **custom dev client**. Build one, then everything runs on-device:

```bash
eas build --platform android --profile development   # or: npx expo run:android  (local, needs Android SDK)
```

Install the resulting dev client, then `npm start` and open it. To verify WalletConnect works
end-to-end without an external dApp, go to **Settings → WalletConnect → Run handshake self-test**.
It runs a real dApp↔wallet handshake over the relay (throwaway key, no biometric), signs a
message, and checks the signature recovers — reporting each step ✓/✗. Needs a network connection.

## Build (store binaries)

Convenience scripts (in `package.json`) wrap the EAS commands:

```bash
# Android — installable APK for testing on a device
npm run build:android:preview

# Android — Play Store bundle (.aab)
npm run build:android

# iOS — App Store build (.ipa)  [needs Apple Developer membership]
npm run build:ios

# Both, production
npm run build:all
```

Each command uploads the project, builds in the cloud, and prints a URL to download the
artifact (and to watch progress). Android production yields an `.aab` for Google Play;
`preview` yields an `.apk` you can sideload.

## Submit to the stores (optional)

```bash
eas submit --platform android --latest   # needs a Google Play service-account key
eas submit --platform ios --latest        # needs App Store Connect API key / Apple ID
```

## Important before any public release

Lattice is **unaudited** and ships with a testnet/unaudited status banner (Settings →
Audit status). Ethereum, Bitcoin, Solana, and Zcash mainnets carry **real value**. Do not
present Lattice as production-safe custody, and expect Apple/Google crypto-wallet review
policies to apply, until an independent security audit and legal review are complete. See
the top of `README.md`.
