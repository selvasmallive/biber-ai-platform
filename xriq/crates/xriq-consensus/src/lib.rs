//! Deterministic single-authority block production for the XRIQ private devnet.

use xriq_core::{
    Address, Block, BlockHeader, Hash32, ParentHeaderView, SignatureBytes, Transaction,
};
use xriq_mempool::Mempool;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SingleAuthorityConfig {
    pub chain_id: String,
    pub producer: Address,
    pub max_transactions_per_block: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BlockProductionInput {
    pub parent: ParentHeaderView,
    pub state_root: Hash32,
    pub transactions_root: Hash32,
    pub timestamp_ms: u64,
    pub consensus_round: u64,
    pub signature: SignatureBytes,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BlockProductionError {
    WrongParentChain,
    HeightOverflow,
    MissingSignature,
    TooManyTransactions { max: usize, actual: usize },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SingleAuthorityProducer {
    config: SingleAuthorityConfig,
}

impl SingleAuthorityProducer {
    pub fn new(config: SingleAuthorityConfig) -> Self {
        Self { config }
    }

    pub fn config(&self) -> &SingleAuthorityConfig {
        &self.config
    }

    pub fn produce_block(
        &self,
        input: BlockProductionInput,
        transactions: Vec<Transaction>,
    ) -> Result<Block, BlockProductionError> {
        if input.parent.chain_id != self.config.chain_id {
            return Err(BlockProductionError::WrongParentChain);
        }
        if input.signature.is_empty() {
            return Err(BlockProductionError::MissingSignature);
        }
        if transactions.len() > self.config.max_transactions_per_block {
            return Err(BlockProductionError::TooManyTransactions {
                max: self.config.max_transactions_per_block,
                actual: transactions.len(),
            });
        }

        let height = input
            .parent
            .height
            .checked_add(1)
            .ok_or(BlockProductionError::HeightOverflow)?;
        let header = BlockHeader {
            version: BlockHeader::SUPPORTED_VERSION,
            chain_id: self.config.chain_id.clone(),
            height,
            previous_block_hash: input.parent.block_hash,
            state_root: input.state_root,
            transactions_root: input.transactions_root,
            timestamp_ms: input.timestamp_ms,
            producer: self.config.producer.clone(),
            consensus_round: input.consensus_round,
            signature: input.signature,
        };

        Ok(Block {
            header,
            transactions,
        })
    }

    pub fn produce_block_from_mempool(
        &self,
        input: BlockProductionInput,
        mempool: &Mempool,
    ) -> Result<Block, BlockProductionError> {
        let transactions = mempool
            .ordered_entries()
            .into_iter()
            .take(self.config.max_transactions_per_block)
            .map(|entry| entry.tx.clone())
            .collect();
        self.produce_block(input, transactions)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_core::{SignatureBytes, XriqAmount};
    use xriq_mempool::{MempoolConfig, MempoolError};

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn hash(byte: u8) -> Hash32 {
        Hash32::from_bytes([byte; 32])
    }

    fn producer() -> SingleAuthorityProducer {
        SingleAuthorityProducer::new(SingleAuthorityConfig {
            chain_id: "xriq-devnet".to_string(),
            producer: address("author"),
            max_transactions_per_block: 2,
        })
    }

    fn input() -> BlockProductionInput {
        BlockProductionInput {
            parent: ParentHeaderView {
                chain_id: "xriq-devnet".to_string(),
                height: 41,
                block_hash: hash(9),
            },
            state_root: hash(1),
            transactions_root: hash(2),
            timestamp_ms: 1_000,
            consensus_round: 0,
            signature: SignatureBytes::new(vec![7, 8, 9]),
        }
    }

    fn tx(from: Address, nonce: u64, fee: u128) -> Transaction {
        Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from,
            to: address("bobbb"),
            amount: XriqAmount::from_base_units(10),
            fee: XriqAmount::from_base_units(fee),
            nonce,
            memo_hash: None,
            expires_at_height: Some(100),
            signature: SignatureBytes::new(vec![1, 2, 3]),
        }
    }

    #[test]
    fn produces_child_block_from_parent() {
        let block = producer().produce_block(input(), vec![]).unwrap();

        assert_eq!(block.header.version, BlockHeader::SUPPORTED_VERSION);
        assert_eq!(block.header.chain_id, "xriq-devnet");
        assert_eq!(block.header.height, 42);
        assert_eq!(block.header.previous_block_hash, hash(9));
        assert_eq!(block.header.state_root, hash(1));
        assert_eq!(block.header.transactions_root, hash(2));
        assert_eq!(block.header.producer, address("author"));
        assert_eq!(block.transactions, vec![]);
    }

    #[test]
    fn rejects_wrong_parent_chain() {
        let mut input = input();
        input.parent.chain_id = "other-chain".to_string();

        assert_eq!(
            producer().produce_block(input, vec![]),
            Err(BlockProductionError::WrongParentChain)
        );
    }

    #[test]
    fn rejects_parent_height_overflow() {
        let mut input = input();
        input.parent.height = u64::MAX;

        assert_eq!(
            producer().produce_block(input, vec![]),
            Err(BlockProductionError::HeightOverflow)
        );
    }

    #[test]
    fn rejects_missing_block_signature() {
        let mut input = input();
        input.signature = SignatureBytes::new(vec![]);

        assert_eq!(
            producer().produce_block(input, vec![]),
            Err(BlockProductionError::MissingSignature)
        );
    }

    #[test]
    fn rejects_too_many_transactions() {
        let transactions = vec![
            tx(address("alice"), 0, 2),
            tx(address("carol"), 0, 2),
            tx(address("davee"), 0, 2),
        ];

        assert_eq!(
            producer().produce_block(input(), transactions),
            Err(BlockProductionError::TooManyTransactions { max: 2, actual: 3 })
        );
    }

    #[test]
    fn selects_mempool_transactions_in_deterministic_order() {
        let mut mempool = Mempool::new(MempoolConfig {
            max_transactions: 4,
            min_fee: XriqAmount::from_base_units(2),
        });
        assert_eq!(mempool.insert(hash(3), tx(address("alice"), 0, 2)), Ok(()));
        assert_eq!(mempool.insert(hash(1), tx(address("carol"), 0, 5)), Ok(()));
        assert_eq!(mempool.insert(hash(2), tx(address("davee"), 0, 5)), Ok(()));

        let block = producer()
            .produce_block_from_mempool(input(), &mempool)
            .unwrap();
        let senders: Vec<Address> = block
            .transactions
            .iter()
            .map(|transaction| transaction.from.clone())
            .collect();

        assert_eq!(senders, vec![address("carol"), address("davee")]);
    }

    #[test]
    fn ignores_rejected_mempool_transactions_before_block_production() {
        let mut mempool = Mempool::new(MempoolConfig {
            max_transactions: 4,
            min_fee: XriqAmount::from_base_units(2),
        });

        assert_eq!(
            mempool.insert(hash(1), tx(address("alice"), 0, 1)),
            Err(MempoolError::FeeTooLow)
        );

        let block = producer()
            .produce_block_from_mempool(input(), &mempool)
            .unwrap();
        assert!(block.transactions.is_empty());
    }
}
