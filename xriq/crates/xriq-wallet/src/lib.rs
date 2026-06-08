//! Private-devnet wallet CLI behavior for XRIQ.
//!
//! This crate deliberately uses deterministic test identities and fake
//! signatures. It is not production key management.

use std::{fmt, fs};

use xriq_core::{Address, AddressError, Hash32, SignatureBytes, Transaction, XriqAmount};
use xriq_crypto::{
    test_only_signature_for_hash, transaction_hash, transaction_signing_hash, SignatureAlgorithm,
};
use xriq_node::{
    private_devnet_file_account_detail_data, private_devnet_file_account_list_data,
    private_devnet_file_account_transactions_data, private_devnet_file_chain_check,
    private_devnet_file_mempool_detail_with_pending_file_data, private_devnet_file_status,
    private_devnet_file_status_with_pending_file, private_devnet_file_submit_pending_transfer_body,
    private_devnet_file_transaction_detail_data,
    private_devnet_file_transaction_detail_with_pending_file_data, NodeStatus,
    PrivateDevnetChainCheckStatus, PrivateDevnetPendingTransactionDetail,
    PrivateDevnetTransactionDetail,
};

const TEST_IDENTITY_WARNING: &str = "private-devnet-test-identity-only";
const TEST_SIGNATURE_WARNING: &str = "local-private-devnet-test-signature-only";
const SIGNED_TRANSFER_FORMAT_VERSION: &str = "xriq-local-signed-transfer-envelope-v1";
const TRANSACTION_SIGNING_DOMAIN: &str = "xriq:v1:transaction:signing";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TestIdentity {
    pub label: String,
    pub address: Address,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransferRequest {
    pub chain_id: String,
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransferDraft {
    pub transaction: Transaction,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignedTransferArtifact {
    pub signer_label: String,
    pub signer_address: Address,
    pub draft: TransferDraft,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletBalance {
    pub address: Address,
    pub balance: XriqAmount,
    pub nonce: u64,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletChainStatus {
    pub chain_id: String,
    pub current_height: u64,
    pub latest_block_hash: Hash32,
    pub state_root: Hash32,
    pub pending_transactions: usize,
    pub stored_blocks: usize,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletChainCheck {
    pub verified: bool,
    pub chain_id: String,
    pub current_height: u64,
    pub latest_block_hash: Hash32,
    pub state_root: Hash32,
    pub pending_transactions: usize,
    pub stored_blocks: usize,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletAccountSummary {
    pub address: Address,
    pub balance: XriqAmount,
    pub nonce: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletAccountList {
    pub accounts: Vec<WalletAccountSummary>,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletAccountTransaction {
    pub block_height: u64,
    pub block_hash: Hash32,
    pub transaction_index: usize,
    pub direction: &'static str,
    pub tx_hash: Hash32,
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletAccountHistory {
    pub address: Address,
    pub transactions: Vec<WalletAccountTransaction>,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletConfirmedTransactionStatus {
    pub tx_hash: Hash32,
    pub block_height: u64,
    pub block_hash: Hash32,
    pub transaction_index: usize,
    pub transaction: Transaction,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletPendingTransactionStatus {
    pub tx_hash: Hash32,
    pub received_order: u64,
    pub transaction: Transaction,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletPendingSubmission {
    pub command: &'static str,
    pub tx_hash: Hash32,
    pub received_order: u64,
    pub transaction: Transaction,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletPendingTransaction {
    pub tx_hash: Hash32,
    pub received_order: u64,
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub expires_at_height: Option<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WalletPendingList {
    pub transactions: Vec<WalletPendingTransaction>,
    pub warning: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WalletTransactionStatus {
    Confirmed(WalletConfirmedTransactionStatus),
    Pending(WalletPendingTransactionStatus),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WalletOutput {
    Help(String),
    TestIdentity(TestIdentity),
    AccountList(WalletAccountList),
    AccountListJson(WalletAccountList),
    Balance(WalletBalance),
    BalanceJson(WalletBalance),
    AccountHistory(WalletAccountHistory),
    AccountHistoryJson(WalletAccountHistory),
    PendingList(WalletPendingList),
    PendingListJson(WalletPendingList),
    PendingSubmission(WalletPendingSubmission),
    PendingSubmissionJson(WalletPendingSubmission),
    ChainCheck(WalletChainCheck),
    ChainCheckJson(WalletChainCheck),
    ChainStatus(WalletChainStatus),
    ChainStatusJson(WalletChainStatus),
    TransactionStatus(WalletTransactionStatus),
    TransactionStatusJson(WalletTransactionStatus),
    TransferDraft(TransferDraft),
    TransferSubmitJson(TransferDraft),
    SignedTransferArtifact(SignedTransferArtifact),
    SignedTransferArtifactJson(SignedTransferArtifact),
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WalletError {
    MissingCommand,
    UnknownCommand(String),
    UnknownFlag(String),
    MissingFlag(&'static str),
    DuplicateFlag(String),
    UnexpectedArgument(String),
    InvalidLabel,
    InvalidAddress(AddressError),
    InvalidNumber {
        flag: &'static str,
        value: String,
    },
    InvalidHash {
        flag: &'static str,
        value: String,
    },
    InvalidFormat(String),
    SignerAddressMismatch {
        signer_label: String,
        signer_address: Address,
        from_address: Address,
    },
    Node(String),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum WalletOutputFormat {
    Text,
    Json,
}

impl fmt::Display for WalletError {
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
            Self::InvalidLabel => formatter.write_str("invalid test identity label"),
            Self::InvalidAddress(error) => write!(formatter, "invalid address: {error:?}"),
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
            Self::SignerAddressMismatch {
                signer_label,
                signer_address,
                from_address,
            } => write!(
                formatter,
                "signer label {signer_label} resolves to {signer_address}, not transfer sender {from_address}"
            ),
            Self::Node(message) => write!(formatter, "node error: {message}"),
        }
    }
}

impl fmt::Display for WalletOutput {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Help(help) => formatter.write_str(help),
            Self::TestIdentity(identity) => {
                writeln!(formatter, "warning={}", identity.warning)?;
                writeln!(formatter, "label={}", identity.label)?;
                write!(formatter, "address={}", identity.address)
            }
            Self::AccountList(list) => formatter.write_str(&render_accounts(list)),
            Self::AccountListJson(list) => formatter.write_str(&render_accounts_json(list)),
            Self::Balance(balance) => {
                writeln!(formatter, "warning={}", balance.warning)?;
                writeln!(formatter, "address={}", balance.address)?;
                writeln!(
                    formatter,
                    "balance_base_units={}",
                    balance.balance.base_units()
                )?;
                write!(formatter, "nonce={}", balance.nonce)
            }
            Self::BalanceJson(balance) => formatter.write_str(&render_balance_json(balance)),
            Self::AccountHistory(history) => formatter.write_str(&render_history(history)),
            Self::AccountHistoryJson(history) => formatter.write_str(&render_history_json(history)),
            Self::PendingList(list) => formatter.write_str(&render_pending_list(list)),
            Self::PendingListJson(list) => formatter.write_str(&render_pending_list_json(list)),
            Self::PendingSubmission(submission) => {
                formatter.write_str(&render_pending_submission(submission))
            }
            Self::PendingSubmissionJson(submission) => {
                formatter.write_str(&render_pending_submission_json(submission))
            }
            Self::ChainCheck(check) => formatter.write_str(&render_chain_check(check)),
            Self::ChainCheckJson(check) => formatter.write_str(&render_chain_check_json(check)),
            Self::ChainStatus(status) => formatter.write_str(&render_chain_status(status)),
            Self::ChainStatusJson(status) => formatter.write_str(&render_chain_status_json(status)),
            Self::TransactionStatus(status) => formatter.write_str(&render_tx_status(status)),
            Self::TransactionStatusJson(status) => {
                formatter.write_str(&render_tx_status_json(status))
            }
            Self::TransferDraft(draft) => {
                let tx = &draft.transaction;
                writeln!(formatter, "warning={}", draft.warning)?;
                writeln!(formatter, "version={}", tx.version)?;
                writeln!(formatter, "chain_id={}", tx.chain_id)?;
                writeln!(formatter, "from={}", tx.from)?;
                writeln!(formatter, "to={}", tx.to)?;
                writeln!(formatter, "amount={}", tx.amount.base_units())?;
                writeln!(formatter, "fee={}", tx.fee.base_units())?;
                writeln!(formatter, "nonce={}", tx.nonce)?;
                match tx.expires_at_height {
                    Some(height) => writeln!(formatter, "expires_at_height={height}")?,
                    None => writeln!(formatter, "expires_at_height=")?,
                }
                writeln!(
                    formatter,
                    "transaction_hash={}",
                    hash_hex(transaction_hash(tx))
                )?;
                write!(
                    formatter,
                    "signature_bytes={}",
                    tx.signature.as_slice().len()
                )
            }
            Self::TransferSubmitJson(draft) => {
                formatter.write_str(&render_transfer_submit_json(draft))
            }
            Self::SignedTransferArtifact(artifact) => {
                formatter.write_str(&render_signed_transfer_artifact(artifact))
            }
            Self::SignedTransferArtifactJson(artifact) => {
                formatter.write_str(&render_signed_transfer_artifact_json(artifact))
            }
        }
    }
}

impl WalletOutputFormat {
    fn parse(value: Option<&str>) -> Result<Self, WalletError> {
        match value.unwrap_or("text") {
            "text" => Ok(Self::Text),
            "json" => Ok(Self::Json),
            value => Err(WalletError::InvalidFormat(value.to_string())),
        }
    }
}

pub fn help_text() -> String {
    [
        "xriq-wallet private-devnet commands:",
        "  xriq-wallet key generate --label <lowercase-label>",
        "  xriq-wallet accounts --chain-file <path> [--alice-balance <base-units>] [--limit <count>] [--format text|json]",
        "  xriq-wallet balance --chain-file <path> --address <address> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-wallet history --chain-file <path> --address <address> [--alice-balance <base-units>] [--limit <count>] [--format text|json]",
        "  xriq-wallet pending --chain-file <path> --pending-file <path> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-wallet status --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-wallet check --chain-file <path> [--pending-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-wallet submit --chain-file <path> --pending-file <path> --transfer-file <path> [--alice-balance <base-units>] [--format text|json]",
        "  xriq-wallet send --chain-file <path> --pending-file <path> --chain-id <id> --from <address> --to <address> --amount <base-units> --fee <base-units> --nonce <number|auto> [--alice-balance <base-units>] [--expires-at-height <height>] [--format text|json]",
        "  xriq-wallet tx status --chain-file <path> --tx-hash <64-hex> [--draft-file <path>|--pending-file <path>] [--alice-balance <base-units>] [--format text|json]",
        "  xriq-wallet transfer --chain-id <id> --from <address> --to <address> --amount <base-units> --fee <base-units> --nonce <number|auto> [--chain-file <path>] [--alice-balance <base-units>] [--expires-at-height <height>] [--format text|json]",
        "  xriq-wallet signed-transfer --chain-id <id> --from <address> --to <address> --amount <base-units> --fee <base-units> --nonce <number|auto> --signer-label <lowercase-label> [--chain-file <path>] [--alice-balance <base-units>] [--expires-at-height <height>] [--format text|json]",
        "",
        "Warning: this wallet is for private devnet tests only and does not manage real keys.",
    ]
    .join("\n")
}

pub fn run_wallet_command<I, S>(args: I) -> Result<WalletOutput, WalletError>
where
    I: IntoIterator<Item = S>,
    S: AsRef<str>,
{
    let args: Vec<String> = args
        .into_iter()
        .map(|argument| argument.as_ref().to_string())
        .collect();
    match args.first().map(String::as_str) {
        None => Err(WalletError::MissingCommand),
        Some("help" | "--help" | "-h") => Ok(WalletOutput::Help(help_text())),
        Some("key") => run_key_command(&args[1..]),
        Some("accounts") => run_accounts_command(&args[1..]),
        Some("balance") => run_balance_command(&args[1..]),
        Some("history") => run_history_command(&args[1..]),
        Some("pending") => run_pending_command(&args[1..]),
        Some("status") => run_status_command(&args[1..]),
        Some("check") => run_check_command(&args[1..]),
        Some("submit") => run_submit_command(&args[1..]),
        Some("send") => run_send_command(&args[1..]),
        Some("tx") => run_tx_command(&args[1..]),
        Some("transfer") => run_transfer_command(&args[1..]),
        Some("signed-transfer") => run_signed_transfer_command(&args[1..]),
        Some(command) => Err(WalletError::UnknownCommand(command.to_string())),
    }
}

pub fn generate_test_identity(label: &str) -> Result<TestIdentity, WalletError> {
    if !is_valid_label(label) {
        return Err(WalletError::InvalidLabel);
    }

    let mut payload = label.to_string();
    while payload.len() < 16 {
        payload.push('0');
    }
    let address =
        Address::parse(&format!("xriqdev1{payload}")).map_err(WalletError::InvalidAddress)?;
    Ok(TestIdentity {
        label: label.to_string(),
        address,
        warning: TEST_IDENTITY_WARNING,
    })
}

pub fn build_test_transfer(request: TransferRequest) -> TransferDraft {
    let mut transaction = Transaction {
        version: Transaction::SUPPORTED_VERSION,
        chain_id: request.chain_id,
        from: request.from,
        to: request.to,
        amount: request.amount,
        fee: request.fee,
        nonce: request.nonce,
        memo_hash: None,
        expires_at_height: request.expires_at_height,
        signature: SignatureBytes::new(Vec::new()),
    };
    transaction.signature = test_only_signature_for_hash(transaction_signing_hash(&transaction));
    TransferDraft {
        transaction,
        warning: TEST_IDENTITY_WARNING,
    }
}

pub fn build_test_signed_transfer_artifact(
    request: TransferRequest,
    signer_label: &str,
) -> Result<SignedTransferArtifact, WalletError> {
    let signer = generate_test_identity(signer_label)?;
    if signer.address != request.from {
        return Err(WalletError::SignerAddressMismatch {
            signer_label: signer_label.to_string(),
            signer_address: signer.address,
            from_address: request.from,
        });
    }
    Ok(SignedTransferArtifact {
        signer_label: signer_label.to_string(),
        signer_address: signer.address,
        draft: build_test_transfer(request),
        warning: TEST_SIGNATURE_WARNING,
    })
}

fn run_key_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    match args.first().map(String::as_str) {
        Some("generate") => {
            let flags = FlagParser::parse(&args[1..])?;
            flags.reject_unknown(&["--label"])?;
            let label = flags.required("--label")?;
            let identity = generate_test_identity(label)?;
            Ok(WalletOutput::TestIdentity(identity))
        }
        Some(command) => Err(WalletError::UnknownCommand(format!("key {command}"))),
        None => Err(WalletError::MissingCommand),
    }
}

fn run_tx_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    match args.first().map(String::as_str) {
        Some("status") => run_tx_status_command(&args[1..]),
        Some(command) => Err(WalletError::UnknownCommand(format!("tx {command}"))),
        None => Err(WalletError::MissingCommand),
    }
}

fn run_accounts_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--alice-balance", "--limit", "--format"])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
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
    let accounts = private_devnet_file_account_list_data(chain_file, alice_balance, limit)
        .map_err(|error| WalletError::Node(error.to_string()))?
        .into_iter()
        .map(|account| WalletAccountSummary {
            address: account.address,
            balance: account.balance,
            nonce: account.nonce,
        })
        .collect();
    let list = WalletAccountList {
        accounts,
        warning: TEST_IDENTITY_WARNING,
    };
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::AccountList(list),
        WalletOutputFormat::Json => WalletOutput::AccountListJson(list),
    })
}

fn run_balance_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&["--chain-file", "--address", "--alice-balance", "--format"])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let address = parse_address(flags.required("--address")?)?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let account = private_devnet_file_account_detail_data(chain_file, alice_balance, address)
        .map_err(|error| WalletError::Node(error.to_string()))?;
    let balance = WalletBalance {
        address: account.address,
        balance: account.balance,
        nonce: account.nonce,
        warning: TEST_IDENTITY_WARNING,
    };
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::Balance(balance),
        WalletOutputFormat::Json => WalletOutput::BalanceJson(balance),
    })
}

fn run_history_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--address",
        "--alice-balance",
        "--limit",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let address = parse_address(flags.required("--address")?)?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let limit = flags
        .optional("--limit")
        .map(|value| parse_usize("--limit", value))
        .transpose()?
        .unwrap_or(25);
    let transactions = private_devnet_file_account_transactions_data(
        chain_file,
        alice_balance,
        address.clone(),
        limit,
    )
    .map_err(|error| WalletError::Node(error.to_string()))?
    .into_iter()
    .map(|transaction| WalletAccountTransaction {
        block_height: transaction.block_height,
        block_hash: transaction.block_hash,
        transaction_index: transaction.transaction_index,
        direction: transaction.direction,
        tx_hash: transaction.tx_hash,
        from: transaction.from,
        to: transaction.to,
        amount: transaction.amount,
        fee: transaction.fee,
        nonce: transaction.nonce,
        expires_at_height: transaction.expires_at_height,
    })
    .collect();
    let history = WalletAccountHistory {
        address,
        transactions,
        warning: TEST_IDENTITY_WARNING,
    };
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::AccountHistory(history),
        WalletOutputFormat::Json => WalletOutput::AccountHistoryJson(history),
    })
}

fn run_pending_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.required("--pending-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let detail = private_devnet_file_mempool_detail_with_pending_file_data(
        chain_file,
        pending_file,
        alice_balance,
    )
    .map_err(|error| WalletError::Node(error.to_string()))?;
    let list = WalletPendingList {
        transactions: detail
            .transactions
            .into_iter()
            .map(|transaction| WalletPendingTransaction {
                tx_hash: transaction.tx_hash,
                received_order: transaction.received_order,
                from: transaction.from,
                to: transaction.to,
                amount: transaction.amount,
                fee: transaction.fee,
                nonce: transaction.nonce,
                expires_at_height: transaction.expires_at_height,
            })
            .collect(),
        warning: TEST_IDENTITY_WARNING,
    };
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::PendingList(list),
        WalletOutputFormat::Json => WalletOutput::PendingListJson(list),
    })
}

fn run_status_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.optional("--pending-file");
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let status = match pending_file {
        Some(pending_file) => {
            private_devnet_file_status_with_pending_file(chain_file, pending_file, alice_balance)
                .map_err(|error| WalletError::Node(error.to_string()))?
        }
        None => private_devnet_file_status(chain_file, alice_balance)
            .map_err(|error| WalletError::Node(format!("{error:?}")))?,
    };
    let status = wallet_chain_status(status);
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::ChainStatus(status),
        WalletOutputFormat::Json => WalletOutput::ChainStatusJson(status),
    })
}

