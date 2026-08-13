import React, { useCallback, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Screen, Button, Card, StatusBanner, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { formatUnits } from '../core/format';
import { SECURITY_STATUS } from '../core/config';
import { tokensForChain, type Token } from '../core/tokens';
import type { ChainConfig } from '../core/chains/types';

export function HomeScreen({ navigation }: any) {
  const w = useWallet();
  const [faucetBusy, setFaucetBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [tokens, setTokens] = useState<Token[]>([]);
  const [tokenBalances, setTokenBalances] = useState<Record<string, bigint>>({});

  const isEvm = w.activeChain.family === 'evm';

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      if (!isEvm) { setTokens([]); return; }
      (async () => {
        const list = await tokensForChain(w.activeChain.id);
        if (!alive) return;
        setTokens(list);
        const entries = await Promise.all(
          list.map(async (t) => [t.address, await w.getTokenBalance(t).catch(() => 0n)] as const),
        );
        if (alive) setTokenBalances(Object.fromEntries(entries));
      })();
      return () => { alive = false; };
    }, [isEvm, w.activeChain.id, w.address, w.refreshing]),
  );

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
          <Text style={styles.appName}>Lattice</Text>
          <View style={[styles.statusPill, { borderColor: w.online ? colors.success : colors.textFaint }]}>
            <View style={[styles.dot, { backgroundColor: w.online ? colors.success : colors.textFaint }]} />
            <Text style={{ color: w.online ? colors.success : colors.textFaint, fontSize: 12, fontWeight: '700' }}>
              {w.online ? 'LIVE' : 'NO NODE'}
            </Text>
          </View>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          {w.chains.map((c) => (
            <ChainChip key={c.id} chain={c} active={c.id === w.activeChain.id} onPress={() => w.setActiveChain(c.id)} />
          ))}
        </ScrollView>

        <StatusBanner text={SECURITY_STATUS.banner} tone="warning" />

        <Card style={styles.balanceCard}>
          <Text style={styles.balanceLabel}>{w.activeChain.name} balance</Text>
          <Text style={styles.balance}>
            {w.balance !== null ? formatUnits(w.balance, w.activeChain.decimals) : '—'}{' '}
            <Text style={styles.symbol}>{w.activeChain.symbol}</Text>
          </Text>
          <Pressable onPress={() => navigation.navigate('Receive')}>
            <Text style={styles.addr}>{w.address ? shortAddr(w.address) : ''}</Text>
          </Pressable>
          <View style={styles.actionRow}>
            <Button title="Send" onPress={() => navigation.navigate('Send')} style={styles.flex} />
            <Button title="Receive" variant="secondary" onPress={() => navigation.navigate('Receive')} style={styles.flex} />
          </View>
          {w.activeChain.family === 'xriq' && (
            <Button title="Request testnet funds" variant="ghost" onPress={doFaucet} loading={faucetBusy} />
          )}
          {msg && <Text style={styles.msg}>{msg}</Text>}
        </Card>

        {isEvm && (
          <>
            <View style={styles.sectionRow}>
              <Text style={styles.sectionTitle}>Tokens</Text>
              <Pressable onPress={() => navigation.navigate('AddToken')}>
                <Text style={styles.addLink}>+ Add token</Text>
              </Pressable>
            </View>
            <Card>
              {tokens.length === 0 ? (
                <Text style={styles.emptyTokens}>
                  No tokens yet. Add an ERC-20 by contract address — read from your own RPC, no
                  tracker.
                </Text>
              ) : (
                tokens.map((t, i) => (
                  <React.Fragment key={t.address}>
                    {i > 0 && <View style={styles.sep} />}
                    <Pressable style={styles.assetRow} onPress={() => navigation.navigate('TokenSend', { token: t })}>
                      <View style={[styles.assetIcon, { backgroundColor: colors.accentSoft }]}>
                        <Text style={[styles.assetGlyph, { color: colors.accent }]}>◈</Text>
                      </View>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.assetName}>{t.symbol}</Text>
                        <Text style={styles.assetSub}>{t.name}</Text>
                      </View>
                      <Text style={styles.assetAmount}>
                        {tokenBalances[t.address] !== undefined ? formatUnits(tokenBalances[t.address], t.decimals) : '…'}
                      </Text>
                    </Pressable>
                  </React.Fragment>
                ))
              )}
            </Card>
          </>
        )}

        <Text style={styles.sectionTitle}>Networks</Text>
        <Card>
          {w.chains.map((c, i) => (
            <React.Fragment key={c.id}>
              {i > 0 && <View style={styles.sep} />}
              <Pressable style={styles.assetRow} onPress={() => w.setActiveChain(c.id)}>
                <View style={[styles.assetIcon, { backgroundColor: (c.color ?? colors.accent) + '22' }]}>
                  <Text style={[styles.assetGlyph, { color: c.color ?? colors.accent }]}>◇</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.assetName}>{c.name}</Text>
                  <Text style={styles.assetSub}>
                    {w.addresses[c.id] ? shortAddr(w.addresses[c.id]) : c.symbol}
                    {c.isTestnet ? ' · testnet' : ''}
                  </Text>
                </View>
                {c.id === w.activeChain.id ? (
                  <Text style={styles.activeTag}>Active</Text>
                ) : (
                  <Text style={styles.symbolTag}>{c.symbol}</Text>
                )}
              </Pressable>
            </React.Fragment>
          ))}
        </Card>

        <Text style={styles.footnote}>
          One recovery phrase · {w.chains.length} networks · keys stored in the device secure enclave
        </Text>
      </ScrollView>
    </Screen>
  );
}

