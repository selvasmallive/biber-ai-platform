//! Deterministic pending-transaction rules for the XRIQ private devnet.

use std::collections::{BTreeMap, BTreeSet};

use xriq_core::{Address, Hash32, Transaction, XriqAmount};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MempoolConfig {
    pub max_transactions: usize,
    pub min_fee: XriqAmount,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MempoolEntry {
    pub tx_hash: Hash32,
    pub tx: Transaction,
    pub received_order: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum MempoolError {
    Full,
    DuplicateTransaction,
    DuplicateAccountNonce,
    FeeTooLow,
    ZeroAmount,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Mempool {
    config: MempoolConfig,
    entries: BTreeMap<Hash32, MempoolEntry>,
    account_nonces: BTreeSet<(Address, u64)>,
    next_order: u64,
}

impl Mempool {
    pub fn new(config: MempoolConfig) -> Self {
        Self {
            config,
            entries: BTreeMap::new(),
            account_nonces: BTreeSet::new(),
            next_order: 0,
        }
    }

    pub const fn config(&self) -> MempoolConfig {
        self.config
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn contains(&self, tx_hash: &Hash32) -> bool {
        self.entries.contains_key(tx_hash)
    }

    pub fn entry(&self, tx_hash: &Hash32) -> Option<&MempoolEntry> {
        self.entries.get(tx_hash)
    }

    pub fn insert(&mut self, tx_hash: Hash32, tx: Transaction) -> Result<(), MempoolError> {
        if self.entries.contains_key(&tx_hash) {
            return Err(MempoolError::DuplicateTransaction);
        }
        if tx.amount.is_zero() {
            return Err(MempoolError::ZeroAmount);
        }
        if tx.fee < self.config.min_fee {
            return Err(MempoolError::FeeTooLow);
        }

        let account_nonce = (tx.from.clone(), tx.nonce);
        if self.account_nonces.contains(&account_nonce) {
            return Err(MempoolError::DuplicateAccountNonce);
        }
        if self.entries.len() >= self.config.max_transactions {
            return Err(MempoolError::Full);
        }

        let entry = MempoolEntry {
            tx_hash,
            tx,
            received_order: self.next_order,
        };
        self.next_order = self.next_order.saturating_add(1);
        self.account_nonces.insert(account_nonce);
        self.entries.insert(tx_hash, entry);
        Ok(())
    }

    pub fn remove(&mut self, tx_hash: &Hash32) -> Option<MempoolEntry> {
        let entry = self.entries.remove(tx_hash)?;
        self.account_nonces
            .remove(&(entry.tx.from.clone(), entry.tx.nonce));
        Some(entry)
    }

    pub fn ordered_entries(&self) -> Vec<&MempoolEntry> {
        let mut entries: Vec<&MempoolEntry> = self.entries.values().collect();
        entries.sort_by(|left, right| {
            right
                .tx
                .fee
                .cmp(&left.tx.fee)
                .then_with(|| left.received_order.cmp(&right.received_order))
                .then_with(|| left.tx_hash.cmp(&right.tx_hash))
        });
        entries
    }

    pub fn clear(&mut self) {
        self.entries.clear();
        self.account_nonces.clear();
        self.next_order = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_core::SignatureBytes;

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn hash(byte: u8) -> Hash32 {
        Hash32::from_bytes([byte; 32])
    }

    fn tx(from: Address, nonce: u64, amount: u128, fee: u128) -> Transaction {
        Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from,
            to: address("bobbb"),
            amount: XriqAmount::from_base_units(amount),
            fee: XriqAmount::from_base_units(fee),
            nonce,
            memo_hash: None,
            expires_at_height: Some(100),
            signature: SignatureBytes::new(vec![1, 2, 3]),
        }
    }

    fn mempool() -> Mempool {
        Mempool::new(MempoolConfig {
            max_transactions: 4,
            min_fee: XriqAmount::from_base_units(2),
        })
    }

    #[test]
    fn accepts_valid_transaction_and_tracks_hash() {
        let mut mempool = mempool();
        let tx_hash = hash(1);

        assert_eq!(
            mempool.insert(tx_hash, tx(address("alice"), 0, 10, 2)),
            Ok(())
        );

        assert_eq!(mempool.len(), 1);
        assert!(mempool.contains(&tx_hash));
        assert!(!mempool.is_empty());
    }

    #[test]
    fn rejects_duplicate_transaction_hash() {
        let mut mempool = mempool();
        let tx_hash = hash(1);

        mempool
            .insert(tx_hash, tx(address("alice"), 0, 10, 2))
            .unwrap();

        assert_eq!(
            mempool.insert(tx_hash, tx(address("carol"), 0, 10, 2)),
            Err(MempoolError::DuplicateTransaction)
        );
    }

    #[test]
    fn rejects_duplicate_account_nonce() {
        let mut mempool = mempool();
        let alice = address("alice");

        mempool
            .insert(hash(1), tx(alice.clone(), 7, 10, 2))
            .unwrap();

        assert_eq!(
            mempool.insert(hash(2), tx(alice, 7, 20, 3)),
            Err(MempoolError::DuplicateAccountNonce)
        );
    }

    #[test]
    fn rejects_low_fee_and_zero_amount() {
        let mut mempool = mempool();

        assert_eq!(
            mempool.insert(hash(1), tx(address("alice"), 0, 10, 1)),
            Err(MempoolError::FeeTooLow)
        );
        assert_eq!(
            mempool.insert(hash(2), tx(address("alice"), 0, 0, 2)),
            Err(MempoolError::ZeroAmount)
        );
        assert_eq!(mempool.len(), 0);
    }

    #[test]
    fn rejects_when_full_and_clear_resets_order() {
        let mut mempool = Mempool::new(MempoolConfig {
            max_transactions: 1,
            min_fee: XriqAmount::from_base_units(2),
        });

        mempool
            .insert(hash(1), tx(address("alice"), 0, 10, 2))
            .unwrap();
        assert_eq!(
            mempool.insert(hash(2), tx(address("carol"), 0, 10, 2)),
            Err(MempoolError::Full)
        );

        mempool.clear();
        assert!(mempool.is_empty());
        mempool
            .insert(hash(3), tx(address("davee"), 0, 10, 2))
            .unwrap();

        assert_eq!(mempool.ordered_entries()[0].received_order, 0);
    }

    #[test]
    fn remove_frees_account_nonce() {
        let mut mempool = mempool();
        let alice = address("alice");
        let tx_hash = hash(1);

        mempool
            .insert(tx_hash, tx(alice.clone(), 7, 10, 2))
            .unwrap();
        assert_eq!(
            mempool.remove(&tx_hash).map(|entry| entry.tx_hash),
            Some(tx_hash)
        );

        assert_eq!(mempool.insert(hash(2), tx(alice, 7, 10, 2)), Ok(()));
        assert_eq!(mempool.len(), 1);
    }

    #[test]
    fn orders_by_fee_then_received_order_then_hash() {
        let mut mempool = mempool();

        mempool
            .insert(hash(3), tx(address("alice"), 0, 10, 2))
            .unwrap();
        mempool
            .insert(hash(1), tx(address("carol"), 0, 10, 5))
            .unwrap();
        mempool
            .insert(hash(2), tx(address("davee"), 0, 10, 5))
            .unwrap();

        let ordered: Vec<Hash32> = mempool
            .ordered_entries()
            .into_iter()
            .map(|entry| entry.tx_hash)
            .collect();

        assert_eq!(ordered, vec![hash(1), hash(2), hash(3)]);
    }
}
