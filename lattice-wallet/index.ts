// Entry point. The RNG polyfill MUST be imported before any crypto code runs so that
// crypto.getRandomValues() is available for mnemonic generation on device.
import 'react-native-get-random-values';
// WalletConnect's React Native compatibility shim installs required globals (must load
// before the WalletKit SDK is used).
import '@walletconnect/react-native-compat';
import { registerRootComponent } from 'expo';
import App from './App';

registerRootComponent(App);
