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
      const hexPart = raw.slice(2);
      const bytes = new Uint8Array((hexPart.match(/.{1,2}/g) ?? []).map((h) => parseInt(h, 16)));
      const text = new TextDecoder().decode(bytes);
      if (/^[\x09\x0a\x0d\x20-\x7e]*$/.test(text) && text.length > 0) return text;
    } catch { /* fall through */ }
    return raw;
  }
  return raw;
}

// ---- eth_sendTransaction calldata decoding (known drain vectors) ----
const SELECTORS: Record<string, string> = {
  '0xa9059cbb': 'transfer',
  '0x095ea7b3': 'approve',
  '0x23b872dd': 'transferFrom',
  '0xa22cb465': 'setApprovalForAll',
  '0x39509351': 'increaseAllowance',
};
const UNLIMITED = 1n << 255n;

function word(data: string, i: number): string {
  return data.slice(10 + i * 64, 10 + (i + 1) * 64);
}
function addrFromWord(w: string): string {
  return '0x' + w.slice(24);
}

function decodeCall(data: string): { lines: string[]; warnings: string[] } {
  const lines: string[] = [];
  const warnings: string[] = [];
  try {
    const sel = data.slice(0, 10).toLowerCase();
    const name = SELECTORS[sel];
    lines.push(`Selector: ${sel}`);
    if (name === 'approve' || name === 'increaseAllowance') {
      const spender = addrFromWord(word(data, 0));
      const amount = BigInt('0x' + word(data, 1));
      const unlimited = amount >= UNLIMITED;
      lines.push(`Function: ${name}`, `Spender: ${shortAddr(spender)}`, `Amount: ${unlimited ? 'UNLIMITED' : amount.toString()}`);
      warnings.push(unlimited
        ? `Grants UNLIMITED token allowance to ${shortAddr(spender)}. A common drain pattern — only approve if you trust it.`
        : `Grants a token spending allowance to ${shortAddr(spender)}.`);
    } else if (name === 'setApprovalForAll') {
      const operator = addrFromWord(word(data, 0));
      const approved = BigInt('0x' + word(data, 1)) !== 0n;
      lines.push('Function: setApprovalForAll', `Operator: ${shortAddr(operator)}`, `Approved: ${approved}`);
      if (approved) warnings.push(`Grants control of ALL your NFTs in this collection to ${shortAddr(operator)}.`);
    } else if (name === 'transfer') {
      lines.push('Function: transfer', `To: ${shortAddr(addrFromWord(word(data, 0)))}`, `Amount: ${BigInt('0x' + word(data, 1)).toString()} (token units)`);
    } else if (name) {
      lines.push(`Function: ${name}`);
    } else {
      warnings.push("Unknown contract call — Lattice can't decode it. Only approve if you trust this dApp.");
    }
  } catch {
    warnings.push('Malformed calldata — do not approve unless you trust this dApp.');
  }
  return { lines, warnings };
}

function flattenMessage(msg: any, prefix = ''): string[] {
  const out: string[] = [];
  for (const [k, v] of Object.entries(msg ?? {})) {
    if (v && typeof v === 'object' && !Array.isArray(v)) out.push(...flattenMessage(v, `${prefix}${k}.`));
    else out.push(`${prefix}${k}: ${Array.isArray(v) ? '[…]' : String(v)}`);
  }
  return out.slice(0, 14);
}

// Human-readable summary of a session request — the "what am I signing" safety screen.
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
      if (/permit/i.test(primary))
        warnings.push('This authorizes token spending (Permit). Verify the spender and amount above.');
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
    const warnings: string[] = [];
    if (tx.data && tx.data !== '0x') {
      const d = decodeCall(tx.data);
      lines.push('', ...d.lines);
      warnings.push(...d.warnings);
    }
    try {
      const maxFee = tx.maxFeePerGas ? BigInt(tx.maxFeePerGas) : tx.gasPrice ? BigInt(tx.gasPrice) : null;
      if (maxFee != null) lines.push(`Max fee/gas: ${formatUnits(maxFee, 9)} gwei`);
    } catch { /* ignore */ }
    return { title: 'Send transaction', lines, warnings };
  }

  return { title: method, lines: ['Unsupported request type — reject unless you trust it.'], warnings: [] };
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
  warnBox: { backgroundColor: '#2A1A1A', borderRadius: radius.md, padding: spacing(3), borderWidth: 1, borderColor: colors.danger },
  warnText: { color: colors.danger, fontSize: 13, lineHeight: 19, fontWeight: '600' },
  err: { color: colors.danger, fontSize: 13 },
  actions: { flexDirection: 'row', gap: spacing(3), marginTop: spacing(2) },
  flex: { flex: 1 },
});
