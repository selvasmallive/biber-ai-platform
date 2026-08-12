import React from 'react';
import { ActivityIndicator, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { NavigationContainer, DarkTheme } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { Text } from 'react-native';

import { WalletProvider, useWallet } from './src/state/WalletProvider';
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
          <StatusBar style="light" />
          <Root />
        </WalletProvider>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
