import React from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { Screen, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { formatUnits } from '../core/format';
import type { HistoryEntry } from '../core/rpc';

export function HistoryScreen() {
  const w = useWallet();
  const { symbol, decimals } = w.activeChain;

  return (
    <Screen>
      <Text style={[font.h2, { marginVertical: spacing(4) }]}>Activity · {symbol}</Text>
      <FlatList
        data={w.history}
        keyExtractor={(item, i) => item.hash || String(i)}
        refreshControl={
          <RefreshControl refreshing={w.refreshing} onRefresh={w.refresh} tintColor={colors.accent} />
        }
        ItemSeparatorComponent={() => <View style={styles.sep} />}
        renderItem={({ item }) => <TxRow item={item} symbol={symbol} decimals={decimals} />}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyGlyph}>◇</Text>
            <Text style={styles.emptyText}>
              {w.online ? 'No transactions yet' : 'Connect to a node to load activity'}
            </Text>
          </View>
        }
        contentContainerStyle={w.history.length === 0 && { flex: 1 }}
      />
    </Screen>
  );
}

function TxRow({ item, symbol, decimals }: { item: HistoryEntry; symbol: string; decimals: number }) {
  const outgoing = item.direction === 'out';
  const sign = outgoing ? '−' : item.direction === 'in' ? '+' : '';
  const color = outgoing ? colors.text : item.direction === 'in' ? colors.success : colors.textDim;
  const counterparty = outgoing ? item.to : item.from;
  return (
    <View style={styles.row}>
      <View style={[styles.icon, { backgroundColor: colors.surfaceAlt }]}>
        <Text style={{ color: colors.accent, fontSize: 18 }}>{outgoing ? '↑' : item.direction === 'in' ? '↓' : '↔'}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.title}>
          {item.direction === 'in' ? 'Received' : item.direction === 'out' ? 'Sent' : 'Transfer'}
        </Text>
        <Text style={styles.sub}>{counterparty ? shortAddr(counterparty) : shortAddr(item.hash || '—')}</Text>
      </View>
      <View style={{ alignItems: 'flex-end' }}>
        <Text style={[styles.amount, { color }]}>
          {item.amountBaseUnits !== undefined ? `${sign}${formatUnits(item.amountBaseUnits, decimals)}` : '—'}
        </Text>
        <Text style={styles.symbol}>{symbol}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing(3), paddingVertical: spacing(3) },
  icon: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  title: { color: colors.text, fontSize: 15, fontWeight: '600' },
  sub: { color: colors.textFaint, fontSize: 12, marginTop: 2 },
  amount: { fontSize: 15, fontWeight: '700' },
  symbol: { color: colors.textFaint, fontSize: 11 },
  sep: { height: 1, backgroundColor: colors.border },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing(3) },
  emptyGlyph: { color: colors.textFaint, fontSize: 40 },
  emptyText: { color: colors.textFaint, fontSize: 14 },
});
