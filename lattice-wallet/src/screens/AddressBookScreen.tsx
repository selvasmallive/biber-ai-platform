import React, { useCallback, useState } from 'react';
import { Alert, FlatList, StyleSheet, Text, TextInput, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import { Screen, Button, Card, shortAddr } from '../components/ui';
import { colors, font, radius, spacing } from '../theme/theme';
import { useWallet } from '../state/WalletProvider';
import { addContact, contactsForChain, removeContact, type Contact } from '../core/addressBook';

export function AddressBookScreen() {
  const w = useWallet();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    contactsForChain(w.activeChain.id).then(setContacts);
  }, [w.activeChain.id]);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const save = async () => {
    setError(null);
    if (!name.trim()) return setError('Enter a name');
    if (!w.activeAdapter.validateAddress(address.trim())) return setError(`Not a valid ${w.activeChain.name} address`);
    await addContact({ name: name.trim(), address: address.trim(), chainId: w.activeChain.id });
    setName('');
    setAddress('');
    load();
  };

  const del = (c: Contact) => {
    Alert.alert('Remove contact?', c.name, [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Remove', style: 'destructive', onPress: async () => { await removeContact(c.id); load(); } },
    ]);
  };

  return (
    <Screen>
      <FlatList
        data={contacts}
        keyExtractor={(c) => c.id}
        ListHeaderComponent={
          <View style={{ gap: spacing(3), paddingVertical: spacing(4) }}>
            <Text style={font.h2}>Address book</Text>
            <Text style={styles.p}>
              Saved on this device only. Verify an address once, then send by name — this defends
              against paste/clipboard address-swap attacks.
            </Text>
            <Card style={{ gap: spacing(2) }}>
              <Text style={styles.label}>Name</Text>
              <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="e.g. Alice" placeholderTextColor={colors.textFaint} />
              <Text style={styles.label}>{w.activeChain.name} address</Text>
              <TextInput style={styles.input} value={address} onChangeText={setAddress} placeholder="address…" placeholderTextColor={colors.textFaint} autoCapitalize="none" autoCorrect={false} />
              {error && <Text style={styles.err}>{error}</Text>}
              <Button title="Save contact" onPress={save} />
            </Card>
            <Text style={styles.section}>Contacts on {w.activeChain.symbol}</Text>
          </View>
        }
        renderItem={({ item }) => (
          <View style={styles.row}>
            <View style={{ flex: 1 }}>
              <Text style={styles.cName}>{item.name}</Text>
              <Text style={styles.cAddr}>{shortAddr(item.address)}</Text>
            </View>
            <Button title="Remove" variant="ghost" onPress={() => del(item)} />
          </View>
        )}
        ListEmptyComponent={<Text style={styles.empty}>No contacts for this chain yet.</Text>}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  p: { ...font.dim, lineHeight: 19 },
  label: { color: colors.textDim, fontSize: 13, fontWeight: '600' },
  input: { height: 48, backgroundColor: colors.surfaceAlt, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, color: colors.text, paddingHorizontal: spacing(3), fontSize: 15 },
  err: { color: colors.danger, fontSize: 12 },
  section: { color: colors.textFaint, fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  row: { flexDirection: 'row', alignItems: 'center', paddingVertical: spacing(3), borderBottomWidth: 1, borderBottomColor: colors.border },
  cName: { color: colors.text, fontSize: 15, fontWeight: '600' },
  cAddr: { color: colors.textFaint, fontSize: 12, marginTop: 2 },
  empty: { color: colors.textFaint, fontSize: 14, textAlign: 'center', marginTop: spacing(6) },
});
