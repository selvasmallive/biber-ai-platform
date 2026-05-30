//! Product-facing API service boundary for the XRIQ private devnet.
//!
//! This crate defines stable response models plus HTTP route/render behavior
//! for explorer, account-history, and admin views. The companion `xriq-api`
//! binary can expose those routes through a local read-only private-devnet
//! socket for Phase 1.1 smoke testing.

use std::{
    collections::BTreeMap,
    fmt::{self, Write as _},
};

use xriq_core::{
    Address, Hash32, SignatureBytes, Transaction, XriqAmount, PRIVATE_DEVNET_MIN_FEE_BASE_UNITS,
};
use xriq_crypto::transaction_hash;
use xriq_indexer::{
    IndexedAccount, IndexedAccountBalance, IndexedAccountTransaction, IndexedAuditEvent,
    IndexedBlock, IndexedChainSnapshot, IndexedTransaction,
};
use xriq_iso20022::{
    account_statement_preview, payment_initiation_preview, payment_status_preview,
    AccountStatementEntry, AccountStatementPreview, PaymentInitiationAligned,
    PaymentInitiationPreview, PaymentStatusAligned, PaymentStatusPreview, XriqIsoAccountHistory,
    XriqIsoAccountTransaction, XriqIsoTransaction, XriqTransferFields,
};

pub const API_ENVIRONMENT: &str = "private-devnet";
pub const API_SERVICE: &str = "xriq-api";
pub const API_VERSION: &str = "phase1.1-dev";
pub const INDEXER_SERVICE: &str = "xriq-indexer";
pub const WALLET_PREVIEW_WARNING: &str = "private-devnet-preview-only-no-signing-no-submit";
pub const MEMPOOL_READONLY_WARNING: &str =
    "private-devnet-read-only-mempool-status-submit-disabled";
pub const SNAPSHOT_READONLY_WARNING: &str =
    "private-devnet-read-only-snapshot-catalog-export-import-disabled";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct XriqApiService {
    snapshot: IndexedChainSnapshot,
    pending_entries: Vec<MempoolEntryResponse>,
}

impl XriqApiService {
    pub fn new(snapshot: IndexedChainSnapshot) -> Self {
        Self {
            snapshot,
            pending_entries: Vec::new(),
        }
    }

    pub fn with_pending_mempool_entries(
        mut self,
        pending_entries: Vec<MempoolEntryResponse>,
    ) -> Self {
        self.pending_entries = pending_entries;
        self
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
                pending_transactions: self.pending_entries.len(),
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

    pub fn mempool(&self, limit: usize) -> MempoolResponse {
        let entries = self
            .pending_entries
            .iter()
            .take(limit)
            .cloned()
            .collect::<Vec<_>>();
        let next_cursor = list_next_cursor(
            self.pending_entries.len(),
            entries.len(),
            entries.last().map(|entry| entry.tx_hash.clone()),
        );

        MempoolResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            warning: MEMPOOL_READONLY_WARNING,
            current_height: self.snapshot.current_height,
            pending_count: self.pending_entries.len(),
            limit,
            next_cursor,
            inspect_status: "enabled",
            submit_status: "disabled",
            produce_block_status: "disabled",
            entries,
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

    pub fn wallet_status(&self) -> WalletStatusResponse {
        WalletStatusResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            warning: WALLET_PREVIEW_WARNING,
            current_height: self.snapshot.current_height,
            latest_block_hash: self.snapshot.latest_block_hash.clone(),
            state_root: self.snapshot.state_root.clone(),
            account_count: self.snapshot.read_model.account_balances.len(),
            pending_transactions: 0,
            can_draft: true,
            can_submit: false,
            can_send: false,
        }
    }

    pub fn wallet_accounts(&self, limit: usize) -> WalletAccountListResponse {
        let accounts = self.accounts(limit);
        WalletAccountListResponse {
            environment: accounts.environment,
            network: accounts.network,
            warning: WALLET_PREVIEW_WARNING,
            limit: accounts.limit,
            next_cursor: accounts.next_cursor,
            accounts: accounts.accounts,
        }
    }

    pub fn wallet_balance(&self, address: &str) -> Result<WalletBalanceResponse, ApiError> {
        let account = self.account(address)?;
        Ok(WalletBalanceResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            warning: WALLET_PREVIEW_WARNING,
            address: account.address,
            balance_base_units: account.balance_base_units,
            nonce: account.nonce,
            height: account.height,
            state_root: account.state_root,
        })
    }

