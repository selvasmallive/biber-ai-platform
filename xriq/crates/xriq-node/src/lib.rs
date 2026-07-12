//! Minimal local node loop for the XRIQ private devnet.

use std::{
    fmt::{self, Write as _},
    fs,
    io::{self, Read, Write},
    net::{TcpListener, TcpStream},
    path::Path,
    time::Duration,
};

use xriq_consensus::{BlockProductionError, BlockProductionInput, SingleAuthorityProducer};
use xriq_core::{
    Address, AddressError, Block, BlockHeader, BlockValidationError, Environment, GenesisConfig,
    GenesisConfigError, Hash32, ParentHeaderView, SignatureBytes, Transaction,
    TransactionValidationContext, TransactionValidationError, XriqAmount,
    PUBLIC_TESTNET_FAUCET_ADDRESS, PUBLIC_TESTNET_FAUCET_DRIP_BASE_UNITS,
    PUBLIC_TESTNET_FAUCET_MAX_BALANCE_BASE_UNITS,
};
use xriq_crypto::{
    account_state_root, block_header_signing_hash, test_only_signature_for_hash, transaction_hash,
    transaction_signing_hash, transactions_root as canonical_transactions_root,
    SignatureVerificationError, TestOnlySignatureVerifier,
};
use xriq_explorer::{
    render_account_detail, render_account_transactions, render_accounts, render_block_detail,
    render_latest_blocks, render_latest_transactions, render_mempool, render_overview,
    ExplorerAccountDetail, ExplorerAccountTransaction, ExplorerBlockDetail, ExplorerBlockSummary,
    ExplorerConfirmedTransaction, ExplorerError, ExplorerMempoolDetail, ExplorerOverview,
    ExplorerService,
};
use xriq_ledger::{LedgerError, LedgerState};
use xriq_mempool::{Mempool, MempoolConfig, MempoolError};
use xriq_rpc::RpcService;
use xriq_storage::{ChainStore, FileChainStore, StorageError, StoredBlock};

pub const PRIVATE_DEVNET_RUNNER_WARNING: &str = "private-devnet-only-no-public-token";
pub const PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION: &str = "xriq-private-devnet-snapshot-v1";
const SNAPSHOT_MANIFEST_FILE: &str = "manifest.json";
const SNAPSHOT_CHAIN_FILE: &str = "chain.bin";
const SNAPSHOT_PENDING_FILE: &str = "pending.tsv";

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

/// Result of importing peer-encoded blocks into a follower node.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct PeerSyncOutcome {
    pub applied: usize,
    pub current_height: u64,
    pub latest_block_hash: Hash32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NodeStatus {
    pub warning: &'static str,
    pub chain_id: String,
    pub current_height: u64,
    pub latest_block_hash: Hash32,
    pub state_root: Hash32,
    pub pending_transactions: usize,
    pub stored_blocks: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetChainCheckStatus {
    pub verified: bool,
    pub status: NodeStatus,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetSnapshotStatus {
    pub snapshot_dir: String,
    pub chain_file: String,
    pub pending_file: Option<String>,
    pub status: NodeStatus,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetSnapshotSummary {
    pub snapshot_name: String,
    pub snapshot_dir: String,
    pub chain_file: String,
    pub pending_file: Option<String>,
    pub status: NodeStatus,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetSnapshotCheckStatus {
    pub verified: bool,
    pub snapshot: PrivateDevnetSnapshotSummary,
    pub replayed_status: NodeStatus,
    pub mismatches: Vec<String>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetHttpServerConfig {
    pub bind: String,
    pub chain_file: String,
    pub pending_file: Option<String>,
    pub snapshot_root: Option<String>,
    pub alice_balance: Option<XriqAmount>,
    pub allow_transaction_submission: bool,
    /// Optional path to a peers file this node advertises at
    /// `GET /v1/peer/peers` so followers can discover other peers.
    pub peers_file: Option<String>,
    /// Optional seed from which this node derives its stable `node_id`,
    /// reported in the `GET /v1/peer/identity` handshake.
    pub node_seed: Option<String>,
    /// When true this node's peer endpoints serve the public testnet genesis
    /// (`--network testnet`) instead of the devnet genesis.
    pub testnet: bool,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetHttpResponse {
    pub status_code: u16,
    pub reason: &'static str,
    pub body: String,
}

impl PrivateDevnetHttpResponse {
    pub fn to_http_response(&self) -> String {
        format!(
            "HTTP/1.1 {} {}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
            self.status_code,
            self.reason,
            self.body.len(),
            self.body
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProducedTransferBlockStatus {
    pub transaction_hash: Hash32,
    pub block_hash: Hash32,
    pub applied_transactions: usize,
    pub status: NodeStatus,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProducedPendingBlockStatus {
    pub block_hash: Hash32,
    pub included_transaction_hashes: Vec<Hash32>,
    pub applied_transactions: usize,
    pub status: NodeStatus,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetPreflightTransferStatus {
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub preflight_balance: XriqAmount,
    pub preflight_nonce: u64,
    pub transaction_hash: Hash32,
    pub block_hash: Hash32,
    pub confirmed_block_height: u64,
    pub confirmed_transaction_index: usize,
    pub final_balance: XriqAmount,
    pub final_nonce: u64,
    pub status: NodeStatus,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetConfirmedTransactionDetail {
    pub tx_hash: Hash32,
    pub status: &'static str,
    pub block_height: u64,
    pub block_hash: Hash32,
    pub transaction_index: usize,
    pub transaction: Transaction,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetPendingTransactionDetail {
    pub tx_hash: Hash32,
    pub status: &'static str,
    pub received_order: u64,
    pub transaction: Transaction,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PrivateDevnetTransactionDetail {
    Confirmed(PrivateDevnetConfirmedTransactionDetail),
    Pending(PrivateDevnetPendingTransactionDetail),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeRunnerOutput {
    Help(String),
    Status(NodeStatus),
    ChainCheck(PrivateDevnetChainCheckStatus),
    ProducedTransferBlock(ProducedTransferBlockStatus),
    ProducedPendingBlock(ProducedPendingBlockStatus),
    PreflightTransfer(PrivateDevnetPreflightTransferStatus),
    ExplorerOverview(String),
    BlockList(String),
    BlockDetail(String),
    AccountDetail(String),
    AccountList(String),
    AccountTransactions(String),
    TransactionList(String),
    MempoolDetail(String),
    TransactionDetail(String),
    SnapshotList(String),
    SnapshotDetail(String),
    SnapshotCheck(String),
    Snapshot(PrivateDevnetSnapshotStatus),
    Json(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeRunnerError {
    MissingCommand,
    UnknownCommand(String),
    UnknownFlag(String),
    MissingFlag(&'static str),
    UnsupportedEnvironment(String),
    PeerSyncError(String),
    FaucetRefused(String),
    InvalidNetwork(String),
    DuplicateFlag(String),
    UnexpectedArgument(String),
    DraftFileRead { path: String, error: String },
    PendingFileRead { path: String, error: String },
    SnapshotFileRead { path: String, error: String },
    SnapshotFileWrite { path: String, error: String },
    SnapshotTargetExists(String),
    SnapshotNotFound(String),
    InvalidSnapshotManifest(String),
    InvalidPendingRecord(String),
    InvalidDraftLine(String),
    UnknownDraftField(String),
    DuplicateDraftField(String),
    MissingDraftField(&'static str),
    UnsupportedDraftVersion { expected: u16, actual: String },
    WrongDraftChainId { expected: String, actual: String },
    InvalidJson(String),
    UnknownJsonField(String),
    DuplicateJsonField(String),
    MissingJsonField(&'static str),
    InvalidNumber { flag: &'static str, value: String },
    InvalidHash { flag: &'static str, value: String },
    InvalidFormat(String),
    InvalidAddress(AddressError),
    Explorer(ExplorerError),
    Node(NodeError),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RunnerOutputFormat {
    Text,
    Json,
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
    UnexpectedStoredBlockCount { expected: usize, actual: usize },
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

impl fmt::Display for NodeStatus {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(formatter, "warning={}", self.warning)?;
        writeln!(formatter, "chain_id={}", self.chain_id)?;
        writeln!(formatter, "current_height={}", self.current_height)?;
        writeln!(
            formatter,
            "latest_block_hash={}",
            hash_hex(self.latest_block_hash)
        )?;
        writeln!(formatter, "state_root={}", hash_hex(self.state_root))?;
        writeln!(
            formatter,
            "pending_transactions={}",
            self.pending_transactions
        )?;
        write!(formatter, "stored_blocks={}", self.stored_blocks)
    }
}

impl fmt::Display for ProducedTransferBlockStatus {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(formatter, "warning={}", self.status.warning)?;
        writeln!(
            formatter,
            "transaction_hash={}",
            hash_hex(self.transaction_hash)
        )?;
        writeln!(formatter, "block_hash={}", hash_hex(self.block_hash))?;
        writeln!(
            formatter,
            "applied_transactions={}",
            self.applied_transactions
        )?;
        writeln!(formatter, "chain_id={}", self.status.chain_id)?;
        writeln!(formatter, "current_height={}", self.status.current_height)?;
        writeln!(
            formatter,
            "latest_block_hash={}",
            hash_hex(self.status.latest_block_hash)
        )?;
        writeln!(formatter, "state_root={}", hash_hex(self.status.state_root))?;
        writeln!(
            formatter,
            "pending_transactions={}",
            self.status.pending_transactions
        )?;
        write!(formatter, "stored_blocks={}", self.status.stored_blocks)
    }
}

impl fmt::Display for PrivateDevnetChainCheckStatus {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(formatter, "warning={}", self.status.warning)?;
        writeln!(formatter, "verified={}", self.verified)?;
        writeln!(formatter, "chain_id={}", self.status.chain_id)?;
        writeln!(formatter, "current_height={}", self.status.current_height)?;
        writeln!(
            formatter,
            "latest_block_hash={}",
            hash_hex(self.status.latest_block_hash)
        )?;
        writeln!(formatter, "state_root={}", hash_hex(self.status.state_root))?;
        writeln!(
            formatter,
            "pending_transactions={}",
            self.status.pending_transactions
        )?;
        write!(formatter, "stored_blocks={}", self.status.stored_blocks)
    }
}

impl fmt::Display for ProducedPendingBlockStatus {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(formatter, "warning={}", self.status.warning)?;
        writeln!(formatter, "block_hash={}", hash_hex(self.block_hash))?;
        writeln!(
            formatter,
            "included_transaction_hashes={}",
            self.included_transaction_hashes
                .iter()
                .map(|tx_hash| hash_hex(*tx_hash))
                .collect::<Vec<_>>()
                .join(",")
        )?;
        writeln!(
            formatter,
            "applied_transactions={}",
            self.applied_transactions
        )?;
        writeln!(formatter, "chain_id={}", self.status.chain_id)?;
        writeln!(formatter, "current_height={}", self.status.current_height)?;
        writeln!(
            formatter,
            "latest_block_hash={}",
            hash_hex(self.status.latest_block_hash)
        )?;
        writeln!(formatter, "state_root={}", hash_hex(self.status.state_root))?;
        writeln!(
            formatter,
            "pending_transactions={}",
            self.status.pending_transactions
        )?;
        write!(formatter, "stored_blocks={}", self.status.stored_blocks)
    }
}

impl fmt::Display for PrivateDevnetPreflightTransferStatus {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(formatter, "warning={}", self.status.warning)?;
        writeln!(formatter, "from={}", self.from)?;
        writeln!(formatter, "to={}", self.to)?;
        writeln!(formatter, "amount={}", self.amount.base_units())?;
        writeln!(formatter, "fee={}", self.fee.base_units())?;
        writeln!(
            formatter,
            "preflight_balance={}",
            self.preflight_balance.base_units()
        )?;
        writeln!(formatter, "preflight_nonce={}", self.preflight_nonce)?;
        writeln!(
            formatter,
            "transaction_hash={}",
            hash_hex(self.transaction_hash)
        )?;
        writeln!(formatter, "block_hash={}", hash_hex(self.block_hash))?;
        writeln!(
            formatter,
            "confirmed_block_height={}",
            self.confirmed_block_height
        )?;
        writeln!(
            formatter,
            "confirmed_transaction_index={}",
            self.confirmed_transaction_index
        )?;
        writeln!(
            formatter,
            "final_balance={}",
            self.final_balance.base_units()
        )?;
        writeln!(formatter, "final_nonce={}", self.final_nonce)?;
        writeln!(formatter, "chain_id={}", self.status.chain_id)?;
        writeln!(formatter, "current_height={}", self.status.current_height)?;
        writeln!(
            formatter,
            "latest_block_hash={}",
            hash_hex(self.status.latest_block_hash)
        )?;
        writeln!(formatter, "state_root={}", hash_hex(self.status.state_root))?;
        writeln!(
            formatter,
            "pending_transactions={}",
            self.status.pending_transactions
        )?;
        write!(formatter, "stored_blocks={}", self.status.stored_blocks)
    }
}

impl fmt::Display for PrivateDevnetSnapshotStatus {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        writeln!(formatter, "warning={}", self.status.warning)?;
        writeln!(
            formatter,
            "snapshot_format_version={}",
            PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION
        )?;
        writeln!(formatter, "snapshot_dir={}", self.snapshot_dir)?;
        writeln!(formatter, "chain_file={}", self.chain_file)?;
        writeln!(
            formatter,
            "pending_file={}",
            self.pending_file.as_deref().unwrap_or("none")
        )?;
        writeln!(formatter, "chain_id={}", self.status.chain_id)?;
        writeln!(formatter, "current_height={}", self.status.current_height)?;
        writeln!(
            formatter,
            "latest_block_hash={}",
            hash_hex(self.status.latest_block_hash)
        )?;
        writeln!(formatter, "state_root={}", hash_hex(self.status.state_root))?;
        writeln!(
            formatter,
            "pending_transactions={}",
            self.status.pending_transactions
        )?;
        write!(formatter, "stored_blocks={}", self.status.stored_blocks)
    }
}

impl fmt::Display for NodeRunnerOutput {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Help(help) => formatter.write_str(help),
            Self::Status(status) => write!(formatter, "{status}"),
            Self::ChainCheck(status) => write!(formatter, "{status}"),
            Self::ProducedTransferBlock(status) => write!(formatter, "{status}"),
            Self::ProducedPendingBlock(status) => write!(formatter, "{status}"),
            Self::PreflightTransfer(status) => write!(formatter, "{status}"),
            Self::ExplorerOverview(overview) => formatter.write_str(overview),
            Self::BlockList(detail)
            | Self::BlockDetail(detail)
            | Self::AccountDetail(detail)
            | Self::AccountList(detail)
            | Self::AccountTransactions(detail)
            | Self::TransactionList(detail)
            | Self::MempoolDetail(detail)
            | Self::TransactionDetail(detail)
            | Self::SnapshotList(detail)
            | Self::SnapshotDetail(detail)
            | Self::SnapshotCheck(detail) => formatter.write_str(detail),
            Self::Snapshot(status) => write!(formatter, "{status}"),
            Self::Json(json) => formatter.write_str(json),
        }
    }
}

impl fmt::Display for NodeRunnerError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MissingCommand => formatter.write_str("missing command"),
            Self::UnknownCommand(command) => write!(formatter, "unknown command: {command}"),
            Self::UnknownFlag(flag) => write!(formatter, "unknown flag: {flag}"),
            Self::MissingFlag(flag) => write!(formatter, "missing required flag: {flag}"),
            Self::UnsupportedEnvironment(value) => write!(
                formatter,
                "unsupported environment {value:?}: only \"local\" and \"staging-devnet\" are allowed; production, mainnet, and public-testnet are not runnable from this build"
            ),
            Self::PeerSyncError(message) => write!(formatter, "peer sync failed: {message}"),
            Self::FaucetRefused(message) => write!(formatter, "faucet refused: {message}"),
            Self::InvalidNetwork(value) => write!(
                formatter,
                "invalid network {value:?}: expected \"devnet\" or \"testnet\""
            ),
            Self::DuplicateFlag(flag) => write!(formatter, "duplicate flag: {flag}"),
            Self::UnexpectedArgument(argument) => {
                write!(formatter, "unexpected argument: {argument}")
            }
            Self::DraftFileRead { path, error } => {
                write!(formatter, "could not read draft file {path}: {error}")
            }
            Self::PendingFileRead { path, error } => {
                write!(formatter, "could not read pending file {path}: {error}")
            }
            Self::SnapshotFileRead { path, error } => {
                write!(formatter, "could not read snapshot file {path}: {error}")
            }
            Self::SnapshotFileWrite { path, error } => {
                write!(formatter, "could not write snapshot file {path}: {error}")
            }
            Self::SnapshotTargetExists(path) => {
                write!(formatter, "snapshot target already exists: {path}")
            }
            Self::SnapshotNotFound(path) => write!(formatter, "snapshot not found: {path}"),
            Self::InvalidSnapshotManifest(message) => {
                write!(formatter, "invalid snapshot manifest: {message}")
            }
            Self::InvalidPendingRecord(record) => {
                write!(formatter, "invalid pending transaction record: {record}")
            }
            Self::InvalidDraftLine(line) => write!(formatter, "invalid draft line: {line}"),
            Self::UnknownDraftField(field) => write!(formatter, "unknown draft field: {field}"),
            Self::DuplicateDraftField(field) => {
                write!(formatter, "duplicate draft field: {field}")
            }
            Self::MissingDraftField(field) => write!(formatter, "missing draft field: {field}"),
            Self::UnsupportedDraftVersion { expected, actual } => write!(
                formatter,
                "unsupported draft version: expected {expected}, got {actual}"
            ),
            Self::WrongDraftChainId { expected, actual } => write!(
                formatter,
                "wrong draft chain id: expected {expected}, got {actual}"
            ),
            Self::InvalidJson(message) => write!(formatter, "invalid json: {message}"),
            Self::UnknownJsonField(field) => write!(formatter, "unknown json field: {field}"),
            Self::DuplicateJsonField(field) => {
                write!(formatter, "duplicate json field: {field}")
            }
            Self::MissingJsonField(field) => write!(formatter, "missing json field: {field}"),
            Self::InvalidNumber { flag, value } => {
                write!(formatter, "invalid number for {flag}: {value}")
            }
            Self::InvalidHash { flag, value } => write!(
                formatter,
                "invalid hash for {flag}: {value}; expected 64 lowercase hexadecimal characters"
            ),
            Self::InvalidFormat(value) => {
                write!(formatter, "invalid format: {value}; expected text or json")
            }
            Self::InvalidAddress(error) => write!(formatter, "invalid address: {error:?}"),
            Self::Explorer(error) => write!(formatter, "explorer error: {error:?}"),
            Self::Node(error) => write!(formatter, "node error: {error:?}"),
        }
    }
}

impl RunnerOutputFormat {
    fn parse(value: Option<&str>) -> Result<Self, NodeRunnerError> {
        match value.unwrap_or("text") {
            "text" => Ok(Self::Text),
            "json" => Ok(Self::Json),
            value => Err(NodeRunnerError::InvalidFormat(value.to_string())),
        }
    }
}

impl NodeRunnerError {
    pub fn code(&self) -> &'static str {
        match self {
            Self::MissingCommand => "missing_command",
            Self::UnknownCommand(_) => "unknown_command",
            Self::UnknownFlag(_) => "unknown_flag",
            Self::MissingFlag(_) => "missing_flag",
            Self::UnsupportedEnvironment(_) => "unsupported_environment",
            Self::PeerSyncError(_) => "peer_sync_error",
            Self::FaucetRefused(_) => "faucet_refused",
            Self::InvalidNetwork(_) => "invalid_network",
            Self::DuplicateFlag(_) => "duplicate_flag",
            Self::UnexpectedArgument(_) => "unexpected_argument",
            Self::DraftFileRead { .. } => "draft_file_read",
            Self::PendingFileRead { .. } => "pending_file_read",
            Self::SnapshotFileRead { .. } => "snapshot_file_read",
            Self::SnapshotFileWrite { .. } => "snapshot_file_write",
            Self::SnapshotTargetExists(_) => "snapshot_target_exists",
            Self::SnapshotNotFound(_) => "snapshot_not_found",
            Self::InvalidSnapshotManifest(_) => "invalid_snapshot_manifest",
            Self::InvalidPendingRecord(_) => "invalid_pending_record",
            Self::InvalidDraftLine(_) => "invalid_draft_line",
            Self::UnknownDraftField(_) => "unknown_draft_field",
            Self::DuplicateDraftField(_) => "duplicate_draft_field",
            Self::MissingDraftField(_) => "missing_draft_field",
            Self::UnsupportedDraftVersion { .. } => "unsupported_draft_version",
            Self::WrongDraftChainId { .. } => "wrong_draft_chain_id",
            Self::InvalidJson(_) => "invalid_json",
            Self::UnknownJsonField(_) => "unknown_json_field",
            Self::DuplicateJsonField(_) => "duplicate_json_field",
            Self::MissingJsonField(_) => "missing_json_field",
            Self::InvalidNumber { .. } => "invalid_number",
            Self::InvalidHash { .. } => "invalid_hash",
            Self::InvalidFormat(_) => "invalid_format",
            Self::InvalidAddress(_) => "invalid_address",
            Self::Explorer(_) => "explorer_error",
            Self::Node(_) => "node_error",
        }
    }
}

pub fn node_help_text() -> String {
    [
        "xriq-node private-devnet commands:",
        "  All commands accept an optional [--environment local|staging-devnet] profile (default local; production/mainnet/public-testnet are rejected).",
        "  xriq-node status --chain-file <path> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node chain-check --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node produce-transfer-block --chain-file <path> --from <address> --to <address> --amount <base-units> --fee <base-units> --nonce <number> [--alice-balance <base-units>] [--expires-at-height <height>] [--timestamp-ms <ms>] [--consensus-round <number>] [--format text|json]",
        "  xriq-node produce-draft-block --chain-file <path> --draft-file <path> [--alice-balance <base-units>] [--timestamp-ms <ms>] [--consensus-round <number>] [--format text|json]",
        "  xriq-node produce-pending-block --chain-file <path> --pending-file <path> [--alice-balance <base-units>] [--timestamp-ms <ms>] [--consensus-round <number>] [--format text|json]",
        "  xriq-node preflight-transfer --chain-file <path> --pending-file <path> --from <address> --to <address> --amount <base-units> --fee <base-units> [--alice-balance <base-units>] [--expires-at-height <height>] [--timestamp-ms <ms>] [--consensus-round <number>] [--format text|json]",
        "  xriq-node explorer-overview --chain-file <path> [--alice-balance <base-units>] [--limit <count>] [--format text|json]",
        "  xriq-node block-list --chain-file <path> [--alice-balance <base-units>] [--limit <count>] [--format text|json]",
        "  xriq-node block-detail --chain-file <path> (--height <height|latest>|--block-hash <64-hex>) [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node account-list --chain-file <path> [--alice-balance <base-units>] [--limit <count>] [--format text|json]",
        "  xriq-node account-detail --chain-file <path> --address <address> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node account-transactions --chain-file <path> --address <address> [--alice-balance <base-units>] [--limit <count>] [--format text|json]",
        "  xriq-node transaction-list --chain-file <path> [--alice-balance <base-units>] [--limit <count>] [--format text|json]",
        "  xriq-node mempool-detail --chain-file <path> [--draft-file <path>] [--pending-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node peer-blocks-export --chain-file <path> [--from-height <height>] [--limit <count>] [--network devnet|testnet] [--alice-balance <base-units>] [--format json]  (read-only; serves validated blocks for peer sync, also at GET /v1/peer/blocks)",
        "  xriq-node peer-identity --chain-file <path> [--node-seed <string>] [--network devnet|testnet] [--alice-balance <base-units>] [--format json]  (read-only compatibility handshake: network, protocol, tip, node id; also at GET /v1/peer/identity)",
        "  xriq-node peer-peers [--peers-file <path>] [--network devnet|testnet] [--chain-file <path>] [--format json]  (read-only; advertises this node's known peers for discovery; also at GET /v1/peer/peers)",
        "  xriq-node testnet-genesis [--format json]  (read-only; prints the canonical TEST-ONLY public testnet genesis spec and its reproducible genesis_spec_hash)",
        "  xriq-node faucet-dispense --chain-file <testnet-path> --to <address> [--amount <base-units>] [--max-balance <base-units>] [--timestamp-ms <ms>] [--consensus-round <n>] [--format json]  (TEST-ONLY; sends valueless test units from the genesis faucet, balance-capped, and confirms a block)",
        "  xriq-node peer-sync --chain-file <path> (--peer <http://host:port> | --peers-file <path>) [--discover <max-peers>] [--node-seed <string>] [--network devnet|testnet] [--limit <count>] [--max-rounds <count>] [--alice-balance <base-units>] [--format json]  (follower; handshakes then pulls/validates blocks from one or many peers on the same network, discovering more and skipping itself, into the chain file)",
        "  xriq-node transaction-detail --chain-file <path> --tx-hash <64-hex> [--draft-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node snapshot-list --snapshot-root <path> [--limit <count>] [--format text|json]",
        "  xriq-node snapshot-latest --snapshot-root <path> [--format text|json]",
        "  xriq-node snapshot-latest-check --snapshot-root <path> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node snapshot-detail --snapshot-dir <path> [--format text|json]",
        "  xriq-node snapshot-check --snapshot-dir <path> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node snapshot-export --chain-file <path> --snapshot-dir <path> [--pending-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node snapshot-import --snapshot-dir <path> --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node serve-readonly --chain-file <path> [--alice-balance <base-units>] [--bind <ip:port>] [--pending-file <path>] [--snapshot-root <path>] [--peers-file <path>] [--node-seed <string>] [--network devnet|testnet]",
        "  xriq-node serve-private --chain-file <path> [--alice-balance <base-units>] [--bind <ip:port>] [--pending-file <path>] [--snapshot-root <path>] [--peers-file <path>] [--node-seed <string>] [--network devnet|testnet]",
        "",
        "Warning: this runner is for private devnet tests only. It does not start a public network.",
    ]
    .join("\n")
}

pub fn node_runner_args_request_json(args: &[String]) -> bool {
    args.windows(2)
        .any(|window| window[0] == "--format" && window[1] == "json")
}

pub fn render_node_runner_error_json(args: &[String], error: &NodeRunnerError) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"format_version\": {},",
        json_string("xriq-node-json-v1")
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"ok\": false,").expect("write to String");
    writeln!(
        &mut output,
        "  \"command\": {},",
        json_optional_string(node_runner_command_name(args))
    )
    .expect("write to String");
    writeln!(&mut output, "  \"error\": {{").expect("write to String");
    writeln!(&mut output, "    \"code\": {},", json_string(error.code())).expect("write to String");
    writeln!(
        &mut output,
        "    \"message\": {}",
        json_string(&error.to_string())
    )
    .expect("write to String");
    output.push_str("  }\n}");
    output
}

fn node_runner_command_name(args: &[String]) -> Option<&str> {
    args.first()
        .map(String::as_str)
        .filter(|command| !command.starts_with('-'))
}

// Resolve an optional `--environment` value, fail-closed. None defaults to
// local; production/mainnet/public-testnet and unknown values are rejected so
// the node cannot be run as, or confused with, production.
fn parse_node_environment(value: Option<&str>) -> Result<Environment, NodeRunnerError> {
    match value {
        None => Ok(Environment::DEFAULT),
        Some(raw) => raw
            .parse::<Environment>()
            .map_err(|error| NodeRunnerError::UnsupportedEnvironment(error.value)),
    }
}

// Extract and validate an optional `--environment` flag from a command's
// argument list, returning the resolved profile and the remaining arguments
// with the flag removed so existing per-command parsers are unaffected.
fn take_environment_flag(args: &[String]) -> Result<(Environment, Vec<String>), NodeRunnerError> {
    let mut value: Option<String> = None;
    let mut rest: Vec<String> = Vec::with_capacity(args.len());
    let mut index = 0;
    while index < args.len() {
        if args[index] == "--environment" {
            let raw = args
                .get(index + 1)
                .ok_or(NodeRunnerError::MissingFlag("--environment"))?;
            if value.is_some() {
                return Err(NodeRunnerError::DuplicateFlag("--environment".to_string()));
            }
            value = Some(raw.clone());
            index += 2;
        } else {
            rest.push(args[index].clone());
            index += 1;
        }
    }
    Ok((parse_node_environment(value.as_deref())?, rest))
}

pub fn run_node_command<I, S>(args: I) -> Result<NodeRunnerOutput, NodeRunnerError>
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let args: Vec<String> = args
        .into_iter()
        .map(|argument| argument.as_ref().to_string())
        .collect();
    // Resolve and strip the optional --environment flag (fail-closed) for any
    // real subcommand; the help and no-command paths are unaffected.
    let args: Vec<String> = match args.first().map(String::as_str) {
        None | Some("help") | Some("--help") | Some("-h") => args,
        Some(_) => {
            let (environment, mut rest) = take_environment_flag(&args[1..])?;
            eprintln!("xriq-node environment={environment}");
            let mut full = Vec::with_capacity(rest.len() + 1);
            full.push(args[0].clone());
            full.append(&mut rest);
            full
        }
    };
    match args.first().map(String::as_str) {
        None => Err(NodeRunnerError::MissingCommand),
        Some("help" | "--help" | "-h") => Ok(NodeRunnerOutput::Help(node_help_text())),
        Some("status") => run_status_command(&args[1..]),
        Some("chain-check") => run_chain_check_command(&args[1..]),
        Some("produce-transfer-block") => run_produce_transfer_block_command(&args[1..]),
        Some("produce-draft-block") => run_produce_draft_block_command(&args[1..]),
        Some("produce-pending-block") => run_produce_pending_block_command(&args[1..]),
        Some("preflight-transfer") => run_preflight_transfer_command(&args[1..]),
        Some("explorer-overview") => run_explorer_overview_command(&args[1..]),
        Some("block-list") => run_block_list_command(&args[1..]),
        Some("block-detail") => run_block_detail_command(&args[1..]),
        Some("account-list") => run_account_list_command(&args[1..]),
        Some("account-detail") => run_account_detail_command(&args[1..]),
        Some("account-transactions") => run_account_transactions_command(&args[1..]),
        Some("transaction-list") => run_transaction_list_command(&args[1..]),
        Some("mempool-detail") => run_mempool_detail_command(&args[1..]),
        Some("peer-blocks-export") => run_peer_blocks_export_command(&args[1..]),
        Some("peer-identity") => run_peer_identity_command(&args[1..]),
        Some("peer-peers") => run_peer_peers_command(&args[1..]),
        Some("peer-sync") => run_peer_sync_command(&args[1..]),
        Some("testnet-genesis") => run_testnet_genesis_command(&args[1..]),
        Some("faucet-dispense") => run_faucet_dispense_command(&args[1..]),
        Some("transaction-detail") => run_transaction_detail_command(&args[1..]),
        Some("snapshot-list") => run_snapshot_list_command(&args[1..]),
        Some("snapshot-latest") => run_snapshot_latest_command(&args[1..]),
        Some("snapshot-latest-check") => run_snapshot_latest_check_command(&args[1..]),
        Some("snapshot-detail") => run_snapshot_detail_command(&args[1..]),
        Some("snapshot-check") => run_snapshot_check_command(&args[1..]),
        Some("snapshot-export") => run_snapshot_export_command(&args[1..]),
        Some("snapshot-import") => run_snapshot_import_command(&args[1..]),
        Some(command) => Err(NodeRunnerError::UnknownCommand(command.to_string())),
    }
}

pub fn parse_private_devnet_http_server_config(
    args: &[String],
    allow_transaction_submission: bool,
) -> Result<PrivateDevnetHttpServerConfig, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--bind",
        "--chain-file",
        "--pending-file",
        "--snapshot-root",
        "--alice-balance",
        "--peers-file",
        "--node-seed",
        "--network",
        "--environment",
    ])?;
    // Validate the optional environment profile fail-closed; the server stays
    // local/private and never runs as production.
    parse_node_environment(flags.optional("--environment"))?;
    let bind = flags
        .optional("--bind")
        .unwrap_or("127.0.0.1:8787")
        .to_string();
    let chain_file = flags.required("--chain-file")?.to_string();
    let pending_file = flags.optional("--pending-file").map(str::to_string);
    let snapshot_root = flags.optional("--snapshot-root").map(str::to_string);
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let peers_file = flags.optional("--peers-file").map(str::to_string);
    let node_seed = flags.optional("--node-seed").map(str::to_string);
    let testnet = matches!(parse_runner_genesis(&flags)?, RunnerGenesis::Testnet);
    Ok(PrivateDevnetHttpServerConfig {
        bind,
        chain_file,
        pending_file,
        snapshot_root,
        alice_balance,
        allow_transaction_submission,
        peers_file,
        node_seed,
        testnet,
    })
}

pub fn run_private_devnet_readonly_http_server(
    config: PrivateDevnetHttpServerConfig,
) -> io::Result<()> {
    let listener = TcpListener::bind(&config.bind)?;
    eprintln!(
        "xriq private-devnet read-only HTTP listening on http://{}",
        listener.local_addr()?
    );
    for stream in listener.incoming() {
        match stream {
            Ok(stream) => {
                if let Err(error) = handle_private_devnet_http_stream(stream, &config) {
                    eprintln!("xriq private-devnet HTTP request failed: {error}");
                }
            }
            Err(error) => eprintln!("xriq private-devnet HTTP accept failed: {error}"),
        }
    }
    Ok(())
}

pub fn private_devnet_http_response(
    config: &PrivateDevnetHttpServerConfig,
    method: &str,
    target: &str,
) -> PrivateDevnetHttpResponse {
    private_devnet_http_response_with_body(config, method, target, "")
}

pub fn private_devnet_http_response_with_body(
    config: &PrivateDevnetHttpServerConfig,
    method: &str,
    target: &str,
    body: &str,
) -> PrivateDevnetHttpResponse {
    let (path, query) = split_http_target(target);

    if method == "POST" && path == "/v1/transactions" {
        return submit_transaction_http_response(config, body);
    }
    if method == "POST" && path == "/v1/mempool" {
        return submit_pending_transaction_http_response(config, body);
    }
    if method == "POST" && path == "/v1/blocks" {
        return produce_pending_block_http_response(config, query);
    }
    if method == "POST" && path == "/v1/snapshots/export" {
        return snapshot_export_http_response(config, query);
    }
    if method == "POST" && path == "/v1/snapshots/import" {
        return snapshot_import_http_response(config, query);
    }

    if method != "GET" {
        return http_error_response(
            405,
            "method_not_allowed",
            "only GET read-only endpoints are currently supported",
        );
    }

    match path {
        "/health" => http_json_response(200, render_private_devnet_http_health_json()),
        "/v1/chain/status" => {
            if let Some(pending_file) = &config.pending_file {
                pending_status_http_response(config, pending_file)
            } else {
                runner_json_http_response(private_devnet_http_runner_args("status", config))
            }
        }
        "/v1/chain/check" => chain_check_http_response(config),
        "/v1/mempool" => {
            if let Some(pending_file) = &config.pending_file {
                pending_mempool_http_response(config, pending_file)
            } else {
                runner_json_http_response(private_devnet_http_runner_args("mempool-detail", config))
            }
        }
        "/v1/explorer/overview" => {
            let mut args = private_devnet_http_runner_args("explorer-overview", config);
            if let Some(limit) = query_value(query, "limit") {
                args.push("--limit".to_string());
                args.push(limit.to_string());
            }
            runner_json_http_response(args)
        }
        "/v1/snapshots" => snapshot_list_http_response(config, query),
        "/v1/snapshots/latest" => snapshot_latest_http_response(config),
        "/v1/snapshots/latest/check" => snapshot_latest_check_http_response(config),
        "/v1/blocks" => {
            let mut args = private_devnet_http_runner_args("block-list", config);
            if let Some(limit) = query_value(query, "limit") {
                args.push("--limit".to_string());
                args.push(limit.to_string());
            }
            runner_json_http_response(args)
        }
        "/v1/peer/identity" => {
            // Read-only compatibility handshake: network, protocol, tip, node id.
            let mut args = private_devnet_http_runner_args("peer-identity", config);
            push_network_arg(&mut args, config);
            if let Some(node_seed) = &config.node_seed {
                args.push("--node-seed".to_string());
                args.push(node_seed.clone());
            }
            runner_json_http_response(args)
        }
        "/v1/peer/peers" => {
            // Read-only discovery: advertise this node's configured peer set.
            let mut args = private_devnet_http_runner_args("peer-peers", config);
            push_network_arg(&mut args, config);
            if let Some(peers_file) = &config.peers_file {
                args.push("--peers-file".to_string());
                args.push(peers_file.clone());
            }
            runner_json_http_response(args)
        }
        "/v1/peer/blocks" => {
            // Read-only peer sync: serve validated blocks a follower can import.
            let mut args = private_devnet_http_runner_args("peer-blocks-export", config);
            push_network_arg(&mut args, config);
            if let Some(from_height) = query_value(query, "from_height") {
                args.push("--from-height".to_string());
                args.push(from_height.to_string());
            }
            if let Some(limit) = query_value(query, "limit") {
                args.push("--limit".to_string());
                args.push(limit.to_string());
            }
            runner_json_http_response(args)
        }
        "/v1/transactions" => {
            let mut args = private_devnet_http_runner_args("transaction-list", config);
            if let Some(limit) = query_value(query, "limit") {
                args.push("--limit".to_string());
                args.push(limit.to_string());
            }
            runner_json_http_response(args)
        }
        "/v1/accounts" => {
            let mut args = private_devnet_http_runner_args("account-list", config);
            if let Some(limit) = query_value(query, "limit") {
                args.push("--limit".to_string());
                args.push(limit.to_string());
            }
            runner_json_http_response(args)
        }
        _ => {
            if let Some(address) = path
                .strip_prefix("/v1/accounts/")
                .and_then(|suffix| suffix.strip_suffix("/transactions"))
                .filter(|address| !address.is_empty())
            {
                let mut args = private_devnet_http_runner_args("account-transactions", config);
                args.push("--address".to_string());
                args.push(address.to_string());
                if let Some(limit) = query_value(query, "limit") {
                    args.push("--limit".to_string());
                    args.push(limit.to_string());
                }
                return runner_json_http_response(args);
            }

            if let Some(address) = path
                .strip_prefix("/v1/accounts/")
                .filter(|address| !address.is_empty())
            {
                let mut args = private_devnet_http_runner_args("account-detail", config);
                args.push("--address".to_string());
                args.push(address.to_string());
                return runner_json_http_response(args);
            }

            if let Some(block_id) = path
                .strip_prefix("/v1/blocks/")
                .filter(|block_id| !block_id.is_empty())
            {
                let mut args = private_devnet_http_runner_args("block-detail", config);
                if block_id == "latest" {
                    args.push("--height".to_string());
                    args.push("latest".to_string());
                } else if block_id.len() == 64 {
                    let Ok(_) = parse_hash_hex(block_id) else {
                        return http_error_response(
                            400,
                            "invalid_hash",
                            "block hash must be 64 lowercase hexadecimal characters",
                        );
                    };
                    args.push("--block-hash".to_string());
                    args.push(block_id.to_string());
                } else {
                    args.push("--height".to_string());
                    args.push(block_id.to_string());
                }
                return runner_json_http_response(args);
            }

            if let Some(snapshot_name) = path
                .strip_prefix("/v1/snapshots/")
                .and_then(|suffix| suffix.strip_suffix("/check"))
                .filter(|snapshot_name| !snapshot_name.is_empty())
            {
                return snapshot_check_http_response(config, snapshot_name);
            }

            if let Some(snapshot_name) = path
                .strip_prefix("/v1/snapshots/")
                .filter(|snapshot_name| !snapshot_name.is_empty())
            {
                return snapshot_detail_http_response(config, snapshot_name);
            }

            if let Some(tx_hash) = path
                .strip_prefix("/v1/transactions/")
                .filter(|tx_hash| !tx_hash.is_empty())
            {
                let Ok(tx_hash) = parse_hash_hex(tx_hash) else {
                    return http_error_response(
                        400,
                        "invalid_hash",
                        "transaction hash must be 64 lowercase hexadecimal characters",
                    );
                };
                return transaction_detail_http_response(config, tx_hash);
            }

            http_error_response(404, "not_found", "private-devnet HTTP endpoint not found")
        }
    }
}

fn handle_private_devnet_http_stream(
    mut stream: TcpStream,
    config: &PrivateDevnetHttpServerConfig,
) -> io::Result<()> {
    let _ = stream.set_read_timeout(Some(Duration::from_secs(5)));
    let mut buffer = [0_u8; 8192];
    let bytes_read = stream.read(&mut buffer)?;
    let mut request_bytes = buffer[..bytes_read].to_vec();
    while let Some((body_start, content_length)) =
        http_content_length_from_request_bytes(&request_bytes)
    {
        let body_bytes_read = request_bytes.len().saturating_sub(body_start);
        if body_bytes_read >= content_length {
            break;
        }
        let bytes_read = stream.read(&mut buffer)?;
        if bytes_read == 0 {
            break;
        }
        request_bytes.extend_from_slice(&buffer[..bytes_read]);
    }
    let request = String::from_utf8_lossy(&request_bytes);
    let response = private_devnet_http_response_from_request(config, &request);
    stream.write_all(response.to_http_response().as_bytes())?;
    stream.flush()
}

fn private_devnet_http_response_from_request(
    config: &PrivateDevnetHttpServerConfig,
    request: &str,
) -> PrivateDevnetHttpResponse {
    let Some(request_line) = request.lines().next() else {
        return http_error_response(400, "bad_request", "missing HTTP request line");
    };
    let mut parts = request_line.split_whitespace();
    let Some(method) = parts.next() else {
        return http_error_response(400, "bad_request", "missing HTTP method");
    };
    let Some(target) = parts.next() else {
        return http_error_response(400, "bad_request", "missing HTTP target");
    };
    if parts.next().is_none() {
        return http_error_response(400, "bad_request", "missing HTTP version");
    }
    let body = http_request_body(request);
    private_devnet_http_response_with_body(config, method, target, body)
}

fn http_request_body(request: &str) -> &str {
    request
        .split_once("\r\n\r\n")
        .map(|(_, body)| body)
        .or_else(|| request.split_once("\n\n").map(|(_, body)| body))
        .unwrap_or("")
}

fn http_content_length_from_request_bytes(request: &[u8]) -> Option<(usize, usize)> {
    let body_start = request
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .map(|index| index + 4)?;
    let headers = String::from_utf8_lossy(&request[..body_start]);
    let content_length = headers.lines().find_map(|line| {
        let (name, value) = line.split_once(':')?;
        name.trim()
            .eq_ignore_ascii_case("content-length")
            .then(|| value.trim().parse::<usize>().ok())
            .flatten()
    })?;
    Some((body_start, content_length))
}

fn private_devnet_http_runner_args(
    command: &str,
    config: &PrivateDevnetHttpServerConfig,
) -> Vec<String> {
    let mut args = vec![
        command.to_string(),
        "--chain-file".to_string(),
        config.chain_file.clone(),
    ];
    if let Some(balance) = config.alice_balance {
        args.push("--alice-balance".to_string());
        args.push(balance.base_units().to_string());
    }
    args.push("--format".to_string());
    args.push("json".to_string());
    args
}

// Peer routes on a testnet-configured server run against the testnet genesis.
fn push_network_arg(args: &mut Vec<String>, config: &PrivateDevnetHttpServerConfig) {
    if config.testnet {
        args.push("--network".to_string());
        args.push("testnet".to_string());
    }
}

fn runner_json_http_response(args: Vec<String>) -> PrivateDevnetHttpResponse {
    match run_node_command(args.iter().map(String::as_str)) {
        Ok(output) => http_json_response(200, output.to_string()),
        Err(error) => {
            let status_code = node_runner_error_http_status(&error);
            http_json_response(status_code, render_node_runner_error_json(&args, &error))
        }
    }
}

fn submit_transaction_http_response(
    config: &PrivateDevnetHttpServerConfig,
    body: &str,
) -> PrivateDevnetHttpResponse {
    if !config.allow_transaction_submission {
        return http_error_response(
            501,
            "not_implemented",
            "transaction submission requires xriq-node serve-private",
        );
    }
    if body.trim().is_empty() {
        return http_error_response(
            400,
            "missing_request_body",
            "POST /v1/transactions expects a wallet transfer draft body or private-devnet JSON transfer body",
        );
    }

    match private_devnet_file_submit_transfer_body(&config.chain_file, config.alice_balance, body) {
        Ok(status) => http_json_response(
            201,
            render_produced_transfer_block_status_json("submit-transaction", &status),
        ),
        Err(error) => {
            let args = vec![
                "submit-transaction".to_string(),
                "--format".to_string(),
                "json".to_string(),
            ];
            http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(&args, &error),
            )
        }
    }
}

fn submit_pending_transaction_http_response(
    config: &PrivateDevnetHttpServerConfig,
    body: &str,
) -> PrivateDevnetHttpResponse {
    if !config.allow_transaction_submission {
        return http_error_response(
            501,
            "not_implemented",
            "pending transaction submission requires xriq-node serve-private",
        );
    }
    if body.trim().is_empty() {
        return http_error_response(
            400,
            "missing_request_body",
            "POST /v1/mempool expects a wallet transfer draft body or private-devnet JSON transfer body",
        );
    }
    let Some(pending_file) = &config.pending_file else {
        return http_error_response(
            501,
            "not_implemented",
            "durable pending transactions require --pending-file",
        );
    };

    match private_devnet_file_submit_pending_transfer_body(
        &config.chain_file,
        pending_file,
        config.alice_balance,
        body,
    ) {
        Ok(detail) => http_json_response(
            202,
            render_transaction_detail_json(&PrivateDevnetTransactionDetail::Pending(detail)),
        ),
        Err(error) => {
            let args = vec![
                "submit-pending-transaction".to_string(),
                "--format".to_string(),
                "json".to_string(),
            ];
            http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(&args, &error),
            )
        }
    }
}

fn produce_pending_block_http_response(
    config: &PrivateDevnetHttpServerConfig,
    query: Option<&str>,
) -> PrivateDevnetHttpResponse {
    if !config.allow_transaction_submission {
        return http_error_response(
            501,
            "not_implemented",
            "pending block production requires xriq-node serve-private",
        );
    }
    let Some(pending_file) = &config.pending_file else {
        return http_error_response(
            501,
            "not_implemented",
            "durable pending block production requires --pending-file",
        );
    };

    let timestamp_ms = match query_value(query, "timestamp_ms") {
        Some(value) => match parse_u64("--timestamp-ms", value) {
            Ok(value) => value,
            Err(error) => {
                return http_json_response(
                    node_runner_error_http_status(&error),
                    render_node_runner_error_json(
                        &[
                            "produce-pending-block".to_string(),
                            "--format".to_string(),
                            "json".to_string(),
                        ],
                        &error,
                    ),
                );
            }
        },
        None => 1_000,
    };
    let consensus_round = match query_value(query, "consensus_round") {
        Some(value) => match parse_u64("--consensus-round", value) {
            Ok(value) => value,
            Err(error) => {
                return http_json_response(
                    node_runner_error_http_status(&error),
                    render_node_runner_error_json(
                        &[
                            "produce-pending-block".to_string(),
                            "--format".to_string(),
                            "json".to_string(),
                        ],
                        &error,
                    ),
                );
            }
        },
        None => 0,
    };

    match private_devnet_file_produce_pending_block(
        &config.chain_file,
        pending_file,
        config.alice_balance,
        timestamp_ms,
        consensus_round,
    ) {
        Ok(status) => http_json_response(
            201,
            render_produced_pending_block_status_json("produce-pending-block", &status),
        ),
        Err(error) => {
            let args = vec![
                "produce-pending-block".to_string(),
                "--format".to_string(),
                "json".to_string(),
            ];
            http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(&args, &error),
            )
        }
    }
}

fn snapshot_export_http_response(
    config: &PrivateDevnetHttpServerConfig,
    query: Option<&str>,
) -> PrivateDevnetHttpResponse {
    if !config.allow_transaction_submission {
        return http_error_response(
            501,
            "not_implemented",
            "snapshot export requires xriq-node serve-private",
        );
    }
    let snapshot_dir = match required_decoded_query_value(query, "snapshot_dir", "--snapshot-dir") {
        Ok(value) => value,
        Err(error) => {
            return http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(
                    &[
                        "snapshot-export".to_string(),
                        "--format".to_string(),
                        "json".to_string(),
                    ],
                    &error,
                ),
            );
        }
    };
    match private_devnet_export_snapshot(
        &config.chain_file,
        config.pending_file.as_deref(),
        config.alice_balance,
        &snapshot_dir,
    ) {
        Ok(status) => {
            http_json_response(201, render_snapshot_status_json("snapshot-export", &status))
        }
        Err(error) => http_json_response(
            node_runner_error_http_status(&error),
            render_node_runner_error_json(
                &[
                    "snapshot-export".to_string(),
                    "--format".to_string(),
                    "json".to_string(),
                ],
                &error,
            ),
        ),
    }
}

fn snapshot_import_http_response(
    config: &PrivateDevnetHttpServerConfig,
    query: Option<&str>,
) -> PrivateDevnetHttpResponse {
    if !config.allow_transaction_submission {
        return http_error_response(
            501,
            "not_implemented",
            "snapshot import requires xriq-node serve-private",
        );
    }
    let snapshot_dir = match required_decoded_query_value(query, "snapshot_dir", "--snapshot-dir") {
        Ok(value) => value,
        Err(error) => {
            return http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(
                    &[
                        "snapshot-import".to_string(),
                        "--format".to_string(),
                        "json".to_string(),
                    ],
                    &error,
                ),
            );
        }
    };
    match private_devnet_import_snapshot(
        &snapshot_dir,
        &config.chain_file,
        config.pending_file.as_deref(),
        config.alice_balance,
    ) {
        Ok(status) => {
            http_json_response(201, render_snapshot_status_json("snapshot-import", &status))
        }
        Err(error) => http_json_response(
            node_runner_error_http_status(&error),
            render_node_runner_error_json(
                &[
                    "snapshot-import".to_string(),
                    "--format".to_string(),
                    "json".to_string(),
                ],
                &error,
            ),
        ),
    }
}

fn snapshot_list_http_response(
    config: &PrivateDevnetHttpServerConfig,
    query: Option<&str>,
) -> PrivateDevnetHttpResponse {
    let Some(snapshot_root) = &config.snapshot_root else {
        return http_error_response(
            501,
            "not_implemented",
            "snapshot discovery requires --snapshot-root",
        );
    };
    let limit = match query_value(query, "limit") {
        Some(value) => match parse_usize("--limit", value) {
            Ok(value) => value,
            Err(error) => {
                return http_json_response(
                    node_runner_error_http_status(&error),
                    render_node_runner_error_json(
                        &[
                            "snapshot-list".to_string(),
                            "--format".to_string(),
                            "json".to_string(),
                        ],
                        &error,
                    ),
                );
            }
        },
        None => 25,
    };
    match private_devnet_snapshot_list_data(snapshot_root, limit) {
        Ok(snapshots) => http_json_response(
            200,
            render_snapshot_list_json("snapshot-list", Path::new(snapshot_root), &snapshots),
        ),
        Err(error) => http_json_response(
            node_runner_error_http_status(&error),
            render_node_runner_error_json(
                &[
                    "snapshot-list".to_string(),
                    "--format".to_string(),
                    "json".to_string(),
                ],
                &error,
            ),
        ),
    }
}

fn snapshot_latest_http_response(
    config: &PrivateDevnetHttpServerConfig,
) -> PrivateDevnetHttpResponse {
    let Some(snapshot_root) = &config.snapshot_root else {
        return http_error_response(
            501,
            "not_implemented",
            "snapshot discovery requires --snapshot-root",
        );
    };
    match private_devnet_snapshot_latest_data(snapshot_root) {
        Ok(snapshot) => http_json_response(
            200,
            render_snapshot_detail_json("snapshot-latest", &snapshot),
        ),
        Err(error) => http_json_response(
            node_runner_error_http_status(&error),
            render_node_runner_error_json(
                &[
                    "snapshot-latest".to_string(),
                    "--format".to_string(),
                    "json".to_string(),
                ],
                &error,
            ),
        ),
    }
}

fn snapshot_latest_check_http_response(
    config: &PrivateDevnetHttpServerConfig,
) -> PrivateDevnetHttpResponse {
    let Some(snapshot_root) = &config.snapshot_root else {
        return http_error_response(
            501,
            "not_implemented",
            "snapshot discovery requires --snapshot-root",
        );
    };
    match private_devnet_snapshot_latest_check_data(snapshot_root, config.alice_balance) {
        Ok(status) => http_json_response(
            200,
            render_snapshot_check_json("snapshot-latest-check", &status),
        ),
        Err(error) => http_json_response(
            node_runner_error_http_status(&error),
            render_node_runner_error_json(
                &[
                    "snapshot-latest-check".to_string(),
                    "--format".to_string(),
                    "json".to_string(),
                ],
                &error,
            ),
        ),
    }
}

fn snapshot_detail_http_response(
    config: &PrivateDevnetHttpServerConfig,
    snapshot_name: &str,
) -> PrivateDevnetHttpResponse {
    let Some(snapshot_root) = &config.snapshot_root else {
        return http_error_response(
            501,
            "not_implemented",
            "snapshot discovery requires --snapshot-root",
        );
    };
    let snapshot_dir = match private_devnet_http_snapshot_child_dir(snapshot_root, snapshot_name) {
        Ok(snapshot_dir) => snapshot_dir,
        Err(error) => {
            return http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(
                    &[
                        "snapshot-detail".to_string(),
                        "--format".to_string(),
                        "json".to_string(),
                    ],
                    &error,
                ),
            );
        }
    };
    if !snapshot_dir.join(SNAPSHOT_MANIFEST_FILE).exists() {
        return http_error_response(
            404,
            "snapshot_not_found",
            "private-devnet snapshot was not found",
        );
    }
    match private_devnet_snapshot_detail_data(&snapshot_dir) {
        Ok(snapshot) => http_json_response(
            200,
            render_snapshot_detail_json("snapshot-detail", &snapshot),
        ),
        Err(error) => http_json_response(
            node_runner_error_http_status(&error),
            render_node_runner_error_json(
                &[
                    "snapshot-detail".to_string(),
                    "--format".to_string(),
                    "json".to_string(),
                ],
                &error,
            ),
        ),
    }
}

