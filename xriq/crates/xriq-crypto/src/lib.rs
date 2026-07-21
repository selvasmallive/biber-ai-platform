//! Canonical hashing and crypto-agility boundaries for XRIQ.
//!
//! This crate uses reviewed hashing primitives from dependencies and keeps the
//! current fake private-devnet signature behavior behind an explicit test-only
//! verifier. It now also provides a production Ed25519 verification primitive
//! (`Ed25519Verifier`, via the audited `ed25519-dalek`) as Phase 1 of the
//! production-crypto migration (`docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`); that
//! primitive is NOT yet wired into the node/consensus/wallet, and this crate still
//! provides no production key custody.

use core::fmt::Write as _;
use sha2::{Digest, Sha256};
use xriq_core::{
    AccountStateEntry, Address, Block, BlockHeader, Hash32, SignatureBytes, Transaction,
};

const DOMAIN_TRANSACTION_SIGNING: &[u8] = b"xriq:v1:transaction:signing";
const DOMAIN_TRANSACTION_HASH: &[u8] = b"xriq:v1:transaction:hash";
const DOMAIN_BLOCK_HEADER_SIGNING: &[u8] = b"xriq:v1:block-header:signing";
const DOMAIN_BLOCK_HEADER_HASH: &[u8] = b"xriq:v1:block-header:hash";
const DOMAIN_TRANSACTIONS_ROOT: &[u8] = b"xriq:v1:transactions-root";
const DOMAIN_ACCOUNT_STATE_ROOT: &[u8] = b"xriq:v1:account-state-root";

