//! Product-facing API service boundary for the XRIQ private devnet.
//!
//! This crate intentionally does not bind a socket yet. It defines stable
//! response models plus HTTP route/render behavior that a later local server
//! can expose for explorer, account-history, and admin views.

use std::{collections::BTreeMap, fmt::Write as _};

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
pub struct ApiHttpResponse {
    pub status_code: u16,
    pub reason: &'static str,
    pub body: String,
}

impl ApiHttpResponse {
    pub fn to_http_response(&self) -> String {
        format!(
            "HTTP/1.1 {} {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            self.status_code,
            self.reason,
            self.body.len(),
            self.body
        )
    }
}

pub fn product_api_http_response(
    service: &XriqApiService,
    method: &str,
    target: &str,
) -> ApiHttpResponse {
    if method != "GET" {
        return api_error_response(
            405,
            "method_not_allowed",
            "XRIQ product API scaffold currently supports GET only",
        );
    }

    let (path, query) = split_http_target(target);
    match path {
        "/api/v1/health" => api_json_response(200, render_health_json(&service.health())),
        "/api/v1/version" => api_json_response(200, render_version_json(&service.version())),
        "/api/v1/network" => api_json_response(200, render_network_json(&service.network())),
        "/api/v1/explorer/overview" => api_json_response(
            200,
            render_explorer_overview_json(&service.explorer_overview()),
        ),
        "/api/v1/blocks" => match limit_from_query(query, 25) {
            Ok(limit) => api_json_response(200, render_block_list_json(&service.blocks(limit))),
            Err(message) => api_error_response(400, "bad_request", &message),
        },
        "/api/v1/transactions" => match limit_from_query(query, 25) {
            Ok(limit) => api_json_response(
                200,
                render_transaction_list_json(&service.transactions(limit)),
            ),
            Err(message) => api_error_response(400, "bad_request", &message),
        },
        "/api/v1/accounts" => match limit_from_query(query, 25) {
            Ok(limit) => api_json_response(200, render_account_list_json(&service.accounts(limit))),
            Err(message) => api_error_response(400, "bad_request", &message),
        },
        "/api/v1/admin/indexer/status" => api_json_response(
            200,
            render_indexer_status_json(&service.admin_indexer_status()),
        ),
        path => dynamic_product_api_http_response(service, path, query),
    }
}

fn dynamic_product_api_http_response(
    service: &XriqApiService,
    path: &str,
    query: Option<&str>,
) -> ApiHttpResponse {
    if let Some(block_id) = path.strip_prefix("/api/v1/blocks/") {
        return match service.block(block_id) {
            Ok(block) => api_json_response(200, render_block_detail_json(&block)),
            Err(error) => api_not_found_response(error),
        };
    }

    if let Some(tx_hash) = path.strip_prefix("/api/v1/transactions/") {
        return match service.transaction(tx_hash) {
            Ok(transaction) => api_json_response(
                200,
                render_transaction_detail_json(&transaction, &service.snapshot().chain_id),
            ),
            Err(error) => api_not_found_response(error),
        };
    }

    if let Some(account_path) = path.strip_prefix("/api/v1/accounts/") {
        if let Some(address) = account_path.strip_suffix("/transactions") {
            return match limit_from_query(query, 25) {
                Ok(limit) => api_json_response(
                    200,
                    render_account_history_json(&service.account_transactions(address, limit)),
                ),
                Err(message) => api_error_response(400, "bad_request", &message),
            };
        }

        return match service.account(account_path) {
            Ok(account) => api_json_response(
                200,
                render_account_detail_json(&account, &service.snapshot().chain_id),
            ),
            Err(error) => api_not_found_response(error),
        };
    }

    api_error_response(404, "not_found", "XRIQ product API endpoint not found")
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

fn api_json_response(status_code: u16, body: String) -> ApiHttpResponse {
    ApiHttpResponse {
        status_code,
        reason: http_reason(status_code),
        body,
    }
}

fn api_error_response(status_code: u16, code: &str, message: &str) -> ApiHttpResponse {
    api_json_response(
        status_code,
        format!(
            "{{\n  \"environment\": {},\n  \"error\": {{\n    \"code\": {},\n    \"message\": {}\n  }}\n}}",
            json_string(API_ENVIRONMENT),
            json_string(code),
            json_string(message)
        ),
    )
}

fn api_not_found_response(error: ApiError) -> ApiHttpResponse {
    match error {
        ApiError::AccountNotFound => {
            api_error_response(404, "account_not_found", "XRIQ account not found")
        }
        ApiError::BlockNotFound => {
            api_error_response(404, "block_not_found", "XRIQ block not found")
        }
        ApiError::TransactionNotFound => {
            api_error_response(404, "transaction_not_found", "XRIQ transaction not found")
        }
    }
}

fn http_reason(status_code: u16) -> &'static str {
    match status_code {
        200 => "OK",
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        _ => "Internal Server Error",
    }
}

