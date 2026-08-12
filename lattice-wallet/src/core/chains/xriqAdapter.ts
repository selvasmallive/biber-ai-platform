// XRIQ adapter — wraps the (Rust-conformant) XRIQ core behind the ChainAdapter seam.
import {
  keypairFromMnemonic,
  signTransfer,
  isValidAddress,
  hex,
  DEFAULT_PATH,
  type XriqTransaction,
} from '../xriq';
import { XriqRpc } from '../rpc';
import type { NetworkConfig } from '../config';
import type { HistoryEntry } from '../rpc';
import type {
  ChainAdapter,
  ChainConfig,
  DerivedAccount,
  FeeEstimate,
  TransferRequest,
  BroadcastResult,
} from './types';

function toNetworkConfig(c: ChainConfig): NetworkConfig {
  return {
    key: c.id,
    label: c.name,
    chainId: c.id === 'xriq' ? 'xriq-devnet' : c.id,
    rpcUrl: c.rpcUrl,
    isTestnet: c.isTestnet,
    faucetEnabled: c.isTestnet,
  };
}

const DEFAULT_FEE = 1n;

export class XriqAdapter implements ChainAdapter {
  private rpc: XriqRpc;
  private chainIdStr: string;

  constructor(readonly config: ChainConfig) {
    const net = toNetworkConfig(config);
    this.chainIdStr = net.chainId;
    this.rpc = new XriqRpc(net);
  }

  deriveAccount(mnemonic: string): DerivedAccount {
    const kp = keypairFromMnemonic(mnemonic, DEFAULT_PATH);
    return {
      chainId: this.config.id,
      address: kp.address,
      publicKeyHex: hex.toHex(kp.publicKey),
      path: "m/44'/1'/0'/0'/0'",
    };
  }

  validateAddress(address: string): boolean {
    return isValidAddress(address);
  }

  async getBalance(address: string): Promise<bigint> {
    return (await this.rpc.getAccount(address)).balanceBaseUnits;
  }

  getHistory(address: string): Promise<HistoryEntry[]> {
    return this.rpc.getHistory(address);
  }

  async estimateFee(): Promise<FeeEstimate> {
    return { feeBaseUnits: DEFAULT_FEE, detail: 'flat testnet fee' };
  }

  async send(mnemonic: string, req: TransferRequest): Promise<BroadcastResult> {
    const kp = keypairFromMnemonic(mnemonic, DEFAULT_PATH);
    const acct = await this.rpc.getAccount(kp.address);
    const tx: XriqTransaction = {
      version: 1,
      chainId: this.chainIdStr,
      from: kp.address,
      to: req.to.trim(),
      amountBaseUnits: req.amountBaseUnits,
      feeBaseUnits: req.feeBaseUnits ?? DEFAULT_FEE,
      nonce: acct.nonce,
      memoHash: null,
      expiresAtHeight: null,
      publicKey: kp.publicKey,
    };
    const signed = signTransfer(tx, kp.privateSeed);
    await this.rpc.submitSigned(tx, signed);
    return { hash: hex.toHex(signed.transactionHash) };
  }
}
