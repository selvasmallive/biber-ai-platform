//! Local RPC endpoint behavior for the XRIQ private devnet.
//!
//! This crate intentionally avoids HTTP dependencies for now. It defines the
//! deterministic behavior that a later HTTP/JSON layer should expose.

use xriq_core::{
    Address, Hash32, Transaction, TransactionValidationContext, TransactionValidationError,
    XriqAmount,
};
use xriq_crypto::{
    account_state_root, transaction_hash, SignatureVerificationError, TestOnlySignatureVerifier,
};
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
    pub state_root: Hash32,
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
    TransactionSignature(SignatureVerificationError),
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
            state_root: account_state_root(&self.ledger.state_root_entries()),
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

    pub fn accounts(&self, limit: usize) -> Vec<AccountResponse> {
        self.ledger
            .accounts()
            .iter()
            .take(limit)
            .map(|(address, account)| AccountResponse {
                address: address.clone(),
                balance: account.balance,
                nonce: account.nonce,
            })
            .collect()
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
        TestOnlySignatureVerifier
            .verify_transaction(&tx)
            .map_err(RpcError::TransactionSignature)?;
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
    use xriq_crypto::{account_state_root, test_only_signature_for_hash, transaction_signing_hash};
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
            public_key: Vec::new(),
        };
        tx.signature = test_only_signature_for_hash(transaction_signing_hash(&tx));
        tx
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
                state_root: account_state_root(&service.ledger.state_root_entries()),
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
    fn lists_accounts_in_deterministic_order() {
        let accounts = service().accounts(10);

        assert_eq!(accounts.len(), 2);
        assert_eq!(accounts[0].address, address("alice"));
        assert_eq!(accounts[0].balance, XriqAmount::from_base_units(100));
        assert_eq!(accounts[1].address, fee_sink());
        assert_eq!(service().accounts(1).len(), 1);
        assert!(service().accounts(0).is_empty());
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
    fn rejects_bad_test_only_transaction_signature_without_mutating_mempool() {
        let mut service = service();
        let mut tx = transaction(address("alice"), 0, 25, 2);
        tx.signature = SignatureBytes::new(vec![9]);

        assert_eq!(
            service.submit_transaction_with_canonical_hash(tx),
            Err(RpcError::TransactionSignature(
                SignatureVerificationError::InvalidSignature
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

    // ---- Property tests: RPC response shaping ----
    //
    // RpcService shapes read responses from ledger + mempool state. Over randomized
    // states (seeded PRNG, reproducible) the shaped responses must faithfully mirror
    // that state — no invented, dropped, or reordered data — and `submit_transaction`
    // must be atomic with a pending_count that matches the post-state:
    //   * chain_status mirrors ledger height/chain_id/state_root + mempool count,
    //   * account/accounts mirror the ledger (accounts capped at limit, address order),
    //   * mempool()/transaction() mirror the mempool's ordered entries and membership,
    //   * a rejected submit leaves the mempool unchanged; an accepted one grows it by
    //     one and reports the new pending_count.

    struct RpcFuzzRng(u64);

    impl RpcFuzzRng {
        fn new(seed: u64) -> Self {
            RpcFuzzRng(seed | 1)
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

        fn byte(&mut self) -> u8 {
            self.next_u64() as u8
        }
    }

    const RPC_LABELS: [&str; 4] = ["alice", "bobbb", "carol", "davey"];
    // Includes labels that are never funded, so account-lookup probes hit both the
    // present and the absent branch.
    const RPC_PROBE_LABELS: [&str; 6] = ["alice", "bobbb", "carol", "davey", "eveee", "zzzzz"];

    fn random_service(rng: &mut RpcFuzzRng) -> RpcService {
        let mut ledger = LedgerState::new(LedgerConfig {
            chain_id: "xriq-devnet".to_string(),
            current_height: rng.below(50),
            min_fee: XriqAmount::from_base_units(2),
            fee_sink: fee_sink(),
        });
        for label in RPC_LABELS {
            if rng.below(2) == 0 {
                ledger.set_account(
                    address(label),
                    Account::new(
                        XriqAmount::from_base_units(1_000 + rng.below(1_000_000) as u128),
                        rng.below(20),
                    ),
                );
            }
        }
        let mut mempool = Mempool::new(MempoolConfig {
            max_transactions: 8,
            min_fee: XriqAmount::from_base_units(2),
        });
        // Insert distinct (from, nonce) transactions; their canonical hashes differ.
        let count = rng.below(7);
        for j in 0..count {
            let from = address(RPC_LABELS[(j % RPC_LABELS.len() as u64) as usize]);
            let tx = transaction(
                from,
                j,
                1 + rng.below(100) as u128,
                2 + rng.below(3) as u128,
            );
            let tx_hash = transaction_hash(&tx);
            let _ = mempool.insert(tx_hash, tx);
        }
        RpcService::new(ledger, mempool, hash(rng.byte()))
    }

    #[test]
    fn property_rpc_responses_mirror_state() {
        for i in 0..10_000u64 {
            let mut rng = RpcFuzzRng::new(0x8BC0_1234_5678_9ABC_u64.wrapping_add(i));
            let latest_hash = hash(rng.byte());
            let mut service = random_service(&mut rng);
            service.set_latest_block_hash(latest_hash);

            // chain_status mirrors ledger + mempool.
            let status = service.chain_status();
            assert_eq!(
                status.chain_id,
                service.ledger().config().chain_id,
                "chain_id at {i}"
            );
            assert_eq!(
                status.current_height,
                service.ledger().current_height(),
                "height at {i}"
            );
            assert_eq!(status.latest_block_hash, latest_hash, "tip at {i}");
            assert_eq!(
                status.state_root,
                account_state_root(&service.ledger().state_root_entries()),
                "state_root at {i}"
            );
            assert_eq!(
                status.pending_transactions,
                service.mempool_state().len(),
                "pending count at {i}"
            );

            // account(): Ok iff the ledger holds it, with mirrored balance/nonce.
            for label in RPC_PROBE_LABELS {
                let probe = address(label);
                match (service.account(&probe), service.ledger().account(&probe)) {
                    (Ok(resp), Some(account)) => {
                        assert_eq!(resp.address, probe);
                        assert_eq!(resp.balance, account.balance);
                        assert_eq!(resp.nonce, account.nonce);
                    }
                    (Err(RpcError::AccountNotFound), None) => {}
                    other => panic!("account shaping disagreed at seed {i}: {other:?}"),
                }
            }

            // accounts(limit): the first `limit` ledger accounts in address order.
            let full: Vec<(Address, Account)> = service
                .ledger()
                .accounts()
                .iter()
                .map(|(address, account)| (address.clone(), *account))
                .collect();
            for &limit in &[0usize, 1, full.len(), full.len() + 3] {
                let shaped = service.accounts(limit);
                assert_eq!(shaped.len(), limit.min(full.len()), "accounts len at {i}");
                for (resp, (address, account)) in shaped.iter().zip(full.iter()) {
                    assert_eq!(&resp.address, address);
                    assert_eq!(resp.balance, account.balance);
                    assert_eq!(resp.nonce, account.nonce);
                }
            }

            // mempool(): count + ordered hashes mirror the mempool exactly.
            let mempool_response = service.mempool();
            let expected_hashes: Vec<Hash32> = service
                .mempool_state()
                .ordered_entries()
                .iter()
                .map(|entry| entry.tx_hash)
                .collect();
            assert_eq!(
                mempool_response.pending_count,
                service.mempool_state().len()
            );
            assert_eq!(
                mempool_response.ordered_transaction_hashes, expected_hashes,
                "order at {i}"
            );

            // transaction(): Some iff resident, with mirrored body.
            for entry in service.mempool_state().ordered_entries() {
                let resp = service
                    .transaction(&entry.tx_hash)
                    .expect("resident tx shaped");
                assert_eq!(resp.tx_hash, entry.tx_hash);
                assert_eq!(resp.transaction, entry.tx);
                assert!(matches!(resp.status, TransactionStatus::Pending));
            }
            let probe_hash = hash(rng.byte());
            assert_eq!(
                service.transaction(&probe_hash).is_some(),
                service.mempool_state().contains(&probe_hash),
                "tx membership at {i}"
            );
        }
    }

    #[test]
    fn property_rpc_submit_is_atomic_and_reports_pending_count() {
        for i in 0..10_000u64 {
            let mut rng = RpcFuzzRng::new(0x5A8B_1234_5678_9ABC_u64.wrapping_add(i));
            let mut service = random_service(&mut rng);

            // Build a transaction that is sometimes valid for a funded sender and
            // sometimes deliberately malformed, to exercise both submit branches.
            let tx = if rng.below(2) == 0 {
                let from = address(RPC_LABELS[rng.below(RPC_LABELS.len() as u64) as usize]);
                let nonce = service
                    .ledger()
                    .account(&from)
                    .map(|a| a.nonce)
                    .unwrap_or(0);
                transaction(
                    from,
                    nonce,
                    1 + rng.below(100) as u128,
                    2 + rng.below(3) as u128,
                )
            } else {
                let from =
                    address(RPC_PROBE_LABELS[rng.below(RPC_PROBE_LABELS.len() as u64) as usize]);
                transaction(
                    from,
                    rng.below(30),
                    rng.below(3) as u128,
                    rng.below(3) as u128,
                )
            };
            let tx_hash = transaction_hash(&tx);

            let before_len = service.mempool_state().len();
            let before_contains = service.mempool_state().contains(&tx_hash);

            match service.submit_transaction(tx_hash, tx) {
                Ok(response) => {
                    assert!(response.accepted, "not accepted at seed {i}");
                    assert_eq!(response.tx_hash, tx_hash, "hash at seed {i}");
                    assert_eq!(
                        service.mempool_state().len(),
                        before_len + 1,
                        "grew by !=1 at {i}"
                    );
                    assert!(
                        service.mempool_state().contains(&tx_hash),
                        "missing after accept at {i}"
                    );
                    assert_eq!(
                        response.pending_count,
                        service.mempool_state().len(),
                        "pending_count at {i}"
                    );
                }
                Err(_) => {
                    // A rejected submit must not mutate the mempool.
                    assert_eq!(
                        service.mempool_state().len(),
                        before_len,
                        "len changed on reject at {i}"
                    );
                    assert_eq!(
                        service.mempool_state().contains(&tx_hash),
                        before_contains,
                        "membership changed on reject at {i}"
                    );
                }
            }
        }
    }
}