fn split_http_target(target: &str) -> (&str, Option<&str>) {
    target
        .split_once('?')
        .map_or((target, None), |(path, query)| (path, Some(query)))
}

fn limit_from_query(query: Option<&str>, default_limit: usize) -> Result<usize, String> {
    let Some(value) = query_param(query, "limit") else {
        return Ok(default_limit);
    };
    value
        .parse::<usize>()
        .map_err(|_| format!("invalid limit: {value}"))
}

fn query_param<'a>(query: Option<&'a str>, key: &str) -> Option<&'a str> {
    query?.split('&').find_map(|pair| {
        let (candidate, value) = pair.split_once('=')?;
        if candidate == key {
            Some(value)
        } else {
            None
        }
    })
}

fn render_health_json(response: &HealthResponse) -> String {
    format!(
        "{{\n  \"ok\": {},\n  \"network\": {},\n  \"environment\": {},\n  \"service\": {},\n  \"version\": {}\n}}",
        response.ok,
        json_string(&response.network),
        json_string(response.environment),
        json_string(response.service),
        json_string(response.version)
    )
}

fn render_version_json(response: &VersionResponse) -> String {
    format!(
        "{{\n  \"environment\": {},\n  \"service\": {},\n  \"version\": {},\n  \"indexer_version\": {}\n}}",
        json_string(response.environment),
        json_string(response.service),
        json_string(response.version),
        json_string(response.indexer_version)
    )
}

fn render_network_json(response: &NetworkResponse) -> String {
    format!(
        "{{\n  \"environment\": {},\n  \"network\": {},\n  \"current_height\": {},\n  \"latest_block_hash\": {},\n  \"state_root\": {}\n}}",
        json_string(response.environment),
        json_string(&response.network),
        response.current_height,
        json_string(&response.latest_block_hash),
        json_string(&response.state_root)
    )
}

fn render_explorer_overview_json(response: &ExplorerOverviewResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"environment\": {},",
        json_string(response.environment)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(&response.network)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"chain\": {{").expect("write to String");
    writeln!(
        &mut output,
        "    \"current_height\": {},",
        response.chain.current_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"latest_block_hash\": {},",
        json_string(&response.chain.latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"state_root\": {},",
        json_string(&response.chain.state_root)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"stored_blocks\": {},",
        response.chain.stored_blocks
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"pending_transactions\": {}",
        response.chain.pending_transactions
    )
    .expect("write to String");
    writeln!(&mut output, "  }},").expect("write to String");
    output.push_str("  \"indexer\": ");
    output.push_str(&render_indexer_status_json_inline(&response.indexer, 2));
    output.push_str(",\n");
    writeln!(&mut output, "  \"totals\": {{").expect("write to String");
    writeln!(&mut output, "    \"blocks\": {},", response.totals.blocks).expect("write to String");
    writeln!(
        &mut output,
        "    \"transactions\": {},",
        response.totals.transactions
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "    \"accounts\": {}",
        response.totals.accounts
    )
    .expect("write to String");
    output.push_str("  }\n}");
    output
}

