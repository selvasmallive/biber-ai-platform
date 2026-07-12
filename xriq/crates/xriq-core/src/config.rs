use crate::{Address, Hash32, XriqAmount};

pub const PRIVATE_DEVNET_CHAIN_ID: &str = "xriq-devnet";
pub const PRIVATE_DEVNET_MIN_FEE_BASE_UNITS: u128 = 2;
pub const PRIVATE_DEVNET_MEMPOOL_MAX_TRANSACTIONS: usize = 8;
pub const PRIVATE_DEVNET_MAX_TRANSACTIONS_PER_BLOCK: usize = 4;

// Public test network chain spec. This is a TEST-ONLY network: the native unit
// has NO monetary value, there is no sale/emission beyond the fixed genesis
// faucet allocation below, and the faucet dispenses clearly-labeled valueless
// test units. Every field here is fixed and reproducible so independent nodes
// agree on the same genesis.
pub const PUBLIC_TESTNET_CHAIN_ID: &str = "xriq-testnet";
pub const PUBLIC_TESTNET_MIN_FEE_BASE_UNITS: u128 = 2;
pub const PUBLIC_TESTNET_MEMPOOL_MAX_TRANSACTIONS: usize = 4096;
pub const PUBLIC_TESTNET_MAX_TRANSACTIONS_PER_BLOCK: usize = 512;
pub const PUBLIC_TESTNET_AUTHORITY_ADDRESS: &str = "xriqdev1testnetauthority00000";
pub const PUBLIC_TESTNET_FEE_SINK_ADDRESS: &str = "xriqdev1testnetfees0000000000";
/// Genesis-funded faucet account. Its balance is valueless test units used only
/// to seed the public testnet faucet; it is not a supply, sale, or distribution.
pub const PUBLIC_TESTNET_FAUCET_ADDRESS: &str = "xriqdev1testnetfaucet00000000";
pub const PUBLIC_TESTNET_FAUCET_BALANCE_BASE_UNITS: u128 = 1_000_000_000_000;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GenesisAccount {
    pub address: Address,
    pub balance: XriqAmount,
    pub nonce: u64,
}