fn run_check_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.optional("--pending-file");
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let check = private_devnet_file_chain_check(chain_file, pending_file, alice_balance)
        .map_err(|error| WalletError::Node(error.to_string()))?;
    let check = wallet_chain_check(check);
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::ChainCheck(check),
        WalletOutputFormat::Json => WalletOutput::ChainCheckJson(check),
    })
}

fn run_submit_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--transfer-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.required("--pending-file")?;
    let transfer_file = flags.required("--transfer-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let body = fs::read_to_string(transfer_file).map_err(|error| {
        WalletError::Node(format!(
            "could not read transfer file {transfer_file}: {error}"
        ))
    })?;
    let detail = private_devnet_file_submit_pending_transfer_body(
        chain_file,
        pending_file,
        alice_balance,
        &body,
    )
    .map_err(|error| WalletError::Node(error.to_string()))?;
    let submission = wallet_pending_submission(detail, "submit-pending");
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::PendingSubmission(submission),
        WalletOutputFormat::Json => WalletOutput::PendingSubmissionJson(submission),
    })
}

fn run_send_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--pending-file",
        "--chain-id",
        "--from",
        "--to",
        "--amount",
        "--fee",
        "--nonce",
        "--alice-balance",
        "--expires-at-height",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let pending_file = flags.required("--pending-file")?;
    let draft = build_test_transfer(transfer_request_from_flags(&flags)?);
    let body = render_transfer_submit_json(&draft);
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let detail = private_devnet_file_submit_pending_transfer_body(
        chain_file,
        pending_file,
        alice_balance,
        &body,
    )
    .map_err(|error| WalletError::Node(error.to_string()))?;
    let submission = wallet_pending_submission(detail, "send-pending");
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::PendingSubmission(submission),
        WalletOutputFormat::Json => WalletOutput::PendingSubmissionJson(submission),
    })
}

fn run_tx_status_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-file",
        "--tx-hash",
        "--draft-file",
        "--pending-file",
        "--alice-balance",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let chain_file = flags.required("--chain-file")?;
    let tx_hash = parse_hash("--tx-hash", flags.required("--tx-hash")?)?;
    let draft_file = flags.optional("--draft-file");
    let pending_file = flags.optional("--pending-file");
    if draft_file.is_some() && pending_file.is_some() {
        return Err(WalletError::InvalidFormat(
            "--draft-file and --pending-file cannot be used together".to_string(),
        ));
    }
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let detail = match pending_file {
        Some(pending_file) => private_devnet_file_transaction_detail_with_pending_file_data(
            chain_file,
            pending_file,
            alice_balance,
            tx_hash,
        ),
        None => private_devnet_file_transaction_detail_data(
            chain_file,
            draft_file,
            alice_balance,
            tx_hash,
        ),
    }
    .map_err(|error| WalletError::Node(error.to_string()))?;
    let status = wallet_transaction_status(detail);
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::TransactionStatus(status),
        WalletOutputFormat::Json => WalletOutput::TransactionStatusJson(status),
    })
}