function ChainChip({ chain, active, onPress }: { chain: ChainConfig; active: boolean; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, active && { borderColor: chain.color ?? colors.accent, backgroundColor: (chain.color ?? colors.accent) + '22' }]}
    >
      <View style={[styles.chipDot, { backgroundColor: chain.color ?? colors.accent }]} />
      <Text style={[styles.chipText, active && { color: colors.text }]}>{chain.symbol}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(4), paddingBottom: spacing(10) },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  appName: { ...font.h2 },
  statusPill: {
    flexDirection: 'row', alignItems: 'center', gap: spacing(2),
    borderWidth: 1, borderRadius: radius.pill, paddingVertical: 4, paddingHorizontal: spacing(3),
  },
  dot: { width: 7, height: 7, borderRadius: 4 },
  chips: { gap: spacing(2), paddingVertical: spacing(1) },
  chip: {
    flexDirection: 'row', alignItems: 'center', gap: spacing(2),
    borderWidth: 1, borderColor: colors.border, borderRadius: radius.pill,
    paddingVertical: spacing(2), paddingHorizontal: spacing(3),
  },
  chipDot: { width: 8, height: 8, borderRadius: 4 },
  chipText: { color: colors.textDim, fontSize: 13, fontWeight: '700' },
  balanceCard: { gap: spacing(3) },
  balanceLabel: { ...font.dim, fontSize: 13 },
  balance: { fontSize: 38, fontWeight: '800', color: colors.text },
  symbol: { fontSize: 20, color: colors.textDim, fontWeight: '600' },
  addr: { color: colors.accent, fontSize: 13, marginBottom: spacing(2) },
  actionRow: { flexDirection: 'row', gap: spacing(3) },
  flex: { flex: 1 },
  msg: { color: colors.textDim, fontSize: 13, textAlign: 'center' },
  sectionTitle: { ...font.h3, marginTop: spacing(2) },
  sectionRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: spacing(2) },
  addLink: { color: colors.accent, fontSize: 13, fontWeight: '700' },
  emptyTokens: { color: colors.textFaint, fontSize: 13, lineHeight: 19 },
  assetAmount: { color: colors.text, fontSize: 15, fontWeight: '700' },
  assetRow: { flexDirection: 'row', alignItems: 'center', gap: spacing(3), paddingVertical: spacing(2) },
  assetIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  assetGlyph: { fontSize: 20 },
  assetName: { color: colors.text, fontSize: 15, fontWeight: '600' },
  assetSub: { color: colors.textFaint, fontSize: 12 },
  activeTag: { color: colors.success, fontSize: 12, fontWeight: '700' },
  symbolTag: { color: colors.textFaint, fontSize: 13, fontWeight: '600' },
  sep: { height: 1, backgroundColor: colors.border, marginVertical: spacing(1) },
  footnote: { color: colors.textFaint, fontSize: 12, textAlign: 'center', marginTop: spacing(2) },
});