pub const TEST_ONLY_SIGNATURE_PREFIX: &[u8] = b"xriq-test-only-signature-v1:";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SignatureAlgorithm {
    TestOnly,
    Ed25519,
    Secp256k1,
    HybridPostQuantumReserved,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SignatureAlgorithmError {
    UnknownAlgorithmId(u16),
}

impl SignatureAlgorithm {
    pub const fn id(self) -> u16 {
        match self {
            Self::TestOnly => 0,
            Self::Ed25519 => 1,
            Self::Secp256k1 => 2,
            Self::HybridPostQuantumReserved => 250,
        }
    }

    pub const fn from_id(id: u16) -> Result<Self, SignatureAlgorithmError> {
        match id {
            0 => Ok(Self::TestOnly),
            1 => Ok(Self::Ed25519),
            2 => Ok(Self::Secp256k1),
            250 => Ok(Self::HybridPostQuantumReserved),
            other => Err(SignatureAlgorithmError::UnknownAlgorithmId(other)),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignatureEnvelope {
    pub algorithm: SignatureAlgorithm,
    pub public_key: Vec<u8>,
    pub signature: SignatureBytes,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SignatureVerificationError {
    UnsupportedAlgorithm,
    MissingSignature,
    InvalidSignature,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct TestOnlySignatureVerifier;

impl TestOnlySignatureVerifier {
    pub fn verify_hash(
        &self,
        message_hash: Hash32,
        signature: &SignatureBytes,
    ) -> Result<(), SignatureVerificationError> {
        if signature.is_empty() {
            return Err(SignatureVerificationError::MissingSignature);
        }
        if signature == &test_only_signature_for_hash(message_hash) {
            Ok(())
        } else {
            Err(SignatureVerificationError::InvalidSignature)
        }
    }

    pub fn verify_transaction(
        &self,
        transaction: &Transaction,
    ) -> Result<(), SignatureVerificationError> {
        self.verify_hash(
            transaction_signing_hash(transaction),
            &transaction.signature,
        )
    }

    pub fn verify_block_header(
        &self,
        header: &BlockHeader,
    ) -> Result<(), SignatureVerificationError> {
        self.verify_hash(block_header_signing_hash(header), &header.signature)
    }

    pub fn verify_envelope(
        &self,
        message_hash: Hash32,
        envelope: &SignatureEnvelope,
    ) -> Result<(), SignatureVerificationError> {
        if envelope.algorithm != SignatureAlgorithm::TestOnly {
            return Err(SignatureVerificationError::UnsupportedAlgorithm);
        }
        self.verify_hash(message_hash, &envelope.signature)
    }
}

pub fn test_only_signature_for_hash(message_hash: Hash32) -> SignatureBytes {
    let mut bytes = TEST_ONLY_SIGNATURE_PREFIX.to_vec();
    bytes.extend_from_slice(message_hash.as_bytes());
    SignatureBytes::new(bytes)
}

/// Production Ed25519 signature verification (Phase 1 primitive). This is NOT yet
/// wired into the node/consensus/wallet — it coexists with the test-only verifier
/// during migration; see `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`. Backed by the
/// audited `ed25519-dalek`; no custom cryptography.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Ed25519Verifier;

impl Ed25519Verifier {
    /// Verify a 64-byte Ed25519 signature over the 32-byte signing hash for the
    /// given 32-byte public key. Malformed key/signature bytes are rejected as
    /// `InvalidSignature` (never panic); `verify_strict` rejects known
    /// malleability / small-order edge cases.
    pub fn verify_hash(
        &self,
        message_hash: Hash32,
        public_key: &[u8],
        signature: &SignatureBytes,
    ) -> Result<(), SignatureVerificationError> {
        if signature.is_empty() {
            return Err(SignatureVerificationError::MissingSignature);
        }
        let key_bytes: [u8; 32] = public_key
            .try_into()
            .map_err(|_| SignatureVerificationError::InvalidSignature)?;
        let verifying_key = ed25519_dalek::VerifyingKey::from_bytes(&key_bytes)
            .map_err(|_| SignatureVerificationError::InvalidSignature)?;
        let sig_bytes: [u8; 64] = signature
            .as_slice()
            .try_into()
            .map_err(|_| SignatureVerificationError::InvalidSignature)?;
        let signature = ed25519_dalek::Signature::from_bytes(&sig_bytes);
        verifying_key
            .verify_strict(message_hash.as_bytes(), &signature)
            .map_err(|_| SignatureVerificationError::InvalidSignature)
    }
}

/// Deterministically derive an Ed25519 signing key from a 32-byte seed. TEST /
/// key-management helper; a real deployment loads keys from a gitignored key file
/// or KMS, never from source. TEST-ONLY seeds must never guard value.
pub fn ed25519_signing_key_from_seed(seed: [u8; 32]) -> ed25519_dalek::SigningKey {
    ed25519_dalek::SigningKey::from_bytes(&seed)
}

/// The 32-byte public key for a signing key.
pub fn ed25519_public_key(signing_key: &ed25519_dalek::SigningKey) -> [u8; 32] {
    signing_key.verifying_key().to_bytes()
}

/// Sign a 32-byte signing hash, returning the 64-byte Ed25519 signature.
pub fn ed25519_sign_hash(
    signing_key: &ed25519_dalek::SigningKey,
    message_hash: Hash32,
) -> SignatureBytes {
    use ed25519_dalek::Signer;
    SignatureBytes::new(
        signing_key
            .sign(message_hash.as_bytes())
            .to_bytes()
            .to_vec(),
    )
}

const ED25519_ADDRESS_DOMAIN: &[u8] = b"xriq:v1:ed25519-address";
const ED25519_ADDRESS_PREFIX: &str = "xriqdev1";
const ED25519_ADDRESS_PAYLOAD_BYTES: usize = 20;

/// Derive a canonical address from an Ed25519 public key: the `xriqdev1` prefix
/// plus 20 bytes of a domain-separated SHA-256 of the key as lowercase hex (a 40
/// char payload). The address is a pure function of the public key — verifiable
/// offline — which is how a signature will later be checked against the `from`
/// address. Part of the production-crypto migration (Phase 2); not yet used for
/// on-chain identity. See `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`.
pub fn ed25519_address(public_key: &[u8; 32]) -> Address {
    let mut preimage = Vec::with_capacity(ED25519_ADDRESS_DOMAIN.len() + public_key.len());
    preimage.extend_from_slice(ED25519_ADDRESS_DOMAIN);
    preimage.extend_from_slice(public_key);
    let hash = digest(&preimage);
    let mut value = String::from(ED25519_ADDRESS_PREFIX);
    for byte in &hash.as_bytes()[..ED25519_ADDRESS_PAYLOAD_BYTES] {
        write!(value, "{byte:02x}").expect("writing hex to String cannot fail");
    }
    Address::parse(&value).expect("derived ed25519 address is a valid xriq address")
}

/// A signature scheme: verify a `SignatureEnvelope` (algorithm + public key +
/// signature) against a message hash. This is the crypto-agility seam of the
/// production-crypto migration (Phase 3): the node/consensus/faucet select a
/// scheme (see `SignatureSchemeKind`) and verify through this one interface,
/// letting the test-only and Ed25519 paths coexist during migration. Not yet
/// wired into transaction/block verification (that needs a public key on the
/// Transaction — Phase 3b). See `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`.
pub trait SignatureScheme {
    fn algorithm(&self) -> SignatureAlgorithm;
    fn verify_envelope(
        &self,
        message_hash: Hash32,
        envelope: &SignatureEnvelope,
    ) -> Result<(), SignatureVerificationError>;
}

/// The placeholder scheme — verifies the deterministic test-only signature. NOT
/// secure; only for `--network devnet` and unit tests.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct TestOnlyScheme;

impl SignatureScheme for TestOnlyScheme {
    fn algorithm(&self) -> SignatureAlgorithm {
        SignatureAlgorithm::TestOnly
    }

    fn verify_envelope(
        &self,
        message_hash: Hash32,
        envelope: &SignatureEnvelope,
    ) -> Result<(), SignatureVerificationError> {
        if envelope.algorithm != SignatureAlgorithm::TestOnly {
            return Err(SignatureVerificationError::UnsupportedAlgorithm);
        }
        TestOnlySignatureVerifier.verify_hash(message_hash, &envelope.signature)
    }
}

/// The production Ed25519 scheme — verifies the envelope's signature against its
/// public key via the audited `ed25519-dalek`.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct Ed25519Scheme;

impl SignatureScheme for Ed25519Scheme {
    fn algorithm(&self) -> SignatureAlgorithm {
        SignatureAlgorithm::Ed25519
    }

    fn verify_envelope(
        &self,
        message_hash: Hash32,
        envelope: &SignatureEnvelope,
    ) -> Result<(), SignatureVerificationError> {
        if envelope.algorithm != SignatureAlgorithm::Ed25519 {
            return Err(SignatureVerificationError::UnsupportedAlgorithm);
        }
        Ed25519Verifier.verify_hash(message_hash, &envelope.public_key, &envelope.signature)
    }
}

/// The signature scheme a node is configured to accept (from
/// `--signature-scheme test-only|ed25519`). Dispatches envelope verification to
/// the selected concrete scheme, so the accepted algorithm is a single explicit
/// choice rather than trusting the envelope's self-declared algorithm.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SignatureSchemeKind {
    TestOnly,
    Ed25519,
}

impl SignatureSchemeKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::TestOnly => "test-only",
            Self::Ed25519 => "ed25519",
        }
    }

    /// Parse the `--signature-scheme` flag value.
    pub fn parse(value: &str) -> Result<Self, SignatureSchemeParseError> {
        match value {
            "test-only" => Ok(Self::TestOnly),
            "ed25519" => Ok(Self::Ed25519),
            other => Err(SignatureSchemeParseError(other.to_string())),
        }
    }

    pub fn algorithm(self) -> SignatureAlgorithm {
        match self {
            Self::TestOnly => SignatureAlgorithm::TestOnly,
            Self::Ed25519 => SignatureAlgorithm::Ed25519,
        }
    }

    pub fn verify_envelope(
        self,
        message_hash: Hash32,
        envelope: &SignatureEnvelope,
    ) -> Result<(), SignatureVerificationError> {
        match self {
            Self::TestOnly => TestOnlyScheme.verify_envelope(message_hash, envelope),
            Self::Ed25519 => Ed25519Scheme.verify_envelope(message_hash, envelope),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignatureSchemeParseError(pub String);

impl core::fmt::Display for SignatureSchemeParseError {
    fn fmt(&self, formatter: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        write!(
            formatter,
            "unknown signature scheme {:?}: expected \"test-only\" or \"ed25519\"",
            self.0
        )
    }
}

impl std::error::Error for SignatureSchemeParseError {}

pub fn transaction_signing_bytes(transaction: &Transaction) -> Vec<u8> {
    let mut output = canonical_preamble(DOMAIN_TRANSACTION_SIGNING);
    encode_transaction_without_signature(transaction, &mut output);
    output
}

pub fn transaction_signing_hash(transaction: &Transaction) -> Hash32 {
    sha256_hash(&transaction_signing_bytes(transaction))
}

pub fn transaction_bytes(transaction: &Transaction) -> Vec<u8> {
    let mut output = canonical_preamble(DOMAIN_TRANSACTION_HASH);
    encode_transaction_without_signature(transaction, &mut output);
    encode_signature(&transaction.signature, &mut output);
    output
}

pub fn transaction_hash(transaction: &Transaction) -> Hash32 {
    sha256_hash(&transaction_bytes(transaction))
}

pub fn transactions_root(transactions: &[Transaction]) -> Hash32 {
    let mut output = canonical_preamble(DOMAIN_TRANSACTIONS_ROOT);
    encode_u32(checked_len(transactions.len()), &mut output);
    for transaction in transactions {
        encode_hash(transaction_hash(transaction), &mut output);
    }
    sha256_hash(&output)
}

pub fn account_state_root(accounts: &[AccountStateEntry]) -> Hash32 {
    let mut sorted_accounts = accounts.to_vec();
    sorted_accounts.sort_by(|left, right| left.address.cmp(&right.address));

    let mut output = canonical_preamble(DOMAIN_ACCOUNT_STATE_ROOT);
    encode_u32(checked_len(sorted_accounts.len()), &mut output);
    for account in sorted_accounts {
        encode_string(account.address.as_str(), &mut output);
        encode_u128(account.balance.base_units(), &mut output);
        encode_u64(account.nonce, &mut output);
    }
    sha256_hash(&output)
}

pub fn block_header_signing_bytes(header: &BlockHeader) -> Vec<u8> {
    let mut output = canonical_preamble(DOMAIN_BLOCK_HEADER_SIGNING);
    encode_header_without_signature(header, &mut output);
    output
}

pub fn block_header_signing_hash(header: &BlockHeader) -> Hash32 {
    sha256_hash(&block_header_signing_bytes(header))
}

/// Verify a transaction's signature under an explicitly-selected scheme.
///
/// This applies the [`SignatureSchemeKind`] seam to a real [`Transaction`]: the
/// canonical `transaction_signing_hash` is the signed message, the transaction's
/// own `signature` bytes are the signature, and `public_key` is the signer's key
/// (empty and unused for the test-only scheme; the 32-byte Ed25519 public key for
/// `ed25519`). The accepted algorithm is `scheme` — never the envelope's
/// self-declared one — so a test-only signature can never pass an ed25519 node and
/// vice versa.
///
/// Verification is self-contained: the signer's `public_key` is read from the
/// transaction itself (empty and unused under the test-only scheme).
pub fn verify_transaction_with_scheme(
    scheme: SignatureSchemeKind,
    transaction: &Transaction,
) -> Result<(), SignatureVerificationError> {
    let envelope = SignatureEnvelope {
        algorithm: scheme.algorithm(),
        public_key: transaction.public_key.clone(),
        signature: transaction.signature.clone(),
    };
    scheme.verify_envelope(transaction_signing_hash(transaction), &envelope)
}

/// Verify a block header's producer signature under an explicitly-selected scheme.
///
/// The block-production analogue of [`verify_transaction_with_scheme`]: signs over
/// `block_header_signing_hash`, using the header's own `signature` and its own
/// producer `public_key` (empty for test-only).
pub fn verify_block_header_with_scheme(
    scheme: SignatureSchemeKind,
    header: &BlockHeader,
) -> Result<(), SignatureVerificationError> {
    let envelope = SignatureEnvelope {
        algorithm: scheme.algorithm(),
        public_key: header.public_key.clone(),
        signature: header.signature.clone(),
    };
    scheme.verify_envelope(block_header_signing_hash(header), &envelope)
}

/// A key that produces signatures under a specific [`SignatureSchemeKind`] — the
/// signing counterpart to [`verify_transaction_with_scheme`] /
/// [`verify_block_header_with_scheme`]. It yields both the `public_key` to place on
/// the signed object and the `signature`, and its `sign_transaction` /
/// `sign_block_header` helpers apply them in the correct order (public key first,
/// because it is part of the signed body).
///
/// `TestOnly` holds no key and produces the deterministic, non-secret placeholder
/// signature; `Ed25519` holds a real signing key. Real deployments load the ed25519
/// key from a gitignored key file / KMS, never from source.
pub enum SchemeSigner {
    TestOnly,
    Ed25519(Box<ed25519_dalek::SigningKey>),
}

impl SchemeSigner {
    /// A signer for a given scheme kind. For `Ed25519`, a signing key must be
    /// supplied (there is no key material for the test-only scheme).
    pub fn ed25519(signing_key: ed25519_dalek::SigningKey) -> Self {
        Self::Ed25519(Box::new(signing_key))
    }

    /// The scheme this signer produces signatures for.
    pub fn scheme(&self) -> SignatureSchemeKind {
        match self {
            Self::TestOnly => SignatureSchemeKind::TestOnly,
            Self::Ed25519(_) => SignatureSchemeKind::Ed25519,
        }
    }

    /// The public key to record on the signed object (empty for the test-only
    /// scheme, the 32-byte Ed25519 public key otherwise).
    pub fn public_key(&self) -> Vec<u8> {
        match self {
            Self::TestOnly => Vec::new(),
            Self::Ed25519(key) => ed25519_public_key(key).to_vec(),
        }
    }

    /// Sign a message hash under this signer's scheme.
    pub fn sign_hash(&self, message_hash: Hash32) -> SignatureBytes {
        match self {
            Self::TestOnly => test_only_signature_for_hash(message_hash),
            Self::Ed25519(key) => ed25519_sign_hash(key, message_hash),
        }
    }

    /// Sign a transaction in place: set its `public_key` (part of the signed body)
    /// then its `signature` over the canonical signing hash. The resulting
    /// transaction verifies under `verify_transaction_with_scheme(self.scheme(), …)`.
    pub fn sign_transaction(&self, transaction: &mut Transaction) {
        transaction.public_key = self.public_key();
        transaction.signature = self.sign_hash(transaction_signing_hash(transaction));
    }

    /// Sign a block header in place (the block-production analogue of
    /// [`sign_transaction`]).
    pub fn sign_block_header(&self, header: &mut BlockHeader) {
        header.public_key = self.public_key();
        header.signature = self.sign_hash(block_header_signing_hash(header));
    }
}

pub fn block_header_bytes(header: &BlockHeader) -> Vec<u8> {
    let mut output = canonical_preamble(DOMAIN_BLOCK_HEADER_HASH);
    encode_header_without_signature(header, &mut output);
    encode_signature(&header.signature, &mut output);
    output
}

pub fn block_header_hash(header: &BlockHeader) -> Hash32 {
    sha256_hash(&block_header_bytes(header))
}

pub fn block_hash(block: &Block) -> Hash32 {
    block_header_hash(&block.header)
}

/// SHA-256 digest of arbitrary bytes. Exposed for deriving stable identifiers
/// (for example peer node ids) outside the canonical block/transaction hashing;
/// callers should domain-separate their input to avoid cross-purpose collisions.
pub fn digest(bytes: &[u8]) -> Hash32 {
    sha256_hash(bytes)
}

fn canonical_preamble(domain: &[u8]) -> Vec<u8> {
    let mut output = Vec::new();
    encode_bytes(domain, &mut output);
    output
}

fn encode_transaction_without_signature(transaction: &Transaction, output: &mut Vec<u8>) {
    encode_u16(transaction.version, output);
    encode_string(&transaction.chain_id, output);
    encode_string(transaction.from.as_str(), output);
    encode_string(transaction.to.as_str(), output);
    encode_u128(transaction.amount.base_units(), output);
    encode_u128(transaction.fee.base_units(), output);
    encode_u64(transaction.nonce, output);
    encode_option_hash(transaction.memo_hash, output);
    encode_option_u64(transaction.expires_at_height, output);
    // The signer's public key is part of the signed body, so a signature is bound
    // to the key that produced it (empty under the test-only scheme).
    encode_bytes(&transaction.public_key, output);
}

fn encode_header_without_signature(header: &BlockHeader, output: &mut Vec<u8>) {
    encode_u16(header.version, output);
    encode_string(&header.chain_id, output);
    encode_u64(header.height, output);
    encode_hash(header.previous_block_hash, output);
    encode_hash(header.state_root, output);
    encode_hash(header.transactions_root, output);
    encode_u64(header.timestamp_ms, output);
    encode_string(header.producer.as_str(), output);
    encode_u64(header.consensus_round, output);
    // The producer's public key is part of the signed body (empty under the
    // test-only scheme).
    encode_bytes(&header.public_key, output);
}

fn encode_signature(signature: &SignatureBytes, output: &mut Vec<u8>) {
    encode_bytes(signature.as_slice(), output);
}

fn encode_option_hash(value: Option<Hash32>, output: &mut Vec<u8>) {
    match value {
        Some(hash) => {
            output.push(1);
            encode_hash(hash, output);
        }
        None => output.push(0),
    }
}

fn encode_option_u64(value: Option<u64>, output: &mut Vec<u8>) {
    match value {
        Some(number) => {
            output.push(1);
            encode_u64(number, output);
        }
        None => output.push(0),
    }
}

fn encode_hash(hash: Hash32, output: &mut Vec<u8>) {
    output.extend_from_slice(hash.as_bytes());
}

fn encode_string(value: &str, output: &mut Vec<u8>) {
    encode_bytes(value.as_bytes(), output);
}

fn encode_bytes(bytes: &[u8], output: &mut Vec<u8>) {
    encode_u32(checked_len(bytes.len()), output);
    output.extend_from_slice(bytes);
}

fn encode_u16(value: u16, output: &mut Vec<u8>) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn encode_u32(value: u32, output: &mut Vec<u8>) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn encode_u64(value: u64, output: &mut Vec<u8>) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn encode_u128(value: u128, output: &mut Vec<u8>) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn checked_len(len: usize) -> u32 {
    u32::try_from(len).expect("canonical encoding length exceeds u32")
}

fn sha256_hash(bytes: &[u8]) -> Hash32 {
    let digest = Sha256::digest(bytes);
    let mut output = [0; 32];
    output.copy_from_slice(&digest);
    Hash32::from_bytes(output)
}

#[cfg(test)]
mod tests {
    use super::*;
    use xriq_core::{
        AccountStateEntry, Address, Block, BlockHeader, SignatureBytes, Transaction, XriqAmount,
        PUBLIC_TESTNET_AUTHORITY_ADDRESS, PUBLIC_TESTNET_AUTHORITY_PUBKEY,
    };

    const ED25519_ADDRESS_GOLDEN: &str = "xriqdev1397e043c1939ff954726c0f3657a7a5093b33b89";

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn hash(byte: u8) -> Hash32 {
        Hash32::from_bytes([byte; 32])
    }

    fn transaction(signature: SignatureBytes) -> Transaction {
        Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from: address("alice"),
            to: address("bobbb"),
            amount: XriqAmount::from_base_units(25),
            fee: XriqAmount::from_base_units(2),
            nonce: 7,
            memo_hash: Some(hash(3)),
            expires_at_height: Some(100),
            signature,
            public_key: Vec::new(),
        }
    }

    fn signed_transaction() -> Transaction {
        let mut tx = transaction(SignatureBytes::new(Vec::new()));
        tx.signature = test_only_signature_for_hash(transaction_signing_hash(&tx));
        tx
    }

    fn header(signature: SignatureBytes) -> BlockHeader {
        BlockHeader {
            version: BlockHeader::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            height: 8,
            previous_block_hash: hash(1),
            state_root: hash(2),
            transactions_root: hash(3),
            timestamp_ms: 1_000,
            producer: address("author"),
            consensus_round: 0,
            signature,
            public_key: Vec::new(),
        }
    }

    #[test]
    fn signature_algorithm_ids_are_stable() {
        assert_eq!(SignatureAlgorithm::TestOnly.id(), 0);
        assert_eq!(SignatureAlgorithm::Ed25519.id(), 1);
        assert_eq!(
            SignatureAlgorithm::from_id(2),
            Ok(SignatureAlgorithm::Secp256k1)
        );
        assert_eq!(
            SignatureAlgorithm::from_id(99),
            Err(SignatureAlgorithmError::UnknownAlgorithmId(99))
        );
    }

    #[test]
    fn transaction_signing_hash_excludes_signature() {
        let first = transaction(SignatureBytes::new(vec![1]));
        let second = transaction(SignatureBytes::new(vec![2, 3]));

        assert_eq!(
            transaction_signing_bytes(&first),
            transaction_signing_bytes(&second)
        );
        assert_eq!(
            transaction_signing_hash(&first),
            transaction_signing_hash(&second)
        );
        assert_ne!(transaction_hash(&first), transaction_hash(&second));
    }

    #[test]
    fn transaction_hash_changes_when_canonical_field_changes() {
        let first = signed_transaction();
        let mut second = first.clone();
        second.amount = XriqAmount::from_base_units(26);
        second.signature = test_only_signature_for_hash(transaction_signing_hash(&second));

        assert_ne!(
            transaction_signing_hash(&first),
            transaction_signing_hash(&second)
        );
        assert_ne!(transaction_hash(&first), transaction_hash(&second));
    }

    #[test]
    fn public_key_is_bound_into_transaction_and_header_hashes() {
        // The public key is part of the signed body: changing it changes both the
        // signing hash and the item hash, so a signature is bound to its key.
        let first = signed_transaction();
        let mut second = first.clone();
        second.public_key = vec![7u8; 32];
        assert_ne!(
            transaction_signing_hash(&first),
            transaction_signing_hash(&second)
        );
        assert_ne!(transaction_hash(&first), transaction_hash(&second));

        let first_header = header(SignatureBytes::new(vec![1]));
        let mut second_header = first_header.clone();
        second_header.public_key = vec![7u8; 32];
        assert_ne!(
            block_header_signing_hash(&first_header),
            block_header_signing_hash(&second_header)
        );
        assert_ne!(
            block_header_bytes(&first_header),
            block_header_bytes(&second_header)
        );
    }

    #[test]
    fn transaction_root_is_order_sensitive() {
        let first = signed_transaction();
        let mut second = first.clone();
        second.nonce = 8;
        second.signature = test_only_signature_for_hash(transaction_signing_hash(&second));

        assert_ne!(
            transactions_root(&[first.clone(), second.clone()]),
            transactions_root(&[second, first])
        );
        assert_ne!(transactions_root(&[]), Hash32::ZERO);
    }

    #[test]
    fn account_state_root_is_account_order_insensitive() {
        let first = AccountStateEntry::new(address("alice"), XriqAmount::from_base_units(100), 0);
        let second = AccountStateEntry::new(address("bobbb"), XriqAmount::from_base_units(25), 2);

        assert_eq!(
            account_state_root(&[first.clone(), second.clone()]),
            account_state_root(&[second, first])
        );
        assert_ne!(account_state_root(&[]), Hash32::ZERO);
    }

    #[test]
    fn account_state_root_changes_when_state_changes() {
        let first = AccountStateEntry::new(address("alice"), XriqAmount::from_base_units(100), 0);
        let mut second = first.clone();
        second.nonce = 1;

        assert_ne!(account_state_root(&[first]), account_state_root(&[second]));
    }

    #[test]
    fn block_header_signing_hash_excludes_signature() {
        let first = header(SignatureBytes::new(vec![1]));
        let second = header(SignatureBytes::new(vec![2, 3]));

        assert_eq!(
            block_header_signing_hash(&first),
            block_header_signing_hash(&second)
        );
        assert_ne!(block_header_hash(&first), block_header_hash(&second));
    }

    #[test]
    fn block_hash_is_header_hash() {
        let tx = signed_transaction();
        let mut block_header = header(SignatureBytes::new(Vec::new()));
        block_header.transactions_root = transactions_root(std::slice::from_ref(&tx));
        block_header.signature =
            test_only_signature_for_hash(block_header_signing_hash(&block_header));
        let block = Block {
            header: block_header,
            transactions: vec![tx],
        };

        assert_eq!(block_hash(&block), block_header_hash(&block.header));
    }

    #[test]
    fn test_only_verifier_accepts_hash_bound_signature() {
        let verifier = TestOnlySignatureVerifier;
        let tx = signed_transaction();

        assert_eq!(verifier.verify_transaction(&tx), Ok(()));

        let mut tampered = tx.clone();
        tampered.fee = XriqAmount::from_base_units(3);
        assert_eq!(
            verifier.verify_transaction(&tampered),
            Err(SignatureVerificationError::InvalidSignature)
        );
    }

    #[test]
    fn test_only_verifier_rejects_non_test_algorithm_envelope() {
        let verifier = TestOnlySignatureVerifier;
        let hash = hash(9);
        let envelope = SignatureEnvelope {
            algorithm: SignatureAlgorithm::Ed25519,
            public_key: vec![1, 2, 3],
            signature: test_only_signature_for_hash(hash),
        };

        assert_eq!(
            verifier.verify_envelope(hash, &envelope),
            Err(SignatureVerificationError::UnsupportedAlgorithm)
        );
    }

    #[test]
    fn test_only_verifier_rejects_empty_signature() {
        assert_eq!(
            TestOnlySignatureVerifier.verify_hash(hash(1), &SignatureBytes::new(Vec::new())),
            Err(SignatureVerificationError::MissingSignature)
        );
    }

    #[test]
    fn ed25519_sign_verify_roundtrip_and_rejects_tampering() {
        let signing_key = ed25519_signing_key_from_seed([7u8; 32]);
        let public_key = ed25519_public_key(&signing_key);
        let message = hash(1);
        let signature = ed25519_sign_hash(&signing_key, message);
        let verifier = Ed25519Verifier;

        // A genuine signature verifies.
        assert_eq!(
            verifier.verify_hash(message, &public_key, &signature),
            Ok(())
        );

        // A different message is rejected.
        assert_eq!(
            verifier.verify_hash(hash(2), &public_key, &signature),
            Err(SignatureVerificationError::InvalidSignature)
        );

        // The wrong public key is rejected.
        let other_key = ed25519_public_key(&ed25519_signing_key_from_seed([8u8; 32]));
        assert_eq!(
            verifier.verify_hash(message, &other_key, &signature),
            Err(SignatureVerificationError::InvalidSignature)
        );

        // A tampered signature (one flipped byte) is rejected.
        let mut tampered = signature.as_slice().to_vec();
        tampered[0] ^= 0xff;
        assert_eq!(
            verifier.verify_hash(message, &public_key, &SignatureBytes::new(tampered)),
            Err(SignatureVerificationError::InvalidSignature)
        );

        // Malformed key/signature lengths are rejected, never a panic.
        assert_eq!(
            verifier.verify_hash(message, &public_key[..31], &signature),
            Err(SignatureVerificationError::InvalidSignature)
        );
        assert_eq!(
            verifier.verify_hash(message, &public_key, &SignatureBytes::new(vec![0u8; 10])),
            Err(SignatureVerificationError::InvalidSignature)
        );
        assert_eq!(
            verifier.verify_hash(message, &public_key, &SignatureBytes::new(Vec::new())),
            Err(SignatureVerificationError::MissingSignature)
        );
    }

    #[test]
    fn ed25519_keys_and_signatures_are_deterministic() {
        // Ed25519 is deterministic: same seed => same key and same signature.
        let a = ed25519_signing_key_from_seed([3u8; 32]);
        let b = ed25519_signing_key_from_seed([3u8; 32]);
        assert_eq!(ed25519_public_key(&a), ed25519_public_key(&b));
        let message = hash(9);
        assert_eq!(
            ed25519_sign_hash(&a, message),
            ed25519_sign_hash(&b, message)
        );
    }

    #[test]
    fn ed25519_address_is_key_derived_deterministic_and_valid() {
        let public_key = ed25519_public_key(&ed25519_signing_key_from_seed([5u8; 32]));
        let address = ed25519_address(&public_key);

        // A pure function of the public key (deterministic).
        assert_eq!(ed25519_address(&public_key), address);

        // A different key yields a different address.
        let other_key = ed25519_public_key(&ed25519_signing_key_from_seed([6u8; 32]));
        assert_ne!(ed25519_address(&other_key), address);

        // Canonical format: xriqdev1 prefix + 40 hex-char (20-byte) payload that
        // round-trips through Address parsing.
        assert!(address.as_str().starts_with("xriqdev1"));
        assert_eq!(address.as_str().len(), "xriqdev1".len() + 40);
        assert_eq!(Address::parse(address.as_str()).unwrap(), address);

        // Golden vector: the derivation is stable across builds (a change here is
        // a deliberate address-scheme change).
        assert_eq!(ed25519_address(&[0u8; 32]).as_str(), ED25519_ADDRESS_GOLDEN);
    }

    #[test]
    fn public_testnet_authority_address_is_key_derived() {
        // Binds the genesis authority address to its public key. xriq-core holds
        // both constants (it cannot depend on xriq-crypto); this test enforces the
        // invariant `authority == ed25519_address(authority_pubkey)`.
        assert_eq!(
            ed25519_address(&PUBLIC_TESTNET_AUTHORITY_PUBKEY).as_str(),
            PUBLIC_TESTNET_AUTHORITY_ADDRESS
        );
    }

    fn test_only_envelope(message: Hash32) -> SignatureEnvelope {
        SignatureEnvelope {
            algorithm: SignatureAlgorithm::TestOnly,
            public_key: Vec::new(),
            signature: test_only_signature_for_hash(message),
        }
    }

    fn ed25519_envelope(seed: [u8; 32], message: Hash32) -> SignatureEnvelope {
        let key = ed25519_signing_key_from_seed(seed);
        SignatureEnvelope {
            algorithm: SignatureAlgorithm::Ed25519,
            public_key: ed25519_public_key(&key).to_vec(),
            signature: ed25519_sign_hash(&key, message),
        }
    }

    #[test]
    fn signature_schemes_verify_matching_envelopes_and_reject_mismatches() {
        let message = hash(4);
        let test_env = test_only_envelope(message);
        let ed_env = ed25519_envelope([9u8; 32], message);

        // Each scheme verifies its own algorithm.
        assert_eq!(TestOnlyScheme.verify_envelope(message, &test_env), Ok(()));
        assert_eq!(Ed25519Scheme.verify_envelope(message, &ed_env), Ok(()));

        // Each rejects the other algorithm as unsupported (never mis-verifies).
        assert_eq!(
            TestOnlyScheme.verify_envelope(message, &ed_env),
            Err(SignatureVerificationError::UnsupportedAlgorithm)
        );
        assert_eq!(
            Ed25519Scheme.verify_envelope(message, &test_env),
            Err(SignatureVerificationError::UnsupportedAlgorithm)
        );

        // Ed25519 rejects a tampered signature and a wrong message.
        let mut sig_bytes = ed_env.signature.as_slice().to_vec();
        sig_bytes[0] ^= 0xff;
        let tampered = SignatureEnvelope {
            algorithm: ed_env.algorithm,
            public_key: ed_env.public_key.clone(),
            signature: SignatureBytes::new(sig_bytes),
        };
        assert_eq!(
            Ed25519Scheme.verify_envelope(message, &tampered),
            Err(SignatureVerificationError::InvalidSignature)
        );
        assert_eq!(
            Ed25519Scheme.verify_envelope(hash(5), &ed_env),
            Err(SignatureVerificationError::InvalidSignature)
        );
    }

    #[test]
    fn signature_scheme_kind_parses_and_dispatches() {
        assert_eq!(
            SignatureSchemeKind::parse("test-only"),
            Ok(SignatureSchemeKind::TestOnly)
        );
        assert_eq!(
            SignatureSchemeKind::parse("ed25519"),
            Ok(SignatureSchemeKind::Ed25519)
        );
        assert!(SignatureSchemeKind::parse("rsa").is_err());
        assert_eq!(SignatureSchemeKind::TestOnly.as_str(), "test-only");
        assert_eq!(SignatureSchemeKind::Ed25519.as_str(), "ed25519");

        // The configured kind only accepts its own algorithm's envelopes.
        let message = hash(7);
        let test_env = test_only_envelope(message);
        let ed_env = ed25519_envelope([2u8; 32], message);
        assert_eq!(
            SignatureSchemeKind::TestOnly.verify_envelope(message, &test_env),
            Ok(())
        );
        assert_eq!(
            SignatureSchemeKind::Ed25519.verify_envelope(message, &ed_env),
            Ok(())
        );
        assert_eq!(
            SignatureSchemeKind::TestOnly.verify_envelope(message, &ed_env),
            Err(SignatureVerificationError::UnsupportedAlgorithm)
        );
        assert_eq!(
            SignatureSchemeKind::Ed25519.verify_envelope(message, &test_env),
            Err(SignatureVerificationError::UnsupportedAlgorithm)
        );
    }

    /// Build a transaction whose `signature` is a real Ed25519 signature over its
    /// canonical signing hash, with its `public_key` set to the signer's key.
    fn ed25519_signed_transaction(seed: [u8; 32]) -> Transaction {
        let key = ed25519_signing_key_from_seed(seed);
        let mut tx = transaction(SignatureBytes::new(Vec::new()));
        // public_key is part of the signed body, so it must be set before signing.
        tx.public_key = ed25519_public_key(&key).to_vec();
        tx.signature = ed25519_sign_hash(&key, transaction_signing_hash(&tx));
        tx
    }

    fn ed25519_signed_header(seed: [u8; 32]) -> BlockHeader {
        let key = ed25519_signing_key_from_seed(seed);
        let mut header = header(SignatureBytes::new(Vec::new()));
        // public_key is part of the signed body, so it must be set before signing.
        header.public_key = ed25519_public_key(&key).to_vec();
        header.signature = ed25519_sign_hash(&key, block_header_signing_hash(&header));
        header
    }

    #[test]
    fn verify_transaction_with_scheme_accepts_only_the_configured_scheme() {
        // A test-only-signed transaction verifies under the test-only scheme
        // (empty public key, unused) and is rejected under ed25519.
        let test_tx = signed_transaction();
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::TestOnly, &test_tx),
            Ok(())
        );
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::Ed25519, &test_tx),
            Err(SignatureVerificationError::InvalidSignature)
        );

        // An ed25519-signed transaction carries its own key and verifies under
        // ed25519.
        let ed_tx = ed25519_signed_transaction([11u8; 32]);
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::Ed25519, &ed_tx),
            Ok(())
        );

        // Wrong public key, tampered body, and the test-only scheme all reject it.
        let mut wrong_key = ed_tx.clone();
        wrong_key.public_key = ed25519_signed_transaction([12u8; 32]).public_key;
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::Ed25519, &wrong_key),
            Err(SignatureVerificationError::InvalidSignature)
        );
        let mut tampered = ed_tx.clone();
        tampered.amount = XriqAmount::from_base_units(999);
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::Ed25519, &tampered),
            Err(SignatureVerificationError::InvalidSignature)
        );
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::TestOnly, &ed_tx),
            Err(SignatureVerificationError::InvalidSignature)
        );
    }

    #[test]
    fn verify_block_header_with_scheme_accepts_only_the_configured_scheme() {
        let ed_header = ed25519_signed_header([21u8; 32]);
        assert_eq!(
            verify_block_header_with_scheme(SignatureSchemeKind::Ed25519, &ed_header),
            Ok(())
        );

        // Tampered header body is rejected.
        let mut tampered = ed_header.clone();
        tampered.height += 1;
        assert_eq!(
            verify_block_header_with_scheme(SignatureSchemeKind::Ed25519, &tampered),
            Err(SignatureVerificationError::InvalidSignature)
        );

        // A test-only-signed header verifies under the test-only scheme only.
        let mut test_header = header(SignatureBytes::new(Vec::new()));
        test_header.signature =
            test_only_signature_for_hash(block_header_signing_hash(&test_header));
        assert_eq!(
            verify_block_header_with_scheme(SignatureSchemeKind::TestOnly, &test_header),
            Ok(())
        );
        assert_eq!(
            verify_block_header_with_scheme(SignatureSchemeKind::Ed25519, &test_header),
            Err(SignatureVerificationError::InvalidSignature)
        );
    }

    #[test]
    fn scheme_signer_produces_signatures_that_verify_under_its_own_scheme() {
        // Test-only signer: empty public key, verifies under test-only, rejected
        // under ed25519.
        let test_signer = SchemeSigner::TestOnly;
        assert_eq!(test_signer.scheme(), SignatureSchemeKind::TestOnly);
        assert!(test_signer.public_key().is_empty());
        let mut tx = transaction(SignatureBytes::new(Vec::new()));
        test_signer.sign_transaction(&mut tx);
        assert!(tx.public_key.is_empty());
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::TestOnly, &tx),
            Ok(())
        );
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::Ed25519, &tx),
            Err(SignatureVerificationError::InvalidSignature)
        );

        // Ed25519 signer: records its public key, verifies under ed25519, rejected
        // under test-only. sign_transaction/sign_block_header set the key before
        // signing, so the result is self-contained and verifies.
        let key = ed25519_signing_key_from_seed([5u8; 32]);
        let signer = SchemeSigner::ed25519(key.clone());
        assert_eq!(signer.scheme(), SignatureSchemeKind::Ed25519);
        assert_eq!(signer.public_key(), ed25519_public_key(&key).to_vec());

        let mut ed_tx = transaction(SignatureBytes::new(Vec::new()));
        signer.sign_transaction(&mut ed_tx);
        assert_eq!(ed_tx.public_key, ed25519_public_key(&key).to_vec());
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::Ed25519, &ed_tx),
            Ok(())
        );
        assert_eq!(
            verify_transaction_with_scheme(SignatureSchemeKind::TestOnly, &ed_tx),
            Err(SignatureVerificationError::InvalidSignature)
        );

        let mut ed_header = header(SignatureBytes::new(Vec::new()));
        signer.sign_block_header(&mut ed_header);
        assert_eq!(ed_header.public_key, ed25519_public_key(&key).to_vec());
        assert_eq!(
            verify_block_header_with_scheme(SignatureSchemeKind::Ed25519, &ed_header),
            Ok(())
        );
    }
}
