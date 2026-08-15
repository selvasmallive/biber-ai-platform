import React from 'react';
import { Modal, StyleSheet, Text, View } from 'react-native';
import { Button, shortAddr } from './ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWalletConnect } from '../state/WalletConnectProvider';
import { formatUnits } from '../core/format';
import { evmConfigByChainId } from '../core/chains/registry';

function decodeMessage(raw: string): string {
  if (typeof raw !== 'string') return String(raw);
  if (/^0x[0-9a-fA-F]*$/.test(raw)) {
    try {
      const bytes = new Uint8Array(raw.slice(2).match(/.{1,2}/g)!.map((h) => parseInt(h, 16)));
      const text = new TextDecoder().decode(bytes);
      // Only show as text if it's printable.
      if (/^[\x09\x0a\x0d\x20-\x7e]*$/.test(text)) return text;
    } catch { /* fall through */ }
    return raw;
  }
  return raw;
}

// Human-readable summary of a session request — the "what am I signing" safety screen.
function describe(request: any): { title: string; lines: string[] } {
  const method: string = request.params.request.method;
  const rp: any[] = request.params.request.params;
  const chainId = Number(String(request.params.chainId).split(':')[1]);
  const chainName = evmConfigByChainId(chainId)?.name ?? `chain ${chainId}`;

  if (method === 'personal_sign') {
    return { title: 'Sign message', lines: [`Network: ${chainName}`, '', decodeMessage(rp[0])] };
  }
  if (method === 'eth_signTypedData' || method === 'eth_signTypedData_v4') {
    let primary = 'typed data';
    try {
      const td = typeof rp[1] === 'string' ? JSON.parse(rp[1]) : rp[1];
      primary = td.primaryType ?? primary;
    } catch { /* ignore */ }
    return { title: 'Sign typed data', lines: [`Network: ${chainName}`, `Type: ${primary}`, 'Review the request in the dApp before approving.'] };
  }
  if (method === 'eth_sendTransaction') {
    const tx = rp[0] ?? {};
    const value = tx.value ? formatUnits(BigInt(tx.value), 18) : '0';
    const lines = [
      `Network: ${chainName}`,
      `To: ${tx.to ? shortAddr(tx.to) : '(contract creation)'}`,
      `Amount: ${value} (native)`,
    ];
    if (tx.data && tx.data !== '0x') lines.push('This is a contract interaction.');
    return { title: 'Send transaction', lines };
  }
  return { title: method, lines: ['Unsupported request type — reject unless you trust it.'] };
}

export function WalletConnectModals() {
  const wc = useWalletConnect();
  const proposal = wc.proposal;
  const request = wc.request;

  return (
    <>
      {/* Session proposal */}
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

      {/* Session request (sign / send) */}
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
  err: { color: colors.danger, fontSize: 13 },
  actions: { flexDirection: 'row', gap: spacing(3), marginTop: spacing(2) },
  flex: { flex: 1 },
});
