//! Product-facing API service boundary for the XRIQ private devnet.
//!
//! This crate intentionally does not start an HTTP server yet. It defines the
//! stable response models and read-only behavior that a later local HTTP layer
//! can expose for explorer, account-history, and admin views.

use std::collections::BTreeMap;

use xriq_indexer::{
    IndexedAccount, IndexedAccountBalance, IndexedAccountTransaction, IndexedBlock,
    IndexedChainSnapshot, IndexedTransaction,
};

pub const API_ENVIRONMENT: &str = "private-devnet";
pub const API_SERVICE: &str = "xriq-api";
pub const API_VERSION: &str = "phase1.1-dev";
pub const INDEXER_SERVICE: &str = "xriq-indexer";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct XriqApiService {
    snapshot: IndexedChainSnapshot,
}

impl XriqApiService {
    pub fn new(snapshot: IndexedChainSnapshot) -> Self {
        Self { snapshot }
    }

    pub fn health(&self) -> HealthResponse {
        HealthResponse {
            ok: true,
            network: self.snapshot.chain_id.clone(),
            environment: API_ENVIRONMENT,
            service: API_SERVICE,
            version: API_VERSION,
        }
    }

    pub fn version(&self) -> VersionResponse {
        VersionResponse {
            environment: API_ENVIRONMENT,
            service: API_SERVICE,
            version: API_VERSION,
            indexer_version: "xriq-indexer-0.1.0",
        }
    }

