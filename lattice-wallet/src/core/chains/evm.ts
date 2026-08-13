// EVM chain adapter — Ethereum and every EVM-compatible network (Polygon, BSC, Base,
// Arbitrum, …) via one implementation parameterized by chain id + RPC URL.
//
// Crypto: secp256k1 (ECDSA) keys, keccak-256 addresses (EIP-55 checksum), RLP encoding,
// EIP-1559 (type-2) transactions for sends, and legacy EIP-155 signing exposed for the
// published golden-vector conformance test. All primitives are audited @noble/@scure libs.
import { HDKey } from '@scure/bip32';
import { mnemonicToSeedSync } from '@scure/bip39';
import { secp256k1 } from '@noble/curves/secp256k1';
import { keccak_256 } from '@noble/hashes/sha3';
import { hex } from '../xriq';
import { encodeBalanceOf, encodeTransfer, encodeCall, decodeUint, decodeString, ERC20_SELECTORS } from '../evmAbi';
import type { HistoryEntry } from '../rpc';
import type {
  ChainAdapter,
  ChainConfig,
  DerivedAccount,
  FeeEstimate,
  TransferRequest,
  BroadcastResult,
} from './types';

// ---------------------------------------------------------------------------
// RLP encoding.
// ---------------------------------------------------------------------------
type RlpInput = Uint8Array | RlpInput[];

function toMinimalBytes(value: bigint): Uint8Array {
  if (value < 0n) throw new Error('negative value');
  if (value === 0n) return new Uint8Array(0);
  let hexStr = value.toString(16);
  if (hexStr.length % 2) hexStr = '0' + hexStr;
  return hex.fromHex(hexStr);
}

function encodeLength(len: number, offset: number): Uint8Array {
  if (len < 56) return new Uint8Array([offset + len]);
  const lenBytes = toMinimalBytes(BigInt(len));
  return new Uint8Array([offset + 55 + lenBytes.length, ...lenBytes]);
}

function concatBytes(...arrs: Uint8Array[]): Uint8Array {
  const total = arrs.reduce((n, a) => n + a.length, 0);
  const out = new Uint8Array(total);
  let o = 0;
  for (const a of arrs) {
    out.set(a, o);
    o += a.length;
  }
  return out;
}

function rlpEncode(input: RlpInput): Uint8Array {
  if (input instanceof Uint8Array) {
    if (input.length === 1 && input[0] < 0x80) return input;
    return concatBytes(encodeLength(input.length, 0x80), input);
  }
  const encodedItems = concatBytes(...input.map(rlpEncode));
  return concatBytes(encodeLength(encodedItems.length, 0xc0), encodedItems);
}

// ---------------------------------------------------------------------------
// Address derivation + EIP-55 checksum.
// ---------------------------------------------------------------------------
export function evmAddressFromPublicKey(uncompressedPubKey: Uint8Array): string {
  // Drop the 0x04 prefix; address = last 20 bytes of keccak256(x || y).
  const body = uncompressedPubKey.length === 65 ? uncompressedPubKey.subarray(1) : uncompressedPubKey;
  const hash = keccak_256(body);
  return toChecksumAddress(hex.toHex(hash.subarray(12)));
}

export function toChecksumAddress(hexAddr: string): string {
  const addr = (hexAddr.startsWith('0x') ? hexAddr.slice(2) : hexAddr).toLowerCase();
  const hash = keccak_256(new TextEncoder().encode(addr));
  let out = '0x';
  for (let i = 0; i < addr.length; i++) {
    const c = addr[i];
    if (c >= '0' && c <= '9') {
      out += c;
    } else {
      const nibble = hash[i >> 1] >> (i % 2 === 0 ? 4 : 0);
      out += (nibble & 0x0f) >= 8 ? c.toUpperCase() : c;
    }
  }
  return out;
}

const EVM_ADDRESS_RE = /^0x[0-9a-fA-F]{40}$/;

export function isValidChecksum(address: string): boolean {
  if (!EVM_ADDRESS_RE.test(address)) return false;
  const noPrefix = address.slice(2);
  // All-lower or all-upper are accepted (no checksum); mixed case must match EIP-55.
  if (noPrefix === noPrefix.toLowerCase() || noPrefix === noPrefix.toUpperCase()) return true;
  return toChecksumAddress(address) === address;
}

export function deriveEvmKey(mnemonic: string, accountIndex = 0): { privateKey: Uint8Array; publicKey: Uint8Array; address: string; path: string } {
  const seed = mnemonicToSeedSync(mnemonic.trim());
  const path = `m/44'/60'/0'/0/${accountIndex}`;
  const child = HDKey.fromMasterSeed(seed).derive(path);
  if (!child.privateKey) throw new Error('failed to derive EVM key');
  const publicKey = secp256k1.getPublicKey(child.privateKey, false); // uncompressed
  return { privateKey: child.privateKey, publicKey, address: evmAddressFromPublicKey(publicKey), path };
}

