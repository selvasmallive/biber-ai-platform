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

    // ---- Property tests: ledger state-transition invariants ----
    //
    // `apply_transaction` is the single mutation of ledger state. These tests assert
    // the invariants that must hold for ANY (state, transaction), across randomized
    // inputs, with a seeded PRNG so any failure is deterministically reproducible:
    //   * total supply is conserved on success (no value created or destroyed),
    //   * a failed apply leaves the ledger byte-for-byte unchanged (atomicity),
    //   * a successful apply increments only the sender's nonce, by exactly one,
    //   * a successful transfer moves exactly `amount` to `to` and `fee` to the sink,
    //   * apply is deterministic.

    // xorshift64* — a tiny, dependency-free deterministic PRNG.
    struct FuzzRng(u64);

    impl FuzzRng {
        fn new(seed: u64) -> Self {
            FuzzRng(seed | 1)
        }

        fn next_u64(&mut self) -> u64 {
            let mut x = self.0;
            x ^= x >> 12;
            x ^= x << 25;
            x ^= x >> 27;
            self.0 = x;
            x.wrapping_mul(0x2545_F491_4F6C_DD1D)
        }

        fn below(&mut self, n: u64) -> u64 {
            if n == 0 {
                0
            } else {
                self.next_u64() % n
            }
        }

        fn bool(&mut self) -> bool {
            self.next_u64() & 1 == 1
        }
    }

    // Distinct labelled accounts (plus the fee sink) so addresses never collide by
    // accident; balances/nonces kept well below overflow so the supply sum fits u128.
    const ACCOUNT_LABELS: [&str; 4] = ["alice", "bobbb", "carol", "davey"];

    fn fuzz_ledger(rng: &mut FuzzRng) -> LedgerState {
        let mut ledger = LedgerState::new(LedgerConfig {
            chain_id: "xriq-devnet".to_string(),
            current_height: rng.below(100),
            min_fee: XriqAmount::from_base_units(rng.below(5) as u128),
            fee_sink: fee_sink(),
        });
        for label in ACCOUNT_LABELS {
            if rng.bool() {
                ledger.set_account(
                    address(label),
                    Account::new(
                        XriqAmount::from_base_units(rng.below(1_000_000) as u128),
                        rng.below(50),
                    ),
                );
            }
        }
        ledger
    }

    // Sum of all account balances (base units). Bounded inputs keep this within u128.
    fn total_supply(ledger: &LedgerState) -> u128 {
        ledger
            .accounts()
            .values()
            .map(|account| account.balance.base_units())
            .sum()
    }

    // A transaction that is GUARANTEED valid for `ledger`: drawn from a funded sender
    // with the correct nonce, distinct recipient, fee >= min_fee, amount <= balance,
    // non-expired, signed. Returns None if no sender can currently afford a transfer.
    fn valid_transfer_for(rng: &mut FuzzRng, ledger: &LedgerState) -> Option<Transaction> {
        let min_fee = ledger.config().min_fee.base_units();
        let funded: Vec<&str> = ACCOUNT_LABELS
            .into_iter()
            .filter(|label| {
                ledger
                    .account(&address(label))
                    .is_some_and(|account| account.balance.base_units() > min_fee + 1)
            })
            .collect();
        if funded.is_empty() {
            return None;
        }
        let from_label = funded[rng.below(funded.len() as u64) as usize];
        let to_label = ACCOUNT_LABELS[rng.below(ACCOUNT_LABELS.len() as u64) as usize];
        if to_label == from_label {
            return None;
        }
        let from = address(from_label);
        let sender = ledger.account(&from).expect("funded sender exists");
        let budget = sender.balance.base_units();
        // Split the budget between fee (>= min_fee) and a positive amount. Balances
        // are bounded well under u64, so the per-step casts cannot truncate.
        let fee_extra_cap = (budget.saturating_sub(min_fee)).min(10) as u64;
        let fee = min_fee + rng.below(fee_extra_cap + 1) as u128;
        let remaining = budget.saturating_sub(fee);
        if remaining == 0 {
            return None;
        }
        let amount = 1u128 + rng.below(remaining as u64) as u128;
        Some(Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: ledger.config().chain_id.clone(),
            from,
            to: address(to_label),
            amount: XriqAmount::from_base_units(amount),
            fee: XriqAmount::from_base_units(fee),
            nonce: sender.nonce,
            memo_hash: None,
            expires_at_height: Some(ledger.current_height() + 1),
            signature: SignatureBytes::new(vec![1, 2, 3]),
            public_key: Vec::new(),
        })
    }

    // A possibly-invalid transaction, to exercise the failure/atomicity path: random
    // sender/recipient/amount/fee/nonce, sometimes deliberately malformed.
    fn arbitrary_transfer(rng: &mut FuzzRng, ledger: &LedgerState) -> Transaction {
        let from = address(ACCOUNT_LABELS[rng.below(ACCOUNT_LABELS.len() as u64) as usize]);
        let to = address(ACCOUNT_LABELS[rng.below(ACCOUNT_LABELS.len() as u64) as usize]);
        Transaction {
            version: if rng.bool() { 1 } else { rng.next_u64() as u16 },
            chain_id: if rng.bool() {
                ledger.config().chain_id.clone()
            } else {
                "wrong-chain".to_string()
            },
            from,
            to,
            amount: XriqAmount::from_base_units(rng.below(2_000_000) as u128),
            fee: XriqAmount::from_base_units(rng.below(10) as u128),
            nonce: rng.below(60),
            memo_hash: None,
            expires_at_height: if rng.bool() {
                Some(rng.below(200))
            } else {
                None
            },
            signature: if rng.bool() {
                SignatureBytes::new(vec![1])
            } else {
                SignatureBytes::new(Vec::new())
            },
            public_key: Vec::new(),
        }
    }

    #[test]
    fn property_apply_conserves_supply_or_is_atomic() {
        for i in 0..20_000u64 {
            let mut rng = FuzzRng::new(0x0DDB_1A5E_5EED_1234 ^ i);
            let mut ledger = fuzz_ledger(&mut rng);
            let tx = if rng.bool() {
                valid_transfer_for(&mut rng, &ledger)
                    .unwrap_or_else(|| arbitrary_transfer(&mut rng, &ledger))
            } else {
                arbitrary_transfer(&mut rng, &ledger)
            };

            let before = ledger.clone();
            let supply_before = total_supply(&ledger);
            let sender_before = ledger.account(&tx.from);

            match ledger.apply_transaction(&tx) {
                Ok(()) => {
                    // No value is created or destroyed.
                    assert_eq!(
                        total_supply(&ledger),
                        supply_before,
                        "supply changed on success at seed {i}"
                    );
                    // Only the sender's nonce moves, by exactly one.
                    let sender_after = ledger.account(&tx.from).expect("sender exists");
                    let sender_before = sender_before.expect("a successful sender existed");
                    assert_eq!(
                        sender_after.nonce,
                        sender_before.nonce + 1,
                        "sender nonce not +1 at seed {i}"
                    );
                    for label in ACCOUNT_LABELS {
                        let addr = address(label);
                        if addr != tx.from {
                            if let (Some(a), Some(b)) =
                                (before.account(&addr), ledger.account(&addr))
                            {
                                assert_eq!(a.nonce, b.nonce, "non-sender nonce moved at seed {i}");
                            }
                        }
                    }
                }
                Err(_) => {
                    // A rejected transaction must not mutate any state.
                    assert_eq!(ledger, before, "state mutated on failure at seed {i}");
                }
            }
        }
    }

    #[test]
    fn property_valid_transfer_routes_amount_and_fee_exactly() {
        for i in 0..20_000u64 {
            let mut rng = FuzzRng::new(0xFEE5_0DAD_1234_5678 ^ i);
            let mut ledger = fuzz_ledger(&mut rng);
            let Some(tx) = valid_transfer_for(&mut rng, &ledger) else {
                continue;
            };
            // Only exercise the clean-routing arithmetic when the three roles are
            // distinct (aliasing is covered by the conservation property above).
            let sink = ledger.config().fee_sink.clone();
            if tx.from == tx.to || tx.from == sink || tx.to == sink {
                continue;
            }
            let from_before = ledger.account(&tx.from).unwrap().balance.base_units();
            let to_before = ledger
                .account(&tx.to)
                .map(|a| a.balance.base_units())
                .unwrap_or(0);
            let sink_before = ledger
                .account(&sink)
                .map(|a| a.balance.base_units())
                .unwrap_or(0);

            ledger
                .apply_transaction(&tx)
                .unwrap_or_else(|error| panic!("valid transfer rejected at seed {i}: {error:?}"));

            let amount = tx.amount.base_units();
            let fee = tx.fee.base_units();
            assert_eq!(
                ledger.account(&tx.from).unwrap().balance.base_units(),
                from_before - amount - fee,
                "sender debit wrong at seed {i}"
            );
            assert_eq!(
                ledger.account(&tx.to).unwrap().balance.base_units(),
                to_before + amount,
                "recipient credit wrong at seed {i}"
            );
            assert_eq!(
                ledger.account(&sink).unwrap().balance.base_units(),
                sink_before + fee,
                "fee routing wrong at seed {i}"
            );
        }
    }

    #[test]
    fn property_apply_is_deterministic() {
        for i in 0..10_000u64 {
            let mut rng = FuzzRng::new(0xD37E_8321_ABCD_4321 ^ i);
            let ledger = fuzz_ledger(&mut rng);
            let tx = valid_transfer_for(&mut rng, &ledger)
                .unwrap_or_else(|| arbitrary_transfer(&mut rng, &ledger));

            let mut a = ledger.clone();
            let mut b = ledger.clone();
            let ra = a.apply_transaction(&tx);
            let rb = b.apply_transaction(&tx);
            assert_eq!(ra, rb, "apply result differs at seed {i}");
            assert_eq!(a, b, "apply state differs at seed {i}");
        }
    }
}
