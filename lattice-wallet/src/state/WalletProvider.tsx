import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { NETWORKS, DEFAULT_NETWORK_KEY, type NetworkConfig } from '../core/config';
import * as keystore from '../core/keystore';
import { XriqRpc, type AccountInfo, type HistoryEntry, type NetworkInfo } from '../core/rpc';
import {
  keypairFromMnemonic,
  newMnemonic,
  isValidMnemonic,
  signTransfer,
  DEFAULT_PATH,
  hex,
  type XriqTransaction,
} from '../core/xriq';
import { pqKeypairFromMnemonic, hybridSign } from '../core/pq';

type Status = 'loading' | 'no-wallet' | 'ready';

interface SendParams {
  to: string;
  amountBaseUnits: bigint;
  feeBaseUnits: bigint;
}

interface WalletState {
  status: Status;
  address: string | null;
  network: NetworkConfig;
  account: AccountInfo | null;
  history: HistoryEntry[];
  networkInfo: NetworkInfo | null;
  online: boolean;
  refreshing: boolean;
  pqEnabled: boolean;

  createWallet: () => Promise<string>; // returns mnemonic for one-time backup
  importWallet: (mnemonic: string) => Promise<void>;
  refresh: () => Promise<void>;
  send: (p: SendParams) => Promise<{ transactionHash: string; response: unknown }>;
  requestFaucet: () => Promise<void>;
  revealPhrase: () => Promise<string>;
  setNetworkKey: (key: string) => void;
  setPqEnabled: (on: boolean) => Promise<void>;
  wipe: () => Promise<void>;
}

const Ctx = createContext<WalletState | null>(null);

const DERIVATION_PATH_LABEL = "m/44'/1'/0'/0'/0'";

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>('loading');
  const [address, setAddress] = useState<string | null>(null);
  const [networkKey, setNetworkKey] = useState<string>(DEFAULT_NETWORK_KEY);
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [networkInfo, setNetworkInfo] = useState<NetworkInfo | null>(null);
  const [online, setOnline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [pqEnabled, setPqEnabledState] = useState(false);

  const network = NETWORKS[networkKey] ?? NETWORKS[DEFAULT_NETWORK_KEY];
  const rpc = useMemo(() => new XriqRpc(network), [network]);

  const bootstrap = useCallback(async () => {
    const meta = await keystore.getMeta();
    if (meta) {
      setAddress(meta.address);
      setPqEnabledState(meta.pqEnabled);
      setStatus('ready');
    } else {
      setStatus('no-wallet');
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const refresh = useCallback(async () => {
    if (!address) return;
    setRefreshing(true);
    try {
      const healthy = await rpc.health();
      setOnline(healthy);
      const [acct, hist, net] = await Promise.allSettled([
        rpc.getAccount(address),
        rpc.getHistory(address),
        rpc.getNetwork(),
      ]);
      if (acct.status === 'fulfilled') setAccount(acct.value);
      if (hist.status === 'fulfilled') setHistory(hist.value);
      if (net.status === 'fulfilled') setNetworkInfo(net.value);
    } finally {
      setRefreshing(false);
    }
  }, [address, rpc]);

  useEffect(() => {
    if (status === 'ready') refresh();
  }, [status, refresh]);

  const createWallet = useCallback(async () => {
    const mnemonic = newMnemonic(256);
    const kp = keypairFromMnemonic(mnemonic);
    await keystore.storeMnemonic(mnemonic, {
      address: kp.address,
      createdAt: Date.now(),
      derivationPath: DERIVATION_PATH_LABEL,
      pqEnabled: false,
    });
    setAddress(kp.address);
    setStatus('ready');
    return mnemonic;
  }, []);

  const importWallet = useCallback(async (mnemonic: string) => {
    const trimmed = mnemonic.trim().replace(/\s+/g, ' ');
    if (!isValidMnemonic(trimmed)) throw new Error('Invalid recovery phrase');
    const kp = keypairFromMnemonic(trimmed);
    await keystore.storeMnemonic(trimmed, {
      address: kp.address,
      createdAt: Date.now(),
      derivationPath: DERIVATION_PATH_LABEL,
      pqEnabled: false,
    });
    setAddress(kp.address);
    setStatus('ready');
  }, []);

  const send = useCallback(
    async ({ to, amountBaseUnits, feeBaseUnits }: SendParams) => {
      if (!address) throw new Error('No wallet');
      // Always read the authoritative nonce from the chain right before signing.
      const acct = await rpc.getAccount(address);
      const mnemonic = await keystore.unlockMnemonic('Confirm to sign transfer');
      const kp = keypairFromMnemonic(mnemonic, DEFAULT_PATH);
      const tx: XriqTransaction = {
        version: 1,
        chainId: network.chainId,
        from: address,
        to: to.trim(),
        amountBaseUnits,
        feeBaseUnits,
        nonce: acct.nonce,
        memoHash: null,
        expiresAtHeight: null,
        publicKey: kp.publicKey,
      };
      const signed = signTransfer(tx, kp.privateSeed);
      // Forward-compatible: when PQ is enabled, produce a real hybrid signature too.
      // The chain currently verifies the Ed25519 leg; the hybrid is retained for the
      // PQ migration and offline verification.
      if (pqEnabled) {
        const pq = pqKeypairFromMnemonic(mnemonic, DEFAULT_PATH);
        hybridSign(signed.signingHash, kp.privateSeed, pq);
      }
      const response = await rpc.submitSigned(tx, signed);
      await refresh();
      return {
        transactionHash: hex.toHex(signed.transactionHash),
        response,
      };
    },
    [address, rpc, network.chainId, pqEnabled, refresh],
  );

  const requestFaucet = useCallback(async () => {
    if (!address) throw new Error('No wallet');
    await rpc.faucet(address);
    await refresh();
  }, [address, rpc, refresh]);

  const revealPhrase = useCallback(() => keystore.revealMnemonic(), []);

  const setPqEnabled = useCallback(async (on: boolean) => {
    const meta = await keystore.getMeta();
    if (meta) await keystore.setMeta({ ...meta, pqEnabled: on });
    setPqEnabledState(on);
  }, []);

  const wipe = useCallback(async () => {
    await keystore.wipeWallet();
    setAddress(null);
    setAccount(null);
    setHistory([]);
    setStatus('no-wallet');
  }, []);

  const value: WalletState = {
    status,
    address,
    network,
    account,
    history,
    networkInfo,
    online,
    refreshing,
    pqEnabled,
    createWallet,
    importWallet,
    refresh,
    send,
    requestFaucet,
    revealPhrase,
    setNetworkKey,
    setPqEnabled,
    wipe,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWallet(): WalletState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useWallet must be used within WalletProvider');
  return ctx;
}
