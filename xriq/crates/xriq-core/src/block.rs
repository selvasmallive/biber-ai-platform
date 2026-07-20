use crate::{Address, Hash32, SignatureBytes, Transaction};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BlockHeader {
    pub version: u16,
    pub chain_id: String,
    pub height: u64,
    pub previous_block_hash: Hash32,
    pub state_root: Hash32,
    pub transactions_root: Hash32,
    pub timestamp_ms: u64,
    pub producer: Address,
    pub consensus_round: u64,
    pub signature: SignatureBytes,
    /// The block producer's public key, for self-contained signature
    /// verification. Empty under the test-only scheme; the 32-byte Ed25519
    /// public key once signed by the production scheme. Part of the
    /// production-crypto migration (Phase 3b); see
    /// `docs/XRIQ_PRODUCTION_CRYPTO_MIGRATION.md`.
    pub public_key: Vec<u8>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Block {
    pub header: BlockHeader,
    pub transactions: Vec<Transaction>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParentHeaderView {
    pub chain_id: String,
    pub height: u64,
    pub block_hash: Hash32,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum BlockValidationError {
    UnsupportedVersion,
    WrongChainId,
    InvalidHeight { expected: u64, actual: u64 },
    HeightOverflow,
    WrongPreviousHash,
    MissingSignature,
}

impl BlockHeader {
    pub const SUPPORTED_VERSION: u16 = 1;

    pub fn validate_against_parent(
        &self,
        parent: &ParentHeaderView,
    ) -> Result<(), BlockValidationError> {
        if self.version != Self::SUPPORTED_VERSION {
            return Err(BlockValidationError::UnsupportedVersion);
        }
        if self.chain_id != parent.chain_id {
            return Err(BlockValidationError::WrongChainId);
        }
        let expected_height = parent
            .height
            .checked_add(1)
            .ok_or(BlockValidationError::HeightOverflow)?;
        if self.height != expected_height {
            return Err(BlockValidationError::InvalidHeight {
                expected: expected_height,
                actual: self.height,
            });
        }
        if self.previous_block_hash != parent.block_hash {
            return Err(BlockValidationError::WrongPreviousHash);
        }
        if self.signature.is_empty() {
            return Err(BlockValidationError::MissingSignature);
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn producer() -> Address {
        Address::parse("xriqdev1producer00000000").unwrap()
    }

    fn parent() -> ParentHeaderView {
        ParentHeaderView {
            chain_id: "xriq-devnet".to_string(),
            height: 41,
            block_hash: Hash32::from_bytes([9; 32]),
        }
    }

    fn header() -> BlockHeader {
        BlockHeader {
            version: BlockHeader::SUPPORTED_VERSION,
            chain_id: "xriq-devnet".to_string(),
            height: 42,
            previous_block_hash: Hash32::from_bytes([9; 32]),
            state_root: Hash32::from_bytes([1; 32]),
            transactions_root: Hash32::from_bytes([2; 32]),
            timestamp_ms: 1_000,
            producer: producer(),
            consensus_round: 0,
            signature: SignatureBytes::new(vec![1, 2, 3]),
            public_key: Vec::new(),
        }
    }

    #[test]
    fn validates_header_against_parent() {
        assert_eq!(header().validate_against_parent(&parent()), Ok(()));
    }

    #[test]
    fn rejects_wrong_height() {
        let mut header = header();
        header.height = 43;
        assert_eq!(
            header.validate_against_parent(&parent()),
            Err(BlockValidationError::InvalidHeight {
                expected: 42,
                actual: 43
            })
        );
    }

    #[test]
    fn rejects_wrong_parent_hash() {
        let mut header = header();
        header.previous_block_hash = Hash32::ZERO;
        assert_eq!(
            header.validate_against_parent(&parent()),
            Err(BlockValidationError::WrongPreviousHash)
        );
    }
}
