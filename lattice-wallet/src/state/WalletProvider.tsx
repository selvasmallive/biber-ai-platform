import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as keystore from '../core/keystore';
import { type HistoryEntry } from '../core/rpc';
import { newMnemonic, isValidMnemonic } from '../core/xriq';
import { CHAINS, DEFAULT_CHAIN_ID, getChainConfig, makeAdapter } from '../core/chains/registry';
import type { ChainAdapter, ChainConfig, TransferRequest } from '../core/chains/types';

type Status = 'loading' | 'no-wallet' | 'ready';

interface WalletState {
  status: Status;
  chains: ChainConfig[];
  activeChain: ChainConfig;
  activeAdapter: ChainAdapter;
  address: string | null; // active chain
  addresses: Record<string, string>; // all chains
  balance: bigint | null; // active chain, base units
  history: HistoryEntry[];
  online: boolean;
  refreshing: boolean;
  pqEnabled: boolean;

  createWallet: () => Promise<string>;
  importWallet: (mnemonic: string) => Promise<void>;
  refresh: () => Promise<void>;
  setActiveChain: (id: string) => Promise<void>;
  send: (req: TransferRequest) => Promise<{ hash: string }>;
  requestFaucet: () => Promise<void>;
  revealPhrase: () => Promise<string>;
  setPqEnabled: (on: boolean) => Promise<void>;
  wipe: () => Promise<void>;
}

const Ctx = createContext<WalletState | null>(null);

// Derive the public address for every supported chain from the mnemonic (addresses are
// non-secret and safe to persist for display without a biometric prompt).
function deriveAllAddresses(mnemonic: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const cfg of CHAINS) {
    try {
      out[cfg.id] = makeAdapter(cfg).deriveAccount(mnemonic).address;
    } catch {
      /* skip a chain that fails to derive */
    }
  }
  return out;
}

export function WalletProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<Status>('loading');
  const [addresses, setAddresses] = useState<Record<string, string>>({});
  const [activeChainId, setActiveChainId] = useState<string>(DEFAULT_CHAIN_ID);
  const [balance, setBalance] = useState<bigint | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [online, setOnline] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [pqEnabled, setPqEnabledState] = useState(false);

  const activeChain = useMemo(() => getChainConfig(activeChainId), [activeChainId]);
  const activeAdapter = useMemo(() => makeAdapter(activeChain), [activeChain]);
  const address = addresses[activeChainId] ?? null;

  useEffect(() => {
    (async () => {
      const meta = await keystore.getMeta();
      if (meta) {
        setAddresses(meta.addresses);
        setActiveChainId(meta.activeChainId ?? DEFAULT_CHAIN_ID);
        setPqEnabledState(meta.pqEnabled);
        setStatus('ready');
      } else {
        setStatus('no-wallet');
      }
    })();
  }, []);

  const refresh = useCallback(async () => {
    if (!address) return;
    setRefreshing(true);
    setBalance(null);
    setHistory([]);
    try {
      const [bal, hist] = await Promise.allSettled([
        activeAdapter.getBalance(address),
        activeAdapter.getHistory(address),
      ]);
      if (bal.status === 'fulfilled') {
        setBalance(bal.value);
        setOnline(true);
      } else {
        setOnline(false);
      }
      if (hist.status === 'fulfilled') setHistory(hist.value);
    } finally {
      setRefreshing(false);
    }
  }, [address, activeAdapter]);

  useEffect(() => {
    if (status === 'ready') refresh();
  }, [status, activeChainId, refresh]);

  const persistNewWallet = useCallback(async (mnemonic: string) => {
    const addrs = deriveAllAddresses(mnemonic);
    await keystore.storeMnemonic(mnemonic, {
      addresses: addrs,
      activeChainId: DEFAULT_CHAIN_ID,
      createdAt: Date.now(),
      pqEnabled: false,
    });
    setAddresses(addrs);
    setActiveChainId(DEFAULT_CHAIN_ID);
    setStatus('ready');
  }, []);

  const createWallet = useCallback(async () => {
    const mnemonic = newMnemonic(256);
    await persistNewWallet(mnemonic);
    return mnemonic;
  }, [persistNewWallet]);

  const importWallet = useCallback(
    async (mnemonic: string) => {
      const trimmed = mnemonic.trim().replace(/\s+/g, ' ');
      if (!isValidMnemonic(trimmed)) throw new Error('Invalid recovery phrase');
      await persistNewWallet(trimmed);
    },
    [persistNewWallet],
  );

  const setActiveChain = useCallback(async (id: string) => {
    setActiveChainId(id);
    const meta = await keystore.getMeta();
    if (meta) await keystore.setMeta({ ...meta, activeChainId: id });
  }, []);

  const send = useCallback(
    async (req: TransferRequest) => {
      const mnemonic = await keystore.unlockMnemonic('Confirm to sign transfer');
      const result = await activeAdapter.send(mnemonic, req);
      await refresh();
      return { hash: result.hash };
    },
    [activeAdapter, refresh],
  );

  const requestFaucet = useCallback(async () => {
    if (activeChain.family !== 'xriq') throw new Error('Faucet only available on XRIQ testnet');
    if (!address) throw new Error('No wallet');
    // XRIQ adapter exposes faucet via its rpc; reach it through a fresh adapter call.
    const { XriqRpc } = await import('../core/rpc');
    const rpc = new XriqRpc({
      key: activeChain.id,
      label: activeChain.name,
      chainId: 'xriq-devnet',
      rpcUrl: activeChain.rpcUrl,
      isTestnet: true,
      faucetEnabled: true,
    });
    await rpc.faucet(address);
    await refresh();
  }, [activeChain, address, refresh]);

  const revealPhrase = useCallback(() => keystore.revealMnemonic(), []);

  const setPqEnabled = useCallback(async (on: boolean) => {
    const meta = await keystore.getMeta();
    if (meta) await keystore.setMeta({ ...meta, pqEnabled: on });
    setPqEnabledState(on);
  }, []);

  const wipe = useCallback(async () => {
    await keystore.wipeWallet();
    setAddresses({});
    setBalance(null);
    setHistory([]);
    setStatus('no-wallet');
  }, []);

  const value: WalletState = {
    status,
    chains: CHAINS,
    activeChain,
    activeAdapter,
    address,
    addresses,
    balance,
    history,
    online,
    refreshing,
    pqEnabled,
    createWallet,
    importWallet,
    refresh,
    setActiveChain,
    send,
    requestFaucet,
    revealPhrase,
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
