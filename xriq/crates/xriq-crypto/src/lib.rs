//! Canonical hashing and crypto-agility boundaries for XRIQ.
//!
//! This crate uses reviewed hashing primitives from dependencies and keeps the
//! current fake private-devnet signature behavior behind an explicit test-only
//! verifier. It now also provides a production Ed25519 verification primitive
//! (`Ed25519Verifier`, via the audited `ed25519-dalek`) as Phase 1 of the
//! production-crypto migration (`docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`); that
//! primitive is NOT yet wired into the node/consensus/wallet, and this crate still
//! provides no production key custody.

use sha2::{Digest, Sha256};
use xriq_core::{AccountStateEntry, Block, BlockHeader, Hash32, SignatureBytes, Transaction};

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
    };

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
}
