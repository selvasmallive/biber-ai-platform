use crate::{Address, Hash32, XriqAmount};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SignatureBytes(Vec<u8>);

impl SignatureBytes {
    pub fn new(bytes: Vec<u8>) -> Self {
        Self(bytes)
    }

    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    pub fn as_slice(&self) -> &[u8] {
        &self.0
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Transaction {
    pub version: u16,
    pub chain_id: String,
    pub from: Address,
    pub to: Address,
    pub amount: XriqAmount,
    pub fee: XriqAmount,
    pub nonce: u64,
    pub memo_hash: Option<Hash32>,
    pub expires_at_height: Option<u64>,
    pub signature: SignatureBytes,
    /// The signer's public key, for self-contained signature verification.
    /// Empty under the test-only scheme (which needs no key); the 32-byte
    /// Ed25519 public key once signed by the production scheme. Part of the
    /// production-crypto migration (Phase 3b); see
    /// `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`.
    pub public_key: Vec<u8>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AccountView {
    pub balance: XriqAmount,
    pub nonce: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TransactionValidationContext {
    pub chain_id: String,
    pub sender: AccountView,
    pub current_height: u64,
    pub min_fee: XriqAmount,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum TransactionValidationError {
    UnsupportedVersion,
    WrongChainId,
    SelfTransfer,
    ZeroAmount,
    FeeTooLow,
    InvalidNonce { expected: u64, actual: u64 },
    InsufficientFunds,
    Expired,
    MissingSignature,
}

impl Transaction {
    pub const SUPPORTED_VERSION: u16 = 1;

    pub fn total_debit(&self) -> Option<XriqAmount> {
        self.amount.checked_add(self.fee)
    }

    pub fn validate_basic(
        &self,
        context: &TransactionValidationContext,
    ) -> Result<(), TransactionValidationError> {
        if self.version != Self::SUPPORTED_VERSION {
            return Err(TransactionValidationError::UnsupportedVersion);
        }
        if self.chain_id != context.chain_id {
            return Err(TransactionValidationError::WrongChainId);
        }
        if self.from == self.to {
            return Err(TransactionValidationError::SelfTransfer);
        }
        if self.amount.is_zero() {
            return Err(TransactionValidationError::ZeroAmount);
        }
        if self.fee < context.min_fee {
            return Err(TransactionValidationError::FeeTooLow);
        }
        if self.nonce != context.sender.nonce {
            return Err(TransactionValidationError::InvalidNonce {
                expected: context.sender.nonce,
                actual: self.nonce,
            });
        }
        if self
            .expires_at_height
            .is_some_and(|height| height <= context.current_height)
        {
            return Err(TransactionValidationError::Expired);
        }
        let total_debit = self
            .total_debit()
            .ok_or(TransactionValidationError::InsufficientFunds)?;
        if context.sender.balance < total_debit {
            return Err(TransactionValidationError::InsufficientFunds);
        }
        if self.signature.is_empty() {
            return Err(TransactionValidationError::MissingSignature);
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn address(label: &str) -> Address {
        Address::parse(&format!("xriqdev1{label}00000000000")).unwrap()
    }

    fn signed_transfer() -> Transaction {
        Transaction {
            version: Transaction::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            from: address("alice"),
            to: address("bobbb"),
            amount: XriqAmount::from_base_units(10),
            fee: XriqAmount::from_base_units(1),
            nonce: 7,
            memo_hash: None,
            expires_at_height: Some(100),
            signature: SignatureBytes::new(vec![1, 2, 3]),
            public_key: Vec::new(),
        }
    }

    fn context() -> TransactionValidationContext {
        TransactionValidationContext {
            chain_id: "xriq-devnet".to_string(),
            sender: AccountView {
                balance: XriqAmount::from_base_units(20),
                nonce: 7,
            },
            current_height: 50,
            min_fee: XriqAmount::from_base_units(1),
        }
    }

    #[test]
    fn accepts_valid_transfer_shape() {
        assert_eq!(signed_transfer().validate_basic(&context()), Ok(()));
    }

    #[test]
    fn rejects_zero_amount() {
        let mut tx = signed_transfer();
        tx.amount = XriqAmount::ZERO;
        assert_eq!(
            tx.validate_basic(&context()),
            Err(TransactionValidationError::ZeroAmount)
        );
    }

    #[test]
    fn rejects_bad_nonce_with_expected_value() {
        let mut tx = signed_transfer();
        tx.nonce = 8;
        assert_eq!(
            tx.validate_basic(&context()),
            Err(TransactionValidationError::InvalidNonce {
                expected: 7,
                actual: 8
            })
        );
    }

    #[test]
    fn rejects_insufficient_funds() {
        let mut context = context();
        context.sender.balance = XriqAmount::from_base_units(10);
        assert_eq!(
            signed_transfer().validate_basic(&context),
            Err(TransactionValidationError::InsufficientFunds)
        );
    }
}
