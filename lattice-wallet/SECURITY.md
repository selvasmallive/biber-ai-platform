# Security notes — signing & WalletConnect

This records a security pass over Lattice's signing and WalletConnect (Reown WalletKit)
code, the fixes applied, and the residual risks that are accepted or deferred. It is **not**
a substitute for an independent third-party audit, which has not been performed.

Threat model: a malicious connected dApp; a spoofed/malicious signature or transaction
request; a malicious recipient or token contract; and physical access to the device.

## Verified correct

- **No silent signing.** Every signature — native send, token send, and every WalletConnect
  request — passes through `keystore.unlockMnemonic()` (biometric/passcode). See
  `WalletConnectProvider.approveRequest`.
- **`eth_sign` is not exposed.** It is absent from the advertised methods and rejected by the
  router, so a dApp cannot get a signature over a raw 32-byte hash (the classic
  "sign a login" → actually-a-transaction blind-sign attack).
- **`from` is ignored** in transaction building — Lattice always signs with its own key, so a
  dApp cannot induce signing "as" another account.
- **Signatures are canonical:** low-S (noble default), `v = 27 + recovery` for messages,
  EIP-155 `v` for legacy, y-parity for EIP-1559. EIP-191 and EIP-712 v4 hashing are verified
  against `ethers` in `__tests__/evm-sign-vectors.ts`.
- **Namespace scoping** via `buildApprovedNamespaces` — dApp requests for unsupported
  methods/chains are rejected, not silently granted.

## Fixed in this pass

| ID | Severity | Issue | Fix |
| -- | -------- | ----- | --- |
| H3 | High | Biometric gate **failed open** when the device had no biometrics/passcode enrolled — secrets were released with no user-presence check. | `keystore.authenticate` now **fails closed** (`getEnrolledLevelAsync() === NONE` ⇒ refuse), with device-passcode fallback enabled. Reveal/sign show a clear "set up a screen lock" error. |
| H1 | High | EIP-712 approval showed only `primaryType` — hiding `verifyingContract`, `chainId`, and message fields (permit-phishing / blind signing). | Approval modal now shows domain name / contract / chain id and the flattened message; warns on `Permit`-type requests. |
| H2 | High | `eth_sendTransaction` calldata was undecoded ("contract interaction") — hidden `approve(attacker, ∞)` etc. | Calldata is decoded for `approve` / `increaseAllowance` / `setApprovalForAll` / `transfer`; **unlimited allowances and blanket NFT approvals are flagged in red**; unknown calls warn explicitly. |
| M1 | Medium | Displayed network could differ from the chain a typed-data signature is actually bound to. | The EIP-712 `domain.chainId` is shown and **warned** when it differs from the connected chain. |
| L1 | Low | No fee disclosure on `eth_sendTransaction`. | Max fee/gas (gwei) is shown when the dApp supplies it. |
| L2 | Low | App router trusted the SDK for topic/method/chain. | Defense-in-depth: request must belong to an active session, use an allowed method, and target a supported chain. |
| L4 | Low | Malformed `value` could crash the approval sheet. | Decoding is wrapped in try/catch; malformed input degrades to a warning. |

## Accepted / deferred residual risks

- **M2 — `eth_signTypedData` (v3) uses v4 encoding.** v3 and v4 share JSON shape but differ
  on array/nested encoding, so a genuine v3 request could hash differently than a v3-aware
  peer expects. Impact is a *mismatched/failed* signature, not fund loss; the approval screen
  now shows the actual data. Most dApps use v4. Revisit if v3 dApps appear.
- **Key material is not zeroed after use.** JavaScript/Hermes cannot reliably wipe memory.
  Mitigated by hardware-backed storage (`expo-secure-store`), on-demand derivation, and never
  logging secrets.
- **Transaction simulation is Phase 1 only.** Before signing, Lattice statically decodes
  common drain selectors (approve / setApprovalForAll / transfer, with unlimited-allowance
  flagged) and **dry-runs the transaction via `eth_call` on your own RPC** to catch reverts and
  show the revert reason (`src/core/simulate.ts`). It does **not** yet compute full asset-change
  diffs (Phase 2, needs a trace-capable RPC) or use a third-party risk API (Phase 3, opt-in).
  Unknown contract calls are still surfaced with an explicit "only approve if you trust this
  dApp" warning. All of Phase 1 uses your own RPC — no third party.
- **Live WalletConnect pairing is not covered by CI** — it requires a dev/EAS build and a real
  dApp. The signing paths it invokes are vector-verified; the handshake should be exercised
  manually before release.
