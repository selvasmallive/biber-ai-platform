import React, { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Screen, Button, Card, StatusBanner, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { parseUnits, formatUnits } from '../core/format';
import { isEnsName } from '../core/ens';
import type { Token } from '../core/tokens';

export function TokenSendScreen({ route, navigation }: any) {
  const w = useWallet();
  const token: Token = route.params.token;
  const [to, setTo] = useState('');
  const [amount, setAmount] = useState('');
  const [review, setReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);
  const [resolvedName, setResolvedName] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);

  const nameInput = to.trim();
  useEffect(() => {
    let alive = true;
    if (isEnsName(nameInput)) {
      setResolving(true);
      w.resolveName(nameInput).then((a) => alive && setResolvedName(a)).catch(() => alive && setResolvedName(null)).finally(() => alive && setResolving(false));
    } else { setResolvedName(null); setResolving(false); }
    return () => { alive = false; };
  }, [nameInput, w]);

  const targetAddress = isEnsName(nameInput) ? resolvedName ?? '' : nameInput;

  const parsed = useMemo(() => {
    try {
      if (!to || !amount) return null;
      if (isEnsName(nameInput) && resolving) return { error: 'Resolving name…' };
      if (isEnsName(nameInput) && !resolvedName) return { error: 'Name did not resolve' };
      if (!w.activeAdapter.validateAddress(targetAddress)) return { error: 'Invalid recipient address' };
      const amountBaseUnits = parseUnits(amount, token.decimals);
      if (amountBaseUnits <= 0n) return { error: 'Amount must be greater than zero' };
      return { amountBaseUnits };
    } catch (e) {
      return { error: (e as Error).message };
    }
  }, [to, amount, nameInput, resolving, resolvedName, targetAddress, token.decimals, w.activeAdapter]);

  const valid = parsed && !('error' in parsed);

  const confirm = async () => {
    if (!valid) return;
    setError(null);
    setBusy(true);
    try {
      const display = formatUnits((parsed as any).amountBaseUnits, token.decimals);
      const res = await w.sendToken(token, targetAddress, (parsed as any).amountBaseUnits, display);
      setTxHash(res.hash);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (txHash) {
    return (
      <Screen>
        <View style={styles.doneWrap}>
          <View style={styles.check}><Text style={styles.checkGlyph}>✓</Text></View>
          <Text style={font.h2}>{token.symbol} sent</Text>
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
        <Text style={font.h2}>Send {token.symbol}</Text>
        <Text style={styles.chainTag}>{token.name} · on {w.activeChain.name}</Text>

        <View>
          <Text style={styles.label}>Recipient address or ENS name</Text>
          <TextInput style={styles.input} value={to} onChangeText={(v) => { setTo(v); setReview(false); }} placeholder="0x… or name.eth" placeholderTextColor={colors.textFaint} autoCapitalize="none" autoCorrect={false} />
          {isEnsName(nameInput) && (
            <Text style={[styles.hintline, { color: resolvedName ? colors.success : colors.textFaint }]}>
              {resolving ? 'Resolving…' : resolvedName ? `→ ${shortAddr(resolvedName)}` : 'no address record'}
            </Text>
          )}
        </View>

        <View>
          <Text style={styles.label}>Amount ({token.symbol})</Text>
          <TextInput style={styles.input} value={amount} onChangeText={(v) => { setAmount(v); setReview(false); }} placeholder="0" placeholderTextColor={colors.textFaint} keyboardType="decimal-pad" />
        </View>

        {parsed && 'error' in parsed && parsed.error && <StatusBanner text={parsed.error} tone="danger" />}
        {error && <StatusBanner text={error} tone="danger" />}

        {review && valid ? (
          <Card style={{ gap: spacing(2) }}>
            <Text style={styles.previewTitle}>You are sending</Text>
            <Text style={styles.previewBig}>{formatUnits((parsed as any).amountBaseUnits, token.decimals)} {token.symbol}</Text>
            <Text style={styles.previewTo}>to {shortAddr(targetAddress)}</Text>
            <Text style={styles.previewContract}>via contract {shortAddr(token.address)}</Text>
            <Text style={styles.signNote}>Confirm with biometrics. Signed on this device; keys never leave it.</Text>
            <Button title="Confirm & sign" onPress={confirm} loading={busy} />
          </Card>
        ) : (
          <Button title="Review" onPress={() => setReview(true)} disabled={!valid} />
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(4) },
  chainTag: { color: colors.textDim, fontSize: 13, marginTop: -spacing(2) },
  label: { color: colors.textDim, fontSize: 13, marginBottom: spacing(2), fontWeight: '600' },
  input: { height: 52, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, color: colors.text, paddingHorizontal: spacing(4), fontSize: 16 },
  hintline: { fontSize: 12, marginTop: spacing(2) },
  previewTitle: { color: colors.textDim, fontSize: 13 },
  previewBig: { color: colors.text, fontSize: 26, fontWeight: '800' },
  previewTo: { color: colors.text, fontSize: 14 },
  previewContract: { color: colors.textFaint, fontSize: 12 },
  signNote: { color: colors.textFaint, fontSize: 12, lineHeight: 18 },
  kLabel: { color: colors.textDim, fontSize: 14 },
  hash: { color: colors.accent, fontSize: 13, marginTop: spacing(2) },
  doneWrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing(4) },
  check: { width: 72, height: 72, borderRadius: 36, backgroundColor: colors.accentSoft, alignItems: 'center', justifyContent: 'center' },
  checkGlyph: { color: colors.success, fontSize: 36, fontWeight: '800' },
});
