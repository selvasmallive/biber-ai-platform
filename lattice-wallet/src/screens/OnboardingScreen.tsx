import React from 'react';
import { Text, View, StyleSheet } from 'react-native';
import { Screen, Button, StatusBanner } from '../components/ui';
import { colors, spacing, font } from '../theme/theme';
import { SECURITY_STATUS } from '../core/config';

export function OnboardingScreen({ navigation }: any) {
  return (
    <Screen>
      <View style={styles.container}>
        <View style={styles.hero}>
          <View style={styles.mark}>
            <View style={styles.markGrid}>
              {Array.from({ length: 9 }).map((_, i) => (
                <View key={i} style={styles.markCell} />
              ))}
            </View>
          </View>
          <Text style={styles.title}>Lattice</Text>
          <Text style={styles.tagline}>
            A non-custodial wallet for XRIQ — post-quantum-ready signing, keys that never
            leave your device.
          </Text>
          <StatusBanner text={SECURITY_STATUS.banner} tone="warning" />
        </View>

        <View style={styles.actions}>
          <Button title="Create a new wallet" onPress={() => navigation.navigate('Backup')} />
          <Button
            title="I already have a recovery phrase"
            variant="ghost"
            onPress={() => navigation.navigate('Import')}
          />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'space-between', paddingVertical: spacing(10) },
  hero: { alignItems: 'center', gap: spacing(5), marginTop: spacing(12) },
  mark: {
    width: 92,
    height: 92,
    borderRadius: 24,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.accentSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  markGrid: { width: 48, height: 48, flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  markCell: { width: 12, height: 12, borderRadius: 3, backgroundColor: colors.accent },
  title: { ...font.h1, fontSize: 40, letterSpacing: 1 },
  tagline: { ...font.dim, textAlign: 'center', lineHeight: 22, paddingHorizontal: spacing(4) },
  actions: { gap: spacing(3) },
});