    pub fn network(&self) -> NetworkResponse {
        NetworkResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            current_height: self.snapshot.current_height,
            latest_block_hash: self.snapshot.latest_block_hash.clone(),
            state_root: self.snapshot.state_root.clone(),
        }
    }

    pub fn explorer_overview(&self) -> ExplorerOverviewResponse {
        ExplorerOverviewResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            chain: ChainSummaryResponse {
                current_height: self.snapshot.current_height,
                latest_block_hash: self.snapshot.latest_block_hash.clone(),
                state_root: self.snapshot.state_root.clone(),
                stored_blocks: self.snapshot.read_model.blocks.len(),
                pending_transactions: 0,
            },
            indexer: self.admin_indexer_status(),
            totals: TotalsResponse {
                blocks: self.snapshot.read_model.blocks.len(),
                transactions: self.snapshot.read_model.transactions.len(),
                accounts: self.snapshot.read_model.account_balances.len(),
            },
        }
    }

    pub fn blocks(&self, limit: usize) -> BlockListResponse {
        let blocks = self
            .snapshot
            .read_model
            .blocks
            .values()
            .rev()
            .take(limit)
            .map(block_response)
            .collect::<Vec<_>>();
        let next_cursor = list_next_cursor(
            self.snapshot.read_model.blocks.len(),
            blocks.len(),
            blocks.last().map(|block| block.height.to_string()),
        );

        BlockListResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            limit,
            next_cursor,
            blocks,
        }
    }

    pub fn block(&self, height_or_hash: &str) -> Result<BlockDetailResponse, ApiError> {
        let block = if let Ok(height) = height_or_hash.parse::<u64>() {
            self.snapshot.read_model.blocks.get(&height)
        } else {
            self.snapshot
                .read_model
                .blocks
                .values()
                .find(|block| block.block_hash == height_or_hash)
        }
        .ok_or(ApiError::BlockNotFound)?;

        Ok(BlockDetailResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            height: block.height,
            block_hash: block.block_hash.clone(),
            previous_block_hash: block.previous_block_hash.clone(),
            state_root: block.state_root.clone(),
            transactions_root: block.transactions_root.clone(),
            transaction_count: block.transaction_count,
            timestamp_utc: timestamp_ms_to_utc(block.timestamp_ms),
            transactions: transactions_for_block(&self.snapshot.read_model.transactions, block),
        })
    }

    pub fn transactions(&self, limit: usize) -> TransactionListResponse {
        let mut transactions = self
            .snapshot
            .read_model
            .transactions
            .values()
            .map(transaction_response)
            .collect::<Vec<_>>();
        transactions.sort_by(|left, right| {
            right
                .block_height
                .cmp(&left.block_height)
                .then_with(|| right.transaction_index.cmp(&left.transaction_index))
                .then_with(|| left.tx_hash.cmp(&right.tx_hash))
        });
        let total = transactions.len();
        transactions.truncate(limit);
        let next_cursor = list_next_cursor(
            total,
            transactions.len(),
            transactions.last().map(|transaction| {
                format!(
                    "{}:{}",
                    transaction.block_height, transaction.transaction_index
                )
            }),
        );

        TransactionListResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            limit,
            next_cursor,
            transactions,
        }
    }

    pub fn transaction(&self, tx_hash: &str) -> Result<TransactionResponse, ApiError> {
        self.snapshot
            .read_model
            .transactions
            .get(tx_hash)
            .map(transaction_response)
            .ok_or(ApiError::TransactionNotFound)
    }

    pub fn accounts(&self, limit: usize) -> AccountListResponse {
        let accounts = self
            .snapshot
            .read_model
            .account_balances
            .values()
            .take(limit)
            .map(|balance| account_response(&self.snapshot.read_model.accounts, balance))
            .collect::<Vec<_>>();
        let next_cursor = list_next_cursor(
            self.snapshot.read_model.account_balances.len(),
            accounts.len(),
            accounts.last().map(|account| account.address.clone()),
        );

        AccountListResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            limit,
            next_cursor,
            accounts,
        }
    }

    pub fn account(&self, address: &str) -> Result<AccountResponse, ApiError> {
        self.snapshot
            .read_model
            .account_balances
            .get(address)
            .map(|balance| account_response(&self.snapshot.read_model.accounts, balance))
            .ok_or(ApiError::AccountNotFound)
    }

    pub fn account_transactions(&self, address: &str, limit: usize) -> AccountHistoryResponse {
        let mut transactions = self
            .snapshot
            .read_model
            .account_transactions
            .values()
            .filter(|transaction| transaction.address == address)
            .map(account_transaction_response)
            .collect::<Vec<_>>();
        transactions.sort_by(|left, right| {
            right
                .block_height
                .cmp(&left.block_height)
                .then_with(|| right.transaction_index.cmp(&left.transaction_index))
                .then_with(|| left.tx_hash.cmp(&right.tx_hash))
                .then_with(|| left.direction.cmp(right.direction))
        });
        let total = transactions.len();
        transactions.truncate(limit);
        let next_cursor = list_next_cursor(
            total,
            transactions.len(),
            transactions.last().map(|transaction| {
                format!(
                    "{}:{}:{}",
                    transaction.block_height, transaction.transaction_index, transaction.tx_hash
                )
            }),
        );

        AccountHistoryResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            address: address.to_string(),
            limit,
            next_cursor,
            transactions,
        }
    }

    pub fn admin_indexer_status(&self) -> IndexerStatusResponse {
        IndexerStatusResponse {
            environment: API_ENVIRONMENT,
            service: INDEXER_SERVICE,
            status: "current",
            latest_indexed_height: self.snapshot.current_height,
            latest_indexed_block_hash: self.snapshot.latest_block_hash.clone(),
            lag_blocks: 0,
            last_run: IndexerRunResponse {
                run_id: format!(
                    "private-devnet-replay-{}-{}",
                    self.snapshot.current_height, self.snapshot.latest_block_hash
                ),
                status: "completed",
                from_height: self.snapshot.summary.from_height,
                to_height: self.snapshot.summary.to_height,
                blocks_indexed: self.snapshot.summary.blocks_indexed,
                transactions_indexed: self.snapshot.summary.transactions_indexed,
            },
        }
    }

    pub fn snapshot(&self) -> &IndexedChainSnapshot {
        &self.snapshot
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ApiError {
    AccountNotFound,
    BlockNotFound,
    TransactionNotFound,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HealthResponse {
    pub ok: bool,
    pub network: String,
    pub environment: &'static str,
    pub service: &'static str,
    pub version: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct VersionResponse {
    pub environment: &'static str,
    pub service: &'static str,
    pub version: &'static str,
    pub indexer_version: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NetworkResponse {
    pub environment: &'static str,
    pub network: String,
    pub current_height: u64,
    pub latest_block_hash: String,
    pub state_root: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ExplorerOverviewResponse {
    pub environment: &'static str,
    pub network: String,
    pub chain: ChainSummaryResponse,
    pub indexer: IndexerStatusResponse,
    pub totals: TotalsResponse,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChainSummaryResponse {
    pub current_height: u64,
    pub latest_block_hash: String,
    pub state_root: String,
    pub stored_blocks: usize,
    pub pending_transactions: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TotalsResponse {
    pub blocks: usize,
    pub transactions: usize,
    pub accounts: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BlockListResponse {
    pub environment: &'static str,
    pub network: String,
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub blocks: Vec<BlockResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BlockResponse {
    pub height: u64,
    pub block_hash: String,
    pub previous_block_hash: String,
    pub state_root: String,
    pub transactions_root: String,
    pub transaction_count: usize,
    pub timestamp_utc: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BlockDetailResponse {
    pub environment: &'static str,
    pub network: String,
    pub height: u64,
    pub block_hash: String,
    pub previous_block_hash: String,
    pub state_root: String,
    pub transactions_root: String,
    pub transaction_count: usize,
    pub timestamp_utc: String,
    pub transactions: Vec<TransactionResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionListResponse {
    pub environment: &'static str,
    pub network: String,
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub transactions: Vec<TransactionResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionResponse {
    pub tx_hash: String,
    pub block_height: u64,
    pub block_hash: String,
    pub transaction_index: usize,
    pub status: String,
    pub from_address: String,
    pub to_address: String,
    pub amount_base_units: String,
    pub fee_base_units: String,
    pub nonce: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountListResponse {
    pub environment: &'static str,
    pub network: String,
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub accounts: Vec<AccountResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountResponse {
    pub address: String,
    pub balance_base_units: String,
    pub nonce: u64,
    pub height: u64,
    pub state_root: String,
    pub first_seen_height: Option<u64>,
    pub last_seen_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountHistoryResponse {
    pub environment: &'static str,
    pub network: String,
    pub address: String,
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub transactions: Vec<AccountTransactionResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AccountTransactionResponse {
    pub address: String,
    pub tx_hash: String,
    pub direction: &'static str,
    pub block_height: u64,
    pub transaction_index: usize,
    pub amount_base_units: String,
    pub fee_base_units: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexerStatusResponse {
    pub environment: &'static str,
    pub service: &'static str,
    pub status: &'static str,
    pub latest_indexed_height: u64,
    pub latest_indexed_block_hash: String,
    pub lag_blocks: u64,
    pub last_run: IndexerRunResponse,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexerRunResponse {
    pub run_id: String,
    pub status: &'static str,
    pub from_height: Option<u64>,
    pub to_height: Option<u64>,
    pub blocks_indexed: usize,
    pub transactions_indexed: usize,
}

fn block_response(block: &IndexedBlock) -> BlockResponse {
    BlockResponse {
        height: block.height,
        block_hash: block.block_hash.clone(),
        previous_block_hash: block.previous_block_hash.clone(),
        state_root: block.state_root.clone(),
        transactions_root: block.transactions_root.clone(),
        transaction_count: block.transaction_count,
        timestamp_utc: timestamp_ms_to_utc(block.timestamp_ms),
    }
}

fn transaction_response(transaction: &IndexedTransaction) -> TransactionResponse {
    TransactionResponse {
        tx_hash: transaction.tx_hash.clone(),
        block_height: transaction.block_height,
        block_hash: transaction.block_hash.clone(),
        transaction_index: transaction.transaction_index,
        status: transaction.status.to_string(),
        from_address: transaction.from_address.clone(),
        to_address: transaction.to_address.clone(),
        amount_base_units: transaction.amount_base_units.clone(),
        fee_base_units: transaction.fee_base_units.clone(),
        nonce: transaction.nonce,
    }
}

fn account_response(
    accounts: &BTreeMap<String, IndexedAccount>,
    balance: &IndexedAccountBalance,
) -> AccountResponse {
    let account = accounts.get(&balance.address);
    AccountResponse {
        address: balance.address.clone(),
        balance_base_units: balance.balance_base_units.clone(),
        nonce: balance.nonce,
        height: balance.height,
        state_root: balance.state_root.clone(),
        first_seen_height: account.and_then(|account| account.first_seen_height),
        last_seen_height: account.and_then(|account| account.last_seen_height),
    }
}

fn account_transaction_response(
    transaction: &IndexedAccountTransaction,
) -> AccountTransactionResponse {
    AccountTransactionResponse {
        address: transaction.address.clone(),
        tx_hash: transaction.tx_hash.clone(),
        direction: transaction.direction,
        block_height: transaction.block_height,
        transaction_index: transaction.transaction_index,
        amount_base_units: transaction.amount_base_units.clone(),
        fee_base_units: transaction.fee_base_units.clone(),
    }
}

fn transactions_for_block(
    transactions: &BTreeMap<String, IndexedTransaction>,
    block: &IndexedBlock,
) -> Vec<TransactionResponse> {
    let mut values = transactions
        .values()
        .filter(|transaction| {
            transaction.block_height == block.height && transaction.block_hash == block.block_hash
        })
        .map(transaction_response)
        .collect::<Vec<_>>();
    values.sort_by(|left, right| {
        left.transaction_index
            .cmp(&right.transaction_index)
            .then_with(|| left.tx_hash.cmp(&right.tx_hash))
    });
    values
}

fn list_next_cursor<T: Into<String>>(
    total_count: usize,
    returned_count: usize,
    last_cursor: Option<T>,
) -> Option<String> {
    if returned_count < total_count {
        last_cursor.map(Into::into)
    } else {
        None
    }
}

fn timestamp_ms_to_utc(timestamp_ms: u64) -> String {
    let seconds = timestamp_ms / 1000;
    let days = seconds / 86_400;
    let seconds_of_day = seconds % 86_400;
    let (year, month, day) = civil_from_days(days as i64);
    let hour = seconds_of_day / 3_600;
    let minute = (seconds_of_day % 3_600) / 60;
    let second = seconds_of_day % 60;
    format!("{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}Z")
}

fn civil_from_days(days_since_unix_epoch: i64) -> (i64, u32, u32) {
    let z = days_since_unix_epoch + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let day_of_era = z - era * 146_097;
    let year_of_era =
        (day_of_era - day_of_era / 1_460 + day_of_era / 36_524 - day_of_era / 146_096) / 365;
    let year = year_of_era + era * 400;
    let day_of_year = day_of_era - (365 * year_of_era + year_of_era / 4 - year_of_era / 100);
    let month_prime = (5 * day_of_year + 2) / 153;
    let day = day_of_year - (153 * month_prime + 2) / 5 + 1;
    let month = month_prime + if month_prime < 10 { 3 } else { -9 };
    let year = year + if month <= 2 { 1 } else { 0 };
    (year, month as u32, day as u32)
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_indexer::{
        IndexReplaySummary, IndexedAccount, IndexedAccountBalance, IndexedAccountTransaction,
        IndexedAuditEvent, IndexedReadModel, INDEXER_ENVIRONMENT, INDEXER_PRIVATE_DEVNET_WARNING,
    };

    const BLOCK_HASH: &str = "fe349b87f4219a7edd3dc8cb430b27200eb3500ab9550692b1493d4c4312371d";
    const STATE_ROOT: &str = "915a4319e23daea9370a2ea1dfe9b57ac0099be910f64d04a5f4b9dfb0c5d067";
    const TX_HASH: &str = "fceb942511656f49850212a35fd39ba162e76dcd74e98ace33049457ab719565";

    fn service() -> XriqApiService {
        XriqApiService::new(snapshot())
    }

    fn snapshot() -> IndexedChainSnapshot {
        let mut blocks = BTreeMap::new();
        blocks.insert(
            1,
            IndexedBlock {
                height: 1,
                block_hash: BLOCK_HASH.to_string(),
                previous_block_hash: "0".repeat(64),
                state_root: STATE_ROOT.to_string(),
                transactions_root:
                    "1f6d2eda722f82fe68789c987ac9dc9b276a6b479900dff85034942c9f0b5dee".to_string(),
                transaction_count: 1,
                timestamp_ms: 1_001,
            },
        );

        let mut transactions = BTreeMap::new();
        transactions.insert(
            TX_HASH.to_string(),
            IndexedTransaction {
                tx_hash: TX_HASH.to_string(),
                block_height: 1,
                block_hash: BLOCK_HASH.to_string(),
                transaction_index: 0,
                status: "confirmed",
                from_address: "xriqdev1alice00000000000".to_string(),
                to_address: "xriqdev1bobbb00000000000".to_string(),
                amount_base_units: "25".to_string(),
                fee_base_units: "2".to_string(),
                nonce: 0,
            },
        );

        let mut accounts = BTreeMap::new();
        accounts.insert(
            "xriqdev1alice00000000000".to_string(),
            IndexedAccount {
                address: "xriqdev1alice00000000000".to_string(),
                first_seen_height: Some(0),
                last_seen_height: Some(1),
            },
        );
        accounts.insert(
            "xriqdev1bobbb00000000000".to_string(),
            IndexedAccount {
                address: "xriqdev1bobbb00000000000".to_string(),
                first_seen_height: Some(1),
                last_seen_height: Some(1),
            },
        );

        let mut account_balances = BTreeMap::new();
        account_balances.insert(
            "xriqdev1alice00000000000".to_string(),
            IndexedAccountBalance {
                address: "xriqdev1alice00000000000".to_string(),
                balance_base_units: "73".to_string(),
                nonce: 1,
                height: 1,
                state_root: STATE_ROOT.to_string(),
            },
        );
        account_balances.insert(
            "xriqdev1bobbb00000000000".to_string(),
            IndexedAccountBalance {
                address: "xriqdev1bobbb00000000000".to_string(),
                balance_base_units: "25".to_string(),
                nonce: 0,
                height: 1,
                state_root: STATE_ROOT.to_string(),
            },
        );

        let mut account_transactions = BTreeMap::new();
        account_transactions.insert(
            (
                "xriqdev1alice00000000000".to_string(),
                TX_HASH.to_string(),
                "sent",
            ),
            IndexedAccountTransaction {
                address: "xriqdev1alice00000000000".to_string(),
                tx_hash: TX_HASH.to_string(),
                direction: "sent",
                block_height: 1,
                transaction_index: 0,
                amount_base_units: "25".to_string(),
                fee_base_units: "2".to_string(),
            },
        );
        account_transactions.insert(
            (
                "xriqdev1bobbb00000000000".to_string(),
                TX_HASH.to_string(),
                "received",
            ),
            IndexedAccountTransaction {
                address: "xriqdev1bobbb00000000000".to_string(),
                tx_hash: TX_HASH.to_string(),
                direction: "received",
                block_height: 1,
                transaction_index: 0,
                amount_base_units: "25".to_string(),
                fee_base_units: "0".to_string(),
            },
        );

        let mut audit_events = BTreeMap::new();
        audit_events.insert(
            "index-block:1".to_string(),
            IndexedAuditEvent {
                event_id: "index-block:1".to_string(),
                actor: "xriq-indexer",
                action: "index_block",
                resource_type: "block",
                resource_id: Some(BLOCK_HASH.to_string()),
                environment: INDEXER_ENVIRONMENT,
            },
        );

        IndexedChainSnapshot {
            warning: INDEXER_PRIVATE_DEVNET_WARNING,
            environment: INDEXER_ENVIRONMENT,
            chain_id: "xriq-devnet".to_string(),
            current_height: 1,
            latest_block_hash: BLOCK_HASH.to_string(),
            state_root: STATE_ROOT.to_string(),
            read_model: IndexedReadModel {
                blocks,
                transactions,
                accounts,
                account_balances,
                account_transactions,
                audit_events,
            },
            summary: IndexReplaySummary {
                blocks_seen: 1,
                blocks_indexed: 1,
                transactions_seen: 1,
                transactions_indexed: 1,
                account_transactions_indexed: 2,
                account_balances_seen: 2,
                account_balances_indexed: 2,
                audit_events_indexed: 1,
                from_height: Some(1),
                to_height: Some(1),
            },
        }
    }

    #[test]
    fn health_version_and_network_are_private_devnet_only() {
        let api = service();

        assert_eq!(
            api.health(),
            HealthResponse {
                ok: true,
                network: "xriq-devnet".to_string(),
                environment: API_ENVIRONMENT,
                service: API_SERVICE,
                version: API_VERSION,
            }
        );
        assert_eq!(api.version().indexer_version, "xriq-indexer-0.1.0");
        assert_eq!(api.network().latest_block_hash, BLOCK_HASH);
    }

    #[test]
    fn explorer_overview_reports_indexed_totals_and_status() {
        let overview = service().explorer_overview();

        assert_eq!(overview.environment, API_ENVIRONMENT);
        assert_eq!(overview.chain.current_height, 1);
        assert_eq!(overview.chain.pending_transactions, 0);
        assert_eq!(overview.totals.blocks, 1);
        assert_eq!(overview.totals.transactions, 1);
        assert_eq!(overview.totals.accounts, 2);
        assert_eq!(overview.indexer.status, "current");
        assert_eq!(overview.indexer.last_run.blocks_indexed, 1);
    }

    #[test]
    fn lists_and_fetches_blocks_by_height_or_hash() {
        let api = service();

        let blocks = api.blocks(25);
        assert_eq!(blocks.environment, API_ENVIRONMENT);
        assert_eq!(blocks.next_cursor, None);
        assert_eq!(blocks.blocks.len(), 1);
        assert_eq!(blocks.blocks[0].timestamp_utc, "1970-01-01T00:00:01Z");

        let by_height = api.block("1").unwrap();
        let by_hash = api.block(BLOCK_HASH).unwrap();
        assert_eq!(by_height, by_hash);
        assert_eq!(by_height.transactions.len(), 1);
        assert_eq!(by_height.transactions[0].tx_hash, TX_HASH);
        assert_eq!(api.block("99"), Err(ApiError::BlockNotFound));
    }

    #[test]
    fn lists_and_fetches_transactions() {
        let api = service();

        let transactions = api.transactions(25);

        assert_eq!(transactions.transactions.len(), 1);
        assert_eq!(transactions.transactions[0].status, "confirmed");
        assert_eq!(transactions.transactions[0].amount_base_units, "25");
        assert_eq!(
            api.transaction(TX_HASH).unwrap(),
            transactions.transactions[0]
        );
        assert_eq!(
            api.transaction(&"9".repeat(64)),
            Err(ApiError::TransactionNotFound)
        );
    }

    #[test]
    fn accounts_and_history_are_deterministic() {
        let api = service();

        let accounts = api.accounts(25);
        assert_eq!(accounts.accounts.len(), 2);
        assert_eq!(accounts.accounts[0].address, "xriqdev1alice00000000000");
        assert_eq!(accounts.accounts[0].balance_base_units, "73");
        assert_eq!(accounts.accounts[0].first_seen_height, Some(0));
        assert_eq!(
            api.account("xriqdev1missing000000000"),
            Err(ApiError::AccountNotFound)
        );

        let history = api.account_transactions("xriqdev1alice00000000000", 25);
        assert_eq!(history.transactions.len(), 1);
        assert_eq!(history.transactions[0].direction, "sent");
        assert_eq!(history.transactions[0].fee_base_units, "2");
    }

    #[test]
    fn indexer_status_uses_deterministic_replay_metadata() {
        let status = service().admin_indexer_status();

        assert_eq!(status.environment, API_ENVIRONMENT);
        assert_eq!(status.service, INDEXER_SERVICE);
        assert_eq!(status.latest_indexed_height, 1);
        assert_eq!(status.lag_blocks, 0);
        assert!(status
            .last_run
            .run_id
            .starts_with("private-devnet-replay-1-"));
        assert_eq!(status.last_run.from_height, Some(1));
        assert_eq!(status.last_run.to_height, Some(1));
    }

    #[test]
    fn utc_timestamp_conversion_handles_epoch_boundaries() {
        assert_eq!(timestamp_ms_to_utc(0), "1970-01-01T00:00:00Z");
        assert_eq!(timestamp_ms_to_utc(1_001), "1970-01-01T00:00:01Z");
        assert_eq!(timestamp_ms_to_utc(86_400_000), "1970-01-02T00:00:00Z");
    }
}