    pub fn wallet_transaction_status(
        &self,
        tx_hash: &str,
    ) -> Result<WalletTransactionStatusResponse, ApiError> {
        let transaction = self.transaction(tx_hash)?;
        Ok(WalletTransactionStatusResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            warning: WALLET_PREVIEW_WARNING,
            tx_hash: transaction.tx_hash,
            status: transaction.status,
            block_height: transaction.block_height,
            block_hash: transaction.block_hash,
            transaction_index: transaction.transaction_index,
        })
    }

    pub fn wallet_transfer_draft_preview(
        &self,
        request: WalletTransferDraftPreviewRequest,
    ) -> WalletTransferDraftPreviewResponse {
        let from_account = self.account(&request.from_address).ok();
        let balance = from_account
            .as_ref()
            .and_then(|account| account.balance_base_units.parse::<u128>().ok());
        let debit = request
            .amount_base_units
            .checked_add(request.fee_base_units);
        let remaining = match (balance, debit) {
            (Some(balance), Some(debit)) if balance >= debit => Some(balance - debit),
            _ => None,
        };
        let mut errors = Vec::new();

        if from_account.is_none() {
            errors.push("sender account not found".to_string());
        }
        if request.from_address == request.to_address {
            errors.push("sender and recipient must differ".to_string());
        }
        if request.amount_base_units == 0 {
            errors.push("amount must be greater than zero".to_string());
        }
        if request.fee_base_units < PRIVATE_DEVNET_MIN_FEE_BASE_UNITS {
            errors.push(format!(
                "fee must be at least {PRIVATE_DEVNET_MIN_FEE_BASE_UNITS} base units"
            ));
        }
        if let Some(account) = &from_account {
            if request.nonce != account.nonce {
                errors.push(format!("nonce must match sender nonce {}", account.nonce));
            }
        }
        if request
            .expires_at_height
            .is_some_and(|height| height <= self.snapshot.current_height)
        {
            errors.push("expiry must be greater than current height".to_string());
        }
        if debit.is_none() {
            errors.push("amount plus fee overflows base-unit range".to_string());
        }
        if matches!((balance, debit), (Some(balance), Some(debit)) if debit > balance) {
            errors.push("debit exceeds available balance".to_string());
        }

        WalletTransferDraftPreviewResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            warning: WALLET_PREVIEW_WARNING,
            mutation: "none",
            validation: WalletDraftValidationResponse {
                ok: errors.is_empty(),
                errors,
            },
            draft: WalletTransferDraftResponse {
                chain_id: request.chain_id,
                from_address: request.from_address,
                to_address: request.to_address,
                amount_base_units: request.amount_base_units.to_string(),
                fee_base_units: request.fee_base_units.to_string(),
                nonce: request.nonce,
                expires_at_height: request.expires_at_height,
            },
            balance: WalletDraftBalanceResponse {
                available_base_units: balance.map(|value| value.to_string()),
                debit_base_units: debit.map(|value| value.to_string()),
                remaining_base_units: remaining.map(|value| value.to_string()),
            },
        }
    }

    pub fn iso20022_payment_initiation_preview(
        &self,
        tx_hash: &str,
    ) -> Result<PaymentInitiationPreview, ApiError> {
        let transaction = self.transaction(tx_hash)?;
        Ok(payment_initiation_preview(&iso_transaction(&transaction)))
    }

    pub fn iso20022_transaction_status(
        &self,
        tx_hash: &str,
    ) -> Result<PaymentStatusPreview, ApiError> {
        let transaction = self.transaction(tx_hash)?;
        Ok(payment_status_preview(&iso_transaction(&transaction)))
    }

    pub fn iso20022_account_statement(
        &self,
        address: &str,
        from: &str,
        to: &str,
    ) -> Result<AccountStatementPreview, ApiError> {
        let account = self.account(address)?;
        let history = self.account_transactions(address, 25);
        let opening_balance =
            statement_opening_balance(&account.balance_base_units, &history.transactions);
        Ok(account_statement_preview(
            &iso_account_history(&history),
            opening_balance,
            account.balance_base_units,
            from,
            to,
        ))
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

    pub fn admin_node_status(&self) -> NodeStatusResponse {
        NodeStatusResponse {
            environment: API_ENVIRONMENT,
            service: API_SERVICE,
            status: "healthy",
            mode: "serve-readonly",
            source: "indexed-chain-snapshot",
            network: self.snapshot.chain_id.clone(),
            current_height: self.snapshot.current_height,
            latest_block_hash: self.snapshot.latest_block_hash.clone(),
            state_root: self.snapshot.state_root.clone(),
            stored_blocks: self.snapshot.read_model.blocks.len(),
            pending_transactions: self.pending_entries.len(),
            wallet_submit_status: "disabled",
            block_production_status: "disabled",
        }
    }

    pub fn admin_audit_events(&self, limit: usize) -> AuditEventListResponse {
        let mut audit_events = self
            .snapshot
            .read_model
            .audit_events
            .values()
            .map(audit_event_response)
            .collect::<Vec<_>>();
        audit_events.sort_by(|left, right| right.event_id.cmp(&left.event_id));
        let total = audit_events.len();
        audit_events.truncate(limit);
        let next_cursor = list_next_cursor(
            total,
            audit_events.len(),
            audit_events.last().map(|event| event.event_id.clone()),
        );

        AuditEventListResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            limit,
            next_cursor,
            audit_events,
        }
    }

    pub fn snapshots(&self) -> SnapshotListResponse {
        SnapshotListResponse {
            environment: API_ENVIRONMENT,
            network: self.snapshot.chain_id.clone(),
            warning: SNAPSHOT_READONLY_WARNING,
            snapshots: vec![self.current_snapshot_response()],
        }
    }

    pub fn snapshot_detail(&self, snapshot_name: &str) -> Result<SnapshotResponse, ApiError> {
        let snapshot = self.current_snapshot_response();
        if snapshot.snapshot_name == snapshot_name {
            Ok(snapshot)
        } else {
            Err(ApiError::SnapshotNotFound)
        }
    }

    pub fn snapshot(&self) -> &IndexedChainSnapshot {
        &self.snapshot
    }

    fn current_snapshot_response(&self) -> SnapshotResponse {
        SnapshotResponse {
            snapshot_name: "current-indexed-chain".to_string(),
            snapshot_dir: "read-model://current-indexed-chain".to_string(),
            current_height: self.snapshot.current_height,
            latest_block_hash: self.snapshot.latest_block_hash.clone(),
            state_root: self.snapshot.state_root.clone(),
            block_count: self.snapshot.read_model.blocks.len(),
            transaction_count: self.snapshot.read_model.transactions.len(),
            audit_event_count: self.snapshot.read_model.audit_events.len(),
            export_status: "disabled",
            import_status: "disabled",
        }
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
        "/api/v1/mempool" => match limit_from_query(query, 25) {
            Ok(limit) => api_json_response(200, render_mempool_json(&service.mempool(limit))),
            Err(message) => api_error_response(400, "bad_request", &message),
        },
        "/api/v1/accounts" => match limit_from_query(query, 25) {
            Ok(limit) => api_json_response(200, render_account_list_json(&service.accounts(limit))),
            Err(message) => api_error_response(400, "bad_request", &message),
        },
        "/api/v1/snapshots" => {
            api_json_response(200, render_snapshot_list_json(&service.snapshots()))
        }
        "/api/v1/wallet/status" => {
            api_json_response(200, render_wallet_status_json(&service.wallet_status()))
        }
        "/api/v1/wallet/accounts" => match limit_from_query(query, 25) {
            Ok(limit) => api_json_response(
                200,
                render_wallet_account_list_json(&service.wallet_accounts(limit)),
            ),
            Err(message) => api_error_response(400, "bad_request", &message),
        },
        "/api/v1/wallet/transfers/draft-preview" => {
            match wallet_draft_preview_request_from_query(query, &service.snapshot().chain_id) {
                Ok(request) => api_json_response(
                    200,
                    render_wallet_transfer_draft_preview_json(
                        &service.wallet_transfer_draft_preview(request),
                    ),
                ),
                Err(message) => api_error_response(400, "bad_request", &message),
            }
        }
        "/api/v1/iso20022/payment-initiation/preview" => {
            match required_query_param_any(query, &["tx_hash"]) {
                Ok(tx_hash) => match service.iso20022_payment_initiation_preview(tx_hash) {
                    Ok(preview) => {
                        api_json_response(200, render_iso_payment_initiation_preview_json(&preview))
                    }
                    Err(error) => api_not_found_response(error),
                },
                Err(message) => api_error_response(400, "bad_request", &message),
            }
        }
        "/api/v1/admin/indexer/status" => api_json_response(
            200,
            render_indexer_status_json(&service.admin_indexer_status()),
        ),
        "/api/v1/admin/node/status" => {
            api_json_response(200, render_node_status_json(&service.admin_node_status()))
        }
        "/api/v1/admin/audit-events" => match limit_from_query(query, 25) {
            Ok(limit) => api_json_response(
                200,
                render_audit_event_list_json(&service.admin_audit_events(limit)),
            ),
            Err(message) => api_error_response(400, "bad_request", &message),
        },
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

    if let Some(account_path) = path.strip_prefix("/api/v1/wallet/accounts/") {
        if let Some(address) = account_path.strip_suffix("/balance") {
            return match service.wallet_balance(address) {
                Ok(balance) => api_json_response(200, render_wallet_balance_json(&balance)),
                Err(error) => api_not_found_response(error),
            };
        }

        if let Some(address) = account_path.strip_suffix("/history") {
            return match limit_from_query(query, 25) {
                Ok(limit) => api_json_response(
                    200,
                    render_account_history_json(&service.account_transactions(address, limit)),
                ),
                Err(message) => api_error_response(400, "bad_request", &message),
            };
        }
    }

    if let Some(tx_path) = path.strip_prefix("/api/v1/wallet/transactions/") {
        if let Some(tx_hash) = tx_path.strip_suffix("/status") {
            return match service.wallet_transaction_status(tx_hash) {
                Ok(status) => {
                    api_json_response(200, render_wallet_transaction_status_json(&status))
                }
                Err(error) => api_not_found_response(error),
            };
        }
    }

    if let Some(tx_path) = path.strip_prefix("/api/v1/iso20022/transactions/") {
        if let Some(tx_hash) = tx_path.strip_suffix("/status") {
            return match service.iso20022_transaction_status(tx_hash) {
                Ok(status) => api_json_response(200, render_iso_payment_status_json(&status)),
                Err(error) => api_not_found_response(error),
            };
        }
    }

    if let Some(account_path) = path.strip_prefix("/api/v1/iso20022/accounts/") {
        if let Some(address) = account_path.strip_suffix("/statement") {
            let from = query_param(query, "from").unwrap_or("1970-01-01T00:00:00Z");
            let to = query_param(query, "to").unwrap_or("1970-01-01T00:00:02Z");
            return match service.iso20022_account_statement(address, from, to) {
                Ok(statement) => {
                    api_json_response(200, render_iso_account_statement_json(&statement))
                }
                Err(error) => api_not_found_response(error),
            };
        }
    }

    if let Some(snapshot_name) = path.strip_prefix("/api/v1/snapshots/") {
        return match service.snapshot_detail(snapshot_name) {
            Ok(snapshot) => api_json_response(200, render_snapshot_json(&snapshot)),
            Err(error) => api_not_found_response(error),
        };
    }

    api_error_response(404, "not_found", "XRIQ product API endpoint not found")
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ApiError {
    AccountNotFound,
    BlockNotFound,
    SnapshotNotFound,
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
pub struct MempoolResponse {
    pub environment: &'static str,
    pub network: String,
    pub warning: &'static str,
    pub current_height: u64,
    pub pending_count: usize,
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub inspect_status: &'static str,
    pub submit_status: &'static str,
    pub produce_block_status: &'static str,
    pub entries: Vec<MempoolEntryResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MempoolEntryResponse {
    pub tx_hash: String,
    pub from_address: String,
    pub to_address: String,
    pub amount_base_units: String,
    pub fee_base_units: String,
    pub nonce: u64,
    pub status: String,
    pub first_seen_at_utc: Option<String>,
    pub last_seen_at_utc: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PendingMempoolParseError {
    pub line: usize,
    pub message: String,
}

impl PendingMempoolParseError {
    fn new(line: usize, message: impl Into<String>) -> Self {
        Self {
            line,
            message: message.into(),
        }
    }
}

impl fmt::Display for PendingMempoolParseError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "line {}: {}", self.line, self.message)
    }
}

impl std::error::Error for PendingMempoolParseError {}

pub fn pending_mempool_entries_from_tsv(
    text: &str,
    expected_chain_id: &str,
) -> Result<Vec<MempoolEntryResponse>, PendingMempoolParseError> {
    let mut entries = Vec::new();
    for (line_index, raw_line) in text.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }
        entries.push(parse_pending_mempool_entry(
            line,
            line_index + 1,
            expected_chain_id,
        )?);
    }
    Ok(entries)
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
pub struct WalletStatusResponse {
    pub environment: &'static str,
    pub network: String,
    pub warning: &'static str,
    pub current_height: u64,
    pub latest_block_hash: String,
    pub state_root: String,
    pub account_count: usize,
    pub pending_transactions: usize,
    pub can_draft: bool,
    pub can_submit: bool,
    pub can_send: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletAccountListResponse {
    pub environment: &'static str,
    pub network: String,
    pub warning: &'static str,
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub accounts: Vec<AccountResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletBalanceResponse {
    pub environment: &'static str,
    pub network: String,
    pub warning: &'static str,
    pub address: String,
    pub balance_base_units: String,
    pub nonce: u64,
    pub height: u64,
    pub state_root: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletTransactionStatusResponse {
    pub environment: &'static str,
    pub network: String,
    pub warning: &'static str,
    pub tx_hash: String,
    pub status: String,
    pub block_height: u64,
    pub block_hash: String,
    pub transaction_index: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletTransferDraftPreviewRequest {
    pub chain_id: String,
    pub from_address: String,
    pub to_address: String,
    pub amount_base_units: u128,
    pub fee_base_units: u128,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletTransferDraftPreviewResponse {
    pub environment: &'static str,
    pub network: String,
    pub warning: &'static str,
    pub mutation: &'static str,
    pub validation: WalletDraftValidationResponse,
    pub draft: WalletTransferDraftResponse,
    pub balance: WalletDraftBalanceResponse,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletDraftValidationResponse {
    pub ok: bool,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletTransferDraftResponse {
    pub chain_id: String,
    pub from_address: String,
    pub to_address: String,
    pub amount_base_units: String,
    pub fee_base_units: String,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletDraftBalanceResponse {
    pub available_base_units: Option<String>,
    pub debit_base_units: Option<String>,
    pub remaining_base_units: Option<String>,
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

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NodeStatusResponse {
    pub environment: &'static str,
    pub service: &'static str,
    pub status: &'static str,
    pub mode: &'static str,
    pub source: &'static str,
    pub network: String,
    pub current_height: u64,
    pub latest_block_hash: String,
    pub state_root: String,
    pub stored_blocks: usize,
    pub pending_transactions: usize,
    pub wallet_submit_status: &'static str,
    pub block_production_status: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuditEventListResponse {
    pub environment: &'static str,
    pub network: String,
    pub limit: usize,
    pub next_cursor: Option<String>,
    pub audit_events: Vec<AuditEventResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AuditEventResponse {
    pub event_id: String,
    pub actor: &'static str,
    pub action: &'static str,
    pub resource_type: &'static str,
    pub resource_id: Option<String>,
    pub environment: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SnapshotListResponse {
    pub environment: &'static str,
    pub network: String,
    pub warning: &'static str,
    pub snapshots: Vec<SnapshotResponse>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SnapshotResponse {
    pub snapshot_name: String,
    pub snapshot_dir: String,
    pub current_height: u64,
    pub latest_block_hash: String,
    pub state_root: String,
    pub block_count: usize,
    pub transaction_count: usize,
    pub audit_event_count: usize,
    pub export_status: &'static str,
    pub import_status: &'static str,
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

fn iso_transaction(transaction: &TransactionResponse) -> XriqIsoTransaction {
    XriqIsoTransaction {
        tx_hash: transaction.tx_hash.clone(),
        confirmed_block_height: (transaction.status == "confirmed")
            .then_some(transaction.block_height),
        status: transaction.status.clone(),
        from_address: transaction.from_address.clone(),
        to_address: transaction.to_address.clone(),
        amount_base_units: transaction.amount_base_units.clone(),
        fee_base_units: transaction.fee_base_units.clone(),
        nonce: transaction.nonce,
    }
}

fn iso_account_history(history: &AccountHistoryResponse) -> XriqIsoAccountHistory {
    XriqIsoAccountHistory {
        address: history.address.clone(),
        transactions: history
            .transactions
            .iter()
            .map(|transaction| XriqIsoAccountTransaction {
                tx_hash: transaction.tx_hash.clone(),
                direction: transaction.direction.to_string(),
                block_height: transaction.block_height,
                amount_base_units: transaction.amount_base_units.clone(),
                fee_base_units: transaction.fee_base_units.clone(),
            })
            .collect(),
    }
}

fn statement_opening_balance(
    closing_balance_base_units: &str,
    transactions: &[AccountTransactionResponse],
) -> String {
    let Some(mut opening) = parse_base_units(closing_balance_base_units) else {
        return closing_balance_base_units.to_string();
    };

    for transaction in transactions {
        let Some(amount) = parse_base_units(&transaction.amount_base_units) else {
            return closing_balance_base_units.to_string();
        };
        let Some(fee) = parse_base_units(&transaction.fee_base_units) else {
            return closing_balance_base_units.to_string();
        };
        match transaction.direction {
            "sent" => {
                let Some(debit) = amount.checked_add(fee) else {
                    return closing_balance_base_units.to_string();
                };
                let Some(next_opening) = opening.checked_add(debit) else {
                    return closing_balance_base_units.to_string();
                };
                opening = next_opening;
            }
            "received" => {
                let Some(next_opening) = opening.checked_sub(amount) else {
                    return closing_balance_base_units.to_string();
                };
                opening = next_opening;
            }
            _ => {}
        }
    }

    opening.to_string()
}

fn parse_base_units(value: &str) -> Option<u128> {
    value.parse::<u128>().ok()
}

fn audit_event_response(event: &IndexedAuditEvent) -> AuditEventResponse {
    AuditEventResponse {
        event_id: event.event_id.clone(),
        actor: event.actor,
        action: event.action,
        resource_type: event.resource_type,
        resource_id: event.resource_id.clone(),
        environment: event.environment,
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

fn parse_pending_mempool_entry(
    line: &str,
    line_number: usize,
    expected_chain_id: &str,
) -> Result<MempoolEntryResponse, PendingMempoolParseError> {
    let parts = line.split('\t').collect::<Vec<_>>();
    if parts.len() != 11 {
        return Err(PendingMempoolParseError::new(
            line_number,
            "expected 11 tab-separated pending record fields",
        ));
    }
    if parts[0] != "xriq-pending-transaction-v1" {
        return Err(PendingMempoolParseError::new(
            line_number,
            "unsupported pending record version",
        ));
    }

    let tx_hash = parts[1];
    if !is_lower_hex(tx_hash, 64) {
        return Err(PendingMempoolParseError::new(
            line_number,
            "tx_hash must be 64 lowercase hex characters",
        ));
    }
    let version = parse_u16_field(parts[2], "version", line_number)?;
    let chain_id = parts[3];
    if chain_id != expected_chain_id {
        return Err(PendingMempoolParseError::new(
            line_number,
            format!("wrong chain_id: expected {expected_chain_id}, got {chain_id}"),
        ));
    }
    let from = Address::parse(parts[4]).map_err(|_| {
        PendingMempoolParseError::new(line_number, "from_address is not a valid devnet address")
    })?;
    let to = Address::parse(parts[5]).map_err(|_| {
        PendingMempoolParseError::new(line_number, "to_address is not a valid devnet address")
    })?;
    let amount = parse_amount_field(parts[6], "amount_base_units", line_number)?;
    let fee = parse_amount_field(parts[7], "fee_base_units", line_number)?;
    let nonce = parse_u64_field(parts[8], "nonce", line_number)?;
    let expires_at_height = match parts[9] {
        "null" => None,
        value => Some(parse_u64_field(value, "expires_at_height", line_number)?),
    };
    let signature = parse_hex_bytes(parts[10]).ok_or_else(|| {
        PendingMempoolParseError::new(line_number, "signature must be lowercase hex bytes")
    })?;

    let transaction = Transaction {
        version,
        chain_id: chain_id.to_string(),
        from: from.clone(),
        to: to.clone(),
        amount,
        fee,
        nonce,
        memo_hash: None,
        expires_at_height,
        signature: SignatureBytes::new(signature),
    };
    let computed_hash = hash_hex(transaction_hash(&transaction));
    if computed_hash != tx_hash {
        return Err(PendingMempoolParseError::new(
            line_number,
            "pending record hash does not match transaction fields",
        ));
    }

    Ok(MempoolEntryResponse {
        tx_hash: tx_hash.to_string(),
        from_address: from.to_string(),
        to_address: to.to_string(),
        amount_base_units: amount.base_units().to_string(),
        fee_base_units: fee.base_units().to_string(),
        nonce,
        status: "pending".to_string(),
        first_seen_at_utc: None,
        last_seen_at_utc: None,
    })
}

fn parse_u16_field(
    value: &str,
    field: &str,
    line_number: usize,
) -> Result<u16, PendingMempoolParseError> {
    value.parse::<u16>().map_err(|_| {
        PendingMempoolParseError::new(line_number, format!("{field} must be an integer"))
    })
}

fn parse_u64_field(
    value: &str,
    field: &str,
    line_number: usize,
) -> Result<u64, PendingMempoolParseError> {
    value.parse::<u64>().map_err(|_| {
        PendingMempoolParseError::new(line_number, format!("{field} must be an integer"))
    })
}

fn parse_amount_field(
    value: &str,
    field: &str,
    line_number: usize,
) -> Result<XriqAmount, PendingMempoolParseError> {
    value
        .parse::<u128>()
        .map(XriqAmount::from_base_units)
        .map_err(|_| {
            PendingMempoolParseError::new(line_number, format!("{field} must be base-unit integer"))
        })
}

fn parse_hex_bytes(value: &str) -> Option<Vec<u8>> {
    if !value.len().is_multiple_of(2) || !is_lower_hex(value, value.len()) {
        return None;
    }
    let mut bytes = Vec::with_capacity(value.len() / 2);
    for pair in value.as_bytes().chunks_exact(2) {
        let high = hex_nibble(pair[0])?;
        let low = hex_nibble(pair[1])?;
        bytes.push((high << 4) | low);
    }
    Some(bytes)
}

fn is_lower_hex(value: &str, expected_len: usize) -> bool {
    value.len() == expected_len
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn hex_nibble(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        _ => None,
    }
}

fn hash_hex(hash: Hash32) -> String {
    let mut output = String::with_capacity(64);
    for byte in hash.as_bytes() {
        write!(&mut output, "{byte:02x}").expect("write to String");
    }
    output
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
        ApiError::SnapshotNotFound => {
            api_error_response(404, "snapshot_not_found", "XRIQ snapshot not found")
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

fn wallet_draft_preview_request_from_query(
    query: Option<&str>,
    default_chain_id: &str,
) -> Result<WalletTransferDraftPreviewRequest, String> {
    let chain_id = query_param(query, "chain_id")
        .unwrap_or(default_chain_id)
        .to_string();
    if chain_id != default_chain_id {
        return Err(format!("chain_id must be {default_chain_id}"));
    }

    let from_address = required_query_param_any(query, &["from_address", "from"])?;
    let to_address = required_query_param_any(query, &["to_address", "to"])?;
    Address::parse(from_address).map_err(|error| {
        format!("invalid from_address: {from_address}; expected private-devnet address ({error:?})")
    })?;
    Address::parse(to_address).map_err(|error| {
        format!("invalid to_address: {to_address}; expected private-devnet address ({error:?})")
    })?;

    Ok(WalletTransferDraftPreviewRequest {
        chain_id,
        from_address: from_address.to_string(),
        to_address: to_address.to_string(),
        amount_base_units: parse_u128_query(
            required_query_param_any(query, &["amount_base_units", "amount"])?,
            "amount_base_units",
        )?,
        fee_base_units: parse_u128_query(
            required_query_param_any(query, &["fee_base_units", "fee"])?,
            "fee_base_units",
        )?,
        nonce: parse_u64_query(required_query_param_any(query, &["nonce"])?, "nonce")?,
        expires_at_height: query_param(query, "expires_at_height")
            .map(|value| parse_u64_query(value, "expires_at_height"))
            .transpose()?,
    })
}

fn required_query_param_any<'a>(query: Option<&'a str>, keys: &[&str]) -> Result<&'a str, String> {
    keys.iter()
        .find_map(|key| query_param(query, key))
        .ok_or_else(|| format!("missing required query parameter: {}", keys[0]))
}

fn parse_u128_query(value: &str, key: &str) -> Result<u128, String> {
    value
        .parse::<u128>()
        .map_err(|_| format!("invalid {key}: {value}"))
}

fn parse_u64_query(value: &str, key: &str) -> Result<u64, String> {
    value
        .parse::<u64>()
        .map_err(|_| format!("invalid {key}: {value}"))
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

fn render_mempool_json(response: &MempoolResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(response.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"current_height\": {},",
        response.current_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"pending_count\": {},",
        response.pending_count
    )
    .expect("write to String");
    writeln!(&mut output, "  \"limit\": {},", response.limit).expect("write to String");
    writeln!(
        &mut output,
        "  \"next_cursor\": {},",
        json_optional_string(response.next_cursor.as_deref())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"inspect_status\": {},",
        json_string(response.inspect_status)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"submit_status\": {},",
        json_string(response.submit_status)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"produce_block_status\": {},",
        json_string(response.produce_block_status)
    )
    .expect("write to String");
    output.push_str("  \"entries\": [");
    for (index, entry) in response.entries.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_mempool_entry_json_inline(entry, 4));
    }
    if !response.entries.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
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

fn render_wallet_status_json(response: &WalletStatusResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(response.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"current_height\": {},",
        response.current_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"latest_block_hash\": {},",
        json_string(&response.latest_block_hash)
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
        "  \"account_count\": {},",
        response.account_count
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"pending_transactions\": {},",
        response.pending_transactions
    )
    .expect("write to String");
    writeln!(&mut output, "  \"capabilities\": {{").expect("write to String");
    writeln!(&mut output, "    \"draft\": {},", response.can_draft).expect("write to String");
    writeln!(&mut output, "    \"submit\": {},", response.can_submit).expect("write to String");
    writeln!(&mut output, "    \"send\": {}", response.can_send).expect("write to String");
    output.push_str("  }\n}");
    output
}

fn render_wallet_account_list_json(response: &WalletAccountListResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(response.warning)
    )
    .expect("write to String");
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

fn render_wallet_balance_json(response: &WalletBalanceResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(response.warning)
    )
    .expect("write to String");
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
    write!(
        &mut output,
        "  \"state_root\": {}\n}}",
        json_string(&response.state_root)
    )
    .expect("write to String");
    output
}

fn render_wallet_transaction_status_json(response: &WalletTransactionStatusResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(response.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"tx_hash\": {},",
        json_string(&response.tx_hash)
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
    write!(
        &mut output,
        "  \"transaction_index\": {}\n}}",
        response.transaction_index
    )
    .expect("write to String");
    output
}

fn render_wallet_transfer_draft_preview_json(
    response: &WalletTransferDraftPreviewResponse,
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(response.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"mutation\": {},",
        json_string(response.mutation)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"validation\": {{").expect("write to String");
    writeln!(&mut output, "    \"ok\": {},", response.validation.ok).expect("write to String");
    output.push_str("    \"errors\": [");
    for (index, error) in response.validation.errors.iter().enumerate() {
        if index > 0 {
            output.push_str(", ");
        }
        output.push_str(&json_string(error));
    }
    output.push_str("]\n  },\n");
    output.push_str("  \"draft\": ");
    output.push_str(&render_wallet_transfer_draft_json_inline(
        &response.draft,
        2,
    ));
    output.push_str(",\n  \"balance\": ");
    output.push_str(&render_wallet_draft_balance_json_inline(
        &response.balance,
        2,
    ));
    output.push_str("\n}");
    output
}

fn render_iso_payment_initiation_preview_json(response: &PaymentInitiationPreview) -> String {
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
        "  \"not_certified\": {},",
        response.not_certified
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"mapping_version\": {},",
        json_string(response.mapping_version)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_type\": {},",
        json_string(response.message_type)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_id\": {},",
        json_string(&response.message_id)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"source_tx_hash\": {},",
        json_string(&response.source_tx_hash)
    )
    .expect("write to String");
    output.push_str("  \"xriq\": ");
    output.push_str(&render_iso_transfer_fields_inline(&response.xriq, 2));
    output.push_str(",\n  \"iso20022_aligned\": ");
    output.push_str(&render_iso_payment_initiation_aligned_inline(
        &response.iso20022_aligned,
        2,
    ));
    output.push_str(",\n  \"unsupported_fields\": ");
    output.push_str(&render_string_array_inline(&response.unsupported_fields, 2));
    output.push_str("\n}");
    output
}

fn render_iso_payment_status_json(response: &PaymentStatusPreview) -> String {
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
        "  \"not_certified\": {},",
        response.not_certified
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"mapping_version\": {},",
        json_string(response.mapping_version)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_type\": {},",
        json_string(response.message_type)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_id\": {},",
        json_string(&response.message_id)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"source_tx_hash\": {},",
        json_string(&response.source_tx_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"xriq_status\": {},",
        json_string(&response.xriq_status)
    )
    .expect("write to String");
    output.push_str("  \"iso20022_aligned\": ");
    output.push_str(&render_iso_payment_status_aligned_inline(
        &response.iso20022_aligned,
        2,
    ));
    output.push_str(",\n  \"unsupported_fields\": ");
    output.push_str(&render_string_array_inline(&response.unsupported_fields, 2));
    output.push_str("\n}");
    output
}

fn render_iso_account_statement_json(response: &AccountStatementPreview) -> String {
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
        "  \"not_certified\": {},",
        response.not_certified
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"mapping_version\": {},",
        json_string(response.mapping_version)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_type\": {},",
        json_string(response.message_type)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"message_id\": {},",
        json_string(&response.message_id)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"account_address\": {},",
        json_string(&response.account_address)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"from\": {},", json_string(&response.from)).expect("write to String");
    writeln!(&mut output, "  \"to\": {},", json_string(&response.to)).expect("write to String");
    writeln!(
        &mut output,
        "  \"opening_balance_base_units\": {},",
        json_string(&response.opening_balance_base_units)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"closing_balance_base_units\": {},",
        json_string(&response.closing_balance_base_units)
    )
    .expect("write to String");
    output.push_str("  \"entries\": [");
    for (index, entry) in response.entries.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_iso_account_statement_entry_inline(entry, 4));
    }
    if !response.entries.is_empty() {
        output.push('\n');
    }
    output.push_str("  ],\n  \"unsupported_fields\": ");
    output.push_str(&render_string_array_inline(&response.unsupported_fields, 2));
    output.push_str("\n}");
    output
}

fn render_indexer_status_json(response: &IndexerStatusResponse) -> String {
    render_indexer_status_json_inline(response, 0)
}

fn render_node_status_json(response: &NodeStatusResponse) -> String {
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
        "  \"service\": {},",
        json_string(response.service)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"status\": {},",
        json_string(response.status)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"mode\": {},", json_string(response.mode)).expect("write to String");
    writeln!(
        &mut output,
        "  \"source\": {},",
        json_string(response.source)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"network\": {},",
        json_string(&response.network)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"current_height\": {},",
        response.current_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"latest_block_hash\": {},",
        json_string(&response.latest_block_hash)
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
        "  \"stored_blocks\": {},",
        response.stored_blocks
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"pending_transactions\": {},",
        response.pending_transactions
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"wallet_submit_status\": {},",
        json_string(response.wallet_submit_status)
    )
    .expect("write to String");
    write!(
        &mut output,
        "  \"block_production_status\": {}\n}}",
        json_string(response.block_production_status)
    )
    .expect("write to String");
    output
}

fn render_audit_event_list_json(response: &AuditEventListResponse) -> String {
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
    output.push_str("  \"audit_events\": [");
    for (index, event) in response.audit_events.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_audit_event_json_inline(event, 4));
    }
    if !response.audit_events.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_snapshot_list_json(response: &SnapshotListResponse) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_response_header(&mut output, response.environment, &response.network);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(response.warning)
    )
    .expect("write to String");
    output.push_str("  \"snapshots\": [");
    for (index, snapshot) in response.snapshots.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&render_snapshot_json_inline(snapshot, 4));
    }
    if !response.snapshots.is_empty() {
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_snapshot_json(response: &SnapshotResponse) -> String {
    render_snapshot_json_inline(response, 0)
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

fn render_mempool_entry_json_inline(entry: &MempoolEntryResponse, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"tx_hash\": {},\n{nested}\"from_address\": {},\n{nested}\"to_address\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {},\n{nested}\"nonce\": {},\n{nested}\"status\": {},\n{nested}\"first_seen_at_utc\": {},\n{nested}\"last_seen_at_utc\": {}\n{spaces}}}",
        json_string(&entry.tx_hash),
        json_string(&entry.from_address),
        json_string(&entry.to_address),
        json_string(&entry.amount_base_units),
        json_string(&entry.fee_base_units),
        entry.nonce,
        json_string(&entry.status),
        json_optional_string(entry.first_seen_at_utc.as_deref()),
        json_optional_string(entry.last_seen_at_utc.as_deref())
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

fn render_audit_event_json_inline(event: &AuditEventResponse, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"event_id\": {},\n{nested}\"actor\": {},\n{nested}\"action\": {},\n{nested}\"resource_type\": {},\n{nested}\"resource_id\": {},\n{nested}\"environment\": {}\n{spaces}}}",
        json_string(&event.event_id),
        json_string(event.actor),
        json_string(event.action),
        json_string(event.resource_type),
        json_optional_string(event.resource_id.as_deref()),
        json_string(event.environment)
    )
}

fn render_snapshot_json_inline(snapshot: &SnapshotResponse, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"snapshot_name\": {},\n{nested}\"snapshot_dir\": {},\n{nested}\"current_height\": {},\n{nested}\"latest_block_hash\": {},\n{nested}\"state_root\": {},\n{nested}\"block_count\": {},\n{nested}\"transaction_count\": {},\n{nested}\"audit_event_count\": {},\n{nested}\"export_status\": {},\n{nested}\"import_status\": {}\n{spaces}}}",
        json_string(&snapshot.snapshot_name),
        json_string(&snapshot.snapshot_dir),
        snapshot.current_height,
        json_string(&snapshot.latest_block_hash),
        json_string(&snapshot.state_root),
        snapshot.block_count,
        snapshot.transaction_count,
        snapshot.audit_event_count,
        json_string(snapshot.export_status),
        json_string(snapshot.import_status)
    )
}

fn render_wallet_transfer_draft_json_inline(
    draft: &WalletTransferDraftResponse,
    indent: usize,
) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"chain_id\": {},\n{nested}\"from_address\": {},\n{nested}\"to_address\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {},\n{nested}\"nonce\": {},\n{nested}\"expires_at_height\": {}\n{spaces}}}",
        json_string(&draft.chain_id),
        json_string(&draft.from_address),
        json_string(&draft.to_address),
        json_string(&draft.amount_base_units),
        json_string(&draft.fee_base_units),
        draft.nonce,
        json_optional_u64(draft.expires_at_height)
    )
}

fn render_wallet_draft_balance_json_inline(
    balance: &WalletDraftBalanceResponse,
    indent: usize,
) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"available_base_units\": {},\n{nested}\"debit_base_units\": {},\n{nested}\"remaining_base_units\": {}\n{spaces}}}",
        json_optional_string(balance.available_base_units.as_deref()),
        json_optional_string(balance.debit_base_units.as_deref()),
        json_optional_string(balance.remaining_base_units.as_deref())
    )
}

fn render_iso_transfer_fields_inline(fields: &XriqTransferFields, indent: usize) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"from_address\": {},\n{nested}\"to_address\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {},\n{nested}\"nonce\": {}\n{spaces}}}",
        json_string(&fields.from_address),
        json_string(&fields.to_address),
        json_string(&fields.amount_base_units),
        json_string(&fields.fee_base_units),
        fields.nonce
    )
}

fn render_iso_payment_initiation_aligned_inline(
    fields: &PaymentInitiationAligned,
    indent: usize,
) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"creditor_account\": {},\n{nested}\"debtor_account\": {},\n{nested}\"instructed_amount\": {},\n{nested}\"currency\": {},\n{nested}\"end_to_end_id\": {}\n{spaces}}}",
        json_string(&fields.creditor_account),
        json_string(&fields.debtor_account),
        json_string(&fields.instructed_amount),
        json_string(fields.currency),
        json_string(&fields.end_to_end_id)
    )
}