impl GenesisAccount {
    pub fn new(address: Address, balance: XriqAmount, nonce: u64) -> Self {
        Self {
            address,
            balance,
            nonce,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GenesisConfig {
    pub chain_id: String,
    pub initial_height: u64,
    pub genesis_block_hash: Hash32,
    pub min_fee: XriqAmount,
    pub fee_sink: Address,
    pub authority: Address,
    pub mempool_max_transactions: usize,
    pub max_transactions_per_block: usize,
    pub accounts: Vec<GenesisAccount>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum GenesisConfigError {
    EmptyChainId,
    EmptyMempool,
    EmptyBlockTransactionLimit,
    BlockLimitExceedsMempoolLimit,
    DuplicateAccount(Address),
    InitialBalanceOverflow,
}

impl GenesisConfig {
    pub fn private_devnet() -> Self {
        Self {
            chain_id: PRIVATE_DEVNET_CHAIN_ID.to_string(),
            initial_height: 0,
            genesis_block_hash: Hash32::ZERO,
            min_fee: XriqAmount::from_base_units(PRIVATE_DEVNET_MIN_FEE_BASE_UNITS),
            fee_sink: Address::parse("xriqdev1fees000000000000")
                .expect("private devnet fee sink address is valid"),
            authority: Address::parse("xriqdev1author00000000000")
                .expect("private devnet authority address is valid"),
            mempool_max_transactions: PRIVATE_DEVNET_MEMPOOL_MAX_TRANSACTIONS,
            max_transactions_per_block: PRIVATE_DEVNET_MAX_TRANSACTIONS_PER_BLOCK,
            accounts: Vec::new(),
        }
    }

    /// The public test network genesis: a fixed, reproducible chain spec whose
    /// only genesis allocation is the valueless faucet account. TEST-ONLY.
    pub fn public_testnet() -> Self {
        Self {
            chain_id: PUBLIC_TESTNET_CHAIN_ID.to_string(),
            initial_height: 0,
            genesis_block_hash: Hash32::ZERO,
            min_fee: XriqAmount::from_base_units(PUBLIC_TESTNET_MIN_FEE_BASE_UNITS),
            fee_sink: Address::parse(PUBLIC_TESTNET_FEE_SINK_ADDRESS)
                .expect("public testnet fee sink address is valid"),
            authority: Address::parse(PUBLIC_TESTNET_AUTHORITY_ADDRESS)
                .expect("public testnet authority address is valid"),
            mempool_max_transactions: PUBLIC_TESTNET_MEMPOOL_MAX_TRANSACTIONS,
            max_transactions_per_block: PUBLIC_TESTNET_MAX_TRANSACTIONS_PER_BLOCK,
            accounts: Vec::new(),
        }
        .with_account(
            Address::parse(PUBLIC_TESTNET_FAUCET_ADDRESS)
                .expect("public testnet faucet address is valid"),
            XriqAmount::from_base_units(PUBLIC_TESTNET_FAUCET_BALANCE_BASE_UNITS),
            0,
        )
    }

    pub fn with_account(mut self, address: Address, balance: XriqAmount, nonce: u64) -> Self {
        self.accounts
            .push(GenesisAccount::new(address, balance, nonce));
        self
    }

    pub fn validate(&self) -> Result<(), GenesisConfigError> {
        if self.chain_id.trim().is_empty() {
            return Err(GenesisConfigError::EmptyChainId);
        }
        if self.mempool_max_transactions == 0 {
            return Err(GenesisConfigError::EmptyMempool);
        }
        if self.max_transactions_per_block == 0 {
            return Err(GenesisConfigError::EmptyBlockTransactionLimit);
        }
        if self.max_transactions_per_block > self.mempool_max_transactions {
            return Err(GenesisConfigError::BlockLimitExceedsMempoolLimit);
        }

        let mut seen = Vec::new();
        for account in &self.accounts {
            if seen.contains(&account.address) {
                return Err(GenesisConfigError::DuplicateAccount(
                    account.address.clone(),
                ));
            }
            seen.push(account.address.clone());
        }

        self.total_initial_balance()?;
        Ok(())
    }

    pub fn total_initial_balance(&self) -> Result<XriqAmount, GenesisConfigError> {
        let mut total = XriqAmount::ZERO;
        for account in &self.accounts {
            total = total
                .checked_add(account.balance)
                .ok_or(GenesisConfigError::InitialBalanceOverflow)?;
        }
        Ok(total)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    #[test]
    fn private_devnet_has_explicit_test_only_defaults() {
        let genesis = GenesisConfig::private_devnet();

        assert_eq!(genesis.chain_id, PRIVATE_DEVNET_CHAIN_ID);
        assert_eq!(genesis.initial_height, 0);
        assert_eq!(genesis.genesis_block_hash, Hash32::ZERO);
        assert_eq!(
            genesis.min_fee,
            XriqAmount::from_base_units(PRIVATE_DEVNET_MIN_FEE_BASE_UNITS)
        );
        assert_eq!(
            genesis.mempool_max_transactions,
            PRIVATE_DEVNET_MEMPOOL_MAX_TRANSACTIONS
        );
        assert_eq!(
            genesis.max_transactions_per_block,
            PRIVATE_DEVNET_MAX_TRANSACTIONS_PER_BLOCK
        );
        assert!(genesis.accounts.is_empty());
        assert_eq!(genesis.validate(), Ok(()));
    }

    #[test]
    fn accepts_deterministic_test_allocations() {
        let genesis = GenesisConfig::private_devnet()
            .with_account(address("alice"), XriqAmount::from_base_units(100), 0)
            .with_account(address("bobbb"), XriqAmount::from_base_units(25), 2);

        assert_eq!(genesis.validate(), Ok(()));
        assert_eq!(
            genesis.total_initial_balance(),
            Ok(XriqAmount::from_base_units(125))
        );
    }

    #[test]
    fn public_testnet_is_valid_and_funds_only_the_faucet() {
        let genesis = GenesisConfig::public_testnet();

        assert_eq!(genesis.chain_id, PUBLIC_TESTNET_CHAIN_ID);
        assert_ne!(genesis.chain_id, PRIVATE_DEVNET_CHAIN_ID);
        assert_eq!(genesis.initial_height, 0);
        assert_eq!(genesis.genesis_block_hash, Hash32::ZERO);
        assert_eq!(genesis.validate(), Ok(()));

        // The only genesis allocation is the valueless faucet account.
        assert_eq!(genesis.accounts.len(), 1);
        let faucet = &genesis.accounts[0];
        assert_eq!(faucet.address.as_str(), PUBLIC_TESTNET_FAUCET_ADDRESS);
        assert_eq!(
            faucet.balance,
            XriqAmount::from_base_units(PUBLIC_TESTNET_FAUCET_BALANCE_BASE_UNITS)
        );
        assert_eq!(faucet.nonce, 0);
        assert_eq!(
            genesis.total_initial_balance(),
            Ok(XriqAmount::from_base_units(
                PUBLIC_TESTNET_FAUCET_BALANCE_BASE_UNITS
            ))
        );
    }

    #[test]
    fn rejects_duplicate_allocations() {
        let alice = address("alice");
        let genesis = GenesisConfig::private_devnet()
            .with_account(alice.clone(), XriqAmount::from_base_units(100), 0)
            .with_account(alice.clone(), XriqAmount::from_base_units(25), 1);

        assert_eq!(
            genesis.validate(),
            Err(GenesisConfigError::DuplicateAccount(alice))
        );
    }

    #[test]
    fn rejects_invalid_capacity_policy() {
        let mut genesis = GenesisConfig::private_devnet();
        genesis.mempool_max_transactions = 1;
        genesis.max_transactions_per_block = 2;

        assert_eq!(
            genesis.validate(),
            Err(GenesisConfigError::BlockLimitExceedsMempoolLimit)
        );
    }
}