fn snapshot_check_http_response(
    config: &PrivateDevnetHttpServerConfig,
    snapshot_name: &str,
) -> PrivateDevnetHttpResponse {
    let Some(snapshot_root) = &config.snapshot_root else {
        return http_error_response(
            501,
            "not_implemented",
            "snapshot discovery requires --snapshot-root",
        );
    };
    let snapshot_dir = match private_devnet_http_snapshot_child_dir(snapshot_root, snapshot_name) {
        Ok(snapshot_dir) => snapshot_dir,
        Err(error) => {
            return http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(
                    &[
                        "snapshot-check".to_string(),
                        "--format".to_string(),
                        "json".to_string(),
                    ],
                    &error,
                ),
            );
        }
    };
    if !snapshot_dir.join(SNAPSHOT_MANIFEST_FILE).exists() {
        return http_error_response(
            404,
            "snapshot_not_found",
            "private-devnet snapshot was not found",
        );
    }
    match private_devnet_snapshot_check_data(&snapshot_dir, config.alice_balance) {
        Ok(status) => {
            http_json_response(200, render_snapshot_check_json("snapshot-check", &status))
        }
        Err(error) => http_json_response(
            node_runner_error_http_status(&error),
            render_node_runner_error_json(
                &[
                    "snapshot-check".to_string(),
                    "--format".to_string(),
                    "json".to_string(),
                ],
                &error,
            ),
        ),
    }
}

fn private_devnet_http_snapshot_child_dir(
    snapshot_root: &str,
    snapshot_name: &str,
) -> Result<std::path::PathBuf, NodeRunnerError> {
    let snapshot_name = percent_decode_query_value("snapshot_name", snapshot_name)?;
    if snapshot_name.is_empty()
        || snapshot_name == "."
        || snapshot_name == ".."
        || snapshot_name.contains('/')
        || snapshot_name.contains('\\')
    {
        return Err(NodeRunnerError::InvalidFormat(
            "snapshot name must be one safe path segment".to_string(),
        ));
    }
    Ok(Path::new(snapshot_root).join(snapshot_name))
}

fn chain_check_http_response(config: &PrivateDevnetHttpServerConfig) -> PrivateDevnetHttpResponse {
    let result = private_devnet_file_chain_check(
        &config.chain_file,
        config.pending_file.as_deref(),
        config.alice_balance,
    );
    match result {
        Ok(status) => http_json_response(200, render_chain_check_json("chain-check", &status)),
        Err(error) => {
            let args = private_devnet_http_runner_args("chain-check", config);
            http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(&args, &error),
            )
        }
    }
}

fn pending_status_http_response(
    config: &PrivateDevnetHttpServerConfig,
    pending_file: &str,
) -> PrivateDevnetHttpResponse {
    match private_devnet_file_status_with_pending_file(
        &config.chain_file,
        pending_file,
        config.alice_balance,
    ) {
        Ok(status) => http_json_response(200, render_node_status_json("status", &status)),
        Err(error) => {
            let args = private_devnet_http_runner_args("status", config);
            http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(&args, &error),
            )
        }
    }
}

fn pending_mempool_http_response(
    config: &PrivateDevnetHttpServerConfig,
    pending_file: &str,
) -> PrivateDevnetHttpResponse {
    match private_devnet_file_mempool_detail_with_pending_file_data(
        &config.chain_file,
        pending_file,
        config.alice_balance,
    ) {
        Ok(detail) => {
            http_json_response(200, render_mempool_detail_json("mempool-detail", &detail))
        }
        Err(error) => {
            let args = private_devnet_http_runner_args("mempool-detail", config);
            http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(&args, &error),
            )
        }
    }
}

fn transaction_detail_http_response(
    config: &PrivateDevnetHttpServerConfig,
    tx_hash: Hash32,
) -> PrivateDevnetHttpResponse {
    if let Some(pending_file) = &config.pending_file {
        return match private_devnet_file_transaction_detail_with_pending_file_data(
            &config.chain_file,
            pending_file,
            config.alice_balance,
            tx_hash,
        ) {
            Ok(detail) => http_json_response(200, render_transaction_detail_json(&detail)),
            Err(NodeRunnerError::Explorer(ExplorerError::TransactionNotFound)) => {
                http_error_response(
                    404,
                    "transaction_not_found",
                    "transaction was not found in confirmed or pending private-devnet state",
                )
            }
            Err(error) => http_json_response(
                node_runner_error_http_status(&error),
                render_node_runner_error_json(
                    &[
                        "transaction-detail".to_string(),
                        "--format".to_string(),
                        "json".to_string(),
                    ],
                    &error,
                ),
            ),
        };
    }

    match private_devnet_file_confirmed_transaction_detail(
        &config.chain_file,
        config.alice_balance,
        tx_hash,
    ) {
        Ok(Some(detail)) => http_json_response(
            200,
            render_transaction_detail_json(&PrivateDevnetTransactionDetail::Confirmed(detail)),
        ),
        Ok(None) => http_error_response(
            404,
            "transaction_not_found",
            "transaction was not found in confirmed private-devnet blocks",
        ),
        Err(error) => http_error_response(500, "node_error", &format!("node error: {error:?}")),
    }
}

fn node_runner_error_http_status(error: &NodeRunnerError) -> u16 {
    match error {
        NodeRunnerError::InvalidAddress(_)
        | NodeRunnerError::InvalidDraftLine(_)
        | NodeRunnerError::InvalidFormat(_)
        | NodeRunnerError::InvalidHash { .. }
        | NodeRunnerError::InvalidJson(_)
        | NodeRunnerError::InvalidNumber { .. }
        | NodeRunnerError::MissingDraftField(_)
        | NodeRunnerError::MissingJsonField(_)
        | NodeRunnerError::MissingFlag(_)
        | NodeRunnerError::DuplicateDraftField(_)
        | NodeRunnerError::DuplicateJsonField(_)
        | NodeRunnerError::UnsupportedDraftVersion { .. }
        | NodeRunnerError::UnexpectedArgument(_)
        | NodeRunnerError::UnknownDraftField(_)
        | NodeRunnerError::UnknownJsonField(_)
        | NodeRunnerError::UnknownFlag(_)
        | NodeRunnerError::WrongDraftChainId { .. } => 400,
        NodeRunnerError::Node(
            NodeError::MissingSender
            | NodeError::Transaction(_)
            | NodeError::TransactionSignature(_)
            | NodeError::Mempool(_),
        ) => 400,
        NodeRunnerError::Explorer(
            ExplorerError::AccountNotFound
            | ExplorerError::BlockNotFound
            | ExplorerError::TransactionNotFound,
        ) => 404,
        NodeRunnerError::SnapshotNotFound(_) => 404,
        NodeRunnerError::SnapshotTargetExists(_) => 409,
        NodeRunnerError::InvalidSnapshotManifest(_) => 400,
        // Faucet refusals (over cap or exhausted) are client-visible rate limits.
        NodeRunnerError::FaucetRefused(_) => 429,
        NodeRunnerError::InvalidNetwork(_) => 400,
        _ => 500,
    }
}

fn split_http_target(target: &str) -> (&str, Option<&str>) {
    match target.split_once('?') {
        Some((path, query)) => (path, Some(query)),
        None => (target, None),
    }
}

fn query_value<'a>(query: Option<&'a str>, key: &str) -> Option<&'a str> {
    query.and_then(|query| {
        query.split('&').find_map(|pair| {
            let (candidate, value) = pair.split_once('=')?;
            (candidate == key).then_some(value)
        })
    })
}

fn required_decoded_query_value(
    query: Option<&str>,
    key: &str,
    flag: &'static str,
) -> Result<String, NodeRunnerError> {
    query_value(query, key)
        .map(|value| percent_decode_query_value(key, value))
        .transpose()?
        .ok_or(NodeRunnerError::MissingFlag(flag))
}

fn percent_decode_query_value(key: &str, value: &str) -> Result<String, NodeRunnerError> {
    let bytes = value.as_bytes();
    let mut decoded = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        match bytes[index] {
            b'+' => {
                decoded.push(b' ');
                index += 1;
            }
            b'%' => {
                if index + 2 >= bytes.len() {
                    return Err(invalid_query_encoding(key));
                }
                let high =
                    hex_value(bytes[index + 1]).ok_or_else(|| invalid_query_encoding(key))?;
                let low = hex_value(bytes[index + 2]).ok_or_else(|| invalid_query_encoding(key))?;
                decoded.push((high << 4) | low);
                index += 3;
            }
            byte => {
                decoded.push(byte);
                index += 1;
            }
        }
    }
    String::from_utf8(decoded).map_err(|_| invalid_query_encoding(key))
}

fn invalid_query_encoding(key: &str) -> NodeRunnerError {
    NodeRunnerError::InvalidFormat(format!(
        "invalid percent-encoding for query parameter {key}"
    ))
}

fn hex_value(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

fn http_json_response(status_code: u16, body: String) -> PrivateDevnetHttpResponse {
    PrivateDevnetHttpResponse {
        status_code,
        reason: http_reason(status_code),
        body,
    }
}

fn http_error_response(status_code: u16, code: &str, message: &str) -> PrivateDevnetHttpResponse {
    http_json_response(
        status_code,
        render_private_devnet_http_error_json(code, message),
    )
}

fn http_reason(status_code: u16) -> &'static str {
    match status_code {
        200 => "OK",
        201 => "Created",
        202 => "Accepted",
        400 => "Bad Request",
        404 => "Not Found",
        405 => "Method Not Allowed",
        500 => "Internal Server Error",
        501 => "Not Implemented",
        _ => "Unknown",
    }
}

fn render_private_devnet_http_health_json() -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"format_version\": {},",
        json_string("xriq-node-http-v1")
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"status\": {}", json_string("ok")).expect("write to String");
    output.push('}');
    output
}

fn render_private_devnet_http_error_json(code: &str, message: &str) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"format_version\": {},",
        json_string("xriq-node-http-v1")
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"ok\": false,").expect("write to String");
    writeln!(&mut output, "  \"error\": {{").expect("write to String");
    writeln!(&mut output, "    \"code\": {},", json_string(code)).expect("write to String");
    writeln!(&mut output, "    \"message\": {}", json_string(message)).expect("write to String");
    output.push_str("  }\n}");
    output
}

