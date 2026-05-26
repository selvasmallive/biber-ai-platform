//! Read-only explorer views for the XRIQ private devnet.
//!
//! This crate intentionally stays dependency-free and UI-framework-free. It
//! provides stable view models and a small text renderer that a later private
//! web explorer can wrap after the protocol surface is more complete.

use std::fmt::Write as _;

use xriq_core::{Address, Hash32, Transaction, XriqAmount};
use xriq_crypto::transaction_hash;
use xriq_rpc::{RpcError, RpcService};
use xriq_storage::{ChainStore, StoredBlock};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerOverview {
    pub chain_id: String,
    pub current_height: u64,
    pub latest_block_hash: Hash32,
    pub state_root: Hash32,
    pub pending_transactions: usize,
    pub stored_blocks: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerBlockSummary {
    pub height: u64,
    pub block_hash: Hash32,
    pub transaction_count: usize,
    pub producer: Address,
    pub timestamp_ms: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerBlockDetail {
    pub summary: ExplorerBlockSummary,
    pub previous_block_hash: Hash32,
    pub state_root: Hash32,
    pub transactions_root: Hash32,
    pub transactions: Vec<ExplorerTransactionSummary>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerTransactionSummary {
    pub index: usize,
    pub tx_hash: Hash32,
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerAccountDetail {
    pub address: Address,
    pub balance: XriqAmount,
    pub nonce: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerAccountTransaction {
    pub block_height: u64,
    pub block_hash: Hash32,
    pub transaction_index: usize,
    pub direction: &'static str,
    pub tx_hash: Hash32,
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerConfirmedTransaction {
    pub block_height: u64,
    pub block_hash: Hash32,
    pub transaction_index: usize,
    pub tx_hash: Hash32,
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerMempoolDetail {
    pub pending_count: usize,
    pub transactions: Vec<ExplorerPendingTransaction>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerPendingTransaction {
    pub tx_hash: Hash32,
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub received_order: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ExplorerError {
    AccountNotFound,
    BlockNotFound,
    TransactionNotFound,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerService<'a, S: ChainStore> {
    rpc: RpcService,
    store: &'a S,
}

impl<'a, S: ChainStore> ExplorerService<'a, S> {
    pub fn new(rpc: RpcService, store: &'a S) -> Self {
        Self { rpc, store }
    }

    pub fn overview(&self) -> ExplorerOverview {
        let status = self.rpc.chain_status();
        ExplorerOverview {
            chain_id: status.chain_id,
            current_height: status.current_height,
            latest_block_hash: status.latest_block_hash,
            state_root: status.state_root,
            pending_transactions: status.pending_transactions,
            stored_blocks: self.store.len(),
        }
    }

    pub fn latest_blocks(&self, limit: usize) -> Vec<ExplorerBlockSummary> {
        self.store
            .blocks_by_height_desc(limit)
            .into_iter()
            .map(block_summary)
            .collect()
    }

    pub fn block_by_height(&self, height: u64) -> Result<ExplorerBlockDetail, ExplorerError> {
        self.store
            .block_by_height(height)
            .map(block_detail)
            .ok_or(ExplorerError::BlockNotFound)
    }

    pub fn block_by_hash(&self, block_hash: &Hash32) -> Result<ExplorerBlockDetail, ExplorerError> {
        self.store
            .block_by_hash(block_hash)
            .map(block_detail)
            .ok_or(ExplorerError::BlockNotFound)
    }

    pub fn latest_block(&self) -> Result<ExplorerBlockDetail, ExplorerError> {
        self.store
            .latest_block()
            .map(block_detail)
            .ok_or(ExplorerError::BlockNotFound)
    }

    pub fn account(&self, address: &Address) -> Result<ExplorerAccountDetail, ExplorerError> {
        let account = self.rpc.account(address).map_err(|error| match error {
            RpcError::AccountNotFound => ExplorerError::AccountNotFound,
            RpcError::Transaction(_) | RpcError::TransactionSignature(_) | RpcError::Mempool(_) => {
                ExplorerError::AccountNotFound
            }
        })?;
        Ok(ExplorerAccountDetail {
            address: account.address,
            balance: account.balance,
            nonce: account.nonce,
        })
    }

    pub fn accounts(&self, limit: usize) -> Vec<ExplorerAccountDetail> {
        self.rpc
            .accounts(limit)
            .into_iter()
            .map(|account| ExplorerAccountDetail {
                address: account.address,
                balance: account.balance,
                nonce: account.nonce,
            })
            .collect()
    }

    pub fn account_transactions(
        &self,
        address: &Address,
        limit: usize,
    ) -> Vec<ExplorerAccountTransaction> {
        if limit == 0 {
            return Vec::new();
        }

        let mut transactions = Vec::new();
        for record in self.store.blocks_by_height_desc(self.store.len()) {
            for (transaction_index, transaction) in record.block.transactions.iter().enumerate() {
                if transaction.from == *address || transaction.to == *address {
                    transactions.push(account_transaction_summary(
                        record,
                        transaction_index,
                        transaction,
                        address,
                    ));
                    if transactions.len() == limit {
                        return transactions;
                    }
                }
            }
        }
        transactions
    }

    pub fn latest_transactions(&self, limit: usize) -> Vec<ExplorerConfirmedTransaction> {
        if limit == 0 {
            return Vec::new();
        }

        let mut transactions = Vec::new();
        for record in self.store.blocks_by_height_desc(self.store.len()) {
            for (transaction_index, transaction) in record.block.transactions.iter().enumerate() {
                transactions.push(confirmed_transaction_summary(
                    record,
                    transaction_index,
                    transaction,
                ));
                if transactions.len() == limit {
                    return transactions;
                }
            }
        }
        transactions
    }

    pub fn mempool(&self) -> ExplorerMempoolDetail {
        let transactions = self
            .rpc
            .mempool_state()
            .ordered_entries()
            .into_iter()
            .map(|entry| ExplorerPendingTransaction {
                tx_hash: entry.tx_hash,
                from: entry.tx.from.clone(),
                to: entry.tx.to.clone(),
                amount: entry.tx.amount,
                fee: entry.tx.fee,
                nonce: entry.tx.nonce,
                received_order: entry.received_order,
                expires_at_height: entry.tx.expires_at_height,
            })
            .collect();
        ExplorerMempoolDetail {
            pending_count: self.rpc.mempool_state().len(),
            transactions,
        }
    }

    pub fn pending_transaction(
        &self,
        tx_hash: &Hash32,
    ) -> Result<ExplorerPendingTransaction, ExplorerError> {
        let entry = self
            .rpc
            .mempool_state()
            .entry(tx_hash)
            .ok_or(ExplorerError::TransactionNotFound)?;
        Ok(ExplorerPendingTransaction {
            tx_hash: entry.tx_hash,
            from: entry.tx.from.clone(),
            to: entry.tx.to.clone(),
            amount: entry.tx.amount,
            fee: entry.tx.fee,
            nonce: entry.tx.nonce,
            received_order: entry.received_order,
            expires_at_height: entry.tx.expires_at_height,
        })
    }

    pub fn render_overview(&self, block_limit: usize) -> String {
        render_overview(&self.overview(), &self.latest_blocks(block_limit))
    }
}

pub fn render_overview(
    overview: &ExplorerOverview,
    latest_blocks: &[ExplorerBlockSummary],
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "XRIQ Private Devnet Explorer").expect("write to String");
    writeln!(&mut output, "chain: {}", overview.chain_id).expect("write to String");
    writeln!(&mut output, "current height: {}", overview.current_height).expect("write to String");
    writeln!(
        &mut output,
        "latest block: {}",
        hash_hex(overview.latest_block_hash)
    )
    .expect("write to String");
    writeln!(&mut output, "state root: {}", hash_hex(overview.state_root))
        .expect("write to String");
    writeln!(
        &mut output,
        "stored blocks: {}, pending transactions: {}",
        overview.stored_blocks, overview.pending_transactions
    )
    .expect("write to String");
    writeln!(&mut output, "latest blocks:").expect("write to String");
    for block in latest_blocks {
        writeln!(
            &mut output,
            "- height {} {} txs={} producer={}",
            block.height,
            hash_hex(block.block_hash),
            block.transaction_count,
            block.producer
        )
        .expect("write to String");
    }
    output
}

pub fn render_latest_blocks(blocks: &[ExplorerBlockSummary]) -> String {
    let mut output = String::new();
    writeln!(&mut output, "latest blocks").expect("write to String");
    writeln!(&mut output, "blocks: {}", blocks.len()).expect("write to String");
    for block in blocks {
        writeln!(
            &mut output,
            "- height {} {} txs={} producer={} timestamp_ms={}",
            block.height,
            hash_hex(block.block_hash),
            block.transaction_count,
            block.producer,
            block.timestamp_ms
        )
        .expect("write to String");
    }
    output
}

pub fn render_block_detail(block: &ExplorerBlockDetail) -> String {
    let mut output = String::new();
    writeln!(
        &mut output,
        "block {} {}",
        block.summary.height,
        hash_hex(block.summary.block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "previous: {}",
        hash_hex(block.previous_block_hash)
    )
    .expect("write to String");
    writeln!(&mut output, "state root: {}", hash_hex(block.state_root)).expect("write to String");
    writeln!(
        &mut output,
        "transactions root: {}",
        hash_hex(block.transactions_root)
    )
    .expect("write to String");
    writeln!(&mut output, "transactions: {}", block.transactions.len()).expect("write to String");
    for tx in &block.transactions {
        writeln!(
            &mut output,
            "- #{index} {tx_hash} {from} -> {to} amount={amount} fee={fee} nonce={nonce}",
            index = tx.index,
            tx_hash = hash_hex(tx.tx_hash),
            from = tx.from,
            to = tx.to,
            amount = tx.amount,
            fee = tx.fee,
            nonce = tx.nonce
        )
        .expect("write to String");
    }
    output
}

pub fn render_account_detail(account: &ExplorerAccountDetail) -> String {
    let mut output = String::new();
    writeln!(&mut output, "account {}", account.address).expect("write to String");
    writeln!(&mut output, "balance: {}", account.balance).expect("write to String");
    writeln!(&mut output, "nonce: {}", account.nonce).expect("write to String");
    output
}

pub fn render_accounts(accounts: &[ExplorerAccountDetail]) -> String {
    let mut output = String::new();
    writeln!(&mut output, "accounts: {}", accounts.len()).expect("write to String");
    for account in accounts {
        writeln!(
            &mut output,
            "- {address} balance={balance} nonce={nonce}",
            address = account.address,
            balance = account.balance,
            nonce = account.nonce
        )
        .expect("write to String");
    }
    output
}

pub fn render_account_transactions(
    address: &Address,
    transactions: &[ExplorerAccountTransaction],
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "account transactions {}", address).expect("write to String");
    writeln!(&mut output, "transactions: {}", transactions.len()).expect("write to String");
    for transaction in transactions {
        writeln!(
            &mut output,
            "- height {height} #{index} {direction} {tx_hash} {from} -> {to} amount={amount} fee={fee} nonce={nonce}",
            height = transaction.block_height,
            index = transaction.transaction_index,
            direction = transaction.direction,
            tx_hash = hash_hex(transaction.tx_hash),
            from = transaction.from,
            to = transaction.to,
            amount = transaction.amount,
            fee = transaction.fee,
            nonce = transaction.nonce,
        )
        .expect("write to String");
    }
    output
}

pub fn render_latest_transactions(transactions: &[ExplorerConfirmedTransaction]) -> String {
    let mut output = String::new();
    writeln!(&mut output, "latest transactions").expect("write to String");
    writeln!(&mut output, "transactions: {}", transactions.len()).expect("write to String");
    for transaction in transactions {
        writeln!(
            &mut output,
            "- height {height} #{index} {tx_hash} {from} -> {to} amount={amount} fee={fee} nonce={nonce}",
            height = transaction.block_height,
            index = transaction.transaction_index,
            tx_hash = hash_hex(transaction.tx_hash),
            from = transaction.from,
            to = transaction.to,
            amount = transaction.amount,
            fee = transaction.fee,
            nonce = transaction.nonce,
        )
        .expect("write to String");
    }
    output
}

pub fn render_mempool(detail: &ExplorerMempoolDetail) -> String {
    let mut output = String::new();
    writeln!(&mut output, "mempool pending: {}", detail.pending_count).expect("write to String");
    for tx in &detail.transactions {
        writeln!(
            &mut output,
            "- {} {from} -> {to} amount={amount} fee={fee} nonce={nonce}",
            hash_hex(tx.tx_hash),
            from = tx.from,
            to = tx.to,
            amount = tx.amount,
            fee = tx.fee,
            nonce = tx.nonce
        )
        .expect("write to String");
    }
    output
}

pub fn hash_hex(hash: Hash32) -> String {
    let mut output = String::with_capacity(64);
    for byte in hash.as_bytes() {
        write!(&mut output, "{byte:02x}").expect("write to String");
    }
    output
}

fn block_summary(record: &StoredBlock) -> ExplorerBlockSummary {
    ExplorerBlockSummary {
        height: record.block.header.height,
        block_hash: record.block_hash,
        transaction_count: record.block.transactions.len(),
        producer: record.block.header.producer.clone(),
        timestamp_ms: record.block.header.timestamp_ms,
    }
}

fn block_detail(record: &StoredBlock) -> ExplorerBlockDetail {
    ExplorerBlockDetail {
        summary: block_summary(record),
        previous_block_hash: record.block.header.previous_block_hash,
        state_root: record.block.header.state_root,
        transactions_root: record.block.header.transactions_root,
        transactions: record
            .block
            .transactions
            .iter()
            .enumerate()
            .map(transaction_summary)
            .collect(),
    }
}

fn transaction_summary((index, tx): (usize, &Transaction)) -> ExplorerTransactionSummary {
    ExplorerTransactionSummary {
        index,
        tx_hash: transaction_hash(tx),
        from: tx.from.clone(),
        to: tx.to.clone(),
        amount: tx.amount,
        fee: tx.fee,
        nonce: tx.nonce,
        expires_at_height: tx.expires_at_height,
    }
}

fn account_transaction_summary(
    record: &StoredBlock,
    transaction_index: usize,
    transaction: &Transaction,
    address: &Address,
) -> ExplorerAccountTransaction {
    ExplorerAccountTransaction {
        block_height: record.block.header.height,
        block_hash: record.block_hash,
        transaction_index,
        direction: account_transaction_direction(transaction, address),
        tx_hash: transaction_hash(transaction),
        from: transaction.from.clone(),
        to: transaction.to.clone(),
        amount: transaction.amount,
        fee: transaction.fee,
        nonce: transaction.nonce,
        expires_at_height: transaction.expires_at_height,
    }
}

fn confirmed_transaction_summary(
    record: &StoredBlock,
    transaction_index: usize,
    transaction: &Transaction,
) -> ExplorerConfirmedTransaction {
    ExplorerConfirmedTransaction {
        block_height: record.block.header.height,
        block_hash: record.block_hash,
        transaction_index,
        tx_hash: transaction_hash(transaction),
        from: transaction.from.clone(),
        to: transaction.to.clone(),
        amount: transaction.amount,
        fee: transaction.fee,
        nonce: transaction.nonce,
        expires_at_height: transaction.expires_at_height,
    }
}

fn account_transaction_direction(transaction: &Transaction, address: &Address) -> &'static str {
    if transaction.from == *address && transaction.to == *address {
        "self"
    } else if transaction.from == *address {
        "sent"
    } else {
        "received"
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_core::{Block, BlockHeader, SignatureBytes};
    use xriq_crypto::account_state_root;
    use xriq_ledger::{Account, LedgerConfig, LedgerState};
    use xriq_mempool::{Mempool, MempoolConfig};
    use xriq_storage::InMemoryChainStore;

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn fee_sink() -> Address {
        Address::parse("xriqdev1fees000000000000").unwrap()
    }

    fn hash(byte: u8) -> Hash32 {
        Hash32::from_bytes([byte; 32])
    }

    fn transaction(from: Address, nonce: u64, amount: u128, fee: u128) -> Transaction {
        transaction_to(from, address("bobbb"), nonce, amount, fee)
    }

    fn transaction_to(
        from: Address,
        to: Address,
        nonce: u64,
        amount: u128,
        fee: u128,
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
        }
    }

    fn block(height: u64, previous_block_hash: Hash32, txs: Vec<Transaction>) -> Block {
        Block {
            header: BlockHeader {
                version: BlockHeader::SUPPORTED_VERSION,
                chain_id: "xriq-devnet".to_string(),
                height,
                previous_block_hash,
                state_root: hash(30 + height as u8),
                transactions_root: hash(40 + height as u8),
                timestamp_ms: 1_000 + height,
                producer: address("author"),
                consensus_round: 0,
                signature: SignatureBytes::new(vec![9]),
            },
            transactions: txs,
        }
    }

    fn fixture() -> (RpcService, InMemoryChainStore) {
        let mut ledger = LedgerState::new(LedgerConfig {
            chain_id: "xriq-devnet".to_string(),
            current_height: 2,
            min_fee: XriqAmount::from_base_units(2),
            fee_sink: fee_sink(),
        });
        ledger.set_account(
            address("alice"),
            Account::new(XriqAmount::from_base_units(100), 1),
        );
        ledger.set_account(
            address("bobbb"),
            Account::new(XriqAmount::from_base_units(25), 0),
        );

        let mut mempool = Mempool::new(MempoolConfig {
            max_transactions: 8,
            min_fee: XriqAmount::from_base_units(2),
        });
        mempool
            .insert(hash(6), transaction(address("alice"), 1, 10, 3))
            .unwrap();
        mempool
            .insert(hash(5), transaction(address("carol"), 0, 7, 5))
            .unwrap();

        let mut store = InMemoryChainStore::new();
        store
            .append_block(
                hash(1),
                block(1, hash(0), vec![transaction(address("alice"), 0, 25, 2)]),
            )
            .unwrap();
        store
            .append_block(
                hash(2),
                block(
                    2,
                    hash(1),
                    vec![transaction_to(address("bobbb"), address("alice"), 0, 5, 2)],
                ),
            )
            .unwrap();

        (RpcService::new(ledger, mempool, hash(2)), store)
    }

    fn fixture_state_root() -> Hash32 {
        let mut ledger = LedgerState::new(LedgerConfig {
            chain_id: "xriq-devnet".to_string(),
            current_height: 2,
            min_fee: XriqAmount::from_base_units(2),
            fee_sink: fee_sink(),
        });
        ledger.set_account(
            address("alice"),
            Account::new(XriqAmount::from_base_units(100), 1),
        );
        ledger.set_account(
            address("bobbb"),
            Account::new(XriqAmount::from_base_units(25), 0),
        );
        account_state_root(&ledger.state_root_entries())
    }

    #[test]
    fn overview_reports_chain_and_store_counts() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        assert_eq!(
            explorer.overview(),
            ExplorerOverview {
                chain_id: "xriq-devnet".to_string(),
                current_height: 2,
                latest_block_hash: hash(2),
                state_root: fixture_state_root(),
                pending_transactions: 2,
                stored_blocks: 2,
            }
        );
    }

    #[test]
    fn lists_latest_blocks_descending() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        let heights: Vec<u64> = explorer
            .latest_blocks(2)
            .into_iter()
            .map(|block| block.height)
            .collect();

        assert_eq!(heights, vec![2, 1]);
        assert!(explorer.latest_blocks(0).is_empty());
    }

    #[test]
    fn returns_block_detail_with_transfer_summary() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        let block = explorer.block_by_height(1).unwrap();

        assert_eq!(block.summary.height, 1);
        assert_eq!(block.summary.block_hash, hash(1));
        assert_eq!(block.previous_block_hash, hash(0));
        assert_eq!(block.transactions.len(), 1);
        assert_eq!(
            block.transactions[0].tx_hash,
            transaction_hash(&store.block_by_height(1).unwrap().block.transactions[0])
        );
        assert_eq!(block.transactions[0].from, address("alice"));
        assert_eq!(block.transactions[0].to, address("bobbb"));
        assert_eq!(
            block.transactions[0].amount,
            XriqAmount::from_base_units(25)
        );

        let latest = explorer.latest_block().unwrap();
        assert_eq!(latest.summary.height, 2);
        assert_eq!(latest.summary.block_hash, hash(2));
    }

    #[test]
    fn returns_account_detail() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        assert_eq!(
            explorer.account(&address("alice")),
            Ok(ExplorerAccountDetail {
                address: address("alice"),
                balance: XriqAmount::from_base_units(100),
                nonce: 1,
            })
        );
        assert_eq!(
            explorer.account(&address("davee")),
            Err(ExplorerError::AccountNotFound)
        );
    }

    #[test]
    fn lists_accounts_in_deterministic_order() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        let accounts = explorer.accounts(10);

        assert_eq!(accounts.len(), 3);
        assert_eq!(accounts[0].address, address("alice"));
        assert_eq!(accounts[0].balance, XriqAmount::from_base_units(100));
        assert_eq!(accounts[1].address, address("bobbb"));
        assert_eq!(accounts[2].address, fee_sink());
        assert_eq!(explorer.accounts(1).len(), 1);
        assert!(explorer.accounts(0).is_empty());
    }

    #[test]
    fn lists_account_transactions_descending_with_direction() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        let alice_transactions = explorer.account_transactions(&address("alice"), 10);

        assert_eq!(alice_transactions.len(), 2);
        assert_eq!(alice_transactions[0].block_height, 2);
        assert_eq!(alice_transactions[0].direction, "received");
        assert_eq!(alice_transactions[0].from, address("bobbb"));
        assert_eq!(alice_transactions[1].block_height, 1);
        assert_eq!(alice_transactions[1].direction, "sent");
        assert_eq!(alice_transactions[1].to, address("bobbb"));
        assert_eq!(explorer.account_transactions(&address("alice"), 1).len(), 1);
        assert!(explorer
            .account_transactions(&address("alice"), 0)
            .is_empty());
        assert!(explorer
            .account_transactions(&address("davee"), 10)
            .is_empty());
    }

    #[test]
    fn lists_latest_confirmed_transactions_descending() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        let transactions = explorer.latest_transactions(10);

        assert_eq!(transactions.len(), 2);
        assert_eq!(transactions[0].block_height, 2);
        assert_eq!(transactions[0].from, address("bobbb"));
        assert_eq!(transactions[0].to, address("alice"));
        assert_eq!(transactions[1].block_height, 1);
        assert_eq!(transactions[1].from, address("alice"));
        assert_eq!(transactions[1].to, address("bobbb"));
        assert_eq!(explorer.latest_transactions(1).len(), 1);
        assert!(explorer.latest_transactions(0).is_empty());
    }

    #[test]
    fn lists_pending_mempool_transactions_in_order() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        let mempool = explorer.mempool();

        assert_eq!(mempool.pending_count, 2);
        assert_eq!(mempool.transactions[0].tx_hash, hash(5));
        assert_eq!(mempool.transactions[1].tx_hash, hash(6));
        assert_eq!(
            explorer.pending_transaction(&hash(6)).unwrap().from,
            address("alice")
        );
    }

    #[test]
    fn missing_block_or_transaction_returns_error() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        assert_eq!(
            explorer.block_by_hash(&hash(99)),
            Err(ExplorerError::BlockNotFound)
        );
        assert_eq!(
            explorer.pending_transaction(&hash(99)),
            Err(ExplorerError::TransactionNotFound)
        );
    }

    #[test]
    fn text_renderers_include_private_devnet_inspection_fields() {
        let (rpc, store) = fixture();
        let explorer = ExplorerService::new(rpc, &store);

        let overview = explorer.render_overview(2);
        assert!(overview.contains("XRIQ Private Devnet Explorer"));
        assert!(overview.contains("current height: 2"));
        assert!(overview.contains("state root: "));
        assert!(overview.contains("pending transactions: 2"));

        let latest_blocks = render_latest_blocks(&explorer.latest_blocks(2));
        assert!(latest_blocks.contains("latest blocks"));
        assert!(latest_blocks.contains("blocks: 2"));
        assert!(latest_blocks.contains("height 2"));

        let block_detail = explorer.block_by_height(1).unwrap();
        let block_hash = hash_hex(block_detail.transactions[0].tx_hash);
        let block = render_block_detail(&block_detail);
        assert!(block.contains("transactions: 1"));
        assert!(block.contains(&block_hash));
        assert!(block.contains("amount=25"));

        let account = render_account_detail(&explorer.account(&address("alice")).unwrap());
        assert!(account.contains("account xriqdev1alice00000000000"));
        assert!(account.contains("balance: 100"));
        assert!(account.contains("nonce: 1"));

        let accounts = render_accounts(&explorer.accounts(10));
        assert!(accounts.contains("accounts: 3"));
        assert!(accounts.contains("xriqdev1alice00000000000"));

        let account_transactions = render_account_transactions(
            &address("alice"),
            &explorer.account_transactions(&address("alice"), 2),
        );
        assert!(account_transactions.contains("account transactions xriqdev1alice00000000000"));
        assert!(account_transactions.contains("received"));
        assert!(account_transactions.contains("sent"));

        let latest_transactions = render_latest_transactions(&explorer.latest_transactions(2));
        assert!(latest_transactions.contains("latest transactions"));
        assert!(latest_transactions.contains("height 2"));
        assert!(latest_transactions.contains("amount=25"));

        let mempool = render_mempool(&explorer.mempool());
        assert!(mempool.contains("mempool pending: 2"));
        assert!(mempool.contains("fee=5"));
    }
}
