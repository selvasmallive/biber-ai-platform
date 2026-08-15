// WalletConnect (Reown WalletKit) integration — lets dApps connect to Lattice and request
// EVM signatures/transactions, which are routed to the on-device signer (verified in
// __tests__/evm-sign-vectors.ts) behind biometric approval.
//
// STATUS: the signing paths are verified; the pairing/session handshake requires a custom
// dev/EAS build (WalletKit has native deps and does not run in Expo Go) and a real dApp to
// test end-to-end. The code compiles and bundles; live pairing is untested from CI.
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { WalletKit, type IWalletKit } from '@reown/walletkit';
import { Core } from '@walletconnect/core';
import { buildApprovedNamespaces, getSdkError } from '@walletconnect/utils';
import { WALLETCONNECT_METADATA, WALLETCONNECT_PROJECT_ID } from '../core/config';
import { EVM_CHAINS, evmConfigByChainId } from '../core/chains/registry';
import { EvmAdapter, deriveEvmKey } from '../core/chains/evm';
import { personalSign, signTypedDataV4, type TypedData } from '../core/chains/evmSign';
import * as keystore from '../core/keystore';

const EVM_METHODS = ['eth_sendTransaction', 'personal_sign', 'eth_signTypedData', 'eth_signTypedData_v4'];
const EVM_EVENTS = ['chainChanged', 'accountsChanged'];

export interface WcSession {
  topic: string;
  name: string;
  url: string;
  icon?: string;
}

interface WcState {
  ready: boolean;
  sessions: WcSession[];
  proposal: any | null; // pending session proposal
  request: any | null; // pending session request
  busy: boolean;
  error: string | null;
  pair: (uri: string) => Promise<void>;
  approveProposal: () => Promise<void>;
  rejectProposal: () => Promise<void>;
  approveRequest: () => Promise<void>;
  rejectRequest: () => Promise<void>;
  disconnect: (topic: string) => Promise<void>;
  clearError: () => void;
}

const Ctx = createContext<WcState | null>(null);

export function WalletConnectProvider({ children }: { children: React.ReactNode }) {
  const kitRef = useRef<IWalletKit | null>(null);
  const [ready, setReady] = useState(false);
  const [sessions, setSessions] = useState<WcSession[]>([]);
  const [proposal, setProposal] = useState<any | null>(null);
  const [request, setRequest] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshSessions = useCallback(() => {
    const kit = kitRef.current;
    if (!kit) return;
    const active = kit.getActiveSessions();
    setSessions(
      Object.values(active).map((s: any) => ({
        topic: s.topic,
        name: s.peer?.metadata?.name ?? 'dApp',
        url: s.peer?.metadata?.url ?? '',
        icon: s.peer?.metadata?.icons?.[0],
      })),
    );
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
        kit.on('session_request', (r: any) => setRequest(r));
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

  const approveProposal = useCallback(async () => {
    const kit = kitRef.current;
    if (!kit || !proposal) return;
    setBusy(true);
    setError(null);
    try {
      const addr = await evmAddress();
      const chains = EVM_CHAINS.map((c) => `eip155:${c.evmChainId}`);
      const accounts = EVM_CHAINS.map((c) => `eip155:${c.evmChainId}:${addr}`);
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
    try {
      await kit.rejectSession({ id: proposal.id, reason: getSdkError('USER_REJECTED') });
    } finally {
      setProposal(null);
    }
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
      const mnemonic = await keystore.unlockMnemonic('Approve dApp request');
      let result: string;

      if (method === 'personal_sign') {
        const k = deriveEvmKey(mnemonic);
        // personal_sign params are [message, address].
        result = personalSign(rp[0], k.privateKey);
      } else if (method === 'eth_signTypedData' || method === 'eth_signTypedData_v4') {
        const k = deriveEvmKey(mnemonic);
        const typed: TypedData = typeof rp[1] === 'string' ? JSON.parse(rp[1]) : rp[1];
        result = signTypedDataV4(typed, k.privateKey);
      } else if (method === 'eth_sendTransaction') {
        const cfg = evmConfigByChainId(numericChain);
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
      // Leave the request open so the user can retry or reject.
    } finally {
      setBusy(false);
    }
  }, [request]);

  const rejectRequest = useCallback(async () => {
    const kit = kitRef.current;
    if (!kit || !request) return;
    try {
      await kit.respondSessionRequest({
        topic: request.topic,
        response: { id: request.id, jsonrpc: '2.0', error: getSdkError('USER_REJECTED') },
      });
    } finally {
      setRequest(null);
    }
  }, [request]);

  const disconnect = useCallback(async (topic: string) => {
    const kit = kitRef.current;
    if (!kit) return;
    await kit.disconnectSession({ topic, reason: getSdkError('USER_DISCONNECTED') });
    refreshSessions();
  }, [refreshSessions]);

  const value: WcState = {
    ready, sessions, proposal, request, busy, error,
    pair, approveProposal, rejectProposal, approveRequest, rejectRequest, disconnect,
    clearError: () => setError(null),
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useWalletConnect(): WcState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useWalletConnect must be used within WalletConnectProvider');
  return ctx;
}
