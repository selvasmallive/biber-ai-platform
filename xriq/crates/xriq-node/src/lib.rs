//! Minimal local node loop for the XRIQ private devnet.

use xriq_consensus::{BlockProductionError, BlockProductionInput, SingleAuthorityProducer};
use xriq_core::{
    Block, Hash32, ParentHeaderView, SignatureBytes, Transaction, TransactionValidationContext,
    TransactionValidationError,
};
use xriq_ledger::{LedgerError, LedgerState};
use xriq_mempool::{Mempool, MempoolError};
use xriq_rpc::RpcService;
use xriq_storage::{ChainStore, StorageError};

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
pub struct ProducedBlock {
    pub block_hash: Hash32,
    pub block: Block,
    pub applied_transactions: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeError {
    MissingSender,
    Transaction(TransactionValidationError),
    Mempool(MempoolError),
    Ledger(LedgerError),
    Block(BlockProductionError),
    Storage(StorageError),
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
        self.mempool
            .insert(tx_hash, tx)
            .map_err(NodeError::Mempool)?;
        Ok(())
    }

    pub fn produce_next_block(
        &mut self,
        input: ProduceNextBlockInput,
    ) -> Result<ProducedBlock, NodeError> {
        let selected_transactions: Vec<(Hash32, Transaction)> = self
            .mempool
            .ordered_entries()
            .into_iter()
            .take(self.producer.config().max_transactions_per_block)
            .map(|entry| (entry.tx_hash, entry.tx.clone()))
            .collect();

        let mut next_ledger = self.ledger.clone();
        for (_, transaction) in &selected_transactions {
            next_ledger
                .apply_transaction(transaction)
                .map_err(NodeError::Ledger)?;
        }

        let parent = ParentHeaderView {
            chain_id: self.ledger.config().chain_id.clone(),
            height: self.ledger.current_height(),
            block_hash: self.latest_block_hash,
        };
        let block_input = BlockProductionInput {
            parent,
            state_root: input.state_root,
            transactions_root: input.transactions_root,
            timestamp_ms: input.timestamp_ms,
            consensus_round: input.consensus_round,
            signature: input.signature,
        };
        let transactions = selected_transactions
            .iter()
            .map(|(_, transaction)| transaction.clone())
            .collect();
        let block = self
            .producer
            .produce_block(block_input, transactions)
            .map_err(NodeError::Block)?;
        next_ledger.set_current_height(block.header.height);
        self.store
            .append_block(input.block_hash, block.clone())
            .map_err(NodeError::Storage)?;

        for (tx_hash, _) in &selected_transactions {
            self.mempool.remove(tx_hash);
        }
        self.ledger = next_ledger;
        self.latest_block_hash = input.block_hash;

        Ok(ProducedBlock {
            block_hash: input.block_hash,
            block,
            applied_transactions: selected_transactions.len(),
        })
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
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_consensus::SingleAuthorityConfig;
    use xriq_core::{Address, XriqAmount};
    use xriq_ledger::{Account, LedgerConfig};
    use xriq_mempool::MempoolConfig;
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

    fn node() -> XriqNode<InMemoryChainStore> {
        let mut ledger = LedgerState::new(LedgerConfig {
            chain_id: "xriq-devnet".to_string(),
            current_height: 0,
            min_fee: XriqAmount::from_base_units(2),
            fee_sink: fee_sink(),
        });
        ledger.set_account(
            address("alice"),
            Account::new(XriqAmount::from_base_units(100), 0),
        );
        let mempool = Mempool::new(MempoolConfig {
            max_transactions: 8,
            min_fee: XriqAmount::from_base_units(2),
        });
        let producer = SingleAuthorityProducer::new(SingleAuthorityConfig {
            chain_id: "xriq-devnet".to_string(),
            producer: address("author"),
            max_transactions_per_block: 4,
        });
        XriqNode::new(
            ledger,
            mempool,
            producer,
            InMemoryChainStore::new(),
            hash(0),
        )
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
}
