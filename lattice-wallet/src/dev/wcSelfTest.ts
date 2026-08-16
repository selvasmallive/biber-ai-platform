// Live WalletConnect handshake self-test — DEV/diagnostic only.
//
// Runs a full end-to-end handshake over the real WalletConnect relay, inside the app: a dApp
// client (SignClient) connects to a wallet client (WalletKit), the wallet approves the
// session and signs a personal_sign request with our EVM signer, and the dApp verifies the
// signature recovers to the wallet address. This exercises the native WalletKit code path
// that can't run in Expo Go — so it's meant to be run from a dev/EAS build.
//
// It uses a THROWAWAY test key (no biometric, no real account) and isolated storage prefixes,
// so it doesn't touch the user's wallet or the app's live WalletConnect session.
import SignClient from '@walletconnect/sign-client';
import { Core } from '@walletconnect/core';
import { WalletKit, type IWalletKit } from '@reown/walletkit';
import { buildApprovedNamespaces, getSdkError } from '@walletconnect/utils';
import { secp256k1 } from '@noble/curves/secp256k1';
import { WALLETCONNECT_PROJECT_ID } from '../core/config';
import { deriveEvmKey, evmAddressFromPublicKey } from '../core/chains/evm';
import { personalSign, hashPersonalMessage } from '../core/chains/evmSign';
import { hex } from '../core/xriq';

const TEST_MNEMONIC = 'test test test test test test test test test test test junk';
const TEST_MESSAGE = 'Lattice WalletConnect self-test';

export interface Step {
  name: string;
  ok: boolean;
  detail?: string;
}

function withTimeout<T>(p: Promise<T>, ms: number, label: string): Promise<T> {
  return Promise.race([
    p,
    new Promise<T>((_, reject) => setTimeout(() => reject(new Error(`${label} timed out after ${ms}ms`)), ms)),
  ]);
}

function recoverPersonalSign(message: string, sigHex: string): string {
  const digest = hashPersonalMessage(message);
  const bytes = hex.fromHex(sigHex.replace(/^0x/, ''));
  const sig = secp256k1.Signature.fromCompact(bytes.slice(0, 64)).addRecoveryBit(bytes[64] - 27);
  const pub = sig.recoverPublicKey(digest).toRawBytes(false);
  return evmAddressFromPublicKey(pub);
}

/** Run the handshake self-test, emitting each step as it completes. Never throws. */
export async function runWcSelfTest(onStep: (s: Step) => void): Promise<boolean> {
  const step = (name: string, ok: boolean, detail?: string) => { onStep({ name, ok, detail }); return ok; };
  const k = deriveEvmKey(TEST_MNEMONIC);
  const address = k.address;

  let walletKit: IWalletKit | undefined;
  let dapp: Awaited<ReturnType<typeof SignClient.init>> | undefined;
  let topic: string | undefined;

  try {
    // --- Wallet side ---
    walletKit = await withTimeout(
      WalletKit.init({
        core: new Core({ projectId: WALLETCONNECT_PROJECT_ID, customStoragePrefix: 'lattice-selftest-wallet' }),
        metadata: { name: 'Lattice SelfTest Wallet', description: 'handshake test', url: 'https://lattice.app', icons: [] },
      }),
      20000,
      'WalletKit init',
    );
    step('WalletKit initialized', true);

    walletKit.on('session_proposal', async (proposal: any) => {
      try {
        const namespaces = buildApprovedNamespaces({
          proposal: proposal.params,
          supportedNamespaces: {
            eip155: {
              chains: ['eip155:1'],
              methods: ['personal_sign'],
              events: ['chainChanged', 'accountsChanged'],
              accounts: [`eip155:1:${address}`],
            },
          },
        });
        await walletKit!.approveSession({ id: proposal.id, namespaces });
      } catch { /* surfaced via the dApp approval timeout */ }
    });

    walletKit.on('session_request', async (event: any) => {
      const { topic: t, id, params } = event;
      if (params.request.method === 'personal_sign') {
        const result = personalSign(params.request.params[0], k.privateKey);
        await walletKit!.respondSessionRequest({ topic: t, response: { id, jsonrpc: '2.0', result } });
      }
    });

    // --- dApp side ---
    dapp = await withTimeout(
      SignClient.init({
        projectId: WALLETCONNECT_PROJECT_ID,
        metadata: { name: 'Lattice SelfTest dApp', description: 'handshake test', url: 'https://lattice.app', icons: [] },
      }),
      20000,
      'SignClient init',
    );
    step('dApp SignClient initialized', true);

    const { uri, approval } = await dapp.connect({
      requiredNamespaces: {
        eip155: { chains: ['eip155:1'], methods: ['personal_sign'], events: ['chainChanged', 'accountsChanged'] },
      },
    });
    step('dApp created pairing URI', !!uri, uri ? `${uri.slice(0, 24)}…` : 'no uri');
    if (!uri) throw new Error('no pairing uri');

    await withTimeout(walletKit.pair({ uri }), 20000, 'wallet pair');
    step('Wallet paired with dApp URI', true);

    const session = await withTimeout(approval(), 25000, 'session approval');
    topic = session.topic;
    step('Session established (proposal approved)', !!topic);

    const signature = await withTimeout(
      dapp.request<string>({ topic: session.topic, chainId: 'eip155:1', request: { method: 'personal_sign', params: [TEST_MESSAGE, address] } }),
      25000,
      'personal_sign request',
    );
    step('dApp received signature', typeof signature === 'string' && signature.length > 2, signature?.slice(0, 20));

    const recovered = recoverPersonalSign(TEST_MESSAGE, signature);
    const match = recovered.toLowerCase() === address.toLowerCase();
    step('Signature recovers to wallet address', match, match ? address : `got ${recovered}`);

    return match;
  } catch (e) {
    step('Handshake failed', false, (e as Error).message);
    return false;
  } finally {
    try { if (dapp && topic) await dapp.disconnect({ topic, reason: getSdkError('USER_DISCONNECTED') }); } catch { /* ignore */ }
  }
}
