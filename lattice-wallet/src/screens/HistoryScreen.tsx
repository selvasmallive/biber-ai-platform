import React, { useCallback, useState } from 'react';
import { FlatList, Linking, Pressable, RefreshControl, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Screen, Button, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { formatUnits } from '../core/format';
import { activityForChain, type ActivityEntry } from '../core/activityLog';
import { explorerAddressUrl, explorerTxUrl } from '../core/explorer';

export function HistoryScreen() {
  const w = useWallet();
  const { symbol, decimals } = w.activeChain;
  const [activity, setActivity] = useState<ActivityEntry[]>([]);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      activityForChain(w.activeChain.id).then((a) => alive && setActivity(a));
      return () => { alive = false; };
    }, [w.activeChain.id, w.refreshing]),
  );

  const addressExplorer = w.address ? explorerAddressUrl(w.activeChain, w.address) : null;

  return (
    <Screen>
      <View style={styles.head}>
        <Text style={font.h2}>Activity · {symbol}</Text>
        <View style={styles.privacyPill}>
          <Text style={styles.privacyText}>{w.historyMode === 'indexer' ? 'Indexer on' : 'Private'}</Text>
        </View>
      </View>

      {w.historyMode === 'basic' ? (
        <>
          <Text style={styles.note}>
            Privacy-first: Lattice shows the transactions you make on this device and links to a
            block explorer for the full record — it never sends your address to a history
            service. You can enable indexer history in Settings.
          </Text>
          {addressExplorer && (
            <Button
              title="View full history on explorer"
              variant="ghost"
              onPress={() => Linking.openURL(addressExplorer)}
              style={{ marginBottom: spacing(3) }}
            />
          )}
          <Text style={styles.section}>On this device</Text>
          <FlatList
            data={activity}
            keyExtractor={(item, i) => item.hash || String(i)}
            ItemSeparatorComponent={() => <View style={styles.sep} />}
            renderItem={({ item }) => <LocalRow item={item} chain={w.activeChain} />}
            ListEmptyComponent={<Text style={styles.empty}>No transactions sent from this device yet.</Text>}
          />
        </>
      ) : (
        <FlatList
          data={w.history}
          keyExtractor={(item, i) => item.hash || String(i)}
          refreshControl={<RefreshControl refreshing={w.refreshing} onRefresh={w.refresh} tintColor={colors.accent} />}
          ItemSeparatorComponent={() => <View style={styles.sep} />}
          renderItem={({ item }) => {
            const url = explorerTxUrl(w.activeChain, item.hash);
            const outgoing = item.direction === 'out';
            const sign = outgoing ? '−' : item.direction === 'in' ? '+' : '';
            return (
              <Pressable style={styles.row} onPress={() => url && Linking.openURL(url)}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.title}>
                    {item.direction === 'in' ? 'Received' : item.direction === 'out' ? 'Sent' : 'Transfer'}
                  </Text>
                  <Text style={styles.sub}>{shortAddr(item.hash || '—')}</Text>
                </View>
                <Text style={styles.amount}>
                  {item.amountBaseUnits !== undefined ? `${sign}${formatUnits(item.amountBaseUnits, decimals)} ${symbol}` : '—'}
                </Text>
              </Pressable>
            );
          }}
          ListEmptyComponent={<Text style={styles.empty}>{w.online ? 'No transactions found.' : 'Connect to load indexer history.'}</Text>}
        />
      )}
    </Screen>
  );
}

function LocalRow({ item, chain }: { item: ActivityEntry; chain: any }) {
  const url = explorerTxUrl(chain, item.hash);
  return (
    <Pressable style={styles.row} onPress={() => url && Linking.openURL(url)}>
      <View style={styles.icon}><Text style={{ color: colors.accent, fontSize: 18 }}>↑</Text></View>
      <View style={{ flex: 1 }}>
        <Text style={styles.title}>Sent to {shortAddr(item.to)}</Text>
        <Text style={styles.sub}>tap to view on explorer</Text>
      </View>
      <Text style={styles.amount}>−{item.amount}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: spacing(4) },
  privacyPill: { borderWidth: 1, borderColor: colors.success, borderRadius: radius.pill, paddingVertical: 3, paddingHorizontal: spacing(3) },
  privacyText: { color: colors.success, fontSize: 11, fontWeight: '700' },
  note: { color: colors.textDim, fontSize: 13, lineHeight: 19, marginBottom: spacing(3) },
  section: { color: colors.textFaint, fontSize: 12, fontWeight: '700', marginBottom: spacing(2), textTransform: 'uppercase' },
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing(3), paddingVertical: spacing(3) },
  icon: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.surfaceAlt, alignItems: 'center', justifyContent: 'center' },
  title: { color: colors.text, fontSize: 15, fontWeight: '600' },
  sub: { color: colors.textFaint, fontSize: 12, marginTop: 2 },
  amount: { color: colors.text, fontSize: 15, fontWeight: '700' },
  sep: { height: 1, backgroundColor: colors.border },
  empty: { color: colors.textFaint, fontSize: 14, textAlign: 'center', marginTop: spacing(8) },
});
