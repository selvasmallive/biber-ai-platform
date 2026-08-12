import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { Screen, Button, StatusBanner } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { isValidMnemonic } from '../core/xriq';

export function ImportScreen({ navigation }: any) {
  const { importWallet } = useWallet();
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const normalized = phrase.trim().replace(/\s+/g, ' ');
  const wordCount = normalized ? normalized.split(' ').length : 0;
  const looksValid = (wordCount === 12 || wordCount === 24) && isValidMnemonic(normalized);

  const onImport = async () => {
    setError(null);
    setBusy(true);
    try {
      await importWallet(normalized);
      navigation.reset({ index: 0, routes: [{ name: 'Main' }] });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={font.h2}>Import wallet</Text>
        <Text style={styles.p}>Enter your 12 or 24-word recovery phrase, separated by spaces.</Text>
        <TextInput
          style={styles.input}
          value={phrase}
          onChangeText={setPhrase}
          placeholder="word1 word2 word3 …"
          placeholderTextColor={colors.textFaint}
          multiline
          autoCapitalize="none"
          autoCorrect={false}
          textAlignVertical="top"
        />
        <View style={styles.row}>
          <Text style={styles.count}>{wordCount} words</Text>
          {wordCount > 0 && (
            <Text style={{ color: looksValid ? colors.success : colors.textFaint, fontSize: 13 }}>
              {looksValid ? '✓ valid' : 'checking…'}
            </Text>
          )}
        </View>
        {error && <StatusBanner text={error} tone="danger" />}
        <Button title="Import" onPress={onImport} disabled={!looksValid} loading={busy} />
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(6) },
  p: { ...font.dim, lineHeight: 21 },
  input: {
    minHeight: 130,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    padding: spacing(4),
    fontSize: 16,
    lineHeight: 24,
  },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  count: { color: colors.textFaint, fontSize: 13 },
});
