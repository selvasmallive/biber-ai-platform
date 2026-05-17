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
    Address, AddressError, Block, BlockHeader, BlockValidationError, GenesisConfig,
    GenesisConfigError, Hash32, ParentHeaderView, SignatureBytes, Transaction,
    TransactionValidationContext, TransactionValidationError, XriqAmount,
};
use xriq_crypto::{
    account_state_root, block_header_signing_hash, test_only_signature_for_hash, transaction_hash,
    transaction_signing_hash, transactions_root as canonical_transactions_root,
    SignatureVerificationError, TestOnlySignatureVerifier,
};
use xriq_explorer::{
    render_account_detail, render_block_detail, render_mempool, render_overview,
    ExplorerAccountDetail, ExplorerBlockDetail, ExplorerBlockSummary, ExplorerError,
    ExplorerMempoolDetail, ExplorerOverview, ExplorerService,
};
use xriq_ledger::{LedgerError, LedgerState};
use xriq_mempool::{Mempool, MempoolConfig, MempoolError};
use xriq_rpc::RpcService;
use xriq_storage::{ChainStore, FileChainStore, StorageError, StoredBlock};

pub const PRIVATE_DEVNET_RUNNER_WARNING: &str = "private-devnet-only-no-public-token";

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
pub struct NodeStatus {
    pub warning: &'static str,
    pub chain_id: String,
    pub current_height: u64,
    pub latest_block_hash: Hash32,
    pub pending_transactions: usize,
    pub stored_blocks: usize,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrivateDevnetHttpServerConfig {
    pub bind: String,
    pub chain_file: String,
    pub alice_balance: Option<XriqAmount>,
    pub allow_transaction_submission: bool,
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
pub struct PrivateDevnetConfirmedTransactionDetail {
    pub tx_hash: Hash32,
    pub status: &'static str,
    pub block_height: u64,
    pub block_hash: Hash32,
    pub transaction_index: usize,
    pub transaction: Transaction,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeRunnerOutput {
    Help(String),
    Status(NodeStatus),
    ProducedTransferBlock(ProducedTransferBlockStatus),
    ExplorerOverview(String),
    BlockDetail(String),
    AccountDetail(String),
    MempoolDetail(String),
    Json(String),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeRunnerError {
    MissingCommand,
    UnknownCommand(String),
    UnknownFlag(String),
    MissingFlag(&'static str),
    DuplicateFlag(String),
    UnexpectedArgument(String),
    DraftFileRead { path: String, error: String },
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
            Self::ProducedTransferBlock(status) => write!(formatter, "{status}"),
            Self::ExplorerOverview(overview) => formatter.write_str(overview),
            Self::BlockDetail(detail)
            | Self::AccountDetail(detail)
            | Self::MempoolDetail(detail) => formatter.write_str(detail),
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
            Self::DuplicateFlag(flag) => write!(formatter, "duplicate flag: {flag}"),
            Self::UnexpectedArgument(argument) => {
                write!(formatter, "unexpected argument: {argument}")
            }
            Self::DraftFileRead { path, error } => {
                write!(formatter, "could not read draft file {path}: {error}")
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
            Self::DuplicateFlag(_) => "duplicate_flag",
            Self::UnexpectedArgument(_) => "unexpected_argument",
            Self::DraftFileRead { .. } => "draft_file_read",
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
        "  xriq-node status --chain-file <path> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node produce-transfer-block --chain-file <path> --from <address> --to <address> --amount <base-units> --fee <base-units> --nonce <number> [--alice-balance <base-units>] [--expires-at-height <height>] [--timestamp-ms <ms>] [--consensus-round <number>] [--format text|json]",
        "  xriq-node produce-draft-block --chain-file <path> --draft-file <path> [--alice-balance <base-units>] [--timestamp-ms <ms>] [--consensus-round <number>] [--format text|json]",
        "  xriq-node explorer-overview --chain-file <path> [--alice-balance <base-units>] [--limit <count>] [--format text|json]",
        "  xriq-node block-detail --chain-file <path> --height <height> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node account-detail --chain-file <path> --address <address> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node mempool-detail --chain-file <path> [--draft-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-node serve-readonly --chain-file <path> [--alice-balance <base-units>] [--bind <ip:port>]",
        "  xriq-node serve-private --chain-file <path> [--alice-balance <base-units>] [--bind <ip:port>]",
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

pub fn run_node_command<I, S>(args: I) -> Result<NodeRunnerOutput, NodeRunnerError>
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let args: Vec<String> = args
        .into_iter()
        .map(|argument| argument.as_ref().to_string())
        .collect();
    match args.first().map(String::as_str) {
        None => Err(NodeRunnerError::MissingCommand),
        Some("help" | "--help" | "-h") => Ok(NodeRunnerOutput::Help(node_help_text())),
        Some("status") => run_status_command(&args[1..]),
        Some("produce-transfer-block") => run_produce_transfer_block_command(&args[1..]),
        Some("produce-draft-block") => run_produce_draft_block_command(&args[1..]),
        Some("explorer-overview") => run_explorer_overview_command(&args[1..]),
        Some("block-detail") => run_block_detail_command(&args[1..]),
        Some("account-detail") => run_account_detail_command(&args[1..]),
        Some("mempool-detail") => run_mempool_detail_command(&args[1..]),
        Some(command) => Err(NodeRunnerError::UnknownCommand(command.to_string())),
    }
}

pub fn parse_private_devnet_http_server_config(
    args: &[String],
    allow_transaction_submission: bool,
) -> Result<PrivateDevnetHttpServerConfig, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--bind", "--chain-file", "--alice-balance"])?;
    let bind = flags
        .optional("--bind")
        .unwrap_or("127.0.0.1:8787")
        .to_string();
    let chain_file = flags.required("--chain-file")?.to_string();
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    Ok(PrivateDevnetHttpServerConfig {
        bind,
        chain_file,
        alice_balance,
        allow_transaction_submission,
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
            runner_json_http_response(private_devnet_http_runner_args("status", config))
        }
        "/v1/mempool" => {
            runner_json_http_response(private_devnet_http_runner_args("mempool-detail", config))
        }
        "/v1/explorer/overview" => {
            let mut args = private_devnet_http_runner_args("explorer-overview", config);
            if let Some(limit) = query_value(query, "limit") {
                args.push("--limit".to_string());
                args.push(limit.to_string());
            }
            runner_json_http_response(args)
        }
        _ => {
            if let Some(address) = path
                .strip_prefix("/v1/accounts/")
                .filter(|address| !address.is_empty())
            {
                let mut args = private_devnet_http_runner_args("account-detail", config);
                args.push("--address".to_string());
                args.push(address.to_string());
                return runner_json_http_response(args);
            }

            if let Some(height) = path
                .strip_prefix("/v1/blocks/")
                .filter(|height| !height.is_empty())
            {
                let mut args = private_devnet_http_runner_args("block-detail", config);
                args.push("--height".to_string());
                args.push(height.to_string());
                return runner_json_http_response(args);
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
                return confirmed_transaction_http_response(config, tx_hash);
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

fn confirmed_transaction_http_response(
    config: &PrivateDevnetHttpServerConfig,
    tx_hash: Hash32,
) -> PrivateDevnetHttpResponse {
    match private_devnet_file_confirmed_transaction_detail(
        &config.chain_file,
        config.alice_balance,
        tx_hash,
    ) {
        Ok(Some(detail)) => {
            http_json_response(200, render_confirmed_transaction_detail_json(&detail))
        }
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
    let store = FileChainStore::open(chain_file)
        .map_err(|error| NodeRunnerError::Node(NodeError::Storage(error)))?;
    let genesis = private_devnet_runner_genesis(alice_balance);
    let mut node =
        XriqNode::from_genesis_replaying_store(&genesis, store).map_err(NodeRunnerError::Node)?;
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

fn run_block_detail_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--height", "--format"])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let height = parse_u64("--height", flags.required("--height")?)?;
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_file_block_detail(chain_file, alice_balance, height)
                .map(NodeRunnerOutput::BlockDetail)?
        }
        RunnerOutputFormat::Json => {
            let detail = private_devnet_file_block_detail_data(chain_file, alice_balance, height)?;
            NodeRunnerOutput::Json(render_block_detail_json("block-detail", &detail))
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

fn run_mempool_detail_command(args: &[String]) -> Result<NodeRunnerOutput, NodeRunnerError> {
    let flags = RunnerFlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--draft-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = RunnerOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let draft_file = flags.optional("--draft-file");
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    Ok(match output_format {
        RunnerOutputFormat::Text => {
            private_devnet_file_mempool_detail(chain_file, draft_file, alice_balance)
                .map(NodeRunnerOutput::MempoolDetail)?
        }
        RunnerOutputFormat::Json => {
            let detail =
                private_devnet_file_mempool_detail_data(chain_file, draft_file, alice_balance)?;
            NodeRunnerOutput::Json(render_mempool_detail_json("mempool-detail", &detail))
        }
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
    writeln!(
        &mut output,
        "  \"address\": {},",
        json_string(account.address.as_str())
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"balance_base_units\": {},",
        json_string(&account.balance.base_units().to_string())
    )
    .expect("write to String");
    writeln!(&mut output, "  \"nonce\": {}", account.nonce).expect("write to String");
    output.push('}');
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

fn render_confirmed_transaction_detail_json(
    detail: &PrivateDevnetConfirmedTransactionDetail,
) -> String {
    let mut output = String::new();
    writeln!(&mut output, "{{").expect("write to String");
    push_success_json_preamble(&mut output, "transaction-detail");
    writeln!(
        &mut output,
        "  \"warning\": {},",
        json_string(PRIVATE_DEVNET_RUNNER_WARNING)
    )
    .expect("write to String");
    writeln!(
        &mut output,
        "  \"tx_hash\": {},",
        json_string(&hash_hex(detail.tx_hash))
    )
    .expect("write to String");
    writeln!(&mut output, "  \"status\": {},", json_string(detail.status))
        .expect("write to String");
    writeln!(&mut output, "  \"block_height\": {},", detail.block_height).expect("write to String");
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
    output.push_str("\n}");
    output
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
        "--alice-balance" => "--alice-balance",
        "--limit" => "--limit",
        "--height" => "--height",
        "--address" => "--address",
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
    fn node_runner_status_replays_file_store() {
        let path = temp_store_path();
        let path_text = path.to_string_lossy().to_string();
        let genesis = genesis();
        let latest_hash;

        {
            let mut node =
                XriqNode::from_genesis(&genesis, FileChainStore::open(&path).unwrap()).unwrap();
            node.submit_transaction_with_canonical_hash(transaction(address("alice"), 0, 25, 2))
                .unwrap();
            let produced = node
                .produce_next_block_with_canonical_roots(produce_canonical_roots_input(&node))
                .unwrap();
            latest_hash = produced.block_hash;
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
                pending_transactions: 0,
                stored_blocks: 1,
            })
        );

        let _ = fs::remove_file(path);
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
        assert!(overview.contains("stored blocks: 2, pending transactions: 0"));
        assert!(overview.contains("- height 2"));
        assert!(overview.contains("- height 1"));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn node_runner_block_detail_renders_replayed_chain_file() {
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
                pending_transactions: 0,
                stored_blocks: 0,
            }
        );

        let _ = fs::remove_file(path);
        let _ = fs::remove_file(draft_path);
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
            alice_balance: Some(XriqAmount::from_base_units(100)),
            allow_transaction_submission: false,
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

        let overview =
            private_devnet_http_response(&config, "GET", "/v1/explorer/overview?limit=5");
        assert_eq!(overview.status_code, 200);
        assert!(overview.body.contains("\"command\": \"explorer-overview\""));
        assert!(overview.body.contains("\"latest_blocks\": ["));

        let block = private_devnet_http_response(&config, "GET", "/v1/blocks/1");
        assert_eq!(block.status_code, 200);
        assert!(block.body.contains("\"command\": \"block-detail\""));
        assert!(block.body.contains("\"transaction_count\": 1"));

        let account =
            private_devnet_http_response(&config, "GET", "/v1/accounts/xriqdev1alice00000000000");
        assert_eq!(account.status_code, 200);
        assert!(account.body.contains("\"command\": \"account-detail\""));
        assert!(account.body.contains("\"balance_base_units\": \"73\""));

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

        let _ = fs::remove_file(path);
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
