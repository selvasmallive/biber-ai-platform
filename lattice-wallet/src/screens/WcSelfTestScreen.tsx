import React, { useState } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { Screen, Button, Card, StatusBanner } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { runWcSelfTest, type Step } from '../dev/wcSelfTest';

type Outcome = 'idle' | 'running' | 'pass' | 'fail';

export function WcSelfTestScreen() {
  const [steps, setSteps] = useState<Step[]>([]);
  const [outcome, setOutcome] = useState<Outcome>('idle');

  const run = async () => {
    setSteps([]);
    setOutcome('running');
    const ok = await runWcSelfTest((s) => setSteps((prev) => [...prev, s]));
    setOutcome(ok ? 'pass' : 'fail');
  };

  return (
    <Screen>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={font.h2}>WalletConnect self-test</Text>
        <Text style={styles.p}>
          Runs a real WalletConnect handshake over the relay — a dApp client connects to the
          wallet client, the session is approved, a message is signed, and the signature is
          verified to recover to the wallet address. Uses a throwaway test key (no biometric,
          not your account). Needs a network connection and a dev/EAS build (not Expo Go).
        </Text>

        {outcome === 'pass' && <StatusBanner text="Handshake OK — all steps passed ✓" tone="info" />}
        {outcome === 'fail' && <StatusBanner text="Handshake failed — see steps below" tone="danger" />}

        <Button title={outcome === 'running' ? 'Running…' : 'Run handshake test'} onPress={run} loading={outcome === 'running'} />

        {steps.length > 0 && (
          <Card style={{ gap: spacing(2) }}>
            {steps.map((s, i) => (
              <View key={i} style={styles.row}>
                <Text style={[styles.mark, { color: s.ok ? colors.success : colors.danger }]}>{s.ok ? '✓' : '✗'}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.stepName}>{s.name}</Text>
                  {s.detail ? <Text style={styles.stepDetail}>{s.detail}</Text> : null}
                </View>
              </View>
            ))}
          </Card>
        )}
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: { gap: spacing(4), paddingVertical: spacing(4) },
  p: { ...font.dim, lineHeight: 20 },
  row: { flexDirection: 'row', gap: spacing(3), alignItems: 'flex-start' },
  mark: { fontSize: 16, fontWeight: '800', width: 18 },
  stepName: { color: colors.text, fontSize: 14, fontWeight: '600' },
  stepDetail: { color: colors.textFaint, fontSize: 12, marginTop: 2 },
});
