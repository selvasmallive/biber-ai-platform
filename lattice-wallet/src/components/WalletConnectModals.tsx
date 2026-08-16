import React, { useEffect, useState } from 'react';
import { Modal, StyleSheet, Text, View } from 'react-native';
import { Button, shortAddr } from './ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWalletConnect } from '../state/WalletConnectProvider';
import { formatUnits } from '../core/format';
import { evmConfigByChainId } from '../core/chains/registry';
import { decodeCalldata, dryRunEvm, type SimStatus } from '../core/simulate';

function decodeMessage(raw: string): string {
  if (typeof raw !== 'string') return String(raw);
  if (/^0x[0-9a-fA-F]*$/.test(raw)) {
    try {
      const bytes = new Uint8Array((raw.slice(2).match(/.{1,2}/g) ?? []).map((h) => parseInt(h, 16)));
      const text = new TextDecoder().decode(bytes);
      if (/^[\x09\x0a\x0d\x20-\x7e]*$/.test(text) && text.length > 0) return text;
    } catch { /* fall through */ }
    return raw;
  }
  return raw;
}

function flattenMessage(msg: any, prefix = ''): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(msg ?? {})) {
    if (v && typeof v === 'object' && !Array.isArray(v)) out.push(...flattenMessage(v, `${prefix}${k}.`));
    else out.push(`${prefix}${k}: ${Array.isArray(v) ? '[…]' : String(v)}`);
  }
  return out.slice(0, 14);
}

function describe(request: any): { title: string; lines: string[]; warnings: string[] } {
  const method: string = request.params.request.method;
  const rp: any[] = request.params.request.params;
  const chainId = Number(String(request.params.chainId).split(':')[1]);
  const chainName = evmConfigByChainId(chainId)?.name ?? `chain ${chainId}`;

  if (method === 'personal_sign') {
    return { title: 'Sign message', lines: [`Network: ${chainName}`, '', decodeMessage(rp[0])], warnings: [] };
  }

  if (method === 'eth_signTypedData' || method === 'eth_signTypedData_v4') {
    const lines: string[] = [`Network: ${chainName}`];
    const warnings: string[] = [];
    try {
      const td = typeof rp[1] === 'string' ? JSON.parse(rp[1]) : rp[1];
      const primary = td.primaryType ?? 'typed data';
      const domChain = td.domain?.chainId != null ? Number(td.domain.chainId) : undefined;
      lines.push(`Type: ${primary}`);
      if (td.domain?.name) lines.push(`Domain: ${td.domain.name}`);
      if (td.domain?.verifyingContract) lines.push(`Contract: ${shortAddr(td.domain.verifyingContract)}`);
      if (domChain != null) lines.push(`Domain chain id: ${domChain}`);
      lines.push('', ...flattenMessage(td.message));
      if (domChain != null && domChain !== chainId)
        warnings.push(`This is bound to chain ${domChain}, but you're connected as ${chainName} (${chainId}). Only sign if you expect that.`);
      if (/permit/i.test(primary)) warnings.push('This authorizes token spending (Permit). Verify the spender and amount above.');
    } catch {
      warnings.push('Could not parse the typed data — do not sign unless you trust this dApp.');
    }
    return { title: 'Sign typed data', lines, warnings };
  }

  if (method === 'eth_sendTransaction') {
    const tx = rp[0] ?? {};
    let value = '0';
    try { value = tx.value ? formatUnits(BigInt(tx.value), 18) : '0'; } catch { /* keep 0 */ }
    const lines = [`Network: ${chainName}`, `To: ${tx.to ? shortAddr(tx.to) : '(contract creation)'}`, `Amount: ${value} (native)`];
    const decoded = decodeCalldata(tx.data);
    if (decoded.lines.length) lines.push('', ...decoded.lines);
    try {
      const maxFee = tx.maxFeePerGas ? BigInt(tx.maxFeePerGas) : tx.gasPrice ? BigInt(tx.gasPrice) : null;
      if (maxFee != null) lines.push(`Max fee/gas: ${formatUnits(maxFee, 9)} gwei`);
    } catch { /* ignore */ }
    return { title: 'Send transaction', lines, warnings: decoded.warnings };
  }

  return { title: method, lines: ['Unsupported request type — reject unless you trust it.'], warnings: [] };
}

// Async dry-run simulation for eth_sendTransaction (Phase 1: your RPC, no third party).
function useSimulation(request: any) {
  const [status, setStatus] = useState<SimStatus | 'loading' | null>(null);
  const [reason, setReason] = useState<string | undefined>();
  useEffect(() => {
    let alive = true;
    setStatus(null);
    setReason(undefined);
    if (!request || request.params.request.method !== 'eth_sendTransaction') return;
    const chainId = Number(String(request.params.chainId).split(':')[1]);
    const cfg = evmConfigByChainId(chainId);
    if (!cfg) return;
    const tx = request.params.request.params[0] ?? {};
    setStatus('loading');
    dryRunEvm(cfg.rpcUrl, { from: tx.from, to: tx.to, value: tx.value, data: tx.data })
      .then((r) => { if (alive) { setStatus(r.status); setReason(r.revertReason); } })
      .catch(() => { if (alive) setStatus('unknown'); });
    return () => { alive = false; };
  }, [request]);
  return { status, reason };
}

