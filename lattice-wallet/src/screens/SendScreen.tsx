import React, { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Screen, Button, Card, StatusBanner, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { formatUnits, parseUnits } from '../core/format';
import { isEnsName } from '../core/ens';

type Step = 'edit' | 'review' | 'done';

export function SendScreen({ navigation }: any) {
  const w = useWallet();
  const chain = w.activeChain;
  const isXriq = chain.family === 'xriq';
  const [to, setTo] = useState('');
  const [amount, setAmount] = useState('');
  const [fee, setFee] = useState('1'); // XRIQ flat fee; EVM estimates automatically
  const [step, setStep] = useState<Step>('edit');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [resolvedName, setResolvedName] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);

  // Resolve ENS names on-chain (Ethereum mainnet) via the wallet's own RPC.
  const nameInput = to.trim();
  useEffect(() => {
    let alive = true;
    if (isEnsName(nameInput)) {
      setResolving(true);
      setResolvedName(null);
      w.resolveName(nameInput)
        .then((addr) => alive && setResolvedName(addr))
        .catch(() => alive && setResolvedName(null))
        .finally(() => alive && setResolving(false));
    } else {
      setResolvedName(null);
      setResolving(false);
    }
    return () => { alive = false; };
  }, [nameInput, w]);

  // The address we actually send to: the ENS resolution when the input is a name.
  const targetAddress = isEnsName(nameInput) ? resolvedName ?? '' : nameInput;

  const parsed = useMemo(() => {
    try {
      if (!to || !amount) return null;
      if (isEnsName(nameInput) && resolving) return { error: 'Resolving name…' };
      if (isEnsName(nameInput) && !resolvedName) return { error: 'Name did not resolve to an address' };
      if (!w.activeAdapter.validateAddress(targetAddress))
        return { error: `Not a valid ${chain.name} address` };
      const amountBaseUnits = parseUnits(amount, chain.decimals);
      if (amountBaseUnits <= 0n) return { error: 'Amount must be greater than zero' };
      if (w.address && targetAddress.toLowerCase() === w.address.toLowerCase())
        return { error: 'Cannot send to your own address' };
      const feeBaseUnits = isXriq ? parseUnits(fee || '0', chain.decimals) : 0n;
      const spend = isXriq ? amountBaseUnits + feeBaseUnits : amountBaseUnits;
      if (w.balance !== null && spend > w.balance)
        return { error: isXriq ? 'Amount + fee exceeds balance' : 'Amount exceeds balance (plus gas)' };
      return { amountBaseUnits, feeBaseUnits, spend };
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [to, amount, fee, isXriq, chain, nameInput, resolving, resolvedName, targetAddress, w.activeAdapter, w.address, w.balance]);

  const valid = parsed && !('error' in parsed);

  const confirm = async () => {
    if (!valid) return;
    setError(null);
    setBusy(true);
    try {
      const displayAmount = `${formatUnits((parsed as any).amountBaseUnits, chain.decimals)} ${chain.symbol}`;
      const req = isXriq
        ? { to: targetAddress, amountBaseUnits: (parsed as any).amountBaseUnits, feeBaseUnits: (parsed as any).feeBaseUnits }
        : { to: targetAddress, amountBaseUnits: (parsed as any).amountBaseUnits };
      const res = await w.send(req, displayAmount);
      setTxHash(res.hash);
      setStep('done');
    } catch (e) {
      setError((e as Error).message);
      setStep('edit');
    } finally {
      setBusy(false);
    }
  };

  if (step === 'done') {
    return (
      <Screen>
        <View style={styles.doneWrap}>
          <View style={styles.check}><Text style={styles.checkGlyph}>✓</Text></View>
          <Text style={font.h2}>Transfer submitted</Text>
          <Text style={styles.p}>Your signed transaction was broadcast to the {chain.name} network.</Text>
          <Card style={{ width: '100%' }}>
            <Text style={styles.kLabel}>Transaction hash</Text>
            <Text style={styles.hash} selectable>{txHash}</Text>
          </Card>
          <Button title="Done" onPress={() => navigation.goBack()} style={{ alignSelf: 'stretch' }} />
        </View>
      </Screen>
    );
  }

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={font.h2}>Send {chain.symbol}</Text>
        <Text style={styles.chainTag}>on {chain.name}</Text>

        <View>
          <Text style={styles.label}>Recipient address{chain.family === 'evm' ? ' or ENS name' : ''}</Text>
          <TextInput
            style={styles.input}
            value={to}
            onChangeText={(v) => { setTo(v); setStep('edit'); }}
            placeholder={isXriq ? 'xriqdev1…' : chain.family === 'evm' ? '0x… or name.eth' : '0x…'}
            placeholderTextColor={colors.textFaint}
            autoCapitalize="none"
            autoCorrect={false}
          />
          {isEnsName(nameInput) && (
            <Text style={[styles.avail, { color: resolvedName ? colors.success : colors.textFaint }]}>
              {resolving ? 'Resolving…' : resolvedName ? `→ ${shortAddr(resolvedName)}` : 'no address record'}
            </Text>
          )}
        </View>

        <View>
          <Text style={styles.label}>Amount ({chain.symbol})</Text>
          <TextInput
            style={styles.input}
            value={amount}
            onChangeText={(v) => { setAmount(v); setStep('edit'); }}
            placeholder="0"
            placeholderTextColor={colors.textFaint}
            keyboardType="decimal-pad"
          />
          {w.balance !== null && (
            <Text style={styles.avail}>Available: {formatUnits(w.balance, chain.decimals)} {chain.symbol}</Text>
          )}
        </View>

        {isXriq ? (
          <View>
            <Text style={styles.label}>Network fee ({chain.symbol})</Text>
            <TextInput
              style={styles.input}
              value={fee}
              onChangeText={(v) => { setFee(v); setStep('edit'); }}
              placeholder="1"
              placeholderTextColor={colors.textFaint}
              keyboardType="number-pad"
            />
          </View>
        ) : (
          <Text style={styles.gasNote}>Gas fee is estimated from the network at signing time (EIP-1559).</Text>
        )}

        {parsed && 'error' in parsed && parsed.error && <StatusBanner text={parsed.error} tone="danger" />}
        {error && <StatusBanner text={error} tone="danger" />}

        {step === 'review' && valid ? (
          <Card style={{ gap: spacing(2) }}>
            <Row k="Network" v={chain.name} />
            <Row k="To" v={shortAddr(to)} />
            <Row k="Amount" v={`${formatUnits((parsed as any).amountBaseUnits, chain.decimals)} ${chain.symbol}`} />
            {isXriq && <Row k="Fee" v={`${formatUnits((parsed as any).feeBaseUnits, chain.decimals)} ${chain.symbol}`} />}
            <Text style={styles.signNote}>
              You'll confirm with biometrics. The transfer is signed on this device — your keys
              never leave it.
            </Text>
            <Button title="Confirm & sign" onPress={confirm} loading={busy} />
          </Card>
        ) : (
          <Button title="Review" onPress={() => setStep('review')} disabled={!valid} />
        )}
      </ScrollView>
    </Screen>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <View style={styles.row}>
      <Text style={styles.kLabel}>{k}</Text>
      <Text style={styles.kValue}>{v}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(4) },
  chainTag: { color: colors.textDim, fontSize: 13, marginTop: -spacing(2) },
  label: { color: colors.textDim, fontSize: 13, marginBottom: spacing(2), fontWeight: '600' },
  input: {
    height: 52, backgroundColor: colors.surface, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.border, color: colors.text,
    paddingHorizontal: spacing(4), fontSize: 16,
  },
  avail: { color: colors.textFaint, fontSize: 12, marginTop: spacing(2) },
  gasNote: { color: colors.textFaint, fontSize: 12, lineHeight: 18 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  kLabel: { color: colors.textDim, fontSize: 14 },
  kValue: { color: colors.text, fontSize: 14, fontWeight: '600' },
  signNote: { color: colors.textFaint, fontSize: 12, lineHeight: 18 },
  p: { ...font.dim, textAlign: 'center' },
  doneWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing(4) },
  check: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.accentSoft, alignItems: 'center', justifyContent: 'center' },
  checkGlyph: { color: colors.success, fontSize: 36, fontWeight: '800' },
  hash: { color: colors.accent, fontSize: 13, marginTop: spacing(2) },
});
