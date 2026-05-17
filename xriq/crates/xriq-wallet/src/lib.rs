//! Private-devnet wallet CLI behavior for XRIQ.
//!
//! This crate deliberately uses deterministic test identities and fake
//! signatures. It is not production key management.

use std::fmt;

use xriq_core::{Address, AddressError, SignatureBytes, Transaction, XriqAmount};
use xriq_crypto::{test_only_signature_for_hash, transaction_signing_hash};

const TEST_IDENTITY_WARNING: &str = "private-devnet-test-identity-only";

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
pub enum WalletOutput {
    Help(String),
    TestIdentity(TestIdentity),
    TransferDraft(TransferDraft),
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
    InvalidNumber { flag: &'static str, value: String },
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
                write!(
                    formatter,
                    "signature_bytes={}",
                    tx.signature.as_slice().len()
                )
            }
        }
    }
}

pub fn help_text() -> String {
    [
        "xriq-wallet private-devnet commands:",
        "  xriq-wallet key generate --label <lowercase-label>",
        "  xriq-wallet transfer --chain-id <id> --from <address> --to <address> --amount <base-units> --fee <base-units> --nonce <number> [--expires-at-height <height>]",
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
        Some("transfer") => run_transfer_command(&args[1..]),
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

fn run_transfer_command(args: &[String]) -> Result<WalletOutput, WalletError> {
    let flags = FlagParser::parse(args)?;
    flags.reject_unknown(&[
        "--chain-id",
        "--from",
        "--to",
        "--amount",
        "--fee",
        "--nonce",
        "--expires-at-height",
    ])?;
    let chain_id = flags.required("--chain-id")?.to_string();
    let from = parse_address(flags.required("--from")?)?;
    let to = parse_address(flags.required("--to")?)?;
    let amount = parse_amount("--amount", flags.required("--amount")?)?;
    let fee = parse_amount("--fee", flags.required("--fee")?)?;
    let nonce = parse_u64("--nonce", flags.required("--nonce")?)?;
    let expires_at_height = flags
        .optional("--expires-at-height")
        .map(|value| parse_u64("--expires-at-height", value))
        .transpose()?;
    let draft = build_test_transfer(TransferRequest {
        chain_id,
        from,
        to,
        amount,
        fee,
        nonce,
        expires_at_height,
    });
    Ok(WalletOutput::TransferDraft(draft))
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

fn parse_u128(flag: &'static str, value: &str) -> Result<u128, WalletError> {
    value.parse().map_err(|_| WalletError::InvalidNumber {
        flag,
        value: value.to_string(),
    })
}

fn is_valid_label(label: &str) -> bool {
    !label.is_empty()
        && label.len() <= 32
        && label
            .chars()
            .all(|character| character.is_ascii_lowercase() || character.is_ascii_digit())
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
        "--chain-id" => "--chain-id",
        "--from" => "--from",
        "--to" => "--to",
        "--amount" => "--amount",
        "--fee" => "--fee",
        "--nonce" => "--nonce",
        "--expires-at-height" => "--expires-at-height",
        _ => "--flag",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn alice() -> Address {
        Address::parse("xriqdev1alice00000000000").unwrap()
    }

    fn bob() -> Address {
        Address::parse("xriqdev1bobbb00000000000").unwrap()
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
        assert!(output.contains("signature_bytes="));
        assert!(!output.contains("private_key"));
        assert!(!output.contains("seed"));
        assert!(!output.contains("xriq-test-only-signature"));
    }
}