export function WalletConnectModals() {
  const wc = useWalletConnect();
  const proposal = wc.proposal;
  const request = wc.request;
  const sim = useSimulation(request);

  return (
    <>
      <Modal visible={!!proposal} transparent animationType="slide" onRequestClose={wc.rejectProposal}>
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            <Text style={styles.title}>Connect to dApp</Text>
            {proposal && (
              <>
                <Text style={styles.dappName}>{proposal.params?.proposer?.metadata?.name ?? 'A dApp'}</Text>
                <Text style={styles.dappUrl}>{proposal.params?.proposer?.metadata?.url ?? ''}</Text>
                <Text style={styles.body}>
                  This will let the dApp see your EVM address and request signatures. It cannot move
                  funds without your explicit approval each time.
                </Text>
              </>
            )}
            {wc.error && <Text style={styles.err}>{wc.error}</Text>}
            <View style={styles.actions}>
              <Button title="Reject" variant="ghost" onPress={wc.rejectProposal} style={styles.flex} />
              <Button title="Connect" onPress={wc.approveProposal} loading={wc.busy} style={styles.flex} />
            </View>
          </View>
        </View>
      </Modal>

      <Modal visible={!!request} transparent animationType="slide" onRequestClose={wc.rejectRequest}>
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            {request && (() => {
              const d = describe(request);
              return (
                <>
                  <Text style={styles.title}>{d.title}</Text>
                  <View style={styles.reqBox}>
                    {d.lines.map((l, i) => (
                      <Text key={i} style={styles.reqLine} selectable>{l}</Text>
                    ))}
                  </View>

                  {/* Simulation result (eth_sendTransaction only) */}
                  {sim.status === 'loading' && <Text style={styles.simMuted}>Simulating…</Text>}
                  {sim.status === 'ok' && <Text style={styles.simOk}>✓ Simulation: transaction is expected to succeed.</Text>}
                  {sim.status === 'unknown' && <Text style={styles.simMuted}>Could not simulate (RPC unavailable).</Text>}
                  {sim.status === 'revert' && (
                    <View style={styles.warnBox}>
                      <Text style={styles.warnText}>✗ Simulation: this transaction is expected to FAIL{sim.reason ? ` — ${sim.reason}` : ''}.</Text>
                    </View>
                  )}

                  {d.warnings.map((wtext, i) => (
                    <View key={i} style={styles.warnBox}>
                      <Text style={styles.warnText}>⚠ {wtext}</Text>
                    </View>
                  ))}
                  <Text style={styles.body}>Signed on this device behind biometrics. Only approve requests you initiated.</Text>
                </>
              );
            })()}
            {wc.error && <Text style={styles.err}>{wc.error}</Text>}
            <View style={styles.actions}>
              <Button title="Reject" variant="ghost" onPress={wc.rejectRequest} style={styles.flex} />
              <Button title="Approve & sign" onPress={wc.approveRequest} loading={wc.busy} style={styles.flex} />
            </View>
          </View>
        </View>
      </Modal>

      {/* Add network (EIP-3085) */}
      <Modal visible={!!wc.addChainRequest} transparent animationType="slide" onRequestClose={wc.rejectAddChain}>
        <View style={styles.backdrop}>
          <View style={styles.sheet}>
            <Text style={styles.title}>Add network</Text>
            {wc.addChainRequest && (
              <>
                <Text style={styles.body}>A dApp wants Lattice to add a new EVM network.</Text>
                <View style={styles.reqBox}>
                  <Text style={styles.reqLine} selectable>Name: {wc.addChainRequest.config.name}</Text>
                  <Text style={styles.reqLine} selectable>Chain id: {wc.addChainRequest.config.evmChainId}</Text>
                  <Text style={styles.reqLine} selectable>Symbol: {wc.addChainRequest.config.symbol}</Text>
                  <Text style={styles.reqLine} selectable>RPC: {wc.addChainRequest.config.rpcUrl}</Text>
                </View>
                <View style={styles.warnBox}>
                  <Text style={styles.warnText}>
                    ⚠ Adding a network trusts its RPC endpoint with your balance and transaction
                    queries. Lattice will verify the RPC reports this chain id before adding it.
                    Only add networks you recognize.
                  </Text>
                </View>
              </>
            )}
            {wc.error && <Text style={styles.err}>{wc.error}</Text>}
            <View style={styles.actions}>
              <Button title="Reject" variant="ghost" onPress={wc.rejectAddChain} style={styles.flex} />
              <Button title="Add network" onPress={wc.approveAddChain} loading={wc.busy} style={styles.flex} />
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.6)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: colors.surface, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, padding: spacing(5), gap: spacing(3), borderWidth: 1, borderColor: colors.border },
  title: { ...font.h2, fontSize: 20 },
  dappName: { color: colors.text, fontSize: 17, fontWeight: '700' },
  dappUrl: { color: colors.accent, fontSize: 13 },
  body: { color: colors.textDim, fontSize: 13, lineHeight: 19 },
  reqBox: { backgroundColor: colors.surfaceAlt, borderRadius: radius.md, padding: spacing(4), borderWidth: 1, borderColor: colors.border },
  reqLine: { color: colors.text, fontSize: 14, lineHeight: 21 },
  simOk: { color: colors.success, fontSize: 13, fontWeight: '600' },
  simMuted: { color: colors.textFaint, fontSize: 13 },
  warnBox: { backgroundColor: '#2A1A1A', borderRadius: radius.md, padding: spacing(3), borderWidth: 1, borderColor: colors.danger },
  warnText: { color: colors.danger, fontSize: 13, lineHeight: 19, fontWeight: '600' },
  err: { color: colors.danger, fontSize: 13 },
  actions: { flexDirection: 'row', gap: spacing(3), marginTop: spacing(2) },
  flex: { flex: 1 },
});
