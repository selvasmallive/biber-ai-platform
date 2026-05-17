//! Minimal local node loop for the XRIQ private devnet.

use xriq_consensus::{BlockProductionError, BlockProductionInput, SingleAuthorityProducer};
use xriq_core::{
    Block, BlockValidationError, GenesisConfig, GenesisConfigError, Hash32, ParentHeaderView,
    SignatureBytes, Transaction, TransactionValidationContext, TransactionValidationError,
};
use xriq_crypto::{
    account_state_root, transaction_hash, transactions_root as canonical_transactions_root,
    SignatureVerificationError, TestOnlySignatureVerifier,
};
use xriq_ledger::{LedgerError, LedgerState};
use xriq_mempool::{Mempool, MempoolConfig, MempoolError};
use xriq_rpc::RpcService;
use xriq_storage::{ChainStore, StorageError, StoredBlock};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProduceNextBlockInput {
    pub block_hash: Hash32,
    pub state_root: Hash32,
    pub transactions_root: Hash32,
    pub timestamp_ms: u64,
    pub consensus_round: u64,
    pub signature: SignatureBytes,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProduceNextBlockCanonicalInput {
    pub state_root: Hash32,
    pub timestamp_ms: u64,
    pub consensus_round: u64,
    pub signature: SignatureBytes,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProduceNextBlockCanonicalRootsInput {
    pub timestamp_ms: u64,
    pub consensus_round: u64,
    pub signature: SignatureBytes,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ProduceNextBlockInnerInput {
    state_root_override: Option<Hash32>,
    transactions_root_override: Option<Hash32>,
    block_hash_override: Option<Hash32>,
    timestamp_ms: u64,
    consensus_round: u64,
    signature: SignatureBytes,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProducedBlock {
    pub block_hash: Hash32,
    pub block: Block,
    pub applied_transactions: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeError {
    Genesis(GenesisConfigError),
    MissingSender,
    Transaction(TransactionValidationError),
    TransactionSignature(SignatureVerificationError),
    Mempool(MempoolError),
    Ledger(LedgerError),
    Block(BlockProductionError),
    Header(BlockValidationError),
    UnauthorizedProducer,
    TooManyBlockTransactions { max: usize, actual: usize },
    WrongTransactionsRoot { expected: Hash32, actual: Hash32 },
    WrongStateRoot { expected: Hash32, actual: Hash32 },
    BlockSignature(SignatureVerificationError),
    Storage(StorageError),
    MissingStoredBlock { height: u64 },
    UnexpectedStoredBlockHeight { minimum: u64, actual: u64 },
    WrongStoredBlockHash { expected: Hash32, actual: Hash32 },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct XriqNode<S: ChainStore> {
    ledger: LedgerState,
    mempool: Mempool,
    producer: SingleAuthorityProducer,
    store: S,
    latest_block_hash: Hash32,
}

impl<S: ChainStore> XriqNode<S> {
    pub fn new(
        ledger: LedgerState,
        mempool: Mempool,
        producer: SingleAuthorityProducer,
        store: S,
        latest_block_hash: Hash32,
    ) -> Self {
        Self {
            ledger,
            mempool,
            producer,
            store,
            latest_block_hash,
        }
    }

    pub fn from_genesis(genesis: &GenesisConfig, store: S) -> Result<Self, GenesisConfigError> {
        genesis.validate()?;
        Ok(Self::new(
            LedgerState::from_genesis(genesis)?,
            Mempool::new(MempoolConfig::from_genesis(genesis)?),
            SingleAuthorityProducer::from_genesis(genesis)?,
            store,
            genesis.genesis_block_hash,
        ))
    }

    pub fn from_genesis_replaying_store(
        genesis: &GenesisConfig,
        store: S,
    ) -> Result<Self, NodeError> {
        let mut node = Self::from_genesis(genesis, store).map_err(NodeError::Genesis)?;
        let Some(latest_record) = node.store.latest_block() else {
            return Ok(node);
        };

        let minimum_height = genesis
            .initial_height
            .checked_add(1)
            .ok_or(NodeError::Header(BlockValidationError::HeightOverflow))?;
        let latest_height = latest_record.block.header.height;
        if latest_height < minimum_height {
            return Err(NodeError::UnexpectedStoredBlockHeight {
                minimum: minimum_height,
                actual: latest_height,
            });
        }

        let mut height = minimum_height;
        while height <= latest_height {
            let record = node
                .store
                .block_by_height(height)
                .cloned()
                .ok_or(NodeError::MissingStoredBlock { height })?;
            node.replay_stored_block(record)?;
            if height == latest_height {
                break;
            }
            height = height
                .checked_add(1)
                .ok_or(NodeError::Header(BlockValidationError::HeightOverflow))?;
        }

        Ok(node)
    }

    pub fn submit_transaction(
        &mut self,
        tx_hash: Hash32,
        tx: Transaction,
    ) -> Result<(), NodeError> {
        if self.mempool.contains(&tx_hash) {
            return Err(NodeError::Mempool(MempoolError::DuplicateTransaction));
        }

        let sender = self
            .ledger
            .account(&tx.from)
            .ok_or(NodeError::MissingSender)?;
        let context = TransactionValidationContext {
            chain_id: self.ledger.config().chain_id.clone(),
            sender: sender.view(),
            current_height: self.ledger.current_height(),
            min_fee: self.ledger.config().min_fee,
        };
        tx.validate_basic(&context)
            .map_err(NodeError::Transaction)?;
        TestOnlySignatureVerifier
            .verify_transaction(&tx)
            .map_err(NodeError::TransactionSignature)?;
        self.mempool
            .insert(tx_hash, tx)
            .map_err(NodeError::Mempool)?;
        Ok(())
    }

    pub fn submit_transaction_with_canonical_hash(
        &mut self,
        tx: Transaction,
    ) -> Result<Hash32, NodeError> {
        let tx_hash = transaction_hash(&tx);
        self.submit_transaction(tx_hash, tx)?;
        Ok(tx_hash)
    }

    pub fn produce_next_block(
        &mut self,
        input: ProduceNextBlockInput,
    ) -> Result<ProducedBlock, NodeError> {
        let ProduceNextBlockInput {
            block_hash,
            state_root,
            transactions_root,
            timestamp_ms,
            consensus_round,
            signature,
        } = input;

        self.produce_next_block_inner(ProduceNextBlockInnerInput {
            state_root_override: Some(state_root),
            transactions_root_override: Some(transactions_root),
            block_hash_override: Some(block_hash),
            timestamp_ms,
            consensus_round,
            signature,
        })
    }

    pub fn produce_next_block_with_canonical_hash(
        &mut self,
        input: ProduceNextBlockCanonicalInput,
    ) -> Result<ProducedBlock, NodeError> {
        self.produce_next_block_inner(ProduceNextBlockInnerInput {
            state_root_override: Some(input.state_root),
            transactions_root_override: None,
            block_hash_override: None,
            timestamp_ms: input.timestamp_ms,
            consensus_round: input.consensus_round,
            signature: input.signature,
        })
    }

    pub fn produce_next_block_with_canonical_roots(
        &mut self,
        input: ProduceNextBlockCanonicalRootsInput,
    ) -> Result<ProducedBlock, NodeError> {
        self.produce_next_block_inner(ProduceNextBlockInnerInput {
            state_root_override: None,
            transactions_root_override: None,
            block_hash_override: None,
            timestamp_ms: input.timestamp_ms,
            consensus_round: input.consensus_round,
            signature: input.signature,
        })
    }

    fn produce_next_block_inner(
        &mut self,
        input: ProduceNextBlockInnerInput,
    ) -> Result<ProducedBlock, NodeError> {
        let selected_transactions: Vec<(Hash32, Transaction)> = self
            .mempool
            .ordered_entries()
            .into_iter()
            .take(self.producer.config().max_transactions_per_block)
            .map(|entry| (entry.tx_hash, entry.tx.clone()))
            .collect();
        let transactions: Vec<Transaction> = selected_transactions
            .iter()
            .map(|(_, transaction)| transaction.clone())
            .collect();
        let transactions_root = input
            .transactions_root_override
            .unwrap_or_else(|| canonical_transactions_root(&transactions));

        let mut next_ledger = self.ledger.clone();
        for (_, transaction) in &selected_transactions {
            next_ledger
                .apply_transaction(transaction)
                .map_err(NodeError::Ledger)?;
        }
        let state_root = input
            .state_root_override
            .unwrap_or_else(|| account_state_root(&next_ledger.state_root_entries()));

        let parent = ParentHeaderView {
            chain_id: self.ledger.config().chain_id.clone(),
            height: self.ledger.current_height(),
            block_hash: self.latest_block_hash,
        };
        let block_input = BlockProductionInput {
            parent,
            state_root,
            transactions_root,
            timestamp_ms: input.timestamp_ms,
            consensus_round: input.consensus_round,
            signature: input.signature,
        };
        let block = self
            .producer
            .produce_block(block_input, transactions)
            .map_err(NodeError::Block)?;
        next_ledger.set_current_height(block.header.height);
        let block_hash = self.append_block_to_store(input.block_hash_override, block.clone())?;

        for (tx_hash, _) in &selected_transactions {
            self.mempool.remove(tx_hash);
        }
        self.ledger = next_ledger;
        self.latest_block_hash = block_hash;

        Ok(ProducedBlock {
            block_hash,
            block,
            applied_transactions: selected_transactions.len(),
        })
    }

    pub fn import_block(&mut self, block_hash: Hash32, block: Block) -> Result<(), NodeError> {
        self.import_block_inner(Some(block_hash), block).map(|_| ())
    }

    pub fn import_block_with_canonical_hash(&mut self, block: Block) -> Result<Hash32, NodeError> {
        self.import_block_inner(None, block)
    }

    fn import_block_inner(
        &mut self,
        block_hash_override: Option<Hash32>,
        block: Block,
    ) -> Result<Hash32, NodeError> {
        let next_ledger = self.validate_next_block_state(&block)?;
        let block_hash = self.append_block_to_store(block_hash_override, block.clone())?;

        self.remove_included_transactions(&block.transactions);
        self.ledger = next_ledger;
        self.latest_block_hash = block_hash;
        Ok(block_hash)
    }

    fn replay_stored_block(&mut self, record: StoredBlock) -> Result<(), NodeError> {
        let expected_hash = xriq_crypto::block_hash(&record.block);
        if record.block_hash != expected_hash {
            return Err(NodeError::WrongStoredBlockHash {
                expected: expected_hash,
                actual: record.block_hash,
            });
        }

        let next_ledger = self.validate_next_block_state(&record.block)?;
        self.ledger = next_ledger;
        self.latest_block_hash = record.block_hash;
        Ok(())
    }

    fn validate_next_block_state(&self, block: &Block) -> Result<LedgerState, NodeError> {
        let parent = self.parent_header_view();
        block
            .header
            .validate_against_parent(&parent)
            .map_err(NodeError::Header)?;
        if block.header.producer != self.producer.config().producer {
            return Err(NodeError::UnauthorizedProducer);
        }
        let max_transactions = self.producer.config().max_transactions_per_block;
        if block.transactions.len() > max_transactions {
            return Err(NodeError::TooManyBlockTransactions {
                max: max_transactions,
                actual: block.transactions.len(),
            });
        }
        for transaction in &block.transactions {
            TestOnlySignatureVerifier
                .verify_transaction(transaction)
                .map_err(NodeError::TransactionSignature)?;
        }
        let expected_transactions_root = canonical_transactions_root(&block.transactions);
        if block.header.transactions_root != expected_transactions_root {
            return Err(NodeError::WrongTransactionsRoot {
                expected: expected_transactions_root,
                actual: block.header.transactions_root,
            });
        }

        let mut next_ledger = self.ledger.clone();
        for transaction in &block.transactions {
            next_ledger
                .apply_transaction(transaction)
                .map_err(NodeError::Ledger)?;
        }
        let expected_state_root = account_state_root(&next_ledger.state_root_entries());
        if block.header.state_root != expected_state_root {
            return Err(NodeError::WrongStateRoot {
                expected: expected_state_root,
                actual: block.header.state_root,
            });
        }
        TestOnlySignatureVerifier
            .verify_block_header(&block.header)
            .map_err(NodeError::BlockSignature)?;
        next_ledger.set_current_height(block.header.height);
        Ok(next_ledger)
    }

    pub fn rpc_service(&self) -> RpcService {
        RpcService::new(
            self.ledger.clone(),
            self.mempool.clone(),
            self.latest_block_hash,
        )
    }

    pub fn ledger(&self) -> &LedgerState {
        &self.ledger
    }

    pub fn mempool(&self) -> &Mempool {
        &self.mempool
    }

    pub fn store(&self) -> &S {
        &self.store
    }

    pub fn latest_block_hash(&self) -> Hash32 {
        self.latest_block_hash
    }

    fn append_block_to_store(
        &mut self,
        block_hash_override: Option<Hash32>,
        block: Block,
    ) -> Result<Hash32, NodeError> {
        match block_hash_override {
            Some(block_hash) => {
                self.store
                    .append_block(block_hash, block)
                    .map_err(NodeError::Storage)?;
                Ok(block_hash)
            }
            None => self
                .store
                .append_block_with_canonical_hash(block)
                .map_err(NodeError::Storage),
        }
    }

    fn parent_header_view(&self) -> ParentHeaderView {
        ParentHeaderView {
            chain_id: self.ledger.config().chain_id.clone(),
            height: self.ledger.current_height(),
            block_hash: self.latest_block_hash,
        }
    }

    fn remove_included_transactions(&mut self, transactions: &[Transaction]) {
        let included_hashes: Vec<Hash32> = self
            .mempool
            .ordered_entries()
            .into_iter()
            .filter(|entry| transactions.contains(&entry.tx))
            .map(|entry| entry.tx_hash)
            .collect();
        for tx_hash in included_hashes {
            self.mempool.remove(&tx_hash);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        fs,
        path::PathBuf,
        time::{SystemTime, UNIX_EPOCH},
    };
    use xriq_core::{Address, BlockHeader, XriqAmount};
    use xriq_crypto::{
        block_header_signing_hash, test_only_signature_for_hash, transaction_signing_hash,
    };
    use xriq_storage::{FileChainStore, InMemoryChainStore};

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn hash(byte: u8) -> Hash32 {
        Hash32::from_bytes([byte; 32])
    }

    fn transaction(from: Address, nonce: u64, amount: u128, fee: u128) -> Transaction {
        let mut tx = Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from,
            to: address("bobbb"),
            amount: XriqAmount::from_base_units(amount),
            fee: XriqAmount::from_base_units(fee),
            nonce,
            memo_hash: None,
            expires_at_height: Some(100),
            signature: SignatureBytes::new(Vec::new()),
        };
        tx.signature = test_only_signature_for_hash(transaction_signing_hash(&tx));
        tx
    }

    fn produce_input(block_hash: Hash32) -> ProduceNextBlockInput {
        ProduceNextBlockInput {
            block_hash,
            state_root: hash(4),
            transactions_root: hash(5),
            timestamp_ms: 1_000,
            consensus_round: 0,
            signature: SignatureBytes::new(vec![9]),
        }
    }

    fn produce_canonical_input<S: ChainStore>(
        node: &XriqNode<S>,
    ) -> ProduceNextBlockCanonicalInput {
        let state_root = hash(4);
        let transactions_root = next_transactions_root(node);
        ProduceNextBlockCanonicalInput {
            state_root,
            timestamp_ms: 1_000,
            consensus_round: 0,
            signature: next_block_signature(node, state_root, transactions_root),
        }
    }

    fn produce_canonical_roots_input<S: ChainStore>(
        node: &XriqNode<S>,
    ) -> ProduceNextBlockCanonicalRootsInput {
        let (state_root, transactions_root) = next_canonical_roots(node);
        ProduceNextBlockCanonicalRootsInput {
            timestamp_ms: 1_000,
            consensus_round: 0,
            signature: next_block_signature(node, state_root, transactions_root),
        }
    }

    fn next_transactions<S: ChainStore>(node: &XriqNode<S>) -> Vec<Transaction> {
        node.mempool()
            .ordered_entries()
            .into_iter()
            .take(node.producer.config().max_transactions_per_block)
            .map(|entry| entry.tx.clone())
            .collect()
    }

    fn next_transactions_root<S: ChainStore>(node: &XriqNode<S>) -> Hash32 {
        xriq_crypto::transactions_root(&next_transactions(node))
    }

    fn next_canonical_roots<S: ChainStore>(node: &XriqNode<S>) -> (Hash32, Hash32) {
        let transactions = next_transactions(node);
        let mut next_ledger = node.ledger().clone();
        for transaction in &transactions {
            next_ledger.apply_transaction(transaction).unwrap();
        }
        (
            xriq_crypto::account_state_root(&next_ledger.state_root_entries()),
            xriq_crypto::transactions_root(&transactions),
        )
    }

    fn next_block_signature<S: ChainStore>(
        node: &XriqNode<S>,
        state_root: Hash32,
        transactions_root: Hash32,
    ) -> SignatureBytes {
        let header = BlockHeader {
            version: BlockHeader::SUPPORTED_VERSION,
            chain_id: node.ledger().config().chain_id.clone(),
            height: node.ledger().current_height() + 1,
            previous_block_hash: node.latest_block_hash(),
            state_root,
            transactions_root,
            timestamp_ms: 1_000,
            producer: node.producer.config().producer.clone(),
            consensus_round: 0,
            signature: SignatureBytes::new(Vec::new()),
        };
        test_only_signature_for_hash(block_header_signing_hash(&header))
    }

    fn genesis() -> GenesisConfig {
        GenesisConfig::private_devnet().with_account(
            address("alice"),
            XriqAmount::from_base_units(100),
            0,
        )
    }

    fn node() -> XriqNode<InMemoryChainStore> {
        let genesis = genesis();
        XriqNode::from_genesis(&genesis, InMemoryChainStore::new()).unwrap()
    }

    fn temp_store_path() -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("xriq-node-store-{nanos}.bin"))
    }

    #[test]
    fn builds_node_from_genesis_config() {
        let node = node();

        assert_eq!(node.ledger().config().chain_id, "xriq-devnet");
        assert_eq!(node.latest_block_hash(), Hash32::ZERO);
        assert_eq!(node.mempool().config().max_transactions, 8);
        assert_eq!(
            node.ledger().account(&address("alice")).unwrap().balance,
            XriqAmount::from_base_units(100)
        );
    }

    #[test]
    fn produces_block_applies_ledger_and_persists_block() {
        let mut node = node();
        let tx = transaction(address("alice"), 0, 25, 2);
        node.submit_transaction(hash(1), tx).unwrap();

        let produced = node.produce_next_block(produce_input(hash(8))).unwrap();

        assert_eq!(produced.block.header.height, 1);
        assert_eq!(produced.applied_transactions, 1);
        assert_eq!(node.latest_block_hash(), hash(8));
        assert_eq!(node.mempool().len(), 0);
        assert_eq!(node.ledger().current_height(), 1);
        assert_eq!(
            node.ledger().account(&address("alice")).unwrap().balance,
            XriqAmount::from_base_units(73)
        );
        assert_eq!(
            node.ledger().account(&address("bobbb")).unwrap().balance,
            XriqAmount::from_base_units(25)
        );
        assert_eq!(
            node.store().latest_block().map(|record| record.block_hash),
            Some(hash(8))
        );
        assert_eq!(node.rpc_service().chain_status().current_height, 1);
    }

    #[test]
    fn canonical_submit_uses_transaction_hash() {
        let mut node = node();
        let tx = transaction(address("alice"), 0, 25, 2);
        let tx_hash = xriq_crypto::transaction_hash(&tx);

        assert_eq!(node.submit_transaction_with_canonical_hash(tx), Ok(tx_hash));
        assert!(node.mempool().contains(&tx_hash));
    }

    #[test]
    fn canonical_block_production_persists_derived_block_hash() {
        let mut node = node();
        let tx = transaction(address("alice"), 0, 25, 2);
        node.submit_transaction_with_canonical_hash(tx).unwrap();

        let produced = node
            .produce_next_block_with_canonical_hash(produce_canonical_input(&node))
            .unwrap();

        assert_eq!(
            produced.block_hash,
            xriq_crypto::block_hash(&produced.block)
        );
        assert_eq!(
            produced.block.header.transactions_root,
            xriq_crypto::transactions_root(&produced.block.transactions)
        );
        assert_eq!(
            node.store().latest_block().map(|record| record.block_hash),
            Some(produced.block_hash)
        );
    }

    #[test]
    fn canonical_root_block_production_uses_derived_roots() {
        let mut node = node();
        let tx = transaction(address("alice"), 0, 25, 2);
        node.submit_transaction_with_canonical_hash(tx).unwrap();

        let produced = node
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&node))
            .unwrap();

        assert_eq!(
            produced.block.header.transactions_root,
            xriq_crypto::transactions_root(&produced.block.transactions)
        );
        assert_eq!(
            produced.block.header.state_root,
            xriq_crypto::account_state_root(&node.ledger().state_root_entries())
        );
        assert_eq!(
            produced.block_hash,
            xriq_crypto::block_hash(&produced.block)
        );
    }

    #[test]
    fn rejects_invalid_transaction_without_mutating_mempool() {
        let mut node = node();

        assert_eq!(
            node.submit_transaction(hash(1), transaction(address("alice"), 7, 25, 2)),
            Err(NodeError::Transaction(
                TransactionValidationError::InvalidNonce {
                    expected: 0,
                    actual: 7,
                }
            ))
        );
        assert_eq!(node.mempool().len(), 0);
    }

    #[test]
    fn rejects_bad_test_only_transaction_signature_without_mutating_mempool() {
        let mut node = node();
        let mut tx = transaction(address("alice"), 0, 25, 2);
        tx.signature = SignatureBytes::new(vec![9]);

        assert_eq!(
            node.submit_transaction_with_canonical_hash(tx),
            Err(NodeError::TransactionSignature(
                SignatureVerificationError::InvalidSignature
            ))
        );
        assert_eq!(node.mempool().len(), 0);
    }

    #[test]
    fn storage_failure_does_not_commit_node_state() {
        let mut node = node();
        node.submit_transaction(hash(1), transaction(address("alice"), 0, 25, 2))
            .unwrap();
        node.produce_next_block(produce_input(hash(8))).unwrap();

        let before_height = node.ledger().current_height();
        let before_latest = node.latest_block_hash();
        let result = node.produce_next_block(produce_input(hash(8)));

        assert_eq!(
            result,
            Err(NodeError::Storage(StorageError::DuplicateBlockHash))
        );
        assert_eq!(node.ledger().current_height(), before_height);
        assert_eq!(node.latest_block_hash(), before_latest);
    }

    #[test]
    fn can_produce_empty_block() {
        let mut node = node();

        let produced = node.produce_next_block(produce_input(hash(8))).unwrap();

        assert_eq!(produced.applied_transactions, 0);
        assert!(produced.block.transactions.is_empty());
        assert_eq!(node.ledger().current_height(), 1);
        assert_eq!(node.store().len(), 1);
    }

    #[test]
    fn imports_peer_block_updates_follower_state_and_storage() {
        let mut producer = node();
        let mut follower = node();
        let tx = transaction(address("alice"), 0, 25, 2);
        producer.submit_transaction(hash(1), tx.clone()).unwrap();
        follower.submit_transaction(hash(1), tx).unwrap();

        let produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();

        assert_eq!(
            follower.import_block(produced.block_hash, produced.block.clone()),
            Ok(())
        );
        assert_eq!(follower.latest_block_hash(), produced.block_hash);
        assert_eq!(follower.ledger().current_height(), 1);
        assert_eq!(follower.mempool().len(), 0);
        assert_eq!(follower.store().len(), 1);
        assert_eq!(
            follower
                .ledger()
                .account(&address("alice"))
                .unwrap()
                .balance,
            XriqAmount::from_base_units(73)
        );
        assert_eq!(producer.ledger(), follower.ledger());
    }

    #[test]
    fn canonical_import_uses_block_hash() {
        let mut producer = node();
        let mut follower = node();
        let produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();

        let imported_hash = follower
            .import_block_with_canonical_hash(produced.block.clone())
            .unwrap();

        assert_eq!(imported_hash, produced.block_hash);
        assert_eq!(imported_hash, xriq_crypto::block_hash(&produced.block));
        assert_eq!(follower.latest_block_hash(), produced.block_hash);
        assert_eq!(follower.store().len(), 1);
    }

    #[test]
    fn replays_persisted_file_store_into_node_state() {
        let path = temp_store_path();
        let genesis = genesis();
        let latest_hash;

        {
            let mut node =
                XriqNode::from_genesis(&genesis, FileChainStore::open(&path).unwrap()).unwrap();
            node.submit_transaction_with_canonical_hash(transaction(address("alice"), 0, 25, 2))
                .unwrap();
            node.produce_next_block_with_canonical_roots(produce_canonical_roots_input(&node))
                .unwrap();
            node.submit_transaction_with_canonical_hash(transaction(address("alice"), 1, 10, 2))
                .unwrap();
            let second = node
                .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&node))
                .unwrap();
            latest_hash = second.block_hash;
        }

        let store = FileChainStore::open(&path).unwrap();
        let reloaded = XriqNode::from_genesis_replaying_store(&genesis, store).unwrap();

        assert_eq!(reloaded.latest_block_hash(), latest_hash);
        assert_eq!(reloaded.ledger().current_height(), 2);
        assert_eq!(reloaded.store().len(), 2);
        assert_eq!(
            reloaded
                .ledger()
                .account(&address("alice"))
                .unwrap()
                .balance,
            XriqAmount::from_base_units(61)
        );
        assert_eq!(
            reloaded
                .ledger()
                .account(&address("bobbb"))
                .unwrap()
                .balance,
            XriqAmount::from_base_units(35)
        );
        assert_eq!(
            reloaded
                .ledger()
                .account(&GenesisConfig::private_devnet().fee_sink)
                .unwrap()
                .balance,
            XriqAmount::from_base_units(4)
        );

        let _ = fs::remove_file(path);
    }

    #[test]
    fn replay_rejects_noncanonical_stored_block_hash() {
        let genesis = genesis();
        let mut producer = XriqNode::from_genesis(&genesis, InMemoryChainStore::new()).unwrap();
        let produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        let wrong_hash = hash(99);
        let mut store = InMemoryChainStore::new();
        store
            .append_block(wrong_hash, produced.block.clone())
            .unwrap();

        assert_eq!(
            XriqNode::from_genesis_replaying_store(&genesis, store),
            Err(NodeError::WrongStoredBlockHash {
                expected: xriq_crypto::block_hash(&produced.block),
                actual: wrong_hash,
            })
        );
    }

    #[test]
    fn replay_rejects_height_gaps() {
        let genesis = genesis();
        let mut producer = XriqNode::from_genesis(&genesis, InMemoryChainStore::new()).unwrap();
        producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        let second = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        let mut store = InMemoryChainStore::new();
        store
            .append_block(second.block_hash, second.block.clone())
            .unwrap();

        assert_eq!(
            XriqNode::from_genesis_replaying_store(&genesis, store),
            Err(NodeError::MissingStoredBlock { height: 1 })
        );
    }

    #[test]
    fn imports_empty_peer_block_after_prior_import() {
        let mut producer = node();
        let mut follower = node();
        let first = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        follower
            .import_block(first.block_hash, first.block.clone())
            .unwrap();

        let second = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();

        assert_eq!(
            follower.import_block(second.block_hash, second.block),
            Ok(())
        );
        assert_eq!(follower.latest_block_hash(), second.block_hash);
        assert_eq!(follower.ledger().current_height(), 2);
        assert_eq!(follower.store().len(), 2);
    }

    #[test]
    fn rejects_peer_block_with_wrong_transaction_root_without_mutating_state() {
        let mut producer = node();
        let mut follower = node();
        let tx = transaction(address("alice"), 0, 25, 2);
        producer.submit_transaction_with_canonical_hash(tx).unwrap();
        let mut produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        produced.block.header.transactions_root = hash(99);
        let before_ledger = follower.ledger().clone();

        assert_eq!(
            follower.import_block(produced.block_hash, produced.block.clone()),
            Err(NodeError::WrongTransactionsRoot {
                expected: xriq_crypto::transactions_root(&produced.block.transactions),
                actual: hash(99),
            })
        );
        assert_eq!(follower.latest_block_hash(), hash(0));
        assert_eq!(follower.ledger(), &before_ledger);
        assert_eq!(follower.store().len(), 0);
    }

    #[test]
    fn rejects_peer_block_with_wrong_state_root_without_mutating_state() {
        let mut producer = node();
        let mut follower = node();
        let tx = transaction(address("alice"), 0, 25, 2);
        producer.submit_transaction_with_canonical_hash(tx).unwrap();
        let mut produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        produced.block.header.state_root = hash(99);
        let before_ledger = follower.ledger().clone();
        let mut expected_ledger = follower.ledger().clone();
        for transaction in &produced.block.transactions {
            expected_ledger.apply_transaction(transaction).unwrap();
        }

        assert_eq!(
            follower.import_block(produced.block_hash, produced.block),
            Err(NodeError::WrongStateRoot {
                expected: xriq_crypto::account_state_root(&expected_ledger.state_root_entries()),
                actual: hash(99),
            })
        );
        assert_eq!(follower.latest_block_hash(), hash(0));
        assert_eq!(follower.ledger(), &before_ledger);
        assert_eq!(follower.store().len(), 0);
    }

    #[test]
    fn rejects_peer_block_with_bad_test_only_signature_without_mutating_state() {
        let mut producer = node();
        let mut follower = node();
        let produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        let mut block = produced.block;
        block.header.signature = SignatureBytes::new(vec![1]);
        let before_ledger = follower.ledger().clone();

        assert_eq!(
            follower.import_block(produced.block_hash, block),
            Err(NodeError::BlockSignature(
                xriq_crypto::SignatureVerificationError::InvalidSignature
            ))
        );
        assert_eq!(follower.latest_block_hash(), hash(0));
        assert_eq!(follower.ledger(), &before_ledger);
        assert_eq!(follower.store().len(), 0);
    }

    #[test]
    fn rejects_peer_block_with_bad_transaction_signature_without_mutating_state() {
        let mut producer = node();
        let mut follower = node();
        let tx = transaction(address("alice"), 0, 25, 2);
        producer.submit_transaction_with_canonical_hash(tx).unwrap();
        let produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        let mut block = produced.block;
        block.transactions[0].signature = SignatureBytes::new(vec![1]);
        let before_ledger = follower.ledger().clone();

        assert_eq!(
            follower.import_block(produced.block_hash, block),
            Err(NodeError::TransactionSignature(
                SignatureVerificationError::InvalidSignature
            ))
        );
        assert_eq!(follower.latest_block_hash(), hash(0));
        assert_eq!(follower.ledger(), &before_ledger);
        assert_eq!(follower.store().len(), 0);
    }

    #[test]
    fn rejects_peer_block_with_wrong_parent_without_mutating_state() {
        let mut producer = node();
        let mut follower = node();
        let mut produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        produced.block.header.previous_block_hash = hash(99);
        let before_ledger = follower.ledger().clone();

        assert_eq!(
            follower.import_block(produced.block_hash, produced.block),
            Err(NodeError::Header(BlockValidationError::WrongPreviousHash))
        );
        assert_eq!(follower.latest_block_hash(), hash(0));
        assert_eq!(follower.ledger(), &before_ledger);
        assert_eq!(follower.store().len(), 0);
    }

    #[test]
    fn rejects_peer_block_from_unauthorized_producer() {
        let mut producer = node();
        let mut follower = node();
        let mut produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        produced.block.header.producer = address("intruder");

        assert_eq!(
            follower.import_block(produced.block_hash, produced.block),
            Err(NodeError::UnauthorizedProducer)
        );
        assert_eq!(follower.ledger().current_height(), 0);
        assert_eq!(follower.store().len(), 0);
    }

    #[test]
    fn rejects_peer_block_over_transaction_limit_without_mutating_state() {
        let mut follower = node();
        let mut producer = node();
        let transactions = vec![
            transaction(address("alice"), 0, 10, 2),
            transaction(address("carol"), 0, 10, 2),
            transaction(address("davee"), 0, 10, 2),
            transaction(address("erinn"), 0, 10, 2),
            transaction(address("frank"), 0, 10, 2),
        ];
        let mut produced = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        produced.block.transactions = transactions;
        let before_ledger = follower.ledger().clone();

        assert_eq!(
            follower.import_block(produced.block_hash, produced.block),
            Err(NodeError::TooManyBlockTransactions { max: 4, actual: 5 })
        );
        assert_eq!(follower.ledger(), &before_ledger);
        assert_eq!(follower.store().len(), 0);
    }
}
