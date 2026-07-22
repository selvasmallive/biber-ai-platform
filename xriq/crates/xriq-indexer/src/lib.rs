//! Deterministic read-model indexing for the XRIQ private devnet.
//!
//! This crate is the first Phase 1.1 bridge from file-backed chain state to the
//! PostgreSQL schema in `xriq/db/schema.sql`. It intentionally keeps storage
//! in memory for now so replay behavior can be tested before wiring a database.

mod postgres;

use std::{collections::BTreeMap, fmt};

use xriq_core::{
    Address, BlockValidationError, GenesisConfig, GenesisConfigError, Hash32, ParentHeaderView,
    Transaction, XriqAmount,
};
use xriq_crypto::{
    account_state_root, block_hash as canonical_block_hash, ed25519_address, transaction_hash,
    transactions_root as canonical_transactions_root, verify_block_header_with_scheme,
    verify_transaction_with_scheme, SignatureSchemeKind, SignatureVerificationError,
};
use xriq_ledger::{LedgerError, LedgerState};
use xriq_storage::{ChainStore, StoredBlock};

pub use postgres::{postgres_write_plan, PostgresWritePlan, PostgresWritePlanError};

pub const INDEXER_ACTOR: &str = "xriq-indexer";
pub const INDEXER_ENVIRONMENT: &str = "private-devnet";
pub const INDEXER_PRIVATE_DEVNET_WARNING: &str = "private-devnet-only-no-public-token";
pub const PRIVATE_DEVNET_ALICE_ADDRESS: &str = "xriqdev1alice00000000000";

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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexedChainSnapshot {
    pub warning: &'static str,
    pub environment: &'static str,
    pub chain_id: String,
    pub current_height: u64,
    pub latest_block_hash: String,
    pub state_root: String,
    pub read_model: IndexedReadModel,
    pub summary: IndexReplaySummary,
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum IndexReplayError {
    Genesis(GenesisConfigError),
    Header(BlockValidationError),
    MissingStoredBlock { height: u64 },
    UnexpectedStoredBlockHeight { minimum: u64, actual: u64 },
    UnexpectedStoredBlockCount { expected: usize, actual: usize },
    WrongStoredBlockHash { expected: String, actual: String },
    UnauthorizedProducer { expected: String, actual: String },
    TooManyBlockTransactions { max: usize, actual: usize },
    TransactionSignature(SignatureVerificationError),
    WrongTransactionsRoot { expected: String, actual: String },
    Ledger(LedgerError),
    WrongStateRoot { expected: String, actual: String },
    BlockSignature(SignatureVerificationError),
    Indexer(IndexerError),
}

impl fmt::Display for IndexReplayError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Genesis(error) => write!(formatter, "genesis error: {error:?}"),
            Self::Header(error) => write!(formatter, "block header error: {error:?}"),
            Self::MissingStoredBlock { height } => {
                write!(formatter, "missing stored block at height {height}")
            }
            Self::UnexpectedStoredBlockHeight { minimum, actual } => write!(
                formatter,
                "unexpected stored block height: expected at least {minimum}, got {actual}"
            ),
            Self::UnexpectedStoredBlockCount { expected, actual } => write!(
                formatter,
                "unexpected stored block count: expected {expected}, got {actual}"
            ),
            Self::WrongStoredBlockHash { expected, actual } => write!(
                formatter,
                "wrong stored block hash: expected {expected}, got {actual}"
            ),
            Self::UnauthorizedProducer { expected, actual } => {
                write!(
                    formatter,
                    "unauthorized producer: expected {expected}, got {actual}"
                )
            }
            Self::TooManyBlockTransactions { max, actual } => write!(
                formatter,
                "too many block transactions: max {max}, got {actual}"
            ),
            Self::TransactionSignature(error) => {
                write!(formatter, "transaction signature error: {error:?}")
            }
            Self::WrongTransactionsRoot { expected, actual } => write!(
                formatter,
                "wrong transactions root: expected {expected}, got {actual}"
            ),
            Self::Ledger(error) => write!(formatter, "ledger error: {error:?}"),
            Self::WrongStateRoot { expected, actual } => {
                write!(
                    formatter,
                    "wrong state root: expected {expected}, got {actual}"
                )
            }
            Self::BlockSignature(error) => write!(formatter, "block signature error: {error:?}"),
            Self::Indexer(error) => write!(formatter, "indexer error: {error:?}"),
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
struct BlockApplyCounts {
    blocks_indexed: usize,
    transactions_seen: usize,
    transactions_indexed: usize,
    account_transactions_indexed: usize,
    audit_events_indexed: usize,
}

pub fn private_devnet_indexer_genesis(alice_balance: Option<XriqAmount>) -> GenesisConfig {
    let genesis = GenesisConfig::private_devnet();
    match alice_balance {
        Some(balance) => genesis.with_account(
            Address::parse(PRIVATE_DEVNET_ALICE_ADDRESS)
                .expect("private devnet Alice address is valid"),
            balance,
            0,
        ),
        None => genesis,
    }
}

pub fn index_private_devnet_store<S: ChainStore>(
    store: &S,
    alice_balance: Option<XriqAmount>,
) -> Result<IndexedChainSnapshot, IndexReplayError> {
    index_store_with_genesis(store, &private_devnet_indexer_genesis(alice_balance))
}

/// Index a store replayed under the public testnet genesis. TEST-ONLY chain with
/// no monetary value; the snapshot's `chain_id` is `xriq-testnet`.
pub fn index_public_testnet_store<S: ChainStore>(
    store: &S,
) -> Result<IndexedChainSnapshot, IndexReplayError> {
    index_store_with_genesis(store, &GenesisConfig::public_testnet())
}

fn index_store_with_genesis<S: ChainStore>(
    store: &S,
    genesis: &GenesisConfig,
) -> Result<IndexedChainSnapshot, IndexReplayError> {
    let replay = replay_private_devnet_store(store, genesis)?;
    let (read_model, summary) =
        index_chain_snapshot(store, &replay.ledger).map_err(IndexReplayError::Indexer)?;
    Ok(IndexedChainSnapshot {
        warning: INDEXER_PRIVATE_DEVNET_WARNING,
        environment: INDEXER_ENVIRONMENT,
        chain_id: replay.ledger.config().chain_id.clone(),
        current_height: replay.ledger.current_height(),
        latest_block_hash: hash_hex(replay.latest_block_hash),
        state_root: hash_hex(account_state_root(&replay.ledger.state_root_entries())),
        read_model,
        summary,
    })
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

#[derive(Debug, Clone, PartialEq, Eq)]
struct ReplayPrivateDevnetStoreResult {
    ledger: LedgerState,
    latest_block_hash: Hash32,
}

fn replay_private_devnet_store<S: ChainStore>(
    store: &S,
    genesis: &GenesisConfig,
) -> Result<ReplayPrivateDevnetStoreResult, IndexReplayError> {
    let mut ledger = LedgerState::from_genesis(genesis).map_err(IndexReplayError::Genesis)?;
    let mut latest_block_hash = genesis.genesis_block_hash;
    let Some(latest_record) = store.latest_block() else {
        return Ok(ReplayPrivateDevnetStoreResult {
            ledger,
            latest_block_hash,
        });
    };

    let minimum_height = genesis
        .initial_height
        .checked_add(1)
        .ok_or(IndexReplayError::Header(
            BlockValidationError::HeightOverflow,
        ))?;
    let latest_height = latest_record.block.header.height;
    if latest_height < minimum_height {
        return Err(IndexReplayError::UnexpectedStoredBlockHeight {
            minimum: minimum_height,
            actual: latest_height,
        });
    }

    let mut height = minimum_height;
    while height <= latest_height {
        let record = store
            .block_by_height(height)
            .ok_or(IndexReplayError::MissingStoredBlock { height })?;
        replay_private_devnet_block(&mut ledger, genesis, latest_block_hash, record)?;
        latest_block_hash = record.block_hash;
        if height == latest_height {
            break;
        }
        height = height.checked_add(1).ok_or(IndexReplayError::Header(
            BlockValidationError::HeightOverflow,
        ))?;
    }

    let expected_blocks = ledger
        .current_height()
        .checked_sub(genesis.initial_height)
        .ok_or(IndexReplayError::UnexpectedStoredBlockHeight {
            minimum: genesis.initial_height,
            actual: ledger.current_height(),
        })?;
    let expected_blocks = usize::try_from(expected_blocks)
        .map_err(|_| IndexReplayError::Header(BlockValidationError::HeightOverflow))?;
    if store.len() != expected_blocks {
        return Err(IndexReplayError::UnexpectedStoredBlockCount {
            expected: expected_blocks,
            actual: store.len(),
        });
    }

    Ok(ReplayPrivateDevnetStoreResult {
        ledger,
        latest_block_hash,
    })
}

// The signature scheme a genesis' blocks are verified under: ed25519 when the
// genesis fixes a real authority public key (the public testnet), test-only when it
// does not (the devnet, whose `authority_pubkey` is all-zero). Mirrors the node's
// per-network default so the read-model re-verification matches block production.
fn indexed_genesis_scheme(genesis: &GenesisConfig) -> SignatureSchemeKind {
    if genesis.authority_pubkey == [0u8; 32] {
        SignatureSchemeKind::TestOnly
    } else {
        SignatureSchemeKind::Ed25519
    }
}

fn replay_private_devnet_block(
    ledger: &mut LedgerState,
    genesis: &GenesisConfig,
    parent_block_hash: Hash32,
    record: &StoredBlock,
) -> Result<(), IndexReplayError> {
    let scheme = indexed_genesis_scheme(genesis);
    let expected_hash = canonical_block_hash(&record.block);
    if record.block_hash != expected_hash {
        return Err(IndexReplayError::WrongStoredBlockHash {
            expected: hash_hex(expected_hash),
            actual: hash_hex(record.block_hash),
        });
    }

    let parent = ParentHeaderView {
        chain_id: ledger.config().chain_id.clone(),
        height: ledger.current_height(),
        block_hash: parent_block_hash,
    };
    record
        .block
        .header
        .validate_against_parent(&parent)
        .map_err(IndexReplayError::Header)?;
    if record.block.header.producer != genesis.authority {
        return Err(IndexReplayError::UnauthorizedProducer {
            expected: genesis.authority.to_string(),
            actual: record.block.header.producer.to_string(),
        });
    }
    // Under ed25519, bind the producer identity to its signing key (the header's
    // public key must derive the producer address); an address-string match alone is
    // forgeable. Mirrors the node's block-import check. Test-only skips it.
    if scheme == SignatureSchemeKind::Ed25519
        && !<[u8; 32]>::try_from(record.block.header.public_key.as_slice())
            .map(|key| ed25519_address(&key) == record.block.header.producer)
            .unwrap_or(false)
    {
        return Err(IndexReplayError::UnauthorizedProducer {
            expected: genesis.authority.to_string(),
            actual: record.block.header.producer.to_string(),
        });
    }
    if record.block.transactions.len() > genesis.max_transactions_per_block {
        return Err(IndexReplayError::TooManyBlockTransactions {
            max: genesis.max_transactions_per_block,
            actual: record.block.transactions.len(),
        });
    }
    for transaction in &record.block.transactions {
        verify_transaction_with_scheme(scheme, transaction)
            .map_err(IndexReplayError::TransactionSignature)?;
    }
    let expected_transactions_root = canonical_transactions_root(&record.block.transactions);
    if record.block.header.transactions_root != expected_transactions_root {
        return Err(IndexReplayError::WrongTransactionsRoot {
            expected: hash_hex(expected_transactions_root),
            actual: hash_hex(record.block.header.transactions_root),
        });
    }

    let mut next_ledger = ledger.clone();
    for transaction in &record.block.transactions {
        next_ledger
            .apply_transaction(transaction)
            .map_err(IndexReplayError::Ledger)?;
    }
    let expected_state_root = account_state_root(&next_ledger.state_root_entries());
    if record.block.header.state_root != expected_state_root {
        return Err(IndexReplayError::WrongStateRoot {
            expected: hash_hex(expected_state_root),
            actual: hash_hex(record.block.header.state_root),
        });
    }
    verify_block_header_with_scheme(scheme, &record.block.header)
        .map_err(IndexReplayError::BlockSignature)?;
    next_ledger.set_current_height(record.block.header.height);
    *ledger = next_ledger;
    Ok(())
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
    use xriq_crypto::{
        block_header_signing_hash, test_only_signature_for_hash, transaction_signing_hash,
    };
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
            public_key: Vec::new(),
        }
    }

    fn signed_transaction(
        from: Address,
        to: Address,
        nonce: u64,
        amount: u128,
        fee: u128,
    ) -> Transaction {
        let mut transaction = transaction(from, to, nonce, amount, fee);
        transaction.signature =
            test_only_signature_for_hash(transaction_signing_hash(&transaction));
        transaction
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
                public_key: Vec::new(),
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

    fn canonical_private_devnet_store() -> (InMemoryChainStore, String) {
        let genesis = private_devnet_indexer_genesis(Some(XriqAmount::from_base_units(100)));
        let tx = signed_transaction(address("alice"), address("bobbb"), 0, 25, 2);
        let mut ledger = LedgerState::from_genesis(&genesis).unwrap();
        ledger.apply_transaction(&tx).unwrap();
        let state_root = account_state_root(&ledger.state_root_entries());
        let transactions_root = canonical_transactions_root(std::slice::from_ref(&tx));
        let mut header = BlockHeader {
            version: BlockHeader::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            height: 1,
            previous_block_hash: Hash32::ZERO,
            state_root,
            transactions_root,
            timestamp_ms: 1_001,
            producer: genesis.authority,
            consensus_round: 0,
            signature: SignatureBytes::new(Vec::new()),
            public_key: Vec::new(),
        };
        header.signature = test_only_signature_for_hash(block_header_signing_hash(&header));
        let mut store = InMemoryChainStore::new();
        let block_hash = store
            .append_block_with_canonical_hash(Block {
                header,
                transactions: vec![tx],
            })
            .unwrap();
        (store, hash_hex(block_hash))
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

    #[test]
    fn indexes_private_devnet_store_with_replayed_metadata() {
        let (store, block_hash) = canonical_private_devnet_store();

        let snapshot =
            index_private_devnet_store(&store, Some(XriqAmount::from_base_units(100))).unwrap();

        assert_eq!(snapshot.warning, INDEXER_PRIVATE_DEVNET_WARNING);
        assert_eq!(snapshot.environment, "private-devnet");
        assert_eq!(snapshot.chain_id, "xriq-devnet");
        assert_eq!(snapshot.current_height, 1);
        assert_eq!(snapshot.latest_block_hash, block_hash);
        assert_eq!(snapshot.summary.blocks_seen, 1);
        assert_eq!(snapshot.read_model.blocks.len(), 1);
        assert_eq!(snapshot.read_model.transactions.len(), 1);
        assert_eq!(snapshot.read_model.account_balances.len(), 3);
    }
}
