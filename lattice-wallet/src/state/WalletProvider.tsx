import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import * as keystore from '../core/keystore';
import { type HistoryEntry } from '../core/rpc';
import { newMnemonic, isValidMnemonic } from '../core/xriq';
import { CHAINS, DEFAULT_CHAIN_ID, getChainConfig, makeAdapter } from '../core/chains/registry';
import { EvmAdapter } from '../core/chains/evm';
import type { ChainAdapter, ChainConfig, TransferRequest } from '../core/chains/types';
import { effectiveConfig, loadRpcOverrides, setRpcOverride as persistRpcOverride, type RpcOverrides } from '../core/rpcSettings';
import { recordActivity } from '../core/activityLog';
import { resolveEns, isEnsName } from '../core/ens';
import { formatUnits } from '../core/format';
import type { Token } from '../core/tokens';

type Status = 'loading' | 'no-wallet' | 'ready';
export type HistoryMode = 'basic' | 'indexer';

interface WalletState {
  status: Status;
  chains: ChainConfig[];
  activeChain: ChainConfig;
  activeAdapter: ChainAdapter;
  address: string | null;
  addresses: Record<string, string>;
  balance: bigint | null;
  history: HistoryEntry[];
  online: boolean;
  refreshing: boolean;
  pqEnabled: boolean;
  historyMode: HistoryMode;
  rpcOverrides: RpcOverrides;

  createWallet: () => Promise<string>;
  importWallet: (mnemonic: string) => Promise<void>;
  refresh: () => Promise<void>;
  setActiveChain: (id: string) => Promise<void>;
  send: (req: TransferRequest, displayAmount?: string) => Promise<{ hash: string }>;
  sendToken: (token: Token, to: string, amountBaseUnits: bigint, displayAmount: string) => Promise<{ hash: string }>;
  getTokenBalance: (token: Token) => Promise<bigint>;
  fetchTokenMeta: (address: string) => Promise<{ symbol: string; decimals: number; name: string }>;
  resolveName: (input: string) => Promise<string | null>;
  requestFaucet: () => Promise<void>;
  revealPhrase: () => Promise<string>;
  setPqEnabled: (on: boolean) => Promise<void>;
  setHistoryMode: (mode: HistoryMode) => Promise<void>;
  setRpcOverride: (chainId: string, url: string) => Promise<void>;
  wipe: () => Promise<void>;
}

const Ctx = createContext<WalletState | null>(null);

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
  const [historyMode, setHistoryModeState] = useState<HistoryMode>('basic');
  const [rpcOverrides, setRpcOverrides] = useState<RpcOverrides>({});

  const activeChain = useMemo(() => effectiveConfig(activeChainId, rpcOverrides), [activeChainId, rpcOverrides]);
  const activeAdapter = useMemo(() => makeAdapter(activeChain), [activeChain]);
  const address = addresses[activeChainId] ?? null;

  useEffect(() => {
    (async () => {
      const [meta, overrides] = await Promise.all([keystore.getMeta(), loadRpcOverrides()]);
      setRpcOverrides(overrides);
      if (meta) {
        setAddresses(meta.addresses);
        setActiveChainId(meta.activeChainId ?? DEFAULT_CHAIN_ID);
        setPqEnabledState(meta.pqEnabled);
        setHistoryModeState(meta.historyMode ?? 'basic');
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
      const balP = activeAdapter.getBalance(address);
      // Only touch a remote indexer for history when the user has opted in. The
      // privacy-first default keeps history to the local activity log + explorer links.
      const histP = historyMode === 'indexer' ? activeAdapter.getHistory(address) : Promise.resolve([]);
      const [bal, hist] = await Promise.allSettled([balP, histP]);
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
  }, [address, activeAdapter, historyMode]);

  useEffect(() => {
    if (status === 'ready') refresh();
  }, [status, activeChainId, historyMode, refresh]);

  const persistNewWallet = useCallback(async (mnemonic: string) => {
    const addrs = deriveAllAddresses(mnemonic);
    await keystore.storeMnemonic(mnemonic, {
      addresses: addrs,
      activeChainId: DEFAULT_CHAIN_ID,
      createdAt: Date.now(),
      pqEnabled: false,
      historyMode: 'basic',
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
    async (req: TransferRequest, displayAmount?: string) => {
      const mnemonic = await keystore.unlockMnemonic('Confirm to sign transfer');
      const result = await activeAdapter.send(mnemonic, req);
      await recordActivity({
        chainId: activeChainId,
        hash: result.hash,
        to: req.to,
        amount: displayAmount ?? `${formatUnits(req.amountBaseUnits, activeChain.decimals)} ${activeChain.symbol}`,
        timestamp: Date.now(),
        kind: 'send',
      });
      await refresh();
      return { hash: result.hash };
    },
    [activeAdapter, activeChainId, activeChain, refresh],
  );

  const sendToken = useCallback(
    async (token: Token, to: string, amountBaseUnits: bigint, displayAmount: string) => {
      if (activeChain.family !== 'evm') throw new Error('Token sends are supported on EVM chains');
      const mnemonic = await keystore.unlockMnemonic('Confirm to sign token transfer');
      const evm = activeAdapter as EvmAdapter;
      const result = await evm.sendErc20(mnemonic, token.address, to, amountBaseUnits);
      await recordActivity({
        chainId: activeChainId,
        hash: result.hash,
        to,
        amount: `${displayAmount} ${token.symbol}`,
        timestamp: Date.now(),
        kind: 'token-send',
        tokenSymbol: token.symbol,
      });
      await refresh();
      return { hash: result.hash };
    },
    [activeAdapter, activeChain, activeChainId, refresh],
  );

  const getTokenBalance = useCallback(
    async (token: Token) => {
      if (!address || activeChain.family !== 'evm') return 0n;
      return (activeAdapter as EvmAdapter).getErc20Balance(token.address, address);
    },
    [activeAdapter, activeChain, address],
  );

  const fetchTokenMeta = useCallback(
    async (tokenAddress: string) => {
      if (activeChain.family !== 'evm') throw new Error('Tokens are EVM-only for now');
      return (activeAdapter as EvmAdapter).fetchErc20Metadata(tokenAddress);
    },
    [activeAdapter, activeChain],
  );

  const resolveName = useCallback(
    async (input: string) => {
      const v = input.trim();
      if (!isEnsName(v)) return null;
      // ENS lives on Ethereum mainnet — resolve there regardless of the active chain.
      const ethCfg = effectiveConfig('ethereum', rpcOverrides);
      return resolveEns(ethCfg.rpcUrl, v);
    },
    [rpcOverrides],
  );

  const requestFaucet = useCallback(async () => {
    if (activeChain.family !== 'xriq') throw new Error('Faucet only available on XRIQ testnet');
    if (!address) throw new Error('No wallet');
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

  const setHistoryMode = useCallback(async (mode: HistoryMode) => {
    setHistoryModeState(mode);
    const meta = await keystore.getMeta();
    if (meta) await keystore.setMeta({ ...meta, historyMode: mode });
  }, []);

  const setRpcOverride = useCallback(async (chainId: string, url: string) => {
    const next = await persistRpcOverride(chainId, url);
    setRpcOverrides(next);
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
    historyMode,
    rpcOverrides,
    createWallet,
    importWallet,
    refresh,
    setActiveChain,
    send,
    sendToken,
    getTokenBalance,
    fetchTokenMeta,
    resolveName,
    requestFaucet,
    revealPhrase,
    setPqEnabled,
    setHistoryMode,
    setRpcOverride,
    wipe,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWallet(): WalletState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useWallet must be used within WalletProvider');
  return ctx;
}
