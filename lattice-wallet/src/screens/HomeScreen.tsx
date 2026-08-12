import React, { useState } from 'react';
import { RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Screen, Button, Card, StatusBanner, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { formatUnits } from '../core/format';
import { NATIVE_SYMBOL, SECURITY_STATUS } from '../core/config';

export function HomeScreen({ navigation }: any) {
  const w = useWallet();
  const [faucetBusy, setFaucetBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const doFaucet = async () => {
    setMsg(null);
    setFaucetBusy(true);
    try {
      await w.requestFaucet();
      setMsg('Faucet request sent');
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setFaucetBusy(false);
    }
  };

  return (
    <Screen>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={w.refreshing} onRefresh={w.refresh} tintColor={colors.accent} />
        }
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.appName}>Lattice</Text>
            <Text style={styles.net}>
              {w.network.label} {w.online ? '· online' : '· offline'}
            </Text>
          </View>
          <View style={[styles.statusPill, { borderColor: w.online ? colors.success : colors.textFaint }]}>
            <View style={[styles.dot, { backgroundColor: w.online ? colors.success : colors.textFaint }]} />
            <Text style={{ color: w.online ? colors.success : colors.textFaint, fontSize: 12, fontWeight: '700' }}>
              {w.online ? 'LIVE' : 'NO NODE'}
            </Text>
          </View>
        </View>

        <StatusBanner text={SECURITY_STATUS.banner} tone="warning" />

        <Card style={styles.balanceCard}>
          <Text style={styles.balanceLabel}>Total balance</Text>
          <Text style={styles.balance}>
            {w.account ? formatUnits(w.account.balanceBaseUnits) : '—'}{' '}
            <Text style={styles.symbol}>{NATIVE_SYMBOL}</Text>
          </Text>
          <Text style={styles.addr} onPress={() => navigation.navigate('Receive')}>
            {w.address ? shortAddr(w.address) : ''}
          </Text>
          <View style={styles.actionRow}>
            <Button title="Send" onPress={() => navigation.navigate('Send')} style={styles.flex} />
            <Button title="Receive" variant="secondary" onPress={() => navigation.navigate('Receive')} style={styles.flex} />
          </View>
          {w.network.faucetEnabled && (
            <Button title="Request testnet funds" variant="ghost" onPress={doFaucet} loading={faucetBusy} />
          )}
          {msg && <Text style={styles.msg}>{msg}</Text>}
        </Card>

        <Text style={styles.sectionTitle}>Assets</Text>
        <Card>
          <View style={styles.assetRow}>
            <View style={styles.assetIcon}><Text style={styles.assetGlyph}>◇</Text></View>
            <View style={{ flex: 1 }}>
              <Text style={styles.assetName}>XRIQ</Text>
              <Text style={styles.assetSub}>Native unit</Text>
            </View>
            <Text style={styles.assetAmount}>
              {w.account ? formatUnits(w.account.balanceBaseUnits) : '—'}
            </Text>
          </View>
          <View style={styles.sep} />
          <View style={styles.assetRow}>
            <View style={[styles.assetIcon, { backgroundColor: colors.accentSoft }]}>
              <Text style={styles.assetGlyph}>⇄</Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.assetName}>AGNA swaps</Text>
              <Text style={styles.assetSub}>DEX — coming online</Text>
            </View>
            <Button title="Open" variant="ghost" onPress={() => navigation.navigate('SwapTab')} />
          </View>
        </Card>

        <Text style={styles.nonce}>Account nonce: {w.account ? String(w.account.nonce) : '—'}</Text>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(4), paddingBottom: spacing(10) },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  appName: { ...font.h2 },
  net: { ...font.dim, fontSize: 12, marginTop: 2 },
  statusPill: {
    flexDirection: 'row', alignItems: 'center', gap: spacing(2),
    borderWidth: 1, borderRadius: radius.pill, paddingVertical: 4, paddingHorizontal: spacing(3),
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  balanceCard: { gap: spacing(3) },
  balanceLabel: { ...font.dim, fontSize: 13 },
  balance: { fontSize: 40, fontWeight: '800', color: colors.text },
  symbol: { fontSize: 20, color: colors.textDim, fontWeight: '600' },
  addr: { color: colors.accent, fontSize: 13, marginBottom: spacing(2) },
  actionRow: { flexDirection: 'row', gap: spacing(3) },
  flex: { flex: 1 },
  msg: { color: colors.textDim, fontSize: 13, textAlign: 'center' },
  sectionTitle: { ...font.h3, marginTop: spacing(2) },
  assetRow: { flexDirection: 'row', alignItems: 'center', gap: spacing(3), paddingVertical: spacing(1) },
  assetIcon: {
    width: 40, height: 40, borderRadius: 12, backgroundColor: colors.surfaceAlt,
    alignItems: 'center', justifyContent: 'center',
  },
  assetGlyph: { color: colors.accent, fontSize: 20 },
  assetName: { color: colors.text, fontSize: 16, fontWeight: '600' },
  assetSub: { color: colors.textFaint, fontSize: 12 },
  assetAmount: { color: colors.text, fontSize: 16, fontWeight: '700' },
  sep: { height: 1, backgroundColor: colors.border, marginVertical: spacing(3) },
  nonce: { color: colors.textFaint, fontSize: 12, textAlign: 'center' },
});
