//! Deterministic account ledger state transitions for the XRIQ private devnet.

use std::collections::BTreeMap;

use xriq_core::{
    AccountStateEntry, AccountView, Address, GenesisConfig, GenesisConfigError, Transaction,
    TransactionValidationContext, TransactionValidationError, XriqAmount,
};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Account {
    pub balance: XriqAmount,
    pub nonce: u64,
}

impl Account {
    pub const fn new(balance: XriqAmount, nonce: u64) -> Self {
        Self { balance, nonce }
    }

    pub const fn view(self) -> AccountView {
        AccountView {
            balance: self.balance,
            nonce: self.nonce,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LedgerConfig {
    pub chain_id: String,
    pub current_height: u64,
    pub min_fee: XriqAmount,
    pub fee_sink: Address,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LedgerState {
    config: LedgerConfig,
    accounts: BTreeMap<Address, Account>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LedgerError {
    MissingSender,
    Transaction(TransactionValidationError),
    DebitUnderflow,
    CreditOverflow,
    NonceOverflow,
}

impl LedgerState {
    pub fn new(config: LedgerConfig) -> Self {
        let mut accounts = BTreeMap::new();
        accounts.insert(config.fee_sink.clone(), Account::new(XriqAmount::ZERO, 0));
        Self { config, accounts }
    }

    pub fn from_genesis(genesis: &GenesisConfig) -> Result<Self, GenesisConfigError> {
        genesis.validate()?;
        let mut ledger = Self::new(LedgerConfig {
            chain_id: genesis.chain_id.clone(),
            current_height: genesis.initial_height,
            min_fee: genesis.min_fee,
            fee_sink: genesis.fee_sink.clone(),
        });
        for account in &genesis.accounts {
            ledger.set_account(
                account.address.clone(),
                Account::new(account.balance, account.nonce),
            );
        }
        Ok(ledger)
    }

    pub fn config(&self) -> &LedgerConfig {
        &self.config
    }

    pub fn current_height(&self) -> u64 {
        self.config.current_height
    }

    pub fn set_current_height(&mut self, current_height: u64) {
        self.config.current_height = current_height;
    }

    pub fn account(&self, address: &Address) -> Option<Account> {
        self.accounts.get(address).copied()
    }

    pub fn set_account(&mut self, address: Address, account: Account) {
        self.accounts.insert(address, account);
    }

    pub fn accounts(&self) -> &BTreeMap<Address, Account> {
        &self.accounts
    }

    pub fn state_root_entries(&self) -> Vec<AccountStateEntry> {
        self.accounts
            .iter()
            .map(|(address, account)| {
                AccountStateEntry::new(address.clone(), account.balance, account.nonce)
            })
            .collect()
    }

    pub fn apply_transaction(&mut self, tx: &Transaction) -> Result<(), LedgerError> {
        let sender = self
            .accounts
            .get(&tx.from)
            .copied()
            .ok_or(LedgerError::MissingSender)?;
        let context = TransactionValidationContext {
            chain_id: self.config.chain_id.clone(),
            sender: sender.view(),
            current_height: self.config.current_height,
            min_fee: self.config.min_fee,
        };
        tx.validate_basic(&context)
            .map_err(LedgerError::Transaction)?;

        let total_debit = tx.total_debit().ok_or(LedgerError::DebitUnderflow)?;
        let sender_balance = sender
            .balance
            .checked_sub(total_debit)
            .ok_or(LedgerError::DebitUnderflow)?;
        let sender_nonce = sender
            .nonce
            .checked_add(1)
            .ok_or(LedgerError::NonceOverflow)?;

        let mut next_accounts = self.accounts.clone();
        next_accounts.insert(tx.from.clone(), Account::new(sender_balance, sender_nonce));
        credit_account(&mut next_accounts, &tx.to, tx.amount)?;
        credit_account(&mut next_accounts, &self.config.fee_sink, tx.fee)?;

        self.accounts = next_accounts;
        Ok(())
    }
}

fn credit_account(
    accounts: &mut BTreeMap<Address, Account>,
    address: &Address,
    amount: XriqAmount,
) -> Result<(), LedgerError> {
    let existing = accounts
        .get(address)
        .copied()
        .unwrap_or_else(|| Account::new(XriqAmount::ZERO, 0));
    let balance = existing
        .balance
        .checked_add(amount)
        .ok_or(LedgerError::CreditOverflow)?;
    accounts.insert(address.clone(), Account::new(balance, existing.nonce));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_core::SignatureBytes;

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn fee_sink() -> Address {
        Address::parse("xriqdev1fees000000000000").unwrap()
    }

    fn ledger() -> LedgerState {
        LedgerState::new(LedgerConfig {
            chain_id: "xriq-devnet".to_string(),
            current_height: 10,
            min_fee: XriqAmount::from_base_units(2),
            fee_sink: fee_sink(),
        })
    }

    fn transfer(from: Address, to: Address, amount: u128, fee: u128, nonce: u64) -> Transaction {
        Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from,
            to,
            amount: XriqAmount::from_base_units(amount),
            fee: XriqAmount::from_base_units(fee),
            nonce,
            memo_hash: None,
            expires_at_height: Some(100),
            signature: SignatureBytes::new(vec![1, 2, 3]),
            public_key: Vec::new(),
        }
    }

    #[test]
    fn applies_transfer_and_collects_fee() {
        let alice = address("alice");
        let bob = address("bobbb");
        let fees = fee_sink();
        let mut ledger = ledger();
        ledger.set_account(
            alice.clone(),
            Account::new(XriqAmount::from_base_units(100), 0),
        );

        let tx = transfer(alice.clone(), bob.clone(), 25, 2, 0);
        assert_eq!(ledger.apply_transaction(&tx), Ok(()));

        assert_eq!(
            ledger.account(&alice),
            Some(Account::new(XriqAmount::from_base_units(73), 1))
        );
        assert_eq!(
            ledger.account(&bob),
            Some(Account::new(XriqAmount::from_base_units(25), 0))
        );
        assert_eq!(
            ledger.account(&fees),
            Some(Account::new(XriqAmount::from_base_units(2), 0))
        );
    }

    #[test]
    fn creates_ledger_from_genesis_allocations() {
        let alice = address("alice");
        let genesis = GenesisConfig::private_devnet().with_account(
            alice.clone(),
            XriqAmount::from_base_units(100),
            7,
        );

        let ledger = LedgerState::from_genesis(&genesis).unwrap();

        assert_eq!(ledger.config().chain_id, "xriq-devnet");
        assert_eq!(ledger.current_height(), 0);
        assert_eq!(
            ledger.account(&alice),
            Some(Account::new(XriqAmount::from_base_units(100), 7))
        );
        assert_eq!(
            ledger.account(&genesis.fee_sink),
            Some(Account::new(XriqAmount::ZERO, 0))
        );
    }

    #[test]
    fn exposes_sorted_account_state_entries_for_rooting() {
        let mut ledger = ledger();
        ledger.set_account(
            address("bobbb"),
            Account::new(XriqAmount::from_base_units(25), 1),
        );
        ledger.set_account(
            address("alice"),
            Account::new(XriqAmount::from_base_units(100), 0),
        );

        let entries = ledger.state_root_entries();
        let addresses: Vec<&str> = entries.iter().map(|entry| entry.address.as_str()).collect();

        assert_eq!(
            addresses,
            vec![
                "xriqdev1alice00000000000",
                "xriqdev1bobbb00000000000",
                "xriqdev1fees000000000000",
            ]
        );
    }

    #[test]
    fn creates_recipient_account_for_valid_transfer() {
        let alice = address("alice");
        let carol = address("carol");
        let mut ledger = ledger();
        ledger.set_account(
            alice.clone(),
            Account::new(XriqAmount::from_base_units(50), 3),
        );

        let tx = transfer(alice, carol.clone(), 10, 2, 3);
        ledger.apply_transaction(&tx).unwrap();

        assert_eq!(
            ledger.account(&carol),
            Some(Account::new(XriqAmount::from_base_units(10), 0))
        );
    }

    #[test]
    fn rejects_missing_sender() {
        let tx = transfer(address("alice"), address("bobbb"), 10, 2, 0);
        assert_eq!(
            ledger().apply_transaction(&tx),
            Err(LedgerError::MissingSender)
        );
    }

    #[test]
    fn rejects_bad_nonce_without_mutating_state() {
        let alice = address("alice");
        let bob = address("bobbb");
        let mut ledger = ledger();
        ledger.set_account(
            alice.clone(),
            Account::new(XriqAmount::from_base_units(100), 4),
        );
        let before = ledger.clone();

        let tx = transfer(alice, bob, 10, 2, 5);
        assert_eq!(
            ledger.apply_transaction(&tx),
            Err(LedgerError::Transaction(
                TransactionValidationError::InvalidNonce {
                    expected: 4,
                    actual: 5
                }
            ))
        );
        assert_eq!(ledger, before);
    }

    #[test]
    fn rejects_insufficient_funds_without_mutating_state() {
        let alice = address("alice");
        let bob = address("bobbb");
        let mut ledger = ledger();
        ledger.set_account(
            alice.clone(),
            Account::new(XriqAmount::from_base_units(10), 0),
        );
        let before = ledger.clone();

        let tx = transfer(alice, bob, 10, 2, 0);
        assert_eq!(
            ledger.apply_transaction(&tx),
            Err(LedgerError::Transaction(
                TransactionValidationError::InsufficientFunds
            ))
        );
        assert_eq!(ledger, before);
    }
}
