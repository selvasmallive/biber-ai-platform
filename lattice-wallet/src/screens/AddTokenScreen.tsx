import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Screen, Button, Card, StatusBanner } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { addToken } from '../core/tokens';
import { isValidChecksum } from '../core/chains/evm';

export function AddTokenScreen({ navigation }: any) {
  const w = useWallet();
  const [address, setAddress] = useState('');
  const [meta, setMeta] = useState<{ symbol: string; decimals: number; name: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validAddr = /^0x[0-9a-fA-F]{40}$/.test(address.trim());

  const fetchMeta = async () => {
    setError(null);
    setBusy(true);
    setMeta(null);
    try {
      const m = await w.fetchTokenMeta(address.trim());
      setMeta(m);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!meta) return;
    await addToken({ chainId: w.activeChain.id, address: address.trim().toLowerCase(), ...meta });
    navigation.goBack();
  };

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={font.h2}>Add a token</Text>
        <Text style={styles.p}>
          Paste the token's contract address. Lattice reads its details from your own RPC — no
          third-party token tracker, so adding a token reveals nothing about you.
        </Text>

        <View>
          <Text style={styles.label}>Contract address on {w.activeChain.name}</Text>
          <TextInput
            style={styles.input}
            value={address}
            onChangeText={(v) => { setAddress(v); setMeta(null); }}
            placeholder="0x…"
            placeholderTextColor={colors.textFaint}
            autoCapitalize="none"
            autoCorrect={false}
          />
          {address.length > 0 && !validAddr && <Text style={styles.warn}>Not a valid contract address</Text>}
        </View>

        {error && <StatusBanner text={error} tone="danger" />}

        {meta ? (
          <Card style={{ gap: spacing(2) }}>
            <Text style={styles.metaSym}>{meta.symbol}</Text>
            <Text style={styles.metaName}>{meta.name}</Text>
            <Text style={styles.metaDec}>{meta.decimals} decimals</Text>
            <Button title={`Add ${meta.symbol}`} onPress={save} />
          </Card>
        ) : (
          <Button title="Fetch token details" onPress={fetchMeta} disabled={!validAddr} loading={busy} />
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(4) },
  p: { ...font.dim, lineHeight: 20 },
  label: { color: colors.textDim, fontSize: 13, marginBottom: spacing(2), fontWeight: '600' },
  input: { height: 52, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, color: colors.text, paddingHorizontal: spacing(4), fontSize: 16 },
  warn: { color: colors.warning, fontSize: 12, marginTop: spacing(2) },
  metaSym: { color: colors.text, fontSize: 22, fontWeight: '800' },
  metaName: { color: colors.textDim, fontSize: 14 },
  metaDec: { color: colors.textFaint, fontSize: 12 },
});