fn render_block_list_json(response: &BlockListResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"environment\": {},",
        json_string(response.environment)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(&response.network)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", response.limit).expect("write to String");
    writeln!(
        &mut output,
        "  \"next_cursor\": {},",
        json_optional_string(response.next_cursor.as_deref())
    )
    .expect("write to String");
    output.push_str("  \"blocks\": [");
    for (index, block) in response.blocks.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_block_json_inline(block, 4));
    }
    if !response.blocks.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_block_detail_json(response: &BlockDetailResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(&mut output, "  \"height\": {},", response.height).expect("write to String");
    writeln!(
        &mut output,
        "  \"block_hash\": {},",
        json_string(&response.block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"previous_block_hash\": {},",
        json_string(&response.previous_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"state_root\": {},",
        json_string(&response.state_root)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transactions_root\": {},",
        json_string(&response.transactions_root)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_count\": {},",
        response.transaction_count
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"timestamp_utc\": {},",
        json_string(&response.timestamp_utc)
    )
    .expect("write to String");
    output.push_str("  \"transactions\": [");
    for (index, transaction) in response.transactions.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_transaction_json_inline(transaction, 4));
    }
    if !response.transactions.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_transaction_list_json(response: &TransactionListResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(&mut output, "  \"limit\": {},", response.limit).expect("write to String");
    writeln!(
        &mut output,
        "  \"next_cursor\": {},",
        json_optional_string(response.next_cursor.as_deref())
    )
    .expect("write to String");
    output.push_str("  \"transactions\": [");
    for (index, transaction) in response.transactions.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_transaction_json_inline(transaction, 4));
    }
    if !response.transactions.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_transaction_detail_json(response: &TransactionResponse, network: &str) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, API_ENVIRONMENT, network);
    writeln!(
        &mut output,
        "  \"tx_hash\": {},",
        json_string(&response.tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"block_height\": {},",
        response.block_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"block_hash\": {},",
        json_string(&response.block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_index\": {},",
        response.transaction_index
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"status\": {},",
        json_string(&response.status)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"from_address\": {},",
        json_string(&response.from_address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"to_address\": {},",
        json_string(&response.to_address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"amount_base_units\": {},",
        json_string(&response.amount_base_units)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"fee_base_units\": {},",
        json_string(&response.fee_base_units)
    )
    .expect("write to String");
    write!(&mut output, "  \"nonce\": {}\n}}", response.nonce).expect("write to String");
    output
}

fn render_account_list_json(response: &AccountListResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(&mut output, "  \"limit\": {},", response.limit).expect("write to String");
    writeln!(
        &mut output,
        "  \"next_cursor\": {},",
        json_optional_string(response.next_cursor.as_deref())
    )
    .expect("write to String");
    output.push_str("  \"accounts\": [");
    for (index, account) in response.accounts.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_account_json_inline(account, 4));
    }
    if !response.accounts.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_account_detail_json(response: &AccountResponse, network: &str) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, API_ENVIRONMENT, network);
    writeln!(
        &mut output,
        "  \"address\": {},",
        json_string(&response.address)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"balance_base_units\": {},",
        json_string(&response.balance_base_units)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"nonce\": {},", response.nonce).expect("write to String");
    writeln!(&mut output, "  \"height\": {},", response.height).expect("write to String");
    writeln!(
        &mut output,
        "  \"state_root\": {},",
        json_string(&response.state_root)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"first_seen_height\": {},",
        json_optional_u64(response.first_seen_height)
    )
    .expect("write to String");
    write!(
        &mut output,
        "  \"last_seen_height\": {}\n}}",
        json_optional_u64(response.last_seen_height)
    )
    .expect("write to String");
    output
}

fn render_account_history_json(response: &AccountHistoryResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(
        &mut output,
        "  \"address\": {},",
        json_string(&response.address)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", response.limit).expect("write to String");
    writeln!(
        &mut output,
        "  \"next_cursor\": {},",
        json_optional_string(response.next_cursor.as_deref())
    )
    .expect("write to String");
    output.push_str("  \"transactions\": [");
    for (index, transaction) in response.transactions.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_account_transaction_json_inline(transaction, 4));
    }
    if !response.transactions.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_indexer_status_json(response: &IndexerStatusResponse) -> String {
    render_indexer_status_json_inline(response, 0)
}

fn render_block_json_inline(block: &BlockResponse, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"height\": {},\n{nested}\"block_hash\": {},\n{nested}\"previous_block_hash\": {},\n{nested}\"state_root\": {},\n{nested}\"transactions_root\": {},\n{nested}\"transaction_count\": {},\n{nested}\"timestamp_utc\": {}\n{spaces}}}",
        block.height,
        json_string(&block.block_hash),
        json_string(&block.previous_block_hash),
        json_string(&block.state_root),
        json_string(&block.transactions_root),
        block.transaction_count,
        json_string(&block.timestamp_utc)
    )
}

