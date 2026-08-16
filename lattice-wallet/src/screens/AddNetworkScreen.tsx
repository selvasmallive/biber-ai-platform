import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Screen, Button, StatusBanner } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { fetchChainId } from '../core/chains/evmRpc';
import type { ChainConfig } from '../core/chains/types';

function parseChainId(input: string): number | null {
  const v = input.trim();
  if (/^0x[0-9a-fA-F]+$/.test(v)) { try { const n = Number(BigInt(v)); return n > 0 ? n : null; } catch { return null; } }
  if (/^\d+$/.test(v)) { const n = Number(v); return n > 0 ? n : null; }
  return null;
}

export function AddNetworkScreen({ navigation }: any) {
  const w = useWallet();
  const [name, setName] = useState('');
  const [chainId, setChainId] = useState('');
  const [rpcUrl, setRpcUrl] = useState('');
  const [symbol, setSymbol] = useState('ETH');
  const [decimals, setDecimals] = useState('18');
  const [explorer, setExplorer] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const num = parseChainId(chainId);
  const httpsRpc = /^https:\/\//i.test(rpcUrl.trim());
  const valid = !!name.trim() && num !== null && httpsRpc;

  const save = async () => {
    if (!valid || num === null) return;
    setError(null);
    setBusy(true);
    try {
      // Verify the RPC actually reports this chain id (spoofed-network guard).
      const actual = await fetchChainId(rpcUrl.trim());
      if (actual !== num) throw new Error(`RPC reports chain id ${actual}, not ${num}. Check the RPC URL.`);
      const config: ChainConfig = {
        id: `evm-${num}`,
        name: name.trim().slice(0, 40),
        symbol: (symbol.trim() || 'ETH').slice(0, 12),
        decimals: Number(decimals) >= 0 && Number.isInteger(Number(decimals)) ? Number(decimals) : 18,
        coinType: 60,
        family: 'evm',
        evmChainId: num,
        rpcUrl: rpcUrl.trim(),
        explorerUrl: /^https:\/\//i.test(explorer.trim()) ? explorer.trim() : undefined,
        isTestnet: false,
        color: '#627EEA',
      };
      await w.addCustomNetwork(config);
      navigation.goBack();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={font.h2}>Add EVM network</Text>
        <Text style={styles.p}>
          Add a custom EVM chain by its RPC endpoint. Lattice verifies the RPC reports the chain
          id you enter before adding it. Only add networks whose RPC you trust — it will see your
          balance and transaction queries.
        </Text>

        <Field label="Network name" value={name} onChange={setName} placeholder="e.g. Arbitrum One" />
        <Field label="Chain id (decimal or 0x…)" value={chainId} onChange={setChainId} placeholder="42161 or 0xa4b1" keyboardType="default" />
        <Field label="RPC URL (https)" value={rpcUrl} onChange={setRpcUrl} placeholder="https://…" />
        <Field label="Currency symbol" value={symbol} onChange={setSymbol} placeholder="ETH" />
        <Field label="Decimals" value={decimals} onChange={setDecimals} placeholder="18" keyboardType="number-pad" />
        <Field label="Block explorer (optional)" value={explorer} onChange={setExplorer} placeholder="https://…" />

        {chainId.length > 0 && num === null && <Text style={styles.warn}>Chain id must be a positive number or 0x-hex</Text>}
        {rpcUrl.length > 0 && !httpsRpc && <Text style={styles.warn}>RPC URL must start with https://</Text>}
        {error && <StatusBanner text={error} tone="danger" />}

        <Button title="Verify & add network" onPress={save} disabled={!valid} loading={busy} />
      </ScrollView>
    </Screen>
  );
}

function Field({ label, value, onChange, placeholder, keyboardType }: any) {
  return (
    <View>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        style={styles.input}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={colors.textFaint}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType={keyboardType}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(3), paddingVertical: spacing(4) },
  p: { ...font.dim, lineHeight: 20 },
  label: { color: colors.textDim, fontSize: 13, marginBottom: spacing(2), fontWeight: '600' },
  input: { height: 50, backgroundColor: colors.surface, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, color: colors.text, paddingHorizontal: spacing(4), fontSize: 15 },
  warn: { color: colors.warning, fontSize: 12 },
});