fn render_iso_payment_status_aligned_inline(
    status: &PaymentStatusAligned,
    indent: usize,
) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"original_end_to_end_id\": {},\n{nested}\"transaction_status\": {},\n{nested}\"status_reason\": {},\n{nested}\"confirmed_block_height\": {}\n{spaces}}}",
        json_string(&status.original_end_to_end_id),
        json_string(status.transaction_status),
        json_string(status.status_reason),
        json_optional_u64(status.confirmed_block_height)
    )
}

fn render_iso_account_statement_entry_inline(
    entry: &AccountStatementEntry,
    indent: usize,
) -> String {
    let spaces = " ".repeat(indent);
    let nested = " ".repeat(indent + 2);
    format!(
        "{spaces}{{\n{nested}\"tx_hash\": {},\n{nested}\"direction\": {},\n{nested}\"amount_base_units\": {},\n{nested}\"fee_base_units\": {},\n{nested}\"status\": {},\n{nested}\"block_height\": {}\n{spaces}}}",
        json_string(&entry.tx_hash),
        json_string(entry.direction),
        json_string(&entry.amount_base_units),
        json_string(&entry.fee_base_units),
        json_string(entry.status),
        entry.block_height
    )
}

fn render_string_array_inline(values: &[&str], indent: usize) -> String {
    let spaces = " ".repeat(indent);
    if values.is_empty() {
        return "[]".to_string();
    }

    let nested = " ".repeat(indent + 2);
    let mut output = String::from("[");
    for (index, value) in values.iter().enumerate() {
        if index > 0 {
            output.push(',');
        }
        output.push('\n');
        output.push_str(&nested);
        output.push_str(&json_string(value));
    }
    output.push('\n');
    output.push_str(&spaces);
    output.push(']');
    output
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
    use xriq_crypto::{test_only_signature_for_hash, transaction_signing_hash};
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

    fn service_with_pending_mempool() -> XriqApiService {
        let snapshot = snapshot();
        let pending_entries =
            pending_mempool_entries_from_tsv(&pending_record(), &snapshot.chain_id).unwrap();
        XriqApiService::new(snapshot).with_pending_mempool_entries(pending_entries)
    }

    fn pending_record() -> String {
        let mut transaction = Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from: Address::parse("xriqdev1alice00000000000").unwrap(),
            to: Address::parse("xriqdev1carol00000000000").unwrap(),
            amount: XriqAmount::from_base_units(10),
            fee: XriqAmount::from_base_units(2),
            nonce: 1,
            memo_hash: None,
            expires_at_height: Some(100),
            signature: SignatureBytes::new(Vec::new()),
        };
        transaction.signature =
            test_only_signature_for_hash(transaction_signing_hash(&transaction));
        [
            "xriq-pending-transaction-v1".to_string(),
            hash_hex(transaction_hash(&transaction)),
            transaction.version.to_string(),
            transaction.chain_id.clone(),
            transaction.from.to_string(),
            transaction.to.to_string(),
            transaction.amount.base_units().to_string(),
            transaction.fee.base_units().to_string(),
            transaction.nonce.to_string(),
            transaction.expires_at_height.unwrap().to_string(),
            bytes_hex(transaction.signature.as_slice()),
        ]
        .join("\t")
    }

    fn bytes_hex(bytes: &[u8]) -> String {
        let mut output = String::with_capacity(bytes.len() * 2);
        for byte in bytes {
            write!(&mut output, "{byte:02x}").expect("write to String");
        }
        output
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

        let overview_with_pending = service_with_pending_mempool().explorer_overview();
        assert_eq!(overview_with_pending.chain.pending_transactions, 1);
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
    fn mempool_status_is_read_only_for_indexed_snapshot() {
        let api = service();

        let mempool = api.mempool(5);
        assert_eq!(mempool.environment, API_ENVIRONMENT);
        assert_eq!(mempool.warning, MEMPOOL_READONLY_WARNING);
        assert_eq!(mempool.current_height, 1);
        assert_eq!(mempool.pending_count, 0);
        assert_eq!(mempool.limit, 5);
        assert_eq!(mempool.next_cursor, None);
        assert_eq!(mempool.inspect_status, "enabled");
        assert_eq!(mempool.submit_status, "disabled");
        assert_eq!(mempool.produce_block_status, "disabled");
        assert!(mempool.entries.is_empty());
    }

    #[test]
    fn mempool_status_can_read_durable_pending_file_entries_without_mutation() {
        let api = service_with_pending_mempool();

        let mempool = api.mempool(5);
        assert_eq!(mempool.warning, MEMPOOL_READONLY_WARNING);
        assert_eq!(mempool.pending_count, 1);
        assert_eq!(mempool.entries.len(), 1);
        assert_eq!(mempool.entries[0].from_address, "xriqdev1alice00000000000");
        assert_eq!(mempool.entries[0].to_address, "xriqdev1carol00000000000");
        assert_eq!(mempool.entries[0].amount_base_units, "10");
        assert_eq!(mempool.entries[0].fee_base_units, "2");
        assert_eq!(mempool.entries[0].nonce, 1);
        assert_eq!(mempool.entries[0].status, "pending");
        assert_eq!(mempool.submit_status, "disabled");
        assert_eq!(mempool.produce_block_status, "disabled");
    }

    #[test]
    fn pending_mempool_parser_rejects_wrong_chain_or_hash() {
        let wrong_chain = pending_record().replace("xriq-devnet", "xriq-other");
        let wrong_chain_error =
            pending_mempool_entries_from_tsv(&wrong_chain, "xriq-devnet").unwrap_err();
        assert!(wrong_chain_error.message.contains("wrong chain_id"));

        let valid_record = pending_record();
        let valid_hash = valid_record.split('\t').nth(1).unwrap().to_string();
        let wrong_hash = valid_record.replacen(&valid_hash, &"0".repeat(64), 1);
        let wrong_hash_error =
            pending_mempool_entries_from_tsv(&wrong_hash, "xriq-devnet").unwrap_err();
        assert!(wrong_hash_error.message.contains("hash does not match"));
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
    fn wallet_preview_api_is_read_only_and_deterministic() {
        let api = service();

        let status = api.wallet_status();
        assert_eq!(status.environment, API_ENVIRONMENT);
        assert_eq!(status.warning, WALLET_PREVIEW_WARNING);
        assert!(status.can_draft);
        assert!(!status.can_submit);
        assert!(!status.can_send);

        let accounts = api.wallet_accounts(25);
        assert_eq!(accounts.warning, WALLET_PREVIEW_WARNING);
        assert_eq!(accounts.accounts.len(), 2);

        let balance = api.wallet_balance("xriqdev1alice00000000000").unwrap();
        assert_eq!(balance.balance_base_units, "73");
        assert_eq!(balance.nonce, 1);

        let tx_status = api.wallet_transaction_status(TX_HASH).unwrap();
        assert_eq!(tx_status.status, "confirmed");
        assert_eq!(tx_status.block_height, 1);

        let preview = api.wallet_transfer_draft_preview(WalletTransferDraftPreviewRequest {
            chain_id: "xriq-devnet".to_string(),
            from_address: "xriqdev1alice00000000000".to_string(),
            to_address: "xriqdev1bobbb00000000000".to_string(),
            amount_base_units: 25,
            fee_base_units: 2,
            nonce: 1,
            expires_at_height: Some(100),
        });
        assert_eq!(preview.warning, WALLET_PREVIEW_WARNING);
        assert_eq!(preview.mutation, "none");
        assert!(preview.validation.ok);
        assert_eq!(preview.balance.available_base_units.as_deref(), Some("73"));
        assert_eq!(preview.balance.debit_base_units.as_deref(), Some("27"));
        assert_eq!(preview.balance.remaining_base_units.as_deref(), Some("46"));

        let invalid = api.wallet_transfer_draft_preview(WalletTransferDraftPreviewRequest {
            chain_id: "xriq-devnet".to_string(),
            from_address: "xriqdev1alice00000000000".to_string(),
            to_address: "xriqdev1alice00000000000".to_string(),
            amount_base_units: 0,
            fee_base_units: 1,
            nonce: 0,
            expires_at_height: Some(1),
        });
        assert!(!invalid.validation.ok);
        assert!(invalid
            .validation
            .errors
            .iter()
            .any(|error| error.contains("sender and recipient")));
        assert!(invalid
            .validation
            .errors
            .iter()
            .any(|error| error.contains("fee must be at least")));
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
    fn admin_node_status_is_read_only_and_snapshot_backed() {
        let status = service().admin_node_status();

        assert_eq!(status.environment, API_ENVIRONMENT);
        assert_eq!(status.service, API_SERVICE);
        assert_eq!(status.status, "healthy");
        assert_eq!(status.mode, "serve-readonly");
        assert_eq!(status.source, "indexed-chain-snapshot");
        assert_eq!(status.current_height, 1);
        assert_eq!(status.stored_blocks, 1);
        assert_eq!(status.pending_transactions, 0);
        assert_eq!(status.wallet_submit_status, "disabled");
        assert_eq!(status.block_production_status, "disabled");

        let status_with_pending = service_with_pending_mempool().admin_node_status();
        assert_eq!(status_with_pending.pending_transactions, 1);
        assert_eq!(status_with_pending.wallet_submit_status, "disabled");
        assert_eq!(status_with_pending.block_production_status, "disabled");
    }

    #[test]
    fn admin_audit_events_and_snapshots_are_read_only() {
        let api = service();

        let audit = api.admin_audit_events(10);
        assert_eq!(audit.environment, API_ENVIRONMENT);
        assert_eq!(audit.audit_events.len(), 1);
        assert_eq!(audit.audit_events[0].event_id, "index-block:1");
        assert_eq!(audit.audit_events[0].actor, INDEXER_SERVICE);
        assert_eq!(audit.audit_events[0].action, "index_block");
        assert_eq!(
            audit.audit_events[0].resource_id.as_deref(),
            Some(BLOCK_HASH)
        );

        let snapshots = api.snapshots();
        assert_eq!(snapshots.warning, SNAPSHOT_READONLY_WARNING);
        assert_eq!(snapshots.snapshots.len(), 1);
        assert_eq!(
            snapshots.snapshots[0].snapshot_name,
            "current-indexed-chain"
        );
        assert_eq!(snapshots.snapshots[0].block_count, 1);
        assert_eq!(snapshots.snapshots[0].transaction_count, 1);
        assert_eq!(snapshots.snapshots[0].audit_event_count, 1);
        assert_eq!(snapshots.snapshots[0].export_status, "disabled");
        assert_eq!(snapshots.snapshots[0].import_status, "disabled");
        assert_eq!(
            api.snapshot_detail("missing-snapshot"),
            Err(ApiError::SnapshotNotFound)
        );
    }

    #[test]
    fn iso20022_preview_methods_map_private_devnet_data_without_certification_claims() {
        let api = service();

        let initiation = api.iso20022_payment_initiation_preview(TX_HASH).unwrap();
        assert_eq!(initiation.environment, API_ENVIRONMENT);
        assert!(initiation.not_certified);
        assert_eq!(initiation.message_type, "payment_initiation_preview");
        assert_eq!(initiation.source_tx_hash, TX_HASH);
        assert_eq!(initiation.iso20022_aligned.currency, "XRIQ-DEV");
        assert_eq!(initiation.iso20022_aligned.end_to_end_id, TX_HASH);

        let status = api.iso20022_transaction_status(TX_HASH).unwrap();
        assert_eq!(status.message_type, "payment_status_preview");
        assert_eq!(status.iso20022_aligned.transaction_status, "ACSC");
        assert_eq!(status.iso20022_aligned.confirmed_block_height, Some(1));

        let statement = api
            .iso20022_account_statement(
                "xriqdev1alice00000000000",
                "1970-01-01T00:00:00Z",
                "1970-01-01T00:00:02Z",
            )
            .unwrap();
        assert_eq!(statement.message_type, "account_statement_preview");
        assert_eq!(statement.opening_balance_base_units, "100");
        assert_eq!(statement.closing_balance_base_units, "73");
        assert_eq!(statement.entries.len(), 1);
        assert_eq!(statement.entries[0].direction, "debit");
        assert_eq!(statement.entries[0].status, "confirmed");
        assert!(!statement.unsupported_fields.is_empty());

        assert_eq!(
            api.iso20022_transaction_status(&"9".repeat(64)),
            Err(ApiError::TransactionNotFound)
        );
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

        let node_status = product_api_http_response(&api, "GET", "/api/v1/admin/node/status");
        assert_eq!(node_status.status_code, 200);
        assert!(node_status.body.contains("\"service\": \"xriq-api\""));
        assert!(node_status.body.contains("\"mode\": \"serve-readonly\""));
        assert!(node_status
            .body
            .contains("\"block_production_status\": \"disabled\""));

        let mempool = product_api_http_response(&api, "GET", "/api/v1/mempool?limit=5");
        assert_eq!(mempool.status_code, 200);
        assert!(mempool.body.contains(MEMPOOL_READONLY_WARNING));
        assert!(mempool.body.contains("\"pending_count\": 0"));
        assert!(mempool.body.contains("\"submit_status\": \"disabled\""));
        assert!(mempool
            .body
            .contains("\"produce_block_status\": \"disabled\""));

        let pending_api = service_with_pending_mempool();
        let pending_mempool =
            product_api_http_response(&pending_api, "GET", "/api/v1/mempool?limit=5");
        assert_eq!(pending_mempool.status_code, 200);
        assert!(pending_mempool.body.contains("\"pending_count\": 1"));
        assert!(pending_mempool.body.contains("\"status\": \"pending\""));
        assert!(pending_mempool.body.contains("xriqdev1carol00000000000"));

        let audit = product_api_http_response(&api, "GET", "/api/v1/admin/audit-events?limit=5");
        assert_eq!(audit.status_code, 200);
        assert!(audit.body.contains("\"audit_events\""));
        assert!(audit.body.contains("\"action\": \"index_block\""));

        let snapshots = product_api_http_response(&api, "GET", "/api/v1/snapshots");
        assert_eq!(snapshots.status_code, 200);
        assert!(snapshots.body.contains(SNAPSHOT_READONLY_WARNING));
        assert!(snapshots
            .body
            .contains("\"snapshot_name\": \"current-indexed-chain\""));
        assert!(snapshots.body.contains("\"export_status\": \"disabled\""));

        let snapshot_detail =
            product_api_http_response(&api, "GET", "/api/v1/snapshots/current-indexed-chain");
        assert_eq!(snapshot_detail.status_code, 200);
        assert!(snapshot_detail
            .body
            .contains("\"import_status\": \"disabled\""));

        let wallet_status = product_api_http_response(&api, "GET", "/api/v1/wallet/status");
        assert_eq!(wallet_status.status_code, 200);
        assert!(wallet_status.body.contains(WALLET_PREVIEW_WARNING));
        assert!(wallet_status.body.contains("\"submit\": false"));

        let wallet_accounts =
            product_api_http_response(&api, "GET", "/api/v1/wallet/accounts?limit=5");
        assert_eq!(wallet_accounts.status_code, 200);
        assert!(wallet_accounts.body.contains("\"accounts\""));

        let wallet_balance = product_api_http_response(
            &api,
            "GET",
            "/api/v1/wallet/accounts/xriqdev1alice00000000000/balance",
        );
        assert_eq!(wallet_balance.status_code, 200);
        assert!(wallet_balance
            .body
            .contains("\"balance_base_units\": \"73\""));

        let wallet_history = product_api_http_response(
            &api,
            "GET",
            "/api/v1/wallet/accounts/xriqdev1alice00000000000/history?limit=5",
        );
        assert_eq!(wallet_history.status_code, 200);
        assert!(wallet_history.body.contains("\"direction\": \"sent\""));

        let wallet_tx_status = product_api_http_response(
            &api,
            "GET",
            &format!("/api/v1/wallet/transactions/{TX_HASH}/status"),
        );
        assert_eq!(wallet_tx_status.status_code, 200);
        assert!(wallet_tx_status.body.contains("\"status\": \"confirmed\""));

        let draft_preview = product_api_http_response(
            &api,
            "GET",
            "/api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000&to_address=xriqdev1bobbb00000000000&amount_base_units=25&fee_base_units=2&nonce=1&expires_at_height=100",
        );
        assert_eq!(draft_preview.status_code, 200);
        assert!(draft_preview.body.contains("\"mutation\": \"none\""));
        assert!(draft_preview.body.contains("\"ok\": true"));
        assert!(draft_preview
            .body
            .contains("\"remaining_base_units\": \"46\""));

        let iso_initiation = product_api_http_response(
            &api,
            "GET",
            &format!("/api/v1/iso20022/payment-initiation/preview?tx_hash={TX_HASH}"),
        );
        assert_eq!(iso_initiation.status_code, 200);
        assert!(iso_initiation
            .body
            .contains("\"message_type\": \"payment_initiation_preview\""));
        assert!(iso_initiation.body.contains("\"not_certified\": true"));
        assert!(iso_initiation.body.contains("\"currency\": \"XRIQ-DEV\""));

        let iso_status = product_api_http_response(
            &api,
            "GET",
            &format!("/api/v1/iso20022/transactions/{TX_HASH}/status"),
        );
        assert_eq!(iso_status.status_code, 200);
        assert!(iso_status.body.contains("\"transaction_status\": \"ACSC\""));
        assert!(iso_status.body.contains("\"confirmed_block_height\": 1"));

        let iso_statement = product_api_http_response(
            &api,
            "GET",
            "/api/v1/iso20022/accounts/xriqdev1alice00000000000/statement?from=1970-01-01T00:00:00Z&to=1970-01-01T00:00:02Z",
        );
        assert_eq!(iso_statement.status_code, 200);
        assert!(iso_statement
            .body
            .contains("\"message_type\": \"account_statement_preview\""));
        assert!(iso_statement
            .body
            .contains("\"opening_balance_base_units\": \"100\""));
        assert!(iso_statement.body.contains("\"direction\": \"debit\""));
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

        let bad_draft = product_api_http_response(
            &api,
            "GET",
            "/api/v1/wallet/transfers/draft-preview?from_address=xriqdev1alice00000000000",
        );
        assert_eq!(bad_draft.status_code, 400);
        assert!(bad_draft
            .body
            .contains("missing required query parameter: to_address"));

        let bad_iso =
            product_api_http_response(&api, "GET", "/api/v1/iso20022/payment-initiation/preview");
        assert_eq!(bad_iso.status_code, 400);
        assert!(bad_iso
            .body
            .contains("missing required query parameter: tx_hash"));

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
