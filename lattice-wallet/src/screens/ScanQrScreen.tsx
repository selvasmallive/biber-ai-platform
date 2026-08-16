import React, { useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { Screen, Button } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWalletConnect } from '../state/WalletConnectProvider';

export function ScanQrScreen({ navigation }: any) {
  const wc = useWalletConnect();
  const [permission, requestPermission] = useCameraPermissions();
  const [error, setError] = useState<string | null>(null);
  const handled = useRef(false);

  const onScan = async ({ data }: { data: string }) => {
    if (handled.current) return;
    const text = (data ?? '').trim();
    if (!text.startsWith('wc:')) return; // ignore non-WalletConnect codes, keep scanning
    handled.current = true;
    try {
      await wc.pair(text);
      navigation.goBack();
    } catch (e) {
      setError((e as Error).message);
      handled.current = false; // allow retry
    }
  };

  if (!permission) {
    return (
      <Screen>
        <View style={styles.center}><Text style={styles.msg}>Checking camera permission…</Text></View>
      </Screen>
    );
  }

  if (!permission.granted) {
    return (
      <Screen>
        <View style={styles.center}>
          <Text style={font.h2}>Scan QR</Text>
          <Text style={styles.msg}>Lattice needs camera access to scan a WalletConnect QR code.</Text>
          <Button title="Allow camera" onPress={requestPermission} />
        </View>
      </Screen>
    );
  }

  return (
    <View style={styles.fill}>
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
        onBarcodeScanned={onScan}
      />
      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.reticle} />
        <Text style={styles.hint}>Point at the dApp's WalletConnect QR code</Text>
        {error && <Text style={styles.err}>{error}</Text>}
      </View>
      <View style={styles.cancelWrap}>
        <Button title="Cancel" variant="ghost" onPress={() => navigation.goBack()} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#000' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing(4), padding: spacing(6) },
  msg: { color: colors.textDim, fontSize: 15, textAlign: 'center', lineHeight: 22 },
  overlay: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', gap: spacing(4) },
  reticle: { width: 240, height: 240, borderWidth: 3, borderColor: colors.accent, borderRadius: radius.lg, backgroundColor: 'transparent' },
  hint: { color: '#fff', fontSize: 14, fontWeight: '600', textShadowColor: '#000', textShadowRadius: 4 },
  err: { color: colors.danger, fontSize: 13, backgroundColor: 'rgba(0,0,0,0.6)', padding: spacing(2), borderRadius: radius.sm },
  cancelWrap: { position: 'absolute', bottom: spacing(10), left: spacing(6), right: spacing(6) },
});
