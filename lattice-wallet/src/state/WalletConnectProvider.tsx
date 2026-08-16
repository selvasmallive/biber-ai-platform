// WalletConnect (Reown WalletKit) integration — lets dApps connect to Lattice and request
// EVM signatures/transactions, which are routed to the on-device signer (verified in
// __tests__/evm-sign-vectors.ts) behind biometric approval.
//
// STATUS: the signing paths are verified; the pairing/session handshake requires a custom
// dev/EAS build (WalletKit has native deps and does not run in Expo Go) and a real dApp to
// test end-to-end. The code compiles and bundles; live pairing is untested from CI.
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import * as Linking from 'expo-linking';
import { WalletKit, type IWalletKit } from '@reown/walletkit';
import { Core } from '@walletconnect/core';
import { buildApprovedNamespaces, getSdkError } from '@walletconnect/utils';
import { WALLETCONNECT_METADATA, WALLETCONNECT_PROJECT_ID } from '../core/config';
import { EVM_CHAINS } from '../core/chains/registry';
import { EvmAdapter, deriveEvmKey } from '../core/chains/evm';
import { personalSign, signTypedDataV4, type TypedData } from '../core/chains/evmSign';
import { resolveEvmConfig, parseAddChainParams } from '../core/chains/wcChains';
import { fetchChainId } from '../core/chains/evmRpc';
import { extractWcUri } from '../core/deeplink';
import { useWallet } from './WalletProvider';
import * as keystore from '../core/keystore';
import type { ChainConfig } from '../core/chains/types';

const EVM_METHODS = [
  'eth_sendTransaction', 'personal_sign', 'eth_signTypedData', 'eth_signTypedData_v4',
  'wallet_switchEthereumChain', 'wallet_addEthereumChain',
];
const EVM_EVENTS = ['chainChanged', 'accountsChanged'];

export interface WcSession { topic: string; name: string; url: string; icon?: string; }
export interface WcAddChainRequest { event: any; config: ChainConfig; }

interface WcState {
  ready: boolean;
  sessions: WcSession[];
  proposal: any | null;
  request: any | null;
  addChainRequest: WcAddChainRequest | null;
  busy: boolean;
  error: string | null;
  pair: (uri: string) => Promise<void>;
  approveProposal: () => Promise<void>;
  rejectProposal: () => Promise<void>;
  approveRequest: () => Promise<void>;
  rejectRequest: () => Promise<void>;
  approveAddChain: () => Promise<void>;
  rejectAddChain: () => Promise<void>;
  disconnect: (topic: string) => Promise<void>;
  clearError: () => void;
}

// EIP-3326 wallet_switchEthereumChain — a chain-switch acknowledgement, not a signature.
// Succeed for chains Lattice supports (built-in or custom); else 4902.
async function handleSwitchChain(kit: IWalletKit, event: any, custom: ChainConfig[]): Promise<void> {
  const { topic, id } = event;
  const requested: string | undefined = event?.params?.request?.params?.[0]?.chainId;
  let num = NaN;
  try { if (requested) num = Number(BigInt(requested)); } catch { /* invalid hex */ }
  const cfg = Number.isFinite(num) ? resolveEvmConfig(num, custom) : null;
  try {
    if (cfg) {
      await kit.respondSessionRequest({ topic, response: { id, jsonrpc: '2.0', result: null } });
      try { await kit.emitSessionEvent({ topic, event: { name: 'chainChanged', data: num }, chainId: `eip155:${num}` }); } catch { /* best-effort */ }
    } else {
      await kit.respondSessionRequest({ topic, response: { id, jsonrpc: '2.0', error: { code: 4902, message: `Unrecognized chain id ${requested ?? ''}`.trim() } } });
    }
  } catch { /* respond failure is non-fatal */ }
}

// EIP-3085 wallet_addEthereumChain — if already known, succeed silently; otherwise surface a
// confirmation to the user (adding a dApp-supplied RPC is security-sensitive).
async function handleAddChain(
  kit: IWalletKit,
  event: any,
  custom: ChainConfig[],
  present: (r: WcAddChainRequest) => void,
): Promise<void> {
  const config = parseAddChainParams(event?.params?.request?.params?.[0]);
  if (!config) {
    try {
      await kit.respondSessionRequest({ topic: event.topic, response: { id: event.id, jsonrpc: '2.0', error: { code: 4902, message: 'Invalid chain parameters' } } });
    } catch { /* ignore */ }
    return;
  }
  if (config.evmChainId != null && resolveEvmConfig(config.evmChainId, custom)) {
    try { await kit.respondSessionRequest({ topic: event.topic, response: { id: event.id, jsonrpc: '2.0', result: null } }); } catch { /* ignore */ }
    return;
  }
  present({ event, config });
}

