//! Deterministic read-model indexing for the XRIQ private devnet.
//!
//! This crate is the first Phase 1.1 bridge from file-backed chain state to the
//! PostgreSQL schema in `xriq/db/schema.sql`. It intentionally keeps storage
//! in memory for now so replay behavior can be tested before wiring a database.

use std::collections::BTreeMap;

use xriq_core::{Address, Hash32, Transaction, XriqAmount};
use xriq_crypto::{account_state_root, transaction_hash};
use xriq_ledger::LedgerState;
use xriq_storage::{ChainStore, StoredBlock};

pub const INDEXER_ACTOR: &str = "xriq-indexer";
pub const INDEXER_ENVIRONMENT: &str = "private-devnet";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexedBlock {
    pub height: u64,
    pub block_hash: String,
    pub previous_block_hash: String,
    pub state_root: String,
    pub transactions_root: String,
    pub transaction_count: usize,
    pub timestamp_ms: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexedTransaction {
    pub tx_hash: String,
    pub block_height: u64,
    pub block_hash: String,
    pub transaction_index: usize,
    pub status: &'static str,
    pub from_address: String,
    pub to_address: String,
    pub amount_base_units: String,
    pub fee_base_units: String,
    pub nonce: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexedAccount {
    pub address: String,
    pub first_seen_height: Option<u64>,
    pub last_seen_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexedAccountBalance {
    pub address: String,
    pub balance_base_units: String,
    pub nonce: u64,
    pub height: u64,
    pub state_root: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexedAccountTransaction {
    pub address: String,
    pub tx_hash: String,
    pub direction: &'static str,
    pub block_height: u64,
    pub transaction_index: usize,
    pub amount_base_units: String,
    pub fee_base_units: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexedAuditEvent {
    pub event_id: String,
    pub actor: &'static str,
    pub action: &'static str,
    pub resource_type: &'static str,
    pub resource_id: Option<String>,
    pub environment: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct IndexedReadModel {
    pub blocks: BTreeMap<u64, IndexedBlock>,
    pub transactions: BTreeMap<String, IndexedTransaction>,
    pub accounts: BTreeMap<String, IndexedAccount>,
    pub account_balances: BTreeMap<String, IndexedAccountBalance>,
    pub account_transactions: BTreeMap<(String, String, &'static str), IndexedAccountTransaction>,
    pub audit_events: BTreeMap<String, IndexedAuditEvent>,
}

#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct IndexReplaySummary {
    pub blocks_seen: usize,
    pub blocks_indexed: usize,
    pub transactions_seen: usize,
    pub transactions_indexed: usize,
    pub account_transactions_indexed: usize,
    pub account_balances_seen: usize,
    pub account_balances_indexed: usize,
    pub audit_events_indexed: usize,
    pub from_height: Option<u64>,
    pub to_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IndexerError {
    ConflictingBlockHeight {
        height: u64,
    },
    ConflictingTransaction {
        tx_hash: String,
    },
    ConflictingAccountTransaction {
        address: String,
        tx_hash: String,
        direction: &'static str,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
struct BlockApplyCounts {
    blocks_indexed: usize,
    transactions_seen: usize,
    transactions_indexed: usize,
    account_transactions_indexed: usize,
    audit_events_indexed: usize,
}

impl IndexedReadModel {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn replay_chain<S: ChainStore>(
        &mut self,
        store: &S,
        ledger: &LedgerState,
    ) -> Result<IndexReplaySummary, IndexerError> {
        let mut summary = IndexReplaySummary {
            blocks_seen: store.len(),
            ..IndexReplaySummary::default()
        };
        let mut blocks = store.blocks_by_height_desc(store.len());
        blocks.reverse();

        for record in blocks {
            summary.from_height = Some(
                summary
                    .from_height
                    .map_or(record.block.header.height, |height| {
                        height.min(record.block.header.height)
                    }),
            );
            summary.to_height = Some(
                summary
                    .to_height
                    .map_or(record.block.header.height, |height| {
                        height.max(record.block.header.height)
                    }),
            );

            let counts = self.apply_block(record)?;
            summary.blocks_indexed += counts.blocks_indexed;
            summary.transactions_seen += counts.transactions_seen;
            summary.transactions_indexed += counts.transactions_indexed;
            summary.account_transactions_indexed += counts.account_transactions_indexed;
            summary.audit_events_indexed += counts.audit_events_indexed;
        }

        let balance_counts = self.index_account_balances(ledger);
        summary.account_balances_seen = ledger.accounts().len();
        summary.account_balances_indexed = balance_counts;

        Ok(summary)
    }

    fn apply_block(&mut self, record: &StoredBlock) -> Result<BlockApplyCounts, IndexerError> {
        let block_hash = hash_hex(record.block_hash);
        let block = IndexedBlock {
            height: record.block.header.height,
            block_hash: block_hash.clone(),
            previous_block_hash: hash_hex(record.block.header.previous_block_hash),
            state_root: hash_hex(record.block.header.state_root),
            transactions_root: hash_hex(record.block.header.transactions_root),
            transaction_count: record.block.transactions.len(),
            timestamp_ms: record.block.header.timestamp_ms,
        };

        let mut counts = BlockApplyCounts {
            transactions_seen: record.block.transactions.len(),
            ..BlockApplyCounts::default()
        };
        counts.blocks_indexed += self.insert_block(block)?;

        for (transaction_index, transaction) in record.block.transactions.iter().enumerate() {
            let transaction_counts = self.apply_transaction(
                &block_hash,
                record.block.header.height,
                transaction_index,
                transaction,
            )?;
            counts.transactions_indexed += transaction_counts.transactions_indexed;
            counts.account_transactions_indexed += transaction_counts.account_transactions_indexed;
        }

        let event = IndexedAuditEvent {
            event_id: format!("index-block:{}:{block_hash}", record.block.header.height),
            actor: INDEXER_ACTOR,
            action: "index_block",
            resource_type: "block",
            resource_id: Some(block_hash),
            environment: INDEXER_ENVIRONMENT,
        };
        counts.audit_events_indexed += self.insert_audit_event(event);

        Ok(counts)
    }

    fn apply_transaction(
        &mut self,
        block_hash: &str,
        block_height: u64,
        transaction_index: usize,
        transaction: &Transaction,
    ) -> Result<BlockApplyCounts, IndexerError> {
        let tx_hash = hash_hex(transaction_hash(transaction));
        let indexed_transaction = IndexedTransaction {
            tx_hash: tx_hash.clone(),
            block_height,
            block_hash: block_hash.to_string(),
            transaction_index,
            status: "confirmed",
            from_address: transaction.from.to_string(),
            to_address: transaction.to.to_string(),
            amount_base_units: amount_string(transaction.amount),
            fee_base_units: amount_string(transaction.fee),
            nonce: transaction.nonce,
        };
        let mut counts = BlockApplyCounts::default();
        counts.transactions_indexed += self.insert_transaction(indexed_transaction)?;

        self.touch_account(&transaction.from, Some(block_height));
        self.touch_account(&transaction.to, Some(block_height));

        if transaction.from == transaction.to {
            counts.account_transactions_indexed +=
                self.insert_account_transaction(account_transaction(
                    &transaction.from,
                    &tx_hash,
                    "self",
                    block_height,
                    transaction_index,
                    transaction.amount,
                    transaction.fee,
                ))?;
        } else {
            counts.account_transactions_indexed +=
                self.insert_account_transaction(account_transaction(
                    &transaction.from,
                    &tx_hash,
                    "sent",
                    block_height,
                    transaction_index,
                    transaction.amount,
                    transaction.fee,
                ))?;
            counts.account_transactions_indexed +=
                self.insert_account_transaction(account_transaction(
                    &transaction.to,
                    &tx_hash,
                    "received",
                    block_height,
                    transaction_index,
                    transaction.amount,
                    XriqAmount::ZERO,
                ))?;
        }

        Ok(counts)
    }

    fn index_account_balances(&mut self, ledger: &LedgerState) -> usize {
        let height = ledger.current_height();
        let state_root = hash_hex(account_state_root(&ledger.state_root_entries()));
        let mut indexed = 0;

        for (address, account) in ledger.accounts() {
            self.touch_account(address, None);
            let balance = IndexedAccountBalance {
                address: address.to_string(),
                balance_base_units: amount_string(account.balance),
                nonce: account.nonce,
                height,
                state_root: state_root.clone(),
            };
            let key = balance.address.clone();
            if self.account_balances.get(&key) != Some(&balance) {
                self.account_balances.insert(key, balance);
                indexed += 1;
            }
        }

        indexed
    }

    fn insert_block(&mut self, block: IndexedBlock) -> Result<usize, IndexerError> {
        match self.blocks.get(&block.height) {
            Some(existing) if existing == &block => Ok(0),
            Some(_) => Err(IndexerError::ConflictingBlockHeight {
                height: block.height,
            }),
            None => {
                self.blocks.insert(block.height, block);
                Ok(1)
            }
        }
    }

    fn insert_transaction(
        &mut self,
        transaction: IndexedTransaction,
    ) -> Result<usize, IndexerError> {
        match self.transactions.get(&transaction.tx_hash) {
            Some(existing) if existing == &transaction => Ok(0),
            Some(_) => Err(IndexerError::ConflictingTransaction {
                tx_hash: transaction.tx_hash,
            }),
            None => {
                self.transactions
                    .insert(transaction.tx_hash.clone(), transaction);
                Ok(1)
            }
        }
    }

    fn insert_account_transaction(
        &mut self,
        transaction: IndexedAccountTransaction,
    ) -> Result<usize, IndexerError> {
        let key = (
            transaction.address.clone(),
            transaction.tx_hash.clone(),
            transaction.direction,
        );
        match self.account_transactions.get(&key) {
            Some(existing) if existing == &transaction => Ok(0),
            Some(_) => Err(IndexerError::ConflictingAccountTransaction {
                address: transaction.address,
                tx_hash: transaction.tx_hash,
                direction: transaction.direction,
            }),
            None => {
                self.account_transactions.insert(key, transaction);
                Ok(1)
            }
        }
    }

    fn insert_audit_event(&mut self, event: IndexedAuditEvent) -> usize {
        let key = event.event_id.clone();
        if self.audit_events.get(&key) == Some(&event) {
            return 0;
        }
        self.audit_events.insert(key, event);
        1
    }

    fn touch_account(&mut self, address: &Address, height: Option<u64>) {
        let key = address.to_string();
        let account = self.accounts.entry(key.clone()).or_insert(IndexedAccount {
            address: key,
            first_seen_height: height,
            last_seen_height: height,
        });

        if let Some(height) = height {
            account.first_seen_height = Some(
                account
                    .first_seen_height
                    .map_or(height, |existing| existing.min(height)),
            );
            account.last_seen_height = Some(
                account
                    .last_seen_height
                    .map_or(height, |existing| existing.max(height)),
            );
        }
    }
}

pub fn index_chain_snapshot<S: ChainStore>(
    store: &S,
    ledger: &LedgerState,
) -> Result<(IndexedReadModel, IndexReplaySummary), IndexerError> {
    let mut model = IndexedReadModel::new();
    let summary = model.replay_chain(store, ledger)?;
    Ok((model, summary))
}

pub fn hash_hex(hash: Hash32) -> String {
    let mut output = String::with_capacity(64);
    for byte in hash.as_bytes() {
        output.push_str(&format!("{byte:02x}"));
    }
    output
}

fn account_transaction(
    address: &Address,
    tx_hash: &str,
    direction: &'static str,
    block_height: u64,
    transaction_index: usize,
    amount: XriqAmount,
    fee: XriqAmount,
) -> IndexedAccountTransaction {
    IndexedAccountTransaction {
        address: address.to_string(),
        tx_hash: tx_hash.to_string(),
        direction,
        block_height,
        transaction_index,
        amount_base_units: amount_string(amount),
        fee_base_units: amount_string(fee),
    }
}

fn amount_string(amount: XriqAmount) -> String {
    amount.base_units().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_core::{Block, BlockHeader, SignatureBytes, Transaction};
    use xriq_ledger::{Account, LedgerConfig, LedgerState};
    use xriq_storage::{ChainStore, InMemoryChainStore};

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn fee_sink() -> Address {
        Address::parse("xriqdev1fees000000000000").unwrap()
    }

    fn hash(byte: u8) -> Hash32 {
        Hash32::from_bytes([byte; 32])
    }

    fn transaction(from: Address, to: Address, nonce: u64, amount: u128, fee: u128) -> Transaction {
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
        }
    }

    fn block(height: u64, previous_block_hash: Hash32, transactions: Vec<Transaction>) -> Block {
        Block {
            header: BlockHeader {
                version: BlockHeader::SUPPORTED_VERSION,
                chain_id: "xriq-devnet".to_string(),
                height,
                previous_block_hash,
                state_root: hash(40 + height as u8),
                transactions_root: hash(50 + height as u8),
                timestamp_ms: 1_000 + height,
                producer: address("author"),
                consensus_round: 0,
                signature: SignatureBytes::new(vec![9]),
            },
            transactions,
        }
    }

    fn fixture() -> (InMemoryChainStore, LedgerState, String, String) {
        let alice = address("alice");
        let bob = address("bobbb");
        let tx1 = transaction(alice.clone(), bob.clone(), 0, 25, 2);
        let tx2 = transaction(bob.clone(), alice.clone(), 0, 5, 2);

        let mut store = InMemoryChainStore::new();
        store
            .append_block(hash(1), block(1, hash(0), vec![tx1.clone()]))
            .unwrap();
        store
            .append_block(hash(2), block(2, hash(1), vec![tx2.clone()]))
            .unwrap();

        let mut ledger = LedgerState::new(LedgerConfig {
            chain_id: "xriq-devnet".to_string(),
            current_height: 0,
            min_fee: XriqAmount::from_base_units(2),
            fee_sink: fee_sink(),
        });
        ledger.set_account(alice, Account::new(XriqAmount::from_base_units(100), 0));
        ledger.apply_transaction(&tx1).unwrap();
        ledger.set_current_height(1);
        ledger.apply_transaction(&tx2).unwrap();
        ledger.set_current_height(2);

        let tx1_hash = hash_hex(transaction_hash(&tx1));
        let tx2_hash = hash_hex(transaction_hash(&tx2));
        (store, ledger, tx1_hash, tx2_hash)
    }

    #[test]
    fn indexes_blocks_transactions_and_final_balances() {
        let (store, ledger, tx1_hash, tx2_hash) = fixture();

        let (model, summary) = index_chain_snapshot(&store, &ledger).unwrap();

        assert_eq!(summary.blocks_seen, 2);
        assert_eq!(summary.blocks_indexed, 2);
        assert_eq!(summary.transactions_seen, 2);
        assert_eq!(summary.transactions_indexed, 2);
        assert_eq!(summary.account_transactions_indexed, 4);
        assert_eq!(summary.account_balances_seen, 3);
        assert_eq!(summary.account_balances_indexed, 3);
        assert_eq!(summary.from_height, Some(1));
        assert_eq!(summary.to_height, Some(2));

        assert_eq!(model.blocks[&1].block_hash, hash_hex(hash(1)));
        assert_eq!(model.blocks[&2].previous_block_hash, hash_hex(hash(1)));
        assert_eq!(model.transactions[&tx1_hash].status, "confirmed");
        assert_eq!(model.transactions[&tx2_hash].block_height, 2);
        assert_eq!(
            model.account_balances["xriqdev1alice00000000000"].balance_base_units,
            "78"
        );
        assert_eq!(
            model.account_balances["xriqdev1bobbb00000000000"].balance_base_units,
            "18"
        );
        assert_eq!(
            model.account_balances["xriqdev1fees000000000000"].balance_base_units,
            "4"
        );
    }

    #[test]
    fn replay_is_idempotent() {
        let (store, ledger, _, _) = fixture();
        let mut model = IndexedReadModel::new();

        model.replay_chain(&store, &ledger).unwrap();
        let first = model.clone();
        let second_summary = model.replay_chain(&store, &ledger).unwrap();

        assert_eq!(model, first);
        assert_eq!(second_summary.blocks_indexed, 0);
        assert_eq!(second_summary.transactions_indexed, 0);
        assert_eq!(second_summary.account_transactions_indexed, 0);
        assert_eq!(second_summary.account_balances_indexed, 0);
        assert_eq!(second_summary.audit_events_indexed, 0);
    }

    #[test]
    fn records_account_transaction_direction_and_recipient_fee() {
        let (store, ledger, tx1_hash, tx2_hash) = fixture();
        let (model, _) = index_chain_snapshot(&store, &ledger).unwrap();

        let alice_sent = &model.account_transactions
            [&("xriqdev1alice00000000000".to_string(), tx1_hash, "sent")];
        assert_eq!(alice_sent.amount_base_units, "25");
        assert_eq!(alice_sent.fee_base_units, "2");

        let alice_received = &model.account_transactions
            [&("xriqdev1alice00000000000".to_string(), tx2_hash, "received")];
        assert_eq!(alice_received.amount_base_units, "5");
        assert_eq!(alice_received.fee_base_units, "0");
    }

    #[test]
    fn detects_conflicting_replay_at_same_height() {
        let (store, ledger, _, _) = fixture();
        let mut model = IndexedReadModel::new();
        model.replay_chain(&store, &ledger).unwrap();

        let mut changed_store = InMemoryChainStore::new();
        changed_store
            .append_block(
                hash(9),
                block(
                    1,
                    hash(0),
                    vec![transaction(address("alice"), address("carol"), 0, 10, 2)],
                ),
            )
            .unwrap();

        assert_eq!(
            model.replay_chain(&changed_store, &ledger),
            Err(IndexerError::ConflictingBlockHeight { height: 1 })
        );
    }
}