fn run_transfer_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-id",
        "--from",
        "--to",
        "--amount",
        "--fee",
        "--nonce",
        "--chain-file",
        "--alice-balance",
        "--expires-at-height",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let draft = build_test_transfer(transfer_request_from_flags(&flags)?);
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::TransferDraft(draft),
        WalletOutputFormat::Json => WalletOutput::TransferSubmitJson(draft),
    })
}

fn run_signed_transfer_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-id",
        "--from",
        "--to",
        "--amount",
        "--fee",
        "--nonce",
        "--signer-label",
        "--chain-file",
        "--alice-balance",
        "--expires-at-height",
        "--format",
    ])?;
    let output_format = WalletOutputFormat::parse(flags.optional("--format"))?;
    let signer_label = flags.required("--signer-label")?;
    let artifact =
        build_test_signed_transfer_artifact(transfer_request_from_flags(&flags)?, signer_label)?;
    Ok(match output_format {
        WalletOutputFormat::Text => WalletOutput::SignedTransferArtifact(artifact),
        WalletOutputFormat::Json => WalletOutput::SignedTransferArtifactJson(artifact),
    })
}

fn transfer_request_from_flags(flags: &FlagParser) -> Result<TransferRequest, WalletError> {
    let chain_id = flags.required("--chain-id")?.to_string();
    let from = parse_address(flags.required("--from")?)?;
    let to = parse_address(flags.required("--to")?)?;
    let amount = parse_amount("--amount", flags.required("--amount")?)?;
    let fee = parse_amount("--fee", flags.required("--fee")?)?;
    let nonce = resolve_transfer_nonce(flags, from.clone())?;
    let expires_at_height = flags
        .optional("--expires-at-height")
        .map(|value| parse_u64("--expires-at-height", value))
        .transpose()?;
    Ok(TransferRequest {
        chain_id,
        from,
        to,
        amount,
        fee,
        nonce,
        expires_at_height,
    })
}

fn resolve_transfer_nonce(flags: &FlagParser, from: Address) -> Result<u64, WalletError> {
    let nonce = flags.required("--nonce")?;
    if nonce != "auto" {
        return parse_u64("--nonce", nonce);
    }
    let chain_file = flags.required("--chain-file")?;
    let alice_balance = flags
        .optional("--alice-balance")
        .map(|value| parse_amount("--alice-balance", value))
        .transpose()?;
    let account = private_devnet_file_account_detail_data(chain_file, alice_balance, from)
        .map_err(|error| WalletError::Node(error.to_string()))?;
    Ok(account.nonce)
}

fn parse_address(value: &str) -> Result<Address, WalletError> {
    Address::parse(value).map_err(WalletError::InvalidAddress)
}

fn parse_amount(flag: &'static str, value: &str) -> Result<XriqAmount, WalletError> {
    Ok(XriqAmount::from_base_units(parse_u128(flag, value)?))
}

fn parse_u64(flag: &'static str, value: &str) -> Result<u64, WalletError> {
    value.parse().map_err(|_| WalletError::InvalidNumber {
        flag,
        value: value.to_string(),
    })
}

fn parse_usize(flag: &'static str, value: &str) -> Result<usize, WalletError> {
    value.parse().map_err(|_| WalletError::InvalidNumber {
        flag,
        value: value.to_string(),
    })
}

fn parse_u128(flag: &'static str, value: &str) -> Result<u128, WalletError> {
    value.parse().map_err(|_| WalletError::InvalidNumber {
        flag,
        value: value.to_string(),
    })
}

fn parse_hash(flag: &'static str, value: &str) -> Result<Hash32, WalletError> {
    parse_hash_hex(value).map_err(|_| WalletError::InvalidHash {
        flag,
        value: value.to_string(),
    })
}

fn parse_hash_hex(value: &str) -> Result<Hash32, ()> {
    if value.len() != 64 || !value.bytes().all(|byte| byte.is_ascii_hexdigit()) {
        return Err(());
    }
    let mut bytes = [0u8; 32];
    for (index, byte) in bytes.iter_mut().enumerate() {
        let high = hex_nibble(value.as_bytes()[index * 2])?;
        let low = hex_nibble(value.as_bytes()[index * 2 + 1])?;
        *byte = (high << 4) | low;
    }
    Ok(Hash32::from_bytes(bytes))
}

fn hex_nibble(byte: u8) -> Result<u8, ()> {
    match byte {
        b'0'..=b'9' => Ok(byte - b'0'),
        b'a'..=b'f' => Ok(byte - b'a' + 10),
        b'A'..=b'F' => Ok(byte - b'A' + 10),
        _ => Err(()),
    }
}

fn is_valid_label(label: &str) -> bool {
    !label.is_empty()
        && label.len() <= 32
        && label
            .chars()
            .all(|character| character.is_ascii_lowercase() || character.is_ascii_digit())
}

fn render_transfer_submit_json(draft: &TransferDraft) -> String {
    let tx = &draft.transaction;
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-node-transfer-submit-v1\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(draft.warning));
    output.push_str(",\n");
    output.push_str("  \"version\": ");
    output.push_str(&tx.version.to_string());
    output.push_str(",\n");
    output.push_str("  \"chain_id\": ");
    output.push_str(&json_string(&tx.chain_id));
    output.push_str(",\n");
    output.push_str("  \"from\": ");
    output.push_str(&json_string(tx.from.as_str()));
    output.push_str(",\n");
    output.push_str("  \"to\": ");
    output.push_str(&json_string(tx.to.as_str()));
    output.push_str(",\n");
    output.push_str("  \"amount_base_units\": ");
    output.push_str(&json_string(&tx.amount.base_units().to_string()));
    output.push_str(",\n");
    output.push_str("  \"fee_base_units\": ");
    output.push_str(&json_string(&tx.fee.base_units().to_string()));
    output.push_str(",\n");
    output.push_str("  \"nonce\": ");
    output.push_str(&tx.nonce.to_string());
    output.push_str(",\n");
    output.push_str("  \"expires_at_height\": ");
    output.push_str(&json_optional_u64(tx.expires_at_height));
    output.push_str(",\n");
    output.push_str("  \"transaction_hash\": ");
    output.push_str(&json_string(&hash_hex(transaction_hash(tx))));
    output.push_str(",\n");
    output.push_str("  \"signature_bytes\": ");
    output.push_str(&tx.signature.as_slice().len().to_string());
    output.push_str("\n}");
    output
}

fn render_signed_transfer_artifact(artifact: &SignedTransferArtifact) -> String {
    let tx = &artifact.draft.transaction;
    let signing_hash = transaction_signing_hash(tx);
    let tx_hash = transaction_hash(tx);
    let mut output = String::new();
    {
        use fmt::Write;
        writeln!(&mut output, "warning={}", artifact.warning).expect("write to String");
        writeln!(
            &mut output,
            "format_version={SIGNED_TRANSFER_FORMAT_VERSION}"
        )
        .expect("write to String");
        writeln!(&mut output, "environment=private-devnet").expect("write to String");
        writeln!(&mut output, "network={}", tx.chain_id).expect("write to String");
        writeln!(&mut output, "signer_label={}", artifact.signer_label).expect("write to String");
        writeln!(&mut output, "signer_address={}", artifact.signer_address)
            .expect("write to String");
        writeln!(&mut output, "version={}", tx.version).expect("write to String");
        writeln!(&mut output, "chain_id={}", tx.chain_id).expect("write to String");
        writeln!(&mut output, "from={}", tx.from).expect("write to String");
        writeln!(&mut output, "to={}", tx.to).expect("write to String");
        writeln!(&mut output, "amount_base_units={}", tx.amount.base_units())
            .expect("write to String");
        writeln!(&mut output, "fee_base_units={}", tx.fee.base_units()).expect("write to String");
        writeln!(&mut output, "nonce={}", tx.nonce).expect("write to String");
        writeln!(
            &mut output,
            "expires_at_height={}",
            tx.expires_at_height
                .map(|height| height.to_string())
                .unwrap_or_default()
        )
        .expect("write to String");
        writeln!(&mut output, "signing_domain={TRANSACTION_SIGNING_DOMAIN}")
            .expect("write to String");
        writeln!(
            &mut output,
            "transaction_signing_hash={}",
            hash_hex(signing_hash)
        )
        .expect("write to String");
        writeln!(&mut output, "transaction_hash={}", hash_hex(tx_hash)).expect("write to String");
        writeln!(&mut output, "signature_algorithm=test-only").expect("write to String");
        writeln!(
            &mut output,
            "signature_algorithm_id={}",
            SignatureAlgorithm::TestOnly.id()
        )
        .expect("write to String");
        writeln!(
            &mut output,
            "signature_bytes={}",
            tx.signature.as_slice().len()
        )
        .expect("write to String");
        writeln!(
            &mut output,
            "verification=TestOnlySignatureVerifier.verify_transaction"
        )
        .expect("write to String");
        writeln!(
            &mut output,
            "submit_endpoint=POST /api/v1/wallet/transfers/submit-signed"
        )
        .expect("write to String");
        writeln!(
            &mut output,
            "required_enablement=--enable-local-wallet-submit-signed"
        )
        .expect("write to String");
        writeln!(&mut output, "mutation_when_disabled=none").expect("write to String");
        writeln!(&mut output, "mutation_when_accepted=pending_state_only")
            .expect("write to String");
        write!(
            &mut output,
            "scope=local-private-devnet-test-identity-only-no-custody-no-browser-keys"
        )
        .expect("write to String");
    }
    output
}