pub fn private_devnet_file_status(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<NodeStatus, NodeError> {
    let store = FileChainStore::open(chain_file).map_err(NodeError::Storage)?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node = XriqNode::from_genesis_replaying_store(&genesis, store)?;
    Ok(node_status(&node))
}

pub fn private_devnet_file_confirmed_transaction_detail(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    tx_hash: Hash32,
) -> Result<Option<PrivateDevnetConfirmedTransactionDetail>, NodeError> {
    let store = FileChainStore::open(chain_file).map_err(NodeError::Storage)?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node = XriqNode::from_genesis_replaying_store(&genesis, store)?;
    for record in node.store().blocks_by_height_desc(node.store().len()) {
        for (transaction_index, transaction) in record.block.transactions.iter().enumerate() {
            if transaction_hash(transaction) == tx_hash {
                return Ok(Some(PrivateDevnetConfirmedTransactionDetail {
                    tx_hash,
                    status: "confirmed",
                    block_height: record.block.header.height,
                    block_hash: record.block_hash,
                    transaction_index,
                    transaction: transaction.clone(),
                }));
            }
        }
    }
    Ok(None)
}

pub fn private_devnet_file_status_with_pending_file(
    chain_file: impl AsRef<Path>,
    pending_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<NodeStatus, NodeRunnerError> {
    let node = private_devnet_node_with_pending_file(chain_file, pending_file, alice_balance)?;
    Ok(node_status(&node))
}

pub fn private_devnet_file_chain_check<P, F>(
    chain_file: P,
    pending_file: Option<F>,
    alice_balance: Option<XriqAmount>,
) -> Result<PrivateDevnetChainCheckStatus, NodeRunnerError>
where
    P: AsRef<Path>,
    F: AsRef<Path>,
{
    let status = if let Some(pending_file) = pending_file {
        private_devnet_file_status_with_pending_file(chain_file, pending_file, alice_balance)?
    } else {
        private_devnet_file_status(chain_file, alice_balance).map_err(NodeRunnerError::Node)?
    };
    Ok(PrivateDevnetChainCheckStatus {
        verified: true,
        status,
    })
}

pub fn private_devnet_file_mempool_detail_with_pending_file_data(
    chain_file: impl AsRef<Path>,
    pending_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<ExplorerMempoolDetail, NodeRunnerError> {
    let node = private_devnet_node_with_pending_file(chain_file, pending_file, alice_balance)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    Ok(explorer.mempool())
}

pub fn private_devnet_file_transaction_detail_with_pending_file_data(
    chain_file: impl AsRef<Path>,
    pending_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    tx_hash: Hash32,
) -> Result<PrivateDevnetTransactionDetail, NodeRunnerError> {
    if let Some(detail) = private_devnet_file_confirmed_transaction_detail(
        chain_file.as_ref(),
        alice_balance,
        tx_hash,
    )
    .map_err(NodeRunnerError::Node)?
    {
        return Ok(PrivateDevnetTransactionDetail::Confirmed(detail));
    }

    let node = private_devnet_node_with_pending_file(chain_file, pending_file, alice_balance)?;
    if let Some(entry) = node.mempool().entry(&tx_hash) {
        return Ok(PrivateDevnetTransactionDetail::Pending(
            PrivateDevnetPendingTransactionDetail {
                tx_hash: entry.tx_hash,
                status: "pending",
                received_order: entry.received_order,
                transaction: entry.tx.clone(),
            },
        ));
    }

    Err(NodeRunnerError::Explorer(
        ExplorerError::TransactionNotFound,
    ))
}

fn private_devnet_export_snapshot(
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
    snapshot_dir: &str,
) -> Result<PrivateDevnetSnapshotStatus, NodeRunnerError> {
    let status = if let Some(pending_file) = pending_file {
        private_devnet_file_status_with_pending_file(chain_file, pending_file, alice_balance)?
    } else {
        private_devnet_file_status(chain_file, alice_balance).map_err(NodeRunnerError::Node)?
    };
    let snapshot_dir_path = Path::new(snapshot_dir);
    prepare_new_snapshot_dir(snapshot_dir_path)?;

    let chain_snapshot_path = snapshot_dir_path.join(SNAPSHOT_CHAIN_FILE);
    copy_snapshot_file(Path::new(chain_file), &chain_snapshot_path)?;

    let pending_snapshot_path = if let Some(pending_file) = pending_file {
        let target = snapshot_dir_path.join(SNAPSHOT_PENDING_FILE);
        if Path::new(pending_file).exists() {
            copy_snapshot_file(Path::new(pending_file), &target)?;
        } else {
            write_snapshot_file(&target, "")?;
        }
        Some(target)
    } else {
        None
    };

    let exported = PrivateDevnetSnapshotStatus {
        snapshot_dir: snapshot_dir_path.to_string_lossy().to_string(),
        chain_file: chain_snapshot_path.to_string_lossy().to_string(),
        pending_file: pending_snapshot_path
            .as_ref()
            .map(|path| path.to_string_lossy().to_string()),
        status,
    };
    write_snapshot_file(
        &snapshot_dir_path.join(SNAPSHOT_MANIFEST_FILE),
        &render_snapshot_manifest_json(&exported),
    )?;
    Ok(exported)
}

fn private_devnet_import_snapshot(
    snapshot_dir: &str,
    chain_file: &str,
    pending_file: Option<&str>,
    alice_balance: Option<XriqAmount>,
) -> Result<PrivateDevnetSnapshotStatus, NodeRunnerError> {
    let snapshot_dir_path = Path::new(snapshot_dir);
    validate_snapshot_manifest(snapshot_dir_path)?;

    copy_snapshot_file_to_new_path(
        &snapshot_dir_path.join(SNAPSHOT_CHAIN_FILE),
        Path::new(chain_file),
    )?;
    let imported_pending_file = if let Some(pending_file) = pending_file {
        let source = snapshot_dir_path.join(SNAPSHOT_PENDING_FILE);
        if source.exists() {
            copy_snapshot_file_to_new_path(&source, Path::new(pending_file))?;
        } else {
            write_new_snapshot_file(Path::new(pending_file), "")?;
        }
        Some(pending_file.to_string())
    } else {
        None
    };

    let status = if let Some(pending_file) = pending_file {
        private_devnet_file_status_with_pending_file(chain_file, pending_file, alice_balance)?
    } else {
        private_devnet_file_status(chain_file, alice_balance).map_err(NodeRunnerError::Node)?
    };
    Ok(PrivateDevnetSnapshotStatus {
        snapshot_dir: snapshot_dir_path.to_string_lossy().to_string(),
        chain_file: chain_file.to_string(),
        pending_file: imported_pending_file,
        status,
    })
}

pub fn private_devnet_snapshot_list(
    snapshot_root: impl AsRef<Path>,
    limit: usize,
) -> Result<String, NodeRunnerError> {
    let snapshot_root = snapshot_root.as_ref();
    let snapshots = private_devnet_snapshot_list_data(snapshot_root, limit)?;
    Ok(render_snapshot_list(snapshot_root, &snapshots))
}

pub fn private_devnet_snapshot_list_data(
    snapshot_root: impl AsRef<Path>,
    limit: usize,
) -> Result<Vec<PrivateDevnetSnapshotSummary>, NodeRunnerError> {
    let snapshot_root = snapshot_root.as_ref();
    let entries =
        fs::read_dir(snapshot_root).map_err(|error| NodeRunnerError::SnapshotFileRead {
            path: snapshot_root.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    let mut snapshots = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|error| NodeRunnerError::SnapshotFileRead {
            path: snapshot_root.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
        let path = entry.path();
        let file_type = entry
            .file_type()
            .map_err(|error| NodeRunnerError::SnapshotFileRead {
                path: path.to_string_lossy().to_string(),
                error: error.to_string(),
            })?;
        if file_type.is_dir() && path.join(SNAPSHOT_MANIFEST_FILE).exists() {
            snapshots.push(read_private_devnet_snapshot_summary(&path)?);
        }
    }
    snapshots.sort_by(|left, right| {
        right
            .status
            .current_height
            .cmp(&left.status.current_height)
            .then_with(|| right.snapshot_name.cmp(&left.snapshot_name))
    });
    snapshots.truncate(limit);
    Ok(snapshots)
}

pub fn private_devnet_snapshot_latest(
    snapshot_root: impl AsRef<Path>,
) -> Result<String, NodeRunnerError> {
    let snapshot = private_devnet_snapshot_latest_data(snapshot_root)?;
    Ok(render_snapshot_detail(&snapshot))
}

pub fn private_devnet_snapshot_latest_data(
    snapshot_root: impl AsRef<Path>,
) -> Result<PrivateDevnetSnapshotSummary, NodeRunnerError> {
    let snapshot_root = snapshot_root.as_ref();
    private_devnet_snapshot_list_data(snapshot_root, 1)?
        .into_iter()
        .next()
        .ok_or_else(|| {
            NodeRunnerError::SnapshotNotFound(snapshot_root.to_string_lossy().to_string())
        })
}

pub fn private_devnet_snapshot_latest_check(
    snapshot_root: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<String, NodeRunnerError> {
    let status = private_devnet_snapshot_latest_check_data(snapshot_root, alice_balance)?;
    Ok(render_snapshot_check(&status))
}

pub fn private_devnet_snapshot_latest_check_data(
    snapshot_root: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<PrivateDevnetSnapshotCheckStatus, NodeRunnerError> {
    let snapshot = private_devnet_snapshot_latest_data(snapshot_root)?;
    private_devnet_snapshot_check_summary(snapshot, alice_balance)
}

pub fn private_devnet_snapshot_detail(
    snapshot_dir: impl AsRef<Path>,
) -> Result<String, NodeRunnerError> {
    let snapshot = private_devnet_snapshot_detail_data(snapshot_dir)?;
    Ok(render_snapshot_detail(&snapshot))
}

pub fn private_devnet_snapshot_detail_data(
    snapshot_dir: impl AsRef<Path>,
) -> Result<PrivateDevnetSnapshotSummary, NodeRunnerError> {
    read_private_devnet_snapshot_summary(snapshot_dir.as_ref())
}

pub fn private_devnet_snapshot_check(
    snapshot_dir: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<String, NodeRunnerError> {
    let status = private_devnet_snapshot_check_data(snapshot_dir, alice_balance)?;
    Ok(render_snapshot_check(&status))
}

pub fn private_devnet_snapshot_check_data(
    snapshot_dir: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<PrivateDevnetSnapshotCheckStatus, NodeRunnerError> {
    let snapshot = read_private_devnet_snapshot_summary(snapshot_dir.as_ref())?;
    private_devnet_snapshot_check_summary(snapshot, alice_balance)
}

fn private_devnet_snapshot_check_summary(
    snapshot: PrivateDevnetSnapshotSummary,
    alice_balance: Option<XriqAmount>,
) -> Result<PrivateDevnetSnapshotCheckStatus, NodeRunnerError> {
    let check = private_devnet_file_chain_check(
        &snapshot.chain_file,
        snapshot.pending_file.as_deref(),
        alice_balance,
    )?;
    let replayed_status = check.status;
    let mismatches = snapshot_status_mismatches(&snapshot.status, &replayed_status);
    Ok(PrivateDevnetSnapshotCheckStatus {
        verified: check.verified && mismatches.is_empty(),
        snapshot,
        replayed_status,
        mismatches,
    })
}

pub fn private_devnet_file_submit_pending_transfer_body(
    chain_file: impl AsRef<Path>,
    pending_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    body: &str,
) -> Result<PrivateDevnetPendingTransactionDetail, NodeRunnerError> {
    let genesis = private_devnet_runner_genesis(alice_balance);
    let transfer = parse_private_devnet_transfer_body(body, &genesis.chain_id)?;
    let mut node =
        private_devnet_node_with_pending_file(chain_file, pending_file.as_ref(), alice_balance)?;
    let transaction = private_devnet_runner_transaction(&node, &transfer);
    let tx_hash = transaction_hash(&transaction);
    node.submit_transaction(tx_hash, transaction.clone())
        .map_err(NodeRunnerError::Node)?;
    append_pending_transaction_record(pending_file.as_ref(), tx_hash, &transaction)?;
    let entry = node
        .mempool()
        .entry(&tx_hash)
        .expect("validated pending transaction was inserted");
    Ok(PrivateDevnetPendingTransactionDetail {
        tx_hash: entry.tx_hash,
        status: "pending",
        received_order: entry.received_order,
        transaction: entry.tx.clone(),
    })
}

fn private_devnet_node_with_pending_file(
    chain_file: impl AsRef<Path>,
    pending_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<XriqNode<FileChainStore>, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let mut node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let pending_load = read_pending_transaction_records(pending_file.as_ref())?;
    quarantine_corrupt_pending_lines(pending_file.as_ref(), &pending_load)?;
    for (tx_hash, transaction) in pending_load.records {
        if private_devnet_file_confirmed_transaction_detail(
            node.store().path(),
            alice_balance,
            tx_hash,
        )
        .map_err(NodeRunnerError::Node)?
        .is_some()
        {
            continue;
        }
        match node.submit_transaction(tx_hash, transaction) {
            Ok(()) => {}
            // Idempotent replay: a duplicate pending entry (for example a line
            // written twice by a crash mid-append or a double-write) must not
            // brick startup. The transaction is already in the mempool, so skip
            // the duplicate instead of returning an error.
            Err(NodeError::Mempool(MempoolError::DuplicateTransaction)) => {}
            Err(error) => return Err(NodeRunnerError::Node(error)),
        }
    }
    Ok(node)
}

pub fn private_devnet_file_transaction_detail_data<P, D>(
    chain_file: P,
    draft_file: Option<D>,
    alice_balance: Option<XriqAmount>,
    tx_hash: Hash32,
) -> Result<PrivateDevnetTransactionDetail, NodeRunnerError>
where
    P: AsRef<Path>,
    D: AsRef<Path>,
{
    if let Some(detail) = private_devnet_file_confirmed_transaction_detail(
        chain_file.as_ref(),
        alice_balance,
        tx_hash,
    )
    .map_err(NodeRunnerError::Node)?
    {
        return Ok(PrivateDevnetTransactionDetail::Confirmed(detail));
    }

    if let Some(draft_file) = draft_file {
        let store = FileChainStore::open(chain_file.as_ref())
            .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
        let genesis = private_devnet_runner_genesis(alice_balance);
        let mut node = XriqNode::from_genesis_replaying_store(&genesis, store)
            .map_err(NodeRunnerError::Node)?;
        let transfer = read_private_devnet_transfer_draft(draft_file, &genesis.chain_id)?;
        let transaction = private_devnet_runner_transaction(&node, &transfer);
        node.submit_transaction_with_canonical_hash(transaction)
            .map_err(NodeRunnerError::Node)?;
        if let Some(entry) = node.mempool().entry(&tx_hash) {
            return Ok(PrivateDevnetTransactionDetail::Pending(
                PrivateDevnetPendingTransactionDetail {
                    tx_hash: entry.tx_hash,
                    status: "pending",
                    received_order: entry.received_order,
                    transaction: entry.tx.clone(),
                },
            ));
        }
    }

    Err(NodeRunnerError::Explorer(
        ExplorerError::TransactionNotFound,
    ))
}

pub fn private_devnet_file_produce_transfer_block(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    transfer: PrivateDevnetTransferInput,
) -> Result<ProducedTransferBlockStatus, NodeError> {
    let store = FileChainStore::open(chain_file).map_err(NodeError::Storage)?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let mut node = XriqNode::from_genesis_replaying_store(&genesis, store)?;
    let transaction = private_devnet_runner_transaction(&node, &transfer);
    let transaction_hash = node.submit_transaction_with_canonical_hash(transaction)?;
    let produced = node.produce_next_block_with_private_devnet_signature(
        transfer.timestamp_ms,
        transfer.consensus_round,
    )?;
    Ok(ProducedTransferBlockStatus {
        transaction_hash,
        block_hash: produced.block_hash,
        applied_transactions: produced.applied_transactions,
        status: node_status(&node),
    })
}

pub fn private_devnet_file_produce_draft_block(
    chain_file: impl AsRef<Path>,
    draft_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    timestamp_ms: u64,
    consensus_round: u64,
) -> Result<ProducedTransferBlockStatus, NodeRunnerError> {
    let genesis = private_devnet_runner_genesis(alice_balance);
    let mut transfer = read_private_devnet_transfer_draft(draft_file, &genesis.chain_id)?;
    transfer.timestamp_ms = timestamp_ms;
    transfer.consensus_round = consensus_round;
    private_devnet_file_produce_transfer_block(chain_file, alice_balance, transfer)
        .map_err(NodeRunnerError::Node)
}

pub fn private_devnet_file_produce_pending_block(
    chain_file: impl AsRef<Path>,
    pending_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    timestamp_ms: u64,
    consensus_round: u64,
) -> Result<ProducedPendingBlockStatus, NodeRunnerError> {
    let mut node =
        private_devnet_node_with_pending_file(chain_file, pending_file.as_ref(), alice_balance)?;
    let produced = node
        .produce_next_block_with_private_devnet_signature(timestamp_ms, consensus_round)
        .map_err(NodeRunnerError::Node)?;
    let included_transaction_hashes = produced
        .block
        .transactions
        .iter()
        .map(transaction_hash)
        .collect::<Vec<_>>();
    let remaining_records = node
        .mempool()
        .ordered_entries()
        .into_iter()
        .map(|entry| (entry.tx_hash, entry.tx.clone()))
        .collect::<Vec<_>>();
    write_pending_transaction_records(pending_file.as_ref(), &remaining_records)?;

    Ok(ProducedPendingBlockStatus {
        block_hash: produced.block_hash,
        included_transaction_hashes,
        applied_transactions: produced.applied_transactions,
        status: node_status(&node),
    })
}

pub fn private_devnet_file_preflight_transfer(
    chain_file: impl AsRef<Path>,
    pending_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    input: PrivateDevnetPreflightTransferInput,
) -> Result<PrivateDevnetPreflightTransferStatus, NodeRunnerError> {
    let (preflight_account, transaction_hash, transfer_body) = {
        let node = private_devnet_node_with_pending_file(
            chain_file.as_ref(),
            pending_file.as_ref(),
            alice_balance,
        )?;
        let preflight_account = node
            .ledger()
            .account(&input.from)
            .ok_or(NodeRunnerError::Node(NodeError::MissingSender))?;
        let transfer = PrivateDevnetTransferInput {
            from: input.from.clone(),
            to: input.to.clone(),
            amount: input.amount,
            fee: input.fee,
            nonce: preflight_account.nonce,
            expires_at_height: input.expires_at_height,
            timestamp_ms: input.timestamp_ms,
            consensus_round: input.consensus_round,
        };
        let transaction = private_devnet_runner_transaction(&node, &transfer);
        let transaction_hash = transaction_hash(&transaction);
        (
            preflight_account,
            transaction_hash,
            render_pending_preflight_transfer_body(&transaction),
        )
    };

    let pending_detail = private_devnet_file_submit_pending_transfer_body(
        chain_file.as_ref(),
        pending_file.as_ref(),
        alice_balance,
        &transfer_body,
    )?;
    if pending_detail.tx_hash != transaction_hash {
        return Err(NodeRunnerError::Explorer(
            ExplorerError::TransactionNotFound,
        ));
    }

    let produced = private_devnet_file_produce_pending_block(
        chain_file.as_ref(),
        pending_file.as_ref(),
        alice_balance,
        input.timestamp_ms,
        input.consensus_round,
    )?;
    if !produced
        .included_transaction_hashes
        .contains(&transaction_hash)
    {
        return Err(NodeRunnerError::Explorer(
            ExplorerError::TransactionNotFound,
        ));
    }

    let confirmed = match private_devnet_file_transaction_detail_with_pending_file_data(
        chain_file.as_ref(),
        pending_file.as_ref(),
        alice_balance,
        transaction_hash,
    )? {
        PrivateDevnetTransactionDetail::Confirmed(detail) => detail,
        PrivateDevnetTransactionDetail::Pending(_) => {
            return Err(NodeRunnerError::Explorer(
                ExplorerError::TransactionNotFound,
            ));
        }
    };
    let final_account = private_devnet_file_account_detail_data(
        chain_file.as_ref(),
        alice_balance,
        input.from.clone(),
    )?;

    Ok(PrivateDevnetPreflightTransferStatus {
        from: input.from,
        to: input.to,
        amount: input.amount,
        fee: input.fee,
        preflight_balance: preflight_account.balance,
        preflight_nonce: preflight_account.nonce,
        transaction_hash,
        block_hash: produced.block_hash,
        confirmed_block_height: confirmed.block_height,
        confirmed_transaction_index: confirmed.transaction_index,
        final_balance: final_account.balance,
        final_nonce: final_account.nonce,
        status: produced.status,
    })
}

pub fn private_devnet_file_submit_transfer_body(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    body: &str,
) -> Result<ProducedTransferBlockStatus, NodeRunnerError> {
    let genesis = private_devnet_runner_genesis(alice_balance);
    let transfer = parse_private_devnet_transfer_body(body, &genesis.chain_id)?;
    private_devnet_file_produce_transfer_block(chain_file, alice_balance, transfer)
        .map_err(NodeRunnerError::Node)
}

pub fn private_devnet_file_submit_transfer_draft_body(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    draft_text: &str,
) -> Result<ProducedTransferBlockStatus, NodeRunnerError> {
    private_devnet_file_submit_transfer_body(chain_file, alice_balance, draft_text)
}

pub fn private_devnet_file_explorer_overview(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    limit: usize,
) -> Result<String, NodeError> {
    let (overview, latest_blocks) =
        private_devnet_file_explorer_overview_data(chain_file, alice_balance, limit)?;
    Ok(render_overview(&overview, &latest_blocks))
}

pub fn private_devnet_file_explorer_overview_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    limit: usize,
) -> Result<(ExplorerOverview, Vec<ExplorerBlockSummary>), NodeError> {
    let store = FileChainStore::open(chain_file).map_err(NodeError::Storage)?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node = XriqNode::from_genesis_replaying_store(&genesis, store)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    Ok((explorer.overview(), explorer.latest_blocks(limit)))
}

pub fn private_devnet_file_block_list(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    limit: usize,
) -> Result<String, NodeRunnerError> {
    let blocks = private_devnet_file_block_list_data(chain_file, alice_balance, limit)?;
    Ok(render_latest_blocks(&blocks))
}

pub fn private_devnet_file_block_list_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    limit: usize,
) -> Result<Vec<ExplorerBlockSummary>, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    Ok(explorer.latest_blocks(limit))
}

pub fn private_devnet_file_block_detail(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    height: u64,
) -> Result<String, NodeRunnerError> {
    let detail = private_devnet_file_block_detail_data(chain_file, alice_balance, height)?;
    Ok(render_block_detail(&detail))
}

pub fn private_devnet_file_block_detail_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    height: u64,
) -> Result<ExplorerBlockDetail, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    explorer
        .block_by_height(height)
        .map_err(NodeRunnerError::Explorer)
}

pub fn private_devnet_file_block_detail_by_hash(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    block_hash: Hash32,
) -> Result<String, NodeRunnerError> {
    let detail =
        private_devnet_file_block_detail_by_hash_data(chain_file, alice_balance, block_hash)?;
    Ok(render_block_detail(&detail))
}

pub fn private_devnet_file_block_detail_by_hash_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    block_hash: Hash32,
) -> Result<ExplorerBlockDetail, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    explorer
        .block_by_hash(&block_hash)
        .map_err(NodeRunnerError::Explorer)
}

pub fn private_devnet_file_latest_block_detail(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<String, NodeRunnerError> {
    let detail = private_devnet_file_latest_block_detail_data(chain_file, alice_balance)?;
    Ok(render_block_detail(&detail))
}

pub fn private_devnet_file_latest_block_detail_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
) -> Result<ExplorerBlockDetail, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    explorer.latest_block().map_err(NodeRunnerError::Explorer)
}

pub fn private_devnet_file_account_list(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    limit: usize,
) -> Result<String, NodeRunnerError> {
    let accounts = private_devnet_file_account_list_data(chain_file, alice_balance, limit)?;
    Ok(render_accounts(&accounts))
}

pub fn private_devnet_file_account_list_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    limit: usize,
) -> Result<Vec<ExplorerAccountDetail>, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    Ok(explorer.accounts(limit))
}

pub fn private_devnet_file_account_detail(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    address: Address,
) -> Result<String, NodeRunnerError> {
    let detail = private_devnet_file_account_detail_data(chain_file, alice_balance, address)?;
    Ok(render_account_detail(&detail))
}

pub fn private_devnet_file_account_detail_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    address: Address,
) -> Result<ExplorerAccountDetail, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    explorer
        .account(&address)
        .map_err(NodeRunnerError::Explorer)
}

pub fn private_devnet_file_account_transactions(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    address: Address,
    limit: usize,
) -> Result<String, NodeRunnerError> {
    let transactions = private_devnet_file_account_transactions_data(
        chain_file,
        alice_balance,
        address.clone(),
        limit,
    )?;
    Ok(render_account_transactions(&address, &transactions))
}

pub fn private_devnet_file_account_transactions_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    address: Address,
    limit: usize,
) -> Result<Vec<ExplorerAccountTransaction>, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    Ok(explorer.account_transactions(&address, limit))
}

pub fn private_devnet_file_latest_transactions(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    limit: usize,
) -> Result<String, NodeRunnerError> {
    let transactions =
        private_devnet_file_latest_transactions_data(chain_file, alice_balance, limit)?;
    Ok(render_latest_transactions(&transactions))
}

pub fn private_devnet_file_latest_transactions_data(
    chain_file: impl AsRef<Path>,
    alice_balance: Option<XriqAmount>,
    limit: usize,
) -> Result<Vec<ExplorerConfirmedTransaction>, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    Ok(explorer.latest_transactions(limit))
}

pub fn private_devnet_file_mempool_detail(
    chain_file: impl AsRef<Path>,
    draft_file: Option<impl AsRef<Path>>,
    alice_balance: Option<XriqAmount>,
) -> Result<String, NodeRunnerError> {
    let detail = private_devnet_file_mempool_detail_data(chain_file, draft_file, alice_balance)?;
    Ok(render_mempool(&detail))
}

pub fn private_devnet_file_mempool_detail_data(
    chain_file: impl AsRef<Path>,
    draft_file: Option<impl AsRef<Path>>,
    alice_balance: Option<XriqAmount>,
) -> Result<ExplorerMempoolDetail, NodeRunnerError> {
    private_devnet_file_mempool_detail_with_sources_data(
        chain_file,
        draft_file,
        None::<&Path>,
        alice_balance,
    )
}

pub fn private_devnet_file_mempool_detail_with_sources_data<P, D, F>(
    chain_file: P,
    draft_file: Option<D>,
    pending_file: Option<F>,
    alice_balance: Option<XriqAmount>,
) -> Result<ExplorerMempoolDetail, NodeRunnerError>
where
    P: AsRef<Path>,
    D: AsRef<Path>,
    F: AsRef<Path>,
{
    let genesis = private_devnet_runner_genesis(alice_balance);
    let mut node = if let Some(pending_file) = pending_file {
        private_devnet_node_with_pending_file(chain_file.as_ref(), pending_file, alice_balance)?
    } else {
        let store = FileChainStore::open(chain_file.as_ref())
            .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?
    };
    if let Some(draft_file) = draft_file {
        let transfer = read_private_devnet_transfer_draft(draft_file, &genesis.chain_id)?;
        let transaction = private_devnet_runner_transaction(&node, &transfer);
        node.submit_transaction_with_canonical_hash(transaction)
            .map_err(NodeRunnerError::Node)?;
    }
    let explorer = ExplorerService::new(node.rpc_service(), node.store());
    Ok(explorer.mempool())
}

fn run_status_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let status =
        private_devnet_file_status(chain_file, alice_balance).map_err(NodeRunnerError::Node)?;
    Ok(match output_format {
        RunnerOutputFormat::Text => NodeRunnerOutput::Status(status),
        RunnerOutputFormat::Json => {
            NodeRunnerOutput::Json(render_node_status_json("status", &status))
        }
    })
}

const PEER_BLOCKS_DEFAULT_LIMIT: usize = 128;
const PEER_BLOCKS_MAX_LIMIT: usize = 1024;

fn run_peer_blocks_export_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--network",
        "--from-height",
        "--limit",
        "--format",
    ])?;
    // JSON only; the payload is hex-encoded binary block data.
    let _ = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.optional("--pending-file").unwrap_or("");
    let genesis = parse_runner_genesis(&flags)?;
    let from_height = match flags.optional("--from-height") {
        Some(value) => value
            .parse::<u64>()
            .map_err(|_| NodeRunnerError::InvalidNumber {
                flag: "--from-height",
                value: value.to_string(),
            })?,
        None => 1,
    };
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(PEER_BLOCKS_DEFAULT_LIMIT)
        .min(PEER_BLOCKS_MAX_LIMIT);

    let node = open_peer_node(chain_file, pending_file, genesis)?;
    let network = node.ledger().config().chain_id.clone();
    let bytes = node
        .export_peer_blocks(from_height, limit)
        .map_err(NodeRunnerError::Node)?;
    let current_height = node.ledger().current_height();
    let json = format!(
        "{{\n  \"command\": \"peer-blocks-export\",\n  \"network\": {},\n  \"from_height\": {from_height},\n  \"current_height\": {current_height},\n  \"encoding\": \"xriq-peer-blocks-v1-hex\",\n  \"blocks_hex\": {}\n}}",
        json_string(&network),
        json_string(&bytes_hex(&bytes))
    );
    Ok(NodeRunnerOutput::Json(json))
}

fn extract_json_string<'a>(body: &'a str, key: &str) -> Option<&'a str> {
    let marker = format!("\"{key}\": \"");
    let start = body.find(&marker)? + marker.len();
    let rest = &body[start..];
    let end = rest.find('"')?;
    Some(&rest[..end])
}

fn extract_json_u64(body: &str, key: &str) -> Option<u64> {
    let marker = format!("\"{key}\": ");
    let start = body.find(&marker)? + marker.len();
    let rest = &body[start..];
    let end = rest
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(rest.len());
    rest[..end].parse::<u64>().ok()
}

fn parse_peer_blocks_response(body: &str) -> Result<(u64, Vec<u8>), NodeRunnerError> {
    let current_height = extract_json_u64(body, "current_height").ok_or_else(|| {
        NodeRunnerError::PeerSyncError("peer response missing current_height".to_string())
    })?;
    let hex = extract_json_string(body, "blocks_hex").ok_or_else(|| {
        NodeRunnerError::PeerSyncError("peer response missing blocks_hex".to_string())
    })?;
    let bytes = parse_hex_bytes(hex).map_err(|_| {
        NodeRunnerError::PeerSyncError("peer response blocks_hex is not valid hex".to_string())
    })?;
    Ok((current_height, bytes))
}

// Minimal blocking HTTP GET for peer sync (the peer server responds once and
// closes the connection). Only http:// is supported for the private testnet.
fn peer_http_get(base_url: &str, path_and_query: &str) -> Result<String, NodeRunnerError> {
    let authority = base_url.strip_prefix("http://").ok_or_else(|| {
        NodeRunnerError::PeerSyncError(format!("peer url must start with http:// (got {base_url})"))
    })?;
    let authority = authority.split('/').next().unwrap_or(authority);
    let (host, port) = match authority.rsplit_once(':') {
        Some((host, port)) => {
            let port = port.parse::<u16>().map_err(|_| {
                NodeRunnerError::PeerSyncError(format!("invalid peer port in {base_url}"))
            })?;
            (host, port)
        }
        None => (authority, 80),
    };
    if host.is_empty() {
        return Err(NodeRunnerError::PeerSyncError(format!(
            "missing peer host in {base_url}"
        )));
    }
    let mut stream = TcpStream::connect((host, port)).map_err(|error| {
        NodeRunnerError::PeerSyncError(format!("could not connect to {host}:{port}: {error}"))
    })?;
    let _ = stream.set_read_timeout(Some(Duration::from_secs(10)));
    let _ = stream.set_write_timeout(Some(Duration::from_secs(10)));
    let request = format!(
        "GET {path_and_query} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: xriq-peer-sync\r\nConnection: close\r\n\r\n"
    );
    stream.write_all(request.as_bytes()).map_err(|error| {
        NodeRunnerError::PeerSyncError(format!("could not send request: {error}"))
    })?;
    let mut response = Vec::new();
    stream.read_to_end(&mut response).map_err(|error| {
        NodeRunnerError::PeerSyncError(format!("could not read response: {error}"))
    })?;
    let response = String::from_utf8_lossy(&response);
    let (head, body) = response.split_once("\r\n\r\n").ok_or_else(|| {
        NodeRunnerError::PeerSyncError("malformed HTTP response (no header/body split)".to_string())
    })?;
    let status_line = head.lines().next().unwrap_or("");
    if status_line.split_whitespace().nth(1) != Some("200") {
        return Err(NodeRunnerError::PeerSyncError(format!(
            "peer returned: {status_line}"
        )));
    }
    Ok(body.to_string())
}

// Peer wire protocol identifier used by the compatibility handshake. A node's
// network is its genesis chain id (checked separately); the protocol must also
// match before any blocks are pulled, so a follower never imports a range from
// an incompatible wire format.
const PEER_PROTOCOL: &str = "xriq-peer-blocks-v1";

// Derive a stable, deterministic node id from a seed. This is a test-only
// identifier (the seed is not a keypair and the id is self-reported, not
// cryptographically proven); it exists so peers can be named and a node can
// recognize itself during discovery. Domain-separated to avoid collisions.
fn derive_node_id(seed: &str) -> String {
    let hash = xriq_crypto::digest(format!("xriq-node-id:{seed}").as_bytes());
    let mut id = String::from("xriqnode1");
    for byte in &hash.as_bytes()[..16] {
        write!(id, "{byte:02x}").expect("write to String");
    }
    id
}

struct PeerIdentity {
    network: String,
    protocol: String,
    current_height: u64,
    node_id: Option<String>,
}

fn parse_peer_identity_response(body: &str) -> Result<PeerIdentity, NodeRunnerError> {
    let network = extract_json_string(body, "network")
        .ok_or_else(|| NodeRunnerError::PeerSyncError("peer identity missing network".to_string()))?
        .to_string();
    let protocol = extract_json_string(body, "protocol")
        .ok_or_else(|| {
            NodeRunnerError::PeerSyncError("peer identity missing protocol".to_string())
        })?
        .to_string();
    let current_height = extract_json_u64(body, "current_height").ok_or_else(|| {
        NodeRunnerError::PeerSyncError("peer identity missing current_height".to_string())
    })?;
    // node_id is optional: a peer started without a --node-seed reports null.
    let node_id = extract_json_string(body, "node_id").map(str::to_string);
    Ok(PeerIdentity {
        network,
        protocol,
        current_height,
        node_id,
    })
}

fn peer_compatibility_error(identity: &PeerIdentity, own_network: &str) -> Option<String> {
    if identity.network != own_network {
        return Some(format!(
            "peer network {:?} does not match {:?}",
            identity.network, own_network
        ));
    }
    if identity.protocol != PEER_PROTOCOL {
        return Some(format!(
            "peer protocol {:?} does not match {:?}",
            identity.protocol, PEER_PROTOCOL
        ));
    }
    None
}

// A peers file lists one `http://host:port` peer per line; blank lines and
// lines starting with `#` are ignored. The lenient reader may return an empty
// list (used for advertisement); `parse_peers_file` additionally requires at
// least one peer (used for the follower's `--peers-file` input).
fn read_peers_file_lenient(path: &str) -> Result<Vec<String>, NodeRunnerError> {
    let contents = fs::read_to_string(path).map_err(|error| {
        NodeRunnerError::PeerSyncError(format!("could not read peers file {path}: {error}"))
    })?;
    Ok(contents
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .map(str::to_string)
        .collect())
}

fn parse_peers_file(path: &str) -> Result<Vec<String>, NodeRunnerError> {
    let peers = read_peers_file_lenient(path)?;
    if peers.is_empty() {
        return Err(NodeRunnerError::PeerSyncError(format!(
            "peers file {path} lists no peers"
        )));
    }
    Ok(peers)
}

// Extract the string entries of a `"peers": [ ... ]` array from a peer's
// discovery response. The entries are bare `http://host:port` URLs (no `]` or
// `"` except as delimiters), so a simple quoted-token scan is sufficient.
fn parse_advertised_peers(body: &str) -> Vec<String> {
    let marker = "\"peers\": [";
    let Some(start) = body.find(marker) else {
        return Vec::new();
    };
    let rest = &body[start + marker.len()..];
    let inner = &rest[..rest.find(']').unwrap_or(rest.len())];
    let mut peers = Vec::new();
    let mut cursor = inner;
    while let Some(open) = cursor.find('"') {
        let after = &cursor[open + 1..];
        let Some(close) = after.find('"') else {
            break;
        };
        peers.push(after[..close].to_string());
        cursor = &after[close + 1..];
    }
    peers
}

fn peer_fetch_peers(peer: &str) -> Result<Vec<String>, NodeRunnerError> {
    Ok(parse_advertised_peers(&peer_http_get(
        peer,
        "/v1/peer/peers",
    )?))
}

struct SinglePeerSyncOutcome {
    applied: usize,
    rounds: usize,
    peer_current_height: u64,
}

// Handshake with one peer: fetch its identity and refuse a mismatched
// network/protocol before any blocks are exchanged.
fn handshake_peer(peer: &str, own_network: &str) -> Result<PeerIdentity, NodeRunnerError> {
    let identity = parse_peer_identity_response(&peer_http_get(peer, "/v1/peer/identity")?)?;
    if let Some(reason) = peer_compatibility_error(&identity, own_network) {
        return Err(NodeRunnerError::PeerSyncError(reason));
    }
    Ok(identity)
}

// Pull-and-import a compatible peer's blocks until caught up or max_rounds is
// reached. Every imported block is fully re-validated before commit (see
// import_peer_blocks).
fn pull_from_peer<S: ChainStore>(
    node: &mut XriqNode<S>,
    peer: &str,
    limit: usize,
    max_rounds: usize,
    mut peer_current_height: u64,
) -> Result<SinglePeerSyncOutcome, NodeRunnerError> {
    let mut applied = 0usize;
    let mut rounds = 0usize;
    while rounds < max_rounds {
        rounds += 1;
        let from_height = node.ledger().current_height() + 1;
        let body = peer_http_get(
            peer,
            &format!("/v1/peer/blocks?from_height={from_height}&limit={limit}"),
        )?;
        let (current_peer_height, bytes) = parse_peer_blocks_response(&body)?;
        peer_current_height = current_peer_height;
        let outcome = node
            .import_peer_blocks(&bytes)
            .map_err(NodeRunnerError::Node)?;
        applied += outcome.applied;
        if outcome.applied == 0 {
            break;
        }
    }
    Ok(SinglePeerSyncOutcome {
        applied,
        rounds,
        peer_current_height,
    })
}

fn run_peer_sync_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--peer",
        "--peers-file",
        "--discover",
        "--node-seed",
        "--network",
        "--alice-balance",
        "--limit",
        "--max-rounds",
        "--format",
    ])?;
    let _ = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.optional("--pending-file").unwrap_or("");
    // The follower's own id (from its --node-seed), used to recognize and skip
    // itself if discovery ever surfaces its own address.
    let own_node_id = flags.optional("--node-seed").map(derive_node_id);
    let genesis = parse_runner_genesis(&flags)?;
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(PEER_BLOCKS_DEFAULT_LIMIT)
        .min(PEER_BLOCKS_MAX_LIMIT);
    let max_rounds = flags
        .optional("--max-rounds")
        .map(|value| parse_usize("--max-rounds", value))
        .transpose()?
        .unwrap_or(1000);
    // --discover <max-peers> enables one-hop discovery (query each seed's
    // advertised peers and merge new ones) and caps the resulting peer set.
    let discover_cap = flags
        .optional("--discover")
        .map(|value| parse_usize("--discover", value))
        .transpose()?;

    // The peer set is --peer (single) and/or --peers-file (many). With a single
    // --peer and no file the semantics stay strict (any failure is fatal); with
    // a peers file an unreachable or incompatible peer is skipped and reported.
    let mut peers: Vec<String> = Vec::new();
    if let Some(peer) = flags.optional("--peer") {
        peers.push(peer.to_string());
    }
    let uses_peers_file = flags.optional("--peers-file").is_some();
    if let Some(path) = flags.optional("--peers-file") {
        peers.extend(parse_peers_file(path)?);
    }
    if peers.is_empty() {
        return Err(NodeRunnerError::MissingFlag("--peer"));
    }
    let strict = !uses_peers_file && peers.len() == 1;

    // One-hop discovery: ask each configured seed for its advertised peers and
    // append any new ones (deduped, order-preserving), capped at discover_cap.
    let mut discovered = 0usize;
    if let Some(cap) = discover_cap {
        let seeds = peers.clone();
        for seed in &seeds {
            if peers.len() >= cap {
                break;
            }
            let Ok(advertised) = peer_fetch_peers(seed) else {
                continue;
            };
            for candidate in advertised {
                if peers.len() >= cap {
                    break;
                }
                if candidate.starts_with("http://") && !peers.contains(&candidate) {
                    peers.push(candidate);
                    discovered += 1;
                }
            }
        }
        // Discovery makes the run tolerant even for a single seed: peers may now
        // include unreachable advertised entries that must not be fatal.
    }
    let strict = strict && discover_cap.is_none();

    let mut node = open_peer_node(chain_file, pending_file, genesis)?;
    // The follower's own network is its chain id; peers on a different network
    // (e.g. devnet vs testnet) are rejected by the handshake.
    let own_network = node.ledger().config().chain_id.clone();
    let mut total_applied = 0usize;
    let mut reachable = 0usize;
    let mut peer_current_height = 0u64;
    let mut peer_reports: Vec<String> = Vec::new();
    let mut skipped_self = 0usize;
    for peer in &peers {
        // Handshake first so a mismatched or self peer is detected before any
        // block pull. A skip is never fatal; only a strict single-peer failure is.
        let identity = match handshake_peer(peer, &own_network) {
            Ok(identity) => identity,
            Err(error) => {
                if strict {
                    return Err(error);
                }
                peer_reports.push(format!(
                    "{{ \"peer\": {}, \"status\": \"skipped\", \"reason\": {} }}",
                    json_string(peer),
                    json_string(&error.to_string())
                ));
                continue;
            }
        };
        if let (Some(own), Some(their)) = (own_node_id.as_deref(), identity.node_id.as_deref()) {
            if own == their {
                skipped_self += 1;
                peer_reports.push(format!(
                    "{{ \"peer\": {}, \"status\": \"skipped\", \"reason\": {} }}",
                    json_string(peer),
                    json_string("peer reports this node's id (self)")
                ));
                continue;
            }
        }
        let node_id_field = identity
            .node_id
            .as_deref()
            .map(json_string)
            .unwrap_or_else(|| "null".to_string());
        match pull_from_peer(&mut node, peer, limit, max_rounds, identity.current_height) {
            Ok(outcome) => {
                total_applied += outcome.applied;
                reachable += 1;
                peer_current_height = peer_current_height.max(outcome.peer_current_height);
                peer_reports.push(format!(
                    "{{ \"peer\": {}, \"status\": \"ok\", \"node_id\": {}, \"applied\": {}, \"rounds\": {}, \"peer_current_height\": {} }}",
                    json_string(peer),
                    node_id_field,
                    outcome.applied,
                    outcome.rounds,
                    outcome.peer_current_height
                ));
            }
            Err(error) => {
                if strict {
                    return Err(error);
                }
                peer_reports.push(format!(
                    "{{ \"peer\": {}, \"status\": \"skipped\", \"reason\": {} }}",
                    json_string(peer),
                    json_string(&error.to_string())
                ));
            }
        }
    }
    if reachable == 0 {
        return Err(NodeRunnerError::PeerSyncError(
            "no configured peer was reachable and compatible".to_string(),
        ));
    }
    let final_height = node.ledger().current_height();
    let own_node_id_field = own_node_id
        .as_deref()
        .map(json_string)
        .unwrap_or_else(|| "null".to_string());
    let peers_json = peer_reports.join(",\n    ");
    let json = format!(
        "{{\n  \"command\": \"peer-sync\",\n  \"network\": {},\n  \"node_id\": {own_node_id_field},\n  \"applied\": {total_applied},\n  \"peers_total\": {},\n  \"peers_discovered\": {discovered},\n  \"peers_reachable\": {reachable},\n  \"peers_skipped_self\": {skipped_self},\n  \"current_height\": {final_height},\n  \"peer_current_height\": {peer_current_height},\n  \"peers\": [\n    {peers_json}\n  ]\n}}",
        json_string(&own_network),
        peers.len()
    );
    Ok(NodeRunnerOutput::Json(json))
}

fn run_peer_identity_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--node-seed",
        "--network",
        "--format",
    ])?;
    let _ = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.optional("--pending-file").unwrap_or("");
    let genesis = parse_runner_genesis(&flags)?;
    let node = open_peer_node(chain_file, pending_file, genesis)?;
    // The advertised network is the node's actual chain id, so devnet and
    // testnet nodes identify distinctly and never cross-sync.
    let network = node.ledger().config().chain_id.clone();
    let current_height = node.ledger().current_height();
    let node_id = flags
        .optional("--node-seed")
        .map(|seed| json_string(&derive_node_id(seed)))
        .unwrap_or_else(|| "null".to_string());
    let json = format!(
        "{{\n  \"command\": \"peer-identity\",\n  \"network\": {},\n  \"protocol\": \"{PEER_PROTOCOL}\",\n  \"current_height\": {current_height},\n  \"node_id\": {node_id}\n}}",
        json_string(&network)
    );
    Ok(NodeRunnerOutput::Json(json))
}

fn run_peer_peers_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    // --chain-file/--alice-balance are accepted for a uniform read-only surface
    // (the HTTP router passes them) but only the advertised peers file is read.
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--peers-file",
        "--network",
        "--format",
    ])?;
    let _ = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let network = runner_genesis(parse_runner_genesis(&flags)?).chain_id;
    let peers = match flags.optional("--peers-file") {
        Some(path) => read_peers_file_lenient(path)?,
        None => Vec::new(),
    };
    let peers_json = if peers.is_empty() {
        "[]".to_string()
    } else {
        let items = peers
            .iter()
            .map(|peer| format!("\n    {}", json_string(peer)))
            .collect::<Vec<_>>()
            .join(",");
        format!("[{items}\n  ]")
    };
    let json = format!(
        "{{\n  \"command\": \"peer-peers\",\n  \"network\": {},\n  \"peers\": {peers_json}\n}}",
        json_string(&network)
    );
    Ok(NodeRunnerOutput::Json(json))
}

const TESTNET_GENESIS_WARNING: &str = "TEST-ONLY public testnet: native units are valueless test units with no monetary value; not for production, sale, or investment.";
const GENESIS_SPEC_HASH_DOMAIN: &[u8] = b"xriq-genesis-spec:v1";

fn push_len_prefixed(out: &mut Vec<u8>, data: &[u8]) {
    out.extend_from_slice(&(data.len() as u64).to_le_bytes());
    out.extend_from_slice(data);
}

// A single stable fingerprint over a genesis config's canonical parameters.
// Independent nodes must compute the same hash to be on the same chain; any
// drift in chain id, policy, authority, or genesis allocation changes it.
fn genesis_spec_hash(genesis: &GenesisConfig) -> Hash32 {
    let mut bytes = Vec::new();
    bytes.extend_from_slice(GENESIS_SPEC_HASH_DOMAIN);
    push_len_prefixed(&mut bytes, genesis.chain_id.as_bytes());
    bytes.extend_from_slice(&genesis.initial_height.to_le_bytes());
    bytes.extend_from_slice(genesis.genesis_block_hash.as_bytes());
    bytes.extend_from_slice(&genesis.min_fee.base_units().to_le_bytes());
    push_len_prefixed(&mut bytes, genesis.fee_sink.as_str().as_bytes());
    push_len_prefixed(&mut bytes, genesis.authority.as_str().as_bytes());
    bytes.extend_from_slice(&(genesis.mempool_max_transactions as u64).to_le_bytes());
    bytes.extend_from_slice(&(genesis.max_transactions_per_block as u64).to_le_bytes());
    bytes.extend_from_slice(&(genesis.accounts.len() as u64).to_le_bytes());
    for account in &genesis.accounts {
        push_len_prefixed(&mut bytes, account.address.as_str().as_bytes());
        bytes.extend_from_slice(&account.balance.base_units().to_le_bytes());
        bytes.extend_from_slice(&account.nonce.to_le_bytes());
    }
    xriq_crypto::digest(&bytes)
}