fn render_transaction_json_inline(transaction: &TransactionResponse, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"tx_hash\": {},\n{nested}\"block_height\": {},\n{nested}\"block_hash\": {},\n{nested}\"transaction_index\": {},\n{nested}\"status\": {},\n{nested}\"from_address\": {},\n{nested}\"to_address\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {},\n{nested}\"nonce\": {}\n{spaces}}}",
        json_string(&transaction.tx_hash),
        transaction.block_height,
        json_string(&transaction.block_hash),
        transaction.transaction_index,
        json_string(&transaction.status),
        json_string(&transaction.from_address),
        json_string(&transaction.to_address),
        json_string(&transaction.amount_base_units),
        json_string(&transaction.fee_base_units),
        transaction.nonce
    )
}

fn render_account_json_inline(account: &AccountResponse, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"address\": {},\n{nested}\"balance_base_units\": {},\n{nested}\"nonce\": {},\n{nested}\"height\": {},\n{nested}\"state_root\": {},\n{nested}\"first_seen_height\": {},\n{nested}\"last_seen_height\": {}\n{spaces}}}",
        json_string(&account.address),
        json_string(&account.balance_base_units),
        account.nonce,
        account.height,
        json_string(&account.state_root),
        json_optional_u64(account.first_seen_height),
        json_optional_u64(account.last_seen_height)
    )
}

fn render_account_transaction_json_inline(
    transaction: &AccountTransactionResponse,
    indent: usize,
) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"address\": {},\n{nested}\"tx_hash\": {},\n{nested}\"direction\": {},\n{nested}\"block_height\": {},\n{nested}\"transaction_index\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {}\n{spaces}}}",
        json_string(&transaction.address),
        json_string(&transaction.tx_hash),
        json_string(transaction.direction),
        transaction.block_height,
        transaction.transaction_index,
        json_string(&transaction.amount_base_units),
        json_string(&transaction.fee_base_units)
    )
}

fn render_indexer_status_json_inline(response: &IndexerStatusResponse, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    let deep = " ".repeat(indent + 4);
    format!(
        "{spaces}{{\n{nested}\"environment\": {},\n{nested}\"service\": {},\n{nested}\"status\": {},\n{nested}\"latest_indexed_height\": {},\n{nested}\"latest_indexed_block_hash\": {},\n{nested}\"lag_blocks\": {},\n{nested}\"last_run\": {{\n{deep}\"run_id\": {},\n{deep}\"status\": {},\n{deep}\"from_height\": {},\n{deep}\"to_height\": {},\n{deep}\"blocks_indexed\": {},\n{deep}\"transactions_indexed\": {}\n{nested}}}\n{spaces}}}",
        json_string(response.environment),
        json_string(response.service),
        json_string(response.status),
        response.latest_indexed_height,
        json_string(&response.latest_indexed_block_hash),
        response.lag_blocks,
        json_string(&response.last_run.run_id),
        json_string(response.last_run.status),
        json_optional_u64(response.last_run.from_height),
        json_optional_u64(response.last_run.to_height),
        response.last_run.blocks_indexed,
        response.last_run.transactions_indexed
    )
}

fn push_response_header(output: &mut String, environment: &str, network: &str) {
    writeln!(output, "  \"environment\": {},", json_string(environment)).expect("write to String");
    writeln!(output, "  \"network\": {},", json_string(network)).expect("write to String");
}

fn json_optional_string(value: Option<&str>) -> String {
    value.map(json_string).unwrap_or_else(|| "null".to_string())
}

fn json_optional_u64(value: Option<u64>) -> String {
    value
        .map(|number| number.to_string())
        .unwrap_or_else(|| "null".to_string())
}

