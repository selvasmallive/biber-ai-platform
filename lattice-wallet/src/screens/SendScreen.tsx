import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Screen, Button, Card, StatusBanner, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { isValidAddress } from '../core/xriq';
import { formatUnits, parseUnits } from '../core/format';
import { NATIVE_SYMBOL } from '../core/config';

type Step = 'edit' | 'review' | 'done';

export function SendScreen({ navigation }: any) {
  const w = useWallet();
  const [to, setTo] = useState('');
  const [amount, setAmount] = useState('');
  const [fee, setFee] = useState('1');
  const [step, setStep] = useState<Step>('edit');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);

  const parsed = useMemo(() => {
    try {
      if (!to || !amount) return null;
      if (!isValidAddress(to)) return { error: 'Recipient address is not a valid XRIQ address' };
      const amountBaseUnits = parseUnits(amount);
      const feeBaseUnits = parseUnits(fee || '0');
      if (amountBaseUnits <= 0n) return { error: 'Amount must be greater than zero' };
      if (w.address && to.trim() === w.address) return { error: 'Cannot send to your own address' };
      const total = amountBaseUnits + feeBaseUnits;
      if (w.account && total > w.account.balanceBaseUnits)
        return { error: 'Amount + fee exceeds balance' };
      return { amountBaseUnits, feeBaseUnits, total };
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [to, amount, fee, w.address, w.account]);

  const valid = parsed && !('error' in parsed);

  const confirm = async () => {
    if (!valid) return;
    setError(null);
    setBusy(true);
    try {
      const res = await w.send({
        to,
        amountBaseUnits: (parsed as any).amountBaseUnits,
        feeBaseUnits: (parsed as any).feeBaseUnits,
      });
      setTxHash(res.transactionHash);
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
          <Text style={styles.p}>Your signed transfer was sent to the node's mempool.</Text>
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
        <Text style={font.h2}>Send {NATIVE_SYMBOL}</Text>

        <View>
          <Text style={styles.label}>Recipient address</Text>
          <TextInput
            style={styles.input}
            value={to}
            onChangeText={(v) => { setTo(v); setStep('edit'); }}
            placeholder="xriqdev1…"
            placeholderTextColor={colors.textFaint}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>

        <View>
          <Text style={styles.label}>Amount ({NATIVE_SYMBOL})</Text>
          <TextInput
            style={styles.input}
            value={amount}
            onChangeText={(v) => { setAmount(v); setStep('edit'); }}
            placeholder="0"
            placeholderTextColor={colors.textFaint}
            keyboardType="number-pad"
          />
          {w.account && (
            <Text style={styles.avail}>Available: {formatUnits(w.account.balanceBaseUnits)} {NATIVE_SYMBOL}</Text>
          )}
        </View>

        <View>
          <Text style={styles.label}>Network fee ({NATIVE_SYMBOL})</Text>
          <TextInput
            style={styles.input}
            value={fee}
            onChangeText={(v) => { setFee(v); setStep('edit'); }}
            placeholder="1"
            placeholderTextColor={colors.textFaint}
            keyboardType="number-pad"
          />
        </View>

        {parsed && 'error' in parsed && parsed.error && (
          <StatusBanner text={parsed.error} tone="danger" />
        )}
        {error && <StatusBanner text={error} tone="danger" />}

        {step === 'review' && valid ? (
          <Card style={{ gap: spacing(2) }}>
            <Row k="To" v={shortAddr(to)} />
            <Row k="Amount" v={`${formatUnits((parsed as any).amountBaseUnits)} ${NATIVE_SYMBOL}`} />
            <Row k="Fee" v={`${formatUnits((parsed as any).feeBaseUnits)} ${NATIVE_SYMBOL}`} />
            <View style={styles.sep} />
            <Row k="Total" v={`${formatUnits((parsed as any).total)} ${NATIVE_SYMBOL}`} bold />
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

function Row({ k, v, bold }: { k: string; v: string; bold?: boolean }) {
  return (
    <View style={styles.row}>
      <Text style={styles.kLabel}>{k}</Text>
      <Text style={[styles.kValue, bold && { fontWeight: '800', fontSize: 16 }]}>{v}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(4) },
  label: { color: colors.textDim, fontSize: 13, marginBottom: spacing(2), fontWeight: '600' },
  input: {
    height: 52, backgroundColor: colors.surface, borderRadius: radius.md,
    borderWidth: 1, borderColor: colors.border, color: colors.text,
    paddingHorizontal: spacing(4), fontSize: 16,
  },
  avail: { color: colors.textFaint, fontSize: 12, marginTop: spacing(2) },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  kLabel: { color: colors.textDim, fontSize: 14 },
  kValue: { color: colors.text, fontSize: 14, fontWeight: '600' },
  sep: { height: 1, backgroundColor: colors.border, marginVertical: spacing(1) },
  signNote: { color: colors.textFaint, fontSize: 12, lineHeight: 18 },
  p: { ...font.dim, textAlign: 'center' },
  doneWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing(4) },
  check: {
    width: 72, height: 72, borderRadius: 36, backgroundColor: colors.accentSoft,
    alignItems: 'center', justifyContent: 'center',
  },
  checkGlyph: { color: colors.success, fontSize: 36, fontWeight: '800' },
  hash: { color: colors.accent, fontSize: 13, marginTop: spacing(2) },
});
