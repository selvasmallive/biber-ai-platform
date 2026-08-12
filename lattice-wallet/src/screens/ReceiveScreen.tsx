import React, { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import QRCode from 'react-native-qrcode-svg';
import * as Clipboard from 'expo-clipboard';
import { Screen, Button, Card } from '../components/ui';
import { colors, font, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';

export function ReceiveScreen() {
  const { address, activeChain } = useWallet();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    if (!address) return;
    await Clipboard.setStringAsync(address);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Screen>
      <View style={styles.wrap}>
        <Text style={font.h2}>Receive {activeChain.symbol}</Text>
        <Text style={styles.p}>Share this {activeChain.name} address or QR code to receive funds.</Text>
        <Card style={styles.qrCard}>
          <View style={styles.qrBox}>
            {address ? (
              <QRCode value={address} size={216} backgroundColor="#FFFFFF" color="#0B0E14" />
            ) : null}
          </View>
        </Card>
        <Card style={{ width: '100%' }}>
          <Text style={styles.label}>Your address</Text>
          <Text style={styles.addr} selectable>{address}</Text>
        </Card>
        <Button title={copied ? '✓ Copied' : 'Copy address'} onPress={copy} style={{ alignSelf: 'stretch' }} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', gap: spacing(4), paddingVertical: spacing(6) },
  p: { ...font.dim, textAlign: 'center' },
  qrCard: { alignItems: 'center', padding: spacing(5) },
  qrBox: { backgroundColor: '#FFFFFF', padding: spacing(4), borderRadius: 16 },
  label: { color: colors.textDim, fontSize: 13, marginBottom: spacing(2), fontWeight: '600' },
  addr: { color: colors.text, fontSize: 14, lineHeight: 22 },
});