fn json_string(value: &str) -> String {
    let mut output = String::with_capacity(value.len() + 2);
    output.push('"');
    for character in value.chars() {
        match character {
            '"' => output.push_str("\\\""),
            '\\' => output.push_str("\\\\"),
            '\n' => output.push_str("\\n"),
            '\r' => output.push_str("\\r"),
            '\t' => output.push_str("\\t"),
            '\u{08}' => output.push_str("\\b"),
            '\u{0c}' => output.push_str("\\f"),
            character if character < '\u{20}' => {
                write!(&mut output, "\\u{:04x}", character as u32).expect("write to String");
            }
            character => output.push(character),
        }
    }
    output.push('"');
    output
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
    fn product_api_http_routes_render_contract_json() {
        let api = service();

        let health = product_api_http_response(&api, "GET", "/api/v1/health");
        assert_eq!(health.status_code, 200);
        assert!(health.body.contains("\"service\": \"xriq-api\""));
        assert!(health.body.contains("\"environment\": \"private-devnet\""));

        let overview = product_api_http_response(&api, "GET", "/api/v1/explorer/overview");
        assert_eq!(overview.status_code, 200);
        assert!(overview.body.contains("\"current_height\": 1"));
        assert!(overview.body.contains("\"indexer\""));
        assert!(overview.body.contains("\"transactions\": 1"));

        let blocks = product_api_http_response(&api, "GET", "/api/v1/blocks?limit=5");
        assert_eq!(blocks.status_code, 200);
        assert!(blocks.body.contains("\"blocks\""));
        assert!(blocks.body.contains(BLOCK_HASH));

        let block = product_api_http_response(&api, "GET", "/api/v1/blocks/1");
        assert_eq!(block.status_code, 200);
        assert!(block
            .body
            .contains("\"timestamp_utc\": \"1970-01-01T00:00:01Z\""));
        assert!(block.body.contains(TX_HASH));

        let transaction =
            product_api_http_response(&api, "GET", &format!("/api/v1/transactions/{TX_HASH}"));
        assert_eq!(transaction.status_code, 200);
        assert!(transaction
            .body
            .contains("\"environment\": \"private-devnet\""));
        assert!(transaction.body.contains("\"network\": \"xriq-devnet\""));
        assert!(transaction.body.contains("\"status\": \"confirmed\""));
        assert!(transaction.body.contains("\"amount_base_units\": \"25\""));

        let account =
            product_api_http_response(&api, "GET", "/api/v1/accounts/xriqdev1alice00000000000");
        assert_eq!(account.status_code, 200);
        assert!(account.body.contains("\"environment\": \"private-devnet\""));
        assert!(account.body.contains("\"network\": \"xriq-devnet\""));
        assert!(account.body.contains("\"balance_base_units\": \"73\""));

        let account_history = product_api_http_response(
            &api,
            "GET",
            "/api/v1/accounts/xriqdev1alice00000000000/transactions?limit=5",
        );
        assert_eq!(account_history.status_code, 200);
        assert!(account_history.body.contains("\"direction\": \"sent\""));
        assert!(account_history.body.contains("\"fee_base_units\": \"2\""));

        let status = product_api_http_response(&api, "GET", "/api/v1/admin/indexer/status");
        assert_eq!(status.status_code, 200);
        assert!(status.body.contains("\"service\": \"xriq-indexer\""));
    }

    #[test]
    fn product_api_http_routes_handle_errors_without_mutation() {
        let api = service();

        let missing_block = product_api_http_response(&api, "GET", "/api/v1/blocks/99");
        assert_eq!(missing_block.status_code, 404);
        assert!(missing_block.body.contains("\"code\": \"block_not_found\""));

        let bad_limit = product_api_http_response(&api, "GET", "/api/v1/accounts?limit=bad");
        assert_eq!(bad_limit.status_code, 400);
        assert!(bad_limit.body.contains("\"code\": \"bad_request\""));

        let unsupported_method = product_api_http_response(&api, "POST", "/api/v1/accounts");
        assert_eq!(unsupported_method.status_code, 405);
        assert!(unsupported_method
            .body
            .contains("currently supports GET only"));

        let missing_route = product_api_http_response(&api, "GET", "/api/v1/dex/pairs");
        assert_eq!(missing_route.status_code, 404);
        assert!(missing_route.body.contains("\"code\": \"not_found\""));

        let raw = product_api_http_response(&api, "GET", "/api/v1/network").to_http_response();
        assert!(raw.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(raw.contains("Content-Type: application/json"));
        assert!(raw.contains("\"network\": \"xriq-devnet\""));
    }

    #[test]
    fn utc_timestamp_conversion_handles_epoch_boundaries() {
        assert_eq!(timestamp_ms_to_utc(0), "1970-01-01T00:00:00Z");
        assert_eq!(timestamp_ms_to_utc(1_001), "1970-01-01T00:00:01Z");
        assert_eq!(timestamp_ms_to_utc(86_400_000), "1970-01-02T00:00:00Z");
    }
}
