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

/// What a transaction *does*. A plain value [`TxAction::Transfer`] is the default
/// and the only shape that moves the native unit. The governance variants carry no
/// value — they mutate the on-chain authorized-wallet registry and are accepted only
/// from the chain authority (gating is enforced at the node layers, mirroring the
/// sender↔key binding). All of this is test-only and valueless; the registry gates a
/// clearly-valueless test counter-asset flow, never anything value-bearing.
///
/// # Canonical encoding stability
/// [`TxAction::Transfer`] must encode to *zero* trailing bytes so that every existing
/// transfer keeps a byte-identical signing/hash preimage (and thus an unchanged
/// `transactions_root`); only the governance variants contribute bytes. See
/// `xriq_crypto::encode_transaction_without_signature`.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub enum TxAction {
    /// Move `amount` of the native unit from `from` to `to` (the classic transfer).
    #[default]
    Transfer,
    /// Authority-only: add `target` to the on-chain authorized-wallet registry.
    /// Idempotent — authorizing an already-authorized wallet is a no-op.
    AuthorizeWallet { target: Address },
    /// Authority-only: remove `target` from the authorized-wallet registry.
    /// Idempotent — revoking a wallet that is not authorized is a no-op.
    RevokeWallet { target: Address },
    /// A two-party swap of the native unit for the (clearly valueless, test-only)
    /// counter-asset, applied atomically only if BOTH parties are in the
    /// authorized-wallet registry. The native leg moves `amount` from `from` to `to`;
    /// the counter leg moves `counter_amount` of the counter-asset from `to` back to
    /// `from`. `from` alone signs — there is NO counterparty signature, which is
    /// acceptable only because both the native unit and the counter-asset are
    /// valueless test units gated by an operator-controlled allowlist; a value-bearing
    /// swap would require real atomic-swap / co-signing semantics.
    Swap { counter_amount: u128 },
}

impl TxAction {
    /// The wallet a governance action targets, if any (`None` for [`Self::Transfer`]
    /// and [`Self::Swap`], which are not registry mutations).
    pub fn governance_target(&self) -> Option<&Address> {
        match self {
            Self::Transfer | Self::Swap { .. } => None,
            Self::AuthorizeWallet { target } | Self::RevokeWallet { target } => Some(target),
        }
    }

    /// Whether this action is an authority-only registry mutation (authorize/revoke).
    /// These are authority-gated at the node. A [`Self::Swap`] is NOT governance — it
    /// is gated on registry membership of both parties, not on the sender being the
    /// authority — so it is excluded here.
    pub fn is_governance(&self) -> bool {
        matches!(
            self,
            Self::AuthorizeWallet { .. } | Self::RevokeWallet { .. }
        )
    }

    /// Whether this action is a two-party counter-asset swap.
    pub fn is_swap(&self) -> bool {
        matches!(self, Self::Swap { .. })
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
    /// What the transaction does. [`TxAction::Transfer`] (the default) is a plain
    /// value transfer; the governance variants mutate the authorized-wallet registry
    /// and are accepted only from the chain authority. Encoded to zero trailing bytes
    /// for `Transfer`, so existing transfer hashes are unchanged.
    pub action: TxAction,
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
    InvalidNonce {
        expected: u64,
        actual: u64,
    },
    InsufficientFunds,
    Expired,
    MissingSignature,
    /// A governance action (registry authorize/revoke) carried a non-zero `amount`.
    /// Governance transactions are valueless: they may pay a fee but move no units.
    GovernanceMustBeValueless,
    /// A governance action was not self-addressed (`to != from`). Governance
    /// transactions carry their target inside the action, so the recipient field is
    /// required to equal the sender, keeping the envelope unambiguous.
    GovernanceRecipientNotSelf,
    /// A swap carried a zero counter-asset amount. A swap must move value on both
    /// legs (native `amount` one way, `counter_amount` the other); the native side is
    /// covered by the existing `ZeroAmount` / `SelfTransfer` checks.
    SwapZeroCounterAmount,
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
        // Shape checks split by action. The transfer path is byte-for-byte the
        // historical validation (self-transfer + non-zero amount); governance
        // transactions carry no value and are self-addressed (the target lives in the
        // action), so they invert those two rules. Every other check below is shared.
        match &self.action {
            TxAction::Transfer => {
                if self.from == self.to {
                    return Err(TransactionValidationError::SelfTransfer);
                }
                if self.amount.is_zero() {
                    return Err(TransactionValidationError::ZeroAmount);
                }
            }
            TxAction::AuthorizeWallet { .. } | TxAction::RevokeWallet { .. } => {
                if self.from != self.to {
                    return Err(TransactionValidationError::GovernanceRecipientNotSelf);
                }
                if !self.amount.is_zero() {
                    return Err(TransactionValidationError::GovernanceMustBeValueless);
                }
            }
            TxAction::Swap { counter_amount } => {
                // A swap has two distinct parties and moves value on both legs. The
                // both-parties-approved registry gate is enforced where the ledger
                // state is available (submit + apply), not here.
                if self.from == self.to {
                    return Err(TransactionValidationError::SelfTransfer);
                }
                if self.amount.is_zero() {
                    return Err(TransactionValidationError::ZeroAmount);
                }
                if *counter_amount == 0 {
                    return Err(TransactionValidationError::SwapZeroCounterAmount);
                }
            }
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
            action: Default::default(),
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