fn render_testnet_genesis_json(genesis: &GenesisConfig) -> String {
    let accounts_json = if genesis.accounts.is_empty() {
        "[]".to_string()
    } else {
        let items = genesis
            .accounts
            .iter()
            .map(|account| {
                format!(
                    "\n    {{ \"address\": {}, \"balance_base_units\": {}, \"nonce\": {} }}",
                    json_string(account.address.as_str()),
                    json_string(&account.balance.base_units().to_string()),
                    account.nonce
                )
            })
            .collect::<Vec<_>>()
            .join(",");
        format!("[{items}\n  ]")
    };
    format!(
        "{{\n  \"command\": \"testnet-genesis\",\n  \"warning\": {},\n  \"chain_id\": {},\n  \"initial_height\": {},\n  \"genesis_block_hash\": {},\n  \"min_fee_base_units\": {},\n  \"fee_sink\": {},\n  \"authority\": {},\n  \"mempool_max_transactions\": {},\n  \"max_transactions_per_block\": {},\n  \"accounts\": {},\n  \"genesis_spec_hash\": {}\n}}",
        json_string(TESTNET_GENESIS_WARNING),
        json_string(&genesis.chain_id),
        genesis.initial_height,
        json_string(&hash_hex(genesis.genesis_block_hash)),
        json_string(&genesis.min_fee.base_units().to_string()),
        json_string(genesis.fee_sink.as_str()),
        json_string(genesis.authority.as_str()),
        genesis.mempool_max_transactions,
        genesis.max_transactions_per_block,
        accounts_json,
        json_string(&hash_hex(genesis_spec_hash(genesis))),
    )
}

// Read-only: print the canonical public testnet genesis spec and its fingerprint.
// TEST-ONLY; the chain has no monetary value.
fn run_testnet_genesis_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--format"])?;
    let _ = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let genesis = GenesisConfig::public_testnet();
    Ok(NodeRunnerOutput::Json(render_testnet_genesis_json(
        &genesis,
    )))
}

// Which chain a runner command operates on. Devnet carries the optional Alice
// funding used by the private devnet genesis; Testnet is the fixed public
// testnet genesis. This is the selector that lets one code path serve either
// chain without hardwiring the devnet genesis.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum RunnerGenesis {
    Devnet(Option<XriqAmount>),
    Testnet,
}

fn runner_genesis(selection: RunnerGenesis) -> GenesisConfig {
    match selection {
        RunnerGenesis::Devnet(alice_balance) => private_devnet_runner_genesis(alice_balance),
        RunnerGenesis::Testnet => GenesisConfig::public_testnet(),
    }
}

// Open a file-backed node on the selected genesis (no pending-transaction
// replay). Used by peer and faucet commands, which read/sync stored blocks.
fn runner_node(
    chain_file: impl AsRef<Path>,
    selection: RunnerGenesis,
) -> Result<XriqNode<FileChainStore>, NodeRunnerError> {
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    XriqNode::from_genesis_replaying_store(&runner_genesis(selection), store)
        .map_err(NodeRunnerError::Node)
}

// Read `--network devnet|testnet` (default devnet, which also reads
// `--alice-balance`) into a genesis selector.
fn parse_runner_genesis(flags: &RunnerFlagParser) -> Result<RunnerGenesis, NodeRunnerError> {
    match flags.optional("--network") {
        None | Some("devnet") => {
            let alice_balance = flags
                .optional("--alice-balance")
                .map(|value| parse_amount("--alice-balance", value))
                .transpose()?;
            Ok(RunnerGenesis::Devnet(alice_balance))
        }
        Some("testnet") => Ok(RunnerGenesis::Testnet),
        Some(other) => Err(NodeRunnerError::InvalidNetwork(other.to_string())),
    }
}

// Open a peer node on the selected genesis. Devnet preserves the exact existing
// path (including pending replay); testnet reads stored blocks only.
fn open_peer_node(
    chain_file: &str,
    pending_file: &str,
    selection: RunnerGenesis,
) -> Result<XriqNode<FileChainStore>, NodeRunnerError> {
    match selection {
        RunnerGenesis::Devnet(alice_balance) => {
            private_devnet_node_with_pending_file(chain_file, pending_file, alice_balance)
        }
        RunnerGenesis::Testnet => runner_node(chain_file, RunnerGenesis::Testnet),
    }
}

fn public_testnet_node(
    chain_file: impl AsRef<Path>,
) -> Result<XriqNode<FileChainStore>, NodeRunnerError> {
    runner_node(chain_file, RunnerGenesis::Testnet)
}

// Dispense valueless test units from the genesis faucet account on the public
// testnet chain. Rate-limited by a balance cap (chain-derived, so it is
// deterministic and needs no side state); the transfer is a normal signed
// transaction confirmed in a freshly produced block. TEST-ONLY, no value.
//
// This operates on its own testnet-genesis chain file and is deliberately not
// wired into the devnet-genesis HTTP server; a genesis-parametrized testnet node
// (a later increment) will expose it over HTTP with additional IP rate limiting.
fn run_faucet_dispense_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--to",
        "--amount",
        "--max-balance",
        "--timestamp-ms",
        "--consensus-round",
        "--format",
    ])?;
    let _ = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let to = parse_address("--to", flags.required("--to")?)?;
    let amount = flags
        .optional("--amount")
        .map(|value| parse_amount("--amount", value))
        .transpose()?
        .unwrap_or_else(|| XriqAmount::from_base_units(PUBLIC_TESTNET_FAUCET_DRIP_BASE_UNITS));
    let max_balance = flags
        .optional("--max-balance")
        .map(|value| parse_amount("--max-balance", value))
        .transpose()?
        .unwrap_or_else(|| {
            XriqAmount::from_base_units(PUBLIC_TESTNET_FAUCET_MAX_BALANCE_BASE_UNITS)
        });
    let consensus_round = flags
        .optional("--consensus-round")
        .map(|value| parse_u64("--consensus-round", value))
        .transpose()?
        .unwrap_or(0);

    let mut node = public_testnet_node(chain_file)?;
    let faucet_address =
        Address::parse(PUBLIC_TESTNET_FAUCET_ADDRESS).expect("public testnet faucet address");

    // Abuse control: refuse a recipient already at or above the balance cap.
    let recipient_balance = node
        .ledger()
        .account(&to)
        .map(|account| account.balance)
        .unwrap_or(XriqAmount::ZERO);
    if recipient_balance.base_units() >= max_balance.base_units() {
        return Err(NodeRunnerError::FaucetRefused(format!(
            "recipient {} already holds {} base units (cap {})",
            to.as_str(),
            recipient_balance.base_units(),
            max_balance.base_units()
        )));
    }

    let faucet_account = node
        .ledger()
        .account(&faucet_address)
        .ok_or_else(|| NodeRunnerError::FaucetRefused("faucet account is unfunded".to_string()))?;
    let fee = node.ledger().config().min_fee;
    let sufficient = amount
        .base_units()
        .checked_add(fee.base_units())
        .map(|required| faucet_account.balance.base_units() >= required)
        .unwrap_or(false);
    if !sufficient {
        return Err(NodeRunnerError::FaucetRefused(format!(
            "faucet balance {} is insufficient for amount {} plus fee {}",
            faucet_account.balance.base_units(),
            amount.base_units(),
            fee.base_units()
        )));
    }

    let transfer = PrivateDevnetTransferInput {
        from: faucet_address.clone(),
        to: to.clone(),
        amount,
        fee,
        nonce: faucet_account.nonce,
        expires_at_height: None,
        timestamp_ms: 0,
        consensus_round,
    };
    let transaction = private_devnet_runner_transaction(&node, &transfer);
    let transaction_hash = transaction_hash(&transaction);
    node.submit_transaction_with_canonical_hash(transaction)
        .map_err(NodeRunnerError::Node)?;

    // A monotonic default timestamp (height-derived) keeps successive faucet
    // blocks ordered without depending on a wall clock.
    let height = node.ledger().current_height().saturating_add(1);
    let timestamp_ms = flags
        .optional("--timestamp-ms")
        .map(|value| parse_u64("--timestamp-ms", value))
        .transpose()?
        .unwrap_or_else(|| height.saturating_mul(1_000));
    let produced = node
        .produce_next_block_with_private_devnet_signature(timestamp_ms, consensus_round)
        .map_err(NodeRunnerError::Node)?;

    let recipient_new = node
        .ledger()
        .account(&to)
        .map(|account| account.balance.base_units())
        .unwrap_or(0);
    let faucet_new = node
        .ledger()
        .account(&faucet_address)
        .map(|account| account.balance.base_units())
        .unwrap_or(0);
    let json = format!(
        "{{\n  \"command\": \"faucet-dispense\",\n  \"warning\": {},\n  \"chain_id\": {},\n  \"to\": {},\n  \"amount_base_units\": {},\n  \"fee_base_units\": {},\n  \"transaction_hash\": {},\n  \"block_height\": {},\n  \"block_hash\": {},\n  \"recipient_balance_base_units\": {},\n  \"faucet_balance_base_units\": {}\n}}",
        json_string(TESTNET_GENESIS_WARNING),
        json_string(&node.ledger().config().chain_id),
        json_string(to.as_str()),
        json_string(&amount.base_units().to_string()),
        json_string(&fee.base_units().to_string()),
        json_string(&hash_hex(transaction_hash)),
        produced.block.header.height,
        json_string(&hash_hex(produced.block_hash)),
        json_string(&recipient_new.to_string()),
        json_string(&faucet_new.to_string()),
    );
    Ok(NodeRunnerOutput::Json(json))
}

fn run_chain_check_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.optional("--pending-file");
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let status = private_devnet_file_chain_check(chain_file, pending_file, alice_balance)?;
    Ok(match output_format {
        RunnerOutputFormat::Text => NodeRunnerOutput::ChainCheck(status),
        RunnerOutputFormat::Json => {
            NodeRunnerOutput::Json(render_chain_check_json("chain-check", &status))
        }
    })
}

fn run_explorer_overview_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--limit", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(10);
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_file_explorer_overview(chain_file, alice_balance, limit)
                .map(NodeRunnerOutput::ExplorerOverview)
                .map_err(NodeRunnerError::Node)?
        }
        RunnerOutputFormat::Json => {
            let (overview, latest_blocks) =
                private_devnet_file_explorer_overview_data(chain_file, alice_balance, limit)
                    .map_err(NodeRunnerError::Node)?;
            NodeRunnerOutput::Json(render_explorer_overview_json(
                "explorer-overview",
                &overview,
                &latest_blocks,
            ))
        }
    })
}

fn run_block_list_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--limit", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(25);
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_file_block_list(chain_file, alice_balance, limit)
                .map(NodeRunnerOutput::BlockList)?
        }
        RunnerOutputFormat::Json => {
            let blocks = private_devnet_file_block_list_data(chain_file, alice_balance, limit)?;
            NodeRunnerOutput::Json(render_block_list_json("block-list", &blocks))
        }
    })
}

fn run_block_detail_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--alice-balance",
        "--height",
        "--block-hash",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let height_raw = flags.optional("--height");
    let block_hash = flags
        .optional("--block-hash")
        .map(|value| parse_hash("--block-hash", value))
        .transpose()?;
    let latest = height_raw == Some("latest");
    let height = if latest {
        None
    } else {
        height_raw
            .map(|value| parse_u64("--height", value))
            .transpose()?
    };
    match (height_raw, block_hash) {
        (Some(_), Some(_)) => {
            return Err(NodeRunnerError::InvalidFormat(
                "provide exactly one of --height or --block-hash".to_string(),
            ))
        }
        (None, None) => return Err(NodeRunnerError::MissingFlag("--height")),
        _ => {}
    }
    Ok(match output_format {
        RunnerOutputFormat::Text => match (height, block_hash, latest) {
            (Some(height), None, false) => {
                private_devnet_file_block_detail(chain_file, alice_balance, height)
                    .map(NodeRunnerOutput::BlockDetail)?
            }
            (None, Some(block_hash), false) => {
                private_devnet_file_block_detail_by_hash(chain_file, alice_balance, block_hash)
                    .map(NodeRunnerOutput::BlockDetail)?
            }
            (None, None, true) => {
                private_devnet_file_latest_block_detail(chain_file, alice_balance)
                    .map(NodeRunnerOutput::BlockDetail)?
            }
            _ => unreachable!("block detail selector already validated"),
        },
        RunnerOutputFormat::Json => match (height, block_hash, latest) {
            (Some(height), None, false) => {
                let detail =
                    private_devnet_file_block_detail_data(chain_file, alice_balance, height)?;
                NodeRunnerOutput::Json(render_block_detail_json("block-detail", &detail))
            }
            (None, Some(block_hash), false) => {
                let detail = private_devnet_file_block_detail_by_hash_data(
                    chain_file,
                    alice_balance,
                    block_hash,
                )?;
                NodeRunnerOutput::Json(render_block_detail_json("block-detail", &detail))
            }
            (None, None, true) => {
                let detail =
                    private_devnet_file_latest_block_detail_data(chain_file, alice_balance)?;
                NodeRunnerOutput::Json(render_block_detail_json("block-detail", &detail))
            }
            _ => unreachable!("block detail selector already validated"),
        },
    })
}

fn run_account_list_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--limit", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(25);
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_file_account_list(chain_file, alice_balance, limit)
                .map(NodeRunnerOutput::AccountList)?
        }
        RunnerOutputFormat::Json => {
            let accounts = private_devnet_file_account_list_data(chain_file, alice_balance, limit)?;
            NodeRunnerOutput::Json(render_account_list_json("account-list", &accounts))
        }
    })
}

fn run_account_detail_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--address", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let address = parse_address("--address", flags.required("--address")?)?;
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_file_account_detail(chain_file, alice_balance, address)
                .map(NodeRunnerOutput::AccountDetail)?
        }
        RunnerOutputFormat::Json => {
            let detail =
                private_devnet_file_account_detail_data(chain_file, alice_balance, address)?;
            NodeRunnerOutput::Json(render_account_detail_json("account-detail", &detail))
        }
    })
}

fn run_account_transactions_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--alice-balance",
        "--address",
        "--limit",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let address = parse_address("--address", flags.required("--address")?)?;
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(25);
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_file_account_transactions(chain_file, alice_balance, address, limit)
                .map(NodeRunnerOutput::AccountTransactions)?
        }
        RunnerOutputFormat::Json => {
            let transactions = private_devnet_file_account_transactions_data(
                chain_file,
                alice_balance,
                address.clone(),
                limit,
            )?;
            NodeRunnerOutput::Json(render_account_transactions_json(
                "account-transactions",
                &address,
                &transactions,
            ))
        }
    })
}

fn run_transaction_list_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--limit", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(25);
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_file_latest_transactions(chain_file, alice_balance, limit)
                .map(NodeRunnerOutput::TransactionList)?
        }
        RunnerOutputFormat::Json => {
            let transactions =
                private_devnet_file_latest_transactions_data(chain_file, alice_balance, limit)?;
            NodeRunnerOutput::Json(render_transaction_list_json(
                "transaction-list",
                &transactions,
            ))
        }
    })
}

fn run_mempool_detail_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--draft-file",
        "--pending-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let draft_file = flags.optional("--draft-file");
    let pending_file = flags.optional("--pending-file");
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let detail = private_devnet_file_mempool_detail_with_sources_data(
        chain_file,
        draft_file,
        pending_file,
        alice_balance,
    )?;
    Ok(match output_format {
        RunnerOutputFormat::Text => NodeRunnerOutput::MempoolDetail(render_mempool(&detail)),
        RunnerOutputFormat::Json => {
            NodeRunnerOutput::Json(render_mempool_detail_json("mempool-detail", &detail))
        }
    })
}

fn run_transaction_detail_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--draft-file",
        "--alice-balance",
        "--tx-hash",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let draft_file = flags.optional("--draft-file");
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let tx_hash = parse_hash("--tx-hash", flags.required("--tx-hash")?)?;
    let detail = private_devnet_file_transaction_detail_data(
        chain_file,
        draft_file,
        alice_balance,
        tx_hash,
    )?;
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            NodeRunnerOutput::TransactionDetail(render_transaction_detail(&detail))
        }
        RunnerOutputFormat::Json => NodeRunnerOutput::Json(render_transaction_detail_json(&detail)),
    })
}

fn run_snapshot_list_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--snapshot-root", "--limit", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let snapshot_root = flags.required("--snapshot-root")?;
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(25);
    Ok(match output_format {
        RunnerOutputFormat::Text => private_devnet_snapshot_list(snapshot_root, limit)
            .map(NodeRunnerOutput::SnapshotList)?,
        RunnerOutputFormat::Json => {
            let snapshots = private_devnet_snapshot_list_data(snapshot_root, limit)?;
            NodeRunnerOutput::Json(render_snapshot_list_json(
                "snapshot-list",
                Path::new(snapshot_root),
                &snapshots,
            ))
        }
    })
}

fn run_snapshot_latest_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--snapshot-root", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let snapshot_root = flags.required("--snapshot-root")?;
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_snapshot_latest(snapshot_root).map(NodeRunnerOutput::SnapshotDetail)?
        }
        RunnerOutputFormat::Json => {
            let snapshot = private_devnet_snapshot_latest_data(snapshot_root)?;
            NodeRunnerOutput::Json(render_snapshot_detail_json("snapshot-latest", &snapshot))
        }
    })
}

fn run_snapshot_latest_check_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--snapshot-root", "--alice-balance", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let snapshot_root = flags.required("--snapshot-root")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_snapshot_latest_check(snapshot_root, alice_balance)
                .map(NodeRunnerOutput::SnapshotCheck)?
        }
        RunnerOutputFormat::Json => {
            let status = private_devnet_snapshot_latest_check_data(snapshot_root, alice_balance)?;
            NodeRunnerOutput::Json(render_snapshot_check_json("snapshot-latest-check", &status))
        }
    })
}

fn run_snapshot_detail_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--snapshot-dir", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let snapshot_dir = flags.required("--snapshot-dir")?;
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_snapshot_detail(snapshot_dir).map(NodeRunnerOutput::SnapshotDetail)?
        }
        RunnerOutputFormat::Json => {
            let snapshot = private_devnet_snapshot_detail_data(snapshot_dir)?;
            NodeRunnerOutput::Json(render_snapshot_detail_json("snapshot-detail", &snapshot))
        }
    })
}

fn run_snapshot_check_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--snapshot-dir", "--alice-balance", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let snapshot_dir = flags.required("--snapshot-dir")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    Ok(match output_format {
        RunnerOutputFormat::Text => private_devnet_snapshot_check(snapshot_dir, alice_balance)
            .map(NodeRunnerOutput::SnapshotCheck)?,
        RunnerOutputFormat::Json => {
            let status = private_devnet_snapshot_check_data(snapshot_dir, alice_balance)?;
            NodeRunnerOutput::Json(render_snapshot_check_json("snapshot-check", &status))
        }
    })
}

fn run_snapshot_export_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--snapshot-dir",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.optional("--pending-file");
    let snapshot_dir = flags.required("--snapshot-dir")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    private_devnet_export_snapshot(chain_file, pending_file, alice_balance, snapshot_dir).map(
        |status| match output_format {
            RunnerOutputFormat::Text => NodeRunnerOutput::Snapshot(status),
            RunnerOutputFormat::Json => {
                NodeRunnerOutput::Json(render_snapshot_status_json("snapshot-export", &status))
            }
        },
    )
}

fn run_snapshot_import_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--snapshot-dir",
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let snapshot_dir = flags.required("--snapshot-dir")?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.optional("--pending-file");
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    private_devnet_import_snapshot(snapshot_dir, chain_file, pending_file, alice_balance).map(
        |status| match output_format {
            RunnerOutputFormat::Text => NodeRunnerOutput::Snapshot(status),
            RunnerOutputFormat::Json => {
                NodeRunnerOutput::Json(render_snapshot_status_json("snapshot-import", &status))
            }
        },
    )
}

fn run_preflight_transfer_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--from",
        "--to",
        "--amount",
        "--fee",
        "--expires-at-height",
        "--timestamp-ms",
        "--consensus-round",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.required("--pending-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let from = parse_address("--from", flags.required("--from")?)?;
    let to = parse_address("--to", flags.required("--to")?)?;
    let amount = parse_amount("--amount", flags.required("--amount")?)?;
    let fee = parse_amount("--fee", flags.required("--fee")?)?;
    let expires_at_height = flags
        .optional("--expires-at-height")
        .map(|value| parse_u64("--expires-at-height", value))
        .transpose()?;
    let timestamp_ms = flags
        .optional("--timestamp-ms")
        .map(|value| parse_u64("--timestamp-ms", value))
        .transpose()?
        .unwrap_or(1_000);
    let consensus_round = flags
        .optional("--consensus-round")
        .map(|value| parse_u64("--consensus-round", value))
        .transpose()?
        .unwrap_or(0);
    private_devnet_file_preflight_transfer(
        chain_file,
        pending_file,
        alice_balance,
        PrivateDevnetPreflightTransferInput {
            from,
            to,
            amount,
            fee,
            expires_at_height,
            timestamp_ms,
            consensus_round,
        },
    )
    .map(|status| match output_format {
        RunnerOutputFormat::Text => NodeRunnerOutput::PreflightTransfer(status),
        RunnerOutputFormat::Json => {
            NodeRunnerOutput::Json(render_preflight_transfer_status_json(&status))
        }
    })
}

fn run_produce_pending_block_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--timestamp-ms",
        "--consensus-round",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.required("--pending-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let timestamp_ms = flags
        .optional("--timestamp-ms")
        .map(|value| parse_u64("--timestamp-ms", value))
        .transpose()?
        .unwrap_or(1_000);
    let consensus_round = flags
        .optional("--consensus-round")
        .map(|value| parse_u64("--consensus-round", value))
        .transpose()?
        .unwrap_or(0);
    private_devnet_file_produce_pending_block(
        chain_file,
        pending_file,
        alice_balance,
        timestamp_ms,
        consensus_round,
    )
    .map(|status| match output_format {
        RunnerOutputFormat::Text => NodeRunnerOutput::ProducedPendingBlock(status),
        RunnerOutputFormat::Json => NodeRunnerOutput::Json(
            render_produced_pending_block_status_json("produce-pending-block", &status),
        ),
    })
}

fn run_produce_draft_block_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--draft-file",
        "--alice-balance",
        "--timestamp-ms",
        "--consensus-round",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let draft_file = flags.required("--draft-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let timestamp_ms = flags
        .optional("--timestamp-ms")
        .map(|value| parse_u64("--timestamp-ms", value))
        .transpose()?
        .unwrap_or(1_000);
    let consensus_round = flags
        .optional("--consensus-round")
        .map(|value| parse_u64("--consensus-round", value))
        .transpose()?
        .unwrap_or(0);
    private_devnet_file_produce_draft_block(
        chain_file,
        draft_file,
        alice_balance,
        timestamp_ms,
        consensus_round,
    )
    .map(|status| match output_format {
        RunnerOutputFormat::Text => NodeRunnerOutput::ProducedTransferBlock(status),
        RunnerOutputFormat::Json => NodeRunnerOutput::Json(
            render_produced_transfer_block_status_json("produce-draft-block", &status),
        ),
    })
}