// ---------------------------------------------------------------------------
// Transaction signing.
// ---------------------------------------------------------------------------
function addressBytes(addr: string): Uint8Array {
  return hex.fromHex(addr.startsWith('0x') ? addr.slice(2) : addr);
}

export interface LegacyTx {
  nonce: bigint;
  gasPrice: bigint;
  gasLimit: bigint;
  to: string;
  value: bigint;
  data: Uint8Array;
  chainId: bigint;
}

/** Sign a legacy EIP-155 transaction; returns the raw broadcastable bytes (hex). */
export function signLegacy155(tx: LegacyTx, privateKey: Uint8Array): { raw: string; hash: string } {
  const fields: RlpInput = [
    toMinimalBytes(tx.nonce),
    toMinimalBytes(tx.gasPrice),
    toMinimalBytes(tx.gasLimit),
    addressBytes(tx.to),
    toMinimalBytes(tx.value),
    tx.data,
    toMinimalBytes(tx.chainId),
    new Uint8Array(0),
    new Uint8Array(0),
  ];
  const sigHash = keccak_256(rlpEncode(fields));
  const sig = secp256k1.sign(sigHash, privateKey);
  const v = tx.chainId * 2n + 35n + BigInt(sig.recovery);
  const signed: RlpInput = [
    toMinimalBytes(tx.nonce),
    toMinimalBytes(tx.gasPrice),
    toMinimalBytes(tx.gasLimit),
    addressBytes(tx.to),
    toMinimalBytes(tx.value),
    tx.data,
    toMinimalBytes(v),
    toMinimalBytes(sig.r),
    toMinimalBytes(sig.s),
  ];
  const raw = rlpEncode(signed);
  return { raw: '0x' + hex.toHex(raw), hash: '0x' + hex.toHex(keccak_256(raw)) };
}

export interface Eip1559Tx {
  chainId: bigint;
  nonce: bigint;
  maxPriorityFeePerGas: bigint;
  maxFeePerGas: bigint;
  gasLimit: bigint;
  to: string;
  value: bigint;
  data: Uint8Array;
}

/** Sign an EIP-1559 (type-2) transaction; returns raw broadcastable bytes (hex). */
export function signEip1559(tx: Eip1559Tx, privateKey: Uint8Array): { raw: string; hash: string } {
  const payloadFields: RlpInput = [
    toMinimalBytes(tx.chainId),
    toMinimalBytes(tx.nonce),
    toMinimalBytes(tx.maxPriorityFeePerGas),
    toMinimalBytes(tx.maxFeePerGas),
    toMinimalBytes(tx.gasLimit),
    addressBytes(tx.to),
    toMinimalBytes(tx.value),
    tx.data,
    [], // empty access list
  ];
  const unsigned = concatBytes(new Uint8Array([0x02]), rlpEncode(payloadFields));
  const sigHash = keccak_256(unsigned);
  const sig = secp256k1.sign(sigHash, privateKey);
  const signedFields: RlpInput = [
    ...payloadFields,
    toMinimalBytes(BigInt(sig.recovery)),
    toMinimalBytes(sig.r),
    toMinimalBytes(sig.s),
  ];
  const signed = concatBytes(new Uint8Array([0x02]), rlpEncode(signedFields));
  return { raw: '0x' + hex.toHex(signed), hash: '0x' + hex.toHex(keccak_256(signed)) };
}

// ---------------------------------------------------------------------------
// JSON-RPC.
// ---------------------------------------------------------------------------
async function jsonRpc<T>(url: string, method: string, params: unknown[]): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
  });
  const json: any = await res.json();
  if (json.error) throw new Error(`${method}: ${json.error.message ?? JSON.stringify(json.error)}`);
  return json.result as T;
}

function hexToBig(h: string | null | undefined): bigint {
  if (!h) return 0n;
  return BigInt(h);
}

const GAS_LIMIT_TRANSFER = 21000n;

export class EvmAdapter implements ChainAdapter {
  constructor(readonly config: ChainConfig) {
    if (config.evmChainId === undefined) throw new Error('EVM adapter needs evmChainId');
  }

  deriveAccount(mnemonic: string): DerivedAccount {
    const k = deriveEvmKey(mnemonic);
    return { chainId: this.config.id, address: k.address, publicKeyHex: hex.toHex(k.publicKey), path: k.path };
  }

  validateAddress(address: string): boolean {
    return isValidChecksum(address.trim());
  }

  async getBalance(address: string): Promise<bigint> {
    return hexToBig(await jsonRpc<string>(this.config.rpcUrl, 'eth_getBalance', [address, 'latest']));
  }

  async getHistory(_address: string): Promise<HistoryEntry[]> {
    // Full history needs an indexer (e.g. Etherscan API). Return empty rather than
    // guessing; balance/send/receive work without it.
    return [];
  }

