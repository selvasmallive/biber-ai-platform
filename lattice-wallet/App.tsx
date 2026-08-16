import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Text } from 'react-native';

import { WalletProvider, useWallet } from './src/state/WalletProvider';
import { WalletConnectProvider } from './src/state/WalletConnectProvider';
import { WalletConnectModals } from './src/components/WalletConnectModals';
import { colors } from './src/theme/theme';
import { OnboardingScreen } from './src/screens/OnboardingScreen';
import { BackupScreen } from './src/screens/BackupScreen';
import { ImportScreen } from './src/screens/ImportScreen';
import { HomeScreen } from './src/screens/HomeScreen';
import { SendScreen } from './src/screens/SendScreen';
import { ReceiveScreen } from './src/screens/ReceiveScreen';
import { HistoryScreen } from './src/screens/HistoryScreen';
import { SwapScreen } from './src/screens/SwapScreen';
import { SettingsScreen } from './src/screens/SettingsScreen';
import { WalletConnectScreen } from './src/screens/WalletConnectScreen';
import { ScanQrScreen } from './src/screens/ScanQrScreen';
import { AddNetworkScreen } from './src/screens/AddNetworkScreen';
import { AddTokenScreen } from './src/screens/AddTokenScreen';
import { TokenSendScreen } from './src/screens/TokenSendScreen';
import { AddressBookScreen } from './src/screens/AddressBookScreen';

const Stack = createNativeStackNavigator();
const Tabs = createBottomTabNavigator();

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: colors.bg,
    card: colors.bg,
    text: colors.text,
    border: colors.border,
    primary: colors.accent,
  },
};

function TabIcon({ glyph, color }: { glyph: string; color: string }) {
  return <Text style={{ color, fontSize: 20 }}>{glyph}</Text>;
}

function MainTabs() {
  return (
    <Tabs.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border, height: 62, paddingBottom: 8, paddingTop: 8 },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textFaint,
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
      }}
    >
      <Tabs.Screen name="Home" component={HomeScreen} options={{ tabBarIcon: ({ color }) => <TabIcon glyph="⬡" color={color} /> }} />
      <Tabs.Screen name="SwapTab" component={SwapScreen} options={{ title: 'Swap', tabBarIcon: ({ color }) => <TabIcon glyph="⇄" color={color} /> }} />
      <Tabs.Screen name="History" component={HistoryScreen} options={{ tabBarIcon: ({ color }) => <TabIcon glyph="≣" color={color} /> }} />
      <Tabs.Screen name="Settings" component={SettingsScreen} options={{ tabBarIcon: ({ color }) => <TabIcon glyph="⚙" color={color} /> }} />
    </Tabs.Navigator>
  );
}

function Root() {
  const { status } = useWallet();

  if (status === 'loading') {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.accent} size="large" />
      </View>
    );
  }

  return (
    <Stack.Navigator
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerShadowVisible: false,
        contentStyle: { backgroundColor: colors.bg },
      }}
    >
      {status === 'no-wallet' ? (
        <>
          <Stack.Screen name="Onboarding" component={OnboardingScreen} options={{ headerShown: false }} />
          <Stack.Screen name="Backup" component={BackupScreen} options={{ title: 'Back up' }} />
          <Stack.Screen name="Import" component={ImportScreen} options={{ title: 'Import' }} />
        </>
      ) : (
        <>
          <Stack.Screen name="Main" component={MainTabs} options={{ headerShown: false }} />
          <Stack.Screen name="Send" component={SendScreen} options={{ presentation: 'modal', title: 'Send' }} />
          <Stack.Screen name="Receive" component={ReceiveScreen} options={{ presentation: 'modal', title: 'Receive' }} />
          <Stack.Screen name="AddToken" component={AddTokenScreen} options={{ presentation: 'modal', title: 'Add token' }} />
          <Stack.Screen name="TokenSend" component={TokenSendScreen} options={{ presentation: 'modal', title: 'Send token' }} />
          <Stack.Screen name="AddressBook" component={AddressBookScreen} options={{ title: 'Address book' }} />
          <Stack.Screen name="WalletConnect" component={WalletConnectScreen} options={{ title: 'WalletConnect' }} />
          <Stack.Screen name="ScanQr" component={ScanQrScreen} options={{ presentation: 'modal', headerShown: false }} />
          <Stack.Screen name="AddNetwork" component={AddNetworkScreen} options={{ presentation: 'modal', title: 'Add network' }} />
          {/* Reachable after wipe */}
          <Stack.Screen name="Onboarding" component={OnboardingScreen} options={{ headerShown: false }} />
          <Stack.Screen name="Backup" component={BackupScreen} options={{ title: 'Back up' }} />
          <Stack.Screen name="Import" component={ImportScreen} options={{ title: 'Import' }} />
        </>
      )}
    </Stack.Navigator>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer theme={navTheme}>
        <WalletProvider>
          <WalletConnectProvider>
            <StatusBar style="light" />
            <Root />
            <WalletConnectModals />
          </WalletConnectProvider>
        </WalletProvider>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