const Ctx = createContext<WcState | null>(null);

export function WalletConnectProvider({ children }: { children: React.ReactNode }) {
  const kitRef = useRef<IWalletKit | null>(null);
  const [ready, setReady] = useState(false);
  const [sessions, setSessions] = useState<WcSession[]>([]);
  const [proposal, setProposal] = useState<any | null>(null);
  const [request, setRequest] = useState<any | null>(null);
  const [addChainRequest, setAddChainRequest] = useState<WcAddChainRequest | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Custom EVM chains are owned by WalletProvider (single source of truth). Mirror them into
  // a ref so the SDK event handlers always read the current list synchronously.
  const { customChains, addCustomNetwork } = useWallet();
  const customChainsRef = useRef<ChainConfig[]>([]);
  useEffect(() => { customChainsRef.current = customChains; }, [customChains]);

  const refreshSessions = useCallback(() => {
    const kit = kitRef.current;
    if (!kit) return;
    const active = kit.getActiveSessions();
    setSessions(Object.values(active).map((s: any) => ({
      topic: s.topic,
      name: s.peer?.metadata?.name ?? 'dApp',
      url: s.peer?.metadata?.url ?? '',
      icon: s.peer?.metadata?.icons?.[0],
    })));
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const core = new Core({ projectId: WALLETCONNECT_PROJECT_ID });
        const kit = await WalletKit.init({ core, metadata: WALLETCONNECT_METADATA });
        if (!alive) return;
        kitRef.current = kit;
        kit.on('session_proposal', (p: any) => setProposal(p));
        kit.on('session_request', (r: any) => {
          const m = r?.params?.request?.method;
          if (m === 'wallet_switchEthereumChain') { void handleSwitchChain(kit, r, customChainsRef.current); return; }
          if (m === 'wallet_addEthereumChain') { void handleAddChain(kit, r, customChainsRef.current, setAddChainRequest); return; }
          setRequest(r);
        });
        kit.on('session_delete', () => refreshSessions());
        refreshSessions();
        setReady(true);
      } catch (e) {
        setError(`WalletConnect init failed: ${(e as Error).message}`);
      }
    })();
    return () => { alive = false; };
  }, [refreshSessions]);

  const evmAddress = useCallback(async () => {
    const meta = await keystore.getMeta();
    const addr = meta?.addresses?.ethereum;
    if (!addr) throw new Error('No EVM account');
    return addr;
  }, []);

  const pair = useCallback(async (uri: string) => {
    const kit = kitRef.current;
    if (!kit) throw new Error('WalletConnect not ready');
    setError(null);
    await kit.pair({ uri: uri.trim() });
  }, []);

  const pendingUriRef = useRef<string | null>(null);
  const pairedRef = useRef<Set<string>>(new Set());
  const tryPairPending = useCallback(async () => {
    const uri = pendingUriRef.current;
    if (!uri || !kitRef.current || pairedRef.current.has(uri)) return;
    pendingUriRef.current = null;
    pairedRef.current.add(uri);
    try { await kitRef.current.pair({ uri }); } catch (e) { setError((e as Error).message); }
  }, []);

  useEffect(() => {
    const handle = (url: string | null) => {
      const uri = url ? extractWcUri(url) : null;
      if (uri) { pendingUriRef.current = uri; tryPairPending(); }
    };
    Linking.getInitialURL().then(handle).catch(() => {});
    const sub = Linking.addEventListener('url', (e) => handle(e.url));
    return () => sub.remove();
  }, [tryPairPending]);

  useEffect(() => { if (ready) tryPairPending(); }, [ready, tryPairPending]);

  const approveProposal = useCallback(async () => {
    const kit = kitRef.current;
    if (!kit || !proposal) return;
    setBusy(true);
    setError(null);
    try {
      const addr = await evmAddress();
      const all = [...EVM_CHAINS, ...customChainsRef.current];
      const chains = all.map((c) => `eip155:${c.evmChainId}`);
      const accounts = all.map((c) => `eip155:${c.evmChainId}:${addr}`);
      const namespaces = buildApprovedNamespaces({
        proposal: proposal.params,
        supportedNamespaces: { eip155: { chains, methods: EVM_METHODS, events: EVM_EVENTS, accounts } },
      });
      await kit.approveSession({ id: proposal.id, namespaces });
      setProposal(null);
      refreshSessions();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [proposal, evmAddress, refreshSessions]);

  const rejectProposal = useCallback(async () => {
    const kit = kitRef.current;
    if (!kit || !proposal) return;
    try { await kit.rejectSession({ id: proposal.id, reason: getSdkError('USER_REJECTED') }); }
    finally { setProposal(null); }
  }, [proposal]);

  const approveRequest = useCallback(async () => {
    const kit = kitRef.current;
    if (!kit || !request) return;
    setBusy(true);
    setError(null);
    try {
      const { topic, params, id } = request;
      const method: string = params.request.method;
      const rp: any[] = params.request.params;
      const numericChain = Number(String(params.chainId).split(':')[1]);

      if (!kit.getActiveSessions()[topic]) throw new Error('No active session for this request');
      if (!EVM_METHODS.includes(method)) throw new Error(`Unsupported method: ${method}`);
      if (method === 'eth_sendTransaction' && !resolveEvmConfig(numericChain, customChainsRef.current))
        throw new Error(`Unsupported chain eip155:${numericChain}`);

      const mnemonic = await keystore.unlockMnemonic('Approve dApp request');
      let result: string;

      if (method === 'personal_sign') {
        const k = deriveEvmKey(mnemonic);
        result = personalSign(rp[0], k.privateKey);
      } else if (method === 'eth_signTypedData' || method === 'eth_signTypedData_v4') {
        const k = deriveEvmKey(mnemonic);
        const typed: TypedData = typeof rp[1] === 'string' ? JSON.parse(rp[1]) : rp[1];
        result = signTypedDataV4(typed, k.privateKey);
      } else if (method === 'eth_sendTransaction') {
        const cfg = resolveEvmConfig(numericChain, customChainsRef.current);
        if (!cfg) throw new Error(`Unsupported chain eip155:${numericChain}`);
        const res = await new EvmAdapter(cfg).sendTxParams(mnemonic, rp[0]);
        result = res.hash;
      } else {
        throw new Error(`Unsupported method: ${method}`);
      }

      await kit.respondSessionRequest({ topic, response: { id, jsonrpc: '2.0', result } });
      setRequest(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [request]);

  const rejectRequest = useCallback(async () => {
    const kit = kitRef.current;
    if (!kit || !request) return;
    try {
      await kit.respondSessionRequest({ topic: request.topic, response: { id: request.id, jsonrpc: '2.0', error: getSdkError('USER_REJECTED') } });
    } finally { setRequest(null); }
  }, [request]);

  const approveAddChain = useCallback(async () => {
    const kit = kitRef.current;
    const req = addChainRequest;
    if (!kit || !req) return;
    setBusy(true);
    setError(null);
    try {
      // SECURITY: verify the supplied RPC actually reports the claimed chain id before we
      // trust it — a mismatched RPC is a red flag (spoofed network / wrong endpoint).
      const actual = await fetchChainId(req.config.rpcUrl);
      if (actual !== req.config.evmChainId)
        throw new Error(`RPC reports chain id ${actual}, but the request claimed ${req.config.evmChainId}. Rejected.`);
      await addCustomNetwork(req.config);
      await kit.respondSessionRequest({ topic: req.event.topic, response: { id: req.event.id, jsonrpc: '2.0', result: null } });
      setAddChainRequest(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [addChainRequest, addCustomNetwork]);

  const rejectAddChain = useCallback(async () => {
    const kit = kitRef.current;
    const req = addChainRequest;
    if (!kit || !req) return;
    try {
      await kit.respondSessionRequest({ topic: req.event.topic, response: { id: req.event.id, jsonrpc: '2.0', error: getSdkError('USER_REJECTED') } });
    } finally { setAddChainRequest(null); }
  }, [addChainRequest]);

  const disconnect = useCallback(async (topic: string) => {
    const kit = kitRef.current;
    if (!kit) return;
    await kit.disconnectSession({ topic, reason: getSdkError('USER_DISCONNECTED') });
    refreshSessions();
  }, [refreshSessions]);

  const value: WcState = {
    ready, sessions, proposal, request, addChainRequest, busy, error,
    pair, approveProposal, rejectProposal, approveRequest, rejectRequest,
    approveAddChain, rejectAddChain, disconnect,
    clearError: () => setError(null),
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWalletConnect(): WcState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useWalletConnect must be used within WalletConnectProvider');
  return ctx;
}