fn render_signed_transfer_artifact_json(artifact: &SignedTransferArtifact) -> String {
    let tx = &artifact.draft.transaction;
    let signing_hash = hash_hex(transaction_signing_hash(tx));
    let tx_hash = hash_hex(transaction_hash(tx));
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": ");
    output.push_str(&json_string(SIGNED_TRANSFER_FORMAT_VERSION));
    output.push_str(",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(artifact.warning));
    output.push_str(",\n");
    output.push_str("  \"environment\": \"private-devnet\",\n");
    output.push_str("  \"network\": ");
    output.push_str(&json_string(&tx.chain_id));
    output.push_str(",\n");
    output.push_str("  \"scope\": {\n");
    output.push_str("    \"local_private_only\": true,\n");
    output.push_str("    \"test_identity_only\": true,\n");
    output.push_str("    \"non_mutating\": true,\n");
    output.push_str("    \"browser_key_material_allowed\": false,\n");
    output.push_str("    \"custody_allowed\": false,\n");
    output.push_str("    \"public_network_allowed\": false,\n");
    output.push_str("    \"dex_allowed\": false,\n");
    output.push_str("    \"production_infrastructure_allowed\": false\n");
    output.push_str("  },\n");
    output.push_str("  \"signer\": {\n");
    output.push_str("    \"label\": ");
    output.push_str(&json_string(&artifact.signer_label));
    output.push_str(",\n");
    output.push_str("    \"address\": ");
    output.push_str(&json_string(artifact.signer_address.as_str()));
    output.push_str(",\n");
    output.push_str("    \"role\": \"local-test-identity-label\"\n");
    output.push_str("  },\n");
    output.push_str("  \"transaction\": {\n");
    output.push_str("    \"version\": ");
    output.push_str(&tx.version.to_string());
    output.push_str(",\n");
    output.push_str("    \"chain_id\": ");
    output.push_str(&json_string(&tx.chain_id));
    output.push_str(",\n");
    output.push_str("    \"from\": ");
    output.push_str(&json_string(tx.from.as_str()));
    output.push_str(",\n");
    output.push_str("    \"to\": ");
    output.push_str(&json_string(tx.to.as_str()));
    output.push_str(",\n");
    output.push_str("    \"amount_base_units\": ");
    output.push_str(&json_string(&tx.amount.base_units().to_string()));
    output.push_str(",\n");
    output.push_str("    \"fee_base_units\": ");
    output.push_str(&json_string(&tx.fee.base_units().to_string()));
    output.push_str(",\n");
    output.push_str("    \"nonce\": ");
    output.push_str(&tx.nonce.to_string());
    output.push_str(",\n");
    output.push_str("    \"memo_hash\": null,\n");
    output.push_str("    \"expires_at_height\": ");
    output.push_str(&json_optional_u64(tx.expires_at_height));
    output.push_str("\n");
    output.push_str("  },\n");
    output.push_str("  \"hashes\": {\n");
    output.push_str("    \"signing_domain\": ");
    output.push_str(&json_string(TRANSACTION_SIGNING_DOMAIN));
    output.push_str(",\n");
    output.push_str("    \"signing_hash_algorithm\": \"sha256\",\n");
    output.push_str("    \"transaction_hash_algorithm\": \"sha256\",\n");
    output.push_str("    \"transaction_signing_hash\": ");
    output.push_str(&json_string(&signing_hash));
    output.push_str(",\n");
    output.push_str("    \"transaction_hash\": ");
    output.push_str(&json_string(&tx_hash));
    output.push_str("\n");
    output.push_str("  },\n");
    output.push_str("  \"signature_envelope\": {\n");
    output.push_str("    \"algorithm\": \"test-only\",\n");
    output.push_str("    \"algorithm_id\": ");
    output.push_str(&SignatureAlgorithm::TestOnly.id().to_string());
    output.push_str(",\n");
    output.push_str("    \"public_key_role\": \"local-test-identity-label\",\n");
    output.push_str("    \"public_key_hint\": ");
    output.push_str(&json_string(&artifact.signer_label));
    output.push_str(",\n");
    output.push_str("    \"signature_encoding\": \"test-only-prefix-plus-signing-hash\",\n");
    output.push_str("    \"signature_bytes_length\": ");
    output.push_str(&tx.signature.as_slice().len().to_string());
    output.push_str(",\n");
    output.push_str("    \"verification\": \"TestOnlySignatureVerifier.verify_transaction\"\n");
    output.push_str("  },\n");
    output.push_str("  \"submit_request_preview\": {\n");
    output.push_str("    \"endpoint\": \"POST /api/v1/wallet/transfers/submit-signed\",\n");
    output.push_str("    \"required_enablement\": \"--enable-local-wallet-submit-signed\",\n");
    output.push_str("    \"mutation_when_disabled\": \"none\",\n");
    output.push_str("    \"mutation_when_accepted\": \"pending_state_only\",\n");
    output.push_str("    \"audit_event_required\": true\n");
    output.push_str("  },\n");
    output.push_str("  \"forbidden_fields\": [\n");
    output.push_str("    \"private_key\",\n");
    output.push_str("    \"seed_phrase\",\n");
    output.push_str("    \"mnemonic\",\n");
    output.push_str("    \"secret_key\",\n");
    output.push_str("    \"raw_signature\",\n");
    output.push_str("    \"custody_account\",\n");
    output.push_str("    \"public_network_endpoint\",\n");
    output.push_str("    \"dex_route\"\n");
    output.push_str("  ]\n");
    output.push_str("}");
    output
}

fn wallet_transaction_status(detail: PrivateDevnetTransactionDetail) -> WalletTransactionStatus {
    match detail {
        PrivateDevnetTransactionDetail::Confirmed(detail) => {
            WalletTransactionStatus::Confirmed(WalletConfirmedTransactionStatus {
                tx_hash: detail.tx_hash,
                block_height: detail.block_height,
                block_hash: detail.block_hash,
                transaction_index: detail.transaction_index,
                transaction: detail.transaction,
            })
        }
        PrivateDevnetTransactionDetail::Pending(detail) => {
            WalletTransactionStatus::Pending(WalletPendingTransactionStatus {
                tx_hash: detail.tx_hash,
                received_order: detail.received_order,
                transaction: detail.transaction,
            })
        }
    }
}

fn wallet_pending_submission(
    detail: PrivateDevnetPendingTransactionDetail,
    command: &'static str,
) -> WalletPendingSubmission {
    WalletPendingSubmission {
        command,
        tx_hash: detail.tx_hash,
        received_order: detail.received_order,
        transaction: detail.transaction,
        warning: TEST_IDENTITY_WARNING,
    }
}

fn wallet_chain_status(status: NodeStatus) -> WalletChainStatus {
    WalletChainStatus {
        chain_id: status.chain_id,
        current_height: status.current_height,
        latest_block_hash: status.latest_block_hash,
        state_root: status.state_root,
        pending_transactions: status.pending_transactions,
        stored_blocks: status.stored_blocks,
        warning: TEST_IDENTITY_WARNING,
    }
}

fn wallet_chain_check(status: PrivateDevnetChainCheckStatus) -> WalletChainCheck {
    let verified = status.verified;
    let status = wallet_chain_status(status.status);
    WalletChainCheck {
        verified,
        chain_id: status.chain_id,
        current_height: status.current_height,
        latest_block_hash: status.latest_block_hash,
        state_root: status.state_root,
        pending_transactions: status.pending_transactions,
        stored_blocks: status.stored_blocks,
        warning: TEST_IDENTITY_WARNING,
    }
}

fn render_chain_status(status: &WalletChainStatus) -> String {
    let mut output = String::new();
    {
        use fmt::Write;
        writeln!(&mut output, "warning={}", status.warning).expect("write to String");
        writeln!(&mut output, "command=status").expect("write to String");
        writeln!(&mut output, "chain_id={}", status.chain_id).expect("write to String");
        writeln!(&mut output, "current_height={}", status.current_height).expect("write to String");
        writeln!(
            &mut output,
            "latest_block_hash={}",
            hash_hex(status.latest_block_hash)
        )
        .expect("write to String");
        writeln!(&mut output, "state_root={}", hash_hex(status.state_root))
            .expect("write to String");
        writeln!(
            &mut output,
            "pending_transactions={}",
            status.pending_transactions
        )
        .expect("write to String");
        write!(&mut output, "stored_blocks={}", status.stored_blocks).expect("write to String");
    }
    output
}

fn render_chain_status_json(status: &WalletChainStatus) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-wallet-json-v1\",\n");
    output.push_str("  \"command\": \"status\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(status.warning));
    output.push_str(",\n");
    output.push_str("  \"chain_id\": ");
    output.push_str(&json_string(&status.chain_id));
    output.push_str(",\n");
    output.push_str("  \"current_height\": ");
    output.push_str(&status.current_height.to_string());
    output.push_str(",\n");
    output.push_str("  \"latest_block_hash\": ");
    output.push_str(&json_string(&hash_hex(status.latest_block_hash)));
    output.push_str(",\n");
    output.push_str("  \"state_root\": ");
    output.push_str(&json_string(&hash_hex(status.state_root)));
    output.push_str(",\n");
    output.push_str("  \"pending_transactions\": ");
    output.push_str(&status.pending_transactions.to_string());
    output.push_str(",\n");
    output.push_str("  \"stored_blocks\": ");
    output.push_str(&status.stored_blocks.to_string());
    output.push_str("\n}");
    output
}

fn render_chain_check(check: &WalletChainCheck) -> String {
    let mut output = String::new();
    {
        use fmt::Write;
        writeln!(&mut output, "warning={}", check.warning).expect("write to String");
        writeln!(&mut output, "command=check").expect("write to String");
        writeln!(&mut output, "verified={}", check.verified).expect("write to String");
        writeln!(&mut output, "chain_id={}", check.chain_id).expect("write to String");
        writeln!(&mut output, "current_height={}", check.current_height).expect("write to String");
        writeln!(
            &mut output,
            "latest_block_hash={}",
            hash_hex(check.latest_block_hash)
        )
        .expect("write to String");
        writeln!(&mut output, "state_root={}", hash_hex(check.state_root))
            .expect("write to String");
        writeln!(
            &mut output,
            "pending_transactions={}",
            check.pending_transactions
        )
        .expect("write to String");
        write!(&mut output, "stored_blocks={}", check.stored_blocks).expect("write to String");
    }
    output
}

fn render_chain_check_json(check: &WalletChainCheck) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-wallet-json-v1\",\n");
    output.push_str("  \"command\": \"check\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(check.warning));
    output.push_str(",\n");
    output.push_str("  \"verified\": ");
    output.push_str(if check.verified { "true" } else { "false" });
    output.push_str(",\n");
    output.push_str("  \"chain_id\": ");
    output.push_str(&json_string(&check.chain_id));
    output.push_str(",\n");
    output.push_str("  \"current_height\": ");
    output.push_str(&check.current_height.to_string());
    output.push_str(",\n");
    output.push_str("  \"latest_block_hash\": ");
    output.push_str(&json_string(&hash_hex(check.latest_block_hash)));
    output.push_str(",\n");
    output.push_str("  \"state_root\": ");
    output.push_str(&json_string(&hash_hex(check.state_root)));
    output.push_str(",\n");
    output.push_str("  \"pending_transactions\": ");
    output.push_str(&check.pending_transactions.to_string());
    output.push_str(",\n");
    output.push_str("  \"stored_blocks\": ");
    output.push_str(&check.stored_blocks.to_string());
    output.push_str("\n}");
    output
}

fn render_pending_list(list: &WalletPendingList) -> String {
    let mut output = String::new();
    {
        use fmt::Write;
        writeln!(&mut output, "warning={}", list.warning).expect("write to String");
        writeln!(&mut output, "command=pending").expect("write to String");
        writeln!(&mut output, "pending_count={}", list.transactions.len())
            .expect("write to String");
        for transaction in &list.transactions {
            writeln!(
                &mut output,
                "- order={order} {tx_hash} {from} -> {to} amount_base_units={amount} fee_base_units={fee} nonce={nonce}",
                order = transaction.received_order,
                tx_hash = hash_hex(transaction.tx_hash),
                from = transaction.from,
                to = transaction.to,
                amount = transaction.amount.base_units(),
                fee = transaction.fee.base_units(),
                nonce = transaction.nonce,
            )
            .expect("write to String");
        }
    }
    output
}

