import React from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
  TextStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { colors, radius, spacing } from '../theme/theme';

export function Screen({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return (
    <SafeAreaView style={[styles.screen, style]} edges={['top', 'left', 'right']}>
      {children}
    </SafeAreaView>
  );
}

export function Card({ children, style }: { children: React.ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function Button({
  title,
  onPress,
  variant = 'primary',
  loading,
  disabled,
  style,
}: {
  title: string;
  onPress?: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  loading?: boolean;
  disabled?: boolean;
  style?: ViewStyle;
}) {
  const bg =
    variant === 'primary'
      ? colors.accent
      : variant === 'danger'
        ? colors.danger
        : variant === 'secondary'
          ? colors.surfaceAlt
          : 'transparent';
  const fg = variant === 'primary' || variant === 'danger' ? '#0B0E14' : colors.text;
  const isDisabled = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: bg, opacity: isDisabled ? 0.5 : pressed ? 0.85 : 1 },
        variant === 'ghost' && { borderWidth: 1, borderColor: colors.border },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={fg} />
      ) : (
        <Text style={[styles.buttonText, { color: fg }]}>{title}</Text>
      )}
    </Pressable>
  );
}

export function Label({ children, style }: { children: React.ReactNode; style?: TextStyle }) {
  return <Text style={[styles.label, style]}>{children}</Text>;
}

export function Mono({ children, style }: { children: React.ReactNode; style?: TextStyle }) {
  return (
    <Text
      style={[
        { fontFamily: undefined, color: colors.textDim, fontSize: 13, letterSpacing: 0.2 },
        style,
      ]}
      selectable
    >
      {children}
    </Text>
  );
}

export function StatusBanner({ text, tone = 'warning' }: { text: string; tone?: 'warning' | 'danger' | 'info' }) {
  const c = tone === 'danger' ? colors.danger : tone === 'info' ? colors.accent : colors.warning;
  return (
    <View style={[styles.banner, { borderColor: c }]}>
      <View style={[styles.dot, { backgroundColor: c }]} />
      <Text style={[styles.bannerText, { color: c }]}>{text}</Text>
    </View>
  );
}

export function Divider() {
  return <View style={styles.divider} />;
}

export function shortAddr(addr: string, head = 10, tail = 6): string {
  if (addr.length <= head + tail + 1) return addr;
  return `${addr.slice(0, head)}…${addr.slice(-tail)}`;
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, paddingHorizontal: spacing(5) },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    padding: spacing(5),
    borderWidth: 1,
    borderColor: colors.border,
  },
  button: {
    height: 52,
    borderRadius: radius.md,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing(5),
  },
  buttonText: { fontSize: 16, fontWeight: '700' },
  label: { color: colors.textDim, fontSize: 13, marginBottom: spacing(2), fontWeight: '600' },
  banner: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: radius.pill,
    paddingVertical: spacing(2),
    paddingHorizontal: spacing(3),
    gap: spacing(2),
    alignSelf: 'flex-start',
  },
  bannerText: { fontSize: 12, fontWeight: '700' },
  dot: { width: 8, height: 8, borderRadius: 4 },
  divider: { height: 1, backgroundColor: colors.border, marginVertical: spacing(4) },
});
