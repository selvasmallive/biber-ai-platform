// Entry point. The RNG polyfill MUST be imported before any crypto code runs so that
// crypto.getRandomValues() is available for mnemonic generation on device.
import 'react-native-get-random-values';
import { registerRootComponent } from 'expo';
import App from './App';

registerRootComponent(App);
