//! Core XRIQ private-devnet protocol types.

pub mod address;
pub mod amount;
pub mod block;
pub mod config;
pub mod environment;
pub mod hash;
pub mod state;
pub mod transaction;

pub use address::{Address, AddressError, DEVNET_ADDRESS_PREFIX};
pub use amount::{XriqAmount, BASE_UNITS_PER_XRIQ};
pub use block::{Block, BlockHeader, BlockValidationError, ParentHeaderView};
pub use config::{
    GenesisAccount, GenesisConfig, GenesisConfigError, PRIVATE_DEVNET_CHAIN_ID,
    PRIVATE_DEVNET_MAX_TRANSACTIONS_PER_BLOCK, PRIVATE_DEVNET_MEMPOOL_MAX_TRANSACTIONS,
    PRIVATE_DEVNET_MIN_FEE_BASE_UNITS, PUBLIC_TESTNET_AUTHORITY_ADDRESS,
    PUBLIC_TESTNET_AUTHORITY_PUBKEY, PUBLIC_TESTNET_CHAIN_ID, PUBLIC_TESTNET_FAUCET_ADDRESS,
    PUBLIC_TESTNET_FAUCET_BALANCE_BASE_UNITS, PUBLIC_TESTNET_FAUCET_DRIP_BASE_UNITS,
    PUBLIC_TESTNET_FAUCET_MAX_BALANCE_BASE_UNITS, PUBLIC_TESTNET_FEE_SINK_ADDRESS,
    PUBLIC_TESTNET_MAX_TRANSACTIONS_PER_BLOCK, PUBLIC_TESTNET_MEMPOOL_MAX_TRANSACTIONS,
    PUBLIC_TESTNET_MIN_FEE_BASE_UNITS,
};
pub use environment::{Environment, EnvironmentError, CANONICAL_NETWORK};
pub use hash::Hash32;
pub use state::AccountStateEntry;
pub use transaction::{
    AccountView, SignatureBytes, Transaction, TransactionValidationContext,
    TransactionValidationError,
};