fn run_produce_transfer_block_command(
    args: &[String],
) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--alice-balance",
        "--from",
        "--to",
        "--amount",
        "--fee",
        "--nonce",
        "--expires-at-height",
        "--timestamp-ms",
        "--consensus-round",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let transfer = PrivateDevnetTransferInput {
        from: parse_address("--from", flags.required("--from")?)?,
        to: parse_address("--to", flags.required("--to")?)?,
        amount: parse_amount("--amount", flags.required("--amount")?)?,
        fee: parse_amount("--fee", flags.required("--fee")?)?,
        nonce: parse_u64("--nonce", flags.required("--nonce")?)?,
        expires_at_height: flags
            .optional("--expires-at-height")
            .map(|value| parse_u64("--expires-at-height", value))
            .transpose()?,
        timestamp_ms: flags
            .optional("--timestamp-ms")
            .map(|value| parse_u64("--timestamp-ms", value))
            .transpose()?
            .unwrap_or(1_000),
        consensus_round: flags
            .optional("--consensus-round")
            .map(|value| parse_u64("--consensus-round", value))
            .transpose()?
            .unwrap_or(0),
    };
    let status = private_devnet_file_produce_transfer_block(chain_file, alice_balance, transfer)
        .map_err(NodeRunnerError::Node)?;
    Ok(match output_format {
        RunnerOutputFormat::Text => NodeRunnerOutput::ProducedTransferBlock(status),
        RunnerOutputFormat::Json => NodeRunnerOutput::Json(
            render_produced_transfer_block_status_json("produce-transfer-block", &status),
        ),
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetTransferInput {
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
    pub timestamp_ms: u64,
    pub consensus_round: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetPreflightTransferInput {
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub expires_at_height: Option<u64>,
    pub timestamp_ms: u64,
    pub consensus_round: u64,
}

fn private_devnet_runner_transaction<S: ChainStore>(
    node: &XriqNode<S>,
    transfer: &PrivateDevnetTransferInput,
) -> Transaction {
    let mut transaction = Transaction {
        version: Transaction::SUPPORTED_VERSION,
        chain_id: node.ledger().config().chain_id.clone(),
        from: transfer.from.clone(),
        to: transfer.to.clone(),
        amount: transfer.amount,
        fee: transfer.fee,
        nonce: transfer.nonce,
        memo_hash: None,
        expires_at_height: transfer.expires_at_height,
        signature: SignatureBytes::new(Vec::new()),
    };
    transaction.signature = test_only_signature_for_hash(transaction_signing_hash(&transaction));
    transaction
}

fn render_pending_preflight_transfer_body(transaction: &Transaction) -> String {
    [
        "warning=private-devnet-test-identity-only".to_string(),
        format!("version={}", transaction.version),
        format!("chain_id={}", transaction.chain_id),
        format!("from={}", transaction.from),
        format!("to={}", transaction.to),
        format!("amount={}", transaction.amount.base_units()),
        format!("fee={}", transaction.fee.base_units()),
        format!("nonce={}", transaction.nonce),
        format!(
            "expires_at_height={}",
            transaction
                .expires_at_height
                .map(|height| height.to_string())
                .unwrap_or_default()
        ),
        format!("signature_bytes={}", transaction.signature.as_slice().len()),
    ]
    .join("\n")
}

fn read_private_devnet_transfer_draft(
    draft_file: impl AsRef<Path>,
    expected_chain_id: &str,
) -> Result<PrivateDevnetTransferInput, NodeRunnerError> {
    let draft_path = draft_file.as_ref();
    let draft_text =
        fs::read_to_string(draft_path).map_err(|error| NodeRunnerError::DraftFileRead {
            path: draft_path.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    parse_private_devnet_transfer_draft(&draft_text, expected_chain_id)
}

fn parse_private_devnet_transfer_body(
    body: &str,
    expected_chain_id: &str,
) -> Result<PrivateDevnetTransferInput, NodeRunnerError> {
    let trimmed = body.trim().trim_start_matches('\u{feff}').trim();
    if trimmed.starts_with('{') {
        parse_private_devnet_transfer_json(trimmed, expected_chain_id)
    } else {
        parse_private_devnet_transfer_draft(trimmed, expected_chain_id)
    }
}

const PENDING_QUARANTINE_MARKER: &str = "xriq-pending-quarantine-v1";

struct QuarantinedPendingLine {
    line_number: usize,
    raw: String,
}

struct PendingReplayLoad {
    records: Vec<(Hash32, Transaction)>,
    quarantined: Vec<QuarantinedPendingLine>,
}

fn pending_quarantine_path(pending_file: &Path) -> std::path::PathBuf {
    let mut name = pending_file.as_os_str().to_os_string();
    name.push(".quarantine");
    std::path::PathBuf::from(name)
}

fn read_pending_transaction_records(
    pending_file: &Path,
) -> Result<PendingReplayLoad, NodeRunnerError> {
    if !pending_file.exists() {
        return Ok(PendingReplayLoad {
            records: Vec::new(),
            quarantined: Vec::new(),
        });
    }
    let text =
        fs::read_to_string(pending_file).map_err(|error| NodeRunnerError::PendingFileRead {
            path: pending_file.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    let mut records = Vec::new();
    let mut quarantined = Vec::new();
    for (index, raw_line) in text.lines().enumerate() {
        let line = raw_line.trim();
        if line.is_empty() {
            continue;
        }
        match parse_pending_transaction_record(line) {
            Ok(record) => records.push(record),
            // Fail-open recovery: an unparseable pending line must not brick
            // node startup. Capture it for quarantine instead of aborting so a
            // single corrupt record cannot deny startup for valid ones.
            Err(_) => quarantined.push(QuarantinedPendingLine {
                line_number: index + 1,
                raw: raw_line.to_string(),
            }),
        }
    }
    Ok(PendingReplayLoad {
        records,
        quarantined,
    })
}

fn quarantine_corrupt_pending_lines(
    pending_file: &Path,
    load: &PendingReplayLoad,
) -> Result<(), NodeRunnerError> {
    if load.quarantined.is_empty() {
        return Ok(());
    }
    let quarantine_file = pending_quarantine_path(pending_file);
    if let Some(parent) = quarantine_file
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent).map_err(|error| NodeRunnerError::PendingFileRead {
            path: quarantine_file.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    }
    let mut quarantine_text = String::new();
    for entry in &load.quarantined {
        writeln!(
            &mut quarantine_text,
            "{PENDING_QUARANTINE_MARKER}\t{}\t{}",
            entry.line_number, entry.raw
        )
        .expect("write to String");
    }
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&quarantine_file)
        .map_err(|error| NodeRunnerError::PendingFileRead {
            path: quarantine_file.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    write!(file, "{quarantine_text}").map_err(|error| NodeRunnerError::PendingFileRead {
        path: quarantine_file.to_string_lossy().to_string(),
        error: error.to_string(),
    })?;
    // Self-healing rewrite: drop the corrupt lines from the live pending file
    // exactly once. This is not silent loss; the corrupt content is preserved in
    // the quarantine sidecar above for later inspection/recovery.
    write_pending_transaction_records(pending_file, &load.records)
}

fn append_pending_transaction_record(
    pending_file: &Path,
    tx_hash: Hash32,
    transaction: &Transaction,
) -> Result<(), NodeRunnerError> {
    if let Some(parent) = pending_file
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent).map_err(|error| NodeRunnerError::PendingFileRead {
            path: pending_file.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    }
    let mut file = fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(pending_file)
        .map_err(|error| NodeRunnerError::PendingFileRead {
            path: pending_file.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    writeln!(
        file,
        "{}",
        render_pending_transaction_record(tx_hash, transaction)
    )
    .map_err(|error| NodeRunnerError::PendingFileRead {
        path: pending_file.to_string_lossy().to_string(),
        error: error.to_string(),
    })
}

fn write_pending_transaction_records(
    pending_file: &Path,
    records: &[(Hash32, Transaction)],
) -> Result<(), NodeRunnerError> {
    if let Some(parent) = pending_file
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent).map_err(|error| NodeRunnerError::PendingFileRead {
            path: pending_file.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    }

    let mut text = String::new();
    for (tx_hash, transaction) in records {
        writeln!(
            &mut text,
            "{}",
            render_pending_transaction_record(*tx_hash, transaction)
        )
        .expect("write to String");
    }

    fs::write(pending_file, text).map_err(|error| NodeRunnerError::PendingFileRead {
        path: pending_file.to_string_lossy().to_string(),
        error: error.to_string(),
    })
}

fn prepare_new_snapshot_dir(snapshot_dir: &Path) -> Result<(), NodeRunnerError> {
    if snapshot_dir.exists() {
        let mut entries =
            fs::read_dir(snapshot_dir).map_err(|error| NodeRunnerError::SnapshotFileRead {
                path: snapshot_dir.to_string_lossy().to_string(),
                error: error.to_string(),
            })?;
        if entries
            .next()
            .transpose()
            .map_err(|error| NodeRunnerError::SnapshotFileRead {
                path: snapshot_dir.to_string_lossy().to_string(),
                error: error.to_string(),
            })?
            .is_some()
        {
            return Err(NodeRunnerError::SnapshotTargetExists(
                snapshot_dir.to_string_lossy().to_string(),
            ));
        }
        return Ok(());
    }
    fs::create_dir_all(snapshot_dir).map_err(|error| NodeRunnerError::SnapshotFileWrite {
        path: snapshot_dir.to_string_lossy().to_string(),
        error: error.to_string(),
    })
}

fn copy_snapshot_file(source: &Path, target: &Path) -> Result<(), NodeRunnerError> {
    if let Some(parent) = target
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent).map_err(|error| NodeRunnerError::SnapshotFileWrite {
            path: target.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    }
    fs::copy(source, target).map(|_| ()).map_err(|error| {
        if source.exists() {
            NodeRunnerError::SnapshotFileWrite {
                path: target.to_string_lossy().to_string(),
                error: error.to_string(),
            }
        } else {
            NodeRunnerError::SnapshotFileRead {
                path: source.to_string_lossy().to_string(),
                error: error.to_string(),
            }
        }
    })
}

fn copy_snapshot_file_to_new_path(source: &Path, target: &Path) -> Result<(), NodeRunnerError> {
    reject_existing_snapshot_target(target)?;
    copy_snapshot_file(source, target)
}

fn write_new_snapshot_file(target: &Path, text: &str) -> Result<(), NodeRunnerError> {
    reject_existing_snapshot_target(target)?;
    write_snapshot_file(target, text)
}

fn reject_existing_snapshot_target(target: &Path) -> Result<(), NodeRunnerError> {
    if target.exists() {
        return Err(NodeRunnerError::SnapshotTargetExists(
            target.to_string_lossy().to_string(),
        ));
    }
    Ok(())
}

fn write_snapshot_file(target: &Path, text: &str) -> Result<(), NodeRunnerError> {
    if let Some(parent) = target
        .parent()
        .filter(|parent| !parent.as_os_str().is_empty())
    {
        fs::create_dir_all(parent).map_err(|error| NodeRunnerError::SnapshotFileWrite {
            path: target.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    }
    fs::write(target, text).map_err(|error| NodeRunnerError::SnapshotFileWrite {
        path: target.to_string_lossy().to_string(),
        error: error.to_string(),
    })
}

fn validate_snapshot_manifest(snapshot_dir: &Path) -> Result<(), NodeRunnerError> {
    let manifest_path = snapshot_dir.join(SNAPSHOT_MANIFEST_FILE);
    let manifest =
        fs::read_to_string(&manifest_path).map_err(|error| NodeRunnerError::SnapshotFileRead {
            path: manifest_path.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    if !manifest.contains(&format!(
        "\"snapshot_format_version\": {}",
        json_string(PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION)
    )) {
        return Err(NodeRunnerError::InvalidSnapshotManifest(
            "missing or unsupported snapshot_format_version".to_string(),
        ));
    }
    Ok(())
}

fn read_private_devnet_snapshot_summary(
    snapshot_dir: &Path,
) -> Result<PrivateDevnetSnapshotSummary, NodeRunnerError> {
    validate_snapshot_manifest(snapshot_dir)?;
    let manifest_path = snapshot_dir.join(SNAPSHOT_MANIFEST_FILE);
    let manifest =
        fs::read_to_string(&manifest_path).map_err(|error| NodeRunnerError::SnapshotFileRead {
            path: manifest_path.to_string_lossy().to_string(),
            error: error.to_string(),
        })?;
    let chain_file_name = snapshot_manifest_required_string(&manifest, "chain_file")?;
    let pending_file_name = snapshot_manifest_optional_string(&manifest, "pending_file")?;
    let chain_file = snapshot_dir.join(&chain_file_name);
    if !chain_file.exists() {
        return Err(NodeRunnerError::SnapshotFileRead {
            path: chain_file.to_string_lossy().to_string(),
            error: "snapshot chain file is missing".to_string(),
        });
    }
    let pending_file = if let Some(pending_file_name) = pending_file_name {
        let pending_file = snapshot_dir.join(pending_file_name);
        if !pending_file.exists() {
            return Err(NodeRunnerError::SnapshotFileRead {
                path: pending_file.to_string_lossy().to_string(),
                error: "snapshot pending file is missing".to_string(),
            });
        }
        Some(pending_file.to_string_lossy().to_string())
    } else {
        None
    };
    let snapshot_name = snapshot_dir
        .file_name()
        .map(|name| name.to_string_lossy().to_string())
        .unwrap_or_else(|| snapshot_dir.to_string_lossy().to_string());
    Ok(PrivateDevnetSnapshotSummary {
        snapshot_name,
        snapshot_dir: snapshot_dir.to_string_lossy().to_string(),
        chain_file: chain_file.to_string_lossy().to_string(),
        pending_file,
        status: NodeStatus {
            warning: PRIVATE_DEVNET_RUNNER_WARNING,
            chain_id: snapshot_manifest_required_string(&manifest, "chain_id")?,
            current_height: snapshot_manifest_required_u64(&manifest, "current_height")?,
            latest_block_hash: snapshot_manifest_required_hash(&manifest, "latest_block_hash")?,
            state_root: snapshot_manifest_required_hash(&manifest, "state_root")?,
            pending_transactions: snapshot_manifest_required_usize(
                &manifest,
                "pending_transactions",
            )?,
            stored_blocks: snapshot_manifest_required_usize(&manifest, "stored_blocks")?,
        },
    })
}

fn snapshot_status_mismatches(manifest: &NodeStatus, replayed: &NodeStatus) -> Vec<String> {
    let mut mismatches = Vec::new();
    if manifest.chain_id != replayed.chain_id {
        mismatches.push("chain_id".to_string());
    }
    if manifest.current_height != replayed.current_height {
        mismatches.push("current_height".to_string());
    }
    if manifest.latest_block_hash != replayed.latest_block_hash {
        mismatches.push("latest_block_hash".to_string());
    }
    if manifest.state_root != replayed.state_root {
        mismatches.push("state_root".to_string());
    }
    if manifest.pending_transactions != replayed.pending_transactions {
        mismatches.push("pending_transactions".to_string());
    }
    if manifest.stored_blocks != replayed.stored_blocks {
        mismatches.push("stored_blocks".to_string());
    }
    mismatches
}

fn snapshot_manifest_required_string(
    manifest: &str,
    field: &'static str,
) -> Result<String, NodeRunnerError> {
    snapshot_manifest_optional_string(manifest, field)?.ok_or_else(|| {
        NodeRunnerError::InvalidSnapshotManifest(format!("missing string field {field}"))
    })
}

fn snapshot_manifest_optional_string(
    manifest: &str,
    field: &'static str,
) -> Result<Option<String>, NodeRunnerError> {
    let value = snapshot_manifest_value(manifest, field)?;
    if value.starts_with("null") {
        return Ok(None);
    }
    let Some(rest) = value.strip_prefix('"') else {
        return Err(NodeRunnerError::InvalidSnapshotManifest(format!(
            "field {field} must be a string or null"
        )));
    };
    let mut end = None;
    for (index, character) in rest.char_indices() {
        if character == '\\' {
            return Err(NodeRunnerError::InvalidSnapshotManifest(format!(
                "escaped string field {field} is not supported"
            )));
        }
        if character == '"' {
            end = Some(index);
            break;
        }
    }
    let Some(end) = end else {
        return Err(NodeRunnerError::InvalidSnapshotManifest(format!(
            "unterminated string field {field}"
        )));
    };
    Ok(Some(rest[..end].to_string()))
}

fn snapshot_manifest_required_u64(
    manifest: &str,
    field: &'static str,
) -> Result<u64, NodeRunnerError> {
    let digits = snapshot_manifest_number_digits(manifest, field)?;
    digits
        .parse()
        .map_err(|_| NodeRunnerError::InvalidSnapshotManifest(format!("invalid number {field}")))
}

fn snapshot_manifest_required_usize(
    manifest: &str,
    field: &'static str,
) -> Result<usize, NodeRunnerError> {
    let digits = snapshot_manifest_number_digits(manifest, field)?;
    digits
        .parse()
        .map_err(|_| NodeRunnerError::InvalidSnapshotManifest(format!("invalid number {field}")))
}

fn snapshot_manifest_required_hash(
    manifest: &str,
    field: &'static str,
) -> Result<Hash32, NodeRunnerError> {
    let value = snapshot_manifest_required_string(manifest, field)?;
    parse_hash(field, &value).map_err(|_| {
        NodeRunnerError::InvalidSnapshotManifest(format!("field {field} must be a 64-hex hash"))
    })
}

fn snapshot_manifest_number_digits<'a>(
    manifest: &'a str,
    field: &'static str,
) -> Result<&'a str, NodeRunnerError> {
    let value = snapshot_manifest_value(manifest, field)?;
    let end = value
        .char_indices()
        .find_map(|(index, character)| (!character.is_ascii_digit()).then_some(index))
        .unwrap_or(value.len());
    if end == 0 {
        return Err(NodeRunnerError::InvalidSnapshotManifest(format!(
            "field {field} must be a number"
        )));
    }
    Ok(&value[..end])
}

fn snapshot_manifest_value<'a>(
    manifest: &'a str,
    field: &'static str,
) -> Result<&'a str, NodeRunnerError> {
    let key = format!("\"{field}\"");
    let Some(key_start) = manifest.find(&key) else {
        return Err(NodeRunnerError::InvalidSnapshotManifest(format!(
            "missing field {field}"
        )));
    };
    let after_key = &manifest[key_start + key.len()..];
    let after_space = after_key.trim_start();
    let Some(after_colon) = after_space.strip_prefix(':') else {
        return Err(NodeRunnerError::InvalidSnapshotManifest(format!(
            "field {field} is missing a colon"
        )));
    };
    Ok(after_colon.trim_start())
}

fn render_pending_transaction_record(tx_hash: Hash32, transaction: &Transaction) -> String {
    [
        "xriq-pending-transaction-v1".to_string(),
        hash_hex(tx_hash),
        transaction.version.to_string(),
        transaction.chain_id.clone(),
        transaction.from.as_str().to_string(),
        transaction.to.as_str().to_string(),
        transaction.amount.base_units().to_string(),
        transaction.fee.base_units().to_string(),
        transaction.nonce.to_string(),
        transaction
            .expires_at_height
            .map(|height| height.to_string())
            .unwrap_or_else(|| "null".to_string()),
        bytes_hex(transaction.signature.as_slice()),
    ]
    .join("\t")
}

fn parse_pending_transaction_record(line: &str) -> Result<(Hash32, Transaction), NodeRunnerError> {
    let parts: Vec<&str> = line.split('\t').collect();
    if parts.len() != 11 {
        return Err(NodeRunnerError::InvalidPendingRecord(line.to_string()));
    }
    if parts[0] != "xriq-pending-transaction-v1" {
        return Err(NodeRunnerError::InvalidPendingRecord(line.to_string()));
    }
    let tx_hash = parse_hash("--pending-file", parts[1])?;
    let version = parts[2]
        .parse::<u16>()
        .map_err(|_| NodeRunnerError::InvalidPendingRecord(line.to_string()))?;
    let expires_at_height = match parts[9] {
        "null" => None,
        value => Some(
            value
                .parse::<u64>()
                .map_err(|_| NodeRunnerError::InvalidPendingRecord(line.to_string()))?,
        ),
    };
    let signature = parse_hex_bytes(parts[10])
        .map(SignatureBytes::new)
        .map_err(|_| NodeRunnerError::InvalidPendingRecord(line.to_string()))?;
    let transaction = Transaction {
        version,
        chain_id: parts[3].to_string(),
        from: Address::parse(parts[4])
            .map_err(|_| NodeRunnerError::InvalidPendingRecord(line.to_string()))?,
        to: Address::parse(parts[5])
            .map_err(|_| NodeRunnerError::InvalidPendingRecord(line.to_string()))?,
        amount: XriqAmount::from_base_units(
            parts[6]
                .parse::<u128>()
                .map_err(|_| NodeRunnerError::InvalidPendingRecord(line.to_string()))?,
        ),
        fee: XriqAmount::from_base_units(
            parts[7]
                .parse::<u128>()
                .map_err(|_| NodeRunnerError::InvalidPendingRecord(line.to_string()))?,
        ),
        nonce: parts[8]
            .parse::<u64>()
            .map_err(|_| NodeRunnerError::InvalidPendingRecord(line.to_string()))?,
        memo_hash: None,
        expires_at_height,
        signature,
    };
    if transaction_hash(&transaction) != tx_hash {
        return Err(NodeRunnerError::InvalidPendingRecord(line.to_string()));
    }
    Ok((tx_hash, transaction))
}

fn parse_private_devnet_transfer_draft(
    draft_text: &str,
    expected_chain_id: &str,
) -> Result<PrivateDevnetTransferInput, NodeRunnerError> {
    let fields = DraftFields::parse(draft_text)?;
    let version = fields.required("version")?;
    let expected_version = Transaction::SUPPORTED_VERSION;
    if version != expected_version.to_string() {
        return Err(NodeRunnerError::UnsupportedDraftVersion {
            expected: expected_version,
            actual: version.to_string(),
        });
    }

    let chain_id = fields.required("chain_id")?;
    if chain_id != expected_chain_id {
        return Err(NodeRunnerError::WrongDraftChainId {
            expected: expected_chain_id.to_string(),
            actual: chain_id.to_string(),
        });
    }

    Ok(PrivateDevnetTransferInput {
        from: parse_address("from", fields.required("from")?)?,
        to: parse_address("to", fields.required("to")?)?,
        amount: parse_amount("amount", fields.required("amount")?)?,
        fee: parse_amount("fee", fields.required("fee")?)?,
        nonce: parse_u64("nonce", fields.required("nonce")?)?,
        expires_at_height: fields
            .optional("expires_at_height")
            .filter(|value| !value.is_empty())
            .map(|value| parse_u64("expires_at_height", value))
            .transpose()?,
        timestamp_ms: 1_000,
        consensus_round: 0,
    })
}

fn parse_private_devnet_transfer_json(
    json_text: &str,
    expected_chain_id: &str,
) -> Result<PrivateDevnetTransferInput, NodeRunnerError> {
    let fields = JsonFields::parse(json_text)?;
    let version = fields.required_scalar("version")?;
    let expected_version = Transaction::SUPPORTED_VERSION;
    if version != expected_version.to_string() {
        return Err(NodeRunnerError::UnsupportedDraftVersion {
            expected: expected_version,
            actual: version.to_string(),
        });
    }

    let chain_id = fields.required_scalar("chain_id")?;
    if chain_id != expected_chain_id {
        return Err(NodeRunnerError::WrongDraftChainId {
            expected: expected_chain_id.to_string(),
            actual: chain_id.to_string(),
        });
    }

    Ok(PrivateDevnetTransferInput {
        from: parse_address("from", fields.required_scalar("from")?)?,
        to: parse_address("to", fields.required_scalar("to")?)?,
        amount: parse_amount(
            "amount_base_units",
            fields.required_scalar_any(&["amount_base_units", "amount"])?,
        )?,
        fee: parse_amount(
            "fee_base_units",
            fields.required_scalar_any(&["fee_base_units", "fee"])?,
        )?,
        nonce: parse_u64("nonce", fields.required_scalar("nonce")?)?,
        expires_at_height: fields
            .optional_scalar("expires_at_height")?
            .map(|value| parse_u64("expires_at_height", value))
            .transpose()?,
        timestamp_ms: fields
            .optional_scalar("timestamp_ms")?
            .map(|value| parse_u64("timestamp_ms", value))
            .transpose()?
            .unwrap_or(1_000),
        consensus_round: fields
            .optional_scalar("consensus_round")?
            .map(|value| parse_u64("consensus_round", value))
            .transpose()?
            .unwrap_or(0),
    })
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct DraftFields {
    pairs: Vec<(String, String)>,
}

impl DraftFields {
    fn parse(draft_text: &str) -> Result<Self, NodeRunnerError> {
        let mut pairs = Vec::new();
        for line in draft_text.lines() {
            let line = line.trim().trim_start_matches('\u{feff}');
            if line.is_empty() {
                continue;
            }
            let Some((field, value)) = line.split_once('=') else {
                return Err(NodeRunnerError::InvalidDraftLine(line.to_string()));
            };
            let field = field.trim();
            if !is_allowed_draft_field(field) {
                return Err(NodeRunnerError::UnknownDraftField(field.to_string()));
            }
            if pairs
                .iter()
                .any(|(existing_field, _)| existing_field == field)
            {
                return Err(NodeRunnerError::DuplicateDraftField(field.to_string()));
            }
            pairs.push((field.to_string(), value.trim().to_string()));
        }
        Ok(Self { pairs })
    }

    fn required(&self, field: &'static str) -> Result<&str, NodeRunnerError> {
        self.optional(field)
            .ok_or(NodeRunnerError::MissingDraftField(field))
    }

    fn optional(&self, field: &str) -> Option<&str> {
        self.pairs
            .iter()
            .find(|(candidate, _)| candidate == field)
            .map(|(_, value)| value.as_str())
    }
}

fn is_allowed_draft_field(field: &str) -> bool {
    matches!(
        field,
        "warning"
            | "version"
            | "chain_id"
            | "from"
            | "to"
            | "amount"
            | "fee"
            | "nonce"
            | "expires_at_height"
            | "transaction_hash"
            | "signature_bytes"
    )
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct JsonFields {
    pairs: Vec<(String, JsonFieldValue)>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
enum JsonFieldValue {
    String(String),
    Number(String),
    Null,
}

impl JsonFields {
    fn parse(json_text: &str) -> Result<Self, NodeRunnerError> {
        let mut parser = FlatJsonObjectParser::new(json_text);
        let pairs = parser.parse_object()?;
        Ok(Self { pairs })
    }

    fn required_scalar(&self, field: &'static str) -> Result<&str, NodeRunnerError> {
        self.optional_scalar(field)?
            .ok_or(NodeRunnerError::MissingJsonField(field))
    }

    fn required_scalar_any(&self, fields: &[&'static str]) -> Result<&str, NodeRunnerError> {
        for field in fields {
            if let Some(value) = self.optional_scalar(field)? {
                return Ok(value);
            }
        }
        Err(NodeRunnerError::MissingJsonField(fields[0]))
    }

    fn optional_scalar(&self, field: &'static str) -> Result<Option<&str>, NodeRunnerError> {
        match self.value(field) {
            Some(JsonFieldValue::String(value) | JsonFieldValue::Number(value)) => {
                Ok(Some(value.as_str()))
            }
            Some(JsonFieldValue::Null) => Ok(None),
            None => Ok(None),
        }
    }

    fn value(&self, field: &str) -> Option<&JsonFieldValue> {
        self.pairs
            .iter()
            .find(|(candidate, _)| candidate == field)
            .map(|(_, value)| value)
    }
}

struct FlatJsonObjectParser<'a> {
    input: &'a str,
    position: usize,
}

impl<'a> FlatJsonObjectParser<'a> {
    fn new(input: &'a str) -> Self {
        Self { input, position: 0 }
    }

    fn parse_object(&mut self) -> Result<Vec<(String, JsonFieldValue)>, NodeRunnerError> {
        self.skip_whitespace();
        self.expect_byte(b'{')?;
        self.skip_whitespace();

        let mut pairs = Vec::new();
        if self.consume_byte(b'}') {
            self.skip_whitespace();
            self.expect_end()?;
            return Ok(pairs);
        }

        loop {
            self.skip_whitespace();
            let field = self.parse_string()?;
            if !is_allowed_transaction_json_field(&field) {
                return Err(NodeRunnerError::UnknownJsonField(field));
            }
            if pairs
                .iter()
                .any(|(existing_field, _)| existing_field == &field)
            {
                return Err(NodeRunnerError::DuplicateJsonField(field));
            }

            self.skip_whitespace();
            self.expect_byte(b':')?;
            self.skip_whitespace();
            let value = self.parse_value()?;
            pairs.push((field, value));
            self.skip_whitespace();

            if self.consume_byte(b',') {
                continue;
            }
            if self.consume_byte(b'}') {
                break;
            }
            return Err(NodeRunnerError::InvalidJson(
                "expected comma or closing brace".to_string(),
            ));
        }

        self.skip_whitespace();
        self.expect_end()?;
        Ok(pairs)
    }

    fn parse_value(&mut self) -> Result<JsonFieldValue, NodeRunnerError> {
        match self.peek_byte() {
            Some(b'"') => self.parse_string().map(JsonFieldValue::String),
            Some(b'n') => {
                self.expect_keyword("null")?;
                Ok(JsonFieldValue::Null)
            }
            Some(b'-' | b'0'..=b'9') => self.parse_number().map(JsonFieldValue::Number),
            Some(_) => Err(NodeRunnerError::InvalidJson(
                "expected string, number, or null value".to_string(),
            )),
            None => Err(NodeRunnerError::InvalidJson(
                "missing json value".to_string(),
            )),
        }
    }

    fn parse_string(&mut self) -> Result<String, NodeRunnerError> {
        self.expect_byte(b'"')?;
        let mut output = String::new();
        while let Some(byte) = self.next_byte() {
            match byte {
                b'"' => return Ok(output),
                b'\\' => output.push(self.parse_escape()?),
                byte if byte < 0x20 => {
                    return Err(NodeRunnerError::InvalidJson(
                        "unescaped control character in string".to_string(),
                    ));
                }
                _ => {
                    let remaining = &self.input[self.position - 1..];
                    let Some(character) = remaining.chars().next() else {
                        return Err(NodeRunnerError::InvalidJson(
                            "invalid string character".to_string(),
                        ));
                    };
                    self.position = self.position - 1 + character.len_utf8();
                    output.push(character);
                }
            }
        }
        Err(NodeRunnerError::InvalidJson(
            "unterminated string".to_string(),
        ))
    }

    fn parse_escape(&mut self) -> Result<char, NodeRunnerError> {
        match self.next_byte() {
            Some(b'"') => Ok('"'),
            Some(b'\\') => Ok('\\'),
            Some(b'/') => Ok('/'),
            Some(b'b') => Ok('\u{08}'),
            Some(b'f') => Ok('\u{0c}'),
            Some(b'n') => Ok('\n'),
            Some(b'r') => Ok('\r'),
            Some(b't') => Ok('\t'),
            Some(b'u') => self.parse_unicode_escape(),
            Some(_) => Err(NodeRunnerError::InvalidJson(
                "invalid string escape".to_string(),
            )),
            None => Err(NodeRunnerError::InvalidJson(
                "unterminated string escape".to_string(),
            )),
        }
    }

    fn parse_unicode_escape(&mut self) -> Result<char, NodeRunnerError> {
        let mut value = 0_u32;
        for _ in 0..4 {
            let Some(byte) = self.next_byte() else {
                return Err(NodeRunnerError::InvalidJson(
                    "unterminated unicode escape".to_string(),
                ));
            };
            value = (value << 4)
                | u32::from(json_hex_nibble(byte).map_err(|_| {
                    NodeRunnerError::InvalidJson("invalid unicode escape".to_string())
                })?);
        }
        char::from_u32(value)
            .ok_or_else(|| NodeRunnerError::InvalidJson("invalid unicode scalar value".to_string()))
    }

    fn parse_number(&mut self) -> Result<String, NodeRunnerError> {
        let start = self.position;
        if self.consume_byte(b'-') {
            return Err(NodeRunnerError::InvalidJson(
                "negative numbers are not accepted for transfer fields".to_string(),
            ));
        }

        let mut digits = 0_usize;
        while matches!(self.peek_byte(), Some(b'0'..=b'9')) {
            self.position += 1;
            digits += 1;
        }
        if digits == 0 {
            return Err(NodeRunnerError::InvalidJson(
                "expected digits in number".to_string(),
            ));
        }
        if matches!(self.peek_byte(), Some(b'.' | b'e' | b'E')) {
            return Err(NodeRunnerError::InvalidJson(
                "only integer numbers are accepted for transfer fields".to_string(),
            ));
        }
        Ok(self.input[start..self.position].to_string())
    }

    fn skip_whitespace(&mut self) {
        while matches!(self.peek_byte(), Some(b' ' | b'\n' | b'\r' | b'\t')) {
            self.position += 1;
        }
    }

    fn expect_byte(&mut self, expected: u8) -> Result<(), NodeRunnerError> {
        if self.consume_byte(expected) {
            Ok(())
        } else {
            Err(NodeRunnerError::InvalidJson(format!(
                "expected '{}'",
                char::from(expected)
            )))
        }
    }

    fn expect_keyword(&mut self, keyword: &str) -> Result<(), NodeRunnerError> {
        if self.input[self.position..].starts_with(keyword) {
            self.position += keyword.len();
            Ok(())
        } else {
            Err(NodeRunnerError::InvalidJson(format!("expected {keyword}")))
        }
    }

    fn expect_end(&self) -> Result<(), NodeRunnerError> {
        if self.position == self.input.len() {
            Ok(())
        } else {
            Err(NodeRunnerError::InvalidJson(
                "unexpected trailing input".to_string(),
            ))
        }
    }

    fn consume_byte(&mut self, expected: u8) -> bool {
        if self.peek_byte() == Some(expected) {
            self.position += 1;
            true
        } else {
            false
        }
    }

    fn next_byte(&mut self) -> Option<u8> {
        let byte = self.peek_byte()?;
        self.position += 1;
        Some(byte)
    }

    fn peek_byte(&self) -> Option<u8> {
        self.input.as_bytes().get(self.position).copied()
    }
}

fn is_allowed_transaction_json_field(field: &str) -> bool {
    matches!(
        field,
        "format_version"
            | "warning"
            | "version"
            | "chain_id"
            | "from"
            | "to"
            | "amount_base_units"
            | "amount"
            | "fee_base_units"
            | "fee"
            | "nonce"
            | "expires_at_height"
            | "transaction_hash"
            | "timestamp_ms"
            | "consensus_round"
            | "signature_bytes"
    )
}

fn json_hex_nibble(byte: u8) -> Result<u8, ()> {
    match byte {
        b'0'..=b'9' => Ok(byte - b'0'),
        b'a'..=b'f' => Ok(byte - b'a' + 10),
        b'A'..=b'F' => Ok(byte - b'A' + 10),
        _ => Err(()),
    }
}

fn private_devnet_runner_genesis(alice_balance: Option<XriqAmount>) -> GenesisConfig {
    let genesis = GenesisConfig::private_devnet();
    match alice_balance {
        Some(balance) => genesis.with_account(
            Address::parse("xriqdev1alice00000000000")
                .expect("private devnet Alice address is valid"),
            balance,
            0,
        ),
        None => genesis,
    }
}

fn node_status<S: ChainStore>(node: &XriqNode<S>) -> NodeStatus {
    let chain_status = node.rpc_service().chain_status();
    NodeStatus {
        warning: PRIVATE_DEVNET_RUNNER_WARNING,
        chain_id: chain_status.chain_id,
        current_height: chain_status.current_height,
        latest_block_hash: chain_status.latest_block_hash,
        state_root: chain_status.state_root,
        pending_transactions: chain_status.pending_transactions,
        stored_blocks: node.store().len(),
    }
}

fn render_node_status_json(command: &str, status: &NodeStatus) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    push_node_status_json_fields(&mut output, status, "  ", false);
    output.push_str("\n}");
    output
}

fn render_chain_check_json(command: &str, status: &PrivateDevnetChainCheckStatus) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"verified\": {},", status.verified).expect("write to String");
    push_node_status_json_fields_without_warning(&mut output, &status.status, "  ", false);
    output.push_str("\n}");
    output
}

fn render_snapshot_status_json(command: &str, status: &PrivateDevnetSnapshotStatus) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(status.status.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"snapshot_format_version\": {},",
        json_string(PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"snapshot_dir\": {},",
        json_string(&status.snapshot_dir)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"chain_file\": {},",
        json_string(&status.chain_file)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"pending_file\": {},",
        json_optional_string(status.pending_file.as_deref())
    )
    .expect("write to String");
    push_node_status_json_fields_without_warning(&mut output, &status.status, "  ", false);
    output.push_str("\n}");
    output
}

fn render_snapshot_list_json(
    command: &str,
    snapshot_root: &Path,
    snapshots: &[PrivateDevnetSnapshotSummary],
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"snapshot_format_version\": {},",
        json_string(PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"snapshot_root\": {},",
        json_string(&snapshot_root.to_string_lossy())
    )
    .expect("write to String");
    writeln!(&mut output, "  \"snapshot_count\": {},", snapshots.len()).expect("write to String");
    writeln!(&mut output, "  \"snapshots\": [").expect("write to String");
    for (index, snapshot) in snapshots.iter().enumerate() {
        push_snapshot_summary_json(&mut output, snapshot, "    ");
        if index + 1 != snapshots.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_snapshot_detail_json(command: &str, snapshot: &PrivateDevnetSnapshotSummary) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"snapshot_format_version\": {},",
        json_string(PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION)
    )
    .expect("write to String");
    push_snapshot_summary_json_fields(&mut output, snapshot, "  ");
    output.push_str("\n}");
    output
}

fn render_snapshot_check_json(command: &str, status: &PrivateDevnetSnapshotCheckStatus) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"snapshot_format_version\": {},",
        json_string(PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"verified\": {},", status.verified).expect("write to String");
    writeln!(&mut output, "  \"mismatches\": [").expect("write to String");
    for (index, mismatch) in status.mismatches.iter().enumerate() {
        write!(&mut output, "    {}", json_string(mismatch)).expect("write to String");
        if index + 1 != status.mismatches.len() {
            output.push(',');
        }
        output.push('\n');
    }
    writeln!(&mut output, "  ],").expect("write to String");
    writeln!(&mut output, "  \"snapshot\": {{").expect("write to String");
    push_snapshot_summary_json_fields(&mut output, &status.snapshot, "    ");
    writeln!(&mut output, "\n  }},").expect("write to String");
    writeln!(&mut output, "  \"replayed_status\": {{").expect("write to String");
    push_node_status_json_fields_without_warning(
        &mut output,
        &status.replayed_status,
        "    ",
        false,
    );
    output.push_str("\n  }\n}");
    output
}

fn render_snapshot_manifest_json(status: &PrivateDevnetSnapshotStatus) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    writeln!(
        &mut output,
        "  \"snapshot_format_version\": {},",
        json_string(PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(status.status.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"chain_file\": {},",
        json_string(SNAPSHOT_CHAIN_FILE)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"pending_file\": {},",
        json_optional_string(
            status
                .pending_file
                .as_deref()
                .map(|_| SNAPSHOT_PENDING_FILE)
        )
    )
    .expect("write to String");
    push_node_status_json_fields_without_warning(&mut output, &status.status, "  ", false);
    output.push_str("\n}\n");
    output
}

fn render_snapshot_list(
    snapshot_root: &Path,
    snapshots: &[PrivateDevnetSnapshotSummary],
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "snapshot root: {}", snapshot_root.display()).expect("write to String");
    writeln!(&mut output, "snapshots: {}", snapshots.len()).expect("write to String");
    for snapshot in snapshots {
        writeln!(
            &mut output,
            "- {} height={} pending={} stored_blocks={} state_root={} dir={}",
            snapshot.snapshot_name,
            snapshot.status.current_height,
            snapshot.status.pending_transactions,
            snapshot.status.stored_blocks,
            hash_hex(snapshot.status.state_root),
            snapshot.snapshot_dir
        )
        .expect("write to String");
    }
    output
}

fn render_snapshot_detail(snapshot: &PrivateDevnetSnapshotSummary) -> String {
    let mut output = String::new();
    writeln!(&mut output, "snapshot {}", snapshot.snapshot_name).expect("write to String");
    writeln!(
        &mut output,
        "snapshot_format_version={}",
        PRIVATE_DEVNET_SNAPSHOT_FORMAT_VERSION
    )
    .expect("write to String");
    writeln!(&mut output, "snapshot_dir={}", snapshot.snapshot_dir).expect("write to String");
    writeln!(&mut output, "chain_file={}", snapshot.chain_file).expect("write to String");
    writeln!(
        &mut output,
        "pending_file={}",
        snapshot.pending_file.as_deref().unwrap_or("none")
    )
    .expect("write to String");
    writeln!(&mut output, "chain_id={}", snapshot.status.chain_id).expect("write to String");
    writeln!(
        &mut output,
        "current_height={}",
        snapshot.status.current_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "latest_block_hash={}",
        hash_hex(snapshot.status.latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "state_root={}",
        hash_hex(snapshot.status.state_root)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "pending_transactions={}",
        snapshot.status.pending_transactions
    )
    .expect("write to String");
    write!(
        &mut output,
        "stored_blocks={}",
        snapshot.status.stored_blocks
    )
    .expect("write to String");
    output
}

fn render_snapshot_check(status: &PrivateDevnetSnapshotCheckStatus) -> String {
    let mut output = String::new();
    writeln!(
        &mut output,
        "snapshot check {}",
        status.snapshot.snapshot_name
    )
    .expect("write to String");
    writeln!(&mut output, "verified={}", status.verified).expect("write to String");
    writeln!(
        &mut output,
        "mismatches={}",
        if status.mismatches.is_empty() {
            "none".to_string()
        } else {
            status.mismatches.join(",")
        }
    )
    .expect("write to String");
    writeln!(&mut output, "snapshot_dir={}", status.snapshot.snapshot_dir)
        .expect("write to String");
    writeln!(
        &mut output,
        "manifest_current_height={}",
        status.snapshot.status.current_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "replayed_current_height={}",
        status.replayed_status.current_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "manifest_latest_block_hash={}",
        hash_hex(status.snapshot.status.latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "replayed_latest_block_hash={}",
        hash_hex(status.replayed_status.latest_block_hash)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "manifest_state_root={}",
        hash_hex(status.snapshot.status.state_root)
    )
    .expect("write to String");
    write!(
        &mut output,
        "replayed_state_root={}",
        hash_hex(status.replayed_status.state_root)
    )
    .expect("write to String");
    output
}

fn render_produced_transfer_block_status_json(
    command: &str,
    status: &ProducedTransferBlockStatus,
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(status.status.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_hash\": {},",
        json_string(&hash_hex(status.transaction_hash))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"block_hash\": {},",
        json_string(&hash_hex(status.block_hash))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"applied_transactions\": {},",
        status.applied_transactions
    )
    .expect("write to String");
    push_node_status_json_fields_without_warning(&mut output, &status.status, "  ", false);
    output.push_str("\n}");
    output
}

fn render_produced_pending_block_status_json(
    command: &str,
    status: &ProducedPendingBlockStatus,
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(status.status.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"block_hash\": {},",
        json_string(&hash_hex(status.block_hash))
    )
    .expect("write to String");
    writeln!(&mut output, "  \"included_transaction_hashes\": [").expect("write to String");
    for (index, tx_hash) in status.included_transaction_hashes.iter().enumerate() {
        let trailing = if index + 1 == status.included_transaction_hashes.len() {
            ""
        } else {
            ","
        };
        writeln!(
            &mut output,
            "    {}{}",
            json_string(&hash_hex(*tx_hash)),
            trailing
        )
        .expect("write to String");
    }
    writeln!(&mut output, "  ],").expect("write to String");
    writeln!(
        &mut output,
        "  \"applied_transactions\": {},",
        status.applied_transactions
    )
    .expect("write to String");
    push_node_status_json_fields_without_warning(&mut output, &status.status, "  ", false);
    output.push_str("\n}");
    output
}

fn render_preflight_transfer_status_json(status: &PrivateDevnetPreflightTransferStatus) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, "preflight-transfer");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(status.status.warning)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"from\": {},",
        json_string(status.from.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"to\": {},",
        json_string(status.to.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"amount_base_units\": {},",
        json_string(&status.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"fee_base_units\": {},",
        json_string(&status.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"preflight_balance_base_units\": {},",
        json_string(&status.preflight_balance.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"preflight_nonce\": {},",
        status.preflight_nonce
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_hash\": {},",
        json_string(&hash_hex(status.transaction_hash))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"block_hash\": {},",
        json_string(&hash_hex(status.block_hash))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"confirmed_block_height\": {},",
        status.confirmed_block_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"confirmed_transaction_index\": {},",
        status.confirmed_transaction_index
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"final_balance_base_units\": {},",
        json_string(&status.final_balance.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut output, "  \"final_nonce\": {},", status.final_nonce).expect("write to String");
    push_node_status_json_fields_without_warning(&mut output, &status.status, "  ", false);
    output.push_str("\n}");
    output
}

fn render_explorer_overview_json(
    command: &str,
    overview: &ExplorerOverview,
    latest_blocks: &[ExplorerBlockSummary],
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"chain_id\": {},",
        json_string(&overview.chain_id)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"current_height\": {},",
        overview.current_height
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"latest_block_hash\": {},",
        json_string(&hash_hex(overview.latest_block_hash))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"state_root\": {},",
        json_string(&hash_hex(overview.state_root))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"pending_transactions\": {},",
        overview.pending_transactions
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"stored_blocks\": {},",
        overview.stored_blocks
    )
    .expect("write to String");
    writeln!(&mut output, "  \"latest_blocks\": [").expect("write to String");
    for (index, block) in latest_blocks.iter().enumerate() {
        push_block_summary_json(&mut output, block, "    ");
        if index + 1 != latest_blocks.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_block_list_json(command: &str, blocks: &[ExplorerBlockSummary]) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"block_count\": {},", blocks.len()).expect("write to String");
    writeln!(&mut output, "  \"blocks\": [").expect("write to String");
    for (index, block) in blocks.iter().enumerate() {
        push_block_summary_json(&mut output, block, "    ");
        if index + 1 != blocks.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_block_detail_json(command: &str, block: &ExplorerBlockDetail) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"height\": {},", block.summary.height).expect("write to String");
    writeln!(
        &mut output,
        "  \"block_hash\": {},",
        json_string(&hash_hex(block.summary.block_hash))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"previous_block_hash\": {},",
        json_string(&hash_hex(block.previous_block_hash))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"state_root\": {},",
        json_string(&hash_hex(block.state_root))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transactions_root\": {},",
        json_string(&hash_hex(block.transactions_root))
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_count\": {},",
        block.summary.transaction_count
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"producer\": {},",
        json_string(block.summary.producer.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"timestamp_ms\": {},",
        block.summary.timestamp_ms
    )
    .expect("write to String");
    writeln!(&mut output, "  \"transactions\": [").expect("write to String");
    for (index, transaction) in block.transactions.iter().enumerate() {
        push_transaction_summary_json(&mut output, transaction, "    ");
        if index + 1 != block.transactions.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_account_list_json(command: &str, accounts: &[ExplorerAccountDetail]) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(&mut output, "  \"account_count\": {},", accounts.len()).expect("write to String");
    writeln!(&mut output, "  \"accounts\": [").expect("write to String");
    for (index, account) in accounts.iter().enumerate() {
        writeln!(&mut output, "    {{").expect("write to String");
        push_account_detail_json(&mut output, account, "      ");
        output.push('\n');
        output.push_str("    }");
        if index + 1 != accounts.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_account_detail_json(command: &str, account: &ExplorerAccountDetail) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    push_account_detail_json(&mut output, account, "  ");
    output.push('\n');
    output.push('}');
    output
}

fn render_account_transactions_json(
    command: &str,
    address: &Address,
    transactions: &[ExplorerAccountTransaction],
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"address\": {},",
        json_string(address.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_count\": {},",
        transactions.len()
    )
    .expect("write to String");
    writeln!(&mut output, "  \"transactions\": [").expect("write to String");
    for (index, transaction) in transactions.iter().enumerate() {
        push_account_transaction_json(&mut output, transaction, "    ");
        if index + 1 != transactions.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_transaction_list_json(
    command: &str,
    transactions: &[ExplorerConfirmedTransaction],
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"transaction_count\": {},",
        transactions.len()
    )
    .expect("write to String");
    writeln!(&mut output, "  \"transactions\": [").expect("write to String");
    for (index, transaction) in transactions.iter().enumerate() {
        push_confirmed_transaction_json(&mut output, transaction, "    ");
        if index + 1 != transactions.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_mempool_detail_json(command: &str, detail: &ExplorerMempoolDetail) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, command);
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"pending_count\": {},",
        detail.pending_count
    )
    .expect("write to String");
    writeln!(&mut output, "  \"transactions\": [").expect("write to String");
    for (index, transaction) in detail.transactions.iter().enumerate() {
        push_pending_transaction_json(&mut output, transaction, "    ");
        if index + 1 != detail.transactions.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn render_transaction_detail(detail: &PrivateDevnetTransactionDetail) -> String {
    let mut output = String::new();
    match detail {
        PrivateDevnetTransactionDetail::Confirmed(detail) => {
            writeln!(&mut output, "transaction {}", hash_hex(detail.tx_hash))
                .expect("write to String");
            writeln!(&mut output, "status: {}", detail.status).expect("write to String");
            writeln!(&mut output, "block_height: {}", detail.block_height)
                .expect("write to String");
            writeln!(&mut output, "block_hash: {}", hash_hex(detail.block_hash))
                .expect("write to String");
            writeln!(
                &mut output,
                "transaction_index: {}",
                detail.transaction_index
            )
            .expect("write to String");
            push_transaction_text_fields(&mut output, &detail.transaction);
        }
        PrivateDevnetTransactionDetail::Pending(detail) => {
            writeln!(&mut output, "transaction {}", hash_hex(detail.tx_hash))
                .expect("write to String");
            writeln!(&mut output, "status: {}", detail.status).expect("write to String");
            writeln!(&mut output, "received_order: {}", detail.received_order)
                .expect("write to String");
            push_transaction_text_fields(&mut output, &detail.transaction);
        }
    }
    output
}

fn render_transaction_detail_json(detail: &PrivateDevnetTransactionDetail) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, "transaction-detail");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    match detail {
        PrivateDevnetTransactionDetail::Confirmed(detail) => {
            writeln!(
                &mut output,
                "  \"tx_hash\": {},",
                json_string(&hash_hex(detail.tx_hash))
            )
            .expect("write to String");
            writeln!(&mut output, "  \"status\": {},", json_string(detail.status))
                .expect("write to String");
            writeln!(&mut output, "  \"block_height\": {},", detail.block_height)
                .expect("write to String");
            writeln!(
                &mut output,
                "  \"block_hash\": {},",
                json_string(&hash_hex(detail.block_hash))
            )
            .expect("write to String");
            writeln!(
                &mut output,
                "  \"transaction_index\": {},",
                detail.transaction_index
            )
            .expect("write to String");
            push_transaction_json_fields(&mut output, &detail.transaction, "  ", false);
        }
        PrivateDevnetTransactionDetail::Pending(detail) => {
            writeln!(
                &mut output,
                "  \"tx_hash\": {},",
                json_string(&hash_hex(detail.tx_hash))
            )
            .expect("write to String");
            writeln!(&mut output, "  \"status\": {},", json_string(detail.status))
                .expect("write to String");
            writeln!(
                &mut output,
                "  \"received_order\": {},",
                detail.received_order
            )
            .expect("write to String");
            push_transaction_json_fields(&mut output, &detail.transaction, "  ", false);
        }
    }
    output.push_str("\n}");
    output
}

fn push_transaction_text_fields(output: &mut String, transaction: &Transaction) {
    writeln!(output, "from: {}", transaction.from).expect("write to String");
    writeln!(output, "to: {}", transaction.to).expect("write to String");
    writeln!(
        output,
        "amount_base_units: {}",
        transaction.amount.base_units()
    )
    .expect("write to String");
    writeln!(output, "fee_base_units: {}", transaction.fee.base_units()).expect("write to String");
    writeln!(output, "nonce: {}", transaction.nonce).expect("write to String");
    write!(
        output,
        "expires_at_height: {}",
        transaction
            .expires_at_height
            .map(|height| height.to_string())
            .unwrap_or_else(|| "none".to_string())
    )
    .expect("write to String");
}

fn push_success_json_preamble(output: &mut String, command: &str) {
    writeln!(
        output,
        "  \"format_version\": {},",
        json_string("xriq-node-json-v1")
    )
    .expect("write to String");
    writeln!(output, "  \"command\": {},", json_string(command)).expect("write to String");
}

fn push_node_status_json_fields(
    output: &mut String,
    status: &NodeStatus,
    indent: &str,
    trailing_comma: bool,
) {
    writeln!(
        output,
        "{indent}\"warning\": {},",
        json_string(status.warning)
    )
    .expect("write to String");
    push_node_status_json_fields_without_warning(output, status, indent, trailing_comma);
}

fn push_node_status_json_fields_without_warning(
    output: &mut String,
    status: &NodeStatus,
    indent: &str,
    trailing_comma: bool,
) {
    writeln!(
        output,
        "{indent}\"chain_id\": {},",
        json_string(&status.chain_id)
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"current_height\": {},",
        status.current_height
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"latest_block_hash\": {},",
        json_string(&hash_hex(status.latest_block_hash))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"state_root\": {},",
        json_string(&hash_hex(status.state_root))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"pending_transactions\": {},",
        status.pending_transactions
    )
    .expect("write to String");
    write!(
        output,
        "{indent}\"stored_blocks\": {}",
        status.stored_blocks
    )
    .expect("write to String");
    if trailing_comma {
        output.push(',');
    }
}

fn push_snapshot_summary_json(
    output: &mut String,
    snapshot: &PrivateDevnetSnapshotSummary,
    indent: &str,
) {
    writeln!(output, "{indent}{{").expect("write to String");
    push_snapshot_summary_json_fields(output, snapshot, &format!("{indent}  "));
    write!(output, "\n{indent}}}").expect("write to String");
}

fn push_snapshot_summary_json_fields(
    output: &mut String,
    snapshot: &PrivateDevnetSnapshotSummary,
    indent: &str,
) {
    writeln!(
        output,
        "{indent}\"snapshot_name\": {},",
        json_string(&snapshot.snapshot_name)
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"snapshot_dir\": {},",
        json_string(&snapshot.snapshot_dir)
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"chain_file\": {},",
        json_string(&snapshot.chain_file)
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"pending_file\": {},",
        json_optional_string(snapshot.pending_file.as_deref())
    )
    .expect("write to String");
    push_node_status_json_fields_without_warning(output, &snapshot.status, indent, false);
}

fn push_block_summary_json(output: &mut String, block: &ExplorerBlockSummary, indent: &str) {
    writeln!(output, "{indent}{{").expect("write to String");
    writeln!(output, "{indent}  \"height\": {},", block.height).expect("write to String");
    writeln!(
        output,
        "{indent}  \"block_hash\": {},",
        json_string(&hash_hex(block.block_hash))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"transaction_count\": {},",
        block.transaction_count
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"producer\": {},",
        json_string(block.producer.as_str())
    )
    .expect("write to String");
    writeln!(output, "{indent}  \"timestamp_ms\": {}", block.timestamp_ms)
        .expect("write to String");
    write!(output, "{indent}}}").expect("write to String");
}

fn push_transaction_summary_json(
    output: &mut String,
    transaction: &xriq_explorer::ExplorerTransactionSummary,
    indent: &str,
) {
    writeln!(output, "{indent}{{").expect("write to String");
    writeln!(output, "{indent}  \"index\": {},", transaction.index).expect("write to String");
    writeln!(
        output,
        "{indent}  \"tx_hash\": {},",
        json_string(&hash_hex(transaction.tx_hash))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"from\": {},",
        json_string(transaction.from.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"to\": {},",
        json_string(transaction.to.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"amount_base_units\": {},",
        json_string(&transaction.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"fee_base_units\": {},",
        json_string(&transaction.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(output, "{indent}  \"nonce\": {},", transaction.nonce).expect("write to String");
    writeln!(
        output,
        "{indent}  \"expires_at_height\": {}",
        json_optional_u64(transaction.expires_at_height)
    )
    .expect("write to String");
    write!(output, "{indent}}}").expect("write to String");
}

fn push_account_detail_json(output: &mut String, account: &ExplorerAccountDetail, indent: &str) {
    writeln!(
        output,
        "{indent}\"address\": {},",
        json_string(account.address.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"balance_base_units\": {},",
        json_string(&account.balance.base_units().to_string())
    )
    .expect("write to String");
    write!(output, "{indent}\"nonce\": {}", account.nonce).expect("write to String");
}

fn push_account_transaction_json(
    output: &mut String,
    transaction: &ExplorerAccountTransaction,
    indent: &str,
) {
    writeln!(output, "{indent}{{").expect("write to String");
    writeln!(
        output,
        "{indent}  \"block_height\": {},",
        transaction.block_height
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"block_hash\": {},",
        json_string(&hash_hex(transaction.block_hash))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"transaction_index\": {},",
        transaction.transaction_index
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"direction\": {},",
        json_string(transaction.direction)
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"tx_hash\": {},",
        json_string(&hash_hex(transaction.tx_hash))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"from\": {},",
        json_string(transaction.from.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"to\": {},",
        json_string(transaction.to.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"amount_base_units\": {},",
        json_string(&transaction.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"fee_base_units\": {},",
        json_string(&transaction.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(output, "{indent}  \"nonce\": {},", transaction.nonce).expect("write to String");
    writeln!(
        output,
        "{indent}  \"expires_at_height\": {}",
        json_optional_u64(transaction.expires_at_height)
    )
    .expect("write to String");
    write!(output, "{indent}}}").expect("write to String");
}

fn push_confirmed_transaction_json(
    output: &mut String,
    transaction: &ExplorerConfirmedTransaction,
    indent: &str,
) {
    writeln!(output, "{indent}{{").expect("write to String");
    writeln!(
        output,
        "{indent}  \"block_height\": {},",
        transaction.block_height
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"block_hash\": {},",
        json_string(&hash_hex(transaction.block_hash))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"transaction_index\": {},",
        transaction.transaction_index
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"tx_hash\": {},",
        json_string(&hash_hex(transaction.tx_hash))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"from\": {},",
        json_string(transaction.from.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"to\": {},",
        json_string(transaction.to.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"amount_base_units\": {},",
        json_string(&transaction.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"fee_base_units\": {},",
        json_string(&transaction.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(output, "{indent}  \"nonce\": {},", transaction.nonce).expect("write to String");
    writeln!(
        output,
        "{indent}  \"expires_at_height\": {}",
        json_optional_u64(transaction.expires_at_height)
    )
    .expect("write to String");
    write!(output, "{indent}}}").expect("write to String");
}

fn push_transaction_json_fields(
    output: &mut String,
    transaction: &Transaction,
    indent: &str,
    trailing_comma: bool,
) {
    writeln!(
        output,
        "{indent}\"from\": {},",
        json_string(transaction.from.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"to\": {},",
        json_string(transaction.to.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"amount_base_units\": {},",
        json_string(&transaction.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}\"fee_base_units\": {},",
        json_string(&transaction.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(output, "{indent}\"nonce\": {},", transaction.nonce).expect("write to String");
    write!(
        output,
        "{indent}\"expires_at_height\": {}",
        json_optional_u64(transaction.expires_at_height)
    )
    .expect("write to String");
    if trailing_comma {
        output.push(',');
    }
}

fn push_pending_transaction_json(
    output: &mut String,
    transaction: &xriq_explorer::ExplorerPendingTransaction,
    indent: &str,
) {
    writeln!(output, "{indent}{{").expect("write to String");
    writeln!(
        output,
        "{indent}  \"tx_hash\": {},",
        json_string(&hash_hex(transaction.tx_hash))
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"from\": {},",
        json_string(transaction.from.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"to\": {},",
        json_string(transaction.to.as_str())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"amount_base_units\": {},",
        json_string(&transaction.amount.base_units().to_string())
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"fee_base_units\": {},",
        json_string(&transaction.fee.base_units().to_string())
    )
    .expect("write to String");
    writeln!(output, "{indent}  \"nonce\": {},", transaction.nonce).expect("write to String");
    writeln!(
        output,
        "{indent}  \"received_order\": {},",
        transaction.received_order
    )
    .expect("write to String");
    writeln!(
        output,
        "{indent}  \"expires_at_height\": {}",
        json_optional_u64(transaction.expires_at_height)
    )
    .expect("write to String");
    write!(output, "{indent}}}").expect("write to String");
}

fn json_optional_u64(value: Option<u64>) -> String {
    value
        .map(|number| number.to_string())
        .unwrap_or_else(|| "null".to_string())
}

fn json_optional_string(value: Option<&str>) -> String {
    value.map(json_string).unwrap_or_else(|| "null".to_string())
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

fn parse_address(_flag: &'static str, value: &str) -> Result<Address, NodeRunnerError> {
    Address::parse(value).map_err(NodeRunnerError::InvalidAddress)
}

fn parse_u64(flag: &'static str, value: &str) -> Result<u64, NodeRunnerError> {
    value.parse().map_err(|_| NodeRunnerError::InvalidNumber {
        flag,
        value: value.to_string(),
    })
}

fn parse_usize(flag: &'static str, value: &str) -> Result<usize, NodeRunnerError> {
    value.parse().map_err(|_| NodeRunnerError::InvalidNumber {
        flag,
        value: value.to_string(),
    })
}

fn parse_hash(flag: &'static str, value: &str) -> Result<Hash32, NodeRunnerError> {
    parse_hash_hex(value).map_err(|_| NodeRunnerError::InvalidHash {
        flag,
        value: value.to_string(),
    })
}

fn bytes_hex(bytes: &[u8]) -> String {
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        use fmt::Write;
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
}

fn parse_hex_bytes(value: &str) -> Result<Vec<u8>, ()> {
    if !value.len().is_multiple_of(2) {
        return Err(());
    }
    let mut bytes = Vec::with_capacity(value.len() / 2);
    for chunk in value.as_bytes().chunks_exact(2) {
        bytes.push((hex_nibble(chunk[0])? << 4) | hex_nibble(chunk[1])?);
    }
    Ok(bytes)
}

fn parse_amount(flag: &'static str, value: &str) -> Result<XriqAmount, NodeRunnerError> {
    Ok(XriqAmount::from_base_units(value.parse().map_err(
        |_| NodeRunnerError::InvalidNumber {
            flag,
            value: value.to_string(),
        },
    )?))
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct RunnerFlagParser {
    pairs: Vec<(String, String)>,
}

impl RunnerFlagParser {
    fn parse(args: &[String]) -> Result<Self, NodeRunnerError> {
        let mut pairs = Vec::new();
        let mut index = 0;
        while index < args.len() {
            let flag = &args[index];
            if !flag.starts_with("--") {
                return Err(NodeRunnerError::UnexpectedArgument(flag.clone()));
            }
            let value = args
                .get(index + 1)
                .ok_or_else(|| NodeRunnerError::MissingFlag(flag_to_static(flag)))?;
            if value.starts_with("--") {
                return Err(NodeRunnerError::MissingFlag(flag_to_static(flag)));
            }
            if pairs.iter().any(|(existing_flag, _)| existing_flag == flag) {
                return Err(NodeRunnerError::DuplicateFlag(flag.clone()));
            }
            pairs.push((flag.clone(), value.clone()));
            index += 2;
        }
        Ok(Self { pairs })
    }

    fn required(&self, flag: &'static str) -> Result<&str, NodeRunnerError> {
        self.optional(flag)
            .ok_or(NodeRunnerError::MissingFlag(flag))
    }

    fn optional(&self, flag: &str) -> Option<&str> {
        self.pairs
            .iter()
            .find(|(candidate, _)| candidate == flag)
            .map(|(_, value)| value.as_str())
    }

    fn reject_unknown(&self, allowed: &[&str]) -> Result<(), NodeRunnerError> {
        for (flag, _) in &self.pairs {
            if !allowed.iter().any(|allowed_flag| allowed_flag == flag) {
                return Err(NodeRunnerError::UnknownFlag(flag.clone()));
            }
        }
        Ok(())
    }
}

fn flag_to_static(flag: &str) -> &'static str {
    match flag {
        "--chain-file" => "--chain-file",
        "--draft-file" => "--draft-file",
        "--pending-file" => "--pending-file",
        "--alice-balance" => "--alice-balance",
        "--limit" => "--limit",
        "--height" => "--height",
        "--block-hash" => "--block-hash",
        "--address" => "--address",
        "--tx-hash" => "--tx-hash",
        "--snapshot-root" => "--snapshot-root",
        "--snapshot-dir" => "--snapshot-dir",
        "--from" => "--from",
        "--to" => "--to",
        "--amount" => "--amount",
        "--fee" => "--fee",
        "--nonce" => "--nonce",
        "--expires-at-height" => "--expires-at-height",
        "--timestamp-ms" => "--timestamp-ms",
        "--consensus-round" => "--consensus-round",
        "--format" => "--format",
        "--bind" => "--bind",
        _ => "--flag",
    }
}

fn parse_hash_hex(value: &str) -> Result<Hash32, ()> {
    if value.len() != 64 {
        return Err(());
    }
    let mut bytes = [0_u8; 32];
    for (index, chunk) in value.as_bytes().chunks_exact(2).enumerate() {
        bytes[index] = (hex_nibble(chunk[0])? << 4) | hex_nibble(chunk[1])?;
    }
    Ok(Hash32::from_bytes(bytes))
}

fn hex_nibble(byte: u8) -> Result<u8, ()> {
    match byte {
        b'0'..=b'9' => Ok(byte - b'0'),
        b'a'..=b'f' => Ok(byte - b'a' + 10),
        _ => Err(()),
    }
}

fn hash_hex(hash: Hash32) -> String {
    let mut output = String::with_capacity(64);
    for byte in hash.as_bytes() {
        use fmt::Write;
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
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
            node.verify_replayed_chain_state(genesis)?;
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

        node.verify_replayed_chain_state(genesis)?;
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

    pub fn produce_next_block_with_private_devnet_signature(
        &mut self,
        timestamp_ms: u64,
        consensus_round: u64,
    ) -> Result<ProducedBlock, NodeError> {
        let (state_root, transactions_root) = self.next_canonical_roots()?;
        let height = self
            .ledger
            .current_height()
            .checked_add(1)
            .ok_or(NodeError::Header(BlockValidationError::HeightOverflow))?;
        let header = BlockHeader {
            version: BlockHeader::SUPPORTED_VERSION,
            chain_id: self.ledger.config().chain_id.clone(),
            height,
            previous_block_hash: self.latest_block_hash,
            state_root,
            transactions_root,
            timestamp_ms,
            producer: self.producer.config().producer.clone(),
            consensus_round,
            signature: SignatureBytes::new(Vec::new()),
        };
        let signature = test_only_signature_for_hash(block_header_signing_hash(&header));
        self.produce_next_block_with_canonical_roots(ProduceNextBlockCanonicalRootsInput {
            timestamp_ms,
            consensus_round,
            signature,
        })
    }

    fn next_canonical_roots(&self) -> Result<(Hash32, Hash32), NodeError> {
        let transactions: Vec<Transaction> = self
            .mempool
            .ordered_entries()
            .into_iter()
            .take(self.producer.config().max_transactions_per_block)
            .map(|entry| entry.tx.clone())
            .collect();
        let mut next_ledger = self.ledger.clone();
        for transaction in &transactions {
            next_ledger
                .apply_transaction(transaction)
                .map_err(NodeError::Ledger)?;
        }
        Ok((
            account_state_root(&next_ledger.state_root_entries()),
            canonical_transactions_root(&transactions),
        ))
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

    /// Export up to `limit` stored blocks starting at `from_height`, encoded for
    /// peer transfer. Serving these is read-only and safe for any peer to pull.
    pub fn export_peer_blocks(&self, from_height: u64, limit: usize) -> Result<Vec<u8>, NodeError> {
        let mut blocks = Vec::new();
        let mut height = from_height;
        while blocks.len() < limit {
            match self.store.block_by_height(height) {
                Some(record) => blocks.push(record.block.clone()),
                None => break,
            }
            height += 1;
        }
        xriq_storage::encode_peer_blocks(&blocks).map_err(NodeError::Storage)
    }

    /// Import peer-encoded blocks into this node. Each block is fully validated
    /// (canonical roots, ledger execution, producer authority, and test-only
    /// signatures) before commit, exactly like a locally produced block; a peer
    /// cannot inject invalid state. Blocks at or below the current height are
    /// skipped so a resend is idempotent.
    pub fn import_peer_blocks(&mut self, bytes: &[u8]) -> Result<PeerSyncOutcome, NodeError> {
        let blocks = xriq_storage::decode_peer_blocks(bytes).map_err(NodeError::Storage)?;
        let mut applied = 0usize;
        for block in blocks {
            if block.header.height <= self.ledger.current_height() {
                continue;
            }
            self.import_block_with_canonical_hash(block)?;
            applied += 1;
        }
        Ok(PeerSyncOutcome {
            applied,
            current_height: self.ledger.current_height(),
            latest_block_hash: self.latest_block_hash,
        })
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

    fn verify_replayed_chain_state(&self, genesis: &GenesisConfig) -> Result<(), NodeError> {
        let expected_blocks = self
            .ledger
            .current_height()
            .checked_sub(genesis.initial_height)
            .ok_or(NodeError::UnexpectedStoredBlockHeight {
                minimum: genesis.initial_height,
                actual: self.ledger.current_height(),
            })?;
        let expected_blocks = usize::try_from(expected_blocks)
            .map_err(|_| NodeError::Header(BlockValidationError::HeightOverflow))?;
        if self.store.len() != expected_blocks {
            return Err(NodeError::UnexpectedStoredBlockCount {
                expected: expected_blocks,
                actual: self.store.len(),
            });
        }

        if expected_blocks == 0 {
            return Ok(());
        }

        let current_height = self.ledger.current_height();
        let latest_record = self
            .store
            .latest_block()
            .ok_or(NodeError::MissingStoredBlock {
                height: current_height,
            })?;
        if latest_record.block.header.height != current_height {
            return Err(NodeError::UnexpectedStoredBlockHeight {
                minimum: current_height,
                actual: latest_record.block.header.height,
            });
        }
        if latest_record.block_hash != self.latest_block_hash {
            return Err(NodeError::WrongStoredBlockHash {
                expected: latest_record.block_hash,
                actual: self.latest_block_hash,
            });
        }

        let expected_state_root = account_state_root(&self.ledger.state_root_entries());
        if latest_record.block.header.state_root != expected_state_root {
            return Err(NodeError::WrongStateRoot {
                expected: expected_state_root,
                actual: latest_record.block.header.state_root,
            });
        }

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
        path::{Path, PathBuf},
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

    fn node_state_root<S: ChainStore>(node: &XriqNode<S>) -> Hash32 {
        xriq_crypto::account_state_root(&node.ledger().state_root_entries())
    }

    fn genesis_state_root() -> Hash32 {
        node_state_root(&node())
    }

    fn temp_store_path() -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("xriq-node-store-{nanos}.bin"))
    }

    fn temp_snapshot_dir() -> PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        std::env::temp_dir().join(format!("xriq-node-snapshot-{nanos}"))
    }

    fn write_wallet_draft(path: &Path, amount: u128, fee: u128, nonce: u64) {
        fs::write(
            path,
            [
                "warning=private-devnet-test-identity-only".to_string(),
                "version=1".to_string(),
                "chain_id=xriq-devnet".to_string(),
                "from=xriqdev1alice00000000000".to_string(),
                "to=xriqdev1bobbb00000000000".to_string(),
                format!("amount={amount}"),
                format!("fee={fee}"),
                format!("nonce={nonce}"),
                "expires_at_height=100".to_string(),
                "signature_bytes=48".to_string(),
            ]
            .join("\n"),
        )
        .unwrap();
    }

    fn hash_hex_from_json_field(json: &str, field: &str) -> Hash32 {
        let needle = format!("\"{field}\": \"");
        let value_start = json.find(&needle).expect("json field exists") + needle.len();
        let value_end = json[value_start..]
            .find('"')
            .map(|offset| value_start + offset)
            .expect("json string field closes");
        parse_hash_hex(&json[value_start..value_end]).expect("json field is hash hex")
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
    fn follower_syncs_multiple_blocks_from_peer_export() {
        let mut leader = node();
        let mut follower = node();

        // Leader produces two blocks (one transaction each).
        leader
            .submit_transaction(hash(1), transaction(address("alice"), 0, 25, 2))
            .unwrap();
        leader
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&leader))
            .unwrap();
        leader
            .submit_transaction(hash(2), transaction(address("alice"), 1, 10, 2))
            .unwrap();
        leader
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&leader))
            .unwrap();
        assert_eq!(leader.ledger().current_height(), 2);

        // Follower pulls the encoded block range and imports it (validated).
        let exported = leader.export_peer_blocks(1, 100).unwrap();
        let outcome = follower.import_peer_blocks(&exported).unwrap();

        assert_eq!(outcome.applied, 2);
        assert_eq!(outcome.current_height, 2);
        assert_eq!(follower.latest_block_hash(), leader.latest_block_hash());
        assert_eq!(follower.ledger(), leader.ledger());

        // Re-importing the same range is idempotent (already-synced blocks skipped).
        let again = follower.import_peer_blocks(&exported).unwrap();
        assert_eq!(again.applied, 0);
        assert_eq!(again.current_height, 2);
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
    fn node_runner_status_replays_file_store() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        let genesis = genesis();
        let latest_hash;
        let latest_state_root;

        {
            let mut node =
                XriqNode::from_genesis(&genesis, FileChainStore::open(&path).unwrap()).unwrap();
            node.submit_transaction_with_canonical_hash(transaction(address("alice"), 0, 25, 2))
                .unwrap();
            let produced = node
                .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&node))
                .unwrap();
            latest_hash = produced.block_hash;
            latest_state_root = produced.block.header.state_root;
        }

        assert_eq!(
            run_node_command([
                "status",
                "--chain-file",
                path_text.as_str(),
                "--alice-balance",
                "100",
            ]),
            Ok(NodeRunnerOutput::Status(NodeStatus {
                warning: PRIVATE_DEVNET_RUNNER_WARNING,
                chain_id: "xriq-devnet".to_string(),
                current_height: 1,
                latest_block_hash: latest_hash,
                state_root: latest_state_root,
                pending_transactions: 0,
                stored_blocks: 1,
            }))
        );

        let output = run_node_command([
            "status",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap()
        .to_string();
        assert!(output.contains("warning=private-devnet-only-no-public-token"));
        assert!(output.contains("current_height=1"));
        assert!(output.contains("stored_blocks=1"));

        let chain_check = run_node_command([
            "chain-check",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();
        assert_eq!(
            chain_check,
            NodeRunnerOutput::ChainCheck(PrivateDevnetChainCheckStatus {
                verified: true,
                status: NodeStatus {
                    warning: PRIVATE_DEVNET_RUNNER_WARNING,
                    chain_id: "xriq-devnet".to_string(),
                    current_height: 1,
                    latest_block_hash: latest_hash,
                    state_root: latest_state_root,
                    pending_transactions: 0,
                    stored_blocks: 1,
                },
            })
        );
        let chain_check_json = run_node_command([
            "chain-check",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(chain_check_json.contains("\"command\": \"chain-check\""));
        assert!(chain_check_json.contains("\"verified\": true"));
        assert!(chain_check_json.contains("\"current_height\": 1"));
        assert!(chain_check_json.contains("\"state_root\":"));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_runner_produces_transfer_block_and_replays_file_store() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();

        let output = run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
        ])
        .unwrap();
        let produced = match output {
            NodeRunnerOutput::ProducedTransferBlock(produced) => produced,
            other => panic!("unexpected output: {other:?}"),
        };

        assert_eq!(produced.applied_transactions, 1);
        assert_eq!(produced.status.current_height, 1);
        assert_eq!(produced.status.latest_block_hash, produced.block_hash);
        assert_eq!(produced.status.pending_transactions, 0);
        assert_eq!(produced.status.stored_blocks, 1);

        let reloaded = XriqNode::from_genesis_replaying_store(
            &genesis(),
            FileChainStore::open(&path).unwrap(),
        )
        .unwrap();
        assert_eq!(reloaded.latest_block_hash(), produced.block_hash);
        assert_eq!(produced.status.state_root, node_state_root(&reloaded));
        assert_eq!(
            reloaded
                .ledger()
                .account(&address("alice"))
                .unwrap()
                .balance,
            XriqAmount::from_base_units(73)
        );
        assert_eq!(
            reloaded
                .ledger()
                .account(&address("bobbb"))
                .unwrap()
                .balance,
            XriqAmount::from_base_units(25)
        );

        let status_output = run_node_command([
            "status",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();
        assert_eq!(
            status_output,
            NodeRunnerOutput::Status(NodeStatus {
                warning: PRIVATE_DEVNET_RUNNER_WARNING,
                chain_id: "xriq-devnet".to_string(),
                current_height: 1,
                latest_block_hash: produced.block_hash,
                state_root: produced.status.state_root,
                pending_transactions: 0,
                stored_blocks: 1,
            })
        );

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_runner_produces_block_from_pending_file_and_compacts() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let submit_draft = [
            "warning=private-devnet-test-identity-only",
            "version=1",
            "chain_id=xriq-devnet",
            "from=xriqdev1alice00000000000",
            "to=xriqdev1bobbb00000000000",
            "amount=25",
            "fee=2",
            "nonce=0",
            "expires_at_height=100",
            "signature_bytes=48",
        ]
        .join("\n");
        let pending_detail = private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &submit_draft,
        )
        .unwrap();
        assert!(fs::read_to_string(&pending_path)
            .unwrap()
            .contains(&hash_hex(pending_detail.tx_hash)));

        let output = run_node_command([
            "produce-pending-block",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();
        let produced_json = output.to_string();
        assert!(produced_json.contains("\"command\": \"produce-pending-block\""));
        assert!(produced_json.contains("\"included_transaction_hashes\": ["));
        assert!(produced_json.contains(&hash_hex(pending_detail.tx_hash)));
        assert!(produced_json.contains("\"applied_transactions\": 1"));
        assert!(produced_json.contains("\"current_height\": 1"));
        assert!(produced_json.contains("\"pending_transactions\": 0"));
        assert_eq!(fs::read_to_string(&pending_path).unwrap(), "");

        let transaction_detail = private_devnet_file_transaction_detail_with_pending_file_data(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            pending_detail.tx_hash,
        )
        .unwrap();
        match transaction_detail {
            PrivateDevnetTransactionDetail::Confirmed(detail) => {
                assert_eq!(detail.block_height, 1);
                assert_eq!(detail.transaction_index, 0);
            }
            other => panic!("unexpected transaction detail: {other:?}"),
        }

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn node_runner_mempool_detail_reads_durable_pending_file() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let draft_path = path.with_extension("draft");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        write_wallet_draft(&draft_path, 25, 2, 0);
        let draft_body = fs::read_to_string(&draft_path).unwrap();
        let pending_detail = private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &draft_body,
        )
        .unwrap();

        let pending_json = run_node_command([
            "mempool-detail",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(pending_json.contains("\"command\": \"mempool-detail\""));
        assert!(pending_json.contains("\"pending_count\": 1"));
        assert!(pending_json.contains(&hash_hex(pending_detail.tx_hash)));
        assert!(pending_json.contains("\"amount_base_units\": \"25\""));
        assert!(pending_json.contains("\"fee_base_units\": \"2\""));

        let in_memory_json = run_node_command([
            "mempool-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(in_memory_json.contains("\"pending_count\": 0"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn node_environment_flag_is_fail_closed() {
        let path = temp_store_path();
        let pending = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending.to_string_lossy().to_string();

        // staging-devnet is accepted and the command runs normally.
        let staging = run_node_command([
            "preflight-transfer",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--environment",
            "staging-devnet",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(staging.contains("\"command\": \"preflight-transfer\""));

        // Production-class profiles are rejected before the command executes.
        let error = run_node_command([
            "status",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--environment",
            "production",
        ])
        .unwrap_err();
        assert!(matches!(error, NodeRunnerError::UnsupportedEnvironment(_)));

        // No flag still defaults to local and works.
        let default_ok = run_node_command([
            "status",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(default_ok.contains("\"command\": \"status\""));

        // The serve config parser shares the same fail-closed validation.
        let serve_error = parse_private_devnet_http_server_config(
            &[
                "--chain-file".to_string(),
                path_text.clone(),
                "--environment".to_string(),
                "mainnet".to_string(),
            ],
            false,
        )
        .unwrap_err();
        assert!(matches!(
            serve_error,
            NodeRunnerError::UnsupportedEnvironment(_)
        ));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending);
    }

    #[test]
    fn node_runner_replays_duplicate_pending_line_idempotently() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let draft_path = path.with_extension("draft");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        write_wallet_draft(&draft_path, 25, 2, 0);
        let draft_body = fs::read_to_string(&draft_path).unwrap();
        let pending_detail = private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &draft_body,
        )
        .unwrap();

        // Simulate a corrupt-on-restart pending file that contains the same
        // accepted transaction twice (for example from a crash mid-append).
        let single_line = fs::read_to_string(&pending_path).unwrap();
        assert_eq!(single_line.lines().count(), 1);
        append_pending_transaction_record(
            &pending_path,
            pending_detail.tx_hash,
            &pending_detail.transaction,
        )
        .unwrap();
        assert_eq!(
            fs::read_to_string(&pending_path).unwrap().lines().count(),
            2
        );

        // Startup replay must not brick on the duplicate; the transaction is
        // already in the mempool, so it stays a single pending entry.
        let pending_json = run_node_command([
            "mempool-detail",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(pending_json.contains("\"command\": \"mempool-detail\""));
        assert!(pending_json.contains("\"pending_count\": 1"));
        assert!(pending_json.contains(&hash_hex(pending_detail.tx_hash)));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn node_runner_quarantines_corrupt_pending_line_on_replay() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let draft_path = path.with_extension("draft");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        write_wallet_draft(&draft_path, 25, 2, 0);
        let draft_body = fs::read_to_string(&draft_path).unwrap();
        let pending_detail = private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &draft_body,
        )
        .unwrap();

        // Append a corrupt (unparseable) pending line, as could happen from a
        // truncated write or external tampering.
        let corrupt_line = "this-is-not-a-valid-pending-record";
        {
            use std::io::Write as _;
            let mut file = fs::OpenOptions::new()
                .append(true)
                .open(&pending_path)
                .unwrap();
            writeln!(file, "{corrupt_line}").unwrap();
        }

        // Startup replay must recover instead of bricking on the corrupt line.
        let pending_json = run_node_command([
            "mempool-detail",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(pending_json.contains("\"command\": \"mempool-detail\""));
        assert!(pending_json.contains("\"pending_count\": 1"));
        assert!(pending_json.contains(&hash_hex(pending_detail.tx_hash)));

        // The corrupt line is self-healed out of the live pending file but
        // preserved in the quarantine sidecar (no silent loss).
        let healed_pending = fs::read_to_string(&pending_path).unwrap();
        assert!(!healed_pending.contains(corrupt_line));
        assert!(healed_pending.contains(&hash_hex(pending_detail.tx_hash)));

        let quarantine_path = {
            let mut name = pending_path.clone().into_os_string();
            name.push(".quarantine");
            PathBuf::from(name)
        };
        let quarantined = fs::read_to_string(&quarantine_path).unwrap();
        assert!(quarantined.contains(PENDING_QUARANTINE_MARKER));
        assert!(quarantined.contains(corrupt_line));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
        let _ = fs::remove_file(quarantine_path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn node_runner_peer_blocks_export_serves_validated_blocks() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();

        run_node_command([
            "preflight-transfer",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();

        let json = run_node_command([
            "peer-blocks-export",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from-height",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(json.contains("\"command\": \"peer-blocks-export\""));
        assert!(json.contains("\"from_height\": 1"));
        assert!(json.contains("\"current_height\": 1"));

        // Extract blocks_hex and decode it back into validated-importable blocks.
        let marker = "\"blocks_hex\": \"";
        let start = json.find(marker).unwrap() + marker.len();
        let end = json[start..].find('"').unwrap() + start;
        let hex = &json[start..end];
        assert!(!hex.is_empty());
        let bytes = parse_hex_bytes(hex).unwrap();
        let blocks = xriq_storage::decode_peer_blocks(&bytes).unwrap();
        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0].header.height, 1);

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn peer_sync_response_parser_reads_export_json() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();

        run_node_command([
            "preflight-transfer",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();

        let export = run_node_command([
            "peer-blocks-export",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from-height",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        // The follower parses exactly what the peer server produces.
        let (current_height, bytes) = parse_peer_blocks_response(&export).unwrap();
        assert_eq!(current_height, 1);
        let blocks = xriq_storage::decode_peer_blocks(&bytes).unwrap();
        assert_eq!(blocks.len(), 1);
        assert_eq!(blocks[0].header.height, 1);

        // Malformed peer bodies surface as peer-sync errors, not panics.
        assert!(matches!(
            parse_peer_blocks_response("{}"),
            Err(NodeRunnerError::PeerSyncError(_))
        ));
        assert!(matches!(
            parse_peer_blocks_response("{\n  \"current_height\": 1\n}"),
            Err(NodeRunnerError::PeerSyncError(_))
        ));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    // Serve exactly `count` sequential requests against a chain file over the
    // real private-devnet HTTP handler, then return. The follower makes a fixed
    // number of connections per sync (one handshake + one per pull round, plus
    // one discovery fetch per seed when --discover is used), so `count` must
    // match exactly or `join()` would block on an extra accept.
    fn serve_peer_requests(chain_file: String, count: usize) -> (u16, std::thread::JoinHandle<()>) {
        serve_peer_requests_full(chain_file, count, None, None, false)
    }

    fn serve_peer_requests_advertising(
        chain_file: String,
        count: usize,
        peers_file: Option<String>,
    ) -> (u16, std::thread::JoinHandle<()>) {
        serve_peer_requests_full(chain_file, count, peers_file, None, false)
    }

    fn serve_peer_requests_full(
        chain_file: String,
        count: usize,
        peers_file: Option<String>,
        node_seed: Option<String>,
        testnet: bool,
    ) -> (u16, std::thread::JoinHandle<()>) {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        let config = PrivateDevnetHttpServerConfig {
            bind: format!("127.0.0.1:{port}"),
            chain_file,
            pending_file: None,
            snapshot_root: None,
            alice_balance: Some(XriqAmount::from_base_units(100)),
            allow_transaction_submission: false,
            peers_file,
            node_seed,
            testnet,
        };
        let handle = std::thread::spawn(move || {
            for _ in 0..count {
                let Ok((mut stream, _)) = listener.accept() else {
                    break;
                };
                let mut buffer = [0_u8; 8192];
                let bytes_read = stream.read(&mut buffer).unwrap_or(0);
                let request = String::from_utf8_lossy(&buffer[..bytes_read]).to_string();
                let response = private_devnet_http_response_from_request(&config, &request);
                let _ = stream.write_all(response.to_http_response().as_bytes());
                let _ = stream.flush();
            }
        });
        (port, handle)
    }

    // Bind, then immediately drop the listener to obtain a loopback port that is
    // guaranteed free (so a connect there is refused rather than hanging).
    fn unreachable_loopback_peer() -> String {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();
        drop(listener);
        format!("http://127.0.0.1:{port}")
    }

    #[test]
    fn peer_sync_follower_pulls_blocks_from_leader_over_tcp() {
        // Leader: a chain file holding one validated block, served by the real
        // private-devnet HTTP handler over a loopback socket.
        let leader_path = temp_store_path();
        let leader_pending = leader_path.with_extension("pending");
        let leader_text = leader_path.to_string_lossy().to_string();
        let leader_pending_text = leader_pending.to_string_lossy().to_string();

        run_node_command([
            "preflight-transfer",
            "--chain-file",
            leader_text.as_str(),
            "--pending-file",
            leader_pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();

        // Follower: a distinct, initially-empty chain file at the shared genesis.
        let follower_path = temp_store_path();
        let follower_text = follower_path.to_string_lossy().to_string();

        // Round 1 — the follower handshakes, pulls the leader's block, and
        // commits it to its own chain file (one handshake + one pull = 2 reqs).
        let (port, handle) = serve_peer_requests(leader_text.clone(), 2);
        let synced = run_node_command([
            "peer-sync",
            "--chain-file",
            follower_text.as_str(),
            "--peer",
            format!("http://127.0.0.1:{port}").as_str(),
            "--alice-balance",
            "100",
            "--max-rounds",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        handle.join().unwrap();
        assert!(synced.contains("\"command\": \"peer-sync\""));
        assert!(synced.contains("\"applied\": 1"));
        assert!(synced.contains("\"current_height\": 1"));
        assert!(synced.contains("\"peer_current_height\": 1"));

        // Round 2 — re-opening the persisted follower file shows it is caught up:
        // the next pull applies nothing (proving the block reached disk).
        let (port, handle) = serve_peer_requests(leader_text.clone(), 2);
        let resynced = run_node_command([
            "peer-sync",
            "--chain-file",
            follower_text.as_str(),
            "--peer",
            format!("http://127.0.0.1:{port}").as_str(),
            "--alice-balance",
            "100",
            "--max-rounds",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        handle.join().unwrap();
        assert!(resynced.contains("\"applied\": 0"));
        assert!(resynced.contains("\"current_height\": 1"));

        // Bad peer address is a clean error, not a panic (single --peer is strict).
        let unreachable = run_node_command([
            "peer-sync",
            "--chain-file",
            follower_text.as_str(),
            "--peer",
            "not-a-url",
            "--alice-balance",
            "100",
            "--max-rounds",
            "1",
            "--format",
            "json",
        ]);
        assert!(matches!(
            unreachable,
            Err(NodeRunnerError::PeerSyncError(_))
        ));

        let _ = fs::remove_file(leader_path);
        let _ = fs::remove_file(leader_pending);
        let _ = fs::remove_file(follower_path);
    }

    #[test]
    fn peer_identity_endpoint_reports_network_and_protocol() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();

        run_node_command([
            "preflight-transfer",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();

        // Without a node seed, node_id is null.
        let anon_config = PrivateDevnetHttpServerConfig {
            bind: "127.0.0.1:8787".to_string(),
            chain_file: path_text,
            pending_file: None,
            snapshot_root: None,
            alice_balance: Some(XriqAmount::from_base_units(100)),
            allow_transaction_submission: false,
            peers_file: None,
            node_seed: None,
            testnet: false,
        };
        let anon = private_devnet_http_response(&anon_config, "GET", "/v1/peer/identity");
        assert_eq!(anon.status_code, 200);
        assert!(anon.body.contains("\"node_id\": null"));
        assert!(parse_peer_identity_response(&anon.body)
            .unwrap()
            .node_id
            .is_none());

        // With a node seed, node_id is the derived, stable id.
        let config = PrivateDevnetHttpServerConfig {
            node_seed: Some("node-alpha".to_string()),
            ..anon_config.clone()
        };
        let identity = private_devnet_http_response(&config, "GET", "/v1/peer/identity");
        assert_eq!(identity.status_code, 200);
        assert!(identity.body.contains("\"command\": \"peer-identity\""));
        assert!(identity.body.contains("\"network\": \"xriq-devnet\""));
        assert!(identity
            .body
            .contains("\"protocol\": \"xriq-peer-blocks-v1\""));
        assert!(identity.body.contains("\"current_height\": 1"));

        // The follower's parser reads exactly this shape and accepts it (a devnet
        // follower talking to a devnet peer).
        let parsed = parse_peer_identity_response(&identity.body).unwrap();
        assert!(peer_compatibility_error(&parsed, "xriq-devnet").is_none());
        assert_eq!(
            parsed.node_id.as_deref(),
            Some(derive_node_id("node-alpha").as_str())
        );

        // A peer on a different network or protocol is rejected by the handshake.
        let wrong_network = parse_peer_identity_response(
            "{\n  \"network\": \"other-net\",\n  \"protocol\": \"xriq-peer-blocks-v1\",\n  \"current_height\": 1\n}",
        )
        .unwrap();
        assert!(peer_compatibility_error(&wrong_network, "xriq-devnet").is_some());
        // A testnet peer is rejected by a devnet follower (network isolation).
        assert!(peer_compatibility_error(&parsed, "xriq-testnet").is_some());
        let wrong_protocol = parse_peer_identity_response(
            "{\n  \"network\": \"xriq-devnet\",\n  \"protocol\": \"xriq-peer-blocks-v9\",\n  \"current_height\": 1\n}",
        )
        .unwrap();
        assert!(peer_compatibility_error(&wrong_protocol, "xriq-devnet").is_some());

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn derive_node_id_is_stable_and_seed_specific() {
        let alpha = derive_node_id("alpha");
        assert_eq!(alpha, derive_node_id("alpha"));
        assert_ne!(alpha, derive_node_id("beta"));
        assert!(alpha.starts_with("xriqnode1"));
        assert_eq!(alpha.len(), "xriqnode1".len() + 32);
    }

    #[test]
    fn peer_sync_skips_self_by_node_id() {
        // Leader B holds the block and has a distinct node id.
        let leader_path = temp_store_path();
        let leader_pending = leader_path.with_extension("pending");
        let leader_text = leader_path.to_string_lossy().to_string();
        let leader_pending_text = leader_pending.to_string_lossy().to_string();

        run_node_command([
            "preflight-transfer",
            "--chain-file",
            leader_text.as_str(),
            "--pending-file",
            leader_pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();
        let (leader_port, leader_handle) = serve_peer_requests_full(
            leader_text.clone(),
            2,
            None,
            Some("node-b".to_string()),
            false,
        );

        // Self peer A shares the follower's node seed, so it reports our id and
        // is skipped after the handshake (one request, no pull).
        let self_chain = temp_store_path();
        let self_chain_text = self_chain.to_string_lossy().to_string();
        let (self_port, self_handle) =
            serve_peer_requests_full(self_chain_text, 1, None, Some("me".to_string()), false);

        let peers_file = temp_store_path();
        let peers_file_text = peers_file.to_string_lossy().to_string();
        fs::write(
            &peers_file,
            format!("http://127.0.0.1:{self_port}\nhttp://127.0.0.1:{leader_port}\n"),
        )
        .unwrap();

        let follower_path = temp_store_path();
        let follower_text = follower_path.to_string_lossy().to_string();

        let synced = run_node_command([
            "peer-sync",
            "--chain-file",
            follower_text.as_str(),
            "--peers-file",
            peers_file_text.as_str(),
            "--node-seed",
            "me",
            "--alice-balance",
            "100",
            "--max-rounds",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        self_handle.join().unwrap();
        leader_handle.join().unwrap();

        assert!(synced.contains("\"peers_total\": 2"));
        assert!(synced.contains("\"peers_skipped_self\": 1"));
        assert!(synced.contains("\"peers_reachable\": 1"));
        assert!(synced.contains("\"applied\": 1"));
        assert!(synced.contains("\"current_height\": 1"));
        assert!(synced.contains("(self)"));
        // The follower advertises its own derived id at the top level.
        assert!(synced.contains(&format!(
            "\"node_id\": {}",
            json_string(&derive_node_id("me"))
        )));

        let _ = fs::remove_file(leader_path);
        let _ = fs::remove_file(leader_pending);
        let _ = fs::remove_file(self_chain);
        let _ = fs::remove_file(peers_file);
        let _ = fs::remove_file(follower_path);
    }

    #[test]
    fn parse_peers_file_reads_urls_and_skips_comments() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        fs::write(
            &path,
            "# leader\nhttp://127.0.0.1:7001\n\n  http://127.0.0.1:7002  \n# trailing comment\n",
        )
        .unwrap();
        let peers = parse_peers_file(&path_text).unwrap();
        assert_eq!(
            peers,
            vec![
                "http://127.0.0.1:7001".to_string(),
                "http://127.0.0.1:7002".to_string(),
            ]
        );

        // A file with only comments/blank lines is an error, not an empty sync.
        fs::write(&path, "# only comments\n\n").unwrap();
        assert!(matches!(
            parse_peers_file(&path_text),
            Err(NodeRunnerError::PeerSyncError(_))
        ));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn peer_sync_from_peers_file_skips_unreachable_peer() {
        // Leader with one validated block, plus an unreachable peer listed first.
        let leader_path = temp_store_path();
        let leader_pending = leader_path.with_extension("pending");
        let leader_text = leader_path.to_string_lossy().to_string();
        let leader_pending_text = leader_pending.to_string_lossy().to_string();

        run_node_command([
            "preflight-transfer",
            "--chain-file",
            leader_text.as_str(),
            "--pending-file",
            leader_pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();

        let dead_peer = unreachable_loopback_peer();
        let (port, handle) = serve_peer_requests(leader_text.clone(), 2);

        let peers_file = temp_store_path();
        let peers_file_text = peers_file.to_string_lossy().to_string();
        fs::write(
            &peers_file,
            format!("{dead_peer}\nhttp://127.0.0.1:{port}\n"),
        )
        .unwrap();

        let follower_path = temp_store_path();
        let follower_text = follower_path.to_string_lossy().to_string();

        let synced = run_node_command([
            "peer-sync",
            "--chain-file",
            follower_text.as_str(),
            "--peers-file",
            peers_file_text.as_str(),
            "--alice-balance",
            "100",
            "--max-rounds",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        handle.join().unwrap();

        // The follower converges via the one reachable peer and reports the skip.
        assert!(synced.contains("\"peers_total\": 2"));
        assert!(synced.contains("\"peers_reachable\": 1"));
        assert!(synced.contains("\"applied\": 1"));
        assert!(synced.contains("\"current_height\": 1"));
        assert!(synced.contains("\"status\": \"ok\""));
        assert!(synced.contains("\"status\": \"skipped\""));

        let _ = fs::remove_file(leader_path);
        let _ = fs::remove_file(leader_pending);
        let _ = fs::remove_file(follower_path);
        let _ = fs::remove_file(peers_file);
    }

    #[test]
    fn parse_advertised_peers_extracts_urls() {
        let body = "{\n  \"command\": \"peer-peers\",\n  \"network\": \"xriq-devnet\",\n  \"peers\": [\n    \"http://127.0.0.1:7001\",\n    \"http://127.0.0.1:7002\"\n  ]\n}";
        assert_eq!(
            parse_advertised_peers(body),
            vec![
                "http://127.0.0.1:7001".to_string(),
                "http://127.0.0.1:7002".to_string(),
            ]
        );
        let empty = "{\n  \"command\": \"peer-peers\",\n  \"network\": \"xriq-devnet\",\n  \"peers\": []\n}";
        assert!(parse_advertised_peers(empty).is_empty());
        assert!(parse_advertised_peers("{}").is_empty());
    }

    #[test]
    fn peer_peers_endpoint_advertises_configured_peers() {
        let chain = temp_store_path();
        let chain_text = chain.to_string_lossy().to_string();
        let peers_path = temp_store_path();
        let peers_text = peers_path.to_string_lossy().to_string();
        fs::write(
            &peers_path,
            "# neighbours\nhttp://127.0.0.1:7101\nhttp://127.0.0.1:7102\n",
        )
        .unwrap();

        let config = PrivateDevnetHttpServerConfig {
            bind: "127.0.0.1:8787".to_string(),
            chain_file: chain_text,
            pending_file: None,
            snapshot_root: None,
            alice_balance: Some(XriqAmount::from_base_units(100)),
            allow_transaction_submission: false,
            peers_file: Some(peers_text),
            node_seed: None,
            testnet: false,
        };
        let advertised = private_devnet_http_response(&config, "GET", "/v1/peer/peers");
        assert_eq!(advertised.status_code, 200);
        assert!(advertised.body.contains("\"command\": \"peer-peers\""));
        assert_eq!(
            parse_advertised_peers(&advertised.body),
            vec![
                "http://127.0.0.1:7101".to_string(),
                "http://127.0.0.1:7102".to_string(),
            ]
        );

        // With no advertised peers file the endpoint returns an empty array.
        let bare = PrivateDevnetHttpServerConfig {
            peers_file: None,
            ..config.clone()
        };
        let empty = private_devnet_http_response(&bare, "GET", "/v1/peer/peers");
        assert_eq!(empty.status_code, 200);
        assert!(empty.body.contains("\"peers\": []"));

        let _ = fs::remove_file(chain);
        let _ = fs::remove_file(peers_path);
    }

    #[test]
    fn peer_sync_discovers_and_syncs_from_learned_peer() {
        // Topology: the follower is given only seed A (an empty node). A
        // advertises node B, which actually holds the block. With --discover the
        // follower learns B from A and syncs the block from B.
        let leader_path = temp_store_path();
        let leader_pending = leader_path.with_extension("pending");
        let leader_text = leader_path.to_string_lossy().to_string();
        let leader_pending_text = leader_pending.to_string_lossy().to_string();

        run_node_command([
            "preflight-transfer",
            "--chain-file",
            leader_text.as_str(),
            "--pending-file",
            leader_pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();

        // B (leader) holds the block: one handshake + one pull = 2 requests.
        let (leader_port, leader_handle) = serve_peer_requests(leader_text.clone(), 2);

        // A (seed) is an empty node that advertises B. The follower makes three
        // requests to A: one discovery fetch, one handshake, one (empty) pull.
        let seed_chain = temp_store_path();
        let seed_chain_text = seed_chain.to_string_lossy().to_string();
        let seed_peers = temp_store_path();
        let seed_peers_text = seed_peers.to_string_lossy().to_string();
        fs::write(&seed_peers, format!("http://127.0.0.1:{leader_port}\n")).unwrap();
        let (seed_port, seed_handle) =
            serve_peer_requests_advertising(seed_chain_text, 3, Some(seed_peers_text));

        let follower_path = temp_store_path();
        let follower_text = follower_path.to_string_lossy().to_string();

        let synced = run_node_command([
            "peer-sync",
            "--chain-file",
            follower_text.as_str(),
            "--peer",
            format!("http://127.0.0.1:{seed_port}").as_str(),
            "--discover",
            "64",
            "--alice-balance",
            "100",
            "--max-rounds",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        seed_handle.join().unwrap();
        leader_handle.join().unwrap();

        // The follower learned exactly one new peer (B) and synced the block.
        assert!(synced.contains("\"peers_total\": 2"));
        assert!(synced.contains("\"peers_discovered\": 1"));
        assert!(synced.contains("\"peers_reachable\": 2"));
        assert!(synced.contains("\"applied\": 1"));
        assert!(synced.contains("\"current_height\": 1"));

        let _ = fs::remove_file(leader_path);
        let _ = fs::remove_file(leader_pending);
        let _ = fs::remove_file(seed_chain);
        let _ = fs::remove_file(seed_peers);
        let _ = fs::remove_file(follower_path);
    }

    #[test]
    fn testnet_genesis_command_emits_reproducible_spec() {
        let json = run_node_command(["testnet-genesis", "--format", "json"])
            .unwrap()
            .to_string();
        assert!(json.contains("\"command\": \"testnet-genesis\""));
        assert!(json.contains("\"chain_id\": \"xriq-testnet\""));
        assert!(json.contains("\"address\": \"xriqdev1testnetfaucet00000000\""));
        assert!(json.contains("\"balance_base_units\": \"1000000000000\""));
        assert!(json.contains("TEST-ONLY"));
        // Golden fingerprint: independent nodes must reproduce this exact hash.
        // If this assertion fails, the testnet genesis spec changed (a hard fork).
        assert!(json.contains(
            "\"genesis_spec_hash\": \"af01fa096c41538735cae46a6f9a7cb052bb198b1dd33316f905e46ec7ad1580\""
        ));

        // The fingerprint is deterministic and distinct from the devnet genesis.
        let testnet = GenesisConfig::public_testnet();
        assert_eq!(
            genesis_spec_hash(&testnet),
            genesis_spec_hash(&GenesisConfig::public_testnet())
        );
        assert_ne!(
            genesis_spec_hash(&testnet),
            genesis_spec_hash(&GenesisConfig::private_devnet())
        );
    }

    #[test]
    fn peer_sync_testnet_nodes_sync_over_tcp() {
        // Leader: a testnet chain holding one block produced by the faucet.
        let leader_path = temp_store_path();
        let leader_text = leader_path.to_string_lossy().to_string();
        run_node_command([
            "faucet-dispense",
            "--chain-file",
            leader_text.as_str(),
            "--to",
            "xriqdev1recipient00000000000",
            "--format",
            "json",
        ])
        .unwrap();

        // Served on the testnet genesis (testnet=true → peer routes use --network testnet).
        let (port, handle) = serve_peer_requests_full(leader_text.clone(), 2, None, None, true);

        let follower_path = temp_store_path();
        let follower_text = follower_path.to_string_lossy().to_string();
        let synced = run_node_command([
            "peer-sync",
            "--chain-file",
            follower_text.as_str(),
            "--network",
            "testnet",
            "--peer",
            format!("http://127.0.0.1:{port}").as_str(),
            "--max-rounds",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        handle.join().unwrap();

        assert!(synced.contains("\"network\": \"xriq-testnet\""));
        assert!(synced.contains("\"applied\": 1"));
        assert!(synced.contains("\"peers_reachable\": 1"));
        assert!(synced.contains("\"current_height\": 1"));

        let _ = fs::remove_file(leader_path);
        let _ = fs::remove_file(follower_path);
    }

    #[test]
    fn peer_sync_rejects_cross_network_peer() {
        // A testnet leader with one faucet block.
        let leader_path = temp_store_path();
        let leader_text = leader_path.to_string_lossy().to_string();
        run_node_command([
            "faucet-dispense",
            "--chain-file",
            leader_text.as_str(),
            "--to",
            "xriqdev1recipient00000000000",
            "--format",
            "json",
        ])
        .unwrap();
        // Served as testnet; the devnet follower only reaches the handshake.
        let (port, handle) = serve_peer_requests_full(leader_text.clone(), 1, None, None, true);

        let follower_path = temp_store_path();
        let follower_text = follower_path.to_string_lossy().to_string();
        // Follower defaults to devnet; the testnet peer is a network mismatch.
        let rejected = run_node_command([
            "peer-sync",
            "--chain-file",
            follower_text.as_str(),
            "--peer",
            format!("http://127.0.0.1:{port}").as_str(),
            "--max-rounds",
            "1",
            "--format",
            "json",
        ]);
        handle.join().unwrap();
        assert!(matches!(rejected, Err(NodeRunnerError::PeerSyncError(_))));

        let _ = fs::remove_file(leader_path);
        let _ = fs::remove_file(follower_path);
    }

    #[test]
    fn faucet_dispenses_valueless_units_and_confirms() {
        let chain = temp_store_path();
        let chain_text = chain.to_string_lossy().to_string();
        let recipient = "xriqdev1recipient00000000000";

        let out1 = run_node_command([
            "faucet-dispense",
            "--chain-file",
            chain_text.as_str(),
            "--to",
            recipient,
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(out1.contains("\"command\": \"faucet-dispense\""));
        assert!(out1.contains("\"chain_id\": \"xriq-testnet\""));
        assert!(out1.contains("TEST-ONLY"));
        assert!(out1.contains("\"amount_base_units\": \"1000\""));
        assert!(out1.contains("\"fee_base_units\": \"2\""));
        assert!(out1.contains("\"block_height\": 1"));
        assert!(out1.contains("\"recipient_balance_base_units\": \"1000\""));
        // The faucet balance dropped from the genesis allocation.
        assert!(out1.contains("\"faucet_balance_base_units\": \"999999998998\""));

        // A second dispense to the same recipient increments the faucet nonce,
        // produces the next block, and tops the recipient up again.
        let out2 = run_node_command([
            "faucet-dispense",
            "--chain-file",
            chain_text.as_str(),
            "--to",
            recipient,
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(out2.contains("\"block_height\": 2"));
        assert!(out2.contains("\"recipient_balance_base_units\": \"2000\""));

        // The chain persisted: re-opening funds a new recipient at height 3.
        let out3 = run_node_command([
            "faucet-dispense",
            "--chain-file",
            chain_text.as_str(),
            "--to",
            "xriqdev1recipient00000000001",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(out3.contains("\"block_height\": 3"));
        assert!(out3.contains("\"recipient_balance_base_units\": \"1000\""));

        let _ = fs::remove_file(chain);
    }

    #[test]
    fn faucet_refuses_over_cap_and_when_exhausted() {
        let chain = temp_store_path();
        let chain_text = chain.to_string_lossy().to_string();
        let recipient = "xriqdev1recipient00000000000";

        // First dispense under a low cap succeeds.
        run_node_command([
            "faucet-dispense",
            "--chain-file",
            chain_text.as_str(),
            "--to",
            recipient,
            "--max-balance",
            "500",
            "--format",
            "json",
        ])
        .unwrap();
        // The recipient now holds 1000 >= the 500 cap, so a repeat is refused.
        let refused = run_node_command([
            "faucet-dispense",
            "--chain-file",
            chain_text.as_str(),
            "--to",
            recipient,
            "--max-balance",
            "500",
            "--format",
            "json",
        ]);
        assert!(matches!(refused, Err(NodeRunnerError::FaucetRefused(_))));

        // Requesting more than the faucet holds is also refused (exhaustion).
        let fresh = temp_store_path();
        let fresh_text = fresh.to_string_lossy().to_string();
        let too_big = run_node_command([
            "faucet-dispense",
            "--chain-file",
            fresh_text.as_str(),
            "--to",
            "xriqdev1recipient00000000001",
            "--amount",
            "2000000000000",
            "--format",
            "json",
        ]);
        assert!(matches!(too_big, Err(NodeRunnerError::FaucetRefused(_))));

        let _ = fs::remove_file(chain);
        let _ = fs::remove_file(fresh);
    }

    #[test]
    fn node_runner_preflight_transfer_submits_produces_and_confirms() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();

        let output = run_node_command([
            "preflight-transfer",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();
        let json = output.to_string();
        assert!(json.contains("\"command\": \"preflight-transfer\""));
        assert!(json.contains("\"preflight_balance_base_units\": \"100\""));
        assert!(json.contains("\"preflight_nonce\": 0"));
        assert!(json.contains("\"transaction_hash\":"));
        assert!(json.contains("\"confirmed_block_height\": 1"));
        assert!(json.contains("\"confirmed_transaction_index\": 0"));
        assert!(json.contains("\"final_balance_base_units\": \"73\""));
        assert!(json.contains("\"final_nonce\": 1"));
        assert!(json.contains("\"current_height\": 1"));
        assert!(json.contains("\"pending_transactions\": 0"));
        assert_eq!(fs::read_to_string(&pending_path).unwrap(), "");

        let detail = private_devnet_file_transaction_detail_data(
            &path_text,
            Option::<&str>::None,
            Some(XriqAmount::from_base_units(100)),
            hash_hex_from_json_field(&json, "transaction_hash"),
        )
        .unwrap();
        assert!(matches!(
            detail,
            PrivateDevnetTransactionDetail::Confirmed(_)
        ));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn node_runner_snapshot_export_import_restores_chain_and_pending_files() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let imported_path = path.with_extension("imported.bin");
        let imported_pending_path = path.with_extension("imported.pending");
        let snapshot_root = temp_snapshot_dir();
        let snapshot_dir = snapshot_root.join("snapshot-a");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let imported_text = imported_path.to_string_lossy().to_string();
        let imported_pending_text = imported_pending_path.to_string_lossy().to_string();
        let snapshot_root_text = snapshot_root.to_string_lossy().to_string();
        let snapshot_text = snapshot_dir.to_string_lossy().to_string();

        run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
        ])
        .unwrap();
        let pending_body = [
            "warning=private-devnet-test-identity-only",
            "version=1",
            "chain_id=xriq-devnet",
            "from=xriqdev1alice00000000000",
            "to=xriqdev1bobbb00000000000",
            "amount=10",
            "fee=2",
            "nonce=1",
            "expires_at_height=100",
            "signature_bytes=48",
        ]
        .join("\n");
        private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            &pending_body,
        )
        .unwrap();

        let export_json = run_node_command([
            "snapshot-export",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--snapshot-dir",
            snapshot_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(export_json.contains("\"command\": \"snapshot-export\""));
        assert!(export_json.contains("\"snapshot_format_version\":"));
        assert!(export_json.contains("\"current_height\": 1"));
        assert!(export_json.contains("\"pending_transactions\": 1"));
        assert!(snapshot_dir.join(SNAPSHOT_CHAIN_FILE).exists());
        assert!(snapshot_dir.join(SNAPSHOT_PENDING_FILE).exists());
        let manifest = fs::read_to_string(snapshot_dir.join(SNAPSHOT_MANIFEST_FILE)).unwrap();
        assert!(manifest.contains("\"snapshot_format_version\":"));
        assert!(manifest.contains("\"pending_file\": \"pending.tsv\""));

        let snapshot_list = run_node_command([
            "snapshot-list",
            "--snapshot-root",
            snapshot_root_text.as_str(),
            "--limit",
            "5",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(snapshot_list.contains("\"command\": \"snapshot-list\""));
        assert!(snapshot_list.contains("\"snapshot_count\": 1"));
        assert!(snapshot_list.contains("\"snapshot_name\": \"snapshot-a\""));
        assert!(snapshot_list.contains("\"current_height\": 1"));
        assert!(snapshot_list.contains("\"pending_transactions\": 1"));

        let snapshot_latest = run_node_command([
            "snapshot-latest",
            "--snapshot-root",
            snapshot_root_text.as_str(),
        ])
        .unwrap()
        .to_string();
        assert!(snapshot_latest.contains("snapshot snapshot-a"));
        assert!(snapshot_latest.contains("current_height=1"));
        assert!(snapshot_latest.contains("pending_transactions=1"));

        let snapshot_latest_json = run_node_command([
            "snapshot-latest",
            "--snapshot-root",
            snapshot_root_text.as_str(),
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(snapshot_latest_json.contains("\"command\": \"snapshot-latest\""));
        assert!(snapshot_latest_json.contains("\"snapshot_name\": \"snapshot-a\""));
        assert!(snapshot_latest_json.contains("\"current_height\": 1"));
        assert!(snapshot_latest_json.contains("\"pending_transactions\": 1"));

        let snapshot_latest_check = run_node_command([
            "snapshot-latest-check",
            "--snapshot-root",
            snapshot_root_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap()
        .to_string();
        assert!(snapshot_latest_check.contains("snapshot check snapshot-a"));
        assert!(snapshot_latest_check.contains("verified=true"));
        assert!(snapshot_latest_check.contains("mismatches=none"));

        let snapshot_latest_check_json = run_node_command([
            "snapshot-latest-check",
            "--snapshot-root",
            snapshot_root_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(snapshot_latest_check_json.contains("\"command\": \"snapshot-latest-check\""));
        assert!(snapshot_latest_check_json.contains("\"verified\": true"));
        assert!(snapshot_latest_check_json.contains("\"snapshot_name\": \"snapshot-a\""));
        assert!(snapshot_latest_check_json.contains("\"replayed_status\": {"));

        let snapshot_detail =
            run_node_command(["snapshot-detail", "--snapshot-dir", snapshot_text.as_str()])
                .unwrap()
                .to_string();
        assert!(snapshot_detail.contains("snapshot snapshot-a"));
        assert!(snapshot_detail.contains("current_height=1"));
        assert!(snapshot_detail.contains("pending_transactions=1"));

        let snapshot_detail_json = run_node_command([
            "snapshot-detail",
            "--snapshot-dir",
            snapshot_text.as_str(),
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(snapshot_detail_json.contains("\"command\": \"snapshot-detail\""));
        assert!(snapshot_detail_json.contains("\"snapshot_name\": \"snapshot-a\""));
        assert!(snapshot_detail_json.contains("\"current_height\": 1"));
        assert!(snapshot_detail_json.contains("\"pending_transactions\": 1"));

        let snapshot_check = run_node_command([
            "snapshot-check",
            "--snapshot-dir",
            snapshot_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap()
        .to_string();
        assert!(snapshot_check.contains("snapshot check snapshot-a"));
        assert!(snapshot_check.contains("verified=true"));
        assert!(snapshot_check.contains("mismatches=none"));

        let snapshot_check_json = run_node_command([
            "snapshot-check",
            "--snapshot-dir",
            snapshot_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(snapshot_check_json.contains("\"command\": \"snapshot-check\""));
        assert!(snapshot_check_json.contains("\"verified\": true"));
        assert!(snapshot_check_json.contains("\"mismatches\": ["));
        assert!(snapshot_check_json.contains("\"snapshot_name\": \"snapshot-a\""));
        assert!(snapshot_check_json.contains("\"replayed_status\": {"));

        let import_json = run_node_command([
            "snapshot-import",
            "--snapshot-dir",
            snapshot_text.as_str(),
            "--chain-file",
            imported_text.as_str(),
            "--pending-file",
            imported_pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(import_json.contains("\"command\": \"snapshot-import\""));
        assert!(import_json.contains("\"current_height\": 1"));
        assert!(import_json.contains("\"pending_transactions\": 1"));

        let imported_chain_check = run_node_command([
            "chain-check",
            "--chain-file",
            imported_text.as_str(),
            "--pending-file",
            imported_pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(imported_chain_check.contains("\"command\": \"chain-check\""));
        assert!(imported_chain_check.contains("\"verified\": true"));
        assert!(imported_chain_check.contains("\"current_height\": 1"));
        assert!(imported_chain_check.contains("\"pending_transactions\": 1"));

        let imported_mempool = run_node_command([
            "mempool-detail",
            "--chain-file",
            imported_text.as_str(),
            "--pending-file",
            imported_pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(imported_mempool.contains("\"pending_count\": 1"));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
        let _ = fs::remove_file(imported_path);
        let _ = fs::remove_file(imported_pending_path);
        let _ = fs::remove_dir_all(snapshot_root);
    }

    #[test]
    fn node_runner_snapshot_latest_rejects_empty_snapshot_root() {
        let snapshot_root = temp_snapshot_dir();
        let snapshot_root_text = snapshot_root.to_string_lossy().to_string();
        fs::create_dir_all(&snapshot_root).unwrap();

        let error = run_node_command([
            "snapshot-latest",
            "--snapshot-root",
            snapshot_root_text.as_str(),
        ])
        .unwrap_err();
        assert!(matches!(error, NodeRunnerError::SnapshotNotFound(_)));

        let error = run_node_command([
            "snapshot-latest-check",
            "--snapshot-root",
            snapshot_root_text.as_str(),
        ])
        .unwrap_err();
        assert!(matches!(error, NodeRunnerError::SnapshotNotFound(_)));

        let _ = fs::remove_dir_all(snapshot_root);
    }

    #[test]
    fn node_runner_snapshot_import_rejects_existing_chain_target() {
        let path = temp_store_path();
        let imported_path = path.with_extension("existing.bin");
        let snapshot_dir = temp_snapshot_dir();
        let path_text = path.to_string_lossy().to_string();
        let imported_text = imported_path.to_string_lossy().to_string();
        let snapshot_text = snapshot_dir.to_string_lossy().to_string();

        run_node_command([
            "snapshot-export",
            "--chain-file",
            path_text.as_str(),
            "--snapshot-dir",
            snapshot_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();
        fs::write(&imported_path, "already here").unwrap();

        let error = run_node_command([
            "snapshot-import",
            "--snapshot-dir",
            snapshot_text.as_str(),
            "--chain-file",
            imported_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap_err();
        assert!(matches!(error, NodeRunnerError::SnapshotTargetExists(_)));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(imported_path);
        let _ = fs::remove_dir_all(snapshot_dir);
    }

    #[test]
    fn node_runner_explorer_overview_renders_replayed_chain_file() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();

        run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
        ])
        .unwrap();
        run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1carol00000000000",
            "--amount",
            "10",
            "--fee",
            "2",
            "--nonce",
            "1",
            "--expires-at-height",
            "100",
        ])
        .unwrap();

        let overview = run_node_command([
            "explorer-overview",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "2",
        ])
        .unwrap()
        .to_string();

        assert!(overview.contains("XRIQ Private Devnet Explorer"));
        assert!(overview.contains("chain: xriq-devnet"));
        assert!(overview.contains("current height: 2"));
        assert!(overview.contains("state root: "));
        assert!(overview.contains("stored blocks: 2, pending transactions: 0"));
        assert!(overview.contains("- height 2"));
        assert!(overview.contains("- height 1"));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_runner_block_detail_renders_replayed_chain_file() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();

        let produced_output = run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
        ])
        .unwrap();
        let produced = match produced_output {
            NodeRunnerOutput::ProducedTransferBlock(produced) => produced,
            other => panic!("unexpected output: {other:?}"),
        };

        let detail = run_node_command([
            "block-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--height",
            "1",
        ])
        .unwrap()
        .to_string();

        assert!(detail.contains("block 1"));
        assert!(detail.contains("transactions: 1"));
        assert!(detail.contains("xriqdev1alice00000000000 -> xriqdev1bobbb00000000000"));
        assert!(detail.contains("amount=25"));
        assert!(detail.contains("fee=2"));

        let produced_block_hash = hash_hex(produced.block_hash);
        let detail_by_hash = run_node_command([
            "block-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--block-hash",
            produced_block_hash.as_str(),
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(detail_by_hash.contains("\"command\": \"block-detail\""));
        assert!(detail_by_hash.contains("\"height\": 1"));
        assert!(detail_by_hash.contains(&produced_block_hash));

        let latest_detail = run_node_command([
            "block-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--height",
            "latest",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(latest_detail.contains("\"command\": \"block-detail\""));
        assert!(latest_detail.contains("\"height\": 1"));
        assert!(latest_detail.contains(&produced_block_hash));

        let block_list = run_node_command([
            "block-list",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "5",
        ])
        .unwrap()
        .to_string();

        assert!(block_list.contains("latest blocks"));
        assert!(block_list.contains("blocks: 1"));
        assert!(block_list.contains("height 1"));
        assert!(block_list.contains(&produced_block_hash));

        let block_list_json = run_node_command([
            "block-list",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "5",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(block_list_json.contains("\"command\": \"block-list\""));
        assert!(block_list_json.contains("\"block_count\": 1"));
        assert!(block_list_json.contains("\"height\": 1"));
        assert!(block_list_json.contains(&produced_block_hash));

        let ambiguous_selector = run_node_command([
            "block-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--height",
            "1",
            "--block-hash",
            produced_block_hash.as_str(),
        ])
        .unwrap_err();
        assert!(matches!(
            ambiguous_selector,
            NodeRunnerError::InvalidFormat(_)
        ));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_runner_account_detail_renders_replayed_chain_file() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();

        run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
        ])
        .unwrap();
        run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1carol00000000000",
            "--amount",
            "10",
            "--fee",
            "2",
            "--nonce",
            "1",
            "--expires-at-height",
            "100",
        ])
        .unwrap();

        let alice = run_node_command([
            "account-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--address",
            "xriqdev1alice00000000000",
        ])
        .unwrap()
        .to_string();
        let bob = run_node_command([
            "account-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--address",
            "xriqdev1bobbb00000000000",
        ])
        .unwrap()
        .to_string();

        assert!(alice.contains("account xriqdev1alice00000000000"));
        assert!(alice.contains("balance: 61"));
        assert!(alice.contains("nonce: 2"));
        assert!(bob.contains("account xriqdev1bobbb00000000000"));
        assert!(bob.contains("balance: 25"));
        assert!(bob.contains("nonce: 0"));

        let account_list = run_node_command([
            "account-list",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "2",
        ])
        .unwrap()
        .to_string();
        assert!(account_list.contains("accounts: 2"));
        assert!(account_list.contains("xriqdev1alice00000000000"));
        assert!(account_list.contains("xriqdev1bobbb00000000000"));
        assert!(!account_list.contains("xriqdev1carol00000000000"));

        let account_list_json = run_node_command([
            "account-list",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(account_list_json.contains("\"command\": \"account-list\""));
        assert!(account_list_json.contains("\"account_count\": 4"));
        assert!(account_list_json.contains("\"accounts\": ["));
        assert!(account_list_json.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(account_list_json.contains("\"address\": \"xriqdev1carol00000000000\""));

        let alice_transactions = run_node_command([
            "account-transactions",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--address",
            "xriqdev1alice00000000000",
            "--limit",
            "1",
        ])
        .unwrap()
        .to_string();
        assert!(alice_transactions.contains("account transactions xriqdev1alice00000000000"));
        assert!(alice_transactions.contains("transactions: 1"));
        assert!(alice_transactions.contains("height 2"));
        assert!(alice_transactions.contains("sent"));
        assert!(alice_transactions.contains("xriqdev1carol00000000000"));

        let bob_transactions = run_node_command([
            "account-transactions",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--address",
            "xriqdev1bobbb00000000000",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(bob_transactions.contains("\"command\": \"account-transactions\""));
        assert!(bob_transactions.contains("\"transaction_count\": 1"));
        assert!(bob_transactions.contains("\"direction\": \"received\""));
        assert!(bob_transactions.contains("\"block_height\": 1"));

        let latest_transactions = run_node_command([
            "transaction-list",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "1",
        ])
        .unwrap()
        .to_string();
        assert!(latest_transactions.contains("latest transactions"));
        assert!(latest_transactions.contains("transactions: 1"));
        assert!(latest_transactions.contains("height 2"));
        assert!(latest_transactions.contains("xriqdev1carol00000000000"));

        let latest_transactions_json = run_node_command([
            "transaction-list",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(latest_transactions_json.contains("\"command\": \"transaction-list\""));
        assert!(latest_transactions_json.contains("\"transaction_count\": 2"));
        assert!(latest_transactions_json.contains("\"block_height\": 2"));
        assert!(latest_transactions_json.contains("\"block_height\": 1"));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_runner_mempool_detail_previews_wallet_draft_without_persisting_block() {
        let path = temp_store_path();
        let draft_path = path.with_extension("draft");
        let path_text = path.to_string_lossy().to_string();
        let draft_text = draft_path.to_string_lossy().to_string();
        fs::write(
            &draft_path,
            [
                "\u{feff}warning=private-devnet-test-identity-only",
                "version=1",
                "chain_id=xriq-devnet",
                "from=xriqdev1alice00000000000",
                "to=xriqdev1bobbb00000000000",
                "amount=25",
                "fee=2",
                "nonce=0",
                "expires_at_height=100",
                "signature_bytes=48",
            ]
            .join("\n"),
        )
        .unwrap();

        let detail = run_node_command([
            "mempool-detail",
            "--chain-file",
            path_text.as_str(),
            "--draft-file",
            draft_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap()
        .to_string();

        assert!(detail.contains("mempool pending: 1"));
        assert!(detail.contains("xriqdev1alice00000000000 -> xriqdev1bobbb00000000000"));
        assert!(detail.contains("amount=25"));
        assert!(detail.contains("fee=2"));
        assert!(detail.contains("nonce=0"));
        assert_eq!(
            private_devnet_file_status(&path, Some(XriqAmount::from_base_units(100))).unwrap(),
            NodeStatus {
                warning: PRIVATE_DEVNET_RUNNER_WARNING,
                chain_id: "xriq-devnet".to_string(),
                current_height: 0,
                latest_block_hash: hash(0),
                state_root: genesis_state_root(),
                pending_transactions: 0,
                stored_blocks: 0,
            }
        );

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn node_runner_transaction_detail_previews_pending_wallet_draft() {
        let path = temp_store_path();
        let draft_path = path.with_extension("draft");
        let path_text = path.to_string_lossy().to_string();
        let draft_text = draft_path.to_string_lossy().to_string();
        write_wallet_draft(&draft_path, 25, 2, 0);

        let mempool = private_devnet_file_mempool_detail_data(
            &path,
            Some(&draft_path),
            Some(XriqAmount::from_base_units(100)),
        )
        .unwrap();
        let tx_hash = mempool.transactions[0].tx_hash;
        let tx_hash_text = hash_hex(tx_hash);

        let detail = run_node_command([
            "transaction-detail",
            "--chain-file",
            path_text.as_str(),
            "--draft-file",
            draft_text.as_str(),
            "--alice-balance",
            "100",
            "--tx-hash",
            tx_hash_text.as_str(),
        ])
        .unwrap()
        .to_string();

        assert!(detail.contains("status: pending"));
        assert!(detail.contains("received_order: 0"));
        assert!(detail.contains("amount_base_units: 25"));
        assert!(detail.contains("fee_base_units: 2"));
        assert!(detail.contains("nonce: 0"));

        let detail_json = run_node_command([
            "transaction-detail",
            "--chain-file",
            path_text.as_str(),
            "--draft-file",
            draft_text.as_str(),
            "--alice-balance",
            "100",
            "--tx-hash",
            tx_hash_text.as_str(),
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(detail_json.contains("\"command\": \"transaction-detail\""));
        assert!(detail_json.contains("\"status\": \"pending\""));
        assert!(detail_json.contains("\"received_order\": 0"));
        assert!(detail_json.contains("\"amount_base_units\": \"25\""));
        assert!(detail_json.contains("\"expires_at_height\": 100"));
        assert_eq!(
            private_devnet_file_status(&path, Some(XriqAmount::from_base_units(100))).unwrap(),
            NodeStatus {
                warning: PRIVATE_DEVNET_RUNNER_WARNING,
                chain_id: "xriq-devnet".to_string(),
                current_height: 0,
                latest_block_hash: hash(0),
                state_root: genesis_state_root(),
                pending_transactions: 0,
                stored_blocks: 0,
            }
        );

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn node_runner_transaction_detail_reads_confirmed_chain_file() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        let produced_output = run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
        ])
        .unwrap();
        let produced = match produced_output {
            NodeRunnerOutput::ProducedTransferBlock(produced) => produced,
            other => panic!("unexpected output: {other:?}"),
        };
        let tx_hash_text = hash_hex(produced.transaction_hash);

        let detail = run_node_command([
            "transaction-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--tx-hash",
            tx_hash_text.as_str(),
        ])
        .unwrap()
        .to_string();

        assert!(detail.contains("status: confirmed"));
        assert!(detail.contains("block_height: 1"));
        assert!(detail.contains("transaction_index: 0"));
        assert!(detail.contains("amount_base_units: 25"));

        let detail_json = run_node_command([
            "transaction-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--tx-hash",
            tx_hash_text.as_str(),
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(detail_json.contains("\"command\": \"transaction-detail\""));
        assert!(detail_json.contains("\"status\": \"confirmed\""));
        assert!(detail_json.contains("\"block_height\": 1"));
        assert!(detail_json.contains("\"transaction_index\": 0"));
        assert!(detail_json.contains("\"amount_base_units\": \"25\""));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_runner_json_format_outputs_stable_machine_fields() {
        let path = temp_store_path();
        let draft_path = path.with_extension("draft");
        let path_text = path.to_string_lossy().to_string();
        let draft_text = draft_path.to_string_lossy().to_string();
        fs::write(
            &draft_path,
            [
                "warning=private-devnet-test-identity-only",
                "version=1",
                "chain_id=xriq-devnet",
                "from=xriqdev1alice00000000000",
                "to=xriqdev1bobbb00000000000",
                "amount=25",
                "fee=2",
                "nonce=0",
                "expires_at_height=100",
                "signature_bytes=48",
            ]
            .join("\n"),
        )
        .unwrap();

        let status_json = run_node_command([
            "status",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(status_json.contains("\"format_version\": \"xriq-node-json-v1\""));
        assert!(status_json.contains("\"command\": \"status\""));
        assert!(status_json.contains("\"warning\": \"private-devnet-only-no-public-token\""));
        assert!(status_json.contains("\"chain_id\": \"xriq-devnet\""));
        assert!(status_json.contains("\"current_height\": 0"));

        let mempool_json = run_node_command([
            "mempool-detail",
            "--chain-file",
            path_text.as_str(),
            "--draft-file",
            draft_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(mempool_json.contains("\"command\": \"mempool-detail\""));
        assert!(mempool_json.contains("\"pending_count\": 1"));
        assert!(mempool_json.contains("\"tx_hash\":"));
        assert!(mempool_json.contains("\"amount_base_units\": \"25\""));
        assert!(mempool_json.contains("\"fee_base_units\": \"2\""));
        assert!(mempool_json.contains("\"expires_at_height\": 100"));

        let produced_json = run_node_command([
            "produce-draft-block",
            "--chain-file",
            path_text.as_str(),
            "--draft-file",
            draft_text.as_str(),
            "--alice-balance",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(produced_json.contains("\"command\": \"produce-draft-block\""));
        assert!(produced_json.contains("\"transaction_hash\":"));
        assert!(produced_json.contains("\"block_hash\":"));
        assert!(produced_json.contains("\"applied_transactions\": 1"));
        assert!(produced_json.contains("\"current_height\": 1"));

        let overview_json = run_node_command([
            "explorer-overview",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "5",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(overview_json.contains("\"command\": \"explorer-overview\""));
        assert!(overview_json.contains("\"state_root\":"));
        assert!(overview_json.contains("\"latest_blocks\": ["));
        assert!(overview_json.contains("\"height\": 1"));
        assert!(overview_json.contains("\"transaction_count\": 1"));

        let block_json = run_node_command([
            "block-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--height",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(block_json.contains("\"command\": \"block-detail\""));
        assert!(block_json.contains("\"transactions\": ["));
        assert!(block_json.contains("\"tx_hash\":"));
        assert!(block_json.contains("\"from\": \"xriqdev1alice00000000000\""));
        assert!(block_json.contains("\"to\": \"xriqdev1bobbb00000000000\""));
        assert!(block_json.contains("\"amount_base_units\": \"25\""));
        assert!(block_json.contains("\"fee_base_units\": \"2\""));

        let account_json = run_node_command([
            "account-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--address",
            "xriqdev1alice00000000000",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        assert!(account_json.contains("\"command\": \"account-detail\""));
        assert!(account_json.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(account_json.contains("\"balance_base_units\": \"73\""));
        assert!(account_json.contains("\"nonce\": 1"));

        assert_eq!(
            run_node_command([
                "status",
                "--chain-file",
                path_text.as_str(),
                "--format",
                "yaml",
            ]),
            Err(NodeRunnerError::InvalidFormat("yaml".to_string()))
        );

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn produced_transfer_block_json_matches_checked_fixture() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        let produced_json = run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture =
            include_str!("../../../fixtures/private-devnet/node-produce-transfer-block.json");

        assert_eq!(produced_json.trim_end(), fixture.trim_end());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn block_detail_json_matches_checked_fixture() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap();

        let block_detail_json = run_node_command([
            "block-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--height",
            "1",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture =
            include_str!("../../../fixtures/private-devnet/node-block-detail-transfer.json");

        assert_eq!(block_detail_json.trim_end(), fixture.trim_end());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn produced_pending_block_json_matches_checked_fixture() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        private_devnet_file_submit_pending_transfer_body(
            &path_text,
            &pending_text,
            Some(XriqAmount::from_base_units(100)),
            include_str!("../../../fixtures/private-devnet/wallet-transfer-submit.json"),
        )
        .unwrap();

        let produced_json = run_node_command([
            "produce-pending-block",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture =
            include_str!("../../../fixtures/private-devnet/node-produce-pending-block.json");

        assert_eq!(produced_json.trim_end(), fixture.trim_end());
        assert_eq!(fs::read_to_string(&pending_path).unwrap(), "");

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn preflight_transfer_json_matches_checked_fixture() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();

        let preflight_json = run_node_command([
            "preflight-transfer",
            "--chain-file",
            path_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--expires-at-height",
            "100",
            "--timestamp-ms",
            "1000",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture = include_str!("../../../fixtures/private-devnet/node-preflight-transfer.json");

        assert_eq!(preflight_json.trim_end(), fixture.trim_end());
        assert_eq!(fs::read_to_string(&pending_path).unwrap(), "");

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn node_status_json_matches_checked_fixture() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        let status_json = run_node_command([
            "status",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture = include_str!("../../../fixtures/private-devnet/node-status-empty.json");

        assert_eq!(status_json.trim_end(), fixture.trim_end());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_empty_mempool_json_matches_checked_fixture() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        let mempool_json = run_node_command([
            "mempool-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture = include_str!("../../../fixtures/private-devnet/node-mempool-empty.json");

        assert_eq!(mempool_json.trim_end(), fixture.trim_end());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_initial_account_json_matches_checked_fixture() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        let account_json = run_node_command([
            "account-detail",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--address",
            "xriqdev1alice00000000000",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture =
            include_str!("../../../fixtures/private-devnet/node-account-alice-initial.json");

        assert_eq!(account_json.trim_end(), fixture.trim_end());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn private_devnet_http_routes_wrap_file_backed_json_outputs() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        let produced = match run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            "xriqdev1alice00000000000",
            "--to",
            "xriqdev1bobbb00000000000",
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
        ])
        .unwrap()
        {
            NodeRunnerOutput::ProducedTransferBlock(produced) => produced,
            other => panic!("unexpected output: {other:?}"),
        };
        let config = PrivateDevnetHttpServerConfig {
            bind: "127.0.0.1:8787".to_string(),
            chain_file: path_text,
            pending_file: None,
            snapshot_root: None,
            alice_balance: Some(XriqAmount::from_base_units(100)),
            allow_transaction_submission: false,
            peers_file: None,
            node_seed: None,
            testnet: false,
        };

        let health = private_devnet_http_response(&config, "GET", "/health");
        assert_eq!(health.status_code, 200);
        assert!(health
            .body
            .contains("\"format_version\": \"xriq-node-http-v1\""));
        assert!(health.body.contains("\"status\": \"ok\""));

        let status = private_devnet_http_response(&config, "GET", "/v1/chain/status");
        assert_eq!(status.status_code, 200);
        assert!(status.body.contains("\"command\": \"status\""));
        assert!(status.body.contains("\"current_height\": 1"));

        let chain_check = private_devnet_http_response(&config, "GET", "/v1/chain/check");
        assert_eq!(chain_check.status_code, 200);
        assert!(chain_check.body.contains("\"command\": \"chain-check\""));
        assert!(chain_check.body.contains("\"verified\": true"));
        assert!(chain_check.body.contains("\"current_height\": 1"));
        assert!(chain_check.body.contains("\"state_root\":"));

        let overview =
            private_devnet_http_response(&config, "GET", "/v1/explorer/overview?limit=5");
        assert_eq!(overview.status_code, 200);
        assert!(overview.body.contains("\"command\": \"explorer-overview\""));
        assert!(overview.body.contains("\"state_root\":"));
        assert!(overview.body.contains("\"latest_blocks\": ["));

        let block_list = private_devnet_http_response(&config, "GET", "/v1/blocks?limit=5");
        assert_eq!(block_list.status_code, 200);
        assert!(block_list.body.contains("\"command\": \"block-list\""));
        assert!(block_list.body.contains("\"block_count\": 1"));
        assert!(block_list.body.contains("\"height\": 1"));
        assert!(block_list.body.contains(&hash_hex(produced.block_hash)));

        let block = private_devnet_http_response(&config, "GET", "/v1/blocks/1");
        assert_eq!(block.status_code, 200);
        assert!(block.body.contains("\"command\": \"block-detail\""));
        assert!(block.body.contains("\"transaction_count\": 1"));

        let block_by_hash_path = format!("/v1/blocks/{}", hash_hex(produced.block_hash));
        let block_by_hash = private_devnet_http_response(&config, "GET", &block_by_hash_path);
        assert_eq!(block_by_hash.status_code, 200);
        assert!(block_by_hash.body.contains("\"command\": \"block-detail\""));
        assert!(block_by_hash.body.contains("\"height\": 1"));
        assert!(block_by_hash.body.contains(&hash_hex(produced.block_hash)));

        let latest_block = private_devnet_http_response(&config, "GET", "/v1/blocks/latest");
        assert_eq!(latest_block.status_code, 200);
        assert!(latest_block.body.contains("\"command\": \"block-detail\""));
        assert!(latest_block.body.contains("\"height\": 1"));
        assert!(latest_block.body.contains(&hash_hex(produced.block_hash)));

        let accounts = private_devnet_http_response(&config, "GET", "/v1/accounts?limit=5");
        assert_eq!(accounts.status_code, 200);
        assert!(accounts.body.contains("\"command\": \"account-list\""));
        assert!(accounts.body.contains("\"account_count\": 3"));
        assert!(accounts
            .body
            .contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(accounts
            .body
            .contains("\"address\": \"xriqdev1bobbb00000000000\""));

        let account =
            private_devnet_http_response(&config, "GET", "/v1/accounts/xriqdev1alice00000000000");
        assert_eq!(account.status_code, 200);
        assert!(account.body.contains("\"command\": \"account-detail\""));
        assert!(account.body.contains("\"balance_base_units\": \"73\""));

        let account_transactions = private_devnet_http_response(
            &config,
            "GET",
            "/v1/accounts/xriqdev1alice00000000000/transactions?limit=1",
        );
        assert_eq!(account_transactions.status_code, 200);
        assert!(account_transactions
            .body
            .contains("\"command\": \"account-transactions\""));
        assert!(account_transactions
            .body
            .contains("\"transaction_count\": 1"));
        assert!(account_transactions
            .body
            .contains("\"direction\": \"sent\""));
        assert!(account_transactions.body.contains("\"block_height\": 1"));

        let transaction_list =
            private_devnet_http_response(&config, "GET", "/v1/transactions?limit=5");
        assert_eq!(transaction_list.status_code, 200);
        assert!(transaction_list
            .body
            .contains("\"command\": \"transaction-list\""));
        assert!(transaction_list.body.contains("\"transaction_count\": 1"));
        assert!(transaction_list.body.contains("\"block_height\": 1"));
        assert!(transaction_list
            .body
            .contains(&hash_hex(produced.transaction_hash)));

        let mempool = private_devnet_http_response(&config, "GET", "/v1/mempool");
        assert_eq!(mempool.status_code, 200);
        assert!(mempool.body.contains("\"command\": \"mempool-detail\""));
        assert!(mempool.body.contains("\"pending_count\": 0"));

        let transaction_path = format!("/v1/transactions/{}", hash_hex(produced.transaction_hash));
        let transaction = private_devnet_http_response(&config, "GET", &transaction_path);
        assert_eq!(transaction.status_code, 200);
        assert!(transaction
            .body
            .contains("\"command\": \"transaction-detail\""));
        assert!(transaction.body.contains("\"status\": \"confirmed\""));
        assert!(transaction.body.contains("\"block_height\": 1"));
        assert!(transaction.body.contains("\"transaction_index\": 0"));
        assert!(transaction.body.contains("\"amount_base_units\": \"25\""));

        let missing_transaction = private_devnet_http_response(
            &config,
            "GET",
            "/v1/transactions/1111111111111111111111111111111111111111111111111111111111111111",
        );
        assert_eq!(missing_transaction.status_code, 404);
        assert!(missing_transaction
            .body
            .contains("\"code\": \"transaction_not_found\""));

        let bad_transaction_hash =
            private_devnet_http_response(&config, "GET", "/v1/transactions/not-a-hash");
        assert_eq!(bad_transaction_hash.status_code, 400);
        assert!(bad_transaction_hash
            .body
            .contains("\"code\": \"invalid_hash\""));

        let missing_block = private_devnet_http_response(&config, "GET", "/v1/blocks/99");
        assert_eq!(missing_block.status_code, 404);
        assert!(missing_block.body.contains("\"code\": \"explorer_error\""));

        let bad_limit =
            private_devnet_http_response(&config, "GET", "/v1/explorer/overview?limit=bad");
        assert_eq!(bad_limit.status_code, 400);
        assert!(bad_limit.body.contains("\"code\": \"invalid_number\""));

        let submit_draft = [
            "warning=private-devnet-test-identity-only",
            "version=1",
            "chain_id=xriq-devnet",
            "from=xriqdev1alice00000000000",
            "to=xriqdev1carol00000000000",
            "amount=10",
            "fee=2",
            "nonce=1",
            "expires_at_height=100",
            "signature_bytes=48",
        ]
        .join("\n");
        let readonly_submit = private_devnet_http_response_with_body(
            &config,
            "POST",
            "/v1/transactions",
            &submit_draft,
        );
        assert_eq!(readonly_submit.status_code, 501);
        assert!(readonly_submit
            .body
            .contains("\"code\": \"not_implemented\""));

        let submit_config = PrivateDevnetHttpServerConfig {
            allow_transaction_submission: true,
            ..config.clone()
        };
        let submit = private_devnet_http_response_with_body(
            &submit_config,
            "POST",
            "/v1/transactions",
            &submit_draft,
        );
        assert_eq!(submit.status_code, 201);
        assert!(submit.body.contains("\"command\": \"submit-transaction\""));
        assert!(submit.body.contains("\"transaction_hash\":"));
        assert!(submit.body.contains("\"current_height\": 2"));
        assert!(submit.body.contains("\"applied_transactions\": 1"));

        let submit_json = [
            "{",
            "  \"format_version\": \"xriq-node-transfer-submit-v1\",",
            "  \"version\": 1,",
            "  \"chain_id\": \"xriq-devnet\",",
            "  \"from\": \"xriqdev1alice00000000000\",",
            "  \"to\": \"xriqdev1davee00000000000\",",
            "  \"amount_base_units\": \"5\",",
            "  \"fee_base_units\": 2,",
            "  \"nonce\": 2,",
            "  \"expires_at_height\": null",
            "}",
        ]
        .join("\n");
        let json_submit = private_devnet_http_response_with_body(
            &submit_config,
            "POST",
            "/v1/transactions",
            &submit_json,
        );
        assert_eq!(json_submit.status_code, 201);
        assert!(json_submit
            .body
            .contains("\"command\": \"submit-transaction\""));
        assert!(json_submit.body.contains("\"current_height\": 3"));
        assert!(json_submit.body.contains("\"applied_transactions\": 1"));

        let bad_json_submit = private_devnet_http_response_with_body(
            &submit_config,
            "POST",
            "/v1/transactions",
            "{\"version\": 1, \"chain_id\": \"xriq-devnet\", \"amount_base_units\": 5}",
        );
        assert_eq!(bad_json_submit.status_code, 400);
        assert!(bad_json_submit
            .body
            .contains("\"code\": \"missing_json_field\""));

        let status_after_submit =
            private_devnet_http_response(&submit_config, "GET", "/v1/chain/status");
        assert_eq!(status_after_submit.status_code, 200);
        assert!(status_after_submit.body.contains("\"current_height\": 3"));

        let snapshot_root = temp_snapshot_dir();
        let snapshot_dir = snapshot_root.join("http-snapshot");
        let snapshot_root_text = snapshot_root.to_string_lossy().to_string();
        let snapshot_text = snapshot_dir.to_string_lossy().to_string();
        let snapshot_export_path = format!("/v1/snapshots/export?snapshot_dir={snapshot_text}");
        let readonly_snapshot_export =
            private_devnet_http_response_with_body(&config, "POST", &snapshot_export_path, "");
        assert_eq!(readonly_snapshot_export.status_code, 501);
        assert!(readonly_snapshot_export
            .body
            .contains("\"code\": \"not_implemented\""));

        let snapshot_export = private_devnet_http_response_with_body(
            &submit_config,
            "POST",
            &snapshot_export_path,
            "",
        );
        assert_eq!(snapshot_export.status_code, 201);
        assert!(snapshot_export
            .body
            .contains("\"command\": \"snapshot-export\""));
        assert!(snapshot_export.body.contains("\"current_height\": 3"));
        assert!(snapshot_dir.join(SNAPSHOT_CHAIN_FILE).exists());
        assert!(snapshot_dir.join(SNAPSHOT_MANIFEST_FILE).exists());

        let missing_snapshot_root =
            private_devnet_http_response(&submit_config, "GET", "/v1/snapshots?limit=5");
        assert_eq!(missing_snapshot_root.status_code, 501);
        assert!(missing_snapshot_root
            .body
            .contains("\"code\": \"not_implemented\""));

        let discovery_config = PrivateDevnetHttpServerConfig {
            snapshot_root: Some(snapshot_root_text.clone()),
            ..submit_config.clone()
        };
        let snapshot_list =
            private_devnet_http_response(&discovery_config, "GET", "/v1/snapshots?limit=5");
        assert_eq!(snapshot_list.status_code, 200);
        assert!(snapshot_list
            .body
            .contains("\"command\": \"snapshot-list\""));
        assert!(snapshot_list.body.contains("\"snapshot_count\": 1"));
        assert!(snapshot_list
            .body
            .contains("\"snapshot_name\": \"http-snapshot\""));
        assert!(snapshot_list.body.contains("\"current_height\": 3"));

        let snapshot_latest =
            private_devnet_http_response(&discovery_config, "GET", "/v1/snapshots/latest");
        assert_eq!(snapshot_latest.status_code, 200);
        assert!(snapshot_latest
            .body
            .contains("\"command\": \"snapshot-latest\""));
        assert!(snapshot_latest
            .body
            .contains("\"snapshot_name\": \"http-snapshot\""));
        assert!(snapshot_latest.body.contains("\"current_height\": 3"));

        let snapshot_latest_check =
            private_devnet_http_response(&discovery_config, "GET", "/v1/snapshots/latest/check");
        assert_eq!(snapshot_latest_check.status_code, 200);
        assert!(snapshot_latest_check
            .body
            .contains("\"command\": \"snapshot-latest-check\""));
        assert!(snapshot_latest_check.body.contains("\"verified\": true"));
        assert!(snapshot_latest_check
            .body
            .contains("\"snapshot_name\": \"http-snapshot\""));
        assert!(snapshot_latest_check
            .body
            .contains("\"replayed_status\": {"));

        let snapshot_detail =
            private_devnet_http_response(&discovery_config, "GET", "/v1/snapshots/http-snapshot");
        assert_eq!(snapshot_detail.status_code, 200);
        assert!(snapshot_detail
            .body
            .contains("\"command\": \"snapshot-detail\""));
        assert!(snapshot_detail
            .body
            .contains("\"snapshot_name\": \"http-snapshot\""));
        assert!(snapshot_detail.body.contains("\"current_height\": 3"));

        let snapshot_check = private_devnet_http_response(
            &discovery_config,
            "GET",
            "/v1/snapshots/http-snapshot/check",
        );
        assert_eq!(snapshot_check.status_code, 200);
        assert!(snapshot_check
            .body
            .contains("\"command\": \"snapshot-check\""));
        assert!(snapshot_check.body.contains("\"verified\": true"));
        assert!(snapshot_check
            .body
            .contains("\"snapshot_name\": \"http-snapshot\""));
        assert!(snapshot_check.body.contains("\"replayed_status\": {"));

        let unsafe_snapshot_detail =
            private_devnet_http_response(&discovery_config, "GET", "/v1/snapshots/..");
        assert_eq!(unsafe_snapshot_detail.status_code, 400);
        assert!(unsafe_snapshot_detail
            .body
            .contains("\"code\": \"invalid_format\""));

        let missing_snapshot_dir = private_devnet_http_response_with_body(
            &submit_config,
            "POST",
            "/v1/snapshots/export",
            "",
        );
        assert_eq!(missing_snapshot_dir.status_code, 400);
        assert!(missing_snapshot_dir
            .body
            .contains("\"code\": \"missing_flag\""));

        let imported_path = path.with_extension("imported-chain");
        let imported_pending_path = path.with_extension("imported-pending");
        let imported_path_text = imported_path.to_string_lossy().to_string();
        let imported_pending_text = imported_pending_path.to_string_lossy().to_string();
        let import_config = PrivateDevnetHttpServerConfig {
            bind: "127.0.0.1:8787".to_string(),
            chain_file: imported_path_text,
            pending_file: Some(imported_pending_text),
            snapshot_root: Some(snapshot_root_text),
            alice_balance: Some(XriqAmount::from_base_units(100)),
            allow_transaction_submission: true,
            peers_file: None,
            node_seed: None,
            testnet: false,
        };
        let snapshot_import = private_devnet_http_response_with_body(
            &import_config,
            "POST",
            &format!("/v1/snapshots/import?snapshot_dir={snapshot_text}"),
            "",
        );
        assert_eq!(snapshot_import.status_code, 201);
        assert!(snapshot_import
            .body
            .contains("\"command\": \"snapshot-import\""));
        assert!(snapshot_import.body.contains("\"current_height\": 3"));

        let imported_status =
            private_devnet_http_response(&import_config, "GET", "/v1/chain/status");
        assert_eq!(imported_status.status_code, 200);
        assert!(imported_status.body.contains("\"current_height\": 3"));

        let imported_chain_check =
            private_devnet_http_response(&import_config, "GET", "/v1/chain/check");
        assert_eq!(imported_chain_check.status_code, 200);
        assert!(imported_chain_check
            .body
            .contains("\"command\": \"chain-check\""));
        assert!(imported_chain_check.body.contains("\"verified\": true"));
        assert!(imported_chain_check.body.contains("\"current_height\": 3"));
        assert!(imported_chain_check.body.contains("\"state_root\":"));

        let raw = status.to_http_response();
        assert!(raw.starts_with("HTTP/1.1 200 OK\r\n"));
        assert!(raw.contains("Content-Type: application/json; charset=utf-8\r\n"));
        assert!(raw.contains("Connection: close\r\n"));

        let parsed = private_devnet_http_response_from_request(
            &config,
            "GET /v1/chain/status HTTP/1.1\r\nHost: localhost\r\n\r\n",
        );
        assert_eq!(parsed.status_code, 200);
        assert!(parsed.body.contains("\"command\": \"status\""));

        let _ = fs::remove_dir_all(snapshot_root);
        let _ = fs::remove_file(imported_path);
        let _ = fs::remove_file(imported_pending_path);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn private_devnet_http_routes_persist_pending_transactions() {
        let path = temp_store_path();
        let pending_path = path.with_extension("pending");
        let path_text = path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let config = PrivateDevnetHttpServerConfig {
            bind: "127.0.0.1:8787".to_string(),
            chain_file: path_text,
            pending_file: Some(pending_text),
            snapshot_root: None,
            alice_balance: Some(XriqAmount::from_base_units(100)),
            allow_transaction_submission: true,
            peers_file: None,
            node_seed: None,
            testnet: false,
        };
        let submit_draft = [
            "warning=private-devnet-test-identity-only",
            "version=1",
            "chain_id=xriq-devnet",
            "from=xriqdev1alice00000000000",
            "to=xriqdev1bobbb00000000000",
            "amount=25",
            "fee=2",
            "nonce=0",
            "expires_at_height=100",
            "signature_bytes=48",
        ]
        .join("\n");

        let submit =
            private_devnet_http_response_with_body(&config, "POST", "/v1/mempool", &submit_draft);
        assert_eq!(submit.status_code, 202);
        assert!(submit.body.contains("\"command\": \"transaction-detail\""));
        assert!(submit.body.contains("\"status\": \"pending\""));
        assert!(submit.body.contains("\"received_order\": 0"));
        assert!(submit.body.contains("\"amount_base_units\": \"25\""));

        let status = private_devnet_http_response(&config, "GET", "/v1/chain/status");
        assert_eq!(status.status_code, 200);
        assert!(status.body.contains("\"pending_transactions\": 1"));
        assert!(status.body.contains("\"current_height\": 0"));

        let mempool = private_devnet_http_response(&config, "GET", "/v1/mempool");
        assert_eq!(mempool.status_code, 200);
        assert!(mempool.body.contains("\"pending_count\": 1"));
        let pending = private_devnet_file_mempool_detail_with_pending_file_data(
            &config.chain_file,
            config.pending_file.as_ref().unwrap(),
            config.alice_balance,
        )
        .unwrap();
        let tx_hash = pending.transactions[0].tx_hash;
        let transaction_path = format!("/v1/transactions/{}", hash_hex(tx_hash));
        let transaction = private_devnet_http_response(&config, "GET", &transaction_path);
        assert_eq!(transaction.status_code, 200);
        assert!(transaction.body.contains("\"status\": \"pending\""));
        assert!(transaction.body.contains("\"amount_base_units\": \"25\""));

        let reloaded_config = config.clone();
        let reloaded_transaction =
            private_devnet_http_response(&reloaded_config, "GET", &transaction_path);
        assert_eq!(reloaded_transaction.status_code, 200);
        assert!(reloaded_transaction
            .body
            .contains("\"status\": \"pending\""));

        let produce = private_devnet_http_response_with_body(&config, "POST", "/v1/blocks", "");
        assert_eq!(produce.status_code, 201);
        assert!(produce
            .body
            .contains("\"command\": \"produce-pending-block\""));
        assert!(produce.body.contains("\"included_transaction_hashes\": ["));
        assert!(produce.body.contains(&hash_hex(tx_hash)));
        assert!(produce.body.contains("\"applied_transactions\": 1"));
        assert!(produce.body.contains("\"current_height\": 1"));
        assert!(produce.body.contains("\"pending_transactions\": 0"));
        assert_eq!(fs::read_to_string(&pending_path).unwrap(), "");

        let mempool_after_produce = private_devnet_http_response(&config, "GET", "/v1/mempool");
        assert_eq!(mempool_after_produce.status_code, 200);
        assert!(mempool_after_produce.body.contains("\"pending_count\": 0"));

        let confirmed_transaction = private_devnet_http_response(&config, "GET", &transaction_path);
        assert_eq!(confirmed_transaction.status_code, 200);
        assert!(confirmed_transaction
            .body
            .contains("\"status\": \"confirmed\""));
        assert!(confirmed_transaction.body.contains("\"block_height\": 1"));

        let config_without_pending = PrivateDevnetHttpServerConfig {
            pending_file: None,
            ..config.clone()
        };
        let missing_pending_file = private_devnet_http_response_with_body(
            &config_without_pending,
            "POST",
            "/v1/mempool",
            &submit_draft,
        );
        assert_eq!(missing_pending_file.status_code, 501);
        assert!(missing_pending_file
            .body
            .contains("\"code\": \"not_implemented\""));

        let missing_pending_file_produce = private_devnet_http_response_with_body(
            &config_without_pending,
            "POST",
            "/v1/blocks",
            "",
        );
        assert_eq!(missing_pending_file_produce.status_code, 501);
        assert!(missing_pending_file_produce
            .body
            .contains("\"code\": \"not_implemented\""));

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn node_runner_json_error_output_has_stable_error_shape() {
        let args = vec![
            "status".to_string(),
            "--format".to_string(),
            "json".to_string(),
        ];
        let error = run_node_command(args.iter().map(String::as_str)).unwrap_err();

        assert_eq!(error, NodeRunnerError::MissingFlag("--chain-file"));
        assert!(node_runner_args_request_json(&args));
        assert_eq!(error.code(), "missing_flag");

        let json = render_node_runner_error_json(&args, &error);
        assert!(json.contains("\"format_version\": \"xriq-node-json-v1\""));
        assert!(json.contains("\"warning\": \"private-devnet-only-no-public-token\""));
        assert!(json.contains("\"ok\": false"));
        assert!(json.contains("\"command\": \"status\""));
        assert!(json.contains("\"code\": \"missing_flag\""));
        assert!(json.contains("\"message\": \"missing required flag: --chain-file\""));

        let leading_format_args = vec![
            "--format".to_string(),
            "json".to_string(),
            "status".to_string(),
        ];
        assert!(node_runner_args_request_json(&leading_format_args));
        assert!(render_node_runner_error_json(
            &leading_format_args,
            &NodeRunnerError::MissingCommand
        )
        .contains("\"command\": null"));
    }

    #[test]
    fn node_runner_produces_block_from_wallet_draft_file() {
        let path = temp_store_path();
        let draft_path = path.with_extension("draft");
        let path_text = path.to_string_lossy().to_string();
        let draft_text = draft_path.to_string_lossy().to_string();
        fs::write(
            &draft_path,
            [
                "\u{feff}warning=private-devnet-test-identity-only",
                "version=1",
                "chain_id=xriq-devnet",
                "from=xriqdev1alice00000000000",
                "to=xriqdev1bobbb00000000000",
                "amount=25",
                "fee=2",
                "nonce=0",
                "expires_at_height=100",
                "signature_bytes=48",
            ]
            .join("\n"),
        )
        .unwrap();

        let output = run_node_command([
            "produce-draft-block",
            "--chain-file",
            path_text.as_str(),
            "--draft-file",
            draft_text.as_str(),
            "--alice-balance",
            "100",
            "--timestamp-ms",
            "1000",
        ])
        .unwrap();
        let produced = match output {
            NodeRunnerOutput::ProducedTransferBlock(produced) => produced,
            other => panic!("unexpected output: {other:?}"),
        };

        assert_eq!(produced.applied_transactions, 1);
        assert_eq!(produced.status.current_height, 1);
        assert_eq!(produced.status.stored_blocks, 1);

        let reloaded = XriqNode::from_genesis_replaying_store(
            &genesis(),
            FileChainStore::open(&path).unwrap(),
        )
        .unwrap();
        assert_eq!(
            reloaded
                .ledger()
                .account(&address("alice"))
                .unwrap()
                .balance,
            XriqAmount::from_base_units(73)
        );
        assert_eq!(
            reloaded.ledger().account(&address("bobbb")).unwrap().nonce,
            0
        );

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn node_runner_rejects_wrong_chain_wallet_draft_without_persisting_block() {
        let path = temp_store_path();
        let draft_path = path.with_extension("draft");
        let path_text = path.to_string_lossy().to_string();
        let draft_text = draft_path.to_string_lossy().to_string();
        fs::write(
            &draft_path,
            [
                "warning=private-devnet-test-identity-only",
                "version=1",
                "chain_id=xriq-mainnet",
                "from=xriqdev1alice00000000000",
                "to=xriqdev1bobbb00000000000",
                "amount=25",
                "fee=2",
                "nonce=0",
                "expires_at_height=100",
                "signature_bytes=48",
            ]
            .join("\n"),
        )
        .unwrap();

        assert_eq!(
            run_node_command([
                "produce-draft-block",
                "--chain-file",
                path_text.as_str(),
                "--draft-file",
                draft_text.as_str(),
                "--alice-balance",
                "100",
            ]),
            Err(NodeRunnerError::WrongDraftChainId {
                expected: "xriq-devnet".to_string(),
                actual: "xriq-mainnet".to_string(),
            })
        );
        assert_eq!(
            private_devnet_file_status(&path, Some(XriqAmount::from_base_units(100))).unwrap(),
            NodeStatus {
                warning: PRIVATE_DEVNET_RUNNER_WARNING,
                chain_id: "xriq-devnet".to_string(),
                current_height: 0,
                latest_block_hash: hash(0),
                state_root: genesis_state_root(),
                pending_transactions: 0,
                stored_blocks: 0,
            }
        );

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn node_runner_rejects_bad_transfer_without_persisting_block() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();

        assert_eq!(
            run_node_command([
                "produce-transfer-block",
                "--chain-file",
                path_text.as_str(),
                "--alice-balance",
                "100",
                "--from",
                "xriqdev1alice00000000000",
                "--to",
                "xriqdev1bobbb00000000000",
                "--amount",
                "25",
                "--fee",
                "2",
                "--nonce",
                "7",
            ]),
            Err(NodeRunnerError::Node(NodeError::Transaction(
                TransactionValidationError::InvalidNonce {
                    expected: 0,
                    actual: 7,
                }
            )))
        );
        assert_eq!(
            private_devnet_file_status(&path, Some(XriqAmount::from_base_units(100))).unwrap(),
            NodeStatus {
                warning: PRIVATE_DEVNET_RUNNER_WARNING,
                chain_id: "xriq-devnet".to_string(),
                current_height: 0,
                latest_block_hash: hash(0),
                state_root: genesis_state_root(),
                pending_transactions: 0,
                stored_blocks: 0,
            }
        );

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_runner_rejects_missing_chain_file_flag() {
        assert_eq!(
            run_node_command(["status"]),
            Err(NodeRunnerError::MissingFlag("--chain-file"))
        );
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
    fn replay_rejects_extra_stored_blocks_outside_replayed_height_range() {
        let genesis = genesis();
        let mut producer = XriqNode::from_genesis(&genesis, InMemoryChainStore::new()).unwrap();
        let first = producer
            .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&producer))
            .unwrap();
        let mut extra_block = first.block.clone();
        extra_block.header.height = genesis.initial_height;
        let extra_hash = xriq_crypto::block_hash(&extra_block);

        let mut store = InMemoryChainStore::new();
        store.append_block(extra_hash, extra_block).unwrap();
        store
            .append_block(first.block_hash, first.block.clone())
            .unwrap();

        assert_eq!(
            XriqNode::from_genesis_replaying_store(&genesis, store),
            Err(NodeError::UnexpectedStoredBlockCount {
                expected: 1,
                actual: 2,
            })
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