fn render_pending_list_json(list: &WalletPendingList) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-wallet-json-v1\",\n");
    output.push_str("  \"command\": \"pending\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(list.warning));
    output.push_str(",\n");
    output.push_str("  \"pending_count\": ");
    output.push_str(&list.transactions.len().to_string());
    output.push_str(",\n");
    output.push_str("  \"transactions\": [\n");
    for (index, transaction) in list.transactions.iter().enumerate() {
        push_pending_transaction_json(&mut output, transaction, "    ");
        if index + 1 != list.transactions.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn push_pending_transaction_json(
    output: &mut String,
    transaction: &WalletPendingTransaction,
    indent: &str,
) {
    output.push_str(indent);
    output.push_str("{\n");
    output.push_str(indent);
    output.push_str("  \"tx_hash\": ");
    output.push_str(&json_string(&hash_hex(transaction.tx_hash)));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"received_order\": ");
    output.push_str(&transaction.received_order.to_string());
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"from\": ");
    output.push_str(&json_string(transaction.from.as_str()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"to\": ");
    output.push_str(&json_string(transaction.to.as_str()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"amount_base_units\": ");
    output.push_str(&json_string(&transaction.amount.base_units().to_string()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"fee_base_units\": ");
    output.push_str(&json_string(&transaction.fee.base_units().to_string()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"nonce\": ");
    output.push_str(&transaction.nonce.to_string());
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"expires_at_height\": ");
    output.push_str(&json_optional_u64(transaction.expires_at_height));
    output.push('\n');
    output.push_str(indent);
    output.push('}');
}

fn render_pending_submission(submission: &WalletPendingSubmission) -> String {
    let mut output = String::new();
    {
        use fmt::Write;
        writeln!(&mut output, "warning={}", submission.warning).expect("write to String");
        writeln!(&mut output, "command={}", submission.command).expect("write to String");
        writeln!(&mut output, "status=pending").expect("write to String");
        writeln!(&mut output, "tx_hash={}", hash_hex(submission.tx_hash)).expect("write to String");
        writeln!(&mut output, "received_order={}", submission.received_order)
            .expect("write to String");
    }
    push_transaction_text_fields(&mut output, &submission.transaction);
    output
}

fn render_pending_submission_json(submission: &WalletPendingSubmission) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-wallet-json-v1\",\n");
    output.push_str("  \"command\": ");
    output.push_str(&json_string(submission.command));
    output.push_str(",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(submission.warning));
    output.push_str(",\n");
    output.push_str("  \"status\": \"pending\",\n");
    output.push_str("  \"tx_hash\": ");
    output.push_str(&json_string(&hash_hex(submission.tx_hash)));
    output.push_str(",\n");
    output.push_str("  \"received_order\": ");
    output.push_str(&submission.received_order.to_string());
    output.push_str(",\n");
    push_transaction_json_fields(&mut output, &submission.transaction);
    output.push_str("\n}");
    output
}

fn render_tx_status(status: &WalletTransactionStatus) -> String {
    let mut output = String::new();
    match status {
        WalletTransactionStatus::Confirmed(status) => {
            use fmt::Write;
            writeln!(&mut output, "warning={TEST_IDENTITY_WARNING}").expect("write to String");
            writeln!(&mut output, "status=confirmed").expect("write to String");
            writeln!(&mut output, "tx_hash={}", hash_hex(status.tx_hash)).expect("write to String");
            writeln!(&mut output, "block_height={}", status.block_height).expect("write to String");
            writeln!(&mut output, "block_hash={}", hash_hex(status.block_hash))
                .expect("write to String");
            writeln!(
                &mut output,
                "transaction_index={}",
                status.transaction_index
            )
            .expect("write to String");
            push_transaction_text_fields(&mut output, &status.transaction);
        }
        WalletTransactionStatus::Pending(status) => {
            use fmt::Write;
            writeln!(&mut output, "warning={TEST_IDENTITY_WARNING}").expect("write to String");
            writeln!(&mut output, "status=pending").expect("write to String");
            writeln!(&mut output, "tx_hash={}", hash_hex(status.tx_hash)).expect("write to String");
            writeln!(&mut output, "received_order={}", status.received_order)
                .expect("write to String");
            push_transaction_text_fields(&mut output, &status.transaction);
        }
    }
    output
}

fn push_transaction_text_fields(output: &mut String, transaction: &Transaction) {
    use fmt::Write;
    writeln!(output, "from={}", transaction.from).expect("write to String");
    writeln!(output, "to={}", transaction.to).expect("write to String");
    writeln!(
        output,
        "amount_base_units={}",
        transaction.amount.base_units()
    )
    .expect("write to String");
    writeln!(output, "fee_base_units={}", transaction.fee.base_units()).expect("write to String");
    writeln!(output, "nonce={}", transaction.nonce).expect("write to String");
    write!(
        output,
        "expires_at_height={}",
        transaction
            .expires_at_height
            .map(|height| height.to_string())
            .unwrap_or_default()
    )
    .expect("write to String");
}

fn render_tx_status_json(status: &WalletTransactionStatus) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-wallet-json-v1\",\n");
    output.push_str("  \"command\": \"tx-status\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(TEST_IDENTITY_WARNING));
    output.push_str(",\n");
    match status {
        WalletTransactionStatus::Confirmed(status) => {
            output.push_str("  \"status\": \"confirmed\",\n");
            output.push_str("  \"tx_hash\": ");
            output.push_str(&json_string(&hash_hex(status.tx_hash)));
            output.push_str(",\n");
            output.push_str("  \"block_height\": ");
            output.push_str(&status.block_height.to_string());
            output.push_str(",\n");
            output.push_str("  \"block_hash\": ");
            output.push_str(&json_string(&hash_hex(status.block_hash)));
            output.push_str(",\n");
            output.push_str("  \"transaction_index\": ");
            output.push_str(&status.transaction_index.to_string());
            output.push_str(",\n");
            push_transaction_json_fields(&mut output, &status.transaction);
        }
        WalletTransactionStatus::Pending(status) => {
            output.push_str("  \"status\": \"pending\",\n");
            output.push_str("  \"tx_hash\": ");
            output.push_str(&json_string(&hash_hex(status.tx_hash)));
            output.push_str(",\n");
            output.push_str("  \"received_order\": ");
            output.push_str(&status.received_order.to_string());
            output.push_str(",\n");
            push_transaction_json_fields(&mut output, &status.transaction);
        }
    }
    output.push_str("\n}");
    output
}

fn push_transaction_json_fields(output: &mut String, transaction: &Transaction) {
    output.push_str("  \"from\": ");
    output.push_str(&json_string(transaction.from.as_str()));
    output.push_str(",\n");
    output.push_str("  \"to\": ");
    output.push_str(&json_string(transaction.to.as_str()));
    output.push_str(",\n");
    output.push_str("  \"amount_base_units\": ");
    output.push_str(&json_string(&transaction.amount.base_units().to_string()));
    output.push_str(",\n");
    output.push_str("  \"fee_base_units\": ");
    output.push_str(&json_string(&transaction.fee.base_units().to_string()));
    output.push_str(",\n");
    output.push_str("  \"nonce\": ");
    output.push_str(&transaction.nonce.to_string());
    output.push_str(",\n");
    output.push_str("  \"expires_at_height\": ");
    output.push_str(&json_optional_u64(transaction.expires_at_height));
}

fn render_balance_json(balance: &WalletBalance) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-wallet-json-v1\",\n");
    output.push_str("  \"command\": \"balance\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(balance.warning));
    output.push_str(",\n");
    output.push_str("  \"address\": ");
    output.push_str(&json_string(balance.address.as_str()));
    output.push_str(",\n");
    output.push_str("  \"balance_base_units\": ");
    output.push_str(&json_string(&balance.balance.base_units().to_string()));
    output.push_str(",\n");
    output.push_str("  \"nonce\": ");
    output.push_str(&balance.nonce.to_string());
    output.push_str("\n}");
    output
}

fn render_accounts(list: &WalletAccountList) -> String {
    let mut output = String::new();
    {
        use fmt::Write;
        writeln!(&mut output, "warning={}", list.warning).expect("write to String");
        writeln!(&mut output, "account_count={}", list.accounts.len()).expect("write to String");
        for account in &list.accounts {
            writeln!(
                &mut output,
                "- {address} balance_base_units={balance} nonce={nonce}",
                address = account.address,
                balance = account.balance.base_units(),
                nonce = account.nonce
            )
            .expect("write to String");
        }
    }
    output
}

