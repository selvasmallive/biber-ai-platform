import React, { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Screen, Button, Card, StatusBanner } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { resolveAgnaClient, agnaStatus } from '../core/agna';

export function SwapScreen() {
  const w = useWallet();
  const status = useMemo(() => agnaStatus(resolveAgnaClient()), []);

  return (
    <Screen>
      <Text style={[font.h2, { marginVertical: spacing(4) }]}>Swap · AGNA</Text>

      <Card style={{ gap: spacing(4) }}>
        <View style={styles.leg}>
          <Text style={styles.legLabel}>You pay</Text>
          <View style={styles.legRow}>
            <View style={styles.token}><Text style={styles.tokenGlyph}>◇</Text><Text style={styles.tokenSym}>{w.activeChain.symbol}</Text></View>
            <Text style={styles.amount}>0</Text>
          </View>
        </View>

        <View style={styles.swapIconWrap}><View style={styles.swapIcon}><Text style={{ color: colors.accent, fontSize: 18 }}>↓</Text></View></View>

        <View style={styles.leg}>
          <Text style={styles.legLabel}>You receive</Text>
          <View style={styles.legRow}>
            <View style={[styles.token, { backgroundColor: colors.accentSoft }]}>
              <Text style={styles.tokenGlyph}>?</Text><Text style={styles.tokenSym}>Select</Text>
            </View>
            <Text style={styles.amount}>0</Text>
          </View>
        </View>
      </Card>

      <View style={{ marginTop: spacing(4), gap: spacing(3) }}>
        <StatusBanner text={status.available ? 'AGNA connected' : 'AGNA not yet available'} tone={status.available ? 'info' : 'warning'} />
        <Card>
          <Text style={styles.explainTitle}>About AGNA swaps</Text>
          <Text style={styles.explain}>{status.message}</Text>
          <Text style={styles.explain}>
            Lattice is already wired for AGNA through a non-custodial interface: when the DEX
            API ships, swaps are quoted here, built as on-chain transactions, and signed on
            your device — the exchange never touches your keys. No trade is simulated until
            then.
          </Text>
        </Card>
        <Button title={status.available ? 'Get quote' : 'Swap coming soon'} disabled={!status.available} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  leg: { gap: spacing(2) },
  legLabel: { color: colors.textDim, fontSize: 13, fontWeight: '600' },
  legRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  token: {
    flexDirection: 'row', alignItems: 'center', gap: spacing(2),
    backgroundColor: colors.surfaceAlt, borderRadius: radius.pill,
    paddingVertical: spacing(2), paddingHorizontal: spacing(3),
  },
  tokenGlyph: { color: colors.accent, fontSize: 16 },
  tokenSym: { color: colors.text, fontSize: 15, fontWeight: '700' },
  amount: { color: colors.textFaint, fontSize: 26, fontWeight: '700' },
  swapIconWrap: { alignItems: 'center' },
  swapIcon: {
    width: 36, height: 36, borderRadius: 18, backgroundColor: colors.surfaceAlt,
    alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border,
  },
  explainTitle: { color: colors.text, fontSize: 15, fontWeight: '700', marginBottom: spacing(2) },
  explain: { color: colors.textDim, fontSize: 13, lineHeight: 20, marginBottom: spacing(2) },
});
