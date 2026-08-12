import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { Screen, Button, Card, StatusBanner } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';

// Two-step: generate + display the phrase, require the user to confirm they saved it.
export function BackupScreen({ navigation }: any) {
  const { createWallet } = useWallet();
  const [mnemonic, setMnemonic] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);

  const generate = async () => {
    setBusy(true);
    try {
      setMnemonic(await createWallet());
    } finally {
      setBusy(false);
    }
  };

  const words = mnemonic ? mnemonic.split(' ') : [];

  if (!mnemonic) {
    return (
      <Screen>
        <ScrollView contentContainerStyle={styles.content}>
          <Text style={font.h2}>Back up your wallet</Text>
          <Text style={styles.p}>
            We'll generate a 24-word recovery phrase. It is the ONLY way to restore your
            wallet. Write it down and store it offline. Anyone with these words controls your
            funds — Lattice cannot recover it for you.
          </Text>
          <StatusBanner text="Never screenshot or share your phrase" tone="danger" />
          <Button title="Generate recovery phrase" onPress={generate} loading={busy} />
        </ScrollView>
      </Screen>
    );
  }

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={font.h2}>Your recovery phrase</Text>
        <Text style={styles.p}>Write these 24 words down in order.</Text>
        <Card>
          <View style={styles.grid}>
            {words.map((w, i) => (
              <View key={i} style={styles.word}>
                <Text style={styles.wordIndex}>{i + 1}</Text>
                <Text style={styles.wordText}>{w}</Text>
              </View>
            ))}
          </View>
        </Card>

        <Button
          title={confirmed ? '✓ I saved it safely' : 'I have written it down'}
          variant={confirmed ? 'secondary' : 'ghost'}
          onPress={() => setConfirmed(true)}
        />
        <Button
          title="Continue to wallet"
          onPress={() => navigation.reset({ index: 0, routes: [{ name: 'Main' }] })}
          disabled={!confirmed}
        />
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(6) },
  p: { ...font.dim, lineHeight: 21 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing(2) },
  word: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    paddingVertical: spacing(2),
    paddingHorizontal: spacing(3),
    width: '31%',
    gap: spacing(2),
  },
  wordIndex: { color: colors.textFaint, fontSize: 11, width: 16 },
  wordText: { color: colors.text, fontSize: 14, fontWeight: '600' },
});
