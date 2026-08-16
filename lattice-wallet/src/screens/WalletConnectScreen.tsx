import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { Screen, Button, Card, StatusBanner, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWalletConnect } from '../state/WalletConnectProvider';

export function WalletConnectScreen({ navigation }: any) {
  const wc = useWalletConnect();
  const [uri, setUri] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const paste = async () => {
    const text = await Clipboard.getStringAsync();
    if (text.startsWith('wc:')) setUri(text);
  };

  const connect = async () => {
    setMsg(null);
    setBusy(true);
    try {
      await wc.pair(uri);
      setUri('');
      setMsg('Pairing… approve the session when it appears.');
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={font.h2}>WalletConnect</Text>
        <Text style={styles.p}>
          Connect Lattice to a dApp. Scan the dApp's WalletConnect QR code, or copy its pairing
          link and paste it here. On a phone, tapping "Lattice" in a dApp opens the app and pairs
          automatically. Every signature and transaction is confirmed on this device behind
          biometrics.
        </Text>

        {!wc.ready && <StatusBanner text="WalletConnect starting…" tone="info" />}
        {wc.error && <StatusBanner text={wc.error} tone="danger" />}

        <Button title="Scan QR code" onPress={() => navigation.navigate('ScanQr')} disabled={!wc.ready} />

        <View>
          <Text style={styles.label}>Or paste a pairing link (wc:…)</Text>
          <TextInput
            style={styles.input}
            value={uri}
            onChangeText={setUri}
            placeholder="wc:…"
            placeholderTextColor={colors.textFaint}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <View style={styles.row}>
            <Button title="Paste" variant="ghost" onPress={paste} style={styles.flex} />
            <Button title="Connect" onPress={connect} disabled={!uri.startsWith('wc:') || !wc.ready} loading={busy} style={styles.flex} />
          </View>
          {msg && <Text style={styles.msg}>{msg}</Text>}
        </View>

        <Text style={styles.section}>Connected dApps</Text>
        {wc.sessions.length === 0 ? (
          <Text style={styles.empty}>No active connections.</Text>
        ) : (
          wc.sessions.map((s) => (
            <Card key={s.topic} style={styles.sessionRow}>
              <View style={{ flex: 1 }}>
                <Text style={styles.sName}>{s.name}</Text>
                <Text style={styles.sUrl}>{s.url || shortAddr(s.topic)}</Text>
              </View>
              <Button title="Disconnect" variant="ghost" onPress={() => wc.disconnect(s.topic)} />
            </Card>
          ))
        )}

        <Text style={styles.note}>
          Note: WalletConnect needs a full app build (it doesn't run in Expo Go). EVM sign /
          send requests are supported; other chains connect natively in Lattice, not via
          WalletConnect.
        </Text>

        <Button title="Run handshake self-test" variant="ghost" onPress={() => navigation.navigate('WcSelfTest')} />
        <Text style={styles.note}>
          Verifies the full pairing → approve → sign → recover flow over the relay (dev build only).
        </Text>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(4) },
  p: { ...font.dim, lineHeight: 20 },
  label: { color: colors.textDim, fontSize: 13, marginBottom: spacing(2), fontWeight: '600' },
  input: { height: 52, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, color: colors.text, paddingHorizontal: spacing(4), fontSize: 15 },
  row: { flexDirection: 'row', gap: spacing(3), marginTop: spacing(3) },
  flex: { flex: 1 },
  msg: { color: colors.textDim, fontSize: 13, marginTop: spacing(2) },
  section: { ...font.h3 },
  empty: { color: colors.textFaint, fontSize: 14 },
  sessionRow: { flexDirection: 'row', alignItems: 'center', gap: spacing(3) },
  sName: { color: colors.text, fontSize: 15, fontWeight: '600' },
  sUrl: { color: colors.textFaint, fontSize: 12, marginTop: 2 },
  note: { color: colors.textFaint, fontSize: 12, lineHeight: 18, marginTop: spacing(2) },
});