fn render_accounts_json(list: &WalletAccountList) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-wallet-json-v1\",\n");
    output.push_str("  \"command\": \"accounts\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(list.warning));
    output.push_str(",\n");
    output.push_str("  \"account_count\": ");
    output.push_str(&list.accounts.len().to_string());
    output.push_str(",\n");
    output.push_str("  \"accounts\": [\n");
    for (index, account) in list.accounts.iter().enumerate() {
        push_account_summary_json(&mut output, account, "    ");
        if index + 1 != list.accounts.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn push_account_summary_json(output: &mut String, account: &WalletAccountSummary, indent: &str) {
    output.push_str(indent);
    output.push_str("{\n");
    output.push_str(indent);
    output.push_str("  \"address\": ");
    output.push_str(&json_string(account.address.as_str()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"balance_base_units\": ");
    output.push_str(&json_string(&account.balance.base_units().to_string()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"nonce\": ");
    output.push_str(&account.nonce.to_string());
    output.push('\n');
    output.push_str(indent);
    output.push('}');
}

fn render_history(history: &WalletAccountHistory) -> String {
    let mut output = String::new();
    {
        use fmt::Write;
        writeln!(&mut output, "warning={}", history.warning).expect("write to String");
        writeln!(&mut output, "address={}", history.address).expect("write to String");
        writeln!(
            &mut output,
            "transaction_count={}",
            history.transactions.len()
        )
        .expect("write to String");
        for transaction in &history.transactions {
            writeln!(
                &mut output,
                "- height {height} #{index} {direction} {tx_hash} {from} -> {to} amount={amount} fee={fee} nonce={nonce}",
                height = transaction.block_height,
                index = transaction.transaction_index,
                direction = transaction.direction,
                tx_hash = hash_hex(transaction.tx_hash),
                from = transaction.from,
                to = transaction.to,
                amount = transaction.amount.base_units(),
                fee = transaction.fee.base_units(),
                nonce = transaction.nonce,
            )
            .expect("write to String");
        }
    }
    output
}

fn render_history_json(history: &WalletAccountHistory) -> String {
    let mut output = String::new();
    output.push_str("{\n");
    output.push_str("  \"format_version\": \"xriq-wallet-json-v1\",\n");
    output.push_str("  \"command\": \"history\",\n");
    output.push_str("  \"warning\": ");
    output.push_str(&json_string(history.warning));
    output.push_str(",\n");
    output.push_str("  \"address\": ");
    output.push_str(&json_string(history.address.as_str()));
    output.push_str(",\n");
    output.push_str("  \"transaction_count\": ");
    output.push_str(&history.transactions.len().to_string());
    output.push_str(",\n");
    output.push_str("  \"transactions\": [\n");
    for (index, transaction) in history.transactions.iter().enumerate() {
        push_account_transaction_json(&mut output, transaction, "    ");
        if index + 1 != history.transactions.len() {
            output.push(',');
        }
        output.push('\n');
    }
    output.push_str("  ]\n}");
    output
}

fn push_account_transaction_json(
    output: &mut String,
    transaction: &WalletAccountTransaction,
    indent: &str,
) {
    output.push_str(indent);
    output.push_str("{\n");
    output.push_str(indent);
    output.push_str("  \"block_height\": ");
    output.push_str(&transaction.block_height.to_string());
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"block_hash\": ");
    output.push_str(&json_string(&hash_hex(transaction.block_hash)));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"transaction_index\": ");
    output.push_str(&transaction.transaction_index.to_string());
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"direction\": ");
    output.push_str(&json_string(transaction.direction));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"tx_hash\": ");
    output.push_str(&json_string(&hash_hex(transaction.tx_hash)));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"from\": ");
    output.push_str(&json_string(transaction.from.as_str()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"to\": ");
    output.push_str(&json_string(transaction.to.as_str()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"amount_base_units\": ");
    output.push_str(&json_string(&transaction.amount.base_units().to_string()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"fee_base_units\": ");
    output.push_str(&json_string(&transaction.fee.base_units().to_string()));
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"nonce\": ");
    output.push_str(&transaction.nonce.to_string());
    output.push_str(",\n");
    output.push_str(indent);
    output.push_str("  \"expires_at_height\": ");
    output.push_str(&json_optional_u64(transaction.expires_at_height));
    output.push('\n');
    output.push_str(indent);
    output.push('}');
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
                use fmt::Write;
                write!(&mut output, "\\u{:04x}", character as u32)
                    .expect("writing to String cannot fail");
            }
            character => output.push(character),
        }
    }
    output.push('"');
    output
}

