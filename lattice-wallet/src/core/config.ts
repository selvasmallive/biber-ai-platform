// Network + app configuration.
//
// SCOPE: Lattice targets the XRIQ test network. The chain has NOT completed its
// independent security audit or legal review, so this wallet is for testnet use and
// must not be represented as custodying real value. The in-app banner and README say
// the same. Point `rpcUrl` at your XRIQ node's HTTP API.

export interface NetworkConfig {
  key: string;
  label: string;
  chainId: string; // must match the node's chain_id exactly (signed into every tx)
  rpcUrl: string; // base URL of the xriq-api HTTP service
  explorerUrl?: string;
  isTestnet: boolean;
  faucetEnabled: boolean;
}

// Default to a locally running node. Override in Settings at runtime.
export const NETWORKS: Record<string, NetworkConfig> = {
  devnet: {
    key: 'devnet',
    label: 'XRIQ Devnet (local)',
    chainId: 'xriq-devnet',
    rpcUrl: 'http://127.0.0.1:8080',
    isTestnet: true,
    faucetEnabled: true,
  },
  testnet: {
    key: 'testnet',
    label: 'XRIQ Public Testnet',
    chainId: 'xriq-testnet',
    rpcUrl: 'https://testnet.xriq.invalid', // set to the real testnet endpoint
    isTestnet: true,
    faucetEnabled: true,
  },
};

export const DEFAULT_NETWORK_KEY = 'devnet';

// Native unit display. XRIQ uses integer base units; adjust decimals to the chain's
// BASE_UNITS_PER_XRIQ when finalized. Kept conservative (0) until confirmed so we
// never over-state a balance.
export const NATIVE_SYMBOL = 'XRIQ';
export const NATIVE_DECIMALS = 0;

// Honest status shown throughout the app.
export const SECURITY_STATUS = {
  audited: false,
  legalReviewed: false,
  banner: 'Testnet · unaudited — do not store real value',
};
