// ENS name resolution — fully on-chain via the wallet's own EVM RPC (no third-party
// name service), so resolving a name leaks nothing beyond the RPC call you already make.
// namehash is verified against the EIP-137 golden vectors in __tests__/ens-vectors.ts.
import { keccak_256 } from '@noble/hashes/sha3';
import { hex } from './xriq';

const ENS_REGISTRY = '0x00000000000C2E074eC69A0dFb2997BA6C7d2e1e';
const SEL_RESOLVER = '0178b8bf'; // resolver(bytes32)
const SEL_ADDR = '3b3b57de'; // addr(bytes32)

/** EIP-137 namehash. */
export function namehash(name: string): Uint8Array {
  let node: Uint8Array = new Uint8Array(32);
  const trimmed = name.trim().toLowerCase();
  if (trimmed.length > 0) {
    const labels = trimmed.split('.');
    for (let i = labels.length - 1; i >= 0; i--) {
      const labelHash = keccak_256(new TextEncoder().encode(labels[i]));
      node = Uint8Array.from(keccak_256(concatBytes(node, labelHash)));
    }
  }
  return node;
}

function concatBytes(a: Uint8Array, b: Uint8Array): Uint8Array {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

export function isEnsName(input: string): boolean {
  return /\.(eth|xyz|luxe|kred|art|club)$/i.test(input.trim());
}

async function ethCall(rpcUrl: string, to: string, data: string): Promise<string> {
  const res = await fetch(rpcUrl, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_call', params: [{ to, data }, 'latest'] }),
  });
  const json: any = await res.json();
  if (json.error) throw new Error(json.error.message ?? 'eth_call failed');
  return json.result as string;
}

/**
 * Resolve an ENS name to an address using the given (mainnet) EVM RPC. Returns null if
 * the name has no resolver or no address record.
 */
export async function resolveEns(rpcUrl: string, name: string): Promise<string | null> {
  const node = hex.toHex(namehash(name));
  const resolverRaw = await ethCall(rpcUrl, ENS_REGISTRY, '0x' + SEL_RESOLVER + node);
  const resolver = '0x' + resolverRaw.slice(-40);
  if (/^0x0+$/.test(resolver)) return null;
  const addrRaw = await ethCall(rpcUrl, resolver, '0x' + SEL_ADDR + node);
  const addr = '0x' + addrRaw.slice(-40);
  return /^0x0+$/.test(addr) ? null : addr;
}
