// Secure, non-custodial key storage.
//
// The recovery phrase is stored ONLY in the platform hardware-backed secure store
// (iOS Keychain / Android Keystore, via expo-secure-store) and is released only after
// a device biometric / passcode check (expo-local-authentication). The seed and
// private keys are derived on demand and never persisted in plaintext, never logged,
// and never sent anywhere. This module is the single choke point for secret material.
import * as SecureStore from 'expo-secure-store';
import * as LocalAuthentication from 'expo-local-authentication';

const MNEMONIC_KEY = 'lattice.mnemonic.v1';
const META_KEY = 'lattice.meta.v1';

export interface WalletMeta {
  /** Public receive addresses per chain id (non-secret; safe to persist for display). */
  addresses: Record<string, string>;
  activeChainId: string;
  createdAt: number;
  pqEnabled: boolean;
  /** 'basic' = privacy-first (local activity + explorer links); 'indexer' = opt-in remote history. */
  historyMode?: 'basic' | 'indexer';
}

const secureOptions: SecureStore.SecureStoreOptions = {
  keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY,
};

export async function hasWallet(): Promise<boolean> {
  const meta = await SecureStore.getItemAsync(META_KEY, secureOptions);
  return meta !== null;
}

export async function getMeta(): Promise<WalletMeta | null> {
  const raw = await SecureStore.getItemAsync(META_KEY, secureOptions);
  return raw ? (JSON.parse(raw) as WalletMeta) : null;
}

export async function setMeta(meta: WalletMeta): Promise<void> {
  await SecureStore.setItemAsync(META_KEY, JSON.stringify(meta), secureOptions);
}

/** Persist the recovery phrase to the hardware-backed store (call once at setup). */
export async function storeMnemonic(mnemonic: string, meta: WalletMeta): Promise<void> {
  await SecureStore.setItemAsync(MNEMONIC_KEY, mnemonic.trim(), secureOptions);
  await setMeta(meta);
}

export interface BiometricResult {
  ok: boolean;
  reason?: string;
}

const NO_DEVICE_SECURITY_MESSAGE =
  'Set up a screen lock (biometrics or passcode) on your device to protect your wallet. ' +
  'Lattice will not sign or reveal your recovery phrase without it.';

/**
 * Require a device biometric / passcode confirmation before releasing secrets.
 *
 * FAIL CLOSED: if the device has no lock at all (no biometrics AND no passcode), we
 * refuse rather than releasing secrets with no user-presence check. `disableDeviceFallback`
 * is false, so a passcode-only device still authenticates via the OS passcode prompt.
 */
export async function authenticate(prompt = 'Unlock Lattice'): Promise<BiometricResult> {
  const level = await LocalAuthentication.getEnrolledLevelAsync();
  if (level === LocalAuthentication.SecurityLevel.NONE) {
    return { ok: false, reason: 'no-device-security' };
  }
  const res = await LocalAuthentication.authenticateAsync({
    promptMessage: prompt,
    disableDeviceFallback: false,
    cancelLabel: 'Cancel',
  });
  return { ok: res.success, reason: res.success ? undefined : (res as any).error };
}

function authError(auth: BiometricResult): Error {
  return new Error(auth.reason === 'no-device-security' ? NO_DEVICE_SECURITY_MESSAGE : 'Authentication failed');
}

/**
 * Reveal the recovery phrase after a fresh biometric check. The returned string is
 * sensitive — callers must not persist, log, or transmit it.
 */
export async function revealMnemonic(): Promise<string> {
  const auth = await authenticate('Reveal recovery phrase');
  if (!auth.ok) throw authError(auth);
  const mnemonic = await SecureStore.getItemAsync(MNEMONIC_KEY, secureOptions);
  if (!mnemonic) throw new Error('No wallet found');
  return mnemonic;
}

/**
 * Load the mnemonic for signing after a biometric check. Kept separate from
 * revealMnemonic so the prompt copy matches the action.
 */
export async function unlockMnemonic(prompt = 'Confirm to sign'): Promise<string> {
  const auth = await authenticate(prompt);
  if (!auth.ok) throw authError(auth);
  const mnemonic = await SecureStore.getItemAsync(MNEMONIC_KEY, secureOptions);
  if (!mnemonic) throw new Error('No wallet found');
  return mnemonic;
}

/** Wipe all wallet material from the device. Irreversible without the backup phrase. */
export async function wipeWallet(): Promise<void> {
  await SecureStore.deleteItemAsync(MNEMONIC_KEY, secureOptions);
  await SecureStore.deleteItemAsync(META_KEY, secureOptions);
}
