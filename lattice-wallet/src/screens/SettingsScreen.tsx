import React, { useState } from 'react';
import { Alert, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';
import { Screen, Button, Card, StatusBanner, Divider } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { SECURITY_STATUS } from '../core/config';
import { shortAddr } from '../components/ui';

export function SettingsScreen({ navigation }: any) {
  const w = useWallet();
  const [revealed, setRevealed] = useState<string | null>(null);
  const [rpcInput, setRpcInput] = useState('');
  const [rpcSaved, setRpcSaved] = useState(false);

  const saveRpc = async () => {
    await w.setRpcOverride(w.activeChain.id, rpcInput.trim());
    setRpcSaved(true);
    setTimeout(() => setRpcSaved(false), 1500);
  };

  const reveal = async () => {
    try {
      const phrase = await w.revealPhrase();
      setRevealed(phrase);
    } catch (e) {
      Alert.alert('Could not reveal', (e as Error).message);
    }
  };

  const confirmWipe = () => {
    Alert.alert(
      'Remove wallet?',
      'This deletes your keys from this device. You can only restore with your recovery phrase. Make sure it is backed up.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: async () => {
            await w.wipe();
            navigation.reset({ index: 0, routes: [{ name: 'Onboarding' }] });
          },
        },
      ],
    );
  };

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={font.h2}>Settings</Text>

        <Text style={styles.section}>Networks</Text>
        <Card style={{ gap: spacing(2) }}>
          {w.chains.map((c) => {
            const active = c.id === w.activeChain.id;
            const custom = w.customChains.some((x) => x.id === c.id);
            return (
              <View key={c.id} style={styles.netRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.netName}>
                    {c.name}{c.isTestnet ? ' · testnet' : ''}{custom ? ' · custom' : ''}
                  </Text>
                  <Text style={styles.netSub}>
                    {w.addresses[c.id] ? shortAddr(w.addresses[c.id]) : c.symbol} · {c.rpcUrl}
                  </Text>
                </View>
                {custom && (
                  <Button title="Remove" variant="ghost" onPress={() => c.evmChainId != null && w.removeCustomNetwork(c.evmChainId)} />
                )}
                <Button
                  title={active ? '✓ Active' : 'Use'}
                  variant={active ? 'secondary' : 'ghost'}
                  onPress={() => w.setActiveChain(c.id)}
                />
              </View>
            );
          })}
          <Button title="+ Add EVM network" variant="ghost" onPress={() => navigation.navigate('AddNetwork')} />
        </Card>

        <Text style={styles.section}>Privacy</Text>
        <Card style={{ gap: spacing(3) }}>
          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>Indexer transaction history</Text>
              <Text style={styles.rowSub}>
                Off (recommended): history stays private — the app shows transactions you make on
                this device and links to a block explorer, never sending your address to a history
                service. On: fetch full history from a third-party indexer.
              </Text>
            </View>
            <Switch
              value={w.historyMode === 'indexer'}
              onValueChange={(on) => w.setHistoryMode(on ? 'indexer' : 'basic')}
              trackColor={{ true: colors.warning, false: colors.surfaceAlt }}
              thumbColor="#fff"
            />
          </View>
          <Divider />
          <Text style={styles.rowTitle}>Custom RPC — {w.activeChain.name}</Text>
          <Text style={styles.rowSub}>
            Point this chain at your own node so no third party sees your queries. Blank uses the
            default ({w.activeChain.rpcUrl}).
          </Text>
          <TextInput
            style={styles.input}
            value={rpcInput}
            onChangeText={setRpcInput}
            placeholder={w.rpcOverrides[w.activeChain.id] ?? w.activeChain.rpcUrl}
            placeholderTextColor={colors.textFaint}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <Button title={rpcSaved ? '✓ Saved' : 'Save RPC endpoint'} variant="ghost" onPress={saveRpc} />
          <Divider />
          <Button title="Address book" variant="ghost" onPress={() => navigation.navigate('AddressBook')} />
          <Button title="WalletConnect — connect to dApps" variant="ghost" onPress={() => navigation.navigate('WalletConnect')} />
        </Card>

        <Text style={styles.section}>Security</Text>
        <Card style={{ gap: spacing(3) }}>
          <View style={styles.switchRow}>
            <View style={{ flex: 1 }}>
              <Text style={styles.rowTitle}>Post-quantum signing</Text>
              <Text style={styles.rowSub}>
                Adds a real ML-DSA-65 (Dilithium) hybrid signature alongside Ed25519. Chain-side
                PQ verification lands with the XRIQ migration.
              </Text>
            </View>
            <Switch
              value={w.pqEnabled}
              onValueChange={w.setPqEnabled}
              trackColor={{ true: colors.pq, false: colors.surfaceAlt }}
              thumbColor="#fff"
            />
          </View>
          <Divider />
          <Text style={styles.rowTitle}>Recovery phrase</Text>
          {revealed ? (
            <>
              <View style={styles.phraseBox}><Text style={styles.phrase} selectable>{revealed}</Text></View>
              <Button title="Hide" variant="ghost" onPress={() => setRevealed(null)} />
            </>
          ) : (
            <Button title="Reveal recovery phrase" variant="ghost" onPress={reveal} />
          )}
        </Card>

        <Text style={styles.section}>Audit status</Text>
        <Card style={{ gap: spacing(2) }}>
          <StatusBanner text={SECURITY_STATUS.banner} tone="warning" />
          <View style={styles.auditRow}>
            <Text style={styles.rowSub}>Independent security audit</Text>
            <Text style={[styles.badge, { color: colors.danger }]}>
              {SECURITY_STATUS.audited ? 'Complete' : 'Not performed'}
            </Text>
          </View>
          <View style={styles.auditRow}>
            <Text style={styles.rowSub}>Legal review</Text>
            <Text style={[styles.badge, { color: colors.danger }]}>
              {SECURITY_STATUS.legalReviewed ? 'Complete' : 'Not performed'}
            </Text>
          </View>
          <Text style={styles.disclaimer}>
            Lattice has not had an independent security audit. It is non-custodial: you hold your
            keys and are responsible for your funds. Verify every transaction before signing.
          </Text>
        </Card>

        <Button title="Remove wallet from this device" variant="danger" onPress={confirmWipe} />
        <Text style={styles.version}>Lattice 0.1.0 · non-custodial · keys stored in device secure enclave</Text>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(3), paddingVertical: spacing(4), paddingBottom: spacing(10) },
  section: { ...font.h3, marginTop: spacing(3) },
  netRow: { flexDirection: 'row', alignItems: 'center', gap: spacing(3) },
  netName: { color: colors.text, fontSize: 15, fontWeight: '600' },
  netSub: { color: colors.textFaint, fontSize: 11, marginTop: 2 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: spacing(3) },
  input: { height: 48, backgroundColor: colors.surfaceAlt, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, color: colors.text, paddingHorizontal: spacing(3), fontSize: 13 },
  rowTitle: { color: colors.text, fontSize: 15, fontWeight: '600' },
  rowSub: { color: colors.textDim, fontSize: 12, lineHeight: 18, marginTop: 2 },
  phraseBox: {
    backgroundColor: colors.surfaceAlt, borderRadius: radius.md, padding: spacing(4),
    borderWidth: 1, borderColor: colors.pq,
  },
  phrase: { color: colors.text, fontSize: 15, lineHeight: 26 },
  auditRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  badge: { fontSize: 13, fontWeight: '700' },
  disclaimer: { color: colors.textFaint, fontSize: 12, lineHeight: 18, marginTop: spacing(2) },
  version: { color: colors.textFaint, fontSize: 11, textAlign: 'center', marginTop: spacing(4) },
});
