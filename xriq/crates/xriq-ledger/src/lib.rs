//! Deterministic account ledger state transitions for the XRIQ private devnet.

use std::collections::{BTreeMap, BTreeSet};

use xriq_core::{
    AccountStateEntry, AccountView, Address, GenesisConfig, GenesisConfigError, Hash32,
    Transaction, TransactionValidationContext, TransactionValidationError, TxAction, XriqAmount,
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
    /// On-chain authorized-wallet registry. Empty by default — and while empty it
    /// contributes nothing to the state root, so any chain that never authorizes a
    /// wallet keeps a byte-identical root (see [`LedgerState::state_root`]). Mutated
    /// only by governance transactions ([`TxAction::AuthorizeWallet`] /
    /// [`TxAction::RevokeWallet`]), which the node accepts only from the chain
    /// authority. A `BTreeSet` keeps membership ordered and deterministic for rooting.
    authorized: BTreeSet<Address>,
    /// Balances of the test-only, clearly-valueless counter-asset, distinct from the
    /// native unit. Empty by default and, while empty, contributes nothing to the state
    /// root (byte-identical root preserved). Moved only by [`TxAction::Swap`], which
    /// applies only when both parties are in `authorized`. Zero balances are pruned so
    /// the map — and therefore the root — is canonical.
    counter_balances: BTreeMap<Address, u128>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LedgerError {
    MissingSender,
    Transaction(TransactionValidationError),
    DebitUnderflow,
    CreditOverflow,
    NonceOverflow,
    /// A [`TxAction::Swap`] named a party (sender or recipient) that is not in the
    /// authorized-wallet registry. Both parties must be approved for a swap to apply.
    UnauthorizedSwapParty,
    /// A [`TxAction::Swap`] recipient lacked enough of the counter-asset to deliver
    /// `counter_amount`.
    CounterAssetUnderflow,
    /// A [`TxAction::Swap`] would overflow a counter-asset balance on credit.
    CounterAssetOverflow,
}

impl LedgerState {
    pub fn new(config: LedgerConfig) -> Self {
        let mut accounts = BTreeMap::new();
        accounts.insert(config.fee_sink.clone(), Account::new(XriqAmount::ZERO, 0));
        Self {
            config,
            accounts,
            authorized: BTreeSet::new(),
            counter_balances: BTreeMap::new(),
        }
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
        for (address, balance) in &genesis.counter_asset_accounts {
            ledger.set_counter_balance(address.clone(), *balance);
        }
        for address in &genesis.authorized_wallets {
            ledger.authorize(address.clone());
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

    /// Whether `address` is in the authorized-wallet registry.
    pub fn is_authorized(&self, address: &Address) -> bool {
        self.authorized.contains(address)
    }

    /// The authorized wallets, in ascending (deterministic) address order.
    pub fn authorized_wallets(&self) -> Vec<Address> {
        self.authorized.iter().cloned().collect()
    }

    /// Add `address` to the registry. Idempotent: authorizing an already-authorized
    /// wallet leaves the registry unchanged. Direct mutator used by the governance
    /// apply path; authority gating lives at the node layers, not here (mirroring the
    /// sender↔key binding, which is also a node concern).
    pub fn authorize(&mut self, address: Address) {
        self.authorized.insert(address);
    }

    /// Remove `address` from the registry. Idempotent: revoking a wallet that is not
    /// authorized leaves the registry unchanged.
    pub fn revoke(&mut self, address: &Address) {
        self.authorized.remove(address);
    }

    /// The counter-asset balance of `address` (zero if it holds none).
    pub fn counter_balance(&self, address: &Address) -> u128 {
        self.counter_balances.get(address).copied().unwrap_or(0)
    }

    /// Set the counter-asset balance of `address`, pruning zero balances so the map
    /// stays canonical. Test/dev seeding helper — the counter-asset is valueless and is
    /// not allocated at genesis.
    pub fn set_counter_balance(&mut self, address: Address, balance: u128) {
        if balance == 0 {
            self.counter_balances.remove(&address);
        } else {
            self.counter_balances.insert(address, balance);
        }
    }

    /// The counter-asset balances, in ascending (deterministic) address order.
    pub fn counter_balance_entries(&self) -> Vec<(Address, u128)> {
        self.counter_balances
            .iter()
            .map(|(address, balance)| (address.clone(), *balance))
            .collect()
    }

    /// The consensus state root committing to the account set, the authorized-wallet
    /// registry, AND the counter-asset balances. Every node computes the root through
    /// this method so all three are folded in identically everywhere. While the registry
    /// and the counter-asset are both empty the root is byte-identical to the historical
    /// account-only root, so no existing golden shifts.
    pub fn state_root(&self) -> Hash32 {
        xriq_crypto::ledger_state_root(
            &self.state_root_entries(),
            &self.authorized_wallets(),
            &self.counter_balance_entries(),
        )
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

        // Apply the action. Every branch stages its changes into the `next_*` clones
        // and nothing is committed to `self` until the end, so a failure anywhere in
        // this function leaves the ledger byte-for-byte unchanged (atomicity):
        //   * Transfer moves `amount` to the recipient;
        //   * a governance action moves no value (amount is validated zero) and mutates
        //     the authorized-wallet registry;
        //   * a Swap moves `amount` native to the recipient AND `counter_amount` of the
        //     counter-asset back from the recipient, but ONLY if both parties are in the
        //     registry (the both-parties-approved gate).
        // All branches pay the fee to the sink.
        let mut next_authorized = self.authorized.clone();
        let mut next_counter = self.counter_balances.clone();
        match &tx.action {
            TxAction::Transfer => {
                credit_account(&mut next_accounts, &tx.to, tx.amount)?;
            }
            TxAction::AuthorizeWallet { target } => {
                next_authorized.insert(target.clone());
            }
            TxAction::RevokeWallet { target } => {
                next_authorized.remove(target);
            }
            TxAction::Swap { counter_amount, .. } => {
                // Both-parties-approved gate: reject before any staging is committed.
                if !self.is_authorized(&tx.from) || !self.is_authorized(&tx.to) {
                    return Err(LedgerError::UnauthorizedSwapParty);
                }
                // Native leg: `amount` from `from` (already debited above) to `to`.
                credit_account(&mut next_accounts, &tx.to, tx.amount)?;
                // Counter leg: `counter_amount` from `to` back to `from`.
                move_counter_asset(&mut next_counter, &tx.to, &tx.from, *counter_amount)?;
            }
        }
        credit_account(&mut next_accounts, &self.config.fee_sink, tx.fee)?;

        self.accounts = next_accounts;
        self.authorized = next_authorized;
        self.counter_balances = next_counter;
        Ok(())
    }
}

// Move `amount` of the counter-asset from `from` to `to` in a staged balance map,
// checked and zero-pruned so the map (and thus the state root) stays canonical.
fn move_counter_asset(
    balances: &mut BTreeMap<Address, u128>,
    from: &Address,
    to: &Address,
    amount: u128,
) -> Result<(), LedgerError> {
    let from_balance = balances
        .get(from)
        .copied()
        .unwrap_or(0)
        .checked_sub(amount)
        .ok_or(LedgerError::CounterAssetUnderflow)?;
    let to_balance = balances
        .get(to)
        .copied()
        .unwrap_or(0)
        .checked_add(amount)
        .ok_or(LedgerError::CounterAssetOverflow)?;
    if from_balance == 0 {
        balances.remove(from);
    } else {
        balances.insert(from.clone(), from_balance);
    }
    if to_balance == 0 {
        balances.remove(to);
    } else {
        balances.insert(to.clone(), to_balance);
    }
    Ok(())
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
            action: Default::default(),
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
    fn from_genesis_seeds_registry_and_counter_asset() {
        let alice = address("alice");
        let bob = address("bobbb");
        let genesis = GenesisConfig::private_devnet()
            .with_account(alice.clone(), XriqAmount::from_base_units(100), 0)
            .with_authorized_wallet(alice.clone())
            .with_authorized_wallet(bob.clone())
            .with_counter_asset(bob.clone(), 500);

        let ledger = LedgerState::from_genesis(&genesis).unwrap();

        assert!(ledger.is_authorized(&alice));
        assert!(ledger.is_authorized(&bob));
        assert_eq!(ledger.authorized_wallets().len(), 2);
        assert_eq!(ledger.counter_balance(&bob), 500);
        assert_eq!(ledger.counter_balance(&alice), 0);
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
            action: Default::default(),
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
            action: Default::default(),
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

    // ---- Authorized-wallet registry: unit + property tests ----
    //
    // The registry is on-chain state mutated only by governance transactions
    // (`AuthorizeWallet` / `RevokeWallet`). Authority gating lives at the node, so
    // these tests exercise the ledger mechanics: the registry primitives, the
    // governance apply path (valueless, fee-charging, atomic), and — critically for
    // consensus — that an EMPTY registry produces a byte-identical state root to the
    // historical account-only root, while a non-empty registry changes it.

    // A self-addressed, valueless governance transaction from `from`. Mirrors the
    // envelope the node accepts: `to == from`, `amount == 0`, a fee, and a signature.
    fn governance_tx(from: Address, action: TxAction, fee: u128, nonce: u64) -> Transaction {
        Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from: from.clone(),
            to: from,
            amount: XriqAmount::ZERO,
            fee: XriqAmount::from_base_units(fee),
            nonce,
            memo_hash: None,
            expires_at_height: Some(100),
            signature: SignatureBytes::new(vec![1, 2, 3]),
            public_key: Vec::new(),
            action,
        }
    }

    #[test]
    fn registry_is_empty_by_default() {
        let ledger = ledger();
        assert!(ledger.authorized_wallets().is_empty());
        assert!(!ledger.is_authorized(&address("alice")));
    }

    #[test]
    fn authorize_is_idempotent_and_revoke_inverts_it() {
        let mut ledger = ledger();
        let alice = address("alice");

        ledger.authorize(alice.clone());
        let after_one = ledger.clone();
        ledger.authorize(alice.clone()); // idempotent: authorizing again is a no-op
        assert_eq!(ledger, after_one, "second authorize mutated the registry");
        assert!(ledger.is_authorized(&alice));

        ledger.revoke(&alice); // inverse of the (single) authorize
        assert!(!ledger.is_authorized(&alice));
        let after_revoke = ledger.clone();
        ledger.revoke(&alice); // idempotent: revoking a non-member is a no-op
        assert_eq!(ledger, after_revoke, "second revoke mutated the registry");
    }

    #[test]
    fn governance_authorize_applies_and_charges_only_the_fee() {
        let authority = address("chain");
        let target = address("bobbb");
        let mut ledger = ledger();
        ledger.set_account(
            authority.clone(),
            Account::new(XriqAmount::from_base_units(100), 0),
        );

        let tx = governance_tx(
            authority.clone(),
            TxAction::AuthorizeWallet {
                target: target.clone(),
            },
            2,
            0,
        );
        ledger.apply_transaction(&tx).unwrap();

        assert!(ledger.is_authorized(&target));
        // Only the fee moved: sender debited the fee and nonce advanced; sink credited.
        assert_eq!(
            ledger.account(&authority),
            Some(Account::new(XriqAmount::from_base_units(98), 1))
        );
        assert_eq!(
            ledger.account(&fee_sink()),
            Some(Account::new(XriqAmount::from_base_units(2), 0))
        );
    }

    #[test]
    fn governance_revoke_removes_from_registry() {
        let authority = address("chain");
        let target = address("bobbb");
        let mut ledger = ledger();
        ledger.set_account(
            authority.clone(),
            Account::new(XriqAmount::from_base_units(100), 0),
        );
        ledger.authorize(target.clone());

        let tx = governance_tx(
            authority.clone(),
            TxAction::RevokeWallet {
                target: target.clone(),
            },
            2,
            0,
        );
        ledger.apply_transaction(&tx).unwrap();
        assert!(!ledger.is_authorized(&target));
    }

    #[test]
    fn governance_carrying_value_is_rejected_without_mutation() {
        let authority = address("chain");
        let mut ledger = ledger();
        ledger.set_account(
            authority.clone(),
            Account::new(XriqAmount::from_base_units(100), 0),
        );
        let mut tx = governance_tx(
            authority.clone(),
            TxAction::AuthorizeWallet {
                target: address("bobbb"),
            },
            2,
            0,
        );
        tx.amount = XriqAmount::from_base_units(1);
        let before = ledger.clone();
        assert_eq!(
            ledger.apply_transaction(&tx),
            Err(LedgerError::Transaction(
                TransactionValidationError::GovernanceMustBeValueless
            ))
        );
        assert_eq!(ledger, before);
    }

    #[test]
    fn governance_not_self_addressed_is_rejected_without_mutation() {
        let authority = address("chain");
        let mut ledger = ledger();
        ledger.set_account(
            authority.clone(),
            Account::new(XriqAmount::from_base_units(100), 0),
        );
        let mut tx = governance_tx(
            authority.clone(),
            TxAction::AuthorizeWallet {
                target: address("bobbb"),
            },
            2,
            0,
        );
        tx.to = address("carol");
        let before = ledger.clone();
        assert_eq!(
            ledger.apply_transaction(&tx),
            Err(LedgerError::Transaction(
                TransactionValidationError::GovernanceRecipientNotSelf
            ))
        );
        assert_eq!(ledger, before);
    }

    #[test]
    fn property_registry_root_stability() {
        for i in 0..20_000u64 {
            let mut rng = FuzzRng::new(0xA557_0217_ED00_0001 ^ i);
            let ledger = fuzz_ledger(&mut rng);

            // Empty registry ⇒ byte-identical to the historical account-only root, so
            // no chain that never authorizes a wallet sees its state root shift.
            assert_eq!(
                ledger.state_root(),
                xriq_crypto::account_state_root(&ledger.state_root_entries()),
                "empty-registry root diverged from account-only root at seed {i}"
            );

            // Authorizing a wallet changes the root; revoking it restores the root
            // (registry inverse ⇒ root inverse).
            let mut with_registry = ledger.clone();
            let target = address(ACCOUNT_LABELS[rng.below(ACCOUNT_LABELS.len() as u64) as usize]);
            with_registry.authorize(target.clone());
            assert!(with_registry.is_authorized(&target));
            assert_ne!(
                with_registry.state_root(),
                ledger.state_root(),
                "non-empty registry did not change the root at seed {i}"
            );
            with_registry.revoke(&target);
            assert_eq!(
                with_registry.state_root(),
                ledger.state_root(),
                "revoke did not restore the empty-registry root at seed {i}"
            );
        }
    }

    #[test]
    fn property_governance_apply_is_atomic_and_moves_only_the_registry() {
        for i in 0..20_000u64 {
            let mut rng = FuzzRng::new(0x60FE_0000_0BAD_0001 ^ i);
            let mut ledger = fuzz_ledger(&mut rng);

            let from = address(ACCOUNT_LABELS[rng.below(ACCOUNT_LABELS.len() as u64) as usize]);
            let target = address(ACCOUNT_LABELS[rng.below(ACCOUNT_LABELS.len() as u64) as usize]);
            let action = if rng.bool() {
                TxAction::AuthorizeWallet {
                    target: target.clone(),
                }
            } else {
                TxAction::RevokeWallet {
                    target: target.clone(),
                }
            };
            // Fee spans below/above min_fee, and the nonce is sometimes wrong, so both
            // the success and the failure/atomicity paths are exercised.
            let fee = rng.below(6) as u128;
            let nonce = if rng.bool() {
                ledger
                    .account(&from)
                    .map(|account| account.nonce)
                    .unwrap_or(0)
            } else {
                rng.below(60)
            };
            let tx = governance_tx(from.clone(), action.clone(), fee, nonce);

            let before = ledger.clone();
            let supply_before = total_supply(&ledger);

            match ledger.apply_transaction(&tx) {
                Ok(()) => {
                    // The registry reflects the action exactly.
                    match &action {
                        TxAction::AuthorizeWallet { target } => {
                            assert!(
                                ledger.is_authorized(target),
                                "authorize not applied at seed {i}"
                            )
                        }
                        TxAction::RevokeWallet { target } => {
                            assert!(
                                !ledger.is_authorized(target),
                                "revoke not applied at seed {i}"
                            )
                        }
                        TxAction::Transfer | TxAction::Swap { .. } => {
                            unreachable!("governance action only")
                        }
                    }
                    // Governance moves no value — the fee merely relocates to the sink.
                    assert_eq!(
                        total_supply(&ledger),
                        supply_before,
                        "supply changed on governance apply at seed {i}"
                    );
                    // Only the sender's nonce advanced, by exactly one.
                    let sender_after = ledger.account(&from).expect("sender exists on success");
                    let sender_before = before.account(&from).expect("a successful sender existed");
                    assert_eq!(
                        sender_after.nonce,
                        sender_before.nonce + 1,
                        "sender nonce not +1 at seed {i}"
                    );
                }
                Err(_) => {
                    // A rejected governance transaction mutates nothing — including the
                    // registry (atomicity across accounts AND the allowlist).
                    assert_eq!(
                        ledger, before,
                        "state mutated on failed governance apply at seed {i}"
                    );
                }
            }
        }
    }

    // ---- Both-parties-approved counter-asset swap: unit + property tests ----
    //
    // A swap moves the native unit one way and the (valueless, test-only) counter-asset
    // the other, atomically, ONLY when both parties are in the authorized-wallet
    // registry. These tests exercise the ledger mechanics: the both-parties-approved
    // gate, exact two-leg movement, and atomicity (a rejected swap mutates nothing —
    // accounts, registry, AND counter-asset).

    fn swap_tx(
        from: Address,
        to: Address,
        amount: u128,
        counter_amount: u128,
        fee: u128,
        nonce: u64,
    ) -> Transaction {
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
            // Non-empty placeholder counterparty co-signature so validate_basic accepts
            // the shape; the ledger applies swaps mechanically and does not verify
            // signatures (that is the node's job), so a placeholder is sufficient here.
            action: TxAction::Swap {
                counter_amount,
                counterparty_public_key: Vec::new(),
                counterparty_signature: SignatureBytes::new(vec![4, 5, 6]),
            },
        }
    }

    fn counter_total(ledger: &LedgerState) -> u128 {
        ledger
            .counter_balance_entries()
            .iter()
            .map(|(_, balance)| balance)
            .sum()
    }

    #[test]
    fn swap_moves_native_and_counter_when_both_approved() {
        let alice = address("alice");
        let bob = address("bobbb");
        let mut ledger = ledger();
        ledger.set_account(
            alice.clone(),
            Account::new(XriqAmount::from_base_units(100), 0),
        );
        ledger.set_account(
            bob.clone(),
            Account::new(XriqAmount::from_base_units(50), 0),
        );
        ledger.authorize(alice.clone());
        ledger.authorize(bob.clone());
        ledger.set_counter_balance(bob.clone(), 30);

        let tx = swap_tx(alice.clone(), bob.clone(), 10, 7, 2, 0);
        ledger.apply_transaction(&tx).unwrap();

        // Native: alice 100 → 88 (−10 −2 fee, nonce +1); bob 50 → 60; sink → 2.
        assert_eq!(
            ledger.account(&alice),
            Some(Account::new(XriqAmount::from_base_units(88), 1))
        );
        assert_eq!(
            ledger.account(&bob),
            Some(Account::new(XriqAmount::from_base_units(60), 0))
        );
        assert_eq!(
            ledger.account(&fee_sink()),
            Some(Account::new(XriqAmount::from_base_units(2), 0))
        );
        // Counter-asset: bob 30 → 23; alice 0 → 7.
        assert_eq!(ledger.counter_balance(&bob), 23);
        assert_eq!(ledger.counter_balance(&alice), 7);
    }

    #[test]
    fn swap_rejected_when_a_party_is_unapproved_without_mutation() {
        let alice = address("alice");
        let bob = address("bobbb");
        let mut ledger = ledger();
        ledger.set_account(
            alice.clone(),
            Account::new(XriqAmount::from_base_units(100), 0),
        );
        ledger.set_account(
            bob.clone(),
            Account::new(XriqAmount::from_base_units(50), 0),
        );
        ledger.authorize(alice.clone()); // bob is NOT authorized
        ledger.set_counter_balance(bob.clone(), 30);

        let tx = swap_tx(alice, bob, 10, 7, 2, 0);
        let before = ledger.clone();
        assert_eq!(
            ledger.apply_transaction(&tx),
            Err(LedgerError::UnauthorizedSwapParty)
        );
        assert_eq!(ledger, before);
    }

    #[test]
    fn swap_rejected_when_counter_asset_insufficient_without_mutation() {
        let alice = address("alice");
        let bob = address("bobbb");
        let mut ledger = ledger();
        ledger.set_account(
            alice.clone(),
            Account::new(XriqAmount::from_base_units(100), 0),
        );
        ledger.set_account(
            bob.clone(),
            Account::new(XriqAmount::from_base_units(50), 0),
        );
        ledger.authorize(alice.clone());
        ledger.authorize(bob.clone());
        ledger.set_counter_balance(bob.clone(), 3); // less than the 7 required

        let tx = swap_tx(alice, bob, 10, 7, 2, 0);
        let before = ledger.clone();
        assert_eq!(
            ledger.apply_transaction(&tx),
            Err(LedgerError::CounterAssetUnderflow)
        );
        assert_eq!(ledger, before);
    }

    #[test]
    fn property_swap_is_atomic_and_moves_exactly_two_legs() {
        for i in 0..20_000u64 {
            let mut rng = FuzzRng::new(0x59A9_0000_0002_0001 ^ i);
            let mut ledger = fuzz_ledger(&mut rng);
            // Seed some counter-asset balances and authorize some accounts (both random,
            // so the unapproved-party and insufficient-counter paths are exercised too).
            for label in ACCOUNT_LABELS {
                if rng.bool() {
                    ledger.set_counter_balance(address(label), rng.below(1_000_000) as u128);
                }
                if rng.bool() {
                    ledger.authorize(address(label));
                }
            }

            let from = address(ACCOUNT_LABELS[rng.below(ACCOUNT_LABELS.len() as u64) as usize]);
            let to = address(ACCOUNT_LABELS[rng.below(ACCOUNT_LABELS.len() as u64) as usize]);
            let min_fee = ledger.config().min_fee.base_units();
            let fee = min_fee + rng.below(4) as u128;
            let amount = 1 + rng.below(1_000) as u128;
            let counter_amount = 1 + rng.below(2_000_000) as u128;
            let nonce = if rng.bool() {
                ledger
                    .account(&from)
                    .map(|account| account.nonce)
                    .unwrap_or(0)
            } else {
                rng.below(60)
            };
            let tx = swap_tx(from.clone(), to.clone(), amount, counter_amount, fee, nonce);

            let before = ledger.clone();
            let native_supply_before = total_supply(&ledger);
            let counter_supply_before = counter_total(&ledger);

            match ledger.apply_transaction(&tx) {
                Ok(()) => {
                    // A successful swap implies both parties were approved and distinct.
                    assert!(
                        before.is_authorized(&from) && before.is_authorized(&to),
                        "swap applied with an unapproved party at seed {i}"
                    );
                    assert_ne!(from, to, "swap applied to itself at seed {i}");
                    // Neither asset is created or destroyed.
                    assert_eq!(
                        total_supply(&ledger),
                        native_supply_before,
                        "native supply changed on swap at seed {i}"
                    );
                    assert_eq!(
                        counter_total(&ledger),
                        counter_supply_before,
                        "counter supply changed on swap at seed {i}"
                    );
                    // Exact two-leg movement when the three native roles are distinct.
                    let sink = ledger.config().fee_sink.clone();
                    if from != sink && to != sink {
                        assert_eq!(
                            ledger.account(&from).unwrap().balance.base_units(),
                            before.account(&from).unwrap().balance.base_units() - amount - fee,
                            "sender native debit wrong at seed {i}"
                        );
                        assert_eq!(
                            ledger.account(&to).unwrap().balance.base_units(),
                            before
                                .account(&to)
                                .map(|a| a.balance.base_units())
                                .unwrap_or(0)
                                + amount,
                            "recipient native credit wrong at seed {i}"
                        );
                        assert_eq!(
                            ledger.account(&sink).unwrap().balance.base_units(),
                            before
                                .account(&sink)
                                .map(|a| a.balance.base_units())
                                .unwrap_or(0)
                                + fee,
                            "fee routing wrong at seed {i}"
                        );
                        // Counter leg moves the other way by exactly counter_amount.
                        assert_eq!(
                            ledger.counter_balance(&to),
                            before.counter_balance(&to) - counter_amount,
                            "recipient counter debit wrong at seed {i}"
                        );
                        assert_eq!(
                            ledger.counter_balance(&from),
                            before.counter_balance(&from) + counter_amount,
                            "sender counter credit wrong at seed {i}"
                        );
                    }
                    // Only the sender's nonce advanced, by exactly one.
                    assert_eq!(
                        ledger.account(&from).unwrap().nonce,
                        before.account(&from).unwrap().nonce + 1,
                        "sender nonce not +1 at seed {i}"
                    );
                }
                Err(_) => {
                    // A rejected swap mutates nothing — accounts, registry, AND the
                    // counter-asset map are byte-identical.
                    assert_eq!(ledger, before, "state mutated on failed swap at seed {i}");
                }
            }
        }
    }
}