fn hash_hex(hash: xriq_core::Hash32) -> String {
    let mut output = String::with_capacity(64);
    for byte in hash.as_bytes() {
        use fmt::Write;
        write!(&mut output, "{byte:02x}").expect("writing to String cannot fail");
    }
    output
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct FlagParser {
    pairs: Vec<(String, String)>,
}

impl FlagParser {
    fn parse(args: &[String]) -> Result<Self, WalletError> {
        let mut pairs = Vec::new();
        let mut index = 0;
        while index < args.len() {
            let flag = &args[index];
            if !flag.starts_with("--") {
                return Err(WalletError::UnexpectedArgument(flag.clone()));
            }
            let value = args
                .get(index + 1)
                .ok_or_else(|| WalletError::MissingFlag(flag_to_static(flag)))?;
            if value.starts_with("--") {
                return Err(WalletError::MissingFlag(flag_to_static(flag)));
            }
            if pairs.iter().any(|(existing_flag, _)| existing_flag == flag) {
                return Err(WalletError::DuplicateFlag(flag.clone()));
            }
            pairs.push((flag.clone(), value.clone()));
            index += 2;
        }
        Ok(Self { pairs })
    }

    fn required(&self, flag: &'static str) -> Result<&str, WalletError> {
        self.optional(flag).ok_or(WalletError::MissingFlag(flag))
    }

    fn optional(&self, flag: &str) -> Option<&str> {
        self.pairs
            .iter()
            .find(|(candidate, _)| candidate == flag)
            .map(|(_, value)| value.as_str())
    }

    fn reject_unknown(&self, allowed: &[&str]) -> Result<(), WalletError> {
        for (flag, _) in &self.pairs {
            if !allowed.iter().any(|allowed_flag| allowed_flag == flag) {
                return Err(WalletError::UnknownFlag(flag.clone()));
            }
        }
        Ok(())
    }
}

fn flag_to_static(flag: &str) -> &'static str {
    match flag {
        "--label" => "--label",
        "--chain-file" => "--chain-file",
        "--address" => "--address",
        "--alice-balance" => "--alice-balance",
        "--limit" => "--limit",
        "--tx-hash" => "--tx-hash",
        "--draft-file" => "--draft-file",
        "--pending-file" => "--pending-file",
        "--transfer-file" => "--transfer-file",
        "--chain-id" => "--chain-id",
        "--from" => "--from",
        "--to" => "--to",
        "--amount" => "--amount",
        "--fee" => "--fee",
        "--nonce" => "--nonce",
        "--signer-label" => "--signer-label",
        "--expires-at-height" => "--expires-at-height",
        "--format" => "--format",
        _ => "--flag",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::{
        fs,
        time::{SystemTime, UNIX_EPOCH},
    };

    fn alice() -> Address {
        Address::parse("xriqdev1alice00000000000").unwrap()
    }

    fn bob() -> Address {
        Address::parse("xriqdev1bobbb00000000000").unwrap()
    }

    fn fee_sink() -> Address {
        Address::parse("xriqdev1fees000000000000").unwrap()
    }

    fn temp_chain_path() -> std::path::PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time moved backwards")
            .as_nanos();
        std::env::temp_dir().join(format!("xriq-wallet-balance-{nanos}.bin"))
    }

    fn produce_confirmed_transfer(path: &std::path::Path) -> String {
        let path_text = path.to_string_lossy().to_string();
        xriq_node::run_node_command([
            "produce-transfer-block",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
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
        let draft = build_test_transfer(TransferRequest {
            chain_id: "xriq-devnet".to_string(),
            from: alice(),
            to: bob(),
            amount: XriqAmount::from_base_units(25),
            fee: XriqAmount::from_base_units(2),
            nonce: 0,
            expires_at_height: Some(100),
        });
        hash_hex(transaction_hash(&draft.transaction))
    }

    fn temp_draft_path() -> std::path::PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time moved backwards")
            .as_nanos();
        std::env::temp_dir().join(format!("xriq-wallet-draft-{nanos}.txt"))
    }

    fn temp_pending_path() -> std::path::PathBuf {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("time moved backwards")
            .as_nanos();
        std::env::temp_dir().join(format!("xriq-wallet-pending-{nanos}.tsv"))
    }

    #[test]
    fn generates_deterministic_test_identity() {
        assert_eq!(
            generate_test_identity("alice"),
            Ok(TestIdentity {
                label: "alice".to_string(),
                address: alice(),
                warning: TEST_IDENTITY_WARNING,
            })
        );
    }

    #[test]
    fn rejects_invalid_test_identity_label() {
        assert_eq!(
            generate_test_identity("Alice"),
            Err(WalletError::InvalidLabel)
        );
        assert_eq!(generate_test_identity(""), Err(WalletError::InvalidLabel));
    }

    #[test]
    fn builds_private_devnet_transfer_draft() {
        let draft = build_test_transfer(TransferRequest {
            chain_id: "xriq-devnet".to_string(),
            from: alice(),
            to: bob(),
            amount: XriqAmount::from_base_units(25),
            fee: XriqAmount::from_base_units(2),
            nonce: 7,
            expires_at_height: Some(100),
        });

        assert_eq!(draft.transaction.version, Transaction::SUPPORTED_VERSION);
        assert_eq!(draft.transaction.chain_id, "xriq-devnet");
        assert_eq!(draft.transaction.from, alice());
        assert_eq!(draft.transaction.to, bob());
        assert_eq!(draft.transaction.amount, XriqAmount::from_base_units(25));
        assert_eq!(draft.transaction.fee, XriqAmount::from_base_units(2));
        assert_eq!(draft.transaction.nonce, 7);
        assert_eq!(draft.transaction.expires_at_height, Some(100));
        assert!(!draft.transaction.signature.is_empty());
        assert_eq!(
            draft.transaction.signature,
            test_only_signature_for_hash(transaction_signing_hash(&draft.transaction))
        );
    }

    #[test]
    fn parses_key_generate_command() {
        let output = run_wallet_command(["key", "generate", "--label", "alice"]).unwrap();
        assert_eq!(
            output,
            WalletOutput::TestIdentity(TestIdentity {
                label: "alice".to_string(),
                address: alice(),
                warning: TEST_IDENTITY_WARNING,
            })
        );
    }

    #[test]
    fn parses_transfer_command() {
        let output = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "7",
            "--expires-at-height",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::TransferDraft(draft) => {
                assert_eq!(draft.transaction.from, alice());
                assert_eq!(draft.transaction.to, bob());
                assert_eq!(draft.transaction.amount, XriqAmount::from_base_units(25));
                assert_eq!(draft.transaction.nonce, 7);
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }
    }

    #[test]
    fn parses_transfer_command_with_auto_nonce_from_replayed_account() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        produce_confirmed_transfer(&path);
        let output = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "5",
            "--fee",
            "2",
            "--nonce",
            "auto",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--expires-at-height",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::TransferDraft(draft) => {
                assert_eq!(draft.transaction.from, alice());
                assert_eq!(draft.transaction.to, bob());
                assert_eq!(draft.transaction.amount, XriqAmount::from_base_units(5));
                assert_eq!(draft.transaction.nonce, 1);
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let _ = fs::remove_file(path);
    }

    #[test]
    fn builds_test_signed_transfer_artifact() {
        let artifact = build_test_signed_transfer_artifact(
            TransferRequest {
                chain_id: "xriq-devnet".to_string(),
                from: alice(),
                to: bob(),
                amount: XriqAmount::from_base_units(25),
                fee: XriqAmount::from_base_units(2),
                nonce: 7,
                expires_at_height: Some(100),
            },
            "alice",
        )
        .unwrap();

        assert_eq!(artifact.signer_label, "alice");
        assert_eq!(artifact.signer_address, alice());
        assert_eq!(artifact.warning, TEST_SIGNATURE_WARNING);
        assert_eq!(artifact.draft.transaction.from, alice());
        assert_eq!(
            artifact.draft.transaction.signature,
            test_only_signature_for_hash(transaction_signing_hash(&artifact.draft.transaction))
        );
    }

    #[test]
    fn parses_signed_transfer_command_as_json() {
        let output = run_wallet_command([
            "signed-transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "7",
            "--signer-label",
            "alice",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-local-signed-transfer-envelope-v1\""));
        assert!(output.contains("\"warning\": \"local-private-devnet-test-signature-only\""));
        assert!(output.contains("\"from\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"public_key_hint\": \"alice\""));
        assert!(output.contains("\"transaction_signing_hash\": "));
        assert!(output.contains("\"transaction_hash\": "));
        assert!(output.contains("\"algorithm\": \"test-only\""));
        assert!(output.contains("\"signature_bytes_length\": 60"));
        assert!(output.contains("\"mutation_when_disabled\": \"none\""));
        assert!(output.contains("\"mutation_when_accepted\": \"pending_state_only\""));
        assert!(!output.contains("xriq-test-only-signature"));
    }

    #[test]
    fn signed_transfer_text_output_omits_key_material() {
        let output = run_wallet_command([
            "signed-transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "7",
            "--signer-label",
            "alice",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("warning=local-private-devnet-test-signature-only"));
        assert!(output.contains("format_version=xriq-local-signed-transfer-envelope-v1"));
        assert!(output.contains("transaction_signing_hash="));
        assert!(output.contains("transaction_hash="));
        assert!(output.contains("signature_algorithm=test-only"));
        assert!(output.contains("signature_bytes=60"));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));
        assert!(!output.contains("mnemonic"));
        assert!(!output.contains("xriq-test-only-signature"));
    }

    #[test]
    fn signed_transfer_requires_signer_to_match_sender() {
        let output = run_wallet_command([
            "signed-transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "7",
            "--signer-label",
            "bobbb",
        ]);

        assert_eq!(
            output,
            Err(WalletError::SignerAddressMismatch {
                signer_label: "bobbb".to_string(),
                signer_address: bob(),
                from_address: alice(),
            })
        );
    }

    #[test]
    fn rejects_auto_nonce_without_chain_file() {
        assert_eq!(
            run_wallet_command([
                "transfer",
                "--chain-id",
                "xriq-devnet",
                "--from",
                alice().as_str(),
                "--to",
                bob().as_str(),
                "--amount",
                "5",
                "--fee",
                "2",
                "--nonce",
                "auto",
            ]),
            Err(WalletError::MissingFlag("--chain-file"))
        );
    }

    #[test]
    fn parses_submit_command_for_wallet_json_transfer_file() {
        let chain_path = temp_chain_path();
        let transfer_path = temp_draft_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let transfer_text = transfer_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let transfer = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap();
        fs::write(&transfer_path, transfer.to_string()).unwrap();

        let output = run_wallet_command([
            "submit",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--transfer-file",
            transfer_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::PendingSubmission(submission) => {
                assert_eq!(submission.command, "submit-pending");
                assert_eq!(submission.received_order, 0);
                assert_eq!(submission.transaction.from, alice());
                assert_eq!(submission.transaction.to, bob());
                assert_eq!(
                    submission.transaction.amount,
                    XriqAmount::from_base_units(25)
                );
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }
        assert!(fs::read_to_string(&pending_path)
            .unwrap()
            .contains("xriqdev1alice00000000000"));

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(transfer_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn renders_submit_json_and_pending_status() {
        let chain_path = temp_chain_path();
        let transfer_path = temp_draft_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let transfer_text = transfer_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let transfer = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap();
        fs::write(&transfer_path, transfer.to_string()).unwrap();

        let output = run_wallet_command([
            "submit",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--transfer-file",
            transfer_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"submit-pending\""));
        assert!(output.contains("\"status\": \"pending\""));
        assert!(output.contains("\"received_order\": 0"));
        assert!(output.contains("\"from\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"to\": \"xriqdev1bobbb00000000000\""));
        assert!(output.contains("\"amount_base_units\": \"25\""));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(transfer_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn parses_send_command_for_direct_pending_submission() {
        let chain_path = temp_chain_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();

        let output = run_wallet_command([
            "send",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "auto",
            "--alice-balance",
            "100",
            "--expires-at-height",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::PendingSubmission(submission) => {
                assert_eq!(submission.command, "send-pending");
                assert_eq!(submission.received_order, 0);
                assert_eq!(submission.transaction.from, alice());
                assert_eq!(submission.transaction.to, bob());
                assert_eq!(
                    submission.transaction.amount,
                    XriqAmount::from_base_units(25)
                );
                assert_eq!(submission.transaction.fee, XriqAmount::from_base_units(2));
                assert_eq!(submission.transaction.nonce, 0);
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }
        assert!(fs::read_to_string(&pending_path)
            .unwrap()
            .contains("xriqdev1alice00000000000"));

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn renders_send_json_without_secret_material() {
        let chain_path = temp_chain_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();

        let output = run_wallet_command([
            "send",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--alice-balance",
            "100",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"send-pending\""));
        assert!(output.contains("\"status\": \"pending\""));
        assert!(output.contains("\"received_order\": 0"));
        assert!(output.contains("\"from\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"to\": \"xriqdev1bobbb00000000000\""));
        assert!(output.contains("\"amount_base_units\": \"25\""));
        assert!(output.contains("\"nonce\": 0"));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn parses_pending_command_for_durable_pending_file() {
        let chain_path = temp_chain_path();
        let transfer_path = temp_draft_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let transfer_text = transfer_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let transfer = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap();
        fs::write(&transfer_path, transfer.to_string()).unwrap();
        let submitted = run_wallet_command([
            "submit",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--transfer-file",
            transfer_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();
        let tx_hash = match submitted {
            WalletOutput::PendingSubmission(submission) => submission.tx_hash,
            other => panic!("unexpected wallet output: {other:?}"),
        };

        let output = run_wallet_command([
            "pending",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::PendingList(list) => {
                assert_eq!(list.transactions.len(), 1);
                assert_eq!(list.transactions[0].tx_hash, tx_hash);
                assert_eq!(list.transactions[0].received_order, 0);
                assert_eq!(list.transactions[0].from, alice());
                assert_eq!(list.transactions[0].to, bob());
                assert_eq!(list.transactions[0].amount, XriqAmount::from_base_units(25));
                assert_eq!(list.transactions[0].fee, XriqAmount::from_base_units(2));
                assert_eq!(list.transactions[0].nonce, 0);
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(transfer_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn renders_pending_json_without_secret_material() {
        let chain_path = temp_chain_path();
        let transfer_path = temp_draft_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let transfer_text = transfer_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let transfer = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap();
        fs::write(&transfer_path, transfer.to_string()).unwrap();
        run_wallet_command([
            "submit",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--transfer-file",
            transfer_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        let output = run_wallet_command([
            "pending",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"pending\""));
        assert!(output.contains("\"pending_count\": 1"));
        assert!(output.contains("\"received_order\": 0"));
        assert!(output.contains("\"from\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"to\": \"xriqdev1bobbb00000000000\""));
        assert!(output.contains("\"amount_base_units\": \"25\""));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(transfer_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn parses_status_command_for_empty_chain() {
        let chain_path = temp_chain_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let output = run_wallet_command([
            "status",
            "--chain-file",
            chain_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::ChainStatus(status) => {
                assert_eq!(status.chain_id, "xriq-devnet");
                assert_eq!(status.current_height, 0);
                assert_eq!(status.latest_block_hash, Hash32::ZERO);
                assert_eq!(status.pending_transactions, 0);
                assert_eq!(status.stored_blocks, 0);
                assert_eq!(status.warning, TEST_IDENTITY_WARNING);
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let _ = fs::remove_file(chain_path);
    }

    #[test]
    fn renders_status_json_with_pending_count() {
        let chain_path = temp_chain_path();
        let transfer_path = temp_draft_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let transfer_text = transfer_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let transfer = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap();
        fs::write(&transfer_path, transfer.to_string()).unwrap();
        run_wallet_command([
            "submit",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--transfer-file",
            transfer_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        let output = run_wallet_command([
            "status",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"status\""));
        assert!(output.contains("\"chain_id\": \"xriq-devnet\""));
        assert!(output.contains("\"current_height\": 0"));
        assert!(output.contains("\"pending_transactions\": 1"));
        assert!(output.contains("\"stored_blocks\": 0"));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(transfer_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn parses_check_command_for_empty_chain() {
        let chain_path = temp_chain_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let output = run_wallet_command([
            "check",
            "--chain-file",
            chain_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::ChainCheck(check) => {
                assert!(check.verified);
                assert_eq!(check.chain_id, "xriq-devnet");
                assert_eq!(check.current_height, 0);
                assert_eq!(check.latest_block_hash, Hash32::ZERO);
                assert_eq!(check.pending_transactions, 0);
                assert_eq!(check.stored_blocks, 0);
                assert_eq!(check.warning, TEST_IDENTITY_WARNING);
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let _ = fs::remove_file(chain_path);
    }

    #[test]
    fn renders_check_json_with_pending_count() {
        let chain_path = temp_chain_path();
        let transfer_path = temp_draft_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let transfer_text = transfer_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let transfer = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap();
        fs::write(&transfer_path, transfer.to_string()).unwrap();
        run_wallet_command([
            "submit",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--transfer-file",
            transfer_text.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        let output = run_wallet_command([
            "check",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"check\""));
        assert!(output.contains("\"verified\": true"));
        assert!(output.contains("\"chain_id\": \"xriq-devnet\""));
        assert!(output.contains("\"current_height\": 0"));
        assert!(output.contains("\"pending_transactions\": 1"));
        assert!(output.contains("\"stored_blocks\": 0"));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(transfer_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn parses_balance_command() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        let output = run_wallet_command([
            "balance",
            "--chain-file",
            path_text.as_str(),
            "--address",
            alice().as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::Balance(balance) => {
                assert_eq!(balance.address, alice());
                assert_eq!(balance.balance, XriqAmount::from_base_units(100));
                assert_eq!(balance.nonce, 0);
                assert_eq!(balance.warning, TEST_IDENTITY_WARNING);
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let _ = fs::remove_file(path);
    }

    #[test]
    fn renders_balance_json() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        let output = run_wallet_command([
            "balance",
            "--chain-file",
            path_text.as_str(),
            "--address",
            alice().as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"balance\""));
        assert!(output.contains("\"warning\": \"private-devnet-test-identity-only\""));
        assert!(output.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"balance_base_units\": \"100\""));
        assert!(output.contains("\"nonce\": 0"));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn parses_accounts_command_for_confirmed_chain() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        produce_confirmed_transfer(&path);
        let output = run_wallet_command([
            "accounts",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "10",
        ])
        .unwrap();

        match output {
            WalletOutput::AccountList(list) => {
                assert_eq!(list.warning, TEST_IDENTITY_WARNING);
                assert_eq!(list.accounts.len(), 3);
                assert!(list.accounts.iter().any(|account| {
                    account.address == alice()
                        && account.balance == XriqAmount::from_base_units(73)
                        && account.nonce == 1
                }));
                assert!(list.accounts.iter().any(|account| {
                    account.address == bob()
                        && account.balance == XriqAmount::from_base_units(25)
                        && account.nonce == 0
                }));
                assert!(list.accounts.iter().any(|account| {
                    account.address == fee_sink()
                        && account.balance == XriqAmount::from_base_units(2)
                        && account.nonce == 0
                }));
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let _ = fs::remove_file(path);
    }

    #[test]
    fn renders_accounts_json_for_confirmed_chain() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        produce_confirmed_transfer(&path);
        let output = run_wallet_command([
            "accounts",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "10",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"accounts\""));
        assert!(output.contains("\"warning\": \"private-devnet-test-identity-only\""));
        assert!(output.contains("\"account_count\": 3"));
        assert!(output.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"balance_base_units\": \"73\""));
        assert!(output.contains("\"nonce\": 1"));
        assert!(output.contains("\"address\": \"xriqdev1bobbb00000000000\""));
        assert!(output.contains("\"balance_base_units\": \"25\""));
        assert!(output.contains("\"address\": \"xriqdev1fees000000000000\""));
        assert!(output.contains("\"balance_base_units\": \"2\""));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn parses_history_command_for_confirmed_transaction() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        let tx_hash = produce_confirmed_transfer(&path);
        let output = run_wallet_command([
            "history",
            "--chain-file",
            path_text.as_str(),
            "--address",
            alice().as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "5",
        ])
        .unwrap();

        match output {
            WalletOutput::AccountHistory(history) => {
                assert_eq!(history.address, alice());
                assert_eq!(history.warning, TEST_IDENTITY_WARNING);
                assert_eq!(history.transactions.len(), 1);
                let transaction = &history.transactions[0];
                assert_eq!(hash_hex(transaction.tx_hash), tx_hash);
                assert_eq!(transaction.block_height, 1);
                assert_eq!(transaction.transaction_index, 0);
                assert_eq!(transaction.direction, "sent");
                assert_eq!(transaction.from, alice());
                assert_eq!(transaction.to, bob());
                assert_eq!(transaction.amount, XriqAmount::from_base_units(25));
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let _ = fs::remove_file(path);
    }

    #[test]
    fn renders_history_json_for_confirmed_transaction() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        let tx_hash = produce_confirmed_transfer(&path);
        let output = run_wallet_command([
            "history",
            "--chain-file",
            path_text.as_str(),
            "--address",
            alice().as_str(),
            "--alice-balance",
            "100",
            "--limit",
            "5",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"history\""));
        assert!(output.contains("\"warning\": \"private-devnet-test-identity-only\""));
        assert!(output.contains("\"address\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"transaction_count\": 1"));
        assert!(output.contains(&format!("\"tx_hash\": \"{tx_hash}\"")));
        assert!(output.contains("\"block_height\": 1"));
        assert!(output.contains("\"transaction_index\": 0"));
        assert!(output.contains("\"direction\": \"sent\""));
        assert!(output.contains("\"amount_base_units\": \"25\""));
        assert!(output.contains("\"fee_base_units\": \"2\""));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn parses_tx_status_command_for_confirmed_transaction() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        let tx_hash = produce_confirmed_transfer(&path);
        let output = run_wallet_command([
            "tx",
            "status",
            "--chain-file",
            path_text.as_str(),
            "--tx-hash",
            tx_hash.as_str(),
            "--alice-balance",
            "100",
        ])
        .unwrap();

        match output {
            WalletOutput::TransactionStatus(WalletTransactionStatus::Confirmed(status)) => {
                assert_eq!(hash_hex(status.tx_hash), tx_hash);
                assert_eq!(status.block_height, 1);
                assert_eq!(status.transaction_index, 0);
                assert_eq!(status.transaction.from, alice());
                assert_eq!(status.transaction.to, bob());
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let _ = fs::remove_file(path);
    }

    #[test]
    fn renders_tx_status_json_for_confirmed_transaction() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        let tx_hash = produce_confirmed_transfer(&path);
        let output = run_wallet_command([
            "tx",
            "status",
            "--chain-file",
            path_text.as_str(),
            "--tx-hash",
            tx_hash.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"format_version\": \"xriq-wallet-json-v1\""));
        assert!(output.contains("\"command\": \"tx-status\""));
        assert!(output.contains("\"status\": \"confirmed\""));
        assert!(output.contains(&format!("\"tx_hash\": \"{tx_hash}\"")));
        assert!(output.contains("\"block_height\": 1"));
        assert!(output.contains("\"transaction_index\": 0"));
        assert!(output.contains("\"from\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"to\": \"xriqdev1bobbb00000000000\""));
        assert!(output.contains("\"amount_base_units\": \"25\""));
        assert!(output.contains("\"fee_base_units\": \"2\""));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));

        let _ = fs::remove_file(path);
    }

    #[test]
    fn parses_tx_status_command_for_draft_pending_transaction() {
        let chain_path = temp_chain_path();
        let draft_path = temp_draft_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let draft_text = draft_path.to_string_lossy().to_string();
        let draft = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
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
        fs::write(&draft_path, draft.to_string()).unwrap();
        let tx_hash = match draft {
            WalletOutput::TransferDraft(draft) => hash_hex(transaction_hash(&draft.transaction)),
            other => panic!("unexpected wallet output: {other:?}"),
        };

        let output = run_wallet_command([
            "tx",
            "status",
            "--chain-file",
            chain_text.as_str(),
            "--draft-file",
            draft_text.as_str(),
            "--tx-hash",
            tx_hash.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"command\": \"tx-status\""));
        assert!(output.contains("\"status\": \"pending\""));
        assert!(output.contains(&format!("\"tx_hash\": \"{tx_hash}\"")));
        assert!(output.contains("\"received_order\": 0"));
        assert!(output.contains("\"from\": \"xriqdev1alice00000000000\""));
        assert!(output.contains("\"to\": \"xriqdev1bobbb00000000000\""));

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(draft_path);
    }

    #[test]
    fn rejects_invalid_tx_status_hash() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        assert_eq!(
            run_wallet_command([
                "tx",
                "status",
                "--chain-file",
                path_text.as_str(),
                "--tx-hash",
                "not-a-hash",
            ]),
            Err(WalletError::InvalidHash {
                flag: "--tx-hash",
                value: "not-a-hash".to_string(),
            })
        );

        let _ = fs::remove_file(path);
    }

    #[test]
    fn renders_transfer_submit_json_for_node_post_body() {
        let output = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "7",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap();

        match &output {
            WalletOutput::TransferSubmitJson(draft) => {
                assert_eq!(draft.transaction.from, alice());
                assert_eq!(draft.transaction.to, bob());
            }
            other => panic!("unexpected wallet output: {other:?}"),
        }

        let json = output.to_string();
        assert!(json.contains("\"format_version\": \"xriq-node-transfer-submit-v1\""));
        assert!(json.contains("\"warning\": \"private-devnet-test-identity-only\""));
        assert!(json.contains("\"version\": 1"));
        assert!(json.contains("\"chain_id\": \"xriq-devnet\""));
        assert!(json.contains("\"from\": \"xriqdev1alice00000000000\""));
        assert!(json.contains("\"to\": \"xriqdev1bobbb00000000000\""));
        assert!(json.contains("\"amount_base_units\": \"25\""));
        assert!(json.contains("\"fee_base_units\": \"2\""));
        assert!(json.contains("\"nonce\": 7"));
        assert!(json.contains("\"expires_at_height\": 100"));
        assert!(json.contains("\"transaction_hash\":"));
        assert!(json.contains("\"signature_bytes\":"));
        assert!(!json.contains("private_key"));
        assert!(!json.contains("seed"));
        assert!(!json.contains("xriq-test-only-signature"));
    }

    #[test]
    fn transfer_submit_json_matches_checked_fixture() {
        let output = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture = include_str!("../../../fixtures/private-devnet/wallet-transfer-submit.json");

        assert_eq!(output.trim_end(), fixture.trim_end());
    }

    #[test]
    fn wallet_chain_check_json_matches_checked_fixture() {
        let path = temp_chain_path();
        let path_text = path.to_string_lossy().to_string();
        let output = run_wallet_command([
            "check",
            "--chain-file",
            path_text.as_str(),
            "--alice-balance",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture =
            include_str!("../../../fixtures/private-devnet/wallet-chain-check-empty.json");

        assert_eq!(output.trim_end(), fixture.trim_end());

        let _ = fs::remove_file(path);
    }

    #[test]
    fn wallet_send_json_matches_checked_fixture() {
        let chain_path = temp_chain_path();
        let pending_path = temp_pending_path();
        let chain_text = chain_path.to_string_lossy().to_string();
        let pending_text = pending_path.to_string_lossy().to_string();
        let output = run_wallet_command([
            "send",
            "--chain-file",
            chain_text.as_str(),
            "--pending-file",
            pending_text.as_str(),
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "0",
            "--alice-balance",
            "100",
            "--expires-at-height",
            "100",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();
        let fixture = include_str!("../../../fixtures/private-devnet/wallet-send-pending.json");

        assert_eq!(output.trim_end(), fixture.trim_end());

        let _ = fs::remove_file(chain_path);
        let _ = fs::remove_file(pending_path);
    }

    #[test]
    fn renders_json_transfer_expiration_as_null_when_absent() {
        let output = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "7",
            "--format",
            "json",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("\"expires_at_height\": null"));
    }

    #[test]
    fn rejects_missing_required_transfer_flag() {
        assert_eq!(
            run_wallet_command(["transfer", "--chain-id", "xriq-devnet"]),
            Err(WalletError::MissingFlag("--from"))
        );
    }

    #[test]
    fn rejects_duplicate_flags() {
        assert_eq!(
            run_wallet_command(["key", "generate", "--label", "alice", "--label", "bobbb",]),
            Err(WalletError::DuplicateFlag("--label".to_string()))
        );
    }

    #[test]
    fn rejects_unknown_flags() {
        assert_eq!(
            run_wallet_command(["key", "generate", "--label", "alice", "--network", "dev"]),
            Err(WalletError::UnknownFlag("--network".to_string()))
        );
    }

    #[test]
    fn rejects_invalid_transfer_output_format() {
        assert_eq!(
            run_wallet_command([
                "transfer",
                "--chain-id",
                "xriq-devnet",
                "--from",
                alice().as_str(),
                "--to",
                bob().as_str(),
                "--amount",
                "25",
                "--fee",
                "2",
                "--nonce",
                "7",
                "--format",
                "xml",
            ]),
            Err(WalletError::InvalidFormat("xml".to_string()))
        );
    }

    #[test]
    fn renders_transfer_output_without_private_key_material() {
        let output = run_wallet_command([
            "transfer",
            "--chain-id",
            "xriq-devnet",
            "--from",
            alice().as_str(),
            "--to",
            bob().as_str(),
            "--amount",
            "25",
            "--fee",
            "2",
            "--nonce",
            "7",
        ])
        .unwrap()
        .to_string();

        assert!(output.contains("warning=private-devnet-test-identity-only"));
        assert!(output.contains("transaction_hash="));
        assert!(output.contains("signature_bytes="));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));
        assert!(!output.contains("xriq-test-only-signature"));
    }
}