  private async feeData(): Promise<{ maxFeePerGas: bigint; maxPriorityFeePerGas: bigint }> {
    try {
      const [block, priority] = await Promise.all([
        jsonRpc<any>(this.config.rpcUrl, 'eth_getBlockByNumber', ['latest', false]),
        jsonRpc<string>(this.config.rpcUrl, 'eth_maxPriorityFeePerGas', []).catch(() => '0x3b9aca00'),
      ]);
      const baseFee = hexToBig(block?.baseFeePerGas);
      const tip = hexToBig(priority);
      const maxFeePerGas = baseFee * 2n + tip;
      return { maxFeePerGas: maxFeePerGas > 0n ? maxFeePerGas : tip, maxPriorityFeePerGas: tip };
    } catch {
      const gasPrice = hexToBig(await jsonRpc<string>(this.config.rpcUrl, 'eth_gasPrice', []));
      return { maxFeePerGas: gasPrice, maxPriorityFeePerGas: gasPrice };
    }
  }

  async estimateFee(_from: string, _req: TransferRequest): Promise<FeeEstimate> {
    const { maxFeePerGas } = await this.feeData();
    const fee = GAS_LIMIT_TRANSFER * maxFeePerGas;
    return { feeBaseUnits: fee, detail: `${GAS_LIMIT_TRANSFER} gas × maxFee` };
  }

  async send(mnemonic: string, req: TransferRequest): Promise<BroadcastResult> {
    const k = deriveEvmKey(mnemonic);
    const [nonceHex, { maxFeePerGas, maxPriorityFeePerGas }] = await Promise.all([
      jsonRpc<string>(this.config.rpcUrl, 'eth_getTransactionCount', [k.address, 'pending']),
      this.feeData(),
    ]);
    const tx: Eip1559Tx = {
      chainId: BigInt(this.config.evmChainId!),
      nonce: hexToBig(nonceHex),
      maxPriorityFeePerGas,
      maxFeePerGas,
      gasLimit: GAS_LIMIT_TRANSFER,
      to: req.to.trim(),
      value: req.amountBaseUnits,
      data: new Uint8Array(0),
    };
    const { raw, hash } = signEip1559(tx, k.privateKey);
    const broadcastHash = await jsonRpc<string>(this.config.rpcUrl, 'eth_sendRawTransaction', [raw]);
    return { hash: broadcastHash || hash, raw };
  }

  // ---- ERC-20 tokens (read from the user's own RPC; no third-party tracker) ----

  async getErc20Balance(tokenAddress: string, owner: string): Promise<bigint> {
    const data = encodeBalanceOf(owner);
    const res = await jsonRpc<string>(this.config.rpcUrl, 'eth_call', [{ to: tokenAddress, data }, 'latest']);
    return decodeUint(res);
  }

  async fetchErc20Metadata(tokenAddress: string): Promise<{ symbol: string; decimals: number; name: string }> {
    const [sym, dec, nm] = await Promise.all([
      jsonRpc<string>(this.config.rpcUrl, 'eth_call', [{ to: tokenAddress, data: encodeCall(ERC20_SELECTORS.symbol) }, 'latest']).catch(() => '0x'),
      jsonRpc<string>(this.config.rpcUrl, 'eth_call', [{ to: tokenAddress, data: encodeCall(ERC20_SELECTORS.decimals) }, 'latest']).catch(() => '0x'),
      jsonRpc<string>(this.config.rpcUrl, 'eth_call', [{ to: tokenAddress, data: encodeCall(ERC20_SELECTORS.name) }, 'latest']).catch(() => '0x'),
    ]);
    return {
      symbol: decodeString(sym) || 'TOKEN',
      decimals: Number(decodeUint(dec)) || 18,
      name: decodeString(nm) || 'Unknown token',
    };
  }

  /** Build, sign, and broadcast an ERC-20 transfer. `amount` is in token base units. */
  async sendErc20(mnemonic: string, tokenAddress: string, to: string, amount: bigint): Promise<BroadcastResult> {
    const k = deriveEvmKey(mnemonic);
    const data = encodeTransfer(to.trim(), amount);
    const dataBytes = hex.fromHex(data.slice(2));
    const [nonceHex, fee, gasHex] = await Promise.all([
      jsonRpc<string>(this.config.rpcUrl, 'eth_getTransactionCount', [k.address, 'pending']),
      this.feeData(),
      jsonRpc<string>(this.config.rpcUrl, 'eth_estimateGas', [{ from: k.address, to: tokenAddress, data }]).catch(() => '0x186a0'),
    ]);
    const gasLimit = (hexToBig(gasHex) * 12n) / 10n; // +20% headroom
    const tx: Eip1559Tx = {
      chainId: BigInt(this.config.evmChainId!),
      nonce: hexToBig(nonceHex),
      maxPriorityFeePerGas: fee.maxPriorityFeePerGas,
      maxFeePerGas: fee.maxFeePerGas,
      gasLimit,
      to: tokenAddress.trim(),
      value: 0n,
      data: dataBytes,
    };
    const { raw, hash } = signEip1559(tx, k.privateKey);
    const broadcastHash = await jsonRpc<string>(this.config.rpcUrl, 'eth_sendRawTransaction', [raw]);
    return { hash: broadcastHash || hash, raw };
  }
}
