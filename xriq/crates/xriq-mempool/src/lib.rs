//! Deterministic pending-transaction rules for the XRIQ private devnet.

use std::collections::{BTreeMap, BTreeSet};

use xriq_core::{Address, GenesisConfig, GenesisConfigError, Hash32, Transaction, XriqAmount};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct MempoolConfig {
    pub max_transactions: usize,
    pub min_fee: XriqAmount,
}

impl MempoolConfig {
    pub fn from_genesis(genesis: &GenesisConfig) -> Result<Self, GenesisConfigError> {
        genesis.validate()?;
        Ok(Self {
            max_transactions: genesis.mempool_max_transactions,
            min_fee: genesis.min_fee,
        })
    }
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
            public_key: Vec::new(),
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
    fn builds_config_from_genesis_policy() {
        let genesis = GenesisConfig::private_devnet();
        let config = MempoolConfig::from_genesis(&genesis).unwrap();

        assert_eq!(config.max_transactions, genesis.mempool_max_transactions);
        assert_eq!(config.min_fee, genesis.min_fee);
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

    // ---- Property tests: mempool invariants ----
    //
    // Over randomized insert/remove sequences (seeded PRNG for reproducibility), the
    // mempool must always uphold:
    //   * capacity is never exceeded,
    //   * at most one entry per (from, nonce), and no duplicate tx hashes,
    //   * every entry satisfies the fee/amount admission policy,
    //   * `ordered_entries` returns exactly the current set, sorted deterministically
    //     by (fee desc, received_order asc, tx_hash asc),
    //   * remove is the inverse of insert (it frees the (from, nonce) slot),
    //   * rejected inserts never mutate the mempool.

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

    const FROM_LABELS: [&str; 3] = ["alice", "carol", "davee"];

    // Small hash space so duplicate tx-hash collisions actually occur during fuzzing.
    fn fuzz_hash(rng: &mut FuzzRng) -> Hash32 {
        hash(rng.below(24) as u8)
    }

    // A tx from a small (from, nonce) space so DuplicateAccountNonce is exercised;
    // fee/amount are sometimes below policy to exercise the rejection paths.
    fn fuzz_tx(rng: &mut FuzzRng, min_fee: u128) -> Transaction {
        let from = address(FROM_LABELS[rng.below(FROM_LABELS.len() as u64) as usize]);
        let nonce = rng.below(4);
        let amount = rng.below(3); // sometimes 0 (rejected)
        let fee = rng.below(min_fee as u64 + 3); // sometimes below min_fee (rejected)
        tx(from, nonce, amount as u128, fee as u128)
    }

    fn assert_mempool_invariants(mempool: &Mempool) {
        let config = mempool.config();
        assert!(
            mempool.len() <= config.max_transactions,
            "capacity exceeded"
        );

        let ordered = mempool.ordered_entries();
        assert_eq!(ordered.len(), mempool.len(), "ordered length != len");

        let mut seen_nonces: BTreeSet<(Address, u64)> = BTreeSet::new();
        for entry in &ordered {
            // Admission policy holds for every resident entry.
            assert!(!entry.tx.amount.is_zero(), "zero-amount entry resident");
            assert!(entry.tx.fee >= config.min_fee, "sub-min-fee entry resident");
            // Uniqueness of (from, nonce).
            assert!(
                seen_nonces.insert((entry.tx.from.clone(), entry.tx.nonce)),
                "duplicate (from, nonce) resident"
            );
            // ordered_entries only reports resident hashes.
            assert!(
                mempool.contains(&entry.tx_hash),
                "ordered hash not resident"
            );
        }

        // Deterministic total order: (fee desc, received_order asc, tx_hash asc).
        for pair in ordered.windows(2) {
            let (a, b) = (pair[0], pair[1]);
            let ordered_ok = a.tx.fee > b.tx.fee
                || (a.tx.fee == b.tx.fee && a.received_order < b.received_order)
                || (a.tx.fee == b.tx.fee
                    && a.received_order == b.received_order
                    && a.tx_hash <= b.tx_hash);
            assert!(ordered_ok, "ordered_entries not in canonical order");
        }

        // Ordering is stable across calls.
        let ordered_again: Vec<Hash32> = mempool
            .ordered_entries()
            .iter()
            .map(|e| e.tx_hash)
            .collect();
        let ordered_hashes: Vec<Hash32> = ordered.iter().map(|e| e.tx_hash).collect();
        assert_eq!(ordered_again, ordered_hashes, "ordering not deterministic");
    }

    #[test]
    fn property_random_insert_remove_upholds_invariants() {
        for i in 0..10_000u64 {
            let mut rng = FuzzRng::new(0x11AA_22BB_33CC_44DD ^ i);
            let max = 1 + rng.below(6) as usize;
            let min_fee = rng.below(4) as u128;
            let mut mempool = Mempool::new(MempoolConfig {
                max_transactions: max,
                min_fee: XriqAmount::from_base_units(min_fee),
            });

            for _ in 0..40 {
                if rng.bool() {
                    let tx_hash = fuzz_hash(&mut rng);
                    let transaction = fuzz_tx(&mut rng, min_fee);
                    let len_before = mempool.len();
                    let contained = mempool.contains(&tx_hash);
                    match mempool.insert(tx_hash, transaction) {
                        Ok(()) => {
                            assert_eq!(mempool.len(), len_before + 1, "insert did not grow len");
                            assert!(mempool.contains(&tx_hash), "inserted hash missing");
                        }
                        Err(_) => {
                            // A rejected insert must not change size or membership.
                            assert_eq!(mempool.len(), len_before, "rejected insert changed len");
                            assert_eq!(
                                mempool.contains(&tx_hash),
                                contained,
                                "rejected insert changed membership"
                            );
                        }
                    }
                } else {
                    let tx_hash = fuzz_hash(&mut rng);
                    let len_before = mempool.len();
                    let removed = mempool.remove(&tx_hash);
                    if removed.is_some() {
                        assert_eq!(mempool.len(), len_before - 1, "remove did not shrink len");
                        assert!(!mempool.contains(&tx_hash), "removed hash still resident");
                    } else {
                        assert_eq!(mempool.len(), len_before, "no-op remove changed len");
                    }
                }
                assert_mempool_invariants(&mempool);
            }
        }
    }

    #[test]
    fn property_remove_frees_the_account_nonce_slot() {
        for i in 0..10_000u64 {
            let mut rng = FuzzRng::new(0x55EE_66FF_7788_9900 ^ i);
            let mut mempool = Mempool::new(MempoolConfig {
                max_transactions: 8,
                min_fee: XriqAmount::from_base_units(2),
            });
            let from = address(FROM_LABELS[rng.below(FROM_LABELS.len() as u64) as usize]);
            let nonce = rng.below(4);
            let first_hash = fuzz_hash(&mut rng);
            // A valid tx: amount > 0, fee >= min_fee.
            let first = tx(from.clone(), nonce, 5, 2);
            if mempool.insert(first_hash, first).is_err() {
                continue;
            }

            // A different tx hash with the SAME (from, nonce) must be rejected...
            let second_hash = hash(fuzz_hash(&mut rng).as_bytes()[0].wrapping_add(100));
            if second_hash == first_hash {
                continue;
            }
            assert_eq!(
                mempool.insert(second_hash, tx(from.clone(), nonce, 7, 3)),
                Err(MempoolError::DuplicateAccountNonce),
                "same (from, nonce) accepted twice at seed {i}"
            );

            // ...until the first is removed, which frees the (from, nonce) slot.
            assert!(mempool.remove(&first_hash).is_some());
            assert_eq!(
                mempool.insert(second_hash, tx(from, nonce, 7, 3)),
                Ok(()),
                "(from, nonce) slot not freed by remove at seed {i}"
            );
            assert_mempool_invariants(&mempool);
        }
    }

    #[test]
    fn property_duplicate_hash_rejected_without_mutation() {
        for i in 0..10_000u64 {
            let mut rng = FuzzRng::new(0xABCD_1234_5678_EF01 ^ i);
            let mut mempool = Mempool::new(MempoolConfig {
                max_transactions: 8,
                min_fee: XriqAmount::from_base_units(2),
            });
            let tx_hash = fuzz_hash(&mut rng);
            let from = address(FROM_LABELS[rng.below(FROM_LABELS.len() as u64) as usize]);
            if mempool
                .insert(tx_hash, tx(from, rng.below(4), 5, 2))
                .is_err()
            {
                continue;
            }
            let snapshot = mempool.clone();
            // Re-inserting the same hash (any body) is rejected and changes nothing.
            let other = address(FROM_LABELS[rng.below(FROM_LABELS.len() as u64) as usize]);
            assert_eq!(
                mempool.insert(tx_hash, tx(other, rng.below(4) + 100, 9, 4)),
                Err(MempoolError::DuplicateTransaction),
                "duplicate hash accepted at seed {i}"
            );
            assert_eq!(
                mempool, snapshot,
                "duplicate insert mutated state at seed {i}"
            );
        }
    }
}
