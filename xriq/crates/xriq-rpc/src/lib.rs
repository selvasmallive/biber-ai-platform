//! Local RPC endpoint behavior for the XRIQ private devnet.
//!
//! This crate intentionally avoids HTTP dependencies for now. It defines the
//! deterministic behavior that a later HTTP/JSON layer should expose.

use xriq_core::{
    Address, Hash32, Transaction, TransactionValidationContext, TransactionValidationError,
    XriqAmount,
};
use xriq_crypto::transaction_hash;
use xriq_ledger::LedgerState;
use xriq_mempool::{Mempool, MempoolError};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct HealthResponse {
    pub status: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChainStatusResponse {
    pub chain_id: String,
    pub current_height: u64,
    pub latest_block_hash: Hash32,
    pub pending_transactions: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountResponse {
    pub address: Address,
    pub balance: XriqAmount,
    pub nonce: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MempoolResponse {
    pub pending_count: usize,
    pub ordered_transaction_hashes: Vec<Hash32>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TransactionStatus {
    Pending,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionResponse {
    pub tx_hash: Hash32,
    pub status: TransactionStatus,
    pub transaction: Transaction,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SubmitTransactionResponse {
    pub tx_hash: Hash32,
    pub accepted: bool,
    pub pending_count: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RpcError {
    AccountNotFound,
    Transaction(TransactionValidationError),
    Mempool(MempoolError),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RpcService {
    ledger: LedgerState,
    mempool: Mempool,
    latest_block_hash: Hash32,
}

impl RpcService {
    pub fn new(ledger: LedgerState, mempool: Mempool, latest_block_hash: Hash32) -> Self {
        Self {
            ledger,
            mempool,
            latest_block_hash,
        }
    }

    pub const fn health(&self) -> HealthResponse {
        HealthResponse { status: "ok" }
    }

    pub fn chain_status(&self) -> ChainStatusResponse {
        ChainStatusResponse {
            chain_id: self.ledger.config().chain_id.clone(),
            current_height: self.ledger.current_height(),
            latest_block_hash: self.latest_block_hash,
            pending_transactions: self.mempool.len(),
        }
    }

    pub fn account(&self, address: &Address) -> Result<AccountResponse, RpcError> {
        let account = self
            .ledger
            .account(address)
            .ok_or(RpcError::AccountNotFound)?;
        Ok(AccountResponse {
            address: address.clone(),
            balance: account.balance,
            nonce: account.nonce,
        })
    }

    pub fn mempool(&self) -> MempoolResponse {
        let ordered_transaction_hashes = self
            .mempool
            .ordered_entries()
            .into_iter()
            .map(|entry| entry.tx_hash)
            .collect();
        MempoolResponse {
            pending_count: self.mempool.len(),
            ordered_transaction_hashes,
        }
    }

    pub fn transaction(&self, tx_hash: &Hash32) -> Option<TransactionResponse> {
        self.mempool
            .entry(tx_hash)
            .map(|entry| TransactionResponse {
                tx_hash: entry.tx_hash,
                status: TransactionStatus::Pending,
                transaction: entry.tx.clone(),
            })
    }

    pub fn submit_transaction(
        &mut self,
        tx_hash: Hash32,
        tx: Transaction,
    ) -> Result<SubmitTransactionResponse, RpcError> {
        if self.mempool.contains(&tx_hash) {
            return Err(RpcError::Mempool(MempoolError::DuplicateTransaction));
        }

        let sender = self
            .ledger
            .account(&tx.from)
            .ok_or(RpcError::AccountNotFound)?;
        let context = TransactionValidationContext {
            chain_id: self.ledger.config().chain_id.clone(),
            sender: sender.view(),
            current_height: self.ledger.current_height(),
            min_fee: self.ledger.config().min_fee,
        };
        tx.validate_basic(&context).map_err(RpcError::Transaction)?;
        self.mempool
            .insert(tx_hash, tx)
            .map_err(RpcError::Mempool)?;

        Ok(SubmitTransactionResponse {
            tx_hash,
            accepted: true,
            pending_count: self.mempool.len(),
        })
    }

    pub fn submit_transaction_with_canonical_hash(
        &mut self,
        tx: Transaction,
    ) -> Result<SubmitTransactionResponse, RpcError> {
        let tx_hash = transaction_hash(&tx);
        self.submit_transaction(tx_hash, tx)
    }

    pub fn ledger(&self) -> &LedgerState {
        &self.ledger
    }

    pub fn mempool_state(&self) -> &Mempool {
        &self.mempool
    }

    pub fn set_latest_block_hash(&mut self, latest_block_hash: Hash32) {
        self.latest_block_hash = latest_block_hash;
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_core::SignatureBytes;
    use xriq_ledger::{Account, LedgerConfig};
    use xriq_mempool::MempoolConfig;

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

    fn service() -> RpcService {
        let mut ledger = LedgerState::new(LedgerConfig {
            chain_id: "xriq-devnet".to_string(),
            current_height: 10,
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
        RpcService::new(ledger, mempool, hash(9))
    }

    #[test]
    fn reports_health_and_chain_status() {
        let service = service();

        assert_eq!(service.health(), HealthResponse { status: "ok" });
        assert_eq!(
            service.chain_status(),
            ChainStatusResponse {
                chain_id: "xriq-devnet".to_string(),
                current_height: 10,
                latest_block_hash: hash(9),
                pending_transactions: 0,
            }
        );
    }

    #[test]
    fn returns_account_balance_and_nonce() {
        assert_eq!(
            service().account(&address("alice")),
            Ok(AccountResponse {
                address: address("alice"),
                balance: XriqAmount::from_base_units(100),
                nonce: 0,
            })
        );
    }

    #[test]
    fn rejects_missing_account_lookup() {
        assert_eq!(
            service().account(&address("carol")),
            Err(RpcError::AccountNotFound)
        );
    }

    #[test]
    fn accepts_valid_transaction_into_mempool() {
        let mut service = service();
        let tx_hash = hash(1);
        let tx = transaction(address("alice"), 0, 25, 2);

        assert_eq!(
            service.submit_transaction(tx_hash, tx.clone()),
            Ok(SubmitTransactionResponse {
                tx_hash,
                accepted: true,
                pending_count: 1,
            })
        );
        assert_eq!(
            service.mempool(),
            MempoolResponse {
                pending_count: 1,
                ordered_transaction_hashes: vec![tx_hash],
            }
        );
        assert_eq!(
            service.transaction(&tx_hash),
            Some(TransactionResponse {
                tx_hash,
                status: TransactionStatus::Pending,
                transaction: tx,
            })
        );
    }

    #[test]
    fn accepts_valid_transaction_with_canonical_hash() {
        let mut service = service();
        let tx = transaction(address("alice"), 0, 25, 2);
        let tx_hash = transaction_hash(&tx);

        assert_eq!(
            service.submit_transaction_with_canonical_hash(tx.clone()),
            Ok(SubmitTransactionResponse {
                tx_hash,
                accepted: true,
                pending_count: 1,
            })
        );
        assert_eq!(
            service.transaction(&tx_hash),
            Some(TransactionResponse {
                tx_hash,
                status: TransactionStatus::Pending,
                transaction: tx,
            })
        );
    }

    #[test]
    fn rejects_transaction_with_bad_nonce_without_mutating_mempool() {
        let mut service = service();

        assert_eq!(
            service.submit_transaction(hash(1), transaction(address("alice"), 7, 25, 2)),
            Err(RpcError::Transaction(
                TransactionValidationError::InvalidNonce {
                    expected: 0,
                    actual: 7,
                }
            ))
        );
        assert_eq!(service.mempool().pending_count, 0);
    }

    #[test]
    fn rejects_duplicate_canonical_transaction_hash() {
        let mut service = service();
        let tx = transaction(address("alice"), 0, 25, 2);
        service
            .submit_transaction_with_canonical_hash(tx.clone())
            .unwrap();

        assert_eq!(
            service.submit_transaction_with_canonical_hash(tx),
            Err(RpcError::Mempool(MempoolError::DuplicateTransaction))
        );
    }

    #[test]
    fn rejects_duplicate_transaction_hash() {
        let mut service = service();
        let tx_hash = hash(1);
        service
            .submit_transaction(tx_hash, transaction(address("alice"), 0, 25, 2))
            .unwrap();

        assert_eq!(
            service.submit_transaction(tx_hash, transaction(address("alice"), 0, 25, 2)),
            Err(RpcError::Mempool(MempoolError::DuplicateTransaction))
        );
    }
}
