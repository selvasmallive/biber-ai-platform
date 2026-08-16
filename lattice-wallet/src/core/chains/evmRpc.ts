// Small EVM JSON-RPC helpers shared outside the adapters.
export async function fetchChainId(rpcUrl: string): Promise<number> {
  const res = await fetch(rpcUrl, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'eth_chainId', params: [] }),
  });
  const json: any = await res.json();
  if (json?.error || !json?.result) throw new Error('RPC did not return a chain id');
  return Number(BigInt(json.result));
}
